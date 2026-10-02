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

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_register_admin_service

from .const import CONF_DEVICE_ID, DOMAIN, EXPORT_DIRECTORY, LOGGER, SERVICE_EXPORT_DEVICES, SERVICE_RESYNC
from .portability import PortabilityError, build_export, export_file_path, write_export

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .manager import Manager

CONF_FILE_NAME = "file_name"

RESYNC_SCHEMA = probatio.Schema({})
# The file name is only a string here; its rules are checked by the handler so a bad name is a translated error
EXPORT_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_DEVICE_ID): probatio.All(cv.ensure_list, [str]),
        probatio.Optional(CONF_FILE_NAME): str,
    }
)


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


async def _async_handle_export(call: ServiceCall) -> dict[str, Any]:
    """
    Return the export of the owned devices as the response and write it to a private file when a name is given.

    Without a device all owned devices are exported; a selected device must be owned (a mirror, the hub device and
    foreign devices are refused). The directory comes from `hass.config.path()` and never from the user (T-04-32).
    """
    hass = call.hass
    manager = async_get_loaded_manager(hass)
    config_dir = Path(hass.config.path())
    file_name: str | None = call.data.get(CONF_FILE_NAME)
    if file_name is not None:
        try:
            export_file_path(config_dir, file_name)
        except PortabilityError as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="bad_file_name") from err
    selected: list[str] = call.data.get(CONF_DEVICE_ID, [])
    if selected:
        device_ids = list(dict.fromkeys(resolve_device(hass, manager, item, owned_only=True) for item in selected))
    else:
        device_ids = list(manager.devices)
    document = build_export(manager.devices[device_id].spec for device_id in device_ids)
    if file_name is None:
        return {"export": document, "file": None}
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    try:
        await hass.async_add_executor_job(write_export, config_dir, file_name, text)
    except (PortabilityError, OSError) as err:
        # Only the reason code or the OS error class is logged: the file name is user input and the text holds actions
        LOGGER.warning("The export file could not be written: %s", getattr(err, "reason", type(err).__name__))
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="export_write_failed") from err
    return {"export": document, "file": f"{EXPORT_DIRECTORY}/{file_name}"}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services of the integration; called once from `async_setup`."""
    async_register_admin_service(
        hass, DOMAIN, SERVICE_RESYNC, _async_handle_resync, RESYNC_SCHEMA, SupportsResponse.OPTIONAL
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_EXPORT_DEVICES, _async_handle_export, EXPORT_SCHEMA, SupportsResponse.OPTIONAL
    )
