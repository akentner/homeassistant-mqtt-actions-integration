"""The mode selects: one per owned device on its companion device, and one for the whole instance (D-13, D-14, D-15)."""

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import MODES, SIGNAL_DEVICES_CHANGED, SIGNAL_MODES_CHANGED
from .entities import MqttActionsEntity, companion_device_info

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
    _signals = (SIGNAL_MODES_CHANGED, SIGNAL_DEVICES_CHANGED)

    def __init__(self, manager: Manager, device_id: str) -> None:
        """Initialize the select of a device that is known to the manager; its unique id is bound to the device."""
        super().__init__(manager)
        device = manager.devices[device_id]
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_mode"
        self._attr_device_info = companion_device_info(
            device_id, device.name, device.spec.kind, mirror=device.mirror is not None, sw_version=manager.version
        )

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


class InstanceModeSelect(_ModeSelect):
    """The mode of the whole instance on the hub device; the most restrictive of this and a device mode counts."""

    _attr_translation_key = "instance_mode"

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
    """Add the instance select, the select of every owned device and of every owned device that appears later."""
    manager = entry.runtime_data
    async_add_entities([InstanceModeSelect(manager)])
    added: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        # A removed device is forgotten, so a device that comes back under the same id gets its entity again
        added.intersection_update(manager.devices)
        for device_id in manager.devices:
            if device_id in added:
                continue
            added.add(device_id)
            async_add_entities(
                [DeviceModeSelect(manager, device_id)], config_subentry_id=manager.subentry_id_of(device_id)
            )

    _add_new_devices()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICES_CHANGED.format(entry.entry_id), _add_new_devices)
    )
