"""Shared pytest configuration for the MQTT Actions integration tests."""

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import ConfigSubentryData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mqtt_actions.const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_RUN_ON_STARTUP,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    SUBENTRY_SWITCH,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load integrations from custom_components in every test."""


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Tolerate the MQTT misc-loop timer, which the mocked paho client never cancels."""
    return True


@pytest.fixture
def make_switch_subentry() -> Callable[..., ConfigSubentryData]:
    """Return a factory for a switch subentry (title = name, unique_id = device_id)."""

    def _make(
        name: str,
        on: list[dict[str, Any]] | None = None,
        off: list[dict[str, Any]] | None = None,
        run_on_startup: bool = False,
        device_id: str | None = None,
    ) -> ConfigSubentryData:
        device_id = device_id or str(uuid.uuid4())
        return ConfigSubentryData(
            data={
                CONF_DEVICE_ID: device_id,
                CONF_ON_CHANGE_TO_ON: on or [],
                CONF_ON_CHANGE_TO_OFF: off or [],
                CONF_RUN_ON_STARTUP: run_on_startup,
            },
            subentry_type=SUBENTRY_SWITCH,
            title=name,
            unique_id=device_id,
        )

    return _make


@pytest.fixture
def make_hub_entry() -> Callable[..., MockConfigEntry]:
    """Return a factory for the hub config entry (not yet added to hass)."""

    def _make(subentries: Sequence[ConfigSubentryData] | None = None, **overrides: Any) -> MockConfigEntry:
        kwargs: dict[str, Any] = {
            "domain": DOMAIN,
            "title": "Test instance",
            "data": {
                CONF_BASE_TOPIC: DEFAULT_BASE_TOPIC,
                CONF_INSTANCE_NAME: "Test instance",
                CONF_INSTANCE_ID: str(uuid.uuid4()),
            },
            "subentries_data": list(subentries or []),
        }
        kwargs.update(overrides)
        return MockConfigEntry(**kwargs)

    return _make
