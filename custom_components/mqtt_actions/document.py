"""
The central config document: the wire contract between the owner of a device and every other instance (D-12, D-13).

Pure module: no Home Assistant import at runtime except the JSON parser of core. One retained (QoS 1) JSON document
per device is published at `<base>/<TOPIC_VERSION>/devices/<device_id>/config` by its owner. It carries:

- identity and bookkeeping: `schema_version`, `device_id`, `owner` (instance id), `owner_name`, `rev` and `hash`
- the shared content (D-13): `kind`, `name`, `run_on_startup`, `run_mode`, `breaker_max_runs`, `breaker_window` and the
  actions, as `on_change_to_on` and `on_change_to_off` for a Switch or as `options` for a Select

The keys of the content are the keys of the subentry data, so a validated document is also valid subentry data.

The canonical-JSON and sha256 algorithm is part of the wire contract and changing it is a breaking protocol change:

- `canonical_json` is `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`
- `content_hash` is the sha256 hex digest of the UTF-8 canonical JSON of the content; owner, owner name, rev, hash,
  device id and schema version are not content, so moving or renaming an instance never changes what a device means
- `actions_hash` binds an approval (D-02, D-16). It is the sha256 of the canonical JSON of the kind, `run_on_startup`,
  `run_mode`, both breaker limits and the list of [lower-cased StateValue, actions] pairs sorted by the lower-cased
  StateValue. It changes when the state-to-actions mapping, the startup flag, the run mode or a breaker limit changes,
  never on a rename. It is computed locally from received content and never read from the wire, so binding more
  settings changes no wire field and needs no SCHEMA_VERSION bump.

Documents are built from the DeviceSpec, where defaults are applied, and never from raw subentry data: a device stored
before Phase 2 publishes the same defaults as an explicit one, so a hash always means "behaves the same".

Receiving is the opposite direction and strict (D-06): `parse_document` is the only way a broker payload becomes a
spec. It never trusts the `hash` field of the wire, it recomputes both hashes from the received content. Its rejections
are typed (`DocumentRejectedError.reason`) and never carry payload or action content, so they are safe to log.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.util.json import json_loads

from .const import (
    CONF_ACTIONS,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_OPTIONS,
    CONF_RUN_MODE,
    CONF_RUN_ON_STARTUP,
    CONF_STATE_VALUE,
    DENIED_DOMAINS,
    DENIED_SERVICES,
    MAX_ACTION_DEPTH,
    MAX_DOCUMENT_BYTES,
    MAX_OPTIONS,
    MIN_OPTIONS,
    RESIDUAL_SERVICES,
    RUN_MODE_RESTART,
    RUN_MODE_SERIAL,
    SCHEMA_VERSION,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from .model import SWITCH_OFF_KEY, SWITCH_ON_KEY, _encodable, _invalid_text, spec_from_data, validate_breaker

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .model import DeviceSpec


def canonical_json(value: Any) -> str:
    """Return the canonical JSON text of a value: sorted keys, compact separators, unescaped UTF-8, no NaN."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_content(spec: DeviceSpec) -> dict[str, Any]:
    """Return the shared content of a device (D-13) from its spec; identity and bookkeeping are not part of it."""
    content: dict[str, Any] = {
        "kind": spec.kind,
        "name": spec.name,
        CONF_RUN_ON_STARTUP: spec.run_on_startup,
        CONF_RUN_MODE: spec.run_mode,
        CONF_BREAKER_MAX_RUNS: spec.breaker_max_runs,
        CONF_BREAKER_WINDOW: spec.breaker_window,
    }
    if spec.kind == SUBENTRY_SELECT:
        content[CONF_OPTIONS] = [
            {
                CONF_STATE_VALUE: trigger.value,
                CONF_FRIENDLY_NAME: trigger.friendly_name,
                CONF_ACTIONS: trigger.actions,
            }
            for trigger in spec.triggers.values()
        ]
    else:
        content[CONF_ON_CHANGE_TO_ON] = spec.triggers[SWITCH_ON_KEY].actions
        content[CONF_ON_CHANGE_TO_OFF] = spec.triggers[SWITCH_OFF_KEY].actions
    return content


def content_hash(content: dict[str, Any]) -> str:
    """Return the sha256 hex digest of the canonical JSON of the shared content."""
    return _sha256(canonical_json(content))


def actions_hash(spec: DeviceSpec) -> str:
    """
    Return the hash an approval is bound to: the mapping, the startup flag, the run mode and the breaker limits.

    What a user approves is what can run, including how often and in which mode (A5 revised by D-16, WR-04); only the
    name is left out, so a rename keeps the approval.
    """
    pairs = sorted(
        ([trigger.value.lower(), trigger.actions] for trigger in spec.triggers.values()),
        key=lambda pair: pair[0],
    )
    return _sha256(
        canonical_json(
            {
                "kind": spec.kind,
                CONF_RUN_ON_STARTUP: spec.run_on_startup,
                CONF_RUN_MODE: spec.run_mode,
                CONF_BREAKER_MAX_RUNS: spec.breaker_max_runs,
                CONF_BREAKER_WINDOW: spec.breaker_window,
                "triggers": pairs,
            }
        )
    )


def build_document(spec: DeviceSpec, *, owner: str, owner_name: str, rev: int) -> dict[str, Any]:
    """Return the document of a device: identity and bookkeeping, the content hash and the shared content."""
    content = build_content(spec)
    return {
        "schema_version": SCHEMA_VERSION,
        CONF_DEVICE_ID: spec.device_id,
        "owner": owner,
        "owner_name": owner_name,
        "rev": rev,
        "hash": content_hash(content),
        **content,
    }


def serialize_document(document: dict[str, Any]) -> str:
    """Return the wire text of a document; deterministic, so an unchanged device always publishes the same bytes."""
    return canonical_json(document)


class RejectReason(StrEnum):
    """The reason codes of a rejected document; safe to log, they name the rule and never the content."""

    BAD_ACTIONS = "bad_actions"
    BAD_BREAKER = "bad_breaker"
    BAD_FRIENDLY_NAME = "bad_friendly_name"
    BAD_KIND = "bad_kind"
    BAD_NAME = "bad_name"
    BAD_OPTION_VALUE = "bad_option_value"
    BAD_OPTIONS = "bad_options"
    BAD_OWNER = "bad_owner"
    BAD_OWNER_NAME = "bad_owner_name"
    BAD_REV = "bad_rev"
    BAD_RUN_MODE = "bad_run_mode"
    BAD_RUN_ON_STARTUP = "bad_run_on_startup"
    BAD_SCHEMA_VERSION = "bad_schema_version"
    DEVICE_ID_MISMATCH = "device_id_mismatch"
    DUPLICATE_STATE_VALUE = "duplicate_state_value"
    NOT_JSON = "not_json"
    NOT_OBJECT = "not_object"
    TOO_DEEP = "too_deep"
    TOO_LARGE = "too_large"
    SCHEMA_TOO_NEW = "schema_too_new"


class DocumentRejectedError(ValueError):
    """A received document is not acceptable; `reason` is a short code, the message never carries document content."""

    def __init__(self, reason: RejectReason) -> None:
        """Initialize the error with its reason code."""
        super().__init__(f"config document rejected: {reason}")
        self.reason = reason


def _reject(reason: RejectReason) -> DocumentRejectedError:
    """Return the rejection for a reason code; raising the result keeps the code out of an exception literal."""
    return DocumentRejectedError(reason)


class SchemaTooNewError(DocumentRejectedError):
    """A document has a higher schema_version than this integration knows (D-14); nothing else was read."""

    def __init__(self, version: int) -> None:
        """Initialize the error with the version the document announced."""
        super().__init__(RejectReason.SCHEMA_TOO_NEW)
        self.version = version


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """A validated document: the spec built from it and both hashes recomputed from the received content."""

    device_id: str
    owner: str
    owner_name: str
    rev: int
    schema_version: int
    spec: DeviceSpec
    content: dict[str, Any]
    content_hash: str
    actions_hash: str
    payload: str


def migrate(document: dict[str, Any]) -> dict[str, Any]:
    """
    Return the document in the current schema.

    Only schema_version 1 exists, so nothing changes. A reader of an older schema_version converts it here, before any
    field is validated (D-14); the conversion belongs in this function and nowhere else.
    """
    return document


def actions_depth(node: Any) -> int:
    """
    Return the number of container levels of a structure: 0 for a scalar, 1 for an empty list or dict, and so on.

    Iterative, so a hostile structure cannot exhaust the stack. A nested choose costs about four levels (the step, its
    choose list, an option and its sequence).
    """
    deepest = 0
    stack: list[tuple[Any, int]] = [(node, 0)]
    while stack:
        current, level = stack.pop()
        if isinstance(current, dict):
            children: Any = current.values()
        elif isinstance(current, list):
            children = current
        else:
            continue
        level += 1
        deepest = max(deepest, level)
        stack.extend((child, level) for child in children)
    return deepest


def _is_text(value: Any) -> bool:
    return isinstance(value, str)


def _invalid_label(value: Any) -> bool:
    """Return True for text that may not reach a log or a Repairs text: not a string, blank, unprintable or too long."""
    return not isinstance(value, str) or not value.strip() or _invalid_text(value)


def _is_int(value: Any) -> bool:
    return type(value) is int


def _action_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def _check_options(document: Mapping[str, Any]) -> list[list[dict[str, Any]]]:
    """Validate the options of a Select document and return their action lists."""
    options = document.get(CONF_OPTIONS)
    if not isinstance(options, list) or not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise _reject(RejectReason.BAD_OPTIONS)
    seen: set[str] = set()
    action_lists: list[list[dict[str, Any]]] = []
    for option in options:
        if not isinstance(option, dict) or not all(
            key in option for key in (CONF_STATE_VALUE, CONF_FRIENDLY_NAME, CONF_ACTIONS)
        ):
            raise _reject(RejectReason.BAD_OPTIONS)
        value = option[CONF_STATE_VALUE]
        friendly = option[CONF_FRIENDLY_NAME]
        if not _is_text(value) or not _is_text(friendly):
            raise _reject(RejectReason.BAD_OPTIONS)
        if not _action_list(option[CONF_ACTIONS]):
            raise _reject(RejectReason.BAD_ACTIONS)
        if not value or value != value.strip() or _invalid_text(value) or not _encodable(value):
            raise _reject(RejectReason.BAD_OPTION_VALUE)
        if not friendly.strip() or _invalid_text(friendly) or not _encodable(friendly):
            raise _reject(RejectReason.BAD_FRIENDLY_NAME)
        if value.lower() in seen:
            raise _reject(RejectReason.DUPLICATE_STATE_VALUE)
        seen.add(value.lower())
        action_lists.append(option[CONF_ACTIONS])
    return action_lists


def _validated(document: dict[str, Any], topic_device_id: str) -> list[list[dict[str, Any]]]:
    """Check every field of a document in the current schema and return its action lists; raise on the first flaw."""
    if document.get(CONF_DEVICE_ID) != topic_device_id:
        raise _reject(RejectReason.DEVICE_ID_MISMATCH)
    if _invalid_label(document.get("owner")):
        raise _reject(RejectReason.BAD_OWNER)
    if _invalid_label(document.get("owner_name")):
        raise _reject(RejectReason.BAD_OWNER_NAME)
    rev = document.get("rev")
    if not _is_int(rev) or rev < 0:
        raise _reject(RejectReason.BAD_REV)
    kind = document.get("kind")
    # A list or dict is unhashable, so the type is checked before the membership test
    if not isinstance(kind, str) or kind not in {SUBENTRY_SWITCH, SUBENTRY_SELECT}:
        raise _reject(RejectReason.BAD_KIND)
    if _invalid_label(document.get("name")):
        raise _reject(RejectReason.BAD_NAME)
    run_mode = document.get(CONF_RUN_MODE)
    if not isinstance(run_mode, str) or run_mode not in {RUN_MODE_SERIAL, RUN_MODE_RESTART}:
        raise _reject(RejectReason.BAD_RUN_MODE)
    max_runs = document.get(CONF_BREAKER_MAX_RUNS)
    window = document.get(CONF_BREAKER_WINDOW)
    if not _is_int(max_runs) or not _is_int(window) or validate_breaker(max_runs, window):
        raise _reject(RejectReason.BAD_BREAKER)
    if not isinstance(document.get(CONF_RUN_ON_STARTUP), bool):
        raise _reject(RejectReason.BAD_RUN_ON_STARTUP)
    if kind == SUBENTRY_SELECT:
        return _check_options(document)
    lists = [document.get(CONF_ON_CHANGE_TO_ON), document.get(CONF_ON_CHANGE_TO_OFF)]
    if not all(_action_list(value) for value in lists):
        raise _reject(RejectReason.BAD_ACTIONS)
    return lists


def parse_document(topic_device_id: str, payload: str) -> ParsedDocument:
    """
    Validate a payload received on the config topic of a device and return the parsed document.

    Checks in this order: size in UTF-8 bytes, JSON object, schema_version (a higher one raises SchemaTooNewError
    before anything else is read), migration, then every field. The `hash` field of the wire is ignored, both hashes
    are recomputed from the received content; unknown extra keys are ignored and never hashed. Raises
    DocumentRejectedError with a reason code and a message free of payload content.
    """
    if len(payload) > MAX_DOCUMENT_BYTES or len(payload.encode(errors="replace")) > MAX_DOCUMENT_BYTES:
        raise _reject(RejectReason.TOO_LARGE)
    try:
        value = json_loads(payload)
    except ValueError as err:
        raise _reject(RejectReason.NOT_JSON) from err
    if type(value) is not dict:
        raise _reject(RejectReason.NOT_OBJECT)
    version = value.get("schema_version")
    if not _is_int(version) or version < 1:
        raise _reject(RejectReason.BAD_SCHEMA_VERSION)
    if version > SCHEMA_VERSION:
        raise SchemaTooNewError(version)
    document = migrate(value)
    action_lists = _validated(document, topic_device_id)
    if any(actions_depth(actions) > MAX_ACTION_DEPTH for actions in action_lists):
        raise _reject(RejectReason.TOO_DEEP)
    spec = spec_from_data(document["kind"], document["name"], document)
    try:
        content = build_content(spec)
        digest = content_hash(content)
        approval = actions_hash(spec)
    except (ValueError, TypeError) as err:
        raise _reject(RejectReason.BAD_ACTIONS) from err
    return ParsedDocument(
        device_id=topic_device_id,
        owner=document["owner"],
        owner_name=document["owner_name"],
        rev=document["rev"],
        schema_version=version,
        spec=spec,
        content=content,
        content_hash=digest,
        actions_hash=approval,
        payload=payload,
    )


# --- service denylist and approval view (D-03, D-04) -----------------------------------------------------------------

_SERVICE_KEYS = ("action", "service", "service_template")
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>|~#])")


def _is_template(value: str) -> bool:
    """Return True when a string is a Jinja template, whose result cannot be judged statically."""
    return "{{" in value or "{%" in value


def _normalize(name: str) -> str:
    """Normalize a service name the way core does before it looks a service up."""
    return name.strip().lower()


def is_denied(name: str) -> bool:
    """
    Return True when a static service name is on the fixed denylist (D-03).

    The name is normalized with strip and lower. A templated name is never denied here: it cannot be judged statically,
    it is reported by the walker and checked again at execution time on the resolved name (D-04, D-05).
    """
    if _is_template(name):
        return False
    normalized = _normalize(name)
    domain, dot, _service = normalized.partition(".")
    return bool(dot) and (domain in DENIED_DOMAINS or normalized in DENIED_SERVICES)


@dataclass(frozen=True, slots=True)
class ActionAnalysis:
    """
    What a static walk over an action tree found, each in first-seen order without duplicates.

    `denied` are normalized static service names on the denylist. `templated` are the service-name templates as written.
    `residual` are step types the denylist cannot judge and the approval view flags: "scene", "event" and "device"
    for those steps, and the normalized service name of a static call into the script domain or a service of
    RESIDUAL_SERVICES (automation.trigger, button.press, homeassistant.turn_on and so on).
    """

    denied: tuple[str, ...] = ()
    templated: tuple[str, ...] = ()
    residual: tuple[str, ...] = ()


def _add(found: list[str], value: str) -> None:
    if value not in found:
        found.append(value)


def _note_markers(node: dict[str, Any], residual: list[str]) -> None:
    """Record the step types of a dict that the denylist cannot judge: scene, event and device steps."""
    for marker in ("scene", "event"):
        if marker in node:
            _add(residual, marker)
    if all(key in node for key in (CONF_DEVICE_ID, "domain", "type")):
        _add(residual, "device")


def _note_service(value: str, denied: list[str], templated: list[str], residual: list[str]) -> None:
    """Sort the value of an action, service or service_template key into denied, templated and residual."""
    if _is_template(value):
        _add(templated, value)
        return
    normalized = _normalize(value)
    if is_denied(normalized):
        _add(denied, normalized)
    elif normalized.startswith("script.") or normalized in RESIDUAL_SERVICES:
        _add(residual, normalized)


def _walk(node: Any, depth: int, denied: list[str], templated: list[str], residual: list[str]) -> None:
    """Walk one node; `depth` counts the container levels above it, so it matches actions_depth."""
    if depth >= MAX_ACTION_DEPTH and isinstance(node, list | dict):
        raise _reject(RejectReason.TOO_DEEP)
    if isinstance(node, list):
        for item in node:
            _walk(item, depth + 1, denied, templated, residual)
    elif isinstance(node, dict):
        _note_markers(node, residual)
        for key, value in node.items():
            if key in _SERVICE_KEYS and isinstance(value, str):
                _note_service(value, denied, templated, residual)
            else:
                _walk(value, depth + 1, denied, templated, residual)


def analyze_actions(actions: Any) -> ActionAnalysis:
    """
    Walk a raw action tree and report denied, templated and residual-risk entries (D-04).

    The walk is deliberately conservative: it reads the keys `action`, `service` and `service_template` and the step
    markers anywhere in the tree, so it may also flag a payload key of a notification that happens to share the name.
    A tree deeper than MAX_ACTION_DEPTH raises DocumentRejectedError with the reason `too_deep`.
    """
    denied: list[str] = []
    templated: list[str] = []
    residual: list[str] = []
    _walk(actions, 0, denied, templated, residual)
    return ActionAnalysis(tuple(denied), tuple(templated), tuple(residual))


def analyze_spec(spec: DeviceSpec) -> ActionAnalysis:
    """Return the merged analysis of the actions of every trigger of a device."""
    merged: tuple[list[str], list[str], list[str]] = ([], [], [])
    for trigger in spec.triggers.values():
        analysis = analyze_actions(trigger.actions)
        for found, values in zip(merged, (analysis.denied, analysis.templated, analysis.residual), strict=True):
            for value in values:
                _add(found, value)
    return ActionAnalysis(tuple(merged[0]), tuple(merged[1]), tuple(merged[2]))


def spec_has_actions(spec: DeviceSpec) -> bool:
    """Return True when any trigger of the device has actions; a device without any needs no approval."""
    return any(trigger.actions for trigger in spec.triggers.values())


def approval_sections(spec: DeviceSpec) -> list[tuple[str, list[dict[str, Any]]]]:
    """
    Return the (label, actions) pairs the approval view shows: triggers with actions only, in trigger order.

    A Switch is labelled onChangeToOn and onChangeToOff like the dialog fields, a Select option
    "<friendly name> (<state value>)".
    """
    label: Callable[[Any], str] = (
        (lambda trigger: f"{trigger.friendly_name} ({trigger.value})")
        if spec.kind == SUBENTRY_SELECT
        else (lambda trigger: trigger.label)
    )
    return [(label(trigger), trigger.actions) for trigger in spec.triggers.values() if trigger.actions]


def escape_markdown(text: str) -> str:
    """
    Return text with every markdown control character escaped by a backslash.

    Names and owner names come from the broker, so they are escaped wherever they reach an issue or a flow text; the
    escaped characters are backslash, backtick, asterisk, underscore, square and angle brackets, pipe, tilde and number
    sign (T-03-05).
    """
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)
