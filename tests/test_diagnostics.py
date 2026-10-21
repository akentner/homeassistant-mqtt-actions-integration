"""The diagnostics download shows structure, never content: an allow-list, short ids and sentinel checks (D-17)."""

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions.const import (
    CONF_BASE_TOPIC,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    DOMAIN,
    HEARTBEAT_OFFLINE_SECONDS,
    ISSUE_LOCAL_ACTION_FAILED_PREFIX,
    LOCAL_ACTIONS_STORE_KEY,
    SUBENTRY_SELECT,
)
from custom_components.mqtt_actions.document import build_content, content_hash
from custom_components.mqtt_actions.topics import config_topic, heartbeat_topic, state_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.helpers import DEVICE_KEYS, HUB_KEYS, LOCAL_ACTIONS_KEYS, ROSTER_KEYS, TOP_KEYS

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
SESSION = "6f1c0f0e-3a52-4f43-8d0c-5a0b7f3c9d21"
PEER_ID = "peer-instance-0123456789abcdef"
SHORT = 8

# Sentinels: none of them may appear anywhere in the serialized diagnostics
S_OWN_ENTITY = "light.sentinel_own_entity"
S_OWN_DATA = "SENTINEL_OWN_SERVICE_DATA"
S_OWN_NAME = "SENTINEL OWN DEVICE NAME"
S_MIRROR_ENTITY = "light.sentinel_mirror_entity"
S_MIRROR_TEMPLATE = "SENTINEL_MIRROR_TEMPLATE"
S_MIRROR_LABEL = "SENTINEL MIRROR LABEL"
S_MIRROR_VALUE = "sentinelmirrorvalue"
S_MIRROR_NAME = "SENTINEL MIRROR DEVICE NAME"
SENTINELS = (
    S_OWN_ENTITY,
    S_OWN_DATA,
    S_OWN_NAME,
    S_MIRROR_ENTITY,
    S_MIRROR_TEMPLATE,
    S_MIRROR_LABEL,
    S_MIRROR_VALUE,
    S_MIRROR_NAME,
)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


async def _deliver(hass: HomeAssistant, device_id: str, payload: str) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _heartbeat(hass: HomeAssistant, instance_id: str, name: str = "Peer") -> None:
    payload = json.dumps(
        {"instance_id": instance_id, "name": name, "version": "0.1.0", "devices": 1, "session": SESSION}
    )
    async_fire_mqtt_message(hass, heartbeat_topic(BASE, instance_id), payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _diagnostics(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, Any]:
    from custom_components.mqtt_actions.diagnostics import async_get_config_entry_diagnostics

    return await async_get_config_entry_diagnostics(hass, entry)


async def _hub_with_owned_device_and_mirror(
    hass: HomeAssistant, make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[MockConfigEntry, str, str]:
    """Return a loaded hub with one owned Switch and one delivered Select mirror, both full of sentinels."""
    sub = make_switch_subentry(
        S_OWN_NAME,
        on=[{"action": "test.on", "target": {"entity_id": S_OWN_ENTITY}, "data": {"message": S_OWN_DATA}}],
    )
    own_id = sub["data"]["device_id"]
    mirror = make_spec(
        SUBENTRY_SELECT,
        name=S_MIRROR_NAME,
        options=[
            (
                S_MIRROR_VALUE,
                S_MIRROR_LABEL,
                [
                    {"action": "test.on", "target": {"entity_id": S_MIRROR_ENTITY}},
                    {"action": "test.say", "data": {"message": "{{ '" + S_MIRROR_TEMPLATE + "' }}"}},
                ],
            ),
            ("other", "Other", []),
        ],
    )
    entry = await _setup(hass, make_hub_entry([sub]))
    await _deliver(hass, mirror.device_id, document_payload(mirror))
    await _heartbeat(hass, PEER_ID)
    return entry, own_id, mirror.device_id


async def test_diagnostics_structure(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The result serializes and names the hub, the roster and one row per owned device and mirror."""
    entry, own_id, mirror_id = await _hub_with_owned_device_and_mirror(hass, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)

    result = await _diagnostics(hass, entry)

    json.dumps(result)
    hub = result["hub"]
    assert hub["base_topic"] == BASE
    assert hub["instance_name"] == "Test instance"
    assert hub["instance_id"] == entry.data[CONF_INSTANCE_ID][:SHORT]
    assert len(hub["instance_id"]) == SHORT
    assert hub["instance_mode"] == manager.instance_mode
    assert hub["instance_id"] in [row["id"] for row in result["roster"]]
    rows = {row["uuid"]: row for row in result["devices"]}
    assert set(rows) == {own_id, mirror_id}
    assert rows[own_id]["kind"] == "switch"
    assert rows[own_id]["origin"] == "owned"
    assert rows[own_id]["owner"] == entry.data[CONF_INSTANCE_ID][:SHORT]
    assert rows[own_id]["approval"] == "owned"
    assert rows[mirror_id]["kind"] == "select"
    assert rows[mirror_id]["origin"] == "mirror"
    assert rows[mirror_id]["owner"] == FOREIGN_OWNER[:SHORT]
    assert rows[mirror_id]["approval"] == "pending"


async def test_sentinel_strings_never_appear_in_the_output(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """No action content, no device name and no full instance id is in the serialized diagnostics (T-04-27, T-04-29)."""
    entry, _own_id, mirror_id = await _hub_with_owned_device_and_mirror(hass, make_hub_entry, make_switch_subentry)
    own_instance = entry.data[CONF_INSTANCE_ID]
    assert await _manager(entry).async_approve(mirror_id, _manager(entry).mirrors[mirror_id].mirror.actions_hash), (
        "an approved mirror must leak nothing either"
    )

    text = json.dumps(await _diagnostics(hass, entry))

    assert len(SENTINELS) >= 5
    for sentinel in SENTINELS:
        assert sentinel not in text
    for full_id in (own_instance, FOREIGN_OWNER, PEER_ID):
        assert full_id not in text
    for short_id in (own_instance[:SHORT], FOREIGN_OWNER[:SHORT], PEER_ID[:SHORT]):
        assert short_id in text


ALTERNATING = ["ON", "OFF", "ON", "OFF", "ON", "OFF"]


async def _state(hass: HomeAssistant, device_id: str, payload: str) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


def _rows(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["uuid"]: row for row in result["devices"]}


def _published_document(mqtt_mock: Any, device_id: str) -> dict[str, Any]:
    """Return the last config document this instance published for a device."""
    topic = config_topic(BASE, device_id)
    payloads = [call.args[1] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]
    assert payloads
    return json.loads(payloads[-1])


async def test_device_rows_cover_modes_breaker_rev_and_hash(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Mode, effective mode, breaker, rev and hash are right for owned devices and for a mirror."""
    async_mock_service(hass, "test", "on")
    async_mock_service(hass, "test", "off")
    observed = make_switch_subentry("Observed", on=[{"action": "test.on"}])
    looping = make_switch_subentry(
        "Looping",
        on=[{"action": "test.on"}],
        off=[{"action": "test.off"}],
        breaker_max_runs=2,
        breaker_window=3600,
    )
    observed_id, looping_id = observed["data"]["device_id"], looping["data"]["device_id"]
    mirror = make_spec(name="Mirror", on=[{"action": "test.on"}])
    entry = await _setup(hass, make_hub_entry([observed, looping]))
    manager = _manager(entry)
    await _deliver(hass, mirror.device_id, document_payload(mirror, rev=3))
    await manager.async_set_device_mode(observed_id, "observe")
    for payload in ALTERNATING:
        await _state(hass, looping_id, payload)

    rows = _rows(await _diagnostics(hass, entry))

    assert (rows[observed_id]["mode"], rows[observed_id]["effective_mode"]) == ("observe", "observe")
    assert (rows[looping_id]["mode"], rows[looping_id]["effective_mode"]) == ("run", "run")
    assert rows[observed_id]["breaker"] == "ok"
    assert rows[looping_id]["breaker"] == "tripped"
    for device_id in (observed_id, looping_id):
        document = _published_document(mqtt_mock, device_id)
        assert rows[device_id]["rev"] == manager.revision(device_id) == document["rev"]
        assert rows[device_id]["hash"] == document["hash"]
        assert rows[device_id]["hash"] == content_hash(build_content(manager.devices[device_id].spec))
    assert rows[mirror.device_id]["rev"] == 3
    assert rows[mirror.device_id]["hash"] == content_hash(build_content(mirror))

    await manager.async_set_instance_mode("disabled")
    rows = _rows(await _diagnostics(hass, entry))

    assert rows[observed_id]["effective_mode"] == "disabled"
    assert rows[observed_id]["mode"] == "observe"
    assert rows[mirror.device_id]["effective_mode"] == "disabled"
    assert rows[mirror.device_id]["mode"] == "run"


async def test_origin_and_owner(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """An owned row names this instance as owner, a mirror row its pinned owner, both shortened."""
    entry, own_id, mirror_id = await _hub_with_owned_device_and_mirror(hass, make_hub_entry, make_switch_subentry)

    rows = _rows(await _diagnostics(hass, entry))

    assert (rows[own_id]["origin"], rows[own_id]["owner"]) == ("owned", entry.data[CONF_INSTANCE_ID][:SHORT])
    assert (rows[mirror_id]["origin"], rows[mirror_id]["owner"]) == ("mirror", FOREIGN_OWNER[:SHORT])


async def test_roster_rows_are_shortened_and_include_offline_peers(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A peer is listed with a shortened id and its details, and stays listed as offline after the expiry."""
    entry = await _setup(hass, make_hub_entry())
    now = [1000.0]
    _manager(entry).clock = lambda: now[0]
    await _heartbeat(hass, PEER_ID, "Peer One")

    rows = {row["id"]: row for row in (await _diagnostics(hass, entry))["roster"]}

    peer = rows[PEER_ID[:SHORT]]
    assert set(peer) == ROSTER_KEYS
    assert (peer["name"], peer["version"], peer["online"]) == ("Peer One", "0.1.0", True)
    assert peer["last_seen"]
    assert entry.data[CONF_INSTANCE_ID][:SHORT] in rows

    now[0] += HEARTBEAT_OFFLINE_SECONDS + 2
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HEARTBEAT_OFFLINE_SECONDS + 5))
    await hass.async_block_till_done(wait_background_tasks=True)
    rows = {row["id"]: row for row in (await _diagnostics(hass, entry))["roster"]}

    assert rows[PEER_ID[:SHORT]]["online"] is False
    assert rows[entry.data[CONF_INSTANCE_ID][:SHORT]]["online"] is True


async def test_redaction_safety_net_removes_leaked_keys(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A key that slips into the intermediate result is redacted, wherever it sits."""
    entry = await _setup(hass, make_hub_entry())
    leaked = {"actions": "LEAK_ACTIONS", "password": "LEAK_PASSWORD", "host": "LEAK_HOST", "port": 1883}

    with patch("custom_components.mqtt_actions.diagnostics._hub", return_value={"base_topic": BASE, **leaked}):
        result = await _diagnostics(hass, entry)

    for key in leaked:
        assert result["hub"][key] == "**REDACTED**"
    text = json.dumps(result)
    for value in ("LEAK_ACTIONS", "LEAK_PASSWORD", "LEAK_HOST"):
        assert value not in text


async def test_unloaded_entry_returns_a_small_answer(hass: HomeAssistant) -> None:
    """An entry without a manager yields a dict that says so and nothing else."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_BASE_TOPIC: BASE, CONF_INSTANCE_NAME: "Idle", CONF_INSTANCE_ID: "idle-instance"}
    )
    entry.add_to_hass(hass)

    result = await _diagnostics(hass, entry)

    assert result == {"loaded": False}


async def test_output_has_exactly_the_documented_keys(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The key sets at the top level, in the hub, in a roster row and in a device row are the documented ones."""
    entry, _own_id, _mirror_id = await _hub_with_owned_device_and_mirror(hass, make_hub_entry, make_switch_subentry)

    result = await _diagnostics(hass, entry)

    assert set(result) == TOP_KEYS
    assert set(result["hub"]) == HUB_KEYS
    assert len(result["roster"]) == 2
    assert all(set(row) == ROSTER_KEYS for row in result["roster"])
    assert len(result["devices"]) == 2
    assert all(set(row) == DEVICE_KEYS for row in result["devices"])
    assert set(result["local_actions"]) == LOCAL_ACTIONS_KEYS


# ------------------------------------------------------------------------------------ local actions (Plan 11-09)

# Sentinels of the local actions of mirrors: none of them may appear in the serialized diagnostics (D-04, D-14)
S_LOCAL_LABEL = "SENTINEL LOCAL LABEL"
S_LOCAL_VALUE = "sentinellocalorphanvalue"
S_LOCAL_ENTITY = "light.sentinel_local_entity"
S_LOCAL_TEMPLATE = "SENTINEL_LOCAL_TEMPLATE"
S_LOCAL_DATA = "SENTINEL_LOCAL_SERVICE_DATA"
S_LOCAL_ERROR = "SENTINEL LOCAL ERROR"
S_LOCAL_TRACE = "SENTINEL_LOCAL_TRACE"
LOCAL_SENTINELS = (
    S_LOCAL_LABEL,
    S_LOCAL_VALUE,
    S_LOCAL_ENTITY,
    S_LOCAL_TEMPLATE,
    S_LOCAL_DATA,
    S_LOCAL_ERROR,
    S_LOCAL_TRACE,
)
# A device known only from its local records; it has no mirror and therefore no device row
ORPHAN_ONLY_ID = "7a1e2b3c-4d5e-4f60-8a9b-0c1d2e3f4a5b"
LOCAL_ACTIONS = [
    {"action": "test.local", "target": {"entity_id": S_LOCAL_ENTITY}, "data": {"message": S_LOCAL_DATA}},
    {"action": "test.say", "data": {"message": "{{ '" + S_LOCAL_TEMPLATE + "' }}"}},
]


def _local_row(device_id: str, kind: str, state_value: str, mode: str = "additive") -> dict[str, Any]:
    return {
        "device_id": device_id,
        "kind": kind,
        "state_value": state_value,
        "label": S_LOCAL_LABEL,
        "mode": mode,
        "actions": LOCAL_ACTIONS,
    }


def _seed_local_records(hass_storage: dict[str, Any], mirror_id: str, own_id: str | None = None) -> None:
    """
    Seed five records: an active one and an orphaned option on the mirror, two on a device without any mirror, and
    one on the owned device (owned devices never carry local actions, so it is inactive).
    """
    rows = [
        _local_row(mirror_id, "select", S_MIRROR_VALUE, "replacement"),
        _local_row(mirror_id, "select", S_LOCAL_VALUE),
        _local_row(ORPHAN_ONLY_ID, "switch", "ON"),
        _local_row(ORPHAN_ONLY_ID, "switch", "OFF", "replacement"),
    ]
    if own_id is not None:
        rows.append(_local_row(own_id, "switch", "ON"))
    hass_storage[LOCAL_ACTIONS_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_ACTIONS_STORE_KEY,
        "data": {"records": rows},
    }


async def _hub_with_local_records(
    hass: HomeAssistant, hass_storage: dict[str, Any], make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[MockConfigEntry, str, str, Any]:
    """Return a loaded hub with an owned Switch, a Select mirror and local records on both plus an orphan-only id."""
    sub = make_switch_subentry(S_OWN_NAME, on=[{"action": "test.on"}])
    own_id = sub["data"]["device_id"]
    mirror = make_spec(
        SUBENTRY_SELECT,
        name=S_MIRROR_NAME,
        options=[(S_MIRROR_VALUE, S_MIRROR_LABEL, [{"action": "test.on"}]), ("other", "Other", [])],
    )
    _seed_local_records(hass_storage, mirror.device_id, own_id)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _deliver(hass, mirror.device_id, document_payload(mirror))
    assert mirror.device_id in _manager(entry).mirrors
    return entry, own_id, mirror.device_id, mirror


async def test_local_actions_appear_as_counts_only(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-04: aggregate and per-device integers; the orphan-only device counts without getting a device row."""
    entry, own_id, mirror_id, _mirror = await _hub_with_local_records(
        hass, hass_storage, make_hub_entry, make_switch_subentry
    )

    result = await _diagnostics(hass, entry)

    assert "local_actions" in result, "the diagnostics carry no local actions summary"
    assert result["local_actions"] == {
        "devices": 3,
        "triggers": 5,
        "orphaned_triggers": 4,
        "orphan_only_devices": 2,
    }
    rows = _rows(result)
    assert set(rows) == {own_id, mirror_id}, "a device known only from local records has no device row"
    assert (rows[mirror_id]["local_action_triggers"], rows[mirror_id]["local_action_orphans"]) == (2, 1)
    assert (rows[own_id]["local_action_triggers"], rows[own_id]["local_action_orphans"]) == (1, 1)
    values = [*result["local_actions"].values()]
    values += [row[key] for row in rows.values() for key in ("local_action_triggers", "local_action_orphans")]
    assert all(type(value) is int and value >= 0 for value in values)


async def test_local_counts_are_zero_without_records(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    entry, _own_id, _mirror_id = await _hub_with_owned_device_and_mirror(hass, make_hub_entry, make_switch_subentry)

    result = await _diagnostics(hass, entry)

    assert result["local_actions"] == dict.fromkeys(LOCAL_ACTIONS_KEYS, 0)
    assert all((row["local_action_triggers"], row["local_action_orphans"]) == (0, 0) for row in result["devices"])


async def test_orphan_only_devices_count_without_any_mirror(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """An instance with no mirror and no device at all still counts the devices its local records name."""
    _seed_local_records(hass_storage, "8b2f3c4d-5e6f-4a70-9b8c-1d2e3f4a5b6c")
    entry = await _setup(hass, make_hub_entry())

    result = await _diagnostics(hass, entry)

    assert result["devices"] == []
    assert result["local_actions"] == {
        "devices": 2,
        "triggers": 4,
        "orphaned_triggers": 4,
        "orphan_only_devices": 2,
    }


async def test_local_sentinels_never_appear_and_the_shared_hash_is_unchanged(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-04, D-14: no record, label, StateValue, action, Template, error or trace; the content hash stays shared."""
    entry, _own_id, mirror_id, mirror = await _hub_with_local_records(
        hass, hass_storage, make_hub_entry, make_switch_subentry
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_LOCAL_ACTION_FAILED_PREFIX}{mirror_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="local_action_failed",
        translation_placeholders={"device": "d", "trigger": S_LOCAL_LABEL, "time": "now", "error": S_LOCAL_ERROR},
        data={"trace": S_LOCAL_TRACE},
    )

    result = await _diagnostics(hass, entry)
    text = json.dumps(result)

    for sentinel in (*LOCAL_SENTINELS, *SENTINELS):
        assert sentinel not in text
    assert ORPHAN_ONLY_ID not in text, "an orphan-only device is counted, never named"
    assert _rows(result)[mirror_id]["hash"] == content_hash(build_content(mirror))
