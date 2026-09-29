"""Pure tests for the decision function and the per-device state tracker (no Home Assistant needed)."""

import pytest

from custom_components.mqtt_actions import state


@pytest.mark.parametrize(
    "case",
    [
        # Retained replays only move the baseline (D-05, STA-04)
        (True, "ON", None, True, False, False, "ON"),
        (True, "ON", None, False, False, False, "ON"),
        (True, "OFF", "ON", True, False, False, "OFF"),
        (True, "OFF", "ON", False, True, False, "OFF"),
        # Run-on-startup: the retained state counts as a change once, even when equal to the baseline (D-06)
        (True, "ON", "ON", True, True, True, "ON"),
        (True, "ON", None, True, True, True, "ON"),
        (True, "ON", "ON", False, True, False, "ON"),
        (True, "ON", "ON", True, False, False, "ON"),
        # Live edges (STA-02); a device without baseline acts on its first live message (D-14)
        (False, "ON", None, True, False, True, "ON"),
        (False, "OFF", None, False, False, True, "OFF"),
        (False, "ON", "ON", False, False, False, "ON"),
        (False, "OFF", "ON", False, False, True, "OFF"),
        (False, "ON", "OFF", False, False, True, "ON"),
        # A live duplicate never acts, even with the startup flag pending
        (False, "ON", "ON", True, True, False, "ON"),
        # Payload normalisation (D-02)
        (False, " on ", None, False, False, True, "ON"),
        (False, "On", None, False, False, True, "ON"),
        (False, "off\n", "ON", False, False, True, "OFF"),
        (True, "off\n", "ON", False, False, False, "OFF"),
        # Unknown payloads are ignored and leave the baseline untouched
        (False, "toggle", "ON", False, False, False, "ON"),
        (False, "true", None, False, False, False, None),
        (False, "", "OFF", False, False, False, "OFF"),
        (True, "", "OFF", True, True, False, "OFF"),
    ],
)
def test_decide_table(case: tuple[bool, str, str | None, bool, bool, bool, str | None]) -> None:
    """Every row of the decision table from the research (Pattern 3)."""
    retain, payload, last_acted, startup_pending, run_on_startup, act, baseline = case
    decision = state.decide(retain, payload, last_acted, startup_pending, run_on_startup)
    assert decision.act is act
    assert decision.baseline == baseline
    assert decision.ignored is (payload.strip().upper() not in {"ON", "OFF"})


def test_decide_normalises_value() -> None:
    """The decision carries the normalised value that selects the script."""
    assert state.decide(False, " on ", None, False, False).value == "ON"
    assert state.decide(False, "off\n", "ON", False, False).value == "OFF"


@pytest.mark.parametrize("payload", ["ON", "toggle", ""])
@pytest.mark.parametrize("retain", [True, False])
def test_tracker_startup_pending_cleared_by_first_message(payload: str, retain: bool) -> None:
    """Any first message, even an ignored one, ends the startup window."""
    tracker = state.StateTracker(run_on_startup=True)
    assert tracker.startup_pending is True
    tracker.handle(retain, payload)
    assert tracker.startup_pending is False


def test_tracker_run_on_startup_acts_once_on_retain() -> None:
    """The first retained message acts with the flag on; a later replay does not."""
    tracker = state.StateTracker(last_acted="ON", run_on_startup=True)
    assert tracker.handle(True, "ON").act is True
    assert tracker.handle(True, "ON").act is False


def test_tracker_without_flag_never_acts_on_retain() -> None:
    """Retained messages are baseline-only when the flag is off."""
    tracker = state.StateTracker()
    assert tracker.handle(True, "ON").act is False
    assert tracker.last_acted == "ON"
    assert tracker.handle(True, "OFF").act is False
    assert tracker.last_acted == "OFF"


def test_tracker_last_acted_none_until_first_valid_message() -> None:
    """D-07: ignored payloads never set a baseline."""
    tracker = state.StateTracker()
    for payload in ("toggle", "true", "", "1"):
        tracker.handle(False, payload)
        tracker.handle(True, payload)
        assert tracker.last_acted is None
    tracker.handle(False, "ON")
    assert tracker.last_acted == "ON"


def test_tracker_live_duplicate_keeps_baseline() -> None:
    """A repeated live value acts once."""
    tracker = state.StateTracker()
    assert tracker.handle(False, "ON").act is True
    assert tracker.handle(False, "ON").act is False
    assert tracker.handle(False, "OFF").act is True
