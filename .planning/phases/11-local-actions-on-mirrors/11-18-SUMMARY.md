---
phase: 11-local-actions-on-mirrors
plan: 18
subsystem: sync
tags: [mqtt, tombstone, local-actions, store, wr-01, tdd]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-13: local actions lifecycle (prune keeps, tombstone discards, adoption discards); Plan 11-14: local failure issue follows its record (D-19)"
provides:
  - "A tombstone (empty config payload) removes only the runtime mirror; local action records stay byte-identical, inactive and listed as not mirrored"
  - "Manager.async_remove_mirror(device_id) without a cause; never writes the local Store; logs the kept count at INFO"
  - "MirrorRemovalCause and Manager._async_discard_tombstoned_records removed"
  - "README Lifecycle/Limitations and troubleshooting local_action_failed say a tombstone keeps local actions"
  - "11-REVIEW-DISPOSITION.md: WR-01 fixed (plan 11-18, 17865da), open: 10"
affects: [11-19, 11-23, phase-11-verification, mir-08]

actuals:
  tokens: 9421
  tasks: 3
  commits: 5
plan_head_before: 857443bf149ceb6fb64a0ef6209639c83703fe62
plan_head_after: 98d942e4a9db478f4dcb4bbccd06a304ebe677af

tech-stack:
  added: []
  patterns:
    - "Only adoption, explicit removal of a customization and hub removal write or delete local records; no broker message does"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-18-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-18-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-18-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-18-task2-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/const.py
    - tests/test_local_actions_lifecycle.py
    - tests/test_local_invariants.py
    - tests/test_docs.py
    - README.md
    - docs/troubleshooting.md
    - .planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md

key-decisions:
  - "D-05 amended (owner decision 2026-10-21, WR-01): a tombstone keeps local records inactive like a prune; the grace-timer alternative is not implemented"
  - "sync._async_remove calls async_remove_mirror only when a mirror exists; a tombstone for an id without a mirror is a no-op"
  - "The kept-count INFO line is logged only when a mirror was actually removed and it left records (count only, no id, label or action)"

patterns-established:
  - "Prune and tombstone share one removal path (async_remove_mirror(device_id)); neither reaches a local Store save"

requirements-completed: [MIR-07, MIR-08, MIR-15]

coverage:
  - id: D1
    description: "A tombstone removes the mirror and keeps its local records byte-identical, publishes nothing, logs the kept count only"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_tombstone_keeps_records_byte_identical_and_publishes_nothing"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_tombstone_after_prune_keeps_records"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_tombstone_without_a_mirror_keeps_records"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_tombstone_never_writes_the_local_store"
        status: pass
      - kind: integration
        ref: "tests/test_local_invariants.py#test_every_lifecycle_transition_publishes_no_local_content"
        status: pass
    human_judgment: false
  - id: D2
    description: "Kept records of a tombstoned device stay listed as not mirrored, attach again and run without approval when the owner republishes"
    requirement: MIR-07
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_tombstoned_device_records_apply_again_when_the_owner_publishes_it_again"
        status: pass
    human_judgment: false
  - id: D3
    description: "The local failure issue of a tombstoned device stays while its record exists and goes when the customization is removed; adoption still discards"
    requirement: MIR-07
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_tombstone_keeps_and_completed_adoption_deletes_the_local_failure_issue"
        status: pass
    human_judgment: false
  - id: D4
    description: "README and troubleshooting say that a tombstone keeps local actions inactive; only adoption discards them"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_docs_say_a_tombstone_keeps_local_actions"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_every_local_actions_topic"
        status: pass
    human_judgment: false
  - id: D5
    description: "Review disposition WR-01 recorded as fixed with plan 11-18 and its GREEN commit"
    verification:
      - kind: other
        ref: "Task 3 disposition verify command (frontmatter and table agree, open: 10)"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 18: Tombstone Keeps Local Actions Summary

**An empty config payload now removes only the runtime mirror: the device's local action records stay byte-identical in the Store, inactive and listed as not mirrored, and attach again when the owner republishes (WR-01, D-05 amended).**

Full suite: 2074 passed, 2 xfailed

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-21T07:32:20Z
- **Completed:** 2026-10-21T07:40:07Z
- **Tasks:** 3
- **Files modified:** 13 (9 source/test/doc files, 4 RED evidence files)

## Accomplishments

- `Manager.async_remove_mirror(device_id)` has no `cause` any more and never writes the local Store. When the removed mirror leaves records, it logs `Kept %d local actions of a removed mirror; they stay inactive until the device returns or you remove them` (count only).
- `Manager._async_discard_tombstoned_records` and `MirrorRemovalCause` (const.py) are gone. `_async_discard_local_records` is unchanged, because adoption still uses it.
- `SyncManager._async_remove` keeps the lock, the `running` guard and the owned-id guard, and calls `async_remove_mirror(device_id)` only when a mirror exists. `_async_prune` calls the same method.
- The README, the troubleshooting page and the docs test now say the same thing: a tombstone keeps local actions inactive, and only adoption discards them.
- Disposition row WR-01 is `fixed` (plan 11-18, 17865da), and `open: 10`.

## Task Commits

1. **Task 1 (tracer): a tombstone keeps local records.** RED `01436ef` (test), GREEN `17865da` (feat)
2. **Task 2: docs say that a tombstone keeps local actions.** RED `5b9fdc1` (test), GREEN `81e615b` (docs)
3. **Task 3: gate and disposition WR-01 fixed.** `98d942e` (docs)

## TDD Gate Compliance

- **Task 1 RED:** `tdd/11-18-task1-red.json` gave `RED_EVIDENCE_OK` (target_test_failed). Semantic assessment: valid RED. The target node was collected and run (1 test, 0 errors, 0 skipped). The premise in `_cached_mirror_with_records` passed. The test then failed on its first post-tombstone assertion, the local Store byte-identity check (`tests/test_local_actions_lifecycle.py:504`), because `_async_discard_tombstoned_records` saved the set with only the OTHER_DEVICE row. It was not an import, collection or fixture fault.
- **Task 1 GREEN:** `17865da`. The six target tests passed (6 passed), and so did the broader set of ten files (309 passed).
- **Task 2 RED:** `tdd/11-18-task2-red.json` gave `RED_EVIDENCE_OK`. Semantic assessment: valid RED. The bullet lookup found the README `**Tombstone.**` bullet. The test failed on the planned `'kept'` assertion (`tests/test_docs.py:669`), because the bullet still said "its tombstone discards the local actions".
- **Task 2 GREEN:** `81e615b` (`docs(11-18)`). The README and troubleshooting text change made `tests/test_docs.py` pass (35 passed). This is a doc-only GREEN, so its commit type is `docs`, not `feat`.
- **REFACTOR:** none was needed.

## Replaced Tests (old to new, one to one, same positions)

| Old (discard) | New (keep) |
|---|---|
| `test_tombstone_discards_records_saves_at_once_and_publishes_nothing` | `test_tombstone_keeps_records_byte_identical_and_publishes_nothing` (RED target) |
| `test_tombstone_after_prune_still_discards_records` | `test_tombstone_after_prune_keeps_records` |
| `test_tombstone_cause_reaches_the_manager_without_a_mirror` | `test_tombstone_without_a_mirror_keeps_records` (goes through the broker path and no longer imports `MirrorRemovalCause`) |
| `test_tombstone_save_failure_keeps_the_records_and_removes_the_mirror` | `test_tombstone_never_writes_the_local_store` |
| `test_tombstone_and_completed_adoption_delete_the_local_failure_issue` | `test_tombstone_keeps_and_completed_adoption_deletes_the_local_failure_issue` |
| (new) | `test_tombstoned_device_records_apply_again_when_the_owner_publishes_it_again` |

The lifecycle file now collects 33 tests, up from a baseline of 32. The Task 2 banner comment now says that a prune and a tombstone both keep the records.

## Invariants Premise

`tests/test_local_invariants.py::_step_tombstone_after_prune` keeps its name. It now asserts that `records_of(lamp_id) == 2` after the tombstone and that the stored lamp rows are the same as before the tombstone. No later step (adoption_failure, adoption_success, hub_removal_keep, hub_removal_delete) assumed that the lamp records were gone, so no other premise changed. The leak scan of the step still finds no marker.

## Final Documentation Wording

README `### Lifecycle`:

> - **Tombstone.** When the owner deletes the device, or any client clears its config topic, the mirror is removed at once, but its local actions are kept, inactive, like after a prune. The device stays in the device list, marked as not mirrored, where you can view and remove them. If the device comes back, for example because the owner publishes it again after a stray clear, they apply again. The number of kept local actions is logged.

README `## Limitations`:

> - A forged tombstone removes the mirrors of a device until the owner publishes it again, and forces a new approval. The local actions of the device are kept and apply again when it returns.

docs/troubleshooting.md `local_action_failed`:

> When the owner deletes the device (a tombstone), its local actions are kept, inactive, and so is this issue, until you remove the local customization or the device returns. When you adopt the device, its local actions are discarded and the issue goes with it.

The `**Adoption.**` and `**Removing the integration**` bullets are unchanged.

## Disposition Change

`11-REVIEW-DISPOSITION.md` changed in two places:
- Frontmatter: WR-01 `disposition: open` became `fixed`, and `open: 11` became `open: 10`.
- Table: `| WR-01 | warning | fixed | plan 11-18, 17865da |`.

WR-02..WR-04 and IN-01..IN-07 stay `open`.

## Gate Results (Task 3)

- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 111 files already formatted.
- `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`: 2074 passed, 2 xfailed in 145.67s. Nothing failed, errored, was deselected or was skipped, and 2074 is above the 2072 baseline.

## Decisions Made

- Per the owner decision of 2026-10-21 (D-05 amended), a tombstone keeps the records inactive. The grace timer is not implemented.
- When there is no mirror, `async_remove_mirror` returns before it counts or logs anything. The INFO line therefore appears only when a mirror was actually removed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The Task 1 RED command ran without `-p no:logging`**
- **Found during:** Task 1 RED
- **Issue:** The planned RED command passes `-p no:logging`, which disables pytest's logging plugin. The RED target uses the `caplog` fixture (the plan requires the log assertion), so with that flag it errors at setup with "recursive dependency involving fixture 'caplog'". That is a fixture fault (INVALID_RED), not RED.
- **Fix:** I ran the same node with `--junitxml` and without `-p no:logging`. JUnit log capture is off by default, so the report holds only the failure. The deviation is recorded in the RED JSON `semanticAssessment`. The Task 2 RED target has no `caplog` and ran with `-p no:logging` as planned.
- **Files modified:** `tdd/11-18-task1-red.{json,xml}`
- **Verification:** `RED_EVIDENCE_OK`. The plan's own Task 1 `<verify>` command has no `-p no:logging` and reports 6 passed.
- **Committed in:** `01436ef`

**2. [Convention] RED evidence files are committed with the test commits**
- **Found during:** Tasks 1 and 2
- **Issue:** The plan says to commit "the two test files only" (Task 1) and "tests/test_docs.py only" (Task 2).
- **Fix:** As in plans 11-15 to 11-17 (for example `4d32927`), the `tdd/11-18-taskN-red.{json,xml}` evidence goes into the `test(11-18)` commit. No file under `custom_components/` is in a test commit, and the structural check passed.
- **Committed in:** `01436ef`, `5b9fdc1`

---

**Total deviations:** 2 (1 blocking fix, 1 commit-scope convention). **Impact:** neither changes the behaviour or the scope.

## Issues Encountered

None.

## Not Touched (Plan 11-23, same wave)

The release-notes Lifecycle bullet, the REQUIREMENTS MIR-08 text, ROADMAP Phase 11 success criterion 5 and the `### Amendments` block in 11-CONTEXT.md are left to Plan 11-23. This plan also did not run `requirements.mark-complete`, because the orchestrator told it not to touch REQUIREMENTS.md.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plan 11-19 can use `Full suite: 2074 passed, 2 xfailed` as its baseline.
- Plan 11-23 still has to carry the amended D-05 rule into REQUIREMENTS MIR-08, ROADMAP success criterion 5, 11-CONTEXT.md and the release-notes draft.

## Self-Check: PASSED

- The four RED evidence files exist on disk.
- Commits 01436ef, 17865da, 5b9fdc1, 81e615b and 98d942e are ancestors of HEAD.
- `check evaluation-scope --plan 11-18 --commits-only` resolved this branch's plan commits.
- All acceptance criteria and every `<verify>` command of Tasks 1 to 3 passed.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*
