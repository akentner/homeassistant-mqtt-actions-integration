---
phase: 11-local-actions-on-mirrors
plan: 17
subsystem: manager
tags: [adoption, circuit-breaker, rollback, local-actions, gap-closure, tdd]
status: complete

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-11 ledger finding F-04 / gap G-04; 11-14 adoption rollback that restores local records and keeps the local failure issue; 11-16 F-03 FIXED"
provides:
  - "_async_adopt_locked snapshots the tripped hash before _async_drop_mirror"
  - "_async_restore_adopted_mirror puts the trip back before sync.async_restore_mirror and saves the main Store right after it"
  - "Regression test tests/test_local_actions_lifecycle.py::test_failed_adoption_keeps_a_tripped_breaker_paused (two failed adoptions in a row)"
  - "Ledger row F-04 FIXED, gap G-04 resolved; no OPEN or ROUTED findings row left"
affects: [11-13 final gate precondition]

actuals:
  tokens: 6967
  tasks: 2
  commits: 3
plan_head_before: 09882665da9519c406473945ceeec697a66cb092
plan_head_after: 8819ed1611ef11c8afeb090b33dda6952d48c02a

tech-stack:
  added: []
  patterns:
    - "A rollback that restores a mirror through the ingest path puts back the per-device runtime keys the drop popped before the rebuild, so the build hooks (_restore_tripped) see them"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-17-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-17-task1-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - tests/test_local_actions_lifecycle.py
    - .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md

key-decisions:
  - "G-04: a failed adoption restores the tripped hash before the mirror rebuild, so _restore_tripped pauses the restored mirror and raises its circuit_breaker issue (MIR-09, Phase 2 D-17, T-11-46)"
  - "G-04: the trip is saved right after sync.async_restore_mirror, not before it, because async_start keeps a trip only for an id among the stored mirrors; one save carries both. An untripped rollback adds no trip and no save"
  - "G-04: the trip handling sits in a new helper _async_restore_adopted_mirror, so _async_adopt_locked stays within Ruff PLR0912 without a noqa"

patterns-established:
  - "Run tests/test_services.py without -p no:logging (its caplog fixture needs the logging plugin); -p no:logging stays for the RED target node only"

requirements-completed: [MIR-09]

coverage:
  - id: D1
    description: "A failed adoption of a tripped mirror leaves it paused with its breaker issue, the trip in the main Store at once, and a new ON edge runs nothing; also after a second failed adoption"
    requirement: MIR-09
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_failed_adoption_keeps_a_tripped_breaker_paused"
        status: pass
    human_judgment: false
  - id: D2
    description: "An untripped mirror's rollback is unchanged and the existing adoption suites pass"
    requirement: MIR-09
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_adoption_subentry_failure_restores_mirror_and_records_and_publishes_nothing"
        status: pass
      - kind: command
        ref: "uv run pytest -q tests/test_local_actions_lifecycle.py tests/test_local_actions_manager.py tests/test_multi_instance_ops.py tests/test_services.py (161 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ledger row F-04 FIXED with 8eb4734 and the test id; no OPEN or ROUTED row; full required-broker suite green"
    requirement: MIR-09
    verification:
      - kind: command
        ref: "Task 2 ledger verify command and 11-13 precondition grep (LEDGER_OK)"
        status: pass
      - kind: command
        ref: "MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q (2072 passed, 2 xfailed)"
        status: pass
    human_judgment: false

duration: 7 min
completed: 2026-10-21
---

# Phase 11 Plan 17: Failed adoption keeps a tripped breaker Summary

**A failed adoption now puts the tripped hash back before the mirror rebuild and saves it together with the mirror payload, so a paused mirror stays paused with its breaker issue (G-04 / F-04 closed, ledger has no routed finding left).**

## Performance

- **Duration:** about 7 min
- **Started:** 2026-10-21T04:49:15Z
- **Completed:** 2026-10-21T04:56Z
- **Tasks:** 2
- **Files modified:** 3 (plus 2 RED evidence files created)

## Accomplishments

- `Manager._async_adopt_locked` (custom_components/mqtt_actions/manager.py:1478-1479) reads `tripped = self._tripped.get(device_id)` before `_async_drop_mirror` pops it.
- The rollback branch calls the new `_async_restore_adopted_mirror(device_id, payload, tripped)` (manager.py:1533-1546). The helper:
  - puts the hash back into `_tripped` before `sync.async_restore_mirror`, so `_build_mirror` -> `_restore_tripped` trips the rebuilt breaker and raises `circuit_breaker_<id>`;
  - saves the main Store right after the restore, only when a trip was restored.
- `_async_drop_mirror`, `_restore_tripped`, `release_all_breakers` and the success path are unchanged.
- Ledger row F-04 is FIXED (`G-04 fixed in 8eb4734`), the G-04 YAML is `status: resolved`, and the summary reads 0 routed and 4 fixed. The 11-13 precondition grep succeeds.

## TDD cycle

- **RED** (`4d32927`): `test_failed_adoption_keeps_a_tripped_breaker_paused`. Setup:
  - the adoptable mirror is approved, its owner is offline, and its ON replacement runs `test.local_on`;
  - live OFF/ON edges trip the safe breaker (5 runs in 10 s). The premise asserts the trip and the breaker issue.
  - Then `async_add_subentry` raises RuntimeError twice in a row.
  - Evidence `tdd/11-17-task1-red.{json,xml}`: `RED_EVIDENCE_OK` (junit, 1 test, 1 failure, 0 errors).
  - **Semantic assessment:** a valid RED. The target ran, and setup and the trip premise passed. The failure is the first assertion after the failed adoption, the planned one on the restored breaker (`tripped=False`, "attempt 1: the restored mirror stays paused", test file line 802). That is the G-04 defect itself, not a setup, import, fixture or unrelated failure.
- **GREEN** (`8eb4734`): the snapshot plus the helper above. The target passes, and so do the four adoption-related modules (161 passed).
- **REFACTOR:** none needed.

## Task Commits

1. **Task 1 RED:** `4d32927` test(11-17): add failing test for a failed adoption that releases a tripped breaker
2. **Task 1 GREEN:** `8eb4734` feat(11-17): keep a tripped breaker paused when an adoption fails
3. **Task 2:** `8819ed1` docs(11-17): set ledger row F-04 to FIXED and resolve gap G-04

## Final ledger counts

- 0 open, 0 routed, 4 fixed (F-01 6f381cb, F-02 44c5fe6, F-03 c9c9c63, F-04 8eb4734), 16 no-change (F-05 to F-20).
- By severity: 0 Critical, 0 High, 0 Medium, 4 Low, 16 Info.
- The final-gate and Phase 12 boundary sections are left to Plan 11-13. No other row changed.

## Verification

- Target: `1 passed`.
- Adoption suites (`tests/test_local_actions_lifecycle.py`, `tests/test_local_actions_manager.py`, `tests/test_multi_instance_ops.py`, `tests/test_services.py`): `161 passed`.
- Task 1 evidence check: RED_EVIDENCE_OK; no skip/xfail markers; the test commit touches no `custom_components/`; `sync.py` and `const.py` are unchanged.
- `uv run ruff check .` and `uv run ruff format --check .`: clean.
- `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`: `2072 passed, 2 xfailed`. Nothing deselected or skipped, and 2072 is above the 2056 baseline.
- Task 2 ledger check: LEDGER_OK. 16 rows still read Info NO-CHANGE.

## Decisions Made

See `key-decisions` in the frontmatter. The main one: the trip is saved after the restore, not before it (see Deviations).

## Deviations from Plan

### Planned deviation (stated in the plan objective)

**Save after the restore, not before it.**
- The ledger wording says to save the trip "before the mirror is restored". The save runs right after `sync.async_restore_mirror` instead.
- Reason: `async_start` keeps `_tripped` only for ids among the stored mirrors (manager.py:960). A save made before the restore lacks the mirror payload, so a stop before the delayed mirror save would drop the trip.
- The hash itself still goes back before the restore, because `_restore_tripped` needs it.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff PLR0912 on `_async_adopt_locked`**
- **Found during:** Task 1 GREEN.
- **Issue:** two inline `if tripped is not None` branches raised the method to 13 branches, over Ruff's limit of 12. The project has no `PLR0912` noqa precedent.
- **Fix:** the trip restore and the save went into the new helper `_async_restore_adopted_mirror`, which wraps the existing `sync.async_restore_mirror` call. The behavior is as planned, and the rollback branch makes one call where it made one before.
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Commit:** 8eb4734

**2. [Process] RED evidence committed with the test**
- The plan says "commit `test(11-17)` with the test file only". The RED evidence JSON/XML went into the same commit, following the 11-16 precedent (`c5c8d5a`).
- No production file is in it, and the Task 1 verify (test commit touches no `custom_components/`) passes.

**Total deviations:** 1 planned, 1 auto-fixed (Rule 3), 1 process note. **Impact:** none on behavior. The rollback contract is exactly as planned.

## Issues Encountered

- The first suite run used `-p no:logging` and produced 5 setup errors in `tests/test_services.py` (`recursive dependency involving fixture 'caplog'`). The flag disables the caplog fixture; the code is not the cause. The plan's verify command, without the flag, gives 161 passed.

## Known Stubs

None.

## Next Phase Readiness

- Every routed finding is fixed. Next step: execute Plan 11-13 (final Phase 11 gate). Its precondition holds.

## Self-Check: PASSED

- FOUND: tdd/11-17-task1-red.json, tdd/11-17-task1-red.xml, custom_components/mqtt_actions/manager.py, tests/test_local_actions_lifecycle.py
- FOUND commits: 4d32927, 8eb4734, 8819ed1 (all ancestors of HEAD)
- TDD gates: test(11-17) 4d32927 precedes feat(11-17) 8eb4734
