"""Select subentry flow: creation, option validation, menu visibility and the never-stored-before-done rule."""

import json
import uuid
from typing import TYPE_CHECKING, Any

import probatio
import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_ACTIONS,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_OPTIONS,
    CONF_RUN_MODE,
    CONF_RUN_ON_STARTUP,
    CONF_STATE_VALUE,
    MAX_OPTIONS,
    MAX_TEXT_LENGTH,
    SUBENTRY_SELECT,
)
from custom_components.mqtt_actions.topics import discovery_topic, state_topic

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ACTIONS_A = [{"action": "test.a"}]
ACTIONS_B = [{"action": "test.b"}]
DEVICE_ACTIONS = [{"action": "test.a", "target": {"device_id": "abc123"}}]


@pytest.fixture
async def hub(hass: HomeAssistant, mqtt_mock, make_hub_entry):
    """Return a set-up hub entry so that update listeners run as they do in production."""
    entry = make_hub_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _start(hass: HomeAssistant, entry) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_SELECT), context={"source": SOURCE_USER}
    )


async def _configure(hass: HomeAssistant, result: dict[str, Any], user_input: dict[str, Any]) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)


async def _menu(hass: HomeAssistant, result: dict[str, Any], step: str) -> dict[str, Any]:
    return await _configure(hass, result, {"next_step_id": step})


def _settings(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"name": "Mode"}
    data.update(overrides)
    return data


def _option(value: str, friendly: str, actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {CONF_STATE_VALUE: value, CONF_FRIENDLY_NAME: friendly, CONF_ACTIONS: actions or []}


async def _add(hass: HomeAssistant, result: dict[str, Any], option: dict[str, Any]) -> dict[str, Any]:
    """Open the add form from the menu and submit one option; return the next flow result."""
    form = await _menu(hass, result, "add_option")
    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "add_option"
    return await _configure(hass, form, option)


async def _menu_with_two_options(hass: HomeAssistant, hub) -> dict[str, Any]:
    result = await _start(hass, hub)
    result = await _configure(hass, result, _settings())
    result = await _add(hass, result, _option("a", "Alpha", ACTIONS_A))
    return await _add(hass, result, _option("b", "Bravo", ACTIONS_B))


def _suggested_values(result: dict[str, Any]) -> dict[str, Any]:
    """Return the suggested values a form result carries in its schema markers."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


def _fields(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        field["name"]: field
        for field in probatio.to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    }


# ------------------------------------------------------------------------------------------------- tracer


async def test_tracer_select_flow_creates_two_option_device_that_runs_actions(
    hass: HomeAssistant, hub, mqtt_mock
) -> None:
    """DEV-03, D-01, D-04: settings, an option menu, Done only from two options, and the device runs its actions."""
    calls_a = async_mock_service(hass, "test", "a")
    calls_b = async_mock_service(hass, "test", "b")

    result = await _start(hass, hub)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _configure(hass, result, _settings(name="  Mode  "))
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"
    assert "add_option" in result["menu_options"]
    assert "settings" in result["menu_options"]
    assert "done" not in result["menu_options"]

    result = await _add(hass, result, _option("a", "Alpha", ACTIONS_A))
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"
    assert "done" not in result["menu_options"]

    result = await _add(hass, result, _option("b", "Bravo", ACTIONS_B))
    assert result["type"] is FlowResultType.MENU
    assert "done" in result["menu_options"]

    result = await _menu(hass, result, "done")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mode"
    await hass.async_block_till_done(wait_background_tasks=True)

    (subentry,) = hub.subentries.values()
    assert subentry.subentry_type == SUBENTRY_SELECT
    assert subentry.title == "Mode"
    assert uuid.UUID(subentry.data[CONF_DEVICE_ID]).version == 4
    assert subentry.unique_id == subentry.data[CONF_DEVICE_ID]
    assert subentry.data[CONF_OPTIONS] == [_option("a", "Alpha", ACTIONS_A), _option("b", "Bravo", ACTIONS_B)]
    assert subentry.data[CONF_RUN_MODE] == "serial"
    assert subentry.data[CONF_BREAKER_MAX_RUNS] == 5
    assert subentry.data[CONF_BREAKER_WINDOW] == 10
    assert type(subentry.data[CONF_BREAKER_MAX_RUNS]) is int
    assert type(subentry.data[CONF_BREAKER_WINDOW]) is int
    assert subentry.data[CONF_RUN_ON_STARTUP] is False
    # RAW selector output: plain JSON, no Template objects
    json.dumps(dict(subentry.data))

    device_id = subentry.data[CONF_DEVICE_ID]
    async_fire_mqtt_message(hass, state_topic("mqtt_actions", device_id), "b")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (len(calls_a), len(calls_b)) == (0, 1)

    published = [
        call.args[1]
        for call in mqtt_mock.async_publish.call_args_list
        if call.args[0] == discovery_topic("homeassistant", device_id)
    ]
    payload = json.loads(published[-1])
    assert payload["components"]["select"]["options"] == ["Alpha", "Bravo"]


async def test_select_flow_schema_serializes_selectors(hass: HomeAssistant, hub) -> None:
    result = await _start(hass, hub)
    settings_fields = _fields(result)
    assert settings_fields[CONF_RUN_MODE]["selector"]["select"]["translation_key"] == "run_mode"
    assert settings_fields[CONF_RUN_MODE]["selector"]["select"]["mode"] == "dropdown"
    assert settings_fields[CONF_RUN_MODE]["default"] == "serial"
    assert "number" in settings_fields[CONF_BREAKER_MAX_RUNS]["selector"]
    assert settings_fields[CONF_BREAKER_MAX_RUNS]["default"] == 5
    assert settings_fields[CONF_BREAKER_WINDOW]["selector"]["number"]["unit_of_measurement"] == "s"
    assert settings_fields[CONF_BREAKER_WINDOW]["default"] == 10
    assert settings_fields[CONF_RUN_ON_STARTUP]["default"] is False

    result = await _configure(hass, result, _settings())
    form = await _menu(hass, result, "add_option")
    assert _fields(form)[CONF_ACTIONS]["selector"] == {"action": {}}


# ------------------------------------------------------------------------------------- settings validation


async def test_select_flow_settings_validation(hass: HomeAssistant, hub) -> None:
    result = await _start(hass, hub)

    blank = await _configure(hass, result, _settings(name="   "))
    assert blank["type"] is FlowResultType.FORM
    assert blank["errors"] == {"name": "name_required"}

    for runs, window, errors in (
        (0, 10, {"breaker_max_runs": "breaker_max_runs_range"}),
        (101, 10, {"breaker_max_runs": "breaker_max_runs_range"}),
        (5, 0, {"breaker_window": "breaker_window_range"}),
        (5, 3601, {"breaker_window": "breaker_window_range"}),
        (0, 0, {"breaker_max_runs": "breaker_max_runs_range", "breaker_window": "breaker_window_range"}),
    ):
        rejected = await _configure(hass, result, _settings(breaker_max_runs=runs, breaker_window=window))
        assert rejected["type"] is FlowResultType.FORM
        assert rejected["step_id"] == "user"
        assert rejected["errors"] == errors
        assert _suggested_values(rejected)["name"] == "Mode"
    assert len(hub.subentries) == 0


async def test_select_flow_stores_settings_as_ints(hass: HomeAssistant, hub) -> None:
    """D-10, D-14: the number selector returns floats; the stored values are ints."""
    result = await _start(hass, hub)
    result = await _configure(
        hass,
        result,
        _settings(run_mode="restart", breaker_max_runs=7.0, breaker_window=30.0, run_on_startup=True),
    )
    result = await _add(hass, result, _option("a", "Alpha"))
    result = await _add(hass, result, _option("b", "Bravo"))
    result = await _menu(hass, result, "done")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)

    (subentry,) = hub.subentries.values()
    assert subentry.data[CONF_RUN_MODE] == "restart"
    assert subentry.data[CONF_BREAKER_MAX_RUNS] == 7
    assert subentry.data[CONF_BREAKER_WINDOW] == 30
    assert type(subentry.data[CONF_BREAKER_MAX_RUNS]) is int
    assert type(subentry.data[CONF_BREAKER_WINDOW]) is int
    assert subentry.data[CONF_RUN_ON_STARTUP] is True


async def test_settings_from_the_menu_update_the_draft(hass: HomeAssistant, hub) -> None:
    result = await _start(hass, hub)
    result = await _configure(hass, result, _settings(breaker_max_runs=9))

    form = await _menu(hass, result, "settings")
    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "settings"
    prefill = _suggested_values(form)
    assert (prefill["name"], prefill[CONF_BREAKER_MAX_RUNS]) == ("Mode", 9)

    result = await _configure(hass, form, _settings(name="Renamed", run_mode="restart"))
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"
    assert result["description_placeholders"]["name"] == "Renamed"


# ---------------------------------------------------------------------------------------- add option rules


@pytest.mark.parametrize(
    ("option", "errors"),
    [
        (_option("", "Alpha"), {"state_value": "state_value_required"}),
        (_option(" a", "Alpha"), {"state_value": "state_value_invalid"}),
        (_option("a ", "Alpha"), {"state_value": "state_value_invalid"}),
        (_option("a\tb", "Alpha"), {"state_value": "state_value_invalid"}),
        (_option("x" * (MAX_TEXT_LENGTH + 1), "Alpha"), {"state_value": "state_value_invalid"}),
        (_option("EXISTING", "Alpha"), {"state_value": "state_value_duplicate"}),
        (_option("a", ""), {"friendly_name": "friendly_name_required"}),
        (_option("a", "   "), {"friendly_name": "friendly_name_required"}),
        (_option("a", "None"), {"friendly_name": "friendly_name_reserved"}),
        (_option("a", " none "), {"friendly_name": "friendly_name_reserved"}),
        (_option("a", "x" * (MAX_TEXT_LENGTH + 1)), {"friendly_name": "friendly_name_invalid"}),
        (_option("a", "Al\x00pha"), {"friendly_name": "friendly_name_invalid"}),
        (_option("a", "  existing name "), {"friendly_name": "friendly_name_duplicate"}),
        (
            _option("existing", "Existing Name"),
            {"state_value": "state_value_duplicate", "friendly_name": "friendly_name_duplicate"},
        ),
    ],
)
async def test_add_option_validation(hass: HomeAssistant, hub, option: dict[str, Any], errors: dict[str, str]) -> None:
    """D-04: an invalid option leaves the draft unchanged and the form shows the error on the field."""
    result = await _start(hass, hub)
    result = await _configure(hass, result, _settings())
    result = await _add(hass, result, _option("existing", "Existing Name"))

    form = await _menu(hass, result, "add_option")
    rejected = await _configure(hass, form, option)
    assert rejected["type"] is FlowResultType.FORM
    assert rejected["step_id"] == "add_option"
    assert rejected["errors"] == errors
    suggested = _suggested_values(rejected)
    assert suggested[CONF_STATE_VALUE] == option[CONF_STATE_VALUE]
    assert suggested[CONF_FRIENDLY_NAME] == option[CONF_FRIENDLY_NAME]

    # The draft is unchanged: after a valid second option there are exactly two options
    accepted = await _configure(hass, rejected, _option("other", "Other Name"))
    assert accepted["type"] is FlowResultType.MENU
    assert accepted["description_placeholders"]["count"] == "2"


async def test_add_option_stores_friendly_name_stripped(hass: HomeAssistant, hub) -> None:
    result = await _start(hass, hub)
    result = await _configure(hass, result, _settings())
    result = await _add(hass, result, _option("a", "  Alpha  "))
    result = await _add(hass, result, _option("b", "Bravo"))
    result = await _menu(hass, result, "done")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    (subentry,) = hub.subentries.values()
    assert subentry.data[CONF_OPTIONS][0][CONF_FRIENDLY_NAME] == "Alpha"


async def test_add_option_invalid_actions_and_device_id_warning(hass: HomeAssistant, hub) -> None:
    result = await _start(hass, hub)
    result = await _configure(hass, result, _settings())
    form = await _menu(hass, result, "add_option")

    invalid = await _configure(hass, form, _option("a", "Alpha", [{"bogus": 1}]))
    assert invalid["type"] is FlowResultType.FORM
    assert invalid["errors"] == {"base": "invalid_actions"}
    assert invalid["description_placeholders"]["field"] == "Alpha"
    assert 0 < len(invalid["description_placeholders"]["error"]) <= 200

    long = await _configure(hass, invalid, _option("a", "Alpha", [{"x" * 500: 1}]))
    assert long["errors"] == {"base": "invalid_actions"}
    assert len(long["description_placeholders"]["error"]) <= 200

    warned = _option("a", "Alpha", DEVICE_ACTIONS)
    warning = await _configure(hass, long, warned)
    assert warning["errors"] == {"base": "device_id_warning"}
    assert warning["description_placeholders"]["device_ids"] == "abc123"

    saved = await _configure(hass, warning, warned)
    assert saved["type"] is FlowResultType.MENU
    assert saved["description_placeholders"]["count"] == "1"

    entity = await _add(hass, saved, _option("b", "Bravo", [{"action": "test.b", "target": {"entity_id": "light.a"}}]))
    assert entity["type"] is FlowResultType.MENU
    assert entity["description_placeholders"]["count"] == "2"


# --------------------------------------------------------------------------------------- menu visibility


async def test_menu_visibility(hass: HomeAssistant, hub) -> None:
    """D-04, A1: Done needs two options and Add disappears at the option cap."""
    result = await _start(hass, hub)
    result = await _configure(hass, result, _settings())
    counts: dict[int, list[str]] = {}
    for index in range(MAX_OPTIONS):
        result = await _add(hass, result, _option(f"v{index}", f"Name {index}"))
        assert result["type"] is FlowResultType.MENU
        counts[index + 1] = result["menu_options"]

    assert "done" not in counts[1]
    assert "done" in counts[2]
    assert "add_option" in counts[MAX_OPTIONS - 1]
    assert "add_option" not in counts[MAX_OPTIONS]
    assert "done" in counts[MAX_OPTIONS]
    assert "settings" in counts[MAX_OPTIONS]


async def test_nothing_is_stored_before_done(hass: HomeAssistant, hub) -> None:
    result = await _start(hass, hub)
    assert len(hub.subentries) == 0
    result = await _configure(hass, result, _settings())
    assert len(hub.subentries) == 0
    result = await _add(hass, result, _option("a", "Alpha"))
    result = await _add(hass, result, _option("b", "Bravo"))
    form = await _menu(hass, result, "settings")
    result = await _configure(hass, form, _settings(name="Renamed"))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hub.subentries) == 0

    result = await _menu(hass, result, "done")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hub.subentries) == 1
