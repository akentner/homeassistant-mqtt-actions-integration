"""Turns switch subentries into subscriptions, scripts and discovery."""

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.loader import async_get_integration

from .actions import ActionsInvalid
from .const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_RUN_ON_STARTUP,
    DOMAIN,
    LOGGER,
    PAYLOAD_ON,
    SUBENTRY_SWITCH,
)
from .discovery import DiscoveryPublisher
from .mqtt_gateway import IncomingMessage, MqttGateway
from .runner import ActionRunner
from .state import decide
from .topics import state_topic

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.script import Script


@dataclass
class Device:
    """Runtime state of one switch device."""

    device_id: str
    name: str
    run_on_startup: bool
    on_script: Script | None
    off_script: Script | None
    unsubscribe: CALLBACK_TYPE | None = None
    last_acted: str | None = None
    startup_pending: bool = True


class Manager:
    """Keeps the running devices in line with the switch subentries of the hub entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the manager."""
        self._hass = hass
        self._entry = entry
        self._base_topic: str = entry.data[CONF_BASE_TOPIC]
        self._instance_id: str = entry.data[CONF_INSTANCE_ID]
        self._lock = asyncio.Lock()
        self.gateway = MqttGateway(hass)
        self.runner = ActionRunner(hass, entry)
        self.devices: dict[str, Device] = {}
        self._publisher: DiscoveryPublisher | None = None

    async def async_start(self) -> None:
        """Publish availability and start every configured device."""
        integration = await async_get_integration(self._hass, DOMAIN)
        self._publisher = DiscoveryPublisher(self.gateway, self._base_topic, str(integration.version))
        await self._publisher.async_publish_availability(self._instance_id, online=True)
        await self.async_reconcile()

    async def async_reconcile(self) -> None:
        """Add devices for new switch subentries; change and removal handling follows in a later plan."""
        async with self._lock:
            for subentry in self._entry.get_subentries_of_type(SUBENTRY_SWITCH):
                if subentry.data[CONF_DEVICE_ID] not in self.devices:
                    await self._async_add_device(subentry)

    async def async_stop(self) -> None:
        """Unsubscribe and unload scripts. Discovery is never cleared here."""
        async with self._lock:
            for device in self.devices.values():
                if device.unsubscribe is not None:
                    device.unsubscribe()
                for script in (device.on_script, device.off_script):
                    if script is not None:
                        await script.async_unload()
            self.devices.clear()

    async def _async_add_device(self, subentry: ConfigSubentry) -> None:
        """Build scripts, subscribe to the state topic and publish discovery for one device."""
        assert self._publisher is not None  # noqa: S101
        device_id: str = subentry.data[CONF_DEVICE_ID]
        device = Device(
            device_id=device_id,
            name=subentry.title,
            run_on_startup=subentry.data[CONF_RUN_ON_STARTUP],
            on_script=await self._async_build(subentry, CONF_ON_CHANGE_TO_ON),
            off_script=await self._async_build(subentry, CONF_ON_CHANGE_TO_OFF),
        )
        self.devices[device_id] = device
        # Resolve the device from self.devices at message time: binding the object would break after a rebuild
        device.unsubscribe = await self.gateway.async_subscribe(
            state_topic(self._base_topic, device_id),
            partial(self._on_message, device_id),
        )
        await self._publisher.async_publish_device(device_id=device_id, name=device.name, instance_id=self._instance_id)

    async def _async_build(self, subentry: ConfigSubentry, key: str) -> Script | None:
        """Build the script for one trigger; invalid stored actions are logged and skipped."""
        try:
            return await self.runner.async_build_script(f"{subentry.title} {key}", subentry.data[key])
        except ActionsInvalid:
            LOGGER.exception("Invalid actions for %s of device %s", key, subentry.title)
            return None

    @callback
    def _on_message(self, device_id: str, msg: IncomingMessage) -> None:
        """Handle a state message: separate baseline from edge and enqueue the matching script."""
        if (device := self.devices.get(device_id)) is None:
            return
        decision = decide(msg.retain, msg.payload, device.last_acted, device.startup_pending, device.run_on_startup)
        device.startup_pending = False
        if decision.ignored:
            LOGGER.debug("Ignoring unknown payload for device %s", device_id)
            return
        device.last_acted = decision.baseline
        if not decision.act:
            return
        script = device.on_script if decision.value == PAYLOAD_ON else device.off_script
        if script is None:
            return
        # Only the device id and the normalised value reach templates, never the raw payload
        self.runner.enqueue(script, {"device_id": device_id, "state": decision.value})
