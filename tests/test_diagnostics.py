"""The diagnostics download shows structure, never content: an allow-list, short ids and sentinel checks (D-17)."""

import json
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.mqtt_actions.const import CONF_INSTANCE_ID, SUBENTRY_SELECT
from custom_components.mqtt_actions.topics import config_topic, heartbeat_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
SESSION = "6f1c0f0e-3a52-4f43-8d0c-5a0b7f3c9d21"
PEER_ID = "peer-instance-0123456789abcdef"
SHORT = 8

# Sentinels: none of them may appear anywhere in the serialized diagnostics
S_OWN_ENTITY = "light.sentinel_own_entity"
S_OWN_DATA = "SENTINEL_OWN_SERVICE_DATA"
S_OWN_NAME = "SENTINEL OWN DEVICE NAME"
S_MIRROR_ENTITY = "light.sentinel_mirror_entity"
S_MIRROR_TEMPLATE = "SENTINEL_MIRROR_TEMPLATE"
S_MIRROR_LABEL = "SENTINEL MIRROR LABEL"
S_MIRROR_VALUE = "sentinelmirrorvalue"
S_MIRROR_NAME = "SENTINEL MIRROR DEVICE NAME"
SENTINELS = (
    S_OWN_ENTITY,
    S_OWN_DATA,
    S_OWN_NAME,
    S_MIRROR_ENTITY,
    S_MIRROR_TEMPLATE,
    S_MIRROR_LABEL,
    S_MIRROR_VALUE,
    S_MIRROR_NAME,
)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


async def _deliver(hass: HomeAssistant, device_id: str, payload: str) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _heartbeat(hass: HomeAssistant, instance_id: str, name: str = "Peer") -> None:
    payload = json.dumps(
        {"instance_id": instance_id, "name": name, "version": "0.1.0", "devices": 1, "session": SESSION}
    )
    async_fire_mqtt_message(hass, heartbeat_topic(BASE, instance_id), payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _diagnostics(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, Any]:
    from custom_components.mqtt_actions.diagnostics import async_get_config_entry_diagnostics

    return await async_get_config_entry_diagnostics(hass, entry)


async def _hub_with_owned_device_and_mirror(
    hass: HomeAssistant, make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[MockConfigEntry, str, str]:
    """Return a loaded hub with one owned Switch and one delivered Select mirror, both full of sentinels."""
    sub = make_switch_subentry(
        S_OWN_NAME,
        on=[{"action": "test.on", "target": {"entity_id": S_OWN_ENTITY}, "data": {"message": S_OWN_DATA}}],
    )
    own_id = sub["data"]["device_id"]
    mirror = make_spec(
        SUBENTRY_SELECT,
        name=S_MIRROR_NAME,
        options=[
            (
                S_MIRROR_VALUE,
                S_MIRROR_LABEL,
                [
                    {"action": "test.on", "target": {"entity_id": S_MIRROR_ENTITY}},
                    {"action": "test.say", "data": {"message": "{{ '" + S_MIRROR_TEMPLATE + "' }}"}},
                ],
            ),
            ("other", "Other", []),
        ],
    )
    entry = await _setup(hass, make_hub_entry([sub]))
    await _deliver(hass, mirror.device_id, document_payload(mirror))
    await _heartbeat(hass, PEER_ID)
    return entry, own_id, mirror.device_id


async def test_diagnostics_structure(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The result serializes and names the hub, the roster and one row per owned device and mirror."""
    entry, own_id, mirror_id = await _hub_with_owned_device_and_mirror(hass, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)

    result = await _diagnostics(hass, entry)

    json.dumps(result)
    hub = result["hub"]
    assert hub["base_topic"] == BASE
    assert hub["instance_name"] == "Test instance"
    assert hub["instance_id"] == entry.data[CONF_INSTANCE_ID][:SHORT]
    assert len(hub["instance_id"]) == SHORT
    assert hub["instance_mode"] == manager.instance_mode
    assert hub["instance_id"] in [row["id"] for row in result["roster"]]
    rows = {row["uuid"]: row for row in result["devices"]}
    assert set(rows) == {own_id, mirror_id}
    assert rows[own_id]["kind"] == "switch"
    assert rows[own_id]["origin"] == "owned"
    assert rows[own_id]["owner"] == entry.data[CONF_INSTANCE_ID][:SHORT]
    assert rows[own_id]["approval"] == "owned"
    assert rows[mirror_id]["kind"] == "select"
    assert rows[mirror_id]["origin"] == "mirror"
    assert rows[mirror_id]["owner"] == FOREIGN_OWNER[:SHORT]
    assert rows[mirror_id]["approval"] == "pending"


async def test_sentinel_strings_never_appear_in_the_output(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """No action content, no device name and no full instance id is in the serialized diagnostics (T-04-27, T-04-29)."""
    entry, _own_id, mirror_id = await _hub_with_owned_device_and_mirror(hass, make_hub_entry, make_switch_subentry)
    own_instance = entry.data[CONF_INSTANCE_ID]
    assert await _manager(entry).async_approve(mirror_id, _manager(entry).mirrors[mirror_id].mirror.actions_hash), (
        "an approved mirror must leak nothing either"
    )

    text = json.dumps(await _diagnostics(hass, entry))

    assert len(SENTINELS) >= 5
    for sentinel in SENTINELS:
        assert sentinel not in text
    for full_id in (own_instance, FOREIGN_OWNER, PEER_ID):
        assert full_id not in text
    for short_id in (own_instance[:SHORT], FOREIGN_OWNER[:SHORT], PEER_ID[:SHORT]):
        assert short_id in text
