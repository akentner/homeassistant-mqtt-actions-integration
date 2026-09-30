"""Two real Home Assistant instances on one fake broker: the owner runs its actions, the follower only mirrors."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.mqtt_actions.const import PRUNE_GRACE_SECONDS, STORE_KEY, STORE_MIRRORS
from custom_components.mqtt_actions.topics import availability_topic, config_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

    from tests.fake_broker import FakeBroker, Instance

BASE = "mqtt_actions"


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
