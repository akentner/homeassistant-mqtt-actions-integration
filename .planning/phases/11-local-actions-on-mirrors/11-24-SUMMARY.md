---
phase: 11-local-actions-on-mirrors
plan: 24
subsystem: local-actions
tags: [local-store, read-only-store, forward-compatibility, unknown-keys, docs, tdd, gap-closure]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-20 and 11-21 unreadable/preserved rows contract; 11-22 removal settings count; suite baseline 2100"
provides:
  - "_LocalActionsReader (Store, read_only=True) with the migration hook; LocalActionsStore.async_load reads through it, so no load writes the local Store whatever version it carries"
  - "LocalActionRecord.extra: unknown keys of a parsable row kept on the record and written back unchanged by every save (edit, label refresh, removal of another record, adoption discard and restore)"
  - "make_local_record(..., extra=) keyword; copy_local_records deep-copies extra"
  - "Idempotency contract for every future minor migration in the migrate_local_actions_payload docstring"
  - "README Newer versions bullet and 11-CONTEXT.md Amendments block (D-07 extended WR-05, D-19 amended WR-06); disposition WR-05 fixed (open 11)"
affects: [11-25, phase-11-verification, phase-12-release]

plan_head_before: 3c76e48ce9288c2a7907856d1247d15debd96680
plan_head_after: 2ed0c436ce9dea228bb90d5a1d4029d8dc91d570
actuals:
  tokens: 11900
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "Read through a private read_only=True Store subclass so Core's save after the migration hook is dropped; the writer Store never runs Core's load"
    - "Keys a release does not know ride on the record (extra) and are written after the known keys; a known key can never come from extra"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-24-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-24-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-24-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-24-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-24-task3-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-24-task3-red.xml
  modified:
    - custom_components/mqtt_actions/local_actions_store.py
    - custom_components/mqtt_actions/local_actions.py
    - custom_components/mqtt_actions/manager.py
    - tests/test_hub_removal.py
    - tests/test_local_actions_store.py
    - tests/test_core_contracts.py
    - tests/test_local_actions_lifecycle.py
    - tests/test_docs.py
    - README.md
    - .planning/phases/11-local-actions-on-mirrors/11-CONTEXT.md
    - .planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md

key-decisions:
  - "Loading the local Store never writes it: LocalActionsStore.async_load reads through a fresh read-only _LocalActionsReader, so a newer minor file keeps its exact bytes and stamp through a start, a reload and the removal settings of a loaded and an unloaded hub (WR-05, D-22, D-07)"
  - "An explicit save (edit, removal, label refresh, adoption discard or restore) keeps every row, unknown row key and unknown top-level key and stamps this release's minor version; every future minor migration must therefore be idempotent"
  - "A parsable row with unknown keys is applied as today (without their meaning) and its unknown keys are kept in LocalActionRecord.extra (owner decision 2026-10-21)"

patterns-established:
  - "A Store this release only reads is built read_only=True; Core's dropped save after the migration hook is pinned by a Core contract test"

requirements-completed: [MIR-06, MIR-08, MIR-15]

coverage:
  - id: D1
    description: "A newer minor local Store keeps its exact bytes and stamp through a Home Assistant start, a reload and the removal settings of a loaded and an unloaded hub; the count path alone never writes it"
    requirement: "MIR-06"
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_newer_minor_local_store_is_never_written_by_the_start_or_the_settings"
        status: pass
      - kind: integration
        ref: "tests/test_hub_removal.py#test_unloaded_hub_settings_count_never_writes_a_newer_minor_local_store"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_newer_minor_version_load_never_writes_the_store"
        status: pass
      - kind: unit
        ref: "tests/test_core_contracts.py#test_a_read_only_store_returns_a_newer_minor_payload_without_writing"
        status: pass
    human_judgment: false
  - id: D2
    description: "A shape-invalid newer minor Store is unreadable at Store and Manager level, every save is refused and its bytes never change"
    requirement: "MIR-08"
    verification:
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_shape_invalid_newer_minor_store_is_unreadable_and_never_written"
        status: pass
      - kind: integration
        ref: "tests/test_hub_removal.py#test_unloaded_hub_counts_unknown_for_every_unreadable_store_shape"
        status: pass
    human_judgment: false
  - id: D3
    description: "Unknown keys of a parsable row survive an edit, a label refresh, the removal of another record, a completed adoption of another device and the rollback of a failed adoption; the row is still applied"
    requirement: "MIR-06"
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_unknown_keys_of_a_readable_row_survive_an_edit_and_a_label_refresh"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_failed_adoption_restores_unknown_row_keys"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_completed_adoption_keeps_unknown_keys_of_other_devices"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_unknown_row_keys_round_trip_as_copies"
        status: pass
    human_judgment: false
  - id: D4
    description: "An explicit save after a newer minor load keeps every row, row key and top-level key and stamps this release's minor version"
    requirement: "MIR-06"
    verification:
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_a_save_after_a_newer_minor_load_keeps_every_key_and_stamps_this_minor"
        status: pass
    human_judgment: false
  - id: D5
    description: "README Newer versions bullet states the unknown-settings behavior and the no-rewrite rule; CONTEXT amendments recorded; disposition WR-05 fixed"
    requirement: "MIR-15"
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_every_local_actions_topic"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 24: Newer-minor Local Store and Unknown Row Keys Summary

**A read-only `_LocalActionsReader` makes every load of the local actions Store write-free (a minor 2 file keeps its bytes through start, reload and the removal settings), and `LocalActionRecord.extra` keeps the unknown keys of readable rows through every save.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-21T09:33Z
- **Completed:** 2026-10-21T09:41Z
- **Tasks:** 3
- **Files modified:** 11 (plus 6 RED evidence files)

## Accomplishments

- Closed re-verification gap `gaps[0]` (WR-05): Core's `Store._async_load_data` saved the migration result stamped with this release's minor version, which rewrote a newer minor file on every start, on the removal settings of an unloaded hub and even for a shape-invalid file that was then reported unreadable. `LocalActionsStore.async_load` now reads through `_LocalActionsReader`, built with `read_only=True`, so Core's save after the migration hook is dropped.
- Closed WR-05 part 1: a row this release can parse but that carries unknown keys keeps them on `LocalActionRecord.extra`; `local_record_data` writes them after the six known keys, so an edit of that row, a D-11 label refresh, the removal of another record, an adoption discard and a failed-adoption restore write them back unchanged. A record without extra keys still stores exactly the v1 row.
- Flagged the cost of explicit saves in the `migrate_local_actions_payload` docstring: an explicit save over a newer minor file stamps this release's minor, so every future minor migration must be idempotent.
- Added the Core pin `test_a_read_only_store_returns_a_newer_minor_payload_without_writing` (passes at HEAD, pins Core, not the fix), README text, CONTEXT amendments and disposition WR-05 fixed (`open: 11`).

## Task Commits

1. **Task 1 (tracer): loading never writes the local Store** - RED `f98aaae` (test), GREEN `b4e253e` (feat)
2. **Task 2: unknown keys of a readable row survive every save** - RED `444b6be` (test), GREEN `94403a8` (feat)
3. **Task 3: README, CONTEXT, disposition** - RED `04e7c4b` (test), GREEN `2d45c04` (docs), disposition `2ed0c43` (docs)

**Plan metadata:** recorded in the final `docs(11-24): complete ...` commit.

## RED semantic assessments

- **Task 1** (`test_newer_minor_local_store_is_never_written_by_the_start_or_the_settings`): RED_EVIDENCE_OK. The target executed and failed on its first bytes assertion after the start, with the diff showing `minor_version` 2 re-stamped as 1 (Core saved the migration result). Not a setup or import error. The other four new Task 1 tests failed for the same reason; the Core pin passed at HEAD as planned.
- **Task 2** (`test_unknown_keys_of_a_readable_row_survive_an_edit_and_a_label_refresh`): RED_EVIDENCE_OK. The target executed and failed on the first stored-rows assertion after the edit ("an edit keeps the unknown keys"); `enabled` and `conditions` were dropped. The four companion tests failed on the same dropped keys.
- **Task 3** (`test_readme_documents_every_local_actions_topic`): RED_EVIDENCE_OK. Failed on the first new phrase `settings it does not know` (the README sentence did not exist yet); every earlier topic passed.

## Flagged assumptions (from the plan)

1. The user's explicit saves keep stamping this release's minor version, as Home Assistant's own Stores do after a downgrade. Every row and key is kept, so the only consequence is that a later minor release runs its migration again; migrations must be idempotent (T-11-63, accepted).
2. A row with unknown keys is applied without their meaning, for example a newer `"enabled": false` still runs here. Owner decision of 2026-10-21; the README states it (T-11-62, accepted).

## Disposition change

WR-05: open -> fixed (`plan 11-24, b4e253e 94403a8`); `open: 12` -> `open: 11`. WR-06 stays open (plan 11-25); IN-01..IN-10 unchanged.

## Verification

- Tracer gate: the Task 1 automated verify was re-run end to end after the GREEN commit and passed before expansion (`Tracer verified end-to-end`).
- Ruff check and format check: clean.
- Required-broker full suite, no `--deselect`, baseline 2100 from 11-22:

Full suite: 2111 passed, 2 xfailed

## Deviations from Plan

None - plan executed exactly as written. RED evidence commits additionally include the `tdd/11-24-taskN-red.xml` report beside the `.json` record, following the 11-22 precedent.

## Issues Encountered

None. Pre-existing uncommitted `.planning/STATE.md` and `.planning/config.json` changes and untracked `.planning/intel/`, `AGENTS.md` and two `.gitkeep` files were present before this plan and left alone, apart from the STATE.md update of this plan.

## Known Stubs

None.

## Threat Flags

None. The change adds no endpoint, auth path or trust-boundary access; it removes a write on a read path (T-11-59, T-11-60 mitigated) and keeps data the user already stored (T-11-61 mitigated).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 11-25 (WR-06, in-flight failure after a mute) can start from a green suite; its full-suite gate reads the passed count of the line above as its baseline.

## Self-Check: PASSED

- Files: the six RED evidence files, `local_actions_store.py`, `local_actions.py`, `manager.py`, README, CONTEXT and disposition exist.
- Commits `f98aaae`, `b4e253e`, `444b6be`, `94403a8`, `04e7c4b`, `2d45c04`, `2ed0c43` are ancestors of HEAD; `git rev-list --count` from the plan base gives 7.
- All three tasks' automated verify blocks passed; the disposition and CONTEXT additive-only checks passed.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*
