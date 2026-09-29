"""The MQTT Actions integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .manager import Manager, async_remove_all_devices
from .mqtt_gateway import MqttGateway

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

type MqttActionsConfigEntry = ConfigEntry[Manager]


async def async_setup_entry(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> bool:
    """Set up MQTT Actions from a config entry."""
    # Nothing else runs before this check: without a ready MQTT client the entry retries later
    if not await MqttGateway(hass).async_wait_ready():
        msg = "MQTT is not available"
        raise ConfigEntryNotReady(msg)
    manager = Manager(hass, entry)
    entry.runtime_data = manager
    # Registered before the start so a subentry change during a slow start is not lost; HA also runs the
    # on-unload callbacks when this setup fails
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    try:
        await manager.async_start()
    except HomeAssistantError as err:
        # HA never calls async_unload_entry for a failed setup, so release subscriptions and Scripts here
        await manager.async_stop()
        raise ConfigEntryNotReady(str(err)) from err
    except BaseException:
        await manager.async_stop()
        raise
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> None:  # noqa: ARG001
    """Reconcile the running devices after subentries changed."""
    await entry.runtime_data.async_reconcile()


async def async_unload_entry(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> bool:  # noqa: ARG001
    """Unload a config entry; a user unload or reload releases tripped breakers before the final save (D-15)."""
    entry.runtime_data.release_all_breakers()
    await entry.runtime_data.async_stop()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> None:
    """
    Clean up the broker and the local state when the hub entry is removed (D-15).

    Phase 3 must redesign this as a confirmed, multi-instance-aware delete; see async_remove_all_devices.
    """
    await async_remove_all_devices(hass, entry)
