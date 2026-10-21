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
    LOCAL_ACTIONS_RECORDS,
    LOCAL_ACTIONS_STORE_VERSION,
    MAX_ISSUE_ERROR_LENGTH,
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


class LocalActionsStoreVersionError(ValueError):
    """Raised for a stored local-actions payload of a version this release cannot read; nothing is rewritten."""


@dataclass(frozen=True, slots=True)
class ParsedLocalActions:
    """
    The records of a loaded local-actions payload.

    `dropped` counts the stored rows left out: malformed ones and later duplicates of an identity. `shape_valid` is
    False when the payload is not a mapping with a record list at all, which loads no record.
    """

    records: tuple[LocalActionRecord, ...]
    dropped: int
    shape_valid: bool = True


def copy_local_records(records: Iterable[LocalActionRecord]) -> tuple[LocalActionRecord, ...]:
    """Return the records with their own deep copies of the actions, so no caller shares nested data with another."""
    return tuple(dataclasses.replace(record, actions=record.copy_actions()) for record in records)


def parse_local_actions_payload(data: Any) -> ParsedLocalActions:
    """
    Return the valid records of a stored payload, in stored order (D-12, T-11-09).

    Every row is validated on its own, so one malformed row never removes a valid one. Records are not matched against
    any device: orphan and kind-mismatched rows load like every other row. The first row of an identity wins, as in
    `match_local_records`; later rows of the same identity are dropped.
    """
    rows = data.get(LOCAL_ACTIONS_RECORDS) if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return ParsedLocalActions((), 0, shape_valid=False)
    records: list[LocalActionRecord] = []
    seen: set[LocalActionIdentity] = set()
    for row in rows:
        try:
            record = parse_local_record(row)
        except LocalActionRecordInvalid:
            continue
        if record.identity not in seen:
            seen.add(record.identity)
            records.append(record)
    return ParsedLocalActions(tuple(records), len(rows) - len(records))


def local_actions_payload(records: Iterable[LocalActionRecord]) -> dict[str, Any]:
    """Return the stored payload of the records: raw JSON rows only, each with its own copy of the actions."""
    return {LOCAL_ACTIONS_RECORDS: [local_record_data(record) for record in records]}


def migrate_local_actions_payload(old_major_version: int, old_minor_version: int, old_data: Any) -> Any:
    """
    Return a stored payload upgraded to the current version, as a copy; raise LocalActionsStoreVersionError.

    Version 1 is the only major version, so the hook upgrades nothing yet: a minor-only difference keeps the rows,
    which the parser then checks one by one. Any other major version is refused rather than reset (D-07).
    """
    if old_major_version != LOCAL_ACTIONS_STORE_VERSION:
        msg = f"local actions Store version {old_major_version}.{old_minor_version} is not supported"
        raise LocalActionsStoreVersionError(msg)
    return copy.deepcopy(old_data)


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


# --- per-branch outcomes (D-18, D-19) ---------------------------------------------------------------------------------


class OutcomeStatus(StrEnum):
    """What one run proved about the local branch of its trigger."""

    SUCCESS = "success"  # the local branch completed cleanly under the current Script, generation and stop epoch
    FAILURE = "failure"  # a step at or below the local branch recorded an error, continued or not
    NO_SUCCESS = "no_success"  # anything else: dropped, cancelled, superseded, stopped, aborted or ambiguous


@dataclass(frozen=True, slots=True)
class StepTrace:
    """The bounded summary of one trace path: first error, a stop ran there, the step was a false condition."""

    error: str | None
    stopped: bool
    condition_false: bool


@dataclass(frozen=True, slots=True)
class BranchOutcome:
    """
    The local outcome of one run of one trigger: identity, status, a bounded error and the run's generation.

    It carries no trace content, no variables and no actions (T-11-08). `label` and `device_name` come from the broker;
    a consumer escapes them before they reach markdown. `identity` is the record identity of the trigger, so a consumer
    can match the outcome to a customization even when the mirror is not registered yet or the option is gone later.
    Generation 0 marks a failure found while the Script was built, not in a run.
    """

    device_id: str
    trigger_key: str
    label: str
    status: OutcomeStatus
    error: str | None
    generation: int
    identity: LocalActionIdentity | None = None
    device_name: str = ""


def bounded_error(text: str) -> str:
    """Return error text cut to the issue cap."""
    return text[:MAX_ISSUE_ERROR_LENGTH]


def summarize_trace(trace: Mapping[str, Iterable[Any]]) -> dict[str, StepTrace]:
    """
    Reduce a Core trace (path -> trace elements with `as_dict()`) to bounded step summaries, in trace order.

    Only the error text, a stop result and a condition result are read; variables and parameters are dropped here.
    """
    steps: dict[str, StepTrace] = {}
    for path, elements in trace.items():
        error: str | None = None
        stopped = False
        condition_false = False
        for element in elements:
            data = element.as_dict()
            if error is None and data.get("error"):
                error = bounded_error(str(data["error"]))
            result = data.get("result")
            result = result if isinstance(result, dict) else {}
            stopped = stopped or "stop" in result
            condition_false = result.get("result") is False
        steps[path] = StepTrace(error, stopped, condition_false)
    return steps


def _under(path: str, prefix: str) -> bool:
    """Return True for the prefix itself and every path below it."""
    return path == prefix or path.startswith(f"{prefix}/")


def branch_error(steps: Mapping[str, StepTrace], path: str) -> str | None:
    """Return the first bounded error recorded at or below a branch path, None when the branch recorded none."""
    return next((step.error for at, step in steps.items() if step.error is not None and _under(at, path)), None)


def reduce_local_outcome(
    plan: EffectiveTriggerPlan, steps: Mapping[str, StepTrace], *, proven: bool
) -> tuple[OutcomeStatus, str | None]:
    """
    Classify the local branch of one run conservatively; never infer success from the outer result.

    Any error at or below the local path is a failure, also a continued one or one hidden by an owner stop. Success
    needs `proven` (the run ran under the current Script, generation and stop epoch), no stop anywhere in the run
    (a stop ends the whole run), and a reached last top-level local step that is not a false condition. Everything
    else, including an ambiguous trace, is no success and leaves an existing local issue alone.
    """
    if plan.local_path is None or not plan.local_actions:
        return OutcomeStatus.NO_SUCCESS, None
    for path, step in steps.items():
        if step.error is not None and _under(path, plan.local_path):
            return OutcomeStatus.FAILURE, bounded_error(step.error)
    if not proven or any(step.stopped for step in steps.values()):
        return OutcomeStatus.NO_SUCCESS, None
    last = steps.get(f"{plan.local_path}/{len(plan.local_actions) - 1}")
    if last is None or last.condition_false:
        return OutcomeStatus.NO_SUCCESS, None
    return OutcomeStatus.SUCCESS, None
