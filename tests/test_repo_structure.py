"""Executable checks for repository distribution (FND-01) and CI supply chain (FND-02)."""

import json
import re
import struct
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "custom_components"
INTEGRATION = COMPONENTS / "mqtt_actions"
WORKFLOWS = ROOT / ".github" / "workflows"
WORKFLOW_FILES = ("validate.yml", "ci.yml")

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
HACS_REQUIRED_MANIFEST_KEYS = ("codeowners", "documentation", "domain", "issue_tracker", "name", "version")
HACS_ALLOWED_KEYS = {
    "name",
    "content_in_root",
    "country",
    "filename",
    "hacs",
    "hide_default_branch",
    "homeassistant",
    "persistent_directory",
    "render_readme",
    "zip_release",
}


def _load_workflow(filename: str) -> dict[Any, Any]:
    document = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _triggers(document: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML parses the bare key `on` as the boolean True.
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), "workflow needs a mapping of triggers"
    return triggers


def _steps(document: dict[Any, Any]) -> list[dict[str, Any]]:
    return [step for job in document["jobs"].values() for step in job["steps"]]


def _uses_refs(document: dict[Any, Any]) -> list[str]:
    refs = [step["uses"] for step in _steps(document) if "uses" in step]
    # Job-level reusable workflows also carry a `uses` key.
    refs += [job["uses"] for job in document["jobs"].values() if "uses" in job]
    return refs


workflow_files = pytest.mark.parametrize("filename", WORKFLOW_FILES)


def test_manifest_has_hacs_required_keys() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    for key in HACS_REQUIRED_MANIFEST_KEYS:
        assert manifest.get(key), f"manifest.json misses {key}"
    assert SEMVER.match(manifest["version"]), manifest["version"]


def test_domain_matches_folder_name() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    folders = [path.name for path in COMPONENTS.iterdir() if path.is_dir() and not path.name.startswith("__")]
    assert folders == [manifest["domain"]] == ["mqtt_actions"]


def test_hacs_json_keys_allowed_and_floor() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert "name" in hacs
    assert set(hacs) <= HACS_ALLOWED_KEYS, set(hacs) - HACS_ALLOWED_KEYS
    assert hacs["homeassistant"] == "2026.9.0"


def test_brand_icon_is_valid_png() -> None:
    data = (INTEGRATION / "brand" / "icon.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    assert width >= 256
    assert height >= 256


def test_license_is_mit_with_holder() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Alexander Kentner" in text


def test_readme_documents_install_limits_and_trust() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered = text.lower()
    for phrase in ("hacs", "mqtt discovery", "retained", "acl"):
        assert phrase in lowered, f"README never mentions {phrase}"
    headings = [line.lstrip("#").strip().lower() for line in text.splitlines() if line.startswith("#")]
    for section in ("installation", "limitations", "security"):
        assert any(heading.startswith(section) for heading in headings), f"README has no {section} section"


def test_readme_documents_phase2_behavior() -> None:
    lowered = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    for phrase in ("select device", "run mode", "circuit breaker", "test button", "/test"):
        assert phrase in lowered, f"README never mentions {phrase}"
    assert "5 runs in 10 seconds" in lowered
    assert "only switch and select devices exist" in lowered


@workflow_files
def test_workflows_have_empty_permissions(filename: str) -> None:
    workflow = _load_workflow(filename)
    assert workflow["permissions"] == {}


@workflow_files
def test_all_action_refs_are_pinned_by_sha(filename: str) -> None:
    workflow = _load_workflow(filename)
    refs = _uses_refs(workflow)
    assert refs, "workflow uses no actions at all"
    for ref in refs:
        assert SHA_PIN.match(ref), f"{ref} is not pinned by a 40-character commit SHA"


@workflow_files
def test_checkout_does_not_persist_credentials(filename: str) -> None:
    workflow = _load_workflow(filename)
    checkouts = [step for step in _steps(workflow) if step.get("uses", "").startswith("actions/checkout@")]
    for step in checkouts:
        assert step.get("with", {}).get("persist-credentials") is False


def test_hacs_action_has_category_and_no_ignore() -> None:
    steps = [step for step in _steps(_load_workflow("validate.yml")) if step.get("uses", "").startswith("hacs/action@")]
    assert len(steps) == 1
    inputs = steps[0].get("with", {})
    assert inputs.get("category") == "integration"
    assert "ignore" not in inputs


@workflow_files
def test_push_trigger_has_no_branch_filter(filename: str) -> None:
    workflow = _load_workflow(filename)
    triggers = _triggers(workflow)
    assert "push" in triggers
    assert "branches" not in (triggers["push"] or {})
    assert "branches-ignore" not in (triggers["push"] or {})


def test_ci_runs_locked_sync_lint_format_and_pytest() -> None:
    commands = [step["run"].strip() for step in _steps(_load_workflow("ci.yml")) if "run" in step]
    for expected in ("uv sync --locked", "uv run ruff check .", "uv run ruff format --check .", "uv run pytest"):
        assert any(command.startswith(expected) for command in commands), f"ci.yml never runs {expected}"
    assert any("mosquitto" in command for command in commands), "ci.yml must install mosquitto for the broker tests"


def test_validate_workflow_has_hassfest_and_hacs_jobs() -> None:
    document = _load_workflow("validate.yml")
    assert document["name"] == "Validate"
    assert {"hassfest", "hacs"} <= set(document["jobs"])
    refs = _uses_refs(document)
    assert any(ref.startswith("home-assistant/actions/hassfest@") for ref in refs)
    assert any(ref.startswith("hacs/action@") for ref in refs)
    assert "schedule" in _triggers(document)


def test_dependabot_covers_actions_and_uv() -> None:
    document = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    assert document["version"] == 2
    ecosystems = {update["package-ecosystem"] for update in document["updates"]}
    assert {"github-actions", "uv"} <= ecosystems
