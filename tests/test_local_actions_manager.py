"""
Local actions of mirrors through the Manager (MIR-02, D-02, D-07, D-21).

`test_pending_mirror_with_persisted_additive_record_gains_local_branch` is the only expected-RED test of Phase 11
(11-VALIDATION.md, "Expected-RED Exception"). It was committed by Plan 11-01 Task 2 before the Manager reads the
separate local Store; its GREEN gate is Plan 11-05 Task 1, which may align the seeded record to the Plan 11-04 schema
but never changes an assertion. No marker or condition ever hides its failure.
"""

from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import PAYLOAD_OFF, PAYLOAD_ON, SUBENTRY_SWITCH
from custom_components.mqtt_actions.topics import state_topic
from tests.documents import document_payload, make_spec
from tests.helpers import BASE, deliver_config, manager_of, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

# Literal on purpose: Plan 11-04 declares LOCAL_ACTIONS_STORE_KEY with this value
LOCAL_STORE_KEY = "mqtt_actions.local_actions"


def _seed_local_store(hass_storage: dict[str, Any], records: list[dict[str, Any]]) -> None:
    """Write local records as an HA Store v1 envelope under the production local key."""
    hass_storage[LOCAL_STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCAL_STORE_KEY,
        "data": {"records": records},
    }


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_pending_mirror_with_persisted_additive_record_gains_local_branch(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """
    D-02: a saved additive record runs its trusted local actions on a pending mirror; the owner branch stays out.

    Expected RED until Plan 11-05 Task 1: today the Manager ignores the separate local Store and refuses the whole
    pending mirror, so neither the local nor the owner service runs and the local call count is 0 instead of 1.
    """
    owner_calls = async_mock_service(hass, "test", "owner_on")
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(on=[{"action": "test.owner_on"}], off=[{"action": "test.owner_off"}])
    _seed_local_store(
        hass_storage,
        [
            {
                "device_id": spec.device_id,
                "kind": SUBENTRY_SWITCH,
                "state_value": PAYLOAD_ON,
                "label": "On",
                "mode": "additive",
                "actions": [{"action": "test.local_on", "data": {"source": "local"}}],
            }
        ],
    )
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    manager = manager_of(entry)
    assert str(manager.approval_state(spec.device_id)) == "pending", "premise: the owner actions are not approved"

    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)

    assert len(local_calls) == 1, f"the local branch of the pending mirror ran {len(local_calls)} times, expected 1"
    assert owner_calls == [], "the unapproved owner branch must never run"
    assert str(manager.approval_state(spec.device_id)) == "pending", "local actions never approve the owner"
