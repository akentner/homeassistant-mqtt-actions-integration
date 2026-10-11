"""The duplicate guard on an instance that only receives an export (UAT-04 clause 2, UAT04-RECEIVER-GUARD, D-08)."""

import json
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import discovery
from custom_components.mqtt_actions.const import CONF_DISCOVERY_EXPORT, DOMAIN
from custom_components.mqtt_actions.topics import discovery_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.test_discovery_export import CORE_PREFIX, _mqtt_row
from tests.test_native_entities import BASE, _deliver, _entity_id, _manager, _presence, _publishes, _setup

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.model import DeviceSpec

FOREIGN_SW_VERSION = "0.1.0"


async def _native_mirror(hass: HomeAssistant, make_hub_entry: Callable, spec: DeviceSpec) -> MockConfigEntry:
    """Set up a hub entry with default options and deliver the marked document of a foreign owner that is online."""
    entry = await _setup(hass, make_hub_entry())
    await _presence(hass, "online")
    await _deliver(hass, spec.device_id, document_payload(spec, native=True))
    return entry


def _mqtt_device(hass: HomeAssistant, device_id: str) -> dr.DeviceEntry | None:
    """Return the core MQTT device that the discovery payload of a device id names."""
    mqtt_entry = hass.config_entries.async_entries("mqtt")[0]
    return dr.async_get(hass).async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry.entry_id)


def _foreign_export(spec: DeviceSpec) -> tuple[str, str]:
    """Return the core-prefix topic and the payload of the export another instance publishes for the device."""
    payload = discovery.build_export(
        spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version=FOREIGN_SW_VERSION
    )
    return discovery_topic(CORE_PREFIX, spec.device_id), json.dumps(payload)


async def _receive_foreign_export(hass: HomeAssistant, spec: DeviceSpec) -> None:
    """Hand the retained export of another instance to core MQTT, as a broker would on subscribe."""
    topic, payload = _foreign_export(spec)
    async_fire_mqtt_message(hass, topic, payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _enabled_rows(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return the entity ids of every enabled registry row with this unique id, whatever the platform."""
    return [
        entity.entity_id
        for entity in er.async_get(hass).entities.values()
        if entity.unique_id == device_id and entity.disabled_by is None
    ]


async def test_a_receiver_disables_the_duplicate_that_a_foreign_core_prefix_export_restores(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
) -> None:
    """
    The bench receiver of the 08-13 re-run: the export is off here, the device is a native mirror, a null tombstone.

    Another instance exports the device on the prefix core MQTT listens to. Core restores the enabled state of the
    removed row, and this instance, which does not export, must still end with one disabled duplicate (D-08 amended).
    """
    spec = make_spec(name="Foreign lamp")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)

    # Premises: no export here, a native mirror with its native row, the core MQTT device and a null tombstone
    assert not entry.options.get(CONF_DISCOVERY_EXPORT)
    assert _manager(entry).is_native(spec.device_id)
    native = _entity_id(hass, "switch", spec.device_id)
    assert native is not None
    # One synchronous step without an await: an enabled row on the MQTT device of the id is created and removed
    registry.async_remove(_mqtt_row(hass, "switch", spec.device_id, device=True))
    assert registry.deleted_entities[("switch", "mqtt", spec.device_id)].disabled_by is None
    assert registry.async_get_entity_id("switch", "mqtt", spec.device_id) is None
    assert _mqtt_device(hass, spec.device_id) is not None
    published = list(mqtt_mock.async_publish.call_args_list)

    await _receive_foreign_export(hass, spec)

    duplicates = [
        entity
        for entity in registry.entities.values()
        if entity.unique_id == spec.device_id and entity.platform == "mqtt"
    ]
    assert len(duplicates) == 1
    assert duplicates[0].disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get(native).disabled_by is None
    assert _enabled_rows(hass, spec.device_id) == [native]
    assert _publishes(mqtt_mock, discovery_topic(CORE_PREFIX, spec.device_id)) == []
    assert list(mqtt_mock.async_publish.call_args_list) == published
