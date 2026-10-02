"""Heartbeat parsing and the heartbeat of one instance on the MQTT mock (OPS-03, D-05)."""

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions.const import CONF_INSTANCE_ID, CONF_INSTANCE_NAME
from custom_components.mqtt_actions.presence import Heartbeat, parse_heartbeat
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
    """D-05: one heartbeat after the online availability, QoS 0, not retained, five keys."""
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
    assert set(data) == {"instance_id", "name", "version", "devices", "session"}
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
