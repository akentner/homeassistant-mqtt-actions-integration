"""The cutover to native entities: the roster gate, the settle timer and the capability (D-09, D-10, D-12)."""

import json
from datetime import timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_fire_time_changed

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_RUN_ON_STARTUP,
    CUTOVER_HINT_MAX_NAMES,
    DOMAIN,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_OFFLINE_SECONDS,
    ISSUE_NATIVE_CUTOVER_WAITING,
    MAX_TRACKED_INSTANCES,
    STORE_KEY,
    STORE_MIRRORS,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.manager import async_remove_local_state
from custom_components.mqtt_actions.presence import parse_heartbeat
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, heartbeat_topic
from tests.documents import document_payload, make_spec
from tests.test_native_start import _legacy_mirror, _loop_back_discovery, _mqtt_device_of
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
    device = device_registry.async_get_device_by_identifier((DOMAIN, device_id), legacy.entry.entry_id)
    assert device is not None
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


async def test_a_forged_capability_heartbeat_does_not_unblock_the_cutover(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """WR-03: anyone on the broker can claim the capability under a legacy peer's id; the claim must not count."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    _peer(hass, "legacy-peer", native=True, availability=None)
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)

    assert _stored_native(hass_storage) is None
    assert _manager(entry).presence.blocking_peers() == ["Peer"]


async def test_a_flooded_roster_keeps_the_cutover_waiting(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """WR-03: random capable ids fill the roster, a real legacy peer is dropped; the gate must fail closed."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    now = _use_clock(_manager(entry))
    # Past the window in which a silent instance counts; the flood below is fresh at this point
    now[0] += HEARTBEAT_OFFLINE_SECONDS + 1
    for number in range(MAX_TRACKED_INSTANCES):
        _peer(hass, f"flood-{number}", native=True, availability=None)
    await hass.async_block_till_done(wait_background_tasks=True)
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)

    assert _stored_native(hass_storage) is None
    assert _manager(entry).presence.blocking_peers() != []
    # The flood ends and its rows expire: the roster has room again, the legacy peer is tracked and blocks by its row
    now[0] += HEARTBEAT_OFFLINE_SECONDS + 1
    _peer(hass, "legacy-peer", native=False, availability=None)
    await _settle(hass, HEARTBEAT_INTERVAL_SECONDS + 5)
    assert _stored_native(hass_storage) is None
    assert _manager(entry).presence.blocking_peers() == ["Peer"]


async def test_a_capable_peer_does_not_block(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: a peer whose heartbeat carries the capability key lets the cutover proceed."""
    subentry = make_switch_subentry("Lamp")
    entry = await _setup(hass, make_hub_entry([subentry]))
    _peer(hass, "native-peer", native=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)

    native = _stored_native(hass_storage)
    assert native is not None
    assert native["instance"] is True
    assert _manager(entry).is_native(_device_id(subentry))


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

    # Live: a broker delivers a change to a running subscriber without the retain flag, and core drops a second replay
    async_fire_mqtt_message(hass, availability_topic(BASE, "legacy-peer"), "offline", retain=False)
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
        async_fire_mqtt_message(hass, availability_topic(BASE, "legacy-peer"), "offline", retain=False)
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


# --- Task 2: the hint and the devices created while waiting ---------------------------------------------------------


def _hint(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_NATIVE_CUTOVER_WAITING)


def _new_switch(device_id: str) -> ConfigSubentry:
    return ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_DEVICE_ID: device_id,
                CONF_ON_CHANGE_TO_ON: [],
                CONF_ON_CHANGE_TO_OFF: [],
                CONF_RUN_ON_STARTUP: False,
            }
        ),
        subentry_type=SUBENTRY_SWITCH,
        title="Fresh",
        unique_id=device_id,
    )


def _config_payloads(mqtt_mock: Any, device_id: str) -> list[dict[str, Any]]:
    topic = config_topic(BASE, device_id)
    return [json.loads(call.args[1]) for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


async def test_the_hint_names_the_blocking_peers(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10, T-5-14: a waiting cutover raises a plain warning that lists the peer, markdown escaped."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    _peer(hass, "legacy-peer", native=False, name="Old *Lamp* [x]")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _hint(hass) is None  # nothing is decided before the settle time

    await _settle(hass)

    issue = _hint(hass)
    assert issue is not None
    assert issue.translation_key == ISSUE_NATIVE_CUTOVER_WAITING
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_fixable is False
    assert issue.translation_placeholders == {"instances": r"Old \*Lamp\* \[x\]"}


async def test_the_hint_is_capped(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """T-5-14: more blocking peers than the cap are listed up to the cap and an ellipsis."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    for index in range(CUTOVER_HINT_MAX_NAMES + 2):
        _peer(hass, f"legacy-peer-{index}", native=False, name=f"Peer {index}")
    await hass.async_block_till_done(wait_background_tasks=True)

    await _settle(hass)

    issue = _hint(hass)
    assert issue is not None
    text = issue.translation_placeholders["instances"]
    assert text.count("Peer ") == CUTOVER_HINT_MAX_NAMES
    assert text.endswith("\u2026")


async def test_the_hint_goes_when_the_cutover_proceeds(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: the issue is deleted once the blocker went offline and the flip happened; nothing blocking, no issue."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _settle(hass)
    assert _hint(hass) is not None

    async_fire_mqtt_message(hass, availability_topic(BASE, "legacy-peer"), "offline", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _stored_native(hass_storage) is not None
    assert _hint(hass) is None


async def test_the_hint_is_never_created_when_nothing_blocks(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    await _settle(hass)
    assert _hint(hass) is None


async def test_the_hint_is_not_rebuilt_while_the_blockers_stay_the_same(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """Every heartbeat re-runs the check; an unchanged set of blockers must not churn the issue registry."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _settle(hass)
    with patch.object(ir, "async_create_issue") as create_issue, patch.object(ir, "async_delete_issue") as delete_issue:
        _peer(hass, "legacy-peer", native=False)
        await hass.async_block_till_done(wait_background_tasks=True)
        await _settle(hass, HEARTBEAT_INTERVAL_SECONDS + 1)
    create_issue.assert_not_called()
    delete_issue.assert_not_called()


async def test_hub_removal_deletes_the_hint(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp")]))
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _settle(hass)
    assert _hint(hass) is not None

    await async_remove_local_state(hass, entry)

    assert _hint(hass) is None


async def test_a_device_created_while_waiting_stays_legacy(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: a device created under a blocking peer is legacy and part of the pending set at the later cutover."""
    entry = await _setup(hass, make_hub_entry())
    _peer(hass, "legacy-peer", native=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _settle(hass)
    device_id = "0b1f6a0e-6a52-4f5b-9b0e-3a4c1c2d9e11"

    hass.config_entries.async_add_subentry(entry, _new_switch(device_id))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not _manager(entry).is_native(device_id)
    published = _discovery_publishes(mqtt_mock, device_id)
    assert published
    assert all(payload and "migrate_discovery" not in payload for payload, _retain in published)
    assert "entities" not in _config_payloads(mqtt_mock, device_id)[-1]

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        async_fire_mqtt_message(hass, availability_topic(BASE, "legacy-peer"), "offline", retain=False)
        await hass.async_block_till_done(wait_background_tasks=True)

    schedule_reload.assert_called_once_with(entry.entry_id)
    native = _stored_native(hass_storage)
    assert native == {"instance": True, "pending": [device_id], "devices": []}


async def test_a_device_created_after_the_cutover_is_native_at_once(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-12: with the instance flag set a new device is native, publishes no discovery and is not pending."""
    entry = await _setup(hass, make_hub_entry())
    await _settle(hass)
    assert _stored_native(hass_storage) == {"instance": True, "pending": [], "devices": []}
    device_id = "0b1f6a0e-6a52-4f5b-9b0e-3a4c1c2d9e11"

    hass.config_entries.async_add_subentry(entry, _new_switch(device_id))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _manager(entry).is_native(device_id)
    assert not _discovery_publishes(mqtt_mock, device_id)
    assert er.async_get(hass).async_get_entity_id("switch", DOMAIN, device_id) is not None
    assert _config_payloads(mqtt_mock, device_id)[-1]["entities"] == "native"
    assert _stored_native(hass_storage) == {"instance": True, "pending": [], "devices": []}


# --- Plan 05-07 task 1 tracer: a running legacy mirror follows the owner's marker ------------------------------------

NEW_ACTIONS = [{"action": "test.on"}]


@pytest.mark.parametrize("changed", [False, True], ids=["same_content", "changed_content"])
async def test_a_marker_for_a_running_legacy_mirror_flips_it_after_a_reload(
    changed: bool, hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """D-09, D-12, MIG-02: the marker, with the content unchanged or changed, flips the mirror and reloads once."""
    spec = make_spec(name="Foreign lamp")
    entry, topic = await _legacy_mirror(hass, make_hub_entry, spec)
    entity_registry = er.async_get(hass)
    customize_mqtt_device(hass, spec.device_id, area_id="kitchen", name_by_user="Stehlampe")
    legacy_ids = legacy_entity_ids(hass, spec.device_id)
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", spec.device_id)
    mqtt_device = _mqtt_device_of(hass, spec.device_id)
    assert switch_id is not None
    assert mqtt_device is not None
    async_fire_mqtt_message(hass, topic, MIGRATE_PAYLOAD, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    marked = make_spec(device_id=spec.device_id, name="Foreign lamp", on=NEW_ACTIONS) if changed else spec
    original = hass.config_entries.async_schedule_reload
    mqtt_mock.async_publish.reset_mock()

    with patch.object(hass.config_entries, "async_schedule_reload", wraps=original) as schedule_reload:
        async_fire_mqtt_message(
            hass, config_topic(BASE, spec.device_id), document_payload(marked, rev=2, native=True), retain=False
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    schedule_reload.assert_called_once_with(entry.entry_id)
    manager = _manager(entry)
    info = manager.mirrors[spec.device_id].mirror
    assert info is not None
    assert info.native is True
    assert manager.is_native(spec.device_id)
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform, moved.device_id) == (old.id, DOMAIN, mqtt_device.id)
    assert entity_registry.async_get_entity_id("switch", DOMAIN, spec.device_id) == switch_id
    assert hass.states.get(switch_id) is not None
    device = dr.async_get(hass).async_get(mqtt_device.id)
    assert device is not None
    assert (device.area_id, device.name_by_user) == ("kitchen", "Stehlampe")
    assert device.identifiers == {(DOMAIN, spec.device_id)}
    stored = json.loads(hass_storage[STORE_KEY]["data"][STORE_MIRRORS][spec.device_id])
    assert stored["entities"] == "native"
    assert [topic for topic in (c.args[0] for c in mqtt_mock.async_publish.call_args_list) if PREFIX in topic] == []


async def test_a_burst_of_marked_documents_schedules_one_reload(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-5-15: three mirrors flipped by three documents in a row, and a later marked change, reload once."""
    entry = await _setup(hass, make_hub_entry())
    specs = [make_spec(name=f"Foreign {index}") for index in range(3)]
    for spec in specs:
        async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), document_payload(spec), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert all(spec.device_id in _manager(entry).mirrors for spec in specs)

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        for spec in specs:
            async_fire_mqtt_message(
                hass, config_topic(BASE, spec.device_id), document_payload(spec, rev=2, native=True), retain=False
            )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert schedule_reload.call_count == 1
        schedule_reload.assert_called_once_with(entry.entry_id)

        changed = make_spec(device_id=specs[0].device_id, name="Foreign 0", on=NEW_ACTIONS)
        async_fire_mqtt_message(
            hass, config_topic(BASE, changed.device_id), document_payload(changed, rev=3, native=True), retain=False
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert schedule_reload.call_count == 1
    assert all(_manager(entry).mirrors[spec.device_id].mirror.native for spec in specs)


async def test_a_document_without_the_marker_or_from_a_competing_owner_schedules_no_reload(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-5-15, T-5-03: an unmarked change and a marked claim of another owner leave the mirror legacy and quiet."""
    spec = make_spec(name="Foreign lamp")
    entry = await _setup(hass, make_hub_entry())
    async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), document_payload(spec), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        changed = make_spec(device_id=spec.device_id, name="Foreign lamp", on=NEW_ACTIONS)
        async_fire_mqtt_message(
            hass, config_topic(BASE, spec.device_id), document_payload(changed, rev=2), retain=False
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        competing = document_payload(spec, owner="instance-other", owner_name="Other", rev=3, native=True)
        async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), competing, retain=False)
        await hass.async_block_till_done(wait_background_tasks=True)

    schedule_reload.assert_not_called()
    info = _manager(entry).mirrors[spec.device_id].mirror
    assert info is not None
    assert (info.native, info.owner) == (False, "instance-foreign")
