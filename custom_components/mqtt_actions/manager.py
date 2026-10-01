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
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_RESTORED
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from .actions import ActionsInvalid, async_validate_actions, validate_spec_structure
from .breaker import CircuitBreaker
from .const import (
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
    LOGGER,
    MAX_LOGGED_PAYLOAD_LENGTH,
    MAX_MIRRORS,
    STORE_APPROVALS,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_MIRRORS,
    STORE_PUBLISHED,
    STORE_REVS,
    STORE_SAVE_DELAY,
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
    build_document,
    canonical_json,
    escape_markdown,
    parse_document,
    serialize_document,
    spec_has_actions,
)
from .model import DeviceSpec, spec_from_subentry, trigger_key
from .mqtt_gateway import IncomingMessage, MqttGateway
from .runner import ActionRunner
from .state import StateTracker
from .sync import SyncManager
from .topics import state_topic, test_topic
from .trust import build_approval_view

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
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


def _parse_approvals(stored: dict[str, Any]) -> dict[str, str]:
    """Return the approved actions hash per device from a loaded Store payload; anything malformed is dropped."""
    approvals = stored.get(STORE_APPROVALS)
    if not isinstance(approvals, dict):
        return {}
    return {key: value for key, value in approvals.items() if isinstance(key, str) and isinstance(value, str)}


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
        if domain == DOMAIN and (issue_id.startswith(ISSUE_DEVICE_PREFIXES) or issue_id == ISSUE_DISCOVERY_DISABLED):
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
        self._running = False
        # Owned device ids whose document the parser rejects; logged once, not published (CR-03)
        self._unpublishable: set[str] = set()
        # Replaceable so tests control the breaker window; production uses the monotonic clock
        self.clock: Callable[[], float] = time.monotonic
        self.sync = SyncManager(self)

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

    async def async_start(self) -> None:
        """Load the persisted state, clear orphans, start every configured device and publish availability online."""
        await self._async_load_store()
        integration = await async_get_integration(self._hass, DOMAIN)
        self._publisher = DiscoveryPublisher(self.gateway, self._base_topic, str(integration.version))
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
        # The lock is held from the first subscribe until the owned devices are registered and published: a retained
        # document replayed while the subscribes are awaited queues its ingest on this lock, and by the time it runs
        # the owned ids are in `devices`, so a foreign claim for an owned id can never become a mirror (CR-02)
        async with self._lock:
            # Subscribed before anything is published, so the owner sees its own documents and every foreign write
            await self.sync.async_start()
            await self._async_orphan_cleanup()
            await self._async_reconcile_locked(startup=True)
            await self._async_publish_owned()
        await self._async_publish_availability(AvailabilityState.ONLINE)

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
            if self._publisher is not None:  # None when the start failed before the publisher existed
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
            self._entry.async_create_background_task(self._hass, self._async_republish(), name=f"{DOMAIN} republish")

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
        self._stored_mirrors = _parse_mirrors(stored)
        self._approvals = _parse_approvals(stored)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return the persisted state; devices without a baseline are omitted (D-07)."""
        return {
            STORE_LAST_ACTED: {
                device_id: device.tracker.last_acted
                for device_id, device in {**self.devices, **self.mirrors}.items()
                if device.tracker.last_acted is not None
            },
            STORE_MIRRORS: {
                device_id: device.mirror.payload for device_id, device in self.mirrors.items() if device.mirror
            },
            STORE_APPROVALS: dict(self._approvals),
            STORE_PUBLISHED: sorted(self._published),
            STORE_TRIPPED: dict(self._tripped),
            STORE_REVS: {device_id: dict(value) for device_id, value in self._revs.items()},
        }

    @callback
    def _schedule_save(self) -> None:
        """Save with a delay so a burst of messages causes one write."""
        self._store.async_delay_save(self._data_to_save, STORE_SAVE_DELAY)

    async def async_apply_mirror(self, parsed: ParsedDocument) -> None:
        """
        Create or update the read-only mirror of a validated foreign document; the caller holds the lock.

        A mirror is a Device without a Script: it follows the state topic for its baseline and runs nothing, because the
        runner only runs triggers of a device it built a Script for (TRU-01). It publishes nothing, is not in `devices`,
        not in the published set and never touched by a reconcile of the owned subentries (D-08, D-19). Whether the
        document is the pinned owner's and differs from the mirror is decided by the caller; an owned id is ignored.
        """
        device_id = parsed.device_id
        if device_id in self.devices:
            return
        if (existing := self.mirrors.get(device_id)) is not None:
            self._update_mirror(existing, parsed)
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
        self._clean_registry(device_id)
        self._schedule_save()

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
    def _mirror_info(parsed: ParsedDocument) -> MirrorInfo:
        """Return what a follower records of a document: its owner, both hashes, the payload and the static analysis."""
        analysis: ActionAnalysis = analyze_spec(parsed.spec)
        return MirrorInfo(
            owner=parsed.owner,
            owner_name=parsed.owner_name,
            rev=parsed.rev,
            content_hash=parsed.content_hash,
            actions_hash=parsed.actions_hash,
            payload=parsed.payload,
            denied=analysis.denied,
            templated=analysis.templated,
            residual=analysis.residual,
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
        mirror = self._mirror_info(parsed)
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

    async def _async_subscribe_mirror(self, device: Device) -> None:
        """Register a mirror and subscribe to its state and test topics; a failed subscribe leaves nothing behind."""
        device_id = device.device_id
        # Registered before subscribing: the retained state can arrive while the subscribe call is still awaited
        self.mirrors[device_id] = device
        try:
            device.unsubscribe = await self.gateway.async_subscribe(
                state_topic(self._base_topic, device_id), partial(self._on_message, device_id)
            )
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
        await self.async_publish_config(device, changed_only=True)
        await self.async_publish_discovery(device)

    async def _async_remove_device(self, device_id: str) -> None:
        """
        Remove a deleted device in the order that keeps the manager from reading its own clear messages (D-16).

        The device leaves `devices` first: the message handlers only act for devices in `devices`, so the discovery
        clear, the config tombstone and the state clear of this delete can never look like a foreign event that the
        owner would heal, which would resurrect the device (D-18). Then the discovery is cleared so the entity
        disappears, the subscriptions end, the config tombstone follows and the retained state goes last. A clear that
        fails keeps the id in the published set so the next start retries all three topics.
        """
        assert self._publisher is not None  # noqa: S101
        device = self.devices.pop(device_id)
        discovery_cleared = await _async_attempt(
            partial(self._publisher.async_clear_device, device_id), f"clear the discovery of device {device.name}"
        )
        if device.unsubscribe is not None:
            device.unsubscribe()
        if device.unsubscribe_test is not None:
            device.unsubscribe_test()
        config_cleared = await _async_attempt(
            partial(self._publisher.async_clear_config, device_id), f"clear the config document of device {device.name}"
        )
        state_cleared = await _async_attempt(
            partial(self._publisher.async_clear_state, device_id), f"clear the retained state of device {device.name}"
        )
        await self.runner.async_unload(device_id, remove_issue=True)
        self._delete_device_issues(device_id)
        self.sync.forget(device_id)
        self._stored_last_acted.pop(device_id, None)
        self._tripped.pop(device_id, None)
        self._revs.pop(device_id, None)
        if discovery_cleared and config_cleared and state_cleared:
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
        known = self._revs.get(device_id)
        try:
            document = build_document(
                device.spec,
                owner=self._instance_id,
                owner_name=self._entry.data[CONF_INSTANCE_NAME],
                rev=1,
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
        """Handle a state message: separate baseline from edge and enqueue the matching script."""
        if (device := self._device(device_id)) is None:
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
            {"device_id": device_id, "state": decision.value},
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
        StateValue of the device runs anything (T-02-08).
        """
        if msg.retain or (device := self._device(device_id)) is None:
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
