"""Two real Home Assistant instances on one fake broker: the owner runs its actions, the follower only mirrors."""

import asyncio
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions.const import (
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    DOMAIN,
    ISSUE_APPROVAL_PREFIX,
    ISSUE_OWNER_CONFLICT_PREFIX,
    ISSUE_OWNERSHIP_CLAIM_PREFIX,
    PRUNE_GRACE_SECONDS,
    REPUBLISH_THROTTLE_SECONDS,
    STORE_KEY,
    STORE_MIRRORS,
)
from custom_components.mqtt_actions.manager import async_remove_all_devices, async_remove_local_state
from custom_components.mqtt_actions.topics import (
    availability_topic,
    config_topic,
    discovery_topic,
    parse_availability_topic,
    parse_config_topic,
    parse_discovery_topic,
    state_topic,
)
from custom_components.mqtt_actions.topics import (
    test_topic as press_topic,
)
from tests.documents import document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

    from tests.fake_broker import FakeBroker, Instance

BASE = "mqtt_actions"
PREFIX = "homeassistant"


async def _settle(*instances: Instance) -> None:
    """Let every instance finish the messages and background tasks the broker delivered."""
    for _ in range(2):
        for instance in instances:
            await instance.hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize("owner_first", [True, False], ids=["owner-first", "follower-first"])
async def test_follower_mirrors_the_owners_device(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable, *, owner_first: bool
) -> None:
    """The follower holds a mirror in both start orders; only the owner's service runs for a live state change."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"]["device_id"]
    if owner_first:
        owner = await make_instance("owner", hass=hass, subentries=[sub])
        follower = await make_instance("follower")
    else:
        follower = await make_instance("follower", hass=hass)
        owner = await make_instance("owner", subentries=[sub])
    assert owner.hass is not follower.hass
    owner_calls = async_mock_service(owner.hass, "test", "on")
    follower_calls = async_mock_service(follower.hass, "test", "on")
    await owner.hass.async_block_till_done(wait_background_tasks=True)
    await follower.hass.async_block_till_done(wait_background_tasks=True)

    assert device_id in follower.manager.mirrors
    assert device_id not in follower.manager.devices
    assert device_id in owner.manager.devices
    assert device_id not in owner.manager.mirrors

    await follower.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await owner.hass.async_block_till_done(wait_background_tasks=True)
    await follower.hass.async_block_till_done(wait_background_tasks=True)

    assert len(owner_calls) == 1
    assert follower_calls == []
    assert follower.manager.mirrors[device_id].tracker.last_acted == "ON"


async def test_owner_delete_removes_the_mirror_everywhere(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09, SYN-06: the owner deletes the device; the follower's mirror is gone and the broker keeps nothing of it."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"]["device_id"]
    owner = await make_instance("owner", hass=hass, subentries=[sub])
    follower = await make_instance("follower")
    await _settle(owner, follower)
    assert device_id in follower.manager.mirrors
    await owner.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower)
    assert any(device_id in topic for topic in fake_broker.retained)

    owner.hass.config_entries.async_remove_subentry(owner.entry, next(iter(owner.entry.subentries)))
    await owner.manager.async_reconcile()
    await _settle(owner, follower)

    assert device_id not in owner.manager.devices
    assert device_id not in follower.manager.mirrors
    assert [topic for topic in fake_broker.retained if device_id in topic] == []


# --- grace-window prune (D-10, SYN-05) --------------------------------------------------------------------------


async def _advance(freezer: FrozenDateTimeFactory, *instances: Instance, windows: float = 1.0) -> None:
    """Move the clock by whole prune windows (plus a second) and let every instance process what that fires."""
    freezer.tick(timedelta(seconds=PRUNE_GRACE_SECONDS * windows + 1))
    async_fire_time_changed(instances[0].hass)
    await _settle(*instances)


async def _owner_and_follower(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable
) -> tuple[Instance, Instance, str]:
    """Start an owner with one device and a follower that mirrors it; return both and the device id."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"]["device_id"]
    owner = await make_instance("owner", hass=hass, subentries=[sub])
    follower = await make_instance("follower")
    await _settle(owner, follower)
    assert device_id in follower.manager.mirrors
    return owner, follower, device_id


async def _owner_deletes(owner: Instance) -> None:
    """Remove the only device of the owner, which publishes the clears and the tombstone."""
    owner.hass.config_entries.async_remove_subentry(owner.entry, next(iter(owner.entry.subentries)))
    await owner.manager.async_reconcile()


async def test_absence_alone_never_removes_a_mirror(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """T-03-21: a document that vanished without any owner availability information never removes the mirror."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    fake_broker.wipe_retained()
    follower.gateway.reconnect()
    await _settle(owner, follower)

    await _advance(freezer, owner, follower, windows=3)

    assert device_id in follower.manager.mirrors


async def test_prune_removes_a_mirror_the_owner_deleted_while_the_follower_was_offline(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    hass_storage: dict[str, Any],
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The follower misses the tombstone; after restart the online owner and the missing document prune the mirror."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    await follower.stop()
    await _owner_deletes(owner)
    await _settle(owner)
    assert [topic for topic in fake_broker.retained if device_id in topic] == []

    await follower.start()
    await _settle(owner, follower)
    assert device_id in follower.manager.mirrors
    assert follower.manager.sync.instance_status(owner.manager.instance_id) == "online"

    await _advance(freezer, owner, follower)

    assert device_id not in follower.manager.mirrors
    assert device_id not in follower.manager._stored_last_acted
    await follower.stop()
    assert hass_storage[f"{STORE_KEY}.follower"]["data"][STORE_MIRRORS] == {}


async def test_prune_waits_for_the_owner_to_be_online(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-10: an offline owner keeps its mirrors; when it turns online live, the mirror goes after a further window."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    await follower.stop()
    await _owner_deletes(owner)
    await owner.stop()
    await _settle(owner)
    assert fake_broker.retained[availability_topic(BASE, owner.manager.instance_id)] == "offline"

    await follower.start()
    await _settle(owner, follower)
    await _advance(freezer, owner, follower, windows=2)
    assert device_id in follower.manager.mirrors

    await owner.start()
    await _settle(owner, follower)
    assert device_id in follower.manager.mirrors
    await _advance(freezer, owner, follower)

    assert device_id not in follower.manager.mirrors


async def test_seen_mirror_is_not_pruned(
    hass: HomeAssistant,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A mirror whose document is replayed after the restart stays, even with the owner online."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    await follower.restart()
    await _settle(owner, follower)
    assert follower.manager.sync.instance_status(owner.manager.instance_id) == "online"

    await _advance(freezer, owner, follower, windows=3)

    assert device_id in follower.manager.mirrors


async def test_reconnect_resets_seen_and_presence_and_rearms(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A reconnect forgets what was seen; a replay with the document keeps the mirror, one without prunes it."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    follower.gateway.reconnect()
    await _settle(owner, follower)
    await _advance(freezer, owner, follower)
    assert device_id in follower.manager.mirrors

    # The retained document disappears without a live tombstone, for example a broker that lost it
    fake_broker.retained.pop(config_topic(BASE, device_id))
    follower.gateway.reconnect()
    await _settle(owner, follower)
    assert follower.manager.sync.instance_status(owner.manager.instance_id) == "online"
    await _advance(freezer, owner, follower)

    assert device_id not in follower.manager.mirrors


@pytest.mark.parametrize("owner_first", [True, False], ids=["owner-first", "follower-first"])
async def test_wiped_broker_heals_without_pruning(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
    *,
    owner_first: bool,
) -> None:
    """T-03-21: after a wipe both reconnect; the owner republishes documents before online and nothing is pruned."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    fake_broker.wipe_retained()
    first, second = (owner, follower) if owner_first else (follower, owner)

    first.gateway.reconnect()
    await _settle(owner, follower)
    if not owner_first:
        # The follower forgot the owner's presence, so a missing document is no evidence before the owner is back
        assert follower.manager.sync.instance_status(owner.manager.instance_id) is None
        await _advance(freezer, owner, follower)
        assert device_id in follower.manager.mirrors
    second.gateway.reconnect()
    await _settle(owner, follower)
    await _advance(freezer, owner, follower, windows=2)

    assert device_id in follower.manager.mirrors
    assert device_id in owner.manager.devices
    assert config_topic(BASE, device_id) in fake_broker.retained


async def test_prune_timer_is_cancelled_on_stop(
    hass: HomeAssistant,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The prune timer never outlives the manager: stop cancels it and advancing time prunes nothing."""
    cancel = Mock()
    with patch("custom_components.mqtt_actions.sync.async_call_later", return_value=cancel) as call_later:
        owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
        assert call_later.call_count >= 1
        assert follower.manager.sync._prune_timer is not None
        sync = follower.manager.sync
        with patch.object(sync, "_async_prune", AsyncMock()) as prune:
            await follower.stop()
            assert sync._prune_timer is None
            cancel.assert_called()
            await _advance(freezer, owner)
            prune.assert_not_called()
    assert device_id not in follower.manager.mirrors


async def test_prune_only_touches_mirrors(
    hass: HomeAssistant,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Owned devices are never pruned, and a mirror of an online owner with its document seen stays."""
    sub_a = make_switch_subentry("Lamp A", on=[{"action": "test.on"}])
    sub_b = make_switch_subentry("Lamp B", on=[{"action": "test.on"}])
    id_a, id_b = sub_a["data"]["device_id"], sub_b["data"]["device_id"]
    owner_a = await make_instance("owner-a", hass=hass, subentries=[sub_a])
    owner_b = await make_instance("owner-b", subentries=[sub_b])
    await _settle(owner_a, owner_b)
    assert id_b in owner_a.manager.mirrors
    assert id_a in owner_b.manager.mirrors

    await _advance(freezer, owner_a, owner_b, windows=3)

    assert set(owner_a.manager.devices) == {id_a}
    assert set(owner_b.manager.devices) == {id_b}
    assert set(owner_a.manager.mirrors) == {id_b}
    assert set(owner_b.manager.mirrors) == {id_a}


# --- approval and execution on every instance (STA-03, TRU-01) ---------------------------------------------------


async def test_approved_mirror_runs_actions_on_both_instances(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """After the follower approved, a UI-style and an external state change run the actions on both instances."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}], off=[{"action": "test.off"}])
    device_id = sub["data"]["device_id"]
    owner = await make_instance("owner", hass=hass, subentries=[sub])
    follower = await make_instance("follower")
    owner_on = async_mock_service(owner.hass, "test", "on")
    owner_off = async_mock_service(owner.hass, "test", "off")
    follower_on = async_mock_service(follower.hass, "test", "on")
    follower_off = async_mock_service(follower.hass, "test", "off")
    await _settle(owner, follower)
    assert device_id in follower.manager.mirrors

    # Before the approval the follower runs nothing, whoever changes the state
    await follower.gateway.async_publish(state_topic(BASE, device_id), "OFF", retain=True)
    await _settle(owner, follower)
    assert (len(owner_off), len(follower_off)) == (1, 0)

    mirror = follower.manager.mirrors[device_id]
    assert mirror.mirror is not None
    assert await follower.manager.async_approve(device_id, mirror.mirror.actions_hash) is True
    await _settle(owner, follower)

    # A toggle in the UI of the follower publishes the state through its own gateway
    await follower.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower)
    assert (len(owner_on), len(follower_on)) == (1, 1)

    # An external client publishes straight to the broker
    fake_broker.publish(state_topic(BASE, device_id), "OFF", retain=True)
    await _settle(owner, follower)
    assert (len(owner_off), len(follower_off)) == (2, 1)
    assert (len(owner_on), len(follower_on)) == (1, 1)


# --- phase acceptance: the five success criteria on three instances (STA-03, SYN-04, SYN-05, SYN-06) --------------


async def _trio(
    hass: HomeAssistant,
    make_instance: Callable,
    make_switch_subentry: Callable,
    *,
    run_on_startup: bool = False,
) -> tuple[Instance, Instance, Instance, str]:
    """Start owner A, follower B and follower C of one switch device with on and off actions; return the device id."""
    sub = make_switch_subentry(
        "Lamp",
        on=[{"action": "test.on"}],
        off=[{"action": "test.off"}],
        run_on_startup=run_on_startup,
    )
    device_id = sub["data"]["device_id"]
    owner = await make_instance("owner", hass=hass, subentries=[sub])
    follower_b = await make_instance("follower-b")
    follower_c = await make_instance("follower-c")
    await _settle(owner, follower_b, follower_c)
    assert device_id in follower_b.manager.mirrors
    assert device_id in follower_c.manager.mirrors
    return owner, follower_b, follower_c, device_id


def _count_services(*instances: Instance) -> dict[str, dict[str, list]]:
    """Mock test.on, test.off and the services an edited device uses on every instance; return the call lists."""
    return {
        instance.name: {
            name: async_mock_service(instance.hass, "test", name) for name in ("on", "off", "on2", "off2", "evil")
        }
        for instance in instances
    }


def _ran(calls: dict[str, dict[str, list]], instance: Instance) -> dict[str, int]:
    """Return how many times each mocked service ran on an instance, services that never ran omitted."""
    return {name: len(items) for name, items in calls[instance.name].items() if items}


async def _approve(instance: Instance, device_id: str) -> None:
    """Approve the current actions of a mirror the way the Repairs fix flow does."""
    mirror = instance.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert await instance.manager.async_approve(device_id, mirror.actions_hash) is True
    await _settle(instance)


def _published_to(instance: Instance, topic: str, *, empty: bool = False) -> list[str]:
    """Return the payloads an instance published on a topic, only empty ones or only non-empty ones."""
    return [
        payload
        for published, payload, _ in instance.gateway.published
        if published == topic and (payload == "") == empty
    ]


def _topic_kind(topic: str) -> str | None:
    """Classify a published topic as config, discovery or availability; anything else is None."""
    if parse_config_topic(BASE, topic) is not None:
        return "config"
    if parse_discovery_topic(PREFIX, topic) is not None:
        return "discovery"
    if parse_availability_topic(BASE, topic) is not None:
        return "availability"
    return None


def _publish_order(instance: Instance) -> list[str]:
    """Return the kinds of the non-empty config, discovery and availability publishes of an instance, in order."""
    kinds = [_topic_kind(topic) for topic, payload, _ in instance.gateway.published if payload]
    return [kind for kind in kinds if kind is not None]


def _device_topics(fake_broker: FakeBroker, device_id: str) -> list[str]:
    """Return the retained topics on the broker that belong to a device."""
    return [topic for topic in fake_broker.retained if device_id in topic]


async def test_fanout_runs_on_every_approved_instance_and_only_there(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
) -> None:
    """STA-03: a UI toggle and an external message run once on the owner and the approving follower, never on C."""
    owner, follower_b, follower_c, device_id = await _trio(
        hass, make_instance, make_switch_subentry, run_on_startup=True
    )
    calls = _count_services(owner, follower_b, follower_c)
    await _approve(follower_b, device_id)

    # A toggle in the UI of B publishes through B's gateway
    await follower_b.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower_b, follower_c)
    # An external client publishes straight to the broker
    fake_broker.publish(state_topic(BASE, device_id), "OFF", retain=True)
    await _settle(owner, follower_b, follower_c)

    assert _ran(calls, owner) == {"on": 1, "off": 1}
    assert _ran(calls, follower_b) == {"on": 1, "off": 1}
    assert _ran(calls, follower_c) == {}

    # The test button of C publishes on the test topic: it runs where the device is approved, and never on C itself
    await follower_c.gateway.async_publish(press_topic(BASE, device_id), "ON", retain=False)
    await _settle(owner, follower_b, follower_c)
    assert _ran(calls, owner) == {"on": 2, "off": 1}
    assert _ran(calls, follower_b) == {"on": 2, "off": 1}
    assert _ran(calls, follower_c) == {}

    # The device has run-on-startup: the restart of the unapproved mirror still runs nothing
    await follower_c.restart()
    await _settle(owner, follower_b, follower_c)
    assert device_id in follower_c.manager.mirrors
    assert _ran(calls, follower_c) == {}


async def test_owner_edit_requires_reapproval_on_followers(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable, fake_broker: FakeBroker
) -> None:
    """D-02: the owner edits the actions; the follower's mirror updates, pauses, asks again and runs after approval."""
    owner, follower, _, device_id = await _trio(hass, make_instance, make_switch_subentry)
    calls = _count_services(owner, follower)
    await _approve(follower, device_id)
    old_hash = follower.manager.mirrors[device_id].mirror.actions_hash

    subentry = next(iter(owner.entry.subentries.values()))
    owner.hass.config_entries.async_update_subentry(
        owner.entry,
        subentry,
        data={
            **subentry.data,
            CONF_ON_CHANGE_TO_ON: [{"action": "test.on2"}],
            CONF_ON_CHANGE_TO_OFF: [{"action": "test.off2"}],
        },
    )
    await owner.manager.async_reconcile()
    await _settle(owner, follower)

    new_hash = follower.manager.mirrors[device_id].mirror.actions_hash
    assert new_hash != old_hash
    issue = ir.async_get(follower.hass).async_get_issue(DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{device_id}")
    assert issue is not None
    assert issue.data == {"device_id": device_id, "actions_hash": new_hash}
    fake_broker.publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower)
    assert _ran(calls, owner) == {"on2": 1}
    assert _ran(calls, follower) == {}

    await _approve(follower, device_id)
    assert ir.async_get(follower.hass).async_get_issue(DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{device_id}") is None
    fake_broker.publish(state_topic(BASE, device_id), "OFF", retain=True)
    await _settle(owner, follower)

    assert _ran(calls, owner) == {"on2": 1, "off2": 1}
    assert _ran(calls, follower) == {"off2": 1}


async def test_first_start_publishes_documents_before_availability(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """SYN-04: on the very first start every config publish precedes the online availability publish."""
    subentries = [
        make_switch_subentry("Lamp A", on=[{"action": "test.on"}]),
        make_switch_subentry("Lamp B", on=[{"action": "test.on"}]),
    ]
    owner = await make_instance("owner", hass=hass, subentries=subentries)
    await _settle(owner)

    order = _publish_order(owner)
    assert order.count("config") == 2
    assert order.count("availability") == 1
    assert order[-1] == "availability"
    last_config = max(index for index, kind in enumerate(order) if kind == "config")
    first_availability = order.index("availability")
    assert last_config < first_availability
    assert owner.gateway.published[-1][1] == "online"


async def test_reconnect_republishes_config_before_availability(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """SYN-04: after a reconnect the owner publishes all documents, then all discovery payloads, then online."""
    subentries = [
        make_switch_subentry("Lamp A", on=[{"action": "test.on"}]),
        make_switch_subentry("Lamp B", on=[{"action": "test.on"}]),
    ]
    owner = await make_instance("owner", hass=hass, subentries=subentries)
    follower = await make_instance("follower")
    await _settle(owner, follower)
    owner.gateway.published.clear()

    owner.gateway.reconnect()
    await _settle(owner, follower)

    assert _publish_order(owner) == ["config", "config", "discovery", "discovery", "availability"]
    assert owner.gateway.published[-1][1] == "online"


async def test_reconnect_after_a_wiped_broker_heals_and_followers_keep_mirrors(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """SYN-04, SYN-05, D-19: after a wipe the owner heals the broker and no follower removes or un-approves a mirror."""
    owner, follower, _, device_id = await _trio(hass, make_instance, make_switch_subentry)
    calls = _count_services(owner, follower)
    await _approve(follower, device_id)
    approved_hash = follower.manager.mirrors[device_id].mirror.actions_hash
    mirror = follower.manager.mirrors[device_id]
    fake_broker.wipe_retained()

    owner.gateway.reconnect()
    follower.gateway.reconnect()
    await _settle(owner, follower)
    await _advance(freezer, owner, follower, windows=3)

    assert config_topic(BASE, device_id) in fake_broker.retained
    assert discovery_topic(PREFIX, device_id) in fake_broker.retained
    assert fake_broker.retained[availability_topic(BASE, owner.manager.instance_id)] == "online"
    assert json.loads(fake_broker.retained[config_topic(BASE, device_id)])["owner"] == owner.manager.instance_id
    assert follower.manager.mirrors[device_id] is mirror
    assert follower.manager._approvals[device_id] == approved_hash
    assert ir.async_get(follower.hass).async_get_issue(DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{device_id}") is None

    # The approved Script survived: an external change still runs the actions on both instances
    fake_broker.publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower)
    assert _ran(calls, owner) == {"on": 1}
    assert _ran(calls, follower) == {"on": 1}


async def test_owner_offline_follower_still_runs_actions(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-19: with the owner offline an approved mirror runs its actions for external changes and is never pruned."""
    owner, follower, _, device_id = await _trio(hass, make_instance, make_switch_subentry)
    calls = _count_services(owner, follower)
    await _approve(follower, device_id)

    await owner.stop()
    await _settle(owner, follower)
    assert fake_broker.retained[availability_topic(BASE, owner.manager.instance_id)] == "offline"
    fake_broker.publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower)
    await _advance(freezer, owner, follower, windows=3)

    assert _ran(calls, owner) == {}
    assert _ran(calls, follower) == {"on": 1}
    assert device_id in follower.manager.mirrors
    assert follower.manager._approvals[device_id] == follower.manager.mirrors[device_id].mirror.actions_hash


async def test_delete_removes_the_device_everywhere(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """SYN-06, success criterion 5: after the owner deleted a device nobody keeps it and the broker holds nothing."""
    owner, follower_b, follower_c, device_id = await _trio(hass, make_instance, make_switch_subentry)
    await _approve(follower_b, device_id)
    await follower_b.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower_b, follower_c)
    assert {config_topic(BASE, device_id), discovery_topic(PREFIX, device_id), state_topic(BASE, device_id)} <= set(
        fake_broker.retained
    )
    approval_issue = f"{ISSUE_APPROVAL_PREFIX}{device_id}"
    assert ir.async_get(follower_c.hass).async_get_issue(DOMAIN, approval_issue) is not None

    await _owner_deletes(owner)
    await _settle(owner, follower_b, follower_c)

    assert device_id not in owner.manager.devices
    for follower in (follower_b, follower_c):
        assert device_id not in follower.manager.mirrors
        assert device_id not in follower.manager._approvals
        assert follower.manager.runner.script_count(device_id) == 0
        assert ir.async_get(follower.hass).async_get_issue(DOMAIN, approval_issue) is None
    for topic in (config_topic(BASE, device_id), discovery_topic(PREFIX, device_id), state_topic(BASE, device_id)):
        assert topic not in fake_broker.retained
    assert _device_topics(fake_broker, device_id) == []


async def test_ownership_conflict_between_three_instances(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-17: a second claimant changes no mirror, the owner heals with bounded republishes and reports the claim."""
    owner, follower, claimant, device_id = await _trio(hass, make_instance, make_switch_subentry)
    follower_events = async_capture_events(follower.hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)
    pinned_spec = follower.manager.mirrors[device_id].spec
    pinned_owner = follower.manager.mirrors[device_id].mirror.owner
    assert pinned_owner == owner.manager.instance_id
    owner.gateway.published.clear()

    for revision in range(1, 5):
        spec = make_spec(device_id=device_id, name="Lamp", on=[{"action": "test.evil"}], off=[])
        payload = document_payload(
            spec, owner=claimant.manager.instance_id, owner_name="Claimant", rev=revision, tamper=None
        )
        await claimant.gateway.async_publish(config_topic(BASE, device_id), payload, retain=True)
        await _settle(owner, follower, claimant)

    conflict_events = [
        event.data
        for event in follower_events
        if event.data["action"] == "create" and event.data["issue_id"] == f"{ISSUE_OWNER_CONFLICT_PREFIX}{device_id}"
    ]
    assert len(conflict_events) >= 1
    assert follower.manager.mirrors[device_id].spec == pinned_spec
    assert follower.manager.mirrors[device_id].mirror.owner == pinned_owner
    assert ir.async_get(owner.hass).async_get_issue(DOMAIN, f"{ISSUE_OWNERSHIP_CLAIM_PREFIX}{device_id}") is not None

    # Four forged writes inside one throttle window: one republish at once and one trailing republish at most
    await _advance(freezer, owner, follower, claimant, windows=REPUBLISH_THROTTLE_SECONDS / PRUNE_GRACE_SECONDS)
    assert len(_published_to(owner, config_topic(BASE, device_id))) <= 2
    assert json.loads(fake_broker.retained[config_topic(BASE, device_id)])["owner"] == owner.manager.instance_id
    assert follower.manager.mirrors[device_id].spec == pinned_spec
    assert device_id in owner.manager.devices


async def test_forged_tombstone_followers_recover_unapproved(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: an external empty retained message removes the mirror, the owner heals it, and it needs a new approval."""
    owner, follower, _, device_id = await _trio(hass, make_instance, make_switch_subentry)
    calls = _count_services(owner, follower)
    await _approve(follower, device_id)

    fake_broker.publish(config_topic(BASE, device_id), "", retain=True)
    await _settle(owner, follower)

    assert json.loads(fake_broker.retained[config_topic(BASE, device_id)])["owner"] == owner.manager.instance_id
    assert device_id in follower.manager.mirrors
    assert device_id not in follower.manager._approvals
    assert ir.async_get(follower.hass).async_get_issue(DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{device_id}") is not None
    fake_broker.publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower)
    assert _ran(calls, owner) == {"on": 1}
    assert _ran(calls, follower) == {}

    await _approve(follower, device_id)
    fake_broker.publish(state_topic(BASE, device_id), "OFF", retain=True)
    await _settle(owner, follower)
    assert _ran(calls, follower) == {"off": 1}


async def test_follower_entity_deletion_heals_the_discovery(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-18: an empty discovery payload of a follower makes the owner republish once per window plus one trailing."""
    owner, follower, _, device_id = await _trio(hass, make_instance, make_switch_subentry)
    topic = discovery_topic(PREFIX, device_id)
    owner.gateway.published.clear()

    # What core MQTT does on the follower when its entity of the device is deleted
    for _ in range(3):
        await follower.gateway.async_publish(topic, "", retain=True)
        await _settle(owner, follower)
        assert topic in fake_broker.retained or len(_published_to(owner, topic)) == 1
    assert len(_published_to(owner, topic)) == 1

    await _advance(freezer, owner, follower, windows=REPUBLISH_THROTTLE_SECONDS / PRUNE_GRACE_SECONDS)
    assert len(_published_to(owner, topic)) == 2
    assert topic in fake_broker.retained

    await _advance(freezer, owner, follower, windows=REPUBLISH_THROTTLE_SECONDS / PRUNE_GRACE_SECONDS)
    assert len(_published_to(owner, topic)) == 2


async def test_hub_removal_delete_clears_everywhere_for_followers(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-11: hub removal with deletion leaves nothing retained for the owner's devices and removes the mirrors."""
    owner, follower_b, follower_c, device_id = await _trio(hass, make_instance, make_switch_subentry)
    await follower_b.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower_b, follower_c)
    owner_id = owner.manager.instance_id

    await owner.stop()
    await async_remove_all_devices(owner.hass, owner.entry, gateway=owner.gateway, store_key=owner.store_key)
    await _settle(owner, follower_b, follower_c)

    assert _device_topics(fake_broker, device_id) == []
    assert availability_topic(BASE, owner_id) not in fake_broker.retained
    assert [topic for topic in fake_broker.retained if owner_id in topic] == []
    for follower in (follower_b, follower_c):
        assert device_id not in follower.manager.mirrors


async def test_hub_removal_keep_leaves_orphans_that_followers_keep(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """D-11, D-10: hub removal with keep publishes no clear; followers keep the orphans, also after a restart."""
    owner, follower_b, follower_c, device_id = await _trio(hass, make_instance, make_switch_subentry)
    await follower_b.gateway.async_publish(state_topic(BASE, device_id), "ON", retain=True)
    await _settle(owner, follower_b, follower_c)
    owner_id = owner.manager.instance_id
    published_before = len(owner.gateway.published)

    await owner.stop()
    await async_remove_local_state(owner.hass, owner.entry, store_key=owner.store_key)
    await _settle(owner, follower_b, follower_c)

    assert [item for item in owner.gateway.published[published_before:] if item[1] == ""] == []
    assert {config_topic(BASE, device_id), discovery_topic(PREFIX, device_id), state_topic(BASE, device_id)} <= set(
        fake_broker.retained
    )
    assert fake_broker.retained[availability_topic(BASE, owner_id)] == "offline"
    await follower_b.restart()
    await _settle(owner, follower_b, follower_c)
    await _advance(freezer, owner, follower_b, follower_c, windows=3)

    for follower in (follower_b, follower_c):
        assert device_id in follower.manager.mirrors
    assert fake_broker.retained[availability_topic(BASE, owner_id)] == "offline"


async def test_foreign_claim_replayed_during_startup_never_becomes_a_mirror(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CR-02: a retained claim for an owned id that arrives while the start subscribes is not turned into a mirror."""
    from tests.fake_broker import FakeGateway

    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"]["device_id"]
    forged = make_spec(device_id=device_id, name="Lamp", on=[{"action": "test.evil"}])
    fake_broker.retained[config_topic(BASE, device_id)] = document_payload(forged, owner="instance-foreign")
    original = FakeGateway.async_subscribe

    async def _yielding_subscribe(self: FakeGateway, *args: Any, **kwargs: Any) -> Any:
        # A real network subscribe yields to the loop, so replayed messages and their ingest tasks run before it returns
        unsubscribe = await original(self, *args, **kwargs)
        for _ in range(5):
            await asyncio.sleep(0)
        return unsubscribe

    monkeypatch.setattr(FakeGateway, "async_subscribe", _yielding_subscribe)

    owner = await make_instance("owner", hass=hass, subentries=[sub])
    await _settle(owner)

    assert device_id in owner.manager.devices
    assert device_id not in owner.manager.mirrors
    assert owner.manager.runner.script_count(device_id) == 1
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{device_id}") is None


@pytest.mark.parametrize("field", ["device", "instance"])
async def test_overlong_name_is_not_published_and_never_loops(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    field: str,
) -> None:
    """CR-03: a name followers would reject is not published, so there is no false overwrite and no republish loop."""
    sub = make_switch_subentry("x" * 70 if field == "device" else "Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"]["device_id"]
    data = None
    if field == "instance":
        data = {"base_topic": BASE, "instance_name": "n" * 70, "instance_id": "owner-id"}
    owner = await make_instance("owner", hass=hass, subentries=[sub], data=data)
    await _settle(owner)

    assert config_topic(BASE, device_id) not in fake_broker.retained
    assert [item for item in owner.gateway.published if item[0] == config_topic(BASE, device_id)] == []
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"doc_overwritten_{device_id}") is None
