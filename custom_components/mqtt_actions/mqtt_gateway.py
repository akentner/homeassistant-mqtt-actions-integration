"""Gateway to the built-in MQTT integration. The only module that imports it."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components import mqtt
from homeassistant.core import callback

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import CALLBACK_TYPE, HomeAssistant


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    """A message received on a subscribed topic."""

    payload: str
    retain: bool


class MqttGateway:
    """Thin adapter over the MQTT integration API; the seam a fake broker replaces in tests."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the gateway."""
        self._hass = hass

    async def async_wait_ready(self) -> bool:
        """Wait for the MQTT client; False means it is not available."""
        return await mqtt.async_wait_for_mqtt_client(self._hass)

    async def async_subscribe(
        self,
        topic: str,
        message_callback: Callable[[IncomingMessage], None],
        qos: int = 1,
    ) -> CALLBACK_TYPE:
        """Subscribe to a topic and return the unsubscribe callback."""

        # Must be a @callback: a lambda or plain function would be run as an executor job and crash on the first message
        @callback
        def _forward(msg: mqtt.ReceiveMessage) -> None:
            payload = msg.payload if isinstance(msg.payload, str) else msg.payload.decode(errors="replace")
            message_callback(IncomingMessage(payload=payload, retain=msg.retain))

        return await mqtt.async_subscribe(self._hass, topic, _forward, qos)

    async def async_publish(self, topic: str, payload: str, *, retain: bool, qos: int = 1) -> None:
        """Publish a message with explicit qos and retain values."""
        await mqtt.async_publish(self._hass, topic, payload, int(qos), bool(retain))

    def discovery_prefix(self) -> str:
        """Return the discovery prefix configured in the MQTT integration (D-04)."""
        entries = self._hass.config_entries.async_entries(mqtt.DOMAIN)
        if not entries:
            return mqtt.DEFAULT_PREFIX
        conf = dict(entries[0].data | entries[0].options)
        return str(conf.get(mqtt.CONF_DISCOVERY_PREFIX, mqtt.DEFAULT_PREFIX))
