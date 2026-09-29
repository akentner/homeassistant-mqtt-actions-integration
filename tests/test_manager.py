"""Integration tests for the manager: edges, retained replays, run-on-startup and the persisted baseline."""

import asyncio
import json
import logging
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
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
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant, ServiceCall

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
    runner = entry.runtime_data.runner
    assert runner.can_run(device_id, SWITCH_ON_KEY) is False
    assert runner.can_run(device_id, SWITCH_OFF_KEY) is True

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
    runner = entry.runtime_data.runner
    assert runner.can_run(device_id, SWITCH_ON_KEY) is False
    assert runner.can_run(device_id, SWITCH_OFF_KEY) is False

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


# --- lifecycle helpers ---------------------------------------------------------------------------------------------

STATE_TOPIC_BASE = "mqtt_actions"
ORPHAN_ID = "5d9c1b0e-7c55-4c1e-8a11-0f7c3a9b2d44"
NEW_DEVICE_ID = "0b1f6a0e-6a52-4f5b-9b0e-3a4c1c2d9e11"


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _preload_store(
    hass_storage: dict[str, Any], *, published: list[str], last_acted: dict[str, str] | None = None
) -> None:
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {STORE_LAST_ACTED: last_acted or {}, STORE_PUBLISHED: published},
    }


def _record_events(entry: MockConfigEntry) -> list[tuple]:
    """Record publishes and unsubscribes of the running manager in the order they happen."""
    events: list[tuple] = []
    gateway = entry.runtime_data.gateway
    real_publish = gateway.async_publish

    async def _publish(topic: str, payload: str, *, retain: bool, qos: int = 1) -> None:
        events.append(("publish", topic, payload))
        await real_publish(topic, payload, retain=retain, qos=qos)

    gateway.async_publish = _publish
    for device in entry.runtime_data.devices.values():
        real_unsubscribe = device.unsubscribe

        def _unsubscribe(real=real_unsubscribe) -> None:
            events.append(("unsubscribe",))
            real()

        device.unsubscribe = _unsubscribe
    return events


def _new_subentry(
    device_id: str, title: str = "Fresh", on: list | None = None, off: list | None = None
) -> ConfigSubentry:
    return ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_DEVICE_ID: device_id,
                CONF_ON_CHANGE_TO_ON: on or [],
                CONF_ON_CHANGE_TO_OFF: off or [],
                CONF_RUN_ON_STARTUP: False,
            }
        ),
        subentry_type=SUBENTRY_SWITCH,
        title=title,
        unique_id=device_id,
    )


def _only_subentry(entry: MockConfigEntry) -> ConfigSubentry:
    (subentry,) = entry.subentries.values()
    return subentry


# --- reconcile: add and change (DEV-05) ----------------------------------------------------------------------------


async def test_reconcile_add_at_runtime_publishes_and_subscribes(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A subentry added while loaded gets discovery published, a live subscription and no startup window."""
    on_calls = async_mock_service(hass, "test", "on")
    entry = await _setup(hass, make_hub_entry())

    hass.config_entries.async_add_subentry(entry, _new_subentry(NEW_DEVICE_ID, on=ON_ACTIONS))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(_publishes(mqtt_mock, discovery_topic("homeassistant", NEW_DEVICE_ID))) == 1
    device = entry.runtime_data.devices[NEW_DEVICE_ID]
    assert device.unsubscribe is not None
    assert device.tracker.startup_pending is False
    await _fire(hass, entry, NEW_DEVICE_ID, "ON", retain=False)
    assert len(on_calls) == 1


async def test_reconcile_after_stop_does_not_revive_manager(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """WR-01: a late update-listener call on a stopped manager must not subscribe or publish anything."""
    on_calls = async_mock_service(hass, "test", "on")
    entry = await _setup(hass, make_hub_entry())
    manager = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    mqtt_mock.async_publish.reset_mock()

    hass.config_entries.async_add_subentry(entry, _new_subentry(NEW_DEVICE_ID, on=ON_ACTIONS))
    await manager.async_reconcile()

    assert manager.devices == {}
    assert _publishes(mqtt_mock, discovery_topic("homeassistant", NEW_DEVICE_ID)) == []
    async_fire_mqtt_message(hass, state_topic(entry.data["base_topic"], NEW_DEVICE_ID), "ON")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(on_calls) == 0


async def test_reconcile_change_rebuilds_scripts_keeps_baseline(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Changing a device swaps its actions and name, keeps the subscription and baseline, republishes discovery."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    new_on_calls = async_mock_service(hass, "test", "on2")
    new_off_calls = async_mock_service(hass, "test", "off2")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "ON", retain=False)
    assert len(on_calls) == 1
    unsubscribe = entry.runtime_data.devices[device_id].unsubscribe

    subentry = _only_subentry(entry)
    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        title="Lamp 2",
        data={
            **subentry.data,
            CONF_ON_CHANGE_TO_ON: [{"action": "test.on2"}],
            CONF_ON_CHANGE_TO_OFF: [{"action": "test.off2"}],
        },
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    # Same subscription object, same baseline: a live ON equal to the baseline runs nothing
    assert entry.runtime_data.devices[device_id].unsubscribe is unsubscribe
    await _fire(hass, entry, device_id, "ON", retain=False)
    assert (len(on_calls), len(new_on_calls)) == (1, 0)
    # One live message causes exactly one run of the new actions, the old ones never run again
    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert (len(off_calls), len(new_off_calls)) == (0, 1)
    await _fire(hass, entry, device_id, "ON", retain=False)
    assert (len(on_calls), len(new_on_calls)) == (1, 1)
    # The previous Script is unloaded, only the one new Script of the device stays owned by the runner
    assert entry.runtime_data.runner.script_count(device_id) == 1
    # Discovery is republished with the new name
    published = _publishes(mqtt_mock, discovery_topic("homeassistant", device_id))
    assert len(published) == 2
    assert json.loads(published[-1][0])["device"]["name"] == "Lamp 2"
    assert entry.runtime_data.devices[device_id].name == "Lamp 2"


async def test_reconcile_change_run_on_startup_flag_takes_effect(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The flag changed while the startup window is still open applies to the first retained message."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, run_on_startup=False)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    subentry = _only_subentry(entry)
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_RUN_ON_STARTUP: True})
    await hass.async_block_till_done(wait_background_tasks=True)
    await _fire(hass, entry, device_id, "ON", retain=True)

    assert len(on_calls) == 1


async def test_reconcile_unchanged_device_is_left_alone(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Adding another device does not rebuild or republish the untouched one."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    on_script = entry.runtime_data.runner.script_for(device_id, SWITCH_ON_KEY)

    hass.config_entries.async_add_subentry(entry, _new_subentry(NEW_DEVICE_ID))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.runner.script_for(device_id, SWITCH_ON_KEY) is on_script
    assert len(_publishes(mqtt_mock, discovery_topic("homeassistant", device_id))) == 1


async def test_reconcile_change_clears_or_reraises_setup_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Reconfiguring clears the stale setup issue when the actions are valid now and re-raises it when they are not."""
    sub = make_switch_subentry("Lamp", on=[{"not_an_action": True}], off=OFF_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    assert _issue(hass, device_id) is not None

    subentry = _only_subentry(entry)
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_ON_CHANGE_TO_ON: ON_ACTIONS})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _issue(hass, device_id) is None
    assert entry.runtime_data.runner.can_run(device_id, SWITCH_ON_KEY) is True

    subentry = _only_subentry(entry)
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, CONF_ON_CHANGE_TO_OFF: [{"still_not_an_action": 1}]}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    issue = _issue(hass, device_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["trigger"] == "setup"
    assert entry.runtime_data.runner.can_run(device_id, SWITCH_OFF_KEY) is False


# --- explicit delete (DSC-02, D-16) --------------------------------------------------------------------------------


async def test_delete_device_clears_discovery_then_state(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-16: discovery is cleared first, then the subscription ends, then the retained state is cleared."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    events = _record_events(entry)
    discovery = discovery_topic("homeassistant", device_id)
    state = state_topic(STATE_TOPIC_BASE, device_id)

    hass.config_entries.async_remove_subentry(entry, _only_subentry(entry).subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert events == [("publish", discovery, ""), ("unsubscribe",), ("publish", state, "")]
    assert _publishes(mqtt_mock, discovery)[-1] == ("", 1, True)
    assert _publishes(mqtt_mock, state)[-1] == ("", 1, True)
    assert device_id not in entry.runtime_data.devices
    # The mocked client skips a second retained message per topic and subscription, a real broker forwards the
    # cleared topic live; deliver it that way and check that core MQTT drops the entity
    async_fire_mqtt_message(hass, discovery, "", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("switch.lamp") is None


async def test_delete_device_stops_actions_and_cleans_state(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """After removal nothing runs, the Scripts are gone, the Store forgets the device and its issue is deleted."""
    on_calls = async_mock_service(hass, "test", "on")
    _register_failing_service(hass)
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=FAIL_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "ON", retain=False)
    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert _issue(hass, device_id) is not None
    assert len(on_calls) == 1

    hass.config_entries.async_remove_subentry(entry, _only_subentry(entry).subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _fire(hass, entry, device_id, "ON", retain=False)
    await _fire(hass, entry, device_id, "OFF", retain=False)

    assert len(on_calls) == 1
    assert entry.runtime_data.runner.script_count(device_id) == 0
    assert _issue(hass, device_id) is None
    assert await hass.config_entries.async_unload(entry.entry_id)
    data = hass_storage[STORE_KEY]["data"]
    assert device_id not in data[STORE_LAST_ACTED]
    assert device_id not in data[STORE_PUBLISHED]


async def test_delete_device_own_subscription_never_sees_state_clear(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """The empty state publish is not delivered to the removed device: no call, no warning, no debug line."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    with caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"):
        caplog.clear()
        hass.config_entries.async_remove_subentry(entry, _only_subentry(entry).subentry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (len(on_calls), len(off_calls)) == (0, 0)
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert "Ignoring empty payload" not in caplog.text


async def test_delete_device_keeps_id_for_orphan_cleanup_when_mqtt_fails(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A failed clear still stops the device, and its id stays published so the next start retries the cleanup."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ):
        hass.config_entries.async_remove_subentry(entry, _only_subentry(entry).subentry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert device_id not in entry.runtime_data.devices
    assert "down" in caplog.text
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_PUBLISHED] == [device_id]


# --- orphan cleanup (DSC-02) ---------------------------------------------------------------------------------------


async def test_orphan_discovery_is_cleared_at_start(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A published id without a subentry (deleted while not loaded) is cleared at the next start and forgotten."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    _preload_store(hass_storage, published=[ORPHAN_ID, device_id], last_acted={ORPHAN_ID: "ON"})
    entry = await _setup(hass, make_hub_entry([sub]))

    assert _publishes(mqtt_mock, discovery_topic("homeassistant", ORPHAN_ID)) == [("", 1, True)]
    assert _publishes(mqtt_mock, state_topic(STATE_TOPIC_BASE, ORPHAN_ID)) == [("", 1, True)]
    (current_discovery,) = _publishes(mqtt_mock, discovery_topic("homeassistant", device_id))
    assert current_discovery[0] != ""
    assert _publishes(mqtt_mock, state_topic(STATE_TOPIC_BASE, device_id)) == []
    assert await hass.config_entries.async_unload(entry.entry_id)
    data = hass_storage[STORE_KEY]["data"]
    assert data[STORE_PUBLISHED] == [device_id]
    assert ORPHAN_ID not in data[STORE_LAST_ACTED]


# --- hub removal (D-15) --------------------------------------------------------------------------------------------


async def test_remove_entry_clears_all_owned_topics(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-15: removing the hub clears discovery, state and availability of every published and current device."""
    sub = make_switch_subentry("Lamp", on=[{"not_an_action": True}])
    device_id = _device_id(sub)
    _preload_store(hass_storage, published=[ORPHAN_ID])
    entry = await _setup(hass, make_hub_entry([sub]))
    instance_id = entry.data[CONF_INSTANCE_ID]
    assert _issue(hass, device_id) is not None

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for owned_id in (device_id, ORPHAN_ID):
        assert _publishes(mqtt_mock, discovery_topic("homeassistant", owned_id))[-1] == ("", 1, True)
        assert _publishes(mqtt_mock, state_topic(STATE_TOPIC_BASE, owned_id))[-1] == ("", 1, True)
    assert _publishes(mqtt_mock, availability_topic(STATE_TOPIC_BASE, instance_id))[-1] == ("", 1, True)
    assert STORE_KEY not in hass_storage
    assert _issues(hass) == []
    # Deliver the cleared discovery topic live, as a real broker does (see the delete test)
    async_fire_mqtt_message(hass, discovery_topic("homeassistant", device_id), "", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("switch.lamp") is None


async def test_remove_entry_survives_unavailable_mqtt(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-01-14: with MQTT unavailable the removal still completes and only logs a warning."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    assert await hass.config_entries.async_unload(entry.entry_id)

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ):
        assert await hass.config_entries.async_remove(entry.entry_id)

    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert STORE_KEY not in hass_storage
    assert [r for r in caplog.records if r.levelno == logging.WARNING and "MQTT" in r.getMessage()]


async def test_remove_entry_survives_mqtt_not_loaded(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """An MQTT entry that exists but is not loaded (broker down at start) must not block the removal either."""
    MockConfigEntry(domain="mqtt", data={"broker": "mock-broker"}).add_to_hass(hass)
    entry = make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)])
    entry.add_to_hass(hass)
    _preload_store(hass_storage, published=[ORPHAN_ID])

    assert await hass.config_entries.async_remove(entry.entry_id)

    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert STORE_KEY not in hass_storage
    assert [r for r in caplog.records if r.levelno == logging.WARNING and "MQTT" in r.getMessage()]


# --- startup readiness, reconnect, reload and unload (FND-05, DSC-02) -----------------------------------------------


def _empty_publishes(mqtt_mock: Any) -> list[str]:
    """Return the topics that received an empty payload (a delete) in the recorded publishes."""
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list if call.args[1] in {"", b""}]


async def test_setup_retry_without_mqtt(hass: HomeAssistant, make_hub_entry: Callable) -> None:
    """Without a ready MQTT client the entry retries instead of failing."""
    entry = make_hub_entry()
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_publishes_online_availability_and_discovery(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """After setup the instance availability is retained online and every device's discovery is published."""
    subs = [make_switch_subentry("Lamp"), make_switch_subentry("Fan")]
    entry = await _setup(hass, make_hub_entry(subs))

    availability = availability_topic(STATE_TOPIC_BASE, entry.data[CONF_INSTANCE_ID])
    assert _publishes(mqtt_mock, availability) == [("online", 1, True)]
    for sub in subs:
        (payload, qos, retain) = _publishes(mqtt_mock, discovery_topic("homeassistant", _device_id(sub)))[-1]
        assert payload != ""
        assert (qos, retain) == (1, True)


async def test_reconnect_republishes_availability_and_discovery(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A broker reconnect republishes availability and discovery retained; a disconnect changes nothing."""
    subs = [make_switch_subentry("Lamp"), make_switch_subentry("Fan")]
    entry = await _setup(hass, make_hub_entry(subs))
    availability = availability_topic(STATE_TOPIC_BASE, entry.data[CONF_INSTANCE_ID])
    mqtt_mock.async_publish.reset_mock()

    async_dispatcher_send(hass, mqtt.MQTT_CONNECTION_STATE, False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mqtt_mock.async_publish.call_args_list == []

    async_dispatcher_send(hass, mqtt.MQTT_CONNECTION_STATE, True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _publishes(mqtt_mock, availability) == [("online", 1, True)]
    for sub in subs:
        published = _publishes(mqtt_mock, discovery_topic("homeassistant", _device_id(sub)))
        assert len(published) == 1
        assert published[0][0] != ""
        assert published[0][1:] == (1, True)


async def test_unload_publishes_offline_and_never_clears_discovery(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """DSC-02: unload publishes a retained offline availability and deletes nothing on the broker."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "ON", retain=False)
    availability = availability_topic(STATE_TOPIC_BASE, entry.data[CONF_INSTANCE_ID])
    mqtt_mock.async_publish.reset_mock()
    runner = entry.runtime_data.runner

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert _publishes(mqtt_mock, availability) == [("offline", 1, True)]
    # No empty payload on any topic, in particular none on a config or state topic
    assert _empty_publishes(mqtt_mock) == []
    # Scripts are unloaded and the subscription is gone: a later live message runs nothing
    assert runner.script_count(device_id) == 0
    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert len(on_calls) == 1
    # The baseline was saved on the way out
    assert hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED][device_id] == "ON"
    assert hass_storage[STORE_KEY]["data"][STORE_PUBLISHED] == [device_id]


async def test_unload_survives_unavailable_mqtt(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A failing offline publish is logged and never blocks the unload or the final save."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)

    assert "down" in caplog.text
    assert hass_storage[STORE_KEY]["data"][STORE_PUBLISHED] == [_device_id(sub)]


async def test_reload_keeps_single_subscription(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """FND-05: after a reload one live message runs its action once."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _fire(hass, entry, _device_id(sub), "ON", retain=False)

    assert len(on_calls) == 1


async def test_unload_then_setup_republishes_without_clearing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Discovery is published again by the second setup and no empty payload appeared in between."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    discovery = discovery_topic("homeassistant", device_id)
    assert len(_publishes(mqtt_mock, discovery)) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(_publishes(mqtt_mock, discovery)) == 2
    assert _empty_publishes(mqtt_mock) == []
    availability = availability_topic(STATE_TOPIC_BASE, entry.data[CONF_INSTANCE_ID])
    assert _publishes(mqtt_mock, availability) == [("online", 1, True), ("offline", 1, True), ("online", 1, True)]


@pytest.mark.parametrize("mqtt_config_entry_options", [{mqtt.CONF_BIRTH_MESSAGE: {}, mqtt.CONF_DISCOVERY: False}])
async def test_discovery_disabled_creates_issue(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """With MQTT discovery disabled the setup warns and raises a non-fixable warning issue."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "mqtt_discovery_disabled")
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "mqtt_discovery_disabled"
    assert [r for r in caplog.records if r.levelno == logging.WARNING and "discovery" in r.getMessage().lower()]

    # Removing the hub takes the issue with it
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "mqtt_discovery_disabled") is None


async def test_discovery_enabled_deletes_stale_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """With discovery enabled no issue exists; a stale one from an earlier setup is deleted."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "mqtt_discovery_disabled",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="mqtt_discovery_disabled",
    )

    await _setup(hass, make_hub_entry())

    assert ir.async_get(hass).async_get_issue(DOMAIN, "mqtt_discovery_disabled") is None


async def test_failed_start_releases_subscriptions_and_retries_cleanly(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """WR-02: a subscribe failure halfway through the start leaves nothing behind, and the retry runs actions once."""
    on_calls = async_mock_service(hass, "test", "on")
    first = make_switch_subentry("First", on=ON_ACTIONS)
    second = make_switch_subentry("Second", on=ON_ACTIONS)
    entry = make_hub_entry([first, second])
    entry.add_to_hass(hass)
    real_subscribe = mqtt.async_subscribe
    calls = 0

    async def _subscribe(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            msg = "MQTT went away"
            raise HomeAssistantError(msg)
        return await real_subscribe(*args, **kwargs)

    with patch("custom_components.mqtt_actions.mqtt_gateway.mqtt.async_subscribe", side_effect=_subscribe):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    # The subscription of the device that did start was released again
    await _fire(hass, entry, _device_id(first), "ON", retain=False)
    assert len(on_calls) == 0

    # The retry builds a fresh manager: one live message runs the action exactly once
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _fire(hass, entry, _device_id(first), "ON", retain=False)
    assert len(on_calls) == 1


async def test_malformed_store_last_acted_is_dropped_and_setup_succeeds(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """WR-04: unhashable or wrongly typed baseline values are dropped; only the valid one survives."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    _preload_store(hass_storage, published=[device_id])
    hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED] = {
        device_id: "ON",
        "list-valued": [],
        "dict-valued": {"a": 1},
        "int-valued": 1,
        "unknown": "MAYBE",
    }

    entry = await _setup(hass, make_hub_entry([sub]))

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.devices[device_id].tracker.last_acted == "ON"
    assert entry.runtime_data._stored_last_acted == {device_id: "ON"}
