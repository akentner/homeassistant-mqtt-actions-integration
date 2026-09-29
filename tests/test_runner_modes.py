"""Integration tests for run modes: one Script per device, serial queue, restart, drops, supersede and unload."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script import Script
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    DOMAIN,
    ISSUE_ACTION_FAILED_PREFIX,
    RUN_MODE_RESTART,
    SERIAL_QUEUE_LIMIT,
    TRIGGER_ON,
)
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY, trigger_key
from custom_components.mqtt_actions.topics import state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant, ServiceCall
    from pytest_homeassistant_custom_component.common import MockConfigEntry

ON_HOLD = [{"action": "test.hold_on"}, {"action": "test.after_on"}]
OFF_ACTIONS = [{"action": "test.off"}]
MAX_EXCEEDED = "Maximum number of runs exceeded"
OWN_LOGGERS = ("custom_components.mqtt_actions", "homeassistant.helpers.script")


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add the entry, set it up and wait for background tasks."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _settle() -> None:
    """Give running and cancelled tasks enough loop turns to reach their next await without waiting for them."""
    for _ in range(25):
        await asyncio.sleep(0)


async def _publish(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payload: str) -> None:
    """Deliver one live state message and let the loop run, without waiting for held runs."""
    async_fire_mqtt_message(hass, state_topic(entry.data["base_topic"], device_id), payload, retain=False)
    await _settle()


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


def _issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}")


def _own_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return records at WARNING or above that come from the integration or from the script helper."""
    return [r for r in caplog.records if r.levelno >= logging.WARNING and r.name.startswith(OWN_LOGGERS)]


class Held:
    """A service that records its start, waits until released and records its end; cancellation is recorded."""

    def __init__(self, hass: HomeAssistant, name: str, order: list[str], gate: asyncio.Event | None = None) -> None:
        self.name = name
        self.order = order
        self.gate = gate or asyncio.Event()
        self.cancelled = 0
        hass.services.async_register("test", name, self._handle)

    async def _handle(self, call: ServiceCall) -> None:
        self.order.append(f"{self.name}:start")
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        self.order.append(f"{self.name}:end")


def _recorder(hass: HomeAssistant, name: str, order: list[str]) -> None:
    """Register a service that only appends its name to the order list."""

    async def _handle(call: ServiceCall) -> None:
        order.append(name)

    hass.services.async_register("test", name, _handle)


# --- restart and serial across the triggers of one device (DEV-06, D-10, D-11) -----------------------------------


async def test_restart_mode_newer_change_cancels_running_run(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-11: in restart mode a newer change cancels the running run, quietly, and only the newer run completes."""
    order: list[str] = []
    hold = Held(hass, "hold_on", order)
    _recorder(hass, "after_on", order)
    _recorder(hass, "off", order)
    sub = make_switch_subentry("Lamp", on=ON_HOLD, off=OFF_ACTIONS, run_mode=RUN_MODE_RESTART)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _publish(hass, entry, device_id, "ON")
    assert order == ["hold_on:start"]
    await _publish(hass, entry, device_id, "OFF")
    hold.gate.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["hold_on:start", "off"]
    assert hold.cancelled == 1
    assert _issue(hass, device_id) is None
    assert _own_warnings(caplog) == []


async def test_restart_mode_cancels_across_select_options(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """Restart is per device: the run of option A is cancelled when option B changes, and B runs."""
    order: list[str] = []
    hold = Held(hass, "hold_a", order)
    _recorder(hass, "after_a", order)
    _recorder(hass, "rec_b", order)
    sub = make_select_subentry(
        "Mode",
        [
            ("a", "Alpha", [{"action": "test.hold_a"}, {"action": "test.after_a"}]),
            ("b", "Bravo", [{"action": "test.rec_b"}]),
        ],
        run_mode=RUN_MODE_RESTART,
    )
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _publish(hass, entry, device_id, "a")
    await _publish(hass, entry, device_id, "b")
    hold.gate.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["hold_a:start", "rec_b"]
    assert _issue(hass, device_id) is None
    assert _own_warnings(caplog) == []


async def test_serial_mode_keeps_order_across_select_options(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """Serial is per device: changes to different options queue first-in first-out."""
    order: list[str] = []
    hold = Held(hass, "hold_a", order)
    _recorder(hass, "rec_b", order)
    sub = make_select_subentry(
        "Mode",
        [("a", "Alpha", [{"action": "test.hold_a"}]), ("b", "Bravo", [{"action": "test.rec_b"}])],
    )
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    for payload in ("a", "b", "a"):
        await _publish(hass, entry, device_id, payload)
    assert order == ["hold_a:start"]
    hold.gate.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["hold_a:start", "hold_a:end", "rec_b", "hold_a:start", "hold_a:end"]


async def test_missing_run_mode_behaves_as_serial(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-10: a subentry stored without run_mode never cancels a running run; the changes queue in order."""
    order: list[str] = []
    hold = Held(hass, "hold_on", order)
    _recorder(hass, "after_on", order)
    _recorder(hass, "off", order)
    sub = make_switch_subentry("Lamp", on=ON_HOLD, off=OFF_ACTIONS)
    assert "run_mode" not in sub["data"]
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _publish(hass, entry, device_id, "ON")
    await _publish(hass, entry, device_id, "OFF")
    assert order == ["hold_on:start"]
    assert hold.cancelled == 0
    hold.gate.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["hold_on:start", "hold_on:end", "after_on", "off"]


async def test_invalid_trigger_actions_are_left_out_others_still_run(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """An option with an invalid action list raises the setup issue; the other options run through the one Script."""
    b_calls = async_mock_service(hass, "test", "b")
    sub = make_select_subentry(
        "Mode",
        [("a", "Alpha", [{"not_an_action": True}]), ("b", "Bravo", [{"action": "test.b"}])],
        run_mode=RUN_MODE_RESTART,
    )
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    issue = _issue(hass, device_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["trigger"] == "setup"
    assert issue.translation_placeholders["device"] == "Mode"
    runner = entry.runtime_data.runner
    assert runner.can_run(device_id, trigger_key("a")) is False
    assert runner.can_run(device_id, trigger_key("b")) is True

    await _publish(hass, entry, device_id, "b")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(b_calls) == 1


async def test_one_script_per_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A device with actions on both triggers owns one Script that can run both; without actions it owns none."""
    both = make_switch_subentry("Lamp", on=[{"action": "test.on"}], off=OFF_ACTIONS)
    none = make_switch_subentry("Plain")
    entry = await _setup(hass, make_hub_entry([both, none]))
    runner = entry.runtime_data.runner

    assert runner.script_count(_device_id(both)) == 1
    assert runner.can_run(_device_id(both), SWITCH_ON_KEY) is True
    assert runner.can_run(_device_id(both), SWITCH_OFF_KEY) is True
    assert runner.script_for(_device_id(both), SWITCH_ON_KEY) is runner.script_for(_device_id(both), SWITCH_OFF_KEY)
    assert runner.script_count(_device_id(none)) == 0
    assert runner.script_for(_device_id(none), SWITCH_ON_KEY) is None


# --- queue bound, dropped and superseded runs, unload (D-11, D-12, A5, A10) --------------------------------------


async def test_serial_queue_is_bounded_and_overflow_is_dropped_with_warning(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-12: 12 rapid changes run SERIAL_QUEUE_LIMIT times in order; two are dropped with a warning on the device."""
    order: list[str] = []
    gate = asyncio.Event()

    async def _record(call: ServiceCall) -> None:
        order.append(call.data["trigger"])
        if len(order) == 1:
            await gate.wait()

    hass.services.async_register("test", "rec", _record)
    sub = make_switch_subentry(
        "Lamp",
        on=[{"action": "test.rec", "data": {"trigger": "on"}}],
        off=[{"action": "test.rec", "data": {"trigger": "off"}}],
    )
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    for payload in ("ON", "OFF") * 6:
        await _publish(hass, entry, device_id, payload)
    gate.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["on", "off"] * (SERIAL_QUEUE_LIMIT // 2)
    exceeded = [r.getMessage() for r in caplog.records if MAX_EXCEEDED in r.getMessage()]
    assert len(exceeded) == 2
    assert all("Lamp" in message for message in exceeded)
    assert _issue(hass, device_id) is None


async def _enqueue_on(entry: MockConfigEntry, device_id: str) -> None:
    """Enqueue one run of the ON trigger directly on the runner."""
    entry.runtime_data.runner.enqueue(
        device_id, "Lamp", TRIGGER_ON, SWITCH_ON_KEY, {"device_id": device_id, "state": "ON"}
    )
    await _settle()


async def test_dropped_run_does_not_clear_failure_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A dropped run (the Script returns None) leaves an existing failure issue in place."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    entry.runtime_data.runner.report_failure(device_id, "Lamp", TRIGGER_ON, "boom")

    with patch.object(Script, "async_run", new=AsyncMock(return_value=None)):
        await _enqueue_on(entry, device_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert _issue(hass, device_id) is not None


async def test_completed_run_with_result_clears_failure_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The latest enqueued run that returns a result deletes the failure issue."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    entry.runtime_data.runner.report_failure(device_id, "Lamp", TRIGGER_ON, "boom")

    with patch.object(Script, "async_run", new=AsyncMock(return_value=object())):
        await _enqueue_on(entry, device_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert _issue(hass, device_id) is None


async def test_superseded_run_does_not_clear_failure_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A10: a run that finishes after a newer run was enqueued leaves the issue; only the newest run clears it."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    entry.runtime_data.runner.report_failure(device_id, "Lamp", TRIGGER_ON, "boom")
    releases = iter([asyncio.Event(), asyncio.Event()])
    events = {}

    async def _fake_run(self: Script, *args: Any, **kwargs: Any) -> object:
        event = next(releases)
        events[len(events)] = event
        await event.wait()
        return object()

    with patch.object(Script, "async_run", new=_fake_run):
        await _enqueue_on(entry, device_id)
        await _enqueue_on(entry, device_id)
        assert len(events) == 2  # both runs are in flight, as in restart mode where a stopped run returns normally
        events[0].set()
        await _settle()
        assert _issue(hass, device_id) is not None
        events[1].set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert _issue(hass, device_id) is None


async def test_unload_stops_running_and_queued_runs(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """Unloading the entry ends the running run and the queued ones quietly: no issue, no error, no lingering task."""
    order: list[str] = []
    hold = Held(hass, "hold_on", order)
    _recorder(hass, "off", order)
    sub = make_switch_subentry("Lamp", on=[{"action": "test.hold_on"}], off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    for payload in ("ON", "OFF", "ON", "OFF"):
        await _publish(hass, entry, device_id, payload)
    assert order == ["hold_on:start"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["hold_on:start"]
    assert hold.cancelled == 1
    assert _issue(hass, device_id) is None
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


async def test_restart_mode_action_less_trigger_change_does_not_cancel_running_run(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A5: a change to a trigger without actions enqueues nothing, so it leaves a running restart run alone."""
    order: list[str] = []
    hold = Held(hass, "hold_on", order)
    _recorder(hass, "after_on", order)
    sub = make_switch_subentry("Lamp", on=ON_HOLD, run_mode=RUN_MODE_RESTART)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _publish(hass, entry, device_id, "ON")
    await _publish(hass, entry, device_id, "OFF")
    assert order == ["hold_on:start"]
    assert hold.cancelled == 0
    hold.gate.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["hold_on:start", "hold_on:end", "after_on"]


async def test_reconfigure_stops_run_of_retired_script_without_issue(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """Changing a device while a run is held stops that run quietly; a later live change runs the new actions."""
    order: list[str] = []
    hold = Held(hass, "hold_on", order)
    new_off_calls = async_mock_service(hass, "test", "off2")
    sub = make_switch_subentry("Lamp", on=[{"action": "test.hold_on"}], off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _publish(hass, entry, device_id, "ON")
    assert order == ["hold_on:start"]

    subentry = next(iter(entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        data={
            **subentry.data,
            CONF_ON_CHANGE_TO_ON: [{"action": "test.on2"}],
            CONF_ON_CHANGE_TO_OFF: [{"action": "test.off2"}],
        },
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hold.cancelled == 1
    assert _issue(hass, device_id) is None
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []

    await _publish(hass, entry, device_id, "OFF")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(new_off_calls) == 1
