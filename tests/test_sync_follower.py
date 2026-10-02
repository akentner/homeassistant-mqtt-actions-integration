"""Follower side of the central config: foreign documents become read-only mirrors that run nothing (D-06, D-08)."""

import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, patch

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    DOMAIN,
    ISSUE_CIRCUIT_BREAKER_PREFIX,
    ISSUE_DEVICE_PREFIXES,
    ISSUE_OWNER_CONFLICT_PREFIX,
    ISSUE_SCHEMA_TOO_NEW_PREFIX,
    MAX_DOCUMENT_BYTES,
    MAX_SCHEMA_TOO_NEW_ISSUES,
    PRUNE_GRACE_SECONDS,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_MIRRORS,
    STORE_SAVE_DELAY,
    STORE_TRIPPED,
    STORE_VERSION,
    SUBENTRY_SELECT,
)
from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.document import build_content, canonical_json
from custom_components.mqtt_actions.model import SWITCH_ON_KEY
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from custom_components.mqtt_actions.topics import test_topic as device_test_topic
from tests.documents import FOREIGN_OWNER, FOREIGN_OWNER_NAME, document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Device, Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on", "target": {"entity_id": "light.lamp"}}]
OFF_ACTIONS = [{"action": "test.off"}]
OTHER_ACTIONS = [{"action": "test.other"}]
CANARY = "CANARY-7f3a91"


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


@pytest.mark.parametrize("device_id", ["x" * 65, "x" * 5000, "has space", "umlaut-\u00e4", "line\nbreak"])
async def test_document_with_an_invalid_device_id_creates_no_mirror(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, device_id: str
) -> None:
    """WR-05: an id outside 1-64 of letters, digits, underscore and dash never becomes a mirror, key or issue."""
    spec = make_spec(device_id=device_id, on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())

    await _deliver(hass, device_id, document_payload(spec))

    manager = _manager(entry)
    assert manager.mirrors == {}
    assert device_id not in manager._data_to_save()[STORE_MIRRORS]
    assert not [issue for domain, issue in ir.async_get(hass).issues if domain == DOMAIN and device_id in issue]


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
    manager = _manager(entry)
    await _deliver(hass, spec.device_id, document_payload(spec))
    mirror = _mirror(entry, spec.device_id)
    state_release, test_release = mirror.unsubscribe, mirror.unsubscribe_test
    mirror.unsubscribe = Mock(side_effect=state_release)
    mirror.unsubscribe_test = Mock(side_effect=test_release)

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert manager.mirrors == {}
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


# --- updates by content hash (D-15) -----------------------------------------------------------------------------


def _issue(hass: HomeAssistant, prefix: str, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{prefix}{device_id}")


def _issue_ids(hass: HomeAssistant, prefix: str) -> list[str]:
    return [
        issue_id for domain, issue_id in ir.async_get(hass).issues if domain == DOMAIN and issue_id.startswith(prefix)
    ]


async def test_changed_document_updates_the_mirror(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """A different content hash replaces spec, rev, hashes and payload; device, subscriptions and baseline stay."""
    spec = make_spec(on=ON_ACTIONS, name="Lamp")
    changed = make_spec(device_id=spec.device_id, on=OTHER_ACTIONS, name="Lamp 2")
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, rev=1), retain=False)
    await _state(hass, spec.device_id, "ON", retain=False)
    mirror = _mirror(entry, spec.device_id)
    subscriptions = (mirror.unsubscribe, mirror.unsubscribe_test)
    first_hash = mirror.mirror.content_hash

    payload = document_payload(changed, rev=2)
    await _deliver(hass, spec.device_id, payload, retain=False)

    assert _mirror(entry, spec.device_id) is mirror
    assert mirror.spec == changed
    assert mirror.spec.triggers[SWITCH_ON_KEY].actions == OTHER_ACTIONS
    assert mirror.mirror.rev == 2
    assert mirror.mirror.content_hash != first_hash
    assert mirror.mirror.payload == payload
    assert mirror.signature == canonical_json(build_content(changed))
    assert (mirror.unsubscribe, mirror.unsubscribe_test) == subscriptions
    assert mirror.tracker.last_acted == "ON"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_MIRRORS] == {spec.device_id: payload}


async def test_identical_hash_is_a_noop(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """The content hash decides: the same content with a higher rev replaces, saves and publishes nothing."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, rev=1), retain=False)
    mirror = _mirror(entry, spec.device_id)
    spec_before, info_before = mirror.spec, mirror.mirror
    _manager(entry)._schedule_save = Mock()
    mqtt_mock.async_publish.reset_mock()

    await _deliver(hass, spec.device_id, document_payload(spec, rev=5), retain=False)

    assert mirror.spec is spec_before
    assert mirror.mirror is info_before
    _manager(entry)._schedule_save.assert_not_called()
    assert mqtt_mock.async_publish.call_count == 0


async def test_lower_rev_with_different_content_is_applied(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """An owner that lost its Store restarts at rev 1; its changed document still updates the mirror."""
    spec = make_spec(on=ON_ACTIONS)
    changed = make_spec(device_id=spec.device_id, on=OTHER_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, rev=7), retain=False)

    await _deliver(hass, spec.device_id, document_payload(changed, rev=1), retain=False)

    mirror = _mirror(entry, spec.device_id)
    assert mirror.spec == changed
    assert mirror.mirror.rev == 1


async def test_update_releases_a_tripped_breaker_and_sanitizes_the_baseline(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """An applied change gives a fresh breaker without its issue; a baseline that is no option any more is unknown."""
    options = [("a", "A", []), ("b", "B", []), ("c", "C", [])]
    spec = make_spec(SUBENTRY_SELECT, options=options)
    changed = make_spec(SUBENTRY_SELECT, device_id=spec.device_id, options=options[:2])
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, rev=1), retain=False)
    await _state(hass, spec.device_id, "c", retain=False)
    manager = _manager(entry)
    mirror = _mirror(entry, spec.device_id)
    assert mirror.tracker.last_acted == "c"
    old_breaker = mirror.breaker
    old_breaker.trip()
    manager._create_breaker_issue(mirror)
    manager._tripped[spec.device_id] = "stale-hash"
    assert _issue(hass, ISSUE_CIRCUIT_BREAKER_PREFIX, spec.device_id) is not None

    await _deliver(hass, spec.device_id, document_payload(changed, rev=2), retain=False)

    assert mirror.breaker is not old_breaker
    assert mirror.breaker.tripped is False
    assert _issue(hass, ISSUE_CIRCUIT_BREAKER_PREFIX, spec.device_id) is None
    assert spec.device_id not in manager._tripped
    assert mirror.tracker.last_acted is None
    assert set(mirror.tracker.accepted.values()) == {"a", "b"}


# --- owner pinning (D-17) ---------------------------------------------------------------------------------------


async def test_pinned_owner_ignores_another_owner(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The first owner is pinned: a valid document of another owner changes nothing and raises one conflict issue."""
    spec = make_spec(on=ON_ACTIONS, name="Lamp_1")
    other = make_spec(device_id=spec.device_id, on=OTHER_ACTIONS, name="Hijacked")
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, owner="owner-a", owner_name="Al_pha"), retain=False)
    mirror = _mirror(entry, spec.device_id)
    spec_before, info_before = mirror.spec, mirror.mirror

    await _deliver(hass, spec.device_id, document_payload(other, owner="owner-b", owner_name="Be*ta"), retain=False)
    await _deliver(
        hass, spec.device_id, document_payload(other, owner="owner-c", owner_name="Gamma", rev=9), retain=False
    )

    assert mirror.spec is spec_before
    assert mirror.mirror is info_before
    assert _issue_ids(hass, ISSUE_OWNER_CONFLICT_PREFIX) == [f"{ISSUE_OWNER_CONFLICT_PREFIX}{spec.device_id}"]
    issue = _issue(hass, ISSUE_OWNER_CONFLICT_PREFIX, spec.device_id)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_key == "owner_conflict"
    assert issue.translation_placeholders == {"device": "Lamp\\_1", "owner": "Al\\_pha", "claimant": "Be\\*ta"}


async def test_conflict_clears_when_the_pinned_owner_is_current_again(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A document of the pinned owner with the current hash deletes the conflict issue."""
    spec = make_spec(on=ON_ACTIONS)
    other = make_spec(device_id=spec.device_id, on=OTHER_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, owner="owner-a"), retain=False)
    await _deliver(hass, spec.device_id, document_payload(other, owner="owner-b"), retain=False)
    assert _issue(hass, ISSUE_OWNER_CONFLICT_PREFIX, spec.device_id) is not None

    await _deliver(hass, spec.device_id, document_payload(spec, owner="owner-a", rev=2), retain=False)

    assert _issue(hass, ISSUE_OWNER_CONFLICT_PREFIX, spec.device_id) is None
    assert _mirror(entry, spec.device_id).mirror.owner == "owner-a"


# --- schema gate (D-14) -----------------------------------------------------------------------------------------


async def test_schema_too_new_keeps_the_mirror_and_raises_an_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A newer schema applies nothing and keeps the last known mirror; the next valid document resolves the issue."""
    spec = make_spec(on=ON_ACTIONS, name="Lamp")
    changed = make_spec(device_id=spec.device_id, on=OTHER_ACTIONS, name="Lamp")
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    mirror = _mirror(entry, spec.device_id)
    info_before = mirror.mirror

    await _deliver(hass, spec.device_id, document_payload(changed, rev=2, schema_version=2), retain=False)

    assert mirror.mirror is info_before
    issue = _issue(hass, ISSUE_SCHEMA_TOO_NEW_PREFIX, spec.device_id)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == "schema_too_new"
    assert issue.translation_placeholders == {"device": "Lamp", "version": "2", "supported": "1"}

    await _deliver(hass, spec.device_id, document_payload(changed, rev=3), retain=False)

    assert _issue(hass, ISSUE_SCHEMA_TOO_NEW_PREFIX, spec.device_id) is None
    assert mirror.spec == changed


async def test_schema_too_new_without_a_mirror_creates_no_mirror(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A newer schema for an unknown device creates an issue but no mirror, and the issues are bounded in number."""
    entry = await _setup(hass, make_hub_entry())
    specs = [make_spec(name=f"Device {index}", on=ON_ACTIONS) for index in range(MAX_SCHEMA_TOO_NEW_ISSUES + 2)]

    for spec in specs:
        await _deliver(hass, spec.device_id, document_payload(spec, schema_version=2), retain=False)

    assert _manager(entry).mirrors == {}
    assert len(_issue_ids(hass, ISSUE_SCHEMA_TOO_NEW_PREFIX)) == MAX_SCHEMA_TOO_NEW_ISSUES
    resolved = specs[0]
    await _deliver(hass, resolved.device_id, document_payload(resolved), retain=False)
    assert resolved.device_id in _manager(entry).mirrors
    assert _issue(hass, ISSUE_SCHEMA_TOO_NEW_PREFIX, resolved.device_id) is None


# --- hostile documents (T-03-18) --------------------------------------------------------------------------------


def _hostile_payloads(spec_id: str) -> dict[str, str]:
    """Return one rejected payload per reason; every one carries the canary in a place that must never be logged."""
    bad_name = make_spec(device_id=spec_id, name=f"Name {CANARY}", on=ON_ACTIONS)
    return {
        "invalid-json": '{"name": "' + CANARY + '", "actions": [',
        "wrong-device-id": document_payload(bad_name, tamper=lambda doc: doc.update(device_id="someone-else")),
        "oversize": document_payload(
            bad_name, tamper=lambda doc: doc.update(canary=CANARY, pad="x" * (MAX_DOCUMENT_BYTES + 1))
        ),
        "invalid-action-structure": document_payload(
            make_spec(device_id=spec_id, name=f"Name {CANARY}", on=[{"not_a_step": CANARY}])
        ),
        "too-few-options": document_payload(
            make_spec(
                SUBENTRY_SELECT,
                device_id=spec_id,
                name=f"Name {CANARY}",
                options=[("only", "Only", [{"action": "test.on", "data": {"x": CANARY}}])],
            )
        ),
    }


@pytest.mark.parametrize(
    "case",
    ["invalid-json", "wrong-device-id", "oversize", "invalid-action-structure", "too-few-options"],
)
async def test_invalid_documents_are_dropped_and_logged_without_content(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, caplog: pytest.LogCaptureFixture, case: str
) -> None:
    """One warning with a fixed reason: no mirror is created or changed and no payload text reaches the log."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    payload = _hostile_payloads(spec.device_id)[case]

    with caplog.at_level(logging.DEBUG):
        await _deliver(hass, spec.device_id, payload, retain=False)

    assert _manager(entry).mirrors == {}
    own = _own_records(caplog)
    assert len([record for record in own if record.levelno == logging.WARNING]) == 1
    assert CANARY not in "\n".join(record.getMessage() for record in own)

    # The same document against an existing mirror changes nothing either
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    mirror = _mirror(entry, spec.device_id)
    info_before = mirror.mirror
    with caplog.at_level(logging.DEBUG):
        await _deliver(hass, spec.device_id, payload, retain=False)
    assert mirror.mirror is info_before
    assert CANARY not in "\n".join(record.getMessage() for record in _own_records(caplog))


async def test_unexpected_exception_does_not_break_ingest(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, caplog: pytest.LogCaptureFixture
) -> None:
    """A surprise exception is logged without content and a later valid document still applies."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())

    with (
        patch(
            "custom_components.mqtt_actions.sync.validate_spec_structure", side_effect=RuntimeError(f"boom {CANARY}")
        ),
        caplog.at_level(logging.DEBUG),
    ):
        await _deliver(hass, spec.device_id, document_payload(spec), retain=False)

    assert _manager(entry).mirrors == {}
    own = _own_records(caplog)
    assert len([record for record in own if record.levelno == logging.WARNING]) == 1
    assert CANARY not in "\n".join(record.getMessage() for record in own)
    assert all(record.exc_info is None for record in own)

    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    assert spec.device_id in _manager(entry).mirrors


async def test_messages_for_one_device_apply_in_arrival_order(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Two documents fired back to back apply in arrival order, so the mirror ends at the later one."""
    first = make_spec(on=ON_ACTIONS)
    second = make_spec(device_id=first.device_id, on=OTHER_ACTIONS)
    entry = await _setup(hass, make_hub_entry())

    async_fire_mqtt_message(hass, config_topic(BASE, first.device_id), document_payload(first, rev=1), retain=False)
    async_fire_mqtt_message(hass, config_topic(BASE, first.device_id), document_payload(second, rev=2), retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    mirror = _mirror(entry, first.device_id)
    assert mirror.mirror.rev == 2
    assert mirror.spec == second


def test_mirror_issues_are_deleted_with_the_mirror_prefixes() -> None:
    """Device delete and hub removal clean every prefix in ISSUE_DEVICE_PREFIXES, so both new families are in it."""
    assert ISSUE_OWNER_CONFLICT_PREFIX in ISSUE_DEVICE_PREFIXES
    assert ISSUE_SCHEMA_TOO_NEW_PREFIX in ISSUE_DEVICE_PREFIXES


# --- tombstone (D-09, SYN-05) -----------------------------------------------------------------------------------


async def _flush_store(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Fire the delayed store save; the frozen clock also moves the loop time the store compares against."""
    freezer.tick(timedelta(seconds=STORE_SAVE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _mqtt_entry(hass: HomeAssistant) -> MockConfigEntry:
    return hass.config_entries.async_entries("mqtt")[0]


def _mirror_device_entry(hass: HomeAssistant, device_id: str) -> dr.DeviceEntry | None:
    return dr.async_get(hass).async_get_device_by_identifier(
        ("mqtt", f"{DOMAIN}_{device_id}"), _mqtt_entry(hass).entry_id
    )


def _register_leftovers(hass: HomeAssistant, device_id: str) -> dr.DeviceEntry:
    """Register a device and an entity of core MQTT that have no state, as a missed delete leaves them."""
    mqtt_entry = _mqtt_entry(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", f"{DOMAIN}_{device_id}")}, name="Leftover"
    )
    er.async_get(hass).async_get_or_create(
        "switch", "mqtt", device_id, config_entry=mqtt_entry, device_id=device.id, suggested_object_id="leftover"
    )
    return device


async def test_live_tombstone_removes_the_mirror_at_once(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-09: an empty live payload removes the mirror, its subscriptions, Script state, Store entries and issues."""
    spec = make_spec(on=ON_ACTIONS, name="Lamp")
    entry = await _setup(hass, make_hub_entry())
    manager = _manager(entry)
    await _deliver(hass, spec.device_id, document_payload(spec, owner="owner-a"), retain=False)
    await _state(hass, spec.device_id, "ON", retain=False)
    mirror = _mirror(entry, spec.device_id)
    await _deliver(hass, spec.device_id, document_payload(spec, owner="owner-b"), retain=False)
    manager._create_breaker_issue(mirror)
    manager._tripped[spec.device_id] = "some-hash"
    assert _issue(hass, ISSUE_OWNER_CONFLICT_PREFIX, spec.device_id) is not None
    assert _issue(hass, ISSUE_CIRCUIT_BREAKER_PREFIX, spec.device_id) is not None
    state_release, test_release = mirror.unsubscribe, mirror.unsubscribe_test
    mirror.unsubscribe = Mock(side_effect=state_release)
    mirror.unsubscribe_test = Mock(side_effect=test_release)
    await _flush_store(hass, freezer)
    assert hass_storage[STORE_KEY]["data"][STORE_LAST_ACTED][spec.device_id] == "ON"

    with patch.object(manager.runner, "async_unload", wraps=manager.runner.async_unload) as unload:
        await _deliver(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in manager.mirrors
    mirror.unsubscribe.assert_called_once()
    mirror.unsubscribe_test.assert_called_once()
    unload.assert_awaited_once_with(spec.device_id, remove_issue=True)
    for prefix in ISSUE_DEVICE_PREFIXES:
        assert _issue(hass, prefix, spec.device_id) is None
    await _flush_store(hass, freezer)
    data = hass_storage[STORE_KEY]["data"]
    assert data[STORE_MIRRORS] == {}
    assert spec.device_id not in data[STORE_LAST_ACTED]
    assert spec.device_id not in data[STORE_TRIPPED]
    await _state(hass, spec.device_id, "OFF", retain=False)
    assert mirror.tracker.last_acted == "ON"


async def test_retained_empty_payload_also_removes(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A retained empty payload, replayed at subscribe, is a tombstone as well."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    assert spec.device_id in _manager(entry).mirrors

    await _deliver(hass, spec.device_id, "", retain=True)

    assert spec.device_id not in _manager(entry).mirrors


async def test_tombstone_for_an_unknown_id_is_a_noop(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, caplog: pytest.LogCaptureFixture
) -> None:
    """An empty payload for an id without a mirror changes nothing and logs nothing above debug."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    other = make_spec(on=ON_ACTIONS)

    with caplog.at_level(logging.DEBUG):
        await _deliver(hass, other.device_id, "", retain=False)

    assert set(_manager(entry).mirrors) == {spec.device_id}
    assert [record for record in _own_records(caplog) if record.levelno > logging.DEBUG] == []


async def test_tombstone_does_not_touch_owned_devices(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """An empty payload for an owned id is healed by the owner branch; the device stays as it is."""
    sub: ConfigSubentryData = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    entry = await _setup(hass, make_hub_entry([sub]))
    manager = _manager(entry)
    device = manager.devices[device_id]
    spec_before = device.spec
    mqtt_mock.async_publish.reset_mock()

    await _deliver(hass, device_id, "", retain=False)

    assert manager.devices[device_id] is device
    assert device.spec is spec_before
    assert device_id not in manager.mirrors
    assert callable(device.unsubscribe)
    assert [payload for payload, _qos, _retain in _publishes(mqtt_mock, config_topic(BASE, device_id)) if payload]


async def test_removed_mirror_can_return(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """After a tombstone a valid document creates the mirror again, as a fresh device without the old baseline."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    await _state(hass, spec.device_id, "ON", retain=False)
    first = _mirror(entry, spec.device_id)
    await _deliver(hass, spec.device_id, "", retain=False)
    assert spec.device_id not in _manager(entry).mirrors

    await _deliver(hass, spec.device_id, document_payload(spec, rev=2), retain=False)

    second = _mirror(entry, spec.device_id)
    assert second is not first
    assert second.tracker.last_acted is None
    assert second.mirror is not None
    assert second.mirror.rev == 2


async def test_tombstone_removes_leftover_registry_entries(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Registry entries without a live entity are leftovers of a missed delete, and the tombstone removes them."""
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    device = _register_leftovers(hass, spec.device_id)
    entities = er.async_entries_for_device(er.async_get(hass), device.id, include_disabled_entities=True)
    assert len(entities) == 1
    assert hass.states.get(entities[0].entity_id) is None

    await _deliver(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in _manager(entry).mirrors
    assert _mirror_device_entry(hass, spec.device_id) is None
    assert er.async_get(hass).async_get(entities[0].entity_id) is None


async def test_live_entities_keep_their_registry_entries(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Pitfall 10: with live discovery the cleanup leaves the registries alone and publishes no empty discovery."""
    spec = make_spec(on=ON_ACTIONS, name="Foreign lamp")
    entry = await _setup(hass, make_hub_entry())
    discovery = discovery_topic("homeassistant", spec.device_id)
    payload = build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3")
    async_fire_mqtt_message(hass, discovery, json.dumps(payload), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _deliver(hass, spec.device_id, document_payload(spec), retain=False)
    device = _mirror_device_entry(hass, spec.device_id)
    assert device is not None
    entities = er.async_entries_for_device(er.async_get(hass), device.id)
    assert entities
    assert all(hass.states.get(entity.entity_id) is not None for entity in entities)
    mqtt_mock.async_publish.reset_mock()

    await _deliver(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in _manager(entry).mirrors
    assert _mirror_device_entry(hass, spec.device_id) is not None
    for entity in entities:
        assert er.async_get(hass).async_get(entity.entity_id) is not None
        assert hass.states.get(entity.entity_id) is not None
    assert [item for item in _publishes(mqtt_mock, discovery) if item[0] == ""] == []


async def test_registry_cleanup_is_guarded(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """Without an MQTT entry nothing is attempted, and a device that has no registry entry is no error."""
    first = make_spec(on=ON_ACTIONS)
    second = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    manager = _manager(entry)
    await _deliver(hass, first.device_id, document_payload(first), retain=False)
    await _deliver(hass, second.device_id, document_payload(second), retain=False)
    device = _register_leftovers(hass, first.device_id)

    with patch.object(manager.gateway, "mqtt_entry_id", return_value=None):
        await _deliver(hass, first.device_id, "", retain=False)
    assert first.device_id not in manager.mirrors
    assert dr.async_get(hass).async_get(device.id) is not None

    assert _mirror_device_entry(hass, second.device_id) is None
    await _deliver(hass, second.device_id, "", retain=False)
    assert second.device_id not in manager.mirrors


# --- grace-window prune (D-10, SYN-05) --------------------------------------------------------------------------


async def _advance_window(hass: HomeAssistant, freezer: FrozenDateTimeFactory, windows: float = 1.0) -> None:
    freezer.tick(timedelta(seconds=PRUNE_GRACE_SECONDS * windows + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_absence_alone_never_removes_a_mirror_single_instance(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A restored mirror with no availability information survives any number of grace windows."""
    spec = make_spec(on=ON_ACTIONS)
    _seed_store(hass_storage, {STORE_MIRRORS: {spec.device_id: document_payload(spec)}})
    entry = await _setup(hass, make_hub_entry())
    assert spec.device_id in _manager(entry).mirrors

    await _advance_window(hass, freezer, windows=3)

    assert spec.device_id in _manager(entry).mirrors


async def test_prune_cleans_registry_leftovers(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A pruned mirror goes through the same removal as a tombstone, leftover registry entries included."""
    spec = make_spec(on=ON_ACTIONS)
    _seed_store(hass_storage, {STORE_MIRRORS: {spec.device_id: document_payload(spec)}})
    entry = await _setup(hass, make_hub_entry())
    device = _register_leftovers(hass, spec.device_id)
    async_fire_mqtt_message(hass, availability_topic(BASE, FOREIGN_OWNER), "online", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert spec.device_id in _manager(entry).mirrors

    await _advance_window(hass, freezer)

    assert spec.device_id not in _manager(entry).mirrors
    assert dr.async_get(hass).async_get(device.id) is None
