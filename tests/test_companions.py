"""Companion device and mode select of a mirrored device of another instance (SYN-09, D-13, D-14, D-15)."""

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions.const import (
    DOMAIN,
    PRUNE_GRACE_SECONDS,
    STORE_APPROVALS,
    STORE_KEY,
    STORE_MIRRORS,
    STORE_SAVE_DELAY,
    STORE_VERSION,
)
from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.document import parse_document
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
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


# --- life cycle: removal, prune, rename (D-13, Phase 3 pitfall 10) -------------------------------------------------


async def _flush_store(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Fire the delayed store save; the frozen clock also moves the loop time the store compares against."""
    freezer.tick(timedelta(seconds=STORE_SAVE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_mirror_removal_removes_the_companion_and_its_mode(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """T-04-26: a tombstone removes the mirror, its companion device, its select and its stored mode."""
    spec = make_spec(on=ON_ACTIONS)
    other = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    await _deliver(hass, other.device_id, document_payload(other), retain=False)
    await _select_mode(hass, spec.device_id, "observe")
    await _select_mode(hass, other.device_id, "observe")
    entity_id = _mode_entity_id(hass, spec.device_id)
    assert entity_id is not None
    await _flush_store(hass, freezer)
    assert hass_storage[STORE_KEY]["data"]["device_modes"] == {spec.device_id: "observe", other.device_id: "observe"}

    await _deliver(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in _manager(entry).mirrors
    assert _companion(hass, entry, spec.device_id) is None
    assert _mode_entity_id(hass, spec.device_id) is None
    assert hass.states.get(entity_id) is None
    assert _manager(entry).device_mode(spec.device_id) == "run"
    await _flush_store(hass, freezer)
    assert hass_storage[STORE_KEY]["data"]["device_modes"] == {other.device_id: "observe"}
    assert _companion(hass, entry, other.device_id) is not None
    assert _mode_entity_id(hass, other.device_id) is not None


async def test_prune_removes_the_companion_too(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-10: the grace-window prune of a mirror whose owner is online removes the companion like a tombstone."""
    spec = make_spec(on=ON_ACTIONS)
    _seed_store(
        hass_storage,
        {STORE_MIRRORS: {spec.device_id: document_payload(spec)}, "device_modes": {spec.device_id: "observe"}},
    )
    entry = await _setup(hass, make_hub_entry())
    async_fire_mqtt_message(hass, availability_topic(BASE, FOREIGN_OWNER), "online", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _companion(hass, entry, spec.device_id) is not None
    assert spec.device_id in _manager(entry).mirrors

    freezer.tick(timedelta(seconds=PRUNE_GRACE_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert spec.device_id not in _manager(entry).mirrors
    assert _companion(hass, entry, spec.device_id) is None
    assert _mode_entity_id(hass, spec.device_id) is None
    assert _manager(entry).device_mode(spec.device_id) == "run"


async def test_removal_never_touches_the_mqtt_registry_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-04-25: with live discovery entities, removing the mirror removes the companion and nothing of core MQTT."""
    spec = make_spec(on=ON_ACTIONS, name="Foreign lamp")
    entry = await _setup(hass, make_hub_entry())
    discovery = discovery_topic("homeassistant", spec.device_id)
    payload = build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3")
    async_fire_mqtt_message(hass, discovery, json.dumps(payload), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)

    (mqtt_entry,) = hass.config_entries.async_entries("mqtt")
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    mqtt_device = device_registry.async_get_device_by_identifier(
        ("mqtt", f"{DOMAIN}_{spec.device_id}"), mqtt_entry.entry_id
    )
    assert mqtt_device is not None
    mqtt_entities = er.async_entries_for_device(entity_registry, mqtt_device.id)
    assert mqtt_entities
    assert all(hass.states.get(entity.entity_id) is not None for entity in mqtt_entities)
    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.id != mqtt_device.id
    mqtt_mock.async_publish.reset_mock()

    await _deliver(hass, spec.device_id, "", retain=False)

    assert _companion(hass, entry, spec.device_id) is None
    assert device_registry.async_get(mqtt_device.id) == mqtt_device
    for entity in mqtt_entities:
        assert entity_registry.async_get(entity.entity_id) == entity
        assert hass.states.get(entity.entity_id) is not None
    assert [call for call in mqtt_mock.async_publish.call_args_list if call.args[0] == discovery] == []


async def test_mirror_rename_updates_the_companion(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-13: a new document of the pinned owner with another name renames the companion device."""
    spec = make_spec(on=ON_ACTIONS, name="Lamp")
    renamed = make_spec(device_id=spec.device_id, on=ON_ACTIONS, name="Floor lamp")
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, rev=1), retain=False)
    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.name == "Lamp"

    await _deliver(hass, spec.device_id, document_payload(renamed, rev=2), retain=False)

    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.name == "Floor lamp"


async def test_mirror_rename_keeps_a_name_the_user_chose(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-13: a name the user gave the companion device stays when the owner renames the device."""
    spec = make_spec(on=ON_ACTIONS, name="Lamp")
    renamed = make_spec(device_id=spec.device_id, on=ON_ACTIONS, name="Floor lamp")
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, rev=1), retain=False)
    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    dr.async_get(hass).async_update_device(companion.id, name_by_user="My lamp")

    await _deliver(hass, spec.device_id, document_payload(renamed, rev=2), retain=False)

    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.name_by_user == "My lamp"
    assert companion.name == "Lamp"


async def test_remove_companion_is_idempotent(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """The helper does nothing for an unknown id and for a second call, and raises nothing."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    manager = _manager(entry)
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    assert _companion(hass, entry, spec.device_id) is not None

    manager._remove_companion("no-such-device")
    manager._remove_companion(spec.device_id)
    manager._remove_companion(spec.device_id)

    assert _companion(hass, entry, spec.device_id) is None
