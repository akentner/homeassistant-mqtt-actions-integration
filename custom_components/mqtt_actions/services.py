"""
The services of the integration (D-12).

Services are registered once in `async_setup`, never in the entry setup, so they exist for the whole run of Home
Assistant and survive an unload of the entry (a hassfest rule). Every service is admin only: they republish, export or
change what runs, so no other user may call them. A handler finds the loaded manager at call time; with no loaded entry
it raises a translated validation error instead of failing with a traceback.

A device is named by `device_id`, the Home Assistant registry id of the companion device that a `device` selector
produces. It is an instance-local value and never part of synced content. `resolve_device` maps it to the device uuid
through the `(DOMAIN, uuid)` identifier of the companion device.
"""

from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, SERVICE_RESYNC

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .manager import Manager

RESYNC_SCHEMA = probatio.Schema({})


def async_get_loaded_manager(hass: HomeAssistant) -> Manager:
    """Return the manager of the loaded entry of the domain, or raise a translated error when none is loaded."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            manager: Manager = entry.runtime_data
            return manager
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")


def resolve_device(hass: HomeAssistant, manager: Manager, registry_device_id: str, *, owned_only: bool = False) -> str:
    """
    Return the device uuid of a Home Assistant device, or raise a translated error.

    Only the companion device of an owned device or a mirror resolves. The hub device carries the entry id as its
    identifier value, which is never a device of the manager, and a device of another integration has no identifier of
    this domain, so both are refused. With `owned_only` a mirror is refused as well.
    """
    device = dr.async_get(hass).async_get(registry_device_id)
    if device is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_device")
    for domain, value in device.identifiers:
        if domain != DOMAIN:
            continue
        if value in manager.devices:
            return value
        if value in manager.mirrors:
            if owned_only:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="export_not_owned")
            return value
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_a_device")


async def _async_handle_resync(call: ServiceCall) -> dict[str, Any]:
    """Run the same manager method as the hub button; a repeat inside the cooldown is an error, not queued work."""
    manager = async_get_loaded_manager(call.hass)
    if not await manager.async_resync():
        # A manager that is not running is a stopped entry, anything else is the cooldown (T-04-35)
        key = "resync_throttled" if manager.running else "not_loaded"
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key=key)
    return {"resynced": True}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services of the integration; called once from `async_setup`."""
    async_register_admin_service(
        hass, DOMAIN, SERVICE_RESYNC, _async_handle_resync, RESYNC_SCHEMA, SupportsResponse.OPTIONAL
    )
