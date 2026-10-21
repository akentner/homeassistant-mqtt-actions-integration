"""
The separate local-actions Store (D-05, D-07, D-10 to D-12, D-22, T-11-09 to T-11-11).

Every test runs against the in-memory `hass_storage` of the test harness and asserts it at once, without advancing time:
the Store writes immediately, never through a delayed save. Restarts are a second `LocalActionsStore` on the same key.
"""

import copy
import json
import logging
from typing import Any

import pytest
from homeassistant.exceptions import UnsupportedStorageVersionError
from homeassistant.helpers.storage import Store

from custom_components.mqtt_actions.const import (
    LOCAL_ACTIONS_STORE_KEY,
    LOCAL_ACTIONS_STORE_VERSION,
    STORE_KEY,
    STORE_VERSION,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.local_actions import (
    LocalActionMode,
    LocalActionRecord,
    LocalActionsStoreVersionError,
    local_actions_payload,
    local_record_data,
    make_local_record,
    migrate_local_actions_payload,
    parse_local_actions_payload,
)
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore

DEVICE = "aaaaaaaaaaaaaaaaaaaaaa"
OTHER_DEVICE = "bbbbbbbbbbbbbbbbbbbbbb"
# A marker that must never reach a log line: rows are dropped and logged by count only
MARKER = "local-secret-marker"


def _row(**overrides: Any) -> dict[str, Any]:
    """Return one valid stored v1 row, with fields overridden."""
    row = {
        "device_id": DEVICE,
        "kind": SUBENTRY_SWITCH,
        "state_value": "ON",
        "label": "On",
        "mode": "additive",
        "actions": [{"action": "test.local_on", "data": {"source": "local", "nested": {"level": [1, 2]}}}],
    }
    row.update(overrides)
    return row


def _envelope(rows: Any, *, version: int = 1, minor_version: int = 1, key: str = LOCAL_ACTIONS_STORE_KEY) -> dict:
    """Return an HA Store envelope as the Store writes it."""
    return {"version": version, "minor_version": minor_version, "key": key, "data": {"records": rows}}


def _record(**overrides: Any) -> LocalActionRecord:
    """Return the record of one row."""
    row = _row(**overrides)
    return make_local_record(
        row["device_id"], row["kind"], row["state_value"], label=row["label"], mode=row["mode"], actions=row["actions"]
    )


def _bytes(hass_storage: dict[str, Any], key: str) -> str:
    """Return the canonical JSON of one stored key, to compare stored bytes."""
    return json.dumps(hass_storage[key], sort_keys=True)


async def _restarted(hass: Any, key: str = LOCAL_ACTIONS_STORE_KEY) -> tuple[LocalActionRecord, ...]:
    """Load the records through a fresh Store, as after a restart of Home Assistant."""
    return await LocalActionsStore(hass, key).async_load_records()


async def test_round_trip_one_additive_record_through_a_separate_store(hass: Any, hass_storage: dict[str, Any]) -> None:
    """D-07, D-22: one saved overlay is written at once under its own key and survives a restart unchanged."""
    record = _record()
    store = LocalActionsStore(hass)
    await store.async_load_records()

    saved = await store.async_save_records([record])

    assert saved == (record,), "the save returns the saved snapshot"
    assert hass_storage.get(LOCAL_ACTIONS_STORE_KEY) == _envelope([_row()]), "the save is immediate and v1-shaped"
    assert await _restarted(hass) == (record,), "the overlay survives a restart"


async def test_round_trip_keeps_original_and_canonical_state_value_label_and_mode(
    hass: Any, hass_storage: dict[str, Any]
) -> None:
    """D-10, D-11: the shown StateValue, the canonical identity, the last label and the mode all round-trip."""
    record = _record(kind=SUBENTRY_SELECT, state_value=" Cozy ", label="Gemütlich", mode="replacement", actions=[])
    store = LocalActionsStore(hass)
    await store.async_load_records()
    await store.async_save_records([record])

    (loaded,) = await _restarted(hass)

    assert loaded.state_value == " Cozy ", "the StateValue as the user saw it is kept"
    assert loaded.identity.state_value == "cozy", "the identity uses the canonical StateValue"
    assert (loaded.identity.device_id, loaded.identity.kind) == (DEVICE, SUBENTRY_SELECT)
    assert loaded.label == "Gemütlich"
    assert loaded.mode is LocalActionMode.REPLACEMENT
    assert loaded.actions == [], "an empty replacement (a mute) round-trips as an empty list"
    assert hass_storage[LOCAL_ACTIONS_STORE_KEY]["data"]["records"][0]["state_value"] == " Cozy "


async def test_round_trip_store_key_and_version_are_its_own(hass: Any) -> None:
    """D-07: the local Store is a different file from the main Store, with an independently declared version."""
    store = LocalActionsStore(hass)

    assert LOCAL_ACTIONS_STORE_KEY == "mqtt_actions.local_actions"
    assert LOCAL_ACTIONS_STORE_KEY != STORE_KEY
    assert (store.key, store.version) == (LOCAL_ACTIONS_STORE_KEY, LOCAL_ACTIONS_STORE_VERSION)
    assert LOCAL_ACTIONS_STORE_VERSION == 1


async def test_round_trip_missing_or_empty_store_loads_no_records(hass: Any, hass_storage: dict[str, Any]) -> None:
    """A missing file and an empty record list both mean no overlays; loading writes nothing."""
    assert await _restarted(hass) == ()
    assert LOCAL_ACTIONS_STORE_KEY not in hass_storage, "loading a missing Store creates no file"

    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([])
    assert await _restarted(hass) == ()


async def test_round_trip_keeps_orphan_and_kind_mismatched_records_without_rewriting(
    hass: Any, hass_storage: dict[str, Any]
) -> None:
    """D-05, D-12, D-22: the Store knows no mirrors; every valid row is kept and loading never garbage-collects."""
    rows = [
        _row(),
        _row(device_id=OTHER_DEVICE, label="Removed option", state_value="gone"),
        _row(kind=SUBENTRY_SELECT, state_value="ON", label="Kind mismatch"),
    ]
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope(rows)
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)

    loaded = await _restarted(hass)

    assert [local_record_data(record) for record in loaded] == rows, "all valid rows load, in stored order"
    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "no startup cleanup rewrites the Store"


async def test_malformed_rows_are_dropped_independently_and_logged_by_count(
    hass: Any, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """T-11-09: one bad row never removes a valid one; the log names the count, never the stored data."""
    first, last = _row(), _row(state_value="OFF", label="Off")
    rows = [
        first,
        f"not a row {MARKER}",
        {key: value for key, value in _row(label=MARKER).items() if key != "mode"},
        _row(kind="light", label=MARKER),
        _row(mode=MARKER),
        _row(actions=f"{MARKER} is not a list"),
        _row(actions=[MARKER]),
        _row(device_id="  ", label=MARKER),
        _row(state_value=7, label=MARKER),
        _row(label=[MARKER]),
        last,
    ]
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope(rows)

    with caplog.at_level(logging.WARNING):
        loaded = await _restarted(hass)

    assert [local_record_data(record) for record in loaded] == [first, last]
    assert "9" in caplog.text, "the number of dropped rows is logged"
    assert MARKER not in caplog.text, "no stored content reaches the log"


async def test_malformed_duplicate_identity_keeps_the_first_row(hass: Any, hass_storage: dict[str, Any]) -> None:
    """D-10: one identity has one record; a second row of the same identity is dropped, the first one wins."""
    first = _row(state_value="ON", label="first")
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([first, _row(state_value=" on ", label="second")])

    loaded = await _restarted(hass)

    assert [record.label for record in loaded] == ["first"]


@pytest.mark.parametrize(
    "data",
    [[], "text", None, {}, {"records": "text"}, {"records": {"0": _row()}}],
    ids=["list", "text", "none", "no-records", "records-text", "records-mapping"],
)
async def test_malformed_payload_shape_loads_no_records(hass: Any, hass_storage: dict[str, Any], data: Any) -> None:
    """T-11-09: a payload that is not a mapping with a record list means no overlays, and it is not rewritten."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_ACTIONS_STORE_KEY,
        "data": data,
    }
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)

    assert await _restarted(hass) == ()
    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before


async def test_newer_major_version_refuses_and_keeps_the_stored_bytes(hass: Any, hass_storage: dict[str, Any]) -> None:
    """T-11-09, D-07: a payload of a newer release fails the load and is never overwritten, not even by a save."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([_row(), {"future": MARKER}], version=2)
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)
    store = LocalActionsStore(hass)

    with pytest.raises(UnsupportedStorageVersionError):
        await store.async_load_records()
    with pytest.raises(Exception, match="local actions"):
        await store.async_save_records([_record()])

    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "the newer payload is untouched"
    assert store.records == ()


def test_migrate_newer_major_version_raises_in_the_pure_migrator() -> None:
    """The pure migrator refuses any version it does not know, newer or older, instead of resetting the data."""
    for version in (LOCAL_ACTIONS_STORE_VERSION + 1, 0):
        with pytest.raises(LocalActionsStoreVersionError):
            migrate_local_actions_payload(version, 1, {"records": [_row()]})


def test_migrate_same_major_returns_a_copy_of_the_rows() -> None:
    """A minor-only difference keeps the rows; the result never aliases the stored payload."""
    stored = {"records": [_row()]}

    migrated = migrate_local_actions_payload(LOCAL_ACTIONS_STORE_VERSION, 2, stored)
    migrated["records"][0]["actions"][0]["data"]["source"] = "changed"

    assert stored == {"records": [_row()]}
    assert parse_local_actions_payload(migrated).records[0].identity.device_id == DEVICE


async def test_migrate_newer_minor_version_loads_the_rows(hass: Any, hass_storage: dict[str, Any]) -> None:
    """A newer minor version of the same major is readable; the Store's migration hook keeps every valid row."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([_row()], minor_version=2)

    assert [local_record_data(record) for record in await _restarted(hass)] == [_row()]


def test_round_trip_pure_payload_functions() -> None:
    """The HA-free serializer and parser are inverse on valid records."""
    records = (_record(), _record(kind=SUBENTRY_SELECT, state_value="cozy", mode="replacement", actions=[]))

    payload = local_actions_payload(records)
    parsed = parse_local_actions_payload(payload)

    assert payload == {"records": [local_record_data(record) for record in records]}
    assert (parsed.records, parsed.dropped) == (records, 0)


async def test_round_trip_callers_cannot_mutate_the_store_snapshot(hass: Any, hass_storage: dict[str, Any]) -> None:
    """T-11-09: loaded, saved and returned records never share nested action data with the Store or each other."""
    actions = [{"action": "test.local_on", "data": {"nested": {"level": [1]}}}]
    record = _record(actions=actions)
    store = LocalActionsStore(hass)
    await store.async_load_records()

    saved = await store.async_save_records([record])
    stored_before = copy.deepcopy(hass_storage[LOCAL_ACTIONS_STORE_KEY])
    saved[0].actions[0]["data"]["nested"]["level"].append("from the returned snapshot")
    record.actions[0]["data"]["nested"]["level"].append("from the saved input")
    store.records[0].actions[0]["data"]["nested"]["level"].append("from the records property")

    assert store.records[0].actions == [{"action": "test.local_on", "data": {"nested": {"level": [1]}}}]
    assert hass_storage[LOCAL_ACTIONS_STORE_KEY] == stored_before

    loaded = await _restarted(hass)
    hass_storage[LOCAL_ACTIONS_STORE_KEY]["data"]["records"][0]["actions"][0]["data"]["nested"]["level"].append("disk")
    assert loaded[0].actions == [{"action": "test.local_on", "data": {"nested": {"level": [1]}}}]


async def test_round_trip_main_store_key_is_never_touched(hass: Any, hass_storage: dict[str, Any]) -> None:
    """D-07: saving overlays writes only the local key."""
    main = Store(hass, STORE_VERSION, STORE_KEY)
    await main.async_save({"approvals": {}})
    main_before = _bytes(hass_storage, STORE_KEY)
    store = LocalActionsStore(hass)
    await store.async_load_records()

    await store.async_save_records([_record()])

    assert _bytes(hass_storage, STORE_KEY) == main_before
