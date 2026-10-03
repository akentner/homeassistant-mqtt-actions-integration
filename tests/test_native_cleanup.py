"""Healing, the discovery issue and the test topic belong to the legacy path; native devices delete cleanly (MIG-03)."""

import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.components import mqtt
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import (
    CONF_DELETE_DEVICES_ON_REMOVE,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_EXPORT,
    CONF_EXPORT_PREFIX,
    DEFAULT_EXPORT_PREFIX,
    DOMAIN,
    ISSUE_DISCOVERY_DISABLED,
    ISSUE_DISCOVERY_REMOVED_PREFIX,
    STORE_KEY,
    STORE_PUBLISHED,
    STORE_VERSION,
)
from custom_components.mqtt_actions.sync import SyncManager
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.test_native_start import (
    _block_discovery_delivery,
    _legacy_mirror,
    _loop_back_discovery,
    _store_the_mirror_as_native,
)
from tests.test_takeover import MIGRATE_PAYLOAD, PREFIX

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on"}]
OFF_ACTIONS = [{"action": "test.off"}]
EXPORT_ON = {CONF_DISCOVERY_EXPORT: True}
ORPHAN_ID = "5d9c1b0e-7c55-4c1e-8a11-0f7c3a9b2d44"
CLEARED = ("", 1, True)


def _seed(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {"version": STORE_VERSION, "minor_version": 1, "key": STORE_KEY, "data": data}


def _seed_native(
    hass_storage: dict[str, Any],
    *,
    instance: bool = True,
    devices: list[str] | None = None,
    pending: list[str] | None = None,
) -> None:
    _seed(hass_storage, {"native": {"instance": instance, "pending": pending or [], "devices": devices or []}})


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _core(device_id: str) -> str:
    return discovery_topic(PREFIX, device_id)


def _export(device_id: str) -> str:
    return discovery_topic(DEFAULT_EXPORT_PREFIX, device_id)


async def _remove_elsewhere(hass: HomeAssistant, device_id: str) -> None:
    """Deliver the empty live discovery payload core MQTT publishes when an entity of the device is deleted."""
    async_fire_mqtt_message(hass, _core(device_id), "", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


def _issues(hass: HomeAssistant, prefix: str) -> list[str]:
    return sorted(
        issue_id for domain, issue_id in ir.async_get(hass).issues if domain == DOMAIN and issue_id.startswith(prefix)
    )


# --- healing and the removal count apply to the legacy path only ---------------------------------------------------


async def test_a_native_owner_never_heals_its_discovery(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """MIG-03: an empty discovery payload is neither healed nor counted for a native device; a legacy one still is."""
    native = make_switch_subentry("Native lamp", device_id=str(uuid.uuid4()))
    legacy = make_switch_subentry("Legacy lamp", device_id=str(uuid.uuid4()))
    native_id, legacy_id = _device_id(native), _device_id(legacy)
    _seed_native(hass_storage, instance=False, devices=[native_id])
    entry = await _setup(hass, make_hub_entry([native, legacy], options=EXPORT_ON))
    assert _manager(entry).is_native(native_id) is True
    assert _manager(entry).is_native(legacy_id) is False
    mqtt_mock.async_publish.reset_mock()

    for _ in range(3):
        await _remove_elsewhere(hass, native_id)
    assert mqtt_mock.async_publish.call_args_list == []
    assert _issues(hass, ISSUE_DISCOVERY_REMOVED_PREFIX) == []

    for _ in range(3):
        await _remove_elsewhere(hass, legacy_id)
    ((payload, qos, retain), *_rest) = _publishes(mqtt_mock, _core(legacy_id))
    assert payload != ""
    assert (qos, retain) == (1, True)
    assert _issues(hass, ISSUE_DISCOVERY_REMOVED_PREFIX) == [f"{ISSUE_DISCOVERY_REMOVED_PREFIX}{legacy_id}"]
    # The export of the native device is not healed either, and nothing on the export prefix was published again
    assert _publishes(mqtt_mock, _export(native_id)) == []


async def test_the_takeover_clear_is_not_a_foreign_removal(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """MIG-03: the owner's own retained clear during the pass reaches its subscription and is not counted."""
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)
    _seed_native(hass_storage, pending=[device_id])
    _loop_back_discovery(hass, mqtt_mock)
    heard: list[str] = []
    real = SyncManager._on_discovery_message

    def _spy(self: SyncManager, msg: Any) -> None:
        heard.append(msg.topic)
        real(self, msg)

    with (
        patch.object(SyncManager, "_on_discovery_message", _spy),
        patch.object(SyncManager, "_note_removal") as note_removal,
    ):
        entry = await _setup(hass, make_hub_entry([subentry]))

    assert _core(device_id) in heard
    note_removal.assert_not_called()
    assert _issues(hass, ISSUE_DISCOVERY_REMOVED_PREFIX) == []
    assert _manager(entry).is_native(device_id) is True
    assert _manager(entry).heals_discovery(device_id) is False


# --- the discovery-disabled issue ----------------------------------------------------------------------------------

DISCOVERY_OFF = {mqtt.CONF_BIRTH_MESSAGE: {}, mqtt.CONF_DISCOVERY: False}


@pytest.mark.parametrize("mqtt_config_entry_options", [DISCOVERY_OFF])
@pytest.mark.parametrize(
    ("native", "options", "expected"),
    [
        pytest.param(True, {}, False, id="fully-native"),
        pytest.param(False, {}, True, id="legacy"),
        pytest.param(True, {CONF_DISCOVERY_EXPORT: True, CONF_EXPORT_PREFIX: PREFIX}, True, id="export-on-core-prefix"),
        pytest.param(True, {CONF_DISCOVERY_EXPORT: True}, False, id="export-on-own-prefix"),
    ],
)
async def test_the_discovery_disabled_issue_is_needed_only_for_the_legacy_path(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    native: bool,
    options: dict[str, Any],
    expected: bool,
) -> None:
    """With MQTT discovery disabled only a legacy device, or an export on the core prefix, still needs it."""
    if native:
        _seed_native(hass_storage)
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")], options=options))

    assert (ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_DISCOVERY_DISABLED) is not None) is expected


@pytest.mark.parametrize("mqtt_config_entry_options", [DISCOVERY_OFF])
async def test_the_discovery_issue_follows_a_deferred_device_and_the_export_option(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A device whose takeover was deferred is legacy for this run, so the issue is raised after the pass."""
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)
    _seed_native(hass_storage, pending=[device_id])
    monkeypatch.setattr(takeover, "async_take_over", _deferred)
    monkeypatch.setattr(takeover, "legacy_device", lambda *_args: object())

    entry = await _setup(hass, make_hub_entry([subentry]))

    assert _manager(entry).is_native(device_id) is False
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_DISCOVERY_DISABLED) is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {CONF_DISCOVERY_EXPORT: True})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_DISCOVERY_DISABLED) is not None


async def _deferred(*_args: Any, **_kwargs: Any) -> takeover.TakeoverStatus:
    return takeover.TakeoverStatus.DEFERRED


# --- the test topic ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("migrated", "expected_native"),
    [pytest.param(True, True, id="native"), pytest.param(False, False, id="deferred")],
)
async def test_a_native_mirror_subscribes_no_test_topic_but_a_deferred_one_does(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
    *,
    migrated: bool,
    expected_native: bool,
) -> None:
    """MIG-03: a native mirror has a test button that runs the trigger here; one kept legacy needs the topic."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    entry, topic = await _legacy_mirror(hass, make_hub_entry, spec)
    if migrated:
        # The owner upgraded: its migrate payload unloaded the discovered entities, so the takeover can move them
        async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _store_the_mirror_as_native(hass_storage, spec)
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)
    if not migrated:
        # A broker that has not delivered the migrate payload: the legacy entities stay loaded and the mirror waits
        monkeypatch.setattr(takeover, "TAKEOVER_UNLOAD_TIMEOUT", 0.05)
        _block_discovery_delivery(monkeypatch)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    mirror = _manager(entry).mirrors[spec.device_id]
    assert _manager(entry).is_native(spec.device_id) is expected_native
    assert mirror.unsubscribe is not None
    assert (mirror.unsubscribe_test is None) is expected_native


# --- the native delete lifecycle -----------------------------------------------------------------------------------


def _remaining(hass: HomeAssistant, entry: MockConfigEntry, device_id: str) -> tuple[list[str], list[str]]:
    """Return the entity ids of the entry that belong to a device, and its companion device ids still registered."""
    entities = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if entity.unique_id == device_id or entity.unique_id.startswith(f"{device_id}_")
    ]
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)
    return entities, [] if device is None else [device.id]


async def test_deleting_a_native_device_clears_everything_and_removes_its_entities(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-10, MIG-03: tombstone, retained state, legacy topic and export go; the registries lose device and entities."""
    subentry = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    device_id = _device_id(subentry)
    _seed_native(hass_storage)
    entry = await _setup(hass, make_hub_entry([subentry], options=EXPORT_ON))
    entities, devices = _remaining(hass, entry, device_id)
    assert entities
    assert devices
    assert _publishes(mqtt_mock, _export(device_id))[-1][0] != ""
    (subentry_id,) = entry.subentries

    assert hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _publishes(mqtt_mock, config_topic(BASE, device_id))[-1] == CLEARED
    assert _publishes(mqtt_mock, state_topic(BASE, device_id))[-1] == CLEARED
    assert _publishes(mqtt_mock, _core(device_id))[-1] == CLEARED
    assert _publishes(mqtt_mock, _export(device_id))[-1] == CLEARED
    assert _remaining(hass, entry, device_id) == ([], [])
    assert device_id not in _manager(entry).devices


async def test_deleting_a_native_mirror_removes_its_device_and_entities(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The tombstone of the owner removes the companion device and every native entity of a native mirror."""
    spec = make_spec(name="Foreign lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    async_fire_mqtt_message(hass, availability_topic(BASE, FOREIGN_OWNER), "online", retain=True)
    async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), document_payload(spec, native=True), retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    entities, devices = _remaining(hass, entry, spec.device_id)
    assert entities
    assert devices

    async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), "", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _remaining(hass, entry, spec.device_id) == ([], [])
    assert spec.device_id not in _manager(entry).mirrors


async def test_hub_removal_clears_the_export_topics_too(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """The delete-everywhere removal clears the export topic of each owned device and of a leftover id."""
    subentry = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(subentry)
    _seed(hass_storage, {STORE_PUBLISHED: [ORPHAN_ID], "native": {"instance": True, "pending": [], "devices": []}})
    entry = await _setup(
        hass, make_hub_entry([subentry], options={CONF_DELETE_DEVICES_ON_REMOVE: True, CONF_DISCOVERY_EXPORT: True})
    )

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for owned_id in (device_id, ORPHAN_ID):
        assert _publishes(mqtt_mock, _export(owned_id))[-1] == CLEARED
        assert _publishes(mqtt_mock, _core(owned_id))[-1] == CLEARED
        assert _publishes(mqtt_mock, config_topic(BASE, owned_id))[-1] == CLEARED
        assert _publishes(mqtt_mock, state_topic(BASE, owned_id))[-1] == CLEARED


async def test_the_orphan_cleanup_clears_the_export_topic_too(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
) -> None:
    """A device deleted while the entry was not loaded also loses its export topic at the next start."""
    _seed(hass_storage, {STORE_PUBLISHED: [ORPHAN_ID], "native": {"instance": True, "pending": [], "devices": []}})

    await _setup(hass, make_hub_entry(options=EXPORT_ON))

    assert _publishes(mqtt_mock, _export(ORPHAN_ID)) == [CLEARED]
    assert _publishes(mqtt_mock, config_topic(BASE, ORPHAN_ID)) == [CLEARED]
