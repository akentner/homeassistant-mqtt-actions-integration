"""Shared pytest configuration for the MQTT Actions integration tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load integrations from custom_components in every test."""


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Tolerate the MQTT misc-loop timer, which the mocked paho client never cancels."""
    return True
