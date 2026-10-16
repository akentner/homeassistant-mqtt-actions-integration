"""The duplicate guard on an instance that only receives an export (UAT-04 clause 2, UAT04-RECEIVER-GUARD, D-08)."""

import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import discovery, takeover
from custom_components.mqtt_actions.const import CONF_DISCOVERY_EXPORT, DOMAIN, SUBENTRY_SELECT
from custom_components.mqtt_actions.topics import discovery_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.helpers import (
    BASE,
    CORE_PREFIX,
    announce_presence,
    create_mqtt_row,
    deliver_config,
    legacy_mirror,
    manager_of,
    mqtt_device_of,
    native_entity_id,
    quiet_period_passes,
    restart_entry,
    setup_entry,
    topic_publishes_with_qos,
)
from tests.log_helpers import OWN_LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.model import DeviceSpec

FOREIGN_SW_VERSION = "0.1.0"


async def _native_mirror(hass: HomeAssistant, make_hub_entry: Callable, spec: DeviceSpec) -> MockConfigEntry:
    """Set up a hub entry with default options and deliver the marked document of a foreign owner that is online."""
    entry = await setup_entry(hass, make_hub_entry())
    await announce_presence(hass, "online")
    await deliver_config(hass, spec.device_id, document_payload(spec, native=True))
    return entry


def _foreign_export(spec: DeviceSpec) -> tuple[str, str]:
    """Return the core-prefix topic and the payload of the export another instance publishes for the device."""
    payload = discovery.build_export(
        spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version=FOREIGN_SW_VERSION
    )
    return discovery_topic(CORE_PREFIX, spec.device_id), json.dumps(payload)


async def _receive_foreign_export(hass: HomeAssistant, spec: DeviceSpec) -> None:
    """Hand the retained export of another instance to core MQTT, as a broker would on subscribe."""
    topic, payload = _foreign_export(spec)
    async_fire_mqtt_message(hass, topic, payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _enabled_rows(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return the entity ids of every enabled registry row with this unique id, whatever the platform."""
    return [
        entity.entity_id
        for entity in er.async_get(hass).entities.values()
        if entity.unique_id == device_id and entity.disabled_by is None
    ]


async def test_a_receiver_disables_the_duplicate_that_a_foreign_core_prefix_export_restores(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
) -> None:
    """
    The bench receiver of the 08-13 re-run: the export is off here, the device is a native mirror, a null tombstone.

    Another instance exports the device on the prefix core MQTT listens to. Core restores the enabled state of the
    removed row, and this instance, which does not export, must still end with one disabled duplicate (D-08 amended).
    """
    spec = make_spec(name="Foreign lamp")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)

    # Premises: no export here, a native mirror with its native row, the core MQTT device and a null tombstone
    assert not entry.options.get(CONF_DISCOVERY_EXPORT)
    assert manager_of(entry).is_native(spec.device_id)
    native = native_entity_id(hass, "switch", spec.device_id)
    assert native is not None
    # One synchronous step without an await: an enabled row on the MQTT device of the id is created and removed
    registry.async_remove(create_mqtt_row(hass, "switch", spec.device_id, device=True))
    assert registry.deleted_entities[("switch", "mqtt", spec.device_id)].disabled_by is None
    assert registry.async_get_entity_id("switch", "mqtt", spec.device_id) is None
    assert mqtt_device_of(hass, spec.device_id) is not None
    published = list(mqtt_mock.async_publish.call_args_list)

    await _receive_foreign_export(hass, spec)

    duplicates = [
        entity
        for entity in registry.entities.values()
        if entity.unique_id == spec.device_id and entity.platform == "mqtt"
    ]
    assert len(duplicates) == 1
    assert duplicates[0].disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get(native).disabled_by is None
    assert _enabled_rows(hass, spec.device_id) == [native]
    assert topic_publishes_with_qos(mqtt_mock, discovery_topic(CORE_PREFIX, spec.device_id)) == []
    assert list(mqtt_mock.async_publish.call_args_list) == published


def _mqtt_rows(hass: HomeAssistant, device_id: str) -> list[er.RegistryEntry]:
    """Return every registry row of core MQTT with this unique id."""
    return [
        entity
        for entity in er.async_get(hass).entities.values()
        if entity.unique_id == device_id and entity.platform == "mqtt"
    ]


def _core_creates_the_row(hass: HomeAssistant, domain: str, device_id: str) -> er.RegistryEntry:
    """
    Create the row the way core MQTT does when a discovery payload meets an earlier deleted row, and return it.

    Core leaves the disabled state to the registry: the record of a deleted row with the same platform and unique id
    decides. A second live delivery of an identical payload creates nothing in this harness, so the call is direct.
    """
    mqtt_entry = hass.config_entries.async_entries("mqtt")[0]
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", f"{DOMAIN}_{device_id}")}
    )
    return er.async_get(hass).async_get_or_create(
        domain, "mqtt", device_id, config_entry=mqtt_entry, device_id=device.id
    )


def _count_disables(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the entity id of every registry update that sets a disabled state, and let the update through."""
    calls: list[str] = []
    real = er.EntityRegistry.async_update_entity

    def _wrapper(self: er.EntityRegistry, entity_id: str, **changes: Any) -> er.RegistryEntry:
        if "disabled_by" in changes:
            calls.append(entity_id)
        return real(self, entity_id, **changes)

    monkeypatch.setattr(er.EntityRegistry, "async_update_entity", _wrapper)
    return calls


def _spy_disable_duplicates(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Record the device id and the result of every guard pass over a device, and let the pass through."""
    calls: list[tuple[str, int]] = []
    real = takeover.disable_duplicates

    def _wrapper(hass: HomeAssistant, entry_id: str, device_id: str, *, mqtt_entry_id: str) -> int:
        result = real(hass, entry_id, device_id, mqtt_entry_id=mqtt_entry_id)
        calls.append((device_id, result))
        return result

    monkeypatch.setattr(takeover, "disable_duplicates", _wrapper)
    return calls


# --- the twin interlock, the ordering and the log line (E1 to E3) ----------------------------------------------------


async def test_a_row_without_a_native_twin_is_no_duplicate_and_stays_enabled(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """E1, T-08-48: a row is a duplicate only next to a native entity of the same domain and unique id."""
    spec = make_spec(name="Foreign lamp")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)
    assert manager_of(entry).is_native(spec.device_id)
    native = native_entity_id(hass, "switch", spec.device_id)
    assert native is not None
    registry.async_remove(native)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert native_entity_id(hass, "switch", spec.device_id) is None

    row = create_mqtt_row(hass, "switch", spec.device_id, device=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert registry.async_get(row).disabled_by is None


async def test_a_duplicate_that_exists_before_the_device_is_held_is_disabled_when_the_native_entity_appears(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """E2, R-3: the order does not matter; the native twin that appears later is a trigger as well."""
    spec = make_spec(name="Foreign lamp")
    entry = await setup_entry(hass, make_hub_entry())
    await announce_presence(hass, "online")
    registry = er.async_get(hass)
    row = create_mqtt_row(hass, "switch", spec.device_id, device=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not manager_of(entry).is_native(spec.device_id)
    assert native_entity_id(hass, "switch", spec.device_id) is None
    assert registry.async_get(row).disabled_by is None

    await deliver_config(hass, spec.device_id, document_payload(spec, native=True))

    native = native_entity_id(hass, "switch", spec.device_id)
    assert native is not None
    assert registry.async_get(row).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get(native).disabled_by is None


class _Lines(logging.Handler):
    """Collect the log records of the integration's own logger, which works without the pytest logging plugin."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def duplicate_lines(self) -> list[logging.LogRecord]:
        """Return the INFO records that report disabled duplicates."""
        return [
            record
            for record in self.records
            if record.levelno == logging.INFO
            and record.getMessage().startswith("Disabled")
            and "duplicate" in record.getMessage()
        ]


async def test_a_pass_that_disables_something_logs_one_line_with_a_count_and_nothing_else(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """E3, R-5, T-08-52: the line holds a count only, no id, name, payload or entity id; a pass of nothing is silent."""
    spec = make_spec(name="Foreign lamp")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    lines = _Lines()
    logger = logging.getLogger(OWN_LOGGER)
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(lines)
    try:
        row = create_mqtt_row(hass, "switch", spec.device_id, device=True)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert er.async_get(hass).async_get(row).disabled_by is er.RegistryEntryDisabler.INTEGRATION
        found = lines.duplicate_lines()
        assert len(found) == 1
        line = found[0]
        assert line.args == (1,)
        for secret in (spec.device_id, "Foreign lamp", row, "switch.foreign_lamp", FOREIGN_OWNER):
            assert secret not in line.getMessage()

        lines.records.clear()
        await restart_entry(hass, entry)
        assert lines.duplicate_lines() == []
    finally:
        logger.removeHandler(lines)
        logger.setLevel(previous_level)


# --- guard rails that must hold from the first fix on (G1 to G6) ----------------------------------------------------


async def test_a_receiver_disables_the_duplicate_of_a_select_device_as_well(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """G1: the tracer for a select device."""
    spec = make_spec(SUBENTRY_SELECT, name="Foreign mode")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)
    assert not entry.options.get(CONF_DISCOVERY_EXPORT)
    native = native_entity_id(hass, "select", spec.device_id)
    assert native is not None
    registry.async_remove(create_mqtt_row(hass, "select", spec.device_id, device=True))
    assert registry.deleted_entities[("select", "mqtt", spec.device_id)].disabled_by is None

    await _receive_foreign_export(hass, spec)

    (duplicate,) = _mqtt_rows(hass, spec.device_id)
    assert duplicate.domain == "select"
    assert duplicate.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert _enabled_rows(hass, spec.device_id) == [native]


async def test_the_rows_of_a_legacy_mirror_are_left_alone(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """G3, T-08-48: an unmarked mirror runs on its core MQTT entities, which are live entities and no duplicates."""
    spec = make_spec(name="Foreign lamp")
    entry, _topic = await legacy_mirror(hass, make_hub_entry, spec)
    assert not manager_of(entry).is_native(spec.device_id)
    registry = er.async_get(hass)
    before = {row.entity_id: row.disabled_by for row in _mqtt_rows_of_the_device(hass, spec.device_id)}
    assert before
    assert before[registry.async_get_entity_id("switch", "mqtt", spec.device_id)] is None

    await hass.async_block_till_done(wait_background_tasks=True)

    after = {row.entity_id: row.disabled_by for row in _mqtt_rows_of_the_device(hass, spec.device_id)}
    assert after == before


def _mqtt_rows_of_the_device(hass: HomeAssistant, device_id: str) -> list[er.RegistryEntry]:
    """Return every registry row on the core MQTT device of a device id."""
    device = mqtt_device_of(hass, device_id)
    assert device is not None
    return er.async_entries_for_device(er.async_get(hass), device.id, include_disabled_entities=True)


async def test_a_row_the_user_disabled_keeps_its_state(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """G3: a disabled state that is not None is never changed, `user` least of all."""
    spec = make_spec(name="Foreign lamp")
    await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)
    mqtt_entry = hass.config_entries.async_entries("mqtt")[0]
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", f"{DOMAIN}_{spec.device_id}")}
    )

    row = registry.async_get_or_create(
        "switch",
        "mqtt",
        spec.device_id,
        config_entry=mqtt_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert row.disabled_by is er.RegistryEntryDisabler.USER
    assert registry.async_get(row.entity_id).disabled_by is er.RegistryEntryDisabler.USER


async def test_a_row_on_another_mqtt_device_is_left_alone(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """G3, T-08-48: the unique id alone never decides; the row must sit on the core MQTT device of the id."""
    spec = make_spec(name="Foreign lamp")
    await _native_mirror(hass, make_hub_entry, spec)
    mqtt_entry = hass.config_entries.async_entries("mqtt")[0]
    device_registry = dr.async_get(hass)
    own = device_registry.async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", f"{DOMAIN}_{spec.device_id}")}
    )
    other = device_registry.async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", "someone-elses-device")}
    )
    assert own.id != other.id

    row = er.async_get(hass).async_get_or_create(
        "switch", "mqtt", spec.device_id, config_entry=mqtt_entry, device_id=other.id
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert er.async_get(hass).async_get(row.entity_id).disabled_by is None


async def test_a_test_button_row_is_left_alone(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """G3: only the switch or select of the id is a duplicate; a test button of the legacy discovery is not."""
    spec = make_spec(name="Foreign lamp")
    await _native_mirror(hass, make_hub_entry, spec)
    mqtt_entry = hass.config_entries.async_entries("mqtt")[0]
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", f"{DOMAIN}_{spec.device_id}")}
    )

    button = er.async_get(hass).async_get_or_create(
        "button", "mqtt", f"{spec.device_id}_test_on", config_entry=mqtt_entry, device_id=device.id
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert button.disabled_by is None
    assert er.async_get(hass).async_get(button.entity_id).disabled_by is None


async def test_the_native_rows_are_never_touched(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """G3: every row of this integration keeps its state while the guard disables the duplicate."""
    spec = make_spec(name="Foreign lamp")
    await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)
    native_before = {row.entity_id: row.disabled_by for row in registry.entities.values() if row.platform == DOMAIN}
    assert native_before

    row = create_mqtt_row(hass, "switch", spec.device_id, device=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert registry.async_get(row).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    native_after = {row.entity_id: row.disabled_by for row in registry.entities.values() if row.platform == DOMAIN}
    assert native_after == native_before


async def test_an_id_this_instance_holds_nothing_for_is_left_alone_even_when_a_foreign_export_arrives(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """G3, T-08-49: the guard serves the devices this instance holds natively and nothing a broker publisher names."""
    held = make_spec(name="Held lamp")
    stranger = make_spec(name="Stranger")
    entry = await _native_mirror(hass, make_hub_entry, held)
    registry = er.async_get(hass)
    assert stranger.device_id not in manager_of(entry).mirrors
    registry.async_remove(create_mqtt_row(hass, "switch", stranger.device_id, device=True))

    await _receive_foreign_export(hass, stranger)

    (row,) = _mqtt_rows(hass, stranger.device_id)
    assert row.disabled_by is None


async def test_a_second_pass_a_second_create_event_and_a_restart_change_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    G4: once nothing is enabled, no pass performs a registry update.

    The row core creates again is born disabled from its record, so the registry alone keeps the old assertions true;
    the spy on `takeover.disable_duplicates` proves that the guard's listener ran and found nothing (review 1 IN-03).
    """
    spec = make_spec(name="Foreign lamp")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)
    registry.async_remove(create_mqtt_row(hass, "switch", spec.device_id, device=True))
    calls = _count_disables(monkeypatch)
    await _receive_foreign_export(hass, spec)
    (duplicate,) = _mqtt_rows(hass, spec.device_id)
    assert duplicate.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert calls == [duplicate.entity_id]

    # A second create event: the row goes, and core creates it again from a record that says integration
    registry.async_remove(duplicate.entity_id)
    passes = _spy_disable_duplicates(monkeypatch)
    again = _core_creates_the_row(hass, "switch", spec.device_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert again.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert calls == [duplicate.entity_id]
    assert passes == [(spec.device_id, 0)], "the guard's listener did not run for the second create event"

    # The sweep at the next start finds nothing enabled either
    await restart_entry(hass, entry)
    assert calls == [duplicate.entity_id]


async def test_on_a_fresh_install_core_disables_the_row_and_the_guard_does_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G5: without a tombstone the export asks for a disabled row and core creates one; there is nothing to correct."""
    spec = make_spec(name="Foreign lamp")
    await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)
    assert ("switch", "mqtt", spec.device_id) not in registry.deleted_entities
    calls = _count_disables(monkeypatch)

    await _receive_foreign_export(hass, spec)

    (duplicate,) = _mqtt_rows(hass, spec.device_id)
    assert duplicate.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert calls == []


async def test_the_export_off_cycle_removes_the_disabled_row_at_the_next_start(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    monkeypatch: pytest.MonkeyPatch,
    discovery_settled: None,
) -> None:
    """
    G6, user decision 2: a cleared export keeps the disabled row until the next start, which removes it.

    README and docs/troubleshooting.md promise it: when the export is switched off again, the disabled duplicates stay
    until Home Assistant is restarted, and the next start removes them. The topic settles empty, so the clear core may
    publish for the row wipes nothing (D-02). The replayed export row is newer than the native twin, so
    `_carries_the_identity` does not keep it. When the export comes back, core restores the row from its record as
    disabled.
    """
    spec = make_spec(name="Foreign lamp")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    registry = er.async_get(hass)
    registry.async_remove(create_mqtt_row(hass, "switch", spec.device_id, device=True))
    await _receive_foreign_export(hass, spec)
    (duplicate,) = _mqtt_rows(hass, spec.device_id)
    assert duplicate.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # The exporter switches the export off: the retained payload is cleared; the disabled row was never loaded
    topic, _payload = _foreign_export(spec)
    async_fire_mqtt_message(hass, topic, "", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [row.entity_id for row in _mqtt_rows(hass, spec.device_id)] == [duplicate.entity_id]

    # The next start finds the topic settled empty and removes the disabled row; nothing clears the topic
    published = len(mqtt_mock.async_publish.call_args_list)
    await restart_entry(hass, entry)
    await quiet_period_passes(hass)
    assert _mqtt_rows(hass, spec.device_id) == []
    clears = [call for call in mqtt_mock.async_publish.call_args_list[published:] if call.args[0] == topic]
    assert [call.args[1:4] for call in clears if not call.args[1]] == []

    # The export comes back: core finds the disabled row, and the guard has nothing to do
    calls = _count_disables(monkeypatch)
    back = _core_creates_the_row(hass, "switch", spec.device_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert back.entity_id == duplicate.entity_id
    assert back.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert calls == []


async def test_a_row_a_foreign_export_created_disabled_survives_the_restart_and_its_export_is_never_cleared(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, discovery_settled: None
) -> None:
    """
    CR-01: the export creates its row disabled, so core MQTT aborts the add and holds a hook for the row's removal.

    That hook publishes an empty retained payload on the core-prefix topic, the other instance's export, as soon as
    the row leaves the registry. The restart and the replay catch after its quiet period must leave the row alone.
    """
    spec = make_spec(name="Foreign lamp")
    entry = await _native_mirror(hass, make_hub_entry, spec)
    assert ("switch", "mqtt", spec.device_id) not in er.async_get(hass).deleted_entities
    await _receive_foreign_export(hass, spec)
    (row,) = _mqtt_rows(hass, spec.device_id)
    assert row.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    topic, _payload = _foreign_export(spec)
    published = len(mqtt_mock.async_publish.call_args_list)

    await restart_entry(hass, entry)
    # The broker hands the retained export to the new subscriptions (the mocked client keeps no retained store)
    await _receive_foreign_export(hass, spec)
    await quiet_period_passes(hass)

    clears = [call for call in mqtt_mock.async_publish.call_args_list[published:] if call.args[0] == topic]
    assert [call.args[1:4] for call in clears if not call.args[1]] == []
    assert [entity.entity_id for entity in _mqtt_rows(hass, spec.device_id)] == [row.entity_id]
    assert er.async_get(hass).async_get(row.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
