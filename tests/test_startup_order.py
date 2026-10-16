"""
The start-up order of the native migration as an executable sequence (Phase 10 FIX-02, research Pitfall 8).

Written before the extraction of `NativeMigration`, so the move is proven against an order that was pinned while the
code still lived in `Manager`. Every spy sits on a seam that does not move: the collaborators (`SyncManager`,
`PresenceManager`, `RetriggerCoordinator`), `DiscoveryPublisher`, the `takeover` module functions and the `Manager`
methods that stay in `Manager`. This module therefore stays byte-identical through the move.

The module also holds the pins that the pre-move mutation survey asked for: one test per migration method whose
neutral early return the rest of the suite did not notice.
"""

from __future__ import annotations

import functools
import inspect
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.discovery import DiscoveryPublisher
from custom_components.mqtt_actions.manager import Manager
from custom_components.mqtt_actions.presence import PresenceManager
from custom_components.mqtt_actions.retrigger import RetriggerCoordinator
from custom_components.mqtt_actions.sync import SyncManager
from tests.helpers import loop_back_discovery, quiet_period_passes, setup_legacy_device, unloaded_legacy_device

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

# A little more than CUTOVER_SETTLE_SECONDS, and a literal on purpose, like QUIET_PERIOD_PASSED in tests/helpers.py
SETTLE_PASSED = 6.0

# (owner, attribute, label) of every seam the start-up order is read from; none of them moves with the migration
START_UP_SEAMS: tuple[tuple[Any, str, str], ...] = (
    (SyncManager, "async_start", "sync"),
    (PresenceManager, "async_start", "presence"),
    (RetriggerCoordinator, "async_start", "retrigger"),
    (Manager, "_async_orphan_cleanup", "orphans"),
    (Manager, "_async_reconcile_locked", "reconcile"),
    (DiscoveryPublisher, "async_publish_migrate", "migrate"),
    (takeover, "async_take_over", "take_over"),
    (takeover, "remove_replay_twins", "replay_twins"),
    (takeover, "async_flush_registries", "flush"),
    (DiscoveryPublisher, "async_clear_device", "clear"),
    (takeover, "disable_duplicates", "guard"),
    (Manager, "async_publish_config", "config"),
    (Manager, "async_publish_discovery", "discovery"),
    (Manager, "_check_discovery_enabled", "discovery_check"),
    (Manager, "_async_publish_availability", "availability"),
    (PresenceManager, "async_publish_heartbeat", "heartbeat"),
)


@pytest.fixture(autouse=True)
def fast_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll quickly; the default wait is long only because production waits for a real broker round trip."""
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)


def _spy(monkeypatch: pytest.MonkeyPatch, owner: Any, name: str, record: Callable[[], None]) -> None:
    """Replace `owner.name` by a wrapper that records first and then calls the original, sync or async alike."""
    original = getattr(owner, name)
    if inspect.iscoroutinefunction(original):

        @functools.wraps(original)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            record()
            return await original(*args, **kwargs)

        monkeypatch.setattr(owner, name, _async_wrapper)
        return

    @functools.wraps(original)
    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        record()
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, _wrapper)


def _record_start_up(monkeypatch: pytest.MonkeyPatch, entry: MockConfigEntry) -> list[tuple[str, bool]]:
    """
    Spy on every start-up seam; each call appends (label, whether the manager lock is held at that moment).

    The lock is read from `entry.runtime_data` at call time, so the list shows where the lock boundary runs.
    """
    calls: list[tuple[str, bool]] = []

    def _recorder(label: str) -> Callable[[], None]:
        def _record() -> None:
            calls.append((label, entry.runtime_data.lock.locked()))

        return _record

    for owner, name, label in START_UP_SEAMS:
        _spy(monkeypatch, owner, name, _recorder(label))
    return calls


def _count_calls(monkeypatch: pytest.MonkeyPatch, owner: Any, name: str) -> list[None]:
    """Spy on one seam and return the list that grows by one entry per call."""
    calls: list[None] = []
    _spy(monkeypatch, owner, name, lambda: calls.append(None))
    return calls


def _up_to_first_heartbeat(calls: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    labels = [label for label, _locked in calls]
    assert "heartbeat" in labels, calls
    return calls[: labels.index("heartbeat") + 1]


async def test_the_start_up_order_of_an_upgrading_owner_is_fixed(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An owner whose device waits for the takeover starts in exactly this order, with the lock held where shown.

    Lock held from the sync start to the second discovery check; not held for the first discovery check, the online
    availability and the heartbeat (research Pitfall 8). The duplicate guard is armed before the owned devices are
    published, and the takeover pass runs migrate, takeover, replay-twin removal, flush, fresh migrate, clear.
    """
    legacy, _before = await unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    loop_back_discovery(hass, mqtt_mock)
    calls = _record_start_up(monkeypatch, legacy.entry)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _up_to_first_heartbeat(calls) == [
        ("discovery_check", False),
        ("sync", True),
        ("presence", True),
        ("retrigger", True),
        ("orphans", True),
        ("reconcile", True),
        ("migrate", True),
        ("take_over", True),
        ("replay_twins", True),
        ("flush", True),
        ("migrate", True),
        ("clear", True),
        ("guard", True),
        ("config", True),
        ("discovery", True),
        ("discovery_check", True),
        ("availability", False),
        ("heartbeat", False),
    ]


async def test_the_replay_catch_runs_only_after_the_quiet_period(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The catch for replayed duplicates has not run when the setup returns; it runs once the quiet period passed."""
    legacy, _before = await unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    loop_back_discovery(hass, mqtt_mock)
    # Only the catch reads the discovery content of a topic
    reads = _count_calls(monkeypatch, SyncManager, "discovery_content")

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert reads == []

    await quiet_period_passes(hass)
    assert reads


@pytest.mark.usefixtures("enable_native_cutover")
async def test_the_cutover_check_waits_for_the_settle_time(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cutover check of a legacy instance has not run when the setup returns; it runs after the settle time."""
    # Only the cutover check asks for the peers that block it
    checks = _count_calls(monkeypatch, PresenceManager, "blocking_peers")

    await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    assert checks == []

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=SETTLE_PASSED))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert checks


# --- Pins the pre-move mutation survey asked for (mutation/pre-move.tsv) ------------------------------------------


def _registry_listeners(hass: HomeAssistant) -> int:
    return hass.bus.async_listeners().get(er.EVENT_ENTITY_REGISTRY_UPDATED, 0)


async def test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """
    An unload stops the duplicate guard: a load and unload cycle leaves no entity registry listener behind.

    The guard of a native owner listens to every entity registry update while the manager runs. The stop has to end
    that listener, or every unload and reload leaves one more listener on the bus that holds the stopped manager. The
    first cycle takes the device over; the second cycle starts and stops a native owner with the guard armed.
    """
    legacy, _before = await unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    loop_back_discovery(hass, mqtt_mock)
    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    after_first_cycle = _registry_listeners(hass)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Premise: the device is native, so the guard is armed and listens while the entry is loaded
    assert legacy.entry.runtime_data.is_native(legacy.device_id) is True
    assert _registry_listeners(hass) > after_first_cycle

    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _registry_listeners(hass) == after_first_cycle
