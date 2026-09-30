"""
The central config document: the wire contract between the owner of a device and every other instance (D-12, D-13).

Pure module, no Home Assistant import at runtime. One retained (QoS 1) JSON document per device is published at
`<base>/<TOPIC_VERSION>/devices/<device_id>/config` by its owner. It carries:

- identity and bookkeeping: `schema_version`, `device_id`, `owner` (instance id), `owner_name`, `rev` and `hash`
- the shared content (D-13): `kind`, `name`, `run_on_startup`, `run_mode`, `breaker_max_runs`, `breaker_window` and the
  actions, as `on_change_to_on` and `on_change_to_off` for a Switch or as `options` for a Select

The keys of the content are the keys of the subentry data, so a validated document is also valid subentry data.

The canonical-JSON and sha256 algorithm is part of the wire contract and changing it is a breaking protocol change:

- `canonical_json` is `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`
- `content_hash` is the sha256 hex digest of the UTF-8 canonical JSON of the content; owner, owner name, rev, hash,
  device id and schema version are not content, so moving or renaming an instance never changes what a device means
- `actions_hash` binds an approval (D-02). It is the sha256 of the canonical JSON of the kind, `run_on_startup` and the
  list of [lower-cased StateValue, actions] pairs sorted by the lower-cased StateValue. It changes when the
  state-to-actions mapping or the startup flag changes, never on a rename, a run mode change or a breaker change (A5).

Documents are built from the DeviceSpec, where defaults are applied, and never from raw subentry data: a device stored
before Phase 2 publishes the same defaults as an explicit one, so a hash always means "behaves the same".
"""

import hashlib
import json
from typing import TYPE_CHECKING, Any

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
    SCHEMA_VERSION,
    SUBENTRY_SELECT,
)
from .model import SWITCH_OFF_KEY, SWITCH_ON_KEY

if TYPE_CHECKING:
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
    """Return the hash an approval is bound to: the StateValue-to-actions mapping plus the startup flag (A5)."""
    pairs = sorted(
        ([trigger.value.lower(), trigger.actions] for trigger in spec.triggers.values()),
        key=lambda pair: pair[0],
    )
    return _sha256(canonical_json({"kind": spec.kind, CONF_RUN_ON_STARTUP: spec.run_on_startup, "triggers": pairs}))


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
