"""
The hub options editor of local actions on mirrors (MIR-01, MIR-05, MIR-07, D-06, D-11 to D-16).

The flow is a thin client of the Manager: every save and removal goes through `async_set_local_action` or
`async_remove_local_action`, nothing of a local customization is stored in the entry options or a subentry, and a
draft that is never confirmed never reaches the Manager.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.data_entry_flow import FlowResultType, section
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions.const import DOMAIN, PAYLOAD_OFF, PAYLOAD_ON, SUBENTRY_SELECT, SUBENTRY_SWITCH
from custom_components.mqtt_actions.local_actions import LocalActionMode, local_trigger_identity
from custom_components.mqtt_actions.topics import state_topic
from tests.documents import document_payload, make_spec
from tests.helpers import BASE, deliver_config, manager_of, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.model import DeviceSpec

TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations"
LOCAL_ON = [{"action": "test.local_on", "data": {"source": "local"}}]
ADDITIONAL_EN = "additional to the owner actions"


def _flat(language: str) -> dict[str, str]:
    """Return the flattened translation keys of a language."""

    def _walk(node: Any, prefix: str) -> dict[str, str]:
        if isinstance(node, dict):
            flat: dict[str, str] = {}
            for key, value in node.items():
                flat.update(_walk(value, f"{prefix}.{key}" if prefix else key))
            return flat
        return {prefix: node}

    return _walk(json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")), "")


def _assert_translated(result: dict[str, Any]) -> None:
    """Every title, description, field, section and menu option a shown step uses has a text in en and de."""
    step = f"options.step.{result['step_id']}"
    keys = [f"{step}.title", f"{step}.description"]
    if result["type"] is FlowResultType.MENU:
        keys.extend(f"{step}.menu_options.{option}" for option in result["menu_options"])
    else:
        for key, value in result["data_schema"].schema.items():
            if isinstance(value, section):
                keys.extend((f"{step}.sections.{key.schema}.name", f"{step}.sections.{key.schema}.description"))
                keys.extend(f"{step}.sections.{key.schema}.data.{inner.schema}" for inner in value.schema.schema)
            else:
                keys.append(f"{step}.data.{key.schema}")
    keys.extend(f"options.error.{error}" for error in (result.get("errors") or {}).values())
    for language in ("en", "de"):
        flat = _flat(language)
        missing = [key for key in keys if not flat.get(key)]
        assert missing == [], f"{language} lacks {missing}"


def _options(result: dict[str, Any], field: str) -> dict[str, str]:
    """Return value -> label of the select field `field` of a shown form."""
    for key, value in result["data_schema"].schema.items():
        if key.schema == field:
            return {option["value"]: option["label"] for option in value.config["options"]}
    msg = f"the form has no field {field}"
    raise AssertionError(msg)


def _value(result: dict[str, Any], field: str, label_start: str) -> str:
    """Return the value of the option of `field` whose label starts with `label_start`."""
    (value,) = (value for value, label in _options(result, field).items() if label.startswith(label_start))
    return value


def _section_suggested(result: dict[str, Any]) -> dict[str, Any]:
    """Return the suggested values of the fields of the local actions section of the editor."""
    (value,) = (value for key, value in result["data_schema"].schema.items() if key.schema == "local_actions")
    assert isinstance(value, section)
    assert value.options["collapsed"] is False, "a collapsed section folds again after a base error (11-02 smoke)"
    return {key.schema: (key.description or {}).get("suggested_value") for key in value.schema.schema}


async def _mirror(hass: HomeAssistant, make_hub_entry: Callable, spec: DeviceSpec) -> MockConfigEntry:
    """Set up a follower and deliver the owner's document of `spec`, so the device is a mirror here."""
    entry = await setup_entry(hass, make_hub_entry())
    await deliver_config(hass, spec.device_id, document_payload(spec))
    assert spec.device_id in manager_of(entry).mirrors
    return entry


async def _configure(hass: HomeAssistant, result: dict[str, Any], user_input: dict[str, Any]) -> dict[str, Any]:
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    if result["type"] in (FlowResultType.FORM, FlowResultType.MENU):
        _assert_translated(result)
    return result


async def _open_device(hass: HomeAssistant, entry: MockConfigEntry, device_label: str) -> dict[str, Any]:
    """Open the hub options, choose Local actions and the device; return the trigger picker."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU, "the hub options open as a menu"
    assert result["step_id"] == "init"
    assert list(result["menu_options"]) == ["settings", "local_actions"]
    _assert_translated(result)
    result = await _configure(hass, result, {"next_step_id": "local_actions"})
    assert result["step_id"] == "local_actions"
    result = await _configure(hass, result, {"device": _value(result, "device", device_label)})
    assert result["step_id"] == "local_actions_device"
    return result


def _edit_input(mode: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"local_actions": {"mode": mode, "actions": actions}}


async def _state(hass: HomeAssistant, device_id: str, payload: str, *, retain: bool) -> None:
    async_fire_mqtt_message(hass, state_topic(BASE, device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


# --- Task 1 (tracer): menu -> device -> trigger -> save -> picker -> reopen ----------------------------------------


async def test_save_and_reopen_additive_switch_trigger(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-06, D-13: a new trigger defaults to additive, saves through the Manager at once and reopens what was saved."""
    local_calls = async_mock_service(hass, "test", "local_on")
    spec = make_spec(name="Lamp", on=[{"action": "test.owner_on"}])
    entry = await _mirror(hass, make_hub_entry, spec)
    manager = manager_of(entry)

    picker = await _open_device(hass, entry, "Lamp")
    assert set(_options(picker, "trigger").values()) == {PAYLOAD_ON, PAYLOAD_OFF}, "no record: no marker yet"
    editor = await _configure(hass, picker, {"trigger": _value(picker, "trigger", PAYLOAD_ON)})
    assert editor["type"] is FlowResultType.FORM
    assert editor["step_id"] == "local_actions_edit"
    assert _section_suggested(editor) == {"mode": "additive", "actions": []}, "a new customization starts additive"

    back = await _configure(hass, editor, _edit_input("additive", LOCAL_ON))

    assert back["type"] is FlowResultType.FORM
    assert back["step_id"] == "local_actions_device", "a save returns to the trigger selection"
    assert _options(back, "trigger")[_value(back, "trigger", PAYLOAD_ON)] == f"{PAYLOAD_ON} — {ADDITIONAL_EN}"
    (row,) = (row for row in manager.local_action_triggers(spec.device_id) if row.state_value == PAYLOAD_ON)
    assert row.record is not None
    assert row.record.mode is LocalActionMode.ADDITIVE
    assert row.record.actions == LOCAL_ON
    assert entry.options == {}, "no overlay content in the entry options"
    assert dict(entry.subentries) == {}, "no subentry is created for a local customization"

    # Applied without restart: the next state change runs the local branch
    await _state(hass, spec.device_id, PAYLOAD_OFF, retain=True)
    await _state(hass, spec.device_id, PAYLOAD_ON, retain=False)
    assert len(local_calls) == 1

    # Reopen: a saved trigger offers edit and removal; the editor shows what was saved
    menu = await _configure(hass, back, {"trigger": _value(back, "trigger", PAYLOAD_ON)})
    assert menu["type"] is FlowResultType.MENU
    assert menu["step_id"] == "local_actions_trigger"
    reopened = await _configure(hass, menu, {"next_step_id": "local_actions_edit"})
    assert reopened["step_id"] == "local_actions_edit"
    assert _section_suggested(reopened) == {"mode": "additive", "actions": LOCAL_ON}


async def test_save_and_reopen_select_option_and_switch_off_reach_the_same_editor(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-10, D-11: Select options show friendly name and StateValue; every trigger kind opens the one editor."""
    switch = make_spec(name="Lamp")
    select = make_spec(SUBENTRY_SELECT, name="Scene", options=[("cozy", "Gemütlich", []), ("bright", "Hell", [])])
    entry = await _mirror(hass, make_hub_entry, switch)
    await deliver_config(hass, select.device_id, document_payload(select))
    manager = manager_of(entry)

    picker = await _open_device(hass, entry, "Scene")
    assert set(_options(picker, "trigger").values()) == {"Gemütlich (cozy)", "Hell (bright)"}
    editor = await _configure(hass, picker, {"trigger": _value(picker, "trigger", "Gemütlich")})
    assert editor["step_id"] == "local_actions_edit"
    assert editor["description_placeholders"]["trigger"] == "Gemütlich"
    assert editor["description_placeholders"]["state_value"] == "cozy"
    back = await _configure(hass, editor, _edit_input("replacement", LOCAL_ON))
    assert back["step_id"] == "local_actions_device"

    off_picker = await _open_device(hass, entry, "Lamp")
    off_editor = await _configure(hass, off_picker, {"trigger": _value(off_picker, "trigger", PAYLOAD_OFF)})
    assert off_editor["step_id"] == editor["step_id"]
    await _configure(hass, off_editor, _edit_input("additive", LOCAL_ON))

    saved = {
        (row.identity.kind, row.state_value, str(row.record.mode))
        for device in (switch, select)
        for row in manager.local_action_triggers(device.device_id)
        if row.record is not None
    }
    assert saved == {(SUBENTRY_SELECT, "cozy", "replacement"), (SUBENTRY_SWITCH, PAYLOAD_OFF, "additive")}


async def test_stale_target_submit_returns_a_base_error_and_saves_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """T-11-24: an option the owner removed while the editor was open is refused by the Manager; nothing is saved."""
    spec = make_spec(SUBENTRY_SELECT, name="Scene", options=[("cozy", "Gemütlich", []), ("bright", "Hell", [])])
    entry = await _mirror(hass, make_hub_entry, spec)
    manager = manager_of(entry)
    picker = await _open_device(hass, entry, "Scene")
    editor = await _configure(hass, picker, {"trigger": _value(picker, "trigger", "Gemütlich")})

    changed = make_spec(
        SUBENTRY_SELECT, device_id=spec.device_id, name="Scene", options=[("bright", "Hell", []), ("party", "P", [])]
    )
    await deliver_config(hass, spec.device_id, document_payload(changed, rev=2), retain=False)
    refused = await _configure(hass, editor, _edit_input("additive", LOCAL_ON))

    assert refused["type"] is FlowResultType.FORM
    assert refused["step_id"] == "local_actions_edit"
    assert refused["errors"] == {"base": "stale_target"}
    assert _section_suggested(refused) == {"mode": "additive", "actions": LOCAL_ON}, "the submitted draft is kept"
    assert all(row.record is None for row in manager.local_action_triggers(spec.device_id))


async def test_stale_manager_submit_returns_a_base_error_and_saves_nothing(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any], make_hub_entry: Callable
) -> None:
    """T-11-24: a submit after the integration was unloaded reaches no Manager and saves nothing."""
    spec = make_spec(name="Lamp")
    entry = await _mirror(hass, make_hub_entry, spec)
    picker = await _open_device(hass, entry, "Lamp")
    editor = await _configure(hass, picker, {"trigger": _value(picker, "trigger", PAYLOAD_ON)})
    before = json.dumps(hass_storage.get("mqtt_actions.local_actions"), sort_keys=True, default=str)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    refused = await _configure(hass, editor, _edit_input("additive", LOCAL_ON))

    assert refused["step_id"] == "local_actions_edit"
    assert refused["errors"] == {"base": "not_loaded"}
    after = json.dumps(hass_storage.get("mqtt_actions.local_actions"), sort_keys=True, default=str)
    assert after == before
    assert entry.options == {}


async def test_settings_stay_reachable_from_the_menu(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The existing hub settings are a step of the menu; only they write the entry options."""
    entry = await setup_entry(hass, make_hub_entry())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await _configure(hass, result, {"next_step_id": "settings"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    saved = await _configure(hass, result, {"delete_devices_on_remove": True})

    assert saved["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"delete_devices_on_remove": True}


async def test_trigger_labels_follow_the_language_of_the_instance(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """The direct mode marker of a picker label is a translated text, not a raw key (D-16, MIR-15)."""
    spec = make_spec(name="Lamp")
    entry = await _mirror(hass, make_hub_entry, spec)
    await manager_of(entry).async_set_local_action(
        local_trigger_identity(spec.device_id, SUBENTRY_SWITCH, PAYLOAD_ON), LocalActionMode.ADDITIVE, LOCAL_ON
    )
    hass.config.language = "de"

    picker = await _open_device(hass, entry, "Lamp")

    label = _options(picker, "trigger")[_value(picker, "trigger", PAYLOAD_ON)]
    assert label == f"{PAYLOAD_ON} — {_flat('de')['selector.local_trigger_status.options.additive']}"
    assert label != f"{PAYLOAD_ON} — {ADDITIONAL_EN}"
