"""
Pin the documented broker ACL against a real Mosquitto (D-07, TRU-04).

The ACL text is not written here: it is read from the first fenced `acl` block of docs/broker-acl.md, so the example
operators copy is the very text the broker enforces below. A denied publish is never assumed to fail visibly (A12):
every denial is asserted on what a reader receives, including a retained read-back.
"""

import queue
import re
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

pytestmark = pytest.mark.broker

ROOT = Path(__file__).resolve().parent.parent.parent
ACL_DOCUMENT = ROOT / "docs" / "broker-acl.md"
ACL_BLOCK = re.compile(r"^```acl\n(.*?)^```$", re.DOTALL | re.MULTILINE)
INSTANCE_MARKERS = {"<instance-id-one>": "ha_one", "<instance-id-two>": "ha_two"}

TIMEOUT = 5.0
QUIET_PERIOD = 0.5
PUBLISH_TIMEOUT = 1.0
BASE = "mqtt_actions"
PREFIX = "homeassistant"
PASSWORDS = {"ha_one": "pw-one", "ha_two": "pw-two", "bridge": "pw-bridge"}

type Received = tuple[str, str, bool]


def _documented_acl() -> str:
    """Return the ACL text of the document; fail when the document or its acl block is missing."""
    assert ACL_DOCUMENT.is_file(), "docs/broker-acl.md does not exist"
    match = ACL_BLOCK.search(ACL_DOCUMENT.read_text(encoding="utf-8"))
    assert match is not None, "docs/broker-acl.md has no fenced block with the info string acl"
    return match.group(1)


class AclClient:
    """An authenticated paho client that records (topic, payload, retain) of every message it receives."""

    def __init__(self, port: int, user: str) -> None:
        self.user = user
        self.messages: queue.Queue[Received] = queue.Queue()
        self._connected = threading.Event()
        self._subscribed = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{user}-{uuid.uuid4().hex[:8]}")
        self.client.username_pw_set(user, PASSWORDS[user])
        self.client.on_connect = lambda *_args: self._connected.set()
        self.client.on_subscribe = lambda *_args: self._subscribed.set()
        self.client.on_message = lambda _client, _userdata, msg: self.messages.put(
            (msg.topic, msg.payload.decode(), bool(msg.retain))
        )
        self.client.connect("127.0.0.1", port)
        self.client.loop_start()
        assert self._connected.wait(TIMEOUT), f"{user} did not connect to the broker"

    def publish(self, topic: str, payload: str, *, retain: bool = True) -> None:
        """Publish with qos 1; a missing acknowledgement is tolerated because a denial may not be reported (A12)."""
        info = self.client.publish(topic, payload, qos=1, retain=retain)
        try:
            info.wait_for_publish(PUBLISH_TIMEOUT)
        except RuntimeError, ValueError:
            return

    def subscribe(self, *topics: str) -> None:
        """Subscribe with qos 1 and wait until the broker answered, granted or not."""
        for topic in topics:
            self._subscribed.clear()
            self.client.subscribe(topic, qos=1)
            assert self._subscribed.wait(TIMEOUT), f"no subscribe answer for {topic}"

    def collect(self, timeout: float = QUIET_PERIOD) -> set[Received]:
        """Return everything that arrives until the line has been quiet for the timeout."""
        received: set[Received] = set()
        while True:
            try:
                received.add(self.messages.get(timeout=timeout))
            except queue.Empty:
                return received

    def close(self) -> None:
        """Disconnect and stop the network thread."""
        self.client.disconnect()
        self.client.loop_stop()


@pytest.fixture
def instance_ids() -> dict[str, str]:
    """Return generated instance ids by user name, the values the ACL markers are replaced with."""
    return {user: str(uuid.uuid4()) for user in INSTANCE_MARKERS.values()}


@pytest.fixture
def acl_port(start_acl_broker: Callable[[str, dict[str, str]], int], instance_ids: dict[str, str]) -> int:
    """Start a Mosquitto that enforces exactly the documented ACL with the instance id markers substituted."""
    text = _documented_acl()
    for marker, user in INSTANCE_MARKERS.items():
        assert marker in text, f"the documented ACL has no {marker} marker"
        text = text.replace(marker, instance_ids[user])
    return start_acl_broker(text, PASSWORDS)


@pytest.fixture
def clients(acl_port: int) -> Iterator[Callable[[str], AclClient]]:
    """Return a factory for authenticated clients and close every client it created at teardown."""
    created: list[AclClient] = []

    def _new(user: str) -> AclClient:
        client = AclClient(acl_port, user)
        created.append(client)
        return client

    yield _new
    for client in created:
        client.close()


def _config(device: str = "dev-1") -> str:
    return f"{BASE}/v1/devices/{device}/config"


def _state(device: str = "dev-1") -> str:
    return f"{BASE}/v1/devices/{device}/state"


def _test(device: str = "dev-1") -> str:
    return f"{BASE}/v1/devices/{device}/test"


def _discovery(device: str = "dev-1") -> str:
    return f"{PREFIX}/device/{device}/config"


def _availability(instance_id: str) -> str:
    return f"{BASE}/v1/instances/{instance_id}/availability"


def _heartbeat(instance_id: str) -> str:
    return f"{BASE}/v1/instances/{instance_id}/heartbeat"


READ_EVERYTHING = (
    f"{BASE}/v1/devices/+/config",
    f"{BASE}/v1/devices/+/state",
    f"{PREFIX}/device/+/config",
    f"{BASE}/v1/instances/+/availability",
)


def test_documented_acl_block_is_the_tested_acl(acl_port: int, clients: Callable[[str], AclClient]) -> None:
    """The broker under test runs the text of the document: the fixture fails when the block or a marker is missing."""
    assert _documented_acl().strip()
    writer = clients("ha_one")
    writer.publish(_state(), "ON")
    reader = clients("ha_two")
    reader.subscribe(_state())

    assert reader.collect() == {(_state(), "ON", True)}


def test_ha_users_can_write_config_state_test_and_discovery(
    clients: Callable[[str], AclClient], instance_ids: dict[str, str]
) -> None:
    """A Home Assistant user publishes retained config, state, discovery and its own availability for the others."""
    writer = clients("ha_one")
    own_availability = _availability(instance_ids["ha_one"])
    writer.publish(_config(), '{"schema_version": 1}')
    writer.publish(_state(), "ON")
    writer.publish(_discovery(), '{"cmps": {}}')
    writer.publish(own_availability, "online")

    reader = clients("ha_two")
    reader.subscribe(*READ_EVERYTHING)

    assert reader.collect() == {
        (_config(), '{"schema_version": 1}', True),
        (_state(), "ON", True),
        (_discovery(), '{"cmps": {}}', True),
        (own_availability, "online", True),
    }


def test_ha_users_can_publish_the_test_topic_live(clients: Callable[[str], AclClient]) -> None:
    """The test topic is a trigger source that only Home Assistant users may write; a peer receives it live."""
    reader = clients("ha_two")
    reader.subscribe(_test())
    writer = clients("ha_one")

    writer.publish(_test(), "ON", retain=False)

    assert reader.collect() == {(_test(), "ON", False)}


def test_external_publisher_can_only_write_state(clients: Callable[[str], AclClient]) -> None:
    """The bridge user writes the state topic; config, discovery and test publishes reach nobody and stay unstored."""
    live = clients("ha_two")
    live.subscribe(_config(), _state(), _discovery(), _test())
    bridge = clients("bridge")

    bridge.publish(_state(), "ON")
    assert live.collect() == {(_state(), "ON", False)}

    bridge.publish(_config(), '{"schema_version": 1}')
    bridge.publish(_discovery(), '{"cmps": {}}')
    bridge.publish(_test(), "ON", retain=False)
    assert live.collect() == set()

    # A retained read-back by a later subscriber finds only the allowed state message
    later = clients("ha_one")
    later.subscribe(_config(), _state(), _discovery())
    assert later.collect() == {(_state(), "ON", True)}


def test_instance_cannot_write_another_instances_availability(
    clients: Callable[[str], AclClient], instance_ids: dict[str, str]
) -> None:
    """An instance may only write the availability topic of its own instance id."""
    reader = clients("ha_one")
    reader.subscribe(f"{BASE}/v1/instances/+/availability")
    other = clients("ha_two")

    other.publish(_availability(instance_ids["ha_one"]), "online")
    assert reader.collect() == set()

    other.publish(_availability(instance_ids["ha_two"]), "online")
    assert reader.collect() == {(_availability(instance_ids["ha_two"]), "online", False)}

    later = clients("ha_one")
    later.subscribe(f"{BASE}/v1/instances/+/availability")
    assert later.collect() == {(_availability(instance_ids["ha_two"]), "online", True)}


def test_external_publisher_cannot_read_config(clients: Callable[[str], AclClient]) -> None:
    """Config documents carry the actions: the bridge user receives nothing from the config wildcard."""
    bridge = clients("bridge")
    bridge.subscribe(f"{BASE}/v1/devices/+/config")
    owner = clients("ha_one")

    owner.publish(_config(), '{"schema_version": 1}')

    assert bridge.collect() == set()


def test_denied_publish_leaves_no_trace(clients: Callable[[str], AclClient]) -> None:
    """A denied qos 1 publish may or may not be acknowledged; a later reader finds no retained message either way."""
    bridge = clients("bridge")
    bridge.publish(_config("denied"), "forged")

    reader = clients("ha_one")
    reader.subscribe(_config("denied"), f"{BASE}/v1/devices/+/config")

    assert reader.collect() == set()


def test_instance_cannot_write_another_instances_heartbeat(
    clients: Callable[[str], AclClient], instance_ids: dict[str, str]
) -> None:
    """D-05: an instance writes only its own heartbeat topic, and every instance reads all of them."""
    reader = clients("ha_one")
    reader.subscribe(f"{BASE}/v1/instances/+/heartbeat")
    other = clients("ha_two")

    other.publish(_heartbeat(instance_ids["ha_two"]), "beat-two", retain=False)
    assert reader.collect() == {(_heartbeat(instance_ids["ha_two"]), "beat-two", False)}

    other.publish(_heartbeat(instance_ids["ha_one"]), "forged", retain=False)
    assert reader.collect() == set()


def test_heartbeat_is_not_replayed_to_late_subscribers(
    clients: Callable[[str], AclClient], instance_ids: dict[str, str]
) -> None:
    """D-05: a heartbeat is live only; a late subscriber gets nothing, so a crashed instance cannot look current."""
    live = clients("ha_one")
    live.subscribe(f"{BASE}/v1/instances/+/heartbeat")
    writer = clients("ha_two")

    writer.publish(_heartbeat(instance_ids["ha_two"]), "beat", retain=False)
    assert live.collect() == {(_heartbeat(instance_ids["ha_two"]), "beat", False)}

    late = clients("ha_one")
    late.subscribe(f"{BASE}/v1/instances/+/heartbeat")
    assert late.collect() == set()


def test_external_publisher_has_no_heartbeat_access(
    clients: Callable[[str], AclClient], instance_ids: dict[str, str]
) -> None:
    """The bridge user neither reads a heartbeat nor makes one reach a Home Assistant user."""
    ha = clients("ha_two")
    ha.subscribe(f"{BASE}/v1/instances/+/heartbeat")
    bridge = clients("bridge")
    bridge.subscribe(f"{BASE}/v1/instances/+/heartbeat")
    owner = clients("ha_one")

    owner.publish(_heartbeat(instance_ids["ha_one"]), "beat", retain=False)
    assert ha.collect() == {(_heartbeat(instance_ids["ha_one"]), "beat", False)}
    assert bridge.collect() == set()

    bridge.publish(_heartbeat(instance_ids["ha_one"]), "forged", retain=False)
    bridge.publish(_heartbeat(str(uuid.uuid4())), "made-up", retain=False)
    assert ha.collect() == set()
