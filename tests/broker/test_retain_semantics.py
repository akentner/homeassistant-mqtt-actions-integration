"""
Pin the retain-flag semantics the baseline strategy rests on, against a real Mosquitto broker.

A retained message is delivered with retain=True when it is replayed on subscribe, and with retain=False when it is
forwarded live to an established subscription (MQTT-3.3.1-9). The mocked client of the Home Assistant test harness
cannot prove this, and the whole "retained means baseline, live means edge" decision (STA-04) depends on it.
"""

import queue
import threading
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.broker

TIMEOUT = 5.0
QUIET_PERIOD = 0.5
TOPIC = "mqtt_actions/v1/devices/test-device/state"

type Received = tuple[str, str, bool]


class RecordingClient:
    """A paho client that records (topic, payload, retain) of every message it receives."""

    def __init__(self, port: int, client_id: str) -> None:
        self.messages: queue.Queue[Received] = queue.Queue()
        connected = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.client.on_connect = lambda *_args: connected.set()
        self.client.on_message = lambda _client, _userdata, msg: self.messages.put(
            (msg.topic, msg.payload.decode(), bool(msg.retain))
        )
        self.client.connect("127.0.0.1", port)
        self.client.loop_start()
        assert connected.wait(TIMEOUT), "client did not connect to the broker"

    def publish(self, payload: str, *, retain: bool = True) -> None:
        """Publish with qos 1 and wait until the broker acknowledged it."""
        info = self.client.publish(TOPIC, payload, qos=1, retain=retain)
        info.wait_for_publish(TIMEOUT)
        assert info.is_published()

    def subscribe(self) -> None:
        """Subscribe with qos 1."""
        self.client.subscribe(TOPIC, qos=1)

    def unsubscribe(self) -> None:
        """Unsubscribe from the topic."""
        self.client.unsubscribe(TOPIC)

    def next_message(self, timeout: float = TIMEOUT) -> Received:
        """Return the next received message or fail the test when none arrives in time."""
        try:
            return self.messages.get(timeout=timeout)
        except queue.Empty:
            pytest.fail(f"no message received within {timeout} seconds")

    def assert_silent(self, timeout: float = QUIET_PERIOD) -> None:
        """Fail when any message arrives within the quiet period."""
        with pytest.raises(queue.Empty):
            self.messages.get(timeout=timeout)

    def close(self) -> None:
        """Disconnect and stop the network thread."""
        self.client.disconnect()
        self.client.loop_stop()


@pytest.fixture
def clients(mosquitto_port: int) -> Iterator[list[RecordingClient]]:
    """Track every client created through the factory below and close them at teardown."""
    created: list[RecordingClient] = []
    yield created
    for client in created:
        client.close()


def _new_client(clients: list[RecordingClient], port: int, name: str) -> RecordingClient:
    client = RecordingClient(port, name)
    clients.append(client)
    return client


def test_replay_on_subscribe_has_retain_true(mosquitto_port: int, clients: list[RecordingClient]) -> None:
    """(a) A retained ON published before subscribing arrives with retain=True."""
    publisher = _new_client(clients, mosquitto_port, "publisher")
    publisher.publish("ON")

    subscriber = _new_client(clients, mosquitto_port, "subscriber")
    subscriber.subscribe()

    assert subscriber.next_message() == (TOPIC, "ON", True)


def test_live_forward_has_retain_false(mosquitto_port: int, clients: list[RecordingClient]) -> None:
    """(b) A later publish arrives at the established subscriber with retain=False, even if published retained."""
    publisher = _new_client(clients, mosquitto_port, "publisher")
    publisher.publish("ON")
    subscriber = _new_client(clients, mosquitto_port, "subscriber")
    subscriber.subscribe()
    assert subscriber.next_message() == (TOPIC, "ON", True)

    publisher.publish("OFF")

    assert subscriber.next_message() == (TOPIC, "OFF", False)


def test_resubscribe_replays_last_value_with_retain_true(mosquitto_port: int, clients: list[RecordingClient]) -> None:
    """(c) Unsubscribing and subscribing again replays the last retained value with retain=True."""
    publisher = _new_client(clients, mosquitto_port, "publisher")
    publisher.publish("ON")
    subscriber = _new_client(clients, mosquitto_port, "subscriber")
    subscriber.subscribe()
    assert subscriber.next_message() == (TOPIC, "ON", True)
    publisher.publish("OFF")
    assert subscriber.next_message() == (TOPIC, "OFF", False)

    subscriber.unsubscribe()
    subscriber.subscribe()

    assert subscriber.next_message() == (TOPIC, "OFF", True)


def test_retained_clear_is_a_live_empty_message(mosquitto_port: int, clients: list[RecordingClient]) -> None:
    """(d) An empty retained publish reaches the established subscriber as retain=False; a new one gets nothing."""
    publisher = _new_client(clients, mosquitto_port, "publisher")
    publisher.publish("ON")
    subscriber = _new_client(clients, mosquitto_port, "subscriber")
    subscriber.subscribe()
    assert subscriber.next_message() == (TOPIC, "ON", True)

    publisher.publish("")

    assert subscriber.next_message() == (TOPIC, "", False)
    newcomer = _new_client(clients, mosquitto_port, "newcomer")
    newcomer.subscribe()
    newcomer.assert_silent()
