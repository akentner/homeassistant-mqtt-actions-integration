"""Companion device and mode select of a mirrored device of another instance (SYN-09, D-13, D-14, D-15)."""

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_mock_service,
)

from custom_components.mqtt_actions.const import DOMAIN, STORE_APPROVALS, STORE_KEY, STORE_MIRRORS, STORE_VERSION
from custom_components.mqtt_actions.document import parse_document
from custom_components.mqtt_actions.topics import config_topic, state_topic
from tests.documents import document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on", "target": {"entity_id": "light.lamp"}}]
OFF_ACTIONS = [{"action": "test.off"}]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


async def _deliver(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = True) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = False) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _approve(entry: MockConfigEntry, device_id: str) -> bool:
    """Approve exactly the hash the mirror currently has, like the dialog does after the user read it."""
    manager = _manager(entry)
    info = manager.mirrors[device_id].mirror
    assert info is not None
    return await manager.async_approve(device_id, info.actions_hash)


def _mode_entity_id(hass: HomeAssistant, device_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{device_id}_mode")


def _companion(hass: HomeAssistant, entry: MockConfigEntry, device_id: str) -> dr.DeviceEntry | None:
    return dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)


async def _select_mode(hass: HomeAssistant, device_id: str, mode: str) -> None:
    """Set the mode through the select service, the way a user does."""
    entity_id = _mode_entity_id(hass, device_id)
    assert entity_id is not None
    await hass.services.async_call("select", "select_option", {"entity_id": entity_id, "option": mode}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _seed_store(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {"version": STORE_VERSION, "minor_version": 1, "key": STORE_KEY, "data": data}


async def test_mirror_has_a_companion_device_and_select(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-13: a foreign device shows up as a companion device of the entry, without a subentry, with its mode select."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())

    await _deliver(hass, spec.device_id, document_payload(spec))

    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.config_entry_id == entry.entry_id
    assert companion.config_subentry_id is None
    assert companion.manufacturer == "MQTT Actions"
    assert companion.model == "Switch device (mirror)"
    assert companion.name == "Foreign lamp"
    entity_id = _mode_entity_id(hass, spec.device_id)
    assert entity_id is not None
    registered = er.async_get(hass).async_get(entity_id)
    assert registered is not None
    assert registered.device_id == companion.id
    assert registered.config_subentry_id is None
    assert registered.entity_category is EntityCategory.CONFIG
    assert hass.states.get(entity_id).state == "run"
    assert hass.states.get(entity_id).attributes["options"] == ["run", "observe", "disabled"]


async def test_observe_stops_an_approved_mirror(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """D-14: an approved mirror in observe mode runs nothing and follows the baseline; run runs the next edge once."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "OFF", retain=True)
    assert await _approve(entry, spec.device_id) is True

    await _select_mode(hass, spec.device_id, "observe")
    await _state(hass, spec.device_id, "ON")

    assert on_calls == []
    assert off_calls == []
    assert _manager(entry).mirrors[spec.device_id].tracker.last_acted == "ON"

    await _select_mode(hass, spec.device_id, "run")
    await _state(hass, spec.device_id, "OFF")

    assert len(off_calls) == 1
    assert on_calls == []


async def test_mirror_mode_survives_restart(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-14, D-15: the mode is saved under the mirror's id and applies again after unload and setup."""
    on_calls = async_mock_service(hass, "test", "on")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "OFF", retain=True)
    assert await _approve(entry, spec.device_id) is True
    await _select_mode(hass, spec.device_id, "observe")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass_storage[STORE_KEY]["data"]["device_modes"] == {spec.device_id: "observe"}

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert spec.device_id in _manager(entry).mirrors
    entity_id = _mode_entity_id(hass, spec.device_id)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "observe"
    assert _manager(entry).effective_mode(spec.device_id) == "observe"

    await _state(hass, spec.device_id, "OFF", retain=True)
    await _state(hass, spec.device_id, "ON")
    assert on_calls == []


async def test_cached_mirror_restored_at_start_has_its_companion(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-15: a mirror restored from the Store gets its companion device and select without any message."""
    spec = make_spec(name="Cached lamp", on=ON_ACTIONS)
    payload = document_payload(spec)
    _seed_store(
        hass_storage,
        {
            STORE_MIRRORS: {spec.device_id: payload},
            STORE_APPROVALS: {spec.device_id: parse_document(spec.device_id, payload).actions_hash},
            "device_modes": {spec.device_id: "disabled"},
        },
    )

    entry = await _setup(hass, make_hub_entry())

    assert spec.device_id in _manager(entry).mirrors
    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.config_subentry_id is None
    assert companion.name == "Cached lamp"
    entity_id = _mode_entity_id(hass, spec.device_id)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "disabled"


async def test_two_mirrors_have_separate_companions(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-13: each mirror has its own device and select, and a mode change of one leaves the other at run."""
    first = make_spec(name="First", on=ON_ACTIONS)
    second = make_spec(name="Second", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, first.device_id, document_payload(first))
    await _deliver(hass, second.device_id, document_payload(second))

    first_companion = _companion(hass, entry, first.device_id)
    second_companion = _companion(hass, entry, second.device_id)
    assert first_companion is not None
    assert second_companion is not None
    assert first_companion.id != second_companion.id

    await _select_mode(hass, first.device_id, "observe")

    first_entity = _mode_entity_id(hass, first.device_id)
    second_entity = _mode_entity_id(hass, second.device_id)
    assert first_entity is not None
    assert second_entity is not None
    assert first_entity != second_entity
    assert hass.states.get(first_entity).state == "observe"
    assert hass.states.get(second_entity).state == "run"
    assert _manager(entry).device_mode(second.device_id) == "run"
