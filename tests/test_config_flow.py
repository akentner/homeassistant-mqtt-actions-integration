"""Hub flow hardening and the Switch subentry flow (FND-03, DEV-01, DEV-02, DEV-05, D-01, D-03, D-06, D-10, D-11)."""

import json
import uuid
from typing import TYPE_CHECKING, Any

import probatio
import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv

from custom_components.mqtt_actions.config_flow import MqttActionsConfigFlow
from custom_components.mqtt_actions.const import (
    CONF_BASE_TOPIC,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_RUN_MODE,
    CONF_RUN_ON_STARTUP,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    SUBENTRY_SWITCH,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ON_ACTIONS = [{"action": "test.on"}]
OFF_ACTIONS = [{"action": "test.off"}]
DEVICE_ACTIONS = [{"action": "test.on", "target": {"device_id": "abc123"}}]


@pytest.fixture
async def hub(hass: HomeAssistant, mqtt_mock, make_hub_entry):
    """Return a set-up hub entry so that update listeners run as they do in production."""
    entry = make_hub_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _start_switch_flow(hass: HomeAssistant, entry) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_SWITCH), context={"source": SOURCE_USER}
    )


def _switch_input(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "Lamp",
        CONF_ON_CHANGE_TO_ON: ON_ACTIONS,
        CONF_ON_CHANGE_TO_OFF: OFF_ACTIONS,
    }
    data.update(overrides)
    return data


def _suggested_values(result: dict[str, Any]) -> dict[str, Any]:
    """Return the suggested values a form result carries in its schema markers."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


# ---------------------------------------------------------------- hub flow


async def test_hub_flow_creates_entry_with_instance_id(hass: HomeAssistant, mqtt_mock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submitting nothing takes the schema defaults: base topic mqtt_actions, instance name = location name
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == hass.config.location_name
    assert result["data"][CONF_BASE_TOPIC] == DEFAULT_BASE_TOPIC == "mqtt_actions"
    assert result["data"][CONF_INSTANCE_NAME] == hass.config.location_name
    assert uuid.UUID(result["data"][CONF_INSTANCE_ID]).version == 4


async def test_hub_flow_trims_input(hass: HomeAssistant, mqtt_mock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BASE_TOPIC: "  home/actions ", CONF_INSTANCE_NAME: "  Living room  "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"][CONF_BASE_TOPIC] == "home/actions"
    assert result["data"][CONF_INSTANCE_NAME] == "Living room"


async def test_hub_flow_aborts_without_mqtt(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_required"


@pytest.mark.parametrize("bad_topic", ["home/#", "home/+/x", "/home", "home/", "a//b", "$SYS/x", "", "   "])
async def test_hub_flow_rejects_invalid_base_topic(hass: HomeAssistant, mqtt_mock, bad_topic: str) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BASE_TOPIC: bad_topic, CONF_INSTANCE_NAME: "Test instance"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base_topic": "invalid_base_topic"}
    assert _suggested_values(result)[CONF_INSTANCE_NAME] == "Test instance"
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_hub_flow_rejects_blank_instance_name(hass: HomeAssistant, mqtt_mock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BASE_TOPIC: "mqtt_actions", CONF_INSTANCE_NAME: "   "}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"instance_name": "instance_name_required"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_hub_flow_single_instance(hass: HomeAssistant, mqtt_mock, make_hub_entry) -> None:
    make_hub_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


def test_hub_flow_has_no_reconfigure_step() -> None:
    """The base topic is one-way (D-01), so there is no way to change it after setup."""
    assert not hasattr(MqttActionsConfigFlow, "async_step_reconfigure")


# ------------------------------------------------------------ switch flow


async def test_switch_flow_creates_subentry(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], _switch_input(name="  Lamp  "))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lamp"
    await hass.async_block_till_done(wait_background_tasks=True)

    (subentry,) = hub.subentries.values()
    assert subentry.title == "Lamp"
    assert uuid.UUID(subentry.data[CONF_DEVICE_ID]).version == 4
    assert subentry.unique_id == subentry.data[CONF_DEVICE_ID]
    assert subentry.data[CONF_ON_CHANGE_TO_ON] == ON_ACTIONS
    assert subentry.data[CONF_ON_CHANGE_TO_OFF] == OFF_ACTIONS
    assert subentry.data[CONF_RUN_ON_STARTUP] is False
    # RAW selector output: plain JSON, no Template objects
    json.dumps(dict(subentry.data))


async def test_switch_flow_stores_run_on_startup_when_set(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _switch_input(**{CONF_RUN_ON_STARTUP: True})
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    (subentry,) = hub.subentries.values()
    assert subentry.data[CONF_RUN_ON_STARTUP] is True


async def test_switch_flow_schema_serializes_action_selector(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    fields = {
        field["name"]: field
        for field in probatio.to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    }
    assert fields[CONF_ON_CHANGE_TO_ON]["selector"] == {"action": {}}
    assert fields[CONF_ON_CHANGE_TO_OFF]["selector"] == {"action": {}}
    assert fields[CONF_RUN_ON_STARTUP]["default"] is False


async def test_switch_flow_rejects_invalid_actions(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _switch_input(**{CONF_ON_CHANGE_TO_OFF: [{"bogus": 1}]})
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_actions"}
    placeholders = result["description_placeholders"]
    assert placeholders["field"] == "onChangeToOff"
    assert placeholders["error"]
    assert len(placeholders["error"]) <= 200
    assert len(hub.subentries) == 0


async def test_switch_flow_truncates_long_validation_errors(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _switch_input(**{CONF_ON_CHANGE_TO_ON: [{"x" * 500: 1}]})
    )
    assert result["errors"] == {"base": "invalid_actions"}
    assert result["description_placeholders"]["field"] == "onChangeToOn"
    assert len(result["description_placeholders"]["error"]) <= 200


async def test_switch_flow_rejects_blank_name(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], _switch_input(name="   "))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"name": "name_required"}
    assert len(hub.subentries) == 0


async def test_switch_flow_device_id_warns_then_saves_on_resubmit(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    flow_id = result["flow_id"]
    submitted = _switch_input(**{CONF_ON_CHANGE_TO_ON: DEVICE_ACTIONS})

    result = await hass.config_entries.subentries.async_configure(flow_id, submitted)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_id_warning"}
    assert result["description_placeholders"]["device_ids"] == "abc123"
    assert _suggested_values(result)["name"] == "Lamp"
    assert len(hub.subentries) == 0

    # A changed resubmit is a new input and warns again
    changed = _switch_input(
        **{CONF_ON_CHANGE_TO_ON: [{"action": "test.on", "target": {"device_id": ["abc123", "def456"]}}]}
    )
    result = await hass.config_entries.subentries.async_configure(flow_id, changed)
    assert result["errors"] == {"base": "device_id_warning"}
    assert result["description_placeholders"]["device_ids"] == "abc123, def456"
    assert len(hub.subentries) == 0

    # The identical resubmit saves
    result = await hass.config_entries.subentries.async_configure(flow_id, changed)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hub.subentries) == 1


async def test_switch_flow_entity_targets_do_not_warn(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _switch_input(**{CONF_ON_CHANGE_TO_ON: [{"action": "test.on", "target": {"entity_id": "light.a"}}]}),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def _reconfigure_flow(hass: HomeAssistant, entry, subentry) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_SWITCH),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )


@pytest.fixture
async def hub_with_switch(hass: HomeAssistant, mqtt_mock, make_hub_entry, make_switch_subentry):
    """Return a set-up hub entry that already owns one switch."""
    entry = make_hub_entry(subentries=[make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def test_switch_reconfigure_replaces_actions_and_keeps_device_id(hass: HomeAssistant, hub_with_switch) -> None:
    entry = hub_with_switch
    (subentry,) = entry.subentries.values()
    device_id = subentry.data[CONF_DEVICE_ID]
    unique_id = subentry.unique_id

    result = await _reconfigure_flow(hass, entry, subentry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    prefill = _suggested_values(result)
    assert prefill["name"] == "Lamp"
    assert prefill[CONF_ON_CHANGE_TO_ON] == ON_ACTIONS
    assert prefill[CONF_ON_CHANGE_TO_OFF] == OFF_ACTIONS

    new_on = [{"action": "test.other"}]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Desk lamp", CONF_ON_CHANGE_TO_ON: new_on, CONF_ON_CHANGE_TO_OFF: [], CONF_RUN_ON_STARTUP: True},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done(wait_background_tasks=True)

    (updated,) = entry.subentries.values()
    assert updated.subentry_id == subentry.subentry_id
    assert updated.title == "Desk lamp"
    assert updated.unique_id == unique_id
    assert updated.data[CONF_DEVICE_ID] == device_id
    assert updated.data[CONF_ON_CHANGE_TO_ON] == new_on
    # A cleared list stays cleared: replace, not merge
    assert updated.data[CONF_ON_CHANGE_TO_OFF] == []
    assert updated.data[CONF_RUN_ON_STARTUP] is True


async def test_switch_reconfigure_applies_validation_and_warning(hass: HomeAssistant, hub_with_switch) -> None:
    entry = hub_with_switch
    (subentry,) = entry.subentries.values()

    result = await _reconfigure_flow(hass, entry, subentry)
    flow_id = result["flow_id"]

    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"name": "Lamp", CONF_ON_CHANGE_TO_ON: [{"bogus": 1}], CONF_ON_CHANGE_TO_OFF: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_actions"}

    warned = {"name": "Lamp", CONF_ON_CHANGE_TO_ON: DEVICE_ACTIONS, CONF_ON_CHANGE_TO_OFF: []}
    result = await hass.config_entries.subentries.async_configure(flow_id, warned)
    assert result["errors"] == {"base": "device_id_warning"}
    assert entry.subentries[subentry.subentry_id].data[CONF_ON_CHANGE_TO_ON] == ON_ACTIONS

    result = await hass.config_entries.subentries.async_configure(flow_id, warned)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry.subentry_id].data[CONF_ON_CHANGE_TO_ON] == DEVICE_ACTIONS


# ------------------------------------------------------- run mode and breaker (DEV-06, STA-06, D-10, D-14)


async def test_switch_flow_stores_run_mode_and_breaker_settings(hass: HomeAssistant, hub) -> None:
    """The schema defaults apply when the fields are omitted; explicit values are stored as ints, not floats."""
    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], _switch_input())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    (subentry,) = hub.subentries.values()
    assert subentry.data[CONF_RUN_MODE] == "serial"
    assert (subentry.data[CONF_BREAKER_MAX_RUNS], subentry.data[CONF_BREAKER_WINDOW]) == (5, 10)
    assert isinstance(subentry.data[CONF_BREAKER_MAX_RUNS], int)
    assert isinstance(subentry.data[CONF_BREAKER_WINDOW], int)

    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _switch_input(name="Other", run_mode="restart", breaker_max_runs=3.0, breaker_window=30.0),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    other = next(subentry for subentry in hub.subentries.values() if subentry.title == "Other")
    assert other.data[CONF_RUN_MODE] == "restart"
    assert (other.data[CONF_BREAKER_MAX_RUNS], other.data[CONF_BREAKER_WINDOW]) == (3, 30)
    assert isinstance(other.data[CONF_BREAKER_MAX_RUNS], int)
    assert isinstance(other.data[CONF_BREAKER_WINDOW], int)
    json.dumps(dict(other.data))


@pytest.mark.parametrize(
    ("runs", "window", "errors"),
    [
        (0, 10, {"breaker_max_runs": "breaker_max_runs_range"}),
        (101, 10, {"breaker_max_runs": "breaker_max_runs_range"}),
        (5, 0, {"breaker_window": "breaker_window_range"}),
        (5, 3601, {"breaker_window": "breaker_window_range"}),
        (0, 3601, {"breaker_max_runs": "breaker_max_runs_range", "breaker_window": "breaker_window_range"}),
    ],
)
async def test_switch_flow_rejects_out_of_range_breaker_values(
    hass: HomeAssistant, hub, runs: int, window: int, errors: dict[str, str]
) -> None:
    result = await _start_switch_flow(hass, hub)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _switch_input(breaker_max_runs=runs, breaker_window=window)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    assert _suggested_values(result)["name"] == "Lamp"
    assert len(hub.subentries) == 0


async def test_switch_reconfigure_prefills_defaults_for_old_data(hass: HomeAssistant, hub_with_switch) -> None:
    """A Phase 1 switch has no run mode or breaker keys: the form shows the defaults and saving stores them."""
    entry = hub_with_switch
    (subentry,) = entry.subentries.values()
    assert CONF_RUN_MODE not in subentry.data

    result = await _reconfigure_flow(hass, entry, subentry)
    prefill = _suggested_values(result)
    assert prefill[CONF_RUN_MODE] == "serial"
    assert (prefill[CONF_BREAKER_MAX_RUNS], prefill[CONF_BREAKER_WINDOW]) == (5, 10)

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"name": "Lamp"})
    assert result["reason"] == "reconfigure_successful"
    (updated,) = entry.subentries.values()
    assert updated.data[CONF_RUN_MODE] == "serial"
    assert (updated.data[CONF_BREAKER_MAX_RUNS], updated.data[CONF_BREAKER_WINDOW]) == (5, 10)
    assert isinstance(updated.data[CONF_BREAKER_MAX_RUNS], int)


async def test_switch_reconfigure_stores_restart_and_breaker(hass: HomeAssistant, hub_with_switch) -> None:
    entry = hub_with_switch
    (subentry,) = entry.subentries.values()
    result = await _reconfigure_flow(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Lamp", "run_mode": "restart", "breaker_max_runs": 2.0, "breaker_window": 60.0}
    )
    assert result["reason"] == "reconfigure_successful"
    (updated,) = entry.subentries.values()
    assert updated.data[CONF_RUN_MODE] == "restart"
    assert (updated.data[CONF_BREAKER_MAX_RUNS], updated.data[CONF_BREAKER_WINDOW]) == (2, 60)


async def test_switch_flow_schema_serializes_new_selectors(hass: HomeAssistant, hub) -> None:
    result = await _start_switch_flow(hass, hub)
    fields = {
        field["name"]: field
        for field in probatio.to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    }
    run_mode = fields[CONF_RUN_MODE]
    assert run_mode["default"] == "serial"
    assert run_mode["selector"]["select"]["mode"] == "dropdown"
    assert run_mode["selector"]["select"]["translation_key"] == "run_mode"
    assert "number" in fields[CONF_BREAKER_MAX_RUNS]["selector"]
    assert fields[CONF_BREAKER_MAX_RUNS]["default"] == 5
    assert fields[CONF_BREAKER_WINDOW]["selector"]["number"]["unit_of_measurement"] == "s"
    assert fields[CONF_BREAKER_WINDOW]["default"] == 10
