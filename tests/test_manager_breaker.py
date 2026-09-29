"""Circuit breaker in the manager (STA-06, D-13 to D-17): trip, pause, persistence, release and cleanup."""

import asyncio
import contextvars
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions import topics
from custom_components.mqtt_actions.const import CONF_DEVICE_ID, DOMAIN, ISSUE_CIRCUIT_BREAKER_PREFIX

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant, ServiceCall
    from pytest_homeassistant_custom_component.common import MockConfigEntry

# The run variable `test` is written into the service data so a recorder can tell live runs from test presses
ON_ACTIONS = [{"action": "test.on", "data": {"test": "{{ test }}"}}]
OFF_ACTIONS = [{"action": "test.off", "data": {"test": "{{ test }}"}}]
MAX_RUNS = 3
WINDOW = 3600
CAP = 20


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


async def _fire(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payload: str, *, retain: bool) -> None:
    """Deliver one state message and let the run finish."""
    async_fire_mqtt_message(hass, topics.state_topic(entry.data["base_topic"], device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _fire_many(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payloads: list[str]) -> None:
    for payload in payloads:
        await _fire(hass, entry, device_id, payload, retain=False)


async def _press(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payload: str) -> None:
    """Deliver one message to the test topic of a device the way the broker forwards a button press."""
    async_fire_mqtt_message(hass, topics.test_topic(entry.data["base_topic"], device_id), payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


def _breaker_issues(hass: HomeAssistant) -> list[ir.IssueEntry]:
    return [
        issue
        for issue in ir.async_get(hass).issues.values()
        if issue.domain == DOMAIN and issue.issue_id.startswith(ISSUE_CIRCUIT_BREAKER_PREFIX)
    ]


def _breaker_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_CIRCUIT_BREAKER_PREFIX}{device_id}")


def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno == logging.WARNING]


def _limited(make_switch_subentry: Callable, name: str = "Lamp", **kwargs: Any) -> ConfigSubentryData:
    """A switch with both actions and the test limits (3 runs in 3600 seconds)."""
    kwargs.setdefault("on", ON_ACTIONS)
    kwargs.setdefault("off", OFF_ACTIONS)
    return make_switch_subentry(name, breaker_max_runs=MAX_RUNS, breaker_window=WINDOW, **kwargs)


ALTERNATING = ["ON", "OFF", "ON", "OFF", "ON", "OFF"]


# --- configuration reaches the breaker (D-14) ---------------------------------------------------------------------


async def test_defaults_and_stored_limits_reach_the_breaker(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A device without stored breaker keys gets 5 runs in 10 seconds; stored values reach the breaker."""
    plain = make_switch_subentry("Plain", on=ON_ACTIONS)
    limited = _limited(make_switch_subentry, "Limited")
    entry = await _setup(hass, make_hub_entry([plain, limited]))

    devices = entry.runtime_data.devices
    assert (devices[_device_id(plain)].breaker.max_runs, devices[_device_id(plain)].breaker.window) == (5, 10.0)
    assert (devices[_device_id(limited)].breaker.max_runs, devices[_device_id(limited)].breaker.window) == (
        MAX_RUNS,
        float(WINDOW),
    )


# --- trip, pause, inform (D-15, D-16) ------------------------------------------------------------------------------


async def test_change_after_max_runs_trips_pauses_and_informs(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """The change after max_runs runs trips: one warning, one Repairs issue, no further run and no more warnings."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = _limited(make_switch_subentry)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    with caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"):
        caplog.clear()
        await _fire_many(hass, entry, device_id, ALTERNATING)
        warnings = _warnings(caplog)

    assert len(on_calls) + len(off_calls) == MAX_RUNS
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "Lamp" in message
    assert str(MAX_RUNS) in message
    assert str(WINDOW) in message
    (issue,) = _breaker_issues(hass)
    assert issue.issue_id == f"circuit_breaker_{device_id}"
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == "circuit_breaker_tripped"
    assert issue.translation_placeholders == {"device": "Lamp", "max_runs": str(MAX_RUNS), "window": str(WINDOW)}
    assert [i for i in ir.async_get(hass).issues.values() if i.domain == DOMAIN] == [issue]
    assert entry.runtime_data.devices[device_id].breaker.tripped is True


async def test_paused_device_updates_baseline_without_running(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-15: while paused the baseline follows the live changes and no action runs."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = _limited(make_switch_subentry)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire_many(hass, entry, device_id, ALTERNATING)
    device = entry.runtime_data.devices[device_id]
    assert device.breaker.tripped is True
    runs = len(on_calls) + len(off_calls)

    await _fire(hass, entry, device_id, "ON", retain=False)
    assert device.tracker.last_acted == "ON"
    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert device.tracker.last_acted == "OFF"

    assert len(on_calls) + len(off_calls) == runs


async def test_trip_stops_running_and_queued_runs(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A3: the tripping change stops the held run and drops the queued one; no action-failed issue appears."""
    release = asyncio.Event()
    after: list[str] = []
    off_calls = async_mock_service(hass, "test", "off")

    async def _hold(call: ServiceCall) -> None:
        await release.wait()

    async def _after(call: ServiceCall) -> None:
        after.append("after")

    hass.services.async_register("test", "hold", _hold)
    hass.services.async_register("test", "after", _after)
    sub = make_switch_subentry(
        "Lamp",
        on=[{"action": "test.hold"}, {"action": "test.after"}],
        off=[{"action": "test.off"}],
        breaker_max_runs=2,
        breaker_window=WINDOW,
    )
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    topic = topics.state_topic(entry.data["base_topic"], device_id)

    for payload in ("ON", "OFF"):
        async_fire_mqtt_message(hass, topic, payload, retain=False)
        for _ in range(5):
            await asyncio.sleep(0)
    assert off_calls == []

    async_fire_mqtt_message(hass, topic, "ON", retain=False)
    # The held run only ends by being stopped, so the settling must not wait for background tasks here
    for _ in range(20):
        await asyncio.sleep(0)
    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.devices[device_id].breaker.tripped is True
    assert after == []
    assert off_calls == []
    assert [i for i in ir.async_get(hass).issues.values() if i.domain == DOMAIN and "action_failed" in i.issue_id] == []


# --- what is counted (D-13, D-14, A2) ------------------------------------------------------------------------------


async def test_uncounted_changes(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Changes of a trigger without actions, unknown payloads and retained messages never count."""
    off_calls = async_mock_service(hass, "test", "off")
    sub = _limited(make_switch_subentry, on=[])
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    breaker = entry.runtime_data.devices[device_id].breaker

    # ON has no actions: three uncounted changes and three counted OFF runs, the limit is exactly reached
    await _fire_many(hass, entry, device_id, ALTERNATING)
    assert len(off_calls) == MAX_RUNS
    assert breaker.tripped is False

    for payload in ("toggle", "maybe", "", "toggle", "maybe"):
        await _fire(hass, entry, device_id, payload, retain=False)
    for payload in ("ON", "OFF", "ON", "OFF", "ON"):
        await _fire(hass, entry, device_id, payload, retain=True)
    assert breaker.tripped is False

    # The next real OFF run is the fourth counted one
    await _fire(hass, entry, device_id, "ON", retain=False)
    assert breaker.tripped is False
    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert breaker.tripped is True
    assert len(off_calls) == MAX_RUNS


async def test_test_press_is_not_counted_and_works_while_paused(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A2, D-13: test presses neither count nor are blocked by a pause; they run the pressed trigger's actions."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = _limited(make_switch_subentry)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    breaker = entry.runtime_data.devices[device_id].breaker

    for _ in range(MAX_RUNS + 2):
        await _press(hass, entry, device_id, "ON")
    assert breaker.tripped is False
    assert len(on_calls) == MAX_RUNS + 2

    await _fire_many(hass, entry, device_id, ["ON", "OFF", "ON", "OFF"])
    assert breaker.tripped is True
    runs = len(on_calls) + len(off_calls)

    await _press(hass, entry, device_id, "OFF")
    await _press(hass, entry, device_id, "ON")

    assert len(on_calls) + len(off_calls) == runs + 2
    assert on_calls[-1].data["test"] is True
    assert off_calls[-1].data["test"] is True
    assert breaker.tripped is True


async def test_window_slides_with_injected_clock(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Changes spaced further apart than the window never trip."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS, breaker_max_runs=2, breaker_window=10)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    now = 0.0
    entry.runtime_data.clock = lambda: now

    for payload in ["ON", "OFF"] * 4:
        now += 11
        await _fire(hass, entry, device_id, payload, retain=False)

    assert len(on_calls) + len(off_calls) == 8
    assert entry.runtime_data.devices[device_id].breaker.tripped is False
    assert _breaker_issues(hass) == []


# --- STA-06 end to end ---------------------------------------------------------------------------------------------


async def test_self_toggling_action_is_stopped(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A service that flips its own device's state is called exactly max_runs times, then the device is paused."""
    calls = 0
    current = ["ON"]
    sub = make_switch_subentry(
        "Lamp",
        on=[{"action": "test.flip"}],
        off=[{"action": "test.flip"}],
        breaker_max_runs=MAX_RUNS,
        breaker_window=WINDOW,
    )
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    topic = topics.state_topic(entry.data["base_topic"], device_id)

    async def _flip(call: ServiceCall) -> None:
        nonlocal calls
        calls += 1
        if calls >= CAP:
            return  # a broken breaker fails the assertion below instead of looping forever
        current[0] = "OFF" if current[0] == "ON" else "ON"
        # A broker delivers the message from its own task, outside the running Script's execution path; an empty
        # context keeps Home Assistant's recursion detection (which follows the context) out of the picture
        hass.loop.call_soon(async_fire_mqtt_message, hass, topic, current[0], 0, False, context=contextvars.Context())

    hass.services.async_register("test", "flip", _flip)

    await _fire(hass, entry, device_id, "ON", retain=False)
    # The flip messages arrive through the event loop after each run, so settle until no further call happens
    previous = -1
    while previous != calls:
        previous = calls
        await hass.async_block_till_done(wait_background_tasks=True)
        await asyncio.sleep(0)

    assert calls < CAP
    assert calls == MAX_RUNS
    assert entry.runtime_data.devices[device_id].breaker.tripped is True
    assert _breaker_issue(hass, device_id) is not None
