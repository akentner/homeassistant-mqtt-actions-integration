"""Test buttons (DEV-07, D-13): discovery payload, press handling and run variable."""

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.components import mqtt
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions import discovery, topics
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_OPTIONS,
    CONF_STATE_VALUE,
    DOMAIN,
    ISSUE_ACTION_FAILED_PREFIX,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY, spec_from_data, trigger_key
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant, ServiceCall
    from pytest_homeassistant_custom_component.common import MockConfigEntry

BASE_TOPIC = "mqtt_actions"
INSTANCE_ID = "inst-1"
DEVICE_ID = "dev-1"

# The run variable `test` is written into the service data so a recorder service can tell the two run kinds apart
ON_ACTIONS = [{"action": "test.on", "data": {"test": "{{ test }}"}}]
OFF_ACTIONS = [{"action": "test.off", "data": {"test": "{{ test }}"}}]
FAIL_ACTIONS = [{"action": "test.fail"}]

ABC_OPTIONS = [
    ("a", "Alpha", [{"action": "test.a", "data": {"test": "{{ test }}"}}]),
    ("b", "Bravo", [{"action": "test.b", "data": {"test": "{{ test }}"}}]),
    ("c", "Charlie", [{"action": "test.c", "data": {"test": "{{ test }}"}}]),
]


def _switch_spec() -> Any:
    return spec_from_data(SUBENTRY_SWITCH, "Lamp", {CONF_DEVICE_ID: DEVICE_ID})


def _select_spec(options: list[tuple[str, str]]) -> Any:
    data = {
        CONF_DEVICE_ID: DEVICE_ID,
        CONF_OPTIONS: [{CONF_STATE_VALUE: value, CONF_FRIENDLY_NAME: friendly} for value, friendly in options],
    }
    return spec_from_data(SUBENTRY_SELECT, "Mode", data)


def _payload(spec: Any) -> dict[str, Any]:
    return discovery.build_discovery(spec=spec, base_topic=BASE_TOPIC, instance_id=INSTANCE_ID, sw_version="1.2.3")


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


async def _fire(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payload: str, *, retain: bool) -> None:
    async_fire_mqtt_message(hass, state_topic(entry.data["base_topic"], device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _press(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = False) -> None:
    """Deliver one message to the test topic of a device the way the broker forwards a button press."""
    async_fire_mqtt_message(hass, topics.test_topic(BASE_TOPIC, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


async def _deliver_discovery(hass: HomeAssistant, mqtt_mock: Any, entry: MockConfigEntry, device_id: str) -> None:
    """Feed the discovery payload the manager published to core MQTT, like a broker does, and mark it online."""
    topic = discovery_topic("homeassistant", device_id)
    published = _publishes(mqtt_mock, topic)[-1][0]
    async_fire_mqtt_message(hass, topic, published)
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, availability_topic(BASE_TOPIC, entry.data["instance_id"]), "online", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _button_entity_id(hass: HomeAssistant, device_id: str, key: str) -> str | None:
    """Find a button in the entity registry by its unique id, never by entity id."""
    return er.async_get(hass).async_get_entity_id("button", "mqtt", f"{device_id}_test_{key}")


def _register_failing_service(hass: HomeAssistant, message: str = "boom") -> None:
    async def _handler(call: ServiceCall) -> None:
        raise HomeAssistantError(message)

    hass.services.async_register("test", "fail", _handler)


def _issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}")


# --- payload shape ------------------------------------------------------------------------------------------------


def test_switch_discovery_has_two_test_buttons() -> None:
    """D-13: the Switch payload keeps its switch and gains Test ON and Test OFF buttons on the test topic."""
    payload = _payload(_switch_spec())

    on_key = discovery.button_component_key(SWITCH_ON_KEY)
    off_key = discovery.button_component_key(SWITCH_OFF_KEY)
    assert list(payload["components"]) == ["switch", on_key, off_key]
    assert payload["components"]["switch"]["platform"] == "switch"
    for key, trigger_hash, name, press in (
        (on_key, SWITCH_ON_KEY, "Test ON", "ON"),
        (off_key, SWITCH_OFF_KEY, "Test OFF", "OFF"),
    ):
        assert payload["components"][key] == {
            "platform": "button",
            "unique_id": f"{DEVICE_ID}_test_{trigger_hash}",
            "name": name,
            "command_topic": topics.test_topic(BASE_TOPIC, DEVICE_ID),
            "payload_press": press,
            "retain": False,
            "qos": 1,
            "entity_category": "config",
        }
    assert json.loads(json.dumps(payload)) == payload


def test_select_discovery_has_one_test_button_per_option_in_order() -> None:
    """One button per option in creation order, pressing publishes the StateValue exactly as created."""
    options = [("Mixed Case", "Mixed"), ("b", "Bravo"), ("c", "Charlie")]
    payload = _payload(_select_spec(options))

    expected = [discovery.button_component_key(trigger_key(value)) for value, _friendly in options]
    assert list(payload["components"]) == ["select", *expected]
    for key, (value, friendly) in zip(expected, options, strict=True):
        button = payload["components"][key]
        assert button["platform"] == "button"
        assert button["name"] == f"Test {friendly}"
        assert button["payload_press"] == value
        assert button["unique_id"] == f"{DEVICE_ID}_test_{trigger_key(value)}"


# --- real core discovery and press --------------------------------------------------------------------------------


async def test_buttons_are_created_and_press_publishes_payload_on_test_topic(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Core creates the buttons; the press service publishes exactly the StateValue, qos 1, not retained."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)

    on_button = _button_entity_id(hass, device_id, SWITCH_ON_KEY)
    off_button = _button_entity_id(hass, device_id, SWITCH_OFF_KEY)
    assert on_button is not None
    assert off_button is not None

    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call("button", "press", {"entity_id": on_button}, blocking=True)
    await hass.services.async_call("button", "press", {"entity_id": off_button}, blocking=True)

    assert _publishes(mqtt_mock, topics.test_topic(BASE_TOPIC, device_id)) == [("ON", 1, False), ("OFF", 1, False)]


# --- press handling -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prior", [None, "ON"])
async def test_press_runs_only_that_triggers_actions_locally(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable, prior: str | None
) -> None:
    """D-13: a press runs the OFF actions once with test true and touches no state, baseline or state topic."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)
    if prior is not None:
        # A retained message sets the baseline and closes the startup window without running anything
        await _fire(hass, entry, device_id, prior, retain=True)
    tracker = entry.runtime_data.devices[device_id].tracker
    before = (tracker.last_acted, tracker.startup_pending, hass.states.get("switch.lamp").state)
    mqtt_mock.async_publish.reset_mock()

    await _press(hass, device_id, "OFF")

    assert len(off_calls) == 1
    assert off_calls[0].data["test"] is True
    assert len(on_calls) == 0
    assert _publishes(mqtt_mock, state_topic(BASE_TOPIC, device_id)) == []
    assert (tracker.last_acted, tracker.startup_pending, hass.states.get("switch.lamp").state) == before


async def test_state_driven_run_has_test_variable_false(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A live state edge runs the same actions with test false, so templates can rely on the variable."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    assert len(on_calls) == 1
    assert on_calls[0].data["test"] is False


async def test_select_press_runs_that_options_actions(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """A Select test message is normalized like a state payload: whitespace and case do not matter."""
    calls = {name: async_mock_service(hass, "test", name) for name in ("a", "b", "c")}
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)

    await _press(hass, device_id, " B ")

    assert (len(calls["a"]), len(calls["b"]), len(calls["c"])) == (0, 1, 0)
    assert calls["b"][0].data["test"] is True
    assert entry.runtime_data.devices[device_id].tracker.last_acted is None


async def test_retained_test_message_is_ignored(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Threat T-02-09: a retained replay on the test topic never runs actions."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    await _setup(hass, make_hub_entry([sub]))

    await _press(hass, _device_id(sub), "ON", retain=True)
    await _press(hass, _device_id(sub), "OFF", retain=True)

    assert (len(on_calls), len(off_calls)) == (0, 0)


async def test_unknown_test_payload_is_logged_and_ignored(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """An unknown payload logs one warning with device name and truncated repr; an empty one only at debug."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    await _setup(hass, make_hub_entry([sub]))

    with caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"):
        caplog.clear()
        await _press(hass, _device_id(sub), "toggle")
        (warning,) = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert "Lamp" in warning.getMessage()
        assert "'toggle'" in warning.getMessage()

        caplog.clear()
        await _press(hass, _device_id(sub), "x\nforged " + "y" * 500)
        (long_warning,) = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert "\n" not in long_warning.getMessage()
        assert len(long_warning.getMessage()) < 250

        caplog.clear()
        await _press(hass, _device_id(sub), "")
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    assert (len(on_calls), len(off_calls)) == (0, 0)


async def test_test_run_failure_uses_normal_repairs_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A failing press creates the same action_failed issue with trigger label and error as a state-driven run."""
    _register_failing_service(hass, "boom")
    sub = make_switch_subentry("Lamp", off=FAIL_ACTIONS)
    device_id = _device_id(sub)
    await _setup(hass, make_hub_entry([sub]))

    await _press(hass, device_id, "OFF")

    issue = _issue(hass, device_id)
    assert issue is not None
    assert issue.translation_placeholders["device"] == "Lamp"
    assert issue.translation_placeholders["trigger"] == "onChangeToOff"
    assert "boom" in issue.translation_placeholders["error"]


async def test_press_on_action_less_trigger_runs_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A trigger without actions has no Script branch: the press runs nothing and raises no issue."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    await _setup(hass, make_hub_entry([sub]))

    await _press(hass, device_id, "OFF")

    assert len(on_calls) == 0
    assert [issue for issue in ir.async_get(hass).issues.values() if issue.domain == DOMAIN] == []


# --- button lifecycle (D-13) ----------------------------------------------------------------------------------------


def _last_discovery(mqtt_mock: Any, device_id: str) -> dict[str, Any]:
    """Return the last discovery payload the manager published for a device."""
    return json.loads(_publishes(mqtt_mock, discovery_topic("homeassistant", device_id))[-1][0])


def _update_options(hass: HomeAssistant, entry: MockConfigEntry, options: list[dict[str, Any]]) -> None:
    subentry = next(iter(entry.subentries.values()))
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_OPTIONS: options})


def _options(entry: MockConfigEntry) -> list[dict[str, Any]]:
    return [dict(option) for option in next(iter(entry.subentries.values())).data[CONF_OPTIONS]]


async def _select_entry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> tuple[MockConfigEntry, str]:
    """Set up a three-option Select device and deliver its discovery to core MQTT."""
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)
    return entry, device_id


async def test_removed_option_removes_its_button_entity(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """Removing option b removes exactly its button from the registry and the state machine, via a tombstone."""
    entry, device_id = await _select_entry(hass, mqtt_mock, make_hub_entry, make_select_subentry)
    b_button = _button_entity_id(hass, device_id, trigger_key("b"))
    assert b_button is not None
    assert hass.states.get(b_button) is not None

    _update_options(hass, entry, [option for option in _options(entry) if option[CONF_STATE_VALUE] != "b"])
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)

    assert _last_discovery(mqtt_mock, device_id)["components"][discovery.button_component_key(trigger_key("b"))] == {
        "platform": "button"
    }
    assert _button_entity_id(hass, device_id, trigger_key("b")) is None
    assert hass.states.get(b_button) is None
    assert _button_entity_id(hass, device_id, trigger_key("a")) is not None
    assert _button_entity_id(hass, device_id, trigger_key("c")) is not None
    assert len(hass.states.async_entity_ids("button")) == 2


async def test_tombstone_is_kept_for_every_republish_while_running(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """A broker reconnect republishes the discovery and the tombstone of the removed option is still in it."""
    entry, device_id = await _select_entry(hass, mqtt_mock, make_hub_entry, make_select_subentry)
    _update_options(hass, entry, [option for option in _options(entry) if option[CONF_STATE_VALUE] != "b"])
    await hass.async_block_till_done(wait_background_tasks=True)
    mqtt_mock.async_publish.reset_mock()

    async_dispatcher_send(hass, mqtt.MQTT_CONNECTION_STATE, True)
    await hass.async_block_till_done(wait_background_tasks=True)

    components = _last_discovery(mqtt_mock, device_id)["components"]
    assert components[discovery.button_component_key(trigger_key("b"))] == {"platform": "button"}


async def test_readded_state_value_drops_the_tombstone(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """Adding an option with the same StateValue again removes the tombstone and its button exists again."""
    entry, device_id = await _select_entry(hass, mqtt_mock, make_hub_entry, make_select_subentry)
    original = _options(entry)
    _update_options(hass, entry, [option for option in original if option[CONF_STATE_VALUE] != "b"])
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)
    assert _button_entity_id(hass, device_id, trigger_key("b")) is None

    _update_options(hass, entry, original)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)

    button = _last_discovery(mqtt_mock, device_id)["components"][discovery.button_component_key(trigger_key("b"))]
    assert button["platform"] == "button"
    assert button["payload_press"] == "b"
    assert _button_entity_id(hass, device_id, trigger_key("b")) is not None


async def test_renamed_option_renames_button_and_keeps_unique_id(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """A friendly name change only changes the button name; unique id and entity id stay."""
    entry, device_id = await _select_entry(hass, mqtt_mock, make_hub_entry, make_select_subentry)
    before = er.async_get(hass).async_get(_button_entity_id(hass, device_id, trigger_key("b")))

    renamed = [
        {**option, CONF_FRIENDLY_NAME: "Bravo 2"} if option[CONF_STATE_VALUE] == "b" else option
        for option in _options(entry)
    ]
    _update_options(hass, entry, renamed)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)

    button = _last_discovery(mqtt_mock, device_id)["components"][discovery.button_component_key(trigger_key("b"))]
    assert button["name"] == "Test Bravo 2"
    assert button["unique_id"] == f"{device_id}_test_{trigger_key('b')}"
    after = er.async_get(hass).async_get(_button_entity_id(hass, device_id, trigger_key("b")))
    assert (after.unique_id, after.entity_id) == (before.unique_id, before.entity_id)
    assert hass.states.get(after.entity_id).attributes["friendly_name"].endswith("Test Bravo 2")


async def test_new_option_adds_a_button(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """Adding an option adds one button component and one button entity."""
    entry, device_id = await _select_entry(hass, mqtt_mock, make_hub_entry, make_select_subentry)
    assert len(hass.states.async_entity_ids("button")) == 3

    new_option = {CONF_STATE_VALUE: "d", CONF_FRIENDLY_NAME: "Delta", "actions": []}
    _update_options(hass, entry, [*_options(entry), new_option])
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver_discovery(hass, mqtt_mock, entry, device_id)

    components = _last_discovery(mqtt_mock, device_id)["components"]
    assert sum(1 for component in components.values() if component["platform"] == "button") == 4
    assert _button_entity_id(hass, device_id, trigger_key("d")) is not None
    assert len(hass.states.async_entity_ids("button")) == 4


async def test_delete_device_clears_buttons_with_the_discovery_clear(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """Deleting the device publishes the empty discovery payload once; delivered live it removes every entity."""
    entry, device_id = await _select_entry(hass, mqtt_mock, make_hub_entry, make_select_subentry)
    topic = discovery_topic("homeassistant", device_id)
    assert hass.states.get("select.mode") is not None
    assert len(hass.states.async_entity_ids("button")) == 3

    hass.config_entries.async_remove_subentry(entry, next(iter(entry.subentries.values())).subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [payload for payload, _qos, _retain in _publishes(mqtt_mock, topic) if payload == ""] == [""]
    # The mocked client skips a second retained message per topic, a real broker forwards the clear live
    async_fire_mqtt_message(hass, topic, "", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("select.mode") is None
    assert hass.states.async_entity_ids("button") == []


def _watch_test_unsubscribe(entry: MockConfigEntry, device_id: str) -> list[str]:
    """Wrap the test subscription release of a device and record its calls."""
    calls: list[str] = []
    device = entry.runtime_data.devices[device_id]
    real = device.unsubscribe_test
    assert real is not None

    def _release() -> None:
        calls.append(device_id)
        real()

    device.unsubscribe_test = _release
    return calls


async def test_test_subscription_is_released_on_delete_and_unload(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The test topic subscription ends with the device and with the entry, and a later press runs nothing."""
    on_calls = async_mock_service(hass, "test", "on")
    removed = make_switch_subentry("Removed", on=ON_ACTIONS)
    kept = make_switch_subentry("Kept", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([removed, kept]))
    removed_released = _watch_test_unsubscribe(entry, _device_id(removed))
    kept_released = _watch_test_unsubscribe(entry, _device_id(kept))

    subentry = next(s for s in entry.subentries.values() if s.title == "Removed")
    hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _press(hass, _device_id(removed), "ON")
    assert removed_released == [_device_id(removed)]
    assert kept_released == []
    assert len(on_calls) == 0

    assert await hass.config_entries.async_unload(entry.entry_id)
    await _press(hass, _device_id(kept), "ON")
    assert kept_released == [_device_id(kept)]
    assert len(on_calls) == 0
