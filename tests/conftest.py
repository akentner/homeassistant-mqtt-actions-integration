"""Shared pytest configuration for the MQTT Actions integration tests."""

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import ConfigSubentryData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mqtt_actions import const
from custom_components.mqtt_actions import manager as manager_module
from custom_components.mqtt_actions.const import (
    CONF_ACTIONS,
    CONF_BASE_TOPIC,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_OPTIONS,
    CONF_RUN_MODE,
    CONF_RUN_ON_STARTUP,
    CONF_STATE_VALUE,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from tests.fake_broker import FakeBroker, InstanceFactory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Sequence

    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load integrations from custom_components in every test."""


@pytest.fixture(autouse=True)
def disable_native_cutover(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Arm no cutover timer in any test, so every test keeps the legacy path it asserts (D-09).

    Only the cutover tests turn the settle timer on, through `enable_native_cutover`.
    """
    monkeypatch.setattr(manager_module, "CUTOVER_SETTLE_SECONDS", None)


@pytest.fixture
def enable_native_cutover(disable_native_cutover: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real settle time for the tests of the cutover; it depends on the autouse fixture for the order."""
    monkeypatch.setattr(manager_module, "CUTOVER_SETTLE_SECONDS", const.CUTOVER_SETTLE_SECONDS)


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Tolerate the MQTT misc-loop timer, which the mocked paho client never cancels."""
    return True


def _optional_settings(
    run_mode: str | None, breaker_max_runs: int | None, breaker_window: int | None
) -> dict[str, Any]:
    """Return the run mode and breaker keys that were given; omitted keys exercise the stored-data default path."""
    settings: dict[str, Any] = {}
    if run_mode is not None:
        settings[CONF_RUN_MODE] = run_mode
    if breaker_max_runs is not None:
        settings[CONF_BREAKER_MAX_RUNS] = breaker_max_runs
    if breaker_window is not None:
        settings[CONF_BREAKER_WINDOW] = breaker_window
    return settings


@pytest.fixture
def make_switch_subentry() -> Callable[..., ConfigSubentryData]:
    """Return a factory for a switch subentry (title = name, unique_id = device_id)."""

    def _make(
        name: str,
        on: list[dict[str, Any]] | None = None,
        off: list[dict[str, Any]] | None = None,
        run_on_startup: bool = False,
        device_id: str | None = None,
        *,
        run_mode: str | None = None,
        breaker_max_runs: int | None = None,
        breaker_window: int | None = None,
    ) -> ConfigSubentryData:
        device_id = device_id or str(uuid.uuid4())
        return ConfigSubentryData(
            data={
                CONF_DEVICE_ID: device_id,
                CONF_ON_CHANGE_TO_ON: on or [],
                CONF_ON_CHANGE_TO_OFF: off or [],
                CONF_RUN_ON_STARTUP: run_on_startup,
                **_optional_settings(run_mode, breaker_max_runs, breaker_window),
            },
            subentry_type=SUBENTRY_SWITCH,
            title=name,
            unique_id=device_id,
        )

    return _make


@pytest.fixture
def make_select_subentry() -> Callable[..., ConfigSubentryData]:
    """Return a factory for a select subentry; options are (state_value, friendly_name, actions) tuples."""

    def _make(
        name: str,
        options: Sequence[tuple[str, str, list[dict[str, Any]]]],
        *,
        run_on_startup: bool = False,
        run_mode: str | None = None,
        breaker_max_runs: int | None = None,
        breaker_window: int | None = None,
        device_id: str | None = None,
    ) -> ConfigSubentryData:
        device_id = device_id or str(uuid.uuid4())
        return ConfigSubentryData(
            data={
                CONF_DEVICE_ID: device_id,
                CONF_OPTIONS: [
                    {CONF_STATE_VALUE: value, CONF_FRIENDLY_NAME: friendly, CONF_ACTIONS: actions}
                    for value, friendly, actions in options
                ],
                CONF_RUN_ON_STARTUP: run_on_startup,
                **_optional_settings(run_mode, breaker_max_runs, breaker_window),
            },
            subentry_type=SUBENTRY_SELECT,
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


@pytest.fixture
def fake_broker() -> FakeBroker:
    """Return a fresh fake broker with real retain semantics."""
    return FakeBroker()


@pytest.fixture
async def make_instance(hass: HomeAssistant, fake_broker: FakeBroker) -> AsyncIterator[InstanceFactory]:
    """Return the factory of started instances sharing the fake broker; every instance is closed at teardown."""
    factory = InstanceFactory(fake_broker)
    yield factory
    await factory.async_close()
