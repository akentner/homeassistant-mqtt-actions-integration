---
phase: 11-local-actions-on-mirrors
plan: 11
subsystem: review
tags: [local-actions, cross-file-review, security, lifecycle, repairs, d-23]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plans 11-01 to 11-10 and 11-12: the complete local-actions implementation, tests and docs"
provides:
  - .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md with data-path review tables, 20 findings, MIR/D/T coverage, a Gaps section and proposed gap-closure plans
affects: [11-13, 11-14, 11-15, 11-16, 11-17]

# Actuals (#2632)
actuals:
  tokens: 10252
  tasks: 2
  commits: 2
plan_head_before: e5cedd58aea665b5b08a3ccf4a88d14f56632121
plan_head_after: 8db8b6c0e6c9730467ee5b7638e44240b7ff2543

tech-stack:
  added: []
  patterns:
    - "Review by data path (runtime, persistence, transport, UI) with a file:line citation for every verified step"
    - "Info severity plus no-change status for observations without a violated contract; Low and above are always routed"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md
  modified: []

key-decisions:
  - "Four Low defects are routed to Phase 11 gaps G-01 to G-04; none is deferred to Phase 12"
  - "The local failure issue must survive restart, transient prune and failed adoption while its record exists (D-19); the 11-07 prune deletion and non-persistent issue are a gap, not a design choice"
  - "A refused local Store load keeps the D-09-style fail-open but must become visible through an instance Repairs issue (G-02)"
  - "The executor choices flagged for review (11-05 save refusal, 11-07 pause and mute answers and dropped late failure, 11-08 server-language markers, 11-09 async_close) hold and are closed as no-change with evidence"

patterns-established:
  - "Gap entries in the VERIFICATION gaps shape with at most 5 artifacts and a named RED regression test"

requirements-completed: [MIR-01, MIR-02, MIR-03, MIR-04, MIR-05, MIR-06, MIR-07, MIR-08, MIR-09, MIR-10, MIR-11, MIR-12, MIR-13, MIR-14, MIR-15]

coverage:
  - id: D1
    description: "Milestone-wide cross-file review ledger with data-path tables, findings table and MIR/D/T coverage"
    verification:
      - kind: other
        ref: "Task 1 verify: grep for 'Trust-level mixing', 'Tombstone after prune' and the exact findings header on 11-CROSS-FILE-REVIEW.md"
        status: pass
    human_judgment: true
    rationale: "Whether the review found every defect is a judgment; the automated check only proves structure and coverage"
  - id: D2
    description: "Every finding routed: 4 Low to bounded gaps G-01..G-04, 16 Info closed as no-change"
    verification:
      - kind: other
        ref: "Task 2 verify: ## Gaps present, no OPEN row with a severity, every ROUTED row carries G-NN"
        status: pass
    human_judgment: true
    rationale: "The no-change dispositions and the gap scope are design judgments the owner may want to confirm"

duration: 17 min
completed: 2026-10-21
---

# Phase 11 Plan 11: Cross-File Review Ledger Summary

**A data-path review of the whole Phase 11 build found no Critical, High or Medium defect. It found four Low defects:
the local failure issue is lost on restart, prune and failed adoption (G-01); an unreadable local Store silently
un-mutes triggers (G-02); a leftover local Store attaches to a new hub (G-03); and a failed adoption releases a tripped
breaker (G-04). All four are routed to bounded Phase 11 gap-closure plans. The other 16 observations are closed as
no-change with evidence.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-10-21T03:19:26Z
- **Completed:** 2026-10-21T03:36:40Z
- **Tasks:** 2 (1 tracer, 1 auto), 2 commits
- **Files:** 1 created (the ledger). No product or test file changed.

## Accomplishments

- **Ledger:** `.planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md`. It has four review groups:
  - **Runtime:** policy and plan, Script assembly and guard, outcome and issue, entry points.
  - **Persistence:** durable edit, and the prune, tombstone, adoption and hub removal paths.
  - **Transport:** broker, export, diagnostics and adoption boundaries, plus the NativeMigration, shared-topic and
    registry seams.
  - **UI:** the hub options editor.
- **Explicit classifications:**
  - **Trust-level mixing** holds. Only the owner subtree is guarded and denied. A denied owner call cannot be
    swallowed by `continue_on_error`, and the owner branch cannot cut the local branch short.
  - **Continued errors** are local failures, as decided in RESEARCH resolved question 2.
  - **Save rollback** holds.
  - **Adoption rollback** restores the records and the mirror, but not the trip or the local issue (F-04, F-01).
  - **Tombstone after prune** discards the records.
- **Coverage:** every one of MIR-01 to MIR-15, D-01 to D-23 and T-11-01 to T-11-33 is mapped to the code and a test,
  with any related finding.
- **No claims beyond scope:** no downgrade round trip, bench or release is claimed. MIR-F4 and the final build stay
  with Phase 12.

## Finding counts per status

| Status | Count | IDs |
|--------|-------|-----|
| OPEN | 0 | - |
| ROUTED | 4 | F-01, F-02, F-03, F-04 |
| FIXED | 0 | - |
| NO-CHANGE | 16 | F-05 to F-20 |

By severity: 0 Critical, 0 High, 0 Medium, 4 Low, 16 Info.

## Gaps and proposed fix-plan grouping

| Plan | Gap | Finding | Concern | Files (max 5) | RED regression test |
|------|-----|---------|---------|---------------|---------------------|
| 11-14 | G-01 | F-01 | The local failure issue survives restart, transient prune and failed adoption. It goes only on success, on removal or discard of the customization, or on hub removal (D-19, T-11-21) | `manager.py`, `tests/test_local_actions_lifecycle.py`, `docs/troubleshooting.md`, `tests/test_docs.py` | `tests/test_local_actions_lifecycle.py::test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal` |
| 11-15 | G-02 | F-02 | A refused local Store load raises an instance Repairs issue in en and de, and the file is still never overwritten (D-05, MIR-05, T-11-09) | `manager.py`, `translations/en.json`, `translations/de.json`, `docs/troubleshooting.md`, `tests/test_local_actions_manager.py` | `tests/test_local_actions_manager.py::test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay` |
| 11-16 | G-03 | F-03 | A new hub removes any leftover local Store before its entry is created (D-08, T-11-28) | `config_flow.py`, `tests/test_hub_removal.py`, `README.md` | `tests/test_hub_removal.py::test_new_hub_never_loads_local_actions_left_by_an_earlier_hub` |
| 11-17 | G-04 | F-04 | A failed adoption restores and saves the tripped hash (MIR-09, T-11-17) | `manager.py`, `tests/test_local_actions_lifecycle.py` | `tests/test_local_actions_lifecycle.py::test_failed_adoption_keeps_a_tripped_breaker_paused` |

- All four plans have `depends_on: [11-11]`.
- G-01, G-02 and G-04 all change `manager.py`, so they should run in sequence.
- F-04 has existed since Phase 4. It is routed because the rollback block changed in Phase 11 (T-11-17), and since
  MIR-09 a trip also pauses local actions.

## Next step

Run `/gsd-plan-phase 11 --gaps`, then execute plans 11-14 to 11-17. Plan 11-13 stops on its precondition while any
ledger row is ROUTED. It runs the final Phase 11 gate once F-01 to F-04 show FIXED, each with its commit and test id.

## Task Commits

1. **Task 1 (tracer): trace data paths and write the finding ledger.** `35a2333` (docs). The tracer gate re-ran the
   `<verify>` green before Task 2.
2. **Task 2: route every finding.** `8db8b6c` (docs).

## Deviations from Plan

None. The plan ran exactly as written, and only the ledger changed.

- **Note on the summary table:** the ledger states its own status counts as prose. Only finding rows carry a severity
  next to a status, so the 11-13 precondition grep matches findings only. The counts table in this SUMMARY is not
  scanned by that gate.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None. The plan added no code. The ledger records the review surface (T-11-34, T-11-37).

## User Setup Required

None.

## Next Phase Readiness

Phase 11 is not ready for Plan 11-13 yet: 4 gaps are routed. Gap closure (`/gsd-plan-phase 11 --gaps`) comes first.

## Self-Check: PASSED

- `.planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md` exists.
- Commits `35a2333` and `8db8b6c` are ancestors of HEAD. Each one changes only the ledger.
- The Task 1 and Task 2 `<verify>` commands pass.
- Gap artifact counts are 4, 5, 3 and 2.
- The Gaps YAML parses with 4 entries.
- No row with a severity is OPEN, and every ROUTED row carries a G-NN id.
