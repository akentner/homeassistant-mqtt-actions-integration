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

SWITCH_FORM_FIELDS = ("name", "on_change_to_on", "on_change_to_off", "run_on_startup")

REQUIRED_KEYS = (
    "config.step.user.title",
    "config.step.user.description",
    "config.step.user.data.base_topic",
    "config.step.user.data.instance_name",
    "config.step.user.data_description.base_topic",
    "config.step.user.data_description.instance_name",
    "config.error.invalid_base_topic",
    "config.error.instance_name_required",
    "config.abort.mqtt_required",
    "config.abort.single_instance_allowed",
    "config_subentries.switch.initiate_flow.user",
    "config_subentries.switch.entry_type",
    "config_subentries.switch.step.user.title",
    "config_subentries.switch.step.reconfigure.title",
    "config_subentries.switch.error.name_required",
    "config_subentries.switch.error.invalid_actions",
    "config_subentries.switch.error.device_id_warning",
    "config_subentries.switch.abort.reconfigure_successful",
    "issues.action_failed.title",
    "issues.action_failed.description",
    "issues.mqtt_discovery_disabled.title",
    "issues.mqtt_discovery_disabled.description",
    "issues.circuit_breaker_tripped.title",
    "issues.circuit_breaker_tripped.description",
    *(
        f"config_subentries.switch.step.{step}.data.{field}"
        for step in ("user", "reconfigure")
        for field in SWITCH_FORM_FIELDS
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


def test_error_placeholders_are_the_ones_the_flow_supplies() -> None:
    en = _load("en")
    assert _variables(en["config_subentries.switch.error.invalid_actions"]) == {"field", "error"}
    assert _variables(en["config_subentries.switch.error.device_id_warning"]) == {"device_ids"}


def test_no_strings_json_exists() -> None:
    """Custom integrations use translations/en.json; strings.json is core-only."""
    assert not (TRANSLATIONS_DIR.parent / "strings.json").exists()
