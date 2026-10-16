---
phase: 10-review-findings-and-native-migration-extraction
plan: 06
subsystem: testing
tags: [fix-04, review-1-in-03, duplicate-guard, pin-tests, tdd, spy]
status: complete

requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-04 (NativeMigration in native_migration.py calls takeover.disable_duplicates through the module)"
provides:
  - "tests/test_export_guard_receiver.py: helper _spy_disable_duplicates(monkeypatch) -> list[tuple[str, int]]"
  - "G4 guard test proves the listener ran and returned 0 for a second create event, and the start-up sweep ran and returned 0 after a restart"
affects: [10-07 to 10-10 (guard tests now see a silently skipped listener or sweep), 11 (MIR-01)]

actuals:
  tokens: 918
  tasks: 2
  commits: 2
plan_head_before: cd7a3eac7a5dcbbeb99f9a9bf9962863778dfac3
plan_head_after: 02483eae41bc000a602835d0b25076adcfa18587

tech-stack:
  added: []
  patterns:
    - "Spy on a module function at the stable seam (takeover.disable_duplicates): wrap the original, record (key, result), return the result; the spy does not depend on where the orchestration lives"

key-files:
  created:
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-06-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-06-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-06-task2-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-06-task2-red.json
  modified:
    - tests/test_export_guard_receiver.py

key-decisions:
  - "FIX-04 spies on takeover.disable_duplicates (module seam) rather than on a NativeMigration method, so the pin survives any later move of the orchestration"
  - "The spy is installed after the duplicate is removed and right before the second create event, so the recorded list holds only the listener pass of that event: exactly [(device_id, 0)]"
  - "The restart part asserts (device_id, 0) in passes plus all results 0 (at least one sweep call, none disables), not an exact list, because the start-up path may legitimately pass over the device more than once"

patterns-established:
  - "Pin a repeat path that changes nothing by proving it ran (spy records the call) and found nothing (result 0), not only by the unchanged end state"

requirements-completed: [FIX-04]

coverage:
  - id: D1
    description: "The second create event of the G4 guard test records exactly one guard pass for the device, returning 0; RED against a listener mutant that skips rows created disabled"
    requirement: FIX-04
    verification:
      - kind: unit
        ref: "tests/test_export_guard_receiver.py#test_a_second_pass_a_second_create_event_and_a_restart_change_nothing"
        status: pass
      - kind: other
        ref: "node ~/.claude/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-06-task1-red.json --raw"
        status: pass
    human_judgment: false
  - id: D2
    description: "The restart part of the same test records at least one start-up sweep pass for the device and every pass returns 0; RED against a mutant without the initial sweep in arm_duplicate_guard"
    requirement: FIX-04
    verification:
      - kind: unit
        ref: "tests/test_export_guard_receiver.py#test_a_second_pass_a_second_create_event_and_a_restart_change_nothing"
        status: pass
      - kind: other
        ref: "node ~/.claude/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-06-task2-red.json --raw"
        status: pass
    human_judgment: false
  - id: D3
    description: "No product change, no assertion removed; full gate green"
    verification:
      - kind: other
        ref: "git diff --quiet cd7a3ea HEAD -- custom_components/; uv run ruff check .; uv run ruff format --check .; uv run pytest -q (1739 passed, 2 xfailed)"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-10-16
---

# Phase 10 Plan 06: Guard Test Proves the Listener and the Sweep Ran Summary

**A spy on `takeover.disable_duplicates` makes the G4 guard test prove that the listener ran for a second create event and the start-up sweep ran after a restart, each returning 0. Before, the test only showed that the registry restored the disabled state (review 1 IN-03, FIX-04).**

## Performance

- **Duration:** about 5 min
- **Started:** 2026-10-16T13:52:19Z
- **Completed:** 2026-10-16T13:57:05Z
- **Tasks:** 2
- **Files modified:** 1 test module (plus 4 RED records)

## Accomplishments

- `_spy_disable_duplicates(monkeypatch)` sits next to `_count_disables`. It wraps `takeover.disable_duplicates` on the module, calls the original, records `(device_id, result)` and returns the result.
- Second create event: the spy goes in right before `_core_creates_the_row`. The test then asserts `passes == [(spec.device_id, 0)]`, with the message "the guard's listener did not run for the second create event".
- Restart: `passes.clear()` runs before `restart_entry`. After the restart the test asserts that `(spec.device_id, 0)` is recorded and that every recorded result is 0. `calls == [duplicate.entity_id]` still holds.
- Both checks were shown to fail first against named temporary mutants. The old assertions passed under each mutant. Both mutants were reverted, and `custom_components/` is unchanged.

## TDD / RED evidence (pin rule, no product change)

| Task | Mutant (temporary, reverted, never committed) | Old assertions under the mutant | New assertion | Record |
|------|-----------------------------------------------|---------------------------------|---------------|--------|
| 1 | `NativeMigration._on_duplicate_registry_updated`: `if entry.disabled_by is not None: return` right after the `entry is None` check | HEAD `cd7a3ea` test file: 1 passed | `assert [] == [(<id>, 0)]` at line 444, "the guard's listener did not run for the second create event" | `tdd/10-06-task1-red.json`: RED_EVIDENCE_OK |
| 2 | `NativeMigration.arm_duplicate_guard`: the initial `self._disable_duplicates(self._duplicate_guard_ids())` removed, listener still armed | HEAD `8e8c9d7` test file (Task 1 version): 1 passed | `assert (<id>, 0) in []` at line 451, "the guard's sweep did not run for the device at the next start" | `tdd/10-06-task2-red.json`: RED_EVIDENCE_OK |

- **Task 1 RED semantic assessment:** The target ran (1 test, 1 failure, 0 errors) and failed on the new spy assertion. The cause was the listener mutant: it skips the row that core creates again, disabled, from its `integration` record. That is the silent skip IN-03 names. No import, collection or fixture fault.
- **Task 2 RED semantic assessment:** The target ran (1 test, 1 failure, 0 errors) and failed on the new restart assertion. The cause was the mutant without the sweep. Under it, the Task 1 listener check and the old restart assertion still passed. No import, collection or fixture fault.
- GREEN: this is a pin plan, so there is no `feat`/`fix` commit. The tests pass against the unchanged product code, which is the GREEN state (Phase 10 execution rules, pin tests).

## Task Commits

1. **Task 1 (tracer): the guard test proves the listener ran and returned 0 for a second create event**: `8e8c9d7` (test)
2. **Task 2: the restart part proves the start-up sweep ran and returned 0**: `02483ea` (test)

**Plan metadata:** see the docs(10-06) commit that adds this SUMMARY and the RED records.

## Files Created/Modified

- `tests/test_export_guard_receiver.py`: `takeover` import, the `_spy_disable_duplicates` helper, the spy assertions and two docstring sentences in `test_a_second_pass_a_second_create_event_and_a_restart_change_nothing`
- `.planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-06-task{1,2}-red.{xml,json}`: JUnit reports and RED records of both mutant runs

## Decisions Made

- The spy targets the module seam `takeover.disable_duplicates`. `NativeMigration._disable_duplicates` resolves it through the module at call time, so the spy does not depend on where the orchestration lives (planned).
- The restart check is "at least one pass for the device, every result 0", not an exact list. This follows the plan's behavior block: the sweep may visit the device more than once at start-up without being wrong.

## Deviations from Plan

None. The plan was executed exactly as written.

## Issues Encountered

None. Tracer feedback gate: the run was interactive in `end-of-phase` mode and the tracer verify was automated-only. Both verify commands were re-run and passed before Task 2 started.

## Verification

- `uv run pytest -q tests/test_export_guard_receiver.py -k second_create_event`: 1 passed
- `uv run pytest -q tests/test_export_guard_receiver.py`: 15 passed
- Task 1 verify chain (helper present, `custom_components/` clean against the first `test(10-06)` parent, Ruff, RED_EVIDENCE_OK): passed
- No assertion removed. Capture-then-grep `^-\s+assert` on both commit diffs prints nothing.
- Full gate: `uv run ruff check .` clean, `uv run ruff format --check .` clean, `uv run pytest -q`: 1739 passed, 2 xfailed (same as the 10-05 baseline; no test added, two tests strengthened)

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- FIX-04 is closed. Ready for plan 10-07 (FIX-07 eager-task pin in `tests/test_core_contracts.py`).
- No blockers.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*

## Self-Check: PASSED

- FOUND: tests/test_export_guard_receiver.py (contains `_spy_disable_duplicates`)
- FOUND: tdd/10-06-task1-red.xml, tdd/10-06-task1-red.json, tdd/10-06-task2-red.xml, tdd/10-06-task2-red.json
- FOUND: 8e8c9d7, 02483ea (ancestors of HEAD)
