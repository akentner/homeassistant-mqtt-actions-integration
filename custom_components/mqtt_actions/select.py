"""The selects: the native Select of an owned device and the mode selects of every device and of the instance."""

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import MODES, SIGNAL_DEVICES_CHANGED, SIGNAL_MODES_CHANGED, SUBENTRY_SELECT
from .entities import MqttActionsEntity, NativeDeviceEntity, device_info_for

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .manager import Manager


class _ModeSelect(MqttActionsEntity, SelectEntity):
    """Base of the two mode selects: the three words, in the configuration category (D-14)."""

    _attr_entity_category = EntityCategory.CONFIG
    _signals = (SIGNAL_MODES_CHANGED,)

    def __init__(self, manager: Manager) -> None:
        """Initialize the select with the three mode words as options."""
        super().__init__(manager)
        self._attr_options = list(MODES)

    async def async_select_option(self, option: str) -> None:
        """Store the chosen mode; a refusal of the manager is an error to the caller."""
        try:
            await self._set_mode(option)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def _set_mode(self, option: str) -> None:
        """Hand the mode to the manager, for the device or for the instance."""
        raise NotImplementedError


class DeviceModeSelect(_ModeSelect):
    """The mode of one device: run, observe or disabled. Local to this instance, never published (D-14)."""

    _attr_translation_key = "device_mode"
    _entity_id_part = "mode"
    _signals = (SIGNAL_MODES_CHANGED, SIGNAL_DEVICES_CHANGED)

    def __init__(self, manager: Manager, device_id: str) -> None:
        """Initialize the select of an owned or mirrored device; its unique id is bound to the device."""
        super().__init__(manager)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_mode"
        self._attr_device_info = device_info_for(manager, device_id)

    @property
    def available(self) -> bool:
        """Return whether the device is still owned or mirrored here."""
        return self._manager.has_device(self._device_id)

    @property
    def current_option(self) -> str:
        """Return the mode of the device itself, not the effective one."""
        return self._manager.device_mode(self._device_id)

    async def _set_mode(self, option: str) -> None:
        await self._manager.async_set_device_mode(self._device_id, option)


class DeviceSelect(NativeDeviceEntity, SelectEntity):
    """
    The select of a Select device: friendly names in the UI, StateValues on the broker (D-07).

    Options and current option are computed from the current spec and the recorded StateValue at every read, so a
    renamed option follows at once and a removed one leaves the state unknown instead of a stale name.
    """

    _attr_name = None

    def __init__(self, manager: Manager, device_id: str) -> None:
        """Initialize the select; its unique id is the device id, the value the discovery entity had."""
        super().__init__(manager, device_id)
        self._attr_unique_id = device_id

    @property
    def options(self) -> list[str]:
        """Return the friendly names of the options in stored order."""
        device = self._manager.device(self._device_id)
        return [] if device is None else [trigger.friendly_name for trigger in device.spec.triggers.values()]

    @property
    def current_option(self) -> str | None:
        """Return the friendly name of the recorded StateValue, None when there is none or it is no option any more."""
        device = self._manager.device(self._device_id)
        if device is None or device.value is None:
            return None
        return next(
            (trigger.friendly_name for trigger in device.spec.triggers.values() if trigger.value == device.value),
            None,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the friendly name of the value shown before the current one, None when unknown (P-04)."""
        device = self._manager.device(self._device_id)
        previous = self._manager.previous_value(self._device_id)
        name = (
            None
            if device is None or previous is None
            else next(
                (trigger.friendly_name for trigger in device.spec.triggers.values() if trigger.value == previous),
                None,
            )
        )
        return {"previous_state": name}

    async def async_select_option(self, option: str) -> None:
        """Publish the StateValue of the chosen friendly name; the state changes with the broker echo."""
        device = self._manager.device(self._device_id)
        value = None
        if device is not None:
            value = next(
                (trigger.value for trigger in device.spec.triggers.values() if trigger.friendly_name == option), None
            )
        if value is None:
            msg = "Not an option of this device"
            raise HomeAssistantError(msg)
        await self._manager.async_send_state(self._device_id, value)


class InstanceModeSelect(_ModeSelect):
    """The mode of the whole instance on the hub device; the most restrictive of this and a device mode counts."""

    _attr_translation_key = "instance_mode"
    _entity_id_part = "instance_mode"

    def __init__(self, manager: Manager) -> None:
        """Initialize the select; its unique id is bound to the config entry."""
        super().__init__(manager)
        self._attr_unique_id = f"{manager.entry.entry_id}_instance_mode"

    @property
    def current_option(self) -> str:
        """Return the mode of the instance."""
        return self._manager.instance_mode

    async def _set_mode(self, option: str) -> None:
        await self._manager.async_set_instance_mode(option)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Manager],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the instance select and the select of every owned device and mirror, now and when one appears later."""
    manager = entry.runtime_data
    async_add_entities([InstanceModeSelect(manager)])
    added: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        # A removed device is forgotten, so a device that comes back under the same id gets its entity again
        added.intersection_update(manager.devices.keys() | manager.mirrors.keys())
        for device_id in [*manager.devices, *manager.mirrors]:
            if device_id in added:
                continue
            added.add(device_id)
            # A mirror has no subentry: its companion device is a plain device of the entry (D-13 revised)
            async_add_entities(
                [DeviceModeSelect(manager, device_id)], config_subentry_id=manager.subentry_id_of(device_id)
            )

    added_native: set[str] = set()

    @callback
    def _add_new_native_devices() -> None:
        qualifying = {
            device_id
            for device_id, device in [*manager.devices.items(), *manager.mirrors.items()]
            if device.spec.kind == SUBENTRY_SELECT and manager.is_native(device_id)
        }
        added_native.intersection_update(qualifying)
        for device_id in sorted(qualifying - added_native):
            added_native.add(device_id)
            async_add_entities([DeviceSelect(manager, device_id)], config_subentry_id=manager.subentry_id_of(device_id))

    _add_new_devices()
    _add_new_native_devices()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICES_CHANGED.format(entry.entry_id), _add_new_devices)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICES_CHANGED.format(entry.entry_id), _add_new_native_devices)
    )
