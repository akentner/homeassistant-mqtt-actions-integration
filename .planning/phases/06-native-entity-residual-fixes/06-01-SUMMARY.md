---
phase: 06-native-entity-residual-fixes
plan: 01
subsystem: sync
tags: [home-assistant, mqtt, store, native-entities, tdd]

requires:
  - phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
    provides: native mirrors (D-07, D-09), the marker in a config document, NativeState and the native Store key
provides:
  - NativeState.mirrors, the persisted set of native mirror ids (D-01)
  - a native mirror stays native after a restart whatever the size of its last document (MIG-04)
  - 1.0.0 Stores keep their native mirrors and are migrated into the set at the first save (D-02)
  - the sticky native flag, ended only with the mirror (D-03)
affects: [06-02, native-entity-residual-fixes, phase-8-uat]

actuals:
  tokens: 6177
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Local per-mirror flag in the additive native Store dict instead of inside the stored payload"
    - "Store key written only when not empty, so exact-dict Store assertions of older suites stay green"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/document.py
    - custom_components/mqtt_actions/const.py
    - tests/test_native_start.py
    - tests/test_native_entities.py
    - .planning/phases/06-native-entity-residual-fixes/06-CONTEXT.md

key-decisions:
  - "The native flag of a mirror is a set of device ids under the native Store key; the stored payload is the document exactly as received (D-01)"
  - "A mirror is native when the set lists it or its payload carries the 1.0.0 marker; only the set is written from now on (D-02)"
  - "The flag is sticky: an id leaves the set at tombstone, prune or adoption and is pruned at start when no mirror was restored (D-03, T-06-01)"
  - "A failed adoption puts the id back before the mirror is restored, because the payload no longer carries a marker"

patterns-established:
  - "mirrors key inside the native Store dict is written only when the set is not empty"
  - "_remember_native_mirror is the single place that adds an id, called after a mirror record is registered or replaced"

requirements-completed: [MIG-04]

coverage:
  - id: D1
    description: "A native mirror whose unmarked document is exactly MAX_DOCUMENT_BYTES is still native after a restart: no test-topic subscription and no reload for the next marked document of the same content"
    requirement: MIG-04
    verification:
      - kind: unit
        ref: "tests/test_native_start.py#test_a_native_mirror_at_the_size_limit_stays_native_after_a_restart"
        status: pass
    human_judgment: false
  - id: D2
    description: "The persisted set rejects malformed, foreign and stale ids and is capped at MAX_MIRRORS; a stale id never turns a later legacy mirror native"
    requirement: MIG-04
    verification:
      - kind: unit
        ref: "tests/test_native_start.py#test_native_mirror_set_ignores_malformed_and_unlisted_ids"
        status: pass
      - kind: unit
        ref: "tests/test_native_start.py#test_native_mirror_set_parser_cuts_and_validates"
        status: pass
      - kind: unit
        ref: "tests/test_native_start.py#test_native_mirror_set_never_marks_a_later_legacy_mirror_native"
        status: pass
    human_judgment: false
  - id: D3
    description: "A 1.0.0 Store (flag only in the cached payload, no mirrors key) loads native and is migrated into the set"
    requirement: MIG-04
    verification:
      - kind: unit
        ref: "tests/test_native_start.py#test_native_mirror_set_takes_over_a_marker_only_store_of_the_previous_release"
        status: pass
      - kind: unit
        ref: "tests/test_native_entities.py#test_a_cached_native_mirror_is_native_again_after_a_restart"
        status: pass
    human_judgment: false
  - id: D4
    description: "The flag is sticky and ends only with the mirror: tombstone, adoption and a failed adoption behave as specified; the exact-dict Store assertions of the cutover suite hold"
    requirement: MIG-04
    verification:
      - kind: unit
        ref: "tests/test_native_start.py#test_native_mirror_set_is_cleared_by_a_tombstone"
        status: pass
      - kind: unit
        ref: "tests/test_native_start.py#test_native_mirror_set_moves_to_the_owned_devices_at_adoption"
        status: pass
      - kind: unit
        ref: "tests/test_native_start.py#test_native_mirror_set_survives_a_failed_adoption"
        status: pass
      - kind: unit
        ref: "tests/test_cutover.py"
        status: pass
    human_judgment: false

duration: 8 min
completed: 2026-10-04
status: complete
plan_head_before: bf64159bbf18a138d640dfb995345eedc4bd9e5c
plan_head_after: 56bdc71b8b6dba19f0a878dc7f30406c9c9b6ad1
commits: 5
---

# Phase 6 Plan 01: Native flag of a mirror in the Store Summary

**The native flag of a mirror now lives in a persisted set of device ids in the native Store dict, so a native mirror stays native after a restart even when its document is exactly MAX_DOCUMENT_BYTES; 1.0.0 Stores still load native and the payload marker writer is gone.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-04T10:25:10Z
- **Completed:** 2026-10-04T10:32:44Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- IN-02 / MIG-04 fixed: the 20-byte marker no longer decides whether a stored copy stays native. The set `NativeState.mirrors` is parsed (valid ids only, at most MAX_MIRRORS, deterministic cut), written only when not empty and read in `_build_mirror`; the payload is stored as received.
- 1.0.0 compatibility (D-02): a mirror is native when the set lists it or its payload carries the old marker, and the first save moves marker-only mirrors into the set. `test_a_cached_native_mirror_is_native_again_after_a_restart` is unchanged and green.
- Sticky lifecycle (D-03): the id is added after a mirror record is registered or replaced, removed at tombstone, prune and adoption, put back when an adoption fails, and pruned at start to the restored mirrors (T-06-01).
- `with_native_marker` is deleted from `document.py`; D-03 in `06-CONTEXT.md` states the sticky decision and no longer carries the re-pin sentence.

## Task Commits

1. **Task 1: Tracer, native mirror at exactly MAX_DOCUMENT_BYTES survives a restart through the Store**
   - `e335375` test (RED, 3 tests)
   - `194409a` fix (GREEN)
2. **Task 2: Lifecycle of the set, retire the marker writer, align D-03**
   - `cc02481` test (RED, 3 tests)
   - `4b98ff8` fix (GREEN, plus the two guards)
   - `56bdc71` docs (D-03 in CONTEXT.md)

**Plan metadata:** committed after this SUMMARY (docs: complete plan).

## Files Created/Modified

- `custom_components/mqtt_actions/manager.py` - `NativeState.mirrors`, `_parse_native`, `_data_to_save`, `_mirror_info`, `_build_mirror`, `_remember_native_mirror`, discard at `async_remove_mirror` and `_async_drop_mirror`, restore on a failed adoption, prune at `async_start`
- `custom_components/mqtt_actions/document.py` - marker writer removed
- `custom_components/mqtt_actions/const.py` - `STORE_NATIVE` comment names the `mirrors` list
- `tests/test_native_start.py` - Phase 6 section: size-limit round trip, set parse and 1.0.0 migration, lifecycle tests, two guards
- `tests/test_native_entities.py` - T-5-11 persistence assertion moved to the Store set, unused import removed
- `.planning/phases/06-native-entity-residual-fixes/06-CONTEXT.md` - D-03 rewritten

## Decisions Made

- Followed the plan as specified (D-01, D-02, D-03 as amended by the planning session). The re-pin and update branches are unchanged: they already keep the flag through `keep_native`, which is the sticky behavior.

## TDD Gate Compliance

The plan is `type: execute` with `tdd="true"` tasks, so the per-task gate applies (a `test(06-01)` commit with intentional red evidence before the fix). The generic gate for `type: tdd` plans looks for a `feat` commit and does not fire; the fix commits are `fix(06-01)` by the plan's own commit-type note.

RED evidence, run on the unchanged production code of each step, verdict from `gsd_run check tdd-red-evidence`:

| Commit | Target test | Failed on | Verdict |
|--------|-------------|-----------|---------|
| `e335375` | `test_a_native_mirror_at_the_size_limit_stays_native_after_a_restart` | `is_native` False after `_restart` | RED_EVIDENCE_OK |
| `e335375` | `test_native_mirror_set_ignores_malformed_and_unlisted_ids` | listed cached mirror not native | RED_EVIDENCE_OK |
| `e335375` | `test_native_mirror_set_takes_over_a_marker_only_store_of_the_previous_release` | persisted list `[]`, expected the id | RED_EVIDENCE_OK |
| `cc02481` | `test_native_mirror_set_is_cleared_by_a_tombstone` | id still listed after the tombstone | RED_EVIDENCE_OK |
| `cc02481` | `test_native_mirror_set_moves_to_the_owned_devices_at_adoption` | id still listed after adoption | RED_EVIDENCE_OK |
| `cc02481` | `test_native_mirror_set_never_marks_a_later_legacy_mirror_native` | stale id still listed after start | RED_EVIDENCE_OK |

GREEN: all six pass after `194409a` and `4b98ff8`. The two guards (`..._survives_a_failed_adoption`, `..._parser_cuts_and_validates`) are green by design; the failed-adoption guard was mutation-checked (removing the rollback re-add turns it red).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The RED-evidence validator only parses TAP and Surefire XML. pytest's JUnit XML was fed to its Surefire path; because pytest writes `classname` before `name` and the validator reads the first `name="..."`, the two attributes were swapped in the record before validation (same content, only the order). The first attempt without the swap returned `INVALID_RED no_target_test_failure`, which was a parser quirk, not a RED problem.
- `-p no:logging` was used for fast RED runs and made the caplog-based follower tests error; the regression runs were repeated without it and are green. The pre-existing uncommitted changes in `.planning/config.json` (and STATE.md before the state update) were not made by this plan and were left out of the code commits.

## Verification

- `uv run pytest tests/test_native_start.py tests/test_native_entities.py tests/test_cutover.py tests/test_sync_follower.py tests/test_native_cleanup.py tests/test_takeover.py -q`: 202 passed
- `uv run pytest tests/ -q`: 1468 passed (baseline 1460 plus 8 new tests)
- `uv run ruff check .` and `uv run ruff format --check .`: clean
- `git grep -n with_native_marker -- custom_components tests`: no output
- `grep -c "mirrors.discard"` gives 2; `intersection_update` appears once in `async_start`; `mirrors: set[str]` and `if self._native.mirrors` appear once each

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path or file access; the new Store key holds device ids only and is validated on load (T-06-01, T-06-03 mitigated, T-06-02 unchanged, T-06-04 fixed, T-06-05 accepted).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 06-02 (IN-03 replay duplicate catch and the README Limitations edit). The README size-limit bullet is not removed here by design: that belongs to 06-02.

## Self-Check: PASSED

---
*Phase: 06-native-entity-residual-fixes*
*Completed: 2026-10-04*
