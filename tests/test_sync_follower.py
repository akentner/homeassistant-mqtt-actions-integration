"""Follower side of the central config: foreign documents become read-only mirrors that run nothing (D-06, D-08)."""

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_MIRRORS,
    STORE_VERSION,
)
from custom_components.mqtt_actions.document import build_content, canonical_json
from custom_components.mqtt_actions.topics import config_topic, discovery_topic, state_topic
from custom_components.mqtt_actions.topics import test_topic as device_test_topic
from tests.documents import FOREIGN_OWNER, FOREIGN_OWNER_NAME, document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Device, Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on", "target": {"entity_id": "light.lamp"}}]
OFF_ACTIONS = [{"action": "test.off"}]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


def _mirror(entry: MockConfigEntry, device_id: str) -> Device:
    return _manager(entry).mirrors[device_id]


async def _deliver(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = True) -> None:
    """Deliver one document to the config topic of a device and let the ingest finish."""
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _seed_store(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {"version": STORE_VERSION, "minor_version": 1, "key": STORE_KEY, "data": data}


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _mirror_topics(device_id: str) -> list[str]:
    return [config_topic(BASE, device_id), discovery_topic("homeassistant", device_id), state_topic(BASE, device_id)]


def _own_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the records of this integration; core MQTT logs received payloads at debug level on its own logger."""
    return [record for record in caplog.records if record.name.startswith("custom_components.mqtt_actions")]


# --- creation and inertness (SYN-02, TRU-01) --------------------------------------------------------------------


async def test_retained_document_creates_a_read_only_mirror(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A foreign document becomes a mirror: not a device, not a subentry, with the owner and both hashes recorded."""
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS, name="Foreign lamp")
    entry = await _setup(hass, make_hub_entry())
    payload = document_payload(spec, rev=3)

    await _deliver(hass, spec.device_id, payload)

    manager = _manager(entry)
    mirror = _mirror(entry, spec.device_id)
    assert mirror.spec == spec
    assert mirror.mirror is not None
    assert mirror.mirror.owner == FOREIGN_OWNER
    assert mirror.mirror.owner_name == FOREIGN_OWNER_NAME
    assert mirror.mirror.rev == 3
    assert mirror.mirror.content_hash
    assert mirror.mirror.actions_hash
    assert mirror.mirror.payload == payload
    assert spec.device_id not in manager.devices
    assert not entry.subentries


async def test_mirror_never_publishes_anything_for_the_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-19: discovery, config and state of a mirrored device stay the owner's; the follower publishes none of them."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    mqtt_mock.async_publish.reset_mock()

    await _deliver(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "ON", retain=True)
    await _state(hass, spec.device_id, "OFF", retain=False)

    assert spec.device_id in _manager(entry).mirrors
    for topic in _mirror_topics(spec.device_id):
        assert _publishes(mqtt_mock, topic) == []


async def test_mirror_tracks_the_baseline_and_runs_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """TRU-01: an unapproved mirror follows the state and never runs an action, not even through the test topic."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    mirror = _mirror(entry, spec.device_id)

    await _state(hass, spec.device_id, "OFF", retain=True)
    assert mirror.tracker.last_acted == "OFF"
    await _state(hass, spec.device_id, "ON", retain=False)
    assert mirror.tracker.last_acted == "ON"
    async_fire_mqtt_message(hass, device_test_topic(BASE, spec.device_id), "OFF", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert on_calls == []
    assert off_calls == []
    assert _manager(entry).runner.script_count(spec.device_id) == 0


async def test_mirror_subscribes_to_state_and_test_topics(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The mirror subscribes from creation, so the retained state sets its baseline before anything could run."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())

    await _deliver(hass, spec.device_id, document_payload(spec))

    mirror = _mirror(entry, spec.device_id)
    assert callable(mirror.unsubscribe)
    assert callable(mirror.unsubscribe_test)


# --- persistence (D-08) -----------------------------------------------------------------------------------------


async def test_mirror_is_stored_and_restored_at_start(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """A mirror survives a restart before the broker replays anything, with its baseline, and still runs nothing."""
    on_calls = async_mock_service(hass, "test", "on")
    spec = make_spec(on=ON_ACTIONS, run_on_startup=True)
    payload = document_payload(spec)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, payload)
    await _state(hass, spec.device_id, "ON", retain=True)

    assert await hass.config_entries.async_unload(entry.entry_id)
    data = hass_storage[STORE_KEY]["data"]
    assert data[STORE_MIRRORS] == {spec.device_id: payload}
    assert data[STORE_LAST_ACTED][spec.device_id] == "ON"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    manager = _manager(entry)
    mirror = manager.mirrors[spec.device_id]
    assert mirror.tracker.last_acted == "ON"
    assert mirror.tracker.startup_pending is True
    assert callable(mirror.unsubscribe)
    assert callable(mirror.unsubscribe_test)

    # The run-on-startup window of a restored mirror opens, and still nothing runs
    await _state(hass, spec.device_id, "ON", retain=True)
    assert on_calls == []

    await _deliver(hass, spec.device_id, payload)
    assert manager.mirrors[spec.device_id] is mirror
    assert len(manager.mirrors) == 1


@pytest.mark.parametrize(
    "make_mirrors",
    [
        lambda _device_id: "text",
        lambda _device_id: ["a", "b"],
        lambda device_id: {device_id: 5},
        lambda device_id: {device_id: ["not", "text"]},
        lambda device_id: {device_id: "{not json"},
        lambda device_id: {device_id: document_payload(make_spec(device_id="another-id"))},
        lambda device_id: {
            device_id: document_payload(make_spec(device_id=device_id, on=[{"not_a_step": "x"}])),
        },
    ],
    ids=["string", "list", "int-payload", "list-payload", "not-json", "id-mismatch", "invalid-actions"],
)
async def test_malformed_mirrors_store_is_dropped(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_mirrors: Callable[[str], Any],
) -> None:
    """T-03-19: a cached payload is parsed and structure-checked again; damage never fails the setup."""
    device_id = "device-under-test"
    _seed_store(hass_storage, {STORE_MIRRORS: make_mirrors(device_id)})

    entry = await _setup(hass, make_hub_entry())

    assert _manager(entry).mirrors == {}


async def test_stored_mirror_of_an_owned_id_is_dropped(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A cached mirror whose id is owned locally is dropped, and the owned device keeps working."""
    on_calls = async_mock_service(hass, "test", "on")
    sub: ConfigSubentryData = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    _seed_store(hass_storage, {STORE_MIRRORS: {device_id: document_payload(make_spec(device_id=device_id))}})

    entry = await _setup(hass, make_hub_entry([sub]))
    manager = _manager(entry)
    await _state(hass, device_id, "ON", retain=False)

    assert manager.mirrors == {}
    assert device_id in manager.devices
    assert len(on_calls) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_MIRRORS] == {}


async def test_reconcile_keeps_mirrors_and_publishes_nothing_for_them(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A reconcile of owned subentries and a restart never remove a mirror or clear its topics on the broker."""
    sub: ConfigSubentryData = make_switch_subentry("Lamp", on=ON_ACTIONS)
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    await _deliver(hass, spec.device_id, document_payload(spec))
    mqtt_mock.async_publish.reset_mock()

    hass.config_entries.async_update_subentry(entry, next(iter(entry.subentries.values())), title="Lamp 2")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert spec.device_id in _manager(entry).mirrors
    assert spec.device_id not in _manager(entry)._published
    for topic in _mirror_topics(spec.device_id):
        assert _publishes(mqtt_mock, topic) == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    mqtt_mock.async_publish.reset_mock()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert spec.device_id in _manager(entry).mirrors
    assert spec.device_id not in _manager(entry)._published
    for topic in _mirror_topics(spec.device_id):
        assert _publishes(mqtt_mock, topic) == []


async def test_unload_releases_mirror_subscriptions(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """After an unload no mirror is left, both subscriptions were released and a state message is harmless."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    mirror = _mirror(entry, spec.device_id)
    state_release, test_release = mirror.unsubscribe, mirror.unsubscribe_test
    mirror.unsubscribe = Mock(side_effect=state_release)
    mirror.unsubscribe_test = Mock(side_effect=test_release)

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert _manager(entry).mirrors == {}
    mirror.unsubscribe.assert_called_once()
    mirror.unsubscribe_test.assert_called_once()
    await _state(hass, spec.device_id, "ON", retain=False)
    assert mirror.tracker.last_acted is None


# --- ingest boundaries ------------------------------------------------------------------------------------------


async def test_own_document_for_an_unknown_device_is_ignored(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A document of this very instance for an id with no local device creates nothing."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())

    await _deliver(hass, spec.device_id, document_payload(spec, owner=entry.data[CONF_INSTANCE_ID]))

    assert _manager(entry).mirrors == {}
    assert _manager(entry).devices == {}


async def test_mirror_count_is_capped(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, caplog: pytest.LogCaptureFixture
) -> None:
    """T-03-16: beyond MAX_MIRRORS a new device creates no mirror, and the overflow is logged once."""
    entry = await _setup(hass, make_hub_entry())
    specs = [make_spec(name=f"Device {index}", on=ON_ACTIONS) for index in range(4)]

    with patch("custom_components.mqtt_actions.sync.MAX_MIRRORS", 2), caplog.at_level(logging.DEBUG):
        for spec in specs:
            await _deliver(hass, spec.device_id, document_payload(spec))

    assert set(_manager(entry).mirrors) == {specs[0].device_id, specs[1].device_id}
    warnings = [record for record in _own_records(caplog) if record.levelno == logging.WARNING]
    assert len(warnings) == 1


async def test_mirror_carries_the_documents_settings(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Run mode, startup flag and breaker limits follow the document; the signature is the canonical content."""
    spec = make_spec(on=ON_ACTIONS, run_on_startup=True, run_mode="restart", breaker_max_runs=3, breaker_window=7)
    entry = await _setup(hass, make_hub_entry())

    await _deliver(hass, spec.device_id, document_payload(spec))

    mirror = _mirror(entry, spec.device_id)
    assert mirror.spec.run_mode == "restart"
    assert mirror.spec.run_on_startup is True
    assert mirror.tracker.run_on_startup is True
    assert mirror.tracker.startup_pending is False
    assert (mirror.breaker.max_runs, mirror.breaker.window) == (3, 7.0)
    assert mirror.signature == canonical_json(build_content(spec))


async def test_static_analysis_is_recorded_on_the_mirror(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A6: a denied and a templated service name do not drop the document, they are recorded for the approval."""
    spec = make_spec(on=[{"action": "shell_command.run"}, {"action": "{{ 'light.turn_on' }}"}])
    entry = await _setup(hass, make_hub_entry())

    await _deliver(hass, spec.device_id, document_payload(spec))

    info = _mirror(entry, spec.device_id).mirror
    assert info is not None
    assert info.denied == ("shell_command.run",)
    assert info.templated == ("{{ 'light.turn_on' }}",)
    assert info.residual == ()
