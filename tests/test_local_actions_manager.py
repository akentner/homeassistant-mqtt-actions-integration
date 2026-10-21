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
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
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
from custom_components.mqtt_actions.local_actions import (
    LOCAL_SAFE_POLICY,
    EffectivePolicy,
    LocalActionMode,
    local_trigger_identity,
)
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore
from custom_components.mqtt_actions.manager import LocalActionError, Manager
from custom_components.mqtt_actions.model import trigger_key
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
    await deliver_config(hass, spec.device_id, document_payload(changed, rev=2))
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
