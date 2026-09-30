"""
Owner side of the central config: the owner defends what it published (SYN-03, D-15, D-17).

One subscription on the config wildcard watches the config topic of every device. For a device this instance owns
(a key of `Manager.devices`; mirrors of foreign devices never are) the owner recognizes its own documents coming back
as echoes, and treats everything else on its topic as a foreign write: foreign content, a foreign tombstone, an
unreadable payload or a claim by another owner. The reaction is always the same and never touches the spec or the
subentry: publish the local document again, throttled per device with a trailing republish so two claimants never
ping-pong, and raise a Repairs issue when the content really differed. Nothing in a log line or an issue carries
payload or action data; the device name and the escaped claimant name are the only broker-influenced texts.
"""

from collections import deque
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later

from .const import (
    DISCOVERY_REMOVAL_HINT_COUNT,
    DISCOVERY_REMOVAL_HINT_WINDOW_SECONDS,
    DOMAIN,
    ISSUE_DISCOVERY_REMOVED_PREFIX,
    ISSUE_DOC_OVERWRITTEN_PREFIX,
    ISSUE_OWNERSHIP_CLAIM_PREFIX,
    LOGGER,
    PUBLISHED_HASH_HISTORY,
    REPUBLISH_THROTTLE_SECONDS,
)
from .document import DocumentRejectedError, build_content, content_hash, escape_markdown, parse_document
from .topics import config_wildcard, discovery_wildcard, parse_config_topic, parse_discovery_topic

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from .document import ParsedDocument
    from .manager import Device, Manager
    from .mqtt_gateway import IncomingMessage

TRANSLATION_DOC_OVERWRITTEN = "doc_overwritten"
TRANSLATION_OWNERSHIP_CLAIM = "ownership_claim"
TRANSLATION_DISCOVERY_REMOVED = "discovery_removed"


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

    @callback
    def async_stop(self) -> None:
        """Release the subscriptions and cancel every throttle window, so nothing is published after the stop."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._config_heal.cancel_all()
        self._discovery_heal.cancel_all()

    @callback
    def note_published(self, device_id: str, digest: str) -> None:
        """Remember a content hash the owner published (or published before a restart) as its own."""
        history = self._published.setdefault(device_id, deque(maxlen=PUBLISHED_HASH_HISTORY))
        if digest not in history:
            history.append(digest)

    @callback
    def forget(self, device_id: str) -> None:
        """Forget everything about a deleted device."""
        self._published.pop(device_id, None)
        self._removals.pop(device_id, None)

    @callback
    def _on_config_message(self, msg: IncomingMessage) -> None:
        """Route a message on any config topic; this plan handles the owner branch only."""
        manager = self._manager
        device_id = parse_config_topic(manager.base_topic, msg.topic)
        if device_id is None:
            return
        if (device := manager.devices.get(device_id)) is not None:
            self._check_owned(device, msg.payload)
        # A topic of a device this instance does not own belongs to the follower branch

    def _check_owned(self, device: Device, payload: str) -> None:
        """Classify a message on the config topic of an owned device and heal it when it is not this instance's."""
        manager = self._manager
        parsed = self._parse(device, payload)
        if parsed is None:
            self._overwritten(device)
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
            device,
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
            device,
            {"device": escape_markdown(device.name), "claimant": escape_markdown(claimant)},
        ):
            LOGGER.warning(
                "Another instance claims to own device %s; this instance stays the owner and publishes it again",
                device.name,
            )
        self._heal(device.device_id)

    def _raise_once(
        self,
        prefix: str,
        translation_key: str,
        device: Device,
        placeholders: dict[str, str],
        severity: ir.IssueSeverity = ir.IssueSeverity.ERROR,
    ) -> bool:
        """Create a non-fixable issue unless it exists, so a repeating writer cannot reset a dismissal; True if new."""
        hass = self._manager.hass
        issue_id = f"{prefix}{device.device_id}"
        if ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None:
            return False
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
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
            device,
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
            await publish(device)
