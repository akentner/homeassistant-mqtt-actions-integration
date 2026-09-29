"""Per-device circuit breaker. Pure logic without Home Assistant imports."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(slots=True)
class CircuitBreaker:
    """
    Sliding window over monotonic stamps that stops a device whose actions keep changing its own state (STA-06).

    Exactly max_runs runs are allowed per window; the next one trips the breaker and does not run. A tripped breaker
    stays tripped until it is reset: time passing never releases it (D-15). The clock is injected so tests control time.
    """

    max_runs: int
    window: float
    clock: Callable[[], float] = time.monotonic
    tripped: bool = False
    _stamps: deque[float] = field(default_factory=deque, init=False, repr=False)

    def record(self) -> bool:
        """Count one run; return False, and trip, when it would exceed max_runs within the window."""
        if self.tripped:
            return False
        now = self.clock()
        while self._stamps and now - self._stamps[0] >= self.window:
            self._stamps.popleft()
        if len(self._stamps) >= self.max_runs:
            self.tripped = True
            return False
        self._stamps.append(now)
        return True

    def trip(self) -> None:
        """Mark the breaker tripped without counting a run, for example when restoring a persisted trip."""
        self.tripped = True

    def reset(self) -> None:
        """Clear the trip and the window."""
        self.tripped = False
        self._stamps.clear()
