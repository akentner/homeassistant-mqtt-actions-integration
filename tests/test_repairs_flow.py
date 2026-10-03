"""Approval through Repairs: the issue lifecycle, the fix flow, hash binding, the race abort and a safe view (D-02)."""

import json
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.mqtt_actions import const, repairs
from custom_components.mqtt_actions.const import (
    APPROVAL_HASH_PREFIX_LENGTH,
    CONF_INSTANCE_ID,
    DOMAIN,
    HEARTBEAT_OFFLINE_SECONDS,
    ISSUE_APPROVAL_PREFIX,
    ISSUE_BLOCKED_PREFIX,
    ISSUE_DENIED_CALL_PREFIX,
)
from custom_components.mqtt_actions.document import escape_markdown
from custom_components.mqtt_actions.manager import async_remove_local_state
from custom_components.mqtt_actions.topics import availability_topic, config_topic, heartbeat_topic, state_topic
from tests.documents import FOREIGN_OWNER_NAME, document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on", "target": {"entity_id": "light.lamp"}}]
OFF_ACTIONS = [{"action": "test.off"}]
OTHER_ACTIONS = [{"action": "test.other"}]
BEL = chr(7)
RLO = chr(0x202E)
EMPTY_LIST = "—"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


async def _deliver(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = True) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = False) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _issue(hass: HomeAssistant, prefix: str, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{prefix}{device_id}")


def _actions_hash(entry: MockConfigEntry, device_id: str) -> str:
    info = _manager(entry).mirrors[device_id].mirror
    assert info is not None
    return info.actions_hash


async def _start_flow(hass: HomeAssistant, device_id: str) -> dict[str, Any]:
    """Open the fix flow of the approval issue the way the Repairs dialog does."""
    return await hass.data["repairs"]["flow_manager"].async_init(
        DOMAIN, data={"issue_id": f"{ISSUE_APPROVAL_PREFIX}{device_id}"}
    )


async def _submit(hass: HomeAssistant, flow_id: str) -> dict[str, Any]:
    return await hass.data["repairs"]["flow_manager"].async_configure(flow_id, {})


async def _pending(
    hass: HomeAssistant, make_hub_entry: Callable, **spec_kwargs: Any
) -> tuple[MockConfigEntry, str, Any]:
    """Set up a hub with the mirror of a foreign device that nobody approved; return the entry, the id and the spec."""
    spec_kwargs.setdefault("on", ON_ACTIONS)
    spec = make_spec(**spec_kwargs)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    return entry, spec.device_id, spec


# --- issue lifecycle ------------------------------------------------------------------------------------------------


async def test_approval_issue_is_created_fixable_with_hash_data(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A mirror with actions raises one fixable request bound to its hash; approved, empty and owned have none."""
    pending_spec = make_spec(on=ON_ACTIONS, name="Pending")
    approved_spec = make_spec(on=ON_ACTIONS, name="Approved")
    empty_spec = make_spec(name="Empty")
    own = make_switch_subentry("Own", on=ON_ACTIONS)
    own_id = own["data"]["device_id"]
    entry = await _setup(hass, make_hub_entry([own]))
    manager = _manager(entry)
    for spec in (pending_spec, approved_spec, empty_spec):
        await _deliver(hass, spec.device_id, document_payload(spec))
    assert await manager.async_approve(approved_spec.device_id, _actions_hash(entry, approved_spec.device_id))

    issue = _issue(hass, ISSUE_APPROVAL_PREFIX, pending_spec.device_id)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "approval_required"
    assert issue.data == {
        "device_id": pending_spec.device_id,
        "actions_hash": _actions_hash(entry, pending_spec.device_id),
    }
    assert issue.translation_placeholders == {
        "device": "Pending",
        "owner": escape_markdown(FOREIGN_OWNER_NAME),
        "hash": _actions_hash(entry, pending_spec.device_id)[:APPROVAL_HASH_PREFIX_LENGTH],
    }
    for device_id in (approved_spec.device_id, empty_spec.device_id, own_id):
        assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is None


async def test_owner_change_raises_a_new_request_and_lapses_the_approval(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """After approval a changed document deletes the old request, raises a new one and the mirror cannot run."""
    entry, device_id, spec = await _pending(hass, make_hub_entry)
    manager = _manager(entry)
    first_hash = _actions_hash(entry, device_id)
    assert await manager.async_approve(device_id, first_hash)
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is None

    changed = make_spec(device_id=device_id, on=OTHER_ACTIONS)
    await _deliver(hass, device_id, document_payload(changed, rev=2), retain=False)

    issue = _issue(hass, ISSUE_APPROVAL_PREFIX, device_id)
    assert issue is not None
    assert issue.data == {"device_id": device_id, "actions_hash": _actions_hash(entry, device_id)}
    assert issue.data["actions_hash"] != first_hash
    assert manager.runner.script_count(device_id) == 0
    assert spec.device_id == device_id


async def test_dismissed_issue_does_not_hide_a_changed_request(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Pitfall 8: dismissing a request never hides the next one, because the old issue is deleted first."""
    entry, device_id, _spec = await _pending(hass, make_hub_entry)
    issue_id = f"{ISSUE_APPROVAL_PREFIX}{device_id}"
    ir.async_ignore_issue(hass, DOMAIN, issue_id, True)
    dismissed = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert dismissed is not None
    assert dismissed.dismissed_version is not None

    await _deliver(
        hass, device_id, document_payload(make_spec(device_id=device_id, on=OTHER_ACTIONS), rev=2), retain=False
    )

    renewed = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert renewed is not None
    assert renewed.dismissed_version is None
    assert renewed.data is not None
    assert renewed.data["actions_hash"] == _actions_hash(entry, device_id)


async def test_issues_are_recreated_at_start(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, hass_storage: dict[str, Any]
) -> None:
    """A pending mirror raises its request again after a restart; an approved one has a Script and no request."""
    pending, approved = make_spec(on=ON_ACTIONS, name="Pending"), make_spec(on=OFF_ACTIONS, name="Approved")
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, pending.device_id, document_payload(pending))
    await _deliver(hass, approved.device_id, document_payload(approved))
    assert await _manager(entry).async_approve(approved.device_id, _actions_hash(entry, approved.device_id))
    assert await hass.config_entries.async_unload(entry.entry_id)
    for spec in (pending, approved):
        ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_APPROVAL_PREFIX}{spec.device_id}")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _issue(hass, ISSUE_APPROVAL_PREFIX, pending.device_id) is not None
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, approved.device_id) is None
    assert _manager(entry).runner.script_count(approved.device_id) == 1
    assert _manager(entry).runner.script_count(pending.device_id) == 0


async def test_blocked_mirror_raises_a_non_fixable_blocked_issue(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A statically denied mirror is explained, never approvable; removing the service turns it into a request."""
    _entry, device_id, _spec = await _pending(
        hass, make_hub_entry, on=[{"action": "shell_command.x"}, {"action": "mqtt.publish"}], name="Risky"
    )

    blocked = _issue(hass, ISSUE_BLOCKED_PREFIX, device_id)
    assert blocked is not None
    assert blocked.is_fixable is False
    assert blocked.translation_key == "mirror_blocked"
    assert blocked.translation_placeholders is not None
    assert set(blocked.translation_placeholders) == {"device", "owner", "services"}
    assert escape_markdown("shell_command.x") in blocked.translation_placeholders["services"]
    assert escape_markdown("mqtt.publish") in blocked.translation_placeholders["services"]
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is None

    await _deliver(
        hass, device_id, document_payload(make_spec(device_id=device_id, on=ON_ACTIONS), rev=2), retain=False
    )

    assert _issue(hass, ISSUE_BLOCKED_PREFIX, device_id) is None
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is not None


async def test_remove_mirror_deletes_approval_blocked_and_denied_issues(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A tombstone deletes every approval related issue of the device."""
    _entry, device_id, _spec = await _pending(hass, make_hub_entry)
    for prefix in (ISSUE_BLOCKED_PREFIX, ISSUE_DENIED_CALL_PREFIX):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{prefix}{device_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="mirror_blocked" if prefix == ISSUE_BLOCKED_PREFIX else "denied_service_call",
        )
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is not None

    await _deliver(hass, device_id, "", retain=False)

    for prefix in (ISSUE_APPROVAL_PREFIX, ISSUE_BLOCKED_PREFIX, ISSUE_DENIED_CALL_PREFIX):
        assert _issue(hass, prefix, device_id) is None


# --- the fix flow ---------------------------------------------------------------------------------------------------


async def test_platform_contract_async_create_fix_flow() -> None:
    """Core finds the flow factory by the module name repairs; it must exist and return the approval flow."""
    from custom_components.mqtt_actions import repairs

    assert callable(repairs.async_create_fix_flow)
    assert repairs.ApprovalRepairFlow.__name__ == "ApprovalRepairFlow"


async def test_flow_shows_device_owner_yaml_hash_and_templates(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The form carries the escaped names, the hash prefix, the YAML of every non-empty list and templated names."""
    entry, device_id, _spec = await _pending(
        hass, make_hub_entry, on=[*ON_ACTIONS, {"action": "{{ 'notify.notify' }}"}], name="Lamp"
    )

    result = await _start_flow(hass, device_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    placeholders = result["description_placeholders"]
    assert set(placeholders) == {
        "device",
        "owner",
        "hash",
        "actions",
        "startup",
        "run_mode",
        "breaker_max_runs",
        "breaker_window",
        "templated",
        "residual",
        "invalid",
    }
    assert placeholders["startup"] == "false"
    assert placeholders["device"] == "Lamp"
    assert placeholders["owner"] == escape_markdown(FOREIGN_OWNER_NAME)
    assert placeholders["hash"] == _actions_hash(entry, device_id)[:APPROVAL_HASH_PREFIX_LENGTH]
    assert "onChangeToOn:" in placeholders["actions"]
    assert "action: test.on" in placeholders["actions"]
    assert "onChangeToOff" not in placeholders["actions"]
    assert placeholders["templated"] == "- {{ 'notify.notify' }}"
    assert placeholders["residual"] == EMPTY_LIST
    assert placeholders["invalid"] == EMPTY_LIST


async def test_flow_states_the_startup_flag_the_hash_binds(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """WR-02: a device that also runs at startup says so in the dialog; the flag is part of the approved hash."""
    _entry, device_id, _spec = await _pending(hass, make_hub_entry, run_on_startup=True)

    result = await _start_flow(hass, device_id)

    assert result["description_placeholders"]["startup"] == "true"


async def test_confirm_form_placeholders_include_settings(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The confirm form also supplies the run mode and both breaker limits the approval hash binds (D-16)."""
    _entry, device_id, _spec = await _pending(
        hass, make_hub_entry, run_mode="restart", breaker_max_runs=3, breaker_window=7
    )

    result = await _start_flow(hass, device_id)

    placeholders = result["description_placeholders"]
    assert placeholders["run_mode"] == "restart"
    assert placeholders["breaker_max_runs"] == "3"
    assert placeholders["breaker_window"] == "7"


async def test_residual_and_invalid_actions_are_listed(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Step kinds the denylist cannot judge and triggers that do not validate here are listed, not dropped."""
    unknown_device = {"device_id": "no-such-device", "domain": "light", "type": "turn_on", "entity_id": "light.x"}
    entry, device_id, _spec = await _pending(
        hass,
        make_hub_entry,
        on=[{"action": "script.turn_on", "target": {"entity_id": "script.x"}}, {"scene": "scene.movie"}],
        off=[unknown_device],
    )

    result = await _start_flow(hass, device_id)

    placeholders = result["description_placeholders"]
    assert escape_markdown("script.turn_on") in placeholders["residual"]
    assert "scene" in placeholders["residual"]
    assert "device" in placeholders["residual"]
    assert "onChangeToOff" in placeholders["invalid"]
    assert device_id in _manager(entry).mirrors
    assert _issue(hass, ISSUE_BLOCKED_PREFIX, device_id) is None
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is not None


async def test_submit_approves_and_the_issue_disappears(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Submitting approves the displayed hash, deletes the issue, builds the Script; the next edge runs."""
    on_calls = async_mock_service(hass, "test", "on")
    entry, device_id, _spec = await _pending(hass, make_hub_entry)
    await _state(hass, device_id, "OFF", retain=True)
    result = await _start_flow(hass, device_id)

    done = await _submit(hass, result["flow_id"])

    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is None
    assert _manager(entry)._approvals == {device_id: _actions_hash(entry, device_id)}
    assert _manager(entry).runner.script_count(device_id) == 1
    await _state(hass, device_id, "ON")
    assert len(on_calls) == 1


async def test_closing_the_dialog_leaves_the_mirror_paused(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A flow that is started and never submitted stores nothing and keeps the request."""
    entry, device_id, _spec = await _pending(hass, make_hub_entry)
    result = await _start_flow(hass, device_id)

    hass.data["repairs"]["flow_manager"].async_abort(result["flow_id"])

    assert _manager(entry)._approvals == {}
    assert _manager(entry).runner.script_count(device_id) == 0
    assert _issue(hass, ISSUE_APPROVAL_PREFIX, device_id) is not None


async def test_race_owner_edits_while_the_dialog_is_open_aborts(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-03-29: the form shows H1, the owner publishes H2, the submit aborts and neither hash is stored."""
    entry, device_id, _spec = await _pending(hass, make_hub_entry)
    first_hash = _actions_hash(entry, device_id)
    result = await _start_flow(hass, device_id)
    assert result["description_placeholders"]["hash"] == first_hash[:APPROVAL_HASH_PREFIX_LENGTH]

    await _deliver(
        hass, device_id, document_payload(make_spec(device_id=device_id, on=OTHER_ACTIONS), rev=2), retain=False
    )
    second_hash = _actions_hash(entry, device_id)
    assert second_hash != first_hash
    done = await _submit(hass, result["flow_id"])

    assert done["type"] is FlowResultType.ABORT
    assert done["reason"] == "changed"
    assert _manager(entry)._approvals == {}
    assert _manager(entry).runner.script_count(device_id) == 0
    renewed = _issue(hass, ISSUE_APPROVAL_PREFIX, device_id)
    assert renewed is not None
    assert renewed.data is not None
    assert renewed.data["actions_hash"] == second_hash


async def test_too_long_actions_refuse_approval(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """Actions too long to show in full are refused, not shown truncated, and nothing is stored."""
    entry, device_id, _spec = await _pending(hass, make_hub_entry)

    with patch("custom_components.mqtt_actions.trust.APPROVAL_YAML_MAX_CHARS", 10):
        result = await _start_flow(hass, device_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "too_large"
    assert _manager(entry)._approvals == {}


async def test_flow_aborts_when_the_entry_is_not_loaded(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Without a loaded hub entry the flow cannot approve anything."""
    entry, device_id, _spec = await _pending(hass, make_hub_entry)
    assert await hass.config_entries.async_unload(entry.entry_id)

    result = await _start_flow(hass, device_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


# --- broker-supplied text (T-03-28) ---------------------------------------------------------------------------------


async def test_hostile_names_and_yaml_are_neutralized(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Names are escaped, fence runs and control characters are removed from the YAML, nothing is shown raw."""
    hostile_name = "[pay](https://evil.example) `x` <b>"
    hostile_data = {"message": f"hi{BEL} ```yaml\n```` {RLO} end"}
    spec = make_spec(on=[{"action": "notify.notify", "data": hostile_data}], name=hostile_name)
    await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec, owner_name="[owner](x) `o`"))

    result = await _start_flow(hass, spec.device_id)
    issue = _issue(hass, ISSUE_APPROVAL_PREFIX, spec.device_id)

    assert issue is not None
    assert issue.translation_placeholders is not None
    placeholders = result["description_placeholders"]
    for texts in (placeholders, issue.translation_placeholders):
        for key in ("device", "owner"):
            assert "[" not in texts[key].replace("\\[", "")
            assert "`" not in texts[key].replace("\\`", "")
            assert "<" not in texts[key].replace("\\<", "")
    actions = placeholders["actions"]
    assert "```" not in actions
    assert BEL not in actions
    assert RLO not in actions
    assert "message" in actions


async def test_submit_after_the_entry_unloaded_aborts(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A dialog that stays open while the integration unloads approves nothing."""
    entry, device_id, _spec = await _pending(hass, make_hub_entry)
    manager = _manager(entry)
    result = await _start_flow(hass, device_id)
    assert await hass.config_entries.async_unload(entry.entry_id)

    done = await _submit(hass, result["flow_id"])

    assert done["type"] is FlowResultType.ABORT
    assert done["reason"] == "not_loaded"
    assert manager._approvals == {}


# --- the duplicate instance id issue and its fix flow (D-07, D-08) ----------------------------------------------------

FOREIGN_SESSION = "6f1c0f0e-3a52-4f43-8d0c-5a0b7f3c9d21"


def _use_clock(manager: Manager) -> list[float]:
    now = [1000.0]
    manager.clock = lambda: now[0]
    return now


async def _own_id_heartbeat(hass: HomeAssistant, entry: MockConfigEntry, session: str = FOREIGN_SESSION) -> None:
    """Deliver a live heartbeat with this instance's own id and another session."""
    instance_id = entry.data[CONF_INSTANCE_ID]
    payload = json.dumps(
        {"instance_id": instance_id, "name": "Clone", "version": "0.1.0", "devices": 1, "session": session}
    )
    async_fire_mqtt_message(hass, heartbeat_topic(BASE, instance_id), payload)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _duplicate_setup(
    hass: HomeAssistant, make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[MockConfigEntry, list[float]]:
    """Set up a hub with one device and let it confirm a duplicate instance id."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    now = _use_clock(_manager(entry))
    await _own_id_heartbeat(hass, entry)
    await _own_id_heartbeat(hass, entry)
    return entry, now


def _duplicate_issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, const.ISSUE_DUPLICATE_INSTANCE_ID)


async def _start_duplicate_flow(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.data["repairs"]["flow_manager"].async_init(
        DOMAIN, data={"issue_id": const.ISSUE_DUPLICATE_INSTANCE_ID}
    )


async def test_duplicate_issue_is_created_once_and_cleared(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-07: one fixable error issue after two foreign sessions, a dismissal stays, 90 seconds of silence deletes it."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    manager = _manager(entry)
    now = _use_clock(manager)
    await _own_id_heartbeat(hass, entry)
    assert _duplicate_issue(hass) is None

    await _own_id_heartbeat(hass, entry)

    issue = _duplicate_issue(hass)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == "duplicate_instance_id"
    assert issue.translation_placeholders == {"instance": escape_markdown(manager.instance_name)}
    assert issue.data == {"instance_id": manager.instance_id}

    ir.async_ignore_issue(hass, DOMAIN, const.ISSUE_DUPLICATE_INSTANCE_ID, True)
    await _own_id_heartbeat(hass, entry)
    dismissed = _duplicate_issue(hass)
    assert dismissed is not None
    assert dismissed.dismissed_version is not None

    now[0] += HEARTBEAT_OFFLINE_SECONDS + 2
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HEARTBEAT_OFFLINE_SECONDS + 5))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _duplicate_issue(hass) is None


async def test_duplicate_issue_is_removed_with_the_hub(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    entry, _now = await _duplicate_setup(hass, make_hub_entry, make_switch_subentry)
    assert _duplicate_issue(hass) is not None

    await async_remove_local_state(hass, entry)

    assert _duplicate_issue(hass) is None


async def test_dispatcher_returns_the_right_flow(hass: HomeAssistant) -> None:
    """The issue id decides: the duplicate id flow for its issue, the approval flow for everything else."""
    duplicate = await repairs.async_create_fix_flow(hass, const.ISSUE_DUPLICATE_INSTANCE_ID, {"instance_id": "x"})
    approval = await repairs.async_create_fix_flow(hass, f"{ISSUE_APPROVAL_PREFIX}abc", {"device_id": "abc"})
    other = await repairs.async_create_fix_flow(hass, "something_else", None)
    transferred = await repairs.async_create_fix_flow(
        hass, f"{const.ISSUE_TRANSFERRED_PREFIX}abc", {"device_id": "abc"}
    )

    assert isinstance(transferred, repairs.TransferredRepairFlow)
    assert isinstance(duplicate, repairs.DuplicateIdRepairFlow)
    assert isinstance(approval, repairs.ApprovalRepairFlow)
    assert isinstance(other, repairs.ApprovalRepairFlow)


async def test_duplicate_flow_form_and_confirmation(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-08: the form names the instance and the device count; a submit releases locally and publishes no clear."""
    entry, _now = await _duplicate_setup(hass, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)
    old_id = manager.instance_id
    mark = len(mqtt_mock.async_publish.call_args_list)

    result = await _start_duplicate_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"instance": escape_markdown(manager.instance_name), "devices": "1"}
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        done = await _submit(hass, result["flow_id"])
    await hass.async_block_till_done(wait_background_tasks=True)

    assert done["type"] is FlowResultType.CREATE_ENTRY
    schedule.assert_called_once_with(entry.entry_id)
    assert entry.data[CONF_INSTANCE_ID] != old_id
    assert str(uuid.UUID(entry.data[CONF_INSTANCE_ID])) == entry.data[CONF_INSTANCE_ID]
    assert manager.devices == {}
    assert len(entry.subentries) == 0
    assert _duplicate_issue(hass) is None
    await manager.async_stop()
    sent = mqtt_mock.async_publish.call_args_list[mark:]
    assert [call for call in sent if call.args[1] == ""] == []
    assert [call for call in sent if call.args[0] == availability_topic(BASE, old_id)] == []


async def test_duplicate_flow_aborts(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The flow does nothing when the entry is not loaded or when the instance id is not the current one."""
    entry, _now = await _duplicate_setup(hass, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)
    old_id = manager.instance_id
    ir.async_create_issue(
        hass,
        DOMAIN,
        const.ISSUE_DUPLICATE_INSTANCE_ID,
        data={"instance_id": "an-earlier-id"},
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="duplicate_instance_id",
        translation_placeholders={"instance": "x"},
    )

    stale = await _start_duplicate_flow(hass)
    assert stale["type"] is FlowResultType.ABORT
    assert stale["reason"] == "changed"
    assert entry.data[CONF_INSTANCE_ID] == old_id
    assert len(manager.devices) == 1

    ir.async_create_issue(
        hass,
        DOMAIN,
        const.ISSUE_DUPLICATE_INSTANCE_ID,
        data={"instance_id": old_id},
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="duplicate_instance_id",
        translation_placeholders={"instance": "x"},
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    unloaded = await _start_duplicate_flow(hass)
    assert unloaded["type"] is FlowResultType.ABORT
    assert unloaded["reason"] == "not_loaded"
    assert entry.data[CONF_INSTANCE_ID] == old_id


# --- the returning old owner: the transferred issue and its release flow (D-09 refined) -------------------------------


def _transferred_issue(hass: HomeAssistant, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{const.ISSUE_TRANSFERRED_PREFIX}{device_id}")


async def _start_transferred_flow(hass: HomeAssistant, device_id: str) -> dict[str, Any]:
    return await hass.data["repairs"]["flow_manager"].async_init(
        DOMAIN, data={"issue_id": f"{const.ISSUE_TRANSFERRED_PREFIX}{device_id}"}
    )


async def _owned_and_transferred(
    hass: HomeAssistant, make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[MockConfigEntry, str]:
    """Set up a hub that owns a lamp with a baseline, then deliver the adopter's valid document that names this hub."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    device_id = sub["data"]["device_id"]
    entry = await _setup(hass, make_hub_entry([sub]))
    await _state(hass, device_id, "ON", retain=True)
    adopter = make_spec(device_id=device_id, name="Lamp", on=ON_ACTIONS, off=OFF_ACTIONS)
    payload = document_payload(adopter, rev=2, transferred_from=[entry.data[CONF_INSTANCE_ID]])
    await _deliver(hass, device_id, payload, retain=False)
    return entry, device_id


async def test_release_flow_follows_the_adopter(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-09: the form names device and claimant; a submit releases locally and follows the adopter as a mirror."""
    entry, device_id = await _owned_and_transferred(hass, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)
    issue = _transferred_issue(hass, device_id)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.data == {"device_id": device_id, "claimant": "instance-foreign"}
    assert device_id in manager.devices
    mark = len(mqtt_mock.async_publish.call_args_list)

    result = await _start_transferred_flow(hass, device_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "device": escape_markdown("Lamp"),
        "claimant": escape_markdown(FOREIGN_OWNER_NAME),
    }
    done = await _submit(hass, result["flow_id"])
    await hass.async_block_till_done(wait_background_tasks=True)

    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert device_id not in manager.devices
    assert len(entry.subentries) == 0
    mirror = manager.mirrors[device_id]
    assert mirror.mirror is not None
    assert mirror.mirror.owner == "instance-foreign"
    assert mirror.tracker.last_acted == "ON"
    assert _transferred_issue(hass, device_id) is None
    sent = mqtt_mock.async_publish.call_args_list[mark:]
    assert [call for call in sent if call.args[1] == ""] == []
    assert [call for call in sent if call.args[0] == config_topic(BASE, device_id)] == []


async def test_transferred_flow_aborts(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The flow changes nothing when the entry is not loaded, the claimant differs or the device is not owned."""
    entry, device_id = await _owned_and_transferred(hass, make_hub_entry, make_switch_subentry)
    manager = _manager(entry)

    for data, reason in (
        ({"device_id": device_id, "claimant": "someone-else"}, "changed"),
        ({"device_id": "unknown-device", "claimant": "instance-foreign"}, "changed"),
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{const.ISSUE_TRANSFERRED_PREFIX}probe",
            data=data,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="transferred",
            translation_placeholders={"device": "x", "claimant": "y"},
        )
        probe = await hass.data["repairs"]["flow_manager"].async_init(
            DOMAIN, data={"issue_id": f"{const.ISSUE_TRANSFERRED_PREFIX}probe"}
        )
        assert probe["type"] is FlowResultType.ABORT
        assert probe["reason"] == reason
        ir.async_delete_issue(hass, DOMAIN, f"{const.ISSUE_TRANSFERRED_PREFIX}probe")
    assert device_id in manager.devices
    assert len(entry.subentries) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    unloaded = await _start_transferred_flow(hass, device_id)
    assert unloaded["type"] is FlowResultType.ABORT
    assert unloaded["reason"] == "not_loaded"
