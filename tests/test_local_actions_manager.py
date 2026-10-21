"""
Local actions of mirrors through the Manager (MIR-02, D-02, D-07, D-21).

`test_pending_mirror_with_persisted_additive_record_gains_local_branch` is the only expected-RED test of Phase 11
(11-VALIDATION.md, "Expected-RED Exception"). It was committed by Plan 11-01 Task 2 before the Manager reads the
separate local Store; its GREEN gate is Plan 11-05 Task 1, which may align the seeded record to the Plan 11-04 schema
but never changes an assertion. No marker or condition ever hides its failure.
"""

import asyncio
import copy
import functools
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions import const as const_module
from custom_components.mqtt_actions import retrigger as retrigger_module
from custom_components.mqtt_actions.const import (
    CONF_DELETE_DEVICES_ON_REMOVE,
    DOMAIN,
    ISSUE_CIRCUIT_BREAKER_PREFIX,
    MODE_DISABLED,
    MODE_OBSERVE,
    PAYLOAD_OFF,
    PAYLOAD_ON,
    RUN_MODE_RESTART,
    STORE_MIRRORS,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.document import escape_markdown
from custom_components.mqtt_actions.local_actions import (
    LOCAL_SAFE_POLICY,
    BranchOutcome,
    EffectivePolicy,
    LocalActionMode,
    OutcomeStatus,
    local_trigger_identity,
)
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore
from custom_components.mqtt_actions.manager import LocalActionError, Manager
from custom_components.mqtt_actions.model import trigger_key
from custom_components.mqtt_actions.mqtt_gateway import IncomingMessage
from custom_components.mqtt_actions.retrigger import RetriggerRequest
from custom_components.mqtt_actions.topics import state_topic
from tests.documents import document_payload, make_spec
from tests.helpers import BASE, deliver_config, manager_of, restart_entry, seed_store, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.model import DeviceSpec

# Literal on purpose: Plan 11-04 declares LOCAL_ACTIONS_STORE_KEY with this value
LOCAL_STORE_KEY = "mqtt_actions.local_actions"


def _seed_local_store(hass_storage: dict[str, Any], records: list[dict[str, Any]]) -> None:
    """Write local records as an HA Store v1 envelope under the production local key."""
    hass_storage[LOCAL_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_STORE_KEY,
        "data": {"records": records},
    }


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_pending_mirror_with_persisted_additive_record_gains_local_branch(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """
    D-02: a saved additive record runs its trusted local actions on a pending mirror; the owner branch stays out.

    Expected RED until Plan 11-05 Task 1: today the Manager ignores the separate local Store and refuses the whole
    pending mirror, so neither the local nor the owner service runs and the local call count is 0 instead of 1.
    """
    owner_calls = async_mock_service(hass, "test", "owner_on")
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=[{"action": "test.owner_on"}], off=[{"action": "test.owner_off"}])
    _seed_local_store(
        hass_storage,
        [
            {
                "device_id": spec.device_id,
                "kind": SUBENTRY_SWITCH,
                "state_value": PAYLOAD_ON,
                "label": "On",
                "mode": "additive",
                "actions": [{"action": "test.local_on", "data": {"source": "local"}}],
            }
        ],
    )
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    manager = manager_of(entry)
    assert str(manager.approval_state(spec.device_id)) == "pending", "premise: the owner actions are not approved"

    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)

    assert len(local_calls) == 1, f"the local branch of the pending mirror ran {len(local_calls)} times, expected 1"
    assert owner_calls == [], "the unapproved owner branch must never run"
    assert str(manager.approval_state(spec.device_id)) == "pending", "local actions never approve the owner"


# --- Plan 11-05 Task 1: load before mirrors, restart, orphan-only records (D-05, D-07, D-22) --------------------------

# A device id of the valid shape that no mirror and no subentry uses
ORPHAN_DEVICE = "0f0e0d0c-0b0a-4908-8706-050403020100"


def _additive_on(device_id: str, *, service: str = "test.local_on") -> dict[str, Any]:
    """Return the stored v1 row of an additive switch-ON record."""
    return {
        "device_id": device_id,
        "kind": SUBENTRY_SWITCH,
        "state_value": PAYLOAD_ON,
        "label": "On",
        "mode": "additive",
        "actions": [{"action": service, "data": {"source": "local"}}],
    }


def _record_order(monkeypatch: pytest.MonkeyPatch, owner: Any, name: str, order: list[Any], label: str) -> None:
    """Wrap an async method so every call appends its label to `order` before running the original."""
    original = getattr(owner, name)

    @functools.wraps(original)
    async def _wrapper(*args: Any, **kwargs: Any) -> Any:
        order.append(label)
        return await original(*args, **kwargs)

    monkeypatch.setattr(owner, name, _wrapper)


async def test_local_load_before_mirrors_and_state_subscription(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-22: the local Store is loaded before any cached mirror is restored or subscribed for its state."""
    async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=[{"action": "test.owner_on"}])
    seed_store(hass_storage, {STORE_MIRRORS: {spec.device_id: document_payload(spec)}})
    _seed_local_store(hass_storage, [_additive_on(spec.device_id)])
    order: list[Any] = []
    _record_order(monkeypatch, LocalActionsStore, "async_load_records", order, "local_load")
    _record_order(monkeypatch, Manager, "_async_restore_mirrors", order, "mirror_restore")
    original_subscribe = Manager._async_subscribe_mirror

    async def _subscribe(self: Manager, device: Any) -> None:
        # What the Script can run at the moment the state subscription starts, so the first message finds it
        order.append(("state_subscribe", self.runner.can_run(device.device_id, trigger_key(PAYLOAD_ON))))
        await original_subscribe(self, device)

    monkeypatch.setattr(Manager, "_async_subscribe_mirror", _subscribe)

    await setup_entry(hass, make_hub_entry())

    assert order[:3] == ["local_load", "mirror_restore", ("state_subscribe", True)], (
        f"start order was {order}; the local Store must load before the mirror restore and the state subscription"
    )


async def test_restart_keeps_persisted_additive_record_and_runs_local_branch(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-07: after a restart the cached pending mirror runs its persisted local branch, never the owner's."""
    owner_calls = async_mock_service(hass, "test", "owner_on")
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=[{"action": "test.owner_on"}], off=[{"action": "test.owner_off"}])
    _seed_local_store(hass_storage, [_additive_on(spec.device_id)])
    stored_local = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))

    await restart_entry(hass, entry)
    manager = manager_of(entry)
    # PHACC replays nothing retained, so the mirror after the restart can only come from the cached document
    assert spec.device_id in manager.mirrors, "premise: the mirror is restored from the cache"
    assert str(manager.approval_state(spec.device_id)) == "pending"

    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)

    assert len(local_calls) == 1, f"the restored local branch ran {len(local_calls)} times, expected 1"
    assert local_calls[0].data == {"source": "local"}
    assert owner_calls == [], "the unapproved owner branch must never run"
    assert hass_storage[LOCAL_STORE_KEY] == stored_local, "a start never rewrites the local Store"


async def test_orphan_only_record_stays_queryable_after_startup_without_running(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-12: a record without a current mirror survives the start, is listed and runs nothing."""
    local_calls = async_mock_service(hass, "test", "local_on")
    _seed_local_store(hass_storage, [_additive_on(ORPHAN_DEVICE)])
    stored_local = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    entry = await setup_entry(hass, make_hub_entry())
    manager = manager_of(entry)

    listed = {device.device_id: device for device in manager.local_action_devices()}
    assert ORPHAN_DEVICE in listed, "an orphan-only record must stay manageable through the local device list"
    assert listed[ORPHAN_DEVICE].mirrored is False
    assert listed[ORPHAN_DEVICE].records == 1

    await _state(hass, ORPHAN_DEVICE, PAYLOAD_ON, retain=False)
    assert local_calls == [], "an orphan record never runs"
    assert hass_storage[LOCAL_STORE_KEY] == stored_local, "no startup garbage collection of local records"


# --- Plan 11-05 Task 2: locked, durable per-trigger edits (D-09 to D-16, D-22) ----------------------------------------

LOCAL_ON = [{"action": "test.local_on", "data": {"source": "local"}}]
LOCAL_OFF = [{"action": "test.local_off", "data": {"source": "local"}}]


def _stored_rows(hass_storage: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Return the record rows written to the local Store, None while nothing was written."""
    stored = hass_storage.get(LOCAL_STORE_KEY)
    return None if stored is None else stored["data"]["records"]


def _breaker_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_CIRCUIT_BREAKER_PREFIX}{device_id}")


async def _pending_mirror(hass: HomeAssistant, make_hub_entry: Callable, *specs: DeviceSpec) -> Manager:
    """Set up a follower and deliver the owner documents; every mirror is pending."""
    entry = await setup_entry(hass, make_hub_entry())
    for spec in specs:
        await deliver_config(hass, spec.device_id, document_payload(spec))
        await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    return manager_of(entry)


async def _trip_by_local_runs(hass: HomeAssistant, manager: Manager, spec: DeviceSpec) -> None:
    """Toggle a device whose ON and OFF both run local actions until its breaker trips (safe policy: 5 runs)."""
    on, off = (
        local_trigger_identity(spec.device_id, spec.kind, PAYLOAD_ON),
        local_trigger_identity(spec.device_id, spec.kind, PAYLOAD_OFF),
    )
    await manager.async_set_local_action(on, LocalActionMode.ADDITIVE, LOCAL_ON)
    await manager.async_set_local_action(off, LocalActionMode.ADDITIVE, LOCAL_OFF)
    for _ in range(3):
        await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
        await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    assert manager.device(spec.device_id).breaker.tripped, "premise: six local runs trip the safe breaker"
    assert _breaker_issue(hass, spec.device_id) is not None


async def test_edit_saves_immediately_and_applies_without_restart_or_retroactive_run(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-13, D-22: a submitted edit is durable at once, applies to the next real edge and runs nothing by itself."""
    owner_calls = async_mock_service(hass, "test", "owner_on")
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "on")

    change = await manager.async_set_local_action(identity, LocalActionMode.ADDITIVE, LOCAL_ON)

    # Read before any clock advance or block_till_done: the save is not a delayed one
    assert _stored_rows(hass_storage) == [
        {
            "device_id": spec.device_id,
            "kind": SUBENTRY_SWITCH,
            "state_value": PAYLOAD_ON,
            # The last known friendly name of the trigger, kept for the orphan display (D-11)
            "label": PAYLOAD_ON,
            "mode": "additive",
            "actions": LOCAL_ON,
        }
    ], "the edit must be written to the local Store immediately"
    assert change.active is True
    assert change.record is not None
    assert change.record.actions == LOCAL_ON
    await hass.async_block_till_done(wait_background_tasks=True)
    assert local_calls == [], "saving an edit never runs actions retroactively"

    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert len(local_calls) == 1, "the saved edit applies to the next real edge without a restart"
    assert owner_calls == []
    assert str(manager.approval_state(spec.device_id)) == "pending"


async def test_edit_rechecks_stale_targets_under_lock_and_saves_nothing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-10, T-11-13: a target that is no current trigger and has no saved record is refused before any save."""
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    stale = (
        local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "maybe"),  # no such StateValue
        local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "on"),  # the other kind
        local_trigger_identity(ORPHAN_DEVICE, SUBENTRY_SWITCH, "on"),  # no mirror, no record
    )
    for identity in stale:
        with pytest.raises(LocalActionError) as caught:
            await manager.async_set_local_action(identity, LocalActionMode.ADDITIVE, LOCAL_ON)
        assert caught.value.reason == "stale_target", identity
        with pytest.raises(LocalActionError) as caught:
            await manager.async_remove_local_action(identity)
        assert caught.value.reason == "stale_target", identity
    assert _stored_rows(hass_storage) is None, "a refused edit writes nothing"


async def test_edit_refuses_invalid_actions_and_mode_without_saving(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-11-13: local raw actions are validated with the action schema; a bad mode or list saves nothing."""
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "ON")
    for mode, actions, reason in (
        (LocalActionMode.ADDITIVE, [{"not_an_action": True}], "invalid_actions"),
        (LocalActionMode.ADDITIVE, "test.local_on", "invalid_actions"),
        ("sometimes", LOCAL_ON, "invalid_mode"),
    ):
        with pytest.raises(LocalActionError) as caught:
            await manager.async_set_local_action(identity, mode, actions)
        assert caught.value.reason == reason
    assert _stored_rows(hass_storage) is None


async def test_edit_and_remove_of_retained_orphan_records_keep_them_inactive(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-12: orphan and kind-mismatched records may be edited and removed, and never run."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=[{"action": "test.owner_on"}])
    mismatched = {**_additive_on(spec.device_id), "kind": SUBENTRY_SELECT, "label": "Old select"}
    _seed_local_store(hass_storage, [_additive_on(ORPHAN_DEVICE), mismatched])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    orphan = local_trigger_identity(ORPHAN_DEVICE, SUBENTRY_SWITCH, "on")
    kind_mismatch = local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "on")

    for identity in (orphan, kind_mismatch):
        change = await manager.async_set_local_action(identity, LocalActionMode.REPLACEMENT, LOCAL_ON)
        assert change.active is False, identity
    rows = _stored_rows(hass_storage)
    assert rows is not None
    assert [(row["device_id"], row["kind"], row["mode"], row["label"]) for row in rows] == [
        (ORPHAN_DEVICE, SUBENTRY_SWITCH, "replacement", "On"),
        (spec.device_id, SUBENTRY_SELECT, "replacement", "Old select"),
    ], "an inactive record keeps its place, its kind and its last label"
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert local_calls == [], "a kind-mismatched record never applies to the switch"

    await manager.async_remove_local_action(orphan)
    await manager.async_remove_local_action(kind_mismatch)
    assert _stored_rows(hass_storage) == []


async def test_save_failure_keeps_previous_record_script_and_breaker(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-22, T-11-15: a failed save changes neither the record, nor the Script, nor a tripped breaker."""
    async_mock_service(hass, "test", "local_on")
    async_mock_service(hass, "test", "local_off")
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    await _trip_by_local_runs(hass, manager, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "on")
    rows_before = copy.deepcopy(_stored_rows(hass_storage))
    script_before = manager.runner.script_for(spec.device_id, trigger_key(PAYLOAD_ON))
    triggers_before = manager.local_action_triggers(spec.device_id)

    with (
        patch.object(LocalActionsStore, "_async_write_data", AsyncMock(side_effect=OSError("disk full"))),
        pytest.raises(LocalActionError) as caught,
    ):
        await manager.async_set_local_action(identity, LocalActionMode.REPLACEMENT, [])
    assert caught.value.reason == "save_failed"
    with (
        patch.object(LocalActionsStore, "_async_write_data", AsyncMock(side_effect=OSError("disk full"))),
        pytest.raises(LocalActionError),
    ):
        await manager.async_remove_local_action(identity)

    assert _stored_rows(hass_storage) == rows_before
    assert manager.local_action_triggers(spec.device_id) == triggers_before
    assert manager.runner.script_for(spec.device_id, trigger_key(PAYLOAD_ON)) is script_before
    assert manager.device(spec.device_id).breaker.tripped, "a failed edit never releases the breaker"
    assert _breaker_issue(hass, spec.device_id) is not None


async def test_successful_edit_releases_only_the_target_breaker_and_runs_nothing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-03, T-11-15: a durable local edit releases the tripped breaker of its own device only."""
    local_on = async_mock_service(hass, "test", "local_on")
    local_off = async_mock_service(hass, "test", "local_off")
    target, other = make_spec(name="Target", on=[{"action": "test.owner_on"}]), make_spec(name="Other")
    manager = await _pending_mirror(hass, make_hub_entry, target, other)
    await _trip_by_local_runs(hass, manager, target)
    await _trip_by_local_runs(hass, manager, other)
    calls = (len(local_on), len(local_off))

    await manager.async_set_local_action(
        local_trigger_identity(target.device_id, SUBENTRY_SWITCH, "on"), LocalActionMode.ADDITIVE, LOCAL_ON
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not manager.device(target.device_id).breaker.tripped
    assert _breaker_issue(hass, target.device_id) is None
    assert manager.device(other.device_id).breaker.tripped, "another device's breaker stays tripped"
    assert _breaker_issue(hass, other.device_id) is not None
    assert (len(local_on), len(local_off)) == calls, "releasing the breaker runs nothing"


async def test_idempotent_repeated_edit_has_one_record_and_an_identical_plan(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """MIR-09: saving the same edit twice keeps one record and builds the same effective plan."""
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "on")

    await manager.async_set_local_action(identity, LocalActionMode.ADDITIVE, LOCAL_ON)
    first_rows = copy.deepcopy(_stored_rows(hass_storage))
    first_plan = manager.runner.plan_for(spec.device_id, trigger_key(PAYLOAD_ON))
    await manager.async_set_local_action(identity, "additive", copy.deepcopy(LOCAL_ON))

    assert _stored_rows(hass_storage) == first_rows
    assert first_rows is not None
    assert len(first_rows) == 1
    assert first_plan is not None
    assert manager.runner.plan_for(spec.device_id, trigger_key(PAYLOAD_ON)) == first_plan


async def test_remove_restores_owner_only_behavior_and_keeps_approval(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-14: removing a customization deletes it durably, the pending mirror runs nothing and approval is unchanged."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "on")
    await manager.async_set_local_action(identity, LocalActionMode.ADDITIVE, LOCAL_ON)

    change = await manager.async_remove_local_action(identity)

    assert change.record is None
    assert _stored_rows(hass_storage) == []
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert local_calls == []
    assert manager.runner.script_count(spec.device_id) == 0, "a pending mirror without local actions has no Script"
    assert str(manager.approval_state(spec.device_id)) == "pending"
    with pytest.raises(LocalActionError):
        await manager.async_remove_local_action(identity)


async def test_edit_waits_for_the_manager_lock(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """MIR-11, T-11-14: an edit is serialized with approval, reconcile and ingest on the one Manager lock."""
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "on")

    async with manager.lock:
        task = hass.async_create_task(manager.async_set_local_action(identity, LocalActionMode.ADDITIVE, LOCAL_ON))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not task.done()
        assert _stored_rows(hass_storage) is None, "nothing is written while another holder has the lock"
    await task
    assert _stored_rows(hass_storage) is not None


async def test_editor_rows_list_current_triggers_then_inactive_records_as_copies(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-11, D-12: current triggers in owner order with friendly name, then inactive records; counts only elsewhere."""
    spec = make_spec(
        SUBENTRY_SELECT, options=[("cozy", "Gemütlich", []), ("bright", "Hell", [{"action": "test.owner_on"}])]
    )
    gone = {**_additive_on(spec.device_id), "kind": SUBENTRY_SELECT, "state_value": "party", "label": "Party"}
    _seed_local_store(hass_storage, [gone, _additive_on(ORPHAN_DEVICE)])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    await manager.async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "Bright"), LocalActionMode.REPLACEMENT, []
    )

    rows = manager.local_action_triggers(spec.device_id)
    assert [(row.state_value, row.label, row.present, row.record is not None) for row in rows] == [
        ("cozy", "Gemütlich", True, False),
        ("bright", "Hell", True, True),
        ("party", "Party", False, True),
    ]
    assert rows[1].record is not None
    rows[1].record.actions.append({"action": "test.tamper"})
    assert manager.local_action_triggers(spec.device_id)[1].record.actions == [], "rows hand out copies"
    assert [(row.label, row.present) for row in manager.local_action_triggers(ORPHAN_DEVICE)] == [("On", False)]
    counts = manager.local_action_counts()
    assert (counts.records, counts.devices, counts.active, counts.inactive, counts.muted) == (3, 2, 1, 2, 1)
    assert counts.orphan_only_devices == 1


# --- Plan 11-05 Task 3: one coherent device-wide policy (D-03, D-09, MIR-11) ------------------------------------------

# Owner metadata that would change every consumer if it were trusted before approval
HOSTILE = {"run_on_startup": True, "run_mode": RUN_MODE_RESTART, "breaker_max_runs": 1, "breaker_window": 60}


def _incoherence(manager: Manager, device_id: str, expected: EffectivePolicy | None) -> list[str]:
    """Return how tracker, breaker and Script of a mirror deviate from one policy snapshot; empty when coherent."""
    device = manager.device(device_id)
    if device is None or expected is None:
        return [f"no device or no policy ({device!r}, {expected!r})"]
    found: list[str] = []
    if device.policy != expected:
        found.append(f"device policy {device.policy} != {expected}")
    if device.tracker.run_on_startup is not expected.run_on_startup:
        found.append("tracker run_on_startup")
    if (device.breaker.max_runs, device.breaker.window) != (expected.breaker_max_runs, expected.breaker_window):
        found.append(f"breaker {device.breaker.max_runs}/{device.breaker.window}")
    script = manager.runner.script_for(device_id, trigger_key(PAYLOAD_ON))
    if script is not None:
        if manager.runner.policy_for(device_id) is not device.policy:
            found.append("the Script was built from another snapshot")
        if script.script_mode != ("queued" if expected.run_mode == "serial" else "restart"):
            found.append(f"script mode {script.script_mode}")
        if script.max_runs != expected.queue_limit:
            found.append(f"script queue {script.max_runs}")
    return found


def _assert_coherent(manager: Manager, device_id: str, expected: EffectivePolicy) -> None:
    """Every consumer of a mirror's device-wide policy reads the same snapshot: tracker, breaker and Script."""
    assert _incoherence(manager, device_id, expected) == []


async def test_pending_local_policy_is_false_serial_5_10_10_whatever_the_owner_says(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-03, T-11-12: unapproved owner startup, run mode and breaker limits never govern trusted local runs."""
    local_calls = async_mock_service(hass, "test", "local_on")
    async_mock_service(hass, "test", "owner_on")
    spec = make_spec(on=[{"action": "test.owner_on"}], **HOSTILE)
    _seed_local_store(hass_storage, [_additive_on(spec.device_id)])
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    await restart_entry(hass, entry)
    manager = manager_of(entry)
    assert str(manager.approval_state(spec.device_id)) == "pending"

    assert (
        EffectivePolicy(run_on_startup=False, run_mode="serial", breaker_max_runs=5, breaker_window=10, queue_limit=10)
        == LOCAL_SAFE_POLICY
    )

    # The retained replay of a start runs nothing: startup execution is off for local actions
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=True)
    assert local_calls == [], "an unapproved owner's run_on_startup must not start local actions"
    # Two real edges: the owner's breaker (1 run per 60 s) would trip at the second, the safe one allows five
    for _ in range(2):
        await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
        await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert len(local_calls) == 2
    assert not manager.device(spec.device_id).breaker.tripped
    _assert_coherent(manager, spec.device_id, LOCAL_SAFE_POLICY)


async def test_approved_exact_hash_switches_every_policy_consumer_together(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-03: the exact approved hash hands the owner's settings to tracker, breaker and Script at once, and back."""
    spec = make_spec(on=[{"action": "test.owner_on"}], **HOSTILE)
    _seed_local_store(hass_storage, [_additive_on(spec.device_id)])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    _assert_coherent(manager, spec.device_id, LOCAL_SAFE_POLICY)

    assert await manager.async_approve(spec.device_id, manager.mirrors[spec.device_id].mirror.actions_hash)
    owner_policy = EffectivePolicy(
        run_on_startup=True, run_mode=RUN_MODE_RESTART, breaker_max_runs=1, breaker_window=60, queue_limit=10
    )
    _assert_coherent(manager, spec.device_id, owner_policy)

    # New owner actions: the approval no longer matches, so every consumer falls back to the safe policy together
    changed = make_spec(device_id=spec.device_id, on=[{"action": "test.owner_other"}], **HOSTILE)
    await deliver_config(hass, spec.device_id, document_payload(changed, rev=2), retain=False)
    assert str(manager.approval_state(spec.device_id)) == "pending"
    _assert_coherent(manager, spec.device_id, LOCAL_SAFE_POLICY)


async def test_policy_snapshot_stays_coherent_through_concurrent_approval_and_edits(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MIR-11, T-11-14: however edits and approval interleave, no run decision sees two policy generations."""
    async_mock_service(hass, "test", "local_on")
    async_mock_service(hass, "test", "owner_on")
    spec = make_spec(on=[{"action": "test.owner_on"}], **HOSTILE)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "on")
    seen: list[EffectivePolicy | None] = []
    incoherent: list[list[str]] = []
    original = Manager._run_trigger

    def _run_trigger(self: Manager, device: Any, value: str) -> None:
        # Checked at every run decision, while builds of the other tasks may be half way through their awaits; an
        # assertion here would be swallowed by the MQTT dispatcher, so the findings are collected instead
        seen.append(device.policy)
        if found := _incoherence(self, device.device_id, device.policy):
            incoherent.append(found)
        original(self, device, value)

    monkeypatch.setattr(Manager, "_run_trigger", _run_trigger)

    async def _toggle() -> None:
        for _ in range(4):
            async_fire_mqtt_message(hass, state_topic(BASE, spec.device_id), PAYLOAD_ON)
            await asyncio.sleep(0)
            async_fire_mqtt_message(hass, state_topic(BASE, spec.device_id), PAYLOAD_OFF)
            await asyncio.sleep(0)

    actions_hash = manager.mirrors[spec.device_id].mirror.actions_hash
    await asyncio.gather(
        manager.async_set_local_action(identity, LocalActionMode.ADDITIVE, LOCAL_ON),
        _toggle(),
        manager.async_approve(spec.device_id, actions_hash),
        _toggle(),
        manager.async_set_local_action(identity, LocalActionMode.REPLACEMENT, LOCAL_ON),
        _toggle(),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert seen, "premise: run decisions happened during the interleaving"
    assert incoherent == [], "a run decision saw tracker, breaker and Script of different policy generations"
    rows = _stored_rows(hass_storage)
    assert rows is not None
    assert len(rows) == 1, "concurrent edits of one identity leave one record"
    owner_policy = EffectivePolicy(
        run_on_startup=True, run_mode=RUN_MODE_RESTART, breaker_max_runs=1, breaker_window=60, queue_limit=10
    )
    _assert_coherent(manager, spec.device_id, owner_policy)


@pytest.mark.parametrize("refusal", ["observe", "disabled", "tripped"])
async def test_observe_disabled_and_tripped_breaker_refuse_local_runs(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable, refusal: str
) -> None:
    """D-03, D-14: the device modes and a tripped breaker gate local runs like owner runs."""
    local_on = async_mock_service(hass, "test", "local_on")
    local_off = async_mock_service(hass, "test", "local_off")
    spec = make_spec(on=[{"action": "test.owner_on"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    if refusal == "tripped":
        await _trip_by_local_runs(hass, manager, spec)
    else:
        await manager.async_set_local_action(
            local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, "on"), LocalActionMode.ADDITIVE, LOCAL_ON
        )
        await manager.async_set_device_mode(spec.device_id, MODE_OBSERVE if refusal == "observe" else MODE_DISABLED)
    calls = (len(local_on), len(local_off))

    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)

    assert (len(local_on), len(local_off)) == calls, f"{refusal} must refuse every local run"


# --- Plan 11-07 Task 1: every entry point runs the effective actions through the same gates (D-03, MIR-09, MIR-10) ---

OWNER_ON = [{"action": "test.owner_on"}]


def _retrigger(manager: Manager, device_id: str, state: str = PAYLOAD_ON) -> tuple[str, str | None] | None:
    """Hand one fresh re-trigger request to the receiver of this instance and return its answer."""
    request = RetriggerRequest(
        request_id=str(uuid.uuid4()),
        requester=manager.instance_id,
        state=state,
        sent_at=manager.retrigger.wall_clock(),
    )
    # The receiver treats its own requests as already rate limited by the caller, so repeated calls are all admitted
    manager.retrigger._remember_own(request.request_id)
    return manager.retrigger._decide(device_id, request)


def _legacy_test_press(manager: Manager, device_id: str, payload: str = PAYLOAD_ON) -> None:
    """Deliver a press on the legacy test topic of a device, as a test button of a v0.1.0 device publishes it."""
    manager.test_message_handler(device_id)(IncomingMessage(payload=payload, retain=False))


def _untouched(manager: Manager, device_id: str) -> tuple[Any, ...]:
    """What a test run must never change: baseline, startup window, breaker count and trip, and the revision."""
    device = manager.device(device_id)
    assert device is not None
    return (
        device.tracker.last_acted,
        device.tracker.startup_pending,
        len(device.breaker._stamps),
        device.breaker.tripped,
        manager.revision(device_id),
    )


def _shared_publishes(mqtt_mock: Any) -> list[str]:
    """Return the topics published so far, without the re-trigger answers addressed to a requester."""
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list if "/acks" not in call.args[0]]


# case -> (approved, record mode and actions or None, services that run, re-trigger answer)
ENTRY_POINT_CASES: dict[str, tuple[bool, tuple[LocalActionMode, list[dict[str, Any]]] | None, list[str], Any]] = {
    "owner_only_pending": (False, None, [], ("not_approved", None)),
    "owner_only_approved": (True, None, ["owner_on"], ("executed", None)),
    "additive_pending": (False, (LocalActionMode.ADDITIVE, LOCAL_ON), ["local_on"], ("executed", None)),
    "additive_approved": (True, (LocalActionMode.ADDITIVE, LOCAL_ON), ["local_on", "owner_on"], ("executed", None)),
    "replacement_pending": (False, (LocalActionMode.REPLACEMENT, LOCAL_ON), ["local_on"], ("executed", None)),
    "replacement_approved": (True, (LocalActionMode.REPLACEMENT, LOCAL_ON), ["local_on"], ("executed", None)),
    # A muted trigger runs nothing whatever the approval, so approving the owner would not change the answer
    "mute_pending": (False, (LocalActionMode.REPLACEMENT, []), [], ("error", "no_actions")),
    "mute_approved": (True, (LocalActionMode.REPLACEMENT, []), [], ("error", "no_actions")),
}


@pytest.mark.parametrize("case", ENTRY_POINT_CASES)
async def test_test_button_legacy_test_and_retrigger_run_what_a_state_change_runs(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable, case: str
) -> None:
    """MIR-10, D-03: native and legacy test presses and the re-trigger run exactly the effective actions of a change."""
    approved, record, expected, answer = ENTRY_POINT_CASES[case]
    mocks = {service: async_mock_service(hass, "test", service) for service in ("owner_on", "local_on")}
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    if approved:
        assert await manager.async_approve(spec.device_id, manager.mirrors[spec.device_id].mirror.actions_hash)
    if record is not None:
        await manager.async_set_local_action(
            local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON), record[0], record[1]
        )
    await hass.async_block_till_done(wait_background_tasks=True)
    before = _untouched(manager, spec.device_id)
    shared_before = _shared_publishes(mqtt_mock)

    runs: dict[str, list[str]] = {}

    async def _settle(source: str) -> None:
        await hass.async_block_till_done(wait_background_tasks=True)
        runs[source] = sorted(service for service, served in mocks.items() for _ in served)
        for served in mocks.values():
            served.clear()

    await manager.async_press_test(spec.device_id, trigger_key(PAYLOAD_ON))
    await _settle("native test button")
    _legacy_test_press(manager, spec.device_id)
    await _settle("legacy test topic")
    retrigger_answer = _retrigger(manager, spec.device_id)
    await _settle("re-trigger")
    assert _untouched(manager, spec.device_id) == before, "a test run never touches baseline, breaker or revision"
    assert _shared_publishes(mqtt_mock) == shared_before, "a test run publishes nothing but the re-trigger answer"
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    await _settle("state change")

    assert runs == dict.fromkeys(runs, expected), f"{case}: every entry point must run the effective actions"
    assert retrigger_answer == answer, f"{case}: the re-trigger answer was {retrigger_answer}"


async def test_test_button_and_retrigger_refuse_local_runs_while_the_breaker_is_tripped(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """MIR-09, D-03: a tripped breaker refuses a test run of a trigger with local actions on every entry point."""
    local_on = async_mock_service(hass, "test", "local_on")
    local_off = async_mock_service(hass, "test", "local_off")
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    await _trip_by_local_runs(hass, manager, spec)
    calls = (len(local_on), len(local_off))

    await manager.async_press_test(spec.device_id, trigger_key(PAYLOAD_ON))
    _legacy_test_press(manager, spec.device_id, PAYLOAD_OFF)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (len(local_on), len(local_off)) == calls, "a tripped breaker must refuse a test run of local actions"
    assert _retrigger(manager, spec.device_id) == ("paused", None)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (len(local_on), len(local_off)) == calls
    assert manager.device(spec.device_id).breaker.tripped, "a refused test run never releases the breaker"


@pytest.mark.parametrize("mode", [MODE_OBSERVE, MODE_DISABLED])
async def test_test_button_and_retrigger_refuse_local_runs_in_observe_and_disabled_mode(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable, mode: str
) -> None:
    """MIR-09, D-14: observe and disabled refuse a test run of local actions, with the existing answer words."""
    local_on = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    await manager.async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON), LocalActionMode.ADDITIVE, LOCAL_ON
    )
    await manager.async_set_device_mode(spec.device_id, mode)

    await manager.async_press_test(spec.device_id, trigger_key(PAYLOAD_ON))
    _legacy_test_press(manager, spec.device_id)
    answer = _retrigger(manager, spec.device_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert local_on == []
    assert answer == ({MODE_OBSERVE: "observing", MODE_DISABLED: "disabled"}[mode], None)


async def test_test_button_of_an_overlay_free_mirror_still_runs_while_paused(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-13 of Phase 2 is unchanged without local actions: a test press of owner-only actions bypasses the pause."""
    owner_calls = async_mock_service(hass, "test", "owner_on")
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    assert await manager.async_approve(spec.device_id, manager.mirrors[spec.device_id].mirror.actions_hash)
    manager.device(spec.device_id).breaker.trip()

    await manager.async_press_test(spec.device_id, trigger_key(PAYLOAD_ON))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(owner_calls) == 1
    assert _retrigger(manager, spec.device_id) == ("paused", None), "the re-trigger keeps refusing a paused device"


def test_retrigger_acknowledgement_vocabulary_is_unchanged() -> None:
    """MIR-10, D-03: local actions add no status or reason word to the broker answers."""
    assert frozenset(retrigger_module._STATUS_WORDS) == {
        "executed",
        "not_approved",
        "paused",
        "observing",
        "disabled",
        "error",
    }
    assert frozenset(retrigger_module._REASON_WORDS) == {
        "unknown_device",
        "bad_state",
        "no_actions",
        "not_runnable",
        "offline",
    }


# --- Plan 11-07 Task 2: one independent local failure issue per device (D-18, D-19) -----------------------------------

# Literal on purpose: a RED run against code without the production constant fails on an assertion, not on an import
LOCAL_ISSUE_PREFIX = "local_action_failed_"
OWNER_ISSUE_PREFIX = "action_failed_"
LOUD_ERROR = "local *boom* [x](y) _z_"


class Flaky:
    """`test.flaky` fails for the triggers named in `failing` (data `which`) and records every call."""

    def __init__(self, hass: HomeAssistant, *failing: str) -> None:
        self.failing = set(failing)
        self.calls: list[str] = []
        hass.services.async_register("test", "flaky", self._handle)

    async def _handle(self, call: Any) -> None:
        self.calls.append(call.data["which"])
        if call.data["which"] in self.failing:
            raise HomeAssistantError(LOUD_ERROR)


def _flaky(which: str, **step: Any) -> list[dict[str, Any]]:
    return [{"action": "test.flaky", "data": {"which": which}, **step}]


def _local_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{LOCAL_ISSUE_PREFIX}{device_id}")


def _owner_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{OWNER_ISSUE_PREFIX}{device_id}")


def _named_trigger(hass: HomeAssistant, device_id: str) -> str | None:
    """Return the trigger the local failure issue names, None without an issue."""
    issue = _local_issue(hass, device_id)
    return (
        None if issue is None or issue.translation_placeholders is None else issue.translation_placeholders["trigger"]
    )


async def _set(manager: Manager, spec: DeviceSpec, value: str, mode: LocalActionMode, actions: Any) -> None:
    await manager.async_set_local_action(local_trigger_identity(spec.device_id, spec.kind, value), mode, actions)


async def test_local_failure_raises_an_independent_issue_naming_the_trigger_and_error(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-18, T-11-23: a local failure raises its own escaped, bounded, non-fixable issue; the owner issue stays out."""
    Flaky(hass, "on")
    spec = make_spec(name="Lamp *x*", on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))

    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)

    issue = _local_issue(hass, spec.device_id)
    assert issue is not None, "a failed local run must raise the local failure issue"
    assert issue.is_fixable is False
    assert issue.is_persistent is True, "the issue survives a Home Assistant restart with its trigger identity (G-01)"
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_key == "local_action_failed"
    placeholders = issue.translation_placeholders
    assert placeholders is not None
    assert set(placeholders) == {"device", "trigger", "time", "error"}
    assert placeholders["device"] == escape_markdown("Lamp *x*")
    assert placeholders["trigger"] == escape_markdown(spec.triggers[trigger_key(PAYLOAD_ON)].label)
    assert placeholders["error"] == escape_markdown(LOUD_ERROR)
    assert "test.flaky" not in repr(issue), "the issue never carries actions"
    assert _owner_issue(hass, spec.device_id) is None, "the owner failure issue is never reused for a local failure"


async def test_local_failure_issue_names_the_latest_failed_trigger_and_clears_only_on_its_success(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-18, D-19: the latest failed trigger is named; the success of a different trigger does not clear it."""
    flaky = Flaky(hass, "on", "off")
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    await _set(manager, spec, PAYLOAD_OFF, LocalActionMode.ADDITIVE, _flaky("off"))
    on_label = escape_markdown(spec.triggers[trigger_key(PAYLOAD_ON)].label)
    off_label = escape_markdown(spec.triggers[trigger_key(PAYLOAD_OFF)].label)

    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _named_trigger(hass, spec.device_id) == on_label
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    assert _named_trigger(hass, spec.device_id) == off_label, "the issue names the latest failed local trigger"

    flaky.failing.clear()
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert flaky.calls[-1] == "on"
    assert _named_trigger(hass, spec.device_id) == off_label, "the success of a different trigger never clears"
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    assert _local_issue(hass, spec.device_id) is None, "a proven success of the named trigger clears the issue"


async def test_local_failure_issue_survives_owner_success_continued_error_stop_and_owner_change(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """
    D-19 (amended 2026-10-21), 11-06 hand-off: no owner result, continued error, stop or owner change clears it.

    Only the named trigger's proven success, a durable save of it without local actions (a mute here) or its removal
    end the local issue.
    """
    flaky = Flaky(hass, "on")
    owner_off = async_mock_service(hass, "test", "owner_off")
    async_mock_service(hass, "test", "owner_on")
    async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON, off=[{"action": "test.owner_off"}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    assert await manager.async_approve(spec.device_id, manager.mirrors[spec.device_id].mirror.actions_hash)
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _local_issue(hass, spec.device_id) is not None

    # An owner-only success of another trigger
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    assert len(owner_off) == 1
    assert _local_issue(hass, spec.device_id) is not None, "an owner success never clears the local issue"

    # The same trigger with a continued error and then a stop: neither is a proven local success
    flaky.failing.clear()
    flaky.failing.add("continued")
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, [*_flaky("continued", continue_on_error=True)])
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    assert _local_issue(hass, spec.device_id) is not None, "a continued local error is still a failure"
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, [*LOCAL_ON, {"stop": "done"}])
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    assert _local_issue(hass, spec.device_id) is not None, "a stopped run never proves a local success"

    # A muted trigger has no local actions left, so it can no longer fail locally: the mute ends its issue (WR-02)
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.REPLACEMENT, [])
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _local_issue(hass, spec.device_id) is None, "muting the named trigger ends its local failure issue (WR-02)"

    # Raise it again for the last step
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    flaky.failing = {"on"}
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _local_issue(hass, spec.device_id) is not None, "premise: the named trigger failed again"

    # An owner content change clears the owner's issues only
    changed = make_spec(
        device_id=spec.device_id, on=[{"action": "test.owner_other"}], off=[{"action": "test.owner_off"}]
    )
    await deliver_config(hass, spec.device_id, document_payload(changed, rev=2), retain=False)
    assert manager.mirrors[spec.device_id].spec == changed
    assert _local_issue(hass, spec.device_id) is not None, "an owner change keeps an unrelated local failure issue"


async def test_local_failure_issue_clears_on_proven_success_after_an_edit_and_on_removal(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-19: an edit alone clears nothing; the next proven success does, and so does removing the customization."""
    Flaky(hass, "on")
    async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _local_issue(hass, spec.device_id) is not None

    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, LOCAL_ON)
    assert _local_issue(hass, spec.device_id) is not None, "saving a fix is not yet a success"
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _local_issue(hass, spec.device_id) is None

    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _local_issue(hass, spec.device_id) is not None
    await _set(manager, spec, PAYLOAD_OFF, LocalActionMode.ADDITIVE, LOCAL_OFF)
    await manager.async_remove_local_action(local_trigger_identity(spec.device_id, spec.kind, PAYLOAD_OFF))
    assert _local_issue(hass, spec.device_id) is not None, "removing another trigger's customization clears nothing"
    await manager.async_remove_local_action(local_trigger_identity(spec.device_id, spec.kind, PAYLOAD_ON))
    assert _local_issue(hass, spec.device_id) is None, "removing the named customization clears the issue"


async def test_saving_the_named_trigger_without_local_actions_clears_its_local_failure_issue(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """WR-02, D-19 (amended 2026-10-21): a saved record without local actions cannot fail locally; it ends the issue."""
    Flaky(hass, "on")
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    on_label = escape_markdown(spec.triggers[trigger_key(PAYLOAD_ON)].label)
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _named_trigger(hass, spec.device_id) == on_label, "premise: the issue names ON"

    # A mute: replacement with an empty list keeps the owner actions suppressed and ends the issue
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.REPLACEMENT, [])
    assert _local_issue(hass, spec.device_id) is None, "a mute of the named trigger ends its local failure issue"

    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=False)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _named_trigger(hass, spec.device_id) == on_label, "premise: the issue names ON again"

    # Additive with an empty list runs no local action either
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, [])
    assert _local_issue(hass, spec.device_id) is None, "emptying the named trigger's additive actions ends the issue"


async def test_only_a_durable_save_of_the_named_trigger_without_local_actions_clears_the_issue(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-11-49: another trigger, a save with local actions and a failed save keep the issue; the durable one ends it."""
    Flaky(hass, "on")
    async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    on_label = escape_markdown(spec.triggers[trigger_key(PAYLOAD_ON)].label)
    on = local_trigger_identity(spec.device_id, spec.kind, PAYLOAD_ON)
    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, _flaky("on"))
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert _named_trigger(hass, spec.device_id) == on_label, "premise: the issue names ON"

    await _set(manager, spec, PAYLOAD_OFF, LocalActionMode.REPLACEMENT, [])
    assert _named_trigger(hass, spec.device_id) == on_label, "muting another trigger keeps the issue of ON"

    await _set(manager, spec, PAYLOAD_ON, LocalActionMode.ADDITIVE, LOCAL_ON)
    assert _named_trigger(hass, spec.device_id) == on_label, "a save with local actions waits for a proven success"

    with (
        patch.object(LocalActionsStore, "_async_write_data", AsyncMock(side_effect=OSError("disk full"))),
        pytest.raises(LocalActionError) as caught,
    ):
        await manager.async_set_local_action(on, LocalActionMode.REPLACEMENT, [])
    assert caught.value.reason == "save_failed"
    assert _named_trigger(hass, spec.device_id) == on_label, "a failed save never clears the issue"

    await manager.async_set_local_action(on, LocalActionMode.REPLACEMENT, [])
    assert _local_issue(hass, spec.device_id) is None, "the durable save without local actions ends the issue"
    await manager.async_set_local_action(on, LocalActionMode.REPLACEMENT, [])
    assert _local_issue(hass, spec.device_id) is None, "saving the same empty record again is a no-op"


async def test_local_failure_issue_survives_an_orphaned_option_until_its_record_is_removed(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-12, D-19: an option the owner removed leaves an orphan; its local issue stays until the record is removed."""
    Flaky(hass, "cozy")
    spec = make_spec(SUBENTRY_SELECT, options=[("cozy", "*Gemütlich*", []), ("bright", "Hell", [])])
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "bright", retain=True)
    manager = manager_of(entry)
    await _set(manager, spec, "cozy", LocalActionMode.ADDITIVE, _flaky("cozy"))
    await _state(hass, spec.device_id, "cozy", retain=False)
    assert _named_trigger(hass, spec.device_id) == escape_markdown("*Gemütlich*")

    # A Select keeps at least two options, so the owner swaps cozy for party
    reduced = make_spec(
        SUBENTRY_SELECT, device_id=spec.device_id, options=[("bright", "Hell", []), ("party", "Party", [])]
    )
    await deliver_config(hass, spec.device_id, document_payload(reduced, rev=2), retain=False)
    assert [row.present for row in manager.local_action_triggers(spec.device_id) if row.state_value == "cozy"] == [
        False
    ], "premise: the record is an orphan now"
    assert _local_issue(hass, spec.device_id) is not None, "an orphaned trigger never clears its issue"

    await manager.async_remove_local_action(local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "cozy"))
    assert _local_issue(hass, spec.device_id) is None


async def test_invalid_local_actions_at_build_raise_the_local_failure_issue(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-18: a stored local customization that no longer validates is shown in the local issue, not only logged."""
    spec = make_spec(on=OWNER_ON)
    _seed_local_store(hass_storage, [{**_additive_on(spec.device_id), "actions": [{"not_an_action": True}]}])
    manager = await _pending_mirror(hass, make_hub_entry, spec)

    issue = _local_issue(hass, spec.device_id)
    assert issue is not None, "invalid local actions must raise the local failure issue"
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["error"]
    assert _owner_issue(hass, spec.device_id) is None

    await manager.async_remove_local_action(local_trigger_identity(spec.device_id, spec.kind, PAYLOAD_ON))
    assert _local_issue(hass, spec.device_id) is None


async def test_failure_outcome_of_a_removed_customization_raises_no_local_issue(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-19: a failure that arrives after its customization was removed would never clear, so it is not shown."""
    spec = make_spec(on=OWNER_ON)
    manager = await _pending_mirror(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, spec.kind, PAYLOAD_ON)

    manager.async_report_local_outcome(
        BranchOutcome(
            spec.device_id,
            trigger_key(PAYLOAD_ON),
            spec.triggers[trigger_key(PAYLOAD_ON)].label,
            OutcomeStatus.FAILURE,
            "late failure",
            1,
            identity=identity,
            device_name=spec.name,
        )
    )

    assert _local_issue(hass, spec.device_id) is None


def test_local_failure_issue_family_is_a_separate_device_issue_prefix() -> None:
    """D-18: its own prefix, deleted with the device and the hub like every per-device issue family."""
    prefix = getattr(const_module, "ISSUE_LOCAL_ACTION_FAILED_PREFIX", None)
    assert prefix == LOCAL_ISSUE_PREFIX
    assert prefix != const_module.ISSUE_ACTION_FAILED_PREFIX
    assert prefix in const_module.ISSUE_DEVICE_PREFIXES


# --- Plan 11-15 Task 1: a refused local Store load is visible as one instance issue (G-02, D-05, T-11-09) -------------

# Literal on purpose: a RED run against code without the production constant fails on an assertion, not on an import
UNREADABLE_ISSUE_ID = "local_actions_unreadable"


def _seed_newer_local_store(hass_storage: dict[str, Any], records: list[dict[str, Any]]) -> str:
    """Write local records as a version 2 envelope this release refuses; return its serialized bytes."""
    hass_storage[LOCAL_STORE_KEY] = {
        "version": 2,
        "minor_version": 1,
        "key": LOCAL_STORE_KEY,
        "data": {"records": records},
    }
    return _local_store_bytes(hass_storage)


def _local_store_bytes(hass_storage: dict[str, Any]) -> str:
    return json.dumps(hass_storage.get(LOCAL_STORE_KEY), sort_keys=True)


def _replacement_on(device_id: str) -> dict[str, Any]:
    """Return the stored row of a replacement record for switch ON."""
    return {
        "device_id": device_id,
        "kind": SUBENTRY_SWITCH,
        "state_value": PAYLOAD_ON,
        "label": "On",
        "mode": "replacement",
        "actions": LOCAL_ON,
    }


def _unreadable_issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, UNREADABLE_ISSUE_ID)


async def test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """G-02, D-05, T-11-09: a refused local load raises one instance issue, keeps the file and applies no overlay."""
    owner_calls = async_mock_service(hass, "test", "owner_on")
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    before = _seed_newer_local_store(hass_storage, [_replacement_on(spec.device_id)])

    manager = await _pending_mirror(hass, make_hub_entry, spec)

    issue = _unreadable_issue(hass)
    assert issue is not None, "a refused local Store load must raise the local_actions_unreadable issue"
    assert issue.domain == DOMAIN
    assert issue.is_fixable is False
    assert issue.is_persistent is False, "every start decides again whether the local Store is readable"
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_key == UNREADABLE_ISSUE_ID
    assert not issue.translation_placeholders, "the issue carries no placeholder and no record content"
    assert _local_store_bytes(hass_storage) == before, "the start never rewrites the newer local Store"

    assert await manager.async_approve(spec.device_id, manager.mirrors[spec.device_id].mirror.actions_hash)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert len(owner_calls) == 1, "the approved owner action runs on the trigger the unreadable record replaced"
    assert local_calls == [], "no overlay of the unreadable Store applies"

    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON)
    with pytest.raises(LocalActionError) as caught:
        await manager.async_set_local_action(identity, LocalActionMode.REPLACEMENT, LOCAL_ON)
    assert caught.value.reason == "save_failed"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _local_store_bytes(hass_storage) == before, "a refused edit never overwrites the newer local Store"


async def test_readable_local_store_deletes_the_unreadable_issue_at_the_next_start(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """G-02: the next start whose local load succeeds deletes the issue."""
    spec = make_spec(on=OWNER_ON)
    _seed_newer_local_store(hass_storage, [_replacement_on(spec.device_id)])
    entry = await setup_entry(hass, make_hub_entry())
    assert _unreadable_issue(hass) is not None, "premise: the refused load raised the issue"

    _seed_local_store(hass_storage, [_replacement_on(spec.device_id)])
    await restart_entry(hass, entry)

    assert manager_of(entry).local_action_counts().records == 1, "premise: the readable local Store was loaded"
    assert _unreadable_issue(hass) is None, "a successful local load deletes the unreadable issue"


async def test_hub_removal_deletes_the_unreadable_local_store_issue(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-08: hub removal in both modes deletes the unreadable issue by its id, and the local file with it."""
    spec = make_spec(on=OWNER_ON)
    for mode, options in (("keep", {}), ("delete", {CONF_DELETE_DEVICES_ON_REMOVE: True})):
        _seed_newer_local_store(hass_storage, [_replacement_on(spec.device_id)])
        entry = await setup_entry(hass, make_hub_entry(options=options))
        assert _unreadable_issue(hass) is not None, f"{mode}: premise: the refused load raised the issue"

        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert _unreadable_issue(hass) is None, f"{mode}: hub removal deletes the unreadable issue"
        assert LOCAL_STORE_KEY not in hass_storage, f"{mode}: hub removal deletes the local Store file (D-08)"


# --- Plan 11-20 Task 1: a shape-invalid local Store is unreadable, not empty (WR-03, D-07, T-11-09) ------------------


async def test_shape_invalid_local_store_raises_the_unreadable_issue_and_is_never_overwritten(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """WR-03, D-07, T-11-50: a record mapping instead of a record list raises the issue and no save ever writes it."""
    owner_calls = async_mock_service(hass, "test", "owner_on")
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    hass_storage[LOCAL_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_STORE_KEY,
        "data": {"records": {"0": _replacement_on(spec.device_id)}},
    }
    before = _local_store_bytes(hass_storage)

    manager = await _pending_mirror(hass, make_hub_entry, spec)

    issue = _unreadable_issue(hass)
    assert issue is not None, "a local Store without a record list must raise the local_actions_unreadable issue"
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.severity == ir.IssueSeverity.ERROR
    assert not issue.translation_placeholders, "the issue carries no placeholder and no record content"
    assert _local_store_bytes(hass_storage) == before, "the start never rewrites the unreadable local Store"

    assert await manager.async_approve(spec.device_id, manager.mirrors[spec.device_id].mirror.actions_hash)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert len(owner_calls) == 1, "the approved owner action runs on the trigger the unreadable record replaced"
    assert local_calls == [], "no overlay of the unreadable Store applies"

    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON)
    with pytest.raises(LocalActionError) as caught:
        await manager.async_set_local_action(identity, LocalActionMode.REPLACEMENT, LOCAL_ON)
    assert caught.value.reason == "save_failed"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _local_store_bytes(hass_storage) == before, "a refused edit never overwrites the unreadable local Store"

    renamed = make_spec(device_id=spec.device_id, name="Renamed lamp", on=OWNER_ON)
    await deliver_config(hass, spec.device_id, document_payload(renamed, rev=2), retain=False)
    assert _local_store_bytes(hass_storage) == before, "an owner change never overwrites the unreadable local Store"


# --- Plan 11-15 Task 2: English and German text of the unreadable issue (G-02, D-06, MIR-15) --------------------------

TRANSLATIONS_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "mqtt_actions" / "translations"


def _unreadable_issue_text(language: str) -> dict[str, Any]:
    """Return the title and description of the unreadable issue in one language, empty strings when missing."""
    issues = json.loads((TRANSLATIONS_DIR / f"{language}.json").read_text(encoding="utf-8")).get("issues", {})
    entry = issues.get(UNREADABLE_ISSUE_ID) or {}
    return {"title": entry.get("title", ""), "description": entry.get("description", "")}


def test_unreadable_local_store_issue_has_english_and_german_text_without_placeholders() -> None:
    """D-06, T-11-43: both languages carry a fixed title and description; nothing from the records reaches the text."""
    english, german = _unreadable_issue_text("en"), _unreadable_issue_text("de")

    for language, text in (("en", english), ("de", german)):
        for field in ("title", "description"):
            assert text[field], f"{language}: issues.{UNREADABLE_ISSUE_ID}.{field} is missing or empty"
            assert "{" not in text[field], f"{language}: issues.{UNREADABLE_ISSUE_ID}.{field} has a placeholder"
    assert "not applied" in english["description"], "the English text says the local customizations are not applied"
    assert "refused" in english["description"], "the English text says that editing is refused"
    assert german != english, "the German text is a translation, not a copy of the English one"
