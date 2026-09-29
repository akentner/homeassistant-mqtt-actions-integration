"""Integration tests for the manager: edges, retained replays, run-on-startup and the persisted baseline."""

import asyncio
import logging
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_RUN_ON_STARTUP,
    DOMAIN,
    ISSUE_ACTION_FAILED_PREFIX,
    MAX_ISSUE_ERROR_LENGTH,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_PUBLISHED,
    STORE_VERSION,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.topics import state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant, ServiceCall
    from pytest_homeassistant_custom_component.common import MockConfigEntry

ON_ACTIONS = [{"action": "test.on"}]
OFF_ACTIONS = [{"action": "test.off"}]


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


# --- edges (STA-02) ---------------------------------------------------------------------------------------------


async def test_edge_live_on_runs_on_actions_once(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A live ON runs only the ON actions, once."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    assert len(on_calls) == 1
    assert len(off_calls) == 0


async def test_edge_off_runs_off_actions(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A live OFF runs only the OFF actions, once."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "OFF", retain=False)

    assert len(off_calls) == 1
    assert len(on_calls) == 0


async def test_edge_duplicate_live_value_is_ignored(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A repeated identical live value runs nothing; the opposite value runs its actions."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    assert len(on_calls) == 1

    await _fire(hass, entry, _device_id(sub), "OFF", retain=False)
    assert len(off_calls) == 1
    assert len(on_calls) == 1


async def test_edge_payload_case_insensitive(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Payloads are trimmed and read case-insensitively (D-02)."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), " on ", retain=False)
    assert len(on_calls) == 1

    await _fire(hass, entry, _device_id(sub), "Off\n", retain=False)
    assert len(off_calls) == 1


async def test_live_message_without_baseline_acts(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-14: the first live ON on a fresh device is a real edge."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    assert len(on_calls) == 1


# --- retained replays and run-on-startup (STA-04, D-05, D-06) -------------------------------------------------------


async def test_retain_replay_sets_baseline_without_actions(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A retained ON runs nothing and a following live ON runs nothing either, because the baseline is ON."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=True)
    assert len(on_calls) == 0

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    assert len(on_calls) == 0

    await _fire(hass, entry, _device_id(sub), "OFF", retain=False)
    assert len(off_calls) == 1


async def test_retain_replay_after_reconnect_runs_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A retained value that differs from the baseline moves the baseline without running actions."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    await _fire(hass, entry, _device_id(sub), "OFF", retain=True)

    assert len(on_calls) == 1
    assert len(off_calls) == 0

    # The baseline is now OFF, so a live OFF is a duplicate
    await _fire(hass, entry, _device_id(sub), "OFF", retain=False)
    assert len(off_calls) == 0


async def test_startup_flag_runs_retained_state_once(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-06: with the flag on, the retained state acts once after start even when it equals the persisted baseline."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, run_on_startup=True)
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {STORE_LAST_ACTED: {_device_id(sub): "ON"}, STORE_PUBLISHED: []},
    }
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=True)

    assert len(on_calls) == 1


async def test_startup_flag_not_reapplied_on_replay(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A later retained replay after a reconnect does not act again."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, run_on_startup=True)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=True)
    await _fire(hass, entry, _device_id(sub), "ON", retain=True)
    await _fire(hass, entry, _device_id(sub), "ON", retain=True)

    assert len(on_calls) == 1


async def test_startup_flag_applies_again_after_reload(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A reload is a start (D-05): the flag treats the retained state as a change once more."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, run_on_startup=True)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, _device_id(sub), "ON", retain=True)
    assert len(on_calls) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _fire(hass, entry, _device_id(sub), "ON", retain=True)

    assert len(on_calls) == 2


async def test_new_device_ignores_startup_flag(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """D-05: a device created at runtime never gets the startup treatment."""
    on_calls = async_mock_service(hass, "test", "on")
    entry = await _setup(hass, make_hub_entry())
    device_id = "0b1f6a0e-6a52-4f5b-9b0e-3a4c1c2d9e11"
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_ON_CHANGE_TO_ON: ON_ACTIONS,
                    CONF_ON_CHANGE_TO_OFF: [],
                    CONF_RUN_ON_STARTUP: True,
                }
            ),
            subentry_type=SUBENTRY_SWITCH,
            title="Fresh",
            unique_id=device_id,
        ),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert device_id in entry.runtime_data.devices

    await _fire(hass, entry, device_id, "ON", retain=True)

    assert len(on_calls) == 0


async def test_unknown_payload_is_ignored_and_logged(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """Unknown payloads log a warning with the device name and a truncated repr; an empty one only logs at debug."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    with caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"):
        caplog.clear()
        await _fire(hass, entry, _device_id(sub), "toggle", retain=False)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "Lamp" in warnings[0].getMessage()
        assert "'toggle'" in warnings[0].getMessage()

        caplog.clear()
        await _fire(hass, entry, _device_id(sub), "x\nforged log line " + "y" * 500, retain=False)
        (long_warning,) = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert "\n" not in long_warning.getMessage()
        assert len(long_warning.getMessage()) < 250

        caplog.clear()
        await _fire(hass, entry, _device_id(sub), "", retain=False)
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    assert len(on_calls) == 1
    assert len(off_calls) == 0

    # The baseline is untouched by the ignored payloads: a live ON is still a duplicate
    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    assert len(on_calls) == 1


# --- baseline persistence (STA-05, D-07) ---------------------------------------------------------------------------


async def test_baseline_persisted_across_reload(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """After a live ON and a reload, a live ON runs nothing and a live OFF runs the OFF actions."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    assert len(on_calls) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED][_device_id(sub)] == "ON"

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    assert len(on_calls) == 1

    await _fire(hass, entry, _device_id(sub), "OFF", retain=False)
    assert len(off_calls) == 1


async def test_baseline_saved_with_delay_after_change(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A baseline change schedules a delayed save instead of writing on every message."""
    async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    assert entry.runtime_data.devices[_device_id(sub)].tracker.last_acted == "ON"
    # Not written yet: the write is delayed, the stop path flushes it
    assert hass_storage.get(STORE_KEY, {}).get("data", {}).get(STORE_LAST_ACTED, {}).get(_device_id(sub)) is None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED][_device_id(sub)] == "ON"


async def test_baseline_not_persisted_before_first_message(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-07: without any valid message the stored map has no entry for the device."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, _device_id(sub), "toggle", retain=False)

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert _device_id(sub) not in hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED]


async def test_baseline_store_records_published_ids(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """The ids whose discovery was published are stored for the orphan cleanup of plan 01-05."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert hass_storage[STORE_KEY]["data"][STORE_PUBLISHED] == [_device_id(sub)]


# --- failure surfacing (DEV-08, D-08, D-09) ------------------------------------------------------------------------

FAIL_ACTIONS = [{"action": "test.fail"}]
ISSUE_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _register_failing_service(hass: HomeAssistant, message: str = "boom") -> dict[str, Any]:
    """Register test.fail; it raises HomeAssistantError with the current message while control['fail'] is True."""
    control: dict[str, Any] = {"fail": True, "message": message}

    async def _handler(call: ServiceCall) -> None:
        if control["fail"]:
            raise HomeAssistantError(control["message"])

    hass.services.async_register("test", "fail", _handler)
    return control


def _issues(hass: HomeAssistant) -> list[ir.IssueEntry]:
    return [issue for issue in ir.async_get(hass).issues.values() if issue.domain == DOMAIN]


def _issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}")


async def test_issue_created_when_action_fails(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A raising service is logged with the exception and shown as exactly one non-fixable Repairs issue."""
    _register_failing_service(hass, "boom")
    sub = make_switch_subentry("Lamp", on=FAIL_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    (issue,) = _issues(hass)
    assert issue.issue_id == f"action_failed_{_device_id(sub)}"
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == "action_failed"
    placeholders = issue.translation_placeholders
    assert placeholders is not None
    assert placeholders["device"] == "Lamp"
    assert placeholders["trigger"] == "onChangeToOn"
    assert ISSUE_TIME_PATTERN.match(placeholders["time"])
    assert "boom" in placeholders["error"]
    # Home Assistant's Script logs its own line without a traceback; the runner adds the one with the exception
    with_exception = [r for r in caplog.records if r.levelno == logging.ERROR and r.exc_info is not None]
    assert len(with_exception) == 1
    assert "Lamp" in with_exception[0].getMessage()
    assert "onChangeToOn" in with_exception[0].getMessage()


async def test_issue_updated_in_place_on_repeated_failure(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A second failure leaves one issue and updates its text (D-08)."""
    control = _register_failing_service(hass, "first failure")
    sub = make_switch_subentry("Lamp", on=FAIL_ACTIONS, off=FAIL_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    control["message"] = "second failure"
    await _fire(hass, entry, _device_id(sub), "OFF", retain=False)

    (issue,) = _issues(hass)
    assert issue.translation_placeholders is not None
    assert "second failure" in issue.translation_placeholders["error"]
    assert issue.translation_placeholders["trigger"] == "onChangeToOff"


async def test_issue_cleared_after_next_success(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: a successful run deletes the issue."""
    control = _register_failing_service(hass)
    sub = make_switch_subentry("Lamp", on=FAIL_ACTIONS, off=FAIL_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    assert _issue(hass, _device_id(sub)) is not None

    control["fail"] = False
    await _fire(hass, entry, _device_id(sub), "OFF", retain=False)

    assert _issues(hass) == []


async def test_issue_dismissed_stays_dismissed_while_failing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A dismissed issue stays dismissed while failures continue; a success deletes it entirely."""
    control = _register_failing_service(hass)
    sub = make_switch_subentry("Lamp", on=FAIL_ACTIONS, off=FAIL_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "ON", retain=False)
    ir.async_ignore_issue(hass, DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}", True)
    assert (issue := _issue(hass, device_id)) is not None
    assert issue.dismissed_version is not None

    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert (issue := _issue(hass, device_id)) is not None
    assert issue.dismissed_version is not None

    control["fail"] = False
    await _fire(hass, entry, device_id, "ON", retain=False)
    assert _issue(hass, device_id) is None


async def test_issue_error_text_is_truncated(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A 2000 character error yields a placeholder no longer than MAX_ISSUE_ERROR_LENGTH."""
    _register_failing_service(hass, "x" * 2000)
    sub = make_switch_subentry("Lamp", on=FAIL_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    (issue,) = _issues(hass)
    assert issue.translation_placeholders is not None
    assert 0 < len(issue.translation_placeholders["error"]) <= MAX_ISSUE_ERROR_LENGTH


async def test_issue_and_log_do_not_leak_action_data(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-01-10: a canary in the action data reaches neither the log nor the issue variables."""
    canary = "CANARY-7f3a91-secret"
    _register_failing_service(hass, "boom")
    sub = make_switch_subentry("Lamp", on=[{"action": "test.fail", "data": {"message": canary}}])
    with caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"):
        entry = await _setup(hass, make_hub_entry([sub]))
        await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    (issue,) = _issues(hass)
    assert canary not in caplog.text
    assert canary not in repr(issue.translation_placeholders)


async def test_issue_for_invalid_stored_actions_at_setup(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Invalid stored actions raise the issue with trigger setup; baseline tracking and the other transition work."""
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=[{"not_an_action": True}], off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    issue = _issue(hass, device_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["trigger"] == "setup"
    assert issue.translation_placeholders["device"] == "Lamp"
    assert len(issue.translation_placeholders["error"]) <= MAX_ISSUE_ERROR_LENGTH
    device = entry.runtime_data.devices[device_id]
    assert device.on_script is None
    assert device.off_script is not None

    await _fire(hass, entry, device_id, "ON", retain=False)
    assert device.tracker.last_acted == "ON"

    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert len(off_calls) == 1


async def test_actions_run_serially_in_order(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Changes arriving while a run is blocked run first-in first-out and none is dropped."""
    order: list[str] = []
    release = asyncio.Event()

    async def _on(call: ServiceCall) -> None:
        order.append("on:start")
        await release.wait()
        order.append("on:end")

    async def _off(call: ServiceCall) -> None:
        order.append("off")

    hass.services.async_register("test", "on", _on)
    hass.services.async_register("test", "off", _off)
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    for payload in ("ON", "OFF", "ON"):
        async_fire_mqtt_message(hass, state_topic(entry.data["base_topic"], device_id), payload, retain=False)
        await asyncio.sleep(0)
    for _ in range(5):
        await asyncio.sleep(0)
    assert order == ["on:start"]

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert order == ["on:start", "on:end", "off", "on:start", "on:end"]


async def test_empty_action_list_runs_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """An empty list builds no Script, runs nothing and creates no issue."""
    sub = make_switch_subentry("Lamp")
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    device = entry.runtime_data.devices[device_id]
    assert device.on_script is None
    assert device.off_script is None

    await _fire(hass, entry, device_id, "ON", retain=False)

    assert device.tracker.last_acted == "ON"
    assert _issues(hass) == []


async def test_issue_deleted_when_runner_unloads_removed_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Removing a device unloads its scripts and deletes its issue (wired up by plan 01-05)."""
    _register_failing_service(hass)
    sub = make_switch_subentry("Lamp", on=FAIL_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "ON", retain=False)
    assert _issue(hass, device_id) is not None

    await entry.runtime_data.runner.async_unload(device_id, remove_issue=True)

    assert _issue(hass, device_id) is None
