"""Base topic validation (D-01, threat T-01-06)."""

import pytest

from custom_components.mqtt_actions import topics


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
