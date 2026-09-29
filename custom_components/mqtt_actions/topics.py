"""Topic builders. Pure functions without Home Assistant imports."""

from .const import TOPIC_VERSION

_FORBIDDEN_CHARACTERS = frozenset("#+\x00")


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


def availability_topic(base: str, instance_id: str) -> str:
    """Return the availability topic of this instance."""
    return f"{base}/{TOPIC_VERSION}/instances/{instance_id}/availability"


def discovery_topic(prefix: str, device_id: str) -> str:
    """Return the device-based MQTT Discovery config topic."""
    return f"{prefix}/device/{device_id}/config"
