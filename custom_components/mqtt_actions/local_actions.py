"""
Pure model of local actions on mirrors: records, identity and the effective plan of one trigger (D-01 to D-05).

No Home Assistant imports. The owner `DeviceSpec` stays the only shared representation (hash, document, adoption); an
`EffectiveTriggerPlan` is the local runtime decision for one trigger, built from copies, and never flows back.
"""

import copy
import dataclasses
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from .const import (
    DEFAULT_BREAKER_MAX_RUNS,
    DEFAULT_BREAKER_WINDOW,
    RUN_MODE_SERIAL,
    SERIAL_QUEUE_LIMIT,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .model import DeviceSpec, TriggerSpec

# The approval word of trust.ApprovalState that makes owner actions eligible; quoted to keep this module HA-free
APPROVED = "approved"
# The device kinds a record can name; a record of the other kind never attaches (D-10, D-12)
LOCAL_KINDS = frozenset({SUBENTRY_SWITCH, SUBENTRY_SELECT})
# The keys of one stored record (Store payload v1, the shape Plan 11-01 seeded)
RECORD_KEYS = ("device_id", "kind", "state_value", "label", "mode", "actions")


class LocalActionRecordInvalid(ValueError):  # noqa: N818 - named like actions.ActionsInvalid
    """Raised when a local record or one of its fields is malformed; the message names the field, never its data."""


class LocalActionMode(StrEnum):
    """How the local actions of a trigger combine with the owner actions."""

    ADDITIVE = "additive"
    REPLACEMENT = "replacement"


class PlanComposition(StrEnum):
    """What one trigger of the device Script runs."""

    OWNER_AND_LOCAL = "owner_and_local"  # both branches, native parallel, owner first
    OWNER_ONLY = "owner_only"
    LOCAL_ONLY = "local_only"
    NOTHING = "nothing"  # no eligible branch and no local decision
    MUTED = "muted"  # an active replacement without local actions: nothing runs, by the user's choice


def normalize_local_state_value(value: str) -> str:
    """Return the matching form of a StateValue: str.strip().lower(), never casefold, as state.decide does."""
    return value.strip().lower()


@dataclass(frozen=True, slots=True, order=True)
class LocalActionIdentity:
    """What a record attaches by: device id, device kind and the normalized StateValue (D-10)."""

    device_id: str
    kind: str
    state_value: str


def local_trigger_identity(device_id: str, kind: str, state_value: str) -> LocalActionIdentity:
    """Return the identity of a trigger; owner labels, revisions and option positions are never part of it."""
    return LocalActionIdentity(device_id, kind, normalize_local_state_value(state_value))


@dataclass(frozen=True, slots=True)
class LocalActionRecord:
    """
    One saved local customization of one trigger.

    `state_value` is the value as the user saw it and `label` the last known friendly name; both are for display only.
    `actions` is a raw, JSON-serializable list owned by the record: it is deep-copied in and out (T-11-06). An empty
    list with `REPLACEMENT` is a deliberate mute; an empty list with `ADDITIVE` adds no branch.
    """

    identity: LocalActionIdentity
    state_value: str
    label: str
    mode: LocalActionMode
    actions: list[dict[str, Any]]

    def copy_actions(self) -> list[dict[str, Any]]:
        """Return a deep copy of the local actions."""
        return copy.deepcopy(self.actions)

    def with_label(self, label: str) -> LocalActionRecord:
        """Return the record with a refreshed display label; the identity stays."""
        return dataclasses.replace(self, label=_text(label, "label"))


def _text(value: Any, field: str, *, required: bool = False) -> str:
    """Return a string field; raise naming the field when it is not text or, if required, blank."""
    if not isinstance(value, str) or (required and not value.strip()):
        msg = f"local record field {field} is invalid"
        raise LocalActionRecordInvalid(msg)
    return value


def _actions(value: Any) -> list[dict[str, Any]]:
    """Return a deep copy of a raw action list; anything but a list of mappings is refused."""
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        msg = "local record field actions is not a list of actions"
        raise LocalActionRecordInvalid(msg)
    return copy.deepcopy(value)


def make_local_record(  # noqa: PLR0913 - one record is six independent facts
    device_id: str, kind: str, state_value: str, *, label: str, mode: LocalActionMode | str, actions: Any
) -> LocalActionRecord:
    """Return a validated record of the local customization of one trigger; raise LocalActionRecordInvalid."""
    _text(device_id, "device_id", required=True)
    if kind not in LOCAL_KINDS:
        msg = "local record field kind is invalid"
        raise LocalActionRecordInvalid(msg)
    _text(state_value, "state_value", required=True)
    try:
        checked_mode = LocalActionMode(mode)
    except ValueError as err:
        msg = "local record field mode is invalid"
        raise LocalActionRecordInvalid(msg) from err
    return LocalActionRecord(
        local_trigger_identity(device_id, kind, state_value),
        state_value,
        _text(label, "label"),
        checked_mode,
        _actions(actions),
    )


def parse_local_record(raw: Any) -> LocalActionRecord:
    """Return the record of one stored v1 row; raise LocalActionRecordInvalid for a malformed row."""
    if not isinstance(raw, dict) or any(key not in raw for key in RECORD_KEYS):
        msg = "local record is not a mapping with every field"
        raise LocalActionRecordInvalid(msg)
    return make_local_record(
        raw["device_id"],
        raw["kind"],
        raw["state_value"],
        label=raw["label"],
        mode=raw["mode"],
        actions=raw["actions"],
    )


def local_record_data(record: LocalActionRecord) -> dict[str, Any]:
    """Return the stored v1 row of a record, with its own copy of the actions."""
    return {
        "device_id": record.identity.device_id,
        "kind": record.identity.kind,
        "state_value": record.state_value,
        "label": record.label,
        "mode": str(record.mode),
        "actions": record.copy_actions(),
    }


@dataclass(frozen=True, slots=True)
class EffectiveTriggerPlan:
    """
    The complete local runtime decision for one trigger of one device.

    `owner_actions` is set only when the owner branch is eligible, `local_actions` only when the local branch is.
    `owner_path` and `local_path` are set by the runner once the trigger has its place in the device Script: each is
    the config and trace path whose children are the top-level steps of that branch.
    """

    device_id: str
    kind: str
    trigger_key: str
    state_value: str
    label: str
    approval: str
    customization: LocalActionMode | None
    owner_actions: list[dict[str, Any]] | None
    local_actions: list[dict[str, Any]] | None
    owner_path: str | None = None
    local_path: str | None = None

    @property
    def owner_eligible(self) -> bool:
        """Return True when the owner branch runs."""
        return self.owner_actions is not None

    @property
    def local_eligible(self) -> bool:
        """Return True when the local branch runs."""
        return self.local_actions is not None

    @property
    def composition(self) -> PlanComposition:
        """Return what this trigger runs."""
        if self.owner_eligible and self.local_eligible:
            return PlanComposition.OWNER_AND_LOCAL
        if self.owner_eligible:
            return PlanComposition.OWNER_ONLY
        if self.local_eligible:
            return PlanComposition.LOCAL_ONLY
        if self.customization is LocalActionMode.REPLACEMENT:
            return PlanComposition.MUTED
        return PlanComposition.NOTHING

    @property
    def runnable(self) -> bool:
        """Return True when at least one branch runs."""
        return self.owner_eligible or self.local_eligible

    def restricted_to(self, *, owner: bool, local: bool) -> EffectiveTriggerPlan:
        """Return the plan with a branch dropped, for example one whose actions did not validate; never adds one."""
        return dataclasses.replace(
            self,
            owner_actions=self.owner_actions if owner else None,
            local_actions=self.local_actions if local else None,
            owner_path=None,
            local_path=None,
        )

    def at_dispatch(self, prefix: str) -> EffectiveTriggerPlan:
        """
        Return the plan with its branch paths below the dispatch sequence `prefix` of its trigger.

        Both branches: one `parallel` step, owner branch 0, local branch 1. One branch: its steps are the sequence.
        """
        if self.owner_eligible and self.local_eligible:
            owner, local = f"{prefix}/0/parallel/0/sequence", f"{prefix}/0/parallel/1/sequence"
        else:
            owner = prefix if self.owner_eligible else None
            local = prefix if self.local_eligible else None
        return dataclasses.replace(self, owner_path=owner, local_path=local)


def build_effective_trigger_plan(
    device_id: str, kind: str, trigger: TriggerSpec, approval: str, record: LocalActionRecord | None
) -> EffectiveTriggerPlan:
    """
    Return the plan of one owner trigger with an optional local record, as a pure transformation over copies.

    A record attaches only by exact identity (device id, kind, normalized StateValue); any other record counts as
    absent. Owner: approved AND owner actions AND not replaced by the attached record (D-02, D-04). Local: the attached
    record has actions, whatever the approval (D-02). The approval word is carried unchanged; a replacement never
    changes it. Neither the trigger nor the record is mutated, and the plan owns its own copies.
    """
    if record is not None and record.identity != local_trigger_identity(device_id, kind, trigger.value):
        record = None
    replaced = record is not None and record.mode is LocalActionMode.REPLACEMENT
    owner = approval == APPROVED and bool(trigger.actions) and not replaced
    return EffectiveTriggerPlan(
        device_id=device_id,
        kind=kind,
        trigger_key=trigger.key,
        state_value=trigger.value,
        label=trigger.label,
        approval=approval,
        customization=None if record is None else record.mode,
        owner_actions=copy.deepcopy(trigger.actions) if owner else None,
        local_actions=record.copy_actions() if record is not None and record.actions else None,
    )


@dataclass(frozen=True, slots=True)
class LocalMatch:
    """The records of one device against its current owner triggers: active by trigger key, the rest inactive."""

    active: Mapping[str, LocalActionRecord]
    inactive: tuple[LocalActionRecord, ...]


def match_local_records(spec: DeviceSpec, records: Iterable[LocalActionRecord]) -> LocalMatch:
    """
    Split the records of the device into active ones (exact identity of a current trigger) and inactive ones.

    Records of other devices are ignored. An orphan (the option is gone) and a record of the other kind stay inactive
    and are never applied; they become active again as soon as a trigger with the same identity returns (D-05, D-12).
    Inactive records are sorted by identity for display; identities are unique in a record set, the first one wins.
    """
    by_identity: dict[LocalActionIdentity, LocalActionRecord] = {}
    for record in records:
        if record.identity.device_id == spec.device_id:
            by_identity.setdefault(record.identity, record)
    active: dict[str, LocalActionRecord] = {}
    for trigger in spec.triggers.values():
        record = by_identity.pop(local_trigger_identity(spec.device_id, spec.kind, trigger.value), None)
        if record is not None:
            active[trigger.key] = record
    return LocalMatch(active, tuple(sorted(by_identity.values(), key=lambda record: record.identity)))


def build_effective_trigger_plans(
    spec: DeviceSpec, approval: str, records: Iterable[LocalActionRecord]
) -> tuple[EffectiveTriggerPlan, ...]:
    """Return one plan per owner trigger, in owner trigger order; inactive records contribute nothing."""
    active = match_local_records(spec, records).active
    return tuple(
        build_effective_trigger_plan(spec.device_id, spec.kind, trigger, approval, active.get(trigger.key))
        for trigger in spec.triggers.values()
    )


# --- policy and counts ------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EffectivePolicy:
    """The device-wide execution settings one snapshot feeds to tracker, breaker and Script (D-03, MIR-11)."""

    run_on_startup: bool
    run_mode: str
    breaker_max_runs: int
    breaker_window: int
    queue_limit: int


# Startup off, serial, the default breaker and queue: no unapproved owner metadata gains execution authority
LOCAL_SAFE_POLICY = EffectivePolicy(
    run_on_startup=False,
    run_mode=RUN_MODE_SERIAL,
    breaker_max_runs=DEFAULT_BREAKER_MAX_RUNS,
    breaker_window=DEFAULT_BREAKER_WINDOW,
    queue_limit=SERIAL_QUEUE_LIMIT,
)


def effective_policy(spec: DeviceSpec, approval: str) -> EffectivePolicy:
    """Return the owner's settings once its exact actions hash is approved, the fixed safe local policy before."""
    if approval != APPROVED:
        return LOCAL_SAFE_POLICY
    return EffectivePolicy(
        run_on_startup=spec.run_on_startup,
        run_mode=spec.run_mode,
        breaker_max_runs=spec.breaker_max_runs,
        breaker_window=spec.breaker_window,
        queue_limit=SERIAL_QUEUE_LIMIT,
    )


@dataclass(frozen=True, slots=True)
class LocalActionCounts:
    """Counts only, never content (D-04): what diagnostics and the removal notice may say about local actions."""

    records: int
    devices: int
    active: int
    inactive: int
    replaced: int
    muted: int
    orphan_only_devices: int


def local_action_counts(records: Iterable[LocalActionRecord], specs: Mapping[str, DeviceSpec]) -> LocalActionCounts:
    """
    Count the records against the current mirror specs by device id.

    A record of a device without a current spec is inactive. `replaced` and `muted` count active replacements with
    and without local actions; an orphan-only device has records but none of them is active.
    """
    by_device: dict[str, list[LocalActionRecord]] = {}
    for record in records:
        by_device.setdefault(record.identity.device_id, []).append(record)
    active: list[LocalActionRecord] = []
    inactive = 0
    orphan_only = 0
    for device_id, device_records in by_device.items():
        spec = specs.get(device_id)
        if spec is None:
            matched: LocalMatch = LocalMatch({}, tuple(device_records))
        else:
            matched = match_local_records(spec, device_records)
        active.extend(matched.active.values())
        inactive += len(device_records) - len(matched.active)
        orphan_only += not matched.active
    replacements = [record for record in active if record.mode is LocalActionMode.REPLACEMENT]
    return LocalActionCounts(
        records=sum(len(device_records) for device_records in by_device.values()),
        devices=len(by_device),
        active=len(active),
        inactive=inactive,
        replaced=sum(1 for record in replacements if record.actions),
        muted=sum(1 for record in replacements if not record.actions),
        orphan_only_devices=orphan_only,
    )
