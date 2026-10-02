"""Hub removal keeps every device on the broker by default and deletes everywhere only on an explicit option (D-11)."""

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import probatio
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir

from custom_components.mqtt_actions import manager as manager_module
from custom_components.mqtt_actions.config_flow import MqttActionsConfigFlow
from custom_components.mqtt_actions.const import (
    CONF_DELETE_DEVICES_ON_REMOVE,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    DOMAIN,
    ISSUE_DEVICE_PREFIXES,
    ISSUE_DISCOVERY_DISABLED,
    STORE_KEY,
    STORE_PUBLISHED,
    STORE_VERSION,
)
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from tests.fake_broker import FakeBroker, FakeGateway

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on"}]
ORPHAN_ID = "5d9c1b0e-7c55-4c1e-8a11-0f7c3a9b2d44"


def _preload_store(hass_storage: dict[str, Any], key: str = STORE_KEY, *, published: list[str]) -> None:
    hass_storage[key] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": {STORE_PUBLISHED: published},
    }


async def _setup(hass: HomeAssistant, entry: Any) -> Any:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _empty_publishes(mqtt_mock: Any) -> list[str]:
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list if call.args[1] in {"", b""}]


def _own_issues(hass: HomeAssistant) -> list[str]:
    return sorted(issue_id for domain, issue_id in ir.async_get(hass).issues if domain == DOMAIN)


def _create_issues(hass: HomeAssistant, device_id: str) -> None:
    """Create one issue per per-device family plus the discovery-disabled issue."""
    for prefix in ISSUE_DEVICE_PREFIXES:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{prefix}{device_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="action_failed",
            translation_placeholders={"trigger": "t", "device": "d", "time": "now", "error": "e"},
        )
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_DISCOVERY_DISABLED,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_DISCOVERY_DISABLED,
    )


# ----------------------------------------------------------------------------------------------- options flow


async def test_hub_has_options_flow_with_delete_choice(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    entry = await _setup(hass, make_hub_entry())

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    fields = {
        field["name"]: field
        for field in probatio.to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    }
    assert set(fields) == {CONF_DELETE_DEVICES_ON_REMOVE}
    assert fields[CONF_DELETE_DEVICES_ON_REMOVE]["selector"] == {"boolean": {}}
    assert not any(key.description and key.description.get("suggested_value") for key in result["data_schema"].schema)

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_DELETE_DEVICES_ON_REMOVE: True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_DELETE_DEVICES_ON_REMOVE: True}

    # The stored choice is what the form shows the next time
    again = await hass.config_entries.options.async_init(entry.entry_id)
    (key,) = again["data_schema"].schema
    assert key.description["suggested_value"] is True
    # A hub still has no reconfigure step (D-01)
    assert not hasattr(MqttActionsConfigFlow, "async_step_reconfigure")


async def test_saving_the_option_publishes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    devices_before = dict(entry.runtime_data.devices)
    mqtt_mock.async_publish.reset_mock()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {CONF_DELETE_DEVICES_ON_REMOVE: True})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert mqtt_mock.async_publish.call_args_list == []
    assert entry.runtime_data.devices == devices_before


# ---------------------------------------------------------------------------------------------------- removal


async def test_remove_with_default_keeps_everything_retained(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-03-11: without the option nothing on the broker is cleared; the local state and every issue go."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    _preload_store(hass_storage, published=[ORPHAN_ID])
    entry = await _setup(hass, make_hub_entry([sub]))
    _create_issues(hass, device_id)
    mqtt_mock.async_publish.reset_mock()

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _empty_publishes(mqtt_mock) == []
    assert STORE_KEY not in hass_storage
    assert _own_issues(hass) == []
    assert hass.config_entries.async_get_entry(entry.entry_id) is None


async def test_remove_with_delete_clears_everywhere(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    _preload_store(hass_storage, published=[ORPHAN_ID])
    entry = await _setup(hass, make_hub_entry([sub], options={CONF_DELETE_DEVICES_ON_REMOVE: True}))
    instance_id = entry.data[CONF_INSTANCE_ID]
    _create_issues(hass, device_id)

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for owned_id in (device_id, ORPHAN_ID):
        assert _publishes(mqtt_mock, discovery_topic("homeassistant", owned_id))[-1] == ("", 1, True)
        assert _publishes(mqtt_mock, config_topic(BASE, owned_id))[-1] == ("", 1, True)
        assert _publishes(mqtt_mock, state_topic(BASE, owned_id))[-1] == ("", 1, True)
    assert _publishes(mqtt_mock, availability_topic(BASE, instance_id))[-1] == ("", 1, True)
    assert STORE_KEY not in hass_storage
    assert _own_issues(hass) == []


async def test_keep_leaves_the_offline_availability(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-11: orphans of a kept hub show unavailable, so the last availability publish is offline, not empty."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    instance_id = entry.data[CONF_INSTANCE_ID]

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _publishes(mqtt_mock, availability_topic(BASE, instance_id))[-1] == ("offline", 1, True)


@pytest.mark.parametrize("delete", [False, True], ids=["keep", "delete"])
async def test_both_modes_remove_store_and_every_issue_prefix(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    delete: bool,
) -> None:
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    options = {CONF_DELETE_DEVICES_ON_REMOVE: True} if delete else {}
    entry = await _setup(hass, make_hub_entry([sub], options=options))
    _create_issues(hass, device_id)
    assert len(_own_issues(hass)) == len(ISSUE_DEVICE_PREFIXES) + 1

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert STORE_KEY not in hass_storage
    assert _own_issues(hass) == []


async def test_delete_mode_survives_unavailable_mqtt(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    entry = await _setup(
        hass,
        make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)], options={CONF_DELETE_DEVICES_ON_REMOVE: True}),
    )
    assert await hass.config_entries.async_unload(entry.entry_id)

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ):
        assert await hass.config_entries.async_remove(entry.entry_id)

    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert STORE_KEY not in hass_storage
    assert [r for r in caplog.records if r.levelno == logging.WARNING and "MQTT" in r.getMessage()]


async def test_keep_mode_needs_no_mqtt(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    assert await hass.config_entries.async_unload(entry.entry_id)
    caplog.clear()

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ) as publish:
        assert await hass.config_entries.async_remove(entry.entry_id)

    publish.assert_not_called()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert STORE_KEY not in hass_storage
    assert [r for r in caplog.records if r.levelno == logging.WARNING and "MQTT" in r.getMessage()] == []


# ------------------------------------------------------------------------------------------ test seams


async def test_removal_functions_accept_gateway_and_store_key(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    gateway = FakeGateway(FakeBroker(), hass)
    _preload_store(hass_storage, "x.state", published=[ORPHAN_ID])
    _preload_store(hass_storage, STORE_KEY, published=[])

    await manager_module.async_remove_all_devices(hass, entry, gateway=gateway, store_key="x.state")

    cleared = {topic for topic, payload, retain in gateway.published if payload == "" and retain}
    for owned_id in (device_id, ORPHAN_ID):
        assert {
            discovery_topic("homeassistant", owned_id),
            config_topic(BASE, owned_id),
            state_topic(BASE, owned_id),
        } <= cleared
    assert availability_topic(BASE, entry.data[CONF_INSTANCE_ID]) in cleared
    assert "x.state" not in hass_storage
    # The production key is untouched: the seam removes only what it was given
    assert STORE_KEY in hass_storage

    _preload_store(hass_storage, "x.state", published=[ORPHAN_ID])
    published_before = len(gateway.published)
    await manager_module.async_remove_local_state(hass, entry, store_key="x.state")
    assert "x.state" not in hass_storage
    assert len(gateway.published) == published_before
    assert STORE_KEY in hass_storage

    # Without the keywords the production defaults apply
    await manager_module.async_remove_local_state(hass, entry)
    assert STORE_KEY not in hass_storage
