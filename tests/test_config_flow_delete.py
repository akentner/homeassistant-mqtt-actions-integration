"""Deleting a device needs an all-instances confirmation; instance presence feeds its wording (SYN-06)."""

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions.const import CONF_DEVICE_ID, SUBENTRY_SELECT, SUBENTRY_SWITCH
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on"}]
OFF_ACTIONS = [{"action": "test.off"}]
SELECT_OPTIONS = [("a", "Alpha", [{"action": "test.a"}]), ("b", "Bravo", [{"action": "test.b"}])]
OTHER_A = "11111111-1111-4111-8111-111111111111"
OTHER_B = "22222222-2222-4222-8222-222222222222"
OTHER_C = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
async def switch_hub(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable):
    """Return a set-up hub entry that owns one switch named Lamp."""
    entry = make_hub_entry(subentries=[make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


@pytest.fixture
async def select_hub(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable):
    """Return a set-up hub entry that owns one two-option select named Mode."""
    entry = make_hub_entry(subentries=[make_select_subentry("Mode", SELECT_OPTIONS)])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


@pytest.fixture(params=[SUBENTRY_SWITCH, SUBENTRY_SELECT])
async def device_hub(
    request: pytest.FixtureRequest,
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
):
    """Return (entry, subentry type) of a set-up hub with one device of each type in turn."""
    if request.param == SUBENTRY_SWITCH:
        subentry = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    else:
        subentry = make_select_subentry("Mode", SELECT_OPTIONS)
    entry = make_hub_entry(subentries=[subentry])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry, request.param


async def _presence(hass: HomeAssistant, instance_id: str, payload: str) -> None:
    """Deliver one availability message of an instance, as the broker forwards it."""
    async_fire_mqtt_message(hass, availability_topic(BASE, instance_id), payload)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _reconfigure(hass: HomeAssistant, entry: Any, subentry_type: str) -> dict[str, Any]:
    (subentry,) = entry.subentries.values()
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, subentry_type),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )


async def _choose(hass: HomeAssistant, result: dict[str, Any], step: str) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_configure(result["flow_id"], {"next_step_id": step})


def _clears(mqtt_mock: Any) -> list[str]:
    """Return the topics that received an empty payload, in publish order."""
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list if call.args[1] == ""]


def _device_clears(device_id: str) -> list[str]:
    return [
        discovery_topic("homeassistant", device_id),
        config_topic(BASE, device_id),
        state_topic(BASE, device_id),
    ]


# ---------------------------------------------------------------------------------------------------- presence


async def test_presence_counts_other_online_instances(hass: HomeAssistant, switch_hub: Any) -> None:
    manager = switch_hub.runtime_data
    assert manager.online_instance_count() == 0

    await _presence(hass, OTHER_A, "online")
    await _presence(hass, OTHER_B, "online")
    await _presence(hass, OTHER_C, "offline")
    assert manager.online_instance_count() == 2
    assert manager.sync.instance_status(OTHER_A) == "online"
    assert manager.sync.instance_status(OTHER_C) == "offline"
    assert manager.sync.instance_status("unknown-instance") is None

    # Payloads are compared after strip and lower; anything else is ignored
    await _presence(hass, OTHER_C, "  ONLINE\n")
    assert manager.online_instance_count() == 3
    await _presence(hass, OTHER_C, "garbage")
    assert manager.online_instance_count() == 3
    assert manager.sync.instance_status(OTHER_C) == "online"

    # An empty payload forgets the instance
    await _presence(hass, OTHER_A, "")
    assert manager.online_instance_count() == 2
    assert manager.sync.instance_status(OTHER_A) is None


async def test_own_instance_never_counts(hass: HomeAssistant, switch_hub: Any) -> None:
    manager = switch_hub.runtime_data
    await _presence(hass, manager.instance_id, "online")
    assert manager.online_instance_count() == 0
    await _presence(hass, OTHER_A, "online")
    assert manager.online_instance_count() == 1


async def test_presence_is_capped(hass: HomeAssistant, switch_hub: Any, caplog: pytest.LogCaptureFixture) -> None:
    """T-03-12: broker traffic with many distinct ids cannot grow the cache, and the overflow is logged once."""
    manager = switch_hub.runtime_data
    caplog.clear()
    with (
        caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"),
        patch("custom_components.mqtt_actions.sync.MAX_TRACKED_INSTANCES", 3),
    ):
        for index in range(8):
            await _presence(hass, f"instance-{index}", "online")
        # A tracked id can still change its status at the cap
        await _presence(hass, "instance-0", "offline")

    assert manager.online_instance_count() <= 3
    assert manager.sync.instance_status("instance-0") == "offline"
    assert manager.sync.instance_status("instance-7") is None
    overflow = [
        record
        for record in caplog.records
        if record.name.startswith("custom_components.mqtt_actions") and "instances" in record.getMessage().lower()
    ]
    assert len(overflow) == 1


# ------------------------------------------------------------------------------------------ menus and forms


async def test_switch_reconfigure_is_a_menu(hass: HomeAssistant, switch_hub: Any) -> None:
    result = await _reconfigure(hass, switch_hub, SUBENTRY_SWITCH)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    assert result["menu_options"] == ["edit_device", "delete_device"]


async def test_switch_edit_device_form_behaves_as_before(hass: HomeAssistant, switch_hub: Any) -> None:
    (subentry,) = switch_hub.subentries.values()
    result = await _reconfigure(hass, switch_hub, SUBENTRY_SWITCH)
    result = await _choose(hass, result, "edit_device")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_device"
    prefill = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert prefill["name"] == "Lamp"
    assert prefill["on_change_to_on"] == ON_ACTIONS

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Desk lamp", "on_change_to_on": [], "on_change_to_off": []}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert switch_hub.subentries[subentry.subentry_id].title == "Desk lamp"


async def test_select_menu_offers_delete_only_when_reconfiguring(hass: HomeAssistant, select_hub: Any) -> None:
    result = await _reconfigure(hass, select_hub, SUBENTRY_SELECT)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"
    assert "delete_device" in result["menu_options"]

    created = await hass.config_entries.subentries.async_init(
        (select_hub.entry_id, SUBENTRY_SELECT), context={"source": SOURCE_USER}
    )
    created = await hass.config_entries.subentries.async_configure(created["flow_id"], {"name": "New"})
    assert created["type"] is FlowResultType.MENU
    assert "delete_device" not in created["menu_options"]


# ------------------------------------------------------------------------------------------ confirmation


async def test_delete_confirmation_states_count_and_name(hass: HomeAssistant, device_hub: tuple[Any, str]) -> None:
    entry, subentry_type = device_hub
    (subentry,) = entry.subentries.values()

    result = await _reconfigure(hass, entry, subentry_type)
    result = await _choose(hass, result, "delete_device")
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "delete_device"
    assert result["menu_options"] == ["delete_confirmed", "keep_device"]
    assert result["description_placeholders"] == {"name": subentry.title, "count": "0"}

    await _presence(hass, OTHER_A, "online")
    await _presence(hass, OTHER_B, "online")
    await _presence(hass, OTHER_C, "offline")
    result = await _reconfigure(hass, entry, subentry_type)
    result = await _choose(hass, result, "delete_device")
    assert result["description_placeholders"] == {"name": subentry.title, "count": "2"}


async def test_delete_confirmed_removes_subentry_and_aborts(
    hass: HomeAssistant, mqtt_mock: Any, device_hub: tuple[Any, str]
) -> None:
    entry, subentry_type = device_hub
    (subentry,) = entry.subentries.values()
    device_id = subentry.data[CONF_DEVICE_ID]

    result = await _reconfigure(hass, entry, subentry_type)
    result = await _choose(hass, result, "delete_device")
    mqtt_mock.async_publish.reset_mock()
    result = await _choose(hass, result, "delete_confirmed")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_deleted"
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.subentries == {}
    assert _clears(mqtt_mock) == _device_clears(device_id)


async def test_keep_returns_to_the_menu_and_removes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, device_hub: tuple[Any, str]
) -> None:
    entry, subentry_type = device_hub
    subentries_before = dict(entry.subentries)

    result = await _reconfigure(hass, entry, subentry_type)
    menu_step = result["step_id"]
    result = await _choose(hass, result, "delete_device")
    mqtt_mock.async_publish.reset_mock()
    result = await _choose(hass, result, "keep_device")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == menu_step
    assert entry.subentries == subentries_before
    assert mqtt_mock.async_publish.call_args_list == []


async def test_confirmation_works_when_the_entry_is_not_loaded(
    hass: HomeAssistant, mqtt_mock: Any, switch_hub: Any
) -> None:
    (subentry,) = switch_hub.subentries.values()
    await _presence(hass, OTHER_A, "online")
    assert await hass.config_entries.async_unload(switch_hub.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await _reconfigure(hass, switch_hub, SUBENTRY_SWITCH)
    result = await _choose(hass, result, "delete_device")
    assert result["description_placeholders"] == {"name": subentry.title, "count": "0"}
    result = await _choose(hass, result, "delete_confirmed")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_deleted"
    assert switch_hub.subentries == {}


async def test_generic_delete_path_tombstones_the_same_topics(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Open question 1: the generic Home Assistant delete cannot be vetoed and ends in the same sequence."""
    entry = make_hub_entry(
        subentries=[make_switch_subentry("Flow", on=ON_ACTIONS), make_switch_subentry("Generic", on=ON_ACTIONS)]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    by_title = {subentry.title: subentry for subentry in entry.subentries.values()}

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_SWITCH),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": by_title["Flow"].subentry_id},
    )
    result = await _choose(hass, result, "delete_device")
    mqtt_mock.async_publish.reset_mock()
    await _choose(hass, result, "delete_confirmed")
    await hass.async_block_till_done(wait_background_tasks=True)
    via_flow = _clears(mqtt_mock)

    mqtt_mock.async_publish.reset_mock()
    hass.config_entries.async_remove_subentry(entry, by_title["Generic"].subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    via_generic = _clears(mqtt_mock)

    assert via_flow == _device_clears(by_title["Flow"].data[CONF_DEVICE_ID])
    assert via_generic == _device_clears(by_title["Generic"].data[CONF_DEVICE_ID])
