"""
Pins of the Home Assistant core internals this integration depends on without a public contract (FIX-01, D-08).

These tests run against the installed Home Assistant, not against a mock of it. Per D-08 they are never skipped, never
marked as an expected failure and carry no marker of their own: a core or PHACC bump that breaks one of them turns CI
red, a Dependabot PR included, and that is the wanted signal. When a pin turns red, read its failure message: it names
the core spot that changed and the documented fallback, so the fix is either an update of the integration or a change
of the pin made on purpose.
"""

import inspect
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import storage
from homeassistant.helpers.entity import entity_sources
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    StoreWithoutWriteLoad,
    async_fire_mqtt_message,
    async_fire_time_changed,
)

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.discovery import DiscoveryContent, build_discovery
from tests.documents import FOREIGN_OWNER, make_spec
from tests.helpers import (
    BASE,
    MIGRATE_PAYLOAD,
    falsy_publishes,
    legacy_entity_ids,
    legacy_mirror,
    quiet_period_passes,
    replay_discovery,
    store_the_mirror_as_native,
    topic_publishes,
)
from tests.log_helpers import own_warnings

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

FLUSH_FALLBACK_HINT = (
    "Home Assistant changed the private registry flush API (registry._store / registry._data_to_save): "
    "takeover.async_flush_registries no longer writes ahead of the schedule. The documented fallback is the scheduled "
    "registry save about 10 s later (see the docstring of takeover.async_flush_registries); update the flush or accept "
    "the fallback and change this pin on purpose."
)
READ_ONLY_LOAD_HINT = (
    "Home Assistant changed how a read-only Store loads a newer minor version: after the migration hook Core now "
    "writes the result (or the hook no longer runs). LocalActionsStore.async_load relies on a Store built with "
    "read_only=True returning the migrated data without a write (WR-05, D-22); read storage.Store._async_load_data and "
    "_async_handle_write_data, then update the reader of local_actions_store.py or change this pin on purpose."
)
FLUSH_WARNING = "A registry could not be written ahead of its schedule after the native takeover"
ENTITY_STORAGE_KEY = "core.entity_registry"
DEVICE_STORAGE_KEY = "core.device_registry"
PIN_ID = "flush-pin"
EAGER_TASK_HINT = (
    "Home Assistant changed Entity._async_registry_updated (homeassistant/helpers/entity.py): a loaded MQTT entity "
    "that is disabled and removed in one synchronous step now makes core MQTT publish its clear-on-remove on the "
    "shared discovery topic, which deletes the rows other instances keep (CR-01). The no-clear guarantee relied on "
    "the eager task that unsubscribes the entity before the remove event. Next step: let "
    "takeover.remove_replay_twins wait until the disabled entity has left entity_sources before removing it, or "
    "publish the migrate payload first (review 2 IN-02, research Pitfall 9)."
)


@pytest.fixture(autouse=True)
def fast_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll quickly; the default wait is long only because production waits for a real broker round trip."""
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)


def _stored_entity_ids(hass_storage: dict[str, Any]) -> set[str]:
    """Return the entity ids the entity registry file holds right now."""
    stored = hass_storage.get(ENTITY_STORAGE_KEY)
    return {row["entity_id"] for row in stored["data"]["entities"]} if stored else set()


def _stored_device_ids(hass_storage: dict[str, Any]) -> set[str]:
    """Return the device ids the device registry file holds right now."""
    stored = hass_storage.get(DEVICE_STORAGE_KEY)
    return {row["id"] for row in stored["data"]["devices"]} if stored else set()


def _restore_real_registry_saves(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Give the registry stores of the test instance the real Store.async_save back.

    The PHACC hass fixture builds the entity registry on its StoreWithoutWriteLoad, whose async_save does nothing, so
    without this the immediate write could never reach hass_storage. Only that harness stub is undone; the registry,
    its _store attribute and its _data_to_save stay exactly as core made them.
    """
    monkeypatch.setattr(StoreWithoutWriteLoad, "async_save", storage.Store.async_save)


def _create_rows(hass: HomeAssistant) -> tuple[str, str]:
    """Create one entity registry row and one device registry row, and return their ids."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create("switch", "test", PIN_ID, config_entry=entry)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={("test", PIN_ID)})
    return entity.entity_id, device.id


async def test_the_registry_flush_writes_both_registries_ahead_of_the_scheduled_save(
    hass: HomeAssistant, hass_storage: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-06: the flush puts a new row of both registries on disk at once, without waiting for the scheduled save."""
    _restore_real_registry_saves(monkeypatch)
    entity_id, device_id = _create_rows(hass)
    assert entity_id not in _stored_entity_ids(hass_storage), "premise: the entity row is not on disk yet"
    assert device_id not in _stored_device_ids(hass_storage), "premise: the device row is not on disk yet"

    assert await takeover.async_flush_registries(hass) is True, FLUSH_FALLBACK_HINT

    assert entity_id in _stored_entity_ids(hass_storage), FLUSH_FALLBACK_HINT
    assert device_id in _stored_device_ids(hass_storage), FLUSH_FALLBACK_HINT


async def test_the_private_registry_flush_api_still_exists(hass: HomeAssistant) -> None:
    """Research Pitfall 9: both registries keep a store with async_save and a _data_to_save that needs no argument."""
    for registry in (er.async_get(hass), dr.async_get(hass)):
        assert hasattr(registry, "_store"), FLUSH_FALLBACK_HINT
        assert callable(getattr(registry._store, "async_save", None)), FLUSH_FALLBACK_HINT
        assert callable(getattr(registry, "_data_to_save", None)), FLUSH_FALLBACK_HINT
        required = [
            name
            for name, parameter in inspect.signature(registry._data_to_save).parameters.items()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        assert required == [], FLUSH_FALLBACK_HINT


async def test_a_read_only_store_returns_a_newer_minor_payload_without_writing(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """WR-05, D-22: Core saves the migration result, and a Store built read-only drops that save."""

    class ReadOnlyReader(storage.Store[dict[str, Any]]):
        async def _async_migrate_func(
            self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
        ) -> dict[str, Any]:
            return old_data

    key = "mqtt_actions.read_only_pin"
    envelope = {"version": 1, "minor_version": 2, "key": key, "data": {"records": [], "future": {"kept": True}}}
    hass_storage[key] = envelope
    before = json.dumps(hass_storage[key], sort_keys=True)

    loaded = await ReadOnlyReader(hass, 1, key, minor_version=1, read_only=True).async_load()

    assert loaded == {"records": [], "future": {"kept": True}}, READ_ONLY_LOAD_HINT
    assert json.dumps(hass_storage[key], sort_keys=True) == before, READ_ONLY_LOAD_HINT


async def test_a_refused_early_write_falls_back_to_the_scheduled_save(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-05: a refused early write returns False, logs one count-free warning, and the scheduled save still writes."""
    entity_id, _ = _create_rows(hass)
    registry = er.async_get(hass)

    async def _refuse(*_args: Any, **_kwargs: Any) -> None:
        msg = "refused"
        raise OSError(msg)

    monkeypatch.setattr(registry._store, "async_save", _refuse)

    assert await takeover.async_flush_registries(hass) is False

    warnings = own_warnings(caplog, exact=True)
    assert [record.getMessage() for record in warnings] == [FLUSH_WARNING]
    assert entity_id not in warnings[0].getMessage()
    assert PIN_ID not in warnings[0].getMessage()
    assert entity_id not in _stored_entity_ids(hass_storage), "premise: the refused write left the row off disk"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    assert entity_id in _stored_entity_ids(hass_storage), (
        "the scheduled registry save no longer follows a refused flush"
    )


def _record_loaded_at_removal(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> list[tuple[DiscoveryContent, list[bool]]]:
    """
    Wrap takeover.remove_replay_twins and record, at each call and before it runs, what the rows of the device were.

    Each record is the content the caller passed (the takeover path passes UNKNOWN, the catch what the shared topic
    holds) and, for each legacy row of the device, whether it was loaded (in entity_sources) and enabled. That is the
    premise of the pins below: only a loaded, enabled row depends on the eager task of core.
    """
    calls: list[tuple[DiscoveryContent, list[bool]]] = []
    original = takeover.remove_replay_twins

    def _recording(*args: Any, **kwargs: Any) -> int:
        device_id = args[2]
        loaded = entity_sources(hass)
        entity_registry = er.async_get(hass)
        flags = [
            entity_id in loaded and entity_registry.async_get(entity_id).disabled_by is None
            for entity_id in legacy_entity_ids(hass, device_id)
        ]
        calls.append((kwargs.get("content", DiscoveryContent.UNKNOWN), flags))
        return original(*args, **kwargs)

    monkeypatch.setattr(takeover, "remove_replay_twins", _recording)
    return calls


async def test_the_takeover_path_removes_a_loaded_enabled_row_without_a_clear_on_the_shared_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    FIX-07 (D-07): a replay right after the takeover of a follower's mirror leaves rows that go without any clear.

    A follower publishes nothing on the shared core-prefix topic, so any publish there is core's own clear-on-remove.
    The rows are loaded and enabled when the takeover path removes them; only the eager task core runs on the disable
    keeps that removal silent.
    """
    spec = make_spec(name="Foreign lamp")
    entry, topic = await legacy_mirror(hass, make_hub_entry, spec)
    async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    store_the_mirror_as_native(hass_storage, spec)
    mqtt_mock.async_publish.reset_mock()
    discovery = json.dumps(build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3"))
    replayed: list[list[str]] = []
    real_take_over = takeover.async_take_over

    async def _take_over_then_replay(*args: Any, **kwargs: Any) -> Any:
        status = await real_take_over(*args, **kwargs)
        replayed.append(await replay_discovery(hass, topic, discovery, spec.device_id))
        return status

    monkeypatch.setattr(takeover, "async_take_over", _take_over_then_replay)
    calls = _record_loaded_at_removal(monkeypatch, hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(replayed) == 1
    assert len(replayed[0]) == 3, "premise: the replay created the three legacy rows"
    assert calls, "premise: the takeover path did not call takeover.remove_replay_twins"
    content, flags = calls[0]
    assert content is DiscoveryContent.UNKNOWN, "premise: the first removal is not the one of the takeover path"
    assert any(flags), "premise: no replayed row was loaded and enabled when the takeover path removed it"
    assert legacy_entity_ids(hass, spec.device_id) == [], EAGER_TASK_HINT
    assert topic_publishes(mqtt_mock, topic) == [], EAGER_TASK_HINT
    assert falsy_publishes(mqtt_mock, topic) == [], EAGER_TASK_HINT


async def test_the_replay_catch_removes_a_loaded_enabled_row_without_a_clear_on_the_shared_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    FIX-07 (D-07): on a running follower the catch removes loaded, enabled replay rows without any clear.

    The guard disables the replayed switch, which stays as an integration-disabled twin on LEGACY content (09.2 D-05);
    the two test buttons stay loaded and enabled until the catch removes them. A follower publishes nothing on the
    shared core-prefix topic, so any publish there is core's own clear-on-remove.
    """
    spec = make_spec(name="Foreign lamp")
    entry, topic = await legacy_mirror(hass, make_hub_entry, spec)
    async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    store_the_mirror_as_native(hass_storage, spec)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert legacy_entity_ids(hass, spec.device_id) == [], "premise: the takeover of the mirror is not done"
    calls = _record_loaded_at_removal(monkeypatch, hass)
    mqtt_mock.async_publish.reset_mock()
    discovery = json.dumps(build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3"))

    replayed = await replay_discovery(hass, topic, discovery, spec.device_id)

    assert len(replayed) == 3, "premise: the replay created the three legacy rows"
    entity_registry = er.async_get(hass)
    (switch,) = [entity_id for entity_id in replayed if entity_id.startswith("switch.")]
    buttons = [entity_id for entity_id in replayed if entity_id != switch]
    assert entity_registry.async_get(switch).disabled_by is er.RegistryEntryDisabler.INTEGRATION, (
        "premise: the guard did not disable the replayed switch"
    )
    assert calls == [], "premise: a removal ran before the quiet period passed"

    await quiet_period_passes(hass)

    catch_calls = [flags for content, flags in calls if content is not DiscoveryContent.UNKNOWN]
    assert catch_calls, "premise: the catch did not call takeover.remove_replay_twins with the content of the topic"
    assert any(catch_calls[0]), "premise: no replayed row was loaded and enabled when the catch removed it"
    for button in buttons:
        assert entity_registry.async_get(button) is None, EAGER_TASK_HINT
    kept = entity_registry.async_get(switch)
    assert kept is not None, "the integration-disabled switch twin left the registry on LEGACY content (09.2 D-05)"
    assert kept.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert topic_publishes(mqtt_mock, topic) == [], EAGER_TASK_HINT
