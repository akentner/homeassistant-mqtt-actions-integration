"""Per-device circuit breaker. Pure logic without Home Assistant imports."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(slots=True)
class CircuitBreaker:
    """Sliding window over monotonic stamps; RED scaffold that never trips."""

    max_runs: int
    window: float
    clock: Callable[[], float] = time.monotonic
    tripped: bool = False
    _stamps: deque[float] = field(default_factory=deque, init=False, repr=False)

    def record(self) -> bool:
        """Count one run; the scaffold allows everything."""
        return True

    def trip(self) -> None:
        """Mark the breaker tripped (scaffold: no-op)."""

    def reset(self) -> None:
        """Clear the trip and the window (scaffold: no-op)."""
