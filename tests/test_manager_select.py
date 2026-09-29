"""Integration tests for Select devices: option edges, payload mapping, startup, unknown payloads and lifecycle."""

import hashlib
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import CONF_DEVICE_ID, DOMAIN
from custom_components.mqtt_actions.topics import discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant, ServiceCall
    from pytest_homeassistant_custom_component.common import MockConfigEntry

ABC_OPTIONS = [
    ("a", "Alpha", [{"action": "test.a"}]),
    ("b", "Bravo", [{"action": "test.b"}]),
    ("c", "Charlie", [{"action": "test.c"}]),
]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add the entry, set it up and wait for background tasks."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _fire(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payload: str, *, retain: bool) -> None:
    """Deliver one state message to the device topic and let the run finish."""
    topic = state_topic(entry.data["base_topic"], device_id)
    async_fire_mqtt_message(hass, topic, payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


def _key(state_value: str) -> str:
    """Return the trigger key contract: 12 hex characters of the sha256 of the lowercased StateValue."""
    return hashlib.sha256(state_value.lower().encode()).hexdigest()[:12]


def _services(hass: HomeAssistant, *names: str) -> dict[str, list[ServiceCall]]:
    """Register one mocked test service per name and return the recorded calls by name."""
    return {name: async_mock_service(hass, "test", name) for name in names}


# --- tracer: the option whose StateValue arrives runs, no other ---------------------------------------------------


async def test_tracer_select_option_payload_runs_only_that_option(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """DEV-03: a live payload equal to a StateValue runs exactly that option's actions once."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "b", retain=False)
    assert (len(calls["a"]), len(calls["b"]), len(calls["c"])) == (0, 1, 0)

    await _fire(hass, entry, _device_id(sub), "C", retain=False)
    assert (len(calls["a"]), len(calls["b"]), len(calls["c"])) == (0, 1, 1)


async def test_select_payload_is_trimmed_and_case_insensitive(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """D-06: payloads are trimmed and compared case-insensitively; the second spelling is a duplicate edge."""
    calls = _services(hass, "mixed", "other")
    sub = make_select_subentry(
        "Mode",
        [("Mixed Case", "Mixed", [{"action": "test.mixed"}]), ("other", "Other", [{"action": "test.other"}])],
    )
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), " mixed case\n", retain=False)
    await _fire(hass, entry, _device_id(sub), "MIXED CASE", retain=False)

    assert len(calls["mixed"]) == 1
    assert len(calls["other"]) == 0


async def test_select_first_live_message_without_baseline_acts(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """D-14 of Phase 1: the first live message on a fresh Select device is a real edge."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "a", retain=False)

    assert len(calls["a"]) == 1


async def test_select_option_without_actions_moves_baseline_without_running(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """An option with an empty action list runs nothing, raises no issue and still moves the baseline."""
    calls = _services(hass, "a")
    sub = make_select_subentry("Mode", [("a", "Alpha", [{"action": "test.a"}]), ("b", "Bravo", [])])
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, device_id, "b", retain=False)

    assert entry.runtime_data.devices[device_id].tracker.last_acted == "b"
    assert len(calls["a"]) == 0
    assert [issue for issue in ir.async_get(hass).issues.values() if issue.domain == DOMAIN] == []


async def test_select_device_survives_reload_without_orphan_cleanup(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """A Select device is enumerated by the orphan cleanup, so a reload never clears its topics."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    mqtt_mock.async_publish.reset_mock()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    empty = [call.args[0] for call in mqtt_mock.async_publish.call_args_list if call.args[1] in {"", b""}]
    assert discovery_topic("homeassistant", device_id) not in empty
    assert state_topic(entry.data["base_topic"], device_id) not in empty
    await _fire(hass, entry, device_id, "c", retain=False)
    assert len(calls["c"]) == 1


# --- runner accessors ---------------------------------------------------------------------------------------------


async def test_runner_accessors_for_switch_with_only_on_actions(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The device-level runner API answers per trigger key: only ON has a Script, so the script count is 1."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    runner = entry.runtime_data.runner

    assert runner.can_run(device_id, _key("ON")) is True
    assert runner.can_run(device_id, _key("OFF")) is False
    assert runner.script_count(device_id) == 1
