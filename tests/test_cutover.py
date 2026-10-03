"""The cutover to native entities: the roster gate, the settle timer and the capability (D-09, D-10, D-12)."""

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_fire_time_changed

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    DOMAIN,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_OFFLINE_SECONDS,
    STORE_KEY,
)
from custom_components.mqtt_actions.presence import parse_heartbeat
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, heartbeat_topic
from tests.test_native_start import _loop_back_discovery
from tests.test_takeover import (
    CLEAR_PAYLOAD,
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
SESSION = "6f1c0f0e-3a52-4f43-8d0c-5a0b7f3c9d21"
SETTLE_PASSED = 6.0  # a little more than CUTOVER_SETTLE_SECONDS


@pytest.fixture(autouse=True)
def fast_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll quickly; the default wait is long only because production waits for a real broker round trip."""
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


def _stored_native(hass_storage: dict[str, Any]) -> dict[str, Any] | None:
    """Return the persisted native state, None while the Store has none (nothing was saved or no native key)."""
    return hass_storage.get(STORE_KEY, {}).get("data", {}).get("native")


def _peer(
    hass: HomeAssistant,
    instance_id: str,
    *,
    native: bool,
    name: str = "Peer",
    heartbeat: bool = True,
    availability: str | None = "online",
) -> None:
    """Announce a foreign instance: a live heartbeat, with or without the capability key, and its availability."""
    if availability is not None:
        async_fire_mqtt_message(hass, availability_topic(BASE, instance_id), availability, retain=True)
    if heartbeat:
        data: dict[str, Any] = {
            "instance_id": instance_id,
            "name": name,
            "version": "0.2.0" if native else "0.1.0",
            "devices": 1,
            "session": SESSION,
        }
        if native:
            data["entities"] = "native"
        async_fire_mqtt_message(hass, heartbeat_topic(BASE, instance_id), json.dumps(data), retain=False)


async def _settle(hass: HomeAssistant, seconds: float = SETTLE_PASSED) -> None:
    """Let the given time pass for the timers of the integration and run what they start."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


def _use_clock(manager: Manager) -> list[float]:
    """Replace the manager clock by a settable one and restart the listening time on it; the list holds its value."""
    now = [1000.0]
    manager.clock = lambda: now[0]
    manager.presence.on_reconnect()
    return now


def _discovery_publishes(mqtt_mock: Any, device_id: str) -> list[tuple[Any, bool]]:
    topic = discovery_topic(PREFIX, device_id)
    return [(call.args[1], call.args[3]) for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _device_id(subentry: Any) -> str:
    return subentry["data"][CONF_DEVICE_ID]


# --- Task 1 tracer: the gate ----------------------------------------------------------------------------------------


async def test_a_legacy_install_without_peers_cuts_over_after_the_settle_time(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-09, D-12, MIG-02: after the settle time the flag is set and the takeover keeps every identity of the device."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_id = legacy.device_id
    customize_mqtt_device(hass, device_id, area_id="kitchen", name_by_user="Stehlampe")
    legacy_ids = legacy_entity_ids(hass, device_id)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    assert len(legacy_ids) == 3  # the switch and the two test buttons
    assert _stored_native(hass_storage) is None
    mqtt_mock.async_publish.reset_mock()
    _loop_back_discovery(hass, mqtt_mock)

    await _settle(hass)

    assert _stored_native(hass_storage) == {"instance": True, "pending": [], "devices": []}
    assert _manager(legacy.entry).is_native(device_id)
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform) == (old.id, DOMAIN)
    switch_id = entity_registry.async_get_entity_id("switch", DOMAIN, device_id)
    assert switch_id == next(entity_id for entity_id in legacy_ids if entity_id.startswith("switch."))
    assert hass.states.get(switch_id) is not None
    device = next(device for device in device_registry.devices.values() if (DOMAIN, device_id) in device.identifiers)
    assert (device.area_id, device.name_by_user) == ("kitchen", "Stehlampe")
    published = _discovery_publishes(mqtt_mock, device_id)
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in published] == [
        ({"migrate_discovery": True}, False),
        (CLEAR_PAYLOAD, True),
    ]


async def test_nothing_happens_before_the_settle_time(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-09: until the timer fires the legacy discovery stays, no migrate payload goes out and no flag is stored."""
    subentry = make_switch_subentry("Lamp")
    await _setup(hass, make_hub_entry([subentry]))

    await _settle(hass, 4.0)

    published = _discovery_publishes(mqtt_mock, _device_id(subentry))
    assert published
    assert all(payload and "migrate_discovery" not in payload for payload, _retain in published)
    assert _stored_native(hass_storage) is None


async def test_an_online_legacy_peer_blocks_the_cutover(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: a v0.1.0-shaped peer that is online keeps the instance on the legacy path."""
    subentry = make_switch_subentry("Lamp")
    entry = await _setup(hass, make_hub_entry([subentry]))
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)

    assert _stored_native(hass_storage) is None
    assert not _manager(entry).is_native(_device_id(subentry))
    published = _discovery_publishes(mqtt_mock, _device_id(subentry))
    assert published
    assert all(payload and "migrate_discovery" not in payload for payload, _retain in published)


async def test_a_capable_peer_does_not_block(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: a peer whose heartbeat carries the capability key lets the cutover proceed."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    _peer(hass, "native-peer", native=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)

    native = _stored_native(hass_storage)
    assert native is not None
    assert native["instance"] is True
    assert _manager(entry).is_native(_device_id(next(iter(entry.subentries.values())).data))


@pytest.mark.parametrize("how", ["announced_offline", "stale_heartbeat"])
async def test_an_offline_peer_does_not_block(
    how: str,
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: a legacy peer that announced offline, or whose last heartbeat is older than the timeout, does not block."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    now = _use_clock(_manager(entry))
    if how == "announced_offline":
        _peer(hass, "legacy-peer", native=False, availability="offline")
    else:
        _peer(hass, "legacy-peer", native=False)
        await hass.async_block_till_done(wait_background_tasks=True)
        now[0] += HEARTBEAT_OFFLINE_SECONDS + 1
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)

    native = _stored_native(hass_storage)
    assert native is not None
    assert native["instance"] is True


async def test_a_peer_announced_online_without_a_heartbeat_blocks_until_it_was_silent_long_enough(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: no heartbeat is no proof of capability; the peer blocks until this instance listened for the timeout."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    now = _use_clock(_manager(entry))
    _peer(hass, "silent-peer", native=False, heartbeat=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)
    assert _stored_native(hass_storage) is None

    now[0] += HEARTBEAT_OFFLINE_SECONDS + 1
    # The next heartbeat tick re-evaluates the roster and with it the gate
    await _settle(hass, HEARTBEAT_INTERVAL_SECONDS + 5)

    native = _stored_native(hass_storage)
    assert native is not None
    assert native["instance"] is True


async def test_a_legacy_peer_going_offline_triggers_the_cutover(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: blocked at first; the clean shutdown of the peer triggers the check at once, with no settle wait."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _settle(hass)
    assert _stored_native(hass_storage) is None

    async_fire_mqtt_message(hass, availability_topic(BASE, "legacy-peer"), "offline", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    native = _stored_native(hass_storage)
    assert native is not None
    assert native["instance"] is True


async def test_the_cutover_runs_once(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """T-5-13: after the flip and the reload no further flip, timer or pass happens and the flag stays stored."""
    subentry = make_switch_subentry("Lamp")
    entry = await _setup(hass, make_hub_entry([subentry]))
    original = hass.config_entries.async_schedule_reload
    with patch.object(hass.config_entries, "async_schedule_reload", wraps=original) as schedule_reload:
        await _settle(hass)
        assert schedule_reload.call_count == 1
        migrates = [p for p, _retain in _discovery_publishes(mqtt_mock, _device_id(subentry)) if p and "migrate" in p]
        assert len(migrates) == 1

        # More roster changes and more time change nothing: the flag is set, so no timer and no check is left
        _peer(hass, "legacy-peer", native=False)
        await hass.async_block_till_done(wait_background_tasks=True)
        await _settle(hass, 2 * HEARTBEAT_INTERVAL_SECONDS)
        async_fire_mqtt_message(hass, availability_topic(BASE, "legacy-peer"), "offline", retain=True)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert schedule_reload.call_count == 1
    migrates = [p for p, _retain in _discovery_publishes(mqtt_mock, _device_id(subentry)) if p and "migrate" in p]
    assert len(migrates) == 1
    native = _stored_native(hass_storage)
    assert native is not None
    assert native["instance"] is True
    assert _manager(entry).is_native(_device_id(subentry))


async def test_the_heartbeat_announces_the_capability(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-10: the published heartbeat carries the capability key, and a v0.1.0 heartbeat parses as not native."""
    entry = await _setup(hass, make_hub_entry())
    instance_id = _manager(entry).instance_id
    topic = heartbeat_topic(BASE, instance_id)
    mqtt_mock.async_publish.reset_mock()

    await _manager(entry).presence.async_publish_heartbeat()

    payload = next(call.args[1] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic)
    assert json.loads(payload)["entities"] == "native"
    heartbeat = parse_heartbeat(BASE, topic, payload)
    assert heartbeat is not None
    assert heartbeat.native is True

    legacy = json.dumps(
        {"instance_id": instance_id, "name": "Old", "version": "0.1.0", "devices": 1, "session": SESSION}
    )
    parsed = parse_heartbeat(BASE, topic, legacy)
    assert parsed is not None
    assert parsed.native is False
