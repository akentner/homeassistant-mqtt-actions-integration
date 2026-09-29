"""Topic builders. Pure functions without Home Assistant imports."""

from .const import TOPIC_VERSION


def state_topic(base: str, device_id: str) -> str:
    """Return the retained state topic of a device; the command topic is the same string (D-01)."""
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/state"


def availability_topic(base: str, instance_id: str) -> str:
    """Return the availability topic of this instance."""
    return f"{base}/{TOPIC_VERSION}/instances/{instance_id}/availability"


def discovery_topic(prefix: str, device_id: str) -> str:
    """Return the device-based MQTT Discovery config topic."""
    return f"{prefix}/device/{device_id}/config"
