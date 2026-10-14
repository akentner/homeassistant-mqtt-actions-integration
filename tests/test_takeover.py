"""
Characterization of the Home Assistant core behavior the native-entity takeover depends on (D-05, MIG-01).

The second half of the file tests the takeover module itself against the same real core MQTT discovery.

These tests exercise real core MQTT discovery and the registries of the installed Home Assistant, not new code of this
integration. They are green by design; their value is that a core bump which changes one of the ordering rules fails
here before it can corrupt a user's registry. The rules: the migrate payload comes before the platform move, entities
move before their device, and the plain empty discovery payload comes last. The public helpers are reused by the
takeover module tests of the later plans.
"""

import asyncio
import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, NamedTuple

import pytest
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import entity_sources
from pytest_homeassistant_custom_component.common import (
    MockPlatform,
    async_fire_mqtt_message,
    mock_platform,
)

from custom_components.mqtt_actions.const import CONF_DEVICE_ID, CONF_INSTANCE_ID, DOMAIN
from custom_components.mqtt_actions.discovery import DiscoveryContent, build_discovery
from custom_components.mqtt_actions.takeover import (
    TakeoverStatus,
    TakeoverTarget,
    async_take_over,
    disable_duplicates,
    is_legacy_entity,
    legacy_device,
    remove_replay_twins,
)
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

PREFIX = "homeassistant"
MIGRATE_PAYLOAD = json.dumps({"migrate_discovery": True})
CLEAR_PAYLOAD = ""


class LegacyDevice(NamedTuple):
    """A v0.1.0-style device whose discovery core MQTT consumed: the entry, its device id, topic and payload."""

    entry: MockConfigEntry
    device_id: str
    topic: str
    payload: str


async def setup_legacy_device(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    name: str = "Lamp",
) -> LegacyDevice:
    """
    Set up a hub entry with one switch device exactly as the current code behaves and let core MQTT discover it.

    The manager publishes the device-based discovery payload; the mocked client does not loop publishes back, so the
    payload is fed to core as the retained replay a real broker would deliver. Core then creates the real discovered
    switch and the two test buttons.
    """
    sub = make_switch_subentry(name)
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    device_id = sub["data"][CONF_DEVICE_ID]
    topic = discovery_topic(PREFIX, device_id)
    payload = _published_payload(mqtt_mock, topic)
    async_fire_mqtt_message(hass, availability_topic(entry.data["base_topic"], entry.data[CONF_INSTANCE_ID]), "online")
    async_fire_mqtt_message(hass, topic, payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    return LegacyDevice(entry, device_id, topic, payload)


def _published_payload(mqtt_mock: Any, topic: str) -> str:
    """Return the last payload the manager published on a topic, read from the mocked MQTT client."""
    payloads = [call.args[1] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]
    assert payloads, f"nothing was published on {topic}"
    return payloads[-1]


def _mqtt_entry_id(hass: HomeAssistant) -> str:
    return hass.config_entries.async_entries("mqtt")[0].entry_id


def customize_mqtt_device(hass: HomeAssistant, device_id: str, *, area_id: str, name_by_user: str) -> dr.DeviceEntry:
    """Set area and user name on the core MQTT device of a legacy device and return the updated device entry."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), _mqtt_entry_id(hass))
    assert device is not None
    updated = device_registry.async_update_device(device.id, area_id=area_id, name_by_user=name_by_user)
    assert updated is not None
    return updated


def legacy_entity_ids(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return the entity ids of the registry entries core MQTT created for a device (switch and test buttons)."""
    return [
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == "mqtt"
        and (entry.unique_id == device_id or entry.unique_id.startswith(f"{device_id}_test_"))
    ]


async def _deliver(hass: HomeAssistant, topic: str, payload: str) -> None:
    """Deliver a live (not retained) message: core skips a second retained message on a topic it already saw."""
    async_fire_mqtt_message(hass, topic, payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


def _subentry(entry: MockConfigEntry) -> ConfigSubentry:
    return next(iter(entry.subentries.values()))


def _mqtt_device(hass: HomeAssistant, device_id: str) -> dr.DeviceEntry:
    device = dr.async_get(hass).async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), _mqtt_entry_id(hass))
    assert device is not None
    return device


def _move_entities(hass: HomeAssistant, legacy: LegacyDevice, entity_ids: list[str]) -> None:
    """Move registry entries to this integration under the subentry of the device (step 3 of the fixed order)."""
    entity_registry = er.async_get(hass)
    for entity_id in entity_ids:
        entity_registry.async_update_entity_platform(
            entity_id,
            DOMAIN,
            new_config_entry_id=legacy.entry.entry_id,
            new_config_subentry_id=_subentry(legacy.entry).subentry_id,
        )


def _discovery_clears(mqtt_mock: Any, topic: str) -> list[Any]:
    """Return the empty payloads published on the discovery topic."""
    return [call for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic and call.args[1] == ""]


def _falsy_publishes(mqtt_mock: Any, topic: str) -> list[Any]:
    """Return every clear on the topic: core MQTT clears with None, which `_discovery_clears` does not see."""
    return [call for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic and not call.args[1]]


class _NativeSwitch(SwitchEntity):
    """The native switch of the later plans, reduced to its identity: unique id and device identifier."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device_id: str) -> None:
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})
        self._attr_is_on = False


async def _forward_native_switch(hass: HomeAssistant, legacy: LegacyDevice) -> None:
    """Register a mock switch platform for this domain and forward it to the already loaded entry."""

    async def _async_setup_entry(_hass: HomeAssistant, _entry: Any, async_add_entities: Any) -> None:
        async_add_entities([_NativeSwitch(legacy.device_id)], config_subentry_id=_subentry(legacy.entry).subentry_id)

    # The entry forwards the real switch platform at setup (plan 05-03); it is unloaded so the mock stands in for it
    assert await hass.config_entries.async_unload_platforms(legacy.entry, [Platform.SWITCH])
    mock_platform(hass, f"{DOMAIN}.switch", MockPlatform(async_setup_entry=_async_setup_entry))
    await hass.config_entries.async_forward_entry_setups(legacy.entry, [Platform.SWITCH])
    await hass.async_block_till_done(wait_background_tasks=True)


# --- the fixed takeover order and its identity guarantee (tracer) -------------------------------------------------


async def _run_takeover(hass: HomeAssistant, legacy: LegacyDevice, legacy_ids: list[str], mode_entity_id: str) -> None:
    """Run the fixed order: migrate, entities, device, merge the companion, plain clear, then the native switch."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    mqtt_device = _mqtt_device(hass, legacy.device_id)
    companion = device_registry.async_get_device_by_identifier((DOMAIN, legacy.device_id), legacy.entry.entry_id)
    assert companion is not None
    assert companion.id != mqtt_device.id
    sub_id = _subentry(legacy.entry).subentry_id

    # (2) migrate first: core unloads the discovered entities and keeps their registry entries
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    # (3) entities move to this integration, still attached to the core MQTT device
    _move_entities(hass, legacy, legacy_ids)
    # (4) the device follows, under the entry and the subentry
    device_registry.async_update_device(
        mqtt_device.id, new_config_entry_id=legacy.entry.entry_id, new_config_subentry_id=sub_id
    )
    # (5) merge the companion: the mode select joins the device, the companion goes, the identifier becomes ours
    entity_registry.async_update_entity(mode_entity_id, device_id=mqtt_device.id)
    device_registry.async_remove_device(companion.id)
    device_registry.async_update_device(mqtt_device.id, new_identifiers={(DOMAIN, legacy.device_id)})
    # (6) the plain clear is last and harmless now
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    # (7) the native switch registers under the same unique id
    await _forward_native_switch(hass, legacy)


async def test_full_takeover_sequence_keeps_identity(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Migrate, entities, device, companion merge, plain clear, native switch: nothing of the identity moves."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_id = legacy.device_id
    customize_mqtt_device(hass, device_id, area_id="kitchen", name_by_user="Stehlampe")
    mqtt_device = _mqtt_device(hass, device_id)

    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", device_id)
    assert switch_id is not None
    switch_before = entity_registry.async_get(switch_id)
    mode_entity_id = entity_registry.async_get_entity_id("select", DOMAIN, f"{device_id}_mode")
    assert mode_entity_id is not None
    mode_before = entity_registry.async_get(mode_entity_id)
    assert switch_before is not None
    assert mode_before is not None
    legacy_ids = legacy_entity_ids(hass, device_id)
    assert len(legacy_ids) == 3  # the switch and the two test buttons

    await _run_takeover(hass, legacy, legacy_ids, mode_entity_id)

    sub_id = _subentry(legacy.entry).subentry_id
    switch_after = entity_registry.async_get(switch_id)
    assert switch_after is not None
    assert switch_after.id == switch_before.id
    assert switch_after.platform == DOMAIN
    assert entity_registry.async_get_entity_id("switch", DOMAIN, device_id) == switch_id
    assert hass.states.get(switch_id) is not None
    mode_after = entity_registry.async_get(mode_entity_id)
    assert mode_after is not None
    assert mode_after.id == mode_before.id
    assert mode_after.device_id == mqtt_device.id
    for entity_id in legacy_ids:
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.platform, moved.device_id) == (DOMAIN, mqtt_device.id)
        assert (moved.config_entry_id, moved.config_subentry_id) == (legacy.entry.entry_id, sub_id)

    devices = [
        device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), legacy.entry.entry_id)
        if (DOMAIN, device_id) in device.identifiers
    ]
    assert [device.id for device in devices] == [mqtt_device.id]
    assert (devices[0].area_id, devices[0].name_by_user) == ("kitchen", "Stehlampe")
    assert devices[0].config_subentry_id == sub_id
    assert ("mqtt", f"{DOMAIN}_{device_id}") not in devices[0].identifiers
    assert _discovery_clears(mqtt_mock, legacy.topic) == []


# --- the four edges of core behavior the order protects against --------------------------------------------------


async def test_plain_clear_on_a_loaded_entity_deletes_the_registry_entry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Negative control: without the migrate payload an empty discovery payload deletes the registry entries."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", legacy.device_id)
    assert switch_id is not None
    assert len(legacy_entity_ids(hass, legacy.device_id)) == 3

    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)

    assert entity_registry.async_get(switch_id) is None
    assert legacy_entity_ids(hass, legacy.device_id) == []
    assert ("switch", "mqtt", legacy.device_id) in entity_registry.deleted_entities


async def test_migrate_then_clear_keeps_the_registry_entry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The migrate payload followed by the empty payload unloads the entities and leaves every registry entry."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    legacy_ids = legacy_entity_ids(hass, legacy.device_id)
    assert len(legacy_ids) == 3

    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)

    assert sorted(legacy_entity_ids(hass, legacy.device_id)) == sorted(legacy_ids)
    for entity_id in legacy_ids:
        registered = entity_registry.async_get(entity_id)
        assert registered is not None
        assert registered.platform == "mqtt"
        assert hass.states.get(entity_id) is None or hass.states.get(entity_id).attributes.get("restored")
    assert ("switch", "mqtt", legacy.device_id) not in entity_registry.deleted_entities


async def test_loaded_entity_refuses_the_platform_move(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A loaded legacy entity cannot be moved to another platform: the migrate payload has to unload it first."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    switch_id = er.async_get(hass).async_get_entity_id("switch", "mqtt", legacy.device_id)
    assert switch_id is not None

    with pytest.raises(ValueError, match="haven't been loaded"):
        _move_entities(hass, legacy, [switch_id])


async def test_moving_the_device_first_removes_its_entities(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Moving the device before its entities removes the switch and the buttons, the mode select is not affected."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    mqtt_device = _mqtt_device(hass, legacy.device_id)
    assert len(legacy_entity_ids(hass, legacy.device_id)) == 3
    mode_entity_id = entity_registry.async_get_entity_id("select", DOMAIN, f"{legacy.device_id}_mode")
    assert mode_entity_id is not None

    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    dr.async_get(hass).async_update_device(
        mqtt_device.id,
        new_config_entry_id=legacy.entry.entry_id,
        new_config_subentry_id=_subentry(legacy.entry).subentry_id,
    )

    assert legacy_entity_ids(hass, legacy.device_id) == []
    assert entity_registry.async_get_entity_id("switch", "mqtt", legacy.device_id) is None
    assert entity_registry.async_get(mode_entity_id) is not None


async def test_core_does_not_guard_a_duplicate_unique_id(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Core lets a platform move create a second entry with the same key, so the takeover module must guard it."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", legacy.device_id)
    assert switch_id is not None
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    entity_registry.async_get_or_create(
        "switch", DOMAIN, legacy.device_id, config_entry=legacy.entry, suggested_object_id="lamp_native"
    )

    _move_entities(hass, legacy, [switch_id])  # raises nothing

    same_key = [
        entry
        for entry in entity_registry.entities.values()
        if (entry.domain, entry.platform, entry.unique_id) == ("switch", DOMAIN, legacy.device_id)
    ]
    assert len(same_key) == 2


async def test_user_disabled_entity_survives_the_migrate(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A switch the user disabled keeps its registry entry through migrate and through migrate plus clear."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", legacy.device_id)
    assert switch_id is not None
    entity_registry.async_update_entity(switch_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done(wait_background_tasks=True)

    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    after_migrate = entity_registry.async_get(switch_id)
    assert after_migrate is not None
    assert after_migrate.disabled_by is er.RegistryEntryDisabler.USER

    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    after_clear = entity_registry.async_get(switch_id)
    assert after_clear is not None
    assert after_clear.platform == "mqtt"
    assert after_clear.disabled_by is er.RegistryEntryDisabler.USER


# --- the takeover module: tracer (D-05, D-07, D-12) --------------------------------------------------------------


def _moved_entity_ids(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return the entity ids of the entries of this integration that carry the shape of a legacy entry."""
    return [
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == DOMAIN
        and entry.domain in {"switch", "select", "button"}
        and (entry.unique_id == device_id or entry.unique_id.startswith(f"{device_id}_test_"))
    ]


def _target(legacy: LegacyDevice) -> TakeoverTarget:
    return TakeoverTarget(device_id=legacy.device_id, subentry_id=_subentry(legacy.entry).subentry_id)


def _start_take_over(
    hass: HomeAssistant, legacy: LegacyDevice, *, unload_timeout: float = 5.0, retry_interval: float = 0.05
) -> asyncio.Task[TakeoverStatus]:
    """
    Start the takeover as a plain loop task.

    A task created through hass would be awaited by every `async_block_till_done` of the test helpers, which would
    make the migrate delivery wait for the very takeover it is supposed to release.
    """
    return asyncio.get_running_loop().create_task(
        async_take_over(
            hass,
            legacy.entry,
            _target(legacy),
            mqtt_entry_id=_mqtt_entry_id(hass),
            unload_timeout=unload_timeout,
            retry_interval=retry_interval,
        )
    )


def _mqtt_entry_state(hass: HomeAssistant) -> tuple[list[tuple[str, str, str | None]], list[tuple[str, str]]]:
    """Return a comparable snapshot of every entity (id, platform, device) and device (id, entry) of the registries."""
    entities = sorted(
        (entry.entity_id, entry.platform, entry.device_id) for entry in er.async_get(hass).entities.values()
    )
    device_registry = dr.async_get(hass)
    devices = sorted(
        (device.id, device.config_entry_id)
        for config_entry in hass.config_entries.async_entries()
        for device in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    )
    return entities, devices


async def test_take_over_moves_a_loaded_owned_switch_after_the_migrate(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Tracer: the module waits for the live migrate, then moves entities, device and companion with every identity."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_id = legacy.device_id
    customize_mqtt_device(hass, device_id, area_id="kitchen", name_by_user="Stehlampe")
    mqtt_device = _mqtt_device(hass, device_id)
    legacy_ids = legacy_entity_ids(hass, device_id)
    assert len(legacy_ids) == 3
    mode_id = entity_registry.async_get_entity_id("select", DOMAIN, f"{device_id}_mode")
    assert mode_id is not None
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in [*legacy_ids, mode_id]}
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", device_id)
    assert switch_id is not None

    task = _start_take_over(hass, legacy)
    await asyncio.sleep(0.2)
    assert not task.done()  # the entities are loaded: nothing may move yet

    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    assert await asyncio.wait_for(task, timeout=5) is TakeoverStatus.DONE

    sub_id = _subentry(legacy.entry).subentry_id
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert moved.id == old.id
        assert moved.platform == DOMAIN
        assert moved.device_id == mqtt_device.id
        assert (moved.config_entry_id, moved.config_subentry_id) == (legacy.entry.entry_id, sub_id)
    devices = [
        device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), legacy.entry.entry_id)
        if (DOMAIN, device_id) in device.identifiers
    ]
    assert [device.id for device in devices] == [mqtt_device.id]
    assert (devices[0].area_id, devices[0].name_by_user) == ("kitchen", "Stehlampe")
    assert (devices[0].config_entry_id, devices[0].config_subentry_id) == (legacy.entry.entry_id, sub_id)
    assert ("mqtt", f"{DOMAIN}_{device_id}") not in devices[0].identifiers

    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    await _forward_native_switch(hass, legacy)
    assert entity_registry.async_get_entity_id("switch", DOMAIN, device_id) == switch_id
    assert hass.states.get(switch_id) is not None


async def test_take_over_does_nothing_without_a_legacy_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A device id without a core MQTT device is NOTHING and changes no registry entry."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    snapshot = _mqtt_entry_state(hass)

    status = await async_take_over(
        hass,
        legacy.entry,
        TakeoverTarget(device_id="no-such-device", subentry_id=None),
        mqtt_entry_id=_mqtt_entry_id(hass),
        unload_timeout=0.1,
        retry_interval=0.05,
    )

    assert status is TakeoverStatus.NOTHING
    assert _mqtt_entry_state(hass) == snapshot


async def test_take_over_defers_and_moves_nothing_while_an_entity_stays_loaded(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Without a migrate payload the wait times out: DEFERRED, every legacy entry and the device stay where they are."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    legacy_ids = legacy_entity_ids(hass, legacy.device_id)
    assert len(legacy_ids) == 3
    snapshot = _mqtt_entry_state(hass)

    status = await _start_take_over(hass, legacy, unload_timeout=0.3, retry_interval=0.05)

    assert status is TakeoverStatus.DEFERRED
    entity_registry = er.async_get(hass)
    for entity_id in legacy_ids:
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert (entry.platform, entry.config_entry_id) == ("mqtt", _mqtt_entry_id(hass))
    assert _mqtt_device(hass, legacy.device_id).config_entry_id == _mqtt_entry_id(hass)
    assert _mqtt_entry_state(hass) == snapshot


# --- the takeover module: hardening (D-05, D-07) -----------------------------------------------------------------

BASE = "mqtt_actions"


def _take_over_now(hass: HomeAssistant, legacy: LegacyDevice) -> Any:
    """Return the awaitable of a takeover that must not need to wait: a short timeout turns a wait into DEFERRED."""
    return async_take_over(
        hass,
        legacy.entry,
        _target(legacy),
        mqtt_entry_id=_mqtt_entry_id(hass),
        unload_timeout=0.1,
        retry_interval=0.02,
    )


async def test_a_foreign_mqtt_entity_with_the_same_unique_id_is_left_alone(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-5-01: an unrelated MQTT entity that carries this device's id as unique id is not this device's entity."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    foreign_payload = {
        "device": {"identifiers": ["somebody_else"], "name": "Somebody else"},
        "origin": {"name": "Somebody else"},
        "components": {
            "other": {
                "platform": "button",
                "unique_id": legacy.device_id,
                "name": "Foreign button",
                "command_topic": "somebody/else/set",
            }
        },
    }
    async_fire_mqtt_message(hass, discovery_topic(PREFIX, "somebody_else"), json.dumps(foreign_payload), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    foreign_id = entity_registry.async_get_entity_id("button", "mqtt", legacy.device_id)
    assert foreign_id is not None
    foreign_before = entity_registry.async_get(foreign_id)
    assert foreign_before is not None
    assert foreign_before.device_id != _mqtt_device(hass, legacy.device_id).id
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE

    foreign_after = entity_registry.async_get(foreign_id)
    assert foreign_after is not None
    assert foreign_after.platform == "mqtt"
    assert foreign_after.device_id == foreign_before.device_id
    assert foreign_after.entity_id == foreign_id
    assert foreign_after.config_entry_id == _mqtt_entry_id(hass)
    assert entity_registry.async_get_entity_id("switch", DOMAIN, legacy.device_id) is not None


async def test_a_ghost_is_taken_over_without_any_broadcast(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A legacy device that is unloaded already needs no wait: the call returns DONE at once."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)

    assert await asyncio.wait_for(_take_over_now(hass, legacy), timeout=1) is TakeoverStatus.DONE
    assert er.async_get(hass).async_get_entity_id("switch", DOMAIN, legacy.device_id) is not None


async def test_a_user_disabled_legacy_entry_is_moved_and_stays_disabled(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A disabled entry is not loaded and still part of the device: it moves and keeps the user's choice."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", legacy.device_id)
    assert switch_id is not None
    entity_registry.async_update_entity(switch_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE

    moved = entity_registry.async_get(switch_id)
    assert moved is not None
    assert moved.platform == DOMAIN
    assert moved.disabled_by is er.RegistryEntryDisabler.USER


async def _legacy_with_native_twins(
    hass: HomeAssistant, legacy: LegacyDevice
) -> tuple[dict[tuple[str, str], er.RegistryEntry], dict[str, er.RegistryEntry], dr.DeviceEntry, dr.DeviceEntry]:
    """Create an auto-generated native twin for every legacy entry; return twins, legacy entries and both devices."""
    entity_registry = er.async_get(hass)
    device_id = legacy.device_id
    mqtt_device = _mqtt_device(hass, device_id)
    native_device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), legacy.entry.entry_id)
    assert native_device is not None
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_entity_ids(hass, device_id)}
    keys = [(entry.domain, entry.unique_id) for entry in before.values() if entry]
    assert len(keys) == 3
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    natives = {
        (domain, unique_id): entity_registry.async_get_or_create(
            domain,
            DOMAIN,
            unique_id,
            config_entry=legacy.entry,
            config_subentry_id=_subentry(legacy.entry).subentry_id,
            device_id=native_device.id,
            suggested_object_id=f"native_{unique_id[-8:]}",
        )
        for domain, unique_id in keys
    }
    return natives, before, mqtt_device, native_device


async def test_an_existing_native_twin_never_replaces_the_legacy_identity(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    T-5-09, WR-04: with auto-generated native twins present the older legacy entries keep entity id and registry id.

    The twins are newer and carry no customization, so they are deleted and the legacy entries move; the emptied
    native device is merged into the legacy device.
    """
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_id = legacy.device_id
    natives, before, mqtt_device, native_device = await _legacy_with_native_twins(hass, legacy)

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE

    for (domain, unique_id), twin in natives.items():
        same_key = [
            entry
            for entry in entity_registry.entities.values()
            if (entry.domain, entry.platform, entry.unique_id) == (domain, DOMAIN, unique_id)
        ]
        original = next(old for old in before.values() if (old.domain, old.unique_id) == (domain, unique_id))
        assert [(entry.id, entry.entity_id, entry.device_id) for entry in same_key] == [
            (original.id, original.entity_id, mqtt_device.id)
        ]
        assert entity_registry.async_get(twin.entity_id) is None
    assert legacy_entity_ids(hass, device_id) == []
    taken = device_registry.async_get(mqtt_device.id)
    assert taken is not None
    assert taken.identifiers == {(DOMAIN, device_id)}
    assert device_registry.async_get(native_device.id) is None


async def test_a_customized_native_twin_is_kept_over_an_untouched_legacy_entry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """WR-04: when only the native twin carries the user's choices it is the identity to keep; the legacy one goes."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_id = legacy.device_id
    natives, _before, mqtt_device, native_device = await _legacy_with_native_twins(hass, legacy)
    for twin in natives.values():
        entity_registry.async_update_entity(twin.entity_id, name="My own name")

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE

    for (domain, unique_id), twin in natives.items():
        same_key = [
            entry
            for entry in entity_registry.entities.values()
            if (entry.domain, entry.platform, entry.unique_id) == (domain, DOMAIN, unique_id)
        ]
        assert [(entry.id, entry.entity_id, entry.name, entry.device_id) for entry in same_key] == [
            (twin.id, twin.entity_id, "My own name", native_device.id)
        ]
    assert legacy_entity_ids(hass, device_id) == []
    assert device_registry.async_get(mqtt_device.id) is None
    assert device_registry.async_get(native_device.id) is not None


async def test_take_over_disables_a_legacy_duplicate_before_it_removes_it_so_no_enabled_tombstone_stays(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    WR-01: a legacy entry that loses to its twin leaves the registry as a disabled record and without a clear.

    The registry restores the state of a deleted record with the same platform and unique id, so an enabled record
    would bring the row back enabled the next time a replay or another instance's export names the unique id.
    """
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    assert all(entry.disabled_by is None for entry in before.values())
    for twin in natives.values():
        entity_registry.async_update_entity(twin.entity_id, name="My own name")
    mqtt_mock.async_publish.reset_mock()

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE
    await hass.async_block_till_done(wait_background_tasks=True)

    assert legacy_entity_ids(hass, legacy.device_id) == []
    records = {
        record.entity_id: record.disabled_by
        for (_domain, platform, unique_id), record in entity_registry.deleted_entities.items()
        if platform == "mqtt" and unique_id.startswith(legacy.device_id)
    }
    assert records == dict.fromkeys(before, er.RegistryEntryDisabler.INTEGRATION)
    assert _falsy_publishes(mqtt_mock, legacy.topic) == []


async def _rediscover_disabled(hass: HomeAssistant, legacy: LegacyDevice, entity_ids: list[str]) -> None:
    """
    Disable rows and let core MQTT discover them again, the state an export or a restart leaves them in.

    Core aborts the add of a disabled row and keeps a registry hook that clears the retained topic once the row is
    removed from the registry.
    """
    entity_registry = er.async_get(hass)
    for entity_id in entity_ids:
        entity_registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver(hass, legacy.topic, legacy.payload)
    assert not set(entity_ids) & set(entity_sources(hass))


async def test_take_over_leaves_a_disabled_legacy_duplicate_in_place_so_core_clears_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    CR-01: a legacy row that core MQTT discovered while it was disabled is never removed, even when its twin wins.

    Removing it would make core clear the retained topic, which for a mirror is the topic of the other instance's
    export. The disabled row already restores as disabled, so it stays where it is.
    """
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", legacy.device_id)
    assert switch_id is not None
    await _rediscover_disabled(hass, legacy, [switch_id])
    natives, _before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    entity_registry.async_update_entity(natives[("switch", legacy.device_id)].entity_id, name="My own name")
    mqtt_mock.async_publish.reset_mock()

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    left = entity_registry.async_get(switch_id)
    assert left is not None
    assert (left.platform, left.disabled_by) == ("mqtt", er.RegistryEntryDisabler.INTEGRATION)


async def test_a_select_device_moves_its_select_and_option_buttons(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """The identity filter covers the select and the option buttons of a Select device the same way."""

    def _select_subentry(name: str) -> Any:
        return make_select_subentry(name, [("low", "Low", []), ("high", "High", [])])

    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, _select_subentry, name="Fan")
    entity_registry = er.async_get(hass)
    device_id = legacy.device_id
    legacy_ids = legacy_entity_ids(hass, device_id)
    assert len(legacy_ids) == 3  # the select and one test button per option
    assert entity_registry.async_get_entity_id("select", "mqtt", device_id) is not None
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    mqtt_device = _mqtt_device(hass, device_id)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE

    sub_id = _subentry(legacy.entry).subentry_id
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform, moved.device_id) == (old.id, DOMAIN, mqtt_device.id)
        assert (moved.config_entry_id, moved.config_subentry_id) == (legacy.entry.entry_id, sub_id)
    assert entity_registry.async_get_entity_id("select", DOMAIN, device_id) is not None


async def test_a_mirror_moves_directly_under_the_entry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Assumption A3: a mirror has no subentry, its legacy entities and device end up directly under the entry."""
    spec = make_spec(name="Foreign lamp")
    entry = make_hub_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    topic = discovery_topic(PREFIX, spec.device_id)
    discovery = build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3")
    async_fire_mqtt_message(hass, topic, json.dumps(discovery), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), document_payload(spec), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    entity_registry = er.async_get(hass)
    legacy_ids = legacy_entity_ids(hass, spec.device_id)
    assert len(legacy_ids) == 3
    mqtt_device = _mqtt_device(hass, spec.device_id)
    await _deliver(hass, topic, MIGRATE_PAYLOAD)

    status = await async_take_over(
        hass,
        entry,
        TakeoverTarget(device_id=spec.device_id, subentry_id=None),
        mqtt_entry_id=_mqtt_entry_id(hass),
        unload_timeout=0.1,
        retry_interval=0.02,
    )

    assert status is TakeoverStatus.DONE
    for entity_id in legacy_ids:
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.platform, moved.config_entry_id, moved.config_subentry_id) == (DOMAIN, entry.entry_id, None)
    device = dr.async_get(hass).async_get(mqtt_device.id)
    assert device is not None
    assert (device.config_entry_id, device.config_subentry_id) == (entry.entry_id, None)
    assert device.identifiers == {(DOMAIN, spec.device_id)}


async def test_a_late_replay_duplicate_is_cleaned_at_the_next_call(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Pitfall 5: a discovery replay after the takeover recreates a legacy twin; the next call removes only that."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_id = legacy.device_id
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    taken = {entity_id: entity_registry.async_get(entity_id) for entity_id in _moved_entity_ids(hass, device_id)}
    assert len(taken) == 3
    taken_device = device_registry.async_get_device_by_identifier((DOMAIN, device_id), legacy.entry.entry_id)
    assert taken_device is not None

    await _deliver(hass, legacy.topic, legacy.payload)  # the late replay: live discovery creates new legacy twins
    replayed = legacy_entity_ids(hass, device_id)
    assert len(replayed) == 3
    assert not set(replayed) & set(taken)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE

    assert legacy_entity_ids(hass, device_id) == []
    for entity_id in replayed:
        assert entity_registry.async_get(entity_id) is None
    for entity_id, old in taken.items():
        assert entity_registry.async_get(entity_id) == old
    assert device_registry.async_get(taken_device.id) is not None
    assert (
        device_registry.async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), _mqtt_entry_id(hass)) is None
    )


async def test_the_device_stays_when_an_unrecognized_entry_remains_on_it(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Moving the device would remove an MQTT entry the module did not move, so the device is left in place."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    mqtt_device = _mqtt_device(hass, legacy.device_id)
    mqtt_entry = hass.config_entries.async_get_entry(_mqtt_entry_id(hass))
    odd = entity_registry.async_get_or_create(
        "sensor", "mqtt", "an-odd-sensor", config_entry=mqtt_entry, device_id=mqtt_device.id
    )
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)

    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE

    assert legacy_entity_ids(hass, legacy.device_id) == []
    switch = entity_registry.async_get_entity_id("switch", DOMAIN, legacy.device_id)
    assert switch is not None
    assert entity_registry.async_get(odd.entity_id) is not None
    device = dr.async_get(hass).async_get(mqtt_device.id)
    assert device is not None
    assert device.config_entry_id == _mqtt_entry_id(hass)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, True),
        ({"unique_id": "dev_test_on", "domain": "button"}, True),
        ({"unique_id": "dev-other"}, False),
        ({"unique_id": "devx_test_on"}, False),
        ({"platform": DOMAIN}, False),
        ({"config_entry_id": "other-entry"}, False),
        ({"device_id": "other-device"}, False),
        ({"domain": "sensor"}, False),
    ],
)
def test_is_legacy_entity_needs_every_part_of_the_identity(changes: dict[str, str], expected: bool) -> None:
    """T-5-01: the unique id alone never decides, platform, entry, device, domain and shape must all match."""
    fields = {
        "platform": "mqtt",
        "config_entry_id": "mqtt-entry",
        "device_id": "mqtt-device",
        "domain": "switch",
        "unique_id": "dev",
    }
    entity = SimpleNamespace(**{**fields, **changes})

    assert is_legacy_entity(entity, "dev", "mqtt-entry", "mqtt-device") is expected  # type: ignore[arg-type]


# --- the takeover module: the catch for replayed duplicates (D-04, D-05, T-06-06) --------------------------------


async def _moved_and_replayed(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[LegacyDevice, dict[str, er.RegistryEntry], list[str]]:
    """Take a legacy device over, clear its discovery and replay it live; return it, the moved entries, the replay."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    moved = {entity_id: entity_registry.async_get(entity_id) for entity_id in _moved_entity_ids(hass, legacy.device_id)}
    assert len(moved) == 3
    await _deliver(hass, legacy.topic, legacy.payload)
    replayed = legacy_entity_ids(hass, legacy.device_id)
    assert len(replayed) == 3
    return legacy, moved, replayed


def _remove_replay_twins_of(hass: HomeAssistant, legacy: LegacyDevice, **kwargs: Any) -> int:
    return remove_replay_twins(
        hass, legacy.entry.entry_id, legacy.device_id, mqtt_entry_id=_mqtt_entry_id(hass), **kwargs
    )


async def test_remove_replay_twins_removes_the_loaded_duplicates_and_the_emptied_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The loaded duplicates of a replay and the emptied MQTT device go; every moved entry and the device stay."""
    legacy, moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    taken_device = device_registry.async_get_device_by_identifier((DOMAIN, legacy.device_id), legacy.entry.entry_id)
    assert taken_device is not None
    assert all(hass.states.get(entity_id) is not None for entity_id in replayed)

    assert _remove_replay_twins_of(hass, legacy) == 3
    await hass.async_block_till_done(wait_background_tasks=True)

    assert legacy_entity_ids(hass, legacy.device_id) == []
    for entity_id in replayed:
        assert entity_registry.async_get(entity_id) is None
        assert hass.states.get(entity_id) is None
    for entity_id, old in moved.items():
        assert entity_registry.async_get(entity_id) == old
    assert device_registry.async_get(taken_device.id) is not None
    assert (
        device_registry.async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{legacy.device_id}"), _mqtt_entry_id(hass))
        is None
    )


async def test_remove_replay_twins_disables_a_loaded_row_first_so_nothing_is_cleared_and_no_enabled_tombstone_stays(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    WR-01: a loaded, enabled duplicate leaves the registry without an empty retained discovery and as a disabled record.

    Core MQTT clears the retained topic of a loaded entity that is removed from the registry, which would wipe the
    export of another instance, and the record of an enabled row restores as enabled the next time core creates it.
    """
    legacy, _moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    loaded = entity_sources(hass)
    assert all(entity_id in loaded for entity_id in replayed)
    assert all(entity_registry.async_get(entity_id).disabled_by is None for entity_id in replayed)
    mqtt_mock.async_publish.reset_mock()

    assert _remove_replay_twins_of(hass, legacy) == 3
    await hass.async_block_till_done(wait_background_tasks=True)

    # Core MQTT clears with a None payload, which `_discovery_clears` (empty string) does not see
    cleared = [
        call for call in mqtt_mock.async_publish.call_args_list if call.args[0] == legacy.topic and not call.args[1]
    ]
    assert cleared == []
    assert legacy_entity_ids(hass, legacy.device_id) == []
    records = [
        record
        for (domain, platform, unique_id), record in entity_registry.deleted_entities.items()
        if platform == "mqtt" and unique_id.startswith(legacy.device_id)
    ]
    assert len(records) == 3
    assert all(record.disabled_by is er.RegistryEntryDisabler.INTEGRATION for record in records)


async def test_remove_replay_twins_leaves_rows_core_discovered_while_they_were_disabled_so_nothing_is_cleared(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    CR-01: core MQTT clears the retained topic when a row it discovered while disabled leaves the registry.

    That is the usual state of a duplicate after a restart or of a row an export created, so the catch leaves every
    disabled row in place: it already restores as disabled, and the topic may hold another instance's export.
    """
    legacy, _moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    await _rediscover_disabled(hass, legacy, replayed)
    mqtt_mock.async_publish.reset_mock()

    assert _remove_replay_twins_of(hass, legacy) == 0
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    entity_registry = er.async_get(hass)
    assert sorted(legacy_entity_ids(hass, legacy.device_id)) == sorted(replayed)
    assert all(
        entity_registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for entity_id in replayed
    )


async def test_remove_replay_twins_leaves_an_entry_without_a_native_twin_and_keeps_the_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """An entry that has no counterpart under this integration is no duplicate: it stays, and so does its device."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    button_id = next(entity_id for entity_id in _moved_entity_ids(hass, legacy.device_id) if "button." in entity_id)
    entity_registry.async_remove(button_id)  # this entry has no native twin when the replay comes
    await _deliver(hass, legacy.topic, legacy.payload)
    replayed = legacy_entity_ids(hass, legacy.device_id)
    assert len(replayed) == 3

    assert _remove_replay_twins_of(hass, legacy) == 2

    left = legacy_entity_ids(hass, legacy.device_id)
    assert len(left) == 1
    assert left[0].startswith("button.")
    assert _mqtt_device(hass, legacy.device_id) is not None


async def test_remove_replay_twins_leaves_an_older_entry_that_carries_the_identity_to_the_takeover(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """WR-04: an older legacy entry is the identity the user knows; the takeover pass resolves it, not the catch."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)

    assert _remove_replay_twins_of(hass, legacy) == 0

    entity_registry = er.async_get(hass)
    for entity_id, old in before.items():
        assert entity_registry.async_get(entity_id) == old
    for twin in natives.values():
        assert entity_registry.async_get(twin.entity_id) == twin


@pytest.mark.parametrize("content", [DiscoveryContent.LEGACY, DiscoveryContent.EMPTY])
async def test_remove_replay_twins_removes_an_integration_disabled_row_for_legacy_or_empty_content(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    content: DiscoveryContent,
) -> None:
    """D-02: with the legacy payload or nothing on the topic, the rows the integration disabled go with their device."""
    legacy, _moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    await _rediscover_disabled(hass, legacy, replayed)

    assert _remove_replay_twins_of(hass, legacy, content=content) == 3
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_registry = er.async_get(hass)
    assert legacy_entity_ids(hass, legacy.device_id) == []
    assert all(entity_registry.async_get(entity_id) is None for entity_id in replayed)
    assert legacy_device(hass, _mqtt_entry_id(hass), legacy.device_id) is None


@pytest.mark.parametrize("content", [DiscoveryContent.EXPORT, DiscoveryContent.UNKNOWN])
async def test_remove_replay_twins_keeps_an_integration_disabled_row_for_export_or_unknown_content(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    content: DiscoveryContent,
) -> None:
    """CR-01, D-03: the topic may hold another instance's export, so no disabled row goes and nothing is cleared."""
    legacy, _moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    await _rediscover_disabled(hass, legacy, replayed)
    mqtt_mock.async_publish.reset_mock()

    assert _remove_replay_twins_of(hass, legacy, content=content) == 0
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    assert sorted(legacy_entity_ids(hass, legacy.device_id)) == sorted(replayed)
    assert legacy_device(hass, _mqtt_entry_id(hass), legacy.device_id) is not None


@pytest.mark.parametrize("content", list(DiscoveryContent))
async def test_remove_replay_twins_keeps_a_user_disabled_row_whatever_the_content(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    content: DiscoveryContent,
) -> None:
    """D-04: a row the user disabled is the user's decision; it stays, and so does its MQTT device."""
    legacy, _moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    await _rediscover_disabled(hass, legacy, replayed)
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    entity_registry.async_update_entity(switch, disabled_by=er.RegistryEntryDisabler.USER)

    _remove_replay_twins_of(hass, legacy, content=content)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.USER
    assert switch in legacy_entity_ids(hass, legacy.device_id)
    assert legacy_device(hass, _mqtt_entry_id(hass), legacy.device_id) is not None


async def test_remove_replay_twins_keeps_a_customized_row_with_legacy_content(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-04, WR-02: a customized row stays even with the legacy payload on the topic; the uncustomized ones go."""
    legacy, _moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    await _rediscover_disabled(hass, legacy, replayed)
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    entity_registry.async_update_entity(switch, name="My own name")

    assert _remove_replay_twins_of(hass, legacy, content=DiscoveryContent.LEGACY) == 2
    await hass.async_block_till_done(wait_background_tasks=True)

    assert legacy_entity_ids(hass, legacy.device_id) == [switch]
    assert entity_registry.async_get(switch).name == "My own name"
    assert legacy_device(hass, _mqtt_entry_id(hass), legacy.device_id) is not None


def _disable_duplicates_of(hass: HomeAssistant, legacy: LegacyDevice) -> int:
    return disable_duplicates(hass, legacy.entry.entry_id, legacy.device_id, mqtt_entry_id=_mqtt_entry_id(hass))


async def test_disable_duplicates_leaves_a_customized_entry_enabled_next_to_an_untouched_native_twin(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    WR-02: the entry that holds the user's name, area or labels is the one automations use, so it is never disabled.

    Age is no criterion here: a row that core restores from a deleted record keeps the old creation time, and that
    row is the duplicate the guard exists for.
    """
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    entity_registry = er.async_get(hass)
    switch = next(old for old in before.values() if (old.domain, old.unique_id) == ("switch", legacy.device_id))
    entity_registry.async_update_entity(switch.entity_id, name="My own name")

    assert _disable_duplicates_of(hass, legacy) == 0

    assert entity_registry.async_get(switch.entity_id).disabled_by is None
    assert entity_registry.async_get(natives[("switch", legacy.device_id)].entity_id).disabled_by is None


async def test_disable_duplicates_disables_a_legacy_entry_when_the_native_twin_carries_the_identity(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """WR-02: only the native twin holds the user's choices, so the legacy entry is the duplicate and gets disabled."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    entity_registry = er.async_get(hass)
    switch = next(old for old in before.values() if (old.domain, old.unique_id) == ("switch", legacy.device_id))
    twin = natives[("switch", legacy.device_id)]
    entity_registry.async_update_entity(twin.entity_id, name="My own name")

    assert _disable_duplicates_of(hass, legacy) == 1

    assert entity_registry.async_get(switch.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity_registry.async_get(twin.entity_id).disabled_by is None


type Customize = Callable[[er.EntityRegistry, str], er.RegistryEntry]

# The user's changes that `_is_customized` must see beyond name, icon, area and tags; each returns the updated entry
CUSTOMIZATIONS = [
    pytest.param(
        lambda registry, entity_id: registry.async_update_entity(entity_id, aliases=[er.COMPUTED_NAME, "Kitchen"]),
        id="aliases",
    ),
    pytest.param(
        lambda registry, entity_id: registry.async_update_entity(entity_id, device_class="outlet"),
        id="device_class",
    ),
    pytest.param(
        lambda registry, entity_id: registry.async_update_entity_options(
            entity_id, "cloud.google_assistant", {"disable_2fa": True}
        ),
        id="options",
    ),
    pytest.param(
        # A wrapper helper such as Switch-as-X hides the switch it wraps and points at its entity id
        lambda registry, entity_id: registry.async_update_entity(
            entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
        ),
        id="hidden_by_integration",
    ),
    pytest.param(
        lambda registry, entity_id: registry.async_update_entity(
            entity_id, new_entity_id="switch.kitchen_lamp_renamed_by_user"
        ),
        id="entity_id_rename",
        marks=pytest.mark.xfail(
            strict=True,
            reason=(
                "Not detectable: core's automatic entity id (async_regenerate_entity_id) also differs for a row "
                "restored from a deleted record, the duplicate the guard exists for"
            ),
        ),
    ),
]


@pytest.mark.parametrize("customize", CUSTOMIZATIONS)
async def test_disable_duplicates_leaves_an_entry_enabled_that_holds_any_user_customization(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    customize: Customize,
) -> None:
    """WR-02: aliases, a device class, user options and a wrapper's hold are the user's choices as much as a name."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    _natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    entity_registry = er.async_get(hass)
    switch = next(old for old in before.values() if (old.domain, old.unique_id) == ("switch", legacy.device_id))
    customized = customize(entity_registry, switch.entity_id)

    assert _disable_duplicates_of(hass, legacy) == 0

    assert entity_registry.async_get(customized.entity_id).disabled_by is None


@pytest.mark.parametrize("customize", CUSTOMIZATIONS)
async def test_remove_replay_twins_leaves_a_newer_entry_that_holds_any_user_customization(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    customize: Customize,
) -> None:
    """WR-02: a replayed entry the user customized is no duplicate to delete, however much newer than its twin."""
    legacy, _moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    switch_id = next(entity_id for entity_id in replayed if entity_id.startswith("switch."))
    customized = customize(entity_registry, switch_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _remove_replay_twins_of(hass, legacy) == 2

    assert entity_registry.async_get(customized.entity_id) is not None


@pytest.mark.parametrize(
    "rejected",
    [{"disabled_by": er.RegistryEntryDisabler.USER}, {"hidden_by": er.RegistryEntryHider.USER}],
    ids=["twin_disabled_by_user", "twin_hidden_by_user"],
)
@pytest.mark.parametrize("legacy_name", [None, "Kitchen"], ids=["untouched_legacy", "named_legacy"])
async def test_disable_duplicates_keeps_the_legacy_entry_when_the_user_turned_the_native_twin_off(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    rejected: dict[str, Any],
    legacy_name: str | None,
) -> None:
    """
    WR-03: a twin the user disabled or hid is the entity they rejected, not the identity they keep.

    Disabling the legacy entry as well would leave no enabled, visible entity for the unique id, and the guard would
    disable it again at every start.
    """
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    entity_registry = er.async_get(hass)
    switch = next(old for old in before.values() if (old.domain, old.unique_id) == ("switch", legacy.device_id))
    entity_registry.async_update_entity(switch.entity_id, name=legacy_name)
    twin = entity_registry.async_update_entity(natives[("switch", legacy.device_id)].entity_id, **rejected)

    assert _disable_duplicates_of(hass, legacy) == 0

    assert entity_registry.async_get(switch.entity_id).disabled_by is None
    assert entity_registry.async_get(twin.entity_id) == twin


async def test_disable_duplicates_disables_a_legacy_entry_the_user_hid(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """WR-03: a legacy entry the user hid is the one they rejected; the hidden state is no customization to protect."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    _natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    entity_registry = er.async_get(hass)
    switch = next(old for old in before.values() if (old.domain, old.unique_id) == ("switch", legacy.device_id))
    entity_registry.async_update_entity(switch.entity_id, hidden_by=er.RegistryEntryHider.USER)

    assert _disable_duplicates_of(hass, legacy) == 1

    assert entity_registry.async_get(switch.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_with_both_entries_customized_neither_the_guard_nor_the_catch_touches_the_legacy_entry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    WR-03: when both entries hold the user's choices, no automatic rule knows which one automations use.

    The newer legacy entry is neither removed by the catch, which would leave its name and labels only in a deleted
    record no UI reaches, nor disabled by the guard.
    """
    legacy, moved, replayed = await _moved_and_replayed(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    switch_id = next(entity_id for entity_id in replayed if entity_id.startswith("switch."))
    twin_id = next(entity_id for entity_id in moved if entity_id.startswith("switch."))
    entity_registry.async_update_entity(switch_id, name="Kitchen", labels={"kitchen"})
    entity_registry.async_update_entity(twin_id, name="Lamp")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _remove_replay_twins_of(hass, legacy) == 2
    assert _disable_duplicates_of(hass, legacy) == 0

    kept = entity_registry.async_get(switch_id)
    assert kept is not None
    assert (kept.name, kept.labels, kept.disabled_by) == ("Kitchen", {"kitchen"}, None)
    assert entity_registry.async_get(twin_id).name == "Lamp"


async def test_disable_duplicates_still_disables_an_entry_whose_only_option_is_the_exposure_core_stores_itself(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """
    WR-02: core writes `should_expose` on its own the first time an assistant asks, so that key is no user choice.

    The stored value cannot tell a user's choice from core's default either: conversation exposes a new switch by
    default. Counting it would protect every duplicate an assistant ever looked at.
    """
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    _natives, before, _mqtt_device_entry, _native_device = await _legacy_with_native_twins(hass, legacy)
    entity_registry = er.async_get(hass)
    switch = next(old for old in before.values() if (old.domain, old.unique_id) == ("switch", legacy.device_id))
    entity_registry.async_update_entity_options(switch.entity_id, "conversation", {"should_expose": True})

    assert _disable_duplicates_of(hass, legacy) == 1

    assert entity_registry.async_get(switch.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_remove_replay_twins_never_touches_a_foreign_mqtt_entity(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-5-01, T-06-06: an unrelated MQTT entity that carries the device id as unique id stays where it is."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    foreign_payload = {
        "device": {"identifiers": ["somebody_else"], "name": "Somebody else"},
        "origin": {"name": "Somebody else"},
        "components": {
            "other": {
                "platform": "button",
                "unique_id": legacy.device_id,
                "name": "Foreign button",
                "command_topic": "somebody/else/set",
            }
        },
    }
    async_fire_mqtt_message(hass, discovery_topic(PREFIX, "somebody_else"), json.dumps(foreign_payload), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    foreign_id = entity_registry.async_get_entity_id("button", "mqtt", legacy.device_id)
    assert foreign_id is not None
    foreign_before = entity_registry.async_get(foreign_id)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    await _deliver(hass, legacy.topic, legacy.payload)
    assert len(legacy_entity_ids(hass, legacy.device_id)) == 4  # three replayed entries and the foreign button

    assert _remove_replay_twins_of(hass, legacy) == 3

    assert entity_registry.async_get(foreign_id) == foreign_before
    assert legacy_entity_ids(hass, legacy.device_id) == [foreign_id]


async def test_remove_replay_twins_without_a_legacy_device_does_nothing_and_publishes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A device id without a core MQTT device returns 0, changes no registry entry and sends nothing to the broker."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    await _deliver(hass, legacy.topic, MIGRATE_PAYLOAD)
    assert await _take_over_now(hass, legacy) is TakeoverStatus.DONE
    await _deliver(hass, legacy.topic, CLEAR_PAYLOAD)
    snapshot = _mqtt_entry_state(hass)
    mqtt_mock.async_publish.reset_mock()

    assert _remove_replay_twins_of(hass, legacy) == 0
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _mqtt_entry_state(hass) == snapshot
    assert mqtt_mock.async_publish.call_args_list == []
