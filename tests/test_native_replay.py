"""A retained legacy Discovery replay around the native takeover leaves no duplicate entity (IN-03, MIG-05, D-04)."""

import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import attr
import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_fire_time_changed

from custom_components.mqtt_actions import sync as sync_module
from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import DOMAIN
from custom_components.mqtt_actions.discovery import DiscoveryContent, DiscoveryPublisher, build_discovery
from custom_components.mqtt_actions.mqtt_gateway import MqttGateway
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, heartbeat_topic
from tests.documents import FOREIGN_OWNER, heartbeat_payload, make_spec
from tests.log_helpers import OWN_LOGGER
from tests.test_native_start import (
    BASE,
    _assert_moved_and_native,
    _legacy_mirror,
    _loop_back_discovery,
    _manager,
    _mqtt_device_of,
    _publishes,
    _restart,
    _seed_native,
    _store_the_mirror_as_native,
    _unloaded_legacy_device,
)
from tests.test_takeover import (
    MIGRATE_PAYLOAD,
    PREFIX,
    _discovery_clears,
    _falsy_publishes,
    legacy_entity_ids,
    setup_legacy_device,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

# Longer than the production quiet period, and a literal on purpose: a RED run against code without the production
# constant must fail on an assertion about the duplicates, not on a missing name
QUIET_PERIOD_PASSED = 10.0
# Another instance on the broker, next to the owner of a mirror (FOREIGN_OWNER)
PEER = "instance-peer"


@pytest.fixture(autouse=True)
def fast_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll quickly; the default wait is long only because production waits for a real broker round trip."""
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)


async def _replay(hass: HomeAssistant, topic: str, payload: str, device_id: str) -> list[str]:
    """Play a legacy Discovery payload live (core ignores a second retained message per topic) and return the ids."""
    async_fire_mqtt_message(hass, topic, payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    return legacy_entity_ids(hass, device_id)


async def _quiet_period_passes(hass: HomeAssistant) -> None:
    """Let the quiet period pass for the timers of the integration and run what they start."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=QUIET_PERIOD_PASSED))
    await hass.async_block_till_done(wait_background_tasks=True)


def _assert_clean(hass: HomeAssistant, device_id: str, replayed: list[str]) -> None:
    """Assert that no mqtt entry of the device id is left, the replayed ones are gone for good, and so is the device."""
    entity_registry = er.async_get(hass)
    assert legacy_entity_ids(hass, device_id) == []
    for entity_id in replayed:
        assert entity_registry.async_get(entity_id) is None
        assert hass.states.get(entity_id) is None
    assert _mqtt_device_of(hass, device_id) is None


def _assert_no_working_duplicate(hass: HomeAssistant, device_id: str, replayed: list[str]) -> None:
    """
    Assert that no replayed entry works: each one is gone or stays disabled by the integration, without a state.

    The duplicate guard disables the replayed switch before the quiet period ends. The catch removes such an entry only
    when the core-prefix topic is seen to hold the legacy payload or nothing (D-02), because core MQTT clears the
    retained topic when a row it discovered while disabled leaves the registry (CR-01). Otherwise the entry stays
    disabled, and so does the MQTT device it sits on.
    """
    entity_registry = er.async_get(hass)
    left = legacy_entity_ids(hass, device_id)
    assert set(left) <= set(replayed)
    assert all(
        entity_registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION for entity_id in left
    )
    for entity_id in replayed:
        assert hass.states.get(entity_id) is None


def _fire_peer(hass: HomeAssistant, peer_id: str, kept_legacy: list[str] | None) -> None:
    """
    Announce a peer online and deliver one live heartbeat of it, without waiting; usable inside a publish side effect.

    The heartbeat lists the device ids the peer keeps an enabled legacy MQTT entity of; None leaves the key out, which
    is what an older peer sends. The key is a literal on purpose: a RED run against code without the product constant
    must fail on an assertion about the kept rows, not on a missing name.
    """
    async_fire_mqtt_message(hass, availability_topic(BASE, peer_id), "online", retain=True)
    data = json.loads(heartbeat_payload(peer_id, native=True))
    if kept_legacy is not None:
        data["kept_legacy"] = kept_legacy
    async_fire_mqtt_message(hass, heartbeat_topic(BASE, peer_id), json.dumps(data), retain=False)


async def _announce_peer(hass: HomeAssistant, peer_id: str, kept_legacy: list[str] | None) -> None:
    """Announce a peer and its heartbeat (`_fire_peer`) and let them settle; call it after the restart."""
    _fire_peer(hass, peer_id, kept_legacy)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize("replay_at", ["before_the_clear", "after_the_clear"])
async def test_a_replay_during_the_pass_leaves_no_duplicate(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
    replay_at: str,
) -> None:
    """D-04, D-05, D-06: the replay lands around the retained clear; after the quiet period only moved entries stay."""
    legacy, before = await _unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    if replay_at == "after_the_clear":
        _loop_back_discovery(hass, mqtt_mock)
    # Before the clear the default mock is used on purpose: the retained clear that it loops back is dropped by core,
    # so core does not clean a replay that came before it (Pitfall 2)
    replayed: list[list[str]] = []
    real_clear = DiscoveryPublisher.async_clear_device

    async def _clear_with_a_replay(self: DiscoveryPublisher, device_id: str) -> None:
        # Only around the takeover's clear: the owner clears the stale topic again after the quiet-period catch (D-06)
        first = not replayed
        if replay_at == "before_the_clear" and first:
            replayed.append(await _replay(hass, legacy.topic, legacy.payload, legacy.device_id))
        await real_clear(self, device_id)
        if replay_at == "after_the_clear" and first:
            replayed.append(await _replay(hass, legacy.topic, legacy.payload, legacy.device_id))

    monkeypatch.setattr(DiscoveryPublisher, "async_clear_device", _clear_with_a_replay)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The replay really landed, so the test cannot go green for the wrong reason
    assert len(replayed) == 1
    assert len(replayed[0]) == 3
    assert set(legacy_entity_ids(hass, legacy.device_id)) == set(replayed[0])  # the catch waits for the quiet period
    await _quiet_period_passes(hass)
    _assert_no_working_duplicate(hass, legacy.device_id, replayed[0])
    _assert_moved_and_native(hass, legacy, before)


async def test_a_replay_after_the_takeover_of_a_native_mirror_leaves_no_duplicate_and_no_publish(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5-02: a mirror's replay is cleaned by the registry alone; the only broker traffic is core's own removal."""
    spec = make_spec(name="Foreign lamp")
    entry, topic = await _legacy_mirror(hass, make_hub_entry, spec)
    entity_registry = er.async_get(hass)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_entity_ids(hass, spec.device_id)}
    async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _store_the_mirror_as_native(hass_storage, spec)
    mqtt_mock.async_publish.reset_mock()
    discovery = json.dumps(build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3"))
    replayed: list[list[str]] = []
    real_take_over = takeover.async_take_over

    async def _take_over_then_replay(*args: Any, **kwargs: Any) -> Any:
        status = await real_take_over(*args, **kwargs)
        replayed.append(await _replay(hass, topic, discovery, spec.device_id))
        return status

    monkeypatch.setattr(takeover, "async_take_over", _take_over_then_replay)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(replayed) == 1
    assert len(replayed[0]) == 3
    await _quiet_period_passes(hass)
    _assert_clean(hass, spec.device_id, replayed[0])
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform) == (old.id, DOMAIN)
        assert hass.states.get(entity_id) is not None
    published = [call.args[1] for call in mqtt_mock.async_publish.call_args_list]
    assert not any(payload and "migrate_discovery" in str(payload) for payload in published)
    assert all(not payload for payload, _retain in _publishes(mqtt_mock, discovery_topic(PREFIX, spec.device_id)))


async def test_a_replay_before_a_restart_of_a_finished_native_owner_is_cleaned_at_the_next_start(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-05: a native owner whose pass is long finished is still cleaned at each start, guarded by the legacy device."""
    legacy, before = await _unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    _loop_back_discovery(hass, mqtt_mock)
    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _assert_moved_and_native(hass, legacy, before)
    assert legacy_entity_ids(hass, legacy.device_id) == []

    for _restart_number in range(2):
        # A running instance has no catch that listens, so the duplicates stay until the next start
        replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
        assert len(replayed) == 3
        await _restart(hass, legacy.entry)
        await _quiet_period_passes(hass)
        _assert_no_working_duplicate(hass, legacy.device_id, replayed)
        _assert_moved_and_native(hass, legacy, before)


async def test_the_replay_catch_is_armed_only_for_an_instance_with_a_native_device(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A legacy instance arms no catch; one with a native device arms the timer."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    assert _manager(legacy.entry)._cancel_replay_catch is None

    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _seed_native(hass_storage, pending=[])
    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _manager(legacy.entry)._cancel_replay_catch is not None


async def test_a_replay_right_after_the_move_is_removed_before_the_clear(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-05: the first catch runs between the registry move and the retained clear, with no quiet period to wait for."""
    legacy, before = await _unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    _loop_back_discovery(hass, mqtt_mock)
    replayed: list[list[str]] = []
    left_at_the_clear: list[list[str]] = []
    real_take_over = takeover.async_take_over
    real_clear = DiscoveryPublisher.async_clear_device

    async def _take_over_then_replay(*args: Any, **kwargs: Any) -> Any:
        status = await real_take_over(*args, **kwargs)
        replayed.append(await _replay(hass, legacy.topic, legacy.payload, legacy.device_id))
        return status

    async def _clear_after_a_look(self: DiscoveryPublisher, device_id: str) -> None:
        left_at_the_clear.append(legacy_entity_ids(hass, device_id))
        await real_clear(self, device_id)

    monkeypatch.setattr(takeover, "async_take_over", _take_over_then_replay)
    monkeypatch.setattr(DiscoveryPublisher, "async_clear_device", _clear_after_a_look)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(replayed) == 1
    assert len(replayed[0]) == 3
    assert left_at_the_clear == [[]]  # nothing is left when the clear goes out
    _assert_clean(hass, legacy.device_id, replayed[0])
    _assert_moved_and_native(hass, legacy, before)


def _mqtt_records(hass: HomeAssistant, device_id: str) -> dict[tuple[str, str, str], Any]:
    """Return the deleted mqtt records of the device id: the main component and the test buttons."""
    return {
        key: record
        for key, record in er.async_get(hass).deleted_entities.items()
        if record.platform == "mqtt"
        and (record.unique_id == device_id or record.unique_id.startswith(f"{device_id}_test_"))
    }


def _tombstone_the_replay(hass: HomeAssistant, device_id: str, replayed: list[str], tombstones: str) -> None:
    """
    Remove the replayed rows so that each leaves a deleted record, disabled by the integration or reset to null.

    An enabled row is disabled by the integration first, so its record keeps that state; the null variant then resets
    every record, which is what `reseed-tombstones.sh` does on the bench.
    """
    entity_registry = er.async_get(hass)
    for entity_id in replayed:
        if entity_registry.async_get(entity_id).disabled_by is None:
            entity_registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        entity_registry.async_remove(entity_id)
    records = _mqtt_records(hass, device_id)
    assert len(records) == len(replayed)
    assert all(record.disabled_by is er.RegistryEntryDisabler.INTEGRATION for record in records.values())
    if tombstones == "null":
        for key, record in records.items():
            entity_registry.deleted_entities[key] = attr.evolve(record, disabled_by=None)


@pytest.mark.parametrize("tombstones", ["integration", "null"], ids=["integration", "null"])
async def test_a_replay_onto_tombstones_is_cleaned_at_the_next_start(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    tombstones: str,
) -> None:
    """D-02, D-05: with the legacy payload retained, the next start removes the disabled twin and the legacy device."""
    legacy, before = await _unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    _loop_back_discovery(hass, mqtt_mock)
    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _assert_moved_and_native(hass, legacy, before)
    assert legacy_entity_ids(hass, legacy.device_id) == []
    first = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(first) == 3
    _tombstone_the_replay(hass, legacy.device_id, first, tombstones)
    entity_registry = er.async_get(hass)

    for _round in range(2):
        replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
        assert len(replayed) == 3
        # Core re-enabled or restored the switch and the guard disabled it, so the test cannot go green for the wrong
        # reason: this is the row the catch used to skip (CR-01)
        (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
        assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
        await _restart(hass, legacy.entry)
        # The mocked client keeps no retained store: hand the broker's retained legacy payload to the new subscriptions
        # (core's discovery skips it, it saw a retained message on the topic before)
        async_fire_mqtt_message(hass, legacy.topic, legacy.payload, retain=True)
        await hass.async_block_till_done(wait_background_tasks=True)
        await _quiet_period_passes(hass)
        _assert_clean(hass, legacy.device_id, replayed)
        _assert_moved_and_native(hass, legacy, before)


async def _a_finished_native_owner(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> tuple[Any, dict[str, er.RegistryEntry]]:
    """Return a native owner whose takeover pass is done and that has no legacy row left, with its moved entries."""
    legacy, before = await _unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    _loop_back_discovery(hass, mqtt_mock)
    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _assert_moved_and_native(hass, legacy, before)
    assert legacy_entity_ids(hass, legacy.device_id) == []
    return legacy, before


async def _restart_with_the_retained_payload(hass: HomeAssistant, legacy: Any, payload: str) -> None:
    """Restart the entry and hand the broker's retained payload to the new subscriptions (core's discovery skips it)."""
    await _restart(hass, legacy.entry)
    async_fire_mqtt_message(hass, legacy.topic, payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _assert_one_retained_clear(mqtt_mock: Any, topic: str) -> None:
    """Assert that the product published exactly one empty retained payload on the topic (core's own clear is None)."""
    assert [call.args[3] for call in _discovery_clears(mqtt_mock, topic)] == [True]


async def test_the_owner_clears_the_stale_legacy_discovery_once_after_each_catch(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-06: after each start-up catch the owner clears the retained legacy discovery once, so no replay can return."""
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    first = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    _tombstone_the_replay(hass, legacy.device_id, first, "integration")

    for _round in range(2):
        replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
        assert len(replayed) == 3
        await _restart_with_the_retained_payload(hass, legacy, legacy.payload)
        mqtt_mock.async_publish.reset_mock()
        await _quiet_period_passes(hass)
        _assert_one_retained_clear(mqtt_mock, legacy.topic)
        _assert_clean(hass, legacy.device_id, replayed)
        _assert_moved_and_native(hass, legacy, before)


async def test_the_owner_clears_a_retained_legacy_discovery_even_when_nothing_was_removed(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """User decision 4: the owner clears a retained legacy payload at the start even without any twin to remove."""
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    await _restart_with_the_retained_payload(hass, legacy, legacy.payload)
    # Core saw a retained message on the topic before, so it creates nothing: there is nothing to remove
    assert legacy_entity_ids(hass, legacy.device_id) == []
    mqtt_mock.async_publish.reset_mock()
    caplog.clear()

    await _quiet_period_passes(hass)

    _assert_one_retained_clear(mqtt_mock, legacy.topic)
    assert not any("Removed" in record.getMessage() for record in caplog.records)
    _assert_moved_and_native(hass, legacy, before)


async def _a_follower_with_disabled_twins_rediscovered(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> tuple[Any, Any, str, list[str]]:
    """
    Return a follower whose native mirror has three replayed rows, all disabled by the integration and rediscovered.

    The guard disables the replayed switch; the buttons are disabled too and core discovers all three rows again while
    they are disabled, so core holds its clear-on-remove hook for each. A loaded button would defer the mirror's
    takeover at the restart and keep the id from the catch (Pitfall 8). Returns the spec, the entry, the core-prefix
    topic and the replayed entity ids.
    """
    spec = make_spec(name="Foreign lamp")
    entry, topic = await _legacy_mirror(hass, make_hub_entry, spec)
    async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _store_the_mirror_as_native(hass_storage, spec)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert legacy_entity_ids(hass, spec.device_id) == []  # the takeover of the mirror is done
    discovery = json.dumps(build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3"))
    replayed = await _replay(hass, topic, discovery, spec.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    for entity_id in replayed:
        entity_registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, topic, discovery, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    return spec, entry, discovery, replayed


def _assert_disabled_twins_kept(hass: HomeAssistant, replayed: list[str]) -> None:
    """Assert that every replayed row is still in the registry, disabled by the integration."""
    entity_registry = er.async_get(hass)
    for entity_id in replayed:
        kept = entity_registry.async_get(entity_id)
        assert kept is not None, "an integration-disabled twin left the registry on LEGACY content"
        assert kept.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_a_follower_keeps_its_disabled_twins_on_legacy_content_and_publishes_nothing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
) -> None:
    """
    Contract changed on purpose by Phase 9.2 D-05: a follower keeps its integration-disabled twins on LEGACY content.

    This test was `test_a_follower_removes_its_disabled_twin_and_publishes_nothing`, which pinned the opposite. A
    follower never removes an integration-disabled twin while the shared core-prefix topic holds the legacy payload:
    core discovered the row while it was disabled and holds a clear-on-remove hook for it, so the removal would make
    core publish an empty retained payload on a topic every instance shares, and that clear deletes the rows other
    instances keep (09.1 bench, CR-01). The follower removes them once the content is EMPTY (plan 09.2-03). T-5-02:
    the product publishes nothing, and neither does core.
    """
    spec, entry, discovery, replayed = await _a_follower_with_disabled_twins_rediscovered(
        hass, mqtt_mock, hass_storage, make_hub_entry
    )
    topic = discovery_topic(PREFIX, spec.device_id)
    await _restart(hass, entry)
    async_fire_mqtt_message(hass, topic, discovery, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    _assert_disabled_twins_kept(hass, replayed)
    assert _mqtt_device_of(hass, spec.device_id) is not None
    assert _falsy_publishes(mqtt_mock, topic) == []


async def test_cross_instance_a_follower_keeps_its_disabled_twins_on_legacy_content_while_the_owner_keeps_a_row(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
) -> None:
    """
    D-12 (bench case, follower side), D-02, D-05: no catch lets the shared topic go empty under the owner's kept row.

    The owner announces in its heartbeat that it keeps an enabled legacy row of the device. Core's discovery publishes
    are looped back, so a clear by core's hook would reach the shared topic and empty it for every instance: after the
    quiet period the twins are still there, nothing falsy went out, the content is still LEGACY and the MQTT device
    stays.
    """
    spec, entry, discovery, replayed = await _a_follower_with_disabled_twins_rediscovered(
        hass, mqtt_mock, hass_storage, make_hub_entry
    )
    topic = discovery_topic(PREFIX, spec.device_id)
    _loop_back_discovery(hass, mqtt_mock)
    await _restart(hass, entry)
    async_fire_mqtt_message(hass, topic, discovery, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _announce_peer(hass, FOREIGN_OWNER, [spec.device_id])
    mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    _assert_disabled_twins_kept(hass, replayed)
    assert _falsy_publishes(mqtt_mock, topic) == []
    assert _manager(entry).sync.discovery_content(spec.device_id) is DiscoveryContent.LEGACY
    assert _mqtt_device_of(hass, spec.device_id) is not None


async def test_cross_instance_the_owner_neither_removes_nor_clears_while_a_peer_keeps_a_row(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    D-12 (reverse case, owner side), D-02: the owner keeps its disabled twin and the topic while a peer keeps a row.

    An online peer announces in its heartbeat that it keeps an enabled legacy row of the device. Removing the twin
    that core discovered while disabled would make core clear the shared topic, and the owner's explicit clear would
    do the same: neither happens, the content stays LEGACY, and one INFO line names only a count (T-04-14).
    """
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    # Core discovers the disabled switch again, so it holds the hook that clears the topic when the row leaves
    async_fire_mqtt_message(hass, legacy.topic, legacy.payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _restart_with_the_retained_payload(hass, legacy, legacy.payload)
    await _announce_peer(hass, PEER, [legacy.device_id])
    mqtt_mock.async_publish.reset_mock()
    caplog.set_level(logging.INFO, logger=OWN_LOGGER)
    caplog.clear()

    await _quiet_period_passes(hass)

    kept = entity_registry.async_get(switch)
    assert kept is not None, "the owner removed its disabled twin while a peer keeps a row"
    assert kept.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    assert _manager(legacy.entry).sync.discovery_content(legacy.device_id) is DiscoveryContent.LEGACY
    assert _mqtt_device_of(hass, legacy.device_id) is not None
    _assert_moved_and_native(hass, legacy, before)
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(OWN_LOGGER)
        and record.levelno == logging.INFO
        and "another instance keeps" in record.getMessage()
    ]
    assert len(lines) == 1
    assert " 1 " in lines[0]
    assert legacy.device_id not in lines[0]
    assert PEER not in lines[0]


async def test_the_owner_keeps_a_customized_duplicate_and_its_device_and_clears_nothing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-04, D-08: a customized duplicate stays with its MQTT device, so the owner does not clear the topic."""
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    # The user names the duplicate and turns it on again; the guard keeps a customized row enabled
    entity_registry.async_update_entity(switch, name="My own name", disabled_by=None)
    await _restart_with_the_retained_payload(hass, legacy, legacy.payload)
    mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    kept = entity_registry.async_get(switch)
    assert kept is not None
    assert kept.name == "My own name"
    assert kept.disabled_by is None
    assert legacy_entity_ids(hass, legacy.device_id) == [switch]  # the uncustomized buttons are gone
    assert _mqtt_device_of(hass, legacy.device_id) is not None
    assert _discovery_clears(mqtt_mock, legacy.topic) == []
    _assert_moved_and_native(hass, legacy, before)


@pytest.mark.usefixtures("discovery_settled")
async def test_a_disabled_leftover_is_removed_at_a_start_with_an_empty_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-02, D-03, D-09: with nothing retained on the topic, the settled start removes the disabled twin and device."""
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    # The guard disabled the switch: this is the leftover the catch used to skip (CR-01)
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    # The bench state: nothing is retained, so nothing is handed to the new subscriptions
    await _restart(hass, legacy.entry)
    mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    _assert_clean(hass, legacy.device_id, replayed)
    _assert_moved_and_native(hass, legacy, before)
    # No product clear for an empty topic, and no core clear: core did not rediscover the row in this run
    assert _falsy_publishes(mqtt_mock, legacy.topic) == []


def _abbreviated(payload: str) -> str:
    """Return the payload with the abbreviated device and components keys, a shape the classifier does not know."""
    document = json.loads(payload)
    document["dev"] = document.pop("device")
    document["cmps"] = document.pop("components")
    return json.dumps(document)


@pytest.mark.parametrize("content", ["unsettled", "foreign_shape"])
async def test_a_disabled_twin_stays_while_the_topic_content_is_unknown(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    caplog: pytest.LogCaptureFixture,
    request: pytest.FixtureRequest,
    content: str,
) -> None:
    """D-03, CR-01: with unknown content the disabled twin and its device stay, and one INFO line names only a count."""
    if content == "foreign_shape":
        request.getfixturevalue("discovery_settled")
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    shown = _abbreviated(legacy.payload)
    if content == "foreign_shape":
        await _restart_with_the_retained_payload(hass, legacy, shown)
    else:
        await _restart(hass, legacy.entry)
    mqtt_mock.async_publish.reset_mock()
    caplog.set_level(logging.INFO, logger=OWN_LOGGER)
    caplog.clear()

    await _quiet_period_passes(hass)

    assert entity_registry.async_get(switch) is not None
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert _mqtt_device_of(hass, legacy.device_id) is not None
    assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    kept = [
        record
        for record in caplog.records
        if record.name.startswith(OWN_LOGGER)
        and record.levelno == logging.INFO
        and "is not known" in record.getMessage()
    ]
    assert len(kept) == 1
    message = kept[0].getMessage()
    assert " 1 " in message
    assert legacy.device_id not in message
    assert shown not in message
    assert legacy.payload not in message
    _assert_moved_and_native(hass, legacy, before)


async def test_the_catch_keeps_an_enabled_customized_button_next_to_a_disabled_twin_on_legacy_content(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """
    CR-01 (review), D-08: an integration-disabled twin on LEGACY content stays while another legacy row is kept.

    Core discovered the disabled switch again in this run, so it holds the clear-on-remove hook for that row. Removing
    the switch would make core publish an empty retained discovery, and that payload deletes every loaded legacy row
    of the device, the renamed button the catch keeps on purpose included. The discovery publishes are looped back.
    """
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    button, *_others = sorted(entity_id for entity_id in replayed if entity_id.startswith("button."))
    # The guard disabled the switch, and the user renamed a test button, which stays enabled and loaded
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    entity_registry.async_update_entity(button, name="My button")
    await hass.async_block_till_done(wait_background_tasks=True)
    # Core discovers the disabled switch again, so it holds the hook that clears the topic when the row leaves
    async_fire_mqtt_message(hass, legacy.topic, legacy.payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _restart_with_the_retained_payload(hass, legacy, legacy.payload)
    assert hass.states.get(button) is not None  # the kept button is loaded, so a clear would delete it
    mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    kept = entity_registry.async_get(button)
    assert kept is not None, "the customized, kept test button was deleted"
    assert kept.name == "My button"
    assert hass.states.get(button) is not None
    assert entity_registry.async_get(switch) is not None
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    assert _mqtt_device_of(hass, legacy.device_id) is not None
    _assert_moved_and_native(hass, legacy, before)


async def _a_renamed_loaded_button_next_to_a_hooked_disabled_switch(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> tuple[Any, str, str]:
    """
    Return the legacy device, a disabled switch core holds a clear-on-remove hook for, and a renamed button.

    A native owner with loop-back, a live replay whose switch the guard disables, a test button the user renamed
    ("Kept"), enabled and loaded, and the payload fired live again so core discovers the disabled switch in this run.
    No time is advanced, so no catch runs.
    """
    legacy, _before = await _a_finished_native_owner(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry
    )
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    button, *_others = sorted(entity_id for entity_id in replayed if entity_id.startswith("button."))
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    entity_registry.async_update_entity(button, name="Kept")
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, legacy.topic, legacy.payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(button) is not None
    return legacy, switch, button


async def test_core_deletes_a_loaded_renamed_row_when_a_hooked_disabled_row_leaves_without_a_migrate(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """
    Core contract (research Q1 probe 4, CR-01): core's hook clear deletes every loaded legacy row of the device.

    A version guard of the mechanism behind CR-01: removing the disabled switch makes core publish an empty retained
    discovery, and that payload, looped back, deletes the renamed button. A core bump that changes it turns this red.
    """
    _legacy, switch, button = await _a_renamed_loaded_button_next_to_a_hooked_disabled_switch(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry
    )

    er.async_get(hass).async_remove(switch)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert er.async_get(hass).async_get(button) is None


async def test_core_keeps_a_loaded_renamed_row_when_the_migrate_comes_before_the_hooked_clear(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """
    Core contract (research Q1 probe 3, D-09 groundwork): a migrate before the hook clear unloads instead of deleting.

    The migrate payload unloads the loaded legacy rows and forgets their discovery, so the empty payload of the hook
    that follows deletes nothing: the renamed button keeps its registry row and its name, without a state.
    """
    legacy, switch, button = await _a_renamed_loaded_button_next_to_a_hooked_disabled_switch(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry
    )
    async_fire_mqtt_message(hass, legacy.topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    er.async_get(hass).async_remove(switch)
    await hass.async_block_till_done(wait_background_tasks=True)

    kept = er.async_get(hass).async_get(button)
    assert kept is not None
    assert kept.name == "Kept"
    assert hass.states.get(button) is None


async def test_a_catch_that_runs_before_the_settle_checks_again_once_the_grace_has_passed(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    WR-02 (review), D-02, D-03: a catch that finds the content unknown because the settle is late checks again.

    A slow broker acknowledges the discovery wildcard after the quiet period. The first catch keeps the disabled twin;
    once the settle and its grace have passed, the catch runs again and removes the twin and the legacy device.
    """
    settles: list[Callable[[], None]] = []

    def _watch(_gateway: MqttGateway, _topic: str, _qos: int, on_done: Callable[[], None]) -> Callable[[], None]:
        settles.append(on_done)
        return lambda: None

    monkeypatch.setattr(MqttGateway, "async_on_subscribed", _watch)
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    monkeypatch.setattr(sync_module, "DISCOVERY_SETTLE_GRACE_SECONDS", 2.0)
    # The bench state: nothing is retained, so nothing is handed to the new subscriptions
    await _restart(hass, legacy.entry)
    now = [1000.0]
    _manager(legacy.entry).clock = lambda: now[0]
    mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    # The settle is not in yet, so the content is unknown and the twin stays for now
    assert entity_registry.async_get(switch) is not None
    settles[-1]()
    await hass.async_block_till_done(wait_background_tasks=True)
    now[0] += 2.0
    await _quiet_period_passes(hass)

    _assert_clean(hass, legacy.device_id, replayed)
    _assert_moved_and_native(hass, legacy, before)
    assert _falsy_publishes(mqtt_mock, legacy.topic) == []


# --- Phase 9.2 D-01: the sending half of kept_legacy ----------------------------------------------------------------


def _heartbeats(mqtt_mock: Any, entry: Any) -> list[dict[str, Any]]:
    """Return the heartbeats this instance published since the last reset, decoded, in order."""
    topic = heartbeat_topic(BASE, _manager(entry).instance_id)
    return [json.loads(payload) for payload, _retain in _publishes(mqtt_mock, topic)]


@pytest.mark.parametrize("row", ["renamed", "untouched"])
async def test_the_first_heartbeat_after_a_start_lists_a_device_with_a_kept_customized_row(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    row: str,
) -> None:
    """
    D-01, research Pitfall 2: the kept list is read from the registry, so the first heartbeat of a start is right.

    A renamed replayed test button is a kept, enabled legacy row: the very first heartbeat after the restart lists the
    device, before any entity of it loaded. Uncustomized replay twins are no kept row, so a native device lists nothing.
    """
    legacy, _before = await _a_finished_native_owner(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry
    )
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    if row == "renamed":
        button, *_others = sorted(entity_id for entity_id in replayed if entity_id.startswith("button."))
        er.async_get(hass).async_update_entity(button, name="Kept")
        await hass.async_block_till_done(wait_background_tasks=True)
    mqtt_mock.async_publish.reset_mock()

    await _restart(hass, legacy.entry)

    heartbeats = _heartbeats(mqtt_mock, legacy.entry)
    assert heartbeats, "no heartbeat after the restart"
    expected = [legacy.device_id] if row == "renamed" else []
    assert heartbeats[0].get("kept_legacy") == expected


async def test_a_heartbeat_lists_a_held_device_that_is_not_native_in_this_run(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """
    D-01, research Pitfall 2: a held device that is not native in this run keeps its loaded legacy rows: it is listed.

    A legacy mirror on a legacy instance has three loaded legacy rows and no native twin: an empty retained payload on
    the shared topic would delete them, so the heartbeat lists the device whatever its rows look like.
    """
    spec = make_spec(name="Foreign lamp")
    entry, _topic = await _legacy_mirror(hass, make_hub_entry, spec)
    mqtt_mock.async_publish.reset_mock()

    await _manager(entry).presence.async_publish_heartbeat()

    heartbeats = _heartbeats(mqtt_mock, entry)
    assert heartbeats
    assert heartbeats[-1].get("kept_legacy") == [spec.device_id]


# --- Phase 9.2 D-09, D-10: the migrate first, and a fresh look after every await ------------------------------------

MIGRATE = {"migrate_discovery": True}


def _topic_sequence(mqtt_mock: Any, topic: str) -> list[tuple[Any, bool]]:
    """Return the (payload, retain) pairs published on a topic since the last reset, a non-empty payload decoded."""
    return [(json.loads(payload) if payload else payload, retain) for payload, retain in _publishes(mqtt_mock, topic)]


async def _an_owner_with_a_disabled_twin_on_legacy_content(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    hooked: bool = False,
    rename_a_button: bool = False,
) -> tuple[Any, dict[str, er.RegistryEntry], list[str], str]:
    """
    Return a restarted native owner with three replayed rows, the switch disabled by the guard, on LEGACY content.

    With `hooked`, the payload is fired live again so core discovers the disabled switch in this run and holds the
    clear-on-remove hook for it. With `rename_a_button`, the user renamed a replayed test button, a kept row (D-08).
    The discovery publishes are looped back, and the publish mock is reset; no catch ran yet.
    """
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    if rename_a_button:
        button, *_others = sorted(entity_id for entity_id in replayed if entity_id.startswith("button."))
        entity_registry.async_update_entity(button, name="Kept")
        await hass.async_block_till_done(wait_background_tasks=True)
    if hooked:
        async_fire_mqtt_message(hass, legacy.topic, legacy.payload, retain=False)
        await hass.async_block_till_done(wait_background_tasks=True)
    await _restart_with_the_retained_payload(hass, legacy, legacy.payload)
    mqtt_mock.async_publish.reset_mock()
    return legacy, before, replayed, switch


@pytest.mark.parametrize("hook", ["hooked", "not_hooked"])
async def test_the_owner_sends_the_migrate_payload_before_it_lets_the_topic_go_empty(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    hook: str,
) -> None:
    """
    D-09: before an action that can empty the shared topic the owner publishes the migrate payload.

    A peer that started while the gate was open has loaded the legacy rows; the migrate makes its core unload them,
    so the empty payload that follows deletes no registry row there (research Q1). Without a hook the sequence is the
    migrate before the removal, a fresh migrate and the owner's retained clear. With a hook, core's own empty payload
    follows the migrate when the twin leaves, and, looped back, it made the content EMPTY, so no product clear follows.
    """
    legacy, before, replayed, _switch = await _an_owner_with_a_disabled_twin_on_legacy_content(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry, hooked=hook == "hooked"
    )

    await _quiet_period_passes(hass)

    _assert_clean(hass, legacy.device_id, replayed)
    _assert_moved_and_native(hass, legacy, before)
    sequence = _topic_sequence(mqtt_mock, legacy.topic)
    if hook == "not_hooked":
        assert sequence == [(MIGRATE, False), (MIGRATE, False), ("", True)]
        return
    assert sequence, "nothing was published on the topic"
    assert sequence[0] == (MIGRATE, False)
    falsy = [index for index, (payload, _retain) in enumerate(sequence) if not payload]
    assert falsy, "core's hook did not clear the topic"
    assert all(index > 0 for index in falsy)
    assert _discovery_clears(mqtt_mock, legacy.topic) == []


@pytest.mark.parametrize("keep", ["peer_keeps", "local_keep"])
async def test_no_migrate_goes_out_while_the_gate_keeps_the_device(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    keep: str,
) -> None:
    """
    D-09, T-09.2-08: no migrate while the gate keeps the device; it would unload the kept rows on every instance.

    An online peer that announces a kept row, or a renamed replayed button of this instance, keeps the device.
    """
    legacy, _before, _replayed, _switch = await _an_owner_with_a_disabled_twin_on_legacy_content(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry, rename_a_button=keep == "local_keep"
    )
    if keep == "peer_keeps":
        await _announce_peer(hass, PEER, [legacy.device_id])
        mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    assert not any(
        isinstance(payload, str) and "migrate_discovery" in payload
        for payload, _retain in _publishes(mqtt_mock, legacy.topic)
    )


@pytest.mark.parametrize("moment", ["before_the_removal", "before_the_clear"])
async def test_the_owner_reads_the_peer_signal_again_right_before_it_empties_the_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    moment: str,
) -> None:
    """
    D-10: a peer that announces a kept row while a migrate is on its way stops the removal or the clear that follows.

    The peer's heartbeat is delivered during the publish of the first migrate (before the removal) or of the second
    one (before the clear); the owner reads the peer signal again after each migrate await.
    """
    legacy, _before, _replayed, switch = await _an_owner_with_a_disabled_twin_on_legacy_content(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry
    )
    deliver = mqtt_mock.async_publish.side_effect
    migrates = [0]
    trigger = 1 if moment == "before_the_removal" else 2

    def _deliver_and_announce(topic: str, payload: Any, *args: Any, **kwargs: Any) -> Any:
        result = deliver(topic, payload, *args, **kwargs)
        if topic == legacy.topic and isinstance(payload, str) and "migrate_discovery" in payload:
            migrates[0] += 1
            if migrates[0] == trigger:
                _fire_peer(hass, PEER, [legacy.device_id])
        return result

    mqtt_mock.async_publish.side_effect = _deliver_and_announce

    await _quiet_period_passes(hass)

    if moment == "before_the_removal":
        kept = er.async_get(hass).async_get(switch)
        assert kept is not None, "the owner removed its disabled twin after a peer announced a kept row"
        assert kept.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    else:
        assert _discovery_clears(mqtt_mock, legacy.topic) == []


# --- Phase 9.2 D-04: the owner waits one heartbeat interval for a peer it has not heard yet ---------------------------

# Longer than one heartbeat interval plus the expiry margin, and a literal on purpose (see QUIET_PERIOD_PASSED)
PEER_WAIT_PASSED = 45.0


async def _time_passes(hass: HomeAssistant, seconds: float) -> None:
    """Let `seconds` pass for the timers of the integration and run what they start."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


async def _an_owner_that_has_not_heard_an_online_peer(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> tuple[Any, dict[str, er.RegistryEntry], list[str], str, list[float]]:
    """
    Return a restarted native owner on LEGACY content with a disabled twin, and an online peer it has not heard.

    The guard disabled the replayed switch. The peer's retained availability says `online`, and no heartbeat of it
    arrived since the start. The manager runs on a fake clock that the test advances, with the listening time
    restarted on it. Core's discovery publishes are looped back, the publish mock is reset and no catch ran yet. No
    hook: core did not discover the disabled switch again. Returns the legacy device, the moved entries, the replayed
    ids, the switch and the clock.
    """
    legacy, before = await _a_finished_native_owner(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    replayed = await _replay(hass, legacy.topic, legacy.payload, legacy.device_id)
    assert len(replayed) == 3
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    await _restart_with_the_retained_payload(hass, legacy, legacy.payload)
    now = [1000.0]
    manager = _manager(legacy.entry)
    manager.clock = lambda: now[0]
    manager.presence._roster.restart_listening()
    async_fire_mqtt_message(hass, availability_topic(BASE, PEER), "online", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    mqtt_mock.async_publish.reset_mock()
    return legacy, before, replayed, switch, now


async def test_the_owner_waits_for_a_peer_that_is_online_but_not_heard_yet(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """
    D-04: an owner that starts together with its peers checks again once their first heartbeat is due.

    At the first catch the peer is online but not heard yet (UNHEARD), so the owner keeps its disabled twin and the
    topic. The peer's heartbeat then says it keeps nothing; within one heartbeat interval the catch runs again, and the
    owner removes the twin and its legacy device and clears the topic once, in the same run.
    """
    legacy, before, replayed, switch, now = await _an_owner_that_has_not_heard_an_online_peer(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry
    )

    await _quiet_period_passes(hass)

    assert er.async_get(hass).async_get(switch) is not None, "the owner removed its twin before it heard the peer"
    assert _discovery_clears(mqtt_mock, legacy.topic) == []
    now[0] += 31
    await _announce_peer(hass, PEER, [])
    await _time_passes(hass, PEER_WAIT_PASSED)

    _assert_clean(hass, legacy.device_id, replayed)
    _assert_one_retained_clear(mqtt_mock, legacy.topic)
    _assert_moved_and_native(hass, legacy, before)


async def test_the_owner_keeps_when_a_peer_stays_unheard_until_the_retries_are_spent(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    D-04, T-04-14: a peer that stays silent keeps everything; the re-arm is bounded and one INFO line names a count.

    The catch checks again within the existing retry bound and never past it; then the owner keeps its disabled twin
    and the topic, logs one count-only line, and leaves the device to the next start.
    """
    legacy, _before, _replayed, switch, now = await _an_owner_that_has_not_heard_an_online_peer(
        hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry
    )
    caplog.set_level(logging.INFO, logger=OWN_LOGGER)
    caplog.clear()

    for _step in range(6):
        now[0] += PEER_WAIT_PASSED
        await _time_passes(hass, PEER_WAIT_PASSED)

    kept = er.async_get(hass).async_get(switch)
    assert kept is not None, "the owner removed its twin while an online peer was not heard"
    assert kept.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert _falsy_publishes(mqtt_mock, legacy.topic) == []
    own_info = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(OWN_LOGGER) and record.levelno == logging.INFO
    ]
    lines = [message for message in own_info if "was not heard yet" in message]
    assert len(lines) == 1
    assert " 1 " in lines[0]
    assert legacy.device_id not in lines[0]
    assert PEER not in lines[0]
    # An unheard peer is counted on its own line, not as a peer that keeps a row or has not said what it keeps
    assert not any("another instance keeps" in message for message in own_info)
