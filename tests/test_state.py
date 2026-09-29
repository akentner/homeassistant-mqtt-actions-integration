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


SELECT_ACCEPTED = {"a": "A", "b": "B", "mixed case": "Mixed Case"}


@pytest.mark.parametrize(
    "case",
    [
        # Columns: retain, payload, last_acted, startup_pending, run_on_startup, act, value, baseline, ignored
        (False, "a", None, False, False, True, "A", "A", False),
        (False, " B\n", "A", False, False, True, "B", "B", False),
        # A retained value only moves the baseline
        (True, "b", "A", False, False, False, "B", "B", False),
        # The canonical StateValue is returned regardless of the payload casing
        (False, "Mixed CASE", None, False, False, True, "Mixed Case", "Mixed Case", False),
        # A live duplicate never acts
        (False, "B", "B", False, False, False, "B", "B", False),
        # Unknown payloads are ignored and leave the baseline untouched
        (False, "c", "A", False, False, False, None, "A", True),
        (False, "", "A", False, False, False, None, "A", True),
        # A retained unknown payload with the startup window open neither acts nor sets a baseline
        (True, "c", None, True, True, False, None, None, True),
    ],
)
def test_decide_select_table(
    case: tuple[bool, str, str | None, bool, bool, bool, str | None, str | None, bool],
) -> None:
    """The accepted-values map drives the decision: canonical value out, unknown payloads ignored (D-06, D-09)."""
    retain, payload, last_acted, startup_pending, run_on_startup, act, value, baseline, ignored = case
    decision = state.decide(retain, payload, last_acted, startup_pending, run_on_startup, accepted=SELECT_ACCEPTED)
    assert decision.act is act
    assert decision.value == value
    assert decision.baseline == baseline
    assert decision.ignored is ignored


def test_tracker_uses_its_accepted_map() -> None:
    """A tracker built with an accepted map handles option payloads and keeps the baseline as the StateValue."""
    tracker = state.StateTracker(accepted=SELECT_ACCEPTED)
    assert tracker.handle(False, "mixed case").act is True
    assert tracker.last_acted == "Mixed Case"
    assert tracker.handle(False, "MIXED CASE").act is False
    assert tracker.handle(False, "on").ignored is True
    assert tracker.last_acted == "Mixed Case"
