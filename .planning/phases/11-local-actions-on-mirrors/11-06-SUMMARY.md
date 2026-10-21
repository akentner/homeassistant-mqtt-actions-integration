---
phase: 11-local-actions-on-mirrors
plan: 06
subsystem: runtime
tags: [local-actions, lifecycle, prune, tombstone, adoption, store, tdd]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-05: Manager local overlay (_local_records, LocalActionsStore save path, local_action_* read APIs, locked edits)"
provides:
  - MirrorRemovalCause (const.py, re-exported by manager.py) with TRANSIENT_PRUNE and TOMBSTONE
  - Manager.async_remove_mirror(device_id, *, cause) - only TOMBSTONE discards local records, also without a live mirror
  - Manager.async_adopt_device(device_id, *, force) -> AdoptionResult(previous_owner, local_actions_discarded)
  - Manager.async_adopt(...) -> str kept as a thin wrapper
  - adopt_device response key local_actions_discarded
  - Owner renames refresh the saved labels of active records durably (D-11)
affects: [11-07, 11-08, 11-09, 11-12]

# Actuals (#2632)
actuals:
  tokens: 14035
  tasks: 3
  commits: 6
plan_head_before: 09c2a053479d321e814ddf2628ecc54a0906ee0d
plan_head_after: 00377b617075fcd32a84c306f9dcece3a8ef116e

tech-stack:
  added: []
  patterns:
    - "Explicit removal cause: callers state why a mirror goes; destruction of local data is opt-in per cause"
    - "Cross-Store adoption: save the local discard first (a failure changes nothing), restore records before the mirror on rollback"

key-files:
  created:
    - tests/test_local_actions_lifecycle.py
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-06-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-06-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-06-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-06-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-06-task3-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-06-task3-red.xml
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/services.py
    - tests/test_services.py

key-decisions:
  - "Only a tombstone destroys local records; the prune keeps them because a missing document is inferred, not an explicit deletion. MirrorRemovalCause lives in const.py so sync.py can import it without a cycle"
  - "A tombstone is passed to the Manager even when no mirror exists (after a prune); an id without mirror and without records stays a silent no-op, owned ids are never touched"
  - "A tombstone whose discard cannot be saved still removes the mirror and keeps the records (warning, count only)"
  - "Adoption saves the overlay-free record set before any other adoption step; a failed local save raises LocalActionsStoreError (a HomeAssistantError) before anything changed, so no new AdoptionError reason or translation was added"
  - "A failed subentry creation restores the records (memory always, disk best-effort) before the mirror is re-ingested, so the restored Script has its local branches again"
  - "Saved labels are refreshed only on an owner content change, for active records only; startup restore and new mirrors never rewrite the local Store"

patterns-established:
  - "Store-change ordering probe: wrap LocalActionsStore.async_save_records and record mqtt_mock.async_publish.call_count at save time"

requirements-completed: [MIR-06, MIR-07, MIR-08, MIR-12]

coverage:
  - id: D1
    description: "Local records survive owner content, name and revision changes, restart and owner re-pin separately; removed options orphan (inactive, editable, removable, no runner plan) and the exact normalized return reattaches with the saved raw actions; kind mismatch stays inactive; owner renames refresh the saved label durably"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_actions_lifecycle.py -k 'survive or orphan or repin or kind' (9 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Prune and startup cleanup keep the local Store byte-identical; a tombstone, also one after a prune, deletes the device's records, saves at once, logs the count only and publishes nothing; owned ids and failed saves keep records"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_actions_lifecycle.py -k 'prune or tombstone' (8 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Adoption refusal for pending owners holds even with every trigger replaced and keeps records; a completed adoption saves the discard before any publish and reports it; injected local-save and subentry-create failures restore mirror plus records with zero publishes; adopt_device returns local_actions_discarded"
    requirement: MIR-12
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_actions_lifecycle.py tests/test_multi_instance_ops.py tests/test_services.py -k adopt (20 passed: 14 existing + 6 new)"
        status: pass
      - kind: other
        ref: "tests/test_local_invariants.py adoption byte comparison (green in the full unit tier)"
        status: pass
    human_judgment: false
  - id: D4
    description: "No regression across tiers"
    requirement: MIR-07
    verification:
      - kind: other
        ref: "uv run pytest -q -m 'not broker and not multi_instance' (1790 passed, 2 xfailed, no --deselect); -m multi_instance (173 passed); -m broker (18 passed)"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-10-21
---

# Phase 11 Plan 06: Overlay Lifecycle Across Owner Changes, Prune, Tombstone and Adoption Summary

**Mirror removal now has an explicit cause. A prune keeps local records. Only a tombstone discards them, and it still does after an earlier prune has removed the mirror. A completed adoption saves the discard before the owned device can publish and reports `local_actions_discarded`. Failed adoptions restore the mirror together with its records. Owner renames refresh the saved labels without changing identity.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-10-21T01:22:58Z
- **Completed:** 2026-10-21T01:37:13Z
- **Tasks:** 3 (1 tracer and 2 TDD), in 6 commits: 3 RED and 3 GREEN. No refactor was needed.
- **Files:** 4 production modules and 1 test module modified. 1 test module and 6 evidence files created.

## Lifecycle interfaces (for Plans 11-07 to 11-12)

- `custom_components/mqtt_actions/const.py`:
  - `class MirrorRemovalCause(StrEnum)` with `TRANSIENT_PRUNE = "transient_prune"` and `TOMBSTONE = "tombstone"`.
  - `manager.py` imports it, so `from custom_components.mqtt_actions.manager import MirrorRemovalCause` also works.
- `Manager.async_remove_mirror(device_id, *, cause: MirrorRemovalCause)`. The caller holds the lock.
  - An owned id returns at once.
  - A present mirror is unloaded by `_async_unload_removed_mirror`, which has the old body.
  - `TOMBSTONE` then runs `_async_discard_tombstoned_records`. That happens even when no mirror exists.
- `sync._async_prune` passes `TRANSIENT_PRUNE`.
- `sync._async_remove` passes `TOMBSTONE` for every running, non-owned id. The old `device_id in manager.mirrors` gate now only decides the debug line.
- `Manager._async_discard_local_records(device_id) -> int`:
  - It saves the record set without that device and returns the count.
  - With no records, nothing is written.
  - It raises `LocalActionsStoreError`, and in that case nothing has changed.
- `@dataclass(frozen=True, slots=True) class AdoptionResult(previous_owner: str, local_actions_discarded: int)` in `manager.py`.
- `Manager.async_adopt_device(device_id, *, force=False) -> AdoptionResult`. The gates and their order are unchanged: `not_a_mirror`, then `not_approved`, then `owner_not_offline`.
- `Manager.async_adopt(...) -> str` stays as a wrapper that returns `.previous_owner`.
- The `adopt_device` response is `{"uuid", "adopted", "previous_owner", "local_actions_discarded"}`.
- Adoption order inside the lock, in `_async_adopt_locked`:
  1. Build the owner-only subentry payload.
  2. Snapshot `previous_records` and save the discard. A failure here raises before anything changed.
  3. Record transfers and revs.
  4. Drop the mirror.
  5. Save the main Store.
  6. Add the subentry. If that fails, roll back: restore the main-Store fields, then the records (`_async_restore_local_records`), then the mirror (`sync.async_restore_mirror`), then re-raise.
  7. Log the count, then reconcile, which publishes.
- `Manager._async_refresh_local_labels(mirror)` runs only in the owner content-change branch of `async_apply_mirror`.
  - It saves `record.with_label(trigger.friendly_name)` for active records whose label differs.
  - If that save fails, the old labels stay in memory and on disk, and the owner update still applies.

## TDD Evidence

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 (tracer) | `74026f3` | `tests/test_local_actions_lifecycle.py::test_option_rename_survives_with_refreshed_label` | RED_EVIDENCE_OK | `aa5290a` | none needed |
| 2 | `ebb207c` | `tests/test_local_actions_lifecycle.py::test_tombstone_after_prune_still_discards_records` | RED_EVIDENCE_OK | `27cdbad` | none needed (cause dispatch was extracted in GREEN) |
| 3 | `e886b45` | `tests/test_services.py::test_adopt_service_promotes_a_mirror` | RED_EVIDENCE_OK | `00377b6` | none needed |

Semantic assessments. The full text is in `tdd/11-06-task{1,2,3}-red.json`.

- **RED 1:** valid. The test failed only on the label field of the stored row, which read `B` where `Bee` was expected. Identity, mode and actions were already kept. The 9 other Task 1 tests were green at RED and characterize the retention that Plan 11-05 already provides. They cover content, rename, revision, restart and re-pin survival, orphan/reattach, orphan removal, kind mismatch and label-save failure.
- **RED 2:** valid. The prune and its premises passed. The tombstone left the records of the tombstoned device. In the same run:
  - The live-tombstone test failed on the same assertion.
  - The manager-seam test failed on the ImportError of the planned `MirrorRemovalCause`. It was not the target.
- **RED 3:** valid. The exact response equality differed only by the missing `local_actions_discarded: 0`. The assertion was extended, not relaxed. The new lifecycle adoption tests failed on the missing `async_adopt_device` or on the records that were kept, and they were not targets. All 13 existing adopt-selected tests passed.

## Verification

- Task 1: `uv run pytest -q tests/test_local_actions_lifecycle.py -k "survive or orphan or repin or kind"`: 9 passed. The tracer gate re-ran this command green before expansion.
- Task 2: `uv run pytest -q tests/test_local_actions_lifecycle.py -k "prune or tombstone"`: 8 passed. The prune and the tombstone tests compare the Store bytes before and after.
- Task 3: `uv run pytest -q tests/test_local_actions_lifecycle.py tests/test_multi_instance_ops.py tests/test_services.py -k adopt`: 20 passed. That is the 14 existing tests (9 ops, 5 services) plus 6 new ones.
- Regressions:
  - `tests/test_sync_follower.py`, `test_companions.py`, `test_native_start.py`, `test_shared_topic_gate.py`, `test_native_cleanup.py` and `test_native_replay.py`: 221 passed after Task 2.
  - Full tiers after Task 3: unit 1790 passed and 2 xfailed, with no `--deselect`. Multi-instance 173 passed. Broker 18 passed.
- `uv run ruff check` and `ruff format --check` are clean on `custom_components` and `tests`.

## Task Commits

1. **Task 1 (tracer): survival, orphan/reattach, label refresh.** `74026f3` (test), `aa5290a` (feat).
2. **Task 2: prune versus tombstone.** `ebb207c` (test), `27cdbad` (feat).
3. **Task 3: transactional adoption discard and report.** `e886b45` (test), `00377b6` (feat).

## Deviations from Plan

### Notes (no auto-fixes were needed)

**1. [Scope] `services.yaml` unchanged**
- Home Assistant's services schema has no per-field response description, so a change to `services.yaml` would invent a key. The plan allows "changes only within what hassfest accepts", and there were none to make.
- Plan 11-12 documents `local_actions_discarded` in docs/operations.md and the README.

**2. [Scope] "Startup and owner refresh do not clear an unrelated local failure" is not pinned here**
- The independent local-failure Repairs issue does not exist yet. Plan 11-07 Task 2 creates it.
- Today an owner content change clears only the owner's existing action-failed issue (`runner.clear_issue`), as before.
- Plan 11-07 has to make sure that this path leaves its new local issue alone.

**3. [Design] Location of `MirrorRemovalCause`**
- It lives in `const.py` and is re-exported through `manager.py`.
- `sync.py` imports `manager` only for type checking. A runtime import would be circular.

**4. [Design] Error on a failed local discard during adoption**
- `LocalActionsStoreError` (a `HomeAssistantError`) propagates to the service caller.
- No new `AdoptionError` reason or translation key was added, because the refusal path and the translations stay as they are.
- Nothing has changed when this error is raised.

**5. [Characterization] Tests that were green at RED**
- Tasks 1 and 2 include retention tests that Plan 11-05 already satisfied: survival, prune, startup cleanup, owned id, no records and save failure. They pin the outcome of each cause explicitly.

**Total deviations:** 0 auto-fixed, plus 2 scope notes, 2 design notes and 1 characterization note. **Impact:** none on correctness. All T-11-16 to T-11-19 mitigations are in place.

## Hand-offs

- **Plan 11-07:** the local-failure issue must survive owner content changes and restarts. The owner-change branch of `async_apply_mirror` clears only the owner's issue.
- **Plan 11-09:** hub removal (D-08) is still open. `async_remove_mirror(cause=...)` is not on that path.
- **Plan 11-12:** document `local_actions_discarded` in the `adopt_device` row and the README, and cover the prune/tombstone/adoption lifecycle in the docs.

## Known Stubs

None.

## Threat Flags

None. The surface is the T-11-16 to T-11-19 register of this plan:
- Explicit cause, the lock, an immediate save and tombstone-after-prune tests.
- The local save comes first, and rollback restores records before the mirror, with zero publishes.
- Approval stays owner-only even with every trigger replaced.
- Logs and the response carry counts and the owner name only. The adoption bytes test stays green.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Plans 11-07 to 11-09 can rely on explicit lifecycle outcomes. Every later wave gate still runs the unfiltered unit tier.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

All 12 created/modified files exist, all 6 task commits are ancestors of HEAD, and the three RED records classify as RED_EVIDENCE_OK.
