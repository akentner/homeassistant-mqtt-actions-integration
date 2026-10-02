"""
Presence of the instances on one broker: the heartbeat of this instance and the roster of its peers (OPS-03, D-05).

Home Assistant owns the MQTT connection, so this integration cannot set a Last Will and a crash leaves a stale retained
`online` availability. The heartbeat is the liveness signal that survives a crash: it is published every
HEARTBEAT_INTERVAL_SECONDS, never retained, and a peer is offline once none was heard for HEARTBEAT_OFFLINE_SECONDS.
A clean shutdown is faster: the retained `offline` availability that the sync side tracks turns a peer offline at once.

Everything received is validated strictly before it is used (T-04-09 to T-04-12): a retained heartbeat is ignored, the
topic id must equal the payload id, every field is typed and capped, and the number of tracked peers is capped. No
heartbeat field ever reaches a log line (T-04-14).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads

from .const import (
    DOMAIN,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_OFFLINE_SECONDS,
    LOGGER,
    MAX_BROKER_MESSAGE_BYTES,
    MAX_HEARTBEAT_DEVICES,
    MAX_TRACKED_INSTANCES,
    SIGNAL_ROSTER_UPDATED,
)
from .model import invalid_name
from .sync import PRESENCE_OFFLINE, PRESENCE_ONLINE
from .topics import heartbeat_topic, heartbeat_wildcard, is_valid_device_id, parse_heartbeat_topic

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE

    from .manager import Manager
    from .mqtt_gateway import IncomingMessage

HEARTBEAT_QOS = 0
# The expiry is strict (a peer is online up to and including the timeout), so its timer fires this much later
EXPIRY_MARGIN_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class Heartbeat:
    """What one instance announces about itself on its heartbeat topic."""

    instance_id: str
    name: str
    version: str
    devices: int
    session: str


def _valid_text(value: object) -> bool:
    """Return whether a heartbeat text is a non-blank, printable string within the name length cap."""
    return isinstance(value, str) and bool(value.strip()) and not invalid_name(value)


def _valid_session(value: object) -> bool:
    """Return whether a session id is a canonical lower-case uuid text."""
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _within_size_cap(payload: str) -> bool:
    """Return whether a payload is within the message cap in characters and in UTF-8 bytes."""
    if len(payload) > MAX_BROKER_MESSAGE_BYTES:
        return False
    try:
        return len(payload.encode()) <= MAX_BROKER_MESSAGE_BYTES
    except UnicodeEncodeError:  # a lone surrogate cannot be text of a heartbeat
        return False


def _valid_devices(value: object) -> bool:
    """Return whether a device count is a real integer (no bool, no float) within the cap."""
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_HEARTBEAT_DEVICES


def _heartbeat_object(base_topic: str, topic: str, payload: str) -> tuple[str, dict[str, Any]] | None:
    """Return the topic id and the JSON object of a message whose size, topic and payload id are acceptable."""
    if not _within_size_cap(payload):
        return None
    topic_id = parse_heartbeat_topic(base_topic, topic)
    if topic_id is None or not is_valid_device_id(topic_id):
        return None
    try:
        data = json_loads(payload)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("instance_id") != topic_id:
        return None
    return topic_id, data


def parse_heartbeat(base_topic: str, topic: str, payload: str) -> Heartbeat | None:
    """
    Return the heartbeat of a message, or None for anything that is not a valid heartbeat of that topic.

    Never raises and never logs: the payload is untrusted, so the answer is only a value or None (T-04-11, T-04-14).
    """
    if (parsed := _heartbeat_object(base_topic, topic, payload)) is None:
        return None
    topic_id, data = parsed
    name, version, devices, session = (data.get(key) for key in ("name", "version", "devices", "session"))
    if _valid_text(name) and _valid_text(version) and _valid_devices(devices) and _valid_session(session):
        return Heartbeat(instance_id=topic_id, name=name, version=version, devices=devices, session=session)
    return None


@dataclass(slots=True)
class _Peer:
    """A peer row: its last heartbeat and when it was heard, on the monotonic clock and on the wall clock."""

    heartbeat: Heartbeat
    seen: float
    seen_at: datetime


class Roster:
    """
    The peers heard through their heartbeats, keyed by instance id.

    A peer is online while its last heartbeat is at most HEARTBEAT_OFFLINE_SECONDS old and its retained availability is
    not `offline`; the availability comes from the callback, which the manager points at the sync side.
    """

    def __init__(self, clock: Callable[[], float], instance_status: Callable[[str], str | None]) -> None:
        """Initialize an empty roster that reads the time from `clock` and the announced presence from the callback."""
        self._clock = clock
        self._instance_status = instance_status
        self._peers: dict[str, _Peer] = {}
        self._listening_since = clock()

    def restart_listening(self) -> None:
        """Start counting the time this instance has listened for heartbeats again, for a start or a reconnect."""
        self._listening_since = self._clock()

    def _fresh(self, peer: _Peer) -> bool:
        return self._clock() - peer.seen <= HEARTBEAT_OFFLINE_SECONDS

    def _online(self, peer: _Peer) -> bool:
        return self._fresh(peer) and self._instance_status(peer.heartbeat.instance_id) != PRESENCE_OFFLINE

    def observe(self, heartbeat: Heartbeat) -> bool:
        """
        Record a heartbeat of a peer as heard now; False when the peer is new and the roster is full.

        At the cap a new peer replaces the stalest row that is already past the timeout, so random ids cannot block a
        real instance for good; when every row is fresh the new peer is not tracked (T-04-12).
        """
        instance_id = heartbeat.instance_id
        if instance_id not in self._peers and len(self._peers) >= MAX_TRACKED_INSTANCES:
            expired = [key for key, peer in self._peers.items() if not self._fresh(peer)]
            if not expired:
                return False
            del self._peers[min(expired, key=lambda key: self._peers[key].seen)]
        self._peers[instance_id] = _Peer(heartbeat, self._clock(), dt_util.utcnow())
        return True

    def status(self, instance_id: str) -> str | None:
        """Return `online` or `offline` for a peer with a row, None for an instance that never sent a heartbeat."""
        if (peer := self._peers.get(instance_id)) is None:
            return None
        return PRESENCE_ONLINE if self._online(peer) else PRESENCE_OFFLINE

    def online_ids(self) -> list[str]:
        """Return the ids of the peers that are online."""
        return [instance_id for instance_id, peer in self._peers.items() if self._online(peer)]

    def rows(self) -> list[dict[str, Any]]:
        """Return every peer row, online or not, in the order the peers were first heard."""
        return [
            {
                "id": peer.heartbeat.instance_id,
                "name": peer.heartbeat.name,
                "version": peer.heartbeat.version,
                "devices": peer.heartbeat.devices,
                "last_seen": peer.seen_at.isoformat(),
                "online": self._online(peer),
            }
            for peer in self._peers.values()
        ]

    def next_expiry_delay(self) -> float | None:
        """Return the seconds until the earliest online peer expires (with a margin), None without an online peer."""
        remaining = [
            peer.seen + HEARTBEAT_OFFLINE_SECONDS - self._clock() for peer in self._peers.values() if self._online(peer)
        ]
        return None if not remaining else max(min(remaining), 0.0) + EXPIRY_MARGIN_SECONDS

    def owner_offline(self, instance_id: str) -> bool:
        """
        Return whether an owner is known to be offline; unknown is not offline, so this errs towards "online" (D-09).

        True when the owner announced `offline`, or its heartbeat is stale, or nothing at all is known about it after
        this instance listened for at least HEARTBEAT_OFFLINE_SECONDS. An owner whose availability says `online` and
        that never sent a heartbeat (an older build, or a crash before this instance listened) is not treated as
        offline: adopting its devices then needs an explicit confirmation.
        """
        announced = self._instance_status(instance_id)
        if announced == PRESENCE_OFFLINE:
            return True
        if (peer := self._peers.get(instance_id)) is not None:
            return not self._fresh(peer)
        if announced == PRESENCE_ONLINE:
            return False
        return self._clock() - self._listening_since >= HEARTBEAT_OFFLINE_SECONDS


class PresenceManager:
    """Publishes the heartbeat of this instance and keeps the roster of the others."""

    def __init__(self, manager: Manager) -> None:
        """Initialize the presence manager; a new session id is generated for every manager, so for every start."""
        self._manager = manager
        self.session = str(uuid.uuid4())
        self._roster = Roster(self._now, manager.sync.instance_status)
        self._unsubscribe: CALLBACK_TYPE | None = None
        self._cancel_tick: CALLBACK_TYPE | None = None
        self._cancel_expiry: CALLBACK_TYPE | None = None
        # The ids that were online at the last evaluation; a change of this set is what the entities are told about
        self._announced: frozenset[str] = frozenset()
        self._overflow_logged = False

    def _now(self) -> float:
        """Read the manager clock at call time so a replaced clock reaches the roster."""
        return self._manager.clock()

    async def async_start(self) -> None:
        """Subscribe to the heartbeat of every instance and start the heartbeat tick."""
        manager = self._manager
        self._overflow_logged = False
        self._roster.restart_listening()
        self._unsubscribe = await manager.gateway.async_subscribe(
            heartbeat_wildcard(manager.base_topic), self._on_message, HEARTBEAT_QOS
        )
        self._cancel_tick = async_track_time_interval(
            manager.hass, self._on_tick, timedelta(seconds=HEARTBEAT_INTERVAL_SECONDS)
        )

    @callback
    def async_stop(self) -> None:
        """Release the subscription and cancel both timers, so nothing is published or evaluated after the stop."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._cancel_tick is not None:
            self._cancel_tick()
            self._cancel_tick = None
        self._disarm_expiry()

    @callback
    def on_reconnect(self) -> None:
        """
        Restart the listening time after a broker reconnect; the peer rows stay.

        A peer is offline by the 90 second rule, so clearing the rows would only make the count flap until the next
        heartbeat. What restarts is the time this instance has listened, which `owner_offline` needs.
        """
        self._roster.restart_listening()
        self._refresh()

    @callback
    def on_availability_changed(self) -> None:
        """Re-evaluate the roster after the announced presence of an instance changed, for example a clean shutdown."""
        self._refresh()

    async def async_publish_heartbeat(self) -> None:
        """Publish one heartbeat, not retained; an unavailable MQTT client is logged, never raised."""
        manager = self._manager
        payload = json.dumps(
            {
                "instance_id": manager.instance_id,
                "name": manager.instance_name,
                "version": manager.version,
                "devices": len(manager.devices),
                "session": self.session,
            }
        )
        try:
            await manager.gateway.async_publish(
                heartbeat_topic(manager.base_topic, manager.instance_id), payload, retain=False, qos=HEARTBEAT_QOS
            )
        except HomeAssistantError as err:
            LOGGER.warning("MQTT could not publish the heartbeat: %s", err)

    @callback
    def _on_tick(self, _now: object) -> None:
        """Publish the next heartbeat in a background task and re-evaluate the roster; a publish needs a task."""
        manager = self._manager
        if not manager.running:
            return
        manager.entry.async_create_background_task(manager.hass, self._async_tick(), name=f"{DOMAIN} heartbeat")
        self._refresh()

    async def _async_tick(self) -> None:
        """Publish a heartbeat under the manager lock, so none follows the offline availability of a stop."""
        manager = self._manager
        async with manager.lock:
            if manager.running:
                await self.async_publish_heartbeat()

    @callback
    def _on_message(self, msg: IncomingMessage) -> None:
        """Take a heartbeat of a peer into the roster; a retained message and an own echo are ignored."""
        manager = self._manager
        if msg.retain:
            return
        heartbeat = parse_heartbeat(manager.base_topic, msg.topic, msg.payload)
        if heartbeat is None or heartbeat.instance_id == manager.instance_id:
            return
        if not self._roster.observe(heartbeat):
            if not self._overflow_logged:
                self._overflow_logged = True
                LOGGER.warning(
                    "More than %d instances sent a heartbeat, so further instances are not tracked",
                    MAX_TRACKED_INSTANCES,
                )
            return
        # The row changed (its last seen time at least), so the entities are told even when the online set did not
        self._announced = frozenset(self._roster.online_ids())
        self._arm_expiry()
        self._send_signal()

    @callback
    def _refresh(self) -> None:
        """Re-evaluate who is online; tell the entities when the set changed and arm the timer of the next expiry."""
        online = frozenset(self._roster.online_ids())
        changed = online != self._announced
        self._announced = online
        self._arm_expiry()
        if changed:
            self._send_signal()

    @callback
    def _arm_expiry(self) -> None:
        """(Re)arm the one timer that turns the earliest online peer offline, so it does not wait for the next tick."""
        self._disarm_expiry()
        delay = self._roster.next_expiry_delay()
        if delay is not None and self._manager.running:
            self._cancel_expiry = async_call_later(self._manager.hass, delay, self._on_expiry)

    @callback
    def _disarm_expiry(self) -> None:
        if self._cancel_expiry is not None:
            self._cancel_expiry()
            self._cancel_expiry = None

    @callback
    def _on_expiry(self, _now: object) -> None:
        self._cancel_expiry = None
        self._refresh()

    @callback
    def _send_signal(self) -> None:
        """Tell the entities that the roster changed."""
        async_dispatcher_send(self._manager.hass, SIGNAL_ROSTER_UPDATED.format(self._manager.entry.entry_id))

    def rows(self) -> list[dict[str, Any]]:
        """Return this instance first and then every peer, each as a dict for the sensor and the diagnostics."""
        manager = self._manager
        own = {
            "id": manager.instance_id,
            "name": manager.instance_name,
            "version": manager.version,
            "devices": len(manager.devices),
            "last_seen": dt_util.utcnow().isoformat(),
            "online": True,
        }
        return [own, *self._roster.rows()]

    def online_count(self) -> int:
        """Return how many instances are online, this one included."""
        return 1 + len(self._roster.online_ids())

    def online_peers(self) -> list[dict[str, Any]]:
        """Return the rows of the peers that are online now, this instance excluded."""
        return [row for row in self._roster.rows() if row["online"]]

    def peer_status(self, instance_id: str) -> str | None:
        """Return `online` or `offline` for a peer that sent a heartbeat, None for any other instance."""
        return self._roster.status(instance_id)

    def owner_offline(self, instance_id: str) -> bool:
        """Return whether an owner is known to be offline; unknown counts as online until enough time has passed."""
        return self._roster.owner_offline(instance_id)
