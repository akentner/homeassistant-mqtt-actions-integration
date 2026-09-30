"""Owner side of the central config: one retained, versioned document per device, published before discovery."""

import copy
import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.components import mqtt
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    DOMAIN,
    STORE_KEY,
    STORE_LAST_ACTED,
    STORE_PUBLISHED,
    STORE_REVS,
    STORE_SAVE_DELAY,
    STORE_TRIPPED,
    STORE_VERSION,
)
from custom_components.mqtt_actions.document import content_hash, escape_markdown
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on", "target": {"entity_id": "light.lamp"}}]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _documents(mqtt_mock: Any, device_id: str) -> list[dict[str, Any]]:
    return [json.loads(payload) for payload, _qos, _retain in _publishes(mqtt_mock, config_topic(BASE, device_id))]


async def _reconnect(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """Simulate an MQTT reconnect and forget everything published so far."""
    mqtt_mock.async_publish.reset_mock()
    async_dispatcher_send(hass, mqtt.MQTT_CONNECTION_STATE, True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _content(document: dict[str, Any]) -> dict[str, Any]:
    """Return the shared content of a published document: everything but identity and bookkeeping."""
    return {
        key: value
        for key, value in document.items()
        if key not in {"schema_version", "device_id", "owner", "owner_name", "rev", "hash"}
    }


async def test_owner_publishes_one_retained_versioned_document_per_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """SYN-01: exactly one retained qos-1 document per device, stamped with owner, rev and content hash."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    ((payload, qos, retain),) = _publishes(mqtt_mock, config_topic(BASE, _device_id(sub)))

    assert (qos, retain) == (1, True)
    document = json.loads(payload)
    assert document["schema_version"] == 1
    assert document["device_id"] == _device_id(sub)
    assert document["owner"] == entry.data[CONF_INSTANCE_ID]
    assert document["owner_name"] == entry.data[CONF_INSTANCE_NAME]
    assert document["rev"] == 1
    assert document["hash"] == content_hash(_content(document))


async def test_document_carries_no_runtime_state(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-13: baseline, tripped flag and approval are local; the document never carries them."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {STORE_LAST_ACTED: {device_id: "OFF"}},
    }
    await _setup(hass, make_hub_entry([sub]))
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), "ON", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _reconnect(hass, mqtt_mock)

    ((payload, _qos, _retain),) = _publishes(mqtt_mock, config_topic(BASE, device_id))

    for forbidden in ("last_acted", "tripped", "approval", "baseline"):
        assert forbidden not in payload


async def test_publish_order_config_then_discovery_then_availability(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-15, SYN-04: on start and on every reconnect all config documents precede all discovery, then online."""
    switch = make_switch_subentry("Lamp", on=ON_ACTIONS)
    select = make_select_subentry("Mode", [("a", "A", []), ("b", "B", [])])
    entry = await _setup(hass, make_hub_entry([switch, select]))
    instance_id = entry.data[CONF_INSTANCE_ID]

    def _order() -> list[str]:
        kinds = []
        for call in mqtt_mock.async_publish.call_args_list:
            topic = call.args[0]
            if topic.endswith("/config") and topic.startswith(f"{BASE}/"):
                kinds.append("config")
            elif topic.endswith("/config") and topic.startswith("homeassistant/"):
                kinds.append("discovery")
            elif topic == availability_topic(BASE, instance_id) and call.args[1] == "online":
                kinds.append("online")
        return kinds

    assert _order() == ["config", "config", "discovery", "discovery", "online"]
    await _reconnect(hass, mqtt_mock)
    assert _order() == ["config", "config", "discovery", "discovery", "online"]


async def test_reconnect_republishes_identical_documents(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """SYN-04: a reconnect publishes the same retained document again, same rev and same hash."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    await _setup(hass, make_hub_entry([sub]))
    (first,) = _publishes(mqtt_mock, config_topic(BASE, _device_id(sub)))

    await _reconnect(hass, mqtt_mock)

    (second,) = _publishes(mqtt_mock, config_topic(BASE, _device_id(sub)))
    assert second == first
    assert second[2] is True


async def test_rev_bumps_only_on_content_change(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """Rev grows with the content hash only: a rename bumps it, a no-op reconcile and a reconnect do not."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    assert len(_documents(mqtt_mock, device_id)) == 1
    subentry = next(iter(entry.subentries.values()))

    hass.config_entries.async_update_subentry(entry, subentry, title="Lamp 2")
    await hass.async_block_till_done(wait_background_tasks=True)
    first, second = _documents(mqtt_mock, device_id)
    assert (first["rev"], second["rev"]) == (1, 2)
    assert second["hash"] != first["hash"]
    assert second["name"] == "Lamp 2"

    # A data change that does not alter the spec (an unknown extra key) publishes nothing new
    subentry = next(iter(entry.subentries.values()))
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, "legacy": 1})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_documents(mqtt_mock, device_id)) == 2

    await _reconnect(hass, mqtt_mock)
    (republished,) = _documents(mqtt_mock, device_id)
    assert republished["rev"] == 2
    assert republished["hash"] == second["hash"]


async def test_rev_and_hash_persist_across_restart(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A restart republishes the same rev: rev and the hash it belongs to are in the Store (D-15)."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    hass.config_entries.async_update_subentry(entry, next(iter(entry.subentries.values())), title="Lamp 2")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _documents(mqtt_mock, device_id)[-1]["rev"] == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    mqtt_mock.async_publish.reset_mock()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    (document,) = _documents(mqtt_mock, device_id)
    assert document["rev"] == 2


@pytest.mark.parametrize(
    "make_revs",
    [
        lambda _device_id: "text",
        lambda _device_id: ["a", "b"],
        lambda device_id: {device_id: "x"},
        lambda device_id: {device_id: {"rev": "1", "hash": "h"}},
        lambda device_id: {device_id: {"rev": True, "hash": "h"}},
        lambda device_id: {device_id: {"rev": 1, "hash": 5}},
        lambda device_id: {device_id: {"rev": 1}},
    ],
    ids=["string", "list", "non-dict-entry", "string-rev", "bool-rev", "non-string-hash", "missing-hash"],
)
async def test_malformed_revs_store_is_dropped(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_revs: Callable[[str], Any],
) -> None:
    """A damaged revs key never fails the setup; the rev simply restarts at 1."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {STORE_REVS: make_revs(device_id)},
    }

    await _setup(hass, make_hub_entry([sub]))

    (document,) = _documents(mqtt_mock, device_id)
    assert document["rev"] == 1


async def test_phase1_switch_publishes_defaults(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A Switch stored before Phase 2 publishes the defaults, so its hash means the same as an explicit one."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    assert "run_mode" not in sub["data"]
    await _setup(hass, make_hub_entry([sub]))

    (document,) = _documents(mqtt_mock, _device_id(sub))

    assert document["run_mode"] == "serial"
    assert document["breaker_max_runs"] == 5
    assert document["breaker_window"] == 10
    assert _publishes(mqtt_mock, discovery_topic("homeassistant", _device_id(sub)))


# --- delete order and tombstone (SYN-06, D-16) ---------------------------------------------------------------------

ORPHAN_ID = "orphan-device-id"


def _only_subentry(entry: MockConfigEntry) -> Any:
    return next(iter(entry.subentries.values()))


async def _delete_only_device(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.config_entries.async_remove_subentry(entry, _only_subentry(entry).subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def _preload_published(hass_storage: dict[str, Any], published: list[str]) -> None:
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {STORE_PUBLISHED: published},
    }


async def test_config_tombstone_is_empty_retained_qos_one(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-16: the config topic of a deleted device receives an empty retained qos-1 payload."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _delete_only_device(hass, entry)

    assert _publishes(mqtt_mock, config_topic(BASE, _device_id(sub)))[-1] == ("", 1, True)


async def test_device_leaves_devices_before_the_first_clear(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-16, D-18: observed from inside every clear publish, the deleted device is already gone from devices."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    manager = entry.runtime_data
    seen: list[bool] = []
    real_publish = manager.gateway.async_publish

    async def _publish(topic: str, payload: str, *, retain: bool, qos: int = 1) -> None:
        if payload == "":
            seen.append(device_id in manager.devices)
        await real_publish(topic, payload, retain=retain, qos=qos)

    manager.gateway.async_publish = _publish

    await _delete_only_device(hass, entry)

    assert seen == [False, False, False]


async def _flush_store(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Fire the delayed store save; the frozen clock also moves the loop time the store compares against."""
    freezer.tick(timedelta(seconds=STORE_SAVE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_delete_forgets_rev_baseline_and_tripped(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """The rev, the baseline and the tripped hash of a deleted device are forgotten and persisted that way."""
    async_mock_service(hass, "test", "on")
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=ON_ACTIONS, breaker_max_runs=1, breaker_window=3600)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))
    for payload in ("ON", "OFF"):
        async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=False)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.devices[device_id].breaker.tripped is True
    await _flush_store(hass, freezer)
    data = hass_storage[STORE_KEY]["data"]
    assert device_id in data[STORE_REVS]
    assert device_id in data[STORE_LAST_ACTED]
    assert device_id in data[STORE_TRIPPED]

    await _delete_only_device(hass, entry)
    await _flush_store(hass, freezer)

    data = hass_storage[STORE_KEY]["data"]
    assert device_id not in data[STORE_REVS]
    assert device_id not in data[STORE_LAST_ACTED]
    assert device_id not in data[STORE_TRIPPED]


async def test_failed_clear_keeps_id_published_and_retry_clears_all_three_topics(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A delete with failing publishes completes, keeps the id published and the next start clears all three topics."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    entry = await _setup(hass, make_hub_entry([sub]))

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ):
        await _delete_only_device(hass, entry)

    assert device_id not in entry.runtime_data.devices
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_PUBLISHED] == [device_id]
    mqtt_mock.async_publish.reset_mock()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for topic in (
        discovery_topic("homeassistant", device_id),
        config_topic(BASE, device_id),
        state_topic(BASE, device_id),
    ):
        assert _publishes(mqtt_mock, topic) == [("", 1, True)]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_PUBLISHED] == []


async def test_orphan_cleanup_clears_the_config_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A published id without a subentry gets an empty publish on discovery, config and state at start."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    _preload_published(hass_storage, [ORPHAN_ID, _device_id(sub)])

    await _setup(hass, make_hub_entry([sub]))

    assert _publishes(mqtt_mock, discovery_topic("homeassistant", ORPHAN_ID)) == [("", 1, True)]
    assert _publishes(mqtt_mock, config_topic(BASE, ORPHAN_ID)) == [("", 1, True)]
    assert _publishes(mqtt_mock, state_topic(BASE, ORPHAN_ID)) == [("", 1, True)]


async def test_hub_removal_path_clears_the_config_topic(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """async_remove_all_devices clears the config topic of every owned and published id as well."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = _device_id(sub)
    _preload_published(hass_storage, [ORPHAN_ID])
    entry = await _setup(hass, make_hub_entry([sub]))

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for owned_id in (device_id, ORPHAN_ID):
        assert _publishes(mqtt_mock, config_topic(BASE, owned_id))[-1] == ("", 1, True)


# --- owner watches its config topic (SYN-03, D-15, D-17) ----------------------------------------------------------

OVERWRITTEN = "doc_overwritten_"
CLAIM = "ownership_claim_"
# D-18 start value; the tests advance the clock by more than one window
WINDOW = 60.0
EVIL_ACTIONS = [{"action": "test.evil"}]
CANARY = "CANARY-7f3a"


def _issue(hass: HomeAssistant, prefix: str, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{prefix}{device_id}")


def _issue_ids(hass: HomeAssistant) -> list[str]:
    return sorted(issue_id for domain, issue_id in ir.async_get(hass).issues if domain == DOMAIN)


async def _deliver(hass: HomeAssistant, topic: str, payload: str | dict[str, Any], *, retain: bool = False) -> None:
    """Deliver one message the way a real broker forwards a live write (retain False), then let handlers finish."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    async_fire_mqtt_message(hass, topic, text, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _foreign(mqtt_mock: Any, owned_id: str, **changes: Any) -> dict[str, Any]:
    """Return the last published document of a device with fields replaced, as another writer would send it."""
    document = copy.deepcopy(_documents(mqtt_mock, owned_id)[-1])
    document.update(changes)
    return document


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float = WINDOW + 1) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _owned(
    hass: HomeAssistant, make_hub_entry: Callable, make_switch_subentry: Callable, name: str = "Lamp"
) -> tuple[MockConfigEntry, str]:
    sub = make_switch_subentry(name, on=ON_ACTIONS)
    return await _setup(hass, make_hub_entry([sub])), _device_id(sub)


async def test_own_echo_is_ignored(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-15: the owner's own document coming back live raises no issue and causes no second publish."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    topic = config_topic(BASE, device_id)
    (payload, _qos, _retain) = _publishes(mqtt_mock, topic)[0]

    await _deliver(hass, topic, payload)

    assert len(_documents(mqtt_mock, device_id)) == 1
    assert _issue_ids(hass) == []


async def test_quick_edits_do_not_look_like_foreign_writes(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-15: two quick edits, then the first document replayed late, raise no issue and no republish."""
    entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    topic = config_topic(BASE, device_id)
    first_payload = _publishes(mqtt_mock, topic)[0][0]
    for title in ("Lamp 2", "Lamp 3"):
        hass.config_entries.async_update_subentry(entry, _only_subentry(entry), title=title)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_documents(mqtt_mock, device_id)) == 3

    await _deliver(hass, topic, first_payload)

    assert len(_documents(mqtt_mock, device_id)) == 3
    assert _issue_ids(hass) == []


async def test_persisted_hash_seeds_the_echo_history(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-15: the document published before an offline edit comes back as an echo, not as a foreign write."""
    entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    topic = config_topic(BASE, device_id)
    previous_payload = _publishes(mqtt_mock, topic)[0][0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_subentry(entry, _only_subentry(entry), title="Lamp renamed")
    mqtt_mock.async_publish.reset_mock()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [doc["rev"] for doc in _documents(mqtt_mock, device_id)] == [2]

    await _deliver(hass, topic, previous_payload, retain=True)

    assert [doc["rev"] for doc in _documents(mqtt_mock, device_id)] == [2]
    assert _issue_ids(hass) == []


async def test_foreign_content_on_my_topic_is_healed_and_reported(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-03-06: foreign content is overwritten by the owner's real document, reported, and never adopted."""
    entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    manager = entry.runtime_data
    spec_before = manager.devices[device_id].spec
    data_before = dict(_only_subentry(entry).data)

    await _deliver(hass, config_topic(BASE, device_id), _foreign(mqtt_mock, device_id, on_change_to_on=EVIL_ACTIONS))

    first, second = _publishes(mqtt_mock, config_topic(BASE, device_id))
    assert second == first
    issue = _issue(hass, OVERWRITTEN, device_id)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.translation_key == "doc_overwritten"
    assert manager.devices[device_id].spec is spec_before
    assert dict(_only_subentry(entry).data) == data_before


async def test_lower_rev_own_document_is_healed_silently(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-15: an older document of this owner (lower rev) is replaced without an issue."""
    entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    hass.config_entries.async_update_subentry(entry, _only_subentry(entry), title="Lamp 2")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_documents(mqtt_mock, device_id)) == 2

    await _deliver(
        hass,
        config_topic(BASE, device_id),
        _foreign(mqtt_mock, device_id, rev=1, on_change_to_on=EVIL_ACTIONS),
    )

    assert [doc["rev"] for doc in _documents(mqtt_mock, device_id)] == [1, 2, 2]
    assert _issue_ids(hass) == []


async def test_equal_content_is_a_noop(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-15: the same content under another rev changes nothing."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)

    await _deliver(hass, config_topic(BASE, device_id), _foreign(mqtt_mock, device_id, rev=99))

    assert len(_documents(mqtt_mock, device_id)) == 1
    assert _issue_ids(hass) == []


async def test_foreign_tombstone_is_healed_and_reported(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-03-06: an empty live payload on the config topic of an owned device is healed and reported."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)

    await _deliver(hass, config_topic(BASE, device_id), "")

    assert len(_documents(mqtt_mock, device_id)) == 2
    assert _issue(hass, OVERWRITTEN, device_id) is not None


@pytest.mark.parametrize(
    "make_payload",
    [
        lambda _doc: f"{CANARY}{{not json",
        lambda doc: json.dumps({**doc, "device_id": "someone-else", "name": CANARY}),
        lambda doc: json.dumps({**doc, "schema_version": 99, "extra": CANARY}),
    ],
    ids=["not-json", "wrong-device-id", "schema-too-new"],
)
async def test_garbage_on_my_topic_is_healed_and_reported(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_payload: Callable[[dict[str, Any]], str],
) -> None:
    """T-03-06: unreadable content is replaced by the real document and reported; no log line carries the payload."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    payload = make_payload(_documents(mqtt_mock, device_id)[-1])

    with caplog.at_level(logging.DEBUG):
        await _deliver(hass, config_topic(BASE, device_id), payload)

    assert len(_documents(mqtt_mock, device_id)) == 2
    assert _issue(hass, OVERWRITTEN, device_id) is not None
    assert CANARY not in caplog.text


async def test_other_owner_claim_raises_ownership_claim_once(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-17: a document of another owner is healed and reported once, naming the claimant."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    claim = _foreign(mqtt_mock, device_id, owner="other-instance", owner_name="Intruder")

    with patch("custom_components.mqtt_actions.sync.ir.async_create_issue", wraps=ir.async_create_issue) as create:
        await _deliver(hass, config_topic(BASE, device_id), claim)
        await _deliver(hass, config_topic(BASE, device_id), claim)

    assert len(_documents(mqtt_mock, device_id)) == 2
    issue = _issue(hass, CLAIM, device_id)
    assert issue is not None
    assert issue.translation_key == "ownership_claim"
    assert issue.translation_placeholders == {"device": "Lamp", "claimant": "Intruder"}
    assert [call.args[2] for call in create.call_args_list] == [f"{CLAIM}{device_id}"]
    assert _issue(hass, OVERWRITTEN, device_id) is None


async def test_heal_is_throttled_with_one_trailing_republish(
    hass: HomeAssistant,
    mqtt_mock: Any,
    freezer: FrozenDateTimeFactory,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-03-07: three foreign writes in one window give one immediate and one trailing republish, then it is idle."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    topic = config_topic(BASE, device_id)
    write = _foreign(mqtt_mock, device_id, on_change_to_on=EVIL_ACTIONS)

    for _ in range(3):
        await _deliver(hass, topic, write)
    assert len(_documents(mqtt_mock, device_id)) == 2
    await _advance(hass, freezer)
    assert len(_documents(mqtt_mock, device_id)) == 3
    # The trailing republish opened a new window that ends without a pending request
    await _advance(hass, freezer)
    assert len(_documents(mqtt_mock, device_id)) == 3

    await _deliver(hass, topic, write)
    assert len(_documents(mqtt_mock, device_id)) == 4


async def test_hostile_claimant_name_is_escaped_in_the_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-03-05: a claimant name with markdown reaches the issue escaped."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    hostile = "[click](https://evil.example)"

    await _deliver(hass, config_topic(BASE, device_id), _foreign(mqtt_mock, device_id, owner="x", owner_name=hostile))

    issue = _issue(hass, CLAIM, device_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["claimant"] == escape_markdown(hostile)
    assert issue.translation_placeholders["claimant"].startswith("\\[click\\]")


async def test_own_delete_is_never_healed(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-03-08: the tombstone and the discovery clear of the owner's own delete cause no republish and no issue."""
    entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)

    await _delete_only_device(hass, entry)
    await _deliver(hass, config_topic(BASE, device_id), "")
    await _deliver(hass, discovery_topic("homeassistant", device_id), "")

    assert [payload for payload, _qos, _retain in _publishes(mqtt_mock, config_topic(BASE, device_id))][1:] == [""]
    assert len(_publishes(mqtt_mock, discovery_topic("homeassistant", device_id))) == 2
    assert _issue_ids(hass) == []


async def test_documents_for_unowned_ids_are_ignored_here(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A valid document for an id this instance does not own creates nothing in the owner branch."""
    _entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    other = _foreign(mqtt_mock, device_id, device_id="someone-elses-device", owner="x", owner_name="Other")
    mqtt_mock.async_publish.reset_mock()

    await _deliver(hass, config_topic(BASE, "someone-elses-device"), other)

    assert mqtt_mock.async_publish.call_args_list == []
    assert _issue_ids(hass) == []


async def test_stop_releases_subscription_and_timers(
    hass: HomeAssistant,
    mqtt_mock: Any,
    freezer: FrozenDateTimeFactory,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """After unload a foreign write publishes nothing and a pending trailing republish does nothing."""
    entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    topic = config_topic(BASE, device_id)
    write = _foreign(mqtt_mock, device_id, on_change_to_on=EVIL_ACTIONS)
    await _deliver(hass, topic, write)
    await _deliver(hass, topic, write)
    assert await hass.config_entries.async_unload(entry.entry_id)
    mqtt_mock.async_publish.reset_mock()

    await _advance(hass, freezer)
    await _deliver(hass, topic, write)
    await _advance(hass, freezer)

    assert mqtt_mock.async_publish.call_args_list == []


@pytest.mark.parametrize("path", ["delete_device", "remove_hub"])
async def test_delete_and_hub_removal_delete_the_overwrite_issues(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    path: str,
) -> None:
    """Deleting the device and removing the hub delete the overwrite and claim issues of the device."""
    entry, device_id = await _owned(hass, make_hub_entry, make_switch_subentry)
    await _deliver(hass, config_topic(BASE, device_id), "")
    await _deliver(hass, config_topic(BASE, device_id), _foreign(mqtt_mock, device_id, owner="x", owner_name="Other"))
    assert _issue_ids(hass) == [f"{CLAIM}{device_id}", f"{OVERWRITTEN}{device_id}"]

    if path == "delete_device":
        await _delete_only_device(hass, entry)
    else:
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert _issue_ids(hass) == []
