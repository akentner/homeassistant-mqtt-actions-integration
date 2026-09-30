"""
A fake MQTT broker for multi-instance tests: real retain semantics, several real Home Assistant instances.

PHACC's mocked paho client loops every publish straight back into the same hass with the publish's own retain flag and
keeps no retained store. A real broker replays retained messages with retain True, forwards live messages with retain
False (also an empty retained clear) and keeps one retained message per topic. Phase 3 depends on those semantics
(tombstones arrive live and empty, echoes arrive live), so this module models them; they are pinned against Mosquitto by
tests/broker/test_retain_semantics.py.

`FakeGateway` replaces the gateway, not the MQTT component, so the managers under test are unmodified. Core MQTT
discovery is not simulated: assert on the retained discovery topics instead.
"""

import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant import loader
from paho.mqtt.client import topic_matches_sub
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_test_home_assistant

from custom_components.mqtt_actions.const import (
    CONF_BASE_TOPIC,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    STORE_KEY,
)
from custom_components.mqtt_actions.manager import Manager
from custom_components.mqtt_actions.mqtt_gateway import IncomingMessage, MqttGateway

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant


@dataclass(eq=False)
class Subscription:
    """One subscription of one gateway; identity is what unsubscribing removes."""

    gateway: FakeGateway
    pattern: str
    callback: Callable[[IncomingMessage], None]


class FakeBroker:
    """Retained store plus subscriptions; a message is delivered on the event loop of the subscribing gateway."""

    def __init__(self) -> None:
        """Initialize an empty broker."""
        self.retained: dict[str, str] = {}
        self.subscriptions: list[Subscription] = []

    def publish(self, topic: str, payload: str, *, retain: bool) -> None:
        """Store or delete a retained message, then forward it live (retain False) to every matching subscription."""
        if retain:
            if payload == "":
                self.retained.pop(topic, None)
            else:
                self.retained[topic] = payload
        for subscription in list(self.subscriptions):
            if topic_matches_sub(subscription.pattern, topic):
                self._deliver(subscription, IncomingMessage(payload=payload, retain=False, topic=topic))

    def replay(self, subscription: Subscription) -> None:
        """Deliver the retained messages matching one subscription, flagged as retained."""
        for topic, payload in list(self.retained.items()):
            if topic_matches_sub(subscription.pattern, topic):
                self._deliver(subscription, IncomingMessage(payload=payload, retain=True, topic=topic))

    def wipe_retained(self) -> None:
        """Forget every retained message, as a broker that lost its persistence."""
        self.retained.clear()

    def _deliver(self, subscription: Subscription, message: IncomingMessage) -> None:
        """Schedule the delivery; a subscription that ended meanwhile no longer receives it."""

        def _call() -> None:
            if subscription in self.subscriptions:
                subscription.callback(message)

        subscription.gateway.hass.loop.call_soon(_call)


class FakeGateway(MqttGateway):
    """The gateway of one instance: same interface as MqttGateway, backed by a FakeBroker."""

    def __init__(self, broker: FakeBroker, hass: HomeAssistant) -> None:
        """Initialize the gateway for one hass."""
        super().__init__(hass)
        self.broker = broker
        self.hass = hass
        # (topic, payload, retain) in publish order
        self.published: list[tuple[str, str, bool]] = []
        self._status_callbacks: list[Callable[[bool], None]] = []

    async def async_wait_ready(self) -> bool:
        """Report the client as ready."""
        return True

    async def async_subscribe(
        self,
        topic: str,
        message_callback: Callable[[IncomingMessage], None],
        qos: int = 1,
    ) -> CALLBACK_TYPE:
        """Subscribe, receive the matching retained messages right away and return the unsubscribe callback."""
        subscription = Subscription(self, topic, message_callback)
        self.broker.subscriptions.append(subscription)
        self.broker.replay(subscription)

        def _unsubscribe() -> None:
            if subscription in self.broker.subscriptions:
                self.broker.subscriptions.remove(subscription)

        return _unsubscribe

    def async_subscribe_connection_status(self, connection_callback: Callable[[bool], None]) -> CALLBACK_TYPE:
        """Register a connection status callback and return the unsubscribe."""
        self._status_callbacks.append(connection_callback)

        def _unsubscribe() -> None:
            if connection_callback in self._status_callbacks:
                self._status_callbacks.remove(connection_callback)

        return _unsubscribe

    async def async_publish(self, topic: str, payload: str, *, retain: bool, qos: int = 1) -> None:
        """Record the publish and hand it to the broker."""
        self.published.append((topic, payload, retain))
        self.broker.publish(topic, payload, retain=retain)

    def discovery_prefix(self) -> str:
        """Return the default discovery prefix."""
        return "homeassistant"

    def discovery_enabled(self) -> bool:
        """Report discovery as enabled."""
        return True

    def mqtt_entry_id(self) -> str | None:
        """Return no MQTT entry: the fake has no registry entries of core MQTT."""
        return None

    def disconnect(self) -> None:
        """Tell every registered callback that the connection was lost."""
        for connection_callback in list(self._status_callbacks):
            connection_callback(False)

    def reconnect(self) -> None:
        """Tell every registered callback the connection is back and replay the retained messages of this gateway."""
        for connection_callback in list(self._status_callbacks):
            connection_callback(True)
        for subscription in [item for item in self.broker.subscriptions if item.gateway is self]:
            self.broker.replay(subscription)


@dataclass
class Instance:
    """One Home Assistant instance with its hub entry, its unmodified Manager and its gateway."""

    hass: HomeAssistant
    entry: MockConfigEntry
    manager: Manager
    gateway: FakeGateway
    name: str
    extra: dict[str, Any] = field(default_factory=dict)


class InstanceFactory:
    """Creates started instances against one broker and closes all of them, hass objects included."""

    def __init__(self, broker: FakeBroker) -> None:
        """Initialize the factory."""
        self._broker = broker
        self._stack = AsyncExitStack()
        self.instances: list[Instance] = []

    async def __call__(
        self,
        name: str,
        *,
        hass: HomeAssistant | None = None,
        subentries: Sequence[ConfigSubentryData] = (),
        data: dict[str, Any] | None = None,
    ) -> Instance:
        """
        Create and start an instance.

        Without `hass` a second Home Assistant is created, which gives the instance its own service registry, issue
        registry and entity registry. The first instance of a test may use the test's own hass.
        """
        if hass is None:
            hass = await self._stack.enter_async_context(async_test_home_assistant())
            # The context manager only restores the time zone; a hass that is not stopped stays in the plugin's
            # INSTANCES list and aborts the test run at the second test that creates one. Runs after the managers stop.
            self._stack.push_async_callback(partial(hass.async_stop, force=True))
            # Lets the custom integration load, as the enable_custom_integrations fixture does for the test's hass
            hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=name,
            data=data
            or {
                CONF_BASE_TOPIC: DEFAULT_BASE_TOPIC,
                CONF_INSTANCE_NAME: name,
                CONF_INSTANCE_ID: str(uuid.uuid4()),
            },
            subentries_data=list(subentries),
        )
        entry.add_to_hass(hass)
        gateway = FakeGateway(self._broker, hass)
        manager = Manager(hass, entry, gateway=gateway, store_key=f"{STORE_KEY}.{name}")
        entry.runtime_data = manager
        await manager.async_start()
        self._stack.push_async_callback(manager.async_stop)
        instance = Instance(hass=hass, entry=entry, manager=manager, gateway=gateway, name=name)
        self.instances.append(instance)
        return instance

    async def async_close(self) -> None:
        """Stop every manager and every extra hass, last created first."""
        await self._stack.aclose()
