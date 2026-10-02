"""
Presence of the instances on one broker: the heartbeat of this instance and the roster of its peers (OPS-03, D-05).

Home Assistant owns the MQTT connection, so this integration cannot set a Last Will and a crash leaves a stale retained
`online` availability. The heartbeat is the liveness signal that survives a crash: it is published every
HEARTBEAT_INTERVAL_SECONDS, never retained, and a peer is offline once none was heard for HEARTBEAT_OFFLINE_SECONDS.
Nothing in a log line carries a heartbeat field.
"""

import json
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads

from .const import LOGGER, SIGNAL_ROSTER_UPDATED
from .topics import heartbeat_topic, heartbeat_wildcard, parse_heartbeat_topic

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import CALLBACK_TYPE

    from .manager import Manager
    from .mqtt_gateway import IncomingMessage

HEARTBEAT_QOS = 0


@dataclass(frozen=True, slots=True)
class Heartbeat:
    """What one instance announces about itself on its heartbeat topic."""

    instance_id: str
    name: str
    version: str
    devices: int
    session: str


def parse_heartbeat(base_topic: str, topic: str, payload: str) -> Heartbeat | None:
    """Return the heartbeat of a message, or None for anything that is not a valid heartbeat of that topic."""
    topic_id = parse_heartbeat_topic(base_topic, topic)
    if topic_id is None:
        return None
    try:
        data = json_loads(payload)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("instance_id") != topic_id:
        return None
    name, version, devices, session = (data.get(key) for key in ("name", "version", "devices", "session"))
    if not (
        isinstance(name, str) and isinstance(version, str) and isinstance(devices, int) and isinstance(session, str)
    ):
        return None
    return Heartbeat(instance_id=topic_id, name=name, version=version, devices=devices, session=session)


@dataclass(slots=True)
class _Peer:
    """A peer row: its last heartbeat and when it was heard, on the monotonic clock and on the wall clock."""

    heartbeat: Heartbeat
    seen: float
    seen_at: datetime


class Roster:
    """The peers heard through their heartbeats, keyed by instance id."""

    def __init__(self, clock: Callable[[], float]) -> None:
        """Initialize an empty roster that reads the time from `clock`."""
        self._clock = clock
        self._peers: dict[str, _Peer] = {}

    def observe(self, heartbeat: Heartbeat) -> None:
        """Record a heartbeat of a peer as heard now."""
        self._peers[heartbeat.instance_id] = _Peer(heartbeat, self._clock(), dt_util.utcnow())

    def peers(self) -> list[_Peer]:
        """Return the peer rows in the order they were first heard."""
        return list(self._peers.values())


class PresenceManager:
    """Publishes the heartbeat of this instance and keeps the roster of the others."""

    def __init__(self, manager: Manager) -> None:
        """Initialize the presence manager; a new session id is generated for every manager, so for every start."""
        self._manager = manager
        self.session = str(uuid.uuid4())
        self._roster = Roster(self._now)
        self._unsubscribe: CALLBACK_TYPE | None = None

    def _now(self) -> float:
        """Read the manager clock at call time so a replaced clock reaches the roster."""
        return self._manager.clock()

    async def async_start(self) -> None:
        """Subscribe to the heartbeat of every instance."""
        manager = self._manager
        self._unsubscribe = await manager.gateway.async_subscribe(
            heartbeat_wildcard(manager.base_topic), self._on_message, HEARTBEAT_QOS
        )

    @callback
    def async_stop(self) -> None:
        """Release the subscription."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def on_reconnect(self) -> None:
        """Restart the bookkeeping after a broker reconnect."""

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
    def _on_message(self, msg: IncomingMessage) -> None:
        """Take a heartbeat of a peer into the roster; a retained message and an own echo are ignored."""
        manager = self._manager
        if msg.retain:
            return
        heartbeat = parse_heartbeat(manager.base_topic, msg.topic, msg.payload)
        if heartbeat is None or heartbeat.instance_id == manager.instance_id:
            return
        self._roster.observe(heartbeat)
        self._send_signal()

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
        peers = [
            {
                "id": peer.heartbeat.instance_id,
                "name": peer.heartbeat.name,
                "version": peer.heartbeat.version,
                "devices": peer.heartbeat.devices,
                "last_seen": peer.seen_at.isoformat(),
                "online": True,
            }
            for peer in self._roster.peers()
        ]
        return [own, *peers]

    def online_count(self) -> int:
        """Return how many instances are online, this one included."""
        return sum(1 for row in self.rows() if row["online"])
