"""MQTT Discovery payloads and their publisher."""

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.json import json_dumps

from .const import DOMAIN, PAYLOAD_OFF, PAYLOAD_ON
from .topics import availability_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from .mqtt_gateway import MqttGateway


class AvailabilityState(StrEnum):
    """Payload of the retained instance availability topic; the empty payload removes the topic."""

    ONLINE = "online"
    OFFLINE = "offline"
    CLEARED = ""


def build_switch_discovery(
    *,
    base_topic: str,
    device_id: str,
    instance_id: str,
    name: str,
    sw_version: str,
) -> dict[str, Any]:
    """Build the device-based discovery payload of a switch (D-01, D-03)."""
    topic = state_topic(base_topic, device_id)
    return {
        "device": {"identifiers": [f"{DOMAIN}_{device_id}"], "name": name},
        "origin": {"name": "MQTT Actions", "sw_version": sw_version},
        "components": {
            "switch": {
                "platform": "switch",
                "unique_id": device_id,
                "name": None,
                # Command topic equals state topic: the state subscription is the only trigger source
                "state_topic": topic,
                "command_topic": topic,
                "retain": True,
                "qos": 1,
                "payload_on": PAYLOAD_ON,
                "payload_off": PAYLOAD_OFF,
                # Core compares the payload exactly; the tracker is case-insensitive, so the entity must be too
                "value_template": "{{ value | upper }}",
            }
        },
        "availability": [{"topic": availability_topic(base_topic, instance_id)}],
    }


class DiscoveryPublisher:
    """Publishes discovery and availability messages through the gateway."""

    def __init__(self, gateway: MqttGateway, base_topic: str, sw_version: str) -> None:
        """Initialize the publisher."""
        self._gateway = gateway
        self._base_topic = base_topic
        self._sw_version = sw_version

    async def async_publish_device(self, *, device_id: str, name: str, instance_id: str) -> None:
        """Publish the retained discovery message of a switch device."""
        payload = build_switch_discovery(
            base_topic=self._base_topic,
            device_id=device_id,
            instance_id=instance_id,
            name=name,
            sw_version=self._sw_version,
        )
        await self._gateway.async_publish(
            discovery_topic(self._gateway.discovery_prefix(), device_id),
            json_dumps(payload),
            retain=True,
        )

    async def async_clear_device(self, device_id: str) -> None:
        """Remove the device: an empty retained discovery payload makes core MQTT drop the entity (DSC-02)."""
        await self._gateway.async_publish(discovery_topic(self._gateway.discovery_prefix(), device_id), "", retain=True)

    async def async_clear_state(self, device_id: str) -> None:
        """Clear the retained state of a deleted device so no stale ON or OFF stays on the broker."""
        await self._gateway.async_publish(state_topic(self._base_topic, device_id), "", retain=True)

    async def async_publish_availability(self, instance_id: str, state: AvailabilityState) -> None:
        """Publish the retained availability of this instance: online, offline or cleared."""
        await self._gateway.async_publish(availability_topic(self._base_topic, instance_id), str(state), retain=True)
