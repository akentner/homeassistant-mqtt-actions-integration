"""Native Switch, Select and test button entities of owned devices and mirrors (ENT-01, ENT-02, MIG-03, D-07)."""

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions import topics
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_OPTIONS,
    CONF_STATE_VALUE,
    DOMAIN,
    ISSUE_OWNER_CONFLICT_PREFIX,
    STORE_KEY,
    STORE_MIRRORS,
    STORE_VERSION,
)
from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.document import parse_document
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY, trigger_key
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from tests.documents import FOREIGN_OWNER, FOREIGN_OWNER_NAME, document_payload, make_spec

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


# --- Task 3: native test buttons -------------------------------------------------------------------------------------


def _button_id(hass: HomeAssistant, device_id: str, key: str) -> str | None:
    return _entity_id(hass, "button", f"{device_id}_test_{key}")


async def _press(hass: HomeAssistant, device_id: str, key: str) -> None:
    entity_id = _button_id(hass, device_id, key)
    assert entity_id is not None
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _all_publishes(mqtt_mock: Any, device_id: str) -> list[tuple]:
    """Return what was published on the state or the test topic of a device."""
    watched = {state_topic(BASE, device_id), topics.test_topic(BASE, device_id)}
    return [call.args[:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] in watched]


async def test_native_test_buttons_exist_per_trigger(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """MIG-03: one native button per trigger with the unique id, name and category of the legacy button."""
    entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    registry = er.async_get(hass)
    (subentry_id,) = entry.subentries

    for key, name in ((SWITCH_ON_KEY, "Test ON"), (SWITCH_OFF_KEY, "Test OFF")):
        entity_id = _button_id(hass, device_id, key)
        assert entity_id is not None
        registered = registry.async_get(entity_id)
        assert registered is not None
        assert registered.platform == DOMAIN
        assert registered.original_name == name
        assert registered.entity_category is EntityCategory.CONFIG
        assert registered.config_subentry_id == subentry_id
        device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)
        assert device is not None
        assert registered.device_id == device.id


async def test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """MIG-03: a press runs the actions of its trigger once, publishes nothing and leaves value and baseline alone."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    await _state(hass, device_id, "OFF", retain=True)
    device = _manager(entry).devices[device_id]
    mqtt_mock.async_publish.reset_mock()

    await _press(hass, device_id, SWITCH_ON_KEY)

    assert (len(on_calls), len(off_calls)) == (1, 0)
    assert _all_publishes(mqtt_mock, device_id) == []
    assert device.value == "OFF"
    assert device.tracker.last_acted == "OFF"
    assert _switch_state(hass, device_id) == "off"


async def test_observe_and_disabled_modes_block_the_press(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-14: a press runs no actions in observe or disabled mode and runs them again in run mode."""
    on_calls = async_mock_service(hass, "test", "on")
    entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)

    await manager.async_set_device_mode(device_id, "observe")
    await _press(hass, device_id, SWITCH_ON_KEY)
    await manager.async_set_device_mode(device_id, "disabled")
    await _press(hass, device_id, SWITCH_ON_KEY)
    assert on_calls == []

    await manager.async_set_device_mode(device_id, "run")
    await _press(hass, device_id, SWITCH_ON_KEY)
    assert len(on_calls) == 1


async def test_removing_an_option_removes_its_native_button_entry(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """A removed option leaves no unavailable button behind; the other buttons stay."""
    entry, device_id = await _native_select(hass, hass_storage, make_hub_entry, make_select_subentry)
    keys = {value: trigger_key(value) for value, _friendly, _actions in SELECT_OPTIONS}
    assert all(_button_id(hass, device_id, key) is not None for key in keys.values())

    subentry = next(iter(entry.subentries.values()))
    kept = [option for option in subentry.data[CONF_OPTIONS] if option[CONF_STATE_VALUE] != "c"]
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_OPTIONS: kept})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _button_id(hass, device_id, keys["c"]) is None
    assert _button_id(hass, device_id, keys["a"]) is not None
    assert _button_id(hass, device_id, keys["Mixed Case"]) is not None


@pytest.mark.parametrize("native", [True, False])
async def test_a_native_device_subscribes_no_test_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    native: bool,
) -> None:
    """MIG-03: a native device has no test-topic subscription, a legacy device still has one."""
    if native:
        _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([subentry]))

    device = _manager(entry).devices[_device_id(subentry)]

    assert (device.unsubscribe_test is None) is native
    assert device.unsubscribe is not None


async def test_press_of_an_unknown_trigger_does_nothing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """An unknown device id or trigger key returns without error and runs nothing."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)

    await manager.async_press_test("no-such-device", SWITCH_ON_KEY)
    await manager.async_press_test(device_id, "no-such-key")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (on_calls, off_calls) == ([], [])


# --- Plan 05-04: native mirrors of a marked document ---------------------------------------------------------------


async def _deliver(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = True) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _presence(hass: HomeAssistant, status: str, owner: str = FOREIGN_OWNER, *, retain: bool = True) -> None:
    async_fire_mqtt_message(hass, availability_topic(BASE, owner), status, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _native_platform_entries(hass: HomeAssistant, domain: str) -> list[er.RegistryEntry]:
    return [
        entry for entry in er.async_get(hass).entities.values() if entry.platform == DOMAIN and entry.domain == domain
    ]


def _companion(hass: HomeAssistant, entry: MockConfigEntry, device_id: str) -> dr.DeviceEntry | None:
    return dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)


async def test_a_marked_mirror_is_a_native_entity_directly_under_the_entry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-07, D-09, ENT-01, STA-01: a marked foreign document is a native switch on a device of the entry itself."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _presence(hass, "online")

    await _deliver(hass, spec.device_id, document_payload(spec, native=True))

    entity_id = _entity_id(hass, "switch", spec.device_id)
    assert entity_id is not None
    registered = er.async_get(hass).async_get(entity_id)
    assert registered is not None
    assert registered.platform == DOMAIN
    assert registered.config_subentry_id is None
    assert registered.config_entry_id == entry.entry_id
    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.config_subentry_id is None
    assert companion.model == f"Switch device (mirror of {FOREIGN_OWNER_NAME})"
    assert registered.device_id == companion.id
    mode = er.async_get(hass).async_get(_entity_id(hass, "select", f"{spec.device_id}_mode"))
    assert mode is not None
    assert mode.device_id == companion.id

    await _state(hass, spec.device_id, "ON", retain=True)
    assert _switch_state(hass, spec.device_id) == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _publishes(mqtt_mock, state_topic(BASE, spec.device_id)) == [("OFF", 1, True)]


async def test_an_unmarked_mirror_stays_on_the_legacy_path(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-09: a document without the marker creates no native entity and keeps its legacy companion device."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())

    await _deliver(hass, spec.device_id, document_payload(spec))

    assert _native_platform_entries(hass, "switch") == []
    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.model == "Switch device (mirror)"


async def test_a_native_mirror_has_test_buttons_that_run_locally_once_approved(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """MIG-03: the buttons of a native mirror run the trigger here, behind the approval, and publish nothing."""
    on_calls = async_mock_service(hass, "test", "on")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _presence(hass, "online")
    await _deliver(hass, spec.device_id, document_payload(spec, native=True))

    on_button = _button_id(hass, spec.device_id, SWITCH_ON_KEY)
    assert on_button is not None
    assert _button_id(hass, spec.device_id, SWITCH_OFF_KEY) is not None
    registered = er.async_get(hass).async_get(on_button)
    assert registered is not None
    assert registered.config_subentry_id is None
    assert registered.device_id == _companion(hass, entry, spec.device_id).id
    assert _manager(entry).mirrors[spec.device_id].unsubscribe_test is None

    await _press(hass, spec.device_id, SWITCH_ON_KEY)
    assert on_calls == []

    info = _manager(entry).mirrors[spec.device_id].mirror
    assert info is not None
    assert await _manager(entry).async_approve(spec.device_id, info.actions_hash)
    await _press(hass, spec.device_id, SWITCH_ON_KEY)
    assert len(on_calls) == 1
    assert _all_publishes(mqtt_mock, spec.device_id) == []


# --- Plan 05-04 task 2: availability, one-way native status, removal -----------------------------------------------


def _mirror_state(hass: HomeAssistant, device_id: str) -> str:
    return _switch_state(hass, device_id)


async def test_a_native_mirror_is_unavailable_until_its_owner_is_online(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-07: availability is the owner's announced presence, like the legacy discovery availability."""
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    await _setup(hass, make_hub_entry())

    await _deliver(hass, spec.device_id, document_payload(spec, native=True))
    assert _mirror_state(hass, spec.device_id) == "unavailable"

    await _presence(hass, "online")
    assert _mirror_state(hass, spec.device_id) == "unknown"

    await _presence(hass, "offline")
    assert _mirror_state(hass, spec.device_id) == "unavailable"

    # An owned native entity needs no announcement: it is available while the manager runs
    _entry, device_id = await _native_switch(hass, hass_storage, make_hub_entry, make_switch_subentry)
    assert _switch_state(hass, device_id) != "unavailable"


async def test_an_availability_change_reaches_the_entity_without_a_heartbeat(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-05: a live message flips the entity at once, although the owner never sent a heartbeat."""
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, native=True))

    await _presence(hass, "online", retain=False)
    assert _mirror_state(hass, spec.device_id) == "unknown"

    await _presence(hass, "offline", retain=False)
    assert _mirror_state(hass, spec.device_id) == "unavailable"

    # A cleared announcement is an unknown owner, which is not online either
    await _presence(hass, "online", retain=False)
    await _presence(hass, "", retain=False)
    assert _mirror_state(hass, spec.device_id) == "unavailable"


async def test_an_unmarked_document_never_reverts_a_native_mirror(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-5-11: a later document of the same owner without the marker updates the content and keeps the entity native."""
    spec = make_spec(name="Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    changed = make_spec(device_id=spec.device_id, name="Floor lamp", on=OFF_ACTIONS, off=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _presence(hass, "online")
    await _deliver(hass, spec.device_id, document_payload(spec, native=True, rev=1), retain=False)

    await _deliver(hass, spec.device_id, document_payload(changed, rev=2), retain=False)

    manager = _manager(entry)
    assert manager.is_native(spec.device_id)
    assert manager.mirrors[spec.device_id].spec.name == "Floor lamp"
    assert _switch_state(hass, spec.device_id) == "unknown"
    assert _companion(hass, entry, spec.device_id).model == f"Switch device (mirror of {FOREIGN_OWNER_NAME})"
    # It stays native after a restart too: what is persisted for the mirror still carries the marker
    stored = manager._data_to_save()[STORE_MIRRORS][spec.device_id]
    assert parse_document(spec.device_id, stored).native is True
    assert parse_document(spec.device_id, stored).spec.name == "Floor lamp"


async def test_a_marker_appearing_on_an_unchanged_document_makes_a_legacy_mirror_native(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-07: an owner that switches to native republishes the same content with the marker; the mirror follows."""
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _presence(hass, "online")
    await _deliver(hass, spec.device_id, document_payload(spec, rev=1), retain=False)
    assert _entity_id(hass, "switch", spec.device_id) is None

    await _deliver(hass, spec.device_id, document_payload(spec, native=True, rev=2), retain=False)

    assert _manager(entry).is_native(spec.device_id)
    assert _entity_id(hass, "switch", spec.device_id) is not None
    assert _companion(hass, entry, spec.device_id).model == f"Switch device (mirror of {FOREIGN_OWNER_NAME})"


@pytest.mark.parametrize("pinned_native", [True, False])
async def test_a_marker_of_a_competing_owner_changes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, pinned_native: bool
) -> None:
    """T-5-03: native-ness follows the pinned owner; another owner's claim is the owner conflict and nothing else."""
    spec = make_spec(name="Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    other = make_spec(device_id=spec.device_id, name="Hijacked", on=OFF_ACTIONS, off=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, native=pinned_native), retain=False)
    mirror = _manager(entry).mirrors[spec.device_id]
    spec_before, info_before = mirror.spec, mirror.mirror

    await _deliver(
        hass,
        spec.device_id,
        document_payload(other, owner="instance-other", owner_name="Other", native=not pinned_native),
        retain=False,
    )

    assert mirror.spec is spec_before
    assert mirror.mirror is info_before
    assert _manager(entry).is_native(spec.device_id) is pinned_native
    assert (_entity_id(hass, "switch", spec.device_id) is not None) is pinned_native
    issue_id = f"{ISSUE_OWNER_CONFLICT_PREFIX}{spec.device_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None


async def test_removing_a_native_mirror_removes_its_device_and_entities(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-09, SYN-05: a tombstone removes everything native and leaves the core MQTT device and entities alone."""
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS, name="Foreign lamp")
    entry = await _setup(hass, make_hub_entry())
    discovery = discovery_topic("homeassistant", spec.device_id)
    payload = build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3")
    async_fire_mqtt_message(hass, discovery, json.dumps(payload), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _presence(hass, "online")
    await _deliver(hass, spec.device_id, document_payload(spec, native=True), retain=False)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _entity_id(hass, "select", f"{spec.device_id}_mode"), "option": "observe"},
        blocking=True,
    )
    manager = _manager(entry)
    assert manager.device_mode(spec.device_id) == "observe"

    (mqtt_entry,) = hass.config_entries.async_entries("mqtt")
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    mqtt_device = device_registry.async_get_device_by_identifier(
        ("mqtt", f"{DOMAIN}_{spec.device_id}"), mqtt_entry.entry_id
    )
    assert mqtt_device is not None
    mqtt_entities = er.async_entries_for_device(entity_registry, mqtt_device.id)
    assert mqtt_entities
    assert _companion(hass, entry, spec.device_id) is not None
    assert _entity_id(hass, "switch", spec.device_id) is not None
    assert _button_id(hass, spec.device_id, SWITCH_ON_KEY) is not None

    await _deliver(hass, spec.device_id, "", retain=False)

    assert _companion(hass, entry, spec.device_id) is None
    assert _entity_id(hass, "switch", spec.device_id) is None
    assert _button_id(hass, spec.device_id, SWITCH_ON_KEY) is None
    assert _button_id(hass, spec.device_id, SWITCH_OFF_KEY) is None
    assert _entity_id(hass, "select", f"{spec.device_id}_mode") is None
    assert spec.device_id not in manager.mirrors
    assert manager.device_mode(spec.device_id) == "run"
    assert spec.device_id not in manager._data_to_save()[STORE_MIRRORS]
    assert device_registry.async_get(mqtt_device.id) == mqtt_device
    for entity in mqtt_entities:
        assert entity_registry.async_get(entity.entity_id) == entity
        assert hass.states.get(entity.entity_id) is not None


@pytest.mark.parametrize("user_name", [None, "My lamp"])
async def test_a_renamed_native_mirror_renames_its_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, user_name: str | None
) -> None:
    """D-13: a new name of the pinned owner renames the device, unless the user gave it a name of their own."""
    spec = make_spec(name="Lamp", on=ON_ACTIONS)
    renamed = make_spec(device_id=spec.device_id, name="Floor lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, native=True, rev=1), retain=False)
    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    if user_name is not None:
        dr.async_get(hass).async_update_device(companion.id, name_by_user=user_name)

    await _deliver(hass, spec.device_id, document_payload(renamed, native=True, rev=2), retain=False)

    companion = _companion(hass, entry, spec.device_id)
    assert companion is not None
    assert companion.name == ("Floor lamp" if user_name is None else "Lamp")
    assert companion.name_by_user == user_name
