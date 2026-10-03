"""The optional MQTT Discovery export of native devices: payload, options and republish (D-03, D-04, D-11, ENT-03)."""

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import discovery
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_DISCOVERY_EXPORT,
    CONF_EXPORT_PREFIX,
    DEFAULT_EXPORT_PREFIX,
    DOMAIN,
    STORE_KEY,
    STORE_VERSION,
    SUBENTRY_SELECT,
)
from custom_components.mqtt_actions.model import spec_from_data
from custom_components.mqtt_actions.mqtt_gateway import MqttGateway
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, state_topic
from tests.documents import make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

CORE_PREFIX = "homeassistant"
EXPORT_ON = {CONF_DISCOVERY_EXPORT: True}


def _seed_native(hass_storage: dict[str, Any]) -> None:
    """Seed the persisted native flag the way production stores it."""
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {"native": {"instance": True, "pending": [], "devices": []}},
    }


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _export_topic(device_id: str, prefix: str = DEFAULT_EXPORT_PREFIX) -> str:
    return discovery_topic(prefix, device_id)


def _only_payload(mqtt_mock: Any, topic: str) -> dict[str, Any]:
    ((payload, _qos, _retain),) = _publishes(mqtt_mock, topic)
    return json.loads(payload)


# --- the payload (D-11) ----------------------------------------------------------------------------------------------


def test_build_export_has_one_component_no_buttons_and_is_disabled_by_default() -> None:
    """D-11: one component, disabled by default, no test button, no test topic and no tombstone entry."""
    switch_spec = spec_from_data("switch", "Lamp", {CONF_DEVICE_ID: "dev-1"})
    select_spec = make_spec(SUBENTRY_SELECT, device_id="dev-2", name="Mode", options=[("a", "A", []), ("b", "B", [])])

    for spec, kind in ((switch_spec, "switch"), (select_spec, "select")):
        payload = discovery.build_export(spec=spec, base_topic="mqtt_actions", instance_id="inst-1", sw_version="1.2.3")

        assert payload["device"] == {"identifiers": [f"mqtt_actions_{spec.device_id}"], "name": spec.name}
        assert payload["origin"] == {"name": "MQTT Actions", "sw_version": "1.2.3"}
        assert payload["availability"] == [{"topic": "mqtt_actions/v1/instances/inst-1/availability"}]
        assert list(payload["components"]) == [kind]
        component = payload["components"][kind]
        assert component["enabled_by_default"] is False
        assert component["unique_id"] == spec.device_id
        assert component["state_topic"] == component["command_topic"] == state_topic("mqtt_actions", spec.device_id)
        assert "/test" not in json.dumps(payload)
        assert "button" not in json.dumps(payload)
        assert json.loads(json.dumps(payload)) == payload


# --- the tracer: publish on the export prefix ------------------------------------------------------------------------


async def test_a_native_device_publishes_the_export_when_enabled(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03, D-11: the retained export is published on the export prefix and nothing on the core discovery prefix."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    await _setup(hass, make_hub_entry([subentry], options=EXPORT_ON))

    ((payload, qos, retain),) = _publishes(mqtt_mock, _export_topic(device_id))
    assert (qos, retain) == (1, True)
    exported = json.loads(payload)
    assert list(exported["components"]) == ["switch"]
    assert exported["components"]["switch"]["enabled_by_default"] is False
    assert _publishes(mqtt_mock, discovery_topic(CORE_PREFIX, device_id)) == []


async def test_the_export_is_off_by_default(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03: without the option a native device publishes nothing on any discovery topic."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    await _setup(hass, make_hub_entry([subentry]))

    topics = [call.args[0] for call in mqtt_mock.async_publish.call_args_list]
    assert [topic for topic in topics if "/device/" in topic and topic.endswith("/config")] == []
    assert _export_topic(device_id) not in topics
    assert discovery_topic(CORE_PREFIX, device_id) not in topics


async def test_the_export_on_the_core_prefix_creates_a_disabled_duplicate(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-5-17: on the prefix core listens to, the export becomes a disabled mqtt entry and the native entity stays."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    entry = await _setup(
        hass, make_hub_entry([subentry], options={CONF_DISCOVERY_EXPORT: True, CONF_EXPORT_PREFIX: CORE_PREFIX})
    )
    topic = discovery_topic(CORE_PREFIX, device_id)
    ((payload, _qos, _retain),) = _publishes(mqtt_mock, topic)
    # The mocked client keeps no retained messages; core hears the export as the replay a real broker would deliver
    async_fire_mqtt_message(hass, availability_topic("mqtt_actions", entry.data["instance_id"]), "online")
    async_fire_mqtt_message(hass, topic, payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    registry = er.async_get(hass)
    exported = registry.async_get_entity_id("switch", "mqtt", device_id)
    native = registry.async_get_entity_id("switch", DOMAIN, device_id)
    assert exported is not None
    assert native is not None
    assert registry.async_get(exported).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get(native).disabled_by is None
    enabled = [
        entity.entity_id
        for entity in registry.entities.values()
        if entity.unique_id == device_id and entity.disabled_by is None
    ]
    assert enabled == [native]


async def test_a_legacy_device_never_publishes_the_export(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A device on the legacy path publishes the legacy payload only, whatever the export option says."""
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    await _setup(hass, make_hub_entry([subentry], options=EXPORT_ON))

    assert _publishes(mqtt_mock, _export_topic(device_id)) == []
    legacy = _only_payload(mqtt_mock, discovery_topic(CORE_PREFIX, device_id))
    assert any(key.startswith("test_") for key in legacy["components"])


async def test_the_export_has_no_healing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-11: an empty retained payload on the export topic is not published again and nothing watches the prefix."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)
    subscribed: list[str] = []
    real_subscribe = MqttGateway.async_subscribe

    async def _recording(self: MqttGateway, topic: str, *args: Any, **kwargs: Any) -> Any:
        subscribed.append(topic)
        return await real_subscribe(self, topic, *args, **kwargs)

    with patch.object(MqttGateway, "async_subscribe", _recording):
        await _setup(hass, make_hub_entry([subentry], options=EXPORT_ON))

    assert len(_publishes(mqtt_mock, _export_topic(device_id))) == 1
    async_fire_mqtt_message(hass, _export_topic(device_id), "", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(_publishes(mqtt_mock, _export_topic(device_id))) == 1
    assert not [topic for topic in subscribed if topic.startswith(DEFAULT_EXPORT_PREFIX)]
