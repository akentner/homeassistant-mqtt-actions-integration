"""The Wave 0 seams and the fake broker tier: IncomingMessage.topic, Manager injection and two real instances."""

import json
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import STORE_KEY
from custom_components.mqtt_actions.manager import Manager
from custom_components.mqtt_actions.mqtt_gateway import IncomingMessage, MqttGateway
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from tests.fake_broker import FakeBroker, FakeGateway

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BASE = "mqtt_actions"


# --- seams (mqtt_mock tier) ---------------------------------------------------------------------------------------


async def test_incoming_message_has_topic(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """The topic defaults to empty and the gateway fills it from the received message."""
    assert IncomingMessage(payload="p", retain=False).topic == ""
    received: list[IncomingMessage] = []

    await MqttGateway(hass).async_subscribe("a/+", received.append)
    async_fire_mqtt_message(hass, "a/b", "p")
    await hass.async_block_till_done()

    assert [(message.topic, message.payload, message.retain) for message in received] == [("a/b", "p", False)]


async def test_manager_accepts_gateway_and_store_key(
    hass: HomeAssistant, mqtt_mock: Any, fake_broker: FakeBroker, make_hub_entry: Callable
) -> None:
    """A gateway and a store key can be injected; without them the production defaults apply."""
    entry = make_hub_entry()
    fake = FakeGateway(fake_broker, hass)

    injected = Manager(hass, entry, gateway=fake, store_key="x.state")
    default = Manager(hass, entry)

    assert injected.gateway is fake
    assert injected._store.key == "x.state"
    assert isinstance(default.gateway, MqttGateway)
    assert not isinstance(default.gateway, FakeGateway)
    assert default._store.key == STORE_KEY


# --- the fake broker ----------------------------------------------------------------------------------------------


def _collector() -> tuple[list[IncomingMessage], Callable[[IncomingMessage], None]]:
    received: list[IncomingMessage] = []
    return received, received.append


async def test_broker_retains_and_replays_with_retain_true(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """A retained publish is kept; a later subscriber gets it once, flagged as retained."""
    publisher, subscriber = FakeGateway(fake_broker, hass), FakeGateway(fake_broker, hass)
    await publisher.async_publish("a/b", "p", retain=True)
    received, callback = _collector()

    await subscriber.async_subscribe("a/b", callback)
    await hass.async_block_till_done()

    assert received == [IncomingMessage(payload="p", retain=True, topic="a/b")]


async def test_broker_forwards_live_with_retain_false(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """An existing subscriber gets a live publish with retain False, also when the publish is retained."""
    publisher, subscriber = FakeGateway(fake_broker, hass), FakeGateway(fake_broker, hass)
    received, callback = _collector()
    await subscriber.async_subscribe("a/b", callback)

    await publisher.async_publish("a/b", "one", retain=True)
    await publisher.async_publish("a/b", "two", retain=False)
    await hass.async_block_till_done()

    assert received == [
        IncomingMessage(payload="one", retain=False, topic="a/b"),
        IncomingMessage(payload="two", retain=False, topic="a/b"),
    ]


async def test_broker_matches_wildcards(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """Plus and hash subscriptions receive the matching topics and only those."""
    gateway = FakeGateway(fake_broker, hass)
    plus, plus_callback = _collector()
    multi, multi_callback = _collector()
    exact, exact_callback = _collector()
    await gateway.async_subscribe("a/+/c", plus_callback)
    await gateway.async_subscribe("a/#", multi_callback)
    await gateway.async_subscribe("x/y", exact_callback)

    for topic in ("a/b/c", "a/b/d", "a/b", "x/y", "x/z", "other"):
        await gateway.async_publish(topic, "p", retain=False)
    await hass.async_block_till_done()

    assert [message.topic for message in plus] == ["a/b/c"]
    assert [message.topic for message in multi] == ["a/b/c", "a/b/d", "a/b"]
    assert [message.topic for message in exact] == ["x/y"]


async def test_empty_retained_payload_deletes_and_is_delivered_live(
    hass: HomeAssistant, fake_broker: FakeBroker
) -> None:
    """An empty retained publish removes the stored message and reaches subscribers live as an empty payload."""
    gateway = FakeGateway(fake_broker, hass)
    await gateway.async_publish("a/b", "p", retain=True)
    received, callback = _collector()
    await gateway.async_subscribe("a/b", callback)
    await hass.async_block_till_done()
    received.clear()

    await gateway.async_publish("a/b", "", retain=True)
    await hass.async_block_till_done()

    assert received == [IncomingMessage(payload="", retain=False, topic="a/b")]
    assert fake_broker.retained == {}
    later, later_callback = _collector()
    await FakeGateway(fake_broker, hass).async_subscribe("a/b", later_callback)
    await hass.async_block_till_done()
    assert later == []


async def test_non_retained_publish_is_not_stored(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """Nothing is replayed for a publish that was not retained."""
    gateway = FakeGateway(fake_broker, hass)
    await gateway.async_publish("a/b", "p", retain=False)
    received, callback = _collector()

    await gateway.async_subscribe("a/b", callback)
    await hass.async_block_till_done()

    assert received == []
    assert fake_broker.retained == {}


async def test_unsubscribe_stops_delivery(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """After the unsubscribe callback ran, no message arrives."""
    gateway = FakeGateway(fake_broker, hass)
    received, callback = _collector()
    unsubscribe = await gateway.async_subscribe("a/b", callback)

    await gateway.async_publish("a/b", "before", retain=False)
    await hass.async_block_till_done()
    unsubscribe()
    await gateway.async_publish("a/b", "after", retain=False)
    await hass.async_block_till_done()

    assert [message.payload for message in received] == ["before"]


async def test_disconnect_and_reconnect_fire_status_and_replay(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """A disconnect reports False, a reconnect reports True and replays the retained messages of its subscriptions."""
    gateway = FakeGateway(fake_broker, hass)
    statuses: list[bool] = []
    gateway.async_subscribe_connection_status(statuses.append)
    received, callback = _collector()
    await gateway.async_subscribe("a/+", callback)
    await FakeGateway(fake_broker, hass).async_publish("a/b", "p", retain=True)
    await FakeGateway(fake_broker, hass).async_publish("other/b", "q", retain=True)
    await hass.async_block_till_done()
    received.clear()

    gateway.disconnect()
    assert statuses == [False]
    gateway.reconnect()
    await hass.async_block_till_done()

    assert statuses == [False, True]
    assert received == [IncomingMessage(payload="p", retain=True, topic="a/b")]


async def test_wipe_retained_empties_the_store(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """A wiped broker forgets every retained message."""
    await FakeGateway(fake_broker, hass).async_publish("a/b", "p", retain=True)
    assert fake_broker.retained == {"a/b": "p"}

    fake_broker.wipe_retained()

    assert fake_broker.retained == {}


async def test_messages_carry_topic_and_gateway_records_publishes(hass: HomeAssistant, fake_broker: FakeBroker) -> None:
    """Every delivered message has its topic and the gateway lists its publishes in order."""
    gateway = FakeGateway(fake_broker, hass)
    received, callback = _collector()
    await gateway.async_subscribe("#", callback)

    await gateway.async_publish("a/1", "x", retain=True)
    await gateway.async_publish("a/2", "y", retain=False)
    await hass.async_block_till_done()

    assert gateway.published == [("a/1", "x", True), ("a/2", "y", False)]
    assert [message.topic for message in received] == ["a/1", "a/2"]


# --- two real instances -------------------------------------------------------------------------------------------


async def test_two_instances_share_one_broker(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """Two hass objects run two unmodified Managers against one broker; only the owner's service runs."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"]["device_id"]
    first_calls = async_mock_service(hass, "test", "on")
    first = await make_instance("first", hass=hass, subentries=[sub])
    second = await make_instance("second")
    second_calls = async_mock_service(second.hass, "test", "on")
    assert first.hass is not second.hass
    await first.hass.async_block_till_done()

    instance_id = first.entry.data["instance_id"]
    assert set(fake_broker.retained) >= {
        config_topic(BASE, device_id),
        discovery_topic("homeassistant", device_id),
        availability_topic(BASE, instance_id),
    }
    assert json.loads(fake_broker.retained[config_topic(BASE, device_id)])["owner"] == instance_id
    assert fake_broker.retained[availability_topic(BASE, instance_id)] == "online"

    seen, callback = _collector()
    await second.gateway.async_subscribe(f"{BASE}/v1/devices/+/config", callback)
    await second.hass.async_block_till_done()
    assert [message.topic for message in seen] == [config_topic(BASE, device_id)]
    assert seen[0].retain is True

    await second.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await first.hass.async_block_till_done(wait_background_tasks=True)
    await second.hass.async_block_till_done(wait_background_tasks=True)

    assert len(first_calls) == 1
    assert len(second_calls) == 0
