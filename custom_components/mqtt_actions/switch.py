"""The native switch of an owned device: its state is the state topic, its commands publish to it (D-03, D-07)."""

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import PAYLOAD_OFF, PAYLOAD_ON, SIGNAL_DEVICES_CHANGED, SUBENTRY_SWITCH
from .entities import NativeDeviceEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .manager import Manager


class DeviceSwitch(NativeDeviceEntity, SwitchEntity):
    """
    The switch of a Switch device.

    The state is the last accepted StateValue of the shared state topic; a command is published retained at QoS 1 and
    changes nothing by itself, so the broker echo is the single state source and every instance agrees (STA-01).
    """

    _attr_name = None

    def __init__(self, manager: Manager, device_id: str) -> None:
        """Initialize the switch; its unique id is the device id, the value the discovery entity had."""
        super().__init__(manager, device_id)
        self._attr_unique_id = device_id

    @property
    def is_on(self) -> bool | None:
        """Return whether the last accepted StateValue is ON, None until one arrived."""
        device = self._manager.device(self._device_id)
        if device is None or device.value is None:
            return None
        return device.value == PAYLOAD_ON

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Publish ON to the state topic."""
        await self._manager.async_send_state(self._device_id, PAYLOAD_ON)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Publish OFF to the state topic."""
        await self._manager.async_send_state(self._device_id, PAYLOAD_OFF)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Manager],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the switch of every native Switch device, now and when one appears later."""
    manager = entry.runtime_data
    added: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        qualifying = {
            device_id
            for device_id, device in [*manager.devices.items(), *manager.mirrors.items()]
            if device.spec.kind == SUBENTRY_SWITCH and manager.is_native(device_id)
        }
        # A device that stopped qualifying is forgotten, so one that comes back under the same id gets its entity again
        added.intersection_update(qualifying)
        for device_id in sorted(qualifying - added):
            added.add(device_id)
            async_add_entities([DeviceSwitch(manager, device_id)], config_subentry_id=manager.subentry_id_of(device_id))

    _add_new_devices()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICES_CHANGED.format(entry.entry_id), _add_new_devices)
    )
