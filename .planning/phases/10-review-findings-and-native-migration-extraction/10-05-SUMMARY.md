---
phase: 10-review-findings-and-native-migration-extraction
plan: 05
subsystem: native-migration
tags: [fix-06, review-2-in-01, replay-catch, takeover, error-path, tdd, pin-tests]
status: complete

requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-04 (NativeMigration in native_migration.py owns the replay catch and _remove_replay_twins)"
provides:
  - "takeover.ReplayTwinsError(removed): raised by remove_replay_twins when a row raised, chained from the original error"
  - "remove_replay_twins error path: stops at the failing row, still removes an emptied core MQTT device, logs the count of the rows before it"
  - "native_migration.TwinRemoval(removed, errored); _async_replay_catch flushes on removed or errored"
affects: [10-06 to 10-10 (native_migration.py carries TwinRemoval), 11 (MIR-01)]

actuals:
  tokens: 5564
  tasks: 2
  commits: 3
plan_head_before: c2a8d9961dc4fa98da2985f477a28ad795c9200d
plan_head_after: e48d74d9eac2a663293fd42a47d33113bebf2200

tech-stack:
  added: []
  patterns:
    - "A per-item loop that must not hide a failure finishes its cleanup and count, then raises a typed error carrying the partial count, chained from the cause; the caller isolates per item and adds the count"
    - "A caller result as a NamedTuple (count, errored) so a flush can run on a partial or failed pass"

key-files:
  created:
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task2-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task2-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task2-red-partial-count.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task2-red-partial-count.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task2-red-precision.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-05-task2-red-precision.json
  modified:
    - custom_components/mqtt_actions/takeover.py
    - custom_components/mqtt_actions/native_migration.py
    - tests/test_native_replay.py
    - tests/test_takeover.py

key-decisions:
  - "remove_replay_twins stops at the first failing row, finishes the emptied-device cleanup and the count line, then raises ReplayTwinsError(removed) from the original error; it never catches and returns a number (Pitfall 16)"
  - "NativeMigration._remove_replay_twins returns TwinRemoval(removed, errored); the replay catch flushes on removed or errored; the takeover path keeps ignoring the result because its own flush runs whenever a takeover is DONE"
  - "The removal loop moved into the private helper takeover._remove_planned (returns count and error) to keep remove_replay_twins under Ruff's branch limit; no change to the candidate selection or the CR-01 / 09.2 gate rules"

patterns-established:
  - "Error path with partial count: cleanup and count first, then a typed raise chained from the cause"

requirements-completed: [FIX-06]

coverage:
  - id: D1
    description: "A row that raises after its removal in the replay catch leaves no emptied core MQTT device, the count line reports the rows before it, one count-free WARNING is logged and the registries are flushed"
    requirement: FIX-06
    verification:
      - kind: integration
        ref: "tests/test_native_replay.py#test_a_row_that_raises_mid_loop_in_the_catch_leaves_no_emptied_device_and_keeps_the_count"
        status: pass
    human_judgment: false
  - id: D2
    description: "A raise on the first row before its removal logs no count line, still flushes and keeps the device with all three integration-disabled rows"
    requirement: FIX-06
    verification:
      - kind: integration
        ref: "tests/test_native_replay.py#test_a_raise_on_the_first_row_still_flushes_and_keeps_the_device"
        status: pass
    human_judgment: false
  - id: D3
    description: "remove_replay_twins raises ReplayTwinsError chained from the RuntimeError with removed == the rows whose removal returned, removes the emptied device, and never counts the row that raised"
    requirement: FIX-06
    verification:
      - kind: integration
        ref: "tests/test_takeover.py#test_remove_replay_twins_raises_with_the_partial_count_after_removing_the_emptied_device"
        status: pass
      - kind: integration
        ref: "tests/test_takeover.py#test_remove_replay_twins_counts_only_rows_whose_removal_returned"
        status: pass
    human_judgment: false
  - id: D4
    description: "No regression: full suite, Ruff check and Ruff format green; CR-01, 09.2 and start-up order tests unchanged"
    verification:
      - kind: other
        ref: "uv run ruff check . && uv run ruff format --check . && uv run pytest -q (1739 passed, 2 xfailed)"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-16
---

# Phase 10 Plan 05: Partial Failure of the Replay-Twin Removal Summary

**`takeover.remove_replay_twins` now finishes its emptied-device cleanup and count line before it raises `ReplayTwinsError(removed)` from the failing row's error, and the replay catch flushes on `TwinRemoval(removed, errored)`, so a mid-loop registry failure no longer strands an emptied core MQTT device or skips the flush (FIX-06, review 2 IN-01).**

## Performance

- **Duration:** about 7 min
- **Started:** 2026-10-16T13:42:25Z
- **Completed:** 2026-10-16T13:49:26Z
- **Tasks:** 2
- **Files modified:** 4 source/test files plus 8 RED evidence files

## Accomplishments

- `class ReplayTwinsError(Exception)` in `takeover.py`, with `removed` and a fixed message without entity data. The original error is the `__cause__`.
- The error path of `remove_replay_twins`: the plan loop (now `_remove_planned`) stops at the first row that raises. When the plan was not empty, the core MQTT device still goes if nothing is left on it. The single INFO line `Removed %d duplicate entities that a replayed legacy discovery created` is logged when the count is above 0. Then the error is raised, or the count is returned. Without a raise, the behavior, return value and log lines are unchanged.
- `class TwinRemoval(NamedTuple)` in `native_migration.py`. `_remove_replay_twins` catches `takeover.ReplayTwinsError` first: it adds `err.removed`, sets `errored`, logs the existing WARNING and logs DEBUG with `type(err.__cause__).__name__`. Any other `Exception` sets `errored` as before. Each device is still handled on its own (Pitfall 16). `_async_replay_catch` flushes on `removal.removed or removal.errored`.

## Task Commits

1. **Task 1 (tracer): a row that raises after its removal in the catch.** RED `87034e3` (test), GREEN `7ec5e95` (fix)
2. **Task 2: the boundaries and the count contract.** `e48d74d` (test, three pins, fail-first proven with named mutants)

**Plan metadata:** see the docs commit that follows

## TDD Records

| Record | Target test | How it went red | Verdict |
|--------|-------------|-----------------|---------|
| `tdd/10-05-task1-red.{xml,json}` | `test_a_row_that_raises_mid_loop_in_the_catch_leaves_no_emptied_device_and_keeps_the_count` | Real RED on the 10-04 code: `mqtt_device_of(...) is None` failed because the emptied device stayed | RED_EVIDENCE_OK |
| `tdd/10-05-task2-red.{xml,json}` | `test_a_raise_on_the_first_row_still_flushes_and_keeps_the_device` | Pin. Mutant: `if removal.removed or removal.errored:` changed to `if removal.removed:` in `_async_replay_catch`. Result: `assert flushes` failed (no flush) | RED_EVIDENCE_OK |
| `tdd/10-05-task2-red-partial-count.{xml,json}` | `test_remove_replay_twins_raises_with_the_partial_count_after_removing_the_emptied_device` | Pin. Mutant: in `_remove_planned`, `removed += 1` moved before `entity_registry.async_remove(...)`. Result: `assert 3 == 2` | RED_EVIDENCE_OK |
| `tdd/10-05-task2-red-precision.{xml,json}` | `test_remove_replay_twins_counts_only_rows_whose_removal_returned` | Pin. Same count-before-removal mutant. Result: `assert 2 == 1` | RED_EVIDENCE_OK |

How each RED was checked:
- Every target ran and failed on its planned assertion. The setup and premise assertions passed, so no RED came from an import, collection or fixture error.
- Each mutant was reverted with `git checkout -- <file>`, and `git diff --quiet -- custom_components/` passed afterwards.
- No mutant was committed.

## Files Created/Modified

- `custom_components/mqtt_actions/takeover.py`: `ReplayTwinsError`, `_remove_planned`, and the error path and docstring of `remove_replay_twins`
- `custom_components/mqtt_actions/native_migration.py`: `TwinRemoval`, the `_remove_replay_twins` result and its `ReplayTwinsError` branch, and the flush condition of the catch
- `tests/test_native_replay.py`: the helpers `_fail_a_replayed_removal`, `_count_flushes`, `_own_records`, `_assert_no_entity_data_logged`, and two FIX-06 catch tests
- `tests/test_takeover.py`: the helper `_fail_a_removal` and two FIX-06 takeover-level tests

## Decisions Made

- These follow the plan's decisions: a typed raise that carries the count across the boundary, and a `TwinRemoval` NamedTuple as the result.
- The takeover path still ignores the result, because its flush already runs on any DONE takeover or exception.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extracted the removal loop into `takeover._remove_planned`**
- **Found during:** Task 1 GREEN
- **Issue:** Ruff PLR0912 (too many branches, 14 > 12) on `remove_replay_twins` after the try/except was added inline.
- **Fix:** Moved the plan loop with its try/except into the private helper `_remove_planned(entity_registry, plan) -> tuple[int, Exception | None]`. The loop body and its WR-01 comment are unchanged.
- **Files modified:** `custom_components/mqtt_actions/takeover.py`
- **Verification:** Ruff clean. The INFO text appears exactly once in `takeover.py`. The full suite is green.
- **Committed in:** `7ec5e95`

**2. [Naming] Three Task 2 RED records instead of one**
- **Found during:** Task 2
- **Issue:** All three Task 2 tests were green on the Task 1 code and needed two different mutants. The plan allows one record per test.
- **Fix:**
  - `10-05-task2-red.{xml,json}` holds the first-row test.
  - `-partial-count` and `-precision` hold the two takeover tests.
- **Committed in:** the plan docs commit

**3. [Test helper placement] `_fail_a_removal` duplicated in `tests/test_takeover.py`**
- **Issue:** `tests/helpers.py` is not in `files_modified`, so the removal wrapper could not be shared there.
- **Fix:** Added a small copy in `tests/test_takeover.py` that also returns the call order, which the precision test needs to name the second and third rows.

---

**Total deviations:** 3 (1 Rule 3 blocking, 2 naming/placement)
**Impact on plan:** None on behavior. The candidate selection and the CR-01, 09.2 and D-08 rules are untouched.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- Ready for 10-06.
- Baseline after 10-05: `uv run pytest -q` gives 1739 passed, 2 xfailed. Ruff check and format are green.

## Self-Check: PASSED

- The modified files exist: takeover.py, native_migration.py, test_native_replay.py, test_takeover.py.
- The 8 RED evidence files exist in `tdd/`.
- Commits `87034e3`, `7ec5e95` and `e48d74d` are ancestors of HEAD.
- All 4 RED records return RED_EVIDENCE_OK.
- `git diff --quiet -- custom_components/` passes.
- Ruff check and format are green. The full suite has 1739 passed, 2 xfailed.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*
