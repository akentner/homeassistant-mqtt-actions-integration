"""Select discovery: payload shape, mapping templates with hostile strings and the real core MQTT round trip."""

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.template import Template
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import discovery, state
from custom_components.mqtt_actions.const import (
    CONF_ACTIONS,
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_OPTIONS,
    CONF_STATE_VALUE,
    SUBENTRY_SELECT,
)
from custom_components.mqtt_actions.model import DeviceSpec, spec_from_data
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from homeassistant.core import HomeAssistant

BASE_TOPIC = "mqtt_actions"
INSTANCE_ID = "inst-1"
DEVICE_ID = "dev-1"
STATE_TOPIC = state_topic(BASE_TOPIC, DEVICE_ID)

# (StateValue, friendly name) pairs that would break a naive template builder
HOSTILE_OPTIONS = [
    ("on", "Aan"),
    ('q"uote', "Fri'end\\ly"),
    ("{{ 1+1 }}", "{% if x %}"),
    ("{# c #}", "}} {{"),
    ("emoji \U0001f600", "Ünï \U0001f600 名前"),
    ("back\\slash", "tab\there"),
    ("Mixed Case", "Mixed"),
]


def _spec(options: Sequence[tuple[str, str]], name: str = "Mode") -> DeviceSpec:
    """Build a Select spec from (StateValue, friendly name) pairs."""
    data = {
        CONF_DEVICE_ID: DEVICE_ID,
        CONF_OPTIONS: [
            {CONF_STATE_VALUE: value, CONF_FRIENDLY_NAME: friendly, CONF_ACTIONS: []} for value, friendly in options
        ],
    }
    return spec_from_data(SUBENTRY_SELECT, name, data)


def _payload(spec: DeviceSpec) -> dict[str, Any]:
    return discovery.build_discovery(spec=spec, base_topic=BASE_TOPIC, instance_id=INSTANCE_ID, sw_version="1.2.3")


def _render(hass: HomeAssistant, template: str, value: str) -> str:
    """Render a template with the payload as `value`, the way core MQTT feeds it."""
    return Template(template, hass).async_render({"value": value}, parse_result=False)


def _templates(options: Sequence[tuple[str, str]]) -> tuple[str, str]:
    spec = _spec(options)
    select = _payload(spec)["components"]["select"]
    return select["value_template"], select["command_template"]


async def _discover(hass: HomeAssistant, spec: DeviceSpec) -> None:
    """Deliver the discovery payload of a spec to core MQTT and mark the instance online."""
    async_fire_mqtt_message(hass, discovery_topic("homeassistant", DEVICE_ID), json_dumps(_payload(spec)))
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, availability_topic(BASE_TOPIC, INSTANCE_ID), "online", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _send(hass: HomeAssistant, payload: str) -> None:
    async_fire_mqtt_message(hass, STATE_TOPIC, payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


# --- payload shape ------------------------------------------------------------------------------------------------


def test_build_discovery_select_component() -> None:
    """D-05, D-07: one select component, options are the friendly names in creation order, templates are strings."""
    spec = _spec([("a", "Alpha"), ("b", "Bravo"), ("c", "Charlie")])

    payload = _payload(spec)

    # One test button per option follows the select (D-13); their shape is pinned in tests/test_test_buttons.py
    assert next(iter(payload["components"])) == "select"
    assert len(payload["components"]) == 4
    select = payload["components"]["select"]
    assert select["platform"] == "select"
    assert select["unique_id"] == DEVICE_ID
    assert select["name"] is None
    assert select["state_topic"] == select["command_topic"] == STATE_TOPIC
    assert select["retain"] is True
    assert select["qos"] == 1
    assert select["options"] == ["Alpha", "Bravo", "Charlie"]
    assert isinstance(select["value_template"], str)
    assert isinstance(select["command_template"], str)
    assert payload["device"] == {"identifiers": ["mqtt_actions_dev-1"], "name": "Mode"}
    assert payload["availability"] == [{"topic": availability_topic(BASE_TOPIC, INSTANCE_ID)}]
    assert json.loads(json.dumps(payload)) == payload


# --- mapping templates with hostile strings (T-02-01) ---------------------------------------------------------------


@pytest.mark.parametrize(("value", "friendly"), HOSTILE_OPTIONS)
async def test_value_template_maps_hostile_strings(hass: HomeAssistant, value: str, friendly: str) -> None:
    """The value template maps a padded, upper-cased StateValue to its friendly name and unknown payloads to empty."""
    value_template, _command = _templates(HOSTILE_OPTIONS)

    assert _render(hass, value_template, f"  {value.upper()}\n") == friendly
    for unknown in ("nope", "", "none", "None"):
        assert _render(hass, value_template, unknown) == ""


@pytest.mark.parametrize(("value", "friendly"), HOSTILE_OPTIONS)
async def test_command_template_maps_hostile_strings(hass: HomeAssistant, value: str, friendly: str) -> None:
    """The command template maps a friendly name to the exact StateValue; an unknown option passes through."""
    _value, command_template = _templates(HOSTILE_OPTIONS)

    assert _render(hass, command_template, friendly) == value
    assert _render(hass, command_template, "not an option") == "not an option"


@pytest.mark.parametrize("payload", ["Aan", " aan ", "AAN\n", "\taan", "aan\N{NO-BREAK SPACE}", "AaN", "aa", ""])
async def test_template_and_tracker_normalize_identically(hass: HomeAssistant, payload: str) -> None:
    """Research pitfall 11: the entity and the tracker accept the same payloads and pick the same option."""
    options = [("Aan", "Een"), ("Uit", "Twee")]
    spec = _spec(options)
    value_template, _command = _templates(options)
    friendly_by_value = dict(options)

    rendered = _render(hass, value_template, payload)
    decision = state.decide(False, payload, None, False, False, accepted=spec.accepted)

    assert (rendered != "") is (not decision.ignored)
    if not decision.ignored:
        assert decision.value is not None
        assert rendered == friendly_by_value[decision.value]


# --- real core MQTT discovery ---------------------------------------------------------------------------------------


async def test_select_entity_options_and_state_round_trip(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """Core builds the select from the payload: the broker StateValue shows as the friendly name and back (D-06)."""
    await _discover(hass, _spec(HOSTILE_OPTIONS))

    entity = hass.states.get("select.mode")
    assert entity is not None
    assert entity.attributes["options"] == [friendly for _value, friendly in HOSTILE_OPTIONS]
    for value, friendly in HOSTILE_OPTIONS:
        await _send(hass, f"  {value.upper()}\n")
        assert hass.states.get("select.mode").state == friendly

    mqtt_mock.async_publish.reset_mock()
    for _value, friendly in HOSTILE_OPTIONS:
        await hass.services.async_call(
            "select", "select_option", {"entity_id": "select.mode", "option": friendly}, blocking=True
        )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _publishes(mqtt_mock, STATE_TOPIC) == [(value, 1, True) for value, _friendly in HOSTILE_OPTIONS]


async def test_select_unknown_payload_keeps_state_without_core_warning(
    hass: HomeAssistant, mqtt_mock: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """STA-07: payloads the mapping does not know leave the entity state alone and core logs no warning."""
    await _discover(hass, _spec([("a", "Alpha"), ("b", "Bravo")]))
    await _send(hass, "b")
    assert hass.states.get("select.mode").state == "Bravo"

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        for unknown in ("nope", "", "none", "None"):
            await _send(hass, unknown)
            assert hass.states.get("select.mode").state == "Bravo"

    assert [record for record in caplog.records if record.levelno >= logging.WARNING] == []


async def test_select_rename_and_remove_current_option_show_unknown(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """Open question 1: renaming or removing the selected option leaves the entity unknown until the next payload."""
    await _discover(hass, _spec([("a", "Alpha"), ("b", "Bravo")]))
    await _send(hass, "b")
    assert hass.states.get("select.mode").state == "Bravo"

    await _discover(hass, _spec([("a", "Alpha"), ("b", "Bravo 2")]))
    assert hass.states.get("select.mode").state == "unknown"
    await _send(hass, "a")
    assert hass.states.get("select.mode").state == "Alpha"
    await _send(hass, "b")
    assert hass.states.get("select.mode").state == "Bravo 2"

    await _discover(hass, _spec([("a", "Alpha"), ("c", "Charlie")]))
    assert hass.states.get("select.mode").state == "unknown"
    await _send(hass, "c")
    assert hass.states.get("select.mode").state == "Charlie"


async def test_select_device_publishes_select_discovery_through_manager(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """Setting up a hub with a Select subentry publishes one retained discovery with a select and no switch."""
    sub = make_select_subentry("Mode", [("a", "Alpha", []), ("b", "Bravo", [])])
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    device_id = sub["data"][CONF_DEVICE_ID]

    ((payload, qos, retain),) = _publishes(mqtt_mock, discovery_topic("homeassistant", device_id))

    components = json.loads(payload)["components"]
    assert [key for key, component in components.items() if component["platform"] == "select"] == ["select"]
    assert [component["platform"] for component in components.values()].count("switch") == 0
    assert components["select"]["options"] == ["Alpha", "Bravo"]
    assert (qos, retain) == (1, True)
    assert hass.states.get("select.mode") is not None
