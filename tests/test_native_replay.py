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

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import DOMAIN
from custom_components.mqtt_actions.discovery import DiscoveryPublisher, build_discovery
from custom_components.mqtt_actions.topics import discovery_topic
from tests.documents import FOREIGN_OWNER, make_spec
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


async def test_a_follower_removes_its_disabled_twin_and_publishes_nothing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
) -> None:
    """T-5-02, D-02: a follower's catch removes the disabled twin of a native mirror; the product publishes nothing."""
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
    # The round-2 state: the buttons are disabled too and core discovers all three rows again while they are disabled.
    # A loaded button would defer the mirror's takeover at the restart and keep the id from the catch (Pitfall 8)
    for entity_id in replayed:
        entity_registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, topic, discovery, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _restart(hass, entry)
    async_fire_mqtt_message(hass, topic, discovery, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    mqtt_mock.async_publish.reset_mock()

    await _quiet_period_passes(hass)

    _assert_clean(hass, spec.device_id, replayed)
    # The product publishes no clear; core's own clear for a row it discovered while disabled (None) is allowed (D-02)
    assert _discovery_clears(mqtt_mock, topic) == []


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
