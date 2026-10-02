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
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_register_admin_service

from .actions import ActionsInvalid, async_validate_actions
from .const import (
    ADOPT_NOT_A_MIRROR,
    ADOPT_NOT_APPROVED,
    ADOPT_OWNER_NOT_OFFLINE,
    CONF_DEVICE_ID,
    DOMAIN,
    EXPORT_DIRECTORY,
    LOGGER,
    MAX_IMPORT_BYTES,
    REASON_BAD_STATE,
    REASON_NO_STATE,
    REASON_RATE_LIMITED,
    SERVICE_ADOPT_DEVICE,
    SERVICE_EXPORT_DEVICES,
    SERVICE_IMPORT_DEVICES,
    SERVICE_RESYNC,
    SERVICE_RETRIGGER,
)
from .manager import AdoptionError
from .portability import (
    REASON_BAD_FILE_NAME,
    REASON_BAD_FORMAT,
    REASON_FILE_UNREADABLE,
    REASON_INVALID_ACTIONS,
    REASON_TOO_LARGE,
    PortabilityError,
    build_export,
    export_file_path,
    parse_export,
    parse_import_text,
    prepare_import,
    read_import,
    write_export,
)
from .retrigger import RetriggerError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .manager import Manager
    from .portability import PreparedDevice

CONF_FILE_NAME = "file_name"
CONF_DATA = "data"
CONF_STATE = "state"
CONF_FORCE = "force"

RESYNC_SCHEMA = probatio.Schema({})
# The file name is only a string here; its rules are checked by the handler so a bad name is a translated error
EXPORT_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_DEVICE_ID): probatio.All(cv.ensure_list, [str]),
        probatio.Optional(CONF_FILE_NAME): str,
    }
)
# The export is a JSON object; its structure is checked by the handler, so a flaw is a translated error with a position
IMPORT_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_DATA): dict,
        probatio.Optional(CONF_FILE_NAME): str,
    }
)
# The device is named by its registry id, the state is free text that the caller matches against the device
RETRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE_ID): str,
        probatio.Optional(CONF_STATE): str,
    }
)
# The device is named by its registry id; force only overrides the owner-online check, never the approval (D-10)
ADOPT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE_ID): str,
        probatio.Optional(CONF_FORCE, default=False): cv.boolean,
    }
)
# The placeholders each refusal of an adoption fills in its message; a broker-supplied name is plain text (D-10)
ADOPT_PLACEHOLDERS = {
    ADOPT_OWNER_NOT_OFFLINE: ("device", "owner"),
    ADOPT_NOT_APPROVED: ("device",),
    ADOPT_NOT_A_MIRROR: (),
}
# The refusals of the caller that have a message of their own; anything else means the device vanished meanwhile
RETRIGGER_REFUSALS = frozenset({REASON_BAD_STATE, REASON_NO_STATE, REASON_RATE_LIMITED})


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


def _import_rejected(err: PortabilityError) -> ServiceValidationError:
    """
    Return the translated rejection of an import: a fixed reason code and a position, never any content.

    A file that cannot be named or read has an error of its own; every other code is `import_rejected`. The log carries
    the reason code and the position and nothing else (T-04-41).
    """
    if err.reason in {REASON_BAD_FILE_NAME, REASON_FILE_UNREADABLE}:
        LOGGER.warning("The import file was refused: %s", err.reason)
        return ServiceValidationError(translation_domain=DOMAIN, translation_key=err.reason)
    position = str(err.index) if err.index is not None else "-"
    LOGGER.warning("An import was rejected: reason %s, position %s", err.reason, position)
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="import_rejected",
        translation_placeholders={"index": position, "reason": err.reason},
    )


async def _async_validate_deeply(hass: HomeAssistant, device: PreparedDevice) -> None:
    """Validate the actions of every trigger on this instance, as the UI flows do; a flaw names the item only."""
    for trigger in device.spec.triggers.values():
        try:
            await async_validate_actions(hass, trigger.actions)
        except ActionsInvalid as err:
            raise PortabilityError(REASON_INVALID_ACTIONS, device.index) from err


def _checked_size(data: Any) -> Any:
    """Return the data when its JSON text is within MAX_IMPORT_BYTES; data that is not plain JSON is no import."""
    try:
        size = len(json.dumps(data, ensure_ascii=False).encode())
    except (TypeError, ValueError) as err:
        raise PortabilityError(REASON_BAD_FORMAT) from err
    if size > MAX_IMPORT_BYTES:
        raise PortabilityError(REASON_TOO_LARGE)
    return data


async def _async_handle_import(call: ServiceCall) -> dict[str, Any]:
    """
    Create one owned device for every item of an export, or none at all.

    Exactly one source is given: the export as `data` or the name of a file in the private directory. Every item is
    validated before the first device is created. Creating the subentries afterwards is not transactional: a failure
    halfway would leave the earlier devices, which is rare and documented. The update listener of the entry
    reconciles, so the manager publishes the document and the discovery of each new device.
    """
    hass = call.hass
    manager = async_get_loaded_manager(hass)
    data: dict[str, Any] | None = call.data.get(CONF_DATA)
    file_name: str | None = call.data.get(CONF_FILE_NAME)
    if (data is None) == (file_name is None):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="import_needs_exactly_one_source")
    try:
        if file_name is not None:
            text = await hass.async_add_executor_job(read_import, Path(hass.config.path()), file_name)
            value: Any = parse_import_text(text)
        else:
            value = _checked_size(data)
        items = parse_export(value)
        prepared = prepare_import(items, owner=manager.instance_id, owner_name=manager.instance_name)
        for device in prepared:
            await _async_validate_deeply(hass, device)
    except PortabilityError as err:
        raise _import_rejected(err) from err
    for device in prepared:
        hass.config_entries.async_add_subentry(
            manager.entry,
            ConfigSubentry(
                data=MappingProxyType(device.data),
                subentry_type=device.kind,
                title=device.name,
                unique_id=device.device_id,
            ),
        )
    LOGGER.info("Imported %d devices", len(prepared))
    return {"imported": [{"index": d.index, "uuid": d.device_id, "name": d.name} for d in prepared]}


async def _async_handle_retrigger(call: ServiceCall) -> dict[str, Any]:
    """
    Run the actions of one device again on every instance that approved it and return who answered how.

    The device may be owned or a mirror. A refusal of the caller (unusable state, no baseline, a repeat inside the
    interval) is a translated validation error and sends nothing (D-01, D-04).
    """
    hass = call.hass
    manager = async_get_loaded_manager(hass)
    device_id = resolve_device(hass, manager, call.data[CONF_DEVICE_ID])
    try:
        return await manager.retrigger.async_retrigger(device_id, call.data.get(CONF_STATE))
    except RetriggerError as err:
        key = f"retrigger_{err.reason}" if err.reason in RETRIGGER_REFUSALS else "unknown_device"
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key=key) from err


def _adoption_refused(manager: Manager, device_id: str, err: AdoptionError) -> ServiceValidationError:
    """Return the translated refusal of an adoption: the key is `adopt_<reason>`, the message names force: true."""
    device = manager.device(device_id)
    values = {"device": device.name if device is not None else "", "owner": err.owner_name or ""}
    names = ADOPT_PLACEHOLDERS.get(err.reason, ())
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=f"adopt_{err.reason}",
        translation_placeholders={name: values[name] for name in names},
    )


async def _async_handle_adopt(call: ServiceCall) -> dict[str, Any]:
    """
    Take over an approved mirror whose owner is offline, or on `force`, and return the old owner's name.

    The device may be owned or a mirror here; the manager refuses anything that is not a mirror, an unapproved or
    blocked mirror even with `force`, and an owner that is not known to be offline without it (D-10, T-04-50).
    """
    hass = call.hass
    manager = async_get_loaded_manager(hass)
    device_id = resolve_device(hass, manager, call.data[CONF_DEVICE_ID])
    try:
        previous_owner = await manager.async_adopt(device_id, force=call.data[CONF_FORCE])
    except AdoptionError as err:
        raise _adoption_refused(manager, device_id, err) from err
    return {"uuid": device_id, "adopted": True, "previous_owner": previous_owner}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services of the integration; called once from `async_setup`."""
    async_register_admin_service(
        hass, DOMAIN, SERVICE_RESYNC, _async_handle_resync, RESYNC_SCHEMA, SupportsResponse.OPTIONAL
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_EXPORT_DEVICES, _async_handle_export, EXPORT_SCHEMA, SupportsResponse.OPTIONAL
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_IMPORT_DEVICES, _async_handle_import, IMPORT_SCHEMA, SupportsResponse.OPTIONAL
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_RETRIGGER, _async_handle_retrigger, RETRIGGER_SCHEMA, SupportsResponse.OPTIONAL
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_ADOPT_DEVICE, _async_handle_adopt, ADOPT_SCHEMA, SupportsResponse.OPTIONAL
    )
