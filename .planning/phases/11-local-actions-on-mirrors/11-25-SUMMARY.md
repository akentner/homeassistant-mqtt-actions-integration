---
phase: 11-local-actions-on-mirrors
plan: 25
subsystem: local-actions
tags: [local-failure-issue, repairs, in-flight-run, regression, tdd, gap-closure]
status: complete

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-19 clear of local_action_failed after a durable save without local actions; 11-24 suite baseline 2111"
provides:
  - "Manager.async_report_local_outcome drops a FAILURE whose current record is missing or has no local actions (WR-06, T-11-64)"
  - "Regression tests for a mute and an emptied additive list saved while a failing run is in flight, a direct late failure, and the bound that keeps real failures (T-11-65)"
  - "Disposition row WR-06 fixed (open 10)"
affects: [phase-11-verification, phase-12-release]

plan_head_before: cad59eb8bc66fee06071f7e708f78e9969086bc9
plan_head_after: d61326d40bbfb209f71ee5bfcfce549c2c948869
actuals:
  tokens: 2200
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A stale outcome of a cancelled run is judged against the record that is current when it arrives, not the one it ran with"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-25-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-25-task1-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - tests/test_local_actions_manager.py
    - .planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md

key-decisions:
  - "A FAILURE outcome is dropped when the current record of its identity has no local actions, exactly like one whose record is gone; a record with actions keeps reporting until a proven success or the removal of its customization (D-19 as amended, owner decision 2026-10-21, WR-06)"

patterns-established:
  - "In-flight race tests hold the runner's outcomes with a listener swap and deliver them after the save, so the order the defect needs does not depend on event loop timing"

requirements-completed: [MIR-05, MIR-13]

coverage:
  - id: D1
    description: "A mute saved while a failing local run of that trigger is in flight leaves no local_action_failed issue after the cancelled run reports"
    requirement: "MIR-05"
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_an_in_flight_failing_run_cannot_reopen_the_issue_after_a_mute_save"
        status: pass
    human_judgment: false
  - id: D2
    description: "An additive record emptied while a failing run is in flight, and a direct late failure for a record without local actions, raise no issue"
    requirement: "MIR-13"
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_an_in_flight_failing_run_cannot_reopen_the_issue_after_emptying_the_additive_actions"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_manager.py#test_failure_outcome_of_a_customization_without_local_actions_raises_no_local_issue"
        status: pass
    human_judgment: false
  - id: D3
    description: "A trigger that still has local actions keeps the failure of its cancelled run"
    requirement: "MIR-13"
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_an_in_flight_failure_still_reports_while_its_trigger_has_local_actions"
        status: pass
    human_judgment: false
---

# Phase 11 Plan 25: In-flight Failure After a Save Without Local Actions Summary

**`async_report_local_outcome` drops a local FAILURE whose current record has no local actions, so a run that was in flight when the user muted or emptied its trigger can no longer re-open `local_action_failed`.**

## Performance

- **Duration:** about 40 min
- **Tasks:** 2 (1 tracer with RED/GREEN, 1 gate and disposition)
- **Files changed:** 3 modified, 2 created (RED evidence)

## Accomplishments

- The FAILURE branch of `Manager.async_report_local_outcome` looks up `_local_record(identity)` once and returns when it is `None` or has no actions. The docstring names the in-flight case (WR-06). The SUCCESS branch and `async_set_local_action` are unchanged.
- Four tests in `tests/test_local_actions_manager.py` plus the constant `IN_FLIGHT_FAILING_ON` and the helpers `_start_in_flight_failing_run`, `_hold_local_outcomes` and `_deliver_held_outcomes`.
- Disposition: WR-01..WR-06 fixed, IN-01..IN-10 open, `open: 10`.

## Task Commits

| Task | Commit | Type | What |
|------|--------|------|------|
| 1 RED | `523c0d5` | test | Four regression tests and the RED evidence `tdd/11-25-task1-red.{json,xml}` |
| 1 GREEN | `ca2782f` | feat | The guard `record is None or not record.actions` in `async_report_local_outcome` |
| 2 | `d61326d` | docs | Disposition row WR-06 fixed, `open: 10` |

## RED semantic assessment

`RED_EVIDENCE_OK` for `test_an_in_flight_failing_run_cannot_reopen_the_issue_after_a_mute_save`. The premises held before the planned assertion: the failing step ran once, the saved ON record has no actions, and exactly one FAILURE was reported by the cancelled run. The assertion then failed because the issue existed (data `kind=switch`, `state_value=on`). That is the WR-06 defect itself, not a setup or collection failure. The emptied-additive test and the direct-outcome test were RED for the same reason; the bound test was green before and after, as intended.

## Guard, bound and flagged assumption

- **Guard:** a FAILURE is reported only while the current record of its identity still has local actions. A removed customization (11-19) and a record without actions (this plan) are dropped the same way, so the two ways to end a customization are no longer asymmetric.
- **Bound:** a save that keeps local actions still lets the cancelled run's failure through (`test_an_in_flight_failure_still_reports_while_its_trigger_has_local_actions`), and the 11-19 tests (T-11-49) stay unchanged and green. Only a proven success of exactly that trigger, a durable save without local actions, or the removal of its customization ends the issue.
- **Flagged assumption (plan):** a failure of a run in flight after a save with other, non-empty local actions still raises the issue, because its actions really failed. Kept and pinned.

## Disposition table

| Finding | Disposition |
|---------|-------------|
| WR-01 .. WR-05 | fixed (unchanged) |
| WR-06 | fixed, plan 11-25, `ca2782f` |
| IN-01 .. IN-10 | open (outside the gap scope the owner set) |

## Verification

- Targeted tests (7 passed) and the local-action tiers (`test_local_actions_manager`, `_lifecycle`, `test_local_parallel`, `test_local_action_plans`, `test_test_buttons`, `test_retrigger`, `test_repairs_flow`): 345 passed.
- Plan check of Task 1 (RED record, guard string, no skip or xfail, test commit touches no production code, `runner.py`, `local_actions.py`, `local_actions_store.py`, `config_flow.py` unchanged): OK.
- Plan check of Task 2 (disposition rows and frontmatter, hash is an ancestor `feat(11-25)` commit): OK.
- Ruff check and format check: clean. README.md and docs/troubleshooting.md unchanged, as planned.
- Baseline from 11-24: 2111 passed, 2 xfailed. This plan adds 4 tests.

Full suite: 2115 passed, 2 xfailed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The in-flight start helper must not call `hass.async_block_till_done()`**
- **Found during:** Task 1 (RED)
- **Issue:** The plan's helper settles with `await hass.async_block_till_done()` in a loop. Home Assistant's `block_till_done` waits for the script run, which is parked in its 30 s delay, so the helper took 30 s per test and the run finished naturally instead of being in flight.
- **Fix:** The helper yields with `await asyncio.sleep(0.01)` up to 50 rounds until `flaky.calls == ["on"]`. The run stays in flight and each test takes about 0.05 s.
- **Files modified:** tests/test_local_actions_manager.py
- **Commit:** 523c0d5

**2. [Rule 3 - Blocking] The save delivers the cancelled run's outcome before it returns, so the plan's probe sequence alone was green**
- **Found during:** Task 1 (RED)
- **Issue:** With a genuinely in-flight run, the rebuild's `async_unload` stops the run and the runner's `finally` hands the FAILURE to the manager during `async_set_local_action`, before the clear that follows the commit. The clear then removes the issue, so the mute test passed on the unfixed code. The reviewer's probe only reproduced because its outcome arrived after the save returned. Which side of the clear the delivery lands on depends on event loop ordering, not on a rule the code enforces.
- **Fix:** `_hold_local_outcomes` swaps the runner's `on_local_outcome` for a list, and `_deliver_held_outcomes` hands the held outcomes to `async_report_local_outcome` after the save. The tests assert as a premise that the real cancelled run reported exactly one FAILURE. This fixes the order the defect needs ("the outcome arrives after the save") without a timing dependency. `IN_FLIGHT_FAILING_ON` and the four test names are as planned.
- **Files modified:** tests/test_local_actions_manager.py
- **Commit:** 523c0d5

**Total deviations:** 2 auto-fixed (both Rule 3, test construction only). **Impact:** none on production code or on the behavior the plan asked for; the guard and its tests match the plan.

## Issues Encountered

None. Running the targeted suites with `-p no:logging` (as the RED command does) shows 3 errors from the lingering-timer check on unrelated tests; the plan's own verify command runs without that flag and is green.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path, file access or schema change.

## User Setup Required

None.

## Next Phase Readiness

Re-verify Phase 11 (`/gsd-verify-work 11`), then Phase 12. The re-verification compares its full-suite count against the `Full suite` line above.

## Self-Check: PASSED

- Files: manager.py, tests/test_local_actions_manager.py, 11-REVIEW-DISPOSITION.md, tdd/11-25-task1-red.json and .xml exist.
- Commits `523c0d5`, `ca2782f` and `d61326d` are ancestors of HEAD.
