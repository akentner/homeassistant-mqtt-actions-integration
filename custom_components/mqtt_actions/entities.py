"""Shared base of the entities of the hub device: the device info and the dispatcher wiring (D-06, D-13)."""

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from .manager import Manager

HUB_MANUFACTURER = "MQTT Actions"
HUB_MODEL = "Hub"


def hub_device_info(manager: Manager) -> DeviceInfo:
    """
    Return the device info of the hub: one device per instance, keyed by the config entry id (D-13).

    The entry id and not the instance id is the identifier, so the device survives a change of the instance id.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, manager.entry.entry_id)},
        name=manager.instance_name,
        manufacturer=HUB_MANUFACTURER,
        model=HUB_MODEL,
        sw_version=manager.version,
        entry_type=DeviceEntryType.SERVICE,
    )


class MqttActionsEntity(Entity):
    """Base of the hub entities: named after the device, never polled, and rewritten when a listed signal fires."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # Dispatcher signal templates (formatted with the config entry id) that make the entity write its state again
    _signals: tuple[str, ...] = ()

    def __init__(self, manager: Manager) -> None:
        """Initialize the entity for the manager of one config entry."""
        self._manager = manager
        self._attr_device_info = hub_device_info(manager)

    async def async_added_to_hass(self) -> None:
        """Connect every signal of the subclass; the connections end with the entity."""
        await super().async_added_to_hass()
        for signal in self._signals:
            self.async_on_remove(
                async_dispatcher_connect(self.hass, signal.format(self._manager.entry.entry_id), self._on_signal)
            )

    @callback
    def _on_signal(self) -> None:
        """Write the state again after a signal."""
        self.async_write_ha_state()
