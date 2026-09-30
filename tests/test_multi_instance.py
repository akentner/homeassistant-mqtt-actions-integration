"""Two real Home Assistant instances on one fake broker: the owner runs its actions, the follower only mirrors."""

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.mqtt_actions.topics import state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

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
