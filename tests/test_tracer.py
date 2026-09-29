"""Tracer: one Switch travels from the UI flows to a locally executed action."""

import ast
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    SUBENTRY_SWITCH,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / DOMAIN


def _publishes(mqtt_mock, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


async def test_switch_end_to_end(hass: HomeAssistant, mqtt_mock) -> None:
    """Hub flow, switch subentry flow, discovery, live edge and retained replay."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")

    # Behavior 1: hub flow creates an entry with a uuid4 instance id and the default base topic (D-11)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_TOPIC: DEFAULT_BASE_TOPIC, CONF_INSTANCE_NAME: "Test instance"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data[CONF_BASE_TOPIC] == "mqtt_actions"
    instance_id = entry.data[CONF_INSTANCE_ID]
    assert uuid.UUID(instance_id).version == 4
    await hass.async_block_till_done()

    # Behavior 2: the switch subentry flow stores a uuid4 device id equal to the subentry unique_id (D-03)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_SWITCH), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Lamp",
            CONF_ON_CHANGE_TO_ON: [{"action": "test.on"}],
            CONF_ON_CHANGE_TO_OFF: [{"action": "test.off"}],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    (subentry,) = entry.subentries.values()
    device_id = subentry.data[CONF_DEVICE_ID]
    assert uuid.UUID(device_id).version == 4
    assert subentry.unique_id == device_id

    # Behavior 3: retained qos-1 discovery and a retained online availability message
    state_topic = f"mqtt_actions/v1/devices/{device_id}/state"
    ((payload, qos, retain),) = _publishes(mqtt_mock, f"homeassistant/device/{device_id}/config")
    assert qos == 1
    assert retain is True
    discovery = json.loads(payload)
    switch = discovery["components"]["switch"]
    assert switch["unique_id"] == device_id
    assert switch["state_topic"] == state_topic
    assert switch["command_topic"] == state_topic
    assert _publishes(mqtt_mock, f"mqtt_actions/v1/instances/{instance_id}/availability")[-1] == ("online", 1, True)

    # Behavior 4: a live ON message runs the ON actions once
    async_fire_mqtt_message(hass, state_topic, "ON", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(on_calls) == 1
    assert len(off_calls) == 0

    # Behavior 5: a retained replay only moves the baseline and runs nothing (D-05)
    async_fire_mqtt_message(hass, state_topic, "OFF", retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(off_calls) == 0
    assert len(on_calls) == 1


def test_only_gateway_imports_mqtt_component() -> None:
    """Only mqtt_gateway.py may import the built-in mqtt integration (fake-broker seam for later phases)."""
    offenders: list[str] = []
    for path in sorted(COMPONENT_DIR.rglob("*.py")):
        if path.name == "mqtt_gateway.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                names = [base, *(f"{base}.{alias.name}" for alias in node.names)]
            else:
                continue
            if any(
                name == "homeassistant.components.mqtt" or name.startswith("homeassistant.components.mqtt.")
                for name in names
            ):
                offenders.append(path.name)
    assert offenders == []
