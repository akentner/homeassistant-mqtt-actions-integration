"""Documentation checks: the README says what the code does (D-16)."""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from custom_components.mqtt_actions import const
from tests.test_diagnostics import DEVICE_KEYS, HUB_KEYS, ROSTER_KEYS, TOP_KEYS

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DOCS = ROOT / "docs"
OPERATIONS = DOCS / "operations.md"
DIAGNOSTICS = DOCS / "diagnostics.md"
TROUBLESHOOTING = DOCS / "troubleshooting.md"
BROKER_ACL = DOCS / "broker-acl.md"
TRANSLATIONS = ROOT / "custom_components" / "mqtt_actions" / "translations" / "en.json"
SERVICES_YAML = ROOT / "custom_components" / "mqtt_actions" / "services.yaml"
# The pages this plan adds; every one of them has to exist for the link and example checks to mean anything
EXPECTED_PAGES = ("operations.md", "diagnostics.md", "troubleshooting.md")
FENCE = re.compile(r"^```([^\n]*)\n(.*?)^```$", re.DOTALL | re.MULTILINE)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _normalize(text: str) -> str:
    """Return text with whitespace collapsed and lower-cased."""
    return re.sub(r"\s+", " ", text).lower()


def _bullets(text: str) -> list[str]:
    """Return the list items of a markdown text: a line starting with a dash plus the indented lines after it."""
    items: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            items.append(line)
        elif items and line.startswith("  ") and line.strip():
            items[-1] += f" {line.strip()}"
    return [_normalize(item) for item in items]


def test_readme_states_what_the_approval_hash_binds() -> None:
    """The approval bullet names the startup flag, run mode and circuit breaker limits, and the one-time lapse."""
    text = README.read_text(encoding="utf-8")
    bullet = next((item for item in _bullets(text) if "bound to the hash" in item), None)
    assert bullet is not None, "the README has no bullet that says the approval is bound to the hash"
    for phrase in ("actions", "startup flag", "run mode", "circuit breaker limits"):
        assert phrase in bullet, f"the approval bullet never names {phrase}"
    assert "lapse once" in _normalize(text)


def _page(path: Path) -> str:
    """Return the text of a documentation page; a page that does not exist fails the test with a clear message."""
    assert path.is_file(), f"{path.relative_to(ROOT)} does not exist"
    return path.read_text(encoding="utf-8")


def _headings(text: str) -> list[str]:
    """Return the lower-cased headings of a markdown text without their hash marks."""
    return [line.lstrip("#").strip().lower() for line in text.splitlines() if line.startswith("#")]


def _documents() -> list[Path]:
    """Return the README and every page below docs."""
    return [README, *sorted(DOCS.glob("*.md"))]


def test_operations_page_exists_with_the_sections() -> None:
    headings = _headings(_page(OPERATIONS))
    for section in (
        "services",
        "re-trigger",
        "roster",
        "resync",
        "modes",
        "adoption",
        "duplicate instance id",
        "export and import",
        "upgrade notes",
    ):
        assert any(heading.startswith(section) for heading in headings), f"the operations page has no {section} section"


def test_operations_page_names_every_service_and_field() -> None:
    text = _page(OPERATIONS)
    services = yaml.safe_load(SERVICES_YAML.read_text(encoding="utf-8"))
    assert services, "services.yaml has no services"
    for service, definition in services.items():
        assert f"`{service}`" in text, f"the operations page never names the service {service}"
        for field in (definition or {}).get("fields", {}):
            assert f"`{field}`" in text, f"the operations page never names the field {field} of {service}"


def test_operations_page_documents_the_wire_contract() -> None:
    text = _page(OPERATIONS)
    topics = (
        "<base topic>/v1/instances/<instance id>/heartbeat",
        "<base topic>/v1/devices/<device uuid>/retrigger",
        "<base topic>/v1/instances/<requester id>/acks",
    )
    request = ("request_id", "requester", "state", "sent_at")
    acknowledgement = ("request_id", "device_id", "instance_id", "instance_name", "status", "reason")
    heartbeat = ("instance_id", "name", "version", "devices", "session")
    statuses = (
        const.ACK_EXECUTED,
        const.ACK_NOT_APPROVED,
        const.ACK_PAUSED,
        const.ACK_OBSERVING,
        const.ACK_DISABLED,
        const.ACK_ERROR,
        const.ACK_NO_ANSWER,
    )
    for topic in topics:
        assert f"`{topic}`" in text, f"the operations page never names the topic {topic}"
    for name in (*request, *acknowledgement, *heartbeat, const.TOPIC_VERSION, "transferred_from"):
        assert f"`{name}`" in text, f"the operations page never names {name}"
    for word in (*statuses, const.EXPORT_FORMAT, "format", "export_version"):
        assert f"`{word}`" in text, f"the operations page never names {word}"
    # The format name and the version of the export are the contract of the files users keep
    assert const.EXPORT_FORMAT == "mqtt_actions_export"
    assert f"`{const.EXPORT_VERSION}`" in text


def test_operations_page_numbers_match_the_constants() -> None:
    """Every limit is written next to its constant name, with the value and unit of const.py."""
    lines = _page(OPERATIONS).splitlines()
    limits = {
        "HEARTBEAT_INTERVAL_SECONDS": f"{int(const.HEARTBEAT_INTERVAL_SECONDS)} seconds",
        "HEARTBEAT_OFFLINE_SECONDS": f"{int(const.HEARTBEAT_OFFLINE_SECONDS)} seconds",
        "DUPLICATE_ID_CONFIRMATIONS": f"{const.DUPLICATE_ID_CONFIRMATIONS} heartbeats",
        "RETRIGGER_ACK_WINDOW_SECONDS": f"{int(const.RETRIGGER_ACK_WINDOW_SECONDS)} seconds",
        "RETRIGGER_DEVICE_INTERVAL_SECONDS": f"{int(const.RETRIGGER_DEVICE_INTERVAL_SECONDS)} seconds",
        "RETRIGGER_SEEN_LIMIT": f"{const.RETRIGGER_SEEN_LIMIT} request ids",
        "RETRIGGER_MAX_AGE_SECONDS": f"{int(const.RETRIGGER_MAX_AGE_SECONDS)} seconds",
        "MAX_IMPORT_DEVICES": f"{const.MAX_IMPORT_DEVICES} devices",
        "MAX_IMPORT_BYTES": f"{const.MAX_IMPORT_BYTES // 1024**2} MiB",
        "MAX_TRANSFER_HISTORY": f"{const.MAX_TRANSFER_HISTORY} entries",
        "RESYNC_MIN_INTERVAL_SECONDS": f"{int(const.RESYNC_MIN_INTERVAL_SECONDS)} seconds",
    }
    for name, expected in limits.items():
        rows = [line for line in lines if f"`{name}`" in line]
        assert rows, f"the operations page never names the constant {name}"
        assert any(expected in row for row in rows), f"the page does not say {expected} next to {name}"


def _paths_of_key(node: Any, key: str, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Return the key paths below which a mapping key of that name appears, at any depth, lists included."""
    found: list[tuple[str, ...]] = []
    if isinstance(node, dict):
        for name, value in node.items():
            here = (*path, str(name))
            if name == key:
                found.append(here)
            found.extend(_paths_of_key(value, key, here))
    elif isinstance(node, list):
        for item in node:
            found.extend(_paths_of_key(item, key, path))
    return found


def test_device_id_appears_only_as_a_service_data_field() -> None:
    """A fenced example may carry the registry device id only as `data` of an mqtt_actions service call (T-04-62)."""
    operations_examples = 0
    for document in _documents():
        text = document.read_text(encoding="utf-8")
        used = False
        for info, body in FENCE.findall(text):
            if "device_id" not in body:
                continue
            used = True
            assert info.strip() == "yaml", f"{document.name} has a device_id in a block that is not YAML"
            parsed = yaml.safe_load(body)
            assert isinstance(parsed, dict), f"{document.name} has a device_id in a block that is no mapping"
            action = parsed.get("action")
            assert isinstance(action, str)
            assert action.startswith("mqtt_actions."), f"{document.name} has a device_id outside an mqtt_actions call"
            assert _paths_of_key(parsed, "device_id") == [("data", "device_id")], (
                f"{document.name} has a device_id somewhere other than the data of the call"
            )
            assert "target" not in parsed, f"{document.name} gives an mqtt_actions call a target"
            if document == OPERATIONS:
                operations_examples += 1
        if used:
            normalized = _normalize(text)
            assert "differs between instances" in normalized, f"{document.name} never says the id differs"
            assert "must not be used in shared actions" in normalized, f"{document.name} never warns about sharing"
    assert operations_examples, "the operations page has no service call example with a device_id"


def test_docs_links_resolve() -> None:
    for name in EXPECTED_PAGES:
        assert (DOCS / name).is_file(), f"docs/{name} does not exist"
    for document in _documents():
        for target in LINK.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = (document.parent / target.split("#", 1)[0]).resolve()
            assert path.exists(), f"{document.name} links to {target}, which does not exist"


def _sentences(text: str) -> list[str]:
    """Return the lower-cased sentences of a text, without backticks and emphasis marks."""
    plain = _normalize(text).replace("`", "").replace("*", "")
    return [part.strip() for part in re.split(r"(?<=[.!?:])\s", plain) if part.strip()]


def _link_targets(document: Path) -> set[Path]:
    """Return the files that a markdown page links to by a relative link."""
    targets: set[Path] = set()
    for target in LINK.findall(document.read_text(encoding="utf-8")):
        if not target.startswith(("http://", "https://", "mailto:", "#")):
            targets.add((document.parent / target.split("#", 1)[0]).resolve())
    return targets


def test_diagnostics_page_lists_the_included_keys_and_the_exclusions() -> None:
    text = _page(DIAGNOSTICS)
    # The key sets that tests/test_diagnostics.py pins to the real output, plus the keys the plan names
    keys = {*TOP_KEYS, *HUB_KEYS, *ROSTER_KEYS, *DEVICE_KEYS, "hub", "roster", "devices", "approval", "breaker"}
    for key in sorted(keys):
        assert f"`{key}`" in text, f"the diagnostics page never names the key {key}"
    sentences = _sentences(text)
    assert any("instance id" in sentence and "eight characters" in sentence for sentence in sentences), (
        "the diagnostics page never says that instance ids are shortened to eight characters"
    )
    exclusions = (
        ("actions", "yaml", "templates", "entity ids", "service data"),
        ("device names",),
        ("credentials", "host names"),
    )
    for needles in exclusions:
        assert any("never" in sentence and all(needle in sentence for needle in needles) for sentence in sentences), (
            f"the diagnostics page has no sentence that says {', '.join(needles)} are never included"
        )


def test_troubleshooting_covers_every_issue_key() -> None:
    text = _page(TROUBLESHOOTING)
    issues = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))["issues"]
    assert issues, "the English translations have no issues"
    for key in issues:
        assert f"`{key}`" in text, f"the troubleshooting page has no entry for the issue {key}"


def test_troubleshooting_covers_the_operating_problems() -> None:
    headings = _headings(_page(TROUBLESHOOTING))
    for problem in (
        "entities are unavailable",
        "approvals lapsed after an upgrade",
        "a denied publish is not reported",
        "adoption or ownership conflicts",
        "a new instance id and the acl",
        "a device exists twice on the integration page",
        "resync did not restore the entities",
    ):
        assert any(heading.startswith(problem) for heading in headings), f"troubleshooting has no {problem} section"


def test_security_limits_are_stated() -> None:
    """No page promises more than the code gives: advisory acknowledgements, cooperative ownership, responsibility."""
    operations = _normalize(_page(OPERATIONS))
    assert "acknowledgements are advisory" in operations
    assert "ownership is cooperative" in operations
    acl = _normalize(_page(BROKER_ACL))
    assert "cooperative" in acl
    assert "adoption and import put content under the administrator's responsibility" in acl
    troubleshooting = _page(TROUBLESHOOTING)
    assert {OPERATIONS.resolve(), DIAGNOSTICS.resolve()} <= _link_targets(TROUBLESHOOTING), (
        "the troubleshooting page does not link the operations and diagnostics pages"
    )
    assert "advisory" in _normalize(troubleshooting)
    assert "cooperative" in _normalize(troubleshooting)
