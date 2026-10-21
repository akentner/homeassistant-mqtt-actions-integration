"""
The gate oracle of effective trigger plans: approval x local customization x owner actions (D-02, D-05, D-11, D-21).

Pure data and a test-local reference rule, written before any Phase 11 production code (Plan 11-01). Plan 11-03 binds
every row to the production plan builder `local_actions.build_effective_trigger_plan` without changing a row; the
binding and the identity, mute, orphan, aliasing and policy tests sit below the self-checks.

The 24 baseline rows are the full product of the three locked axes. In a baseline row a present customization is an
active record with a non-empty local sequence. The separate rows cover what the baseline cannot express: an empty
replacement (a deliberate local mute), an empty additive record, an orphaned record and a record of the other device
kind. The rules the rows encode:

- the owner branch is eligible only for an approved mirror whose trigger has owner actions and is not replaced locally
- the local branch is eligible for any active customization with local actions, whatever the approval state is
- an absent customization is exactly today's owner-only behavior
- an empty replacement runs nothing on purpose (muted), an empty additive record adds no local branch
- identity is device id plus device kind plus normalized StateValue; an orphan or a kind mismatch never attaches

Some pure combinations cannot happen end to end: a `no_actions` mirror never has a trigger with owner actions. The
defensive matrix keeps them; the integration tests only build reachable states.
"""

import copy
import itertools
from dataclasses import astuple, dataclass
from typing import Any

import pytest

from custom_components.mqtt_actions import local_actions
from custom_components.mqtt_actions.local_actions import (
    LocalActionMode,
    build_effective_trigger_plan,
    build_effective_trigger_plans,
    make_local_record,
)
from custom_components.mqtt_actions.model import TriggerSpec, trigger_key
from tests.documents import make_spec

# The approval words of a mirror (trust.ApprovalState), quoted rather than imported on purpose
APPROVED = "approved"
PENDING = "pending"
BLOCKED = "blocked"
NO_ACTIONS = "no_actions"
APPROVAL_STATES = (APPROVED, PENDING, BLOCKED, NO_ACTIONS)

ABSENT = "absent"
ADDITIVE = "additive"
REPLACEMENT = "replacement"
CUSTOMIZATIONS = (ABSENT, ADDITIVE, REPLACEMENT)

OWNER_ACTIONS = "owner_actions"
NO_OWNER_ACTIONS = "no_owner_actions"
OWNER_TRIGGERS = (OWNER_ACTIONS, NO_OWNER_ACTIONS)

# Where the record of a customization stands against the current mirror
ACTIVE = "active"
ORPHAN = "orphan"
KIND_MISMATCH = "kind_mismatch"

# What one trigger of the device Script runs
OWNER_AND_LOCAL = "owner_and_local"  # both branches, native parallel inside the one device Script
OWNER_ONLY = "owner_only"
LOCAL_ONLY = "local_only"
NOTHING = "nothing"  # no eligible branch and no local decision
MUTED = "muted"  # an active empty replacement: nothing runs, by the user's choice

SWITCH = "switch"
SELECT = "select"


@dataclass(frozen=True)
class GateCase:
    """One expected plan: the inputs, then whether each branch is eligible and what the trigger runs."""

    approval: str
    customization: str
    owner_trigger: str
    owner_eligible: bool
    local_eligible: bool
    composition: str
    local_actions: bool = True
    record: str = ACTIVE
    name: str = ""

    @property
    def case_id(self) -> str:
        """Return the parametrized id: the axes for a baseline row, the name for a separate row."""
        return self.name or f"{self.approval}-{self.customization}-{self.owner_trigger}"


def _row(approval: str, customization: str, owner_trigger: str, owner: bool, local: bool, composition: str) -> GateCase:
    return GateCase(approval, customization, owner_trigger, owner, local, composition)


# The 24 baseline rows, written out as data: the reference rule below must agree with every one of them
EXPECTED_GATE_CASES: tuple[GateCase, ...] = (
    _row(APPROVED, ABSENT, OWNER_ACTIONS, True, False, OWNER_ONLY),
    _row(APPROVED, ABSENT, NO_OWNER_ACTIONS, False, False, NOTHING),
    _row(APPROVED, ADDITIVE, OWNER_ACTIONS, True, True, OWNER_AND_LOCAL),
    _row(APPROVED, ADDITIVE, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(APPROVED, REPLACEMENT, OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(APPROVED, REPLACEMENT, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(PENDING, ABSENT, OWNER_ACTIONS, False, False, NOTHING),
    _row(PENDING, ABSENT, NO_OWNER_ACTIONS, False, False, NOTHING),
    _row(PENDING, ADDITIVE, OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(PENDING, ADDITIVE, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(PENDING, REPLACEMENT, OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(PENDING, REPLACEMENT, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(BLOCKED, ABSENT, OWNER_ACTIONS, False, False, NOTHING),
    _row(BLOCKED, ABSENT, NO_OWNER_ACTIONS, False, False, NOTHING),
    _row(BLOCKED, ADDITIVE, OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(BLOCKED, ADDITIVE, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(BLOCKED, REPLACEMENT, OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(BLOCKED, REPLACEMENT, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
    # Defensive: a no_actions mirror never has owner actions end to end, the pure rule must still refuse them
    _row(NO_ACTIONS, ABSENT, OWNER_ACTIONS, False, False, NOTHING),
    _row(NO_ACTIONS, ABSENT, NO_OWNER_ACTIONS, False, False, NOTHING),
    _row(NO_ACTIONS, ADDITIVE, OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(NO_ACTIONS, ADDITIVE, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(NO_ACTIONS, REPLACEMENT, OWNER_ACTIONS, False, True, LOCAL_ONLY),
    _row(NO_ACTIONS, REPLACEMENT, NO_OWNER_ACTIONS, False, True, LOCAL_ONLY),
)

# Separate rows outside the matrix: empty local sequences and records that do not attach to the current mirror
SEPARATE_GATE_CASES: tuple[GateCase, ...] = (
    GateCase(
        APPROVED, REPLACEMENT, OWNER_ACTIONS, False, False, MUTED, local_actions=False, name="empty-replacement-mutes"
    ),
    GateCase(
        PENDING,
        REPLACEMENT,
        OWNER_ACTIONS,
        False,
        False,
        MUTED,
        local_actions=False,
        name="empty-replacement-mutes-pending",
    ),
    GateCase(
        APPROVED,
        ADDITIVE,
        OWNER_ACTIONS,
        True,
        False,
        OWNER_ONLY,
        local_actions=False,
        name="additive-empty-adds-no-branch",
    ),
    GateCase(
        PENDING,
        ADDITIVE,
        OWNER_ACTIONS,
        False,
        False,
        NOTHING,
        local_actions=False,
        name="additive-empty-pending-runs-nothing",
    ),
    # The owner dropped the option: there is no owner trigger for it and the record stays inactive
    GateCase(APPROVED, ADDITIVE, NO_OWNER_ACTIONS, False, False, NOTHING, record=ORPHAN, name="orphan-additive"),
    GateCase(APPROVED, REPLACEMENT, NO_OWNER_ACTIONS, False, False, NOTHING, record=ORPHAN, name="orphan-replacement"),
    # A record of the other kind with the same StateValue never replaces or extends this device's trigger
    GateCase(
        APPROVED,
        REPLACEMENT,
        OWNER_ACTIONS,
        True,
        False,
        OWNER_ONLY,
        record=KIND_MISMATCH,
        name="kind-mismatch-never-replaces",
    ),
    GateCase(
        PENDING, ADDITIVE, OWNER_ACTIONS, False, False, NOTHING, record=KIND_MISMATCH, name="kind-mismatch-never-adds"
    ),
)


def reference_plan(case: GateCase) -> tuple[bool, bool, str]:
    """
    Return (owner eligible, local eligible, composition) by the locked rule, independent of the rows.

    Owner: approved AND owner actions AND not replaced by an active record. Local: an active record with local actions,
    whatever the approval. An active replacement without local actions is a mute; an inactive record counts as absent.
    """
    active = case.customization != ABSENT and case.record == ACTIVE
    replacing = active and case.customization == REPLACEMENT
    owner = case.approval == APPROVED and case.owner_trigger == OWNER_ACTIONS and not replacing
    local = active and case.local_actions
    if owner and local:
        composition = OWNER_AND_LOCAL
    elif owner:
        composition = OWNER_ONLY
    elif local:
        composition = LOCAL_ONLY
    elif replacing:
        composition = MUTED
    else:
        composition = NOTHING
    return owner, local, composition


def reference_identity(device_id: str, kind: str, state_value: str) -> tuple[str, str, str]:
    """Return the identity a record attaches by: device id, device kind and the normalized StateValue, never a label."""
    return device_id, kind, state_value.strip().lower()


# --- self-checks of the matrix ----------------------------------------------------------------------------------------


def test_gate_matrix_has_exactly_24_rows() -> None:
    assert len(EXPECTED_GATE_CASES) == 4 * 3 * 2 == 24


def test_gate_ids_are_unique_and_separate_rows_are_outside_the_matrix() -> None:
    matrix_ids = [case.case_id for case in EXPECTED_GATE_CASES]
    separate_ids = [case.case_id for case in SEPARATE_GATE_CASES]
    assert len(set(matrix_ids)) == len(matrix_ids) == 24
    assert len(set(separate_ids)) == len(separate_ids)
    assert not set(matrix_ids) & set(separate_ids)
    assert all(not case.name for case in EXPECTED_GATE_CASES)


def test_gate_matrix_covers_every_axis_combination_once() -> None:
    combinations = [(case.approval, case.customization, case.owner_trigger) for case in EXPECTED_GATE_CASES]
    assert sorted(combinations) == sorted(itertools.product(APPROVAL_STATES, CUSTOMIZATIONS, OWNER_TRIGGERS))


def test_baseline_rows_have_active_records_with_local_actions() -> None:
    assert all(case.record == ACTIVE and case.local_actions for case in EXPECTED_GATE_CASES)


def test_separate_rows_cover_mute_additive_empty_orphan_and_kind_mismatch() -> None:
    assert any(case.composition == MUTED and case.customization == REPLACEMENT for case in SEPARATE_GATE_CASES)
    assert any(not case.local_actions and case.customization == ADDITIVE for case in SEPARATE_GATE_CASES)
    assert {case.record for case in SEPARATE_GATE_CASES} >= {ORPHAN, KIND_MISMATCH}
    # Muting is only ever the empty active replacement: no baseline row and no inactive record mutes
    assert all(case.composition != MUTED for case in EXPECTED_GATE_CASES)
    assert all(case.composition != MUTED for case in SEPARATE_GATE_CASES if case.record != ACTIVE)


@pytest.mark.parametrize("case", EXPECTED_GATE_CASES, ids=lambda case: case.case_id)
def test_gate_matrix_row_matches_the_reference_rule(case: GateCase) -> None:
    assert reference_plan(case) == (case.owner_eligible, case.local_eligible, case.composition)


@pytest.mark.parametrize("case", SEPARATE_GATE_CASES, ids=lambda case: case.case_id)
def test_separate_row_matches_the_reference_rule(case: GateCase) -> None:
    assert reference_plan(case) == (case.owner_eligible, case.local_eligible, case.composition)


# --- properties the rows must keep ------------------------------------------------------------------------------------


def test_owner_branch_needs_the_exact_approval_and_owner_actions() -> None:
    """D-02: no row gives the owner branch to an unapproved mirror, to a trigger without actions or to a replacement."""
    for case in (*EXPECTED_GATE_CASES, *SEPARATE_GATE_CASES):
        if case.owner_eligible:
            assert case.approval == APPROVED
            assert case.owner_trigger == OWNER_ACTIONS
            assert not (case.customization == REPLACEMENT and case.record == ACTIVE)


def test_local_eligibility_is_independent_of_approval() -> None:
    """D-02: the local branch is the same for every approval state; owner approval never gates trusted local work."""
    by_inputs: dict[tuple[str, str], set[bool]] = {}
    for case in EXPECTED_GATE_CASES:
        by_inputs.setdefault((case.customization, case.owner_trigger), set()).add(case.local_eligible)
    assert all(len(values) == 1 for values in by_inputs.values())
    assert all(case.local_eligible == (case.customization != ABSENT) for case in EXPECTED_GATE_CASES)


def test_absent_customization_is_todays_owner_only_behavior() -> None:
    """D-05: without a record the plan is exactly the existing gate: owner actions only, and only when approved."""
    for case in EXPECTED_GATE_CASES:
        if case.customization == ABSENT:
            assert not case.local_eligible
            assert case.owner_eligible == (case.approval == APPROVED and case.owner_trigger == OWNER_ACTIONS)


def test_replacement_never_grants_the_owner_branch() -> None:
    """D-04: replacing a trigger locally keeps the owner branch out, also for an approved mirror."""
    replaced = [case for case in EXPECTED_GATE_CASES if case.customization == REPLACEMENT]
    assert len(replaced) == 8
    assert not any(case.owner_eligible for case in replaced)


# --- identity -------------------------------------------------------------------------------------------------------


def test_identity_keeps_switch_and_select_with_the_same_state_value_apart() -> None:
    """D-10: a Switch ON and a Select option `on` of the same device id are different triggers."""
    assert reference_identity("dev-1", SWITCH, "ON") != reference_identity("dev-1", SELECT, "on")


def test_identity_normalizes_the_state_value_and_ignores_labels() -> None:
    """D-10, D-11: case and surrounding blanks do not split one StateValue; a display name is not part of it."""
    assert reference_identity("dev-1", SELECT, " Cozy ") == reference_identity("dev-1", SELECT, "cozy")
    assert reference_identity("dev-1", SELECT, "cozy") != reference_identity("dev-2", SELECT, "cozy")
    assert reference_identity("dev-1", SELECT, "cozy") != reference_identity("dev-1", SELECT, "Gemuetlich")


# --- the production binding (Plan 11-03): every row against build_effective_trigger_plan ----------------------------

DEVICE = "dev-1"
OWNER_SEQUENCE = [{"action": "test.owner", "data": {"nested": ["owner"]}}]
LOCAL_SEQUENCE = [{"action": "test.local", "data": {"nested": ["local"]}}]


def _bind(case: GateCase) -> Any:
    """Build the production plan of one row: a Select option `cozy` and the row's record, if any."""
    owner = copy.deepcopy(OWNER_SEQUENCE) if case.owner_trigger == OWNER_ACTIONS else []
    trigger = TriggerSpec("cozy", trigger_key("cozy"), "Cozy", "Cozy", owner)
    record = None
    if case.customization != ABSENT:
        record = make_local_record(
            DEVICE,
            SWITCH if case.record == KIND_MISMATCH else SELECT,
            "gone" if case.record == ORPHAN else "cozy",
            label="Cozy",
            mode=LocalActionMode(case.customization),
            actions=copy.deepcopy(LOCAL_SEQUENCE) if case.local_actions else [],
        )
    return build_effective_trigger_plan(DEVICE, SELECT, trigger, case.approval, record)


@pytest.mark.parametrize("case", EXPECTED_GATE_CASES, ids=lambda case: case.case_id)
def test_production_plan_matches_gate_row(case: GateCase) -> None:
    plan = _bind(case)
    assert (plan.owner_eligible, plan.local_eligible, str(plan.composition)) == (
        case.owner_eligible,
        case.local_eligible,
        case.composition,
    )
    # D-04: a replacement leaves the owner approval word alone
    assert plan.approval == case.approval


@pytest.mark.parametrize("case", SEPARATE_GATE_CASES, ids=lambda case: case.case_id)
def test_production_plan_matches_separate_row(case: GateCase) -> None:
    plan = _bind(case)
    assert (plan.owner_eligible, plan.local_eligible, str(plan.composition)) == (
        case.owner_eligible,
        case.local_eligible,
        case.composition,
    )
    assert plan.approval == case.approval


def test_production_identity_is_the_reference_identity() -> None:
    """D-10: device id, kind and the strip/lower StateValue; the original value and label are kept apart."""
    record = make_local_record(DEVICE, SELECT, " Cozy ", label="Gemuetlich", mode=LocalActionMode.ADDITIVE, actions=[])
    assert astuple(record.identity) == reference_identity(DEVICE, SELECT, " Cozy ")
    assert record.state_value == " Cozy "
    assert record.label == "Gemuetlich"
    assert local_actions.local_trigger_identity(DEVICE, SELECT, "COZY") == record.identity
    assert local_actions.local_trigger_identity(DEVICE, SWITCH, "cozy") != record.identity


@pytest.mark.parametrize(
    "actions",
    ["test.local", {"action": "test.local"}, [1], [["test.local"]], None, ("x",)],
    ids=["string", "mapping", "int-item", "list-item", "none", "tuple"],
)
def test_make_local_record_refuses_a_malformed_action_list(actions: Any) -> None:
    with pytest.raises(ValueError, match="actions"):
        make_local_record(DEVICE, SELECT, "cozy", label="Cozy", mode=LocalActionMode.ADDITIVE, actions=actions)


@pytest.mark.parametrize(
    ("device_id", "kind", "state_value", "label", "mode"),
    [
        ("", SELECT, "cozy", "Cozy", ADDITIVE),
        (DEVICE, "light", "cozy", "Cozy", ADDITIVE),
        (DEVICE, SELECT, "  ", "Cozy", ADDITIVE),
        (DEVICE, SELECT, "cozy", 7, ADDITIVE),
        (DEVICE, SELECT, "cozy", "Cozy", "sometimes"),
    ],
    ids=["empty-device", "unknown-kind", "blank-state-value", "label-not-text", "unknown-mode"],
)
def test_make_local_record_refuses_malformed_fields(
    device_id: str, kind: str, state_value: str, label: Any, mode: str
) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - the field named in the message differs per row
        make_local_record(device_id, kind, state_value, label=label, mode=mode, actions=[])  # type: ignore[arg-type]


def test_parse_local_record_reads_a_v1_row_and_refuses_malformed_rows() -> None:
    row = {"device_id": DEVICE, "kind": SWITCH, "state_value": "ON", "label": "On", "mode": ADDITIVE, "actions": []}
    record = local_actions.parse_local_record(row)
    assert record.identity == local_actions.local_trigger_identity(DEVICE, SWITCH, "on")
    assert record.mode is LocalActionMode.ADDITIVE
    assert local_actions.local_record_data(record) == row
    for broken in ({**row, "actions": "x"}, {**row, "mode": "x"}, {k: v for k, v in row.items() if k != "kind"}, []):
        with pytest.raises(ValueError):  # noqa: PT011
            local_actions.parse_local_record(broken)


def test_record_actions_do_not_alias_input_output_or_plan() -> None:
    """T-11-06: a frozen record owns deep copies; neither the caller nor a plan can change it afterwards."""
    source = copy.deepcopy(LOCAL_SEQUENCE)
    record = make_local_record(DEVICE, SELECT, "cozy", label="Cozy", mode=LocalActionMode.ADDITIVE, actions=source)
    source[0]["data"]["nested"].append("caller")
    assert record.actions == LOCAL_SEQUENCE

    spec = make_spec(SELECT, device_id=DEVICE, options=[("cozy", "Cozy", copy.deepcopy(OWNER_SEQUENCE))])
    plan = build_effective_trigger_plans(spec, APPROVED, [record])[0]
    assert plan.owner_actions is not None
    assert plan.local_actions is not None
    plan.owner_actions[0]["data"]["nested"].append("plan")
    plan.local_actions[0]["data"]["nested"].append("plan")
    assert record.actions == LOCAL_SEQUENCE
    assert next(iter(spec.triggers.values())).actions == OWNER_SEQUENCE

    data = local_actions.local_record_data(record)
    data["actions"][0]["data"]["nested"].append("output")
    assert record.actions == LOCAL_SEQUENCE


def test_renamed_owner_label_keeps_identity_and_attachment() -> None:
    """D-10, D-11: a renamed option keeps its record; the plan shows the owner's current label."""
    record = make_local_record(DEVICE, SELECT, "Cozy", label="Cozy", mode=LocalActionMode.REPLACEMENT, actions=[])
    renamed = make_spec(SELECT, device_id=DEVICE, options=[("cozy", "Gemuetlich", copy.deepcopy(OWNER_SEQUENCE))])

    plan = build_effective_trigger_plans(renamed, APPROVED, [record])[0]

    assert plan.customization is LocalActionMode.REPLACEMENT
    assert str(plan.composition) == MUTED
    assert plan.label == "Gemuetlich"
    assert record.label == "Cozy"


def test_orphan_record_stays_inactive_and_reattaches_when_the_option_returns() -> None:
    """D-05, D-12: the record of a removed option is kept inactive and attaches again to the same StateValue."""
    record = make_local_record(
        DEVICE, SELECT, "cozy", label="Cozy", mode=LocalActionMode.ADDITIVE, actions=copy.deepcopy(LOCAL_SEQUENCE)
    )
    without = make_spec(SELECT, device_id=DEVICE, options=[("warm", "Warm", []), ("cold", "Cold", [])])
    returned = make_spec(SELECT, device_id=DEVICE, options=[("warm", "Warm", []), ("COZY", "Cozy again", [])])

    match = local_actions.match_local_records(without, [record])
    assert match.active == {}
    assert match.inactive == (record,)
    assert [plan.customization for plan in build_effective_trigger_plans(without, PENDING, [record])] == [None, None]

    match = local_actions.match_local_records(returned, [record])
    assert match.active == {trigger_key("COZY"): record}
    assert match.inactive == ()
    plans = build_effective_trigger_plans(returned, PENDING, [record])
    assert [str(plan.composition) for plan in plans] == [NOTHING, LOCAL_ONLY]


def test_cross_kind_record_never_attaches() -> None:
    """D-10, D-12: a Switch ON record and a Select option `on` of the same device id stay apart, both ways."""
    switch_record = make_local_record(
        DEVICE, SWITCH, "ON", label="On", mode=LocalActionMode.REPLACEMENT, actions=copy.deepcopy(LOCAL_SEQUENCE)
    )
    select_record = make_local_record(
        DEVICE, SELECT, "on", label="on", mode=LocalActionMode.REPLACEMENT, actions=copy.deepcopy(LOCAL_SEQUENCE)
    )
    switch = make_spec(SWITCH, device_id=DEVICE, on=copy.deepcopy(OWNER_SEQUENCE))
    select = make_spec(SELECT, device_id=DEVICE, options=[("on", "on", copy.deepcopy(OWNER_SEQUENCE))])

    switch_plans = build_effective_trigger_plans(switch, APPROVED, [select_record])
    select_plans = build_effective_trigger_plans(select, APPROVED, [switch_record])

    assert all(plan.customization is None for plan in (*switch_plans, *select_plans))
    assert str(switch_plans[0].composition) == OWNER_ONLY
    assert str(select_plans[0].composition) == OWNER_ONLY
    assert local_actions.match_local_records(select, [switch_record]).inactive == (switch_record,)


def test_inactive_records_sort_by_identity_and_plans_follow_owner_order() -> None:
    records = [
        make_local_record(DEVICE, SELECT, value, label=value, mode=LocalActionMode.ADDITIVE, actions=[])
        for value in ("zeta", "alpha", "b")
    ]
    spec = make_spec(SELECT, device_id=DEVICE, options=[("b", "B", []), ("a", "A", [])])

    match = local_actions.match_local_records(spec, records)

    assert [record.identity.state_value for record in match.inactive] == ["alpha", "zeta"]
    assert [plan.state_value for plan in build_effective_trigger_plans(spec, APPROVED, records)] == ["b", "a"]


def test_effective_policy_ignores_unapproved_owner_metadata() -> None:
    """D-03, MIR-11: startup off, serial, 5 runs in 10 s and queue 10 until the exact owner hash is approved."""
    spec = make_spec(run_on_startup=True, run_mode="restart", breaker_max_runs=3, breaker_window=30)
    safe = local_actions.LOCAL_SAFE_POLICY
    assert (safe.run_on_startup, safe.run_mode, safe.breaker_max_runs, safe.breaker_window, safe.queue_limit) == (
        False,
        "serial",
        5,
        10,
        10,
    )
    for approval in (PENDING, BLOCKED, NO_ACTIONS):
        assert local_actions.effective_policy(spec, approval) == safe
    approved = local_actions.effective_policy(spec, APPROVED)
    assert (approved.run_on_startup, approved.run_mode, approved.breaker_max_runs, approved.breaker_window) == (
        True,
        "restart",
        3,
        30,
    )


def test_local_action_counts_cover_devices_active_inactive_replaced_and_muted() -> None:
    """D-04, D-08: counts only; a device whose records are all inactive is an orphan-only device."""
    other = "dev-2"
    spec = make_spec(SELECT, device_id=DEVICE, options=[("cozy", "Cozy", []), ("warm", "Warm", [])])
    records = [
        make_local_record(DEVICE, SELECT, "cozy", label="Cozy", mode=LocalActionMode.REPLACEMENT, actions=[]),
        make_local_record(
            DEVICE,
            SELECT,
            "warm",
            label="Warm",
            mode=LocalActionMode.REPLACEMENT,
            actions=copy.deepcopy(LOCAL_SEQUENCE),
        ),
        make_local_record(DEVICE, SELECT, "gone", label="Gone", mode=LocalActionMode.ADDITIVE, actions=[]),
        make_local_record(other, SWITCH, "ON", label="On", mode=LocalActionMode.ADDITIVE, actions=[]),
    ]

    counts = local_actions.local_action_counts(records, {DEVICE: spec})

    assert (counts.records, counts.devices, counts.active, counts.inactive) == (4, 2, 2, 2)
    assert (counts.replaced, counts.muted, counts.orphan_only_devices) == (1, 1, 1)
