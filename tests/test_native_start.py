"""The native takeover pass at the start of the manager: owners, followers, deferral and adoption (D-05, D-09, D-12)."""

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import DEFAULT

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    DOMAIN,
    STORE_KEY,
    STORE_MIRRORS,
    STORE_VERSION,
)
from custom_components.mqtt_actions.topics import config_topic, discovery_topic, state_topic
from tests.documents import document_payload, make_spec
from tests.test_takeover import (
    CLEAR_PAYLOAD,
    PREFIX,
    customize_mqtt_device,
    legacy_entity_ids,
    setup_legacy_device,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"


def _seed(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {"version": STORE_VERSION, "minor_version": 1, "key": STORE_KEY, "data": data}


def _seed_native(hass_storage: dict[str, Any], *, pending: list[str], instance: bool = True) -> None:
    """Seed the persisted native state of an instance whose devices still wait for the takeover."""
    _seed(hass_storage, {"native": {"instance": instance, "pending": pending, "devices": []}})


def _stored_pending(hass_storage: dict[str, Any]) -> list[str]:
    return hass_storage[STORE_KEY]["data"]["native"]["pending"]


def _loop_back_discovery(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """
    Deliver every publish on a discovery topic back to core MQTT as a live message, the way a real broker would.

    The mocked client does not loop publishes back, so without this the migrate payload would never unload the legacy
    entities. Live delivery matches production: a migrate payload is never retained.
    """

    def _deliver(topic: str, payload: Any, *_args: Any, **_kwargs: Any) -> Any:
        if topic.startswith(f"{PREFIX}/"):
            async_fire_mqtt_message(hass, topic, payload, retain=False)
        return DEFAULT

    mqtt_mock.async_publish.side_effect = _deliver


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple[Any, bool]]:
    """Return the (payload, retain) pairs published on a topic, in order."""
    return [(call.args[1], call.args[3]) for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _all_topics(mqtt_mock: Any) -> list[str]:
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _restart(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Unload and set up the entry again, the way an update of the integration does."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


@pytest.fixture(autouse=True)
def fast_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll quickly; the default wait is long only because production waits for a real broker round trip."""
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)


# --- Task 1 tracer: the owner pass ---------------------------------------------------------------------------------


async def test_an_upgrade_takes_over_the_legacy_entities_and_marks_the_document(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-05, D-09, D-12, MIG-01: migrate, move, retained clear, in that order; every identity of the device is kept."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_id = legacy.device_id
    customize_mqtt_device(hass, device_id, area_id="kitchen", name_by_user="Stehlampe")
    switch_id = entity_registry.async_get_entity_id("switch", "mqtt", device_id)
    assert switch_id is not None
    legacy_ids = legacy_entity_ids(hass, device_id)
    assert len(legacy_ids) == 3  # the switch and the two test buttons
    before = {entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_ids}
    mqtt_device = device_registry.async_get_device_by_identifier(
        ("mqtt", f"{DOMAIN}_{device_id}"), hass.config_entries.async_entries("mqtt")[0].entry_id
    )
    assert mqtt_device is not None
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    _seed_native(hass_storage, pending=[device_id])
    mqtt_mock.async_publish.reset_mock()
    _loop_back_discovery(hass, mqtt_mock)

    assert await hass.config_entries.async_setup(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    sub_id = next(iter(legacy.entry.subentries.values())).subentry_id
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform, moved.device_id) == (old.id, DOMAIN, mqtt_device.id)
        assert (moved.config_entry_id, moved.config_subentry_id) == (legacy.entry.entry_id, sub_id)
    assert entity_registry.async_get_entity_id("switch", DOMAIN, device_id) == switch_id
    assert hass.states.get(switch_id) is not None
    device = device_registry.async_get(mqtt_device.id)
    assert device is not None
    assert (device.area_id, device.name_by_user) == ("kitchen", "Stehlampe")
    assert (device.config_entry_id, device.config_subentry_id) == (legacy.entry.entry_id, sub_id)
    assert device.identifiers == {(DOMAIN, device_id)}
    assert _stored_pending(hass_storage) == []

    published = _publishes(mqtt_mock, legacy.topic)
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in published] == [
        ({"migrate_discovery": True}, False),
        (CLEAR_PAYLOAD, True),
    ]
    document = json.loads(_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert document["entities"] == "native"


async def test_a_device_without_legacy_entities_still_gets_the_migrate_and_the_clear(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A fresh install has no legacy registry entry, but followers may: the migrate and the clear go out anyway."""
    subentry = make_switch_subentry("Lamp")
    device_id = subentry["data"][CONF_DEVICE_ID]
    _seed_native(hass_storage, pending=[device_id])

    await _setup(hass, make_hub_entry([subentry]))

    published = _publishes(mqtt_mock, discovery_topic(PREFIX, device_id))
    assert [(json.loads(payload) if payload else payload, retain) for payload, retain in published] == [
        ({"migrate_discovery": True}, False),
        (CLEAR_PAYLOAD, True),
    ]
    assert _stored_pending(hass_storage) == []


async def test_the_pass_never_publishes_for_an_id_that_is_not_owned(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-5-02: a pending id that is no owned device, a mirror for one, causes no publish on any topic of that id."""
    mirror_spec = make_spec(name="Foreign lamp")
    unknown_id = "unknown-device-id"
    own = make_switch_subentry("Lamp")
    _seed(
        hass_storage,
        {
            STORE_MIRRORS: {mirror_spec.device_id: document_payload(mirror_spec)},
            "native": {"instance": True, "pending": [mirror_spec.device_id, unknown_id], "devices": []},
        },
    )

    entry = await _setup(hass, make_hub_entry([own]))

    assert mirror_spec.device_id in _manager(entry).mirrors
    for foreign_id in (mirror_spec.device_id, unknown_id):
        assert not [topic for topic in _all_topics(mqtt_mock) if foreign_id in topic]
    assert _stored_pending(hass_storage) == []


async def test_a_second_start_runs_no_pass(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """With nothing pending no migrate and no clear is published, and the marked documents go out again."""
    subentry = make_switch_subentry("Lamp")
    device_id = subentry["data"][CONF_DEVICE_ID]
    _seed_native(hass_storage, pending=[])

    entry = await _setup(hass, make_hub_entry([subentry]))

    assert _publishes(mqtt_mock, discovery_topic(PREFIX, device_id)) == []
    first = json.loads(_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert first["entities"] == "native"
    mqtt_mock.async_publish.reset_mock()

    await _restart(hass, entry)

    assert _publishes(mqtt_mock, discovery_topic(PREFIX, device_id)) == []
    second = json.loads(_publishes(mqtt_mock, config_topic(BASE, device_id))[-1][0])
    assert second["entities"] == "native"
    assert state_topic(BASE, device_id) not in _all_topics(mqtt_mock)
