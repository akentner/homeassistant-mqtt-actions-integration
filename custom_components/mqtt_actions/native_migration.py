"""
The migration of this instance from MQTT Discovery entities to native entities (D-09, FIX-02).

`NativeMigration` is a collaborator of the manager, like the sync, presence and retrigger parts: it holds a reference to
its manager and owns the orchestration of the migration. That is the cutover timer, the cutover check and its hint
issue, the native takeover pass with its finish, deferral and the retry of unconfirmed clears, the replay catch timer
and pass with the gate of the shared core-prefix topic, the duplicate guard listener and the per-run sets.

It never decides a registry question itself: `takeover.py` does, and it is always called through the module, so a test
that patches a function there keeps intercepting it. The persisted native state stays in the manager, which also keeps
the list of kept legacy devices that the heartbeat announces. Every `@callback` method is synchronous by contract.
"""

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later

from .const import CUTOVER_HINT_MAX_NAMES, CUTOVER_SETTLE_SECONDS, DOMAIN, ISSUE_NATIVE_CUTOVER_WAITING
from .document import escape_markdown

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE

    from .manager import Manager


class NativeMigration:
    """Moves the devices of this instance to native entities and keeps their legacy duplicates away."""

    def __init__(self, manager: Manager) -> None:
        """Initialize the migration of one manager; nothing is armed before the start."""
        self._manager = manager
        # The wait before the first cutover check, read once so a test can turn the timer off; None means none (D-09)
        self.cutover_settle_seconds: float | None = CUTOVER_SETTLE_SECONDS
        self._cancel_cutover: CALLBACK_TYPE | None = None
        # Set once the settle time has passed; only then does a roster change start a cutover check
        self._cutover_ready = False
        # The blocking peers the hint issue shows now, so an unchanged set does not rebuild the issue on every heartbeat
        self._cutover_hint: tuple[str, ...] | None = None

    @callback
    def arm_timers(self) -> None:
        """Arm the timers of a start: the cutover; the start calls it after the first heartbeat."""
        self._arm_cutover()

    @callback
    def stop(self) -> None:
        """Disarm everything of this run; the manager calls it right after it stopped running."""
        self._cutover_ready = False
        if self._cancel_cutover is not None:
            self._cancel_cutover()
            self._cancel_cutover = None

    @callback
    def _arm_cutover(self) -> None:
        """Wait the settle time before the first cutover check; a native instance never waits or checks (D-09)."""
        if self._manager.native_state.instance or self.cutover_settle_seconds is None:
            return
        self._cancel_cutover = async_call_later(self._manager.hass, self.cutover_settle_seconds, self._on_cutover_due)

    @callback
    def _on_cutover_due(self, _now: object) -> None:
        """Start trusting the roster once the settle time passed, and check at once (D-09)."""
        self._cancel_cutover = None
        self._cutover_ready = True
        self._start_cutover_check()

    @callback
    def on_roster_changed(self) -> None:
        """Re-run the cutover check after the roster, an announced presence or the time changed (D-10)."""
        if self._cutover_ready:
            self._start_cutover_check()

    @callback
    def _start_cutover_check(self) -> None:
        """Start the check in a background task of the entry; it takes the lock, which a callback cannot await."""
        if not self._manager.running or self._manager.native_state.instance:
            return
        self._manager.entry.async_create_background_task(
            self._manager.hass, self._async_cutover_check(), name=f"{DOMAIN} cutover"
        )

    async def _async_cutover_check(self) -> None:
        """
        Switch this instance to native entities once no online peer is a legacy instance (D-09, D-10, D-12, MIG-02).

        The flag is persisted before the reload and checked first, so the switch happens exactly once (T-5-13). Every
        owned device that is not native yet becomes pending and the reload runs the takeover pass before the platform
        forward; nothing is moved or published here. Without such a device the flag alone is enough.
        """
        async with self._manager.lock:
            if not self._manager.running or self._manager.native_state.instance:
                return
            if blocking := self._manager.presence.blocking_peers():
                self._show_cutover_hint(tuple(blocking))
                return
            self._clear_cutover_hint()
            self._manager.native_state.instance = True
            self._manager.native_state.pending.update(self._manager.devices.keys() - self._manager.native_state.devices)
            await self._manager.async_save_now()
            if self._manager.native_state.pending:
                self._manager.hass.config_entries.async_schedule_reload(self._manager.entry.entry_id)

    @callback
    def _show_cutover_hint(self, blocking: tuple[str, ...]) -> None:
        """
        Explain in Repairs why this instance still uses MQTT Discovery; only the first names are shown (D-10, T-5-14).

        The names come from the broker, so they are escaped and capped, and they are never logged. The issue is deleted
        first so that a changed set of peers refreshes the text.
        """
        if blocking == self._cutover_hint:
            return
        self._cutover_hint = blocking
        shown = ", ".join(escape_markdown(name) for name in blocking[:CUTOVER_HINT_MAX_NAMES])
        instances = f"{shown} …" if len(blocking) > CUTOVER_HINT_MAX_NAMES else shown
        ir.async_delete_issue(self._manager.hass, DOMAIN, ISSUE_NATIVE_CUTOVER_WAITING)
        ir.async_create_issue(
            self._manager.hass,
            DOMAIN,
            ISSUE_NATIVE_CUTOVER_WAITING,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NATIVE_CUTOVER_WAITING,
            translation_placeholders={"instances": instances},
        )

    @callback
    def _clear_cutover_hint(self) -> None:
        """Delete the hint; the cutover proceeds, so there is nothing left to wait for."""
        self._cutover_hint = None
        ir.async_delete_issue(self._manager.hass, DOMAIN, ISSUE_NATIVE_CUTOVER_WAITING)
