"""Heartbeat parsing and the heartbeat of one instance on the MQTT mock (OPS-03, D-05)."""

import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_fire_time_changed

from custom_components.mqtt_actions import const
from custom_components.mqtt_actions.const import (
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_OFFLINE_SECONDS,
    MAX_BROKER_MESSAGE_BYTES,
    MAX_HEARTBEAT_DEVICES,
)
from custom_components.mqtt_actions.presence import Heartbeat, Roster, parse_heartbeat
from custom_components.mqtt_actions.topics import availability_topic, heartbeat_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

BASE = "mqtt_actions"
SESSION = "6f1c0f0e-3a52-4f43-8d0c-5a0b7f3c9d21"
MANIFEST = Path(__file__).parent.parent / "custom_components" / "mqtt_actions" / "manifest.json"


def _message(**overrides: Any) -> str:
    """Return a valid heartbeat payload for instance `inst-a`, with the given keys replaced."""
    data: dict[str, Any] = {
        "instance_id": "inst-a",
        "name": "Alpha",
        "version": "0.1.0",
        "devices": 2,
        "session": SESSION,
    }
    data.update(overrides)
    return json.dumps(data)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def test_parse_heartbeat_accepts_a_valid_message() -> None:
    heartbeat = parse_heartbeat(BASE, heartbeat_topic(BASE, "inst-a"), _message())

    assert heartbeat == Heartbeat(instance_id="inst-a", name="Alpha", version="0.1.0", devices=2, session=SESSION)


async def test_heartbeat_is_published_non_retained_with_qos_0(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-05: one heartbeat after the online availability, QoS 0, not retained, five keys and the capability key."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    entry = await _setup(hass, make_hub_entry([sub]))
    instance_id = entry.data[CONF_INSTANCE_ID]
    topic = heartbeat_topic(BASE, instance_id)

    published = _publishes(mqtt_mock, topic)
    assert len(published) == 1
    payload, qos, retain = published[0]
    assert qos == 0
    assert retain is False
    data = json.loads(payload)
    assert set(data) == {"instance_id", "name", "version", "devices", "session", "entities"}
    assert data["entities"] == "native"
    assert data["instance_id"] == instance_id
    assert data["name"] == entry.data[CONF_INSTANCE_NAME]
    assert data["version"] == json.loads(MANIFEST.read_text())["version"]
    assert data["devices"] == 1
    assert data["session"] == str(uuid.UUID(data["session"]))
    assert uuid.UUID(data["session"]).version == 4

    topics_in_order = [call.args[0] for call in mqtt_mock.async_publish.call_args_list]
    online = [
        index
        for index, call in enumerate(mqtt_mock.async_publish.call_args_list)
        if call.args[0] == availability_topic(BASE, instance_id) and call.args[1] == "online"
    ]
    assert online, "the online availability was not published"
    assert topics_in_order.index(topic) > online[-1]


async def test_own_echo_is_not_a_peer(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """The heartbeat this instance published, delivered back to its own subscription, is no roster row."""
    entry = await _setup(hass, make_hub_entry())
    presence = entry.runtime_data.presence
    topic = heartbeat_topic(BASE, entry.data[CONF_INSTANCE_ID])
    payload = _publishes(mqtt_mock, topic)[0][0]

    async_fire_mqtt_message(hass, topic, payload)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert presence.online_count() == 1
    assert [row["id"] for row in presence.rows()] == [entry.data[CONF_INSTANCE_ID]]


# --- strict validation (T-04-11) ----------------------------------------------------------------------------------


def _raw(data: dict[str, Any]) -> str:
    """Serialize with real characters, so a payload can be short in characters and long in UTF-8 bytes."""
    return json.dumps(data, ensure_ascii=False)


def _data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_message())
    data.update(overrides)
    return data


def _without(key: str) -> str:
    data = _data()
    del data[key]
    return _raw(data)


GOOD_TOPIC = heartbeat_topic(BASE, "inst-a")
INVALID_MESSAGES = {
    "not json": (GOOD_TOPIC, "nope"),
    "json list": (GOOD_TOPIC, "[1, 2]"),
    "json scalar": (GOOD_TOPIC, "7"),
    "too many characters": (GOOD_TOPIC, _raw(_data(pad="x" * (MAX_BROKER_MESSAGE_BYTES + 1)))),
    "too many bytes": (GOOD_TOPIC, _raw(_data(pad="\u00e4" * (MAX_BROKER_MESSAGE_BYTES // 2 + 1)))),
    "availability topic": (availability_topic(BASE, "inst-a"), _message()),
    "other base topic": (heartbeat_topic("other", "inst-a"), _message()),
    "id with a space": (heartbeat_topic(BASE, "inst a"), _message(instance_id="inst a")),
    "id with a wildcard": (heartbeat_topic(BASE, "inst+a"), _message(instance_id="inst+a")),
    "id too long": (heartbeat_topic(BASE, "i" * 65), _message(instance_id="i" * 65)),
    "payload id differs": (GOOD_TOPIC, _message(instance_id="inst-b")),
    "missing instance id": (GOOD_TOPIC, _without("instance_id")),
    "missing name": (GOOD_TOPIC, _without("name")),
    "missing version": (GOOD_TOPIC, _without("version")),
    "missing devices": (GOOD_TOPIC, _without("devices")),
    "missing session": (GOOD_TOPIC, _without("session")),
    "blank name": (GOOD_TOPIC, _message(name="   ")),
    "name with a newline": (GOOD_TOPIC, _message(name="a\nb")),
    "name over 64 characters": (GOOD_TOPIC, _message(name="n" * 65)),
    "name not a string": (GOOD_TOPIC, _message(name=5)),
    "blank version": (GOOD_TOPIC, _message(version=" ")),
    "version over 64 characters": (GOOD_TOPIC, _message(version="1" * 65)),
    "version not a string": (GOOD_TOPIC, _message(version=1)),
    "negative devices": (GOOD_TOPIC, _message(devices=-1)),
    "bool devices": (GOOD_TOPIC, _message(devices=True)),
    "float devices": (GOOD_TOPIC, _message(devices=1.5)),
    "string devices": (GOOD_TOPIC, _message(devices="2")),
    "too many devices": (GOOD_TOPIC, _message(devices=MAX_HEARTBEAT_DEVICES + 1)),
    "upper case session": (GOOD_TOPIC, _message(session=SESSION.upper())),
    "session without dashes": (GOOD_TOPIC, _message(session=SESSION.replace("-", ""))),
    "session not a uuid": (GOOD_TOPIC, _message(session="abc")),
    "session not a string": (GOOD_TOPIC, _message(session=5)),
}


@pytest.mark.parametrize(("topic", "payload"), list(INVALID_MESSAGES.values()), ids=list(INVALID_MESSAGES))
def test_parse_heartbeat_rejects_invalid_messages(topic: str, payload: str) -> None:
    assert parse_heartbeat(BASE, topic, payload) is None


def test_parse_heartbeat_accepts_the_limits() -> None:
    """The boundary values are valid: a zero device count, the maximum count and 64 character texts."""
    message = _message(name="n" * 64, version="1" * 64, devices=MAX_HEARTBEAT_DEVICES)
    assert parse_heartbeat(BASE, GOOD_TOPIC, message) is not None
    assert parse_heartbeat(BASE, GOOD_TOPIC, _message(devices=0)) is not None


async def test_retained_heartbeat_is_ignored(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """T-04-10: a retained heartbeat never creates a row; a live one afterwards does."""
    entry = await _setup(hass, make_hub_entry())
    presence = entry.runtime_data.presence

    async_fire_mqtt_message(hass, GOOD_TOPIC, _message(), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [row["id"] for row in presence.rows()] == [entry.data[CONF_INSTANCE_ID]]

    async_fire_mqtt_message(hass, GOOD_TOPIC, _message(), retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [row["id"] for row in presence.rows()][1:] == ["inst-a"]


async def test_rejected_heartbeats_log_nothing_from_the_payload(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, caplog: pytest.LogCaptureFixture
) -> None:
    """T-04-14: whatever a heartbeat carries, no field of it reaches a log line."""
    caplog.set_level(logging.DEBUG, logger="custom_components.mqtt_actions")
    entry = await _setup(hass, make_hub_entry())
    hostile = [
        _message(name="LONGNAME" + "x" * 80),
        _message(name="FORGED\nWARNING mqtt_actions: injected"),
        _message(name="<script>MARKUPNAME</script>"),
        _message(version="VERSIONTEXT" + "9" * 80),
        _message(session="SESSIONTEXT"),
        _message(instance_id="OTHERID"),
        "RAWNONJSON{",
    ]

    for payload in hostile:
        async_fire_mqtt_message(hass, GOOD_TOPIC, payload)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.presence.online_count() >= 1
    # Core MQTT logs every received payload at debug level; only the lines of this integration are the subject here
    ours = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("custom_components.mqtt_actions")
    )
    for text in ("LONGNAME", "FORGED", "injected", "MARKUPNAME", "VERSIONTEXT", "SESSIONTEXT", "OTHERID", "RAWNONJSON"):
        assert text not in ours


async def test_heartbeat_tick_publishes_every_30_seconds(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-05: a tick publishes a heartbeat; after the manager stopped no tick publishes anything."""
    entry = await _setup(hass, make_hub_entry())
    topic = heartbeat_topic(BASE, entry.data[CONF_INSTANCE_ID])
    assert len(_publishes(mqtt_mock, topic)) == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HEARTBEAT_INTERVAL_SECONDS + 1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_publishes(mqtt_mock, topic)) == 2
    assert all(item[1:] == (0, False) for item in _publishes(mqtt_mock, topic))

    await entry.runtime_data.async_stop()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3 * HEARTBEAT_INTERVAL_SECONDS))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_publishes(mqtt_mock, topic)) == 2


async def test_peer_cap(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, caplog: pytest.LogCaptureFixture
) -> None:
    """T-04-12: with the cap patched small, further instance ids are not tracked and the overflow is logged once."""
    entry = await _setup(hass, make_hub_entry())
    presence = entry.runtime_data.presence

    with patch("custom_components.mqtt_actions.presence.MAX_TRACKED_INSTANCES", 2):
        for number in range(5):
            instance_id = f"peer-{number}"
            async_fire_mqtt_message(
                hass, heartbeat_topic(BASE, instance_id), _message(instance_id=instance_id, name=f"Peer {number}")
            )
        await hass.async_block_till_done(wait_background_tasks=True)
        # A tracked peer keeps updating
        async_fire_mqtt_message(
            hass, heartbeat_topic(BASE, "peer-0"), _message(instance_id="peer-0", name="Peer 0 renamed")
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    peers = presence.rows()[1:]
    assert [row["id"] for row in peers] == ["peer-0", "peer-1"]
    assert peers[0]["name"] == "Peer 0 renamed"
    assert caplog.text.count("further instances are not tracked") == 1


# --- the owner-offline answer (D-09, assumption A10) --------------------------------------------------------------


class _Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


def _roster() -> tuple[Roster, _Clock, dict[str, str]]:
    clock = _Clock()
    availability: dict[str, str] = {}
    roster = Roster(clock, availability.get)
    roster.restart_listening()
    return roster, clock, availability


def _hb(instance_id: str = "owner") -> Heartbeat:
    return Heartbeat(instance_id=instance_id, name="Owner", version="0.1.0", devices=1, session=SESSION)


def test_owner_offline_when_the_owner_announced_offline() -> None:
    roster, _clock, availability = _roster()
    availability["owner"] = "offline"
    assert roster.owner_offline("owner") is True
    roster.observe(_hb())
    assert roster.owner_offline("owner") is True
    assert roster.status("owner") == "offline"


def test_owner_offline_when_the_heartbeat_is_stale() -> None:
    roster, clock, availability = _roster()
    availability["owner"] = "online"
    roster.observe(_hb())
    clock.now += HEARTBEAT_OFFLINE_SECONDS - 1
    assert roster.owner_offline("owner") is False
    assert roster.status("owner") == "online"
    clock.now += 2
    assert roster.owner_offline("owner") is True
    assert roster.status("owner") == "offline"


def test_owner_with_a_fresh_heartbeat_is_not_offline() -> None:
    roster, _clock, _availability = _roster()
    roster.observe(_hb())
    assert roster.owner_offline("owner") is False


def test_owner_that_announced_online_without_a_heartbeat_is_never_offline() -> None:
    roster, clock, availability = _roster()
    availability["owner"] = "online"
    clock.now += 600
    assert roster.owner_offline("owner") is False
    assert roster.status("owner") is None


def test_unknown_owner_is_offline_only_after_listening_long_enough() -> None:
    roster, clock, _availability = _roster()
    clock.now += HEARTBEAT_OFFLINE_SECONDS - 1
    assert roster.owner_offline("owner") is False
    clock.now += 1
    assert roster.owner_offline("owner") is True


def test_a_reconnect_restarts_the_listening_time() -> None:
    roster, clock, _availability = _roster()
    clock.now += 2 * HEARTBEAT_OFFLINE_SECONDS
    assert roster.owner_offline("owner") is True
    roster.restart_listening()
    assert roster.owner_offline("owner") is False
    clock.now += HEARTBEAT_OFFLINE_SECONDS
    assert roster.owner_offline("owner") is True


# --- a second instance with the same instance id (D-07, assumption A12) -----------------------------------------------


def _use_clock(manager: Any) -> list[float]:
    """Replace the manager clock by a settable one; the returned list holds its single value."""
    now = [1000.0]
    manager.clock = lambda: now[0]
    return now


async def _heartbeat_of_own_id(hass: HomeAssistant, entry: MockConfigEntry, session: str) -> None:
    """Deliver a live heartbeat that carries this instance's own id and the given session."""
    instance_id = entry.data[CONF_INSTANCE_ID]
    async_fire_mqtt_message(
        hass, heartbeat_topic(BASE, instance_id), _message(instance_id=instance_id, session=session)
    )
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_duplicate_detection_needs_two_foreign_session_heartbeats(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-07: the own echo never counts, one foreign session is no duplicate, two within 90 seconds are."""
    entry = await _setup(hass, make_hub_entry())
    presence = entry.runtime_data.presence
    now = _use_clock(entry.runtime_data)
    assert presence.duplicate_detected is False

    await _heartbeat_of_own_id(hass, entry, presence.session)
    await _heartbeat_of_own_id(hass, entry, presence.session)
    await _heartbeat_of_own_id(hass, entry, presence.session)
    assert presence.duplicate_detected is False

    await _heartbeat_of_own_id(hass, entry, SESSION)
    assert presence.duplicate_detected is False
    now[0] += HEARTBEAT_OFFLINE_SECONDS - 1
    await _heartbeat_of_own_id(hass, entry, SESSION)
    assert presence.duplicate_detected is True
    # An own instance id never becomes a roster row
    assert [row["id"] for row in presence.rows()] == [entry.data[CONF_INSTANCE_ID]]


async def test_two_foreign_heartbeats_more_than_90_seconds_apart_are_no_duplicate(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A12: an observation older than the offline timeout is dropped, so a slow trickle never confirms a duplicate."""
    entry = await _setup(hass, make_hub_entry())
    presence = entry.runtime_data.presence
    now = _use_clock(entry.runtime_data)

    await _heartbeat_of_own_id(hass, entry, SESSION)
    now[0] += HEARTBEAT_OFFLINE_SECONDS + 1
    await _heartbeat_of_own_id(hass, entry, SESSION)
    assert presence.duplicate_detected is False

    now[0] += 1
    await _heartbeat_of_own_id(hass, entry, SESSION)
    assert presence.duplicate_detected is True


async def test_duplicate_clears_after_90_seconds_of_silence(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A12: with no foreign session heard for 90 seconds the expiry timer clears the detection again."""
    entry = await _setup(hass, make_hub_entry())
    presence = entry.runtime_data.presence
    now = _use_clock(entry.runtime_data)
    await _heartbeat_of_own_id(hass, entry, SESSION)
    await _heartbeat_of_own_id(hass, entry, SESSION)
    assert presence.duplicate_detected is True

    now[0] += HEARTBEAT_OFFLINE_SECONDS - 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HEARTBEAT_OFFLINE_SECONDS - 1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert presence.duplicate_detected is True

    now[0] += 2
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HEARTBEAT_OFFLINE_SECONDS + 5))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert presence.duplicate_detected is False


async def test_duplicate_observations_are_bounded(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-04-55: a flood of foreign-session heartbeats keeps at most MAX_DUPLICATE_OBSERVATIONS records."""
    entry = await _setup(hass, make_hub_entry())
    presence = entry.runtime_data.presence
    _use_clock(entry.runtime_data)

    for number in range(const.MAX_DUPLICATE_OBSERVATIONS * 3):
        await _heartbeat_of_own_id(hass, entry, str(uuid.UUID(int=number + 1)))

    assert presence.duplicate_detected is True
    assert len(presence._duplicate_seen) <= const.MAX_DUPLICATE_OBSERVATIONS


# --- the roster as a gate: forged capability and flooding must not open it (WR-03) -------------------------------


def _capable(instance_id: str = "owner") -> Heartbeat:
    return Heartbeat(instance_id=instance_id, name="Owner", version="0.2.0", devices=1, session=SESSION, native=True)


def test_a_capability_claim_never_replaces_a_fresh_legacy_row() -> None:
    """WR-03: a forged native heartbeat under the id of an online legacy peer must not make it stop blocking."""
    roster, clock, availability = _roster()
    availability["owner"] = "online"
    roster.observe(_hb())

    assert roster.observe(_capable()) is True

    assert roster.legacy_online_names() == ["Owner"]
    # The forgery does not even keep the legacy row fresh: its own heartbeats do
    clock.now += HEARTBEAT_OFFLINE_SECONDS + 1
    assert roster.legacy_online_names() == []


@pytest.mark.parametrize("how", ["stale", "announced_offline"])
def test_a_capability_claim_replaces_a_legacy_row_that_no_longer_blocks(how: str) -> None:
    """WR-03: the same peer upgraded and restarted; once its old row stopped blocking, the new heartbeat counts."""
    roster, clock, availability = _roster()
    availability["owner"] = "online"
    roster.observe(_hb())
    if how == "stale":
        clock.now += HEARTBEAT_OFFLINE_SECONDS + 1
    else:
        availability["owner"] = "offline"

    roster.observe(_capable())
    availability["owner"] = "online"

    assert roster.legacy_online_names() == []
    assert roster.status("owner") == "online"


def test_a_full_roster_is_saturated_for_the_timeout_after_it_dropped_a_new_peer() -> None:
    """WR-03: a dropped new peer may be a legacy instance, so the roster says so for as long as the drop counts."""
    roster, clock, _availability = _roster()
    for number in range(const.MAX_TRACKED_INSTANCES):
        assert roster.observe(_capable(f"peer-{number}")) is True
    assert roster.saturated() is False

    assert roster.observe(_hb("late-legacy-peer")) is False

    assert roster.saturated() is True
    clock.now += HEARTBEAT_OFFLINE_SECONDS + 1
    assert roster.saturated() is False
