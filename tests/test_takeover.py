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
from typing import TYPE_CHECKING, Any, NamedTuple

import pytest
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from pytest_homeassistant_custom_component.common import (
    MockPlatform,
    async_fire_mqtt_message,
    mock_platform,
)

from custom_components.mqtt_actions.const import CONF_DEVICE_ID, CONF_INSTANCE_ID, DOMAIN
from custom_components.mqtt_actions.takeover import TakeoverStatus, TakeoverTarget, async_take_over
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic

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
