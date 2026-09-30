"""Helpers that build foreign config documents and their wire payloads for the follower tests."""

import json
import uuid
from typing import TYPE_CHECKING, Any

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
    RUN_MODE_SERIAL,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.document import build_document, serialize_document
from custom_components.mqtt_actions.model import DeviceSpec, spec_from_data

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

FOREIGN_OWNER = "instance-foreign"
FOREIGN_OWNER_NAME = "Foreign instance"


def make_spec(
    kind: str = SUBENTRY_SWITCH,
    *,
    device_id: str | None = None,
    name: str = "Lamp",
    on: list[dict[str, Any]] | None = None,
    off: list[dict[str, Any]] | None = None,
    options: Sequence[tuple[str, str, list[dict[str, Any]]]] | None = None,
    run_on_startup: bool = False,
    run_mode: str = RUN_MODE_SERIAL,
    breaker_max_runs: int = 5,
    breaker_window: int = 10,
) -> DeviceSpec:
    """Return the spec of a device built the way the owner would build it from its subentry data."""
    data: dict[str, Any] = {
        CONF_DEVICE_ID: device_id or str(uuid.uuid4()),
        CONF_RUN_ON_STARTUP: run_on_startup,
        CONF_RUN_MODE: run_mode,
        CONF_BREAKER_MAX_RUNS: breaker_max_runs,
        CONF_BREAKER_WINDOW: breaker_window,
    }
    if kind == SUBENTRY_SELECT:
        data[CONF_OPTIONS] = [
            {CONF_STATE_VALUE: value, CONF_FRIENDLY_NAME: friendly, CONF_ACTIONS: actions}
            for value, friendly, actions in options or [("a", "A", []), ("b", "B", [])]
        ]
    else:
        data[CONF_ON_CHANGE_TO_ON] = on or []
        data[CONF_ON_CHANGE_TO_OFF] = off or []
    return spec_from_data(kind, name, data)


def document_payload(
    spec: DeviceSpec,
    *,
    owner: str = FOREIGN_OWNER,
    owner_name: str = FOREIGN_OWNER_NAME,
    rev: int = 1,
    schema_version: int | None = None,
    tamper: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """
    Return the wire text of the document an owner would publish for a spec.

    `schema_version` overrides the version, `tamper` may change, add or delete any key of the document before it is
    serialized. The hash field is not recomputed after tampering, exactly like a hostile writer's document.
    """
    document = build_document(spec, owner=owner, owner_name=owner_name, rev=rev)
    if schema_version is not None:
        document["schema_version"] = schema_version
    if tamper is not None:
        tamper(document)
    return serialize_document(document)


def raw_payload(document: dict[str, Any]) -> str:
    """Return the wire text of an arbitrary document, for payloads no owner would build."""
    return json.dumps(document)
