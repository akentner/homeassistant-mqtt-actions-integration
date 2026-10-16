"""
Registry takeover of the legacy core-MQTT entities of a device into this integration (D-05, D-07, MIG-01).

Before native entities, a switch or select device and its test buttons were created by core MQTT discovery and belong
to the MQTT config entry. This module moves them, with entity id, registry id, device id, area and user name intact,
to the hub entry of this integration. It is registry logic only: it never publishes and never imports the MQTT
integration. The migrate payload that unloads the discovered entities and the retained clear that follows belong to
the caller, which keeps the broker order, a fixed rule of the phase, in one place.

The module also removes the duplicates that a replayed legacy discovery creates after a takeover: core MQTT replays
retained discovery at its own pace, so a second set of `mqtt` entities can appear next to the moved ones. That catch is
registry logic as well; it still never publishes and never imports the MQTT integration. The same goes for the helper
that disables an enabled duplicate which core MQTT created for a native device, whoever published its discovery.

The core-prefix discovery topic of a device is shared by every instance on the broker, so whether the catch may let it
go empty is one decision for the whole fleet: `shared_topic_verdict` takes the role of this instance, the topic content,
this instance's own keep and what the online peers announce, and nothing else decides it (D-02 to D-05, D-08).

The order of the steps is load-bearing and each edge is pinned by a core test in `tests/test_takeover.py`:
nothing moves while a legacy entity is loaded, entities move before their device, and the companion device of the
mode select is merged last.
"""

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import entity_sources
from homeassistant.helpers.typing import UNDEFINED

from .const import DOMAIN, LOGGER
from .discovery import DiscoveryContent

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

TAKEOVER_UNLOAD_TIMEOUT = 10.0
TAKEOVER_RETRY_INTERVAL = 0.25
# Core MQTT replays retained discovery at its own pace and exposes no signal for "done"; its own discovery cooldown is
# 5 seconds, which is the quiet period the catch for replayed duplicates waits for
REPLAY_QUIET_SECONDS = 5.0
# A catch that finds the content of a device unknown because the discovery settle is late or inside its grace checks
# again, at most this often per start and never sooner than the floor below (WR-02)
REPLAY_CATCH_RETRIES = 5
REPLAY_RETRY_MIN_SECONDS = 1.0

# The domain of core MQTT is a literal: only `mqtt_gateway.py` may import the MQTT integration
MQTT_DOMAIN = "mqtt"
LEGACY_DOMAINS = frozenset({"switch", "select", "button"})
# The export publishes one component per device, a switch or a select, and never a test button
EXPORT_DOMAINS = frozenset({"switch", "select"})
LEGACY_TEST_PREFIX = "_test_"
# Core stores an assistant's exposure default on an entry the first time the assistant asks, and the stored value
# cannot tell that default from a user's choice: it is no customization
CORE_OPTION_KEYS = frozenset({"should_expose"})
# The core-prefix content that holds no export, so a twin the integration disabled may go: for EMPTY content always,
# for LEGACY content only when the shared topic may go empty (D-02, D-05)
REMOVABLE_DISABLED_CONTENT = frozenset({DiscoveryContent.LEGACY, DiscoveryContent.EMPTY})


class PeerKeep(StrEnum):
    """
    What the online peers announce about one device id, for the gate of the shared legacy topic (D-02, D-03).

    KEPT: an online peer lists the id among the devices it keeps an enabled legacy row of. UNKNOWN: an online peer sent
    no valid list (an older version, an overflow or a malformed field), or the roster had no room for a peer.
    UNHEARD: an instance announced online has sent no heartbeat since this start. CLEAR: none of these; offline and
    stale peers never count. The precedence is KEPT, UNKNOWN, UNHEARD, CLEAR.
    """

    CLEAR = "clear"
    UNHEARD = "unheard"
    UNKNOWN = "unknown"
    KEPT = "kept"


@dataclass(frozen=True, slots=True)
class TopicVerdict:
    """
    What the catch may do on the shared core-prefix topic of one device id (D-02 to D-05, D-08).

    `remove_disabled`: an integration-disabled twin may leave the registry, though core may clear the topic for it.
    `may_clear`: the owner may publish its explicit retained clear. `rearm`: only a peer not heard yet blocks, so the
    catch may look again once a heartbeat interval passed (D-04).
    """

    remove_disabled: bool
    may_clear: bool
    rearm: bool


_NOTHING = TopicVerdict(remove_disabled=False, may_clear=False, rearm=False)


def shared_topic_verdict(*, owner: bool, content: DiscoveryContent, local_keeps: bool, peers: PeerKeep) -> TopicVerdict:
    """
    Return what the catch may do on the shared core-prefix topic of a device; a pure decision, no hass and no log.

    EMPTY content holds nothing to wipe, so an integration-disabled twin may go and there is nothing to clear (D-02).
    Any other content than LEGACY (an export or unknown content) keeps everything (CR-01, D-03). On LEGACY content only
    the owner may let the topic go empty (D-05): a follower keeps its disabled twins, because core's clear-on-remove
    hook would empty a topic every instance shares. The owner keeps everything while it keeps an enabled legacy row
    itself (D-08), and while an online peer keeps one (KEPT) or has not said what it keeps (UNKNOWN) (D-02, D-03). A
    peer announced online but not heard since this start keeps everything as well, and asks for a re-arm (UNHEARD,
    D-04). Only CLEAR lets the owner remove the twin and clear the topic.
    """
    if content is DiscoveryContent.EMPTY:
        return TopicVerdict(remove_disabled=True, may_clear=False, rearm=False)
    if content is not DiscoveryContent.LEGACY or not owner or local_keeps:
        return _NOTHING
    if peers is PeerKeep.CLEAR:
        return TopicVerdict(remove_disabled=True, may_clear=True, rearm=False)
    if peers is PeerKeep.UNHEARD:
        return TopicVerdict(remove_disabled=False, may_clear=False, rearm=True)
    return _NOTHING


class TakeoverStatus(StrEnum):
    """Outcome of a takeover: no legacy device, everything moved, or postponed because an entity is still loaded."""

    NOTHING = "nothing"
    DONE = "done"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class TakeoverTarget:
    """The device to take over; the subentry id of an owned device and None for a mirror, which sits under the entry."""

    device_id: str
    subentry_id: str | None


class ReplayTwinsError(Exception):
    """
    Raised by `remove_replay_twins` when the removal of a row raised (FIX-06, review 2 IN-01).

    `removed` counts the rows whose removal returned before the failure; the row that raised is never counted, even
    when the registry removed it. The emptied core MQTT device is already gone and the count is already logged when
    this is raised. The original error is the `__cause__`. The message carries no entity data (T-04-14).
    """

    def __init__(self, removed: int) -> None:
        """Keep the count of the rows removed before the failure."""
        super().__init__("The removal of a replayed duplicate raised")
        self.removed = removed


def legacy_device(hass: HomeAssistant, mqtt_entry_id: str, device_id: str) -> dr.DeviceEntry | None:
    """Return the core MQTT device the legacy discovery payload created for a device id, or None."""
    return dr.async_get(hass).async_get_device_by_identifier((MQTT_DOMAIN, f"{DOMAIN}_{device_id}"), mqtt_entry_id)


def is_legacy_entity(entity: er.RegistryEntry, device_id: str, mqtt_entry_id: str, mqtt_device_id: str) -> bool:
    """
    Return whether a registry entry really is a legacy entity of this integration's MQTT device.

    The unique id alone never decides: a hostile document may carry the device id of an unrelated MQTT entity (T-5-01).
    Platform, config entry, device, domain and the shape of the unique id must all match.
    """
    return (
        entity.platform == MQTT_DOMAIN
        and entity.config_entry_id == mqtt_entry_id
        and entity.device_id == mqtt_device_id
        and entity.domain in LEGACY_DOMAINS
        and (entity.unique_id == device_id or entity.unique_id.startswith(f"{device_id}{LEGACY_TEST_PREFIX}"))
    )


def _legacy_entries(
    hass: HomeAssistant, device: dr.DeviceEntry, device_id: str, mqtt_entry_id: str
) -> list[er.RegistryEntry]:
    """Return the legacy registry entries of the MQTT device, disabled ones included."""
    entries = er.async_entries_for_device(er.async_get(hass), device.id, include_disabled_entities=True)
    return [entry for entry in entries if is_legacy_entity(entry, device_id, mqtt_entry_id, device.id)]


async def _async_wait_unloaded(
    hass: HomeAssistant,
    collect: Callable[[], list[er.RegistryEntry]],
    *,
    unload_timeout: float,
    retry_interval: float,
) -> list[er.RegistryEntry] | None:
    """Wait until no legacy entity of the device is loaded; return the entries, or None when the wait ran out."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + unload_timeout
    while True:
        entries = collect()
        loaded = entity_sources(hass)
        if not any(entry.entity_id in loaded for entry in entries):
            return entries
        if loop.time() >= deadline:
            return None
        await asyncio.sleep(retry_interval)


async def async_take_over(  # noqa: PLR0913
    hass: HomeAssistant,
    entry: ConfigEntry,
    target: TakeoverTarget,
    *,
    mqtt_entry_id: str,
    unload_timeout: float = TAKEOVER_UNLOAD_TIMEOUT,
    retry_interval: float = TAKEOVER_RETRY_INTERVAL,
) -> TakeoverStatus:
    """
    Move the legacy MQTT entities and device of one device id under this entry, in the one safe order.

    Returns NOTHING when core MQTT has no device for the id, DEFERRED when a legacy entity is still loaded after the
    wait (nothing was changed, the caller retries at the next setup) and DONE otherwise.
    """
    if (device := legacy_device(hass, mqtt_entry_id, target.device_id)) is None:
        return TakeoverStatus.NOTHING
    entries = await _async_wait_unloaded(
        hass,
        lambda: _legacy_entries(hass, device, target.device_id, mqtt_entry_id),
        unload_timeout=unload_timeout,
        retry_interval=retry_interval,
    )
    if entries is None:
        LOGGER.warning("Takeover of device %r postponed: its legacy entities are still loaded", _short(target))
        return TakeoverStatus.DEFERRED

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    moved = 0
    # Entities first: moving the device first would remove the entities that still belong to the old entry
    loaded = entity_sources(hass)
    for legacy in entries:
        if (twin_id := entity_registry.async_get_entity_id(legacy.domain, DOMAIN, legacy.unique_id)) is not None:
            # Core does not guard a duplicate key: a platform move would leave two entries (T-5-09). One of the two
            # goes, and the one that carries the identity the user knows stays (WR-04). The legacy entry is not loaded
            # and a loaded twin is never removed, so a removal publishes nothing. A disabled legacy entry stays where
            # it is: core MQTT clears the retained topic when a row it discovered while disabled leaves the registry,
            # and for a mirror that topic holds the other instance's export (CR-01). An enabled one is disabled first,
            # so its deleted record restores as disabled (WR-01). The twin's record is left enabled: only this
            # integration's native platform creates that unique id again, and its entity is meant to be enabled.
            twin = entity_registry.entities[twin_id]
            if twin_id not in loaded and _carries_the_identity(legacy, twin):
                entity_registry.async_remove(twin_id)
            else:
                if legacy.disabled_by is None:
                    entity_registry.async_update_entity(
                        legacy.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                    )
                    entity_registry.async_remove(legacy.entity_id)
                continue
        entity_registry.async_update_entity_platform(
            legacy.entity_id,
            DOMAIN,
            new_config_entry_id=entry.entry_id,
            new_config_subentry_id=UNDEFINED if target.subentry_id is None else target.subentry_id,
        )
        moved += 1

    leftovers = [
        remaining
        for remaining in er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True)
        if remaining.config_entry_id == mqtt_entry_id
    ]
    if leftovers:
        # Moving the device would remove these entries, so it stays where it is
        LOGGER.warning(
            "Device %r keeps its MQTT device: it has entries this integration did not create", _short(target)
        )
        return TakeoverStatus.DONE
    native = device_registry.async_get_device_by_identifier((DOMAIN, target.device_id), entry.entry_id)
    if moved == 0 and native is not None and native.id != device.id:
        # The native device exists already and every legacy entry was a duplicate: the legacy device is empty
        device_registry.async_remove_device(device.id)
        return TakeoverStatus.DONE
    device_registry.async_update_device(
        device.id, new_config_entry_id=entry.entry_id, new_config_subentry_id=target.subentry_id
    )
    _merge_companion(hass, entry, target, device)
    return TakeoverStatus.DONE


def _is_kept(entity_registry: er.EntityRegistry, legacy: er.RegistryEntry, entry_id: str) -> bool:
    """
    Return whether a legacy entry is no replayed duplicate but an entry to keep (WR-03, WR-04).

    It has no native twin under this config entry, it holds the user's choices, or it carries the identity of the
    two. One predicate for the catch and for the kept set a heartbeat announces, so the two can never drift apart.
    """
    twin_id = entity_registry.async_get_entity_id(legacy.domain, DOMAIN, legacy.unique_id)
    twin = entity_registry.entities.get(twin_id) if twin_id is not None else None
    return (
        twin is None
        or twin.config_entry_id != entry_id
        or _is_customized(legacy)
        or _carries_the_identity(legacy, twin)
    )


def keeps_enabled_legacy_row(hass: HomeAssistant, entry_id: str, device_id: str, *, mqtt_entry_id: str) -> bool:
    """
    Return whether this instance keeps an enabled legacy entry of the device, the one the catch never removes (D-08).

    A kept entry that is enabled is loaded, so an empty retained payload on the shared topic would delete it. False
    without a legacy device. Registry logic only.
    """
    if (device := legacy_device(hass, mqtt_entry_id, device_id)) is None:
        return False
    entity_registry = er.async_get(hass)
    return any(
        legacy.disabled_by is None and _is_kept(entity_registry, legacy, entry_id)
        for legacy in _legacy_entries(hass, device, device_id, mqtt_entry_id)
    )


def _remove_planned(
    entity_registry: er.EntityRegistry, plan: list[tuple[er.RegistryEntry, bool]]
) -> tuple[int, Exception | None]:
    """Remove the planned rows in order; return how many removals returned and the error that stopped the loop."""
    removed = 0
    try:
        for legacy, disable_first in plan:
            if disable_first:
                # Disabled first, so core unloads the entity and clears nothing on removal, and the deleted record
                # carries the disabled state that a later restore of the same row inherits (WR-01)
                entity_registry.async_update_entity(legacy.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
            entity_registry.async_remove(legacy.entity_id)
            removed += 1
    except Exception as err:  # noqa: BLE001
        # The row that raised may have left the registry anyway and is not counted: the caller still removes an emptied
        # device and learns the count and the failure from the raise after it (FIX-06)
        return removed, err
    return removed, None


def remove_replay_twins(  # noqa: PLR0913
    hass: HomeAssistant,
    entry_id: str,
    device_id: str,
    *,
    mqtt_entry_id: str,
    content: DiscoveryContent = DiscoveryContent.UNKNOWN,
    may_empty_topic: bool = False,
) -> int:
    """
    Remove the legacy entries a replayed discovery created next to the moved entities of a device; return the count.

    A candidate is a legacy entry of the core MQTT device of the id that has a native twin under this config entry.
    It goes only when the twin carries the identity: an older or customized legacy entry is left to the takeover pass,
    and an entry without a twin is no duplicate. A customized entry stays whatever the twin holds: with both entries
    customized no rule knows which one automations use, and removing it would leave the user's choices only in a
    deleted record that no UI reaches (WR-03). The twin is never removed. A disabled entry goes only when the
    integration disabled it and `content`, what the core-prefix discovery topic of the id holds, allows it: core MQTT
    aborts the add of a row it discovers disabled and publishes an empty retained discovery as soon as that row leaves
    the registry, and that topic is shared by every instance. With EMPTY content the clear wipes nothing, so the entry
    goes. With LEGACY content it goes only when the caller says the topic may go empty (`may_empty_topic`): only the
    owner may let it, and only while no online instance keeps a legacy row of the device (D-02, D-05,
    `shared_topic_verdict`); the default False keeps the entry, like the UNKNOWN default of `content`. With EXPORT or
    UNKNOWN content, the default for a caller that passes none, every disabled entry stays, because the clear would
    wipe the topic of another instance's export (CR-01, D-01, D-03). With LEGACY content a disabled entry also stays
    while an enabled
    legacy entry of the device stays: core discovered the disabled row in this run, and the clear it publishes when the
    row leaves deletes every loaded legacy entry of the device, the kept ones included (D-08). A kept entry that is
    disabled is not loaded and survives that clear. The keeps are therefore decided before anything is removed. An
    entry the user disabled stays whatever the content (D-04). A
    disabled entry is removed as it is: its deleted record keeps `integration` (WR-01). An enabled entry is disabled
    before it is removed: core MQTT clears the topic of a loaded entity that leaves the registry as well, and the
    deleted record of an enabled entry would restore as enabled (WR-01). Disabling and removing run in one synchronous
    step, so core cannot discover the row in between. Registry logic only: nothing is published here, and core
    publishes nothing for an enabled row removed this way. The emptied MQTT device goes too, unless an entry remains on
    it, whether this integration created it or not. A row whose removal raises stops the loop: the emptied device
    still goes, the rows removed before it are logged, and `ReplayTwinsError` with that count is raised from the error
    (FIX-06).
    """
    if (device := legacy_device(hass, mqtt_entry_id, device_id)) is None:
        return 0
    entity_registry = er.async_get(hass)
    # The keeps are decided before anything goes: whether a disabled row may go depends on what else stays (D-08)
    keeps_an_enabled_row = False
    plan: list[tuple[er.RegistryEntry, bool]] = []  # (entry, disable first)
    for legacy in _legacy_entries(hass, device, device_id, mqtt_entry_id):
        if _is_kept(entity_registry, legacy, entry_id):
            keeps_an_enabled_row = keeps_an_enabled_row or legacy.disabled_by is None
            continue
        if legacy.disabled_by is None:
            plan.append((legacy, True))
        elif legacy.disabled_by is er.RegistryEntryDisabler.INTEGRATION and (
            content is DiscoveryContent.EMPTY or (content in REMOVABLE_DISABLED_CONTENT and may_empty_topic)
        ):
            # The topic holds no export, and on LEGACY content the caller decided that no instance keeps a row the
            # clear core may publish for this row would delete (D-02, D-05)
            plan.append((legacy, False))
        # Else core may hold a hook for an aborted add of this row, and its removal may clear an export (CR-01)
    if keeps_an_enabled_row and content is DiscoveryContent.LEGACY:
        # Core discovered a disabled row of this topic in this run and holds a clear-on-remove hook for it: its empty
        # retained payload would delete every loaded legacy row of the device, the kept ones included (D-08). A kept
        # row that is disabled is not loaded, and core's clear leaves it in the registry
        plan = [(legacy, disable_first) for legacy, disable_first in plan if disable_first]
    if not plan:
        return 0
    removed, failure = _remove_planned(entity_registry, plan)
    # Removing a device removes the entries on it, so it goes only when nothing at all is left on it
    if not er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True):
        device_registry = dr.async_get(hass)
        # Removing the entities may have dropped the device already
        if device_registry.async_get(device.id) is not None:
            device_registry.async_remove_device(device.id)
    if removed:
        LOGGER.info("Removed %d duplicate entities that a replayed legacy discovery created", removed)
    if failure is not None:
        raise ReplayTwinsError(removed) from failure
    return removed


def disable_duplicates(hass: HomeAssistant, entry_id: str, device_id: str, *, mqtt_entry_id: str) -> int:
    """
    Disable the enabled core MQTT duplicates of a native device; return the count.

    An export on the prefix core MQTT listens to asks for a disabled duplicate, whichever instance published it.
    When core MQTT creates the entry again, the registry restores the state of an earlier deleted entry with the
    same platform and unique id, and that state may be enabled. A candidate is the switch or select entry of the
    core MQTT device of the id whose unique id is exactly the id, whose disabled state is None and that has a native
    twin under this config entry, unless it holds the user's choices (`_is_customized`), whatever the twin holds, or
    the twin is turned off: an entry without a twin is a live entity, a customized one is the entity the user knows,
    and with both customized no rule knows which one automations use. A twin that is disabled, or that the user hid,
    is the entity the user rejected, and disabling the legacy entry as well would leave no enabled entity for the id
    (WR-03). This is the customization half of the identity test of `remove_replay_twins` and deliberately not its
    age half: a row that core restores from a deleted record keeps its old creation time, and that row is the
    duplicate this guard exists for. The twin, a test button, a disabled entry and every other unique id are never
    touched, and nothing is removed or enabled. Registry logic only: nothing is published. The disabled entry stays
    in the registry for now: core MQTT clears the retained topic, another instance's export included, when a row it
    discovered while disabled leaves the registry (CR-01). The takeover never removes it, and the start-up replay catch
    removes it only when the core-prefix topic holds the legacy payload or nothing (D-02); with an export or unknown
    content it keeps the disabled state `integration` across restarts, and a later export finds it disabled.
    """
    if (device := legacy_device(hass, mqtt_entry_id, device_id)) is None:
        return 0
    entity_registry = er.async_get(hass)
    disabled = 0
    for entry in _legacy_entries(hass, device, device_id, mqtt_entry_id):
        if entry.unique_id != device_id or entry.domain not in EXPORT_DOMAINS or entry.disabled_by is not None:
            continue
        twin_id = entity_registry.async_get_entity_id(entry.domain, DOMAIN, entry.unique_id)
        if twin_id is None:
            continue
        twin = entity_registry.entities[twin_id]
        if twin.config_entry_id != entry_id or _is_customized(entry) or _is_turned_off(twin):
            # The entry that holds the user's choices is the one automations and dashboards use (WR-02), and the one
            # left next to a twin the user turned off is the one they kept (WR-03)
            continue
        entity_registry.async_update_entity(entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        disabled += 1
    return disabled


class KeptReason(StrEnum):
    """Why the guard keeps an enabled core MQTT duplicate: the user customized it, or turned the native twin off."""

    CUSTOMIZED = "customized"
    TWIN_REJECTED = "twin_rejected"


def kept_duplicates(
    hass: HomeAssistant, entry_id: str, device_id: str, *, mqtt_entry_id: str
) -> list[tuple[str, KeptReason]]:
    """
    Return the enabled core MQTT duplicates of a native device that the guard keeps, with their reason (FIX-08, D-01).

    A candidate is what `disable_duplicates` looks at: the switch or select entry of the core MQTT device of the id
    whose unique id is exactly the id, that is enabled and that has a native twin under this config entry. A twin
    turned off by the user makes it `TWIN_REJECTED` (WR-03), even when the entry is customized too, because the guard
    keeps it for that reason alone; otherwise an entry that holds the user's choices is `CUSTOMIZED` (WR-02). Any other
    candidate is the one the guard disables, so it is not listed. A disabled entry, such as the twin the 09.1 D-03 /
    09.2 D-03 fail-safe leaves behind, is never a candidate (D-03). Registry read only: nothing is written, removed,
    disabled, enabled or published.
    """
    if (device := legacy_device(hass, mqtt_entry_id, device_id)) is None:
        return []
    entity_registry = er.async_get(hass)
    kept: list[tuple[str, KeptReason]] = []
    for entry in _legacy_entries(hass, device, device_id, mqtt_entry_id):
        if entry.unique_id != device_id or entry.domain not in EXPORT_DOMAINS or entry.disabled_by is not None:
            continue
        twin_id = entity_registry.async_get_entity_id(entry.domain, DOMAIN, entry.unique_id)
        if twin_id is None:
            continue
        twin = entity_registry.entities[twin_id]
        if twin.config_entry_id != entry_id:
            continue
        if _is_turned_off(twin):
            kept.append((entry.entity_id, KeptReason.TWIN_REJECTED))
        elif _is_customized(entry):
            kept.append((entry.entity_id, KeptReason.CUSTOMIZED))
    return kept


def has_moved_entities(hass: HomeAssistant, entry: ConfigEntry, device_id: str) -> bool:
    """
    Return whether an entity of the device already sits under this integration in the entity registry.

    After a takeover that raised halfway, the registry and not the return path says what happened: an entry that
    moved cannot go back to core MQTT, so the device has to stay native for the run (WR-02).
    """
    entity_registry = er.async_get(hass)
    return any(
        entity.platform == DOMAIN
        and entity.config_entry_id == entry.entry_id
        and entity.domain in LEGACY_DOMAINS
        and (entity.unique_id == device_id or entity.unique_id.startswith(f"{device_id}{LEGACY_TEST_PREFIX}"))
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )


async def async_flush_registries(hass: HomeAssistant) -> bool:
    """
    Write the entity and device registry to disk now and return whether both writes went through.

    Home Assistant only schedules a save of a registry change, about ten seconds ahead. A takeover is recorded as done
    in the Store of this integration, so a crash inside that window would leave the Store claiming a move the
    registry files never saw, and the entities would start again under new ids (WR-01). Home Assistant has no public
    flush; the registry's own store is the narrowest way to force one, and a failure only costs the early write.
    """
    flushed = True
    for registry in (er.async_get(hass), dr.async_get(hass)):
        try:
            await registry._store.async_save(registry._data_to_save())  # noqa: SLF001
        except Exception:  # noqa: BLE001
            LOGGER.warning("A registry could not be written ahead of its schedule after the native takeover")
            LOGGER.debug("The registry flush failed", exc_info=True)
            flushed = False
    return flushed


def _is_customized(entry: er.RegistryEntry) -> bool:
    """
    Return whether the user changed anything on the entry that is worth keeping (WR-02).

    Name, icon, area, tags, voice aliases, a device class override, options the user set, and the hidden state a
    wrapper helper such as Switch-as-X sets on the entity it points at. A new entry carries the computed name as its
    only alias. A state the user turned off is no customization but a rejection of that entry (WR-03). A renamed
    entity id is not detectable: core's automatic entity id also differs for a row restored from a deleted record,
    which is the duplicate the guard exists for.
    """
    return bool(
        entry.name
        or entry.icon
        or entry.area_id
        or entry.labels
        or entry.categories
        or list(entry.aliases) != [er.COMPUTED_NAME]
        or entry.device_class
        or _has_user_options(entry)
        or entry.hidden_by is er.RegistryEntryHider.INTEGRATION
    )


def _is_turned_off(entry: er.RegistryEntry) -> bool:
    """Return whether the entry is disabled, for whatever reason, or hidden by the user (WR-03)."""
    return entry.disabled_by is not None or entry.hidden_by is er.RegistryEntryHider.USER


def _has_user_options(entry: er.RegistryEntry) -> bool:
    """Return whether an option is set that core does not store by itself; the exposure default is stored on a query."""
    return any(key not in CORE_OPTION_KEYS for options in entry.options.values() for key in options)


def _carries_the_identity(candidate: er.RegistryEntry, other: er.RegistryEntry) -> bool:
    """
    Return whether `candidate` is the entry to keep of two entries with the same unique id (WR-04).

    The entry with the user's customizations wins; without a difference the older entry wins, because its entity id is
    the one automations and dashboards already use, while a newer twin was generated by a platform or a replay.
    """
    if _is_customized(candidate) != _is_customized(other):
        return _is_customized(candidate)
    return candidate.created_at <= other.created_at


def _short(target: TakeoverTarget) -> str:
    """Return the device id capped for logging; a mirror's id comes from the broker."""
    return target.device_id[:40]


def _merge_companion(hass: HomeAssistant, entry: ConfigEntry, target: TakeoverTarget, device: dr.DeviceEntry) -> None:
    """Move the entities of the old companion device to the taken-over device, remove the companion, rename."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    companion = device_registry.async_get_device_by_identifier((DOMAIN, target.device_id), entry.entry_id)
    if companion is not None and companion.id != device.id:
        for companion_entity in er.async_entries_for_device(
            entity_registry, companion.id, include_disabled_entities=True
        ):
            entity_registry.async_update_entity(companion_entity.entity_id, device_id=device.id)
        device_registry.async_remove_device(companion.id)
    device_registry.async_update_device(device.id, new_identifiers={(DOMAIN, target.device_id)})
