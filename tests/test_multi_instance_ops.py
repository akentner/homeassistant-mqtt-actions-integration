"""Operations scenarios of several real instances on one fake broker: presence and the roster (OPS-03)."""

import asyncio
import json
import time
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.mqtt_actions import retrigger as retrigger_module
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_OFFLINE_SECONDS,
    SIGNAL_ROSTER_UPDATED,
)
from custom_components.mqtt_actions.topics import (
    acks_topic,
    availability_topic,
    heartbeat_topic,
    retrigger_topic,
    state_topic,
)

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


# --- re-trigger (OPS-01, OPS-02, D-01 to D-04) -------------------------------------------------------------------


async def _approved_pair(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> tuple[Instance, Instance, str, dict[str, list]]:
    """
    Start owner A and follower B of one switch with ON and OFF actions; B approved it and both baselines are ON.

    Both instances know each other through a heartbeat. The returned dict holds the service call lists by name.
    """
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}], off=[{"action": "test.off"}])
    device_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    b = await make_instance("beta")
    calls = {
        "a_on": async_mock_service(a.hass, "test", "on"),
        "a_off": async_mock_service(a.hass, "test", "off"),
        "b_on": async_mock_service(b.hass, "test", "on"),
        "b_off": async_mock_service(b.hass, "test", "off"),
    }
    await _settle(a, b)
    mirror = b.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert await b.manager.async_approve(device_id, mirror.actions_hash) is True
    fake_broker.publish(state_topic(BASE, device_id), "ON", retain=True)
    await a.manager.presence.async_publish_heartbeat()
    await b.manager.presence.async_publish_heartbeat()
    await _settle(a, b)
    assert (len(calls["a_on"]), len(calls["b_on"])) == (1, 1)
    return a, b, device_id, calls


def _device_snapshot(instance: Instance, device_id: str) -> tuple[object, ...]:
    """Return what a re-trigger must never change on one instance: baseline, breaker and the published revision."""
    device = instance.manager.device(device_id)
    assert device is not None
    return (
        device.tracker.last_acted,
        device.breaker.tripped,
        list(device.breaker._stamps),
        instance.manager.revision(device_id),
    )


async def test_retrigger_runs_approved_instances_and_touches_no_state(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-01, D-02: both instances run the ON actions once, acknowledge, and no state, baseline or breaker moves."""
    a, b, device_id, calls = await _approved_pair(hass, fake_broker, make_instance, make_switch_subentry)
    topic = state_topic(BASE, device_id)
    before = (_device_snapshot(a, device_id), _device_snapshot(b, device_id), dict(fake_broker.retained))
    published_before = len(a.gateway.published) + len(b.gateway.published)

    result = await a.manager.retrigger.async_retrigger(device_id)
    await _settle(a, b)

    assert (len(calls["a_on"]), len(calls["b_on"])) == (2, 2)
    assert (len(calls["a_off"]), len(calls["b_off"])) == (0, 0)
    assert result["uuid"] == device_id
    assert result["state"] == "ON"
    answers = {entry["instance_id"]: entry["status"] for entry in result["instances"]}
    assert answers == {a.manager.instance_id: "executed", b.manager.instance_id: "executed"}
    after = (_device_snapshot(a, device_id), _device_snapshot(b, device_id), dict(fake_broker.retained))
    assert after[:2] == before[:2]
    assert after[2][topic] == before[2][topic] == "ON"
    assert after[2].keys() == before[2].keys()
    published = [*a.gateway.published, *b.gateway.published][published_before:]
    assert all(published_topic != topic for published_topic, _payload, _retain in published)
    assert all(retain is False for _topic, _payload, retain in published)


async def test_retrigger_returns_before_the_window_when_everyone_answered(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-03: the caller leaves the 5 second window as soon as every expected instance answered."""
    a, b, device_id, _calls = await _approved_pair(hass, fake_broker, make_instance, make_switch_subentry)
    started = time.monotonic()

    result = await a.manager.retrigger.async_retrigger(device_id)

    assert time.monotonic() - started < 2
    assert {entry["status"] for entry in result["instances"]} == {"executed"}
    await _settle(a, b)


async def test_roster_offline_and_silent_instances_are_no_answer(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-03: offline roster instances and silent online ones are no_answer, and foreign acknowledgements are ignored."""
    a, b, device_id, _calls = await _approved_pair(hass, fake_broker, make_instance, make_switch_subentry)
    now = _use_clock(a)
    _peer_heartbeat(fake_broker)
    await _settle(a, b)
    assert _peer_online(a) is True
    # The peer grows stale, beta stays fresh through a new heartbeat, and its coordinator stops answering
    now[0] += HEARTBEAT_OFFLINE_SECONDS + 10
    await _fire(a, HEARTBEAT_OFFLINE_SECONDS + 10)
    await b.manager.presence.async_publish_heartbeat()
    await _settle(a, b)
    assert _peer_online(a) is False
    assert _peer_online(a, b.manager.instance_id) is True
    b.manager.retrigger.async_stop()

    with patch.object(retrigger_module, "RETRIGGER_ACK_WINDOW_SECONDS", 0.6):
        task = asyncio.create_task(a.manager.retrigger.async_retrigger(device_id))
        topic = retrigger_topic(BASE, device_id)
        for _ in range(100):
            sent = [payload for published, payload, _retain in a.gateway.published if published == topic]
            if sent:
                break
            await asyncio.sleep(0.01)
        request_id = json.loads(sent[0])["request_id"]
        # Answers of beta for another request, and for another device, must not count as its answer
        for forged_request, forged_device in ((str(uuid.uuid4()), device_id), (request_id, str(uuid.uuid4()))):
            forged = {
                "request_id": forged_request,
                "device_id": forged_device,
                "instance_id": b.manager.instance_id,
                "instance_name": "beta",
                "status": "executed",
            }
            fake_broker.publish(acks_topic(BASE, a.manager.instance_id), json.dumps(forged), retain=False)
        started = time.monotonic()
        result = await task

    assert time.monotonic() - started < 2
    entries = {entry["instance_id"]: entry for entry in result["instances"]}
    assert entries[a.manager.instance_id]["status"] == "executed"
    assert entries[b.manager.instance_id] == {
        "instance_id": b.manager.instance_id,
        "instance_name": "beta",
        "status": "no_answer",
    }
    assert entries[PEER] == {"instance_id": PEER, "instance_name": "Peer", "status": "no_answer", "reason": "offline"}
    assert len(entries) == 3
    await _settle(a, b)


async def test_retrigger_honors_modes_and_breaker_in_the_multi_instance_tier(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """TRU-01, D-14: an observing follower and a follower with a tripped breaker answer so and run nothing."""
    a, b, device_id, calls = await _approved_pair(hass, fake_broker, make_instance, make_switch_subentry)
    c = await make_instance("gamma")
    c_on = async_mock_service(c.hass, "test", "on")
    await _settle(a, b, c)
    mirror = c.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert await c.manager.async_approve(device_id, mirror.actions_hash) is True
    await c.manager.presence.async_publish_heartbeat()
    await a.manager.presence.async_publish_heartbeat()
    await _settle(a, b, c)
    await b.manager.async_set_device_mode(device_id, "observe")
    c_device = c.manager.device(device_id)
    assert c_device is not None
    c_device.breaker.trip()
    before = (len(calls["a_on"]), len(calls["b_on"]), len(c_on))

    result = await a.manager.retrigger.async_retrigger(device_id)
    await _settle(a, b, c)

    answers = {entry["instance_id"]: entry["status"] for entry in result["instances"]}
    assert answers == {
        a.manager.instance_id: "executed",
        b.manager.instance_id: "observing",
        c.manager.instance_id: "paused",
    }
    assert (len(calls["a_on"]), len(calls["b_on"]), len(c_on)) == (before[0] + 1, before[1], before[2])


async def test_unapproved_mirror_answers_not_approved_and_runs_nothing(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-42: a follower that never approved answers not_approved and its service is untouched."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    b = await make_instance("beta")
    a_on = async_mock_service(a.hass, "test", "on")
    b_on = async_mock_service(b.hass, "test", "on")
    await _settle(a, b)
    fake_broker.publish(state_topic(BASE, device_id), "ON", retain=True)
    await a.manager.presence.async_publish_heartbeat()
    await b.manager.presence.async_publish_heartbeat()
    await _settle(a, b)
    assert (len(a_on), len(b_on)) == (1, 0)

    result = await a.manager.retrigger.async_retrigger(device_id)
    await _settle(a, b)

    answers = {entry["instance_id"]: entry["status"] for entry in result["instances"]}
    assert answers == {a.manager.instance_id: "executed", b.manager.instance_id: "not_approved"}
    assert (len(a_on), len(b_on)) == (2, 0)


async def test_acknowledgements_per_request_are_capped(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-47: one answer per instance and at most MAX_TRACKED_INSTANCES answers per request are kept."""
    a, _b, device_id, _calls = await _approved_pair(hass, fake_broker, make_instance, make_switch_subentry)
    _peer_heartbeat(fake_broker)  # a silent peer keeps the collector waiting while the answers arrive
    await _settle(a)
    topic = retrigger_topic(BASE, device_id)

    with (
        patch.object(retrigger_module, "RETRIGGER_ACK_WINDOW_SECONDS", 0.6),
        patch.object(retrigger_module, "MAX_TRACKED_INSTANCES", 3, create=True),
    ):
        task = asyncio.create_task(a.manager.retrigger.async_retrigger(device_id))
        for _ in range(100):
            sent = [payload for published, payload, _retain in a.gateway.published if published == topic]
            if sent:
                break
            await asyncio.sleep(0.01)
        request_id = json.loads(sent[-1])["request_id"]
        for number in range(10):
            forged = {
                "request_id": request_id,
                "device_id": device_id,
                "instance_id": f"flood-{number}",
                "instance_name": "flood",
                "status": "executed",
            }
            for _repeat in range(2):  # the second answer of an instance never replaces the first
                fake_broker.publish(acks_topic(BASE, a.manager.instance_id), json.dumps(forged), retain=False)
        result = await task

    flood = [entry for entry in result["instances"] if entry["instance_id"].startswith("flood-")]
    assert len({entry["instance_id"] for entry in flood}) == len(flood)
    # The caller's own answer and its roster entries come first; the cap counts answers, so at most two extras fit
    assert len(flood) <= 2
    await _settle(a)
