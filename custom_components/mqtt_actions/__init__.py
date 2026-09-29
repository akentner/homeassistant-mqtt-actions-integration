"""The MQTT Actions integration."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # noqa: ARG001
    """Set up MQTT Actions from a config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # noqa: ARG001
    """Unload a config entry."""
    return True
