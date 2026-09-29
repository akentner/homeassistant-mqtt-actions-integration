"""Integration tests for the manager: edges, retained replays, run-on-startup and the persisted baseline."""

import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_RUN_ON_STARTUP,
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
    from homeassistant.core import HomeAssistant
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
