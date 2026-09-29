"""Integration tests for Select devices: option edges, payload mapping, startup, unknown payloads and lifecycle."""

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_OPTIONS,
    DOMAIN,
    MAX_LOGGED_PAYLOAD_LENGTH,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_PUBLISHED,
    STORE_VERSION,
)
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
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


ORPHAN_ID = "5d9c1b0e-7c55-4c1e-8a11-0f7c3a9b2d44"


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _preload_store(
    hass_storage: dict[str, Any], *, published: list[str], last_acted: dict[str, str] | None = None
) -> None:
    """Put a persisted store into the test storage before the entry is set up."""
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {STORE_LAST_ACTED: last_acted or {}, STORE_PUBLISHED: published},
    }


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


# --- unknown payloads (STA-07, D-09) ------------------------------------------------------------------------------


async def test_select_unknown_payload_is_ignored_and_logged(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """A payload that is no StateValue logs the device name and a truncated repr, runs nothing, keeps the baseline."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "a", retain=False)

    with caplog.at_level(logging.DEBUG, logger="custom_components.mqtt_actions"):
        caplog.clear()
        await _fire(hass, entry, device_id, "nope", retain=False)
        (warning,) = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert "Mode" in warning.getMessage()
        assert "'nope'" in warning.getMessage()

        caplog.clear()
        await _fire(hass, entry, device_id, "x\nforged log line " + "y" * 500, retain=False)
        (long_warning,) = [r for r in caplog.records if r.levelno == logging.WARNING]
        message = long_warning.getMessage()
        assert "\n" not in message
        assert "Mode" in message
        # The repr of at most MAX_LOGGED_PAYLOAD_LENGTH characters plus the ellipsis marker, never the full payload
        assert "y" * (MAX_LOGGED_PAYLOAD_LENGTH - 10) not in message
        assert "'..." in message
        assert len(message) < 100

        caplog.clear()
        await _fire(hass, entry, device_id, "", retain=False)
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    assert (len(calls["a"]), len(calls["b"]), len(calls["c"])) == (1, 0, 0)
    assert entry.runtime_data.devices[device_id].tracker.last_acted == "a"
    # The baseline is untouched by the ignored payloads: a live "a" is still a duplicate
    await _fire(hass, entry, device_id, "a", retain=False)
    assert len(calls["a"]) == 1


async def test_select_unknown_retained_payload_sets_no_baseline(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """D-09: a retained unknown payload sets no baseline, so the following live option payload acts."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry("Mode", ABC_OPTIONS, run_on_startup=True)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _fire(hass, entry, device_id, "nope", retain=True)
    assert entry.runtime_data.devices[device_id].tracker.last_acted is None
    assert len(calls["a"]) == 0

    await _fire(hass, entry, device_id, "a", retain=False)
    assert len(calls["a"]) == 1


# --- startup and baseline (D-08, D-02) ----------------------------------------------------------------------------


async def test_select_retained_state_is_baseline_only_and_startup_flag_runs_once(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """D-08: retained state only sets the baseline; the flag runs the retained option once per start."""
    plain_calls = async_mock_service(hass, "test", "plain")
    flag_calls = async_mock_service(hass, "test", "flag")
    plain = make_select_subentry("Plain", [("a", "A", []), ("b", "B", [{"action": "test.plain"}])])
    flagged = make_select_subentry(
        "Flagged", [("a", "A", []), ("b", "B", [{"action": "test.flag"}])], run_on_startup=True
    )
    entry = await _setup(hass, make_hub_entry([plain, flagged]))

    await _fire(hass, entry, _device_id(plain), "b", retain=True)
    await _fire(hass, entry, _device_id(plain), "b", retain=False)
    assert len(plain_calls) == 0

    await _fire(hass, entry, _device_id(flagged), "b", retain=True)
    await _fire(hass, entry, _device_id(flagged), "b", retain=True)
    assert len(flag_calls) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _fire(hass, entry, _device_id(flagged), "b", retain=True)
    await _fire(hass, entry, _device_id(flagged), "b", retain=True)
    assert len(flag_calls) == 2
    assert len(plain_calls) == 0


async def test_select_removed_state_value_becomes_unknown(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-02: after an option is removed its payload is unknown and, as the baseline, it resets to none."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "b", retain=False)
    assert len(calls["b"]) == 1

    subentry = next(iter(entry.subentries.values()))
    kept = [option for option in subentry.data[CONF_OPTIONS] if option["state_value"] != "b"]
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_OPTIONS: kept})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.devices[device_id].tracker.last_acted is None

    with caplog.at_level(logging.WARNING, logger="custom_components.mqtt_actions"):
        caplog.clear()
        await _fire(hass, entry, device_id, "b", retain=False)
        (warning,) = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert "Mode" in warning.getMessage()
    assert len(calls["b"]) == 1
    assert entry.runtime_data.devices[device_id].tracker.last_acted is None

    await _fire(hass, entry, device_id, "c", retain=False)
    assert len(calls["c"]) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED][device_id] == "c"


async def test_select_baseline_persisted_across_reload(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """A live option value is stored as its exact StateValue; an equal live payload after reload runs nothing."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry(
        "Mode", [("a", "Alpha", [{"action": "test.a"}]), ("Bee", "Bravo", [{"action": "test.b"}])]
    )
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _fire(hass, entry, device_id, "BEE", retain=False)
    assert len(calls["b"]) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED][device_id] == "Bee"

    await _fire(hass, entry, device_id, "bee", retain=False)
    assert len(calls["b"]) == 1
    await _fire(hass, entry, device_id, "a", retain=False)
    assert len(calls["a"]) == 1


async def test_stored_baseline_that_is_not_a_state_value_is_dropped(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """A stored last_acted that is no StateValue of its device is ignored at start, so the next live payload acts."""
    calls = _services(hass, "a", "b", "c")
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    device_id = _device_id(sub)
    _preload_store(hass_storage, published=[device_id], last_acted={device_id: "ghost"})
    entry = await _setup(hass, make_hub_entry([sub]))
    assert entry.runtime_data.devices[device_id].tracker.last_acted is None

    await _fire(hass, entry, device_id, "a", retain=False)
    assert len(calls["a"]) == 1


# --- orphan cleanup and hub removal -------------------------------------------------------------------------------


async def test_select_orphan_topics_cleared_at_start(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """A published id without a subentry is cleared at start while the current Select device is left alone."""
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    device_id = _device_id(sub)
    _preload_store(hass_storage, published=[ORPHAN_ID, device_id], last_acted={ORPHAN_ID: "a", device_id: "b"})
    entry = await _setup(hass, make_hub_entry([sub]))

    assert _publishes(mqtt_mock, discovery_topic("homeassistant", ORPHAN_ID)) == [("", 1, True)]
    assert _publishes(mqtt_mock, state_topic(entry.data["base_topic"], ORPHAN_ID)) == [("", 1, True)]
    (current_discovery,) = _publishes(mqtt_mock, discovery_topic("homeassistant", device_id))
    assert current_discovery[0] != ""
    assert _publishes(mqtt_mock, state_topic(entry.data["base_topic"], device_id)) == []
    assert entry.runtime_data.devices[device_id].tracker.last_acted == "b"
    assert await hass.config_entries.async_unload(entry.entry_id)
    data = hass_storage[STORE_KEY]["data"]
    assert data[STORE_PUBLISHED] == [device_id]
    assert ORPHAN_ID not in data[STORE_LAST_ACTED]


async def test_remove_entry_clears_select_device_topics(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """Removing the hub clears the discovery and state topics of a current Select device and the orphan."""
    sub = make_select_subentry("Mode", ABC_OPTIONS)
    device_id = _device_id(sub)
    _preload_store(hass_storage, published=[ORPHAN_ID])
    entry = await _setup(hass, make_hub_entry([sub]))
    instance_id = entry.data["instance_id"]

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for owned_id in (device_id, ORPHAN_ID):
        assert _publishes(mqtt_mock, discovery_topic("homeassistant", owned_id))[-1] == ("", 1, True)
        assert _publishes(mqtt_mock, state_topic("mqtt_actions", owned_id))[-1] == ("", 1, True)
    assert _publishes(mqtt_mock, availability_topic("mqtt_actions", instance_id))[-1] == ("", 1, True)
    assert STORE_KEY not in hass_storage
