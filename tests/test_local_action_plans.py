"""
The gate oracle of effective trigger plans: approval x local customization x owner actions (D-02, D-05, D-11, D-21).

Pure data and a test-local reference rule, written before any Phase 11 production code. The module imports nothing from
the integration, so it collects and passes on its own; Plan 11-03 binds every row to the production plan builder
without changing a row.

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

import itertools
from dataclasses import dataclass

import pytest

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
