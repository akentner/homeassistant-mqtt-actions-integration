"""The native takeover pass at the start of the manager: owners, followers, deferral and adoption (D-05, D-09, D-12)."""

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import DEFAULT, AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component import plugins
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_mqtt_message,
    async_mock_service,
)

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    DOMAIN,
    STORE_KEY,
    STORE_MIRRORS,
    STORE_VERSION,
)
from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.topics import config_topic, discovery_topic, state_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.test_takeover import (
    CLEAR_PAYLOAD,
    MIGRATE_PAYLOAD,
    PREFIX,
    customize_mqtt_device,
    legacy_entity_ids,
    setup_legacy_device,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"


def _seed(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {"version": STORE_VERSION, "minor_version": 1, "key": STORE_KEY, "data": data}


def _seed_native(hass_storage: dict[str, Any], *, pending: list[str], instance: bool = True) -> None:
    """Seed the persisted native state of an instance whose devices still wait for the takeover."""
    _seed(hass_storage, {"native": {"instance": instance, "pending": pending, "devices": []}})


def _stored_pending(hass_storage: dict[str, Any]) -> list[str]:
    return hass_storage[STORE_KEY]["data"]["native"]["pending"]


def _loop_back_discovery(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """
    Deliver every publish on a discovery topic back to core MQTT as a live message, the way a real broker would.

    The mocked paho client already loops a publish back with the publish's own retain flag, so a retained clear would
    reach core as a retained replay, which core drops when it saw a retained message on the topic before. A live
    delivery makes core handle the clear like it does in production. The migrate payload is live either way.
    """

    def _deliver(topic: str, payload: Any, *_args: Any, **_kwargs: Any) -> Any:
        if topic.startswith(f"{PREFIX}/"):
            async_fire_mqtt_message(hass, topic, payload, retain=False)
        return DEFAULT

    mqtt_mock.async_publish.side_effect = _deliver


def _block_discovery_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Stop the mocked paho client from looping publishes on a discovery topic back, so core MQTT never hears them.

    That is a broker that has not delivered the owner's migrate payload (yet): the legacy entities stay loaded.
    """
    original = plugins.async_fire_mqtt_message

    def _fire(hass: HomeAssistant, topic: str, *args: Any, **kwargs: Any) -> None:
        if not topic.startswith(f"{PREFIX}/"):
            original(hass, topic, *args, **kwargs)

    monkeypatch.setattr(plugins, "async_fire_mqtt_message", _fire)


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple[Any, bool]]:
    """Return the (payload, retain) pairs published on a topic, in order."""
    return [(call.args[1], call.args[3]) for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _all_topics(mqtt_mock: Any) -> list[str]:
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _restart(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Unload and set up the entry again, the way an update of the integration does."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


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
    _seed_native(hass_storage, pending=[device_id])
    mqtt_mock.async_publish.reset_mock()
    _loop_back_discovery(hass, mqtt_mock)

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

    published = _publishes(mqtt_mock, legacy.topic)
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in published] == [
        ({"migrate_discovery": True}, False),
        (CLEAR_PAYLOAD, True),
    ]
    document = json.loads(_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
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
    _seed_native(hass_storage, pending=[device_id])
    _loop_back_discovery(hass, mqtt_mock)
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
    _seed_native(hass_storage, pending=[device_id])

    await _setup(hass, make_hub_entry([subentry]))

    published = _publishes(mqtt_mock, discovery_topic(PREFIX, device_id))
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in published] == [
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
    _seed(
        hass_storage,
        {
            STORE_MIRRORS: {mirror_spec.device_id: document_payload(mirror_spec)},
            "native": {"instance": True, "pending": [mirror_spec.device_id, unknown_id], "devices": []},
        },
    )

    entry = await _setup(hass, make_hub_entry([own]))

    assert mirror_spec.device_id in _manager(entry).mirrors
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
    _seed_native(hass_storage, pending=[])

    entry = await _setup(hass, make_hub_entry([subentry]))

    assert _publishes(mqtt_mock, discovery_topic(PREFIX, device_id)) == []
    first = json.loads(_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert first["entities"] == "native"
    mqtt_mock.async_publish.reset_mock()

    await _restart(hass, entry)

    assert _publishes(mqtt_mock, discovery_topic(PREFIX, device_id)) == []
    second = json.loads(_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert second["entities"] == "native"
    assert state_topic(BASE, device_id) not in _all_topics(mqtt_mock)


# --- Task 2: followers and the legacy fallback ---------------------------------------------------------------------


async def _legacy_mirror(hass: HomeAssistant, make_hub_entry: Callable, spec: Any) -> tuple[MockConfigEntry, str]:
    """Set up a follower with an unmarked mirror whose legacy core MQTT entities exist; return it and the topic."""
    entry = await _setup(hass, make_hub_entry())
    topic = discovery_topic(PREFIX, spec.device_id)
    discovery = build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3")
    async_fire_mqtt_message(hass, topic, json.dumps(discovery), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), document_payload(spec), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(legacy_entity_ids(hass, spec.device_id)) == 3
    assert spec.device_id in _manager(entry).mirrors
    return entry, topic


def _store_the_mirror_as_native(hass_storage: dict[str, Any], spec: Any) -> None:
    """Replace the cached document of the mirror by the marked one, as if the owner had upgraded and been heard."""
    hass_storage[STORE_KEY]["data"][STORE_MIRRORS][spec.device_id] = document_payload(spec, native=True)


def _mqtt_device_of(hass: HomeAssistant, device_id: str) -> dr.DeviceEntry | None:
    mqtt_entry_id = hass.config_entries.async_entries("mqtt")[0].entry_id
    return dr.async_get(hass).async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry_id)


async def test_a_follower_takes_over_a_native_mirror_at_start_without_publishing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-05, D-12: the entities and the device of a native mirror move to the entry, nothing goes on the broker."""
    spec = make_spec(name="Foreign lamp")
    entry, topic = await _legacy_mirror(hass, make_hub_entry, spec)
    entity_registry = er.async_get(hass)
    legacy_ids = legacy_entity_ids(hass, spec.device_id)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", spec.device_id)
    mqtt_device = _mqtt_device_of(hass, spec.device_id)
    assert switch_id is not None
    assert mqtt_device is not None
    # The owner upgraded: its migrate payload unloaded the discovered entities on every instance
    async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _store_the_mirror_as_native(hass_storage, spec)
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
    _seed_native(hass_storage, pending=[device_id])
    mqtt_mock.async_publish.reset_mock()
    monkeypatch.setattr(takeover, "TAKEOVER_UNLOAD_TIMEOUT", 0.05)
    _block_discovery_delivery(monkeypatch)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    manager = _manager(legacy.entry)
    assert manager.is_native(device_id) is False
    assert _stored_pending(hass_storage) == [device_id]
    for entity_id, old in before.items():
        assert entity_registry.async_get(entity_id) == old
    assert entity_registry.async_get_entity_id("switch", DOMAIN, device_id) is None
    published = _publishes(mqtt_mock, legacy.topic)
    assert (CLEAR_PAYLOAD, True) not in published
    assert any(payload and "components" in json.loads(payload) for payload, _retain in published)
    document = json.loads(_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert "entities" not in document

    # The next setup retries and, with the migrate delivered by the broker, completes the takeover
    monkeypatch.setattr(takeover, "TAKEOVER_UNLOAD_TIMEOUT", 5.0)
    _loop_back_discovery(hass, mqtt_mock)
    await _restart(hass, legacy.entry)

    assert _stored_pending(hass_storage) == []
    assert _manager(legacy.entry).is_native(device_id) is True
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform) == (old.id, DOMAIN)


async def _unloaded_legacy_device(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> tuple[Any, dict[str, er.RegistryEntry]]:
    """Return a legacy device whose entry is unloaded and pending for the takeover, and its legacy registry entries."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    before = {
        entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_entity_ids(hass, legacy.device_id)
    }
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _seed_native(hass_storage, pending=[legacy.device_id])
    mqtt_mock.async_publish.reset_mock()
    return legacy, before


def _assert_moved_and_native(hass: HomeAssistant, legacy: Any, before: dict[str, er.RegistryEntry]) -> None:
    """Assert that the entities of the device sit under this integration, loaded, and that the device is native."""
    entity_registry = er.async_get(hass)
    assert legacy.entry.runtime_data.is_native(legacy.device_id) is True
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform) == (old.id, DOMAIN)
        state = hass.states.get(entity_id)
        assert state is not None
        assert not state.attributes.get("restored")


async def test_a_failed_retained_clear_after_the_move_keeps_the_device_native_and_is_retried(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """WR-02: the registry moved, so the device stays native; only the clear is pending and a resync retries it."""
    legacy, before = await _unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    _loop_back_discovery(hass, mqtt_mock)
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

    _assert_moved_and_native(hass, legacy, before)
    assert _stored_pending(hass_storage) == [legacy.device_id]
    # No legacy discovery goes out again, or core MQTT would create the entities a second time
    assert [
        payload for payload, _retain in _publishes(mqtt_mock, legacy.topic) if payload and "components" in payload
    ] == []

    broker_down = False
    assert await _manager(legacy.entry).async_resync()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (CLEAR_PAYLOAD, True) in _publishes(mqtt_mock, legacy.topic)
    # The marker goes with the next save, which an unload forces
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    assert _stored_pending(hass_storage) == []
    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _assert_moved_and_native(hass, legacy, before)


async def test_an_error_after_part_of_the_move_keeps_the_device_native(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-02: an exception once entries moved is judged by the registry, so the device does not fall back to legacy."""
    legacy, before = await _unloaded_legacy_device(hass, mqtt_mock, hass_storage, make_hub_entry, make_switch_subentry)
    _loop_back_discovery(hass, mqtt_mock)
    real_take_over = takeover.async_take_over

    async def _fail_after_the_move(*args: Any, **kwargs: Any) -> Any:
        await real_take_over(*args, **kwargs)
        msg = "registry surprise"
        raise RuntimeError(msg)

    monkeypatch.setattr(takeover, "async_take_over", _fail_after_the_move)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    _assert_moved_and_native(hass, legacy, before)
    assert [
        payload for payload, _retain in _publishes(mqtt_mock, legacy.topic) if payload and "components" in payload
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
    entry, _topic = await _legacy_mirror(hass, make_hub_entry, spec)
    entity_registry = er.async_get(hass)
    legacy_ids = legacy_entity_ids(hass, spec.device_id)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    mqtt_device = _mqtt_device_of(hass, spec.device_id)
    assert mqtt_device is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _store_the_mirror_as_native(hass_storage, spec)
    mqtt_mock.async_publish.reset_mock()
    monkeypatch.setattr(takeover, "TAKEOVER_UNLOAD_TIMEOUT", 0.05)
    _block_discovery_delivery(monkeypatch)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    manager = _manager(entry)
    assert manager.is_native(spec.device_id) is False
    assert entity_registry.async_get_entity_id("switch", DOMAIN, spec.device_id) is None
    for entity_id, old in before.items():
        assert entity_registry.async_get(entity_id) == old
    assert _mqtt_device_of(hass, spec.device_id) == mqtt_device
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
    _seed_native(hass_storage, pending=[device_id])
    monkeypatch.setattr(takeover, "async_take_over", AsyncMock(side_effect=RuntimeError("registry surprise")))
    monkeypatch.setattr(takeover, "legacy_device", lambda *_args: object())

    entry = await _setup(hass, make_hub_entry([subentry]))

    assert entry.state is ConfigEntryState.LOADED
    assert _manager(entry).is_native(device_id) is False
    assert _stored_pending(hass_storage) == [device_id]
    published = _publishes(mqtt_mock, discovery_topic(PREFIX, device_id))
    assert (CLEAR_PAYLOAD, True) not in published
    assert [json.loads(payload) for payload, retain in published if not retain] == [{"migrate_discovery": True}]


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
    info = _manager(entry).mirrors[spec.device_id].mirror
    assert info is not None
    assert await _manager(entry).async_approve(spec.device_id, info.actions_hash)


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
    entry = await _setup(hass, make_hub_entry())
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
    await _manager(entry).async_adopt(spec.device_id, force=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    _assert_nothing_removed(entity_events, device_events, state_events)

    manager = _manager(entry)
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
    assert _publishes(mqtt_mock, discovery_topic(PREFIX, spec.device_id)) == []
    document = json.loads(_publishes(mqtt_mock, config_topic(BASE, spec.device_id))[-1][0])
    assert document["entities"] == "native"


async def test_adopting_a_legacy_mirror_on_a_native_instance_queues_the_takeover(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-5-12: the legacy device is pending and reloads the entry; until then no native entity doubles the legacy."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    _seed_native(hass_storage, pending=[])
    entry = await _setup(hass, make_hub_entry())
    await _approved_mirror(hass, entry, spec, native=False)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _manager(entry).async_adopt(spec.device_id, force=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    manager = _manager(entry)
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
    entry = await _setup(hass, make_hub_entry())
    await _approved_mirror(hass, entry, spec, native=False)
    mqtt_mock.async_publish.reset_mock()

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _manager(entry).async_adopt(spec.device_id, force=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    manager = _manager(entry)
    assert spec.device_id in manager.devices
    assert manager.is_native(spec.device_id) is False
    assert "native" not in hass_storage[STORE_KEY]["data"]
    reload.assert_not_called()
    published = _publishes(mqtt_mock, discovery_topic(PREFIX, spec.device_id))
    assert [json.loads(payload)["components"] and retain for payload, retain in published] == [True]
    document = json.loads(_publishes(mqtt_mock, config_topic(BASE, spec.device_id))[-1][0])
    assert "entities" not in document
