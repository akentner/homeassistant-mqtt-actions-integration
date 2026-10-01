"""Trust gate: a mirror runs only with an approval bound to its actions hash, through guarded service names (TRU-01)."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_mock_service,
)

from custom_components.mqtt_actions.actions import async_validate_actions
from custom_components.mqtt_actions.const import (
    APPROVAL_HASH_PREFIX_LENGTH,
    APPROVAL_TEMPLATED_MAX_LINES,
    CONF_BASE_TOPIC,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    DOMAIN,
    ISSUE_CIRCUIT_BREAKER_PREFIX,
    ISSUE_DENIED_CALL_PREFIX,
    STORE_APPROVALS,
    STORE_KEY,
    STORE_MIRRORS,
    STORE_VERSION,
    TRIGGER_ON,
    TRIGGER_SETUP,
)
from custom_components.mqtt_actions.document import escape_markdown, parse_document
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY
from custom_components.mqtt_actions.runner import ActionRunner
from custom_components.mqtt_actions.topics import config_topic, state_topic
from custom_components.mqtt_actions.topics import test_topic as device_test_topic
from tests.documents import document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant, ServiceCall

    from custom_components.mqtt_actions.manager import Device, Manager
    from custom_components.mqtt_actions.model import DeviceSpec

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on", "target": {"entity_id": "light.lamp"}}]
OFF_ACTIONS = [{"action": "test.off"}]
OTHER_ACTIONS = [{"action": "test.other"}]
DENIED_ACTIONS = [{"action": "shell_command.x"}]
TEMPLATED_DENIED = [{"action": "{{ 'shell_command.x' }}", "continue_on_error": True}, {"action": "test.ok"}]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _manager(entry: MockConfigEntry) -> Manager:
    return entry.runtime_data


def _mirror(entry: MockConfigEntry, device_id: str) -> Device:
    return _manager(entry).mirrors[device_id]


async def _deliver(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = True) -> None:
    async_fire_mqtt_message(hass, config_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool = False) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _press(hass: HomeAssistant, device_id: str, payload: str) -> None:
    async_fire_mqtt_message(hass, device_test_topic(BASE, device_id), payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _approve(entry: MockConfigEntry, device_id: str) -> bool:
    """Approve exactly the hash the mirror currently has, like the dialog does after the user read it."""
    manager = _manager(entry)
    info = manager.mirrors[device_id].mirror
    assert info is not None
    return await manager.async_approve(device_id, info.actions_hash)


def _seed_store(hass_storage: dict[str, Any], data: dict[str, Any]) -> None:
    hass_storage[STORE_KEY] = {"version": STORE_VERSION, "minor_version": 1, "key": STORE_KEY, "data": data}


def _issue(hass: HomeAssistant, prefix: str, device_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{prefix}{device_id}")


async def _settle() -> None:
    for _ in range(25):
        await asyncio.sleep(0)


def _service_templates(node: Any) -> list[Any]:
    """Return every value under the keys action and service_template of a validated tree, nested ones included."""
    found: list[Any] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("action", "service_template"):
                found.append(value)
            else:
                found.extend(_service_templates(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_service_templates(item))
    return found


def _bare_runner(hass: HomeAssistant) -> ActionRunner:
    """Return a real runner on a config entry that is not set up, for tests below the manager."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BASE_TOPIC: BASE, CONF_INSTANCE_NAME: "Runner", CONF_INSTANCE_ID: "runner"},
    )
    entry.add_to_hass(hass)
    return ActionRunner(hass, entry)


async def _run(hass: HomeAssistant, runner: ActionRunner, spec: DeviceSpec, key: str = SWITCH_ON_KEY) -> None:
    trigger = spec.triggers[key]
    runner.enqueue(spec.device_id, spec.name, trigger.label, key, {"device_id": spec.device_id})
    await hass.async_block_till_done(wait_background_tasks=True)


# --- the guard (D-03, D-05) ---------------------------------------------------------------------------------------


async def test_guard_actions_wraps_service_name_templates(hass: HomeAssistant) -> None:
    """Every service-name template becomes a GuardedTemplate with the same text; static names and the input stay."""
    from custom_components.mqtt_actions.trust import GuardedTemplate, guard_actions

    raw = [{"action": "{{ 'notify.notify' }}"}, {"service_template": "{{ 'a.b' }}"}, {"action": "test.static"}]
    validated = await async_validate_actions(hass, raw)

    guarded = guard_actions(validated)

    assert guarded is not validated
    assert isinstance(guarded[0]["action"], GuardedTemplate)
    assert guarded[0]["action"].template == "{{ 'notify.notify' }}"
    assert isinstance(guarded[1]["service_template"], GuardedTemplate)
    assert guarded[1]["service_template"].template == "{{ 'a.b' }}"
    assert guarded[2]["action"] == "test.static"
    assert type(validated[0]["action"]) is Template
    assert type(validated[1]["service_template"]) is Template


async def test_nested_templated_service_name_three_levels_deep_is_guarded(hass: HomeAssistant) -> None:
    """A templated name inside choose, then sequence, then if-then is wrapped too."""
    from custom_components.mqtt_actions.trust import GuardedTemplate, guard_actions

    condition = {"condition": "template", "value_template": "{{ true }}"}
    raw = [
        {
            "choose": [
                {
                    "conditions": [condition],
                    "sequence": [{"sequence": [{"if": [condition], "then": [{"action": "{{ 'x.y' }}"}]}]}],
                }
            ]
        },
        {"parallel": [{"action": "{{ 'p.q' }}"}]},
        {"repeat": {"count": 2, "sequence": [{"action": "{{ 'r.s' }}"}]}},
    ]
    validated = await async_validate_actions(hass, raw)

    found = _service_templates(guard_actions(validated))

    assert len(found) == 3
    assert all(isinstance(value, GuardedTemplate) for value in found)
    assert not any(type(value) is GuardedTemplate for value in _service_templates(validated))


async def test_guarded_template_raises_a_plain_exception_for_a_denied_name(hass: HomeAssistant) -> None:
    """The denial derives from neither HomeAssistantError nor TemplateError, so continue_on_error cannot swallow it."""
    from custom_components.mqtt_actions.trust import DeniedServiceCallError, GuardedTemplate

    assert DeniedServiceCallError.__mro__ == (DeniedServiceCallError, Exception, BaseException, object)
    assert not issubclass(DeniedServiceCallError, HomeAssistantError | TemplateError)

    with pytest.raises(DeniedServiceCallError) as caught:
        GuardedTemplate("{{ 'shell_command.x' }}", hass).async_render()

    assert caught.value.service == "shell_command.x"


async def test_guarded_template_allows_other_names_and_normalizes(hass: HomeAssistant) -> None:
    """A resolved name is judged after strip and lower, like core normalizes it; other names render normally."""
    from custom_components.mqtt_actions.trust import DeniedServiceCallError, GuardedTemplate

    assert str(GuardedTemplate("{{ ' Notify.Notify ' }}", hass).async_render()).strip() == "Notify.Notify"
    with pytest.raises(DeniedServiceCallError) as caught:
        GuardedTemplate("{{ ' Shell_Command.X ' }}", hass).async_render()
    assert caught.value.service == "shell_command.x"


# --- the restricted build (D-03, D-05) ----------------------------------------------------------------------------


async def test_denied_call_aborts_the_run_even_with_continue_on_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A templated name that resolves to a denied service stops the run in a restricted build; unrestricted runs on."""
    denied_calls = async_mock_service(hass, "shell_command", "x")
    ok_calls = async_mock_service(hass, "test", "ok")
    spec = make_spec(name="Hostile", on=TEMPLATED_DENIED)
    runner = _bare_runner(hass)

    await runner.async_build_device(spec, restricted=True)
    with caplog.at_level(logging.WARNING):
        await _run(hass, runner, spec)

    assert denied_calls == []
    assert ok_calls == []
    issue = _issue(hass, ISSUE_DENIED_CALL_PREFIX, spec.device_id)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.translation_placeholders is not None
    assert set(issue.translation_placeholders) == {"device", "trigger", "service"}
    assert issue.translation_placeholders["service"] == escape_markdown("shell_command.x")
    records = [r for r in caplog.records if r.name.startswith("custom_components.mqtt_actions")]
    assert any(
        r.levelno == logging.WARNING
        and "Hostile" in r.getMessage()
        and "shell_command.x" in r.getMessage()
        and TRIGGER_ON in r.getMessage()
        for r in records
    )

    # The same spec built without the restriction, as for an owned device, runs both steps (pins the hook point)
    await runner.async_build_device(spec)
    await _run(hass, runner, spec)
    assert len(denied_calls) == 1
    assert len(ok_calls) == 1


async def test_restricted_build_refuses_statically_denied_triggers(hass: HomeAssistant) -> None:
    """A literal denied service leaves its trigger non-runnable with a setup issue; other triggers stay runnable."""
    spec = make_spec(on=DENIED_ACTIONS, off=OFF_ACTIONS)
    runner = _bare_runner(hass)

    await runner.async_build_device(spec, restricted=True)

    assert runner.can_run(spec.device_id, SWITCH_ON_KEY) is False
    assert runner.can_run(spec.device_id, SWITCH_OFF_KEY) is True
    setup_issue = ir.async_get(hass).async_get_issue(DOMAIN, f"action_failed_{spec.device_id}")
    assert setup_issue is not None
    assert setup_issue.translation_placeholders is not None
    assert setup_issue.translation_placeholders["trigger"] == TRIGGER_SETUP
    assert escape_markdown("shell_command.x") in setup_issue.translation_placeholders["error"]


# --- the approval gate (D-01, D-02, TRU-01) -----------------------------------------------------------------------


async def test_unapproved_mirror_runs_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, hass_storage: dict[str, Any]
) -> None:
    """State edges, test presses and run-on-startup run nothing for a mirror nobody approved (T-03-24)."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS, run_on_startup=True)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))

    await _state(hass, spec.device_id, "OFF")
    await _state(hass, spec.device_id, "ON")
    await _press(hass, spec.device_id, "ON")
    await _press(hass, spec.device_id, "OFF")
    assert _manager(entry).runner.script_count(spec.device_id) == 0

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _state(hass, spec.device_id, "ON", retain=True)

    assert spec.device_id in _manager(entry).mirrors
    assert _manager(entry).runner.script_count(spec.device_id) == 0
    assert on_calls == []
    assert off_calls == []


async def test_approved_mirror_runs_actions_on_a_real_edge(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Approving the current hash stores it, builds one restricted Script and a live edge runs the actions once."""
    on_calls = async_mock_service(hass, "test", "on")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "OFF", retain=True)
    manager = _manager(entry)
    actions_hash = parse_document(spec.device_id, document_payload(spec)).actions_hash

    assert await _approve(entry, spec.device_id) is True

    assert manager._approvals == {spec.device_id: actions_hash}
    assert manager.runner.script_count(spec.device_id) == 1
    await _state(hass, spec.device_id, "ON")
    assert len(on_calls) == 1


async def test_approval_is_not_retroactive(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """Approval runs nothing by itself: the retained baseline stays and only a later real edge runs (STA-04)."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "ON", retain=True)

    assert await _approve(entry, spec.device_id) is True
    await hass.async_block_till_done(wait_background_tasks=True)
    assert on_calls == []
    assert _mirror(entry, spec.device_id).tracker.last_acted == "ON"

    await _state(hass, spec.device_id, "ON")
    assert on_calls == []
    await _state(hass, spec.device_id, "OFF")
    assert len(off_calls) == 1
    assert on_calls == []


async def test_approval_requires_the_current_hash(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Another hash, an unknown device and a blocked mirror are refused; nothing is stored and nothing is built."""
    blocked = make_spec(on=DENIED_ACTIONS)
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    await _deliver(hass, blocked.device_id, document_payload(blocked))
    manager = _manager(entry)
    blocked_hash = manager.mirrors[blocked.device_id].mirror.actions_hash  # type: ignore[union-attr]

    assert await manager.async_approve(spec.device_id, "0" * 64) is False
    assert await manager.async_approve("unknown-device", "0" * 64) is False
    assert await manager.async_approve(blocked.device_id, blocked_hash) is False

    assert manager._approvals == {}
    assert manager.runner.script_count(spec.device_id) == 0
    assert manager.runner.script_count(blocked.device_id) == 0


async def test_changed_actions_lapse_the_approval(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """Different actions unload the Script and stop the run in flight; reverting to the approved actions runs again."""
    order: list[str] = []
    gate = asyncio.Event()
    cancelled: list[bool] = []

    async def _hold(call: ServiceCall) -> None:
        order.append("hold:start")
        try:
            await gate.wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    hass.services.async_register("test", "hold", _hold)
    other_calls = async_mock_service(hass, "test", "other")
    v1 = make_spec(on=[{"action": "test.hold"}], off=OFF_ACTIONS, name="Lamp")
    v2 = make_spec(device_id=v1.device_id, on=OTHER_ACTIONS, off=OFF_ACTIONS, name="Lamp")
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, v1.device_id, document_payload(v1))
    await _state(hass, v1.device_id, "OFF", retain=True)
    manager = _manager(entry)
    approved_hash = manager.mirrors[v1.device_id].mirror.actions_hash  # type: ignore[union-attr]
    assert await _approve(entry, v1.device_id) is True
    async_fire_mqtt_message(hass, state_topic(BASE, v1.device_id), "ON", retain=False)
    await _settle()
    assert order == ["hold:start"]

    await _deliver(hass, v1.device_id, document_payload(v2, rev=2), retain=False)
    await _settle()

    assert cancelled == [True]
    assert manager.runner.script_count(v1.device_id) == 0
    assert manager._approvals == {v1.device_id: approved_hash}
    assert manager.mirrors[v1.device_id].mirror.actions_hash != approved_hash  # type: ignore[union-attr]
    await _state(hass, v1.device_id, "OFF")
    await _state(hass, v1.device_id, "ON")
    assert other_calls == []

    gate.set()
    await _deliver(hass, v1.device_id, document_payload(v1, rev=3), retain=False)
    assert manager.runner.script_count(v1.device_id) == 1
    await _state(hass, v1.device_id, "OFF")
    await _state(hass, v1.device_id, "ON")
    assert order == ["hold:start", "hold:start"]


async def test_rename_and_settings_change_keep_the_approval(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A new name, run mode or breaker limits keep the approval; the rebuilt Script uses the new run mode (A5)."""
    async_mock_service(hass, "test", "on")
    v1 = make_spec(on=ON_ACTIONS, name="Lamp")
    v2 = make_spec(
        device_id=v1.device_id, on=ON_ACTIONS, name="Renamed", run_mode="restart", breaker_max_runs=3, breaker_window=7
    )
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, v1.device_id, document_payload(v1))
    assert await _approve(entry, v1.device_id) is True
    manager = _manager(entry)
    approved = dict(manager._approvals)
    script = manager.runner.script_for(v1.device_id, SWITCH_ON_KEY)
    assert script is not None
    assert script.script_mode == "queued"

    await _deliver(hass, v1.device_id, document_payload(v2, rev=2), retain=False)

    assert manager._approvals == approved
    rebuilt = manager.runner.script_for(v1.device_id, SWITCH_ON_KEY)
    assert rebuilt is not None
    assert rebuilt.script_mode == "restart"
    assert manager.mirrors[v1.device_id].name == "Renamed"


async def test_approval_persists_across_restart(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, hass_storage: dict[str, Any]
) -> None:
    """After a flush, unload and setup the mirror has its Script before any message and a live edge runs."""
    on_calls = async_mock_service(hass, "test", "on")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    await _state(hass, spec.device_id, "OFF", retain=True)
    assert await _approve(entry, spec.device_id) is True
    actions_hash = _mirror(entry, spec.device_id).mirror.actions_hash  # type: ignore[union-attr]

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORE_KEY]["data"][STORE_APPROVALS] == {spec.device_id: actions_hash}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    manager = _manager(entry)
    assert manager.runner.script_count(spec.device_id) == 1
    await _state(hass, spec.device_id, "ON")
    assert len(on_calls) == 1


@pytest.mark.parametrize(
    "make_approvals",
    [
        lambda _device_id: "text",
        lambda _device_id: ["a", "b"],
        lambda device_id: {device_id: 5},
        lambda device_id: {device_id: ["not", "text"]},
        lambda device_id: {device_id: "0" * 64},
        lambda _device_id: {"no-such-mirror": "0" * 64},
    ],
    ids=["text", "list", "int-value", "list-value", "non-matching-hash", "unknown-mirror"],
)
async def test_malformed_approvals_store_is_dropped(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    hass_storage: dict[str, Any],
    make_approvals: Callable[[str], Any],
) -> None:
    """Malformed and orphaned approval entries never fail setup and approve nothing."""
    spec = make_spec(on=ON_ACTIONS)
    _seed_store(
        hass_storage,
        {STORE_MIRRORS: {spec.device_id: document_payload(spec)}, STORE_APPROVALS: make_approvals(spec.device_id)},
    )

    entry = await _setup(hass, make_hub_entry())

    manager = _manager(entry)
    assert spec.device_id in manager.mirrors
    assert manager.runner.script_count(spec.device_id) == 0
    assert "no-such-mirror" not in manager._approvals
    assert all(isinstance(value, str) for value in manager._approvals.values())


async def test_blocked_mirror_is_not_approvable_and_never_built(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, hass_storage: dict[str, Any]
) -> None:
    """A statically denied mirror is refused, and a forged matching approval in the Store builds no Script either."""
    denied_calls = async_mock_service(hass, "shell_command", "x")
    spec = make_spec(on=DENIED_ACTIONS)
    payload = document_payload(spec)
    forged = parse_document(spec.device_id, payload).actions_hash
    _seed_store(hass_storage, {STORE_MIRRORS: {spec.device_id: payload}, STORE_APPROVALS: {spec.device_id: forged}})

    entry = await _setup(hass, make_hub_entry())
    manager = _manager(entry)

    assert manager.runner.script_count(spec.device_id) == 0
    assert await manager.async_approve(spec.device_id, forged) is False
    # Forged in memory and refreshed: the restricted build refuses on its own as well
    manager._approvals[spec.device_id] = forged
    await manager._async_refresh_mirror_script(manager.mirrors[spec.device_id])
    assert manager.runner.script_count(spec.device_id) == 0
    await _state(hass, spec.device_id, "OFF", retain=True)
    await _state(hass, spec.device_id, "ON")
    assert denied_calls == []


async def test_mirror_without_actions_needs_no_approval(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A mirror whose triggers have no actions builds no Script and has nothing to approve (A9)."""
    spec = make_spec()
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    manager = _manager(entry)

    assert manager.runner.script_count(spec.device_id) == 0
    assert await _approve(entry, spec.device_id) is False
    assert manager._approvals == {}


async def test_owned_devices_are_unrestricted_and_need_no_approval(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """An owned device with a denylisted service builds and runs; no approval state exists for it (D-03)."""
    denied_calls = async_mock_service(hass, "shell_command", "x")
    sub = make_switch_subentry("Own", on=DENIED_ACTIONS)
    device_id = sub["data"]["device_id"]
    entry = await _setup(hass, make_hub_entry([sub]))
    manager = _manager(entry)

    assert manager.runner.script_count(device_id) == 1
    await _state(hass, device_id, "ON")

    assert len(denied_calls) == 1
    assert manager._approvals == {}


async def test_approved_mirror_test_button_runs_with_test_true(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """A test press runs an approved mirror with the run variable test true, and an unapproved one not at all."""
    calls = async_mock_service(hass, "test", "on")
    spec = make_spec(on=[{"action": "test.on", "data": {"was_test": "{{ test }}"}}])
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))

    await _press(hass, spec.device_id, "ON")
    assert calls == []

    assert await _approve(entry, spec.device_id) is True
    await _press(hass, spec.device_id, "ON")

    assert len(calls) == 1
    assert calls[0].data["was_test"] is True


async def test_mirror_breaker_trips_like_an_owned_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """An approved mirror trips its breaker after breaker_max_runs and creates the circuit breaker issue."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    spec = make_spec(on=ON_ACTIONS, off=OFF_ACTIONS, breaker_max_runs=2, breaker_window=60)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    assert await _approve(entry, spec.device_id) is True

    for payload in ("ON", "OFF", "ON"):
        await _state(hass, spec.device_id, payload)

    assert len(on_calls) + len(off_calls) == 2
    assert _mirror(entry, spec.device_id).breaker.tripped is True
    assert _issue(hass, ISSUE_CIRCUIT_BREAKER_PREFIX, spec.device_id) is not None


async def test_tombstone_forgets_the_approval(hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable) -> None:
    """Removing a mirror deletes its approval entry, its denied-call issue and its Store record (A10)."""
    async_mock_service(hass, "test", "on")
    spec = make_spec(on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry())
    await _deliver(hass, spec.device_id, document_payload(spec))
    assert await _approve(entry, spec.device_id) is True
    manager = _manager(entry)
    manager.runner.report_denied(spec.device_id, spec.name, TRIGGER_ON, "shell_command.x")
    assert _issue(hass, ISSUE_DENIED_CALL_PREFIX, spec.device_id) is not None

    await _deliver(hass, spec.device_id, "", retain=False)

    assert spec.device_id not in manager.mirrors
    assert manager._approvals == {}
    assert _issue(hass, ISSUE_DENIED_CALL_PREFIX, spec.device_id) is None
    saved = manager._data_to_save()
    assert saved[STORE_APPROVALS] == {}
    assert spec.device_id not in saved[STORE_MIRRORS]


# --- the approval view (D-02, T-03-28) ---------------------------------------------------------------------------


def _view(spec: DeviceSpec, invalid: tuple[str, ...] = (), **document: Any) -> Any:
    from custom_components.mqtt_actions.manager import Manager
    from custom_components.mqtt_actions.trust import build_approval_view

    info = Manager._mirror_info(parse_document(spec.device_id, document_payload(spec, **document)))
    return build_approval_view(spec, info, invalid)


def test_view_renders_each_non_empty_action_list_under_its_label() -> None:
    """The YAML holds the lists that have actions under the dialog labels; names are escaped, empty lists are dashes."""
    from custom_components.mqtt_actions.trust import EMPTY_LIST_TEXT

    spec = make_spec(on=ON_ACTIONS, name="My_lamp")

    view = _view(spec)

    assert view.device_name == escape_markdown("My_lamp")
    assert view.owner_name == escape_markdown("Foreign instance")
    assert len(view.short_hash) == APPROVAL_HASH_PREFIX_LENGTH
    assert view.actions_hash.startswith(view.short_hash)
    assert "onChangeToOn:" in view.actions_yaml
    assert "action: test.on" in view.actions_yaml
    assert "onChangeToOff" not in view.actions_yaml
    assert view.truncated is False
    assert (view.templated, view.residual, view.invalid) == (EMPTY_LIST_TEXT,) * 3


def test_view_labels_select_options_and_lists_invalid_triggers() -> None:
    """A Select option is labelled with its friendly name and value; invalid labels appear as a bullet list."""
    spec = make_spec(
        "select", options=[("a", "Alpha", ON_ACTIONS), ("b", "Bravo", OFF_ACTIONS), ("c", "Charlie", [])], name="Mode"
    )

    view = _view(spec, ("Alpha (a)",))

    assert "Alpha (a):" in view.actions_yaml
    assert "Bravo (b):" in view.actions_yaml
    assert "Charlie" not in view.actions_yaml
    assert view.invalid == "- Alpha (a)"


def test_view_caps_the_yaml_and_flags_truncation() -> None:
    """A document too long to show in full is flagged, and the text never exceeds the cap."""
    spec = make_spec(on=ON_ACTIONS)

    with patch("custom_components.mqtt_actions.trust.APPROVAL_YAML_MAX_CHARS", 20):
        view = _view(spec)

    assert view.truncated is True
    assert len(view.actions_yaml) <= 20


def test_view_caps_the_templated_names() -> None:
    """At most APPROVAL_TEMPLATED_MAX_LINES templated names are listed, and the rest is counted."""
    actions = [{"action": f"{{{{ 'x.y{index}' }}}}"} for index in range(APPROVAL_TEMPLATED_MAX_LINES + 5)]
    spec = make_spec(on=actions)

    view = _view(spec)

    lines = view.templated.splitlines()
    assert len(lines) == APPROVAL_TEMPLATED_MAX_LINES + 1
    assert lines[0] == "- {{ 'x.y0' }}"
    assert lines[-1].endswith("(+5)")


def test_view_removes_control_characters_and_fence_runs() -> None:
    """Control and format characters go, and no run of three backticks can close the fence in the dialog."""
    hostile = {"message": f"a{chr(7)}b{chr(0x202E)}c ```yaml\n```` d"}
    spec = make_spec(on=[{"action": "notify.notify", "data": hostile}])

    view = _view(spec)

    assert "```" not in view.actions_yaml
    assert chr(7) not in view.actions_yaml
    assert chr(0x202E) not in view.actions_yaml
    assert "abc" in view.actions_yaml
