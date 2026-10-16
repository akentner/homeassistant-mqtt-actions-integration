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

import asyncio
from functools import partial
from typing import TYPE_CHECKING, NamedTuple

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later

from . import takeover
from .const import (
    CUTOVER_HINT_MAX_NAMES,
    CUTOVER_SETTLE_SECONDS,
    DOMAIN,
    HEARTBEAT_INTERVAL_SECONDS,
    ISSUE_KEPT_DUPLICATES,
    ISSUE_NATIVE_CUTOVER_WAITING,
    KEPT_DUPLICATES_MAX_SHOWN,
    LOGGER,
)
from .discovery import DiscoveryContent
from .document import escape_markdown
from .mqtt_gateway import async_attempt
from .presence import EXPIRY_MARGIN_SECONDS
from .topics import test_topic

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from homeassistant.core import CALLBACK_TYPE, Event

    from .manager import Manager


class TwinRemoval(NamedTuple):
    """
    The result of one pass of the duplicate removal over a set of devices (FIX-06).

    `removed` counts the rows whose removal returned, including those of a device that raised later; `errored` says
    that at least one device raised, so the caller flushes even when nothing was counted.
    """

    removed: int
    errored: bool


# The placeholder of a reason without a kept duplicate, the empty-value convention of the dialogs
NONE_SHOWN = "—"


def kept_duplicates_placeholders(rows: Iterable[tuple[str, takeover.KeptReason]]) -> dict[str, str]:
    """
    Return the placeholders of the kept-duplicates warning: the total and the entity ids per reason (FIX-08, D-01).

    The ids are local registry data, never broker content; they are still sorted, escaped for Markdown and capped at
    KEPT_DUPLICATES_MAX_SHOWN per reason, followed by an ellipsis when more are kept. A reason without a row shows a
    dash. The reason labels are translated text, so they stay out of the placeholders.
    """
    rows = list(rows)

    def _shown(reason: takeover.KeptReason) -> str:
        entity_ids = sorted(entity_id for entity_id, kept in rows if kept is reason)
        if not entity_ids:
            return NONE_SHOWN
        shown = ", ".join(escape_markdown(entity_id) for entity_id in entity_ids[:KEPT_DUPLICATES_MAX_SHOWN])
        return f"{shown} …" if len(entity_ids) > KEPT_DUPLICATES_MAX_SHOWN else shown

    return {
        "count": str(len(rows)),
        "customized": _shown(takeover.KeptReason.CUSTOMIZED),
        "rejected": _shown(takeover.KeptReason.TWIN_REJECTED),
    }


class NativeMigration:
    """Moves the devices of this instance to native entities and keeps their legacy duplicates away."""

    def __init__(self, manager: Manager) -> None:
        """Initialize the migration of one manager; nothing is armed before the start."""
        self._manager = manager
        # Owned or mirrored devices whose takeover could not run yet; they use the legacy path for this run only and
        # their id stays pending in the Store, so the next setup retries (T-5-08)
        self._legacy_this_run: set[str] = set()
        # Owned devices whose entities were moved to this integration but whose retained discovery could not be cleared
        # yet: native for this run, pending in the Store, and the clear is retried on the next republish (WR-02)
        self._clear_unconfirmed: set[str] = set()
        # The wait before the first cutover check, read once so a test can turn the timer off; None means none (D-09)
        self.cutover_settle_seconds: float | None = CUTOVER_SETTLE_SECONDS
        self._cancel_cutover: CALLBACK_TYPE | None = None
        # The timer of the catch for duplicates a replayed legacy discovery creates; None while none is armed (D-05)
        self._cancel_replay_catch: CALLBACK_TYPE | None = None
        # How often the catch of this start checked again, because the discovery settle was not done yet (WR-02) or an
        # online peer was not heard yet (D-04); both reasons share the bound REPLAY_CATCH_RETRIES
        self._replay_catch_retries = 0
        # Set once the start-up catch was armed in this run; only then may an emptied topic arm it again (D-06)
        self._replay_catch_armed = False
        # The registry listener that disables an enabled duplicate of a native device; None while the manager is stopped
        self._cancel_duplicate_guard: CALLBACK_TYPE | None = None
        # Set once the settle time has passed; only then does a roster change start a cutover check
        self._cutover_ready = False
        # The blocking peers the hint issue shows now, so an unchanged set does not rebuild the issue on every heartbeat
        self._cutover_hint: tuple[str, ...] | None = None

    @callback
    def arm_timers(self) -> None:
        """Arm the timers of a start, the cutover and then the replay catch; the start calls it after the heartbeat."""
        self._arm_cutover()
        # Core replays retained discovery at its own pace and the order of its messages is no signal, so the catch for
        # replayed duplicates waits a quiet period instead of a settle event that does not exist (D-05)
        self._arm_replay_catch()

    @callback
    def stop(self) -> None:
        """Disarm everything of this run; the manager calls it right after it stopped running."""
        self._cutover_ready = False
        if self._cancel_cutover is not None:
            self._cancel_cutover()
            self._cancel_cutover = None
        if self._cancel_replay_catch is not None:
            self._cancel_replay_catch()
            self._cancel_replay_catch = None
        self._replay_catch_armed = False
        self._disarm_duplicate_guard()

    def is_deferred(self, device_id: str) -> bool:
        """Return whether the takeover of a device was deferred, so it runs on the legacy path for this run (T-5-08)."""
        return device_id in self._legacy_this_run

    def clear_pending(self, device_id: str) -> bool:
        """Return whether a device moved but the retained clear of its discovery is still outstanding (WR-02)."""
        return device_id in self._clear_unconfirmed

    @callback
    def defer_for_run(self, device_id: str) -> None:
        """Keep a device on the legacy path for this run; the takeover of the next start moves it (D-12)."""
        self._legacy_this_run.add(device_id)

    @callback
    def forget(self, device_id: str) -> None:
        """Forget the per-run bookkeeping of a device that is deleted or released here."""
        self._legacy_this_run.discard(device_id)
        self._clear_unconfirmed.discard(device_id)

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

    def _native_device_ids(self) -> list[str]:
        """Return the sorted ids of the owned devices and mirrors that are native; a deferred device is never one."""
        return sorted(
            device_id
            for device_id in {*self._manager.devices, *self._manager.mirrors}
            if self._manager.is_native(device_id)
        )

    def _topic_verdict(
        self, device_id: str, content: DiscoveryContent, mqtt_entry_id: str | None
    ) -> takeover.TopicVerdict:
        """
        Return what the catch may do on the shared core-prefix topic of a device, from the inputs now (D-02 to D-05).

        The role (an owned device not adopted by another instance is the owner's, anything else a follower's), this
        instance's own enabled kept legacy row and what the online peers announce, read now: a caller that awaited in
        between reads it again (D-10).
        """
        owner = device_id in self._manager.devices and device_id not in self._manager.sync.transferred_away
        local_keeps = mqtt_entry_id is not None and takeover.keeps_enabled_legacy_row(
            self._manager.hass, self._manager.entry.entry_id, device_id, mqtt_entry_id=mqtt_entry_id
        )
        return takeover.shared_topic_verdict(
            owner=owner,
            content=content,
            local_keeps=local_keeps,
            peers=self._manager.presence.peer_keep_state(device_id),
        )

    def _ids_that_may_empty_the_topic(
        self, content: Mapping[str, DiscoveryContent], mqtt_entry_id: str | None
    ) -> frozenset[str]:
        """Return the ids whose verdict lets an integration-disabled twin go; an id that raises keeps its twins."""
        allowed: set[str] = set()
        for device_id, device_content in content.items():
            try:
                if self._topic_verdict(device_id, device_content, mqtt_entry_id).remove_disabled:
                    allowed.add(device_id)
            except Exception as err:  # noqa: BLE001
                # No registry or broker content in the log; keeping the twins is the safe direction
                LOGGER.warning("The check whether a shared discovery topic may go empty raised an unexpected error")
                LOGGER.debug("The shared topic check failed with %s", type(err).__name__)
        return frozenset(allowed)

    @callback
    def _remove_replay_twins(
        self,
        device_ids: Iterable[str],
        content: Mapping[str, DiscoveryContent] | None = None,
        may_empty_topic: Collection[str] = frozenset(),
    ) -> TwinRemoval:
        """
        Remove the duplicates a replayed legacy discovery created for these devices; return the count and errors (D-05).

        `content` maps a device id to what its core-prefix discovery topic holds. An id without an entry, and every id
        when it is None as on the takeover path, is UNKNOWN: an integration-disabled twin stays (CR-01). It goes for
        EMPTY content, and for LEGACY content only when the id is in `may_empty_topic`, the ids whose shared topic may
        go empty (D-02, D-05): the takeover path passes none, so a follower, and an owner whose peers keep a row, never
        lets core clear the shared topic there. Registry logic only: nothing is published and no migrate payload is
        sent for a mirror (T-5-02). One device that raises must not keep the others, or the start, from finishing. The
        rows a device removed before it raised still count, and `errored` reports the failure (FIX-06).
        """
        if (mqtt_entry_id := self._manager.gateway.mqtt_entry_id()) is None:
            return TwinRemoval(0, errored=False)
        removed = 0
        errored = False
        for device_id in device_ids:
            try:
                removed += takeover.remove_replay_twins(
                    self._manager.hass,
                    self._manager.entry.entry_id,
                    device_id,
                    mqtt_entry_id=mqtt_entry_id,
                    content=(content or {}).get(device_id, DiscoveryContent.UNKNOWN),
                    may_empty_topic=device_id in may_empty_topic,
                )
            except takeover.ReplayTwinsError as err:
                # The rows removed before the failure are gone and counted; the emptied device went with them (FIX-06)
                removed += err.removed
                errored = True
                LOGGER.warning("The check for duplicate entities of a device raised an unexpected error")
                LOGGER.debug("The check for duplicate entities failed with %s", type(err.__cause__).__name__)
            except Exception as err:  # noqa: BLE001
                # No registry or broker content in the log: this check must never keep the manager from running
                errored = True
                LOGGER.warning("The check for duplicate entities of a device raised an unexpected error")
                LOGGER.debug("The check for duplicate entities failed with %s", type(err).__name__)
        return TwinRemoval(removed, errored=errored)

    @callback
    def _arm_replay_catch(self) -> None:
        """Start the quiet period before the catch for replayed duplicates; a legacy instance has no native device."""
        if not self._manager.running or not self._native_device_ids():
            return
        if self._cancel_replay_catch is not None:
            self._cancel_replay_catch()
        self._replay_catch_retries = 0
        self._cancel_replay_catch = async_call_later(
            self._manager.hass, takeover.REPLAY_QUIET_SECONDS, self._on_replay_catch_due
        )
        self._replay_catch_armed = True

    @callback
    def on_discovery_emptied(self, device_id: str) -> None:
        """
        Arm the catch again when the shared topic of a native device turned from LEGACY to EMPTY in this run (D-06).

        The owner cleared the topic, so a follower's integration-disabled twins that the catch kept on LEGACY content
        may go now, in this run and not only at the next start. Only while the manager runs, after the start-up catch
        was armed in this run, with no catch timer pending, for a native id that still has a legacy MQTT device, and
        within the retry bound that every re-arm of this start shares (T-09.2-12). A catch that is running when this
        arms folds its own re-arm into this timer instead of arming a second one (review WR-02). The owner's own clear
        comes back as EMPTY too; that extra bounded run only removes leftovers. The catch decides as always, and this
        never publishes.
        """
        if (
            not self._manager.running
            or not self._replay_catch_armed
            or self._cancel_replay_catch is not None
            or not self._manager.is_native(device_id)
            or (mqtt_entry_id := self._manager.gateway.mqtt_entry_id()) is None
            or takeover.legacy_device(self._manager.hass, mqtt_entry_id, device_id) is None
            or self._replay_catch_retries >= takeover.REPLAY_CATCH_RETRIES
        ):
            return
        self._replay_catch_retries += 1
        self._cancel_replay_catch = async_call_later(
            self._manager.hass, takeover.REPLAY_RETRY_MIN_SECONDS, self._on_replay_catch_due
        )

    @callback
    def _on_replay_catch_due(self, _now: object) -> None:
        """Start the catch in a background task of the entry; it takes the lock, which a callback cannot await."""
        self._cancel_replay_catch = None
        if not self._manager.running:
            return
        self._manager.entry.async_create_background_task(
            self._manager.hass, self._async_replay_catch(), name=f"{DOMAIN} replay catch"
        )

    async def _async_replay_catch(self) -> None:
        """
        Remove the duplicates that a replay created after the quiet period, for every native device (D-05).

        The order is fixed: the content and peer read, the migrate, the re-read, the synchronous registry step, the
        flush, the re-check, the migrate, the re-check, then the owner-only clear (D-06, D-09, D-10). The core-prefix
        topic is shared by every instance, so one gate decides every action that can let it go empty
        (`takeover.shared_topic_verdict`): a twin the integration disabled, usually by the duplicate guard, goes for
        EMPTY content; for LEGACY content only on the owner, and only when the owner keeps no enabled legacy row itself
        and no online peer announces one or has not said what it keeps (D-02, D-03, D-05, D-08). A follower keeps it on
        LEGACY content: core's clear-on-remove hook would empty the shared topic (D-05). Every disabled twin stays for
        EXPORT or UNKNOWN content (CR-01, D-01 to D-04).

        Before the owner lets the topic go empty it publishes the migrate payload, so a peer that loaded the legacy
        rows while the gate was open unloads them and the empty payload deletes none of them (D-09, research Q1): once
        before the removal of an integration-disabled twin on LEGACY content, and again right before every clear. No
        migrate goes out while the gate keeps the device: it would unload the kept rows on every instance (T-09.2-08).
        With several devices each migrate is decided from a read right before its own publish (WR-01). After each
        migrate await the content and the peer signal are read again, and a peer that announced a kept row
        meanwhile stops the removal or the clear (D-10); the removal follows the re-read with no await in between
        (WR-01), and a twin whose migrate did not go out stays.

        The owner then clears a topic that still holds the legacy payload, so no later replay can bring the rows back,
        and it does so even when nothing was removed (user decision 4). The clear never goes out for EMPTY, EXPORT or
        UNKNOWN content, never for a mirror and never for a device another instance adopted (T-5-02, T-04-60). A
        follower publishes nothing. A device that keeps a legacy row is not cleared either: the empty payload would
        delete a loaded row that was kept on purpose (D-08). The owned devices kept because a peer keeps a row or has
        not announced what it keeps, and the devices that keep their legacy MQTT device because the content is unknown,
        are logged as counts (D-03, T-04-14).
        While the discovery settle is not done or still inside its grace, the catch arms itself again for the time that
        is left instead, a bounded number of times per start (WR-02). An owned device that the gate keeps only because
        an instance announced online was not heard since this start (UNHEARD) arms it again too, for the rest of one
        heartbeat interval plus the expiry margin, and after that for one full interval plus the margin per retry, so a
        peer that starts together with the owner, or whose first heartbeat was lost, no longer keeps the owner from
        cleaning up in that run (D-04, review WR-03). Both reasons share the same retry counter and bound; with both,
        the longer wait wins. After the bound the owner keeps the device and logs a count; the next start checks again.
        A peer that sent no valid kept list (UNKNOWN, an older version) never re-arms: nothing changes in this run.
        """
        async with self._manager.lock:
            if not self._manager.running:
                return
            device_ids = self._native_device_ids()
            mqtt_entry_id = self._manager.gateway.mqtt_entry_id()
            content = {device_id: self._manager.sync.discovery_content(device_id) for device_id in device_ids}
            may_empty = self._ids_that_may_empty_the_topic(content, mqtt_entry_id)
            # The owner migrates first where the gate lets a disabled twin go on LEGACY content (D-09)
            to_migrate = [
                device_id
                for device_id in device_ids
                if device_id in may_empty and content[device_id] is DiscoveryContent.LEGACY
            ]
            if to_migrate:
                migrated = await self._async_publish_migrates(to_migrate)
                # Read again after the awaits: a peer that announced a kept row meanwhile, or new content, keeps the
                # twin (D-10); a LEGACY twin whose migrate did not go out stays
                mqtt_entry_id = self._manager.gateway.mqtt_entry_id()
                content = {device_id: self._manager.sync.discovery_content(device_id) for device_id in device_ids}
                may_empty = frozenset(
                    device_id
                    for device_id in self._ids_that_may_empty_the_topic(content, mqtt_entry_id)
                    if content[device_id] is DiscoveryContent.EMPTY or device_id in migrated
                )
            # The last read and the removal in one synchronous step: no await in between, so no message can change the
            # decision (WR-01)
            removal = self._remove_replay_twins(device_ids, content, may_empty)
            if removal.removed or removal.errored:
                # The removal is on disk like the move before it (WR-01), a partial one too (FIX-06)
                await takeover.async_flush_registries(self._manager.hass)
            if (mqtt_entry_id := self._manager.gateway.mqtt_entry_id()) is None or self._manager.publisher is None:
                return
            kept_for_peers = 0
            unheard = 0
            for device_id in device_ids:
                try:
                    # Read again after the flush: an export that arrived meanwhile is never wiped (CR-01), and a peer
                    # that announced a kept row meanwhile keeps the topic (D-10)
                    if self._may_clear(device_id, mqtt_entry_id):
                        # A fresh migrate right before the clear, and one more look after its await (D-09, D-10)
                        if await async_attempt(
                            partial(self._manager.publisher.async_publish_migrate, device_id),
                            f"publish the migrate payload of device {device_id}",
                        ) and self._may_clear(device_id, mqtt_entry_id):
                            await async_attempt(
                                partial(self._manager.publisher.async_clear_device, device_id),
                                f"clear the discovery of device {device_id}",
                            )
                        continue
                    if (content_now := self._manager.sync.discovery_content(device_id)) is not DiscoveryContent.LEGACY:
                        continue
                    # The gate asks for a re-arm: an owned device kept only for a peer not heard yet (D-04)
                    if self._topic_verdict(device_id, content_now, mqtt_entry_id).rearm:
                        unheard += 1
                    elif (
                        device_id in self._manager.devices
                        and device_id not in self._manager.sync.transferred_away
                        and self._manager.presence.peer_keep_state(device_id)
                        in (takeover.PeerKeep.KEPT, takeover.PeerKeep.UNKNOWN)
                        and not takeover.keeps_enabled_legacy_row(
                            self._manager.hass, self._manager.entry.entry_id, device_id, mqtt_entry_id=mqtt_entry_id
                        )
                    ):
                        kept_for_peers += 1
                except Exception as err:  # noqa: BLE001
                    # No registry or broker content in the log: one device must not keep the others from their clear
                    LOGGER.warning("The cleanup of a stale legacy discovery raised an unexpected error")
                    LOGGER.debug("The cleanup of a stale legacy discovery failed with %s", type(err).__name__)
            if kept_for_peers:
                # A count only, never an id, a heartbeat field or a payload (T-04-14)
                LOGGER.info(
                    "Kept the MQTT entities of %d native devices: another instance keeps an MQTT entity of them or has "
                    "not announced what it keeps",
                    kept_for_peers,
                )
            # A count only, never an id or a payload: the topic content of these devices was not known, so their
            # disabled twins stay until a start that knows it (D-03)
            unknown = sum(
                1
                for device_id in device_ids
                if self._manager.sync.discovery_content(device_id) is DiscoveryContent.UNKNOWN
                and takeover.legacy_device(self._manager.hass, mqtt_entry_id, device_id) is not None
            )
            self._rearm_or_log_replay_catch(unknown, unheard)

    @callback
    def _rearm_or_log_replay_catch(self, unknown: int, unheard: int) -> None:
        """
        Arm the catch again for devices kept only for now, within the bound, or log the counts once it is spent.

        `unknown` counts the devices whose topic content is not known while the settle may still make it known (WR-02),
        `unheard` the owned devices kept only for an online peer not heard yet (D-04). Both share the retry counter and
        REPLAY_CATCH_RETRIES; with both, the longer wait wins. A timer that an emptied topic armed while this run
        awaited (D-06) is replaced, not kept next to the new one, and its count covers the new run: exactly one catch
        timer is ever pending, so a stop cancels it and no second catch chain spends the bound (review WR-02). The
        lines carry counts only (T-04-14).
        """
        waits: list[float] = []
        if unknown and (settles_in := self._manager.sync.discovery_settles_in()) is not None:
            # The settle is not done or still inside its grace, so the content may still become known: check again
            # instead of leaving the twins to the next start, which would meet the same timing (WR-02)
            waits.append(max(settles_in, takeover.REPLAY_RETRY_MIN_SECONDS))
        if unheard:
            # A peer announced online sends its first heartbeat within one interval of this start: check again
            # once it is due, instead of keeping until the next start (D-04). Past that point a heartbeat was lost
            # (QoS 0) or the peer is gone, so check once per interval: each retry then waits for one more heartbeat
            # instead of spending the bound within seconds (review WR-03)
            heard_by = HEARTBEAT_INTERVAL_SECONDS + EXPIRY_MARGIN_SECONDS
            elapsed = self._manager.presence.listening_seconds()
            waits.append(max(heard_by - elapsed if elapsed < heard_by else heard_by, takeover.REPLAY_RETRY_MIN_SECONDS))
        if waits and (
            self._cancel_replay_catch is not None or self._replay_catch_retries < takeover.REPLAY_CATCH_RETRIES
        ):
            if self._cancel_replay_catch is not None:
                # An emptied topic armed the catch while this run awaited (D-06); that run is counted already, so one
                # run covers both reasons and exactly one timer stays pending (review WR-02)
                self._cancel_replay_catch()
            else:
                self._replay_catch_retries += 1
            self._cancel_replay_catch = async_call_later(self._manager.hass, max(waits), self._on_replay_catch_due)
            LOGGER.debug(
                "Checking %d native devices again: %d with unsettled discovery content, %d waiting for an instance",
                unknown + unheard,
                unknown,
                unheard,
            )
            return
        if unknown:
            LOGGER.info(
                "Kept the MQTT entities of %d native devices: the content of their retained discovery is not "
                "known, the next start checks again",
                unknown,
            )
        if unheard:
            # A count only, never an id, a heartbeat field or a payload (T-04-14)
            LOGGER.info(
                "Kept the MQTT entities of %d native devices: another online instance was not heard yet, the next "
                "start checks again",
                unheard,
            )

    async def _async_publish_migrates(self, device_ids: Iterable[str]) -> set[str]:
        """
        Publish the migrate payload of each device the gate still lets go now; return the ids where it went out (D-09).

        Each device is decided from a read taken right before its own publish: a peer heard during the publish of an
        earlier device may announce a kept row of this one, and its migrate would unload that row on the peer while the
        topic stays retained (D-10, T-09.2-08, WR-01). A device whose content is no longer LEGACY or whose gate keeps it
        now is skipped and keeps its twins.
        """
        migrated: set[str] = set()
        if self._manager.publisher is None:
            return migrated
        for device_id in device_ids:
            content_now = self._manager.sync.discovery_content(device_id)
            if content_now is not DiscoveryContent.LEGACY or device_id not in self._ids_that_may_empty_the_topic(
                {device_id: content_now}, self._manager.gateway.mqtt_entry_id()
            ):
                continue
            if await async_attempt(
                partial(self._manager.publisher.async_publish_migrate, device_id),
                f"publish the migrate payload of device {device_id}",
            ):
                migrated.add(device_id)
        return migrated

    def _may_clear(self, device_id: str, mqtt_entry_id: str) -> bool:
        """
        Return whether the owner may clear the shared core-prefix topic of a device now, from a fresh read (D-08, D-10).

        The topic still holds the legacy payload, the device is owned and not adopted by another instance, the gate
        says `may_clear` (no kept row here, no online peer that keeps one or has not said), and no legacy MQTT device
        is left here. A caller that awaited reads it again.
        """
        content = self._manager.sync.discovery_content(device_id)
        return (
            content is DiscoveryContent.LEGACY
            and device_id in self._manager.devices
            and device_id not in self._manager.sync.transferred_away
            and self._topic_verdict(device_id, content, mqtt_entry_id).may_clear
            and takeover.legacy_device(self._manager.hass, mqtt_entry_id, device_id) is None
        )

    def _duplicate_guard_ids(self) -> set[str]:
        """Return the ids of the native devices this instance holds: owned or mirrored, not transferred away (R-1)."""
        return {
            device_id for device_id in self._native_device_ids() if device_id not in self._manager.sync.transferred_away
        }

    @callback
    def _disarm_duplicate_guard(self) -> None:
        """Stop the guard for an enabled duplicate of a native device; a no-op while it is not armed."""
        if self._cancel_duplicate_guard is not None:
            self._cancel_duplicate_guard()
            self._cancel_duplicate_guard = None

    @callback
    def arm_duplicate_guard(self) -> None:
        """
        Arm the guard for duplicates of native devices whenever the manager runs, whatever the export option says.

        Core MQTT restores the state of a deleted registry entry with the same platform and unique id, so a discovery
        export on the prefix core listens to can create a duplicate that comes back enabled. Any instance on the broker
        may publish that export and a receiver cannot know who does, so the guard does not read this instance's export
        option or prefix. It disables the rows that exist now and then every row core creates while it is armed. A
        disabled row stays in the registry until the next start-up replay catch, which removes it only when the
        core-prefix topic holds the legacy payload or nothing (D-02). With an export or unknown content it stays,
        because core MQTT clears the retained topic, another instance's export included, when a row it discovered
        while disabled leaves the registry (CR-01). Such a row keeps its disabled state across restarts. Registry logic
        only: nothing is published.
        """
        self._disarm_duplicate_guard()
        if not self._manager.running:
            return
        self._cancel_duplicate_guard = self._manager.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_duplicate_registry_updated
        )
        self._disable_duplicates(self._duplicate_guard_ids())

    @callback
    def _on_duplicate_registry_updated(self, event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """
        Look at every new row of a native device id that can make or complete a duplicate; all else returns at once.

        Two creations matter: the core MQTT row (core just created the duplicate) and the switch or select of this
        integration (the native twin just appeared, which closes the gap when the duplicate came first). An update
        never triggers a pass, so a row a user enables afterwards stays as it is until the next start (T-08-36).
        """
        if event.data["action"] != "create":
            return
        entry = er.async_get(self._manager.hass).async_get(event.data["entity_id"])
        if entry is None:
            return
        is_core_row = entry.platform == takeover.MQTT_DOMAIN
        is_native_twin = (
            entry.platform == DOMAIN
            and entry.config_entry_id == self._manager.entry.entry_id
            and entry.domain in takeover.EXPORT_DOMAINS
        )
        if not (is_core_row or is_native_twin) or entry.unique_id not in self._duplicate_guard_ids():
            return
        # Core is still creating the entity: the change waits for the next loop iteration, it does not nest in the event
        self._manager.hass.loop.call_soon(self._disable_duplicates, {entry.unique_id})

    @callback
    def _disable_duplicates(self, device_ids: Iterable[str]) -> None:
        """Disable the enabled duplicates of these devices; a failure never keeps the manager from running."""
        if (mqtt_entry_id := self._manager.gateway.mqtt_entry_id()) is None or self._cancel_duplicate_guard is None:
            return
        disabled = 0
        for device_id in device_ids:
            try:
                disabled += takeover.disable_duplicates(
                    self._manager.hass, self._manager.entry.entry_id, device_id, mqtt_entry_id=mqtt_entry_id
                )
            except Exception as err:  # noqa: BLE001
                # No registry or broker content in the log: this guard must never keep the manager from running
                LOGGER.warning("The check for an enabled duplicate of a device raised an unexpected error")
                LOGGER.debug("The check for an enabled duplicate failed with %s", type(err).__name__)
        if disabled:
            # A count only: the ids, names and payloads come from the broker
            LOGGER.info("Disabled %d duplicate entities that core MQTT created for native devices", disabled)

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

    @callback
    def _refresh_kept_duplicates(self) -> None:
        """
        Show the core MQTT duplicates the guard keeps enabled in one Repairs warning, or delete it (FIX-08, D-01, D-02).

        The list is read from the registry for every id the guard holds (`takeover.kept_duplicates`): a duplicate the
        user customized (WR-02) or kept next to a native twin they turned off (WR-03). It is one non-fixable warning
        per instance with no fix flow; it only reads the registry and never removes, disables or enables a row
        (CR-01). A changed list deletes the issue first, so an earlier dismissal never hides it (research Pitfall 15);
        an empty list deletes it. Without an MQTT entry nothing is kept. A failure while building the list leaves the
        warning as it is until the next evaluation point and logs no entity data (T-04-14).
        """
        if not self._manager.running:
            return
        rows: list[tuple[str, takeover.KeptReason]] = []
        try:
            if (mqtt_entry_id := self._manager.gateway.mqtt_entry_id()) is not None:
                for device_id in sorted(self._duplicate_guard_ids()):
                    rows += takeover.kept_duplicates(
                        self._manager.hass, self._manager.entry.entry_id, device_id, mqtt_entry_id=mqtt_entry_id
                    )
        except Exception as err:  # noqa: BLE001
            # No registry or broker content in the log: this check must never keep the manager from running
            LOGGER.warning("The check for duplicate entities kept enabled raised an unexpected error")
            LOGGER.debug("The check for duplicate entities kept enabled failed with %s", type(err).__name__)
            return
        ir.async_delete_issue(self._manager.hass, DOMAIN, ISSUE_KEPT_DUPLICATES)
        if not rows:
            return
        ir.async_create_issue(
            self._manager.hass,
            DOMAIN,
            ISSUE_KEPT_DUPLICATES,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_KEPT_DUPLICATES,
            translation_placeholders=kept_duplicates_placeholders(rows),
        )

    async def async_takeover(self) -> None:
        """
        Move the legacy MQTT entities of pending owned devices and native mirrors here (D-05, D-09, D-12, MIG-01).

        The order for an owned device is fixed: the live migrate payload, then the registry takeover, then the catch
        for duplicates that a replayed discovery created meanwhile, then the registry flush, then the retained clear.
        The same catch runs again after a quiet period (`_async_replay_catch`), because the replay can also arrive
        after the clear. A device whose legacy entities stay loaded is deferred: nothing moves, nothing is cleared, it
        stays pending and runs on the legacy path for this run (T-5-08). Only ids that are owned devices are ever
        published for (T-5-02). A follower publishes nothing. The caller holds the lock; the platforms are not
        forwarded yet. Every path ends with the refresh of the warning for duplicates kept enabled (FIX-08, D-04).
        """
        assert self._manager.publisher is not None  # noqa: S101
        owned = sorted(self._manager.native_state.pending & self._manager.devices.keys())
        stale = self._manager.native_state.pending - set(owned)
        self._manager.native_state.pending.difference_update(stale)
        mqtt_entry_id = self._manager.gateway.mqtt_entry_id()
        mirrors = sorted(
            device_id
            for device_id, mirror in self._manager.mirrors.items()
            if mirror.mirror is not None
            and mirror.mirror.native
            and mqtt_entry_id is not None
            and takeover.legacy_device(self._manager.hass, mqtt_entry_id, device_id) is not None
        )
        if not owned and not mirrors:
            if stale:
                await self._manager.async_save_now()
            # The pass is done: the duplicates the guard keeps enabled are listed now, at every start (D-04)
            self._refresh_kept_duplicates()
            return
        # Published for every pending device, even without a legacy device of our own: another instance's core MQTT
        # may have its entities loaded, and the clear alone would delete their registry entries
        migrated = {
            device_id
            for device_id in owned
            if await async_attempt(
                partial(self._manager.publisher.async_publish_migrate, device_id),
                f"publish the migrate payload of device {device_id}",
            )
        }
        targets = [takeover.TakeoverTarget(device_id, self._manager.subentry_id_of(device_id)) for device_id in owned]
        targets += [takeover.TakeoverTarget(device_id, None) for device_id in mirrors]
        results = await asyncio.gather(
            *(self._async_take_over_one(target, mqtt_entry_id, skip=set(owned) - migrated) for target in targets),
            return_exceptions=True,
        )
        # A replay that core MQTT delivered after the move created a second set of entities next to the moved ones; they
        # go now, so the retained clear below finds nothing loaded. A deferred device moved nothing, and an exception is
        # judged by the registry in the loop below, so neither is touched (D-05)
        self._remove_replay_twins(
            target.device_id
            for target, status in zip(targets, results, strict=True)
            if status is takeover.TakeoverStatus.DONE
        )
        if any(status is takeover.TakeoverStatus.DONE or isinstance(status, BaseException) for status in results):
            # The registry files hold the move and the removal before any marker says it is done and before the
            # retained clear goes out
            await takeover.async_flush_registries(self._manager.hass)
        for target, status in zip(targets, results, strict=True):
            deferred = status is takeover.TakeoverStatus.DEFERRED
            if isinstance(status, BaseException):
                # No registry or broker content in the log: a registry surprise must never keep the start from finishing
                LOGGER.warning("The native takeover of a device raised an unexpected error")
                LOGGER.debug("The native takeover failed with %s", type(status).__name__)
                # The registry decides, not the return path: entries that moved cannot go back to core MQTT
                deferred = not takeover.has_moved_entities(self._manager.hass, self._manager.entry, target.device_id)
            if deferred:
                await self._async_defer_takeover(target.device_id)
            elif not await self._async_finish_takeover(target.device_id, set(owned)):
                # Moved, but the retained clear is still to do: native for this run, and the id stays pending in the
                # Store so the next start and the next republish retry the clear (WR-02)
                self._clear_unconfirmed.add(target.device_id)
        await self._manager.async_save_now()
        self._refresh_kept_duplicates()

    async def _async_take_over_one(
        self, target: takeover.TakeoverTarget, mqtt_entry_id: str | None, *, skip: set[str]
    ) -> takeover.TakeoverStatus:
        """Take one device over; a device in `skip`, whose migrate payload did not go out, is deferred untouched."""
        if target.device_id in skip:
            return takeover.TakeoverStatus.DEFERRED
        if mqtt_entry_id is None:
            return takeover.TakeoverStatus.NOTHING
        return await takeover.async_take_over(
            self._manager.hass,
            self._manager.entry,
            target,
            mqtt_entry_id=mqtt_entry_id,
            unload_timeout=takeover.TAKEOVER_UNLOAD_TIMEOUT,
            retry_interval=takeover.TAKEOVER_RETRY_INTERVAL,
        )

    async def _async_finish_takeover(self, device_id: str, owned: set[str]) -> bool:
        """
        Finish a taken-over device; False when the retained clear of an owned device could not be published.

        The owner clears the retained discovery last and ends the stale test-topic subscription of the legacy path. A
        follower has nothing to clear. A fresh migrate goes out right before the clear (D-09): it closes the window
        since the pass's migrate, in which a peer may have loaded the legacy rows, and covers the unconfirmed-clear
        retry after a reconnect, which runs with no migrate of its own. A failed migrate returns False, so the clear
        stays unconfirmed and is retried with a fresh migrate, never sent bare. No peer gate here (research Q5): it
        would block the owner's cutover clear whenever a legacy peer keeps its rows.
        """
        if device_id not in owned:
            return True
        assert self._manager.publisher is not None  # noqa: S101
        if not await async_attempt(
            partial(self._manager.publisher.async_publish_migrate, device_id),
            f"publish the migrate payload of device {device_id}",
        ):
            return False
        if not await async_attempt(
            partial(self._manager.publisher.async_clear_device, device_id), f"clear the discovery of device {device_id}"
        ):
            return False
        self._manager.native_state.pending.discard(device_id)
        if (device := self._manager.devices.get(device_id)) is not None and device.unsubscribe_test is not None:
            device.unsubscribe_test()
            device.unsubscribe_test = None
        return True

    async def _async_defer_takeover(self, device_id: str) -> None:
        """
        Keep a device that could not be taken over on the legacy path for this run, with everything as in 0.1.0.

        A native mirror was built without the test-topic subscription of the legacy path, so it gets it now: its legacy
        test buttons are still the entities of the device.
        """
        LOGGER.info("The native takeover of a device is postponed to the next start; it stays as it is until then")
        self._legacy_this_run.add(device_id)
        if (mirror := self._manager.mirrors.get(device_id)) is None or mirror.unsubscribe_test is not None:
            return
        try:
            mirror.unsubscribe_test = await self._manager.gateway.async_subscribe(
                test_topic(self._manager.base_topic, device_id), self._manager.test_message_handler(device_id)
            )
        except HomeAssistantError as err:
            LOGGER.warning("MQTT could not subscribe to the test topic of device %s: %s", mirror.name, err)

    async def async_retry_unconfirmed_clears(self) -> None:
        """
        Publish the retained discovery clear again for devices whose entities moved but whose clear failed (WR-02).

        The caller holds the lock. A cleared device is no longer pending, so the Store forgets the marker.
        """
        if not self._clear_unconfirmed:
            return
        assert self._manager.publisher is not None  # noqa: S101
        for device_id in sorted(self._clear_unconfirmed):
            if device_id not in self._manager.devices:
                self._clear_unconfirmed.discard(device_id)
                continue
            if await self._async_finish_takeover(device_id, {device_id}):
                self._clear_unconfirmed.discard(device_id)
                self._manager.schedule_save()
