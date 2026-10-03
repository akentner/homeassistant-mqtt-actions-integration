"""Topic builders. Pure functions without Home Assistant imports."""

import re

from .const import TOPIC_VERSION

_FORBIDDEN_CHARACTERS = frozenset("#+\x00")
# A parsed id is exactly one topic level: no separator and no wildcard
_SEGMENT_FORBIDDEN = frozenset("/#+\x00")
# Owned device ids are uuid4 strings; a foreign id is accepted only in this shape and length (WR-05)
_DEVICE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def is_valid_device_id(value: str) -> bool:
    """Return True for an id fit to be stored and used in issue ids and topics: 1 to 64 of letters, digits, _ and -."""
    return _DEVICE_ID.fullmatch(value) is not None


class InvalidBaseTopic(ValueError):  # noqa: N818
    """Raised when a base topic could widen a subscription or is not a valid topic prefix."""


def validate_base_topic(value: str) -> str:
    """
    Return the base topic unchanged or raise InvalidBaseTopic.

    The base topic is one-way (D-01) and prefixes every per-device subscription, so a wildcard here would turn
    them into broad subscriptions (threat T-01-06).
    """
    if not value:
        msg = "base topic is empty"
        raise InvalidBaseTopic(msg)
    if _FORBIDDEN_CHARACTERS.intersection(value):
        msg = "base topic contains a wildcard or NUL character"
        raise InvalidBaseTopic(msg)
    levels = value.split("/")
    if any(not level for level in levels):
        msg = "base topic has a leading or trailing slash or an empty level"
        raise InvalidBaseTopic(msg)
    if levels[0].startswith("$"):
        msg = "base topic must not start with $ (broker-reserved namespace)"
        raise InvalidBaseTopic(msg)
    return value


def state_topic(base: str, device_id: str) -> str:
    """Return the retained state topic of a device; the command topic is the same string (D-01)."""
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/state"


def test_topic(base: str, device_id: str) -> str:
    """Return the non-retained topic the test buttons of a device publish to; it never carries device state (D-13)."""
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/test"


def retrigger_topic(base: str, device_id: str) -> str:
    """Return the non-retained topic a re-trigger request of a device is published to (D-02)."""
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/retrigger"


def acks_topic(base: str, requester_id: str) -> str:
    """Return the non-retained topic on which the instances answer the re-trigger requests of one requester (D-03)."""
    return f"{base}/{TOPIC_VERSION}/instances/{requester_id}/acks"


def availability_topic(base: str, instance_id: str) -> str:
    """Return the availability topic of this instance."""
    return f"{base}/{TOPIC_VERSION}/instances/{instance_id}/availability"


def heartbeat_topic(base: str, instance_id: str) -> str:
    """Return the non-retained heartbeat topic of an instance (D-05)."""
    return f"{base}/{TOPIC_VERSION}/instances/{instance_id}/heartbeat"


def discovery_topic(prefix: str, device_id: str) -> str:
    """Return the device-based MQTT Discovery config topic."""
    return f"{prefix}/device/{device_id}/config"


def config_topic(base: str, device_id: str) -> str:
    """Return the retained config document topic of a device; only its owner writes it (D-12)."""
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/config"


def config_wildcard(base: str) -> str:
    """Return the subscription that matches the config topic of every device; the base is wildcard-free."""
    return f"{base}/{TOPIC_VERSION}/devices/+/config"


def retrigger_wildcard(base: str) -> str:
    """Return the subscription that matches the re-trigger topic of every device."""
    return f"{base}/{TOPIC_VERSION}/devices/+/retrigger"


def availability_wildcard(base: str) -> str:
    """Return the subscription that matches the availability topic of every instance."""
    return f"{base}/{TOPIC_VERSION}/instances/+/availability"


def heartbeat_wildcard(base: str) -> str:
    """Return the subscription that matches the heartbeat topic of every instance."""
    return f"{base}/{TOPIC_VERSION}/instances/+/heartbeat"


def discovery_wildcard(prefix: str) -> str:
    """Return the subscription that matches the device discovery topic of every device."""
    return f"{prefix}/device/+/config"


def _parse_segment(topic: str, prefix: str, suffix: str) -> str | None:
    """Return the one segment between an exact prefix and suffix, or None when the topic does not have that shape."""
    if not (topic.startswith(prefix) and topic.endswith(suffix)) or len(topic) < len(prefix) + len(suffix) + 1:
        return None
    segment = topic[len(prefix) : len(topic) - len(suffix)]
    if not segment or _SEGMENT_FORBIDDEN.intersection(segment):
        return None
    return segment


def parse_config_topic(base: str, topic: str) -> str | None:
    """Return the device id of a config topic, or None for any other topic."""
    return _parse_segment(topic, f"{base}/{TOPIC_VERSION}/devices/", "/config")


def parse_retrigger_topic(base: str, topic: str) -> str | None:
    """Return the device id of a re-trigger topic, or None for any other topic."""
    return _parse_segment(topic, f"{base}/{TOPIC_VERSION}/devices/", "/retrigger")


def parse_availability_topic(base: str, topic: str) -> str | None:
    """Return the instance id of an availability topic, or None for any other topic."""
    return _parse_segment(topic, f"{base}/{TOPIC_VERSION}/instances/", "/availability")


def parse_heartbeat_topic(base: str, topic: str) -> str | None:
    """Return the instance id of a heartbeat topic, or None for any other topic."""
    return _parse_segment(topic, f"{base}/{TOPIC_VERSION}/instances/", "/heartbeat")


def parse_discovery_topic(prefix: str, topic: str) -> str | None:
    """Return the device id of a device discovery topic, or None for any other topic."""
    return _parse_segment(topic, f"{prefix}/device/", "/config")
