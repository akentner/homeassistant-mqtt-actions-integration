"""Pure tests for the device model: defaults, option order, malformed stored data and setting coercion."""

import math
import re
from typing import Any

import pytest

from custom_components.mqtt_actions.const import (
    CONF_ACTIONS,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_OPTIONS,
    CONF_RUN_MODE,
    CONF_STATE_VALUE,
    DEFAULT_BREAKER_MAX_RUNS,
    DEFAULT_BREAKER_WINDOW,
    RUN_MODE_RESTART,
    RUN_MODE_SERIAL,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY, spec_from_data, trigger_key

ACTIONS = [{"action": "test.on"}]


def _option(value: Any, friendly: Any, actions: Any = None) -> dict[str, Any]:
    return {CONF_STATE_VALUE: value, CONF_FRIENDLY_NAME: friendly, CONF_ACTIONS: actions if actions is not None else []}


def _select(options: Any, **extra: Any) -> Any:
    return spec_from_data(SUBENTRY_SELECT, "Mode", {CONF_DEVICE_ID: "dev-1", CONF_OPTIONS: options, **extra})


def test_spec_switch_defaults() -> None:
    """D-10, D-14: stored Switch data from Phase 1 gets serial, 5 runs in 10 seconds and no startup run."""
    data = {CONF_DEVICE_ID: "dev-1", CONF_ON_CHANGE_TO_ON: ACTIONS, CONF_ON_CHANGE_TO_OFF: []}

    spec = spec_from_data(SUBENTRY_SWITCH, "Lamp", data)

    assert spec.kind == SUBENTRY_SWITCH
    assert (spec.device_id, spec.name) == ("dev-1", "Lamp")
    assert spec.run_mode == RUN_MODE_SERIAL
    assert (spec.breaker_max_runs, spec.breaker_window) == (5, 10)
    assert spec.run_on_startup is False
    assert dict(spec.accepted) == {"on": "ON", "off": "OFF"}
    assert list(spec.triggers) == [SWITCH_ON_KEY, SWITCH_OFF_KEY]
    on, off = spec.triggers.values()
    assert (on.label, on.value, on.actions) == ("onChangeToOn", "ON", ACTIONS)
    assert (off.label, off.value, off.actions) == ("onChangeToOff", "OFF", [])


def test_spec_select_order_and_accepted_map() -> None:
    """D-05, D-06: options keep stored order and the accepted map holds each lowercased StateValue as stored."""
    spec = _select([_option("Beta", "B"), _option("alpha", "A"), _option("Gamma", "G")])

    assert spec.kind == SUBENTRY_SELECT
    assert list(spec.triggers) == [trigger_key("Beta"), trigger_key("alpha"), trigger_key("Gamma")]
    assert [trigger.friendly_name for trigger in spec.triggers.values()] == ["B", "A", "G"]
    assert dict(spec.accepted) == {"beta": "Beta", "alpha": "alpha", "gamma": "Gamma"}
    assert trigger_key("On") == trigger_key("ON")
    assert re.fullmatch(r"[0-9a-f]{12}", trigger_key("Beta"))


def test_spec_select_drops_malformed_options() -> None:
    """T-02-04: malformed, duplicate and unencodable options are dropped; the rest still builds a spec."""
    options = [
        "junk",
        5,
        None,
        {CONF_FRIENDLY_NAME: "no value"},
        {CONF_STATE_VALUE: "no friendly"},
        _option(5, "int value"),
        _option("int friendly", 5),
        _option("", "empty value"),
        _option(" leading", "padded"),
        _option("trailing ", "padded"),
        _option("empty friendly", ""),
        _option("\ud800", "lone surrogate value"),
        _option("lone surrogate friendly", "\ud800"),
        _option("Dup", "First"),
        _option("dup", "Second"),
        _option("ok", "Ok", "not a list"),
    ]

    spec = _select(options)

    assert [trigger.value for trigger in spec.triggers.values()] == ["Dup", "ok"]
    assert spec.triggers[trigger_key("Dup")].friendly_name == "First"
    assert spec.triggers[trigger_key("ok")].actions == []
    assert dict(spec.accepted) == {"dup": "Dup", "ok": "ok"}


@pytest.mark.parametrize("options", [None, "options", 5, {"a": 1}])
def test_spec_select_options_that_are_not_a_list_yield_no_triggers(options: Any) -> None:
    """Stored options of the wrong type never crash the loader."""
    spec = _select(options)

    assert spec.triggers == {}
    assert dict(spec.accepted) == {}


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (5.0, 5),
        (7, 7),
        (12.0, 12),
        (True, None),
        (False, None),
        (0, None),
        (-3, None),
        (0.5, None),
        (5.5, None),
        ("5", None),
        (None, None),
        (math.nan, None),
        (math.inf, None),
    ],
)
@pytest.mark.parametrize(
    ("key", "default", "attribute"),
    [
        (CONF_BREAKER_MAX_RUNS, DEFAULT_BREAKER_MAX_RUNS, "breaker_max_runs"),
        (CONF_BREAKER_WINDOW, DEFAULT_BREAKER_WINDOW, "breaker_window"),
    ],
)
def test_spec_breaker_coercion(stored: Any, expected: int | None, key: str, default: int, attribute: str) -> None:
    """Integral floats become ints; booleans, zero, negatives, fractions, strings and None fall back to the default."""
    spec = _select([_option("a", "A")], **{key: stored})

    value = getattr(spec, attribute)
    assert value == (default if expected is None else expected)
    assert type(value) is int


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (RUN_MODE_RESTART, RUN_MODE_RESTART),
        (RUN_MODE_SERIAL, RUN_MODE_SERIAL),
        ("parallel", RUN_MODE_SERIAL),
        (None, RUN_MODE_SERIAL),
        (5, RUN_MODE_SERIAL),
    ],
)
def test_spec_run_mode_coercion(stored: Any, expected: str) -> None:
    """A run mode other than serial or restart becomes serial."""
    assert _select([_option("a", "A")], **{CONF_RUN_MODE: stored}).run_mode == expected
