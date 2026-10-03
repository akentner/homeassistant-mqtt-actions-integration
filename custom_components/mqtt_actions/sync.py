"""
Both sides of the central config: the owner defends what it published, a follower mirrors what others published.

Owner side (SYN-03, D-15, D-17). One subscription on the config wildcard watches the config topic of every device.
For a device this instance owns (a key of `Manager.devices`; mirrors of foreign devices never are) the owner
recognizes its own documents coming back as echoes, and treats everything else on its topic as a foreign write:
foreign content, a foreign tombstone, an unreadable payload or a claim by another owner. The reaction is always the
same and never touches the spec or the subentry: publish the local document again, throttled per device with a
trailing republish so two claimants never ping-pong, and raise a Repairs issue when the content really differed.
Nothing in a log line or an issue carries payload or action data; the device name and the escaped claimant name are
the only broker-influenced texts.

Follower side (SYN-02, D-06, D-08). A document for a device this instance does not own is parsed strictly,
structure-checked and turned into a read-only mirror by the manager. Nothing of a document that fails a gate is stored,
shown or logged, except a fixed reason code and the length-capped device id (T-03-18). The ingest runs in background
tasks that take the manager's FIFO lock, so two quick documents for one device apply in arrival order.

Removal (SYN-05, D-09, D-10). A live or retained empty payload removes a mirror at once. A deletion this instance
missed is found by a prune: a grace window after setup, every reconnect and every time an owner turns online, a mirror
whose document was not seen since the last (re)connect is removed, but only when its pinned owner is announced online.
A missing message alone never deletes anything: an unknown or offline owner, and a reconnect that wiped what was known
about presence, keep every mirror.
"""

from collections import deque
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .actions import ActionsInvalid, validate_spec_structure
from .const import (
    DISCOVERY_REMOVAL_HINT_COUNT,
    DISCOVERY_REMOVAL_HINT_WINDOW_SECONDS,
    DOMAIN,
    ISSUE_DISCOVERY_REMOVED_PREFIX,
    ISSUE_DOC_OVERWRITTEN_PREFIX,
    ISSUE_OWNER_CONFLICT_PREFIX,
    ISSUE_OWNERSHIP_CLAIM_PREFIX,
    ISSUE_SCHEMA_TOO_NEW_PREFIX,
    ISSUE_TRANSFERRED_PREFIX,
    LOGGER,
    MAX_LOGGED_PAYLOAD_LENGTH,
    MAX_MIRRORS,
    MAX_SCHEMA_TOO_NEW_ISSUES,
    MAX_TRACKED_INSTANCES,
    PRUNE_GRACE_SECONDS,
    PUBLISHED_HASH_HISTORY,
    REPUBLISH_THROTTLE_SECONDS,
    SCHEMA_VERSION,
    SIGNAL_ROSTER_UPDATED,
)
from .document import (
    DocumentRejectedError,
    SchemaTooNewError,
    build_content,
    content_hash,
    escape_markdown,
    parse_document,
)
from .topics import (
    availability_wildcard,
    config_wildcard,
    discovery_wildcard,
    is_valid_device_id,
    parse_availability_topic,
    parse_config_topic,
    parse_discovery_topic,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from .document import ParsedDocument
    from .manager import Device, Manager, MirrorInfo
    from .mqtt_gateway import IncomingMessage

TRANSLATION_DOC_OVERWRITTEN = "doc_overwritten"
TRANSLATION_OWNERSHIP_CLAIM = "ownership_claim"
TRANSLATION_DISCOVERY_REMOVED = "discovery_removed"
TRANSLATION_OWNER_CONFLICT = "owner_conflict"
TRANSLATION_SCHEMA_TOO_NEW = "schema_too_new"
TRANSLATION_TRANSFERRED = "transferred"

# Stored presence values; only these two payloads of the availability topic mean anything
PRESENCE_ONLINE = "online"
PRESENCE_OFFLINE = "offline"


def _shown(device_id: str) -> str:
    """Return a device id fit for a log line: length-capped and quoted, so a broker-chosen id cannot forge a line."""
    return repr(device_id[:MAX_LOGGED_PAYLOAD_LENGTH]) + ("..." if len(device_id) > MAX_LOGGED_PAYLOAD_LENGTH else "")


@dataclass(frozen=True, slots=True)
class TransferInfo:
    """What an old owner recognized of the adopter of one of its devices: who, under which name, and its document."""

    claimant: str
    claimant_name: str
    # The document text that passed the parser; the release flow creates the mirror from it (T-04-59)
    payload: str


class _TrailingThrottle:
    """
    Run an action at most once per window and key, and never lose a request that arrives inside a window.

    An idle key runs at once and opens a window. A request inside the window only sets a pending flag. When the window
    ends, a pending key runs once and opens a new window; otherwise the key is idle again (T-03-07).
    """

    def __init__(self, hass: HomeAssistant, window: float, run: Callable[[str], None]) -> None:
        """Initialize the throttle; `run` is called on the event loop with the key."""
        self._hass = hass
        self._window = window
        self._run = run
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._pending: set[str] = set()

    @callback
    def request(self, key: str) -> None:
        """Run now when the key is idle, otherwise remember one trailing run."""
        if key in self._timers:
            self._pending.add(key)
            return
        self._open(key)
        self._run(key)

    @callback
    def cancel_all(self) -> None:
        """Cancel every window and forget every pending run."""
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()
        self._pending.clear()

    def _open(self, key: str) -> None:
        self._timers[key] = async_call_later(self._hass, self._window, partial(self._expired, key))

    @callback
    def _expired(self, key: str, _now: object) -> None:
        del self._timers[key]
        if key in self._pending:
            self._pending.discard(key)
            self._open(key)
            self._run(key)


class SyncManager:
    """Watches the config topic for the devices this instance owns and heals what others write there."""

    def __init__(self, manager: Manager) -> None:
        """Initialize the sync manager of one Manager."""
        self._manager = manager
        self._unsubscribers: list[CALLBACK_TYPE] = []
        # device id -> content hashes this instance published recently; a document with one of them is its own echo
        self._published: dict[str, deque[str]] = {}
        self._config_heal = _TrailingThrottle(manager.hass, REPUBLISH_THROTTLE_SECONDS, self._start_config_heal)
        self._discovery_heal = _TrailingThrottle(manager.hass, REPUBLISH_THROTTLE_SECONDS, self._start_discovery_heal)
        # The discovery prefix is read when subscribing; a runtime change of it needs a reload
        self._discovery_prefix = ""
        # device id -> times of the most recent removals of its discovery; only the last few are kept
        self._removals: dict[str, deque[float]] = {}
        # instance id -> last announced presence; capped, and only the announced values are kept
        self._instances: dict[str, str] = {}
        self._presence_overflow_logged = False
        self._mirror_overflow_logged = False
        # Ids of mirrored devices whose config document arrived since the last (re)connect or setup; a subset of the
        # mirror ids plus the ids of mirrors created since, so it is bounded by MAX_MIRRORS
        self._seen: set[str] = set()
        self._prune_timer: CALLBACK_TYPE | None = None
        # Owned device ids that another instance adopted, with the adopter's valid document; in memory only, so it is
        # bounded by the owned devices and empty again after a restart (assumption A15)
        self._transferred: dict[str, TransferInfo] = {}

    async def async_start(self) -> None:
        """Subscribe to the config wildcard; the caller does this before anything is published (SYN-04)."""
        manager = self._manager
        self._unsubscribers.append(
            await manager.gateway.async_subscribe(config_wildcard(manager.base_topic), self._on_config_message)
        )
        self._discovery_prefix = manager.gateway.discovery_prefix()
        self._unsubscribers.append(
            await manager.gateway.async_subscribe(
                discovery_wildcard(self._discovery_prefix), self._on_discovery_message
            )
        )
        self._presence_overflow_logged = False
        self._mirror_overflow_logged = False
        self._unsubscribers.append(
            await manager.gateway.async_subscribe(
                availability_wildcard(manager.base_topic), self._on_availability_message
            )
        )
        self._seen.clear()
        self.arm_prune()

    @callback
    def async_stop(self) -> None:
        """Release the subscriptions and cancel every timer, so nothing is published or pruned after the stop."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._config_heal.cancel_all()
        self._discovery_heal.cancel_all()
        self._cancel_prune()

    @callback
    def on_reconnect(self) -> None:
        """
        Forget what was seen and what was known about presence after a broker reconnect, then wait for the replay.

        A broker that lost its retained messages replays neither documents nor availability, which must look like an
        unknown owner and never like an online one (D-10). The owner republishes documents before it announces online.
        """
        self._seen.clear()
        if self._instances:
            self._instances.clear()
            self._announce_presence_change()
        self.arm_prune()

    @callback
    def arm_prune(self) -> None:
        """(Re)start the grace window after which unseen mirrors of online owners are pruned."""
        self._cancel_prune()
        self._prune_timer = async_call_later(self._manager.hass, PRUNE_GRACE_SECONDS, self._prune_due)

    @callback
    def _cancel_prune(self) -> None:
        if self._prune_timer is not None:
            self._prune_timer()
            self._prune_timer = None

    @callback
    def _prune_due(self, _now: object) -> None:
        """Start the prune in a background task; it cannot run inside the timer callback."""
        self._prune_timer = None
        manager = self._manager
        manager.entry.async_create_background_task(manager.hass, self._async_prune(), name=f"{DOMAIN} prune")

    async def _async_prune(self) -> None:
        """
        Remove every mirror whose document was not seen since the last (re)connect and whose pinned owner is online.

        The owner being online while its document is missing means it deleted the device while this instance was away.
        An owner that is offline or unknown keeps its mirrors, so orphaned devices stay (D-10, D-11). Owned devices are
        never in `mirrors`. Content never reaches the log, only the count.
        """
        manager = self._manager
        try:
            async with manager.lock:
                if not manager.running:
                    return
                stale = [
                    device_id
                    for device_id, mirror in manager.mirrors.items()
                    if device_id not in self._seen
                    and device_id not in manager.devices
                    and mirror.mirror is not None
                    and self.instance_status(mirror.mirror.owner) == PRESENCE_ONLINE
                ]
                for device_id in stale:
                    await manager.async_remove_mirror(device_id)
                    self._seen.discard(device_id)
                if stale:
                    LOGGER.info(
                        "Removed %d mirrored devices that their owners deleted while this instance was away", len(stale)
                    )
        except Exception:  # noqa: BLE001 - nothing a broker sends may reach a log
            LOGGER.warning("Mirrors of deleted devices could not be pruned")

    def online_instance_count(self) -> int:
        """Return how many instances other than this one are currently announced as online."""
        own = self._manager.instance_id
        return sum(
            1 for instance_id, status in self._instances.items() if instance_id != own and status == PRESENCE_ONLINE
        )

    def instance_status(self, instance_id: str) -> str | None:
        """Return the last announced presence of an instance (`online` or `offline`), None when it is not known."""
        return self._instances.get(instance_id)

    @callback
    def _on_availability_message(self, msg: IncomingMessage) -> None:
        """
        Track the presence of an instance from its retained availability topic (D-16).

        Only `online` and `offline` count (compared after strip and lower case); an empty payload forgets the instance
        and anything else is ignored. A new id beyond the cap is not tracked and the overflow is logged once.
        """
        instance_id = parse_availability_topic(self._manager.base_topic, msg.topic)
        if instance_id is None:
            return
        status = msg.payload.strip().lower()
        stored_before = self._instances.get(instance_id)
        if not msg.payload:
            self._instances.pop(instance_id, None)
        elif status in {PRESENCE_ONLINE, PRESENCE_OFFLINE}:
            if instance_id not in self._instances and len(self._instances) >= MAX_TRACKED_INSTANCES:
                if not self._presence_overflow_logged:
                    self._presence_overflow_logged = True
                    LOGGER.warning(
                        "More than %d instances announced their availability, so further instances are not tracked",
                        MAX_TRACKED_INSTANCES,
                    )
                return
            previous = self._instances.get(instance_id)
            self._instances[instance_id] = status
            if status == PRESENCE_ONLINE and previous != PRESENCE_ONLINE:
                # An owner that was offline or unknown when this instance started may have deleted devices meanwhile
                self.arm_prune()
        # A clean shutdown shows in the roster at once, without waiting for the heartbeat timeout (D-05)
        roster_signalled = self._manager.presence.on_availability_changed()
        if self._instances.get(instance_id) != stored_before and not roster_signalled:
            # A native mirror re-reads its availability although the roster set is unchanged, for example when an
            # owner without a heartbeat announces itself (D-07); a roster signal already makes every entity re-read
            self._announce_presence_change(instance_id)

    @callback
    def _announce_presence_change(self, instance_id: str | None = None) -> None:
        """
        Tell the entities that an announced presence changed, when a native mirror follows it (D-07).

        A native mirror is available while its owner is online, so only the owner of a native mirror matters; without
        one (`instance_id` None means any owner) nothing is signalled and the roster signals stay exactly as they were.
        """
        manager = self._manager
        if any(
            device.mirror is not None
            and device.mirror.native
            and (instance_id is None or device.mirror.owner == instance_id)
            for device in manager.mirrors.values()
        ):
            async_dispatcher_send(manager.hass, SIGNAL_ROSTER_UPDATED.format(manager.entry.entry_id))

    @callback
    def note_published(self, device_id: str, digest: str) -> None:
        """Remember a content hash the owner published (or published before a restart) as its own."""
        history = self._published.setdefault(device_id, deque(maxlen=PUBLISHED_HASH_HISTORY))
        if digest not in history:
            history.append(digest)

    @callback
    def forget(self, device_id: str) -> None:
        """Forget everything about a deleted or released device."""
        self._published.pop(device_id, None)
        self._removals.pop(device_id, None)
        self.clear_transferred(device_id)

    @property
    def transferred_away(self) -> frozenset[str]:
        """Return the owned device ids that another instance adopted; this instance neither heals nor publishes them."""
        return frozenset(self._transferred)

    def transfer_info(self, device_id: str) -> TransferInfo | None:
        """Return what was recognized of the adopter of a device, None for a device that was not transferred away."""
        return self._transferred.get(device_id)

    @callback
    def clear_transferred(self, device_id: str) -> str | None:
        """Forget that a device was transferred away and return the saved document of the adopter, if any."""
        info = self._transferred.pop(device_id, None)
        return None if info is None else info.payload

    async def async_follow(self, device_id: str, payload: str) -> None:
        """
        Create the mirror of the adopter from its saved document; the caller holds the manager lock.

        The document goes through the same gates as any received one, so nothing saved here is trusted more than a
        message from the broker.
        """
        await self._async_ingest_locked(device_id, payload)

    @callback
    def _on_config_message(self, msg: IncomingMessage) -> None:
        """Route a message on any config topic: the owner branch for an owned device, else the follower branch."""
        manager = self._manager
        device_id = parse_config_topic(manager.base_topic, msg.topic)
        if device_id is None:
            return
        if (device := manager.devices.get(device_id)) is not None:
            self._check_owned(device, msg.payload)
            return
        if not is_valid_device_id(device_id):
            # An unbounded or odd id would reach the Store, issue ids, subscriptions and the registries (WR-05)
            LOGGER.debug("Ignoring a config message for a device with an invalid id %s", _shown(device_id))
            return
        if not msg.payload:
            self._seen.discard(device_id)
        elif device_id in manager.mirrors:
            # Any document means the owner has not deleted the device, whether it is valid or not
            self._seen.add(device_id)
        # A tombstone takes the same queue as a document, so a document and its tombstone apply in arrival order
        task = self._async_remove(device_id) if not msg.payload else self._async_ingest(device_id, msg.payload)
        manager.entry.async_create_background_task(manager.hass, task, name=f"{DOMAIN} ingest")

    async def _async_remove(self, device_id: str) -> None:
        """Remove the mirror of a device whose config topic was cleared (D-09); an unknown id is a no-op."""
        manager = self._manager
        try:
            async with manager.lock:
                if manager.running and device_id in manager.mirrors and device_id not in manager.devices:
                    LOGGER.debug(
                        "The config document of mirrored device %s was cleared, so its mirror is removed",
                        _shown(device_id),
                    )
                    await manager.async_remove_mirror(device_id)
        except Exception:  # noqa: BLE001 - nothing a broker sends may reach a log
            LOGGER.warning("The mirror of device %s could not be removed", _shown(device_id))

    async def _async_ingest(self, device_id: str, payload: str) -> None:
        """
        Turn a document for a device this instance does not own into a mirror, in arrival order.

        Runs under the manager lock, so the manager state cannot change underneath it, and is guarded by a broad
        except: an exception in a background task would be logged by core, and a hostile document must never choose
        what reaches a log.
        """
        manager = self._manager
        try:
            async with manager.lock:
                # The device may have been added, or the manager stopped, since the message arrived
                if manager.running and device_id not in manager.devices:
                    await self._async_ingest_locked(device_id, payload)
        except Exception:  # noqa: BLE001 - a hostile document can make anything raise; none of it may reach a log
            LOGGER.warning("A config document for device %s could not be processed", _shown(device_id))

    async def _async_ingest_locked(self, device_id: str, payload: str) -> None:
        """Validate a document and apply it to the mirror of its device; the caller holds the lock."""
        manager = self._manager
        shown = _shown(device_id)
        try:
            parsed = parse_document(device_id, payload)
        except SchemaTooNewError as err:
            self._schema_too_new(device_id, err.version)
            return
        except DocumentRejectedError as err:
            LOGGER.warning("A config document for device %s was dropped: %s", shown, err.reason)
            return
        try:
            validate_spec_structure(parsed.spec)
        except ActionsInvalid:
            # The schema error may quote action data, so only the fixed reason is logged
            LOGGER.warning("A config document for device %s was dropped: invalid_actions", shown)
            return
        if parsed.owner == manager.instance_id:
            LOGGER.debug("Ignoring a config document of this instance for the unknown device %s", shown)
            return
        if (mirror := manager.mirrors.get(device_id)) is None:
            if len(manager.mirrors) >= MAX_MIRRORS:
                if not self._mirror_overflow_logged:
                    self._mirror_overflow_logged = True
                    LOGGER.warning(
                        "More than %d devices of other instances were announced, so further ones are ignored",
                        MAX_MIRRORS,
                    )
                return
            await manager.async_apply_mirror(parsed)
            self._seen.add(device_id)
        elif (info := mirror.mirror) is not None and info.owner != parsed.owner:
            if not self._may_repin(info, parsed):
                # The first owner wins; nothing another owner sends changes the mirror (D-17)
                self._conflict(mirror, info, parsed.owner_name)
                return
            # The pinned owner was adopted away: the document names it and the roster says it is gone (D-09)
            LOGGER.info("The mirrored device %s follows a new owner, because its previous owner was adopted", shown)
            await manager.async_apply_mirror(parsed)
        elif info is None or parsed.content_hash != info.content_hash or (parsed.native and not info.native):
            # The hash decides, never the rev: an owner that lost its Store restarts at rev 1 (D-15); a marker that
            # appears on unchanged content is the owner switching to native entities, which the mirror follows (D-07)
            await manager.async_apply_mirror(parsed)
        self._resolve(device_id)

    def _may_repin(self, info: MirrorInfo, parsed: ParsedDocument) -> bool:
        """
        Return whether a document of another owner moves the pin: the single exception to first owner wins (D-09).

        Both must hold: the transfer marker of the document names the owner this mirror is pinned to, and the roster
        says that owner is offline. A marker that names someone else, or a pinned owner that is online or unknown, is a
        conflict like any other claim (T-04-49). The approval stays bound to the actions hash, so new actions of the new
        owner still need an approval here.
        """
        return info.owner in parsed.transferred_from and self._manager.presence.owner_offline(info.owner)

    @callback
    def forget_mirror(self, device_id: str) -> None:
        """Forget that a document of a device was seen; the device left the mirrors, for example by adoption."""
        self._seen.discard(device_id)

    async def async_restore_mirror(self, device_id: str, payload: str) -> None:
        """Feed a saved document through the normal ingest path again; the caller holds the manager lock (T-04-53)."""
        await self._async_ingest_locked(device_id, payload)

    def _resolve(self, device_id: str) -> None:
        """Delete the conflict and schema issues of a device: its pinned owner has a current, readable document."""
        hass = self._manager.hass
        for prefix in (ISSUE_OWNER_CONFLICT_PREFIX, ISSUE_SCHEMA_TOO_NEW_PREFIX):
            ir.async_delete_issue(hass, DOMAIN, f"{prefix}{device_id}")

    def _conflict(self, mirror: Device, info: MirrorInfo, claimant_name: str) -> None:
        """React to a valid document of another owner for a mirrored device: ignore it and report both claims (D-17)."""
        if self._raise_once(
            ISSUE_OWNER_CONFLICT_PREFIX,
            TRANSLATION_OWNER_CONFLICT,
            mirror.device_id,
            {
                "device": escape_markdown(mirror.name),
                "owner": escape_markdown(info.owner_name),
                "claimant": escape_markdown(claimant_name),
            },
        ):
            LOGGER.warning(
                "Another instance claims the mirrored device %s; this instance keeps following its first owner",
                _shown(mirror.name),
            )

    def _schema_too_new(self, device_id: str, version: int) -> None:
        """
        React to a document newer than this integration reads: apply nothing and ask for an update (D-14).

        An existing mirror keeps its last known state. Without a mirror the number of such issues is bounded, so
        documents with random ids cannot fill Repairs (T-03-16).
        """
        manager = self._manager
        if (mirror := manager.mirrors.get(device_id)) is None:
            existing = sum(
                1
                for domain, issue_id in ir.async_get(manager.hass).issues
                if domain == DOMAIN and issue_id.startswith(ISSUE_SCHEMA_TOO_NEW_PREFIX)
            )
            if existing >= MAX_SCHEMA_TOO_NEW_ISSUES:
                LOGGER.debug("Ignoring a newer config document for device %s: too many such issues", _shown(device_id))
                return
        shown_name = mirror.name if mirror is not None else device_id[:MAX_LOGGED_PAYLOAD_LENGTH]
        if self._raise_once(
            ISSUE_SCHEMA_TOO_NEW_PREFIX,
            TRANSLATION_SCHEMA_TOO_NEW,
            device_id,
            {"device": escape_markdown(shown_name), "version": str(version)[:12], "supported": str(SCHEMA_VERSION)},
            ir.IssueSeverity.WARNING,
        ):
            LOGGER.warning(
                "A config document for device %s uses a newer format than this integration understands; update it "
                "to receive changes",
                _shown(device_id),
            )

    def _check_owned(self, device: Device, payload: str) -> None:
        """Classify a message on the config topic of an owned device and heal it when it is not this instance's."""
        manager = self._manager
        parsed = self._parse(device, payload)
        names_this_instance = (
            parsed is not None
            and parsed.owner != manager.instance_id
            and manager.instance_id in parsed.transferred_from
        )
        if device.device_id in self._transferred:
            # Recognized already: nothing is healed any more (T-04-60); only a newer valid document is kept for the flow
            if names_this_instance:
                assert parsed is not None  # noqa: S101
                self._transferred_to(device, parsed, payload)
            return
        if parsed is None:
            self._overwritten(device)
        elif names_this_instance:
            # A valid document of another owner that lists this instance as a previous owner: the device was adopted
            self._transferred_to(device, parsed, payload)
        elif parsed.owner != manager.instance_id:
            self._claimed(device, parsed.owner_name)
        elif self._differs(device, parsed):
            # A lower rev is an older document of this owner, for example published before an offline edit
            if parsed.rev >= manager.revision(device.device_id):
                self._overwritten(device)
            else:
                self._heal(device.device_id)

    @staticmethod
    def _parse(device: Device, payload: str) -> ParsedDocument | None:
        """Return the parsed document, or None for an empty, rejected or unexaminable payload."""
        if not payload:
            return None
        try:
            return parse_document(device.device_id, payload)
        except DocumentRejectedError:
            return None
        except Exception:  # noqa: BLE001 - hostile structures can raise anything; all of it is an unreadable payload
            LOGGER.debug("A document on the config topic of device %s could not be examined", device.name)
            return None

    def _differs(self, device: Device, parsed: ParsedDocument) -> bool:
        """Return whether a document of this owner has content other than the local truth and its own echoes."""
        if parsed.content_hash in self._published.get(device.device_id, ()):
            return False
        try:
            return parsed.content_hash != content_hash(build_content(device.spec))
        except ValueError, TypeError:
            return False

    def _overwritten(self, device: Device) -> None:
        """React to foreign content, a foreign tombstone or an unreadable payload on an owned topic (T-03-06)."""
        if self._raise_once(
            ISSUE_DOC_OVERWRITTEN_PREFIX,
            TRANSLATION_DOC_OVERWRITTEN,
            device.device_id,
            {"device": escape_markdown(device.name)},
        ):
            LOGGER.warning(
                "Something other than this instance changed or cleared the shared config of device %s, so it is "
                "published again",
                device.name,
            )
        self._heal(device.device_id)

    def _claimed(self, device: Device, claimant: str) -> None:
        """React to a document of another owner for an owned device id: no takeover, republish and report (D-17)."""
        if self._raise_once(
            ISSUE_OWNERSHIP_CLAIM_PREFIX,
            TRANSLATION_OWNERSHIP_CLAIM,
            device.device_id,
            {"device": escape_markdown(device.name), "claimant": escape_markdown(claimant)},
        ):
            LOGGER.warning(
                "Another instance claims to own device %s; this instance stays the owner and publishes it again",
                device.name,
            )
        self._heal(device.device_id)

    def _transferred_to(self, device: Device, parsed: ParsedDocument, payload: str) -> None:
        """
        React to the valid document of an adopter that lists this instance as a previous owner (D-09, T-04-59).

        This instance stops healing and publishing the device and raises one fixable issue; it never steps down by
        itself, the release flow does that after a confirmation. The saved document is the newest one of the adopter.
        A different adopter replaces the issue, so the flow binds the claimant that is current.
        """
        device_id = device.device_id
        known = self._transferred.get(device_id)
        self._transferred[device_id] = TransferInfo(parsed.owner, parsed.owner_name, payload)
        if known is not None and known.claimant == parsed.owner:
            return
        if known is not None:
            ir.async_delete_issue(self._manager.hass, DOMAIN, f"{ISSUE_TRANSFERRED_PREFIX}{device_id}")
        if self._raise_once(
            ISSUE_TRANSFERRED_PREFIX,
            TRANSLATION_TRANSFERRED,
            device_id,
            {"device": escape_markdown(device.name), "claimant": escape_markdown(parsed.owner_name)},
            ir.IssueSeverity.WARNING,
            data={"device_id": device_id, "claimant": parsed.owner},
        ):
            LOGGER.warning(
                "Another instance adopted device %s, so this instance stops publishing it until it is released",
                device.name,
            )

    def _raise_once(  # noqa: PLR0913
        self,
        prefix: str,
        translation_key: str,
        device_id: str,
        placeholders: dict[str, str],
        severity: ir.IssueSeverity = ir.IssueSeverity.ERROR,
        *,
        data: dict[str, str] | None = None,
    ) -> bool:
        """
        Create an issue unless it exists, so a repeating writer cannot reset a dismissal; True if new.

        With `data` the issue is fixable and carries that data to its fix flow; otherwise it is informational.
        """
        hass = self._manager.hass
        issue_id = f"{prefix}{device_id}"
        if ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None:
            return False
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            data=data,
            is_fixable=data is not None,
            severity=severity,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )
        return True

    def _heal(self, device_id: str) -> None:
        self._config_heal.request(device_id)

    @callback
    def _on_discovery_message(self, msg: IncomingMessage) -> None:
        """
        Heal the discovery of an owned device that core MQTT cleared (DSC-03, D-18).

        Only an empty payload counts: the owner's own publishes and the discovery of other instances are not empty.
        Core publishes it when any instance deletes one entity of the device, and then drops every entity of it.
        Only ids in `devices` are healed, and a device being deleted has already left `devices`, so the owner's own
        delete is never mistaken for a removal elsewhere.
        """
        if msg.payload:
            return
        manager = self._manager
        device_id = parse_discovery_topic(self._discovery_prefix, msg.topic)
        if device_id is None or (device := manager.devices.get(device_id)) is None:
            return
        self._note_removal(device)
        self._discovery_heal.request(device_id)

    def _note_removal(self, device: Device) -> None:
        """Count a removal and explain in Repairs once it keeps happening (T-03-10)."""
        now = self._manager.clock()
        removals = self._removals.setdefault(device.device_id, deque(maxlen=DISCOVERY_REMOVAL_HINT_COUNT))
        removals.append(now)
        if len(removals) < DISCOVERY_REMOVAL_HINT_COUNT or now - removals[0] > DISCOVERY_REMOVAL_HINT_WINDOW_SECONDS:
            return
        if self._raise_once(
            ISSUE_DISCOVERY_REMOVED_PREFIX,
            TRANSLATION_DISCOVERY_REMOVED,
            device.device_id,
            {"device": escape_markdown(device.name), "count": str(DISCOVERY_REMOVAL_HINT_COUNT)},
            ir.IssueSeverity.WARNING,
        ):
            LOGGER.warning(
                "The entities of device %s were removed %d times recently, for example by deleting an entity on "
                "another instance; the discovery is published again each time",
                device.name,
                DISCOVERY_REMOVAL_HINT_COUNT,
            )

    @callback
    def _start_config_heal(self, device_id: str) -> None:
        """Start the republish of the config document of one device."""
        self._start_heal(device_id, self._manager.async_publish_config, "config")

    @callback
    def _start_discovery_heal(self, device_id: str) -> None:
        """Start the republish of the discovery of one device."""
        self._start_heal(device_id, self._manager.async_publish_discovery, "discovery")

    def _start_heal(self, device_id: str, publish: Callable[[Device], Awaitable[None]], what: str) -> None:
        """Run a republish in a background task; the publish cannot run inside the message callback."""
        manager = self._manager
        manager.entry.async_create_background_task(
            manager.hass, self._async_heal(device_id, publish), name=f"{DOMAIN} heal {what}"
        )

    async def _async_heal(self, device_id: str, publish: Callable[[Device], Awaitable[None]]) -> None:
        """Publish again under the manager lock, unless the manager stopped or the device is gone."""
        manager = self._manager
        async with manager.lock:
            if not manager.running or (device := manager.devices.get(device_id)) is None:
                return
            if device_id in self._transferred:
                # Another instance adopted it: publishing would only start the fight again (T-04-60)
                return
            await publish(device)
