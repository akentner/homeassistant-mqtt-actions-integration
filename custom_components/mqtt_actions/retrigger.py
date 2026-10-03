"""
Re-trigger: run the actions of one device again on every instance that approved it, and report who did (OPS-01, OPS-02).

The caller publishes one non-retained request on the re-trigger topic of the device. It carries the exact StateValue to
run, never actions. Every instance, the caller included, receives it and runs the actions of that trigger through the
same path as a test button press (D-01): the tracker, the baseline, the state topic and the circuit breaker are never
touched. Each instance answers on the acknowledgement topic of the requester, and the caller collects the answers for a
short window (D-03).

The request is a second remote execution path next to the state topic, so it reuses the existing gates instead of
creating its own and is never retained (T-04-42). A receiver checks, in this order: retained, size and strict parse,
freshness, duplicate request id, rate limit per device (requests of other instances only), device known, state valid,
mode, circuit breaker and runnability. Everything received is untrusted: parsing never raises and no broker text
reaches a log line unquoted (T-04-46, T-04-48).
"""

import asyncio
import json
import math
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import json_loads

from .const import (
    ACK_DISABLED,
    ACK_ERROR,
    ACK_EXECUTED,
    ACK_NO_ANSWER,
    ACK_NOT_APPROVED,
    ACK_OBSERVING,
    ACK_PAUSED,
    DOMAIN,
    LOGGER,
    MAX_TRACKED_INSTANCES,
    MODE_DISABLED,
    MODE_OBSERVE,
    REASON_BAD_STATE,
    REASON_NO_ACTIONS,
    REASON_NO_STATE,
    REASON_NOT_RUNNABLE,
    REASON_OFFLINE,
    REASON_RATE_LIMITED,
    REASON_UNKNOWN_DEVICE,
    RETRIGGER_ACK_WINDOW_SECONDS,
    RETRIGGER_DEVICE_INTERVAL_SECONDS,
    RETRIGGER_MAX_AGE_SECONDS,
    RETRIGGER_SEEN_LIMIT,
)
from .model import invalid_name, shown, trigger_key
from .presence import valid_text, valid_uuid, within_size_cap
from .topics import acks_topic, is_valid_device_id, parse_retrigger_topic, retrigger_topic, retrigger_wildcard
from .trust import ApprovalState

if TYPE_CHECKING:
    from collections.abc import Callable

    from .manager import Device, Manager
    from .mqtt_gateway import IncomingMessage

RETRIGGER_QOS = 1
# What an acknowledgement may say; no_answer is produced by the caller and is never a valid wire status
_STATUS_WORDS = frozenset({ACK_EXECUTED, ACK_NOT_APPROVED, ACK_PAUSED, ACK_OBSERVING, ACK_DISABLED, ACK_ERROR})
_REASON_WORDS = frozenset(
    {REASON_UNKNOWN_DEVICE, REASON_BAD_STATE, REASON_NO_ACTIONS, REASON_NOT_RUNNABLE, REASON_OFFLINE}
)


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


def _json_object(payload: str) -> dict[str, Any] | None:
    """Return the JSON object of a payload that is within the size cap, or None."""
    if not within_size_cap(payload):
        return None
    try:
        data = json_loads(payload)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _valid_id(value: object) -> bool:
    """Return whether a value is an id in the shape of device and instance ids."""
    return isinstance(value, str) and is_valid_device_id(value)


def _valid_state(value: object) -> bool:
    """Return whether a value is a non-empty printable text within the length cap of a StateValue."""
    return isinstance(value, str) and bool(value) and not invalid_name(value)


def _valid_time(value: object) -> bool:
    """Return whether a value is a finite number that is not a bool."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # an integer too large for a float
        return False


def parse_request(base_topic: str, topic: str, payload: str) -> tuple[str, RetriggerRequest] | None:
    """
    Return the device id of the topic and the request of a message, or None for anything else.

    Never raises and never logs: the message is untrusted, so the answer is only a value or None (T-04-46).
    """
    device_id = parse_retrigger_topic(base_topic, topic)
    if device_id is None or not is_valid_device_id(device_id) or (data := _json_object(payload)) is None:
        return None
    request_id, requester, state, sent_at = (data.get(key) for key in ("request_id", "requester", "state", "sent_at"))
    if not (valid_uuid(request_id) and _valid_id(requester) and _valid_state(state) and _valid_time(sent_at)):
        return None
    return device_id, RetriggerRequest(request_id=request_id, requester=requester, state=state, sent_at=sent_at)


def parse_ack(payload: str) -> RetriggerAck | None:
    """Return the acknowledgement of a message, or None for anything that is not exactly one; never raises."""
    if (data := _json_object(payload)) is None:
        return None
    request_id, device_id, instance_id, name, status, reason = (
        data.get(key) for key in ("request_id", "device_id", "instance_id", "instance_name", "status", "reason")
    )
    if not (
        valid_uuid(request_id)
        and _valid_id(device_id)
        and _valid_id(instance_id)
        and valid_text(name)
        and isinstance(status, str)
        and status in _STATUS_WORDS
        and (reason is None or (isinstance(reason, str) and reason in _REASON_WORDS))
    ):
        return None
    return RetriggerAck(request_id, device_id, instance_id, name, status, reason)


@dataclass(slots=True)
class _Pending:
    """One call that waits for answers: who it expects, who is offline in the roster and the first answer of each."""

    device_id: str
    # instance id -> name of every instance expected to answer: this one and the peers the roster says are online
    expected: dict[str, str]
    # instance id -> name of the roster instances that are offline; they are listed without waiting for them
    offline: dict[str, str]
    answers: dict[str, RetriggerAck] = field(default_factory=dict)
    done: asyncio.Event = field(default_factory=asyncio.Event)


def _remember(store: OrderedDict[str, None], key: str) -> None:
    """Remember a key in an insertion-ordered record that keeps only the last RETRIGGER_SEEN_LIMIT keys."""
    store[key] = None
    while len(store) > RETRIGGER_SEEN_LIMIT:
        store.popitem(last=False)


class RetriggerCoordinator:
    """The caller side (collects the answers) and the receiver side (runs and answers) of the re-trigger."""

    def __init__(self, manager: Manager) -> None:
        """Initialize the coordinator of one manager."""
        self._manager = manager
        self._unsubscribe_requests: Callable[[], None] | None = None
        self._unsubscribe_acks: Callable[[], None] | None = None
        # request id -> the call waiting for its answers; one record per call, removed when the call ends
        self._pending: dict[str, _Pending] = {}
        # The ids of the requests this instance sent itself; its own echo is not a foreign request, so it skips the
        # receiver rate limit but never the duplicate check (research pitfall 3)
        self._own: OrderedDict[str, None] = OrderedDict()
        # The request ids this instance has already handled
        self._seen: OrderedDict[str, None] = OrderedDict()
        # device id -> when a request of it was last accepted on the receiver side; bounded, on Manager.clock
        self._last_accepted: dict[str, float] = {}
        # device id -> when this instance last sent a request for it, on Manager.clock
        self._last_sent: dict[str, float] = {}
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
        """Remember the id of a request this instance sent, so its own echo is recognized."""
        _remember(self._own, request_id)

    def _claim_send_slot(self, device_id: str) -> None:
        """Record that a request for the device is sent now, or raise when one was sent less than an interval ago."""
        now = self._manager.clock()
        self._last_sent = {
            key: sent for key, sent in self._last_sent.items() if now - sent < RETRIGGER_DEVICE_INTERVAL_SECONDS
        }
        if device_id in self._last_sent:
            raise RetriggerError(REASON_RATE_LIMITED)
        self._last_sent[device_id] = now

    async def async_retrigger(self, device_id: str, state: str | None = None) -> dict[str, Any]:
        """
        Ask every instance to run the actions of one trigger of a device and return who answered how.

        The trigger is the StateValue of the last acted state of this instance, or the named `state` when it matches a
        StateValue of the device. Raises RetriggerError when nothing was sent: the device is unknown, the state is
        unusable, or a request for the device was sent less than RETRIGGER_DEVICE_INTERVAL_SECONDS ago. The call
        returns as soon as every instance the roster says is online answered, else after RETRIGGER_ACK_WINDOW_SECONDS.
        """
        manager = self._manager
        if (device := manager.device(device_id)) is None:
            raise RetriggerError(REASON_UNKNOWN_DEVICE)
        value = self._select_state(device, state)
        self._claim_send_slot(device_id)
        request_id = str(uuid.uuid4())
        rows = manager.presence.rows()
        pending = _Pending(
            device_id=device_id,
            expected={row["id"]: row["name"] for row in rows if row["online"]},
            offline={row["id"]: row["name"] for row in rows if not row["online"]},
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
        except BaseException:
            # Nothing reached the broker: neither the pending record nor the interval may count this attempt
            self._pending.pop(request_id, None)
            self._last_sent.pop(device_id, None)
            raise
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
        """
        Return one entry per instance: the expected ones, then the offline ones, then unexpected answers.

        An expected instance without an answer is `no_answer`. A roster instance that is offline is `no_answer` with the
        reason `offline`, unless it answered after all.
        """
        entries: list[dict[str, str]] = []
        for instance_id, name in pending.expected.items():
            if (ack := pending.answers.get(instance_id)) is None:
                entries.append({"instance_id": instance_id, "instance_name": name, "status": ACK_NO_ANSWER})
            else:
                entries.append(_entry(ack))
        for instance_id, name in pending.offline.items():
            if (ack := pending.answers.get(instance_id)) is None:
                entries.append(
                    {
                        "instance_id": instance_id,
                        "instance_name": name,
                        "status": ACK_NO_ANSWER,
                        "reason": REASON_OFFLINE,
                    }
                )
            else:
                entries.append(_entry(ack))
        known = pending.expected.keys() | pending.offline.keys()
        entries.extend(_entry(ack) for instance_id, ack in pending.answers.items() if instance_id not in known)
        return entries

    @callback
    def _on_ack(self, msg: IncomingMessage) -> None:
        """Take the first answer of an instance to a request this instance is waiting for."""
        if msg.retain or (ack := parse_ack(msg.payload)) is None:
            return
        pending = self._pending.get(ack.request_id)
        if (
            pending is None
            or ack.device_id != pending.device_id
            or ack.instance_id in pending.answers
            or len(pending.answers) >= MAX_TRACKED_INSTANCES
        ):
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

    def _admit(self, device_id: str, request: RetriggerRequest) -> bool:
        """Return whether a parsed request passes freshness, the duplicate rule and the per-device rate limit."""
        if abs(self.wall_clock() - request.sent_at) > RETRIGGER_MAX_AGE_SECONDS:
            return False
        if request.request_id in self._seen:
            return False
        _remember(self._seen, request.request_id)
        now = self._manager.clock()
        last = self._last_accepted.get(device_id)
        # The echo of this instance's own request skips the limit; the caller already limited its own calls
        if request.request_id not in self._own and last is not None and now - last < RETRIGGER_DEVICE_INTERVAL_SECONDS:
            return False
        # Re-inserted so the dict stays ordered by time; bounded because device ids in requests are not trusted
        self._last_accepted.pop(device_id, None)
        self._last_accepted[device_id] = now
        if len(self._last_accepted) > MAX_TRACKED_INSTANCES:
            self._last_accepted = {
                key: accepted
                for key, accepted in self._last_accepted.items()
                if now - accepted < RETRIGGER_DEVICE_INTERVAL_SECONDS
            }
            while len(self._last_accepted) > MAX_TRACKED_INSTANCES:
                del self._last_accepted[next(iter(self._last_accepted))]
        return True

    def _decide(self, device_id: str, request: RetriggerRequest) -> tuple[str, str | None] | None:
        """
        Return the answer to a request after running its trigger when allowed, None when the request is dropped.

        Only what the existing gates allow runs: a device in observe or disabled mode, a paused device and an unapproved
        or blocked mirror run nothing. The run is enqueued like a test button press, so the tracker, the baseline, the
        state topic and the circuit breaker are never touched (D-01).
        """
        if not self._admit(device_id, request):
            return None
        if (device := self._manager.device(device_id)) is None:
            return ACK_ERROR, REASON_UNKNOWN_DEVICE
        if (value := device.spec.accepted.get(request.state.strip().lower())) is None:
            return ACK_ERROR, REASON_BAD_STATE
        if (stopped := self._stopped(device)) is not None:
            return stopped
        return self._run(device, value)

    def _stopped(self, device: Device) -> tuple[str, str | None] | None:
        """Return the answer of a device that runs nothing because of its mode or its circuit breaker, else None."""
        mode = self._manager.effective_mode(device.device_id)
        if mode == MODE_DISABLED:
            return ACK_DISABLED, None
        if mode == MODE_OBSERVE:
            LOGGER.info("Observe mode: a re-trigger of device %s ran no actions", shown(device.name))
            return ACK_OBSERVING, None
        if device.breaker.tripped:
            return ACK_PAUSED, None
        return None

    def _run(self, device: Device, value: str) -> tuple[str, str | None]:
        """Enqueue the actions of the trigger of a StateValue like a test press, or explain why they cannot run."""
        manager = self._manager
        trigger = device.spec.triggers.get(trigger_key(value))
        if trigger is None:
            return ACK_ERROR, REASON_NOT_RUNNABLE
        if not manager.runner.can_run(device.device_id, trigger.key):
            if manager.approval_state(device.device_id) in {ApprovalState.PENDING, ApprovalState.BLOCKED}:
                return ACK_NOT_APPROVED, None
            return ACK_ERROR, REASON_NOT_RUNNABLE if trigger.actions else REASON_NO_ACTIONS
        manager.runner.enqueue(
            device.device_id,
            device.name,
            trigger.label,
            trigger.key,
            {"device_id": device.device_id, "state": value},
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
