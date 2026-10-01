"""Config-flow descriptions render as Markdown, so user text in their placeholders must be escaped (G-03-2, T-03-38)."""

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.data_entry_flow import FlowResultType

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
