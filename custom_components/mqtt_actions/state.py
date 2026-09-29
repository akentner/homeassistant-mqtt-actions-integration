"""Edge detection for state messages. Pure functions without Home Assistant imports."""

from dataclasses import dataclass

from .const import PAYLOAD_OFF, PAYLOAD_ON


@dataclass(frozen=True, slots=True)
class Decision:
    """Outcome of processing one state message."""

    act: bool
    value: str | None = None
    baseline: str | None = None
    ignored: bool = False


def decide(
    retain: bool,  # noqa: FBT001
    payload: str,
    last_acted: str | None,
    startup_pending: bool,  # noqa: FBT001
    run_on_startup: bool,  # noqa: FBT001
) -> Decision:
    """
    Decide whether a state message runs the actions and what the new baseline is.

    A retained message is a replay caused by a (re)subscribe: it only moves the baseline (D-05), except for the first
    message after startup on a device with run_on_startup enabled (D-06). A live message is a real edge when it differs
    from the baseline; a device without a baseline acts on its first live message (D-14).
    """
    value = payload.strip().upper()
    if value not in {PAYLOAD_ON, PAYLOAD_OFF}:
        return Decision(act=False, baseline=last_acted, ignored=True)
    if retain:
        return Decision(act=startup_pending and run_on_startup, value=value, baseline=value)
    return Decision(act=value != last_acted, value=value, baseline=value)


@dataclass(slots=True)
class StateTracker:
    """Per-device state: the last processed value and the startup window for run_on_startup."""

    last_acted: str | None = None
    run_on_startup: bool = False
    startup_pending: bool = True

    def handle(self, retain: bool, payload: str) -> Decision:  # noqa: FBT001
        """Process one message, update the baseline for valid values and close the startup window."""
        decision = decide(retain, payload, self.last_acted, self.startup_pending, self.run_on_startup)
        self.startup_pending = False
        if not decision.ignored:
            self.last_acted = decision.baseline
        return decision
