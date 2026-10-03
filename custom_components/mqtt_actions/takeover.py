"""
Registry takeover of the legacy core-MQTT entities of a device into this integration (D-05, D-07, MIG-01).

Before native entities, a switch or select device and its test buttons were created by core MQTT discovery and belong
to the MQTT config entry. This module moves them, with entity id, registry id, device id, area and user name intact,
to the hub entry of this integration. It is registry logic only: it never publishes and never imports the MQTT
integration. The migrate payload that unloads the discovered entities and the retained clear that follows belong to
the caller, which keeps the broker order, a fixed rule of the phase, in one place.

The order of the steps is load-bearing and each edge is pinned by a core test in `tests/test_takeover.py`:
nothing moves while a legacy entity is loaded, entities move before their device, and the companion device of the
mode select is merged last.
"""

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import entity_sources
from homeassistant.helpers.typing import UNDEFINED

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

TAKEOVER_UNLOAD_TIMEOUT = 10.0
TAKEOVER_RETRY_INTERVAL = 0.25

# The domain of core MQTT is a literal: only `mqtt_gateway.py` may import the MQTT integration
MQTT_DOMAIN = "mqtt"
LEGACY_DOMAINS = frozenset({"switch", "select", "button"})
LEGACY_TEST_PREFIX = "_test_"


class TakeoverStatus(StrEnum):
    """Outcome of a takeover: no legacy device, everything moved, or postponed because an entity is still loaded."""

    NOTHING = "nothing"
    DONE = "done"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class TakeoverTarget:
    """The device to take over; the subentry id of an owned device and None for a mirror, which sits under the entry."""

    device_id: str
    subentry_id: str | None


def legacy_device(hass: HomeAssistant, mqtt_entry_id: str, device_id: str) -> dr.DeviceEntry | None:
    """Return the core MQTT device the legacy discovery payload created for a device id, or None."""
    return dr.async_get(hass).async_get_device_by_identifier((MQTT_DOMAIN, f"{DOMAIN}_{device_id}"), mqtt_entry_id)


def is_legacy_entity(entity: er.RegistryEntry, device_id: str, mqtt_entry_id: str, mqtt_device_id: str) -> bool:
    """
    Return whether a registry entry really is a legacy entity of this integration's MQTT device.

    The unique id alone never decides: a hostile document may carry the device id of an unrelated MQTT entity (T-5-01).
    Platform, config entry, device, domain and the shape of the unique id must all match.
    """
    return (
        entity.platform == MQTT_DOMAIN
        and entity.config_entry_id == mqtt_entry_id
        and entity.device_id == mqtt_device_id
        and entity.domain in LEGACY_DOMAINS
        and (entity.unique_id == device_id or entity.unique_id.startswith(f"{device_id}{LEGACY_TEST_PREFIX}"))
    )


def _legacy_entries(
    hass: HomeAssistant, device: dr.DeviceEntry, device_id: str, mqtt_entry_id: str
) -> list[er.RegistryEntry]:
    """Return the legacy registry entries of the MQTT device, disabled ones included."""
    entries = er.async_entries_for_device(er.async_get(hass), device.id, include_disabled_entities=True)
    return [entry for entry in entries if is_legacy_entity(entry, device_id, mqtt_entry_id, device.id)]


async def _async_wait_unloaded(
    hass: HomeAssistant,
    collect: Callable[[], list[er.RegistryEntry]],
    *,
    unload_timeout: float,
    retry_interval: float,
) -> list[er.RegistryEntry] | None:
    """Wait until no legacy entity of the device is loaded; return the entries, or None when the wait ran out."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + unload_timeout
    while True:
        entries = collect()
        loaded = entity_sources(hass)
        if not any(entry.entity_id in loaded for entry in entries):
            return entries
        if loop.time() >= deadline:
            return None
        await asyncio.sleep(retry_interval)


async def async_take_over(  # noqa: PLR0913
    hass: HomeAssistant,
    entry: ConfigEntry,
    target: TakeoverTarget,
    *,
    mqtt_entry_id: str,
    unload_timeout: float = TAKEOVER_UNLOAD_TIMEOUT,
    retry_interval: float = TAKEOVER_RETRY_INTERVAL,
) -> TakeoverStatus:
    """
    Move the legacy MQTT entities and device of one device id under this entry, in the one safe order.

    Returns NOTHING when core MQTT has no device for the id, DEFERRED when a legacy entity is still loaded after the
    wait (nothing was changed, the caller retries at the next setup) and DONE otherwise.
    """
    if (device := legacy_device(hass, mqtt_entry_id, target.device_id)) is None:
        return TakeoverStatus.NOTHING
    entries = await _async_wait_unloaded(
        hass,
        lambda: _legacy_entries(hass, device, target.device_id, mqtt_entry_id),
        unload_timeout=unload_timeout,
        retry_interval=retry_interval,
    )
    if entries is None:
        LOGGER.warning("Takeover of device %r postponed: its legacy entities are still loaded", target.device_id[:40])
        return TakeoverStatus.DEFERRED

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Entities first: moving the device first would remove the entities that still belong to the old entry
    for legacy in entries:
        entity_registry.async_update_entity_platform(
            legacy.entity_id,
            DOMAIN,
            new_config_entry_id=entry.entry_id,
            new_config_subentry_id=UNDEFINED if target.subentry_id is None else target.subentry_id,
        )
    device_registry.async_update_device(
        device.id, new_config_entry_id=entry.entry_id, new_config_subentry_id=target.subentry_id
    )
    _merge_companion(hass, entry, target, device)
    return TakeoverStatus.DONE


def _merge_companion(hass: HomeAssistant, entry: ConfigEntry, target: TakeoverTarget, device: dr.DeviceEntry) -> None:
    """Move the entities of the old companion device to the taken-over device, remove the companion, rename."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    companion = device_registry.async_get_device_by_identifier((DOMAIN, target.device_id), entry.entry_id)
    if companion is not None and companion.id != device.id:
        for companion_entity in er.async_entries_for_device(
            entity_registry, companion.id, include_disabled_entities=True
        ):
            entity_registry.async_update_entity(companion_entity.entity_id, device_id=device.id)
        device_registry.async_remove_device(companion.id)
    device_registry.async_update_device(device.id, new_identifiers={(DOMAIN, target.device_id)})
