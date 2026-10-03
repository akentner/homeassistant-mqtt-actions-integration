"""Native Switch, Select and test button entities of owned devices (ENT-01, ENT-02, MIG-03, D-03, D-07, D-08)."""

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_OPTIONS,
    CONF_STATE_VALUE,
    DOMAIN,
    STORE_KEY,
    STORE_VERSION,
)
from custom_components.mqtt_actions.topics import discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on"}]
OFF_ACTIONS = [{"action": "test.off"}]


def _seed_native(hass_storage: dict[str, Any], *, instance: bool = True, devices: list[str] | None = None) -> None:
    """Seed the persisted native flag the way production stores it; the other Store keys stay absent."""
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {"native": {"instance": instance, "pending": [], "devices": devices or []}},
    }


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = False) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _switch_state(hass: HomeAssistant, device_id: str) -> str:
    entity_id = _entity_id(hass, "switch", device_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


async def _native_switch(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    name: str = "Lamp",
) -> tuple[MockConfigEntry, str]:
    """Set up a native instance with one Switch device that has on and off actions."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry(name, on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([subentry]))
    return entry, _device_id(subentry)


# --- Task 1 tracer: an owned Switch device as a native entity ------------------------------------------------------


async def test_native_switch_is_registered_under_the_subentry(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03, ENT-01: the entity is the integration's own, on the subentry, with the id the legacy entity had."""
    entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)

    entity_id = _entity_id(hass, "switch", device_id)
    assert entity_id is not None
    registered = er.async_get(hass).async_get(entity_id)
    assert registered is not None
    assert registered.platform == DOMAIN
    assert registered.unique_id == device_id
    (subentry_id,) = entry.subentries
    assert registered.config_subentry_id == subentry_id
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)
    assert device is not None
    assert registered.device_id == device.id
    assert device.name == "Lamp"
    assert hass.states.get(entity_id).name == "Lamp"


async def test_native_switch_state_follows_the_state_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """STA-07: accepted payloads map like the tracker does, unknown and empty ones leave the state alone."""
    _entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    assert _switch_state(hass, device_id) == "unknown"

    await _state(hass, device_id, "ON", retain=True)
    assert _switch_state(hass, device_id) == "on"

    await _state(hass, device_id, "OFF")
    assert _switch_state(hass, device_id) == "off"

    await _state(hass, device_id, "  on ")
    assert _switch_state(hass, device_id) == "on"
    await _state(hass, device_id, "oFf")
    assert _switch_state(hass, device_id) == "off"

    await _state(hass, device_id, "garbage")
    assert _switch_state(hass, device_id) == "off"
    await _state(hass, device_id, "", retain=True)
    assert _switch_state(hass, device_id) == "off"


async def test_a_disabled_device_still_shows_its_state(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """The value is recorded before the disabled gate; disabled only stops the actions."""
    on_calls = async_mock_service(hass, "test", "on")
    entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    await _manager(entry).async_set_device_mode(device_id, "disabled")

    await _state(hass, device_id, "ON")

    assert _switch_state(hass, device_id) == "on"
    assert on_calls == []


async def test_turn_on_publishes_the_exact_value_retained_at_qos_1(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-07, ENT-02, STA-01: the command goes retained at QoS 1 and the state waits for the echo."""
    entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    entity_id = _entity_id(hass, "switch", device_id)
    assert entity_id is not None
    topic = state_topic(BASE, device_id)

    # The mocked MQTT client loops a publish back, so the first command is held at the gateway to see the state wait
    with patch.object(_manager(entry).gateway, "async_publish", new=AsyncMock()) as publish:
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
        await hass.async_block_till_done(wait_background_tasks=True)
    publish.assert_awaited_once_with(topic, "ON", retain=True, qos=1)
    assert _switch_state(hass, device_id) == "unknown"

    await _state(hass, device_id, "ON")
    assert _switch_state(hass, device_id) == "on"

    # Through the real gateway the publish reaches the MQTT client with the same flags
    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _publishes(mqtt_mock, topic) == [("OFF", 1, True)]


async def test_the_echo_runs_the_actions_once(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """STA-02: the actions still come from the state topic, once per real change."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    _entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)

    await _state(hass, device_id, "ON")
    await _state(hass, device_id, "ON")

    assert len(on_calls) == 1
    assert off_calls == []


async def test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03, D-08: no discovery topic is written, and the mode select sits on the device of the switch."""
    _entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)

    assert _publishes(mqtt_mock, discovery_topic("homeassistant", device_id)) == []
    switch_id = _entity_id(hass, "switch", device_id)
    mode_id = _entity_id(hass, "select", f"{device_id}_mode")
    assert switch_id is not None
    assert mode_id is not None
    registry = er.async_get(hass)
    switch_entry = registry.async_get(switch_id)
    mode_entry = registry.async_get(mode_id)
    assert switch_entry is not None
    assert mode_entry is not None
    assert switch_entry.device_id == mode_entry.device_id
    assert switch_entry.config_subentry_id == mode_entry.config_subentry_id


async def test_an_instance_without_the_native_flag_keeps_the_legacy_path(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03: with no `native` Store key the discovery is published and the integration has no switch entity."""
    subentry = make_switch_subentry("Lamp", on=ON_ACTIONS)
    await _setup(hass, make_hub_entry([subentry]))

    assert len(_publishes(mqtt_mock, discovery_topic("homeassistant", _device_id(subentry)))) == 1
    assert _entity_id(hass, "switch", _device_id(subentry)) is None
    assert not [
        entry for entry in er.async_get(hass).entities.values() if entry.platform == DOMAIN and entry.domain == "switch"
    ]


# --- Task 2: the native Select ---------------------------------------------------------------------------------------

SELECT_OPTIONS = [
    ("a", "Alpha", [{"action": "test.a"}]),
    ("Mixed Case", "Bravo", [{"action": "test.b"}]),
    ("c", "Charlie", [{"action": "test.c"}]),
]


async def _native_select(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> tuple[MockConfigEntry, str]:
    """Set up a native instance with one Select device."""
    _seed_native(hass_storage)
    subentry = make_select_subentry("Mode", SELECT_OPTIONS)
    entry = await _setup(hass, make_hub_entry([subentry]))
    return entry, _device_id(subentry)


def _select_entity_id(hass: HomeAssistant, device_id: str) -> str:
    entity_id = _entity_id(hass, "select", device_id)
    assert entity_id is not None
    return entity_id


def _select_state(hass: HomeAssistant, device_id: str) -> str:
    state = hass.states.get(_select_entity_id(hass, device_id))
    assert state is not None
    return state.state


async def test_native_select_offers_the_friendly_names_and_shows_the_current_one(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """ENT-01: the options are the friendly names in stored order; any spelling of a StateValue maps to its option."""
    entry, device_id = await _native_select(hass, hass_storage, make_hub_entry, make_select_subentry)
    entity_id = _select_entity_id(hass, device_id)
    registered = er.async_get(hass).async_get(entity_id)
    assert registered is not None
    assert registered.platform == DOMAIN
    assert registered.unique_id == device_id
    (subentry_id,) = entry.subentries
    assert registered.config_subentry_id == subentry_id
    assert hass.states.get(entity_id).attributes["options"] == ["Alpha", "Bravo", "Charlie"]
    assert _select_state(hass, device_id) == "unknown"

    await _state(hass, device_id, "a", retain=True)
    assert _select_state(hass, device_id) == "Alpha"

    await _state(hass, device_id, "  MIXED case\n")
    assert _select_state(hass, device_id) == "Bravo"


async def test_an_unknown_select_payload_keeps_the_state(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """STA-07: a payload that is no StateValue and the empty retained clear leave the current option alone."""
    _entry, device_id = await _native_select(hass, hass_storage, make_hub_entry, make_select_subentry)
    await _state(hass, device_id, "c", retain=True)

    await _state(hass, device_id, "nonsense")
    assert _select_state(hass, device_id) == "Charlie"
    await _state(hass, device_id, "", retain=True)
    assert _select_state(hass, device_id) == "Charlie"


async def test_choosing_an_option_publishes_the_state_value_not_the_friendly_name(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-07, ENT-02: the broker gets the exact StateValue, retained at QoS 1, and a foreign option is refused."""
    _entry, device_id = await _native_select(hass, hass_storage, make_hub_entry, make_select_subentry)
    entity_id = _select_entity_id(hass, device_id)

    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": "Bravo"}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _publishes(mqtt_mock, state_topic(BASE, device_id)) == [("Mixed Case", 1, True)]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "select", "select_option", {"entity_id": entity_id, "option": "Delta"}, blocking=True
        )
    assert len(_publishes(mqtt_mock, state_topic(BASE, device_id))) == 1


async def test_renaming_an_option_is_followed_live(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """The entity shows the new friendly name of the same StateValue after a reconfigure."""
    entry, device_id = await _native_select(hass, hass_storage, make_hub_entry, make_select_subentry)
    await _state(hass, device_id, "a", retain=True)
    assert _select_state(hass, device_id) == "Alpha"

    subentry = next(iter(entry.subentries.values()))
    renamed = [
        {**option, CONF_FRIENDLY_NAME: "Omega"} if option[CONF_STATE_VALUE] == "a" else option
        for option in subentry.data[CONF_OPTIONS]
    ]
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_OPTIONS: renamed})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(_select_entity_id(hass, device_id)).attributes["options"] == ["Omega", "Bravo", "Charlie"]
    assert _select_state(hass, device_id) == "Omega"


async def test_removing_the_selected_option_leaves_the_state_unknown(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """A removed option is no stale name: the state becomes unknown."""
    entry, device_id = await _native_select(hass, hass_storage, make_hub_entry, make_select_subentry)
    await _state(hass, device_id, "c", retain=True)
    assert _select_state(hass, device_id) == "Charlie"

    subentry = next(iter(entry.subentries.values()))
    kept = [option for option in subentry.data[CONF_OPTIONS] if option[CONF_STATE_VALUE] != "c"]
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_OPTIONS: kept})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(_select_entity_id(hass, device_id)).attributes["options"] == ["Alpha", "Bravo"]
    assert _select_state(hass, device_id) == "unknown"


async def test_the_mode_select_shares_the_device_of_the_native_entities(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-08: one device per concept; the mode select and the native select report the same device."""
    entry, device_id = await _native_select(hass, hass_storage, make_hub_entry, make_select_subentry)
    registry = er.async_get(hass)
    native = registry.async_get(_select_entity_id(hass, device_id))
    mode_id = _entity_id(hass, "select", f"{device_id}_mode")
    assert mode_id is not None
    mode = registry.async_get(mode_id)
    assert native is not None
    assert mode is not None
    assert native.device_id == mode.device_id
    device = dr.async_get(hass).async_get(native.device_id)
    assert device is not None
    assert (DOMAIN, device_id) in device.identifiers
    assert device.model == "Select device"
    assert _manager(entry).device_mode(device_id) == "run"
