"""The central config document: contract, canonical hashes and strict parsing (D-06, D-12, D-13, D-14)."""

import hashlib
import json
from typing import Any

from custom_components.mqtt_actions.document import (
    actions_hash,
    build_content,
    build_document,
    canonical_json,
    content_hash,
    serialize_document,
)

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
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.model import DeviceSpec, spec_from_data

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


def test_actions_hash_binds_mapping_and_startup_flag() -> None:
    """The approval hash follows the StateValue-to-actions mapping and run_on_startup, nothing else (A5)."""
    base = _switch(on=LIGHT_ON, off=LIGHT_OFF)
    base_hash = actions_hash(base)
    assert actions_hash(_switch("Renamed", on=LIGHT_ON, off=LIGHT_OFF)) == base_hash
    assert actions_hash(_switch(on=LIGHT_ON, off=LIGHT_OFF, **{CONF_RUN_MODE: "restart"})) == base_hash
    assert actions_hash(_switch(on=LIGHT_ON, off=LIGHT_OFF, **{CONF_BREAKER_MAX_RUNS: 9})) == base_hash
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
