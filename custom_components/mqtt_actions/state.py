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
    act = value != last_acted
    return Decision(act=act, value=value, baseline=value if act else last_acted)
