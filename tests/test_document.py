"""The central config document: contract, canonical hashes and strict parsing (D-06, D-12, D-13, D-14)."""

import copy
import hashlib
import json
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.mqtt_actions.actions import ActionsInvalid, validate_actions_structure
from custom_components.mqtt_actions.const import (
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
    MAX_TEXT_LENGTH,
    SCHEMA_VERSION,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.document import (
    NATIVE_KEY,
    NATIVE_VALUE,
    DocumentRejectedError,
    ParsedDocument,
    SchemaTooNewError,
    actions_hash,
    analyze_actions,
    analyze_spec,
    approval_sections,
    build_content,
    build_document,
    canonical_json,
    content_hash,
    escape_markdown,
    is_denied,
    migrate,
    parse_document,
    serialize_document,
    spec_has_actions,
)
from custom_components.mqtt_actions.model import DeviceSpec, spec_from_data

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

LIGHT_ON = [{"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}]
LIGHT_OFF = [{"action": "light.turn_off", "target": {"entity_id": "light.kitchen"}}]


def _switch(
    name: str = "Lamp",
    *,
    on: list[dict[str, Any]] | None = None,
    off: list[dict[str, Any]] | None = None,
    device_id: str = "dev-1",
    **extra: Any,
) -> DeviceSpec:
    data: dict[str, Any] = {
        CONF_DEVICE_ID: device_id,
        CONF_ON_CHANGE_TO_ON: LIGHT_ON if on is None else on,
        CONF_ON_CHANGE_TO_OFF: [] if off is None else off,
        CONF_RUN_ON_STARTUP: False,
        **extra,
    }
    return spec_from_data(SUBENTRY_SWITCH, name, data)


def _select(
    name: str = "Mode",
    options: list[tuple[str, str, list[dict[str, Any]]]] | None = None,
    **extra: Any,
) -> DeviceSpec:
    chosen = options or [("eco", "Eco", LIGHT_ON), ("boost", "Boost", LIGHT_OFF), ("off", "Off", [])]
    data: dict[str, Any] = {
        CONF_DEVICE_ID: "dev-2",
        CONF_OPTIONS: [
            {CONF_STATE_VALUE: value, CONF_FRIENDLY_NAME: friendly, CONF_ACTIONS: actions}
            for value, friendly, actions in chosen
        ],
        CONF_RUN_ON_STARTUP: False,
        **extra,
    }
    return spec_from_data(SUBENTRY_SELECT, name, data)


def _document(spec: DeviceSpec, **overrides: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {"owner": "inst", "owner_name": "Main", "rev": 3}
    arguments.update(overrides)
    return build_document(spec, **arguments)


# --- contract -----------------------------------------------------------------------------------------------------


def test_switch_document_has_contract_keys() -> None:
    """D-12, D-13: a Switch document carries identity, bookkeeping and every shared setting, and nothing else."""
    document = _document(_switch())
    assert set(document) == {
        "schema_version",
        "device_id",
        "owner",
        "owner_name",
        "rev",
        "hash",
        "kind",
        "name",
        "run_on_startup",
        "run_mode",
        "breaker_max_runs",
        "breaker_window",
        "on_change_to_on",
        "on_change_to_off",
    }
    assert document["schema_version"] == 1
    assert document["kind"] == "switch"
    assert document["device_id"] == "dev-1"
    assert document["owner"] == "inst"
    assert document["owner_name"] == "Main"
    assert document["rev"] == 3


def test_select_document_options_in_order() -> None:
    """A Select document lists its options in creation order and carries no Switch keys."""
    document = _document(_select())
    assert document["kind"] == "select"
    assert document["options"] == [
        {"state_value": "eco", "friendly_name": "Eco", "actions": LIGHT_ON},
        {"state_value": "boost", "friendly_name": "Boost", "actions": LIGHT_OFF},
        {"state_value": "off", "friendly_name": "Off", "actions": []},
    ]
    assert "on_change_to_on" not in document
    assert "on_change_to_off" not in document


WIRE_CONTENT_HASH = "b070c2007c34d6fcad5cac004a6221ea67e1bf12bcea6da10ab91f0e89e519cc"
WIRE_DOCUMENT = (
    '{"breaker_max_runs":5,"breaker_window":10,"device_id":"dev-1",'
    f'"hash":"{WIRE_CONTENT_HASH}",'
    '"kind":"switch","name":"Küche","on_change_to_off":[],'
    '"on_change_to_on":[{"action":"light.turn_on","target":{"entity_id":"light.kitchen"}}],'
    '"owner":"inst","owner_name":"Main","rev":3,"run_mode":"serial","run_on_startup":false,"schema_version":1}'
)


def test_wire_fixture_switch() -> None:
    """The wire format is pinned: any change of key, separator, escaping or hash algorithm fails here."""
    document = _document(_switch("Küche"))
    assert serialize_document(document) == WIRE_DOCUMENT
    assert document["hash"] == WIRE_CONTENT_HASH


def test_canonical_hash_is_sha256_of_compact_sorted_json() -> None:
    """The content hash is sha256 over compact, sorted, unescaped JSON, independent of input key order."""
    content = build_content(_switch("Küche"))
    expected = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    assert content_hash(content) == expected
    assert content_hash(dict(reversed(list(content.items())))) == expected
    assert canonical_json({"b": 1, "a": "ü"}) == '{"a":"ü","b":1}'


def test_hash_is_independent_of_storage_shape() -> None:
    """A device stored before Phase 2 hashes like one with the defaults written out (D-13)."""
    phase_one = _switch()
    explicit = _switch(
        **{CONF_RUN_MODE: "serial", CONF_BREAKER_MAX_RUNS: 5, CONF_BREAKER_WINDOW: 10},
    )
    assert content_hash(build_content(phase_one)) == content_hash(build_content(explicit))


def test_hash_excludes_identity_and_bookkeeping() -> None:
    """Owner, owner name, rev and device id are not content; name, run mode and breaker limits are."""
    base = _switch()
    base_hash = _document(base)["hash"]
    assert _document(base, owner="other")["hash"] == base_hash
    assert _document(base, owner_name="Other")["hash"] == base_hash
    assert _document(base, rev=99)["hash"] == base_hash
    assert _document(_switch(device_id="dev-9"))["hash"] == base_hash
    assert _document(_switch("Renamed"))["hash"] != base_hash
    assert _document(_switch(**{CONF_RUN_MODE: "restart"}))["hash"] != base_hash
    assert _document(_switch(**{CONF_BREAKER_MAX_RUNS: 6}))["hash"] != base_hash
    assert _document(_switch(**{CONF_BREAKER_WINDOW: 11}))["hash"] != base_hash


def test_actions_hash_binds_mapping_startup_run_mode_and_breaker() -> None:
    """The approval hash follows mapping, startup flag, run mode and both breaker limits, never a rename (D-16)."""
    base = _switch(on=LIGHT_ON, off=LIGHT_OFF)
    base_hash = actions_hash(base)
    assert actions_hash(_switch("Renamed", on=LIGHT_ON, off=LIGHT_OFF)) == base_hash
    assert actions_hash(_switch(on=LIGHT_ON, off=LIGHT_OFF, **{CONF_RUN_MODE: "restart"})) != base_hash
    assert actions_hash(_switch(on=LIGHT_ON, off=LIGHT_OFF, **{CONF_BREAKER_MAX_RUNS: 9})) != base_hash
    assert actions_hash(_switch(on=LIGHT_ON, off=LIGHT_OFF, **{CONF_BREAKER_WINDOW: 11})) != base_hash
    assert actions_hash(_switch(on=[{"action": "light.toggle"}], off=LIGHT_OFF)) != base_hash
    assert actions_hash(_switch(on=LIGHT_OFF, off=LIGHT_ON)) != base_hash
    assert actions_hash(_switch(on=LIGHT_ON, off=LIGHT_OFF, **{CONF_RUN_ON_STARTUP: True})) != base_hash
    reordered = [("off", "Off", []), ("boost", "Boost", LIGHT_OFF), ("eco", "Eco", LIGHT_ON)]
    assert actions_hash(_select()) == actions_hash(_select(options=reordered))


def test_serialization_is_deterministic() -> None:
    """Two serializations are identical and the text round-trips through json."""
    document = _document(_select())
    first = serialize_document(document)
    assert serialize_document(document) == first
    assert json.loads(first) == document


# --- strict parsing (D-06, D-14) ----------------------------------------------------------------------------------


def _wire(spec: DeviceSpec, **overrides: Any) -> str:
    return serialize_document(_document(spec, **overrides))


def test_parse_roundtrip_switch_and_select() -> None:
    """A published document parses back to an equal spec with recomputed hashes and the bookkeeping kept."""
    for spec in (_switch("Küche", off=LIGHT_OFF), _select()):
        payload = _wire(spec)
        parsed = parse_document(spec.device_id, payload)
        assert isinstance(parsed, ParsedDocument)
        assert parsed.spec == spec
        assert parsed.content == build_content(spec)
        assert parsed.content_hash == content_hash(build_content(spec))
        assert parsed.actions_hash == actions_hash(spec)
        assert (parsed.owner, parsed.owner_name, parsed.rev, parsed.schema_version) == ("inst", "Main", 3, 1)
        assert parsed.device_id == spec.device_id
        assert parsed.payload == payload


def test_parse_never_trusts_the_wire_hash() -> None:
    """T-03-01: a forged hash field changes nothing; both hashes come from the received content."""
    spec = _switch()
    document = _document(spec)
    document["hash"] = "f" * 64
    parsed = parse_document("dev-1", serialize_document(document))
    assert parsed.content_hash == content_hash(build_content(spec))
    assert parsed.content_hash != document["hash"]
    assert parsed.actions_hash == actions_hash(spec)


def test_unknown_extra_keys_are_ignored_and_not_hashed() -> None:
    """Extra top-level keys neither fail the parse nor change either hash."""
    spec = _switch()
    plain = parse_document("dev-1", _wire(spec))
    document = _document(spec)
    document["future_field"] = {"anything": [1, 2, 3]}
    parsed = parse_document("dev-1", serialize_document(document))
    assert parsed.content_hash == plain.content_hash
    assert parsed.actions_hash == plain.actions_hash
    assert parsed.spec == plain.spec


def _nested(depth: int) -> list[Any]:
    """Return an action-like structure with exactly `depth` container levels."""
    if depth == 1:
        return []
    if depth == 2:
        return [{}]
    return [{"a": _nested(depth - 2)}]


def _switch_doc(**overrides: Any) -> dict[str, Any]:
    document = _document(_switch(off=LIGHT_OFF))
    document.update(overrides)
    return document


def _select_doc(**overrides: Any) -> dict[str, Any]:
    document = _document(_select())
    document.update(overrides)
    return document


def _with_option(index: int, **changes: Any) -> dict[str, Any]:
    document = _select_doc()
    document["options"] = copy.deepcopy(document["options"])
    document["options"][index].update(changes)
    return document


def _without_key(document: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in document.items() if name != key}


def _option(value: str, friendly: str = "F", actions: Any = None) -> dict[str, Any]:
    return {"state_value": value, "friendly_name": friendly, "actions": [] if actions is None else actions}


BAD_TEXTS = ["", "line\nbreak", "tab\there", "bidi\u202eevil", "x" * (MAX_TEXT_LENGTH + 1)]

REJECTED: list[tuple[str, Callable[[], str]]] = [
    ("not_json", lambda: "{not json"),
    ("not_json", lambda: ""),
    ("not_object", lambda: "[]"),
    ("not_object", lambda: '"text"'),
    ("not_object", lambda: "12"),
    ("not_object", lambda: "null"),
    (
        "too_large",
        lambda: json.dumps({"x": "ü" * (MAX_DOCUMENT_BYTES // 2 + 1)}, ensure_ascii=False),
    ),
    ("bad_schema_version", lambda: json.dumps(_without_key(_switch_doc(), "schema_version"))),
    ("bad_schema_version", lambda: json.dumps(_switch_doc(schema_version="1"))),
    ("bad_schema_version", lambda: json.dumps(_switch_doc(schema_version=True))),
    ("bad_schema_version", lambda: json.dumps(_switch_doc(schema_version=0))),
    ("bad_schema_version", lambda: json.dumps(_switch_doc(schema_version=-1))),
    ("device_id_mismatch", lambda: json.dumps(_without_key(_switch_doc(), "device_id"))),
    ("device_id_mismatch", lambda: json.dumps(_switch_doc(device_id="other"))),
    *[("bad_owner", lambda value=value: json.dumps(_switch_doc(owner=value))) for value in [*BAD_TEXTS, 5, None]],
    ("bad_owner", lambda: json.dumps(_without_key(_switch_doc(), "owner"))),
    *[
        ("bad_owner_name", lambda value=value: json.dumps(_switch_doc(owner_name=value)))
        for value in [*BAD_TEXTS, 5, None]
    ],
    ("bad_owner_name", lambda: json.dumps(_without_key(_switch_doc(), "owner_name"))),
    ("bad_rev", lambda: json.dumps(_switch_doc(rev=-1))),
    ("bad_rev", lambda: json.dumps(_switch_doc(rev=True))),
    ("bad_rev", lambda: json.dumps(_switch_doc(rev="1"))),
    ("bad_rev", lambda: json.dumps(_switch_doc(rev=1.5))),
    ("bad_rev", lambda: json.dumps(_without_key(_switch_doc(), "rev"))),
    ("bad_kind", lambda: json.dumps(_switch_doc(kind="light"))),
    ("bad_kind", lambda: json.dumps(_switch_doc(kind=5))),
    ("bad_kind", lambda: json.dumps(_switch_doc(kind=[]))),
    ("bad_kind", lambda: json.dumps(_switch_doc(kind={}))),
    ("bad_kind", lambda: json.dumps(_without_key(_switch_doc(), "kind"))),
    *[("bad_name", lambda value=value: json.dumps(_switch_doc(name=value))) for value in [*BAD_TEXTS, 5, None, "   "]],
    ("bad_name", lambda: json.dumps(_without_key(_switch_doc(), "name"))),
    ("bad_run_mode", lambda: json.dumps(_switch_doc(run_mode="parallel"))),
    ("bad_run_mode", lambda: json.dumps(_switch_doc(run_mode=1))),
    ("bad_run_mode", lambda: json.dumps(_switch_doc(run_mode={}))),
    ("bad_run_mode", lambda: json.dumps(_switch_doc(run_mode=[]))),
    ("bad_run_mode", lambda: json.dumps(_without_key(_switch_doc(), "run_mode"))),
    ("bad_breaker", lambda: json.dumps(_switch_doc(breaker_max_runs=0))),
    ("bad_breaker", lambda: json.dumps(_switch_doc(breaker_max_runs=101))),
    ("bad_breaker", lambda: json.dumps(_switch_doc(breaker_window=3601))),
    ("bad_breaker", lambda: json.dumps(_switch_doc(breaker_window=0))),
    ("bad_breaker", lambda: json.dumps(_switch_doc(breaker_max_runs=2.5))),
    ("bad_breaker", lambda: json.dumps(_switch_doc(breaker_window="10"))),
    ("bad_breaker", lambda: json.dumps(_switch_doc(breaker_max_runs=True))),
    ("bad_breaker", lambda: json.dumps(_without_key(_switch_doc(), "breaker_window"))),
    ("bad_run_on_startup", lambda: json.dumps(_switch_doc(run_on_startup="yes"))),
    ("bad_run_on_startup", lambda: json.dumps(_switch_doc(run_on_startup=1))),
    ("bad_run_on_startup", lambda: json.dumps(_without_key(_switch_doc(), "run_on_startup"))),
    ("bad_actions", lambda: json.dumps(_switch_doc(on_change_to_on="not a list"))),
    ("bad_actions", lambda: json.dumps(_switch_doc(on_change_to_off=[1, 2]))),
    ("bad_actions", lambda: json.dumps(_switch_doc(on_change_to_on=[[{"action": "a.b"}]]))),
    ("bad_actions", lambda: json.dumps(_without_key(_switch_doc(), "on_change_to_on"))),
    ("bad_actions", lambda: json.dumps(_with_option(0, actions={"action": "a.b"}))),
    ("bad_actions", lambda: json.dumps(_with_option(1, actions=["x"]))),
    ("bad_options", lambda: json.dumps(_select_doc(options=[_option("a")]))),
    ("bad_options", lambda: json.dumps(_select_doc(options=[_option(f"v{i}") for i in range(MAX_OPTIONS + 1)]))),
    ("bad_options", lambda: json.dumps(_select_doc(options="a,b"))),
    ("bad_options", lambda: json.dumps(_select_doc(options=[_option("a"), "b"]))),
    ("bad_options", lambda: json.dumps(_select_doc(options=[_option("a"), {"state_value": "b", "actions": []}]))),
    ("bad_actions", lambda: json.dumps(_select_doc(options=[_option("a"), {**_option("b"), "actions": 1}]))),
    ("bad_options", lambda: json.dumps(_select_doc(options=[_option("a"), {**_option("b"), "friendly_name": 5}]))),
    ("bad_options", lambda: json.dumps(_select_doc(options=[_option("a"), {**_option("b"), "state_value": None}]))),
    ("bad_options", lambda: json.dumps(_without_key(_select_doc(), "options"))),
    ("bad_option_value", lambda: json.dumps(_with_option(0, state_value=""))),
    ("bad_option_value", lambda: json.dumps(_with_option(0, state_value=" eco"))),
    ("bad_option_value", lambda: json.dumps(_with_option(0, state_value="eco "))),
    ("bad_option_value", lambda: json.dumps(_with_option(0, state_value="a\nb"))),
    ("bad_option_value", lambda: json.dumps(_with_option(0, state_value="x" * (MAX_TEXT_LENGTH + 1)))),
    ("bad_friendly_name", lambda: json.dumps(_with_option(0, friendly_name=""))),
    ("bad_friendly_name", lambda: json.dumps(_with_option(0, friendly_name="a\tb"))),
    ("bad_friendly_name", lambda: json.dumps(_with_option(0, friendly_name="x" * (MAX_TEXT_LENGTH + 1)))),
    ("duplicate_state_value", lambda: json.dumps(_with_option(1, state_value="ECO"))),
    ("too_deep", lambda: json.dumps(_switch_doc(on_change_to_on=_nested(MAX_ACTION_DEPTH + 1)))),
    ("too_deep", lambda: json.dumps(_with_option(2, actions=_nested(MAX_ACTION_DEPTH + 1)))),
    ("too_deep", lambda: json.dumps(_switch_doc(on_change_to_on=_nested(400)))),
]


@pytest.mark.parametrize(("reason", "make_payload"), REJECTED)
def test_parse_rejects_invalid_documents(reason: str, make_payload: Callable[[], str]) -> None:
    """Every hostile or malformed document is a typed rejection; no message carries payload or action content."""
    payload = make_payload()
    with pytest.raises(DocumentRejectedError) as error:
        parse_document("dev-1" if "dev-2" not in payload else "dev-2", payload)
    assert error.value.reason == reason
    assert "light.kitchen" not in str(error.value)
    assert len(str(error.value)) < 200


def test_lone_surrogate_never_becomes_a_spec() -> None:
    """Text that cannot be encoded is rejected; the JSON parser already refuses it, so no spec is ever built."""
    payload = json.dumps(_with_option(0, state_value="lone\ud800"))
    with pytest.raises(DocumentRejectedError):
        parse_document("dev-2", payload)


def test_depth_limit_is_inclusive() -> None:
    """A structure with exactly MAX_ACTION_DEPTH container levels is accepted, one more is not."""
    at_limit = _switch_doc(on_change_to_on=_nested(MAX_ACTION_DEPTH))
    assert parse_document("dev-1", json.dumps(at_limit)).spec.triggers
    with pytest.raises(DocumentRejectedError):
        parse_document("dev-1", json.dumps(_switch_doc(on_change_to_on=_nested(MAX_ACTION_DEPTH + 1))))


def test_schema_too_new_is_its_own_error_and_comes_first() -> None:
    """D-14: a higher schema_version is reported as such before any other field is read."""
    document = {"schema_version": SCHEMA_VERSION + 1, "device_id": 5, "owner": None, "kind": "hologram"}
    with pytest.raises(SchemaTooNewError) as error:
        parse_document("dev-1", json.dumps(document))
    assert isinstance(error.value, DocumentRejectedError)
    assert error.value.version == SCHEMA_VERSION + 1
    assert error.value.reason == "schema_too_new"


def test_migrate_seam_is_identity_at_current_version() -> None:
    """migrate is the place a reader of an older schema_version converts; at the current version it changes nothing."""
    document = _switch_doc()
    assert migrate(document) == document


def test_parse_applies_migrate_before_field_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A migration can repair a document before the fields are validated."""
    from custom_components.mqtt_actions import document as document_module

    broken = _switch_doc(kind="legacy-switch")
    monkeypatch.setattr(document_module, "migrate", lambda document: {**document, "kind": "switch"})
    assert parse_document("dev-1", json.dumps(broken)).spec.kind == "switch"


# --- denylist (D-03, D-04) ----------------------------------------------------------------------------------------


def test_denylist_constants_shape() -> None:
    """D-03: the denylist is a fixed pair of frozensets of lower-case names."""
    assert isinstance(DENIED_DOMAINS, frozenset)
    assert isinstance(DENIED_SERVICES, frozenset)
    assert {"shell_command", "python_script", "rest_command", "command_line", "hassio", "backup"} == DENIED_DOMAINS
    assert {
        "homeassistant.restart",
        "homeassistant.stop",
        "homeassistant.reload_all",
        "homeassistant.reload_core_config",
        "homeassistant.reload_config_entry",
        "homeassistant.set_location",
        "homeassistant.save_persistent_states",
        "mqtt.publish",
        "mqtt.dump",
        "recorder.purge",
        "recorder.purge_entities",
        "recorder.disable",
        "update.install",
        "downloader.download_file",
        "logger.set_level",
        "logger.set_default_level",
        "system_log.clear",
    } == DENIED_SERVICES
    assert all(name == name.lower() and "." not in name for name in DENIED_DOMAINS)
    assert all(name == name.lower() and name.count(".") == 1 for name in DENIED_SERVICES)


@pytest.mark.parametrize(
    "name",
    [
        "shell_command.anything",
        "hassio.host_reboot",
        "backup.create",
        "mqtt.publish",
        "homeassistant.restart",
        "recorder.purge",
        "update.install",
        "downloader.download_file",
        "recorder.disable",
        "logger.set_level",
        "  Update.Install ",
        "SHELL_COMMAND.run",
        "  Hassio.host_reboot  ",
        "\tMQTT.Publish\n",
    ],
)
def test_is_denied_true(name: str) -> None:
    assert is_denied(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "notify.notify",
        "script.turn_on",
        "automation.trigger",
        "light.turn_on",
        "homeassistant.turn_on",
        "mqtt.other",
        "",
        "shell_command",
        "hassio",
        "{{ 'shell_command.run' }}",
        "{% if x %}shell_command.run{% endif %}",
    ],
)
def test_is_denied_false(name: str) -> None:
    assert is_denied(name) is False


def _deep(service_key: str = "action", name: str = "shell_command.run") -> list[dict[str, Any]]:
    """A denied service three levels deep: choose > default > repeat > sequence."""
    return [
        {
            "choose": [
                {
                    "conditions": [],
                    "sequence": [{"repeat": {"count": 2, "sequence": [{service_key: name}]}}],
                }
            ],
            "default": [],
        }
    ]


def test_walker_finds_services_recursively() -> None:
    """The walker reads action, service and service_template through every container of the script language."""
    assert analyze_actions(_deep()).denied == ("shell_command.run",)
    assert analyze_actions(_deep("service")).denied == ("shell_command.run",)
    assert analyze_actions(_deep("service_template", "{{ 'x' }}")).templated == ("{{ 'x' }}",)
    containers = [
        [{"choose": [{"conditions": [], "sequence": [{"action": "mqtt.publish"}]}]}],
        [{"choose": [], "default": [{"action": "mqtt.publish"}]}],
        [{"if": [], "then": [{"action": "mqtt.publish"}], "else": [{"action": "hassio.host_reboot"}]}],
        [{"repeat": {"while": [], "sequence": [{"action": "mqtt.publish"}]}}],
        [{"sequence": [{"sequence": [{"action": "mqtt.publish"}]}]}],
        [{"parallel": [{"action": "light.turn_on"}, {"sequence": [{"action": "mqtt.publish"}]}]}],
    ]
    for actions in containers:
        assert "mqtt.publish" in analyze_actions(actions).denied, actions


def test_walker_separates_denied_and_templated() -> None:
    """Static denied names are normalized and reported; templates are reported apart and never denied."""
    analysis = analyze_actions(
        [
            {"action": "  Shell_Command.Run "},
            {"action": "light.turn_on"},
            {"action": "{{ states('input_text.svc') }}"},
            {"service": "{% if true %}a.b{% endif %}"},
            {"action": "shell_command.run"},
            {"action": "hassio.host_reboot"},
            {"action": "{{ states('input_text.svc') }}"},
        ]
    )
    assert analysis.denied == ("shell_command.run", "hassio.host_reboot")
    assert analysis.templated == ("{{ states('input_text.svc') }}", "{% if true %}a.b{% endif %}")
    assert "light.turn_on" not in analysis.denied + analysis.templated


def test_walker_flags_residual_step_types() -> None:
    """Scene, event and device steps and calls to scripts or automations are flagged, never denied (A14)."""
    analysis = analyze_actions(
        [
            {"scene": "scene.movie"},
            {"event": "my_event"},
            {"device_id": "abc", "domain": "light", "type": "turn_on", "entity_id": "light.x"},
            {"action": "script.turn_on", "target": {"entity_id": "script.x"}},
            {"action": "script.my_script"},
            {"action": "automation.trigger"},
            {"action": "button.press", "target": {"entity_id": "button.restart"}},
            {"action": "homeassistant.turn_on", "target": {"entity_id": "script.x"}},
            {"action": "homeassistant.toggle", "target": {"entity_id": "scene.x"}},
            {"action": "light.turn_on"},
        ]
    )
    assert set(analysis.residual) == {
        "scene",
        "event",
        "device",
        "script.turn_on",
        "script.my_script",
        "automation.trigger",
        "button.press",
        "homeassistant.turn_on",
        "homeassistant.toggle",
    }
    assert analysis.denied == ()
    assert "light.turn_on" not in analysis.residual


def test_walker_depth_guard() -> None:
    """A structure deeper than MAX_ACTION_DEPTH is refused by the walker instead of recursing."""
    with pytest.raises(DocumentRejectedError) as error:
        analyze_actions(_nested(MAX_ACTION_DEPTH + 5))
    assert error.value.reason == "too_deep"
    with pytest.raises(DocumentRejectedError):
        analyze_actions(_nested(MAX_ACTION_DEPTH + 1))
    assert analyze_actions(_nested(MAX_ACTION_DEPTH)).denied == ()


def test_analyze_spec_covers_every_trigger() -> None:
    """The analysis of a device merges all its triggers; a device without actions has none."""
    select = _select(
        options=[
            ("a", "A", [{"action": "shell_command.run"}]),
            ("b", "B", [{"action": "{{ x }}"}]),
            ("c", "C", [{"action": "mqtt.publish"}]),
        ]
    )
    analysis = analyze_spec(select)
    assert analysis.denied == ("shell_command.run", "mqtt.publish")
    assert analysis.templated == ("{{ x }}",)
    switch = _switch(on=[{"action": "hassio.host_reboot"}], off=[{"action": "backup.create"}])
    assert analyze_spec(switch).denied == ("hassio.host_reboot", "backup.create")
    assert spec_has_actions(switch) is True
    assert spec_has_actions(_switch(on=[], off=[])) is False
    assert spec_has_actions(_select(options=[("a", "A", []), ("b", "B", [])])) is False
    assert spec_has_actions(_select()) is True


def test_approval_sections_label_and_omit_empty() -> None:
    """Sections exist for triggers with actions only, labelled like the dialog fields, in trigger order."""
    switch = _switch(on=LIGHT_ON, off=[])
    assert approval_sections(switch) == [("onChangeToOn", LIGHT_ON)]
    both = _switch(on=LIGHT_ON, off=LIGHT_OFF)
    assert approval_sections(both) == [("onChangeToOn", LIGHT_ON), ("onChangeToOff", LIGHT_OFF)]
    assert approval_sections(_select()) == [("Eco (eco)", LIGHT_ON), ("Boost (boost)", LIGHT_OFF)]


def test_escape_markdown_neutralizes_links_and_fences() -> None:
    """No markup character survives unescaped; plain text is unchanged."""
    special = set("\\`*_[]<>|~#")
    hostile = ["[x](http://evil)", "```\nfence```", "<b>bold</b> *a* _b_ | c ~d~ # e", "back\\slash", "a`b"]
    for text in hostile:
        escaped = escape_markdown(text)
        index = 0
        while index < len(escaped):
            if escaped[index] == "\\":
                index += 2
                continue
            assert escaped[index] not in special, (text, escaped)
            index += 1
    assert escape_markdown("Plain text 123") == "Plain text 123"
    assert escape_markdown("[x]") == "\\[x\\]"


# --- structure validation (D-06) ----------------------------------------------------------------------------------


def test_validate_actions_structure(hass: HomeAssistant) -> None:
    """Only the schema is applied: valid sequences pass without any registered service, invalid ones raise."""
    assert validate_actions_structure([{"action": "nothing.registered", "data": {"a": 1}}]) is None
    assert validate_actions_structure([{"action": "{{ 'a.b' }}"}]) is None
    assert validate_actions_structure([]) is None
    for invalid in (
        [{"action": "x.y", "bogus": 1}],
        [{"not_a_step": 1}],
        "hello",
        [5],
        [{"action": "a.b", "target": "x"}],
    ):
        with pytest.raises(ActionsInvalid):
            validate_actions_structure(invalid)


# --- transfer marker of an adopted device (D-09, T-04-49, T-04-52) ------------------------------------------------


def test_transferred_from_roundtrip() -> None:
    """The marker is a list of previous owners, newest last, and parses back to the same tuple."""
    spec = _switch()
    document = _document(spec, transferred_from=["inst-a", "inst-b"])
    assert document["transferred_from"] == ["inst-a", "inst-b"]
    parsed = parse_document("dev-1", serialize_document(document))
    assert parsed.transferred_from == ("inst-a", "inst-b")


def test_transferred_from_is_bookkeeping_and_not_hashed() -> None:
    """D-09: the marker changes neither hash and not the schema version, and a document without it is unchanged."""
    spec = _switch(on=LIGHT_ON, off=LIGHT_OFF)
    plain = _document(spec)
    marked = _document(spec, transferred_from=["inst-a"])
    assert marked["hash"] == plain["hash"]
    assert marked["schema_version"] == plain["schema_version"] == SCHEMA_VERSION == 1
    plain_parsed = parse_document("dev-1", serialize_document(plain))
    marked_parsed = parse_document("dev-1", serialize_document(marked))
    assert marked_parsed.content_hash == plain_parsed.content_hash
    assert marked_parsed.actions_hash == plain_parsed.actions_hash
    # No marker, no key: the text is the one a Phase 3 owner publishes, and an empty marker is never written
    assert "transferred_from" not in serialize_document(plain)
    assert "transferred_from" not in serialize_document(_document(spec, transferred_from=()))
    assert plain_parsed.transferred_from == ()


def test_absent_and_null_marker_mean_no_transfer() -> None:
    """A document of an older owner has no marker, and a null marker is the same."""
    document = _document(_switch())
    assert parse_document("dev-1", serialize_document(document)).transferred_from == ()
    document["transferred_from"] = None
    assert parse_document("dev-1", serialize_document(document)).transferred_from == ()


@pytest.mark.parametrize(
    "marker",
    [
        "inst-a",
        {"inst-a": 1},
        ["inst-a", 7],
        ["inst-a", None],
        ["has space"],
        ["with/slash"],
        ["x" * 65],
        [f"inst-{number}" for number in range(9)],
        ["inst-a", ""],
    ],
    ids=["string", "dict", "non-string", "null-entry", "space", "slash", "too-long-id", "nine-entries", "empty-entry"],
)
def test_transferred_from_rejects_malformed_markers(marker: Any) -> None:
    """T-04-52: a malformed marker rejects the whole document with a fixed reason and no content."""
    document = _document(_switch())
    document["transferred_from"] = marker
    with pytest.raises(DocumentRejectedError) as error:
        parse_document("dev-1", serialize_document(document))
    assert error.value.reason == "bad_transfer"
    assert len(str(error.value)) < 200


def test_transferred_from_accepts_the_maximum_length() -> None:
    """Eight entries are the limit and still parse."""
    marker = [f"inst-{number}" for number in range(8)]
    document = _document(_switch(), transferred_from=marker)
    assert parse_document("dev-1", serialize_document(document)).transferred_from == tuple(marker)


# --- native marker of an owner with native entities (D-09, T-5-03) -------------------------------------------------


def test_the_marker_is_never_hashed() -> None:
    """D-09: the marker changes neither hash nor the content, and a document without it is the one built before."""
    spec = _switch(on=LIGHT_ON, off=LIGHT_OFF)
    plain = _document(spec)
    marked = _document(spec, native=True)
    assert marked[NATIVE_KEY] == NATIVE_VALUE
    assert marked["hash"] == plain["hash"]
    assert marked["schema_version"] == plain["schema_version"] == SCHEMA_VERSION == 1
    plain_parsed = parse_document("dev-1", serialize_document(plain))
    marked_parsed = parse_document("dev-1", serialize_document(marked))
    assert marked_parsed.content_hash == plain_parsed.content_hash
    assert marked_parsed.actions_hash == plain_parsed.actions_hash
    assert marked_parsed.content == plain_parsed.content
    # No marker, no key: the text is the one an owner of the previous release publishes
    assert NATIVE_KEY not in plain
    assert serialize_document(_document(spec, native=False)) == serialize_document(plain)
    assert set(plain) == {"schema_version", CONF_DEVICE_ID, "owner", "owner_name", "rev", "hash", *build_content(spec)}
    assert plain_parsed.native is False
    assert marked_parsed.native is True


@pytest.mark.parametrize("value", ["other", "NATIVE", 1, True, None, ["native"], {"native": 1}])
def test_the_marker_is_read_strictly(value: Any) -> None:
    """T-5-03: only the exact string reads as native; any other value is not native and never rejects the document."""
    document = _document(_switch())
    document[NATIVE_KEY] = value
    assert parse_document("dev-1", serialize_document(document)).native is False


def test_an_absent_marker_reads_as_not_native() -> None:
    """A document of an owner of the previous release has no marker and parses as before."""
    assert parse_document("dev-1", serialize_document(_document(_switch()))).native is False


def test_a_marker_next_to_unknown_extra_keys_parses_unchanged() -> None:
    """The property that makes a reader of the previous release ignore the marker: unknown keys never matter."""
    spec = _switch()
    plain = parse_document("dev-1", _wire(spec))
    document = _document(spec, native=True)
    document["future_field"] = {"anything": [1, 2, 3]}
    parsed = parse_document("dev-1", serialize_document(document))
    assert parsed.content_hash == plain.content_hash
    assert parsed.actions_hash == plain.actions_hash
    assert parsed.spec == plain.spec
    assert parsed.native is True
