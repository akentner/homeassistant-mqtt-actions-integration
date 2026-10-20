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

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .model import DeviceSpec, TriggerSpec

# The approval word of trust.ApprovalState that makes owner actions eligible; quoted to keep this module HA-free
APPROVED = "approved"


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


@dataclass(frozen=True, slots=True)
class LocalActionIdentity:
    """What a record attaches by: device id, device kind and the normalized StateValue (D-10)."""

    device_id: str
    kind: str
    state_value: str


@dataclass(frozen=True, slots=True)
class LocalActionRecord:
    """One saved local customization of one trigger."""

    identity: LocalActionIdentity
    state_value: str
    label: str
    mode: LocalActionMode
    actions: list[dict[str, Any]]


def make_local_record(  # noqa: PLR0913 - one record is six independent facts
    device_id: str, kind: str, state_value: str, *, label: str, mode: LocalActionMode, actions: list[dict[str, Any]]
) -> LocalActionRecord:
    """Return a record of the local customization of one trigger."""
    return LocalActionRecord(
        LocalActionIdentity(device_id, kind, normalize_local_state_value(state_value)),
        state_value,
        label,
        mode,
        actions,
    )


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
    """Return the plan of one owner trigger with an optional local record."""
    attached = (
        record
        if record is not None and record.identity.state_value == normalize_local_state_value(trigger.value)
        else None
    )
    return EffectiveTriggerPlan(
        device_id=device_id,
        kind=kind,
        trigger_key=trigger.key,
        state_value=trigger.value,
        label=trigger.label,
        approval=approval,
        customization=None if attached is None else attached.mode,
        owner_actions=copy.deepcopy(trigger.actions) if approval == APPROVED and trigger.actions else None,
        local_actions=copy.deepcopy(attached.actions) if attached is not None and attached.actions else None,
    )


def build_effective_trigger_plans(
    spec: DeviceSpec, approval: str, records: Iterable[LocalActionRecord]
) -> tuple[EffectiveTriggerPlan, ...]:
    """Return one plan per owner trigger, in owner trigger order."""
    by_value = {
        record.identity.state_value: record for record in records if record.identity.device_id == spec.device_id
    }
    return tuple(
        build_effective_trigger_plan(
            spec.device_id, spec.kind, trigger, approval, by_value.get(normalize_local_state_value(trigger.value))
        )
        for trigger in spec.triggers.values()
    )
