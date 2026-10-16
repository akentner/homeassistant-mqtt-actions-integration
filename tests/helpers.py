"""
Helpers shared by several test modules (D-11).

Test modules import shared helpers only from here, never from each other.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any, NamedTuple
from unittest.mock import DEFAULT

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component import plugins
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_fire_time_changed

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    DOMAIN,
    STORE_KEY,
    STORE_MIRRORS,
    STORE_VERSION,
)
from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic
from tests.documents import FOREIGN_OWNER, document_payload

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.manager import Manager


# The documented diagnostics key sets; an unknown key fails the test, which is the point (D-17)
TOP_KEYS = {"integration_version", "hub", "roster", "devices"}
HUB_KEYS = {"base_topic", "instance_name", "instance_id", "instance_mode"}
ROSTER_KEYS = {"id", "name", "version", "last_seen", "online"}
DEVICE_KEYS = {"uuid", "kind", "origin", "owner", "mode", "effective_mode", "approval", "breaker", "rev", "hash"}


PREFIX = "homeassistant"
MIGRATE_PAYLOAD = json.dumps({"migrate_discovery": True})
CLEAR_PAYLOAD = ""
BASE = "mqtt_actions"
CORE_PREFIX = "homeassistant"
# Longer than the production quiet period, and a literal on purpose: a RED run against code without the production
# constant must fail on an assertion about the duplicates, not on a missing name
QUIET_PERIOD_PASSED = 10.0


class LegacyDevice(NamedTuple):
    """A v0.1.0-style device whose discovery core MQTT consumed: the entry, its device id, topic and payload."""

    entry: MockConfigEntry
    device_id: str
    topic: str
    payload: str


async def setup_legacy_device(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    name: str = "Lamp",
) -> LegacyDevice:
    """
    Set up a hub entry with one switch device exactly as the current code behaves and let core MQTT discover it.

    The manager publishes the device-based discovery payload; the mocked client does not loop publishes back, so the
    payload is fed to core as the retained replay a real broker would deliver. Core then creates the real discovered
    switch and the two test buttons.
    """
    sub = make_switch_subentry(name)
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    device_id = sub["data"][CONF_DEVICE_ID]
    topic = discovery_topic(PREFIX, device_id)
    payload = last_published_payload(mqtt_mock, topic)
    async_fire_mqtt_message(hass, availability_topic(entry.data["base_topic"], entry.data[CONF_INSTANCE_ID]), "online")
    async_fire_mqtt_message(hass, topic, payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    return LegacyDevice(entry, device_id, topic, payload)


def last_published_payload(mqtt_mock: Any, topic: str) -> str:
    """Return the last payload the manager published on a topic, read from the mocked MQTT client."""
    payloads = [call.args[1] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]
    assert payloads, f"nothing was published on {topic}"
    return payloads[-1]


def core_mqtt_entry_id(hass: HomeAssistant) -> str:
    return hass.config_entries.async_entries("mqtt")[0].entry_id


def customize_mqtt_device(hass: HomeAssistant, device_id: str, *, area_id: str, name_by_user: str) -> dr.DeviceEntry:
    """Set area and user name on the core MQTT device of a legacy device and return the updated device entry."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), core_mqtt_entry_id(hass))
    assert device is not None
    updated = device_registry.async_update_device(device.id, area_id=area_id, name_by_user=name_by_user)
    assert updated is not None
    return updated


def legacy_entity_ids(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return the entity ids of the registry entries core MQTT created for a device (switch and test buttons)."""
    return [
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == "mqtt"
        and (entry.unique_id == device_id or entry.unique_id.startswith(f"{device_id}_test_"))
    ]


def discovery_clears(mqtt_mock: Any, topic: str) -> list[Any]:
    """Return the empty payloads published on the discovery topic."""
    return [call for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic and call.args[1] == ""]


def falsy_publishes(mqtt_mock: Any, topic: str) -> list[Any]:
    """Return every clear on the topic: core MQTT clears with None, which `discovery_clears` does not see."""
    return [call for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic and not call.args[1]]


def seed_store(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {"version": STORE_VERSION, "minor_version": 1, "key": STORE_KEY, "data": data}


def seed_native_pending(hass_storage: dict[str, Any], *, pending: list[str], instance: bool = True) -> None:
    """Seed the persisted native state of an instance whose devices still wait for the takeover."""
    seed_store(hass_storage, {"native": {"instance": instance, "pending": pending, "devices": []}})


def loop_back_discovery(hass: HomeAssistant, mqtt_mock: Any) -> None:
    """
    Deliver every publish on a discovery topic back to core MQTT as a live message, the way a real broker would.

    The mocked paho client already loops a publish back with the publish's own retain flag, so a retained clear would
    reach core as a retained replay, which core drops when it saw a retained message on the topic before. A live
    delivery makes core handle the clear like it does in production. The migrate payload is live either way.

    Core removes a loaded duplicate by publishing an empty retained payload, which the mocked client hands on as None;
    `async_fire_mqtt_message` cannot take None, so it gets the empty string, the same removal on the wire.
    """

    def _deliver(topic: str, payload: Any, *_args: Any, **_kwargs: Any) -> Any:
        if topic.startswith(f"{PREFIX}/"):
            async_fire_mqtt_message(hass, topic, "" if payload is None else payload, retain=False)
        return DEFAULT

    mqtt_mock.async_publish.side_effect = _deliver


def block_discovery_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Stop the mocked paho client from looping publishes on a discovery topic back, so core MQTT never hears them.

    That is a broker that has not delivered the owner's migrate payload (yet): the legacy entities stay loaded.
    """
    original = plugins.async_fire_mqtt_message

    def _fire(hass: HomeAssistant, topic: str, *args: Any, **kwargs: Any) -> None:
        if not topic.startswith(f"{PREFIX}/"):
            original(hass, topic, *args, **kwargs)

    monkeypatch.setattr(plugins, "async_fire_mqtt_message", _fire)


def topic_publishes(mqtt_mock: Any, topic: str) -> list[tuple[Any, bool]]:
    """Return the (payload, retain) pairs published on a topic, in order."""
    return [(call.args[1], call.args[3]) for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def restart_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Unload and set up the entry again, the way an update of the integration does."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def manager_of(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


async def legacy_mirror(hass: HomeAssistant, make_hub_entry: Callable, spec: Any) -> tuple[MockConfigEntry, str]:
    """Set up a follower with an unmarked mirror whose legacy core MQTT entities exist; return it and the topic."""
    entry = await setup_entry(hass, make_hub_entry())
    topic = discovery_topic(PREFIX, spec.device_id)
    discovery = build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3")
    async_fire_mqtt_message(hass, topic, json.dumps(discovery), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), document_payload(spec), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(legacy_entity_ids(hass, spec.device_id)) == 3
    assert spec.device_id in manager_of(entry).mirrors
    return entry, topic


def store_the_mirror_as_native(hass_storage: dict[str, Any], spec: Any) -> None:
    """Replace the cached document of the mirror by the marked one, as if the owner had upgraded and been heard."""
    hass_storage[STORE_KEY]["data"][STORE_MIRRORS][spec.device_id] = document_payload(spec, native=True)


def mqtt_device_of(hass: HomeAssistant, device_id: str) -> dr.DeviceEntry | None:
    mqtt_entry_id = hass.config_entries.async_entries("mqtt")[0].entry_id
    return dr.async_get(hass).async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry_id)


async def unloaded_legacy_device(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> tuple[Any, dict[str, er.RegistryEntry]]:
    """Return a legacy device whose entry is unloaded and pending for the takeover, and its legacy registry entries."""
    legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    before = {
        entity_id: entity_registry.async_get(entity_id) for entity_id in legacy_entity_ids(hass, legacy.device_id)
    }
    assert await hass.config_entries.async_unload(legacy.entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    seed_native_pending(hass_storage, pending=[legacy.device_id])
    mqtt_mock.async_publish.reset_mock()
    return legacy, before


def assert_moved_and_native(hass: HomeAssistant, legacy: Any, before: dict[str, er.RegistryEntry]) -> None:
    """Assert that the entities of the device sit under this integration, loaded, and that the device is native."""
    entity_registry = er.async_get(hass)
    assert legacy.entry.runtime_data.is_native(legacy.device_id) is True
    for entity_id, old in before.items():
        moved = entity_registry.async_get(entity_id)
        assert moved is not None
        assert (moved.id, moved.platform) == (old.id, DOMAIN)
        state = hass.states.get(entity_id)
        assert state is not None
        assert not state.attributes.get("restored")


def native_entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


def topic_publishes_with_qos(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


async def deliver_config(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = True) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def announce_presence(
    hass: HomeAssistant, status: str, owner: str = FOREIGN_OWNER, *, retain: bool = True
) -> None:
    async_fire_mqtt_message(hass, availability_topic(BASE, owner), status, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def create_mqtt_row(hass: HomeAssistant, domain: str, unique_id: str, *, device: bool = False) -> str:
    """Create an enabled registry row of core MQTT, optionally on the MQTT device the export payload names."""
    mqtt_entry = hass.config_entries.async_entries("mqtt")[0]
    device_id = None
    if device:
        mqtt_device = dr.async_get(hass).async_get_or_create(
            config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", f"mqtt_actions_{unique_id}")}
        )
        device_id = mqtt_device.id
    row = er.async_get(hass).async_get_or_create(
        domain, "mqtt", unique_id, config_entry=mqtt_entry, device_id=device_id
    )
    assert row.disabled_by is None
    return row.entity_id


async def replay_discovery(hass: HomeAssistant, topic: str, payload: str, device_id: str) -> list[str]:
    """Play a legacy Discovery payload live (core ignores a second retained message per topic) and return the ids."""
    async_fire_mqtt_message(hass, topic, payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    return legacy_entity_ids(hass, device_id)


async def quiet_period_passes(hass: HomeAssistant) -> None:
    """Let the quiet period pass for the timers of the integration and run what they start."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=QUIET_PERIOD_PASSED))
    await hass.async_block_till_done(wait_background_tasks=True)
