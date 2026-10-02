"""Config-flow descriptions render as Markdown, so user text in their placeholders must be escaped (G-03-2, T-03-38)."""

from typing import TYPE_CHECKING, Any

import probatio
import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv

from custom_components.mqtt_actions.const import SUBENTRY_SELECT, SUBENTRY_SWITCH
from custom_components.mqtt_actions.document import escape_markdown

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

# The exact name from the UAT report, and a state value with the same hostile characters
HOSTILE_NAME = "UAT `bt` a_b_c | <b>fett</b>"
ESCAPED_NAME = r"UAT \`bt\` a\_b\_c \| \<b\>fett\</b\>"
HOSTILE_VALUE = "v_1 `x` | <i>y</i>"
ESCAPED_VALUE = r"v\_1 \`x\` \| \<i\>y\</i\>"


@pytest.fixture(params=[SUBENTRY_SWITCH, SUBENTRY_SELECT])
async def hostile_device_hub(
    request: pytest.FixtureRequest,
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
):
    """Return (entry, subentry type) of a set-up hub whose single device carries the hostile name."""
    if request.param == SUBENTRY_SWITCH:
        subentry = make_switch_subentry(HOSTILE_NAME, on=[{"action": "test.on"}], off=[{"action": "test.off"}])
    else:
        subentry = make_select_subentry(
            HOSTILE_NAME, [("a", "Alpha", [{"action": "test.a"}]), ("b", "Bravo", [{"action": "test.b"}])]
        )
    entry = make_hub_entry(subentries=[subentry])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry, request.param


@pytest.fixture
async def hostile_select_hub(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
):
    """Return a set-up hub whose Select device and first option carry the hostile texts."""
    options = [
        (HOSTILE_VALUE, HOSTILE_NAME, [{"action": "test.a"}]),
        ("b", "Bravo", [{"action": "test.b"}]),
        ("c", "Charlie", [{"action": "test.c"}]),
    ]
    entry = make_hub_entry(subentries=[make_select_subentry(HOSTILE_NAME, options)])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _reconfigure(hass: HomeAssistant, entry: Any, subentry_type: str) -> dict[str, Any]:
    (subentry,) = entry.subentries.values()
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, subentry_type),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )


async def _choose(hass: HomeAssistant, result: dict[str, Any], step: str) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_configure(result["flow_id"], {"next_step_id": step})


def test_expected_constants_match_escape_markdown() -> None:
    """Pin the hand-written expectations to the real function, so a wrong constant fails here and not in a flow test."""
    assert escape_markdown(HOSTILE_NAME) == ESCAPED_NAME
    assert escape_markdown(HOSTILE_VALUE) == ESCAPED_VALUE


async def test_delete_confirmation_shows_the_device_name_as_plain_text(
    hass: HomeAssistant, hostile_device_hub: tuple[Any, str]
) -> None:
    """G-03-2, D-16, SYN-06: the delete confirmation of either device type escapes the name it shows."""
    entry, subentry_type = hostile_device_hub

    result = await _reconfigure(hass, entry, subentry_type)
    result = await _choose(hass, result, "delete_device")

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "delete_device"
    assert result["description_placeholders"] == {"name": ESCAPED_NAME, "count": "0"}


# ------------------------------------------------------------------------------------------------- select dialogs


async def _configure(hass: HomeAssistant, result: dict[str, Any], user_input: dict[str, Any]) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)


async def _menu(hass: HomeAssistant, result: dict[str, Any], step: str) -> dict[str, Any]:
    return await _configure(hass, result, {"next_step_id": step})


def _fields(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        field["name"]: field
        for field in probatio.to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    }


async def test_select_menu_escapes_the_name_and_every_option_line(hass: HomeAssistant, hostile_select_hub: Any) -> None:
    """G-03-2: the menu shows the name and both parts of each option line literally; the list structure stays."""
    result = await _reconfigure(hass, hostile_select_hub, SUBENTRY_SELECT)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"
    placeholders = result["description_placeholders"]
    assert placeholders["name"] == ESCAPED_NAME
    assert placeholders["count"] == "3"
    assert placeholders["options"] == "\n".join([f"- {ESCAPED_NAME} ({ESCAPED_VALUE})", "- Bravo (b)", "- Charlie (c)"])


async def test_remove_confirmation_escapes_friendly_name_and_state_value(
    hass: HomeAssistant, hostile_select_hub: Any
) -> None:
    """G-03-2: the option removal confirmation shows the friendly name and the state value literally."""
    result = await _reconfigure(hass, hostile_select_hub, SUBENTRY_SELECT)
    chooser = await _menu(hass, result, "remove_option")
    assert chooser["type"] is FlowResultType.FORM

    confirm = await _configure(hass, chooser, {"option": HOSTILE_VALUE})

    assert confirm["type"] is FlowResultType.MENU
    assert confirm["step_id"] == "remove_confirm"
    assert confirm["description_placeholders"] == {"friendly_name": ESCAPED_NAME, "state_value": ESCAPED_VALUE}


async def test_edit_option_details_escapes_the_state_value(hass: HomeAssistant, hostile_select_hub: Any) -> None:
    """G-03-2: the option edit form shows the state value literally in its description."""
    result = await _reconfigure(hass, hostile_select_hub, SUBENTRY_SELECT)
    chooser = await _menu(hass, result, "edit_option")
    assert chooser["type"] is FlowResultType.FORM

    details = await _configure(hass, chooser, {"option": HOSTILE_VALUE})

    assert details["type"] is FlowResultType.FORM
    assert details["step_id"] == "edit_option_details"
    assert details["description_placeholders"]["state_value"] == ESCAPED_VALUE


async def test_option_chooser_labels_stay_plain_text(hass: HomeAssistant, hostile_select_hub: Any) -> None:
    """Over-escaping guard: the chooser widget renders plain text, so its labels keep the raw texts."""
    result = await _reconfigure(hass, hostile_select_hub, SUBENTRY_SELECT)
    chooser = await _menu(hass, result, "edit_option")

    options = _fields(chooser)["option"]["selector"]["select"]["options"]

    assert [option["value"] for option in options] == [HOSTILE_VALUE, "b", "c"]
    assert [option["label"] for option in options] == [HOSTILE_NAME, "Bravo", "Charlie"]
