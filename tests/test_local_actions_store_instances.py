"""
Per-instance local-actions Store keys of the fake-broker factory (T-11-11).

Every Home Assistant of the test harness shares one storage mock, so two instances on one broker read each other's
local actions unless each gets its own injected key. Its own module because `make_instance` puts it in the
multi-instance tier; the unit-tier contracts of the Store live in `test_local_actions_store.py`.
"""

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.mqtt_actions.const import LOCAL_ACTIONS_STORE_KEY, SUBENTRY_SWITCH
from custom_components.mqtt_actions.local_actions import make_local_record
from custom_components.mqtt_actions.local_actions_store import LocalActionsStore

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from tests.fake_broker import InstanceFactory

pytestmark = pytest.mark.multi_instance


async def test_factory_instances_get_distinct_local_keys_and_see_only_their_own_records(
    hass: HomeAssistant, make_instance: InstanceFactory, hass_storage: dict[str, Any]
) -> None:
    """Two instances on one broker: four distinct Store keys, and each local Store loads only its own record."""
    owner = await make_instance("owner", hass=hass)
    follower = await make_instance("follower")
    keys = [owner.store_key, owner.local_store_key, follower.store_key, follower.local_store_key]

    assert len(set(keys)) == len(keys), f"the instances share a Store key: {keys}"
    assert LOCAL_ACTIONS_STORE_KEY not in keys, "no test manager uses the global production local key"

    records = {}
    for instance in (owner, follower):
        record = make_local_record(
            "a" * 22, SUBENTRY_SWITCH, "ON", label=instance.name, mode="additive", actions=[{"action": "test.x"}]
        )
        store = LocalActionsStore(instance.hass, instance.local_store_key)
        await store.async_load_records()
        await store.async_save_records([record])
        records[instance.name] = record

    for instance in (owner, follower):
        loaded = await LocalActionsStore(instance.hass, instance.local_store_key).async_load_records()
        assert loaded == (records[instance.name],), f"{instance.name} sees another instance's local actions"
    assert hass_storage.keys() >= {owner.local_store_key, follower.local_store_key}
