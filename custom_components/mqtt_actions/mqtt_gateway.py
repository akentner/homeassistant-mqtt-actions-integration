"""Gateway to the built-in MQTT integration. The only module that imports it."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

# The highest MQTT qos level
MAX_QOS = 2


async def async_attempt(action: Callable[[], Awaitable[None]], description: str) -> bool:
    """Run one MQTT cleanup step; an unavailable MQTT client is logged and never raised (T-01-14)."""
    try:
        await action()
    except HomeAssistantError as err:
        LOGGER.warning("MQTT could not %s: %s", description, err)
        return False
    return True


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    """A message received on a subscribed topic."""

    payload: str
    retain: bool
    # Empty for a message built without a topic; wildcard subscriptions identify the device or instance by it
    topic: str = ""


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
            message_callback(IncomingMessage(payload=payload, retain=msg.retain, topic=msg.topic))

        return await mqtt.async_subscribe(self._hass, topic, _forward, qos)

    def async_subscribe_connection_status(self, connection_callback: Callable[[bool], None]) -> CALLBACK_TYPE:
        """Call the callback with True after every (re)connect and False after a disconnect; returns the unsubscribe."""

        # Must be a @callback for the same reason as in async_subscribe
        @callback
        def _forward(connected: bool) -> None:  # noqa: FBT001
            connection_callback(connected)

        return mqtt.async_subscribe_connection_status(self._hass, _forward)

    def async_on_subscribed(self, topic: str, qos: int, on_done: Callable[[], None]) -> CALLBACK_TYPE:
        """
        Call on_done once the broker acknowledged the subscription of topic at qos, and again after every resubscribe.

        Core subscribes a filter once, at the highest qos any subscriber asked for, and signals that qos. Another
        subscriber to the same filter, such as core's discovery at a discovery qos of 2, can raise it above ours, so
        every qos from `qos` up counts as done (WR-01). When core already holds the subscription, on_done may be called
        once per watched qos right away; it must be idempotent. Returns the stop callback.
        """

        # Must be a @callback for the same reason as in async_subscribe
        @callback
        def _forward() -> None:
            on_done()

        try:
            # Core reads its runtime data before it registers anything, so a missing MQTT integration raises on the
            # first level and no watch is left behind
            stops = [
                mqtt.async_on_subscribe_done(self._hass, topic, level, _forward) for level in range(qos, MAX_QOS + 1)
            ]
        except KeyError:
            # The MQTT integration is not loaded: without a settle signal an unseen topic is never taken as empty
            return lambda: None

        @callback
        def _stop() -> None:
            for stop in stops:
                stop()

        return _stop

    async def async_publish(self, topic: str, payload: str, *, retain: bool, qos: int = 1) -> None:
        """Publish a message with explicit qos and retain values; raises HomeAssistantError when MQTT is unavailable."""
        try:
            await mqtt.async_publish(self._hass, topic, payload, int(qos), bool(retain))
        except KeyError as err:
            # An MQTT entry that exists but is not loaded (broker down at start) has no runtime data yet
            msg = "The MQTT integration is not loaded"
            raise HomeAssistantError(msg) from err

    def _mqtt_conf(self) -> dict[str, Any]:
        """Return the MQTT entry configuration the way core merges it: options over data (D-04)."""
        entries = self._hass.config_entries.async_entries(mqtt.DOMAIN)
        if not entries:
            return {}
        return dict(entries[0].data | entries[0].options)

    def mqtt_entry_id(self) -> str | None:
        """Return the entry id of the first MQTT config entry, or None when there is none."""
        entries = self._hass.config_entries.async_entries(mqtt.DOMAIN)
        return entries[0].entry_id if entries else None

    def discovery_prefix(self) -> str:
        """Return the discovery prefix configured in the MQTT integration (D-04)."""
        return str(self._mqtt_conf().get(mqtt.CONF_DISCOVERY_PREFIX, mqtt.DEFAULT_PREFIX))

    def discovery_enabled(self) -> bool:
        """Return whether the MQTT integration processes discovery messages; without it no entity ever appears."""
        return bool(self._mqtt_conf().get(mqtt.CONF_DISCOVERY, mqtt.DEFAULT_DISCOVERY))
