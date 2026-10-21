"""
Local actions of mirrors through the owner lifecycle: evolution, orphan and reattach, prune, tombstone, adoption.

D-05: local records survive owner content, name and revision changes, restarts and owner re-pins; a removed Select
option leaves its record inactive and the exact StateValue return reattaches it (D-10 to D-12).
"""

import copy
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import (
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    PAYLOAD_OFF,
    PAYLOAD_ON,
    PRUNE_GRACE_SECONDS,
    STORE_MIRRORS,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.local_actions import LocalActionMode, local_trigger_identity
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore
from custom_components.mqtt_actions.model import trigger_key
from custom_components.mqtt_actions.topics import state_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.helpers import BASE, announce_presence, deliver_config, manager_of, restart_entry, seed_store, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
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
