"""
Local actions of mirrors through the Manager (MIR-02, D-02, D-07, D-21).

`test_pending_mirror_with_persisted_additive_record_gains_local_branch` is the only expected-RED test of Phase 11
(11-VALIDATION.md, "Expected-RED Exception"). It was committed by Plan 11-01 Task 2 before the Manager reads the
separate local Store; its GREEN gate is Plan 11-05 Task 1, which may align the seeded record to the Plan 11-04 schema
but never changes an assertion. No marker or condition ever hides its failure.
"""

import copy
import functools
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import PAYLOAD_OFF, PAYLOAD_ON, STORE_MIRRORS, SUBENTRY_SWITCH
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore
from custom_components.mqtt_actions.manager import Manager
from custom_components.mqtt_actions.model import trigger_key
from custom_components.mqtt_actions.topics import state_topic
from tests.documents import document_payload, make_spec
from tests.helpers import BASE, deliver_config, manager_of, restart_entry, seed_store, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.core import HomeAssistant

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
