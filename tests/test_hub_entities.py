"""The hub device, its roster sensor and the resync button with a real entry setup on the MQTT mock (OPS-03)."""

import json
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions.const import DOMAIN
from custom_components.mqtt_actions.topics import heartbeat_topic

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
