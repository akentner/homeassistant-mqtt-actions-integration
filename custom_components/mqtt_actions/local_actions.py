"""
Pure model of local actions on mirrors: records, identity and the effective plan of one trigger (D-01 to D-05).

No Home Assistant imports. RED skeleton of Plan 11-03 Task 1: the interfaces exist so the runner tests compile; the
plan builder still returns today's owner-only plans and attaches no local record.
"""

import copy
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .model import DeviceSpec

APPROVED = "approved"


class LocalActionMode(StrEnum):
    """How the local actions of a trigger combine with the owner actions."""

    ADDITIVE = "additive"
    REPLACEMENT = "replacement"


@dataclass(frozen=True, slots=True)
class LocalActionIdentity:
    """What a record attaches by: device id, device kind and the normalized StateValue."""

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
    """Return a record (skeleton)."""
    return LocalActionRecord(
        LocalActionIdentity(device_id, kind, state_value.strip().lower()), state_value, label, mode, actions
    )


@dataclass(frozen=True, slots=True)
class EffectiveTriggerPlan:
    """The complete local runtime decision for one trigger of one device."""

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


def build_effective_trigger_plans(
    spec: DeviceSpec, approval: str, records: Iterable[LocalActionRecord]
) -> tuple[EffectiveTriggerPlan, ...]:
    """Return one plan per owner trigger (skeleton: owner-only, records ignored)."""
    del records
    return tuple(
        EffectiveTriggerPlan(
            device_id=spec.device_id,
            kind=spec.kind,
            trigger_key=trigger.key,
            state_value=trigger.value,
            label=trigger.label,
            approval=approval,
            customization=None,
            owner_actions=copy.deepcopy(trigger.actions) if approval == APPROVED and trigger.actions else None,
            local_actions=None,
        )
        for trigger in spec.triggers.values()
    )
