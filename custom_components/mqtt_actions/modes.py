"""Run, observe and disabled: pure helpers for the mode of a device and of the instance (D-14)."""

from typing import Any

from .const import MODE_DISABLED, MODE_OBSERVE, MODE_RUN, MODES

# The higher the rank, the more restrictive the mode
_RANK = {MODE_RUN: 0, MODE_OBSERVE: 1, MODE_DISABLED: 2}


def is_mode(value: Any) -> bool:
    """Return whether the value is exactly one of the three mode words; bools, numbers and other text are not."""
    return isinstance(value, str) and value in MODES


def most_restrictive(*modes: str) -> str:
    """Return the most restrictive mode, disabled over observe over run; run when there is none."""
    return max(modes, key=_RANK.__getitem__, default=MODE_RUN)
