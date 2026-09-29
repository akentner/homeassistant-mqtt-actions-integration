"""Discovery contract against real core MQTT discovery: identity, availability, toggle, prefix and clearing."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.components import mqtt
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import discovery
from custom_components.mqtt_actions.const import CONF_DEVICE_ID, CONF_INSTANCE_ID, DOMAIN
from custom_components.mqtt_actions.mqtt_gateway import MqttGateway
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

MANIFEST_VERSION = json.loads(
    (Path(__file__).parent.parent / "custom_components" / DOMAIN / "manifest.json").read_text()
)["version"]


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


async def _setup_lamp(
    hass: HomeAssistant, make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[MockConfigEntry, str]:
    """Set up a hub entry with one switch device called Lamp; return the entry and the device id."""
    sub = make_switch_subentry("Lamp")
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    # The mocked client keeps no retained messages; a real broker replays the retained online to the new entity
    topic = availability_topic(entry.data["base_topic"], entry.data[CONF_INSTANCE_ID])
    async_fire_mqtt_message(hass, topic, "online", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry, sub["data"][CONF_DEVICE_ID]


def _published_discovery(mqtt_mock: Any, device_id: str, prefix: str = "homeassistant") -> dict[str, Any]:
    ((payload, _qos, _retain), *_rest) = _publishes(mqtt_mock, discovery_topic(prefix, device_id))
    return json.loads(payload)


# --- payload (DSC-01, D-01, D-03) ----------------------------------------------------------------------------------


def test_discovery_payload_full_keys() -> None:
    """The builder output holds every key core MQTT discovery needs and is JSON-serialisable."""
    payload = discovery.build_switch_discovery(
        base_topic="mqtt_actions",
        device_id="dev-1",
        instance_id="inst-1",
        name="Lamp",
        sw_version="1.2.3",
    )

    assert payload["device"] == {"identifiers": ["mqtt_actions_dev-1"], "name": "Lamp"}
    assert payload["origin"] == {"name": "MQTT Actions", "sw_version": "1.2.3"}
    topic = "mqtt_actions/v1/devices/dev-1/state"
    assert payload["components"]["switch"] == {
        "platform": "switch",
        "unique_id": "dev-1",
        "name": None,
        "state_topic": topic,
        "command_topic": topic,
        "retain": True,
        "qos": 1,
        "payload_on": "ON",
        "payload_off": "OFF",
        "value_template": "{{ value | upper }}",
    }
    assert payload["availability"] == [{"topic": "mqtt_actions/v1/instances/inst-1/availability"}]
    assert json.loads(json.dumps(payload)) == payload


async def test_discovery_payload_carries_manifest_version(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The published origin sw_version is the manifest version, not a literal."""
    _entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)

    published = _published_discovery(mqtt_mock, device_id)

    assert published["origin"] == {"name": "MQTT Actions", "sw_version": MANIFEST_VERSION}


async def test_discovery_command_topic_equals_state_topic(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-01: the published state and command topics are the same string."""
    entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)

    switch = _published_discovery(mqtt_mock, device_id)["components"]["switch"]

    assert switch["state_topic"] == switch["command_topic"] == state_topic(entry.data["base_topic"], device_id)


async def test_discovery_publish_is_retained_qos1(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The discovery message is retained and qos 1."""
    _entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)

    ((_payload, qos, retain),) = _publishes(mqtt_mock, discovery_topic("homeassistant", device_id))

    assert qos == 1
    assert retain is True


# --- prefix (D-04) -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mqtt_config_entry_options",
    [{mqtt.CONF_BIRTH_MESSAGE: {}, mqtt.CONF_DISCOVERY_PREFIX: "custom"}],
)
async def test_discovery_uses_prefix_from_mqtt_options(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """An options prefix moves the config topic and core MQTT still creates the entity from it."""
    _entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)

    assert len(_publishes(mqtt_mock, f"custom/device/{device_id}/config")) == 1
    assert _publishes(mqtt_mock, f"homeassistant/device/{device_id}/config") == []
    assert hass.states.get("switch.lamp") is not None


@pytest.mark.parametrize(
    ("mqtt_config_entry_data", "mqtt_config_entry_options"),
    [
        (
            {mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_PROTOCOL: "5", mqtt.CONF_DISCOVERY_PREFIX: "fromdata"},
            {mqtt.CONF_BIRTH_MESSAGE: {}, mqtt.CONF_DISCOVERY_PREFIX: "fromoptions"},
        )
    ],
)
async def test_discovery_prefix_options_win_over_data(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-04: options are merged over data, as core MQTT does, so the options value wins."""
    _entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)

    assert len(_publishes(mqtt_mock, f"fromoptions/device/{device_id}/config")) == 1
    assert _publishes(mqtt_mock, f"fromdata/device/{device_id}/config") == []


@pytest.mark.parametrize(
    ("mqtt_config_entry_data", "mqtt_config_entry_options"),
    [({mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_PROTOCOL: "5", mqtt.CONF_DISCOVERY_PREFIX: "fromdata"}, {})],
)
async def test_discovery_prefix_falls_back_to_data(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """A prefix present only in the entry data is honoured."""
    assert MqttGateway(hass).discovery_prefix() == "fromdata"


async def test_discovery_prefix_defaults_to_homeassistant(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """Without any configured value the prefix is homeassistant."""
    assert MqttGateway(hass).discovery_prefix() == "homeassistant"


def test_discovery_prefix_without_mqtt_entry(hass: HomeAssistant) -> None:
    """With no MQTT entry at all the default prefix is returned."""
    assert MqttGateway(hass).discovery_prefix() == "homeassistant"


# --- discovery enabled (D-04) --------------------------------------------------------------------------------------


async def test_gateway_discovery_enabled_by_default(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """Discovery is on unless the MQTT entry turns it off."""
    assert MqttGateway(hass).discovery_enabled() is True


@pytest.mark.parametrize("mqtt_config_entry_options", [{mqtt.CONF_BIRTH_MESSAGE: {}, mqtt.CONF_DISCOVERY: False}])
async def test_gateway_discovery_enabled_reads_mqtt_entry(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """The MQTT entry option discovery=False is reported (options merged over data)."""
    assert MqttGateway(hass).discovery_enabled() is False


def test_gateway_discovery_enabled_without_mqtt_entry(hass: HomeAssistant) -> None:
    """With no MQTT entry the default (enabled) is returned."""
    assert MqttGateway(hass).discovery_enabled() is True


# --- entity created by core MQTT (DSC-01, D-03, D-07) --------------------------------------------------------------


async def test_discovery_creates_switch_entity(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Core MQTT turns the published payload into a switch: unknown state, UUID unique_id, named device."""
    _entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)

    state = hass.states.get("switch.lamp")
    assert state is not None
    assert state.state == "unknown"
    entity = er.async_get(hass).async_get("switch.lamp")
    assert entity is not None
    assert entity.unique_id == device_id
    assert entity.platform == "mqtt"
    (mqtt_entry,) = hass.config_entries.async_entries("mqtt")
    device = dr.async_get(hass).async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry.entry_id)
    assert device is not None
    assert device.name == "Lamp"


async def test_discovery_availability_toggles_entity(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The instance availability topic drives the entity: offline is unavailable, online restores it."""
    entry, _device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)
    topic = availability_topic(entry.data["base_topic"], entry.data[CONF_INSTANCE_ID])
    assert hass.states.get("switch.lamp").state == "unknown"

    async_fire_mqtt_message(hass, topic, "offline")
    await hass.async_block_till_done()
    assert hass.states.get("switch.lamp").state == "unavailable"

    async_fire_mqtt_message(hass, topic, "online")
    await hass.async_block_till_done()
    assert hass.states.get("switch.lamp").state == "unknown"


async def test_discovery_accepts_lowercase_inbound(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The value template upper-cases, so a lower-case live on turns the entity on."""
    entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)

    async_fire_mqtt_message(hass, state_topic(entry.data["base_topic"], device_id), "on", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("switch.lamp").state == "on"


async def test_discovery_toggle_publishes_retained_on_and_off(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """STA-01: switch.turn_on and turn_off publish ON and OFF to the shared state topic, qos 1, retained."""
    entry, device_id = await _setup_lamp(hass, make_hub_entry, make_switch_subentry)
    topic = state_topic(entry.data["base_topic"], device_id)

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.lamp"}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.lamp"}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _publishes(mqtt_mock, topic) == [("ON", 1, True), ("OFF", 1, True)]


# --- clearing and availability publisher ---------------------------------------------------------------------------


async def test_discovery_clear_publishes_empty_retained(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """async_clear_device publishes an empty retained qos-1 payload on the discovery topic."""
    publisher = discovery.DiscoveryPublisher(MqttGateway(hass), "mqtt_actions", "0.1.0")

    await publisher.async_clear_device("dev-1")

    assert _publishes(mqtt_mock, "homeassistant/device/dev-1/config") == [("", 1, True)]


async def test_discovery_clear_state_publishes_empty_retained(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """async_clear_state publishes an empty retained qos-1 payload on the state topic."""
    publisher = discovery.DiscoveryPublisher(MqttGateway(hass), "mqtt_actions", "0.1.0")

    await publisher.async_clear_state("dev-1")

    assert _publishes(mqtt_mock, "mqtt_actions/v1/devices/dev-1/state") == [("", 1, True)]


async def test_discovery_availability_publishes_online_offline_and_cleared(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """The availability publisher covers online, offline and cleared, always retained with qos 1."""
    publisher = discovery.DiscoveryPublisher(MqttGateway(hass), "mqtt_actions", "0.1.0")

    await publisher.async_publish_availability("inst-1", discovery.AvailabilityState.ONLINE)
    await publisher.async_publish_availability("inst-1", discovery.AvailabilityState.OFFLINE)
    await publisher.async_publish_availability("inst-1", discovery.AvailabilityState.CLEARED)

    assert _publishes(mqtt_mock, "mqtt_actions/v1/instances/inst-1/availability") == [
        ("online", 1, True),
        ("offline", 1, True),
        ("", 1, True),
    ]
