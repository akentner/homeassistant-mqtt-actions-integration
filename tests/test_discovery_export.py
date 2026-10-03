"""The optional MQTT Discovery export of native devices: payload, options and republish (D-03, D-04, D-11, ENT-03)."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import probatio
import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import discovery
from custom_components.mqtt_actions.const import (
    CONF_DELETE_DEVICES_ON_REMOVE,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_EXPORT,
    CONF_EXPORT_PREFIX,
    DEFAULT_EXPORT_PREFIX,
    DOMAIN,
    STORE_KEY,
    STORE_VERSION,
    SUBENTRY_SELECT,
)
from custom_components.mqtt_actions.model import spec_from_data
from custom_components.mqtt_actions.mqtt_gateway import MqttGateway
from custom_components.mqtt_actions.topics import availability_topic, discovery_topic, state_topic
from tests.documents import make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

CORE_PREFIX = "homeassistant"
EXPORT_ON = {CONF_DISCOVERY_EXPORT: True}


def _seed_native(hass_storage: dict[str, Any]) -> None:
    """Seed the persisted native flag the way production stores it."""
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {"native": {"instance": True, "pending": [], "devices": []}},
    }


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


def _export_topic(device_id: str, prefix: str = DEFAULT_EXPORT_PREFIX) -> str:
    return discovery_topic(prefix, device_id)


def _only_payload(mqtt_mock: Any, topic: str) -> dict[str, Any]:
    ((payload, _qos, _retain),) = _publishes(mqtt_mock, topic)
    return json.loads(payload)


# --- the payload (D-11) ----------------------------------------------------------------------------------------------


def test_build_export_has_one_component_no_buttons_and_is_disabled_by_default() -> None:
    """D-11: one component, disabled by default, no test button, no test topic and no tombstone entry."""
    switch_spec = spec_from_data("switch", "Lamp", {CONF_DEVICE_ID: "dev-1"})
    select_spec = make_spec(SUBENTRY_SELECT, device_id="dev-2", name="Mode", options=[("a", "A", []), ("b", "B", [])])

    for spec, kind in ((switch_spec, "switch"), (select_spec, "select")):
        payload = discovery.build_export(spec=spec, base_topic="mqtt_actions", instance_id="inst-1", sw_version="1.2.3")

        assert payload["device"] == {"identifiers": [f"mqtt_actions_{spec.device_id}"], "name": spec.name}
        assert payload["origin"] == {"name": "MQTT Actions", "sw_version": "1.2.3"}
        assert payload["availability"] == [{"topic": "mqtt_actions/v1/instances/inst-1/availability"}]
        assert list(payload["components"]) == [kind]
        component = payload["components"][kind]
        assert component["enabled_by_default"] is False
        assert component["unique_id"] == spec.device_id
        assert component["state_topic"] == component["command_topic"] == state_topic("mqtt_actions", spec.device_id)
        assert "/test" not in json.dumps(payload)
        assert "button" not in json.dumps(payload)
        assert json.loads(json.dumps(payload)) == payload


# --- the tracer: publish on the export prefix ------------------------------------------------------------------------


async def test_a_native_device_publishes_the_export_when_enabled(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03, D-11: the retained export is published on the export prefix and nothing on the core discovery prefix."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    await _setup(hass, make_hub_entry([subentry], options=EXPORT_ON))

    ((payload, qos, retain),) = _publishes(mqtt_mock, _export_topic(device_id))
    assert (qos, retain) == (1, True)
    exported = json.loads(payload)
    assert list(exported["components"]) == ["switch"]
    assert exported["components"]["switch"]["enabled_by_default"] is False
    assert _publishes(mqtt_mock, discovery_topic(CORE_PREFIX, device_id)) == []


async def test_the_export_is_off_by_default(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-03: without the option a native device publishes nothing on any discovery topic."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    await _setup(hass, make_hub_entry([subentry]))

    topics = [call.args[0] for call in mqtt_mock.async_publish.call_args_list]
    assert [topic for topic in topics if "/device/" in topic and topic.endswith("/config")] == []
    assert _export_topic(device_id) not in topics
    assert discovery_topic(CORE_PREFIX, device_id) not in topics


async def test_the_export_on_the_core_prefix_creates_a_disabled_duplicate(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-5-17: on the prefix core listens to, the export becomes a disabled mqtt entry and the native entity stays."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    entry = await _setup(
        hass, make_hub_entry([subentry], options={CONF_DISCOVERY_EXPORT: True, CONF_EXPORT_PREFIX: CORE_PREFIX})
    )
    topic = discovery_topic(CORE_PREFIX, device_id)
    ((payload, _qos, _retain),) = _publishes(mqtt_mock, topic)
    # The mocked client keeps no retained messages; core hears the export as the replay a real broker would deliver
    async_fire_mqtt_message(hass, availability_topic("mqtt_actions", entry.data["instance_id"]), "online")
    async_fire_mqtt_message(hass, topic, payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    registry = er.async_get(hass)
    exported = registry.async_get_entity_id("switch", "mqtt", device_id)
    native = registry.async_get_entity_id("switch", DOMAIN, device_id)
    assert exported is not None
    assert native is not None
    assert registry.async_get(exported).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry.async_get(native).disabled_by is None
    enabled = [
        entity.entity_id
        for entity in registry.entities.values()
        if entity.unique_id == device_id and entity.disabled_by is None
    ]
    assert enabled == [native]


async def test_a_legacy_device_never_publishes_the_export(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A device on the legacy path publishes the legacy payload only, whatever the export option says."""
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)

    await _setup(hass, make_hub_entry([subentry], options=EXPORT_ON))

    assert _publishes(mqtt_mock, _export_topic(device_id)) == []
    legacy = _only_payload(mqtt_mock, discovery_topic(CORE_PREFIX, device_id))
    assert any(key.startswith("test_") for key in legacy["components"])


async def test_the_export_has_no_healing(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-11: an empty retained payload on the export topic is not published again and nothing watches the prefix."""
    _seed_native(hass_storage)
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)
    subscribed: list[str] = []
    real_subscribe = MqttGateway.async_subscribe

    async def _recording(self: MqttGateway, topic: str, *args: Any, **kwargs: Any) -> Any:
        subscribed.append(topic)
        return await real_subscribe(self, topic, *args, **kwargs)

    with patch.object(MqttGateway, "async_subscribe", _recording):
        await _setup(hass, make_hub_entry([subentry], options=EXPORT_ON))

    assert len(_publishes(mqtt_mock, _export_topic(device_id))) == 1
    async_fire_mqtt_message(hass, _export_topic(device_id), "", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(_publishes(mqtt_mock, _export_topic(device_id))) == 1
    assert not [topic for topic in subscribed if topic.startswith(DEFAULT_EXPORT_PREFIX)]


# --- the hub options (D-03, D-11) ------------------------------------------------------------------------------------

TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations"


async def _native_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
    *,
    options: dict[str, Any] | None = None,
) -> tuple[MockConfigEntry, list[str]]:
    """Set up a native instance with one Switch and one Select and the given hub options."""
    _seed_native(hass_storage)
    switch = make_switch_subentry("Lamp")
    select = make_select_subentry("Mode", [("a", "A", []), ("b", "B", [])])
    entry = await _setup(hass, make_hub_entry([switch, select], options=options or {}))
    return entry, [_device_id(switch), _device_id(select)]


async def _submit(hass: HomeAssistant, entry: MockConfigEntry, user_input: dict[str, Any]) -> dict[str, Any]:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    await hass.async_block_till_done(wait_background_tasks=True)
    return result


async def test_the_options_flow_offers_the_export_and_stores_what_is_submitted(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The form carries the delete choice, the export switch and the prefix; only submitted keys are stored."""
    entry = await _setup(hass, make_hub_entry())

    form = await hass.config_entries.options.async_init(entry.entry_id)
    assert form["type"] is FlowResultType.FORM
    fields = {
        field["name"]: field
        for field in probatio.to_field_list(form["data_schema"], custom_serializer=cv.custom_serializer)
    }
    assert set(fields) == {CONF_DELETE_DEVICES_ON_REMOVE, CONF_DISCOVERY_EXPORT, CONF_EXPORT_PREFIX}
    assert fields[CONF_DISCOVERY_EXPORT]["selector"] == {"boolean": {}}
    assert fields[CONF_EXPORT_PREFIX]["selector"] == {"text": {"multiline": False, "multiple": False}}
    suggested = {key.schema: key.description.get("suggested_value") for key in form["data_schema"].schema}
    assert suggested[CONF_DISCOVERY_EXPORT] is False
    assert suggested[CONF_EXPORT_PREFIX] == DEFAULT_EXPORT_PREFIX

    saved = await hass.config_entries.options.async_configure(form["flow_id"], {CONF_DELETE_DEVICES_ON_REMOVE: True})
    assert saved["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_DELETE_DEVICES_ON_REMOVE: True}

    saved = await _submit(
        hass,
        entry,
        {CONF_DELETE_DEVICES_ON_REMOVE: False, CONF_DISCOVERY_EXPORT: True, CONF_EXPORT_PREFIX: "my/export"},
    )
    assert saved["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_DELETE_DEVICES_ON_REMOVE: False,
        CONF_DISCOVERY_EXPORT: True,
        CONF_EXPORT_PREFIX: "my/export",
    }
    again = await hass.config_entries.options.async_init(entry.entry_id)
    suggested = {key.schema: key.description.get("suggested_value") for key in again["data_schema"].schema}
    assert suggested[CONF_DISCOVERY_EXPORT] is True
    assert suggested[CONF_EXPORT_PREFIX] == "my/export"


@pytest.mark.parametrize("prefix", ["export/#", "a/+/b", "export//x", "/export", "export/", "$SYS/export", ""])
async def test_an_invalid_export_prefix_is_refused(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, prefix: str
) -> None:
    """T-5-17: a prefix that is no valid topic prefix returns the error and stores nothing."""
    entry = await _setup(hass, make_hub_entry(options={CONF_DELETE_DEVICES_ON_REMOVE: True}))

    result = await _submit(hass, entry, {CONF_DISCOVERY_EXPORT: True, CONF_EXPORT_PREFIX: prefix})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_EXPORT_PREFIX: "invalid_export_prefix"}
    assert entry.options == {CONF_DELETE_DEVICES_ON_REMOVE: True}


async def test_changing_the_prefix_moves_the_export(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """The old export topic of every native device is cleared and the new one carries the export."""
    entry, device_ids = await _native_entry(
        hass, hass_storage, make_hub_entry, make_switch_subentry, make_select_subentry, options=EXPORT_ON
    )
    mqtt_mock.async_publish.reset_mock()

    await _submit(hass, entry, {CONF_DISCOVERY_EXPORT: True, CONF_EXPORT_PREFIX: "other_export"})

    for device_id in device_ids:
        assert _publishes(mqtt_mock, _export_topic(device_id)) == [("", 1, True)]
        ((payload, qos, retain),) = _publishes(mqtt_mock, _export_topic(device_id, "other_export"))
        assert (qos, retain) == (1, True)
        assert json.loads(payload)["components"]
    topics = [call.args[0] for call in mqtt_mock.async_publish.call_args_list]
    for device_id in device_ids:
        assert topics.index(_export_topic(device_id)) < topics.index(_export_topic(device_id, "other_export"))


async def test_switching_the_export_off_clears_the_topics(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """The empty retained payload goes to the export topic of every native device and nothing is published again."""
    entry, device_ids = await _native_entry(
        hass, hass_storage, make_hub_entry, make_switch_subentry, make_select_subentry, options=EXPORT_ON
    )
    mqtt_mock.async_publish.reset_mock()

    await _submit(hass, entry, {CONF_DELETE_DEVICES_ON_REMOVE: False})

    for device_id in device_ids:
        assert _publishes(mqtt_mock, _export_topic(device_id)) == [("", 1, True)]
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    for device_id in device_ids:
        assert _publishes(mqtt_mock, _export_topic(device_id)) == [("", 1, True)]


async def test_switching_the_export_on_publishes_without_a_reload(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """Enabling the option on a running native instance publishes the export from the entry update."""
    entry, device_ids = await _native_entry(
        hass, hass_storage, make_hub_entry, make_switch_subentry, make_select_subentry
    )
    manager = entry.runtime_data
    for device_id in device_ids:
        assert _publishes(mqtt_mock, _export_topic(device_id)) == []

    await _submit(hass, entry, {CONF_DISCOVERY_EXPORT: True})

    assert entry.runtime_data is manager
    for device_id in device_ids:
        ((payload, _qos, retain),) = _publishes(mqtt_mock, _export_topic(device_id))
        assert retain is True
        assert json.loads(payload)["components"]


async def test_the_export_follows_option_changes_for_native_devices_only(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """A legacy device is skipped by the republish: it neither gets an export nor an export clear."""
    subentry = make_switch_subentry("Lamp")
    device_id = _device_id(subentry)
    entry = await _setup(hass, make_hub_entry([subentry]))
    mqtt_mock.async_publish.reset_mock()

    await _submit(hass, entry, {CONF_DISCOVERY_EXPORT: True})

    assert _publishes(mqtt_mock, _export_topic(device_id)) == []


def test_the_option_strings_exist_in_both_languages() -> None:
    """The two fields and the prefix error have a text in English and German."""
    for language in ("en", "de"):
        translations = json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
        step = translations["options"]["step"]["init"]
        for key in (CONF_DISCOVERY_EXPORT, CONF_EXPORT_PREFIX):
            assert step["data"][key]
            assert step["data_description"][key]
        assert translations["options"]["error"]["invalid_export_prefix"]
