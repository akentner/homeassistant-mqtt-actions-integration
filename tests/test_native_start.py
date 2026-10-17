"""The native takeover pass at the start of the manager: owners, followers, deferral and adoption (D-05, D-09, D-12)."""

import json
import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_mqtt_message,
    async_mock_service,
)

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    DOMAIN,
    MAX_DOCUMENT_BYTES,
    MAX_MIRRORS,
    STORE_KEY,
    STORE_MIRRORS,
)
from custom_components.mqtt_actions.manager import _parse_native
from custom_components.mqtt_actions.topics import config_topic, discovery_topic, state_topic
from tests.documents import document_payload, make_spec
from tests.helpers import (
    BASE,
    CLEAR_PAYLOAD,
    MIGRATE_PAYLOAD,
    PREFIX,
    assert_moved_and_native,
    block_discovery_delivery,
    customize_mqtt_device,
    legacy_entity_ids,
    legacy_mirror,
    loop_back_discovery,
    manager_of,
    mqtt_device_of,
    restart_entry,
    seed_native_pending,
    seed_store,
    setup_entry,
    setup_legacy_device,
    store_the_mirror_as_native,
    topic_publishes,
    unloaded_legacy_device,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.manager import Manager


def _stored_pending(hass_storage: dict[str, Any]) -> list[str]:
    return hass_storage[STORE_KEY]["data"]["native"]["pending"]


def _all_topics(mqtt_mock: Any) -> list[str]:
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list]


@pytest.fixture(autouse=True)
def fast_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll quickly; the default wait is long only because production waits for a real broker round trip."""
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)


# --- Task 1 tracer: the owner pass ---------------------------------------------------------------------------------


@pytest.mark.parametrize("language", ["en", "de"])
async def test_an_upgrade_takes_over_the_legacy_entities_and_marks_the_document(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    language: str,
) -> None:
    """D-05, D-09, D-12, MIG-01: migrate, move, retained clear, in that order; every identity of the device is kept."""
    hass.config.language = language
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_id = legacy.device_id
    customize_mqtt_device(hass, device_id, area_id="kitchen", name_by_user="Stehlampe")
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", device_id)
    assert switch_id is not None
    legacy_ids = legacy_entity_ids(hass, device_id)
    assert len(legacy_ids) == 3  # the switch and the two test buttons
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    unique_ids = {entity_id: (old.domain, old.unique_id) for entity_id, old in before.items()}
    mqtt_device = device_registry.async_get_device_by_identifier(
        ("mqtt", f"{DOMAIN}_{device_id}"), hass.config_entries.async_entries("mqtt")[0].entry_id
    )
    assert mqtt_device is not None
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    seed_native_pending(hass_storage, pending=[device_id])
    mqtt_mock.async_publish.reset_mock()
    loop_back_discovery(hass, mqtt_mock)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    sub_id = next(iter(legacy.entry.subentries.values())).subentry_id
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform, moved.device_id) == (old.id, DOMAIN, mqtt_device.id)
        assert (moved.config_entry_id, moved.config_subentry_id) == (legacy.entry.entry_id, sub_id)
    # The legacy entities, the test buttons too, keep their entity id and unique id in every language
    for entity_id, (domain, unique_id) in unique_ids.items():
        assert entity_registry.async_get_entity_id(domain, DOMAIN, unique_id) == entity_id
    assert entity_registry.async_get_entity_id("switch", DOMAIN, device_id) == switch_id
    assert hass.states.get(switch_id) is not None
    device = device_registry.async_get(mqtt_device.id)
    assert device is not None
    assert (device.area_id, device.name_by_user) == ("kitchen", "Stehlampe")
    assert (device.config_entry_id, device.config_subentry_id) == (legacy.entry.entry_id, sub_id)
    assert device.identifiers == {(DOMAIN, device_id)}
    assert _stored_pending(hass_storage) == []

    published = topic_publishes(mqtt_mock, legacy.topic)
    # Phase 9.2 D-09: a fresh migrate right before the clear
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in published] == [
        ({"migrate_discovery": True}, False),
        ({"migrate_discovery": True}, False),
        (CLEAR_PAYLOAD, True),
    ]
    document = json.loads(topic_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert document["entities"] == "native"


async def test_the_registries_are_written_before_the_takeover_is_recorded_as_done(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-01: both registries are flushed before the pending marker is saved away, or a crash would lose the ids."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    device_id = legacy.device_id
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    seed_native_pending(hass_storage, pending=[device_id])
    loop_back_discovery(hass, mqtt_mock)
    order: list[str] = []

    def _spy_registry(name: str, registry: Any) -> None:
        original = registry._store.async_save

        async def _save(*args: Any, **kwargs: Any) -> None:
            order.append(name)
            await original(*args, **kwargs)

        monkeypatch.setattr(registry._store, "async_save", _save)

    _spy_registry("entity registry", er.async_get(hass))
    _spy_registry("device registry", dr.async_get(hass))
    original_save = Store.async_save

    async def _save_store(store: Store, data: Any) -> None:
        if store.key == STORE_KEY:
            order.append("pending cleared" if data["native"]["pending"] == [] else "pending kept")
        await original_save(store, data)

    monkeypatch.setattr(Store, "async_save", _save_store)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _stored_pending(hass_storage) == []
    assert {"entity registry", "device registry", "pending cleared"} <= set(order)
    cleared = order.index("pending cleared")
    assert "entity registry" in order[:cleared]
    assert "device registry" in order[:cleared]


async def test_a_device_without_legacy_entities_still_gets_the_migrate_and_the_clear(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A fresh install has no legacy registry entry, but followers may: the migrate and the clear go out anyway."""
    subentry = make_switch_subentry("Lamp")
    device_id = subentry["data"][CONF_DEVICE_ID]
    seed_native_pending(hass_storage, pending=[device_id])

    await setup_entry(hass, make_hub_entry([subentry]))

    published = topic_publishes(mqtt_mock, discovery_topic(PREFIX, device_id))
    # Phase 9.2 D-09: a fresh migrate right before the clear
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in published] == [
        ({"migrate_discovery": True}, False),
        ({"migrate_discovery": True}, False),
        (CLEAR_PAYLOAD, True),
    ]
    assert _stored_pending(hass_storage) == []


async def test_the_pass_never_publishes_for_an_id_that_is_not_owned(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-5-02: a pending id that is no owned device, a mirror for one, causes no publish on any topic of that id."""
    mirror_spec = make_spec(name="Foreign lamp")
    unknown_id = "unknown-device-id"
    own = make_switch_subentry("Lamp")
    seed_store(
        hass_storage,
        {
            STORE_MIRRORS: {mirror_spec.device_id: document_payload(mirror_spec)},
            "native": {"instance": True, "pending": [mirror_spec.device_id, unknown_id], "devices": []},
        },
    )

    entry = await setup_entry(hass, make_hub_entry([own]))

    assert mirror_spec.device_id in manager_of(entry).mirrors
    for foreign_id in (mirror_spec.device_id, unknown_id):
        assert not [topic for topic in _all_topics(mqtt_mock) if foreign_id in topic]
    assert _stored_pending(hass_storage) == []


async def test_a_second_start_runs_no_pass(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """With nothing pending no migrate and no clear is published, and the marked documents go out again."""
    subentry = make_switch_subentry("Lamp")
    device_id = subentry["data"][CONF_DEVICE_ID]
    seed_native_pending(hass_storage, pending=[])

    entry = await setup_entry(hass, make_hub_entry([subentry]))

    assert topic_publishes(mqtt_mock, discovery_topic(PREFIX, device_id)) == []
    first = json.loads(topic_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert first["entities"] == "native"
    mqtt_mock.async_publish.reset_mock()

    await restart_entry(hass, entry)

    assert topic_publishes(mqtt_mock, discovery_topic(PREFIX, device_id)) == []
    second = json.loads(topic_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert second["entities"] == "native"
    assert state_topic(BASE, device_id) not in _all_topics(mqtt_mock)


# --- Task 2: followers and the legacy fallback ---------------------------------------------------------------------


async def test_a_follower_takes_over_a_native_mirror_at_start_without_publishing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-12: the entities and the device of a native mirror move to the entry, nothing goes on the broker."""
    spec = make_spec(name="Foreign lamp")
    entry, topic = await legacy_mirror(hass, make_hub_entry, spec)
    entity_registry = er.async_get(hass)
    legacy_ids = legacy_entity_ids(hass, spec.device_id)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", spec.device_id)
    mqtt_device = mqtt_device_of(hass, spec.device_id)
    assert switch_id is not None
    assert mqtt_device is not None
    # The owner upgraded: its migrate payload unloaded the discovered entities on every instance
    async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    store_the_mirror_as_native(hass_storage, spec)
    mqtt_mock.async_publish.reset_mock()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform, moved.device_id) == (old.id, DOMAIN, mqtt_device.id)
        assert (moved.config_entry_id, moved.config_subentry_id) == (entry.entry_id, None)
    assert entity_registry.async_get_entity_id("switch", DOMAIN, spec.device_id) == switch_id
    assert hass.states.get(switch_id) is not None
    device = dr.async_get(hass).async_get(mqtt_device.id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, spec.device_id)}
    assert entity_registry.async_get_entity_id("select", DOMAIN, f"{spec.device_id}_mode") is not None
    assert [topic for topic in _all_topics(mqtt_mock) if topic.startswith(f"{PREFIX}/")] == []


async def test_a_deferred_takeover_leaves_the_device_legacy_for_this_run(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5-08: legacy entities that stay loaded defer the device; the next setup, with the migrate heard, finishes."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_id = legacy.device_id
    legacy_ids = legacy_entity_ids(hass, device_id)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    seed_native_pending(hass_storage, pending=[device_id])
    mqtt_mock.async_publish.reset_mock()
    monkeypatch.setattr(takeover, "TAKEOVER_UNLOAD_TIMEOUT", 0.05)
    block_discovery_delivery(monkeypatch)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    manager = manager_of(legacy.entry)
    assert manager.is_native(device_id) is False
    assert _stored_pending(hass_storage) == [device_id]
    for entity_id, old in before.items():
        assert entity_registry.async_get(entity_id) == old
    assert entity_registry.async_get_entity_id("switch", DOMAIN, device_id) is None
    published = topic_publishes(mqtt_mock, legacy.topic)
    assert (CLEAR_PAYLOAD, True) not in published
    assert any(payload and "components" in json.loads(payload) for payload, _retain in published)
    document = json.loads(topic_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert "entities" not in document

    # The next setup retries and, with the migrate delivered by the broker, completes the takeover
    monkeypatch.setattr(takeover, "TAKEOVER_UNLOAD_TIMEOUT", 5.0)
    loop_back_discovery(hass, mqtt_mock)
    await restart_entry(hass, legacy.entry)

    assert _stored_pending(hass_storage) == []
    assert manager_of(legacy.entry).is_native(device_id) is True
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform) == (old.id, DOMAIN)


async def test_a_failed_retained_clear_after_the_move_keeps_the_device_native_and_is_retried(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """WR-02: the registry moved, so the device stays native; only the clear is pending and a resync retries it."""
    legacy, before = await unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    loop_back_discovery(hass, mqtt_mock)
    deliver = mqtt_mock.async_publish.side_effect
    broker_down = True

    def _publish(topic: str, payload: Any, *args: Any, **kwargs: Any) -> Any:
        if broker_down and topic == legacy.topic and payload == CLEAR_PAYLOAD:
            msg = "MQTT is not available"
            raise HomeAssistantError(msg)
        return deliver(topic, payload, *args, **kwargs)

    mqtt_mock.async_publish.side_effect = _publish

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert_moved_and_native(hass, legacy, before)
    assert _stored_pending(hass_storage) == [legacy.device_id]
    # No legacy discovery goes out again, or core MQTT would create the entities a second time
    assert [
        payload for payload, _retain in topic_publishes(mqtt_mock, legacy.topic) if payload and "components" in payload
    ] == []

    broker_down = False
    assert await manager_of(legacy.entry).async_resync()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (CLEAR_PAYLOAD, True) in topic_publishes(mqtt_mock, legacy.topic)
    # Phase 9.2 D-09: a fresh migrate right before the clear, on the retry too
    retried = topic_publishes(mqtt_mock, legacy.topic)[-2:]
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in retried] == [
        ({"migrate_discovery": True}, False),
        (CLEAR_PAYLOAD, True),
    ]
    # The marker goes with the next save, which an unload forces
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    assert _stored_pending(hass_storage) == []
    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert_moved_and_native(hass, legacy, before)


async def test_the_takeover_path_passes_no_device_that_may_empty_the_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Phase 9.2 D-05: the takeover pass never lets an integration-disabled twin empty the shared topic.

    The pass passes no content and no may-empty id to the registry step, so core's clear-on-remove hook never fires
    there; only the start-up catch decides that, with the gate.
    """
    legacy, before = await unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    loop_back_discovery(hass, mqtt_mock)
    original = takeover.remove_replay_twins
    may_empty: list[bool] = []

    def _record(*args: Any, **kwargs: Any) -> int:
        may_empty.append(kwargs.get("may_empty_topic", False))
        return original(*args, **kwargs)

    monkeypatch.setattr(takeover, "remove_replay_twins", _record)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert_moved_and_native(hass, legacy, before)
    assert may_empty, "the pass did not run the registry step"
    assert not any(may_empty)


async def test_an_error_after_part_of_the_move_keeps_the_device_native(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-02: an exception once entries moved is judged by the registry, so the device does not fall back to legacy."""
    legacy, before = await unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    loop_back_discovery(hass, mqtt_mock)
    real_take_over = takeover.async_take_over

    async def _fail_after_the_move(*args: Any, **kwargs: Any) -> Any:
        await real_take_over(*args, **kwargs)
        msg = "registry surprise"
        raise RuntimeError(msg)

    monkeypatch.setattr(takeover, "async_take_over", _fail_after_the_move)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert_moved_and_native(hass, legacy, before)
    assert [
        payload for payload, _retain in topic_publishes(mqtt_mock, legacy.topic) if payload and "components" in payload
    ] == []


async def test_a_deferred_mirror_keeps_its_legacy_companion_for_this_run(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A native mirror whose legacy entities are still loaded gets no native entity and nothing is moved."""
    spec = make_spec(name="Foreign lamp")
    entry, _topic = await legacy_mirror(hass, make_hub_entry, spec)
    entity_registry = er.async_get(hass)
    legacy_ids = legacy_entity_ids(hass, spec.device_id)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    mqtt_device = mqtt_device_of(hass, spec.device_id)
    assert mqtt_device is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    store_the_mirror_as_native(hass_storage, spec)
    mqtt_mock.async_publish.reset_mock()
    monkeypatch.setattr(takeover, "TAKEOVER_UNLOAD_TIMEOUT", 0.05)
    block_discovery_delivery(monkeypatch)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    manager = manager_of(entry)
    assert manager.is_native(spec.device_id) is False
    assert entity_registry.async_get_entity_id("switch", DOMAIN, spec.device_id) is None
    for entity_id, old in before.items():
        assert entity_registry.async_get(entity_id) == old
    assert mqtt_device_of(hass, spec.device_id) == mqtt_device
    companion = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, spec.device_id), entry.entry_id)
    assert companion is not None
    assert companion.model == "Switch device (mirror)"
    assert entity_registry.async_get_entity_id("select", DOMAIN, f"{spec.device_id}_mode") is not None
    # The legacy test buttons still reach the mirror through the test topic
    assert manager.mirrors[spec.device_id].unsubscribe_test is not None
    assert [topic for topic in _all_topics(mqtt_mock) if topic.startswith(f"{PREFIX}/")] == []


async def test_an_unexpected_error_in_the_takeover_defers_the_device_and_the_integration_still_starts(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registry surprise never keeps the integration from starting: the device stays pending and legacy."""
    subentry = make_switch_subentry("Lamp")
    device_id = subentry["data"][CONF_DEVICE_ID]
    seed_native_pending(hass_storage, pending=[device_id])
    monkeypatch.setattr(takeover, "async_take_over", AsyncMock(side_effect=RuntimeError("registry surprise")))
    monkeypatch.setattr(takeover, "legacy_device", lambda *_args: object())

    entry = await setup_entry(hass, make_hub_entry([subentry]))

    assert entry.state is ConfigEntryState.LOADED
    assert manager_of(entry).is_native(device_id) is False
    assert _stored_pending(hass_storage) == [device_id]
    published = topic_publishes(mqtt_mock, discovery_topic(PREFIX, device_id))
    assert (CLEAR_PAYLOAD, True) not in published
    assert [json.loads(payload) for payload, retain in published if not retain] == [{"migrate_discovery": True}]


async def test_a_running_mirror_whose_owner_turns_native_stays_legacy_until_the_reload(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-12, T-5-09: the marked document only schedules the reload; the mirror reads legacy until that reload runs."""
    spec = make_spec(name="Foreign lamp")
    entry, _topic = await legacy_mirror(hass, make_hub_entry, spec)
    reloads: list[str] = []
    # The reload is captured, not run, so the state between the switch and the reload stays observable
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", reloads.append)

    await _deliver_document(hass, spec.device_id, document_payload(spec, rev=2, native=True))

    manager = manager_of(entry)
    assert reloads == [entry.entry_id]
    assert manager.is_native(spec.device_id) is False
    assert er.async_get(hass).async_get_entity_id("switch", DOMAIN, spec.device_id) is None
    assert len(legacy_entity_ids(hass, spec.device_id)) == 3


async def test_a_deferred_device_released_here_starts_clean_in_the_same_run(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A released id loses its per-run deferral, so a native mirror that follows under the same id is native at once."""
    subentry = make_switch_subentry("Lamp")
    device_id = subentry["data"][CONF_DEVICE_ID]
    seed_native_pending(hass_storage, pending=[device_id])
    monkeypatch.setattr(takeover, "async_take_over", AsyncMock(side_effect=RuntimeError("registry surprise")))
    monkeypatch.setattr(takeover, "legacy_device", lambda *_args: object())
    entry = await setup_entry(hass, make_hub_entry([subentry]))
    manager = manager_of(entry)
    assert manager.migration.is_deferred(device_id) is True

    assert await manager.async_release_locally([device_id]) == [device_id]
    await hass.async_block_till_done(wait_background_tasks=True)
    spec = make_spec(device_id=device_id, name="Lamp")
    await _deliver_document(hass, device_id, document_payload(spec, native=True))

    assert device_id in manager.mirrors
    assert manager.is_native(device_id) is True


# --- Task 3: adoption between native and legacy devices ------------------------------------------------------------

ON_ACTIONS = [{"action": "test.on"}]
OFF_ACTIONS = [{"action": "test.off"}]


async def _approved_mirror(hass: HomeAssistant, entry: MockConfigEntry, spec: Any, *, native: bool) -> None:
    """Deliver the document of a foreign owner, marked or not, and approve exactly the actions the mirror has."""
    async_mock_service(hass, "test", "on")
    async_mock_service(hass, "test", "off")
    async_fire_mqtt_message(
        hass, config_topic(BASE, spec.device_id), document_payload(spec, native=native), retain=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    info = manager_of(entry).mirrors[spec.device_id].mirror
    assert info is not None
    assert await manager_of(entry).async_approve(spec.device_id, info.actions_hash)


def _switch_entry(hass: HomeAssistant, device_id: str) -> er.RegistryEntry | None:
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id("switch", DOMAIN, device_id)
    return None if entity_id is None else entity_registry.async_get(entity_id)


def _assert_nothing_removed(entity_events: list[Any], device_events: list[Any], state_events: list[Any]) -> None:
    """Assert that no registry entry, device or state was removed in the captured events."""
    assert [event.data["entity_id"] for event in entity_events if event.data["action"] == "remove"] == []
    assert [event.data["device_id"] for event in device_events if event.data["action"] == "remove"] == []
    assert [event.data["entity_id"] for event in state_events if event.data["new_state"] is None] == []


def _test_button_entries(hass: HomeAssistant, spec: Any) -> dict[str, er.RegistryEntry]:
    """Return the registry entries of the native test buttons of a device, by entity id."""
    entity_registry = er.async_get(hass)
    entity_ids = (
        entity_registry.async_get_entity_id("button", DOMAIN, f"{spec.device_id}_test_{key}") for key in spec.triggers
    )
    return {entity_id: entity_registry.async_get(entity_id) for entity_id in entity_ids if entity_id is not None}


async def test_adopting_a_native_mirror_keeps_the_device_native_on_a_legacy_instance(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-5-12: the adopted device stays native although this instance's own flag is not set, and it is marked."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await setup_entry(hass, make_hub_entry())
    await _approved_mirror(hass, entry, spec, native=True)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    old_switch = _switch_entry(hass, spec.device_id)
    assert old_switch is not None
    # The user customized the mirror's native switch: an area and a name (CR-01, IN-04)
    area = ar.async_get(hass).async_create("Living room")
    entity_registry.async_update_entity(old_switch.entity_id, area_id=area.id, name="My lamp")
    old_switch = _switch_entry(hass, spec.device_id)
    assert old_switch is not None
    old_buttons = _test_button_entries(hass, spec)
    assert len(old_buttons) == len(spec.triggers) > 0
    old_device = device_registry.async_get_device_by_identifier((DOMAIN, spec.device_id), entry.entry_id)
    assert old_device is not None
    mqtt_mock.async_publish.reset_mock()

    # Home Assistant restores a deleted registry entry on re-creation, so the final state alone cannot show the loss:
    # nothing of the device may be removed on the way, or exposure settings and the live state would be dropped
    entity_events = async_capture_events(hass, er.EVENT_ENTITY_REGISTRY_UPDATED)
    device_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    state_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await manager_of(entry).async_adopt(spec.device_id, force=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    _assert_nothing_removed(entity_events, device_events, state_events)

    manager = manager_of(entry)
    assert spec.device_id in manager.devices
    assert manager.is_native(spec.device_id) is True
    assert hass_storage[STORE_KEY]["data"]["native"]["devices"] == [spec.device_id]
    native_switch = _switch_entry(hass, spec.device_id)
    assert native_switch is not None
    assert native_switch.config_subentry_id == manager.subentry_id_of(spec.device_id)
    # The same registry entry survives with its id, entity id, area and name (CR-01)
    assert native_switch.id == old_switch.id
    assert native_switch.entity_id == old_switch.entity_id
    assert native_switch.area_id == area.id
    assert native_switch.name == "My lamp"
    for entity_id, old_button in old_buttons.items():
        button = entity_registry.async_get(entity_id)
        assert button is not None
        assert button.id == old_button.id
        assert button.config_subentry_id == manager.subentry_id_of(spec.device_id)
    # ... and so does the device that carries them
    new_device = device_registry.async_get_device_by_identifier((DOMAIN, spec.device_id), entry.entry_id)
    assert new_device is not None
    assert new_device.id == old_device.id
    assert new_device.config_subentry_id == manager.subentry_id_of(spec.device_id)
    assert new_device.model == "Switch device"
    state = hass.states.get(old_switch.entity_id)
    assert state is not None
    assert not state.attributes.get("restored")
    assert topic_publishes(mqtt_mock, discovery_topic(PREFIX, spec.device_id)) == []
    document = json.loads(topic_publishes(mqtt_mock, config_topic(BASE, spec.device_id))[-1][0])
    assert document["entities"] == "native"


async def test_adopting_a_legacy_mirror_on_a_native_instance_queues_the_takeover(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-5-12: the legacy device is pending and reloads the entry; until then no native entity doubles the legacy."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    seed_native_pending(hass_storage, pending=[])
    entry = await setup_entry(hass, make_hub_entry())
    await _approved_mirror(hass, entry, spec, native=False)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await manager_of(entry).async_adopt(spec.device_id, force=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    manager = manager_of(entry)
    assert spec.device_id in manager.devices
    assert hass_storage[STORE_KEY]["data"]["native"]["pending"] == [spec.device_id]
    reload.assert_called_once_with(entry.entry_id)
    assert manager.is_native(spec.device_id) is False
    assert _switch_entry(hass, spec.device_id) is None


async def test_adoption_on_a_legacy_instance_of_a_legacy_mirror_is_unchanged(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """The Phase 4 behavior holds when neither side is native: legacy discovery, no marker, no pass, no reload."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await setup_entry(hass, make_hub_entry())
    await _approved_mirror(hass, entry, spec, native=False)
    mqtt_mock.async_publish.reset_mock()

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await manager_of(entry).async_adopt(spec.device_id, force=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    manager = manager_of(entry)
    assert spec.device_id in manager.devices
    assert manager.is_native(spec.device_id) is False
    assert "native" not in hass_storage[STORE_KEY]["data"]
    reload.assert_not_called()
    published = topic_publishes(mqtt_mock, discovery_topic(PREFIX, spec.device_id))
    assert [json.loads(payload)["components"] and retain for payload, retain in published] == [True]
    document = json.loads(topic_publishes(mqtt_mock, config_topic(BASE, spec.device_id))[-1][0])
    assert "entities" not in document


# --- Phase 6: the native flag of a mirror lives in the Store, not in the payload (IN-02, MIG-04) --------------------


async def _deliver_document(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = False) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _native_mirror_ids(manager: Manager) -> list[str]:
    """Return the persisted native mirror ids; `.get` makes a missing key an assertion failure, not a KeyError."""
    return manager._data_to_save().get("native", {}).get("mirrors", [])


def _padded_to_the_limit(spec: Any, rev: int) -> str:
    """Return the unmarked document of a spec, padded with an ignored top-level key to exactly MAX_DOCUMENT_BYTES."""
    plain = document_payload(spec, rev=rev)
    # The canonical JSON cost of an empty `pad` key: a comma plus `"pad":""`
    pad = MAX_DOCUMENT_BYTES - len(plain.encode()) - len(',"pad":""')
    payload = document_payload(spec, rev=rev, tamper=lambda document: document.update(pad="x" * pad))
    assert len(payload.encode()) == MAX_DOCUMENT_BYTES
    return payload


async def test_a_native_mirror_at_the_size_limit_stays_native_after_a_restart(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """IN-02: the native flag of a mirror survives a restart whatever the size of its last document."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    # The content must change: an ignored key is never hashed, so padding alone would not even be applied
    changed = make_spec(device_id=spec.device_id, name="Foreign lamp", on=OFF_ACTIONS)
    entry = await setup_entry(hass, make_hub_entry())
    await _deliver_document(hass, spec.device_id, document_payload(spec, native=True))
    await _deliver_document(hass, spec.device_id, _padded_to_the_limit(changed, rev=2))
    assert manager_of(entry).is_native(spec.device_id)

    await restart_entry(hass, entry)

    manager = manager_of(entry)
    assert manager.is_native(spec.device_id)
    assert manager.mirrors[spec.device_id].unsubscribe_test is None
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _deliver_document(hass, spec.device_id, document_payload(changed, rev=3, native=True))
    schedule_reload.assert_not_called()


async def test_native_mirror_set_ignores_malformed_and_unlisted_ids(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-06-01, T-06-03: only a valid listed id of a cached mirror makes it native; the Store is untrusted input."""
    listed = make_spec(name="Listed lamp", on=ON_ACTIONS)
    unlisted = make_spec(name="Unlisted lamp", on=ON_ACTIONS)
    seed_store(
        hass_storage,
        {
            STORE_MIRRORS: {
                listed.device_id: document_payload(listed),
                unlisted.device_id: document_payload(unlisted),
            },
            "native": {
                "instance": False,
                "pending": [],
                "devices": [],
                "mirrors": [listed.device_id, 42, "../bad", "x" * 300],
            },
        },
    )

    entry = await setup_entry(hass, make_hub_entry())

    manager = manager_of(entry)
    assert manager.is_native(listed.device_id)
    assert not manager.is_native(unlisted.device_id)
    assert _native_mirror_ids(manager) == [listed.device_id]


async def test_native_mirror_set_takes_over_a_marker_only_store_of_the_previous_release(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-02: a 1.0.0 Store has the marker in the cached payload and no native key; it loads native and is migrated."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    seed_store(hass_storage, {STORE_MIRRORS: {spec.device_id: document_payload(spec, native=True)}})

    entry = await setup_entry(hass, make_hub_entry())

    assert manager_of(entry).is_native(spec.device_id)
    assert _native_mirror_ids(manager_of(entry)) == [spec.device_id]
    await restart_entry(hass, entry)
    assert manager_of(entry).is_native(spec.device_id)
    assert _native_mirror_ids(manager_of(entry)) == [spec.device_id]


async def test_native_mirror_set_is_cleared_by_a_tombstone(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-03: the owner deleting the device ends the mirror, and with it the id in the persisted set."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    entry = await setup_entry(hass, make_hub_entry())
    await _deliver_document(hass, spec.device_id, document_payload(spec, native=True))
    manager = manager_of(entry)
    assert _native_mirror_ids(manager) == [spec.device_id]

    await _deliver_document(hass, spec.device_id, "")

    assert spec.device_id not in manager.mirrors
    assert _native_mirror_ids(manager) == []


async def test_native_mirror_set_moves_to_the_owned_devices_at_adoption(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-03: an adopted native mirror is an owned native device now, so the owned set applies and the id leaves."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await setup_entry(hass, make_hub_entry())
    await _approved_mirror(hass, entry, spec, native=True)
    manager = manager_of(entry)
    assert _native_mirror_ids(manager) == [spec.device_id]

    await manager.async_adopt(spec.device_id, force=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _native_mirror_ids(manager) == []
    assert manager._data_to_save()["native"]["devices"] == [spec.device_id]


async def test_native_mirror_set_never_marks_a_later_legacy_mirror_native(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-06-01: an id without a cached mirror is pruned at the start and cannot make a later unmarked mirror native."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    seed_store(hass_storage, {"native": {"instance": False, "pending": [], "devices": [], "mirrors": [spec.device_id]}})
    entry = await setup_entry(hass, make_hub_entry())
    manager = manager_of(entry)
    assert _native_mirror_ids(manager) == []

    await _deliver_document(hass, spec.device_id, document_payload(spec))

    assert manager.is_native(spec.device_id) is False
    assert manager.mirrors[spec.device_id].unsubscribe_test is not None
    assert _native_mirror_ids(manager) == []


async def test_native_mirror_set_survives_a_failed_adoption(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-03: when the subentry cannot be added, the restored mirror is native again although no document marks it."""
    spec = make_spec(name="Foreign lamp")
    changed = make_spec(device_id=spec.device_id, name="Renamed lamp")
    entry = await setup_entry(hass, make_hub_entry())
    await _deliver_document(hass, spec.device_id, document_payload(spec, native=True))
    await _deliver_document(hass, spec.device_id, document_payload(changed, rev=2))
    manager = manager_of(entry)
    assert manager.is_native(spec.device_id)

    with (
        patch.object(hass.config_entries, "async_add_subentry", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        await manager.async_adopt(spec.device_id, force=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert spec.device_id in manager.mirrors
    assert manager.is_native(spec.device_id)
    assert _native_mirror_ids(manager) == [spec.device_id]


def test_native_mirror_set_parser_cuts_and_validates() -> None:
    """T-06-03: the persisted set keeps valid ids only, at most MAX_MIRRORS of them, and anything else is empty."""
    valid = sorted(str(uuid.uuid4()) for _ in range(MAX_MIRRORS + 1))
    assert _parse_native({"native": {"mirrors": valid}}).mirrors == set(valid[:MAX_MIRRORS])
    mixed = ["../bad", 42, None, valid[0], "x" * 300]
    assert _parse_native({"native": {"mirrors": mixed}}).mirrors == {valid[0]}
    for not_a_list in ("text", {"a": "b"}, None, 7):
        assert _parse_native({"native": {"mirrors": not_a_list}}).mirrors == set()
