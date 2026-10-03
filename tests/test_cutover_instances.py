"""The cutover to native entities across two real instances on one broker (D-09, D-10, D-12, MIG-02, ENT-02)."""

import json
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.mqtt_actions.const import DOMAIN
from custom_components.mqtt_actions.presence import parse_heartbeat
from custom_components.mqtt_actions.topics import (
    availability_topic,
    config_topic,
    discovery_topic,
    heartbeat_topic,
    state_topic,
)
from tests.documents import heartbeat_payload

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from tests.fake_broker import FakeBroker, Instance

pytestmark = pytest.mark.multi_instance

BASE = "mqtt_actions"
PREFIX = "homeassistant"
SETTLE_PASSED = 6.0  # a little more than CUTOVER_SETTLE_SECONDS
MIGRATE = '{"migrate_discovery":true}'  # the compact text json_dumps of Home Assistant writes


async def _settle(*instances: Instance) -> None:
    """Let every instance finish the messages, background tasks and reloads the broker caused."""
    for _ in range(3):
        for instance in instances:
            await instance.hass.async_block_till_done(wait_background_tasks=True)


async def _pass_time(*instances: Instance, seconds: float = SETTLE_PASSED) -> None:
    """Let time pass for the timers of every instance; they share one event loop, so one call fires them all."""
    async_fire_time_changed(instances[0].hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await _settle(*instances)


def _discovery_publishes(instance: Instance, device_id: str, start: int = 0) -> list[tuple[str, bool]]:
    topic = discovery_topic(PREFIX, device_id)
    return [(payload, retain) for t, payload, retain in instance.gateway.published[start:] if t == topic]


async def _owner_and_follower(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable
) -> tuple[Instance, Instance, str]:
    """Start an owner of one device with actions and a follower with the approved mirror of it, both on real setups."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}], off=[{"action": "test.off"}])
    device_id = sub["data"]["device_id"]
    owner = await make_instance("owner", hass=hass, subentries=[sub], real_setup=True)
    follower = await make_instance("follower", real_setup=True)
    await _settle(owner, follower)
    assert device_id in follower.manager.mirrors
    info = follower.manager.mirrors[device_id].mirror
    assert info is not None
    assert await follower.manager.async_approve(device_id, info.actions_hash)
    return owner, follower, device_id


async def _cut_over(owner: Instance, follower: Instance, device_id: str) -> list[tuple[str, bool]]:
    """Let the settle time pass; the owner switches and the follower follows. Return the owner's discovery publishes."""
    start = len(owner.gateway.published)
    reloads = patch.object(
        follower.hass.config_entries, "async_schedule_reload", wraps=follower.hass.config_entries.async_schedule_reload
    )
    with reloads as follower_reloads:
        await _pass_time(owner, follower)
        assert follower_reloads.call_count == 1
        follower_reloads.assert_called_once_with(follower.entry.entry_id)
    return _discovery_publishes(owner, device_id, start)


async def test_the_owner_cuts_over_and_a_running_follower_follows(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-09, D-12, MIG-02: the owner switches, its marked document makes the follower reload into native entities."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    discovery = discovery_topic(PREFIX, device_id)
    assert discovery in fake_broker.retained
    old_follower_manager = follower.manager

    publishes = await _cut_over(owner, follower, device_id)

    assert owner.manager.is_native(device_id)
    assert publishes == [(MIGRATE, False), ("", True)]
    assert discovery not in fake_broker.retained
    assert json.loads(fake_broker.retained[config_topic(BASE, device_id)])["entities"] == "native"
    assert follower.manager is not old_follower_manager
    mirror = follower.manager.mirrors[device_id]
    assert mirror.mirror is not None
    assert mirror.mirror.native
    assert follower.manager.is_native(device_id)
    assert er.async_get(follower.hass).async_get_entity_id("switch", DOMAIN, device_id) is not None
    assert er.async_get(owner.hass).async_get_entity_id("switch", DOMAIN, device_id) is not None


async def test_a_legacy_peer_online_blocks_the_owner_and_going_offline_releases_it(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """D-10: a v0.1.0-shaped online peer keeps the owner legacy; its offline announcement releases it at once."""
    sub = make_switch_subentry("Lamp")
    device_id = sub["data"]["device_id"]
    owner = await make_instance("owner", hass=hass, subentries=[sub], real_setup=True)
    peer = "legacy-peer"
    fake_broker.publish(availability_topic(BASE, peer), "online", retain=True)
    fake_broker.publish(heartbeat_topic(BASE, peer), heartbeat_payload(peer, native=False), retain=False)
    await _settle(owner)

    await _pass_time(owner)

    assert not owner.manager.is_native(device_id)
    assert all("migrate" not in payload for payload, _retain in _discovery_publishes(owner, device_id))
    assert discovery_topic(PREFIX, device_id) in fake_broker.retained
    start = len(owner.gateway.published)

    fake_broker.publish(availability_topic(BASE, peer), "offline", retain=True)
    await _settle(owner)

    assert owner.manager.is_native(device_id)
    assert _discovery_publishes(owner, device_id, start) == [(MIGRATE, False), ("", True)]
    assert discovery_topic(PREFIX, device_id) not in fake_broker.retained


async def test_a_native_toggle_runs_the_actions_on_every_instance(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    enable_native_cutover: None,
) -> None:
    """STA-01, STA-03, STA-07 through ENT-02: one toggle, one retained QoS 1 publish, one run per instance."""
    owner, follower, device_id = await _owner_and_follower(hass, make_instance, make_switch_subentry)
    await _cut_over(owner, follower, device_id)
    owner_on = async_mock_service(owner.hass, "test", "on")
    follower_on = async_mock_service(follower.hass, "test", "on")
    owner_off = async_mock_service(owner.hass, "test", "off")
    follower_off = async_mock_service(follower.hass, "test", "off")
    owner_switch = er.async_get(owner.hass).async_get_entity_id("switch", DOMAIN, device_id)
    follower_switch = er.async_get(follower.hass).async_get_entity_id("switch", DOMAIN, device_id)
    assert owner_switch is not None
    assert follower_switch is not None
    topic = state_topic(BASE, device_id)
    start = len(follower.gateway.published)

    await follower.hass.services.async_call("switch", "turn_on", {"entity_id": follower_switch}, blocking=True)
    await _settle(owner, follower)

    published = [
        (p, r, q) for (t, p, r), q in zip(follower.gateway.published, follower.gateway.qos, strict=True) if t == topic
    ]
    assert published[-1] == ("ON", True, 1)
    assert len(follower.gateway.published) > start
    assert (len(owner_on), len(follower_on)) == (1, 1)
    assert owner.hass.states.get(owner_switch).state == "on"
    assert follower.hass.states.get(follower_switch).state == "on"

    await follower.gateway.async_publish(topic, "bogus", retain=True)
    await _settle(owner, follower)

    assert (len(owner_on), len(follower_on)) == (1, 1)
    assert (len(owner_off), len(follower_off)) == (0, 0)
    assert owner.hass.states.get(owner_switch).state == "on"
    assert follower.hass.states.get(follower_switch).state == "on"


def test_the_peer_helpers_build_the_two_generations() -> None:
    """D-10: a heartbeat without the capability has no entities key, with it the key says native."""
    old = json.loads(heartbeat_payload("peer"))
    new = json.loads(heartbeat_payload("peer", native=True))

    assert "entities" not in old
    assert new["entities"] == "native"
    topic = heartbeat_topic(BASE, "peer")
    assert parse_heartbeat(BASE, topic, heartbeat_payload("peer")).native is False
    assert parse_heartbeat(BASE, topic, heartbeat_payload("peer", native=True)).native is True
