"""
The separate local-actions Store (D-05, D-07, D-10 to D-12, D-22, T-11-09 to T-11-11).

Every test runs against the in-memory `hass_storage` of the test harness and asserts it at once, without advancing time:
the Store writes immediately, never through a delayed save. Restarts are a second `LocalActionsStore` on the same key.
"""

import copy
import dataclasses
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, UnsupportedStorageVersionError
from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError

from custom_components.mqtt_actions.const import (
    LOCAL_ACTIONS_STORE_KEY,
    LOCAL_ACTIONS_STORE_VERSION,
    STORE_APPROVALS,
    STORE_DEVICE_MODES,
    STORE_INSTANCE_MODE,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_MIRRORS,
    STORE_PUBLISHED,
    STORE_REVS,
    STORE_TRANSFERS,
    STORE_TRIPPED,
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
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore, LocalActionsStoreError
from tests.fake_broker import Instance, instance_store_keys
from tests.helpers import manager_of, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

DEVICE = "aaaaaaaaaaaaaaaaaaaaaa"
OTHER_DEVICE = "bbbbbbbbbbbbbbbbbbbbbb"
# A marker that must never reach a log line: rows are dropped and logged by count only
MARKER = "local-secret-marker"
# The name Home Assistant gives a file it could not parse: "<path>.corrupt.<isotime>" (helpers/storage.py)
CORRUPT_TIME = "2026-10-21T00:00:00.000000+00:00"


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Give every test of this module a temporary configuration directory, so no corrupt copy ever leaves the test."""
    return hass_tmp_config_dir


def _corrupt_copy(hass: Any, key: str = LOCAL_ACTIONS_STORE_KEY, time: str = CORRUPT_TIME) -> Path:
    """Create the copy Home Assistant leaves after a JSON decode error of a Store file; return its path."""
    storage = Path(hass.config.path(".storage"))
    storage.mkdir(parents=True, exist_ok=True)
    copy_path = storage / f"{key}.corrupt.{time}"
    copy_path.write_text("{not json", encoding="utf-8")
    return copy_path


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
    [[], "text", {}, {"records": "text"}, {"records": {"0": _row(label=MARKER)}}],
    ids=["list", "text", "no-records", "records-text", "records-mapping"],
)
async def test_malformed_payload_shape_refuses_the_load_and_every_save(
    hass: Any, hass_storage: dict[str, Any], caplog: pytest.LogCaptureFixture, data: Any
) -> None:
    """WR-03, D-07, T-11-09: a payload without a record list is unreadable; it is never loaded as empty or rewritten."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_ACTIONS_STORE_KEY,
        "data": data,
    }
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)
    store = LocalActionsStore(hass)

    with caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"):
        with pytest.raises(HomeAssistantError) as caught:
            await store.async_load_records()
        # Matched by name, so this module still collects before the error class exists
        assert type(caught.value).__name__ == "LocalActionsStoreUnreadableError"
        with pytest.raises(HomeAssistantError):
            await store.async_save_records([_record()])

    assert store.records == ()
    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "the unreadable payload is untouched"
    assert MARKER not in str(caught.value), "the error names the reason, never stored content"
    own = [record.getMessage() for record in caplog.records if record.name.startswith("custom_components.mqtt_actions")]
    assert not [line for line in own if MARKER in line], "no stored content reaches a log line of the integration"


async def test_null_payload_loads_no_records_like_a_missing_file(hass: Any, hass_storage: dict[str, Any]) -> None:
    """An envelope whose data is null holds no records, like a missing file; it stays writable."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_ACTIONS_STORE_KEY,
        "data": None,
    }
    store = LocalActionsStore(hass)

    assert await store.async_load_records() == ()
    await store.async_save_records([_record()])

    assert hass_storage[LOCAL_ACTIONS_STORE_KEY] == _envelope([_row()]), "a later save writes a v1 payload"


async def test_corrupt_copy_beside_a_missing_file_refuses_the_load_and_every_save(
    hass: Any, hass_storage: dict[str, Any]
) -> None:
    """WR-03, D-07, T-11-51: Home Assistant moved an unparsable file aside; the Store is unreadable, not empty."""
    corrupt = _corrupt_copy(hass)
    before = corrupt.read_bytes()
    store = LocalActionsStore(hass)

    with pytest.raises(HomeAssistantError) as caught:
        await store.async_load_records()
    # Matched by name, so this module still collects before the error class exists
    assert type(caught.value).__name__ == "LocalActionsStoreUnreadableError"
    assert "{not json" not in str(caught.value), "the error names the reason, never the copy's content"
    with pytest.raises(LocalActionsStoreError):
        await store.async_save_records([_record()])

    assert corrupt.read_bytes() == before, "the copy is never changed"
    assert LOCAL_ACTIONS_STORE_KEY not in hass_storage, "no empty Store is written beside the copy"
    assert store.records == ()

    corrupt.unlink()
    fresh = LocalActionsStore(hass)
    assert await fresh.async_load_records() == (), "without the copy a missing file is an empty Store again"
    await fresh.async_save_records([_record()])
    assert hass_storage[LOCAL_ACTIONS_STORE_KEY] == _envelope([_row()])


async def test_corrupt_copy_of_another_key_never_counts(hass: Any, hass_storage: dict[str, Any]) -> None:
    """WR-03: only a copy of this Store's own key makes it unreadable, never one of another or a longer key."""
    del hass_storage
    _corrupt_copy(hass, STORE_KEY)
    _corrupt_copy(hass, f"{LOCAL_ACTIONS_STORE_KEY}_other")

    assert await _restarted(hass) == ()


async def test_remove_records_deletes_the_corrupt_copies_of_its_own_key_only(
    hass: Any, hass_storage: dict[str, Any]
) -> None:
    """D-08, G-03, T-11-52: removal deletes the copies of its own key, keeps every other copy and fails closed."""
    del hass_storage
    own = [_corrupt_copy(hass), _corrupt_copy(hass, time="2026-10-21T01:00:00.000000+00:00")]
    other = _corrupt_copy(hass, STORE_KEY)

    await LocalActionsStore(hass).async_remove_records()

    assert [path.exists() for path in own] == [False, False], "both copies of the local key are deleted"
    assert other.exists(), "a copy of another key is never touched"
    assert await _restarted(hass) == (), "after the removal the local Store is readable and empty"

    _corrupt_copy(hass)
    with patch("pathlib.Path.unlink", side_effect=PermissionError), pytest.raises(LocalActionsStoreError):
        await LocalActionsStore(hass).async_remove_records()


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


async def test_newer_minor_version_load_never_writes_the_store(hass: Any, hass_storage: dict[str, Any]) -> None:
    """WR-05, D-22: a load reads a minor 2 file without any write call, so its bytes and its stamp stay."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([_row(), _row(state_value="OFF", label="Off")], minor_version=2)
    hass_storage[LOCAL_ACTIONS_STORE_KEY]["data"]["groups"] = [{"future": True}]
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)

    with patch("homeassistant.helpers.storage.Store._async_write_data", new_callable=AsyncMock) as write:
        loaded = await _restarted(hass)

    assert len(loaded) == 2
    write.assert_not_awaited()
    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "the stored minor 2 file keeps its exact bytes"


async def test_shape_invalid_newer_minor_store_is_unreadable_and_never_written(
    hass: Any, hass_storage: dict[str, Any]
) -> None:
    """WR-05, T-11-60: a minor 2 payload without a record list is reported unreadable and never rewritten."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "key": LOCAL_ACTIONS_STORE_KEY,
        "data": {"records": "text", "v2": {"future": True}},
    }
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)
    store = LocalActionsStore(hass)

    with pytest.raises(HomeAssistantError) as caught:
        await store.async_load_records()
    # Matched by name, so this module still collects before the error class exists
    assert type(caught.value).__name__ == "LocalActionsStoreUnreadableError"
    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "the load did not rewrite the payload"

    with pytest.raises(LocalActionsStoreError):
        await store.async_save_records([_record()])

    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "the refused save did not write either"


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


# --- Task 2: isolation from the main Store and other instances, failed saves, removal (D-05, D-07, T-11-10/11) ---

# The explicit key set of the v1.0.1 main serializer: an older release writes exactly these keys and nothing else
V101_MAIN_KEYS = (
    STORE_LAST_ACTED,
    STORE_MIRRORS,
    STORE_APPROVALS,
    STORE_PUBLISHED,
    STORE_TRIPPED,
    STORE_REVS,
    STORE_TRANSFERS,
    STORE_INSTANCE_MODE,
    STORE_DEVICE_MODES,
)


async def test_old_main_store_save_leaves_the_local_store_byte_identical(
    hass: Any, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-07: neither today's main save nor a simulated v1.0.1 serializer reads or rewrites the local Store."""
    del mqtt_mock
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([_row(), _row(device_id=OTHER_DEVICE, label="Orphan")])
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)
    entry = await setup_entry(hass, make_hub_entry())

    await manager_of(entry).async_save_now()
    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "today's main save leaves the local bytes"
    stored_main = hass_storage[STORE_KEY]["data"]
    await Store(hass, STORE_VERSION, STORE_KEY).async_save({key: stored_main[key] for key in V101_MAIN_KEYS})

    assert set(hass_storage[STORE_KEY]["data"]) == set(V101_MAIN_KEYS), "premise: the old serializer drops extra keys"
    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before, "a v1.0.1 main save leaves the local bytes"
    assert len(await _restarted(hass)) == 2, "the overlays are still there for the next upgrade"


@pytest.mark.parametrize(
    "error",
    [WriteError("disk full"), OSError("disk gone")],
    ids=["write-error-the-base-store-only-logs", "error-the-base-store-raises"],
)
async def test_failed_save_keeps_the_previous_durable_and_in_memory_snapshot(
    hass: Any, hass_storage: dict[str, Any], error: Exception
) -> None:
    """T-11-10, D-22: a failed write raises, the stored bytes and the returned records stay the previous ones."""
    previous = _record(label="previous")
    store = LocalActionsStore(hass)
    await store.async_load_records()
    await store.async_save_records([previous])
    stored_before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)

    with (
        patch("homeassistant.helpers.storage.Store._async_write_data", new=AsyncMock(side_effect=error)),
        pytest.raises(LocalActionsStoreError),
    ):
        await store.async_save_records([_record(label="next", state_value="OFF")])

    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == stored_before, "the durable snapshot is the previous one"
    assert store.records == (previous,), "the in-memory snapshot is the previous one"
    assert await _restarted(hass) == (previous,)
    assert await store.async_save_records([]) == (), "the Store saves again once writing works"


async def test_save_before_load_and_duplicate_identities_write_nothing(hass: Any, hass_storage: dict[str, Any]) -> None:
    """A save never overwrites a Store it has not read, and one identity never gets two records."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([_row()])
    before = _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY)
    store = LocalActionsStore(hass)

    with pytest.raises(LocalActionsStoreError):
        await store.async_save_records([])
    await store.async_load_records()
    with pytest.raises(LocalActionsStoreError):
        await store.async_save_records([_record(state_value="ON"), _record(state_value=" on ", label="twin")])

    assert _bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY) == before


async def test_remove_deletes_only_the_selected_local_key(hass: Any, hass_storage: dict[str, Any]) -> None:
    """D-05: removing one instance's local Store leaves the other local key and the main Store alone."""
    key_a, key_b = instance_store_keys("a")[1], instance_store_keys("b")[1]
    for key in (key_a, key_b):
        store = LocalActionsStore(hass, key)
        await store.async_load_records()
        await store.async_save_records([_record()])
    await Store(hass, STORE_VERSION, STORE_KEY).async_save({STORE_APPROVALS: {}})
    others = {key: _bytes(hass_storage, key) for key in (key_b, STORE_KEY)}
    store_a = LocalActionsStore(hass, key_a)
    await store_a.async_load_records()

    await store_a.async_remove_records()

    assert key_a not in hass_storage, "the selected local Store is gone at once"
    assert {key: _bytes(hass_storage, key) for key in (key_b, STORE_KEY)} == others
    assert store_a.records == ()
    assert await _restarted(hass, key_a) == ()


def test_instance_store_keys_are_distinct_per_instance_and_from_production() -> None:
    """T-11-11: every test instance gets its own main and local key; none is the production local key."""
    names = ("owner", "follower", "third")
    keys = [key for name in names for key in instance_store_keys(name)]

    assert len(set(keys)) == len(keys), "no two instances, and no main and local key, share a Store"
    assert LOCAL_ACTIONS_STORE_KEY not in keys
    assert all(key.endswith(f".{name}") for name in names for key in instance_store_keys(name))
    defaults = {item.name: item.default for item in dataclasses.fields(Instance)}
    assert defaults["local_store_key"] == LOCAL_ACTIONS_STORE_KEY, "a bare Instance defaults to the production key"


async def test_instance_local_stores_see_only_their_own_records(hass: Any, hass_storage: dict[str, Any]) -> None:
    """T-11-11: two instances on one shared storage mock never read each other's overlays."""
    del hass_storage
    owner_key, follower_key = instance_store_keys("owner")[1], instance_store_keys("follower")[1]
    owner_record, follower_record = _record(label="owner"), _record(device_id=OTHER_DEVICE, label="follower")
    for key, record in ((owner_key, owner_record), (follower_key, follower_record)):
        store = LocalActionsStore(hass, key)
        await store.async_load_records()
        await store.async_save_records([record])

    assert await _restarted(hass, owner_key) == (owner_record,)
    assert await _restarted(hass, follower_key) == (follower_record,)


# --- Plan 11-21 Task 1: rows and keys this release cannot parse are kept (WR-03, D-07 extended, MIR-06) ---------------

# Rows this release cannot parse, for example of a mode a newer minor release adds
UNPARSEABLE = [_row(state_value="OFF", mode="conditional"), "not a row", {"device_id": DEVICE, "future": [1, {"a": 2}]}]
EXTRA = {"groups": [{"future": True, "nested": {"level": [1]}}], "schema": "next"}


def _seed_with_extras(hass_storage: dict[str, Any], rows: list[Any], extra: dict[str, Any]) -> None:
    """Write rows plus unknown top-level keys as a v1 envelope."""
    envelope = _envelope(rows)
    envelope["data"].update(copy.deepcopy(extra))
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = envelope


async def test_preserved_rows_and_unknown_keys_are_written_back_after_the_records(
    hass: Any, hass_storage: dict[str, Any]
) -> None:
    """WR-03, T-11-54: every save writes the kept rows verbatim after the parsed records, and keeps unknown keys."""
    first, second = _row(), _row(state_value="cozy", kind=SUBENTRY_SELECT, label="Cozy")
    seeded = [UNPARSEABLE[0], first, UNPARSEABLE[1], second, UNPARSEABLE[2]]
    _seed_with_extras(hass_storage, copy.deepcopy(seeded), EXTRA)
    store = LocalActionsStore(hass)
    loaded = await store.async_load_records()
    assert [local_record_data(record) for record in loaded] == [first, second], "only parsed rows are records"

    written: list[str] = []
    for _ in range(2):
        await store.async_save_records(store.records)
        data = hass_storage[LOCAL_ACTIONS_STORE_KEY]["data"]
        assert data == {**EXTRA, "records": [first, second, *UNPARSEABLE]}
        assert json.dumps(data["records"][2:], sort_keys=True) == json.dumps(UNPARSEABLE, sort_keys=True)
        written.append(_bytes(hass_storage, LOCAL_ACTIONS_STORE_KEY))
    assert written[0] == written[1], "a second save writes the same bytes"
    assert await _restarted(hass) == loaded, "the kept rows never become records after a restart"


async def test_duplicate_identity_rows_are_not_preserved(hass: Any, hass_storage: dict[str, Any]) -> None:
    """D-10: a later duplicate of a parsed identity is dropped, so removing the record never brings it back."""
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([_row(label="first"), _row(state_value=" on ", label="second")])
    store = LocalActionsStore(hass)
    await store.async_load_records()

    await store.async_save_records([])

    assert hass_storage[LOCAL_ACTIONS_STORE_KEY]["data"] == {"records": []}


async def test_remove_records_forgets_preserved_rows_and_keys(hass: Any, hass_storage: dict[str, Any]) -> None:
    """D-08: removing the Store is the user's explicit choice; the kept rows and keys go with it."""
    _seed_with_extras(hass_storage, [_row(), *copy.deepcopy(UNPARSEABLE)], EXTRA)
    store = LocalActionsStore(hass)
    await store.async_load_records()

    await store.async_remove_records()
    await store.async_save_records([_record()])

    assert hass_storage[LOCAL_ACTIONS_STORE_KEY]["data"] == {"records": [_row()]}
    assert store.preserved_device_ids == frozenset()


async def test_preserved_device_ids_name_only_mapping_rows_with_a_device_id(
    hass: Any, hass_storage: dict[str, Any]
) -> None:
    """Plan 11-22 reads the device ids of kept rows; only a non-blank string device id counts."""
    rows = ["text", {"device_id": 7}, {"device_id": "  "}, {"device_id": "abc", "mode": "x"}, {"mode": "x"}]
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = _envelope([_row(device_id=OTHER_DEVICE), *rows])
    store = LocalActionsStore(hass)
    await store.async_load_records()

    assert store.preserved_device_ids == frozenset({"abc"}), "a parsed record is not a kept row"


def test_payload_functions_keep_preserved_rows_and_extra_keys_as_copies() -> None:
    """T-11-54: the pure functions copy kept rows and keys in and out; an extra key never overrides the records."""
    data = {"records": [_row(), *copy.deepcopy(UNPARSEABLE)], **copy.deepcopy(EXTRA)}

    parsed = parse_local_actions_payload(data)
    data["records"][1]["mode"] = "changed"
    data["records"][3]["future"].append("changed")
    data["groups"][0]["nested"]["level"].append("changed")

    assert parsed.records == (_record(),)
    assert parsed.preserved == tuple(UNPARSEABLE), "the kept rows are copies, in stored order"
    assert parsed.extra == EXTRA, "the unknown keys are copies"
    assert parsed.dropped == len(UNPARSEABLE)

    preserved, extra = copy.deepcopy(parsed.preserved), copy.deepcopy(parsed.extra)
    payload = local_actions_payload(parsed.records, preserved=preserved, extra=extra)
    preserved[0]["mode"] = "changed"
    extra["groups"][0]["nested"]["level"].append("changed")

    assert payload == {**EXTRA, "records": [_row(), *UNPARSEABLE]}
    assert list(payload) == [*EXTRA, "records"], "the unknown keys come first, then the records"

    payload = local_actions_payload([_record()], preserved=(), extra={"records": ["override"], "other": 1})
    assert payload == {"other": 1, "records": [_row()]}, "an extra key named records never overrides the records"
