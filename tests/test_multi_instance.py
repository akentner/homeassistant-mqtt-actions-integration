"""Two real Home Assistant instances on one fake broker: the owner runs its actions, the follower only mirrors."""

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.mqtt_actions.topics import state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BASE = "mqtt_actions"


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
