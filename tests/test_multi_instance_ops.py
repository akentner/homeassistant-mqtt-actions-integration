"""Operations scenarios of several real instances on one fake broker: presence and the roster (OPS-03)."""

import asyncio
import json
import time
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions import const
from custom_components.mqtt_actions import retrigger as retrigger_module
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_ON_CHANGE_TO_ON,
    DOMAIN,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_OFFLINE_SECONDS,
    ISSUE_DOC_OVERWRITTEN_PREFIX,
    ISSUE_OWNER_CONFLICT_PREFIX,
    ISSUE_OWNERSHIP_CLAIM_PREFIX,
    SIGNAL_ROSTER_UPDATED,
    STORE_DEVICE_MODES,
    STORE_LAST_ACTED,
    STORE_PUBLISHED,
    STORE_REVS,
    STORE_TRANSFERS,
    STORE_TRIPPED,
)
from custom_components.mqtt_actions.document import escape_markdown
from custom_components.mqtt_actions.manager import AdoptionError
from custom_components.mqtt_actions.topics import (
    acks_topic,
    availability_topic,
    config_topic,
    discovery_topic,
    heartbeat_topic,
    retrigger_topic,
    state_topic,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from tests.fake_broker import FakeBroker, Instance

from tests.documents import document_payload, make_spec

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


# --- adoption of an orphaned device (SYN-07, D-09, D-10) ----------------------------------------------------------


async def _adoption_trio(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    *,
    approve: bool = True,
) -> tuple[Instance, Instance, Instance, str, dict[str, list]]:
    """
    Start owner A and followers B and C of one switch; B approved the mirror, the baseline is ON, heartbeats are out.

    The returned dict holds the `test.on` call list of every instance by name.
    """
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}], off=[{"action": "test.off"}])
    device_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    b = await make_instance("beta")
    c = await make_instance("gamma")
    on_calls = {instance.name: async_mock_service(instance.hass, "test", "on") for instance in (a, b, c)}
    await _settle(a, b, c)
    if approve:
        mirror = b.manager.mirrors[device_id].mirror
        assert mirror is not None
        assert await b.manager.async_approve(device_id, mirror.actions_hash) is True
    fake_broker.publish(state_topic(BASE, device_id), "ON", retain=True)
    for instance in (a, b, c):
        await instance.manager.presence.async_publish_heartbeat()
    await _settle(a, b, c)
    assert len(on_calls["alpha"]) == 1
    assert len(on_calls["beta"]) == (1 if approve else 0)
    return a, b, c, device_id, on_calls


def _retained_document(fake_broker: FakeBroker, device_id: str) -> dict:
    return json.loads(fake_broker.retained[config_topic(BASE, device_id)])


async def test_adoption_end_to_end(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: B adopts the device of the stopped owner A under the same uuid, and C re-pins to B without a conflict."""
    a, b, c, device_id, on_calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    old = _retained_document(fake_broker, device_id)
    await a.stop()
    await _settle(a, b, c)
    assert fake_broker.retained[availability_topic(BASE, a.manager.instance_id)] == "offline"
    baseline = b.manager.mirrors[device_id].tracker.last_acted
    assert baseline == "ON"
    ran_before = len(on_calls["beta"])

    previous = await b.manager.async_adopt(device_id)
    await _settle(a, b, c)

    assert previous == "alpha"
    assert device_id in b.manager.devices
    assert device_id not in b.manager.mirrors
    document = _retained_document(fake_broker, device_id)
    assert document["owner"] == b.manager.instance_id
    assert document["owner_name"] == "beta"
    assert document["transferred_from"] == [a.manager.instance_id]
    assert document["rev"] == old["rev"] + 1
    assert document["hash"] == old["hash"]
    discovery = json.loads(fake_broker.retained[discovery_topic("homeassistant", device_id)])
    assert discovery["availability"] == [{"topic": availability_topic(BASE, b.manager.instance_id)}]
    assert b.manager.devices[device_id].tracker.last_acted == baseline
    assert len(on_calls["beta"]) == ran_before
    mirror = c.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert mirror.owner == b.manager.instance_id
    assert mirror.transferred_from == (a.manager.instance_id,)
    assert ir.async_get(c.hass).async_get_issue(DOMAIN, f"{ISSUE_OWNER_CONFLICT_PREFIX}{device_id}") is None


async def test_adoption_clears_nothing_on_the_broker(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-04-53: no empty payload goes to the config, discovery or state topic of the device, and the state stays."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await a.stop()
    await _settle(a, b, c)
    state = fake_broker.retained[state_topic(BASE, device_id)]
    published: list[tuple[str, str, bool]] = []
    original = fake_broker.publish

    def _spy(topic: str, payload: str, *, retain: bool) -> None:
        published.append((topic, payload, retain))
        original(topic, payload, retain=retain)

    monkeypatch.setattr(fake_broker, "publish", _spy)

    await b.manager.async_adopt(device_id)
    await _settle(a, b, c)

    device_topics = {
        config_topic(BASE, device_id),
        discovery_topic("homeassistant", device_id),
        state_topic(BASE, device_id),
    }
    assert [item for item in published if item[0] in device_topics and item[1] == ""] == []
    assert any(item[0] == config_topic(BASE, device_id) for item in published)
    assert fake_broker.retained[state_topic(BASE, device_id)] == state


async def test_marker_survives_a_restart_of_the_adopter(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: every later republish carries the marker, so a follower that was offline still learns the transfer."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await a.stop()
    await _settle(a, b, c)
    await b.manager.async_adopt(device_id)
    await _settle(a, b, c)
    adopted = _retained_document(fake_broker, device_id)

    await b.restart()
    await _settle(a, b, c)

    again = _retained_document(fake_broker, device_id)
    assert again["transferred_from"] == [a.manager.instance_id]
    assert again["rev"] == adopted["rev"]
    assert again["owner"] == b.manager.instance_id
    assert device_id in b.manager.devices


async def test_adopter_edits_after_adoption_keep_the_history(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """A later edit of the adopted device changes the hash, raises the rev again and keeps the marker."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await a.stop()
    await _settle(a, b, c)
    await b.manager.async_adopt(device_id)
    await _settle(a, b, c)
    adopted = _retained_document(fake_broker, device_id)
    subentry = next(iter(b.entry.subentries.values()))

    b.hass.config_entries.async_update_subentry(
        b.entry, subentry, data={**subentry.data, CONF_ON_CHANGE_TO_ON: [{"action": "test.on2"}]}
    )
    await b.manager.async_reconcile()
    await _settle(a, b, c)

    edited = _retained_document(fake_broker, device_id)
    assert edited["hash"] != adopted["hash"]
    assert edited["rev"] == adopted["rev"] + 1
    assert edited["transferred_from"] == [a.manager.instance_id]
    assert edited["owner"] == b.manager.instance_id


# --- adoption: preconditions, the narrow pin rule and the transfer history (D-09, D-10) ----------------------------


def _use_running_clock(instance: Instance) -> list[float]:
    """Replace the manager clock by a settable one that starts at the real monotonic time, and restart the listening."""
    now = [time.monotonic()]
    instance.manager.clock = lambda: now[0]
    instance.manager.presence.on_reconnect()
    return now


def _snapshot(instance: Instance, device_id: str) -> tuple[object, ...]:
    """Return what a refused adoption must leave alone on an instance."""
    manager = instance.manager
    return (
        len(instance.gateway.published),
        device_id in manager.mirrors,
        device_id in manager.devices,
        dict(manager._transfers),
        dict(manager._revs),
        dict(manager._approvals),
        len(instance.entry.subentries),
    )


async def _refused(instance: Instance, device_id: str, reason: str, *, force: bool = False) -> AdoptionError:
    """Assert that an adoption is refused with a reason, leaves no trace and writes no Store."""
    before = _snapshot(instance, device_id)
    with patch.object(instance.manager._store, "async_save", new_callable=AsyncMock) as save:
        with pytest.raises(AdoptionError) as raised:
            await instance.manager.async_adopt(device_id, force=force)
        save.assert_not_called()
    assert raised.value.reason == reason
    assert _snapshot(instance, device_id) == before
    return raised.value


def _foreign_document(
    fake_broker: FakeBroker, spec, *, owner: str = "ghost-owner", rev: int = 1, transferred_from=None
) -> None:
    """Publish a retained document of a synthetic owner that is not a running instance."""
    payload = document_payload(spec, owner=owner, owner_name=owner.title(), rev=rev, transferred_from=transferred_from)
    fake_broker.publish(config_topic(BASE, spec.device_id), payload, retain=True)


async def test_adoption_needs_the_owner_offline_or_force(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-10: with the owner running and its heartbeats fresh the adoption names the owner and changes nothing."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    assert b.manager.presence.owner_offline(a.manager.instance_id) is False

    error = await _refused(b, device_id, "owner_not_offline")
    assert error.owner_name == "alpha"
    assert device_id in b.manager.mirrors

    assert await b.manager.async_adopt(device_id, force=True) == "alpha"
    await _settle(a, b, c)
    assert device_id in b.manager.devices
    assert device_id not in b.manager.mirrors


async def test_unknown_owner_needs_force_until_enough_was_heard(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-54: no heartbeat heard never means offline when the availability says online; silence needs 90 seconds."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    online_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    b = await make_instance("beta")
    ghost_spec = make_spec(name="Ghost lamp", on=[{"action": "test.on"}])
    _foreign_document(fake_broker, ghost_spec)
    await _settle(a, b)
    for device_id in (online_id, ghost_spec.device_id):
        mirror = b.manager.mirrors[device_id].mirror
        assert mirror is not None
        assert await b.manager.async_approve(device_id, mirror.actions_hash) is True
    now = _use_running_clock(b)
    assert fake_broker.retained[availability_topic(BASE, a.manager.instance_id)] == "online"

    # An instance whose availability says online and that never sent a heartbeat is not offline, however long we wait
    now[0] += 600
    await _refused(b, online_id, "owner_not_offline")

    # An owner nobody has heard of is offline only once this instance listened for 90 seconds
    now[0] -= 600 - (HEARTBEAT_OFFLINE_SECONDS - 1)
    await _refused(b, ghost_spec.device_id, "owner_not_offline")
    now[0] += 2
    assert await b.manager.async_adopt(ghost_spec.device_id) == "Ghost-Owner"
    assert ghost_spec.device_id in b.manager.devices


async def test_stale_heartbeat_allows_adoption(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: an owner whose last heartbeat is older than 90 seconds is gone, even with an online availability."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    now = _use_running_clock(b)
    await a.manager.presence.async_publish_heartbeat()
    await _settle(a, b, c)
    assert fake_broker.retained[availability_topic(BASE, a.manager.instance_id)] == "online"
    await _refused(b, device_id, "owner_not_offline")

    now[0] += HEARTBEAT_OFFLINE_SECONDS + 1

    assert await b.manager.async_adopt(device_id) == "alpha"
    await _settle(a, b, c)
    assert device_id in b.manager.devices


async def test_adoption_requires_an_approved_mirror(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable
) -> None:
    """T-04-50: a pending and a blocked mirror are refused with and without force; approved and action-less pass."""
    b = await make_instance("beta", hass=hass)
    pending = make_spec(name="Pending", on=[{"action": "test.on"}])
    blocked = make_spec(name="Blocked", on=[{"action": "shell_command.run"}])
    plain = make_spec(name="Plain")
    approved = make_spec(name="Approved", on=[{"action": "test.on"}])
    for spec in (pending, blocked, plain, approved):
        _foreign_document(fake_broker, spec)
    await _settle(b)
    mirror = b.manager.mirrors[approved.device_id].mirror
    assert mirror is not None
    assert await b.manager.async_approve(approved.device_id, mirror.actions_hash) is True
    assert b.manager.approval_state(blocked.device_id) == "blocked"
    assert b.manager.approval_state(pending.device_id) == "pending"

    for spec in (pending, blocked):
        for force in (False, True):
            await _refused(b, spec.device_id, "not_approved", force=force)

    for spec in (plain, approved):
        assert await b.manager.async_adopt(spec.device_id, force=True) == "Ghost-Owner"
    await _settle(b)
    assert set(b.manager.devices) == {plain.device_id, approved.device_id}
    assert set(b.manager.mirrors) == {pending.device_id, blocked.device_id}


async def test_not_a_mirror_and_unknown_device(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """An owned device, an unknown id and a mirror whose owner id cannot be named in a marker are not adoptable."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await _refused(a, device_id, "not_a_mirror", force=True)
    await _refused(b, str(uuid.uuid4()), "not_a_mirror", force=True)
    odd = make_spec(name="Odd owner", on=[{"action": "test.on"}])
    payload = document_payload(odd, owner="owner with spaces", owner_name="Odd")
    fake_broker.publish(config_topic(BASE, odd.device_id), payload, retain=True)
    await _settle(a, b, c)
    mirror = b.manager.mirrors[odd.device_id].mirror
    assert mirror is not None
    assert await b.manager.async_approve(odd.device_id, mirror.actions_hash) is True
    await _refused(b, odd.device_id, "not_a_mirror", force=True)


async def test_marker_with_an_online_pinned_owner_is_a_conflict(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-49: a forced adoption while the owner is online does not move a follower that sees the owner online."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    events = async_capture_events(c.hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)

    await b.manager.async_adopt(device_id, force=True)
    await _settle(a, b, c)

    created = [
        event.data
        for event in events
        if event.data["action"] == "create" and event.data["issue_id"] == f"{ISSUE_OWNER_CONFLICT_PREFIX}{device_id}"
    ]
    assert created
    mirror = c.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert mirror.owner == a.manager.instance_id
    assert mirror.transferred_from == ()


async def test_marker_that_does_not_name_the_pinned_owner_is_a_conflict(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-49: with the pinned owner offline, a marker naming someone else still changes nothing."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await a.stop()
    await _settle(a, b, c)
    assert c.manager.presence.owner_offline(a.manager.instance_id) is True
    pinned = c.manager.mirrors[device_id].spec

    _foreign_document(fake_broker, pinned, owner="newcomer", rev=9, transferred_from=["someone-else"])
    await _settle(a, b, c)

    mirror = c.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert mirror.owner == a.manager.instance_id
    assert ir.async_get(c.hass).async_get_issue(DOMAIN, f"{ISSUE_OWNER_CONFLICT_PREFIX}{device_id}") is not None


async def test_marker_naming_the_offline_pinned_owner_repins(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: the narrow rule has a positive side: the marker names the pinned owner and the roster says it is gone."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await a.stop()
    await _settle(a, b, c)

    _foreign_document(
        fake_broker,
        c.manager.mirrors[device_id].spec,
        owner="newcomer",
        rev=9,
        transferred_from=[a.manager.instance_id],
    )
    await _settle(a, b, c)

    mirror = c.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert (mirror.owner, mirror.rev) == ("newcomer", 9)
    assert ir.async_get(c.hass).async_get_issue(DOMAIN, f"{ISSUE_OWNER_CONFLICT_PREFIX}{device_id}") is None


async def test_forged_marker_cannot_repin_when_the_owner_is_online(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-49: a forged document that names the pinned owner changes nothing while the roster shows it online."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    pinned = c.manager.mirrors[device_id].spec
    assert c.manager.presence.owner_offline(a.manager.instance_id) is False
    evil = make_spec(device_id=device_id, name="Lamp", on=[{"action": "test.evil"}])

    _foreign_document(fake_broker, evil, owner="forger", rev=7, transferred_from=[a.manager.instance_id])
    await _settle(a, b, c)

    mirror = c.manager.mirrors[device_id]
    assert mirror.mirror is not None
    assert mirror.mirror.owner == a.manager.instance_id
    assert mirror.spec == pinned


async def test_chain_of_adoptions_keeps_the_history(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: A to B to C names A and B in that order, and a follower pinned to B re-pins to C when B is offline."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await a.stop()
    await _settle(a, b, c)
    await b.manager.async_adopt(device_id)
    await _settle(a, b, c)
    d = await make_instance("delta")
    await _settle(a, b, c, d)
    mirror_d = d.manager.mirrors[device_id].mirror
    assert mirror_d is not None
    assert mirror_d.owner == b.manager.instance_id
    mirror_c = c.manager.mirrors[device_id].mirror
    assert mirror_c is not None
    assert await c.manager.async_approve(device_id, mirror_c.actions_hash) is True
    await b.stop()
    await _settle(a, b, c, d)

    await c.manager.async_adopt(device_id)
    await _settle(a, b, c, d)

    document = _retained_document(fake_broker, device_id)
    assert document["owner"] == c.manager.instance_id
    assert document["transferred_from"] == [a.manager.instance_id, b.manager.instance_id]
    pinned = d.manager.mirrors[device_id].mirror
    assert pinned is not None
    assert pinned.owner == c.manager.instance_id
    assert ir.async_get(d.hass).async_get_issue(DOMAIN, f"{ISSUE_OWNER_CONFLICT_PREFIX}{device_id}") is None


async def test_history_keeps_only_the_newest_eight(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable
) -> None:
    """T-04-52: a ninth transfer drops the oldest entry and the newest stays last."""
    b = await make_instance("beta", hass=hass)
    spec = make_spec(name="Lamp", on=[{"action": "test.on"}])
    history = [f"old-{number}" for number in range(8)]
    _foreign_document(fake_broker, spec, owner="owner-x", rev=4, transferred_from=history)
    await _settle(b)
    mirror = b.manager.mirrors[spec.device_id].mirror
    assert mirror is not None
    assert await b.manager.async_approve(spec.device_id, mirror.actions_hash) is True

    await b.manager.async_adopt(spec.device_id, force=True)
    await _settle(b)

    document = _retained_document(fake_broker, spec.device_id)
    assert document["transferred_from"] == [*history[1:], "owner-x"]
    assert document["rev"] == 5
    assert len(document["transferred_from"]) == 8


async def test_follower_that_was_offline_during_the_adoption(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: a follower that starts after the adoption mirrors the adopted document directly, without a conflict."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    await a.stop()
    await _settle(a, b, c)
    await b.manager.async_adopt(device_id)
    await _settle(a, b, c)

    d = await make_instance("delta")
    await _settle(a, b, c, d)

    mirror = d.manager.mirrors[device_id].mirror
    assert mirror is not None
    assert mirror.owner == b.manager.instance_id
    assert mirror.transferred_from == (a.manager.instance_id,)
    assert ir.async_get(d.hass).async_get_issue(DOMAIN, f"{ISSUE_OWNER_CONFLICT_PREFIX}{device_id}") is None


async def test_failed_subentry_add_restores_the_mirror(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-53: when the subentry cannot be added the mirror, its approval and its baseline come back."""
    a, b, c, device_id, on_calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    off_calls = async_mock_service(b.hass, "test", "off")
    await a.stop()
    await _settle(a, b, c)

    with (
        patch.object(b.hass.config_entries, "async_add_subentry", side_effect=HomeAssistantError("refused")),
        pytest.raises(HomeAssistantError),
    ):
        await b.manager.async_adopt(device_id)
    await _settle(a, b, c)

    assert device_id in b.manager.mirrors
    assert device_id not in b.manager.devices
    assert b.manager.approval_state(device_id) == "approved"
    assert b.manager._transfers == {}
    assert device_id not in b.manager._revs
    assert b.manager.mirrors[device_id].tracker.last_acted == "ON"
    fake_broker.publish(state_topic(BASE, device_id), "OFF", retain=True)
    await _settle(a, b, c)
    assert (len(on_calls["beta"]), len(off_calls)) == (1, 1)


async def test_repin_keeps_the_breaker_and_the_script_of_an_unchanged_mirror(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09, D-15: following a new owner with the same content releases no tripped breaker and rebuilds no Script."""
    a, b, c, device_id, _calls = await _adoption_trio(hass, fake_broker, make_instance, make_switch_subentry)
    mirror_c = c.manager.mirrors[device_id].mirror
    assert mirror_c is not None
    assert await c.manager.async_approve(device_id, mirror_c.actions_hash) is True
    device_c = c.manager.mirrors[device_id]
    device_c.breaker.trip()
    breaker = device_c.breaker
    await a.stop()
    await _settle(a, b, c)

    await b.manager.async_adopt(device_id)
    await _settle(a, b, c)

    info = c.manager.mirrors[device_id].mirror
    assert info is not None
    assert info.owner == b.manager.instance_id
    assert c.manager.mirrors[device_id] is device_c
    assert device_c.breaker is breaker
    assert device_c.breaker.tripped is True
    assert c.manager.runner.script_count(device_id) == 1
    assert c.manager.approval_state(device_id) == "approved"


# --- a clone shares the instance id: detection and the local release (D-07, D-08) -------------------------------------


async def _duplicate_pair(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> tuple[Instance, Instance, list[str]]:
    """
    Start the original A and a restored copy B with the same instance id, name and devices; both heard each other.

    The copy keeps its own Store key (the name argument), as a restored backup on another machine would have its own
    storage. The retained state topics hold a value, so a clearing publish of the copy would be visible.
    """
    lamp = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    mode = make_select_subentry("Mode", [("a", "A", [{"action": "test.a"}]), ("b", "B", [])])
    a = await make_instance("alpha", hass=hass, subentries=[lamp, mode])
    b = await make_instance("alpha-copy", data=dict(a.entry.data), subentries=[lamp, mode])
    for instance in (a, b):
        async_mock_service(instance.hass, "test", "on")
        async_mock_service(instance.hass, "test", "a")
    ids = [lamp["data"][CONF_DEVICE_ID], mode["data"][CONF_DEVICE_ID]]
    fake_broker.publish(state_topic(BASE, ids[0]), "ON", retain=True)
    fake_broker.publish(state_topic(BASE, ids[1]), "a", retain=True)
    await _settle(a, b)
    assert a.manager.instance_id == b.manager.instance_id
    return a, b, ids


async def _exchange_heartbeats(a: Instance, b: Instance, rounds: int = 2) -> None:
    for _ in range(rounds):
        await a.manager.presence.async_publish_heartbeat()
        await b.manager.presence.async_publish_heartbeat()
    await _settle(a, b)


async def test_duplicate_detection_changes_nothing_by_itself(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-07, T-04-55: both detect the shared id, and nothing but their heartbeats is published or changed."""
    a, b, ids = await _duplicate_pair(hass, fake_broker, make_instance, make_switch_subentry, make_select_subentry)
    before = dict(fake_broker.retained)
    marks = (len(a.gateway.published), len(b.gateway.published))

    await _exchange_heartbeats(a, b)

    assert a.manager.presence.duplicate_detected is True
    assert b.manager.presence.duplicate_detected is True
    for instance, mark in zip((a, b), marks, strict=True):
        topics = {item[0] for item in instance.gateway.published[mark:]}
        assert topics == {heartbeat_topic(BASE, instance.manager.instance_id)}
        assert set(instance.manager.devices) == set(ids)
        assert len(instance.entry.subentries) == 2
    assert dict(fake_broker.retained) == before
    assert a.entry.data[CONF_INSTANCE_ID] == b.entry.data[CONF_INSTANCE_ID]


async def test_duplicate_id_fix_leaves_the_originals_topics_byte_identical(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-08, T-04-56: the copy forgets its devices locally, gets a new id and leaves the original's topics alone."""
    a, b, ids = await _duplicate_pair(hass, fake_broker, make_instance, make_switch_subentry, make_select_subentry)
    old_id = a.manager.instance_id
    before = dict(fake_broker.retained)
    assert availability_topic(BASE, old_id) in before
    assert {config_topic(BASE, ids[0]), discovery_topic("homeassistant", ids[0]), state_topic(BASE, ids[0])} <= set(
        before
    )
    mark = len(b.gateway.published)

    with patch.object(b.hass.config_entries, "async_schedule_reload") as schedule:
        await b.manager.async_resolve_duplicate_id()
    schedule.assert_called_once_with(b.entry.entry_id)
    await _settle(a, b)
    await b.restart()
    await _settle(a, b)

    # Every retained message of the original is the same bytes as before
    assert {topic: fake_broker.retained.get(topic) for topic in before} == before
    # The copy never published an empty (clearing) payload, neither during the fix nor during its restart
    assert [item for item in b.gateway.published[mark:] if item[1] == ""] == []
    new_id = b.entry.data[CONF_INSTANCE_ID]
    assert new_id != old_id
    assert str(uuid.UUID(new_id)) == new_id
    assert a.entry.data[CONF_INSTANCE_ID] == old_id
    assert b.manager.instance_id == new_id
    assert b.manager.devices == {}
    assert len(b.entry.subentries) == 0
    for device_id in ids:
        mirror = b.manager.mirrors[device_id].mirror
        assert mirror is not None
        assert mirror.owner == old_id
    assert fake_broker.retained[availability_topic(BASE, new_id)] == "online"
    assert set(a.manager.devices) == set(ids)


async def test_released_devices_are_not_readded_by_the_reconcile(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """T-04-56: the reconcile that each subentry removal triggers never adds a device that is being released."""
    a, b, ids = await _duplicate_pair(hass, fake_broker, make_instance, make_switch_subentry, make_select_subentry)

    async def _reconcile(_hass: HomeAssistant, _entry: object) -> None:
        await b.manager.async_reconcile()

    b.entry.add_update_listener(_reconcile)
    mark = len(b.gateway.published)
    with patch.object(b.manager, "_async_add_device", wraps=b.manager._async_add_device) as add:
        released = await b.manager.async_release_locally(list(ids))
        await _settle(a, b)

    assert sorted(released) == sorted(ids)
    add.assert_not_called()
    assert b.manager.devices == {}
    assert len(b.entry.subentries) == 0
    assert b.manager._releasing == set()
    assert b.gateway.published[mark:] == []


async def test_release_keeps_baseline_and_mode_and_drops_the_rest(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-08: the record drops published, revs, tripped and transfers of the device, keeps baseline and mode."""
    a, _b, ids = await _duplicate_pair(hass, fake_broker, make_instance, make_switch_subentry, make_select_subentry)
    manager = a.manager
    lamp_id, mode_id = ids
    await manager.async_set_device_mode(lamp_id, "observe")
    manager._tripped[lamp_id] = "hash"
    manager._transfers[lamp_id] = ["previous-owner"]
    assert lamp_id in manager._published
    assert lamp_id in manager._revs
    subentry_counts: list[int] = []

    async def _record(_data: object) -> None:
        subentry_counts.append(len(a.entry.subentries))

    with (
        patch.object(manager._store, "async_save", new_callable=AsyncMock, side_effect=_record) as save,
        patch.object(manager._store, "async_delay_save") as delayed,
    ):
        assert await manager.async_release_locally(["unknown-id"]) == []
        released = await manager.async_release_locally([lamp_id])

    assert released == [lamp_id]
    delayed.assert_not_called()
    saved = save.call_args.args[0]
    for key in (STORE_PUBLISHED, STORE_REVS, STORE_TRIPPED, STORE_TRANSFERS):
        assert lamp_id not in saved[key], key
    assert mode_id in saved[STORE_PUBLISHED]
    assert mode_id in saved[STORE_REVS]
    assert saved[STORE_LAST_ACTED][lamp_id] == "ON"
    assert saved[STORE_DEVICE_MODES][lamp_id] == "observe"
    # The Store was written while the subentry still existed: a crash after it loses nothing the next start would clear
    assert subentry_counts[-1] == 2
    assert lamp_id not in manager.devices
    assert mode_id in manager.devices
    assert len(a.entry.subentries) == 1
    assert manager.device_mode(lamp_id) == "observe"


async def test_stop_after_release_publishes_no_offline(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """T-04-57: the stop that follows the fix publishes no availability for the id it shares with the original."""
    a, b, _ids = await _duplicate_pair(hass, fake_broker, make_instance, make_switch_subentry, make_select_subentry)
    old_id = a.manager.instance_id
    with patch.object(b.hass.config_entries, "async_schedule_reload"):
        await b.manager.async_resolve_duplicate_id()
    mark = len(b.gateway.published)

    await b.manager.async_stop()
    await _settle(a, b)

    assert [item for item in b.gateway.published[mark:] if item[0] == availability_topic(BASE, old_id)] == []
    assert fake_broker.retained[availability_topic(BASE, old_id)] == "online"


# --- an old owner comes back after its device was adopted (D-09 refined, assumption A15) --------------------------


def _transferred_issue(instance: Instance, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(instance.hass).async_get_issue(DOMAIN, f"{const.ISSUE_TRANSFERRED_PREFIX}{device_id}")


async def _adopted_and_returned(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> tuple[Instance, Instance, Instance, str, str]:
    """
    A owns a lamp and another device; B adopts the lamp while A is stopped; A starts again and the messages settle.

    Returns A, B, C, the id of the adopted lamp and the id of the device that A still owns for sure.
    """
    lamp = make_switch_subentry("Lamp", on=[{"action": "test.on"}], off=[{"action": "test.off"}])
    other = make_switch_subentry("Other", on=[{"action": "test.on"}])
    lamp_id, other_id = lamp["data"][CONF_DEVICE_ID], other["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[lamp, other])
    b = await make_instance("beta")
    c = await make_instance("gamma")
    for instance in (a, b, c):
        async_mock_service(instance.hass, "test", "on")
        async_mock_service(instance.hass, "test", "off")
    await _settle(a, b, c)
    mirror = b.manager.mirrors[lamp_id].mirror
    assert mirror is not None
    assert await b.manager.async_approve(lamp_id, mirror.actions_hash) is True
    fake_broker.publish(state_topic(BASE, lamp_id), "ON", retain=True)
    for instance in (a, b, c):
        await instance.manager.presence.async_publish_heartbeat()
    await _settle(a, b, c)
    await a.stop()
    await _settle(a, b, c)
    await b.manager.async_adopt(lamp_id)
    await _settle(a, b, c)
    await a.start()
    await _settle(a, b, c)
    return a, b, c, lamp_id, other_id


async def test_old_owner_recognizes_the_transfer_after_a_restart(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: A's start overwrites B's document, B heals, A recognizes the marker and raises one fixable issue."""
    a, b, _c, lamp_id, _other_id = await _adopted_and_returned(hass, fake_broker, make_instance, make_switch_subentry)

    issue = _transferred_issue(a, lamp_id)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "transferred"
    assert issue.translation_placeholders == {"device": escape_markdown("Lamp"), "claimant": escape_markdown("beta")}
    assert issue.data == {"device_id": lamp_id, "claimant": b.manager.instance_id}
    document = _retained_document(fake_broker, lamp_id)
    assert document["owner"] == b.manager.instance_id
    assert document["transferred_from"] == [a.manager.instance_id]
    assert lamp_id in a.manager.sync.transferred_away
    # Settled: another round of messages changes nothing, so the two owners do not fight
    before = dict(fake_broker.retained)
    await _settle(a, b)
    assert dict(fake_broker.retained) == before


async def test_recognizing_the_transfer_does_not_step_down(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-59: A still owns the device and its subentry, and it never cleared anything on the broker."""
    a, _b, _c, lamp_id, other_id = await _adopted_and_returned(hass, fake_broker, make_instance, make_switch_subentry)

    assert lamp_id in a.manager.devices
    assert other_id in a.manager.devices
    assert a.manager.subentry_id_of(lamp_id) is not None
    assert len(a.entry.subentries) == 2
    assert [item for item in a.gateway.published if item[1] == ""] == []


async def test_transferred_away_device_is_not_republished(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-60: reconnect, resync and a heal request publish nothing for the lost device, but still for the others."""
    a, b, c, lamp_id, other_id = await _adopted_and_returned(hass, fake_broker, make_instance, make_switch_subentry)
    mark = len(a.gateway.published)

    a.gateway.reconnect()
    await _settle(a, b, c)
    assert await a.manager.async_resync() is True
    a.manager.sync._heal(lamp_id)
    a.manager.sync._discovery_heal.request(lamp_id)
    await _settle(a, b, c)

    topics = [item[0] for item in a.gateway.published[mark:]]
    lamp_topics = {config_topic(BASE, lamp_id), discovery_topic("homeassistant", lamp_id)}
    other_topics = {config_topic(BASE, other_id), discovery_topic("homeassistant", other_id)}
    assert not lamp_topics & set(topics)
    assert other_topics <= set(topics)
    assert _retained_document(fake_broker, lamp_id)["owner"] == b.manager.instance_id


async def test_marker_that_does_not_name_this_instance_is_a_claim(
    hass: HomeAssistant, fake_broker: FakeBroker, make_instance: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-59: a valid foreign document whose marker names someone else is the ordinary claim, healed and reported."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    await _settle(a)
    mark = len(a.gateway.published)

    _foreign_document(
        fake_broker, make_spec(device_id=device_id), owner="ghost-owner", rev=5, transferred_from=["somebody-else"]
    )
    await _settle(a)

    assert ir.async_get(a.hass).async_get_issue(DOMAIN, f"{ISSUE_OWNERSHIP_CLAIM_PREFIX}{device_id}") is not None
    assert _transferred_issue(a, device_id) is None
    assert device_id not in a.manager.sync.transferred_away
    assert config_topic(BASE, device_id) in [item[0] for item in a.gateway.published[mark:]]


@pytest.mark.parametrize(
    "variant",
    ["bad_marker_entry", "marker_not_a_list", "invalid_content"],
)
async def test_invalid_foreign_document_never_creates_the_transfer_issue(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    variant: str,
) -> None:
    """T-04-59: a document that names this instance but fails the parser is overwritten and healed as before."""
    sub = make_switch_subentry("Lamp", on=[{"action": "test.on"}])
    device_id = sub["data"][CONF_DEVICE_ID]
    a = await make_instance("alpha", hass=hass, subentries=[sub])
    await _settle(a)
    mark = len(a.gateway.published)
    own = a.manager.instance_id
    spec = make_spec(device_id=device_id)

    if variant == "bad_marker_entry":
        payload = document_payload(spec, owner="ghost-owner", transferred_from=[own, "not an id!"])
    elif variant == "marker_not_a_list":
        payload = document_payload(
            spec, owner="ghost-owner", tamper=lambda document: document.update(transferred_from=own)
        )
    else:
        payload = document_payload(
            spec, owner="ghost-owner", transferred_from=[own], tamper=lambda document: document.update(kind="bogus")
        )
    fake_broker.publish(config_topic(BASE, device_id), payload, retain=True)
    await _settle(a)

    assert _transferred_issue(a, device_id) is None
    assert device_id not in a.manager.sync.transferred_away
    assert ir.async_get(a.hass).async_get_issue(DOMAIN, f"{ISSUE_DOC_OVERWRITTEN_PREFIX}{device_id}") is not None
    assert config_topic(BASE, device_id) in [item[0] for item in a.gateway.published[mark:]]
