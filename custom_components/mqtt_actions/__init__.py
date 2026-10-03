"""The MQTT Actions integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import CONF_DELETE_DEVICES_ON_REMOVE, DOMAIN
from .manager import Manager, async_remove_all_devices, async_remove_local_state
from .mqtt_gateway import MqttGateway
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

type MqttActionsConfigEntry = ConfigEntry[Manager]

# Forwarded after the manager started and unloaded before it stops (D-13)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.SELECT]

# The integration is configured through the UI only; hassfest requires this once `async_setup` exists
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001
    """Register the services once per Home Assistant start; the entry setup registers none (D-12)."""
    async_setup_services(hass)
    return True


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
    # The entities read the running manager, so the platforms come last; a failure here must not leave it running
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await manager.async_stop()
        raise
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> None:  # noqa: ARG001
    """Reconcile the running devices after subentries changed."""
    await entry.runtime_data.async_reconcile()


async def async_unload_entry(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> bool:
    """
    Unload a config entry: the platforms first, then the manager (D-13).

    A user unload or reload releases tripped breakers before the final save (D-15). When a platform refuses to unload,
    nothing else is touched and the entry stays loaded.
    """
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    entry.runtime_data.release_all_breakers()
    await entry.runtime_data.async_stop()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: MqttActionsConfigEntry) -> None:
    """
    Clean up when the hub entry is removed: keep the devices on the broker unless the user chose deletion (D-11).

    Replaces the unconditional delete of Phase 1 (D-15). Home Assistant runs this after the unload and offers no dialog,
    so the choice is the hub option stored before the removal. Keep leaves every retained message alone, including the
    `offline` availability of the unload, so other instances show the orphans as unavailable and never prune them; it
    touches MQTT not at all. Both modes remove the local Store and every integration issue.
    """
    if entry.options.get(CONF_DELETE_DEVICES_ON_REMOVE, False):
        await async_remove_all_devices(hass, entry)
    else:
        await async_remove_local_state(hass, entry)
