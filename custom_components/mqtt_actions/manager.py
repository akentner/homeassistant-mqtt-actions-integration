"""
Turns device subentries (Switch and Select) into subscriptions, scripts and discovery.

Known limitation: the MQTT client is shared with Home Assistant and offers this integration no Last Will, so a hard
crash leaves a stale retained "online" availability on the broker. Heartbeat-based availability (deferred requirement
AVL-01) addresses it.
"""

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_RESTORED
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from . import takeover
from .actions import ActionsInvalid, async_validate_actions, validate_spec_structure
from .breaker import CircuitBreaker
from .const import (
    ADOPT_NOT_A_MIRROR,
    ADOPT_NOT_APPROVED,
    ADOPT_OWNER_NOT_OFFLINE,
    APPROVAL_HASH_PREFIX_LENGTH,
    BLOCKED_SERVICES_MAX_SHOWN,
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    DOMAIN,
    ISSUE_APPROVAL_PREFIX,
    ISSUE_BLOCKED_PREFIX,
    ISSUE_CIRCUIT_BREAKER_PREFIX,
    ISSUE_DENIED_CALL_PREFIX,
    ISSUE_DEVICE_PREFIXES,
    ISSUE_DISCOVERY_DISABLED,
    ISSUE_DUPLICATE_INSTANCE_ID,
    LOGGER,
    MAX_LOGGED_PAYLOAD_LENGTH,
    MAX_MIRRORS,
    MAX_TRANSFER_HISTORY,
    MODE_DISABLED,
    MODE_OBSERVE,
    MODE_RUN,
    RESYNC_MIN_INTERVAL_SECONDS,
    SIGNAL_DEVICE_STATE,
    SIGNAL_DEVICES_CHANGED,
    SIGNAL_MODES_CHANGED,
    STORE_APPROVALS,
    STORE_DEVICE_MODES,
    STORE_INSTANCE_MODE,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_MIRRORS,
    STORE_NATIVE,
    STORE_PUBLISHED,
    STORE_REVS,
    STORE_SAVE_DELAY,
    STORE_TRANSFERS,
    STORE_TRIPPED,
    STORE_VERSION,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from .discovery import AvailabilityState, DiscoveryPublisher, button_component_key
from .document import (
    DocumentRejectedError,
    analyze_spec,
    approval_sections,
    build_content,
    build_document,
    canonical_json,
    escape_markdown,
    parse_document,
    serialize_document,
    spec_has_actions,
    with_native_marker,
)
from .entities import device_info_for
from .model import DeviceSpec, TriggerSpec, shown, spec_from_subentry, trigger_key
from .modes import is_mode, most_restrictive
from .mqtt_gateway import IncomingMessage, MqttGateway
from .portability import subentry_payload
from .presence import PresenceManager
from .retrigger import RetriggerCoordinator
from .runner import ActionRunner
from .state import StateTracker
from .sync import SyncManager
from .topics import is_valid_device_id, state_topic, test_topic
from .trust import ApprovalState, build_approval_view

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from .document import ActionAnalysis, ParsedDocument
    from .trust import ApprovalView


@dataclass(frozen=True, slots=True)
class MirrorInfo:
    """
    What a follower knows about the owner of a mirrored device and the document it was built from (D-08).

    `denied`, `templated` and `residual` are the static analysis of the actions (A6): they are recorded, never a reason
    to drop the document, and the approval view of a later plan shows them.
    """

    owner: str
    owner_name: str
    rev: int
    content_hash: str
    actions_hash: str
    # The received document text; parsed again at every load, the stored hashes are never trusted (T-03-19)
    payload: str
    denied: tuple[str, ...] = ()
    templated: tuple[str, ...] = ()
    residual: tuple[str, ...] = ()
    # The previous owners the document names when the device was adopted, newest last (D-09)
    transferred_from: tuple[str, ...] = ()
    # True when the pinned owner marked its document as one of native entities; the mirror is then a native entity here
    native: bool = False


class AdoptionError(Exception):
    """
    An adoption was refused before anything changed (D-10).

    `reason` is one of the ADOPT_* codes of the constants; `owner_name` is the name the current owner announced, for the
    message of the service, and is None when there is no mirror to speak of.
    """

    def __init__(self, reason: str, owner_name: str | None = None) -> None:
        """Remember the reason code and the owner name; the message is the code."""
        super().__init__(reason)
        self.reason = reason
        self.owner_name = owner_name


# The content hash recorded for an adopted device before its first publish: it can never equal a sha256 hex digest, so
# the first publish of the adopter always counts as a change and publishes the old rev plus one (D-09)
ADOPTED_HASH = "adopted"


@dataclass
class Device:
    """Runtime state of one device (Switch or Select), owned here or mirrored from another instance."""

    device_id: str
    spec: DeviceSpec
    tracker: StateTracker
    signature: str
    breaker: CircuitBreaker
    unsubscribe: CALLBACK_TYPE | None = None
    unsubscribe_test: CALLBACK_TYPE | None = None
    # Button component keys of removed triggers; kept in memory so every republish carries their tombstone
    retired_components: set[str] = field(default_factory=set)
    # Set for a mirror of a foreign device, None for an owned device
    mirror: MirrorInfo | None = None
    # The last accepted canonical StateValue of the state topic, None until one arrived; what a native entity shows
    value: str | None = None

    @property
    def name(self) -> str:
        """Return the display name of the device."""
        return self.spec.name


def _device_subentries(entry: ConfigEntry) -> list[ConfigSubentry]:
    """Return the device subentries of the hub entry: the Switch subentries followed by the Select subentries."""
    return [*entry.get_subentries_of_type(SUBENTRY_SWITCH), *entry.get_subentries_of_type(SUBENTRY_SELECT)]


def _fingerprint(title: str, data: Mapping[str, Any]) -> str:
    """Return the stable fingerprint of a device configuration; the one place that decides what a change is."""
    return json.dumps({"title": title, "data": dict(data)}, sort_keys=True)


def _signature(subentry: ConfigSubentry) -> str:
    """Return a stable fingerprint of what a subentry configures, to tell a real change from an unrelated update."""
    return _fingerprint(subentry.title, subentry.data)


def _hash_fingerprint(fingerprint: str) -> str:
    return hashlib.sha256(fingerprint.encode()).hexdigest()


def signature_hash(title: str, data: Mapping[str, Any]) -> str:
    """Return the sha256 hex digest of the fingerprint of a device configuration; persisted with a tripped breaker."""
    return _hash_fingerprint(_fingerprint(title, data))


def _parse_published(stored: dict[str, Any]) -> set[str]:
    """Return the published device ids from a loaded Store payload; anything malformed is dropped."""
    published = stored.get(STORE_PUBLISHED)
    return {item for item in published if isinstance(item, str)} if isinstance(published, list) else set()


def _parse_tripped(stored: dict[str, Any]) -> dict[str, str]:
    """Return the tripped device ids with their config hash from a loaded Store payload; malformed data is dropped."""
    tripped = stored.get(STORE_TRIPPED)
    if not isinstance(tripped, dict):
        return {}
    return {key: value for key, value in tripped.items() if isinstance(key, str) and isinstance(value, str)}


def _parse_revs(stored: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the published rev and content hash per device from a loaded Store payload; malformed data is dropped."""
    revs = stored.get(STORE_REVS)
    if not isinstance(revs, dict):
        return {}
    return {
        key: {"rev": value["rev"], "hash": value["hash"]}
        for key, value in revs.items()
        if isinstance(key, str)
        and isinstance(value, dict)
        and isinstance(value.get("rev"), int)
        and not isinstance(value.get("rev"), bool)
        and isinstance(value.get("hash"), str)
    }


def _parse_transfers(stored: dict[str, Any]) -> dict[str, list[str]]:
    """Return the previous owners per adopted device from a loaded Store payload; anything malformed is dropped."""
    transfers = stored.get(STORE_TRANSFERS)
    if not isinstance(transfers, dict):
        return {}
    return {
        key: list(value)
        for key, value in transfers.items()
        if isinstance(key, str)
        and isinstance(value, list)
        and 0 < len(value) <= MAX_TRANSFER_HISTORY
        and all(isinstance(item, str) and is_valid_device_id(item) for item in value)
    }


def _parse_approvals(stored: dict[str, Any]) -> dict[str, str]:
    """Return the approved actions hash per device from a loaded Store payload; anything malformed is dropped."""
    approvals = stored.get(STORE_APPROVALS)
    if not isinstance(approvals, dict):
        return {}
    return {key: value for key, value in approvals.items() if isinstance(key, str) and isinstance(value, str)}


def _parse_instance_mode(stored: dict[str, Any]) -> str:
    """Return the instance mode from a loaded Store payload; anything that is not a mode word becomes run (D-14)."""
    mode = stored.get(STORE_INSTANCE_MODE)
    return mode if is_mode(mode) else MODE_RUN


def _parse_device_modes(stored: dict[str, Any]) -> dict[str, str]:
    """Return the device modes from a loaded Store payload; a malformed entry and a run entry are dropped (D-14)."""
    modes = stored.get(STORE_DEVICE_MODES)
    if not isinstance(modes, dict):
        return {}
    return {key: value for key, value in modes.items() if isinstance(key, str) and is_mode(value) and value != MODE_RUN}


def _parse_mirrors(stored: dict[str, Any]) -> dict[str, ParsedDocument]:
    """
    Return the cached mirrors of a loaded Store payload; every payload is parsed and structure-checked again (T-03-19).

    A malformed container, a non-string entry, a payload that no longer parses, names another device than its key or has
    invalid actions is dropped; nothing in the Store is trusted, not even the hashes. At most MAX_MIRRORS are kept.
    """
    cached = stored.get(STORE_MIRRORS)
    if not isinstance(cached, dict):
        return {}
    mirrors: dict[str, ParsedDocument] = {}
    for device_id, payload in cached.items():
        if len(mirrors) >= MAX_MIRRORS:
            break
        if not isinstance(device_id, str) or not isinstance(payload, str):
            continue
        try:
            parsed = parse_document(device_id, payload)
            validate_spec_structure(parsed.spec)
            analyze_spec(parsed.spec)
        except Exception:  # noqa: BLE001 - a cached payload is untrusted input; whatever it raises, it is dropped
            LOGGER.debug("A cached mirror of device %r was dropped because it is not valid", device_id[:40])
            continue
        mirrors[device_id] = parsed
    return mirrors


@dataclass(slots=True)
class NativeState:
    """The persisted native switch of this instance (D-03): the instance flag and two sets of owned device ids."""

    instance: bool = False
    pending: set[str] = field(default_factory=set)
    devices: set[str] = field(default_factory=set)


def _parse_native(stored: dict[str, Any]) -> NativeState:
    """Return the native state from a loaded Store payload; anything malformed means the defaults (D-03)."""
    native = stored.get(STORE_NATIVE)
    if not isinstance(native, dict):
        return NativeState()
    instance = native.get("instance")
    pending = native.get("pending")
    devices = native.get("devices")
    return NativeState(
        instance=instance if isinstance(instance, bool) else False,
        pending={item for item in pending if isinstance(item, str) and is_valid_device_id(item)}
        if isinstance(pending, list)
        else set(),
        devices={item for item in devices if isinstance(item, str) and is_valid_device_id(item)}
        if isinstance(devices, list)
        else set(),
    )


async def _async_attempt(action: Callable[[], Awaitable[None]], description: str) -> bool:
    """Run one MQTT cleanup step; an unavailable MQTT client is logged and never raised (T-01-14)."""
    try:
        await action()
    except HomeAssistantError as err:
        LOGGER.warning("MQTT could not %s: %s", description, err)
        return False
    return True


async def _async_clear_topics(publisher: DiscoveryPublisher, device_id: str) -> bool:
    """
    Clear the retained discovery, config and state topics of a device in that order; True when all were cleared.

    The empty config payload is the tombstone that tells followers the device is gone (D-16).
    """
    discovery_cleared = await _async_attempt(
        partial(publisher.async_clear_device, device_id), f"clear the discovery of device {device_id}"
    )
    config_cleared = await _async_attempt(
        partial(publisher.async_clear_config, device_id), f"clear the config document of device {device_id}"
    )
    state_cleared = await _async_attempt(
        partial(publisher.async_clear_state, device_id), f"clear the retained state of device {device_id}"
    )
    return discovery_cleared and config_cleared and state_cleared


async def async_remove_local_state(hass: HomeAssistant, entry: ConfigEntry, *, store_key: str = STORE_KEY) -> None:  # noqa: ARG001
    """
    Forget everything this instance keeps locally: the Store and every integration issue (D-11).

    Both hub removal modes end here; nothing is published. `store_key` is a test seam like the Manager constructor
    parameters: production passes nothing.
    """
    await Store(hass, STORE_VERSION, store_key).async_remove()
    registry = ir.async_get(hass)
    for domain, issue_id in list(registry.issues):
        if domain == DOMAIN and (
            issue_id.startswith(ISSUE_DEVICE_PREFIXES)
            or issue_id in {ISSUE_DISCOVERY_DISABLED, ISSUE_DUPLICATE_INSTANCE_ID}
        ):
            ir.async_delete_issue(hass, domain, issue_id)


async def async_remove_all_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    gateway: MqttGateway | None = None,
    store_key: str = STORE_KEY,
) -> None:
    """
    Delete-everywhere mode of the hub removal (D-11): clear everything this instance published and forget local state.

    Only used when the user chose deletion in the hub options before removing the hub; the default keeps every device
    retained on the broker. Called when no manager exists any more. The scope is the ids this instance published
    (persisted set) plus the current subentries, plus its availability topic; the local state goes last. `gateway` and
    `store_key` are test seams: production passes neither.
    """
    store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, store_key)
    stored = await store.async_load() or {}
    device_ids = _parse_published(stored) | {subentry.data[CONF_DEVICE_ID] for subentry in _device_subentries(entry)}
    integration = await async_get_integration(hass, DOMAIN)
    publisher = DiscoveryPublisher(
        gateway if gateway is not None else MqttGateway(hass), entry.data[CONF_BASE_TOPIC], str(integration.version)
    )
    for device_id in sorted(device_ids):
        await _async_clear_topics(publisher, device_id)
    await _async_attempt(
        partial(publisher.async_publish_availability, entry.data[CONF_INSTANCE_ID], AvailabilityState.CLEARED),
        "clear the instance availability",
    )
    await async_remove_local_state(hass, entry, store_key=store_key)


class Manager:
    """Keeps the running devices in line with the device subentries of the hub entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        gateway: MqttGateway | None = None,
        store_key: str = STORE_KEY,
    ) -> None:
        """
        Initialize the manager.

        The gateway and the store key are injectable so tests can run several managers against a fake broker; the
        production defaults are the MQTT gateway and the shared store key.
        """
        self._hass = hass
        self._entry = entry
        self._base_topic: str = entry.data[CONF_BASE_TOPIC]
        self._instance_id: str = entry.data[CONF_INSTANCE_ID]
        self._lock = asyncio.Lock()
        self.gateway = gateway if gateway is not None else MqttGateway(hass)
        self.runner = ActionRunner(hass, entry)
        self.devices: dict[str, Device] = {}
        # Read-only mirrors of devices other instances own; never in `devices`, never a subentry (D-08)
        self.mirrors: dict[str, Device] = {}
        # Cached mirrors parsed from the Store at load, consumed when the start restores them
        self._stored_mirrors: dict[str, ParsedDocument] = {}
        # mirror id -> the actions hash the user approved here; a mirror runs only while its hash equals this (D-02)
        self._approvals: dict[str, str] = {}
        self._publisher: DiscoveryPublisher | None = None
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, store_key)
        self._stored_last_acted: dict[str, str] = {}
        self._published: set[str] = set()
        # device id -> config hash at the time its breaker tripped; the counting window is never stored (D-17)
        self._tripped: dict[str, str] = {}
        # device id -> the rev last published and the content hash it belongs to (D-15)
        self._revs: dict[str, dict[str, Any]] = {}
        # adopted device id -> the ids of its previous owners, newest last; written into every document of the device
        self._transfers: dict[str, list[str]] = {}
        # Device ids that are being released locally; the reconcile ignores their subentries until all are removed, so
        # the reconcile that every subentry removal triggers cannot add a released device again (D-08, T-04-56)
        self._releasing: set[str] = set()
        # Released device ids whose baseline is still kept in `_stored_last_acted` for the mirror that follows
        self._released: set[str] = set()
        # Set after a duplicate id fix: the next stop publishes no offline availability for the id the original shares
        self._skip_offline_once = False
        self._running = False
        # Owned device ids whose document the parser rejects; logged once, not published (CR-03)
        self._unpublishable: set[str] = set()
        # Replaceable so tests control the breaker window; production uses the monotonic clock
        self.clock: Callable[[], float] = time.monotonic
        self.sync = SyncManager(self)
        self.presence = PresenceManager(self)
        self.retrigger = RetriggerCoordinator(self)
        # The integration version, read at the start; announced in the heartbeat
        self._version = ""
        # When the last accepted resync happened on `clock`; None until the first one (D-12)
        self._last_resync: float | None = None
        # The mode of this instance and the modes of single devices, only entries other than run; local to this
        # instance, kept in the Store and never part of a document or a hash (D-14)
        self._instance_mode = MODE_RUN
        self._device_modes: dict[str, str] = {}
        # Which owned devices are native entities instead of MQTT discovery entities; local, kept in the Store (D-03)
        self._native = NativeState()
        # Owned or mirrored devices whose takeover could not run yet; they use the legacy path for this run only and
        # their id stays pending in the Store, so the next setup retries (T-5-08)
        self._legacy_this_run: set[str] = set()

    @property
    def _native_pending(self) -> set[str]:
        """Return the owned device ids that still wait for the takeover pass; the persisted set itself, not a copy."""
        return self._native.pending

    @property
    def _native_devices(self) -> set[str]:
        """Return the owned device ids that are native although the instance flag is not set; the persisted set."""
        return self._native.devices

    @property
    def hass(self) -> HomeAssistant:
        """Return the Home Assistant instance."""
        return self._hass

    @property
    def entry(self) -> ConfigEntry:
        """Return the hub config entry."""
        return self._entry

    @property
    def base_topic(self) -> str:
        """Return the base topic of this hub."""
        return self._base_topic

    @property
    def instance_id(self) -> str:
        """Return the id of this instance, the owner written into every document it publishes."""
        return self._instance_id

    @property
    def instance_name(self) -> str:
        """Return the display name of this instance."""
        return str(self._entry.data[CONF_INSTANCE_NAME])

    @property
    def version(self) -> str:
        """Return the version of this integration as read from its manifest at the start."""
        return self._version

    @property
    def lock(self) -> asyncio.Lock:
        """Return the lock that serializes reconcile, start, stop and every publish of owned state."""
        return self._lock

    @property
    def running(self) -> bool:
        """Return whether the manager is started and not stopped."""
        return self._running

    def online_instance_count(self) -> int:
        """Return how many other instances are currently online, as announced on the availability topics."""
        return self.sync.online_instance_count()

    def revision(self, device_id: str) -> int:
        """Return the rev last published for a device, 0 when none was published yet."""
        known = self._revs.get(device_id)
        return 0 if known is None else int(known["rev"])

    @property
    def instance_mode(self) -> str:
        """Return the mode of the whole instance (D-14)."""
        return self._instance_mode

    def device_mode(self, device_id: str) -> str:
        """Return the mode of one device itself, run when none is stored (D-14)."""
        return self._device_modes.get(device_id, MODE_RUN)

    def effective_mode(self, device_id: str) -> str:
        """Return the mode that counts for a device: the most restrictive of the instance and the device (D-14)."""
        return most_restrictive(self._instance_mode, self.device_mode(device_id))

    def subentry_id_of(self, device_id: str) -> str | None:
        """Return the id of the subentry of an owned device, None for a mirror or an unknown id (D-13)."""
        for subentry in _device_subentries(self._entry):
            if subentry.data[CONF_DEVICE_ID] == device_id:
                return subentry.subentry_id
        return None

    def is_native(self, device_id: str) -> bool:
        """
        Return whether a device is a native entity of this integration instead of an MQTT discovery entity (D-03).

        True for an owned device that is listed as native or while the instance flag is set, and for a mirror whose
        pinned owner marked its document as native (D-07, D-09); False for an unknown id. A device that still waits for
        the takeover pass, or whose takeover was deferred for this run, is not native: its legacy entities exist, so a
        native one next to them would be a duplicate (T-5-08).
        """
        if device_id in self._legacy_this_run:
            return False
        if (mirror := self.mirrors.get(device_id)) is not None:
            return mirror.mirror is not None and mirror.mirror.native
        return (
            device_id in self.devices
            and device_id not in self._native_pending
            and (self._native.instance or device_id in self._native_devices)
        )

    def has_device(self, device_id: str) -> bool:
        """Return whether the id belongs to an owned device or a mirror."""
        return self._device(device_id) is not None

    def device(self, device_id: str) -> Device | None:
        """Return the owned device or the mirror with this id, None for an unknown id."""
        return self._device(device_id)

    async def async_set_device_mode(self, device_id: str, mode: str) -> None:
        """
        Set the mode of one owned or mirrored device; local only, nothing is published (D-14, T-04-21).

        Raises ValueError for a word that is no mode and for an id that is neither owned nor mirrored. Run removes the
        entry, so the Store only holds the deviations. A device that leaves disabled starts from a clean baseline.
        """
        if not is_mode(mode):
            msg = "Not a mode"
            raise ValueError(msg)
        if self._device(device_id) is None:
            msg = "Unknown device"
            raise ValueError(msg)
        await self._async_change_mode(partial(self._store_device_mode, device_id, mode))

    async def async_set_instance_mode(self, mode: str) -> None:
        """
        Set the mode of the whole instance; local only, nothing is published (D-14, T-04-21).

        Raises ValueError for a word that is no mode. Every device whose effective mode leaves disabled because of it
        starts from a clean baseline; a device that is disabled on its own stays disabled.
        """
        if not is_mode(mode):
            msg = "Not a mode"
            raise ValueError(msg)
        await self._async_change_mode(partial(self._store_instance_mode, mode))

    def _store_device_mode(self, device_id: str, mode: str) -> None:
        if mode == MODE_RUN:
            self._device_modes.pop(device_id, None)
        else:
            self._device_modes[device_id] = mode

    def _store_instance_mode(self, mode: str) -> None:
        self._instance_mode = mode

    async def _async_change_mode(self, apply: Callable[[], None]) -> None:
        """
        Apply a mode change, save it, tell the selects and re-baseline every device that left disabled (D-14, A17).

        The effective mode of each device is read before and after, so one change decides for the hub mode and the
        device mode alike which devices were disabled and no longer are; `_async_rebaseline` handles each of them.
        """
        before = {device_id: self.effective_mode(device_id) for device_id in [*self.devices, *self.mirrors]}
        apply()
        self._schedule_save()
        async_dispatcher_send(self._hass, SIGNAL_MODES_CHANGED.format(self._entry.entry_id))
        released = [
            device_id
            for device_id, mode in before.items()
            if mode == MODE_DISABLED and self.effective_mode(device_id) != MODE_DISABLED
        ]
        if not released:
            return
        async with self._lock:
            for device_id in released:
                if self._running and (device := self._device(device_id)) is not None:
                    await self._async_rebaseline(device)

    async def _async_rebaseline(self, device: Device) -> None:
        """
        Forget the baseline of a device that left disabled and let the broker replay its retained state (A17).

        What the state topic did while the device was disabled was never processed, so the old baseline is stale. The
        baseline and the startup window are cleared, and the state topic is subscribed again: the retained value comes
        back as a replay, which moves the baseline and never runs anything. With nothing retained the first live
        message counts as a real change, like for a new device. The caller holds the lock.
        """
        device_id = device.device_id
        device.tracker.last_acted = None
        device.tracker.startup_pending = False
        self._stored_last_acted.pop(device_id, None)
        self._schedule_save()
        if device.unsubscribe is not None:
            device.unsubscribe()
            device.unsubscribe = None
        try:
            device.unsubscribe = await self.gateway.async_subscribe(
                state_topic(self._base_topic, device_id), partial(self._on_message, device_id)
            )
        except HomeAssistantError as err:
            LOGGER.warning("MQTT could not subscribe to the state of device %s again: %s", device.name, err)

    @callback
    def _notify_devices_changed(self) -> None:
        """Tell the select platform that an owned device appeared or disappeared (D-15)."""
        async_dispatcher_send(self._hass, SIGNAL_DEVICES_CHANGED.format(self._entry.entry_id))

    async def async_start(self) -> None:
        """Load the persisted state, clear orphans, start every configured device and publish availability online."""
        await self._async_load_store()
        integration = await async_get_integration(self._hass, DOMAIN)
        self._version = str(integration.version)
        self._publisher = DiscoveryPublisher(self.gateway, self._base_topic, self._version)
        self._running = True
        self._check_discovery_enabled()
        self._entry.async_on_unload(self.gateway.async_subscribe_connection_status(self._on_connection_status))
        current = {subentry.data[CONF_DEVICE_ID] for subentry in _device_subentries(self._entry)}
        # Cached mirrors exist before the broker replays anything, so a restart never loses a mirror (SYN-02)
        await self._async_restore_mirrors(current)
        kept = current | self.mirrors.keys()
        self._stored_last_acted = {
            device_id: value for device_id, value in self._stored_last_acted.items() if device_id in kept
        }
        self._tripped = {device_id: value for device_id, value in self._tripped.items() if device_id in kept}
        self._approvals = {
            device_id: value for device_id, value in self._approvals.items() if device_id in self.mirrors
        }
        self._revs = {device_id: value for device_id, value in self._revs.items() if device_id in current}
        self._transfers = {device_id: value for device_id, value in self._transfers.items() if device_id in current}
        self._device_modes = {device_id: value for device_id, value in self._device_modes.items() if device_id in kept}
        # The lock is held from the first subscribe until the owned devices are registered and published: a retained
        # document replayed while the subscribes are awaited queues its ingest on this lock, and by the time it runs
        # the owned ids are in `devices`, so a foreign claim for an owned id can never become a mirror (CR-02)
        async with self._lock:
            # Subscribed before anything is published, so the owner sees its own documents and every foreign write
            await self.sync.async_start()
            await self.presence.async_start()
            await self.retrigger.async_start()
            await self._async_orphan_cleanup()
            await self._async_reconcile_locked(startup=True)
            # Before the platform forward and before any document: the entities move first, then the retained clear
            await self._async_native_takeover()
            await self._async_publish_owned()
        await self._async_publish_availability(AvailabilityState.ONLINE)
        await self.presence.async_publish_heartbeat()

    async def _async_native_takeover(self) -> None:
        """
        Move the legacy MQTT entities of pending owned devices and native mirrors here (D-05, D-09, D-12, MIG-01).

        The order for an owned device is fixed: the live migrate payload, then the registry takeover, then the
        retained clear. A device whose legacy entities stay loaded is deferred: nothing moves, nothing is cleared, it
        stays pending and runs on the legacy path for this run (T-5-08). Only ids that are owned devices are ever
        published for (T-5-02). A follower publishes nothing. The caller holds the lock; the platforms are not
        forwarded yet.
        """
        assert self._publisher is not None  # noqa: S101
        owned = sorted(self._native_pending & self.devices.keys())
        stale = self._native_pending - set(owned)
        self._native_pending.difference_update(stale)
        mqtt_entry_id = self.gateway.mqtt_entry_id()
        mirrors = sorted(
            device_id
            for device_id, mirror in self.mirrors.items()
            if mirror.mirror is not None
            and mirror.mirror.native
            and mqtt_entry_id is not None
            and takeover.legacy_device(self._hass, mqtt_entry_id, device_id) is not None
        )
        if not owned and not mirrors:
            if stale:
                await self._store.async_save(self._data_to_save())
            return
        # Published for every pending device, even without a legacy device of our own: another instance's core MQTT
        # may have its entities loaded, and the clear alone would delete their registry entries
        migrated = {
            device_id
            for device_id in owned
            if await _async_attempt(
                partial(self._publisher.async_publish_migrate, device_id),
                f"publish the migrate payload of device {device_id}",
            )
        }
        targets = [takeover.TakeoverTarget(device_id, self.subentry_id_of(device_id)) for device_id in owned]
        targets += [takeover.TakeoverTarget(device_id, None) for device_id in mirrors]
        results = await asyncio.gather(
            *(self._async_take_over_one(target, mqtt_entry_id, skip=set(owned) - migrated) for target in targets),
            return_exceptions=True,
        )
        for target, status in zip(targets, results, strict=True):
            deferred = status is takeover.TakeoverStatus.DEFERRED
            if isinstance(status, BaseException):
                # No registry or broker content in the log: a registry surprise must never keep the start from finishing
                LOGGER.warning("The native takeover of a device failed unexpectedly, so it stays on the legacy path")
                LOGGER.debug("The native takeover failed with %s", type(status).__name__)
                deferred = True
            if deferred or not await self._async_finish_takeover(target.device_id, set(owned)):
                await self._async_defer_takeover(target.device_id)
        await self._store.async_save(self._data_to_save())

    async def _async_take_over_one(
        self, target: takeover.TakeoverTarget, mqtt_entry_id: str | None, *, skip: set[str]
    ) -> takeover.TakeoverStatus:
        """Take one device over; a device in `skip`, whose migrate payload did not go out, is deferred untouched."""
        if target.device_id in skip:
            return takeover.TakeoverStatus.DEFERRED
        if mqtt_entry_id is None:
            return takeover.TakeoverStatus.NOTHING
        return await takeover.async_take_over(
            self._hass,
            self._entry,
            target,
            mqtt_entry_id=mqtt_entry_id,
            unload_timeout=takeover.TAKEOVER_UNLOAD_TIMEOUT,
            retry_interval=takeover.TAKEOVER_RETRY_INTERVAL,
        )

    async def _async_finish_takeover(self, device_id: str, owned: set[str]) -> bool:
        """
        Finish a taken-over device; False when the retained clear of an owned device could not be published.

        The owner clears the retained discovery last and ends the stale test-topic subscription of the legacy path. A
        follower has nothing to clear.
        """
        if device_id not in owned:
            return True
        assert self._publisher is not None  # noqa: S101
        if not await _async_attempt(
            partial(self._publisher.async_clear_device, device_id), f"clear the discovery of device {device_id}"
        ):
            return False
        self._native_pending.discard(device_id)
        if (device := self.devices.get(device_id)) is not None and device.unsubscribe_test is not None:
            device.unsubscribe_test()
            device.unsubscribe_test = None
        return True

    async def _async_defer_takeover(self, device_id: str) -> None:
        """
        Keep a device that could not be taken over on the legacy path for this run, with everything as in 0.1.0.

        A native mirror was built without the test-topic subscription of the legacy path, so it gets it now: its legacy
        test buttons are still the entities of the device.
        """
        LOGGER.info("The native takeover of a device is postponed to the next start; it stays as it is until then")
        self._legacy_this_run.add(device_id)
        if (mirror := self.mirrors.get(device_id)) is None or mirror.unsubscribe_test is not None:
            return
        try:
            mirror.unsubscribe_test = await self.gateway.async_subscribe(
                test_topic(self._base_topic, device_id), partial(self._on_test_message, device_id)
            )
        except HomeAssistantError as err:
            LOGGER.warning("MQTT could not subscribe to the test topic of device %s: %s", mirror.name, err)

    async def async_reconcile(self, *, startup: bool = False) -> None:
        """
        Bring the running devices in line with the device subentries: remove, change and add.

        Only devices built while the manager starts (HA start or entry reload) get the startup window; a device the
        user creates later is not a start (D-05).
        """
        async with self._lock:
            await self._async_reconcile_locked(startup=startup)

    async def _async_reconcile_locked(self, *, startup: bool = False) -> None:
        """Reconcile the running devices with the subentries; the caller holds the lock."""
        # A late update-listener call after async_stop must not revive a manager nobody will ever unsubscribe
        if not self._running:
            return
        subentries = {subentry.data[CONF_DEVICE_ID]: subentry for subentry in _device_subentries(self._entry)}
        for device_id in [device_id for device_id in self.devices if device_id not in subentries]:
            await self._async_remove_device(device_id)
        for device_id, subentry in subentries.items():
            if device_id in self._releasing:
                # Popped for a local release; its subentry is only waiting to be removed (D-08)
                continue
            if (device := self.devices.get(device_id)) is None:
                await self._async_add_device(subentry, startup=startup)
            elif device.signature != _signature(subentry):
                await self._async_change_device(device, subentry)

    async def async_stop(self) -> None:
        """
        Persist the baseline, unsubscribe, unload scripts and publish availability offline.

        Nothing is deleted on the broker here: an empty payload on a discovery or state topic only happens on an
        explicit device delete or on hub removal (DSC-02). The final save comes first so a slow or failing publish
        cannot cost the baseline. Tripped breakers are not released here: a failed setup calls this too, and a Home
        Assistant restart never unloads the entry, so the tripped state survives both (D-17); a user unload or reload
        releases through release_all_breakers first (D-15).
        """
        async with self._lock:
            self._running = False
            self.sync.async_stop()
            self.presence.async_stop()
            self.retrigger.async_stop()
            await self._store.async_save(self._data_to_save())
            for device in [*self.devices.values(), *self.mirrors.values()]:
                if device.unsubscribe is not None:
                    device.unsubscribe()
                if device.unsubscribe_test is not None:
                    device.unsubscribe_test()
                await self.runner.async_unload(device.device_id)
            self.devices.clear()
            self.mirrors.clear()
            # Scripts of a device whose start failed halfway are not in self.devices yet
            await self.runner.async_unload_all()
            if self._skip_offline_once:
                # The availability topic of this id belongs to the original too (T-04-57); this stop is the one reload
                self._skip_offline_once = False
            elif self._publisher is not None:  # None when the start failed before the publisher existed
                await self._async_publish_availability(AvailabilityState.OFFLINE)

    @callback
    def release_all_breakers(self) -> None:
        """Release every breaker, delete its issue and forget the tripped map; a user unload or reload is a release."""
        for device in [*self.devices.values(), *self.mirrors.values()]:
            device.breaker.reset()
            self._delete_breaker_issue(device.device_id)
        self._tripped.clear()

    @callback
    def _on_connection_status(self, connected: bool) -> None:  # noqa: FBT001
        """Republish after a broker reconnect and restart the follower bookkeeping; publishes need a task."""
        if connected and self._running:
            self.sync.on_reconnect()
            self.presence.on_reconnect()
            self._entry.async_create_background_task(self._hass, self._async_republish(), name=f"{DOMAIN} republish")

    async def async_resync(self) -> bool:
        """
        Publish everything this instance owns again on request: documents, discovery, then online (D-12, DSC-04).

        Returns False and publishes nothing when the manager is not running or when the last accepted resync is less
        than RESYNC_MIN_INTERVAL_SECONDS ago on `clock` (T-04-15); True after it republished. The time is remembered
        before the publish is awaited, so a second request during a running resync is throttled as well, and the
        republish itself takes the manager lock, so work cannot queue up.
        """
        if not self._running:
            return False
        now = self.clock()
        if self._last_resync is not None and now - self._last_resync < RESYNC_MIN_INTERVAL_SECONDS:
            return False
        self._last_resync = now
        await self._async_republish()
        return True

    async def _async_republish(self) -> None:
        """
        Publish the config documents, the discovery and the online availability again (FND-05, SYN-04).

        The order is load-bearing: a follower that sees the owner online and a mirror's document missing concludes
        that the owner deleted it, so every document comes first and the availability last (D-15). Idempotent: core
        MQTT ignores an unchanged retained discovery payload, and a broker that lost its retained messages gets them
        back.
        """
        async with self._lock:
            if not self._running:
                return
            await self._async_publish_owned()
            await self._async_publish_availability(AvailabilityState.ONLINE)
            await self.presence.async_publish_heartbeat()

    async def _async_publish_owned(self) -> None:
        """Publish every config document, then every discovery; the caller holds the lock and publishes availability."""
        for device in self.devices.values():
            await self.async_publish_config(device)
        for device in self.devices.values():
            await self.async_publish_discovery(device)

    def _check_discovery_enabled(self) -> None:
        """Warn and raise a Repairs issue when MQTT discovery is disabled, because then no entity ever appears."""
        if self.gateway.discovery_enabled():
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE_DISCOVERY_DISABLED)
            return
        LOGGER.warning("MQTT discovery is disabled, so the entities of MQTT Actions cannot appear")
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
        self._tripped = _parse_tripped(stored)
        self._revs = _parse_revs(stored)
        self._transfers = _parse_transfers(stored)
        self._stored_mirrors = _parse_mirrors(stored)
        self._approvals = _parse_approvals(stored)
        self._instance_mode = _parse_instance_mode(stored)
        self._device_modes = _parse_device_modes(stored)
        self._native = _parse_native(stored)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return the persisted state; devices without a baseline are omitted (D-07)."""
        data = self._base_data_to_save()
        # The native key is only written once it carries something, so an instance that never used it keeps its Store
        if self._native != NativeState():
            data[STORE_NATIVE] = {
                "instance": self._native.instance,
                "pending": sorted(self._native.pending),
                "devices": sorted(self._native.devices),
            }
        return data

    def _base_data_to_save(self) -> dict[str, Any]:
        """Return the persisted state of every key that is always written."""
        live = {**self.devices, **self.mirrors}
        return {
            STORE_LAST_ACTED: {
                # The baselines of locally released devices stay until the mirror that follows them has taken over
                **{
                    device_id: baseline
                    for device_id, baseline in self._stored_last_acted.items()
                    if device_id in self._released and device_id not in live
                },
                **{
                    device_id: device.tracker.last_acted
                    for device_id, device in live.items()
                    if device.tracker.last_acted is not None
                },
            },
            STORE_MIRRORS: {
                device_id: device.mirror.payload for device_id, device in self.mirrors.items() if device.mirror
            },
            STORE_APPROVALS: dict(self._approvals),
            STORE_PUBLISHED: sorted(self._published),
            STORE_TRIPPED: dict(self._tripped),
            STORE_REVS: {device_id: dict(value) for device_id, value in self._revs.items()},
            STORE_TRANSFERS: {device_id: list(value) for device_id, value in self._transfers.items()},
            STORE_INSTANCE_MODE: self._instance_mode,
            STORE_DEVICE_MODES: dict(self._device_modes),
        }

    @callback
    def _schedule_save(self) -> None:
        """Save with a delay so a burst of messages causes one write."""
        self._store.async_delay_save(self._data_to_save, STORE_SAVE_DELAY)

    async def async_apply_mirror(self, parsed: ParsedDocument) -> None:
        """
        Create or update the read-only mirror of a validated foreign document; the caller holds the lock.

        A document with the content the mirror already has (the new owner after an adoption) only replaces the owner
        bookkeeping.

        A mirror is a Device without a Script: it follows the state topic for its baseline and runs nothing, because the
        runner only runs triggers of a device it built a Script for (TRU-01). It publishes nothing, is not in `devices`,
        not in the published set and never touched by a reconcile of the owned subentries (D-08, D-19). Whether the
        document is the pinned owner's and differs from the mirror is decided by the caller; an owned id is ignored.
        """
        device_id = parsed.device_id
        if device_id in self.devices:
            return
        if (existing := self.mirrors.get(device_id)) is not None:
            if existing.mirror is not None and existing.mirror.content_hash == parsed.content_hash:
                # The same content under a new owner is a re-pin after an adoption (D-09). Only the bookkeeping moves:
                # a fresh breaker would release a tripped device and a rebuilt Script would drop its running queue.
                was_native = existing.mirror.native
                existing.mirror = self._mirror_info(parsed, keep_native=was_native)
                self._follow_native_status(existing, was_native=was_native)
                self._sync_approval_issues(existing)
                self._schedule_save()
                return
            was_native = existing.mirror is not None and existing.mirror.native
            self._update_mirror(existing, parsed)
            self._rename_companion(device_id, parsed.spec.name)
            self._follow_native_status(existing, was_native=was_native)
            # A changed document starts clean: a stale setup or denied-call issue belongs to the old actions
            self.runner.clear_issue(device_id)
            ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_DENIED_CALL_PREFIX}{device_id}")
            await self._async_refresh_mirror_script(existing)
            self._sync_approval_issues(existing)
            return
        device = self._build_mirror(parsed, startup=False)
        # The Script exists before the first message can arrive, so an approved mirror never misses its startup window
        await self._async_refresh_mirror_script(device)
        await self._async_subscribe_mirror(device)
        self._sync_approval_issues(device)
        self._schedule_save()
        # The select platform adds the companion device and the mode select of the new mirror (D-13)
        self._notify_devices_changed()

    async def async_approve(self, device_id: str, actions_hash: str) -> bool:
        """
        Approve the actions of a mirror on this instance, and only the exact hash the user saw (D-02, T-03-29).

        Returns False and stores nothing unless the mirror exists, is not blocked by a denied service, has actions and
        its current actions hash equals `actions_hash`. On success the approval is stored, the Script is built from the
        approved actions and nothing runs retroactively: the baseline stays and only a later real edge runs.
        """
        async with self._lock:
            mirror = self.mirrors.get(device_id)
            info = None if mirror is None else mirror.mirror
            if (
                not self._running
                or mirror is None
                or info is None
                or info.denied
                or not spec_has_actions(mirror.spec)
                or info.actions_hash != actions_hash
            ):
                return False
            self._approvals[device_id] = actions_hash
            self._schedule_save()
            ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_DENIED_CALL_PREFIX}{device_id}")
            ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{device_id}")
            await self._async_refresh_mirror_script(mirror)
            LOGGER.info("The actions of mirrored device %r were approved", mirror.name[:MAX_LOGGED_PAYLOAD_LENGTH])
            return True

    async def async_adopt(self, device_id: str, *, force: bool = False) -> str:
        """
        Turn the mirror of an orphaned device into an owned device of this instance and return the old owner's name.

        The device keeps its uuid, its state topic and its baseline, so its entities stay; this instance publishes a new
        document with itself as owner and the old owner in the transfer marker (SYN-07, D-09, D-10). Preconditions, in
        this order, all checked before anything changes: the id is a mirror (`not_a_mirror`); it is approved here or has
        no actions, and a blocked or unapproved mirror is refused even with `force`, so unreviewed remote actions never
        become owned ones (`not_approved`, T-04-50); the owner is offline according to the roster, unless `force`
        (`owner_not_offline`, T-04-51). The whole change runs under the manager lock, so no late document of the old
        owner can re-create the mirror halfway. Raises AdoptionError.
        """
        async with self._lock:
            mirror = self.mirrors.get(device_id) if self._running and device_id not in self.devices else None
            info = None if mirror is None else mirror.mirror
            # A marker can only name ids of the shape of an id; an odd owner id could not be named, so it is no orphan
            if mirror is None or info is None or not is_valid_device_id(info.owner):
                raise AdoptionError(ADOPT_NOT_A_MIRROR)
            if self.approval_state(device_id) in {ApprovalState.PENDING, ApprovalState.BLOCKED}:
                raise AdoptionError(ADOPT_NOT_APPROVED, info.owner_name)
            if not force and not self.presence.owner_offline(info.owner):
                raise AdoptionError(ADOPT_OWNER_NOT_OFFLINE, info.owner_name)
            await self._async_adopt_locked(mirror, info)
            return info.owner_name

    async def _async_adopt_locked(self, mirror: Device, info: MirrorInfo) -> None:
        """
        Replace a mirror by an owned device with the same id; the caller holds the lock and checked the preconditions.

        Nothing is cleared on the broker and the registry of core MQTT is not touched: the discovery of the device
        stays, and the new owner publishes it again with its own availability when the device is added. A native mirror
        becomes a native owned device; a legacy mirror on a native instance is queued for the takeover of the next
        setup.
        """
        device_id = mirror.device_id
        spec = mirror.spec
        subentry = ConfigSubentry(
            data=MappingProxyType(subentry_payload(build_content(spec), device_id)),
            subentry_type=spec.kind,
            title=spec.name,
            unique_id=device_id,
        )
        approval = self._approvals.get(device_id)
        # The previous owners, newest last, never more than the marker may carry (T-04-52)
        self._transfers[device_id] = [*info.transferred_from, info.owner][-MAX_TRANSFER_HISTORY:]
        # The first publish of the adopter is the old rev plus one, whatever the hash is (D-09)
        self._revs[device_id] = {"rev": info.rev, "hash": ADOPTED_HASH}
        if mirror.tracker.last_acted is not None:
            self._stored_last_acted[device_id] = mirror.tracker.last_acted
        # A native device stays native whatever this instance's flag says; a legacy device of a native instance first
        # needs the takeover pass of the next setup, so it is pending and not native until then (T-5-12)
        queue_takeover = not info.native and self._native.instance
        if info.native:
            self._native_devices.add(device_id)
        elif queue_takeover:
            self._native_pending.add(device_id)
        await self._async_drop_mirror(mirror)
        # The select platform forgets the mirror's mode select now; the add below gives the owned device its own
        self._notify_devices_changed()
        # Saved before the subentry exists: a crash in between loses the adoption, not the device (T-04-53)
        await self._store.async_save(self._data_to_save())
        try:
            self._hass.config_entries.async_add_subentry(self._entry, subentry)
        except Exception:
            self._transfers.pop(device_id, None)
            self._revs.pop(device_id, None)
            self._native_devices.discard(device_id)
            self._native_pending.discard(device_id)
            if approval is not None:
                self._approvals[device_id] = approval
            await self.sync.async_restore_mirror(device_id, info.payload)
            raise
        LOGGER.info("Adopted device %s from an instance that is offline or was forced", shown(spec.name))
        # The update listener of the entry reconciles too, once the lock is free, and then finds nothing to do
        await self._async_reconcile_locked()
        if queue_takeover:
            # The next setup runs the pass for it: the migrate payload, the takeover and the retained clear
            self._hass.config_entries.async_schedule_reload(self._entry.entry_id)

    async def _async_drop_mirror(self, mirror: Device) -> None:
        """
        Release a mirror without clearing anything: no broker message and no registry cleanup of core MQTT.

        Both subscriptions end, the Script is unloaded, the per-device issues, the approval and the companion device go
        and the sync side forgets the mirror. The stored mode and the baseline stay for the owned device that follows.
        """
        device_id = mirror.device_id
        self.mirrors.pop(device_id, None)
        if mirror.unsubscribe is not None:
            mirror.unsubscribe()
        if mirror.unsubscribe_test is not None:
            mirror.unsubscribe_test()
        await self.runner.async_unload(device_id, remove_issue=True)
        self._delete_device_issues(device_id)
        self._approvals.pop(device_id, None)
        self._tripped.pop(device_id, None)
        self._remove_companion(device_id)
        self.sync.forget_mirror(device_id)

    @callback
    def on_duplicate_id_changed(self, *, detected: bool) -> None:
        """
        Raise or delete the issue about another instance with this instance's id (D-07).

        Nothing changes automatically: the issue only offers the fix flow. It is created once, so a dismissal stays, and
        the log line is fixed text that carries nothing from the heartbeats.
        """
        if not detected:
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE_DUPLICATE_INSTANCE_ID)
            LOGGER.info("No other instance with the same instance id was heard any more")
            return
        LOGGER.warning(
            "Another Home Assistant instance uses the same instance id as this one, for example a clone or a "
            "restored backup"
        )
        if ir.async_get(self._hass).async_get_issue(DOMAIN, ISSUE_DUPLICATE_INSTANCE_ID) is not None:
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            ISSUE_DUPLICATE_INSTANCE_ID,
            # The flow acts only while the id is still the one that was reported
            data={"instance_id": self._instance_id},
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_DUPLICATE_INSTANCE_ID,
            translation_placeholders={"instance": escape_markdown(self.instance_name)},
        )

    async def async_release_locally(self, device_ids: Iterable[str]) -> list[str]:
        """
        Forget owned devices on this instance only and return the ids that were released (D-08).

        The broker is never touched: no tombstone, no discovery clear, no state clear and no publish at all, because
        the topics may belong to another instance that owns the same ids (a clone, an adopter). The order is fixed.
        Under the lock each device leaves `devices` first, then its subscriptions and Script end, its issues, its
        published, revision, tripped and transfer records go, and the Store is saved at once, so a crash afterwards can
        never make the next start clear topics of a device that is no longer here (T-04-56). Only then are the
        subentries removed; the guard keeps the reconcile of each removal from adding a released device again. The
        baseline and the mode stay for the mirror that may follow. Ids that are not owned devices are ignored.
        """
        released: list[str] = []
        subentry_ids: list[str] = []
        try:
            async with self._lock:
                for device_id in device_ids:
                    if device_id not in self.devices:
                        continue
                    if (subentry_id := self.subentry_id_of(device_id)) is not None:
                        subentry_ids.append(subentry_id)
                    device = self.devices.pop(device_id)
                    self._releasing.add(device_id)
                    released.append(device_id)
                    self._release_device(device)
                    await self.runner.async_unload(device_id, remove_issue=True)
                if not released:
                    return []
                await self._store.async_save(self._data_to_save())
                self._notify_devices_changed()
            for subentry_id in subentry_ids:
                self._hass.config_entries.async_remove_subentry(self._entry, subentry_id)
                # The update listener of the removal runs now, while the guard is still up
                await asyncio.sleep(0)
        finally:
            self._releasing.difference_update(released)
        return released

    @callback
    def _release_device(self, device: Device) -> None:
        """Drop everything an owned device holds locally, except its baseline and mode; publishes nothing."""
        device_id = device.device_id
        if device.unsubscribe is not None:
            device.unsubscribe()
        if device.unsubscribe_test is not None:
            device.unsubscribe_test()
        self._delete_device_issues(device_id)
        self.sync.forget(device_id)
        if device.tracker.last_acted is not None:
            self._stored_last_acted[device_id] = device.tracker.last_acted
        self._released.add(device_id)
        self._published.discard(device_id)
        self._revs.pop(device_id, None)
        self._tripped.pop(device_id, None)
        self._transfers.pop(device_id, None)
        self._unpublishable.discard(device_id)
        self._forget_native(device_id)

    @callback
    def _forget_native(self, device_id: str) -> None:
        """Forget the native bookkeeping of an owned device that is deleted or released here."""
        self._native_pending.discard(device_id)
        self._native_devices.discard(device_id)
        self._legacy_this_run.discard(device_id)

    async def async_release_device_locally(self, device_id: str) -> bool:
        """
        Let this instance follow the adopter of one of its devices instead of owning it; False when it does not apply.

        Applies only to an owned device that was recognized as transferred away. The device is released locally, with
        nothing published, and the saved document of the adopter then creates the mirror, which starts with the
        baseline and the mode the device had (D-09).
        """
        if (info := self.sync.transfer_info(device_id)) is None or device_id not in self.devices:
            return False
        if not await self.async_release_locally([device_id]):
            return False
        async with self._lock:
            if self._running:
                await self.sync.async_follow(device_id, info.payload)
        return True

    async def async_resolve_duplicate_id(self) -> None:
        """
        Fix a duplicate instance id: forget the own devices locally and continue under a new id (D-08).

        The original keeps the id, the devices, their topics and its availability. The next stop, which is the reload
        that is scheduled here, publishes no offline availability for the old id. The new id is not in a per-instance
        ACL of the broker; the user is told in the flow text.
        """
        await self.async_release_locally(list(self.devices))
        self._skip_offline_once = True
        self._hass.config_entries.async_update_entry(
            self._entry, data={**self._entry.data, CONF_INSTANCE_ID: str(uuid.uuid4())}
        )
        self._hass.config_entries.async_schedule_reload(self._entry.entry_id)

    def approval_state(self, device_id: str) -> ApprovalState:
        """
        Return the approval state of a device as one public word (D-17).

        An owned device is `owned`. A mirror is `blocked` when its recorded analysis denies a service, `no_actions` when
        there is nothing to approve, `approved` when the stored approval equals its actions hash and `pending` if not.
        """
        if device_id in self.devices:
            return ApprovalState.OWNED
        if (mirror := self.mirrors.get(device_id)) is None or (info := mirror.mirror) is None:
            return ApprovalState.UNKNOWN
        if info.denied:
            return ApprovalState.BLOCKED
        if not spec_has_actions(mirror.spec):
            return ApprovalState.NO_ACTIONS
        if self._approvals.get(device_id) == info.actions_hash:
            return ApprovalState.APPROVED
        return ApprovalState.PENDING

    async def async_approval_view(self, device_id: str) -> ApprovalView | None:
        """
        Return what the approval dialog shows for a mirror, or None when there is no such mirror.

        The view is built from one consistent snapshot of the mirror. Deep validation runs for every trigger with
        actions and names the labels that do not validate on this instance; that never drops or blocks the mirror (Open
        Question 3). The caller binds the hash of the view it displays, `async_approve` checks it again under the lock.
        """
        if (mirror := self.mirrors.get(device_id)) is None or (info := mirror.mirror) is None:
            return None
        spec = mirror.spec
        invalid: list[str] = []
        for label, actions in approval_sections(spec):
            try:
                await async_validate_actions(self._hass, actions)
            except ActionsInvalid:
                invalid.append(label)
        return build_approval_view(spec, info, invalid)

    @callback
    def _sync_approval_issues(self, device: Device) -> None:
        """
        Bring the approval and blocked issues of a mirror in line with its state; only mirrors have them.

        A statically denied mirror is explained and never approvable. An unapproved mirror with actions gets a request:
        the old one is deleted first, because replacing an issue keeps its dismissal and a dismissed request must never
        hide a changed one (Pitfall 8). An approved mirror and one without actions need nothing.
        """
        if (info := device.mirror) is None:
            return
        device_id = device.device_id
        approval_id = f"{ISSUE_APPROVAL_PREFIX}{device_id}"
        blocked_id = f"{ISSUE_BLOCKED_PREFIX}{device_id}"
        ir.async_delete_issue(self._hass, DOMAIN, approval_id)
        ir.async_delete_issue(self._hass, DOMAIN, blocked_id)
        owner = escape_markdown(info.owner_name)
        name = escape_markdown(device.name)
        if info.denied:
            services = ", ".join(escape_markdown(service[:80]) for service in info.denied[:BLOCKED_SERVICES_MAX_SHOWN])
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                blocked_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="mirror_blocked",
                translation_placeholders={
                    "device": name,
                    "owner": owner,
                    "services": f"{services}, \u2026" if len(info.denied) > BLOCKED_SERVICES_MAX_SHOWN else services,
                },
            )
            return
        if self._approvals.get(device_id) == info.actions_hash or not spec_has_actions(device.spec):
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            approval_id,
            # Only the id and the hash: the flow reads everything else from the manager at the moment it shows it
            data={"device_id": device_id, "actions_hash": info.actions_hash},
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="approval_required",
            translation_placeholders={
                "device": name,
                "owner": owner,
                "hash": info.actions_hash[:APPROVAL_HASH_PREFIX_LENGTH],
            },
        )

    async def _async_refresh_mirror_script(self, device: Device) -> None:
        """
        Build the Script of a mirror only for an approved, unblocked document, and unload it otherwise (TRU-01).

        The gate is "no Script until the approved hash equals the actions hash of the mirror": a blocked mirror, one
        without actions and one whose approval does not match (never approved, or the owner changed the actions) get no
        Script, and unloading stops its running and queued runs. The build is restricted, so even a forged approval
        entry cannot give a statically denied service a Script (T-03-33).
        """
        info = device.mirror
        if info is None:
            return
        approved = self._approvals.get(device.device_id) == info.actions_hash
        if info.denied or not spec_has_actions(device.spec) or not approved:
            await self.runner.async_unload(device.device_id)
            return
        await self.runner.async_build_device(device.spec, restricted=True)

    async def async_remove_mirror(self, device_id: str) -> None:
        """
        Remove the mirror of a device its owner deleted, and everything this instance keeps about it (D-09, SYN-05).

        The caller holds the lock and has decided that the removal is final: a tombstone or a prune with positive
        evidence. Nothing is published, the topics belong to the owner. Both subscriptions end, the Script state is
        unloaded, the persisted payload, baseline and tripped hash are forgotten and every per-device issue is deleted.
        Leftover registry entries are cleaned last, and only when no entity of the device is live.
        """
        if device_id in self.devices:
            # An owned id is never a mirror; unloading its Script here would kill the owner's own device
            return
        if (device := self.mirrors.pop(device_id, None)) is None:
            return
        if device.unsubscribe is not None:
            device.unsubscribe()
        if device.unsubscribe_test is not None:
            device.unsubscribe_test()
        await self.runner.async_unload(device_id, remove_issue=True)
        self._delete_breaker_issue(device_id)
        self._delete_device_issues(device_id)
        self._stored_last_acted.pop(device_id, None)
        self._tripped.pop(device_id, None)
        # An approval does not outlive its mirror (A10): a returning device is a new request
        self._approvals.pop(device_id, None)
        # Neither a mode nor a companion device outlives its mirror (T-04-26)
        self._device_modes.pop(device_id, None)
        self._remove_companion(device_id)
        self._clean_registry(device_id)
        self._schedule_save()
        self._notify_devices_changed()

    @callback
    def _remove_companion(self, device_id: str) -> None:
        """
        Remove the companion device of a mirror and, with it, its mode select; unknown ids and repeats do nothing.

        A mirror has no subentry, so core never removes its companion. The lookup uses the identifier of this
        integration only: the core MQTT device of the discovery payload is another registry entry and must stay,
        because removing a live discovery entity would make core MQTT clear the device for every instance (D-13).
        """
        device_registry = dr.async_get(self._hass)
        companion = device_registry.async_get_device_by_identifier((DOMAIN, device_id), self._entry.entry_id)
        if companion is not None:
            device_registry.async_remove_device(companion.id)

    @callback
    def _clean_registry(self, device_id: str) -> None:
        """
        Remove the device and entity registry entries a missed delete left behind, and only those.

        An entity that is live in core still has its discovery on the broker: removing its registry entry would make
        core publish an empty retained discovery, which clears the device for every instance including the owner
        (Pitfall 10). So nothing is removed while any entity has a state that is not a restored one. Without an MQTT
        entry or a registry device there is nothing to do.
        """
        if (mqtt_entry_id := self.gateway.mqtt_entry_id()) is None:
            return
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry_id)
        if device is None:
            return
        entities = er.async_entries_for_device(er.async_get(self._hass), device.id, include_disabled_entities=True)
        for entity in entities:
            state = self._hass.states.get(entity.entity_id)
            if state is not None and not state.attributes.get(ATTR_RESTORED):
                LOGGER.debug(
                    "Keeping the registry entries of removed mirror %r: its entities are still live", device_id[:40]
                )
                return
        device_registry.async_remove_device(device.id)

    async def _async_restore_mirrors(self, owned: set[str]) -> None:
        """Rebuild the cached mirrors at start; owned ids are dropped, the rest gets the startup window."""
        cached, self._stored_mirrors = self._stored_mirrors, {}
        for device_id, parsed in cached.items():
            if device_id in owned:
                LOGGER.debug(
                    "A cached mirror of device %r was dropped because the device is owned here", device_id[:40]
                )
                continue
            device = self._build_mirror(parsed, startup=True)
            await self._async_refresh_mirror_script(device)
            await self._async_subscribe_mirror(device)
            self._sync_approval_issues(device)

    @staticmethod
    def _mirror_info(parsed: ParsedDocument, *, keep_native: bool = False) -> MirrorInfo:
        """
        Return what a follower records of a document: its owner, both hashes, the payload and the static analysis.

        `keep_native` is set when the mirror this replaces was native: a document without the marker never reverts it
        (T-5-11), and the stored payload then carries the marker so the status also survives a restart.
        """
        analysis: ActionAnalysis = analyze_spec(parsed.spec)
        carried = keep_native and not parsed.native
        return MirrorInfo(
            owner=parsed.owner,
            owner_name=parsed.owner_name,
            rev=parsed.rev,
            content_hash=parsed.content_hash,
            actions_hash=parsed.actions_hash,
            payload=with_native_marker(parsed.payload) if carried else parsed.payload,
            denied=analysis.denied,
            templated=analysis.templated,
            residual=analysis.residual,
            transferred_from=parsed.transferred_from,
            native=parsed.native or keep_native,
        )

    def _build_mirror(self, parsed: ParsedDocument, *, startup: bool) -> Device:
        """Build the runtime state of a mirror: tracker, breaker and the recorded static analysis; no Script."""
        spec = parsed.spec
        stored = self._stored_last_acted.get(parsed.device_id)
        device = Device(
            device_id=parsed.device_id,
            spec=spec,
            tracker=StateTracker(
                last_acted=stored if stored in spec.accepted.values() else None,
                run_on_startup=spec.run_on_startup,
                startup_pending=startup,
                accepted=spec.accepted,
            ),
            # The canonical content stands in for the subentry fingerprint, so the persisted breaker hash still works
            signature=canonical_json(parsed.content),
            breaker=self._new_breaker(spec),
            mirror=self._mirror_info(parsed),
        )
        self._restore_tripped(device)
        return device

    def _update_mirror(self, device: Device, parsed: ParsedDocument) -> None:
        """
        Apply a changed document of the pinned owner to an existing mirror; the device and its subscriptions stay.

        Like a reconfigured owned device it gets a fresh breaker with its issue deleted, and a baseline that is no
        StateValue of the new spec becomes unknown (D-15 of Phase 2, A11).
        """
        spec = parsed.spec
        # A mirror that was native stays native, whatever the new document says (T-5-11)
        mirror = self._mirror_info(parsed, keep_native=device.mirror is not None and device.mirror.native)
        device.spec = spec
        device.mirror = mirror
        device.signature = canonical_json(parsed.content)
        device.tracker.run_on_startup = spec.run_on_startup
        device.tracker.accepted = spec.accepted
        if device.tracker.last_acted is not None and device.tracker.last_acted not in spec.accepted.values():
            device.tracker.last_acted = None
        device.breaker = self._new_breaker(spec)
        self._delete_breaker_issue(device.device_id)
        self._tripped.pop(device.device_id, None)
        self._schedule_save()

    @callback
    def _follow_native_status(self, device: Device, *, was_native: bool) -> None:
        """
        Bring the companion of a mirror in line after its record was replaced and the mirror is native.

        The device model names the owner. A mirror that just became native drops its test topic, gets its native
        entities through the platforms and keeps the companion device it already had (D-07, MIG-03).
        """
        if device.mirror is None or not device.mirror.native:
            return
        device_registry = dr.async_get(self._hass)
        companion = device_registry.async_get_device_by_identifier((DOMAIN, device.device_id), self._entry.entry_id)
        model = device_info_for(self, device.device_id).get("model")
        if companion is not None and model is not None and companion.model != model:
            device_registry.async_update_device(companion.id, model=model)
        if was_native:
            return
        if device.unsubscribe_test is not None:
            device.unsubscribe_test()
            device.unsubscribe_test = None
        self._notify_devices_changed()

    async def _async_subscribe_mirror(self, device: Device) -> None:
        """Register a mirror and subscribe to its state and test topics; a failed subscribe leaves nothing behind."""
        device_id = device.device_id
        # Registered before subscribing: the retained state can arrive while the subscribe call is still awaited
        self.mirrors[device_id] = device
        try:
            device.unsubscribe = await self.gateway.async_subscribe(
                state_topic(self._base_topic, device_id), partial(self._on_message, device_id)
            )
            # A native mirror has test buttons that run the trigger here, so it needs no test topic (MIG-03)
            if not self.is_native(device_id):
                device.unsubscribe_test = await self.gateway.async_subscribe(
                    test_topic(self._base_topic, device_id), partial(self._on_test_message, device_id)
                )
        except BaseException:
            self.mirrors.pop(device_id, None)
            if device.unsubscribe is not None:
                device.unsubscribe()
            await self.runner.async_unload(device_id)
            raise

    def _device(self, device_id: str) -> Device | None:
        """Return the owned device or the mirror with this id; the two sets never share an id."""
        if (device := self.devices.get(device_id)) is None:
            device = self.mirrors.get(device_id)
        return device

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
            breaker=self._new_breaker(spec),
        )
        self._restore_tripped(device)
        await self.runner.async_build_device(spec)
        # The document published before a restart or an offline edit comes back as an echo, not as a foreign write
        if (known := self._revs.get(device_id)) is not None:
            self.sync.note_published(device_id, known["hash"])
        self.devices[device_id] = device
        # Resolve the device from self.devices at message time: binding the object would break after a rebuild
        device.unsubscribe = await self.gateway.async_subscribe(
            state_topic(self._base_topic, device_id),
            partial(self._on_message, device_id),
        )
        # A native device has a test button that runs the trigger directly, so no test topic round trip exists (MIG-03)
        if not self.is_native(device_id):
            device.unsubscribe_test = await self.gateway.async_subscribe(
                test_topic(self._base_topic, device_id),
                partial(self._on_test_message, device_id),
            )
        # The start publishes all documents first, then all discovery (D-15); only a later add publishes per device
        if not startup:
            await self.async_publish_config(device)
            await self.async_publish_discovery(device)
        self._published.add(device_id)
        self._schedule_save()
        self._notify_devices_changed()

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
        # A removed option retires its button; a re-added StateValue derives the same key, so its tombstone goes
        current_keys = {button_component_key(key) for key in spec.triggers}
        previous_keys = {button_component_key(key) for key in device.spec.triggers}
        device.retired_components |= previous_keys - current_keys
        device.retired_components -= current_keys
        device.spec = spec
        device.tracker.run_on_startup = spec.run_on_startup
        device.tracker.accepted = spec.accepted
        if device.tracker.last_acted is not None and device.tracker.last_acted not in spec.accepted.values():
            device.tracker.last_acted = None
            self._schedule_save()
        device.signature = _signature(subentry)
        # A changed configuration releases a tripped device with a fresh window (D-15)
        device.breaker = self._new_breaker(spec)
        self._delete_breaker_issue(device.device_id)
        if self._tripped.pop(device.device_id, None) is not None:
            self._schedule_save()
        self._rename_companion(device.device_id, spec.name)
        await self.async_publish_config(device, changed_only=True)
        await self.async_publish_discovery(device)
        # A native select re-reads its options and its current option; a legacy device ignores the signal
        self._notify_devices_changed()

    @callback
    def _rename_companion(self, device_id: str, name: str) -> None:
        """
        Give the companion device of an owned device its new name, unless the user chose a name of their own (D-13).

        Only the device registry entry of this integration is touched: the core MQTT device of the discovery payload
        is a different entry and follows its own retained payload.
        """
        device_registry = dr.async_get(self._hass)
        companion = device_registry.async_get_device_by_identifier((DOMAIN, device_id), self._entry.entry_id)
        if companion is not None and companion.name_by_user is None and companion.name != name:
            device_registry.async_update_device(companion.id, name=name)

    async def _async_remove_device(self, device_id: str) -> None:
        """
        Remove a deleted device in the order that keeps the manager from reading its own clear messages (D-16).

        The device leaves `devices` first: the message handlers only act for devices in `devices`, so the discovery
        clear, the config tombstone and the state clear of this delete can never look like a foreign event that the
        owner would heal, which would resurrect the device (D-18). Then the discovery is cleared so the entity
        disappears, the subscriptions end, the config tombstone follows and the retained state goes last. A clear that
        fails keeps the id in the published set so the next start retries all three topics. A device that another
        instance adopted is only forgotten here: nothing is cleared, because the topics belong to the adopter (T-04-56).
        """
        assert self._publisher is not None  # noqa: S101
        device = self.devices.pop(device_id)
        # Another instance adopted the device: its topics are the adopter's now and this delete must not clear them
        adopted_away = self.sync.transfer_info(device_id) is not None
        discovery_cleared = adopted_away or await _async_attempt(
            partial(self._publisher.async_clear_device, device_id), f"clear the discovery of device {device.name}"
        )
        if device.unsubscribe is not None:
            device.unsubscribe()
        if device.unsubscribe_test is not None:
            device.unsubscribe_test()
        config_cleared = adopted_away or await _async_attempt(
            partial(self._publisher.async_clear_config, device_id), f"clear the config document of device {device.name}"
        )
        state_cleared = adopted_away or await _async_attempt(
            partial(self._publisher.async_clear_state, device_id), f"clear the retained state of device {device.name}"
        )
        await self.runner.async_unload(device_id, remove_issue=True)
        self._delete_device_issues(device_id)
        self.sync.forget(device_id)
        self._stored_last_acted.pop(device_id, None)
        self._tripped.pop(device_id, None)
        self._revs.pop(device_id, None)
        self._transfers.pop(device_id, None)
        self._device_modes.pop(device_id, None)
        self._forget_native(device_id)
        if discovery_cleared and config_cleared and state_cleared:
            self._published.discard(device_id)
        self._schedule_save()
        self._notify_devices_changed()

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

    async def async_publish_config(self, device: Device, *, changed_only: bool = False) -> None:
        """
        Publish the retained config document of an owned device (SYN-01, D-12).

        The rev grows only when the content hash differs from the one last published, and both are persisted so a
        restart republishes the same rev (D-15). With `changed_only` an unchanged document is not published again; the
        start and every reconnect publish unconditionally. A document that cannot be built is logged by device name
        only and nothing is published.
        """
        assert self._publisher is not None  # noqa: S101
        device_id = device.device_id
        if device_id in self.sync.transferred_away:
            # Another instance adopted it; this instance never publishes it again, not even on a start or a resync
            return
        known = self._revs.get(device_id)
        try:
            document = build_document(
                device.spec,
                owner=self._instance_id,
                owner_name=self._entry.data[CONF_INSTANCE_NAME],
                rev=1,
                # An adopted device carries its previous owners in every document, so a late follower learns it (D-09)
                transferred_from=tuple(self._transfers.get(device_id, ())),
                # The marker only while the device is native, so a deferred or legacy device publishes none
                native=self.is_native(device_id),
            )
            digest: str = document["hash"]
            changed = known is None or known["hash"] != digest
            document["rev"] = 1 if known is None else known["rev"] + (1 if changed else 0)
            payload = serialize_document(document)
        except ValueError, TypeError:
            LOGGER.warning("The config document of device %s cannot be built, so it is not published", device.name)
            return
        # The document must pass the parser every follower applies, or it is dropped everywhere and the owner's own echo
        # looks like a foreign overwrite that is healed by publishing again, in a loop (CR-03)
        try:
            parse_document(device_id, payload)
        except DocumentRejectedError as err:
            if device_id not in self._unpublishable:
                self._unpublishable.add(device_id)
                LOGGER.warning(
                    "The config document of device %s would be rejected by other instances (%s), so it is not sent",
                    device.name,
                    err.reason,
                )
            return
        self._unpublishable.discard(device_id)
        if changed:
            self._revs[device_id] = {"rev": document["rev"], "hash": digest}
            self._schedule_save()
        elif changed_only:
            return
        # Noted before the publish: the echo can arrive before the publish call returns
        self.sync.note_published(device_id, digest)
        await _async_attempt(
            partial(self._publisher.async_publish_config, device_id, payload),
            f"publish the config document of device {device.name}",
        )

    async def async_publish_discovery(self, device: Device) -> None:
        """Publish the retained discovery of a device; an unavailable MQTT client is logged, the next start retries."""
        assert self._publisher is not None  # noqa: S101
        # A native device has entities of its own and needs no discovery (D-03)
        if device.device_id in self.sync.transferred_away or self.is_native(device.device_id):
            return
        await _async_attempt(
            partial(
                self._publisher.async_publish_device,
                spec=device.spec,
                instance_id=self._instance_id,
                retired=frozenset(device.retired_components),
            ),
            f"publish the discovery of device {device.name}",
        )

    @callback
    def _on_message(self, device_id: str, msg: IncomingMessage) -> None:
        """Handle a state message: record the value, separate baseline from edge and enqueue the matching script."""
        if (device := self._device(device_id)) is None:
            return
        # The shown state is recorded before the mode gate: a disabled device still shows what the broker says (STA-07)
        self._record_value(device, msg.payload)
        # Disabled processes nothing: the baseline stays where it was and no payload is looked at (D-14)
        if self.effective_mode(device_id) == MODE_DISABLED:
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
        self._run_trigger(device, decision.value)

    @callback
    def _record_value(self, device: Device, payload: str) -> None:
        """Remember the StateValue of an accepted payload and tell the native entity; other payloads change nothing."""
        value = device.spec.accepted.get(payload.strip().lower())
        if value is None or value == device.value:
            return
        device.value = value
        async_dispatcher_send(self._hass, SIGNAL_DEVICE_STATE.format(self._entry.entry_id, device.device_id))

    async def async_send_state(self, device_id: str, value: str) -> None:
        """
        Publish a StateValue to the shared state topic of a device, retained at QoS 1 (D-07, T-5-10).

        Nothing is changed locally: the echo of the broker is the single state source. Raises ValueError for an unknown
        device and for a value that is not exactly one of its StateValues; the HomeAssistantError of an unavailable
        MQTT client propagates.
        """
        if (device := self._device(device_id)) is None or value not in device.spec.accepted.values():
            msg = "Unknown device or state value"
            raise ValueError(msg)
        await self.gateway.async_publish(state_topic(self._base_topic, device_id), value, retain=True, qos=1)

    @callback
    def _run_trigger(self, device: Device, value: str) -> None:
        """Run the actions of the trigger of a real change, unless the mode or the circuit breaker stops it."""
        device_id = device.device_id
        trigger = device.spec.triggers.get(trigger_key(value))
        if trigger is None or not self.runner.can_run(device_id, trigger.key):
            return
        # Observe tracks the baseline in the caller and stops here; it is not a run, so no breaker counts it (D-14)
        if self.effective_mode(device_id) == MODE_OBSERVE:
            LOGGER.info(
                "Observe mode: device %s would have run %s, no actions were run",
                shown(device.name),
                shown(trigger.label),
            )
            return
        # Only a real change that would run counts; a paused device tracks its baseline and runs nothing (D-15)
        if device.breaker.tripped:
            LOGGER.debug("Device %s is paused by its circuit breaker, its change runs no actions", device.name)
            return
        if not device.breaker.record():
            self._trip(device)
            return
        # Only the device id and the canonical value reach templates, never the raw payload
        self.runner.enqueue(
            device_id,
            device.name,
            trigger.label,
            trigger.key,
            {"device_id": device_id, "state": value},
        )

    def _new_breaker(self, spec: DeviceSpec) -> CircuitBreaker:
        """Build the breaker of a device from its configured limits (D-14)."""
        return CircuitBreaker(spec.breaker_max_runs, float(spec.breaker_window), clock=self._breaker_clock)

    def _breaker_clock(self) -> float:
        """Read the manager clock at call time so a replaced clock reaches breakers that already exist."""
        return self.clock()

    @callback
    def _trip(self, device: Device) -> None:
        """
        Pause a device whose breaker just tripped: warn, raise the Repairs issue and stop its runs (D-15, D-16).

        The log line and the issue carry only the device name and the two limits, never action data (T-02-18). Stopping
        the running and queued runs is what actually ends a loop: otherwise sequences already in flight would still
        publish state changes (A3).
        """
        LOGGER.warning(
            "Circuit breaker tripped for device %s: more than %d runs within %d seconds, so the device is paused",
            device.name,
            device.breaker.max_runs,
            device.spec.breaker_window,
        )
        self._create_breaker_issue(device)
        self._tripped[device.device_id] = _hash_fingerprint(device.signature)
        self._schedule_save()
        self._entry.async_create_background_task(
            self._hass, self.runner.async_stop_runs(device.device_id), name=f"{DOMAIN} stop {device.name}"
        )

    @callback
    def _restore_tripped(self, device: Device) -> None:
        """
        Pause a device that was tripped before the restart, as long as its configuration is unchanged (D-17).

        Issues are not persistent, so the issue is created again at every start. A stored hash that no longer matches
        means the configuration changed while the entry was not loaded, which is a release (D-15).
        """
        if (stored := self._tripped.get(device.device_id)) is None:
            return
        if stored != _hash_fingerprint(device.signature):
            del self._tripped[device.device_id]
            self._schedule_save()
            return
        device.breaker.trip()
        LOGGER.warning(
            "Circuit breaker of device %s is still tripped: it stays paused until its settings change or the "
            "integration is reloaded",
            device.name,
        )
        self._create_breaker_issue(device)

    @callback
    def _create_breaker_issue(self, device: Device) -> None:
        """Show the Repairs issue of a paused device; it names the device and the limits only."""
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            f"{ISSUE_CIRCUIT_BREAKER_PREFIX}{device.device_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="circuit_breaker_tripped",
            translation_placeholders={
                # The name of a mirror comes from the broker
                "device": escape_markdown(device.name) if device.mirror is not None else device.name,
                "max_runs": str(device.spec.breaker_max_runs),
                "window": str(device.spec.breaker_window),
            },
        )

    @callback
    def _delete_device_issues(self, device_id: str) -> None:
        """Delete every per-device Repairs issue of a device: the prefix of each issue family plus the device id."""
        for prefix in ISSUE_DEVICE_PREFIXES:
            ir.async_delete_issue(self._hass, DOMAIN, f"{prefix}{device_id}")

    @callback
    def _delete_breaker_issue(self, device_id: str) -> None:
        """Delete the circuit breaker issue of a device."""
        ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_CIRCUIT_BREAKER_PREFIX}{device_id}")

    @callback
    def _on_test_message(self, device_id: str, msg: IncomingMessage) -> None:
        """
        Run the actions of the trigger whose test button was pressed (D-13).

        The press never touches the tracker, the baseline or the state topic, and nothing is published. A retained
        message is a replay, never a press, so it must not run actions (T-02-09). Only a payload that equals a
        StateValue of the device runs anything (T-02-08). A device that is observed or disabled runs nothing.
        """
        if msg.retain or (device := self._device(device_id)) is None or self._test_blocked(device):
            return
        value = device.spec.accepted.get(msg.payload.strip().lower())
        if value is None:
            self._log_ignored(device, msg.payload)
            return
        if (trigger := device.spec.triggers.get(trigger_key(value))) is not None:
            self._enqueue_test(device, trigger)

    async def async_press_test(self, device_id: str, key: str) -> None:
        """
        Run the actions of one trigger of a device as a test, the way a native test button does (MIG-03).

        The press never touches the tracker, the baseline or the state topic, and nothing is published. It passes the
        same mode gate as the test topic; an unknown device id or trigger key does nothing.
        """
        if (device := self._device(device_id)) is None or (trigger := device.spec.triggers.get(key)) is None:
            return
        if not self._test_blocked(device):
            self._enqueue_test(device, trigger)

    def _test_blocked(self, device: Device) -> bool:
        """Return whether the mode stops a test run; the test buttons follow the mode of the state topic (D-14)."""
        if (mode := self.effective_mode(device.device_id)) == MODE_RUN:
            return False
        LOGGER.debug("The test press of device %s runs no actions in %s mode", shown(device.name), mode)
        return True

    @callback
    def _enqueue_test(self, device: Device, trigger: TriggerSpec) -> None:
        """Enqueue the actions of a trigger as a test run, unless the runner has no Script for it (T-04-19)."""
        device_id = device.device_id
        if not self.runner.can_run(device_id, trigger.key):
            return
        self.runner.enqueue(
            device_id,
            device.name,
            trigger.label,
            trigger.key,
            {"device_id": device_id, "state": trigger.value},
            test=True,
        )

    @staticmethod
    def _log_ignored(device: Device, payload: str) -> None:
        """Log an unknown payload; the empty retained-clear message is only debug noise (D-02)."""
        if not payload:
            LOGGER.debug("Ignoring empty payload for device %s", device.name)
            return
        LOGGER.warning("Ignoring unknown payload %s for device %s", shown(payload), device.name)
