---
phase: 10-review-findings-and-native-migration-extraction
plan: 01
subsystem: testing
tags: [core-contracts, registry-flush, ci, github-actions, tdd, fix-01]
status: complete

requires:
  - phase: 09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a
    provides: "takeover.async_flush_registries (WR-01) with its catch-warn-fallback behavior"
provides:
  - "tests/test_core_contracts.py: FLUSH_FALLBACK_HINT and three loud pins of the private registry flush API (behavioral, structural, fallback)"
  - "ci.yml and validate.yml run on every branch push (branches: [\"**\"]) and still skip version tags"
  - "test_push_trigger_runs_branch_pushes_and_skips_version_tags and the rewritten test_ci_and_validate_are_reusable_and_skip_tag_pushes"
affects: [10-07 (FIX-07 pin lands in tests/test_core_contracts.py), every later Phase 10 push (CI now runs on the branch)]

actuals:
  tokens: 2500
  tasks: 2
  commits: 3
plan_head_before: 7163c7d018fdba5d4a05aefbd32ca60e53615fba
plan_head_after: 537d9ccdf1f2877625b76df04a774afc5c43d285

tech-stack:
  added: []
  patterns:
    - "Core-contract pin: behavioral assertion through hass_storage plus a structural hasattr/callable/signature check, both carrying one failure message that names the fallback"
    - "Pin RED by product mutant: apply a temporary mutant, record JUnit RED evidence, revert, confirm git diff --quiet -- custom_components/"

key-files:
  created:
    - tests/test_core_contracts.py
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-01-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-01-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-01-task2-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-01-task2-red.json
  modified:
    - tests/test_repo_structure.py
    - .github/workflows/ci.yml
    - .github/workflows/validate.yml
    - .planning/todos/completed/2026-10-12-ci-push-trigger-branches.md (moved from pending/)

key-decisions:
  - "The behavioral flush pin restores the real Store.async_save on PHACC's StoreWithoutWriteLoad (the harness stub of the entity registry store); the registry, its _store and its _data_to_save stay as core made them"
  - "The structural pin loops over both registries in one test instead of parametrizing, so the module keeps exactly three tests"

patterns-established:
  - "tests/test_core_contracts.py is the single home of core-internals pins; never skipped, never xfail, no marker (D-08)"

requirements-completed: [FIX-01]

coverage:
  - id: D1
    description: "A core change that removes or breaks the private registry flush fails the suite loudly with FLUSH_FALLBACK_HINT"
    requirement: FIX-01
    verification:
      - kind: unit
        ref: "tests/test_core_contracts.py#test_the_registry_flush_writes_both_registries_ahead_of_the_scheduled_save"
        status: pass
      - kind: unit
        ref: "tests/test_core_contracts.py#test_the_private_registry_flush_api_still_exists"
        status: pass
    human_judgment: false
  - id: D2
    description: "A refused early write returns False, logs one count-free warning and the scheduled save still writes the row (D-05)"
    requirement: FIX-01
    verification:
      - kind: unit
        ref: "tests/test_core_contracts.py#test_a_refused_early_write_falls_back_to_the_scheduled_save"
        status: pass
    human_judgment: false
  - id: D3
    description: "CI and Validate declare branches [\"**\"] next to tags-ignore v*.*.*; release.yml stays tag-only"
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_push_trigger_runs_branch_pushes_and_skips_version_tags"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_ci_and_validate_are_reusable_and_skip_tag_pushes"
        status: pass
    human_judgment: false
  - id: D4
    description: "A real branch push on GitHub creates CI and Validate runs with event push; a v*.*.* tag push creates none directly"
    human_judgment: true
    rationale: "Needs the owner's push to GitHub; Claude never pushes"

duration: 8 min
completed: 2026-10-16
---

# Phase 10 Plan 01: Loud registry-flush pins and CI on branch pushes Summary

**Three never-skipped core-contract pins prove `takeover.async_flush_registries` writes both registries into storage at once, and `branches: ["**"]` in ci.yml and validate.yml makes branch pushes run CI again.**

## Performance

- **Duration:** about 8 min
- **Started:** 2026-10-16T12:17Z
- **Completed:** 2026-10-16T12:25Z
- **Tasks:** 2
- **Files modified:** 4 source/test/workflow files, plus the todo move and 4 TDD records

## Accomplishments

- `tests/test_core_contracts.py` (new): module docstring with the D-08 rule, `FLUSH_FALLBACK_HINT`, and three pins:
  - `test_the_registry_flush_writes_both_registries_ahead_of_the_scheduled_save`: the flush returns True, and with no time advanced both new rows are in `hass_storage["core.entity_registry"]` and `hass_storage["core.device_registry"]` (D-06)
  - `test_the_private_registry_flush_api_still_exists`: both registries have `_store` with a callable `async_save`, and a callable `_data_to_save` with no required parameter (Pitfall 9, structural half)
  - `test_a_refused_early_write_falls_back_to_the_scheduled_save`: `OSError("refused")` from the entity store gives False and exactly one integration WARNING with no entity id and no "flush-pin" in it; the row reaches storage after 11 s of fired time (D-05)
- CI and Validate trigger on every branch push again, and version tags still skip them (they run only through release.yml)
- Todo `2026-10-12-ci-push-trigger-branches` moved to `.planning/todos/completed/`

## Task Commits

1. **Task 1 (tracer): pin the private registry flush API** - `95f8c35` (test)
2. **Task 2 RED: rewritten trigger tests** - `845710a` (test)
3. **Task 2 GREEN: branch filter in both workflows** - `537d9cc` (fix)

## TDD / RED evidence

- **Task 1 RED** (`tdd/10-01-task1-red.json`, `tdd/10-01-task1-red.xml`, RED_EVIDENCE_OK): target `test_the_registry_flush_writes_both_registries_ahead_of_the_scheduled_save`. **Mutant:** in `custom_components/mqtt_actions/takeover.py` the call `registry._data_to_save()` was changed temporarily to `registry._data_to_save_renamed()`, which stands for a core rename. The flush caught the AttributeError and returned False, so the pin failed on `is True` and printed FLUSH_FALLBACK_HINT. The mutant was reverted with `git checkout`, `git diff --quiet -- custom_components/` passed, and the mutant was never committed. `takeover.py` keeps its last commit `e33a631` from before this plan.
- **Task 1, "stops writing" case:** the first run without the store restore (see Deviations) showed that the hass_storage assertion catches a store that returns but writes nothing. `async_flush_registries` returned True, but the entity row never reached storage, and the pin failed with FLUSH_FALLBACK_HINT.
- **Task 2 RED** (`tdd/10-01-task2-red.json`, `tdd/10-01-task2-red.xml`, RED_EVIDENCE_OK): target `test_ci_and_validate_are_reusable_and_skip_tag_pushes`. It failed with "ci.yml never runs for a branch push". The parametrized `[ci.yml]` and `[validate.yml]` cases failed on the same assertion and `[release.yml]` passed (3 failed, 1 passed).
- **GREEN:** `537d9cc` adds exactly two lines (2/0 numstat), one per workflow.

## Rewritten repo-structure tests (on purpose)

- `test_push_trigger_has_no_branch_filter` is replaced by `test_push_trigger_runs_branch_pushes_and_skips_version_tags[validate.yml, ci.yml, release.yml]`. ci.yml and validate.yml need `branches == ["**"]`, no `branches-ignore`, and `v*.*.*` in `tags-ignore`. release.yml needs no branch filter and `v*.*.*` in `tags`.
- `test_ci_and_validate_are_reusable_and_skip_tag_pushes` now requires `branches == ["**"]` where it used to require that the key was absent.
- Reason (in both docstrings): GitHub Actions never runs a push filter with only `tags-ignore` for a branch push. Because of that, no branch push has run CI or Validate since 2f786d8, and the old tests pinned that bug.

## Decisions Made

- The behavioral pin undoes only PHACC's harness stub (`StoreWithoutWriteLoad.async_save` set back to `storage.Store.async_save`). Core's registry objects stay untouched, so a core rename of `_store` or `_data_to_save` still fails the pin.
- The structural check loops over both registries inside one test, so `pytest -q tests/test_core_contracts.py` reads `3 passed` as the plan requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] PHACC's entity registry store does not write on async_save**
- **Found during:** Task 1
- **Issue:** The PHACC `hass` fixture builds the entity registry on `StoreWithoutWriteLoad`, whose `async_save` does nothing. The device registry gets a real store because it is set up before the patch. So the planned hass_storage assertion could never see the entity row: the flush returned True and the entity key stayed missing.
- **Fix:** Added the helper `_restore_real_registry_saves(monkeypatch)`. It sets `StoreWithoutWriteLoad.async_save` back to the real `storage.Store.async_save` for the behavioral pin only. The fallback test does not need it: scheduled saves go through `async_delay_save`, which PHACC does not stub.
- **Files modified:** tests/test_core_contracts.py
- **Commit:** 95f8c35

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact:** The test harness changed, not the product. It makes D-06's "immediate write through hass_storage" observable as intended.

## Issues Encountered

None beyond the deviation above.

## Gate

- `uv run ruff check .`: all checks passed
- `uv run ruff format --check .`: 95 files already formatted
- `uv run pytest -q`: 1730 passed, 2 xfailed in about 128 s (baseline 1727 + 3 new pins)
- `git diff 7163c7d HEAD -- custom_components/` is empty; `release.yml` is unchanged since 6263692; HEAD is on the phase branch; `main` is still `601a41c`

## Owner Follow-up

- Push the phase branch `gsd/phase-10-review-findings-and-native-migration-extraction` and confirm that CI and Validate each create a run with event `push`.
- At the next `v*.*.*` tag, confirm that no direct CI or Validate run starts (only release.yml).
- The owner may delete the leftover branch `ci/v1.0.1-bump` on origin (from the todo).

## Next Phase Readiness

Ready for 10-02. Every later Phase 10 commit that gets pushed now runs CI, so the new pins are part of the signal.

## Self-Check: PASSED

- FOUND: tests/test_core_contracts.py, tdd/10-01-task1-red.{xml,json}, tdd/10-01-task2-red.{xml,json}, .planning/todos/completed/2026-10-12-ci-push-trigger-branches.md
- FOUND commits on HEAD: 95f8c35, 845710a, 537d9cc
- Both RED records: RED_EVIDENCE_OK
