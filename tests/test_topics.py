"""Base topic validation (D-01, threat T-01-06)."""

import pytest

from custom_components.mqtt_actions import topics
from custom_components.mqtt_actions.const import TOPIC_VERSION


@pytest.mark.parametrize("topic", ["mqtt_actions", "home/actions", "a/b/c"])
def test_valid_base_topic_is_returned_unchanged(topic: str) -> None:
    assert topics.validate_base_topic(topic) == topic


@pytest.mark.parametrize(
    "topic",
    [
        "",
        "home/#",
        "#",
        "home/+/x",
        "/home",
        "home/",
        "a//b",
        "$SYS/x",
        "$share",
        "bad\x00topic",
    ],
    ids=[
        "empty",
        "multi-level-wildcard",
        "bare-multi-level-wildcard",
        "single-level-wildcard",
        "leading-slash",
        "trailing-slash",
        "empty-level",
        "sys-prefix",
        "dollar-prefix",
        "nul-character",
    ],
)
def test_invalid_base_topic_is_rejected(topic: str) -> None:
    with pytest.raises(topics.InvalidBaseTopic):
        topics.validate_base_topic(topic)


def test_invalid_base_topic_is_a_value_error() -> None:
    assert issubclass(topics.InvalidBaseTopic, ValueError)


def test_test_topic_shape() -> None:
    """D-13: the test button topic is per device, versioned, and never the state topic."""
    assert topics.test_topic("mqtt_actions", "dev-1") == "mqtt_actions/v1/devices/dev-1/test"
    assert topics.test_topic("mqtt_actions", "dev-1") != topics.state_topic("mqtt_actions", "dev-1")


def test_config_topic_shape() -> None:
    """D-12: the config topic is per device and versioned, and differs from every other topic of the device."""
    topic = topics.config_topic("mqtt_actions", "dev-1")
    assert topic == f"mqtt_actions/{TOPIC_VERSION}/devices/dev-1/config"
    assert topic not in {
        topics.state_topic("mqtt_actions", "dev-1"),
        topics.test_topic("mqtt_actions", "dev-1"),
        topics.discovery_topic("homeassistant", "dev-1"),
    }


def test_config_wildcard_and_parsers() -> None:
    """The wildcards end in the expected suffix and the parsers accept exactly one non-empty middle segment."""
    assert topics.config_wildcard("mqtt_actions").endswith("devices/+/config")
    assert topics.parse_config_topic("mqtt_actions", topics.config_topic("mqtt_actions", "dev-1")) == "dev-1"
    good = topics.config_topic("mqtt_actions", "dev-1")
    bad = [
        good.replace("mqtt_actions", "other", 1),
        f"{good}/extra",
        f"mqtt_actions/{TOPIC_VERSION}/devices/config",
        f"mqtt_actions/{TOPIC_VERSION}/devices//config",
        topics.state_topic("mqtt_actions", "dev-1"),
        f"mqtt_actions/{TOPIC_VERSION}/devices/a+b/config",
        f"mqtt_actions/{TOPIC_VERSION}/devices/a#/config",
        f"mqtt_actions/{TOPIC_VERSION}/devices/a/b/config",
    ]
    for topic in bad:
        assert topics.parse_config_topic("mqtt_actions", topic) is None, topic


def test_availability_wildcard_and_parsers() -> None:
    """The availability topics of all instances are matched by one wildcard and parsed back to the instance id."""
    assert topics.availability_wildcard("mqtt_actions") == f"mqtt_actions/{TOPIC_VERSION}/instances/+/availability"
    good = topics.availability_topic("mqtt_actions", "inst-1")
    assert topics.parse_availability_topic("mqtt_actions", good) == "inst-1"
    bad = [
        good.replace("mqtt_actions", "other", 1),
        f"{good}/extra",
        f"mqtt_actions/{TOPIC_VERSION}/instances/availability",
        f"mqtt_actions/{TOPIC_VERSION}/instances//availability",
        f"mqtt_actions/{TOPIC_VERSION}/instances/inst-1/state",
        f"mqtt_actions/{TOPIC_VERSION}/instances/a+b/availability",
        f"mqtt_actions/{TOPIC_VERSION}/instances/a#/availability",
        f"mqtt_actions/{TOPIC_VERSION}/instances/a/b/availability",
    ]
    for topic in bad:
        assert topics.parse_availability_topic("mqtt_actions", topic) is None, topic


def test_discovery_wildcard_and_parsers() -> None:
    """The device discovery topics of all devices are matched by one wildcard and parsed back to the device id."""
    assert topics.discovery_wildcard("homeassistant") == "homeassistant/device/+/config"
    good = topics.discovery_topic("homeassistant", "dev-1")
    assert topics.parse_discovery_topic("homeassistant", good) == "dev-1"
    bad = [
        good.replace("homeassistant", "other", 1),
        f"{good}/extra",
        "homeassistant/device/config",
        "homeassistant/device//config",
        "homeassistant/device/dev-1/state",
        "homeassistant/device/a+b/config",
        "homeassistant/device/a#/config",
        "homeassistant/device/a/b/config",
    ]
    for topic in bad:
        assert topics.parse_discovery_topic("homeassistant", topic) is None, topic


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5d1d6c55-1b1d-4a5c-9a39-2d3f0b2b6a11", True),
        ("a", True),
        ("x" * 64, True),
        ("x" * 65, False),
        ("", False),
        ("a b", False),
        ("a.b", False),
        ("a\n", False),
        ("\u00e4", False),
    ],
)
def test_is_valid_device_id(value: str, *, expected: bool) -> None:
    """WR-05: a foreign device id is 1 to 64 characters of letters, digits, underscore and dash."""
    assert topics.is_valid_device_id(value) is expected
