"""Turns switch subentries into subscriptions, scripts and discovery."""

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.storage import Store
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
    MAX_ISSUE_ERROR_LENGTH,
    MAX_LOGGED_PAYLOAD_LENGTH,
    PAYLOAD_OFF,
    PAYLOAD_ON,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_PUBLISHED,
    STORE_SAVE_DELAY,
    STORE_VERSION,
    SUBENTRY_SWITCH,
    TRIGGER_OFF,
    TRIGGER_ON,
    TRIGGER_SETUP,
)
from .discovery import DiscoveryPublisher
from .mqtt_gateway import IncomingMessage, MqttGateway
from .runner import ActionRunner
from .state import StateTracker
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
    tracker: StateTracker
    on_script: Script | None
    off_script: Script | None
    unsubscribe: CALLBACK_TYPE | None = None


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
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._stored_last_acted: dict[str, str] = {}
        self._published: set[str] = set()

    async def async_start(self) -> None:
        """Load the persisted state, publish availability and start every configured device."""
        await self._async_load_store()
        integration = await async_get_integration(self._hass, DOMAIN)
        self._publisher = DiscoveryPublisher(self.gateway, self._base_topic, str(integration.version))
        await self._publisher.async_publish_availability(self._instance_id, online=True)
        await self.async_reconcile(startup=True)

    async def async_reconcile(self, *, startup: bool = False) -> None:
        """
        Add devices for new switch subentries; change and removal handling follows in a later plan.

        Only devices built while the manager starts (HA start or entry reload) get the startup window; a device the
        user creates later is not a start (D-05).
        """
        async with self._lock:
            for subentry in self._entry.get_subentries_of_type(SUBENTRY_SWITCH):
                if subentry.data[CONF_DEVICE_ID] not in self.devices:
                    await self._async_add_device(subentry, startup=startup)

    async def async_stop(self) -> None:
        """Persist the baseline, unsubscribe and unload scripts. Discovery is never cleared here."""
        async with self._lock:
            await self._store.async_save(self._data_to_save())
            for device in self.devices.values():
                if device.unsubscribe is not None:
                    device.unsubscribe()
                await self.runner.async_unload(device.device_id)
            self.devices.clear()

    async def _async_load_store(self) -> None:
        """Load the persisted baseline and published ids; anything malformed is dropped."""
        stored = await self._store.async_load() or {}
        last_acted = stored.get(STORE_LAST_ACTED)
        self._stored_last_acted = (
            {key: value for key, value in last_acted.items() if value in {PAYLOAD_ON, PAYLOAD_OFF}}
            if isinstance(last_acted, dict)
            else {}
        )
        published = stored.get(STORE_PUBLISHED)
        self._published = (
            {item for item in published if isinstance(item, str)} if isinstance(published, list) else set()
        )

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return the persisted state; devices without a baseline are omitted (D-07)."""
        return {
            STORE_LAST_ACTED: {
                device_id: device.tracker.last_acted
                for device_id, device in self.devices.items()
                if device.tracker.last_acted is not None
            },
            STORE_PUBLISHED: sorted(self._published),
        }

    @callback
    def _schedule_save(self) -> None:
        """Save with a delay so a burst of messages causes one write."""
        self._store.async_delay_save(self._data_to_save, STORE_SAVE_DELAY)

    async def _async_add_device(self, subentry: ConfigSubentry, *, startup: bool) -> None:
        """Build scripts, subscribe to the state topic and publish discovery for one device."""
        assert self._publisher is not None  # noqa: S101
        device_id: str = subentry.data[CONF_DEVICE_ID]
        device = Device(
            device_id=device_id,
            name=subentry.title,
            tracker=StateTracker(
                last_acted=self._stored_last_acted.get(device_id),
                run_on_startup=subentry.data[CONF_RUN_ON_STARTUP],
                startup_pending=startup,
            ),
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
        self._published.add(device_id)
        self._schedule_save()

    async def _async_build(self, subentry: ConfigSubentry, key: str) -> Script | None:
        """
        Build the script for one trigger.

        Invalid stored actions are logged and shown in Repairs (trigger setup); that transition then has no script while
        the other one and the baseline tracking keep working. Reconfiguring the device rebuilds it.
        """
        device_id: str = subentry.data[CONF_DEVICE_ID]
        try:
            return await self.runner.async_build_script(device_id, f"{subentry.title} {key}", subentry.data[key])
        except ActionsInvalid as err:
            error = str(err)[:MAX_ISSUE_ERROR_LENGTH]
            LOGGER.error("Invalid actions for %s of device %s: %s", key, subentry.title, error)
            self.runner.report_failure(device_id, subentry.title, TRIGGER_SETUP, error)
            return None

    @callback
    def _on_message(self, device_id: str, msg: IncomingMessage) -> None:
        """Handle a state message: separate baseline from edge and enqueue the matching script."""
        if (device := self.devices.get(device_id)) is None:
            return
        previous = device.tracker.last_acted
        decision = device.tracker.handle(msg.retain, msg.payload)
        if decision.ignored:
            self._log_ignored(device, msg.payload)
            return
        if device.tracker.last_acted != previous:
            self._schedule_save()
        if not decision.act:
            return
        is_on = decision.value == PAYLOAD_ON
        script = device.on_script if is_on else device.off_script
        if script is None:
            return
        # Only the device id and the normalised value reach templates, never the raw payload
        self.runner.enqueue(
            device_id,
            device.name,
            TRIGGER_ON if is_on else TRIGGER_OFF,
            script,
            {"device_id": device_id, "state": decision.value},
        )

    @staticmethod
    def _log_ignored(device: Device, payload: str) -> None:
        """Log an unknown payload; the empty retained-clear message is only debug noise (D-02)."""
        if not payload:
            LOGGER.debug("Ignoring empty payload for device %s", device.name)
            return
        shown = repr(payload[:MAX_LOGGED_PAYLOAD_LENGTH]) + ("..." if len(payload) > MAX_LOGGED_PAYLOAD_LENGTH else "")
        LOGGER.warning("Ignoring unknown payload %s for device %s", shown, device.name)
