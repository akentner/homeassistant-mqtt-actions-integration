"""Operations scenarios of several real instances on one fake broker: presence and the roster (OPS-03)."""

from typing import TYPE_CHECKING

import pytest

from custom_components.mqtt_actions.topics import heartbeat_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from tests.fake_broker import Instance

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
