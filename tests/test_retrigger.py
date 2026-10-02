"""Re-trigger protocol (OPS-01, OPS-02, D-01 to D-04): topics, request and acknowledgement parsing, receiver rules."""

import json

from custom_components.mqtt_actions import topics

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
    # Imported here so that a missing module fails this test and not the whole collection
    from custom_components.mqtt_actions.retrigger import (
        RetriggerAck,
        RetriggerRequest,
        parse_ack,
        parse_request,
    )

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
