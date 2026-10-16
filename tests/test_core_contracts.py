"""
Pins of the Home Assistant core internals this integration depends on without a public contract (FIX-01, D-08).

These tests run against the installed Home Assistant, not against a mock of it. Per D-08 they are never skipped, never
marked as an expected failure and carry no marker of their own: a core or PHACC bump that breaks one of them turns CI
red, a Dependabot PR included, and that is the wanted signal. When a pin turns red, read its failure message: it names
the core spot that changed and the documented fallback, so the fix is either an update of the integration or a change
of the pin made on purpose.
"""

import inspect
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import storage
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    StoreWithoutWriteLoad,
    async_fire_time_changed,
)

from custom_components.mqtt_actions import takeover
from tests.log_helpers import own_warnings

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant

FLUSH_FALLBACK_HINT = (
    "Home Assistant changed the private registry flush API (registry._store / registry._data_to_save): "
    "takeover.async_flush_registries no longer writes ahead of the schedule. The documented fallback is the scheduled "
    "registry save about 10 s later (see the docstring of takeover.async_flush_registries); update the flush or accept "
    "the fallback and change this pin on purpose."
)
FLUSH_WARNING = "A registry could not be written ahead of its schedule after the native takeover"
ENTITY_STORAGE_KEY = "core.entity_registry"
DEVICE_STORAGE_KEY = "core.device_registry"
PIN_ID = "flush-pin"


def _stored_entity_ids(hass_storage: dict[str, Any]) -> set[str]:
    """Return the entity ids the entity registry file holds right now."""
    stored = hass_storage.get(ENTITY_STORAGE_KEY)
    return {row["entity_id"] for row in stored["data"]["entities"]} if stored else set()


def _stored_device_ids(hass_storage: dict[str, Any]) -> set[str]:
    """Return the device ids the device registry file holds right now."""
    stored = hass_storage.get(DEVICE_STORAGE_KEY)
    return {row["id"] for row in stored["data"]["devices"]} if stored else set()


def _restore_real_registry_saves(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Give the registry stores of the test instance the real Store.async_save back.

    The PHACC hass fixture builds the entity registry on its StoreWithoutWriteLoad, whose async_save does nothing, so
    without this the immediate write could never reach hass_storage. Only that harness stub is undone; the registry,
    its _store attribute and its _data_to_save stay exactly as core made them.
    """
    monkeypatch.setattr(StoreWithoutWriteLoad, "async_save", storage.Store.async_save)


def _create_rows(hass: HomeAssistant) -> tuple[str, str]:
    """Create one entity registry row and one device registry row, and return their ids."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create("switch", "test", PIN_ID, config_entry=entry)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={("test", PIN_ID)})
    return entity.entity_id, device.id


async def test_the_registry_flush_writes_both_registries_ahead_of_the_scheduled_save(
    hass: HomeAssistant, hass_storage: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-06: the flush puts a new row of both registries on disk at once, without waiting for the scheduled save."""
    _restore_real_registry_saves(monkeypatch)
    entity_id, device_id = _create_rows(hass)
    assert entity_id not in _stored_entity_ids(hass_storage), "premise: the entity row is not on disk yet"
    assert device_id not in _stored_device_ids(hass_storage), "premise: the device row is not on disk yet"

    assert await takeover.async_flush_registries(hass) is True, FLUSH_FALLBACK_HINT

    assert entity_id in _stored_entity_ids(hass_storage), FLUSH_FALLBACK_HINT
    assert device_id in _stored_device_ids(hass_storage), FLUSH_FALLBACK_HINT


async def test_the_private_registry_flush_api_still_exists(hass: HomeAssistant) -> None:
    """Research Pitfall 9: both registries keep a store with async_save and a _data_to_save that needs no argument."""
    for registry in (er.async_get(hass), dr.async_get(hass)):
        assert hasattr(registry, "_store"), FLUSH_FALLBACK_HINT
        assert callable(getattr(registry._store, "async_save", None)), FLUSH_FALLBACK_HINT
        assert callable(getattr(registry, "_data_to_save", None)), FLUSH_FALLBACK_HINT
        required = [
            name
            for name, parameter in inspect.signature(registry._data_to_save).parameters.items()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        assert required == [], FLUSH_FALLBACK_HINT


async def test_a_refused_early_write_falls_back_to_the_scheduled_save(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-05: a refused early write returns False, logs one count-free warning, and the scheduled save still writes."""
    entity_id, _ = _create_rows(hass)
    registry = er.async_get(hass)

    async def _refuse(*_args: Any, **_kwargs: Any) -> None:
        msg = "refused"
        raise OSError(msg)

    monkeypatch.setattr(registry._store, "async_save", _refuse)

    assert await takeover.async_flush_registries(hass) is False

    warnings = own_warnings(caplog, exact=True)
    assert [record.getMessage() for record in warnings] == [FLUSH_WARNING]
    assert entity_id not in warnings[0].getMessage()
    assert PIN_ID not in warnings[0].getMessage()
    assert entity_id not in _stored_entity_ids(hass_storage), "premise: the refused write left the row off disk"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    assert entity_id in _stored_entity_ids(hass_storage), (
        "the scheduled registry save no longer follows a refused flush"
    )
