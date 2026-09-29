"""
Turns device subentries (Switch and Select) into subscriptions, scripts and discovery.

Known limitation: the MQTT client is shared with Home Assistant and offers this integration no Last Will, so a hard
crash leaves a stale retained "online" availability on the broker. Heartbeat-based availability (deferred requirement
AVL-01) addresses it.
"""

import asyncio
import json
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from .const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    DOMAIN,
    ISSUE_ACTION_FAILED_PREFIX,
    ISSUE_DISCOVERY_DISABLED,
    LOGGER,
    MAX_LOGGED_PAYLOAD_LENGTH,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_PUBLISHED,
    STORE_SAVE_DELAY,
    STORE_VERSION,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from .discovery import AvailabilityState, DiscoveryPublisher
from .model import DeviceSpec, spec_from_subentry, trigger_key
from .mqtt_gateway import IncomingMessage, MqttGateway
from .runner import ActionRunner
from .state import StateTracker
from .topics import state_topic, test_topic

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant


@dataclass
class Device:
    """Runtime state of one device (Switch or Select)."""

    device_id: str
    spec: DeviceSpec
    tracker: StateTracker
    signature: str
    unsubscribe: CALLBACK_TYPE | None = None
    unsubscribe_test: CALLBACK_TYPE | None = None

    @property
    def name(self) -> str:
        """Return the display name of the device."""
        return self.spec.name


def _device_subentries(entry: ConfigEntry) -> list[ConfigSubentry]:
    """Return the device subentries of the hub entry: the Switch subentries followed by the Select subentries."""
    return [*entry.get_subentries_of_type(SUBENTRY_SWITCH), *entry.get_subentries_of_type(SUBENTRY_SELECT)]


def _signature(subentry: ConfigSubentry) -> str:
    """Return a stable fingerprint of what a subentry configures, to tell a real change from an unrelated update."""
    return json.dumps({"title": subentry.title, "data": dict(subentry.data)}, sort_keys=True)


def _parse_published(stored: dict[str, Any]) -> set[str]:
    """Return the published device ids from a loaded Store payload; anything malformed is dropped."""
    published = stored.get(STORE_PUBLISHED)
    return {item for item in published if isinstance(item, str)} if isinstance(published, list) else set()


async def _async_attempt(action: Callable[[], Awaitable[None]], description: str) -> bool:
    """Run one MQTT cleanup step; an unavailable MQTT client is logged and never raised (T-01-14)."""
    try:
        await action()
    except HomeAssistantError as err:
        LOGGER.warning("MQTT could not %s: %s", description, err)
        return False
    return True


async def _async_clear_topics(publisher: DiscoveryPublisher, device_id: str) -> bool:
    """Clear the retained discovery and state topics of a device; True when both were cleared."""
    discovery_cleared = await _async_attempt(
        partial(publisher.async_clear_device, device_id), f"clear the discovery of device {device_id}"
    )
    state_cleared = await _async_attempt(
        partial(publisher.async_clear_state, device_id), f"clear the retained state of device {device_id}"
    )
    return discovery_cleared and state_cleared


async def async_remove_all_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Clear everything this instance published to the broker and forget its local state (D-15).

    Called when the hub config entry is removed, when no manager exists any more. The scope is the ids this instance
    published (persisted set) plus the current subentries, plus its availability topic. Phase 3 must redesign this as a
    confirmed, multi-instance-aware delete: with several instances sharing a broker, removing one hub must not silently
    delete devices other instances still use.
    """
    store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
    stored = await store.async_load() or {}
    device_ids = _parse_published(stored) | {subentry.data[CONF_DEVICE_ID] for subentry in _device_subentries(entry)}
    integration = await async_get_integration(hass, DOMAIN)
    publisher = DiscoveryPublisher(MqttGateway(hass), entry.data[CONF_BASE_TOPIC], str(integration.version))
    for device_id in sorted(device_ids):
        await _async_clear_topics(publisher, device_id)
    await _async_attempt(
        partial(publisher.async_publish_availability, entry.data[CONF_INSTANCE_ID], AvailabilityState.CLEARED),
        "clear the instance availability",
    )
    await store.async_remove()
    registry = ir.async_get(hass)
    for domain, issue_id in list(registry.issues):
        if domain == DOMAIN and (
            issue_id.startswith(ISSUE_ACTION_FAILED_PREFIX) or issue_id == ISSUE_DISCOVERY_DISABLED
        ):
            ir.async_delete_issue(hass, domain, issue_id)


class Manager:
    """Keeps the running devices in line with the device subentries of the hub entry."""

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
        self._running = False

    async def async_start(self) -> None:
        """Load the persisted state, clear orphans, start every configured device and publish availability online."""
        await self._async_load_store()
        integration = await async_get_integration(self._hass, DOMAIN)
        self._publisher = DiscoveryPublisher(self.gateway, self._base_topic, str(integration.version))
        self._running = True
        self._check_discovery_enabled()
        self._entry.async_on_unload(self.gateway.async_subscribe_connection_status(self._on_connection_status))
        current = {subentry.data[CONF_DEVICE_ID] for subentry in _device_subentries(self._entry)}
        self._stored_last_acted = {
            device_id: value for device_id, value in self._stored_last_acted.items() if device_id in current
        }
        await self._async_orphan_cleanup()
        await self.async_reconcile(startup=True)
        await self._async_publish_availability(AvailabilityState.ONLINE)

    async def async_reconcile(self, *, startup: bool = False) -> None:
        """
        Bring the running devices in line with the device subentries: remove, change and add.

        Only devices built while the manager starts (HA start or entry reload) get the startup window; a device the
        user creates later is not a start (D-05).
        """
        async with self._lock:
            # A late update-listener call after async_stop must not revive a manager nobody will ever unsubscribe
            if not self._running:
                return
            subentries = {subentry.data[CONF_DEVICE_ID]: subentry for subentry in _device_subentries(self._entry)}
            for device_id in [device_id for device_id in self.devices if device_id not in subentries]:
                await self._async_remove_device(device_id)
            for device_id, subentry in subentries.items():
                if (device := self.devices.get(device_id)) is None:
                    await self._async_add_device(subentry, startup=startup)
                elif device.signature != _signature(subentry):
                    await self._async_change_device(device, subentry)

    async def async_stop(self) -> None:
        """
        Persist the baseline, unsubscribe, unload scripts and publish availability offline.

        Nothing is deleted on the broker here: an empty payload on a discovery or state topic only happens on an
        explicit device delete or on hub removal (DSC-02). The final save comes first so a slow or failing publish
        cannot cost the baseline.
        """
        async with self._lock:
            self._running = False
            await self._store.async_save(self._data_to_save())
            for device in self.devices.values():
                if device.unsubscribe is not None:
                    device.unsubscribe()
                if device.unsubscribe_test is not None:
                    device.unsubscribe_test()
                await self.runner.async_unload(device.device_id)
            self.devices.clear()
            # Scripts of a device whose start failed halfway are not in self.devices yet
            await self.runner.async_unload_all()
            if self._publisher is not None:  # None when the start failed before the publisher existed
                await self._async_publish_availability(AvailabilityState.OFFLINE)

    @callback
    def _on_connection_status(self, connected: bool) -> None:  # noqa: FBT001
        """Republish after a broker reconnect; the publishes cannot run inside the dispatcher callback."""
        if connected and self._running:
            self._entry.async_create_background_task(self._hass, self._async_republish(), name=f"{DOMAIN} republish")

    async def _async_republish(self) -> None:
        """
        Publish discovery and online availability again (FND-05).

        Idempotent: core MQTT ignores an unchanged retained discovery payload, and a broker that lost its retained
        messages gets them back.
        """
        async with self._lock:
            if not self._running:
                return
            for device in self.devices.values():
                await self._async_publish_discovery(device)
            await self._async_publish_availability(AvailabilityState.ONLINE)

    def _check_discovery_enabled(self) -> None:
        """Warn and raise a Repairs issue when MQTT discovery is disabled, because then no entity ever appears."""
        if self.gateway.discovery_enabled():
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE_DISCOVERY_DISABLED)
            return
        LOGGER.warning("MQTT discovery is disabled, so the switch entities of MQTT Actions cannot appear")
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            ISSUE_DISCOVERY_DISABLED,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_DISCOVERY_DISABLED,
        )

    async def _async_publish_availability(self, state: AvailabilityState) -> None:
        """Publish the retained instance availability; an unavailable MQTT client is logged, never raised."""
        assert self._publisher is not None  # noqa: S101
        await _async_attempt(
            partial(self._publisher.async_publish_availability, self._instance_id, state),
            f"publish the {state.value} availability",
        )

    async def _async_load_store(self) -> None:
        """Load the persisted baseline and published ids; anything malformed is dropped."""
        stored = await self._store.async_load() or {}
        last_acted = stored.get(STORE_LAST_ACTED)
        # Any string is kept here; a device sanitizes its baseline against its own StateValues when it is added (A11)
        self._stored_last_acted = (
            {key: value for key, value in last_acted.items() if isinstance(key, str) and isinstance(value, str)}
            if isinstance(last_acted, dict)
            else {}
        )
        self._published = _parse_published(stored)

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
        spec = spec_from_subentry(subentry)
        stored = self._stored_last_acted.get(device_id)
        device = Device(
            device_id=device_id,
            spec=spec,
            # A stored baseline that is no longer a StateValue of the device is unknown (A11)
            tracker=StateTracker(
                last_acted=stored if stored in spec.accepted.values() else None,
                run_on_startup=spec.run_on_startup,
                startup_pending=startup,
                accepted=spec.accepted,
            ),
            signature=_signature(subentry),
        )
        await self.runner.async_build_device(spec)
        self.devices[device_id] = device
        # Resolve the device from self.devices at message time: binding the object would break after a rebuild
        device.unsubscribe = await self.gateway.async_subscribe(
            state_topic(self._base_topic, device_id),
            partial(self._on_message, device_id),
        )
        device.unsubscribe_test = await self.gateway.async_subscribe(
            test_topic(self._base_topic, device_id),
            partial(self._on_test_message, device_id),
        )
        await self._async_publish_discovery(device)
        self._published.add(device_id)
        self._schedule_save()

    async def _async_change_device(self, device: Device, subentry: ConfigSubentry) -> None:
        """
        Apply a reconfigured subentry: new Scripts, name and flag; the subscription and the baseline stay.

        The Repairs issue is cleared first so a stale setup problem does not outlive the change; invalid new actions
        raise it again while the Scripts are rebuilt. The previous Scripts are unloaded after the new ones exist. A
        baseline that is no longer a StateValue of the device (a removed option) becomes unknown (D-02).
        """
        self.runner.clear_issue(device.device_id)
        spec = spec_from_subentry(subentry)
        await self.runner.async_build_device(spec)
        device.spec = spec
        device.tracker.run_on_startup = spec.run_on_startup
        device.tracker.accepted = spec.accepted
        if device.tracker.last_acted is not None and device.tracker.last_acted not in spec.accepted.values():
            device.tracker.last_acted = None
            self._schedule_save()
        device.signature = _signature(subentry)
        await self._async_publish_discovery(device)

    async def _async_remove_device(self, device_id: str) -> None:
        """
        Remove a deleted device in the order that keeps the manager from reading its own clear message (D-16).

        Discovery goes first so the entity disappears, then the subscription ends, and only then the retained state is
        cleared. A clear that fails keeps the id in the published set so the next start retries it.
        """
        assert self._publisher is not None  # noqa: S101
        device = self.devices[device_id]
        cleared = await _async_attempt(
            partial(self._publisher.async_clear_device, device_id), f"clear the discovery of device {device.name}"
        )
        if device.unsubscribe is not None:
            device.unsubscribe()
        if device.unsubscribe_test is not None:
            device.unsubscribe_test()
        state_cleared = await _async_attempt(
            partial(self._publisher.async_clear_state, device_id), f"clear the retained state of device {device.name}"
        )
        await self.runner.async_unload(device_id, remove_issue=True)
        del self.devices[device_id]
        self._stored_last_acted.pop(device_id, None)
        if cleared and state_cleared:
            self._published.discard(device_id)
        self._schedule_save()

    async def _async_orphan_cleanup(self) -> None:
        """
        Clear the broker topics of devices deleted while this entry was not loaded (for example MQTT down).

        No update listener existed then, so the persisted published set is compared with the current subentries.
        """
        assert self._publisher is not None  # noqa: S101
        current = {subentry.data[CONF_DEVICE_ID] for subentry in _device_subentries(self._entry)}
        for device_id in sorted(self._published - current):
            if await _async_clear_topics(self._publisher, device_id):
                self._published.discard(device_id)
                self._stored_last_acted.pop(device_id, None)
                self._schedule_save()

    async def _async_publish_discovery(self, device: Device) -> None:
        """Publish the retained discovery of a device; an unavailable MQTT client is logged, the next start retries."""
        assert self._publisher is not None  # noqa: S101
        await _async_attempt(
            partial(self._publisher.async_publish_device, spec=device.spec, instance_id=self._instance_id),
            f"publish the discovery of device {device.name}",
        )

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
        assert decision.value is not None  # noqa: S101
        trigger = device.spec.triggers.get(trigger_key(decision.value))
        if trigger is None or not self.runner.can_run(device_id, trigger.key):
            return
        # Only the device id and the canonical value reach templates, never the raw payload
        self.runner.enqueue(
            device_id,
            device.name,
            trigger.label,
            trigger.key,
            {"device_id": device_id, "state": decision.value},
        )

    @callback
    def _on_test_message(self, device_id: str, msg: IncomingMessage) -> None:
        """
        Run the actions of the trigger whose test button was pressed (D-13).

        The press never touches the tracker, the baseline or the state topic, and nothing is published. A retained
        message is a replay, never a press, so it must not run actions (T-02-09). Only a payload that equals a
        StateValue of the device runs anything (T-02-08).
        """
        if msg.retain or (device := self.devices.get(device_id)) is None:
            return
        value = device.spec.accepted.get(msg.payload.strip().lower())
        if value is None:
            self._log_ignored(device, msg.payload)
            return
        trigger = device.spec.triggers.get(trigger_key(value))
        if trigger is None or not self.runner.can_run(device_id, trigger.key):
            return
        self.runner.enqueue(
            device_id,
            device.name,
            trigger.label,
            trigger.key,
            {"device_id": device_id, "state": value},
            test=True,
        )

    @staticmethod
    def _log_ignored(device: Device, payload: str) -> None:
        """Log an unknown payload; the empty retained-clear message is only debug noise (D-02)."""
        if not payload:
            LOGGER.debug("Ignoring empty payload for device %s", device.name)
            return
        shown = repr(payload[:MAX_LOGGED_PAYLOAD_LENGTH]) + ("..." if len(payload) > MAX_LOGGED_PAYLOAD_LENGTH else "")
        LOGGER.warning("Ignoring unknown payload %s for device %s", shown, device.name)
