"""
Re-trigger: run the actions of one device again on every instance that approved it, and report who did (OPS-01, OPS-02).

The caller publishes one non-retained request on the re-trigger topic of the device. It carries the exact StateValue to
run, never actions. Every instance, the caller included, receives it and runs the actions of that trigger through the
same path as a test button press (D-01): the tracker, the baseline, the state topic and the circuit breaker are never
touched. Each instance answers on the acknowledgement topic of the requester, and the caller collects the answers for a
short window (D-03).

The request is a second remote execution path next to the state topic, so it reuses the existing gates instead of
creating its own and is never retained (T-04-42).
"""

import asyncio
import json
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import json_loads

from .const import (
    ACK_EXECUTED,
    ACK_NO_ANSWER,
    DOMAIN,
    LOGGER,
    REASON_BAD_STATE,
    REASON_NO_STATE,
    REASON_UNKNOWN_DEVICE,
    RETRIGGER_ACK_WINDOW_SECONDS,
    RETRIGGER_SEEN_LIMIT,
)
from .model import trigger_key
from .topics import acks_topic, parse_retrigger_topic, retrigger_topic, retrigger_wildcard

if TYPE_CHECKING:
    from collections.abc import Callable

    from .manager import Device, Manager
    from .mqtt_gateway import IncomingMessage

RETRIGGER_QOS = 1


class RetriggerError(Exception):
    """A re-trigger the caller refuses before anything is sent; `reason` is a short code, never free text."""

    def __init__(self, reason: str) -> None:
        """Remember the reason code."""
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class RetriggerRequest:
    """What a caller asks for: run the actions of one StateValue of the device named by the topic."""

    request_id: str
    requester: str
    state: str
    sent_at: float


@dataclass(frozen=True, slots=True)
class RetriggerAck:
    """What an instance answers about one request."""

    request_id: str
    device_id: str
    instance_id: str
    instance_name: str
    status: str
    reason: str | None = None


def parse_request(base_topic: str, topic: str, payload: str) -> tuple[str, RetriggerRequest] | None:
    """Return the device id of the topic and the request of a message, or None when it is not a re-trigger request."""
    device_id = parse_retrigger_topic(base_topic, topic)
    if device_id is None:
        return None
    try:
        data = json_loads(payload)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    request_id, requester, state, sent_at = (data.get(key) for key in ("request_id", "requester", "state", "sent_at"))
    if not (
        isinstance(request_id, str)
        and isinstance(requester, str)
        and isinstance(state, str)
        and isinstance(sent_at, int | float)
    ):
        return None
    return device_id, RetriggerRequest(request_id=request_id, requester=requester, state=state, sent_at=sent_at)


def parse_ack(payload: str) -> RetriggerAck | None:
    """Return the acknowledgement of a message, or None when it is not one."""
    try:
        data = json_loads(payload)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    values = [data.get(key) for key in ("request_id", "device_id", "instance_id", "instance_name", "status")]
    reason = data.get("reason")
    if not all(isinstance(value, str) for value in values) or not (reason is None or isinstance(reason, str)):
        return None
    request_id, device_id, instance_id, instance_name, status = values
    return RetriggerAck(request_id, device_id, instance_id, instance_name, status, reason)


@dataclass(slots=True)
class _Pending:
    """One call that waits for answers: the instances it expects and the first answer of each."""

    device_id: str
    # instance id -> name of every instance expected to answer: this one and the peers the roster says are online
    expected: dict[str, str]
    answers: dict[str, RetriggerAck] = field(default_factory=dict)
    done: asyncio.Event = field(default_factory=asyncio.Event)


class RetriggerCoordinator:
    """The caller side (collects the answers) and the receiver side (runs and answers) of the re-trigger."""

    def __init__(self, manager: Manager) -> None:
        """Initialize the coordinator of one manager."""
        self._manager = manager
        self._unsubscribe_requests: Callable[[], None] | None = None
        self._unsubscribe_acks: Callable[[], None] | None = None
        # request id -> the call waiting for its answers; one record per call, removed when the call ends
        self._pending: dict[str, _Pending] = {}
        # The ids of the requests this instance sent itself, bounded; its own echo is not a foreign request
        self._own: OrderedDict[str, None] = OrderedDict()
        # Replaceable so tests control the wall clock; sent_at and freshness use the wall clock, not the monotonic one
        self.wall_clock: Callable[[], float] = time.time

    async def async_start(self) -> None:
        """Subscribe to the requests of every device and to the answers addressed to this instance."""
        manager = self._manager
        self._unsubscribe_requests = await manager.gateway.async_subscribe(
            retrigger_wildcard(manager.base_topic), self._on_request, RETRIGGER_QOS
        )
        self._unsubscribe_acks = await manager.gateway.async_subscribe(
            acks_topic(manager.base_topic, manager.instance_id), self._on_ack, RETRIGGER_QOS
        )

    @callback
    def async_stop(self) -> None:
        """Release both subscriptions and let every waiting call return with what it has."""
        if self._unsubscribe_requests is not None:
            self._unsubscribe_requests()
            self._unsubscribe_requests = None
        if self._unsubscribe_acks is not None:
            self._unsubscribe_acks()
            self._unsubscribe_acks = None
        for pending in self._pending.values():
            pending.done.set()

    # --- caller side ------------------------------------------------------------------------------------------

    @staticmethod
    def _select_state(device: Device, state: str | None) -> str:
        """Return the StateValue to send: the named one when it matches, else the last acted one of the caller."""
        if state is None:
            if (value := device.tracker.last_acted) is None:
                raise RetriggerError(REASON_NO_STATE)
            return value
        if (value := device.spec.accepted.get(state.strip().lower())) is None:
            raise RetriggerError(REASON_BAD_STATE)
        return value

    def _remember_own(self, request_id: str) -> None:
        """Remember the id of a request this instance sent; only the last RETRIGGER_SEEN_LIMIT ids are kept."""
        self._own[request_id] = None
        while len(self._own) > RETRIGGER_SEEN_LIMIT:
            self._own.popitem(last=False)

    async def async_retrigger(self, device_id: str, state: str | None = None) -> dict[str, Any]:
        """
        Ask every instance to run the actions of one trigger of a device and return who answered how.

        The trigger is the StateValue of the last acted state of this instance, or the named `state` when it matches a
        StateValue of the device. Raises RetriggerError when nothing was sent. The call returns as soon as every
        expected instance answered, else after RETRIGGER_ACK_WINDOW_SECONDS.
        """
        manager = self._manager
        if (device := manager.device(device_id)) is None:
            raise RetriggerError(REASON_UNKNOWN_DEVICE)
        value = self._select_state(device, state)
        request_id = str(uuid.uuid4())
        pending = _Pending(
            device_id=device_id,
            expected={row["id"]: row["name"] for row in manager.presence.rows() if row["online"]},
        )
        self._pending[request_id] = pending
        self._remember_own(request_id)
        payload = json.dumps(
            {
                "request_id": request_id,
                "requester": manager.instance_id,
                "state": value,
                "sent_at": self.wall_clock(),
            }
        )
        try:
            await manager.gateway.async_publish(
                retrigger_topic(manager.base_topic, device_id), payload, retain=False, qos=RETRIGGER_QOS
            )
            try:
                async with asyncio.timeout(RETRIGGER_ACK_WINDOW_SECONDS):
                    await pending.done.wait()
            except TimeoutError:
                pass
        finally:
            self._pending.pop(request_id, None)
        return {
            "request_id": request_id,
            "uuid": device_id,
            "state": value,
            "instances": self._entries(pending),
        }

    @staticmethod
    def _entries(pending: _Pending) -> list[dict[str, str]]:
        """Return one entry per expected instance in roster order, then the instances that answered unexpectedly."""
        entries: list[dict[str, str]] = []
        for instance_id, name in pending.expected.items():
            if (ack := pending.answers.get(instance_id)) is None:
                entries.append({"instance_id": instance_id, "instance_name": name, "status": ACK_NO_ANSWER})
            else:
                entries.append(_entry(ack))
        entries.extend(
            _entry(ack) for instance_id, ack in pending.answers.items() if instance_id not in pending.expected
        )
        return entries

    @callback
    def _on_ack(self, msg: IncomingMessage) -> None:
        """Take the first answer of an instance to a request this instance is waiting for."""
        if msg.retain or (ack := parse_ack(msg.payload)) is None:
            return
        pending = self._pending.get(ack.request_id)
        if pending is None or ack.device_id != pending.device_id or ack.instance_id in pending.answers:
            return
        pending.answers[ack.instance_id] = ack
        if pending.expected.keys() <= pending.answers.keys():
            pending.done.set()

    # --- receiver side ----------------------------------------------------------------------------------------

    @callback
    def _on_request(self, msg: IncomingMessage) -> None:
        """Run the actions a request asks for, as far as the gates allow, and acknowledge it."""
        manager = self._manager
        if msg.retain or (parsed := parse_request(manager.base_topic, msg.topic, msg.payload)) is None:
            return
        device_id, request = parsed
        if (answer := self._decide(device_id, request)) is None:
            return
        status, reason = answer
        manager.entry.async_create_background_task(
            manager.hass, self._async_acknowledge(device_id, request, status, reason), name=f"{DOMAIN} re-trigger ack"
        )

    def _decide(self, device_id: str, request: RetriggerRequest) -> tuple[str, str | None] | None:
        """Run the trigger like a test button press and return the answer, or None when nothing is to be answered."""
        manager = self._manager
        if (device := manager.device(device_id)) is None:
            return None
        if (value := device.spec.accepted.get(request.state.strip().lower())) is None:
            return None
        trigger = device.spec.triggers.get(trigger_key(value))
        if trigger is None or not manager.runner.can_run(device_id, trigger.key):
            return None
        manager.runner.enqueue(
            device_id,
            device.name,
            trigger.label,
            trigger.key,
            {"device_id": device_id, "state": value},
            test=True,
        )
        return ACK_EXECUTED, None

    async def _async_acknowledge(
        self, device_id: str, request: RetriggerRequest, status: str, reason: str | None
    ) -> None:
        """Publish the answer to the requester, not retained; an unavailable MQTT client is logged, never raised."""
        manager = self._manager
        if not manager.running:
            return
        answer = {
            "request_id": request.request_id,
            "device_id": device_id,
            "instance_id": manager.instance_id,
            "instance_name": manager.instance_name,
            "status": status,
        }
        if reason is not None:
            answer["reason"] = reason
        try:
            await manager.gateway.async_publish(
                acks_topic(manager.base_topic, request.requester), json.dumps(answer), retain=False, qos=RETRIGGER_QOS
            )
        except HomeAssistantError as err:
            LOGGER.warning("MQTT could not publish a re-trigger acknowledgement: %s", err)


def _entry(ack: RetriggerAck) -> dict[str, str]:
    """Return the entry of the service response for one acknowledgement."""
    entry = {
        "instance_id": ack.instance_id,
        "instance_name": ack.instance_name,
        "status": ack.status,
    }
    if ack.reason is not None:
        entry["reason"] = ack.reason
    return entry
