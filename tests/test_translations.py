"""English and German translation parity (hassfest validates only en.json, so drift in de.json would be invisible)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from custom_components.mqtt_actions.const import DOMAIN

TRANSLATIONS_DIR = Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations"
LANGUAGES = ("en", "de")
VARIABLE = re.compile(r"\{(\w+)\}")
# hassfest rejects a placeholder that sits inside single quotes
VARIABLE_IN_SINGLE_QUOTES = re.compile(r"'[^']*\{\w+\}[^']*'")

SWITCH_FORM_FIELDS = (
    "name",
    "on_change_to_on",
    "on_change_to_off",
    "run_on_startup",
    "run_mode",
    "breaker_max_runs",
    "breaker_window",
)

SELECT_SETTINGS_FIELDS = ("name", "run_on_startup", "run_mode", "breaker_max_runs", "breaker_window")
SELECT_ERROR_KEYS = (
    "name_required",
    "name_invalid",
    "invalid_actions",
    "device_id_warning",
    "state_value_required",
    "state_value_invalid",
    "state_value_duplicate",
    "friendly_name_required",
    "friendly_name_invalid",
    "friendly_name_reserved",
    "friendly_name_duplicate",
    "breaker_max_runs_range",
    "breaker_window_range",
)

# Issue translation keys of the central config (owner and follower side) and the variables each description may use
NEW_ISSUES = {
    "doc_overwritten": {"device"},
    "ownership_claim": {"device", "claimant"},
    "discovery_removed": {"device", "count"},
    "owner_conflict": {"device", "owner", "claimant"},
    "schema_too_new": {"device", "version", "supported"},
    "approval_required": {"device", "owner", "hash"},
    "mirror_blocked": {"device", "owner", "services"},
    "denied_service_call": {"device", "trigger", "service"},
}

# The approval fix flow (plan 03-06): the confirm step and the three reasons it can abort
APPROVAL_FLOW = "issues.approval_required.fix_flow"
APPROVAL_FLOW_KEYS = (
    f"{APPROVAL_FLOW}.step.confirm.title",
    f"{APPROVAL_FLOW}.step.confirm.description",
    f"{APPROVAL_FLOW}.abort.changed",
    f"{APPROVAL_FLOW}.abort.too_large",
    f"{APPROVAL_FLOW}.abort.not_loaded",
)
FENCED_YAML = re.compile(r"```yaml\s*\{actions\}\s*```")

# Flow descriptions whose user-text placeholders the flow escapes with escape_markdown (G-03-2). A translation must use
# them as bare words: wrapped in code, emphasis, link or quote markup they would render wrong or be escaped twice.
ESCAPED_FLOW_PLACEHOLDERS = {
    "config_subentries.switch.step.delete_device.description": ("name",),
    "config_subentries.select.step.delete_device.description": ("name",),
    "config_subentries.select.step.menu.description": ("name", "options"),
    "config_subentries.select.step.edit_option_details.description": ("state_value",),
    "config_subentries.select.step.remove_confirm.description": ("friendly_name", "state_value"),
}
MARKDOWN_CONTROL = r"\\`*_\[\]<>|~#"

# Translated errors of the services; each carries fixed text and no placeholder
SERVICE_EXCEPTIONS = (
    "not_loaded",
    "resync_throttled",
    "unknown_device",
    "not_a_device",
    "export_not_owned",
    "bad_file_name",
    "export_write_failed",
    "import_needs_exactly_one_source",
    "file_unreadable",
    "retrigger_bad_state",
    "retrigger_no_state",
    "retrigger_rate_limited",
)

# The message of a rejected import: exactly the position and the fixed reason code
IMPORT_REJECTED_VARIABLES = {"index", "reason"}

REQUIRED_KEYS = (
    "config.step.user.title",
    "config.step.user.description",
    "config.step.user.data.base_topic",
    "config.step.user.data.instance_name",
    "config.step.user.data_description.base_topic",
    "config.step.user.data_description.instance_name",
    "config.error.invalid_base_topic",
    "config.error.instance_name_required",
    "config.error.instance_name_invalid",
    "config.abort.mqtt_required",
    "config.abort.single_instance_allowed",
    "config_subentries.switch.initiate_flow.user",
    "config_subentries.switch.entry_type",
    "config_subentries.switch.step.user.title",
    "config_subentries.switch.step.reconfigure.title",
    "config_subentries.switch.step.reconfigure.description",
    "config_subentries.switch.step.reconfigure.menu_options.edit_device",
    "config_subentries.switch.step.reconfigure.menu_options.delete_device",
    "config_subentries.switch.step.edit_device.title",
    "config_subentries.switch.step.edit_device.description",
    *(
        f"config_subentries.{kind}.step.delete_device.{part}"
        for kind in ("switch", "select")
        for part in ("title", "description", "menu_options.delete_confirmed", "menu_options.keep_device")
    ),
    *(f"config_subentries.{kind}.abort.device_deleted" for kind in ("switch", "select")),
    "config_subentries.select.step.menu.menu_options.delete_device",
    "options.step.init.title",
    "options.step.init.description",
    "options.step.init.data.delete_devices_on_remove",
    "options.step.init.data_description.delete_devices_on_remove",
    "config_subentries.switch.error.name_required",
    "config_subentries.switch.error.name_invalid",
    "config_subentries.switch.error.invalid_actions",
    "config_subentries.switch.error.device_id_warning",
    "config_subentries.switch.abort.reconfigure_successful",
    "issues.action_failed.title",
    "issues.action_failed.description",
    "issues.mqtt_discovery_disabled.title",
    "issues.mqtt_discovery_disabled.description",
    "issues.circuit_breaker_tripped.title",
    "issues.circuit_breaker_tripped.description",
    *(f"issues.{issue}.{part}" for issue in NEW_ISSUES for part in ("title", "description")),
    *APPROVAL_FLOW_KEYS,
    *(
        f"config_subentries.switch.step.{step}.data.{field}"
        for step in ("user", "edit_device")
        for field in SWITCH_FORM_FIELDS
    ),
    "config_subentries.switch.error.breaker_max_runs_range",
    "config_subentries.switch.error.breaker_window_range",
    "entity.sensor.instances_online.name",
    "entity.button.resync.name",
    "services.resync.name",
    "services.resync.description",
    "services.export_devices.name",
    "services.export_devices.description",
    *(
        f"services.export_devices.fields.{field}.{part}"
        for field in ("device_id", "file_name")
        for part in ("name", "description")
    ),
    "services.import_devices.name",
    "services.import_devices.description",
    *(
        f"services.import_devices.fields.{field}.{part}"
        for field in ("data", "file_name")
        for part in ("name", "description")
    ),
    "services.retrigger.name",
    "services.retrigger.description",
    *(
        f"services.retrigger.fields.{field}.{part}"
        for field in ("device_id", "state")
        for part in ("name", "description")
    ),
    "exceptions.import_rejected.message",
    *(f"exceptions.{key}.message" for key in SERVICE_EXCEPTIONS),
    *(f"entity.select.{key}.name" for key in ("device_mode", "instance_mode")),
    *(
        f"entity.select.{key}.state.{mode}"
        for key in ("device_mode", "instance_mode")
        for mode in ("run", "observe", "disabled")
    ),
    *(
        f"config_subentries.switch.step.{step}.data_description.{field}"
        for step in ("user", "edit_device")
        for field in SWITCH_FORM_FIELDS
    ),
    "config_subentries.select.initiate_flow.user",
    "config_subentries.select.entry_type",
    "config_subentries.select.abort.reconfigure_successful",
    "selector.run_mode.options.serial",
    "selector.run_mode.options.restart",
    *(f"config_subentries.select.step.{step}.title" for step in ("user", "settings", "menu", "add_option")),
    *(f"config_subentries.select.step.menu.menu_options.{option}" for option in ("add_option", "settings", "done")),
    *(
        f"config_subentries.select.step.{step}.data.{field}"
        for step in ("user", "settings")
        for field in SELECT_SETTINGS_FIELDS
    ),
    *(
        f"config_subentries.select.step.add_option.data.{field}"
        for field in ("state_value", "friendly_name", "actions")
    ),
    *(f"config_subentries.select.error.{key}" for key in SELECT_ERROR_KEYS),
    *(f"config_subentries.select.step.menu.menu_options.{option}" for option in ("edit_option", "remove_option")),
    *(
        f"config_subentries.select.step.{step}.title"
        for step in ("edit_option", "edit_option_details", "remove_option")
    ),
    "config_subentries.select.step.remove_confirm.title",
    "config_subentries.select.step.remove_confirm.description",
    "config_subentries.select.step.edit_option.description",
    "config_subentries.select.step.edit_option.data.option",
    "config_subentries.select.step.remove_option.description",
    "config_subentries.select.step.remove_option.data.option",
    "config_subentries.select.step.remove_confirm.menu_options.remove_confirmed",
    "config_subentries.select.step.remove_confirm.menu_options.keep_option",
    "config_subentries.select.step.edit_option_details.description",
    *(
        f"config_subentries.select.step.edit_option_details.{group}.{field}"
        for group in ("data", "data_description")
        for field in ("friendly_name", "actions")
    ),
)


def _flatten(node: Any, prefix: str = "") -> dict[str, str]:
    """Flatten nested translation objects into dotted keys."""
    if isinstance(node, dict):
        flat: dict[str, str] = {}
        for key, value in node.items():
            flat.update(_flatten(value, f"{prefix}.{key}" if prefix else key))
        return flat
    return {prefix: node}


def _load(language: str) -> dict[str, str]:
    return _flatten(json.loads((TRANSLATIONS_DIR / f"{language}.json").read_text(encoding="utf-8")))


def _variables(text: str) -> set[str]:
    return set(VARIABLE.findall(text))


def test_en_and_de_have_identical_keys() -> None:
    assert set(_load("en")) == set(_load("de"))


def test_placeholders_match_between_languages() -> None:
    en, de = _load("en"), _load("de")
    mismatches = {
        key: (_variables(en[key]), _variables(de[key])) for key in en if _variables(en[key]) != _variables(de[key])
    }
    assert mismatches == {}


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_variable_inside_single_quotes(language: str) -> None:
    offenders = [key for key, value in _load(language).items() if VARIABLE_IN_SINGLE_QUOTES.search(value)]
    assert offenders == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_required_keys_present(language: str) -> None:
    flat = _load(language)
    missing = [key for key in REQUIRED_KEYS if not flat.get(key)]
    assert missing == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_issue_strings_use_expected_variables(language: str) -> None:
    flat = _load(language)
    assert _variables(flat["issues.action_failed.description"]) == {"device", "trigger", "time", "error"}
    assert _variables(flat["issues.circuit_breaker_tripped.description"]) == {"device", "max_runs", "window"}
    assert _variables(flat["issues.owner_conflict.description"]) == {"device", "owner", "claimant"}
    assert _variables(flat["issues.schema_too_new.description"]) == {"device", "version", "supported"}
    assert _variables(flat["issues.approval_required.description"]) == {"device", "owner", "hash"}
    assert _variables(flat[f"{APPROVAL_FLOW}.step.confirm.description"]) == {
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
    assert _variables(flat["issues.mirror_blocked.description"]) == {"device", "owner", "services"}
    assert _variables(flat["issues.denied_service_call.description"]) == {"device", "trigger", "service"}


@pytest.mark.parametrize("language", LANGUAGES)
def test_required_import_keys_exist_in_both_languages(language: str) -> None:
    """The import service texts exist, and the rejection message uses exactly the position and the reason."""
    flat = _load(language)
    assert flat["services.import_devices.name"]
    assert flat["services.import_devices.description"]
    assert _variables(flat["exceptions.import_rejected.message"]) == IMPORT_REJECTED_VARIABLES


@pytest.mark.parametrize("language", LANGUAGES)
def test_required_import_error_keys_exist_in_both_languages(language: str) -> None:
    """The source rule and the unreadable file have a fixed message without placeholders."""
    flat = _load(language)
    for key in ("import_needs_exactly_one_source", "file_unreadable"):
        assert flat[f"exceptions.{key}.message"]
        assert _variables(flat[f"exceptions.{key}.message"]) == set()


@pytest.mark.parametrize("language", LANGUAGES)
def test_confirm_description_contains_a_fenced_yaml_block(language: str) -> None:
    """The actions are shown as code: the placeholder sits alone inside a fenced yaml block."""
    assert FENCED_YAML.search(_load(language)[f"{APPROVAL_FLOW}.step.confirm.description"])


@pytest.mark.parametrize("language", LANGUAGES)
def test_issue_texts_exist_in_both_languages(language: str) -> None:
    """The owner-side issues have a title and a description in every language, using exactly their placeholders."""
    flat = _load(language)
    for issue, variables in NEW_ISSUES.items():
        assert flat[f"issues.{issue}.title"]
        assert _variables(flat[f"issues.{issue}.description"]) == variables


def test_error_placeholders_are_the_ones_the_flow_supplies() -> None:
    en = _load("en")
    assert _variables(en["config_subentries.switch.error.invalid_actions"]) == {"field", "error"}
    assert _variables(en["config_subentries.switch.error.device_id_warning"]) == {"device_ids"}


def test_delete_placeholders_are_the_ones_the_flow_supplies() -> None:
    """The delete confirmation of both device types is given exactly the device name and the online count."""
    en = _load("en")
    for kind in ("switch", "select"):
        assert _variables(en[f"config_subentries.{kind}.step.delete_device.description"]) == {"name", "count"}


def test_select_placeholders_are_the_ones_the_flow_supplies() -> None:
    en = _load("en")
    assert _variables(en["config_subentries.select.step.menu.description"]) == {"name", "count", "options"}
    assert _variables(en["config_subentries.select.error.invalid_actions"]) == {"field", "error"}
    assert _variables(en["config_subentries.select.error.device_id_warning"]) == {"device_ids"}
    assert _variables(en["config_subentries.select.step.edit_option_details.description"]) == {"state_value"}
    assert _variables(en["config_subentries.select.step.remove_confirm.description"]) == {
        "friendly_name",
        "state_value",
    }


@pytest.mark.parametrize("language", LANGUAGES)
def test_discovery_issue_speaks_of_entities_not_switch_entities(language: str) -> None:
    """Select and button entities need discovery too, so the Repairs text must not name only switches."""
    flat = _load(language)
    assert "switch" not in flat["issues.mqtt_discovery_disabled.description"].lower()
    assert "schalter" not in flat["issues.mqtt_discovery_disabled.description"].lower()


def test_no_strings_json_exists() -> None:
    """Custom integrations use translations/en.json; strings.json is core-only."""
    assert not (TRANSLATIONS_DIR.parent / "strings.json").exists()


@pytest.mark.parametrize("language", LANGUAGES)
def test_escaped_flow_placeholders_are_not_wrapped_in_markup(language: str) -> None:
    """A single escape pass renders right only if the placeholder is a bare word (T-03-39)."""
    flat = _load(language)
    offenders = []
    for key, names in ESCAPED_FLOW_PLACEHOLDERS.items():
        text = flat[key]
        if "```" in text:
            offenders.append((key, "fenced block"))
        for name in names:
            variable = re.escape("{" + name + "}")
            if re.search(f"[{MARKDOWN_CONTROL}]{variable}|{variable}[{MARKDOWN_CONTROL}]", text):
                offenders.append((key, name))
    assert offenders == []


RETRIGGER_KEYS = (
    "services.retrigger.name",
    "services.retrigger.description",
    "services.retrigger.fields.device_id.name",
    "services.retrigger.fields.device_id.description",
    "services.retrigger.fields.state.name",
    "services.retrigger.fields.state.description",
    "exceptions.retrigger_bad_state.message",
    "exceptions.retrigger_no_state.message",
    "exceptions.retrigger_rate_limited.message",
)


def test_required_retrigger_keys_exist_in_both_languages() -> None:
    """The re-trigger service texts and its three translated refusals exist in en and de, with fixed text only."""
    for language in LANGUAGES:
        flat = _load(language)
        assert [key for key in RETRIGGER_KEYS if not flat.get(key)] == [], language
        assert all(not _variables(flat[key]) for key in RETRIGGER_KEYS), language


ADOPT_KEYS = (
    "services.adopt_device.name",
    "services.adopt_device.description",
    "services.adopt_device.fields.device_id.name",
    "services.adopt_device.fields.device_id.description",
    "services.adopt_device.fields.force.name",
    "services.adopt_device.fields.force.description",
    "exceptions.adopt_owner_not_offline.message",
    "exceptions.adopt_not_approved.message",
    "exceptions.adopt_not_a_mirror.message",
)


@pytest.mark.parametrize("language", LANGUAGES)
def test_required_adopt_keys_exist_in_both_languages(language: str) -> None:
    """The adoption service texts and its three refusals exist; the owner-not-offline text names force: true."""
    flat = _load(language)
    assert [key for key in ADOPT_KEYS if not flat.get(key)] == []
    assert _variables(flat["exceptions.adopt_owner_not_offline.message"]) == {"device", "owner"}
    assert _variables(flat["exceptions.adopt_not_approved.message"]) == {"device"}
    assert _variables(flat["exceptions.adopt_not_a_mirror.message"]) == set()
    assert "force: true" in flat["exceptions.adopt_owner_not_offline.message"]
