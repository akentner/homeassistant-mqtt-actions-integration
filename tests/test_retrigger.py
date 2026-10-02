"""Re-trigger protocol (OPS-01, OPS-02, D-01 to D-04): topics, request and acknowledgement parsing, receiver rules."""

import json
import math
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.mqtt_actions import retrigger as retrigger_module
from custom_components.mqtt_actions import topics
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    MAX_BROKER_MESSAGE_BYTES,
    RETRIGGER_DEVICE_INTERVAL_SECONDS,
)
from custom_components.mqtt_actions.retrigger import (
    RetriggerAck,
    RetriggerError,
    RetriggerRequest,
    parse_ack,
    parse_request,
)
from tests.documents import document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from tests.fake_broker import FakeBroker, Instance

BASE = "b"
REQUEST_ID = "0b1d4e0e-3d5a-4f6e-8a55-2c1f9a7d6b10"


def test_retrigger_topic_helpers() -> None:
    """The request topic is per device, the acknowledgement topic per requester, and only the exact shape parses."""
    assert topics.retrigger_topic(BASE, "d1") == "b/v1/devices/d1/retrigger"
    assert topics.retrigger_wildcard(BASE) == "b/v1/devices/+/retrigger"
    assert topics.acks_topic(BASE, "i1") == "b/v1/instances/i1/acks"

    assert topics.parse_retrigger_topic(BASE, "b/v1/devices/d1/retrigger") == "d1"
    assert topics.parse_retrigger_topic(BASE, topics.test_topic(BASE, "d1")) is None
    assert topics.parse_retrigger_topic(BASE, topics.config_topic(BASE, "d1")) is None
    assert topics.parse_retrigger_topic(BASE, "b/v1/devices/d1/x/retrigger") is None


def test_request_and_ack_roundtrip_parse() -> None:
    """A valid request and a valid acknowledgement parse into their dataclasses with the sent values."""
    payload = json.dumps({"request_id": REQUEST_ID, "requester": "inst-a", "state": "ON", "sent_at": 1_700_000_000.5})
    parsed = parse_request(BASE, "b/v1/devices/d1/retrigger", payload)
    assert parsed == (
        "d1",
        RetriggerRequest(request_id=REQUEST_ID, requester="inst-a", state="ON", sent_at=1_700_000_000.5),
    )

    ack_payload = json.dumps(
        {
            "request_id": REQUEST_ID,
            "device_id": "d1",
            "instance_id": "inst-b",
            "instance_name": "Beta",
            "status": "error",
            "reason": "no_actions",
        }
    )
    assert parse_ack(ack_payload) == RetriggerAck(
        request_id=REQUEST_ID,
        device_id="d1",
        instance_id="inst-b",
        instance_name="Beta",
        status="error",
        reason="no_actions",
    )
    plain = json.dumps(
        {
            "request_id": REQUEST_ID,
            "device_id": "d1",
            "instance_id": "inst-b",
            "instance_name": "Beta",
            "status": "executed",
        }
    )
    ack = parse_ack(plain)
    assert ack is not None
    assert (ack.status, ack.reason) == ("executed", None)


# --- strict parsing (T-04-46) --------------------------------------------------------------------------------------

REQUEST = {"request_id": REQUEST_ID, "requester": "inst-a", "state": "ON", "sent_at": 1_700_000_000.5}
ACK = {
    "request_id": REQUEST_ID,
    "device_id": "d1",
    "instance_id": "inst-b",
    "instance_name": "Beta",
    "status": "executed",
}
REQUEST_TOPIC = "b/v1/devices/d1/retrigger"
_MISSING = object()


def _without(base: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in base.items() if name != key}


def _request_cases() -> list[Any]:
    cases: list[Any] = [
        pytest.param(REQUEST_TOPIC, "not json", id="not-json"),
        pytest.param(REQUEST_TOPIC, "[]", id="json-list"),
        pytest.param(
            REQUEST_TOPIC, json.dumps({**REQUEST, "pad": "x" * MAX_BROKER_MESSAGE_BYTES}), id="too-many-chars"
        ),
        pytest.param(
            REQUEST_TOPIC,
            json.dumps({**REQUEST, "pad": "ä" * 600}, ensure_ascii=False),
            id="too-many-utf8-bytes",
        ),
        pytest.param(topics.test_topic("b", "d1"), json.dumps(REQUEST), id="test-topic"),
        pytest.param("b/v1/devices/d1/x/retrigger", json.dumps(REQUEST), id="extra-level"),
    ]
    for name, value in (
        ("request_id", "NOT-A-UUID"),
        ("request_id", REQUEST_ID.upper()),
        ("request_id", REQUEST_ID.replace("-", "")),
        ("request_id", 5),
        ("requester", "has space"),
        ("requester", "a/b"),
        ("requester", ""),
        ("requester", "x" * 65),
        ("requester", 5),
        ("state", 5),
        ("state", None),
        ("state", ""),
        ("state", "x" * 65),
        ("sent_at", True),
        ("sent_at", "1700000000"),
        ("sent_at", None),
        ("sent_at", math.nan),
        ("sent_at", math.inf),
    ):
        cases.append(pytest.param(REQUEST_TOPIC, json.dumps({**REQUEST, name: value}), id=f"{name}={value!r}"))
    cases.extend(
        pytest.param(REQUEST_TOPIC, json.dumps(_without(REQUEST, key)), id=f"missing-{key}") for key in REQUEST
    )
    return cases


@pytest.mark.parametrize(("topic", "payload"), _request_cases())
def test_parse_request_rejects_invalid_payloads(topic: str, payload: str) -> None:
    """T-04-46: every malformed, oversized or foreign message is None, and nothing raises."""
    assert parse_request(BASE, topic, payload) is None


def _ack_cases() -> list[Any]:
    cases: list[Any] = [
        pytest.param("not json", id="not-json"),
        pytest.param("[]", id="json-list"),
        pytest.param(json.dumps({**ACK, "pad": "x" * MAX_BROKER_MESSAGE_BYTES}), id="too-many-chars"),
        pytest.param(json.dumps({**ACK, "pad": "ä" * 600}, ensure_ascii=False), id="too-many-utf8-bytes"),
    ]
    for name, value in (
        ("request_id", "NOT-A-UUID"),
        ("request_id", 5),
        ("instance_id", "has space"),
        ("instance_id", ""),
        ("instance_id", 5),
        ("instance_name", "   "),
        ("instance_name", ""),
        ("instance_name", "a\x00b"),
        ("instance_name", "line\nbreak"),
        ("instance_name", "x" * 65),
        ("instance_name", 5),
        ("status", "no_answer"),
        ("status", "whatever"),
        ("status", 5),
        ("reason", "because"),
        ("reason", 5),
        ("device_id", "a b"),
        ("device_id", ""),
        ("device_id", "x" * 65),
        ("device_id", 5),
    ):
        cases.append(pytest.param(json.dumps({**ACK, name: value}), id=f"{name}={value!r}"))
    cases.extend(pytest.param(json.dumps(_without(ACK, key)), id=f"missing-{key}") for key in ACK)
    return cases


@pytest.mark.parametrize("payload", _ack_cases())
def test_parse_ack_rejects_invalid_payloads(payload: str) -> None:
    """T-04-46: an acknowledgement that is not exactly an acknowledgement is None."""
    assert parse_ack(payload) is None


# --- receiver rules on one instance (T-04-42, T-04-43, T-04-45) ---------------------------------------------------

BROKER_BASE = "mqtt_actions"
NOW = 1_700_000_000.0
REQUESTER = "requester-1"
INTERVAL = RETRIGGER_DEVICE_INTERVAL_SECONDS


async def _settle(instance: Instance) -> None:
    """Let the instance finish the messages and background tasks the broker delivered (a mirror needs a few rounds)."""
    for _ in range(4):
        await instance.hass.async_block_till_done(wait_background_tasks=True)


def _clock(instance: Instance, start: float = 1000.0) -> list[float]:
    """Replace the monotonic clock and the wall clock of an instance with one settable pair; return the monotonic."""
    now = [start]
    instance.manager.clock = lambda: now[0]
    instance.manager.retrigger.wall_clock = lambda: NOW
    return now


def _request_payload(
    request_id: str | None = None, *, requester: str = REQUESTER, state: str = "ON", sent_at: float = NOW
) -> str:
    return json.dumps(
        {"request_id": request_id or str(uuid.uuid4()), "requester": requester, "state": state, "sent_at": sent_at}
    )


async def _send(
    fake_broker: FakeBroker, instance: Instance, device_id: str, payload: str | None = None, *, retain: bool = False
) -> None:
    """Deliver a request of a foreign requester live (retain False) and let the instance finish."""
    fake_broker.publish(topics.retrigger_topic(BROKER_BASE, device_id), payload or _request_payload(), retain=retain)
    await _settle(instance)


def _acks(instance: Instance, requester: str = REQUESTER) -> list[dict[str, Any]]:
    """Return the acknowledgements an instance published for a requester, with their retain flags checked."""
    published = [item for item in instance.gateway.published if item[0] == topics.acks_topic(BROKER_BASE, requester)]
    assert all(retain is False for _topic, _payload, retain in published)
    return [json.loads(payload) for _topic, payload, _retain in published]


async def _owned(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable, **kwargs: Any
) -> tuple[Instance, str, list[Any]]:
    """Start one instance owning a switch with ON actions; return it, the device id and the test.on call list."""
    kwargs.setdefault("on", [{"action": "test.on"}])
    sub = make_switch_subentry("Lamp", **kwargs)
    instance = await make_instance("recv", hass=hass, subentries=[sub])
    calls = async_mock_service(hass, "test", "on")
    await _settle(instance)
    return instance, sub["data"][CONF_DEVICE_ID], calls


async def test_retained_requests_are_ignored(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-43: a request that arrives as a retained replay runs nothing and gets no acknowledgement."""
    instance, device_id, calls = await _owned(hass, make_instance, make_switch_subentry)
    _clock(instance)
    # Stored without delivery, so the only delivery is the replay a reconnect causes, flagged as retained
    fake_broker.retained[topics.retrigger_topic(BROKER_BASE, device_id)] = _request_payload()

    instance.gateway.reconnect()
    await _settle(instance)

    assert calls == []
    assert _acks(instance) == []
    # The same payload live is accepted, so the replay flag was the only difference
    await _send(fake_broker, instance, device_id)
    assert len(calls) == 1
    assert [ack["status"] for ack in _acks(instance)] == ["executed"]


async def test_stale_and_future_requests_are_dropped(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-45: a request more than 60 seconds old or sent more than 60 seconds ahead runs nothing."""
    instance, device_id, calls = await _owned(hass, make_instance, make_switch_subentry)
    now = _clock(instance)

    for sent_at in (NOW - 60.5, NOW + 60.5):
        await _send(fake_broker, instance, device_id, _request_payload(sent_at=sent_at))
        now[0] += INTERVAL
    assert calls == []
    assert _acks(instance) == []

    await _send(fake_broker, instance, device_id, _request_payload(sent_at=NOW - 59))
    now[0] += INTERVAL
    await _send(fake_broker, instance, device_id, _request_payload(sent_at=NOW + 59))
    assert len(calls) == 2
    assert len(_acks(instance)) == 2


async def test_duplicate_request_ids_run_once(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-43: the same request id runs once and is acknowledged once; only the last ids are remembered."""
    instance, device_id, calls = await _owned(hass, make_instance, make_switch_subentry)
    now = _clock(instance)
    payload = _request_payload()

    await _send(fake_broker, instance, device_id, payload)
    now[0] += INTERVAL  # the rate limit would not stop the second delivery, only the duplicate rule does
    await _send(fake_broker, instance, device_id, payload)
    assert len(calls) == 1
    assert len(_acks(instance)) == 1

    with patch.object(retrigger_module, "RETRIGGER_SEEN_LIMIT", 2):
        ids = [str(uuid.uuid4()) for _ in range(3)]
        for request_id in ids:
            now[0] += INTERVAL
            await _send(fake_broker, instance, device_id, _request_payload(request_id))
        assert len(calls) == 4
        # The oldest remembered id fell out and is accepted again; a recent one is still a duplicate
        now[0] += INTERVAL
        await _send(fake_broker, instance, device_id, _request_payload(ids[0]))
        assert len(calls) == 5
        now[0] += INTERVAL
        await _send(fake_broker, instance, device_id, _request_payload(ids[2]))
        assert len(calls) == 5


async def test_receiver_rate_limit_per_device(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-43: one accepted request per device per interval from other instances; another device is unaffected."""
    first = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    second = make_switch_subentry("Fan", on=[{"action": "test.on"}])
    instance = await make_instance("recv", hass=hass, subentries=[first, second])
    calls = async_mock_service(hass, "test", "on")
    now = _clock(instance)
    a, b = first["data"][CONF_DEVICE_ID], second["data"][CONF_DEVICE_ID]

    await _send(fake_broker, instance, a)
    now[0] += INTERVAL - 1
    await _send(fake_broker, instance, a)
    assert len(calls) == 1
    assert len(_acks(instance)) == 1  # the limited request is ignored without an answer

    await _send(fake_broker, instance, b)
    assert len(calls) == 2

    now[0] += 1
    await _send(fake_broker, instance, a)
    assert len(calls) == 3

    # A request whose id this instance sent itself is its own echo and skips the receiver limit
    own_id = str(uuid.uuid4())
    instance.manager.retrigger._remember_own(own_id)
    await _send(fake_broker, instance, a, _request_payload(own_id, requester=instance.manager.instance_id))
    assert len(calls) == 4


# --- statuses ---------------------------------------------------------------------------------------------------


@dataclass
class _Setup:
    instance: Instance
    device_id: str
    state: str
    calls: list[Any]


async def _mirror(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, *, on: list[dict[str, Any]], approve: bool
) -> _Setup:
    spec = make_spec(on=on)
    instance = await make_instance("recv", hass=hass)
    calls = async_mock_service(hass, "test", "on")
    fake_broker.publish(topics.config_topic(BROKER_BASE, spec.device_id), document_payload(spec), retain=True)
    await _settle(instance)
    assert spec.device_id in instance.manager.mirrors
    if approve:
        info = instance.manager.mirrors[spec.device_id].mirror
        assert info is not None
        assert await instance.manager.async_approve(spec.device_id, info.actions_hash) is True
    return _Setup(instance, spec.device_id, "ON", calls)


async def _prepare(
    case: str,
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
) -> _Setup:
    """Build the receiver of one status case and return it with the device and the state the request names."""
    if case in {"executed", "not_approved_pending", "not_approved_blocked", "mirror_no_actions"}:
        on = {
            "executed": [{"action": "test.on"}],
            "not_approved_pending": [{"action": "test.on"}],
            "not_approved_blocked": [{"action": "shell_command.x"}],
            "mirror_no_actions": [],
        }[case]
        return await _mirror(hass, fake_broker, make_instance, on=on, approve=case == "executed")
    if case == "no_actions":
        instance, device_id, calls = await _owned(hass, make_instance, make_switch_subentry, on=[])
        return _Setup(instance, device_id, "ON", calls)
    if case == "not_runnable":
        instance, device_id, calls = await _owned(
            hass, make_instance, make_switch_subentry, on=[{"not_an_action": "x"}]
        )
        return _Setup(instance, device_id, "ON", calls)
    instance, device_id, calls = await _owned(hass, make_instance, make_switch_subentry)
    setup = _Setup(instance, device_id, "ON", calls)
    if case == "disabled":
        await instance.manager.async_set_device_mode(device_id, "disabled")
    elif case == "instance_disabled":
        await instance.manager.async_set_instance_mode("disabled")
    elif case == "observing":
        await instance.manager.async_set_device_mode(device_id, "observe")
    elif case == "paused":
        device = instance.manager.device(device_id)
        assert device is not None
        device.breaker.trip()
    elif case == "bad_state":
        setup.state = "MAYBE"
    elif case == "unknown_device":
        setup.device_id = str(uuid.uuid4())
    return setup


STATUS_CASES = {
    "executed": ("executed", None),
    "disabled": ("disabled", None),
    "instance_disabled": ("disabled", None),
    "observing": ("observing", None),
    "paused": ("paused", None),
    "not_approved_pending": ("not_approved", None),
    "not_approved_blocked": ("not_approved", None),
    "no_actions": ("error", "no_actions"),
    "mirror_no_actions": ("error", "no_actions"),
    "not_runnable": ("error", "not_runnable"),
    "bad_state": ("error", "bad_state"),
    "unknown_device": ("error", "unknown_device"),
}


@pytest.mark.parametrize("case", STATUS_CASES)
async def test_statuses(
    case: str,
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03, TRU-01, D-14: every case answers with its status word and reason, and only an approved one runs."""
    setup = await _prepare(case, hass, fake_broker, make_instance, make_switch_subentry)
    _clock(setup.instance)

    await _send(fake_broker, setup.instance, setup.device_id, _request_payload(state=setup.state))

    status, reason = STATUS_CASES[case]
    answers = _acks(setup.instance)
    assert len(answers) == 1
    assert answers[0]["status"] == status
    assert answers[0].get("reason") == reason
    assert answers[0]["device_id"] == setup.device_id
    assert answers[0]["instance_id"] == setup.instance.manager.instance_id
    assert len(setup.calls) == (1 if status == "executed" else 0)


# --- the caller (D-02, D-03) -----------------------------------------------------------------------------------


async def test_caller_rate_limit_and_state_selection(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-01: the caller refuses a repeat inside the interval, matches a named state and refuses an unusable one."""
    sub = make_select_subentry(
        "Mode",
        [
            ("Auto", "Auto", [{"action": "test.auto"}]),
            ("Eco", "Eco", [{"action": "test.eco"}]),
        ],
    )
    device_id = sub["data"][CONF_DEVICE_ID]
    switch = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    switch_id = switch["data"][CONF_DEVICE_ID]
    instance = await make_instance("caller", hass=hass, subentries=[sub, switch])
    auto_calls = async_mock_service(hass, "test", "auto")
    eco_calls = async_mock_service(hass, "test", "eco")
    now = _clock(instance)
    coordinator = instance.manager.retrigger
    await _settle(instance)

    # Without a baseline and without a named state there is nothing to send
    with pytest.raises(RetriggerError) as no_state:
        await coordinator.async_retrigger(switch_id)
    assert no_state.value.reason == "no_state"
    assert not [
        item for item in instance.gateway.published if item[0] == topics.retrigger_topic(BROKER_BASE, switch_id)
    ]

    fake_broker.publish(topics.state_topic(BROKER_BASE, device_id), "Auto", retain=True)
    await _settle(instance)
    assert len(auto_calls) == 1

    with pytest.raises(RetriggerError) as bad_state:
        await coordinator.async_retrigger(device_id, "nonsense")
    assert bad_state.value.reason == "bad_state"

    # A refused call did not count: the named state is matched case-insensitively and its canonical value is sent
    result = await coordinator.async_retrigger(device_id, " eCo ")
    await _settle(instance)
    assert result["state"] == "Eco"
    assert (len(auto_calls), len(eco_calls)) == (1, 1)

    sent = [item for item in instance.gateway.published if item[0] == topics.retrigger_topic(BROKER_BASE, device_id)]
    assert len(sent) == 1
    with pytest.raises(RetriggerError) as limited:
        await coordinator.async_retrigger(device_id)
    assert limited.value.reason == "rate_limited"
    assert (
        len([item for item in instance.gateway.published if item[0] == topics.retrigger_topic(BROKER_BASE, device_id)])
        == 1
    )

    now[0] += INTERVAL
    result = await coordinator.async_retrigger(device_id)
    await _settle(instance)
    assert result["state"] == "Auto"
    assert (len(auto_calls), len(eco_calls)) == (2, 1)
