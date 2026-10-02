"""The hub device, its roster sensor and the resync button with a real entry setup on the MQTT mock (OPS-03)."""

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_fire_time_changed

from custom_components.mqtt_actions import const as const_module
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    DOMAIN,
    HEARTBEAT_OFFLINE_SECONDS,
    MAX_TRACKED_INSTANCES,
)
from custom_components.mqtt_actions.sensor import RosterSensor
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, heartbeat_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BASE = "mqtt_actions"
SESSION = "6f1c0f0e-3a52-4f43-8d0c-5a0b7f3c9d21"


async def _setup(hass: HomeAssistant, entry: Any) -> Any:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _heartbeat(hass: HomeAssistant, instance_id: str, name: str = "Peer", version: str = "0.1.0") -> None:
    """Deliver a live heartbeat of a foreign instance on its heartbeat topic."""
    payload = json.dumps(
        {"instance_id": instance_id, "name": name, "version": version, "devices": 2, "session": SESSION}
    )
    async_fire_mqtt_message(hass, heartbeat_topic(BASE, instance_id), payload, retain=False)


def _roster_entity_id(hass: HomeAssistant, entry: Any) -> str | None:
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_roster")


async def test_hub_device_and_roster_sensor_exist(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-06, D-13: a hub device keyed by the entry id carries a diagnostic roster sensor that counts this instance."""
    entry = await _setup(hass, make_hub_entry())

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert device is not None
    assert entry.entry_id in device.config_entries
    assert device.name == "Test instance"
    assert device.manufacturer == "MQTT Actions"
    assert device.model == "Hub"

    entity_id = _roster_entity_id(hass, entry)
    assert entity_id is not None
    registered = er.async_get(hass).async_get(entity_id)
    assert registered is not None
    assert registered.platform == DOMAIN
    assert registered.device_id == device.id
    assert registered.entity_category is EntityCategory.DIAGNOSTIC
    assert hass.states.get(entity_id).state == "1"


async def test_roster_sensor_follows_the_heartbeats(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-06: a heartbeat of a foreign instance raises the count, a second distinct instance raises it again."""
    entry = await _setup(hass, make_hub_entry())
    entity_id = _roster_entity_id(hass, entry)
    assert entity_id is not None

    _heartbeat(hass, "peer-one")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == "2"

    _heartbeat(hass, "peer-two")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == "3"


async def test_unload_removes_hub_entities_and_stops_the_manager(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-13: unloading removes the entity states and stops the manager; a new setup works."""
    entry = await _setup(hass, make_hub_entry())
    manager = entry.runtime_data
    entity_id = _roster_entity_id(hass, entry)
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert manager.running is False
    state = hass.states.get(entity_id)
    assert state is None or state.state == "unavailable"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state == "1"


ROW_KEYS = {"name", "id", "version", "last_seen", "online"}
# The recorder drops the attributes of a state above this size (homeassistant.components.recorder.const)
RECORDER_MAX_ATTRS_BYTES = 16384


def _instances(hass: HomeAssistant, entity_id: str) -> list[dict[str, Any]]:
    return hass.states.get(entity_id).attributes["instances"]


def _recorded_attributes_bytes(hass: HomeAssistant, entity_id: str) -> int:
    """Return the JSON size of the attributes the recorder would store, that is without the unrecorded ones."""
    attributes = {
        key: value
        for key, value in hass.states.get(entity_id).attributes.items()
        if key not in RosterSensor._unrecorded_attributes
    }
    return len(json.dumps(attributes).encode())


async def test_roster_attributes_list_every_instance(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-06: every row has exactly the five keys, this instance comes first and is online, peers follow."""
    entry = await _setup(hass, make_hub_entry())
    entity_id = _roster_entity_id(hass, entry)
    assert entity_id is not None

    _heartbeat(hass, "peer-one", name="Peer One", version="1.2.3")
    await hass.async_block_till_done(wait_background_tasks=True)

    own, peer = _instances(hass, entity_id)
    assert set(own) == ROW_KEYS
    assert set(peer) == ROW_KEYS
    assert own["id"] == entry.data[CONF_INSTANCE_ID]
    assert own["name"] == "Test instance"
    assert own["version"] == entry.runtime_data.version
    assert own["online"] is True
    assert (peer["id"], peer["name"], peer["version"], peer["online"]) == ("peer-one", "Peer One", "1.2.3", True)


async def test_peer_turns_offline_in_the_sensor_after_90_seconds(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-05, D-06: after the expiry the count drops, and the peer stays listed with online False."""
    entry = await _setup(hass, make_hub_entry())
    now = [1000.0]
    entry.runtime_data.clock = lambda: now[0]
    entity_id = _roster_entity_id(hass, entry)
    assert entity_id is not None

    _heartbeat(hass, "peer-one")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == "2"

    now[0] += HEARTBEAT_OFFLINE_SECONDS + 2
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HEARTBEAT_OFFLINE_SECONDS + 5))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "1"
    rows = {row["id"]: row for row in _instances(hass, entity_id)}
    assert rows["peer-one"]["online"] is False
    assert rows[entry.data[CONF_INSTANCE_ID]]["online"] is True


async def test_roster_attribute_is_unrecorded_and_capped(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-04-16: the list is unrecorded, never longer than the cap plus this instance, and the recorded rest is small."""
    assert "instances" in RosterSensor._unrecorded_attributes

    entry = await _setup(hass, make_hub_entry())
    entity_id = _roster_entity_id(hass, entry)
    assert entity_id is not None

    with patch("custom_components.mqtt_actions.sensor.MAX_TRACKED_INSTANCES", 3):
        for number in range(6):
            _heartbeat(hass, f"peer-{number}")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(_instances(hass, entity_id)) == 3 + 1

    # The real cap: every tracked peer fits the list (the roster itself is capped at the same number)
    for number in range(MAX_TRACKED_INSTANCES + 10):
        _heartbeat(hass, f"flood-{number}", name="n" * 64, version="v" * 64)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_instances(hass, entity_id)) == MAX_TRACKED_INSTANCES + 1
    assert _recorded_attributes_bytes(hass, entity_id) < RECORDER_MAX_ATTRS_BYTES


ON_ACTIONS = [{"action": "test.on"}]


def _resync_entity_id(hass: HomeAssistant, entry: Any) -> str | None:
    return er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_resync")


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _published_topics(mqtt_mock: Any) -> list[str]:
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list]


async def test_resync_button_republishes_in_the_phase_3_order(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-12: the press publishes the config document, the discovery and `online`, in that order and never a clear."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = sub["data"][CONF_DEVICE_ID]
    entity_id = _resync_entity_id(hass, entry)
    assert entity_id is not None
    mqtt_mock.async_publish.reset_mock()

    await _press(hass, entity_id)

    calls = mqtt_mock.async_publish.call_args_list
    topics = _published_topics(mqtt_mock)
    document = config_topic(BASE, device_id)
    discovery = discovery_topic("homeassistant", device_id)
    availability = availability_topic(BASE, entry.data[CONF_INSTANCE_ID])
    assert topics.index(document) < topics.index(discovery) < topics.index(availability)
    for topic in (document, discovery, availability):
        (call,) = (call for call in calls if call.args[0] == topic)
        assert call.args[3] is True  # retained
        assert call.args[1] not in {"", b""}
    assert calls[topics.index(availability)].args[1] == "online"
    assert [call.args[0] for call in calls if call.args[1] in {"", b""}] == []


async def test_resync_is_throttled(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-15: a second press within the cooldown publishes nothing; after the cooldown it publishes again."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    now = [1000.0]
    entry.runtime_data.clock = lambda: now[0]
    entity_id = _resync_entity_id(hass, entry)
    assert entity_id is not None
    document = config_topic(BASE, sub["data"][CONF_DEVICE_ID])
    mqtt_mock.async_publish.reset_mock()

    await _press(hass, entity_id)
    assert _published_topics(mqtt_mock).count(document) == 1

    now[0] += const_module.RESYNC_MIN_INTERVAL_SECONDS - 1
    mqtt_mock.async_publish.reset_mock()
    await _press(hass, entity_id)
    assert _published_topics(mqtt_mock) == []

    now[0] += 2
    await _press(hass, entity_id)
    assert _published_topics(mqtt_mock).count(document) == 1


async def test_resync_returns_false_when_not_running(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A stopped manager neither publishes nor answers True."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    manager = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert manager.running is False
    mqtt_mock.async_publish.reset_mock()

    assert await manager.async_resync() is False
    assert _published_topics(mqtt_mock) == []


async def test_resync_returns_true_after_a_republish(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The first call republishes and says so; a call inside the cooldown says False."""
    entry = await _setup(hass, make_hub_entry())
    manager = entry.runtime_data
    now = [1000.0]
    manager.clock = lambda: now[0]

    assert await manager.async_resync() is True
    assert await manager.async_resync() is False


async def test_resync_button_entity(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """D-12: the button sits on the hub device in the config category."""
    entry = await _setup(hass, make_hub_entry())
    entity_id = _resync_entity_id(hass, entry)
    assert entity_id is not None
    registered = er.async_get(hass).async_get(entity_id)
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert registered is not None
    assert device is not None
    assert registered.device_id == device.id
    assert registered.entity_category is EntityCategory.CONFIG
