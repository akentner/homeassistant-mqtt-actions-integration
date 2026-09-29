"""The MQTT Actions integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady

from .manager import Manager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

type MqttActionsConfigEntry = ConfigEntry[Manager]


async def async_setup_entry(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> bool:
    """Set up MQTT Actions from a config entry."""
    manager = Manager(hass, entry)
    if not await manager.gateway.async_wait_ready():
        msg = "MQTT is not available"
        raise ConfigEntryNotReady(msg)
    entry.runtime_data = manager
    await manager.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> None:  # noqa: ARG001
    """Reconcile the running devices after subentries changed."""
    await entry.runtime_data.async_reconcile()


async def async_unload_entry(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> bool:  # noqa: ARG001
    """Unload a config entry."""
    await entry.runtime_data.async_stop()
    return True
