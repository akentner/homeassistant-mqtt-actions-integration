"""Operations scenarios of several real instances on one fake broker: presence and the roster (OPS-03)."""

import json
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_OFFLINE_SECONDS,
    SIGNAL_ROSTER_UPDATED,
)
from custom_components.mqtt_actions.topics import availability_topic, heartbeat_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from tests.fake_broker import FakeBroker, Instance

pytestmark = pytest.mark.multi_instance

BASE = "mqtt_actions"


async def _settle(*instances: Instance) -> None:
    """Let every instance finish the messages and background tasks the broker delivered."""
    for _ in range(2):
        for instance in instances:
            await instance.hass.async_block_till_done(wait_background_tasks=True)


async def test_instances_see_each_other_through_heartbeats(
    hass: HomeAssistant, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-05: a heartbeat of A puts A into the roster of B with its id, name, version and device count."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    b = await make_instance("beta")
    await _settle(a, b)

    await a.manager.presence.async_publish_heartbeat()
    await _settle(a, b)

    rows = {row["id"]: row for row in b.manager.presence.rows()}
    row = rows[a.manager.instance_id]
    assert row["name"] == "alpha"
    assert row["version"] == a.manager.version
    assert row["devices"] == 1
    assert row["online"] is True
    assert b.manager.presence.online_count() == 2
    sent = [item for item in a.gateway.published if item[0] == heartbeat_topic(BASE, a.manager.instance_id)]
    assert sent
    assert all(retain is False for _topic, _payload, retain in sent)


PEER = "peer-instance"
SESSION = "6f1c0f0e-3a52-4f43-8d0c-5a0b7f3c9d21"


def _peer_heartbeat(fake_broker: FakeBroker) -> None:
    """Publish a live heartbeat of a synthetic peer that is not a running instance, so nothing refreshes it."""
    payload = json.dumps({"instance_id": PEER, "name": "Peer", "version": "0.1.0", "devices": 3, "session": SESSION})
    fake_broker.publish(heartbeat_topic(BASE, PEER), payload, retain=False)


def _use_clock(instance: Instance) -> list[float]:
    """Replace the manager clock with a settable one; the returned list holds its single value."""
    now = [1000.0]
    instance.manager.clock = lambda: now[0]
    return now


async def _fire(instance: Instance, seconds: float) -> None:
    async_fire_time_changed(instance.hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await _settle(instance)


def _peer_online(instance: Instance, peer_id: str = PEER) -> bool | None:
    rows = {row["id"]: row for row in instance.manager.presence.rows()}
    return None if peer_id not in rows else rows[peer_id]["online"]


async def test_roster_marks_a_peer_offline_after_90_seconds(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable
) -> None:
    """D-05: online at 89 seconds, offline at 91 even though its retained availability still says online."""
    b = await make_instance("beta", hass=hass)
    now = _use_clock(b)
    fake_broker.publish(availability_topic(BASE, PEER), "online", retain=True)
    signals: list[None] = []
    async_dispatcher_connect(b.hass, SIGNAL_ROSTER_UPDATED.format(b.entry.entry_id), lambda: signals.append(None))
    _peer_heartbeat(fake_broker)
    await _settle(b)
    assert _peer_online(b) is True
    assert len(signals) == 1

    now[0] += HEARTBEAT_OFFLINE_SECONDS - 1
    await _fire(b, HEARTBEAT_OFFLINE_SECONDS - 1)
    assert _peer_online(b) is True
    assert b.manager.presence.online_count() == 2
    assert len(signals) == 1

    now[0] += 2
    await _fire(b, HEARTBEAT_OFFLINE_SECONDS + 5)
    assert _peer_online(b) is False
    assert b.manager.presence.online_count() == 1
    assert b.manager.presence.peer_status(PEER) == "offline"
    assert len(signals) == 2

    _peer_heartbeat(fake_broker)
    await _settle(b)
    assert _peer_online(b) is True
    assert len(signals) == 3


async def test_clean_shutdown_marks_the_peer_offline_at_once(hass: HomeAssistant, make_instance: Callable) -> None:
    """The offline availability of a stopping instance turns its roster row offline without the 90 second wait."""
    a = await make_instance("alpha", hass=hass)
    b = await make_instance("beta")
    await _settle(a, b)
    await a.manager.presence.async_publish_heartbeat()
    await _settle(a, b)
    assert _peer_online(b, a.manager.instance_id) is True
    signals: list[None] = []
    async_dispatcher_connect(b.hass, SIGNAL_ROSTER_UPDATED.format(b.entry.entry_id), lambda: signals.append(None))

    await a.stop()
    await _settle(a, b)

    assert _peer_online(b, a.manager.instance_id) is False
    assert b.manager.presence.online_count() == 1
    assert b.manager.presence.owner_offline(a.manager.instance_id) is True
    assert signals


async def test_rows_survive_a_reconnect(hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable) -> None:
    """The peer rows stay across a reconnect and the instance publishes a heartbeat again."""
    b = await make_instance("beta", hass=hass)
    _peer_heartbeat(fake_broker)
    await _settle(b)
    topic = heartbeat_topic(BASE, b.manager.instance_id)
    before = len([item for item in b.gateway.published if item[0] == topic])

    b.gateway.reconnect()
    await _settle(b)

    assert _peer_online(b) is True
    assert len([item for item in b.gateway.published if item[0] == topic]) == before + 1
    assert b.gateway.published[-1][0] == topic


async def test_heartbeat_tick_keeps_the_roster_fresh_for_running_peers(
    hass: HomeAssistant, make_instance: Callable
) -> None:
    """Two running instances publish on the tick, so neither turns the other offline."""
    a = await make_instance("alpha", hass=hass)
    b = await make_instance("beta")
    now_b = _use_clock(b)
    await _settle(a, b)
    await a.manager.presence.async_publish_heartbeat()
    await _settle(a, b)

    for _ in range(4):
        now_b[0] += HEARTBEAT_INTERVAL_SECONDS
        await _fire(b, HEARTBEAT_INTERVAL_SECONDS * 1.0)
        async_fire_time_changed(a.hass, dt_util.utcnow() + timedelta(seconds=HEARTBEAT_INTERVAL_SECONDS * 4))
        await _settle(a, b)

    assert _peer_online(b, a.manager.instance_id) is True


async def test_leaving_disabled_rebaselines_without_running(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-20: the retained value that changed while disabled is a baseline on return, never a run (A17)."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}], off=[{"action": "test.off"}], run_on_startup=True)
    device_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    device = a.manager.devices[device_id]
    topic = state_topic(BASE, device_id)
    assert device.tracker.startup_pending is True

    await a.manager.async_set_device_mode(device_id, "disabled")
    fake_broker.publish(topic, "OFF", retain=True)
    await _settle(a)
    assert device.tracker.last_acted is None
    assert device.tracker.startup_pending is True

    await a.manager.async_set_device_mode(device_id, "run")
    await _settle(a)

    # The replay of the retained OFF moved the baseline only, although run_on_startup is on
    assert device.tracker.last_acted == "OFF"
    assert device.tracker.startup_pending is False
    assert (len(on_calls), len(off_calls)) == (0, 0)

    fake_broker.publish(topic, "ON", retain=True)
    await _settle(a)
    assert (len(on_calls), len(off_calls)) == (1, 0)


async def test_leaving_disabled_without_retained_state_counts_the_next_live_change(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """A17: with nothing retained to replay, the first live message after disabled is a real change."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    topic = state_topic(BASE, device_id)
    fake_broker.publish(topic, "ON", retain=False)
    await _settle(a)
    assert len(on_calls) == 1
    assert a.manager.devices[device_id].tracker.last_acted == "ON"

    await a.manager.async_set_device_mode(device_id, "disabled")
    await a.manager.async_set_device_mode(device_id, "run")
    await _settle(a)
    assert a.manager.devices[device_id].tracker.last_acted is None

    fake_broker.publish(topic, "ON", retain=False)
    await _settle(a)
    assert len(on_calls) == 2
