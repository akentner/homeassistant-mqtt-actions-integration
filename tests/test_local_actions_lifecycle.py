"""
Local actions of mirrors through the owner lifecycle: evolution, orphan and reattach, prune, tombstone, adoption.

D-05: local records survive owner content, name and revision changes, restarts and owner re-pins; a removed Select
option leaves its record inactive and the exact StateValue return reattaches it (D-10 to D-12).
"""

import copy
import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    DOMAIN,
    ISSUE_APPROVAL_PREFIX,
    ISSUE_CIRCUIT_BREAKER_PREFIX,
    PAYLOAD_OFF,
    PAYLOAD_ON,
    PRUNE_GRACE_SECONDS,
    SERVICE_ADOPT_DEVICE,
    STORE_MIRRORS,
    STORE_TRIPPED,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.document import build_content
from custom_components.mqtt_actions.local_actions import LocalActionMode, local_trigger_identity
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore, LocalActionsStoreError
from custom_components.mqtt_actions.manager import AdoptionError
from custom_components.mqtt_actions.model import trigger_key
from custom_components.mqtt_actions.portability import subentry_payload
from custom_components.mqtt_actions.topics import state_topic
from custom_components.mqtt_actions.trust import build_approval_view
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.helpers import BASE, announce_presence, deliver_config, manager_of, restart_entry, seed_store, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Manager
    from custom_components.mqtt_actions.model import DeviceSpec

# Literal on purpose: the production key of the local Store (LOCAL_ACTIONS_STORE_KEY)
LOCAL_STORE_KEY = "mqtt_actions.local_actions"

OWNER_ON = [{"action": "test.owner_on"}]
LOCAL_ON = [{"action": "test.local_on", "data": {"source": "local"}}]
LOCAL_B = [{"action": "test.local_b", "data": {"source": "local"}}]
LOCAL_B2 = [{"action": "test.local_b2", "data": {"source": "local", "edited": True}}]


def _stored_rows(hass_storage: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Return the record rows written to the local Store, None while nothing was written."""
    stored = hass_storage.get(LOCAL_STORE_KEY)
    return None if stored is None else stored["data"]["records"]


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = False) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _owner_sends(hass: HomeAssistant, spec: DeviceSpec, **document: Any) -> None:
    """Deliver a changed owner document live; a second retained document is no update for the follower."""
    await deliver_config(hass, spec.device_id, document_payload(spec, **document), retain=False)


async def _switch_with_local_on(
    hass: HomeAssistant, hass_storage: dict[str, Any], make_hub_entry: Callable, spec: DeviceSpec
) -> tuple[Any, Manager, list[dict[str, Any]] | None]:
    """Set up a follower with a pending switch mirror and an additive local ON record; return the stored rows too."""
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    manager = manager_of(entry)
    await manager.async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON), LocalActionMode.ADDITIVE, LOCAL_ON
    )
    rows = copy.deepcopy(_stored_rows(hass_storage))
    return entry, manager, rows


async def _local_on_runs(hass: HomeAssistant, device_id: str) -> None:
    """Move the switch OFF and then ON with live edges, so the ON trigger runs once."""
    await _state(hass, device_id, PAYLOAD_OFF)
    await _state(hass, device_id, PAYLOAD_ON)


def _assert_one_active_on_record(manager: Manager, spec: DeviceSpec) -> None:
    """The ON trigger of the mirror still carries the saved record under its original identity."""
    rows = {row.state_value: row for row in manager.local_action_triggers(spec.device_id)}
    record = rows[PAYLOAD_ON].record
    assert rows[PAYLOAD_ON].present is True
    assert record is not None
    assert record.identity == local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON)
    assert record.actions == LOCAL_ON


# --- Task 1: survival through owner evolution (D-05, D-10, D-11) -----------------------------------------------------


async def test_records_survive_owner_content_change(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05: new owner actions keep the local record, its Store bytes and its local branch."""
    local_calls = async_mock_service(hass, "test", "local_on")
    async_mock_service(hass, "test", "owner_changed")
    spec = make_spec(on=OWNER_ON)
    _entry, manager, rows = await _switch_with_local_on(hass, hass_storage, make_hub_entry, spec)

    changed = make_spec(device_id=spec.device_id, on=[{"action": "test.owner_changed"}])
    await _owner_sends(hass, changed, rev=2)

    assert manager.mirrors[spec.device_id].spec.triggers[trigger_key(PAYLOAD_ON)].actions == [
        {"action": "test.owner_changed"}
    ], "premise: the changed owner document was applied"
    assert _stored_rows(hass_storage) == rows, "an owner content change never rewrites or drops a local record"
    _assert_one_active_on_record(manager, spec)
    await _local_on_runs(hass, spec.device_id)
    assert len(local_calls) == 1


async def test_records_survive_owner_rename(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-10: a new device name is no part of the identity; the record stays and runs."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(name="Lamp", on=OWNER_ON)
    _entry, manager, rows = await _switch_with_local_on(hass, hass_storage, make_hub_entry, spec)

    await _owner_sends(hass, make_spec(device_id=spec.device_id, name="Renamed lamp", on=OWNER_ON), rev=2)

    assert manager.mirrors[spec.device_id].name == "Renamed lamp", "premise: the rename was applied"
    assert _stored_rows(hass_storage) == rows
    _assert_one_active_on_record(manager, spec)
    await _local_on_runs(hass, spec.device_id)
    assert len(local_calls) == 1


async def test_records_survive_owner_revision_bump(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05: a higher revision with the same content changes nothing local."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    _entry, manager, rows = await _switch_with_local_on(hass, hass_storage, make_hub_entry, spec)

    await _owner_sends(hass, spec, rev=7)

    assert _stored_rows(hass_storage) == rows
    _assert_one_active_on_record(manager, spec)
    await _local_on_runs(hass, spec.device_id)
    assert len(local_calls) == 1


async def test_records_survive_restart(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-07: a restart restores the cached mirror and its saved record without rewriting the local Store."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    entry, _manager, rows = await _switch_with_local_on(hass, hass_storage, make_hub_entry, spec)
    stored = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])

    await restart_entry(hass, entry)
    manager = manager_of(entry)

    assert spec.device_id in manager.mirrors, "premise: the mirror is restored from the cache"
    assert hass_storage[LOCAL_STORE_KEY] == stored
    assert _stored_rows(hass_storage) == rows
    _assert_one_active_on_record(manager, spec)
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    await _state(hass, spec.device_id, PAYLOAD_ON)
    assert len(local_calls) == 1


async def test_records_survive_owner_repin(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-09: following the adopter of an offline owner keeps the local record and its branch."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=OWNER_ON)
    _entry, manager, rows = await _switch_with_local_on(hass, hass_storage, make_hub_entry, spec)
    await announce_presence(hass, "offline")

    await _owner_sends(hass, spec, owner="adopter", owner_name="Adopter", rev=2, transferred_from=[FOREIGN_OWNER])

    info = manager.mirrors[spec.device_id].mirror
    assert info is not None
    assert info.owner == "adopter", "premise: the mirror follows the adopter"
    assert _stored_rows(hass_storage) == rows
    _assert_one_active_on_record(manager, spec)
    await _local_on_runs(hass, spec.device_id)
    assert len(local_calls) == 1


# --- Task 1: orphan, reattach, label refresh and kind mismatch (D-05, D-11, D-12) -------------------------------------


def _select(options: list[tuple[str, str]], device_id: str | None = None) -> DeviceSpec:
    return make_spec(SUBENTRY_SELECT, device_id=device_id, options=[(value, name, []) for value, name in options])


async def _select_with_local_b(
    hass: HomeAssistant, make_hub_entry: Callable, spec: DeviceSpec, actions: list[dict[str, Any]] = LOCAL_B
) -> tuple[Any, Manager]:
    """Set up a follower with a pending Select mirror at `a` and an additive local record on option `b`."""
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "a", retain=True)
    manager = manager_of(entry)
    await manager.async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "b"), LocalActionMode.ADDITIVE, actions
    )
    return entry, manager


def _row(manager: Manager, device_id: str, state_value: str) -> Any:
    return next(row for row in manager.local_action_triggers(device_id) if row.state_value == state_value)


async def test_option_rename_survives_with_refreshed_label(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-11: an owner rename of a present option refreshes the saved label durably; identity and actions stay."""
    local_calls = async_mock_service(hass, "test", "local_b")
    spec = _select([("a", "A"), ("b", "B")])
    _entry, manager = await _select_with_local_b(hass, make_hub_entry, spec)
    rows = _stored_rows(hass_storage)
    assert rows is not None
    assert rows[0]["label"] == "B", "premise: the record was saved with the friendly name of the option"

    await _owner_sends(hass, _select([("a", "A"), ("b", "Bee")], spec.device_id), rev=2)

    assert _stored_rows(hass_storage) == [{**rows[0], "label": "Bee"}], (
        "the last known friendly name is refreshed in the local Store; nothing else of the record changes"
    )
    row = _row(manager, spec.device_id, "b")
    assert row.present is True
    assert row.label == "Bee"
    assert row.record is not None
    assert row.record.identity == local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "b")
    assert row.record.label == "Bee"
    assert row.record.actions == LOCAL_B
    await _state(hass, spec.device_id, "b")
    assert len(local_calls) == 1


async def test_label_refresh_save_failure_keeps_the_old_label_and_the_owner_update(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-22: a label refresh that cannot be saved keeps the old label everywhere; the owner change still applies."""
    local_calls = async_mock_service(hass, "test", "local_b")
    spec = _select([("a", "A"), ("b", "B")])
    _entry, manager = await _select_with_local_b(hass, make_hub_entry, spec)
    rows = copy.deepcopy(_stored_rows(hass_storage))

    with patch.object(LocalActionsStore, "_async_write_data", AsyncMock(side_effect=OSError("disk full"))):
        await _owner_sends(hass, _select([("a", "A"), ("b", "Bee")], spec.device_id), rev=2)

    assert manager.mirrors[spec.device_id].spec.triggers[trigger_key("b")].friendly_name == "Bee"
    assert _stored_rows(hass_storage) == rows
    row = _row(manager, spec.device_id, "b")
    assert row.record is not None
    assert row.record.label == "B", "memory keeps the label that is on disk"
    await _state(hass, spec.device_id, "b")
    assert len(local_calls) == 1, "the record stays active"


async def test_removed_option_orphans_the_record_and_exact_return_reattaches(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-12: a removed option leaves an inactive, editable record; its return runs the saved raw actions."""
    first = async_mock_service(hass, "test", "local_b")
    edited = async_mock_service(hass, "test", "local_b2")
    spec = _select([("a", "A"), ("b", "B")])
    entry, manager = await _select_with_local_b(hass, make_hub_entry, spec)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "b")

    await _owner_sends(hass, _select([("a", "A"), ("c", "C")], spec.device_id), rev=2)

    orphan = _row(manager, spec.device_id, "b")
    assert orphan.present is False
    assert orphan.label == "B", "an orphan keeps its last known friendly name"
    assert orphan.record is not None
    assert orphan.record.actions == LOCAL_B
    assert manager.runner.can_run(spec.device_id, trigger_key("b")) is False, "an orphan supplies no runner plan"
    counts = manager.local_action_counts()
    assert (counts.records, counts.active, counts.inactive, counts.orphan_only_devices) == (1, 0, 1, 1)

    change = await manager.async_set_local_action(identity, LocalActionMode.ADDITIVE, LOCAL_B2)
    assert change.active is False, "editing an orphan does not activate it"
    await _state(hass, spec.device_id, "b")
    await _state(hass, spec.device_id, "c")
    assert (first, edited) == ([], []), "an orphan never runs"

    # Neither a restart nor the owner's next change deletes the orphan record
    stored = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    await restart_entry(hass, entry)
    manager = manager_of(entry)
    await _owner_sends(hass, _select([("a", "A"), ("c", "Cee")], spec.device_id), rev=3)
    assert hass_storage[LOCAL_STORE_KEY] == stored
    assert _row(manager, spec.device_id, "b").present is False

    # The exact StateValue returns, under a new friendly name and another case
    await _owner_sends(hass, _select([("a", "A"), ("B", "Bee")], spec.device_id), rev=4)

    row = next(row for row in manager.local_action_triggers(spec.device_id) if row.record is not None)
    assert row.present is True
    assert row.record.identity == identity
    assert row.record.actions == LOCAL_B2, "the reattached trigger uses the saved raw local actions"
    await _state(hass, spec.device_id, "a")
    await _state(hass, spec.device_id, "B")
    assert first == []
    assert len(edited) == 1
    assert edited[0].data == {"source": "local", "edited": True}


async def test_orphan_record_stays_removable(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-12: the user can delete an orphan record through the Manager API; the device then has no local row."""
    spec = _select([("a", "A"), ("b", "B")])
    _entry, manager = await _select_with_local_b(hass, make_hub_entry, spec)
    await _owner_sends(hass, _select([("a", "A"), ("c", "C")], spec.device_id), rev=2)
    assert _row(manager, spec.device_id, "b").present is False, "premise: the record is an orphan"

    change = await manager.async_remove_local_action(local_trigger_identity(spec.device_id, SUBENTRY_SELECT, "b"))

    assert change.record is None
    assert _stored_rows(hass_storage) == []
    assert [row.record for row in manager.local_action_triggers(spec.device_id)] == [None, None]


async def test_kind_mismatched_record_stays_inactive_through_owner_changes(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-10, D-12: a switch record on a Select id never applies, survives every owner change and stays editable."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = _select([("on", "On"), ("off", "Off")])
    hass_storage[LOCAL_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_STORE_KEY,
        "data": {
            "records": [
                {
                    "device_id": spec.device_id,
                    "kind": SUBENTRY_SWITCH,
                    "state_value": PAYLOAD_ON,
                    "label": "ON",
                    "mode": "replacement",
                    "actions": LOCAL_ON,
                }
            ]
        },
    }
    stored = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    manager = manager_of(entry)
    await _state(hass, spec.device_id, "off", retain=True)

    await _owner_sends(hass, _select([("on", "Switched on"), ("off", "Off")], spec.device_id), rev=2)
    await _state(hass, spec.device_id, "on")

    assert local_calls == [], "a record of the other kind never applies"
    assert hass_storage[LOCAL_STORE_KEY] == stored, "an owner change neither refreshes nor drops a mismatched record"
    mismatch = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON)
    inactive = [row for row in manager.local_action_triggers(spec.device_id) if not row.present]
    assert [row.identity for row in inactive] == [mismatch]
    change = await manager.async_set_local_action(mismatch, LocalActionMode.ADDITIVE, LOCAL_ON)
    assert change.active is False


# --- Task 2: transient prune keeps, a tombstone destroys, even after a prune (D-05, D-08) ----------------------------

OTHER_DEVICE = "0f0e0d0c-0b0a-4908-8706-050403020100"


def _row_data(device_id: str, state_value: str = PAYLOAD_ON, kind: str = SUBENTRY_SWITCH) -> dict[str, Any]:
    """Return the stored v1 row of an additive record."""
    return {
        "device_id": device_id,
        "kind": kind,
        "state_value": state_value,
        "label": state_value,
        "mode": "additive",
        "actions": LOCAL_ON,
    }


def _seed_local(hass_storage: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    hass_storage[LOCAL_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_STORE_KEY,
        "data": {"records": rows},
    }


async def _cached_mirror_with_records(
    hass: HomeAssistant, hass_storage: dict[str, Any], make_hub_entry: Callable, spec: DeviceSpec
) -> tuple[Any, Manager]:
    """Start a follower whose mirror comes from the cache only, with ON and OFF records plus another device's record."""
    seed_store(hass_storage, {STORE_MIRRORS: {spec.device_id: document_payload(spec)}})
    _seed_local(
        hass_storage,
        [_row_data(spec.device_id), _row_data(spec.device_id, PAYLOAD_OFF), _row_data(OTHER_DEVICE)],
    )
    entry = await setup_entry(hass, make_hub_entry())
    manager = manager_of(entry)
    assert spec.device_id in manager.mirrors, "premise: the mirror is restored from the cache"
    return entry, manager


async def _prune(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Announce the owner online and let the grace window pass: an unseen mirror of an online owner is pruned."""
    await announce_presence(hass, "online")
    freezer.tick(timedelta(seconds=PRUNE_GRACE_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _own_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name.startswith("custom_components")]


async def test_transient_prune_keeps_local_records_byte_identical(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-05: a prune removes the runtime mirror, never its local records; they stay listed and manageable."""
    spec = make_spec(on=OWNER_ON)
    _entry, manager = await _cached_mirror_with_records(hass, hass_storage, make_hub_entry, spec)
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])

    await _prune(hass, freezer)

    assert spec.device_id not in manager.mirrors, "premise: the prune removed the mirror"
    assert hass_storage[LOCAL_STORE_KEY] == before, "a prune never changes the local Store"
    listed = {device.device_id: device for device in manager.local_action_devices()}
    assert listed[spec.device_id].mirrored is False
    assert listed[spec.device_id].records == 2


async def test_startup_cleanup_of_a_cached_mirror_keeps_local_records(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-05: the start drops a cached mirror of an id owned here, and keeps every local record of that id."""
    sub = make_switch_subentry("Lamp", on=OWNER_ON)
    owned = sub["data"][CONF_DEVICE_ID]
    spec = make_spec(device_id=owned, on=OWNER_ON)
    seed_store(hass_storage, {STORE_MIRRORS: {owned: document_payload(spec)}})
    _seed_local(hass_storage, [_row_data(owned)])
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])

    manager = manager_of(await setup_entry(hass, make_hub_entry([sub])))

    assert owned in manager.devices
    assert owned not in manager.mirrors
    assert hass_storage[LOCAL_STORE_KEY] == before


async def test_tombstone_discards_records_saves_at_once_and_publishes_nothing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-05: a tombstone deletes every record of the device, saves without delay and logs the count only."""
    spec = make_spec(on=OWNER_ON)
    _entry, manager = await _cached_mirror_with_records(hass, hass_storage, make_hub_entry, spec)
    mqtt_mock.async_publish.reset_mock()

    with caplog.at_level(logging.INFO):
        await deliver_config(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in manager.mirrors
    assert _stored_rows(hass_storage) == [_row_data(OTHER_DEVICE)], "only the tombstoned device loses its records"
    assert [device.device_id for device in manager.local_action_devices()] == [OTHER_DEVICE]
    assert mqtt_mock.async_publish.call_count == 0, "deleting local records publishes nothing"
    messages = _own_messages(caplog)
    assert any("2 local actions" in message for message in messages), messages
    assert not any("test.local_on" in message for message in messages), "no action content reaches the log"


async def test_tombstone_after_prune_still_discards_records(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-05: the tombstone that follows an earlier prune deletes the records although no mirror exists any more."""
    spec = make_spec(on=OWNER_ON)
    _entry, manager = await _cached_mirror_with_records(hass, hass_storage, make_hub_entry, spec)
    await _prune(hass, freezer)
    assert spec.device_id not in manager.mirrors, "premise: the prune removed the mirror"
    assert len(_stored_rows(hass_storage) or []) == 3, "premise: the prune kept the records"
    mqtt_mock.async_publish.reset_mock()

    await deliver_config(hass, spec.device_id, "", retain=False)

    assert _stored_rows(hass_storage) == [_row_data(OTHER_DEVICE)]
    assert [device.device_id for device in manager.local_action_devices()] == [OTHER_DEVICE]
    assert mqtt_mock.async_publish.call_count == 0


async def test_tombstone_cause_reaches_the_manager_without_a_mirror(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """The manager seam: a tombstone of an id without a mirror deletes its records instead of returning early."""
    from custom_components.mqtt_actions.manager import MirrorRemovalCause

    _seed_local(hass_storage, [_row_data(OTHER_DEVICE), _row_data(OTHER_DEVICE, PAYLOAD_OFF)])
    manager = manager_of(await setup_entry(hass, make_hub_entry()))
    assert OTHER_DEVICE not in manager.mirrors

    async with manager.lock:
        await manager.async_remove_mirror(OTHER_DEVICE, cause=MirrorRemovalCause.TRANSIENT_PRUNE)
    assert len(_stored_rows(hass_storage) or []) == 2, "a prune cause keeps the records"

    async with manager.lock:
        await manager.async_remove_mirror(OTHER_DEVICE, cause=MirrorRemovalCause.TOMBSTONE)
    assert _stored_rows(hass_storage) == []
    assert manager.local_action_devices() == ()


async def test_tombstone_on_an_owned_id_keeps_its_records(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """An owned id is never a mirror: the owner heals its topic and no local record of that id is touched."""
    sub = make_switch_subentry("Lamp", on=OWNER_ON)
    owned = sub["data"][CONF_DEVICE_ID]
    _seed_local(hass_storage, [_row_data(owned)])
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    manager = manager_of(await setup_entry(hass, make_hub_entry([sub])))

    await deliver_config(hass, owned, "", retain=False)

    assert owned in manager.devices
    assert hass_storage[LOCAL_STORE_KEY] == before


async def test_tombstone_without_records_writes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """A tombstone of a mirror that has no local record leaves the local Store unwritten."""
    spec = make_spec(on=OWNER_ON)
    manager = manager_of(await setup_entry(hass, make_hub_entry()))
    await deliver_config(hass, spec.device_id, document_payload(spec))

    await deliver_config(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in manager.mirrors
    assert LOCAL_STORE_KEY not in hass_storage


async def test_tombstone_save_failure_keeps_the_records_and_removes_the_mirror(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-22: when the discard cannot be saved the records stay, on disk and in memory; the mirror still goes."""
    spec = make_spec(on=OWNER_ON)
    _entry, manager = await _cached_mirror_with_records(hass, hass_storage, make_hub_entry, spec)
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])

    with patch.object(LocalActionsStore, "_async_write_data", AsyncMock(side_effect=OSError("disk full"))):
        await deliver_config(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in manager.mirrors
    assert hass_storage[LOCAL_STORE_KEY] == before
    assert manager.local_action_counts().records == 3


# --- Task 3: adoption discards only when it completes, reports the count, rolls back on failure (D-04, D-05) --------


async def _adoptable_mirror(
    hass: HomeAssistant, hass_storage: dict[str, Any], make_hub_entry: Callable, *, approve: bool = True
) -> tuple[Any, Manager, DeviceSpec]:
    """
    Start a follower with the mirror of an offline owner and three records: ON and OFF of the mirror, one elsewhere.

    The OFF record of the mirror is a kind mismatch (Select kind), so an inactive record of the device is counted too.
    """
    spec = make_spec(name="Foreign lamp", on=OWNER_ON)
    _seed_local(
        hass_storage,
        [
            {**_row_data(spec.device_id), "mode": "replacement"},
            {**_row_data(spec.device_id, PAYLOAD_OFF, SUBENTRY_SELECT), "mode": "replacement"},
            _row_data(OTHER_DEVICE),
        ],
    )
    entry = await setup_entry(hass, make_hub_entry())
    await announce_presence(hass, "offline")
    await deliver_config(hass, spec.device_id, document_payload(spec))
    manager = manager_of(entry)
    if approve:
        info = manager.mirrors[spec.device_id].mirror
        assert info is not None
        assert await manager.async_approve(spec.device_id, info.actions_hash) is True
    return entry, manager, spec


async def test_adoption_refused_for_a_pending_owner_keeps_records_even_with_every_trigger_replaced(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-04, T-11-18: replacing every trigger locally never satisfies the owner approval that adoption requires."""
    _entry, manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry, approve=False)
    await manager.async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_OFF), LocalActionMode.REPLACEMENT, []
    )
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    assert str(manager.approval_state(spec.device_id)) == "pending"
    mqtt_mock.async_publish.reset_mock()

    for force in (False, True):
        with pytest.raises(AdoptionError) as refused:
            await manager.async_adopt_device(spec.device_id, force=force)
        assert refused.value.reason == "not_approved"

    assert spec.device_id in manager.mirrors
    assert hass_storage[LOCAL_STORE_KEY] == before, "a refused adoption keeps every record"
    assert mqtt_mock.async_publish.call_count == 0


async def test_adoption_discards_records_before_any_publish_and_reports_the_count(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-05: the completed adoption saves the discard before the owned device publishes, and says how many."""
    entry, manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry)
    mqtt_mock.async_publish.reset_mock()
    publishes_at_save: list[int] = []
    original_save = LocalActionsStore.async_save_records

    async def _save(self: LocalActionsStore, records: Any) -> Any:
        publishes_at_save.append(mqtt_mock.async_publish.call_count)
        return await original_save(self, records)

    monkeypatch.setattr(LocalActionsStore, "async_save_records", _save)

    with caplog.at_level(logging.INFO):
        result = await manager.async_adopt_device(spec.device_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (type(result).__name__, result.previous_owner, result.local_actions_discarded) == (
        "AdoptionResult",
        "Foreign instance",
        2,
    )
    assert spec.device_id in manager.devices
    assert _stored_rows(hass_storage) == [_row_data(OTHER_DEVICE)]
    assert publishes_at_save == [0], "the discard is durable before the adopted device publishes anything"
    assert mqtt_mock.async_publish.call_count > 0, "premise: the adopted device publishes afterwards"
    subentry = next(item for item in entry.subentries.values() if item.unique_id == spec.device_id)
    assert dict(subentry.data) == subentry_payload(build_content(spec), spec.device_id)
    assert "test.local" not in json.dumps(dict(subentry.data)), "no local content enters the adopted subentry"
    assert [device.device_id for device in manager.local_action_devices()] == [OTHER_DEVICE]
    messages = _own_messages(caplog)
    assert any("2 local actions" in message for message in messages), messages
    assert not any("test.local" in message for message in messages)


async def test_adopt_wrapper_still_returns_the_previous_owner_name(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """The existing `async_adopt` contract stays a plain str; it discards the same way."""
    _entry, manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry)

    assert await manager.async_adopt(spec.device_id) == "Foreign instance"
    assert _stored_rows(hass_storage) == [_row_data(OTHER_DEVICE)]


async def test_adoption_local_save_failure_changes_nothing_and_publishes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-11-17: when the discard cannot be saved the adoption stops before anything changed."""
    entry, manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry)
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    counts = manager.local_action_counts()
    mqtt_mock.async_publish.reset_mock()

    with (
        patch.object(LocalActionsStore, "_async_write_data", AsyncMock(side_effect=OSError("disk full"))),
        pytest.raises(LocalActionsStoreError),
    ):
        await manager.async_adopt_device(spec.device_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert spec.device_id in manager.mirrors
    assert spec.device_id not in manager.devices
    assert entry.subentries == {}
    assert str(manager.approval_state(spec.device_id)) == "approved"
    assert hass_storage[LOCAL_STORE_KEY] == before
    assert manager.local_action_counts() == counts
    assert mqtt_mock.async_publish.call_count == 0
    # Nothing was half done: the next attempt adopts and discards normally
    assert (await manager.async_adopt_device(spec.device_id)).local_actions_discarded == 2


async def test_adoption_subentry_failure_restores_mirror_and_records_and_publishes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-11-17: a failed subentry creation rolls back the local discard as well as the mirror."""
    local_calls = async_mock_service(hass, "test", "local_on")
    owner_calls = async_mock_service(hass, "test", "owner_on")
    entry, manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry)
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    counts = manager.local_action_counts()
    mqtt_mock.async_publish.reset_mock()

    with (
        patch.object(hass.config_entries, "async_add_subentry", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        await manager.async_adopt_device(spec.device_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert spec.device_id in manager.mirrors
    assert entry.subentries == {}
    assert str(manager.approval_state(spec.device_id)) == "approved"
    assert hass_storage[LOCAL_STORE_KEY] == before, "the discard is undone on disk"
    assert manager.local_action_counts() == counts
    assert mqtt_mock.async_publish.call_count == 0
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    await _state(hass, spec.device_id, PAYLOAD_ON)
    assert (len(local_calls), owner_calls) == (1, []), "the restored mirror runs its local replacement again"


# Literal on purpose: the production key of the main Store (STORE_KEY)
MAIN_STORE_KEY = "mqtt_actions.state"


def _breaker_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_CIRCUIT_BREAKER_PREFIX}{device_id}")


async def _trip_by_local_runs(hass: HomeAssistant, manager: Manager, spec: DeviceSpec) -> None:
    """Toggle the adoptable mirror, whose ON edge runs its local replacement, until the safe breaker trips."""
    for _ in range(10):
        await _state(hass, spec.device_id, PAYLOAD_OFF)
        await _state(hass, spec.device_id, PAYLOAD_ON)
        if manager.device(spec.device_id).breaker.tripped:
            break
    assert manager.device(spec.device_id).breaker.tripped, "premise: repeated local runs trip the safe breaker"
    assert _breaker_issue(hass, spec.device_id) is not None


async def test_failed_adoption_keeps_a_tripped_breaker_paused(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """MIR-09, Phase 2 D-17, T-11-17: a failed adoption releases no breaker; the trip is saved at once (G-04)."""
    local_calls = async_mock_service(hass, "test", "local_on")
    owner_calls = async_mock_service(hass, "test", "owner_on")
    entry, manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry)
    await _trip_by_local_runs(hass, manager, spec)
    await hass.async_block_till_done(wait_background_tasks=True)
    mqtt_mock.async_publish.reset_mock()

    for attempt in (1, 2):
        with (
            patch.object(hass.config_entries, "async_add_subentry", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            await manager.async_adopt_device(spec.device_id)

        assert manager.device(spec.device_id).breaker.tripped, f"attempt {attempt}: the restored mirror stays paused"
        assert _breaker_issue(hass, spec.device_id) is not None, attempt
        # Read before any clock advance or wait: the trip must not depend on a delayed save
        assert spec.device_id in hass_storage[MAIN_STORE_KEY]["data"][STORE_TRIPPED], attempt
        await hass.async_block_till_done(wait_background_tasks=True)
        assert spec.device_id in manager.mirrors
        assert entry.subentries == {}
        assert str(manager.approval_state(spec.device_id)) == "approved"
        calls = (len(local_calls), len(owner_calls))
        await _state(hass, spec.device_id, PAYLOAD_OFF)
        await _state(hass, spec.device_id, PAYLOAD_ON)
        assert (len(local_calls), len(owner_calls)) == calls, f"attempt {attempt}: a paused mirror runs nothing"
        assert mqtt_mock.async_publish.call_count == 0, attempt


async def test_adopt_service_reports_the_discarded_count(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """The admin response names how many local actions the adoption discarded, next to the unchanged fields."""
    entry, _manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry)
    companion = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, spec.device_id), entry.entry_id)
    assert companion is not None

    result = await hass.services.async_call(
        DOMAIN, SERVICE_ADOPT_DEVICE, {"device_id": companion.id}, blocking=True, return_response=True
    )

    assert result == {
        "uuid": spec.device_id,
        "adopted": True,
        "previous_owner": "Foreign instance",
        "local_actions_discarded": 2,
    }


# --- Plan 11-07 Task 3: the approval names local replacements without moving owner authority (D-04, D-17) -------------


def _approval_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{device_id}")


async def test_approval_view_and_issue_count_active_replacements_only(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """MIR-12, D-17: active replacements, muted ones too, are counted; additive, orphan and other-kind ones are not."""
    spec = make_spec(SUBENTRY_SELECT, options=[("a", "A", OWNER_ON), ("b", "B", OWNER_ON), ("c", "C", OWNER_ON)])
    _seed_local(
        hass_storage,
        [
            {**_row_data(spec.device_id, "gone", SUBENTRY_SELECT), "mode": "replacement"},  # an orphan
            {**_row_data(spec.device_id, "a", SUBENTRY_SWITCH), "mode": "replacement"},  # the other kind
            {**_row_data(OTHER_DEVICE, "a", SUBENTRY_SELECT), "mode": "replacement"},  # another device
        ],
    )
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    manager = manager_of(entry)
    view = await manager.async_approval_view(spec.device_id)
    assert view is not None
    assert view.replaced_trigger_count == 0, "inactive records replace nothing"
    issue = _approval_issue(hass, spec.device_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["replaced"] == "0"
    ir.async_get(hass).async_ignore(DOMAIN, issue.issue_id, ignore=True)

    for value, mode, actions in (
        ("a", LocalActionMode.REPLACEMENT, LOCAL_B),
        ("b", LocalActionMode.REPLACEMENT, []),
        ("c", LocalActionMode.ADDITIVE, LOCAL_B),
    ):
        await manager.async_set_local_action(
            local_trigger_identity(spec.device_id, SUBENTRY_SELECT, value), mode, actions
        )

    view = await manager.async_approval_view(spec.device_id)
    assert view is not None
    assert view.replaced_trigger_count == 2, "the replacement and the muted trigger, not the additive one"
    issue = _approval_issue(hass, spec.device_id)
    assert issue is not None, "a local edit never clears the owner approval request"
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["replaced"] == "2"
    assert issue.dismissed_version is not None, "a count update keeps the user's dismissal"
    assert str(manager.approval_state(spec.device_id)) == "pending"


async def test_every_trigger_replaced_keeps_pending_owner_hash_yaml_and_refused_adoption(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-04, D-17, T-11-22: with every owner trigger replaced the approval still concerns the owner actions only."""
    _entry, manager, spec = await _adoptable_mirror(hass, hass_storage, make_hub_entry, approve=False)
    info = manager.mirrors[spec.device_id].mirror
    assert info is not None
    owner_only = build_approval_view(spec, info, [])
    await manager.async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_OFF), LocalActionMode.REPLACEMENT, LOCAL_B
    )

    view = await manager.async_approval_view(spec.device_id)
    assert view is not None
    assert view.replaced_trigger_count == 2
    assert view.actions_yaml == owner_only.actions_yaml, "the review shows the owner actions only"
    assert "local" not in view.actions_yaml
    assert (view.actions_hash, view.short_hash) == (owner_only.actions_hash, owner_only.short_hash)
    assert view.actions_hash == info.actions_hash
    assert str(manager.approval_state(spec.device_id)) == "pending", "replacing every trigger approves nothing"
    issue = _approval_issue(hass, spec.device_id)
    assert issue is not None
    assert issue.data == {"device_id": spec.device_id, "actions_hash": info.actions_hash}
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["replaced"] == "2"
    with pytest.raises(AdoptionError) as refused:
        await manager.async_adopt_device(spec.device_id, force=True)
    assert refused.value.reason == "not_approved"


# --- Plan 11-14 (G-01): the local failure issue lives as long as its customization (D-19, MIR-13, T-11-21) ------------

# Literal on purpose: the production prefix of the local failure issue (ISSUE_LOCAL_ACTION_FAILED_PREFIX)
LOCAL_ISSUE_PREFIX = "local_action_failed_"
LOCAL_FAIL = [{"action": "test.local_fail"}]
LOCAL_FAIL_ERROR = "local boom"


class FailingLocal:
    """`test.local_fail` raises while `failing` is set and records every call."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.failing = True
        self.calls = 0
        hass.services.async_register("test", "local_fail", self._handle)

    async def _handle(self, _call: Any) -> None:
        self.calls += 1
        if self.failing:
            raise HomeAssistantError(LOCAL_FAIL_ERROR)


def _local_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{LOCAL_ISSUE_PREFIX}{device_id}")


async def _reload_issue_registry(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Put the issue registry's own saved data into its storage, as HA does at shutdown, and load it like a start."""
    registry = ir.async_get(hass)
    data = registry._data_to_save()
    # The test Store of the registry writes nothing; this save only consumes the pending delayed write
    await registry._store.async_save(data)
    envelope = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "key": ir.STORAGE_KEY,
        "data": data,
    }
    hass_storage[ir.STORAGE_KEY] = json.loads(json.dumps(envelope))
    await registry.async_load()


async def _failing_local_mirror(
    hass: HomeAssistant, make_hub_entry: Callable, spec: DeviceSpec, entry: Any = None
) -> tuple[Any, Manager]:
    """Set up (or reuse) a follower with a pending mirror whose additive ON record calls the failing service."""
    entry = entry or await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    manager = manager_of(entry)
    await manager.async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON), LocalActionMode.ADDITIVE, LOCAL_FAIL
    )
    return entry, manager


async def test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """G-01, D-19: only a proven success of the named trigger or removal of its customization ends the local issue."""
    failing = FailingLocal(hass)
    async_mock_service(hass, "test", "owner_on")
    spec = make_spec(on=OWNER_ON)
    identity = local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON)
    entry, manager = await _failing_local_mirror(hass, make_hub_entry, spec)
    await _local_on_runs(hass, spec.device_id)
    raised = _local_issue(hass, spec.device_id)
    assert raised is not None, "premise: the failed local run raised the local failure issue"
    assert raised.translation_placeholders is not None
    named = {key: raised.translation_placeholders[key] for key in ("trigger", "error")}

    # A restart of Home Assistant: the issue registry comes back from its own storage, then the integration starts
    await _reload_issue_registry(hass, hass_storage)
    await restart_entry(hass, entry)
    manager = manager_of(entry)
    restored = _local_issue(hass, spec.device_id)
    assert restored is not None
    assert restored.active is True, "the local failure issue must survive a restart of Home Assistant"
    expected_data = {"kind": identity.kind, "state_value": identity.state_value}
    assert restored.data == expected_data, "the identity of the named trigger survives the restart"
    assert restored.translation_placeholders is not None
    assert {key: restored.translation_placeholders[key] for key in ("trigger", "error")} == named

    # A transient prune of the cached mirror keeps the record, so it keeps the issue
    await _prune(hass, freezer)
    assert spec.device_id not in manager.mirrors, "premise: the prune removed the mirror"
    assert manager.local_action_counts().records == 1, "premise: the prune kept the record"
    assert _local_issue(hass, spec.device_id) is not None, "a transient prune keeps the local failure issue"

    # The owner document returns; a failed adoption keeps the record, so it keeps the issue
    await deliver_config(hass, spec.device_id, document_payload(spec))
    assert spec.device_id in manager.mirrors, "premise: the mirror is back"
    info = manager.mirrors[spec.device_id].mirror
    assert info is not None
    assert await manager.async_approve(spec.device_id, info.actions_hash) is True
    with (
        patch.object(hass.config_entries, "async_add_subentry", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        await manager.async_adopt_device(spec.device_id, force=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert spec.device_id in manager.mirrors, "premise: the rollback restored the mirror"
    assert manager.local_action_counts().records == 1, "premise: the rollback restored the record"
    assert _local_issue(hass, spec.device_id) is not None, "a failed adoption keeps the local failure issue"

    # A proven success of the named trigger clears the issue
    failing.failing = False
    calls = failing.calls
    await _local_on_runs(hass, spec.device_id)
    assert failing.calls == calls + 1, "premise: the local branch ran"
    assert _local_issue(hass, spec.device_id) is None, "a proven success of the named trigger clears the issue"

    # A new failure raises it again, and removing that trigger's customization deletes it
    failing.failing = True
    await _local_on_runs(hass, spec.device_id)
    assert _local_issue(hass, spec.device_id) is not None, "premise: the new failure raised the issue again"
    await manager.async_remove_local_action(identity)
    assert _local_issue(hass, spec.device_id) is None, "removing the customization deletes the issue"


async def test_tombstone_and_completed_adoption_delete_the_local_failure_issue(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-19: a saved tombstone discard and a completed adoption end the customization, and its issue with it."""
    FailingLocal(hass)
    async_mock_service(hass, "test", "owner_on")
    tombstoned = make_spec(name="Tombstoned lamp", on=OWNER_ON)
    adopted = make_spec(name="Adopted lamp", on=OWNER_ON)
    entry, manager = await _failing_local_mirror(hass, make_hub_entry, tombstoned)
    await _failing_local_mirror(hass, make_hub_entry, adopted, entry)
    await _local_on_runs(hass, tombstoned.device_id)
    await _local_on_runs(hass, adopted.device_id)
    assert _local_issue(hass, tombstoned.device_id) is not None, "premise: the failure raised the issue"
    assert _local_issue(hass, adopted.device_id) is not None, "premise: the failure raised the issue"

    await deliver_config(hass, tombstoned.device_id, "", retain=False)
    assert tombstoned.device_id not in manager.mirrors
    assert _local_issue(hass, tombstoned.device_id) is None, "a saved tombstone discard deletes the issue"

    info = manager.mirrors[adopted.device_id].mirror
    assert info is not None
    assert await manager.async_approve(adopted.device_id, info.actions_hash) is True
    assert (await manager.async_adopt_device(adopted.device_id, force=True)).local_actions_discarded == 1
    await hass.async_block_till_done(wait_background_tasks=True)
    assert adopted.device_id in manager.devices
    assert _local_issue(hass, adopted.device_id) is None, "a completed adoption deletes the issue"


# --- Plan 11-14 Task 2: a start deletes a local failure issue whose record is gone (D-05, D-19, T-11-40) --------------

STALE_DEVICE = "1a2b3c4d-5e6f-4a0b-8c1d-2e3f4a5b6c7d"
LEFTOVER_DEVICE = "7d6c5b4a-3f2e-4d1c-8b0a-6f5e4d3c2b1a"
SEEDED_PLACEHOLDERS = {"device": "Lamp", "trigger": "onChangeToOn", "time": "2026-10-21T00:00:00+00:00", "error": "x"}


def _persistent_issue_row(device_id: str, state_value: str = PAYLOAD_ON) -> dict[str, Any]:
    """Return the stored row of a persistent local failure issue naming the switch trigger `state_value`."""
    identity = local_trigger_identity(device_id, SUBENTRY_SWITCH, state_value)
    return {
        "created": "2026-10-21T00:00:00+00:00",
        "dismissed_version": None,
        "domain": DOMAIN,
        "is_persistent": True,
        "issue_id": f"{LOCAL_ISSUE_PREFIX}{device_id}",
        "breaks_in_ha_version": None,
        "data": {"kind": identity.kind, "state_value": identity.state_value},
        "is_fixable": False,
        "issue_domain": None,
        "learn_more_url": None,
        "severity": "error",
        "translation_key": "local_action_failed",
        "translation_placeholders": dict(SEEDED_PLACEHOLDERS),
    }


def _leftover_issue_row(device_id: str) -> dict[str, Any]:
    """Return the stored row of a non-persistent issue of the previous release: it reloads inactive with no data."""
    return {
        "created": "2026-10-21T00:00:00+00:00",
        "dismissed_version": None,
        "domain": DOMAIN,
        "is_persistent": False,
        "issue_id": f"{LOCAL_ISSUE_PREFIX}{device_id}",
    }


async def _seed_issues(hass: HomeAssistant, hass_storage: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    """Load the issue registry from a storage that holds `rows`, as a start of Home Assistant does."""
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "key": ir.STORAGE_KEY,
        "data": {"issues": rows},
    }
    await ir.async_get(hass).async_load()
    for row in rows:
        assert _local_issue(hass, row["issue_id"].removeprefix(LOCAL_ISSUE_PREFIX)) is not None, "premise: seeded"


async def test_start_deletes_a_local_failure_issue_whose_record_is_gone(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-19: after a successful local load, an issue whose trigger has no saved record can never clear, so it goes."""
    _seed_local(hass_storage, [_row_data(OTHER_DEVICE)])
    await _seed_issues(
        hass,
        hass_storage,
        [
            _persistent_issue_row(STALE_DEVICE),
            _persistent_issue_row(OTHER_DEVICE, PAYLOAD_OFF),
            _leftover_issue_row(LEFTOVER_DEVICE),
        ],
    )

    await setup_entry(hass, make_hub_entry())

    assert _local_issue(hass, STALE_DEVICE) is None, "an issue whose device has no record is deleted at start"
    assert _local_issue(hass, OTHER_DEVICE) is None, "an issue whose trigger has no record is deleted at start"
    assert _local_issue(hass, LEFTOVER_DEVICE) is None, "an inactive leftover without identity is deleted at start"


async def test_start_keeps_a_local_failure_issue_whose_record_exists(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-19: an issue whose record exists stays, also for an orphan record; the start writes no record."""
    _seed_local(hass_storage, [_row_data(OTHER_DEVICE)])
    before = copy.deepcopy(hass_storage[LOCAL_STORE_KEY])
    await _seed_issues(hass, hass_storage, [_persistent_issue_row(OTHER_DEVICE)])

    manager = manager_of(await setup_entry(hass, make_hub_entry()))

    assert OTHER_DEVICE not in manager.mirrors, "premise: the record is an orphan, no mirror exists"
    issue = _local_issue(hass, OTHER_DEVICE)
    assert issue is not None, "an issue whose record exists survives the start"
    assert issue.active is True
    assert issue.translation_placeholders == SEEDED_PLACEHOLDERS
    assert hass_storage[LOCAL_STORE_KEY] == before, "the start changes no local record"


async def test_refused_local_load_keeps_every_local_failure_issue(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-11-40, D-05: a refused local load proves nothing about the records, so no local failure issue is deleted."""
    hass_storage[LOCAL_STORE_KEY] = {
        "version": 2,
        "minor_version": 1,
        "key": LOCAL_STORE_KEY,
        "data": {"records": [_row_data(OTHER_DEVICE)]},
    }
    await _seed_issues(hass, hass_storage, [_persistent_issue_row(STALE_DEVICE), _leftover_issue_row(LEFTOVER_DEVICE)])

    manager = manager_of(await setup_entry(hass, make_hub_entry()))

    assert manager.local_action_counts().records == 0, "premise: the newer local Store was refused"
    assert _local_issue(hass, STALE_DEVICE) is not None, "a refused load deletes no local failure issue"
    assert _local_issue(hass, LEFTOVER_DEVICE) is not None, "a refused load deletes no leftover issue either"
