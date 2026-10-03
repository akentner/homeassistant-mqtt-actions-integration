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
from unittest.mock import patch

from homeassistant import loader
from homeassistant.config_entries import ConfigEntryState
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
        # (topic, payload, retain) in publish order, and the QoS of each publish at the same index
        self.published: list[tuple[str, str, bool]] = []
        self.qos: list[int] = []
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
        self.qos.append(qos)
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
    """
    One Home Assistant instance with its hub entry, its Manager and its gateway.

    A bare instance runs a Manager built by hand. A `real_setup` instance runs the real setup of the integration, so its
    platforms exist and a reload of the entry builds the next manager on the same gateway.
    """

    hass: HomeAssistant
    entry: MockConfigEntry
    gateway: FakeGateway
    name: str
    store_key: str = STORE_KEY
    extra: dict[str, Any] = field(default_factory=dict)
    real_setup: bool = False

    @property
    def manager(self) -> Manager:
        """Return the manager that runs now: the runtime data of the entry, which a reload replaces."""
        return self.entry.runtime_data

    async def stop(self) -> None:
        """Stop the instance unless it already stopped; the broker keeps what was published."""
        if self.real_setup:
            if self.entry.state is ConfigEntryState.LOADED:
                await self.hass.config_entries.async_unload(self.entry.entry_id)
                await self.hass.async_block_till_done(wait_background_tasks=True)
        elif self.manager.running:
            await self.manager.async_stop()

    async def start(self) -> None:
        """Start again on the same hass, entry, gateway and store key, as after a restart of Home Assistant."""
        if self.real_setup:
            await self.hass.config_entries.async_setup(self.entry.entry_id)
            await self.hass.async_block_till_done(wait_background_tasks=True)
            return
        manager = Manager(self.hass, self.entry, gateway=self.gateway, store_key=self.store_key)
        self.entry.runtime_data = manager
        await manager.async_start()

    async def restart(self) -> None:
        """Stop the manager and start a new one; the Store, the entry and the gateway stay."""
        await self.stop()
        await self.start()


class InstanceFactory:
    """Creates started instances against one broker and closes all of them, hass objects included."""

    def __init__(self, broker: FakeBroker) -> None:
        """Initialize the factory."""
        self._broker = broker
        self._stack = AsyncExitStack()
        self.instances: list[Instance] = []
        # The gateway and the store key of each hass that runs the real setup; the patched constructors read them
        self._real: dict[HomeAssistant, tuple[FakeGateway, str]] = {}

    async def __call__(
        self,
        name: str,
        *,
        hass: HomeAssistant | None = None,
        subentries: Sequence[ConfigSubentryData] = (),
        data: dict[str, Any] | None = None,
        real_setup: bool = False,
    ) -> Instance:
        """
        Create and start an instance.

        Without `hass` a second Home Assistant is created, which gives the instance its own service registry, issue
        registry and entity registry. The first instance of a test may use the test's own hass. With `real_setup` the
        entry is set up through Home Assistant, so the platforms are forwarded and the entry can be reloaded; the
        default starts a bare Manager and changes nothing for the tests that rely on it.
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
        store_key = f"{STORE_KEY}.{name}"
        instance = Instance(
            hass=hass, entry=entry, gateway=gateway, name=name, store_key=store_key, real_setup=real_setup
        )
        if real_setup:
            self._patch_gateways()
            self._real[hass] = (gateway, store_key)
            # The manifest depends on mqtt, whose client the fake gateway replaces; core MQTT itself is never set up
            hass.config.components.add("mqtt")
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done(wait_background_tasks=True)
        else:
            manager = Manager(hass, entry, gateway=gateway, store_key=store_key)
            entry.runtime_data = manager
            await manager.async_start()
        # Stops whichever manager the instance runs at the end, so a restart inside a test is not stopped twice
        self._stack.push_async_callback(instance.stop)
        self.instances.append(instance)
        return instance

    def _patch_gateways(self) -> None:
        """
        Make the real setup of every hass use its fake gateway and its own store key; done once, undone at the close.

        The patches replace the constructors the setup and the manager call, and the dispatch is by the hass they get,
        so a reload builds its manager on the same gateway and the same Store. They are entered first, so they end last.
        """
        if self._real:
            return

        def _gateway(hass: HomeAssistant) -> FakeGateway:
            return self._real[hass][0]

        def _manager(hass: HomeAssistant, entry: MockConfigEntry) -> Manager:
            gateway, store_key = self._real[hass]
            return Manager(hass, entry, gateway=gateway, store_key=store_key)

        for target, replacement in (
            ("custom_components.mqtt_actions.MqttGateway", _gateway),
            ("custom_components.mqtt_actions.manager.MqttGateway", _gateway),
            ("custom_components.mqtt_actions.Manager", _manager),
        ):
            self._stack.enter_context(patch(target, replacement))

    async def async_close(self) -> None:
        """Stop every manager and every extra hass, last created first."""
        await self._stack.aclose()
