"""Sliding-window circuit breaker (STA-06, D-14): pure logic with an injected clock."""

from custom_components.mqtt_actions.breaker import CircuitBreaker


class FakeClock:
    """A controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _breaker(max_runs: int, window: float) -> tuple[CircuitBreaker, FakeClock]:
    clock = FakeClock()
    return CircuitBreaker(max_runs, window, clock=clock), clock


def test_allows_max_runs_then_trips_on_the_next() -> None:
    """Exactly max_runs runs fit into a window; the next record trips and does not run."""
    breaker, clock = _breaker(3, 10)
    for now in (0, 1, 2):
        clock.now = now
        assert breaker.record() is True
    assert breaker.tripped is False

    clock.now = 3
    assert breaker.record() is False
    assert breaker.tripped is True


def test_window_boundary_prunes_at_exactly_window() -> None:
    """A stamp exactly one window old no longer counts; one a hundredth younger still does."""
    breaker, clock = _breaker(2, 10)
    clock.now = 0
    assert breaker.record() is True
    clock.now = 5
    assert breaker.record() is True
    clock.now = 10
    assert breaker.record() is True
    assert breaker.tripped is False

    other, other_clock = _breaker(2, 10)
    other_clock.now = 0
    assert other.record() is True
    other_clock.now = 5
    assert other.record() is True
    other_clock.now = 9.99
    assert other.record() is False
    assert other.tripped is True


def test_after_a_trip_nothing_counts_and_time_does_not_untrip() -> None:
    """A tripped breaker refuses every record, stores nothing and stays tripped however much time passes."""
    breaker, clock = _breaker(1, 10)
    clock.now = 0
    assert breaker.record() is True
    clock.now = 1
    assert breaker.record() is False
    stored = len(breaker._stamps)

    for now in (2, 3, 1000, 100000):
        clock.now = now
        assert breaker.record() is False
    assert len(breaker._stamps) == stored
    assert breaker.tripped is True


def test_single_run_limit_and_trip_and_reset() -> None:
    """With one allowed run the second trips; trip() marks it without a record; reset() clears trip and window."""
    breaker, clock = _breaker(1, 10)
    clock.now = 0
    assert breaker.record() is True
    clock.now = 1
    assert breaker.record() is False
    assert breaker.tripped is True

    breaker.reset()
    assert breaker.tripped is False
    assert len(breaker._stamps) == 0
    clock.now = 2
    assert breaker.record() is True

    other, _ = _breaker(3, 10)
    other.trip()
    assert other.tripped is True
    assert other.record() is False
    other.reset()
    assert other.tripped is False
    assert other.record() is True
