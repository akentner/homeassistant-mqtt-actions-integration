"""Shared base of the entities of the hub device: the device info and the dispatcher wiring (D-06, D-13)."""

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_DEVICE_STATE, SIGNAL_DEVICES_CHANGED, SUBENTRY_SELECT

if TYPE_CHECKING:
    from .manager import Manager

HUB_MANUFACTURER = "MQTT Actions"
HUB_MODEL = "Hub"
SWITCH_DEVICE_MODEL = "Switch device"
SELECT_DEVICE_MODEL = "Select device"


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


def device_info_for(manager: Manager, device_id: str) -> DeviceInfo:
    """
    Return the device info of an owned or mirrored device: the one device its mode select and native entities share.

    The device belongs to this integration and is keyed by the device uuid; the discovery device with the same uuid is
    registered by core MQTT under the MQTT config entry and never shares a registry entry with it. For an owned device
    the entity platform attaches it to the subentry of the device; a mirror has no subentry (D-08, D-13).
    """
    device = manager.device(device_id)
    assert device is not None  # noqa: S101
    model = SELECT_DEVICE_MODEL if device.spec.kind == SUBENTRY_SELECT else SWITCH_DEVICE_MODEL
    if device.mirror is not None:
        # A native mirror names its owner (D-07); the name is plain text, bounded by the parser of the document
        model = f"{model} (mirror of {device.mirror.owner_name})" if device.mirror.native else f"{model} (mirror)"
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device.name,
        manufacturer=HUB_MANUFACTURER,
        model=model,
        sw_version=manager.version,
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


class NativeDeviceEntity(MqttActionsEntity):
    """Base of the native entities of one owned device: its device info and a state that follows the broker (D-03)."""

    _signals = (SIGNAL_DEVICES_CHANGED,)

    def __init__(self, manager: Manager, device_id: str) -> None:
        """Initialize the entity of a device; it shares the device of the mode select."""
        super().__init__(manager)
        self._device_id = device_id
        self._attr_device_info = device_info_for(manager, device_id)

    @property
    def available(self) -> bool:
        """Return whether the device is still owned or mirrored here."""
        return self._manager.has_device(self._device_id)

    async def async_added_to_hass(self) -> None:
        """Also write the state when the accepted state of the device changes; the connection ends with the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_DEVICE_STATE.format(self._manager.entry.entry_id, self._device_id),
                self._on_signal,
            )
        )
