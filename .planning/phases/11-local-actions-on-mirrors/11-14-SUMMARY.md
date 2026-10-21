---
phase: 11-local-actions-on-mirrors
plan: 14
subsystem: repairs
tags: [issue-registry, repairs, local-actions, lifecycle, gap-closure, tdd]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-07 local failure issue (D-18, D-19); 11-11 cross-file review ledger with finding F-01 / gap G-01"
provides:
  - "Persistent local_action_failed issue: active after an HA restart with its trigger identity data and placeholders"
  - "_delete_device_issues(device_id, *, keep_local_failure=False); prune unload and adoption drop keep the local issue"
  - "_delete_local_failure_issue(device_id): called after a saved tombstone discard and after a completed adoption"
  - "_delete_local_failure_issues_without_record(): start cleanup, only in the success branch of the local load"
  - "Corrected troubleshooting text for local_action_failed; ledger row F-01 FIXED"
affects: [11-13 final gate precondition, 11-15, 11-17 (also change manager.py)]

actuals:
  tokens: 6078
  tasks: 3
  commits: 8
plan_head_before: 4fcace16e53f4aaf3b8a80f085e2c9b263cb7772
plan_head_after: 6ed518ff440e119e5ebba95e445d98ef483264ed

tech-stack:
  added: []
  patterns:
    - "Issue families with their own lifetime are excluded from the generic per-device cleanup by a keyword flag, not by editing ISSUE_DEVICE_PREFIXES"
    - "Restart simulation in tests: put the registry's own _data_to_save() into hass_storage under ir.STORAGE_KEY, then registry.async_load()"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-14-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-14-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-14-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-14-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-14-task3-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-14-task3-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - tests/test_local_actions_lifecycle.py
    - tests/test_local_actions_manager.py
    - docs/troubleshooting.md
    - tests/test_docs.py
    - .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md

key-decisions:
  - "G-01: local_action_failed is created with is_persistent=True; prune and adoption drop keep it via keep_local_failure, and only a saved tombstone discard, a completed adoption, removal, a proven success or hub removal delete it"
  - "G-01: the start deletes a local failure issue whose identity is unreadable or has no saved record, only after a successful local Store load; a refused load deletes nothing (T-11-40) and records are never matched against mirrors (D-05)"

patterns-established:
  - "keep_local_failure flag: callers that keep the local records also keep their failure issue"

requirements-completed: [MIR-13, MIR-15]

coverage:
  - id: D1
    description: "The local failure issue survives an HA restart (active, same data and placeholders), a transient prune and a failed adoption, and clears on a proven success and on removal of the customization"
    requirement: MIR-13
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_local_failure_raises_an_independent_issue_naming_the_trigger_and_error"
        status: pass
    human_judgment: false
  - id: D2
    description: "A saved tombstone discard and a completed adoption delete the local failure issue"
    requirement: MIR-13
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_tombstone_and_completed_adoption_delete_the_local_failure_issue"
        status: pass
    human_judgment: false
  - id: D3
    description: "A start deletes a local failure issue whose record is gone, keeps one whose record exists, and a refused local load deletes none"
    requirement: MIR-13
    verification:
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_start_deletes_a_local_failure_issue_whose_record_is_gone"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_start_keeps_a_local_failure_issue_whose_record_exists"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_lifecycle.py#test_refused_local_load_keeps_every_local_failure_issue"
        status: pass
    human_judgment: false
  - id: D4
    description: "Troubleshooting entry of local_action_failed states survival across restart, prune and failed adoption"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_troubleshooting_says_the_local_failure_issue_survives_restart_prune_and_failed_adoption"
        status: pass
    human_judgment: false
  - id: D5
    description: "Ledger row F-01 FIXED with the Task 1 GREEN commit and the regression test id; F-02 to F-04 still ROUTED"
    verification:
      - kind: other
        ref: "plan 11-14 Task 3 ledger verify command (grep of row F-01, sha ancestry and feat(11-14) subject)"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 14: Local failure issue lifecycle (G-01) Summary

**The local_action_failed issue is now persistent and kept out of the generic per-device cleanup on prune and adoption drop, so it survives an HA restart, a transient prune and a failed adoption. A saved tombstone discard, a completed adoption and a start-time check for a missing record delete it.**

## Performance

- **Duration:** about 14 min (2026-10-21T04:14:03Z to 2026-10-21T04:27:40Z)
- **Tasks:** 3 of 3
- **Files modified:** 6 source/test/doc files plus 6 RED evidence files

## Accomplishments

- `Manager._create_local_failure_issue` passes `is_persistent=True`. Placeholders and identity data are unchanged, still cut and escaped (T-11-23).
- `_delete_device_issues` gained `keep_local_failure: bool = False`. `_async_unload_removed_mirror` (prune and tombstone unload) and `_async_drop_mirror` (adoption) pass `True`. Owned-device removal, release and hub removal keep the old behavior. `const.py` / `ISSUE_DEVICE_PREFIXES` is unchanged.
- New `_delete_local_failure_issue(device_id)` runs in two places. One is `_async_discard_tombstoned_records`, only after the discard saved without raising. The other is `_async_adopt_locked`, only after `async_add_subentry` succeeded and never in the rollback.
- New `_delete_local_failure_issues_without_record()` runs in the `else` (success) branch of `_async_load_local_actions`.
- Troubleshooting text corrected (MIR-15). Ledger row F-01 set to FIXED.

## Task Commits

| Task | Gate | Commit | Message |
|------|------|--------|---------|
| 1 | RED | ffb67f9 | test(11-14): add failing test for local failure issue surviving restart, prune and failed adoption |
| 1 | GREEN | 6f381cb | feat(11-14): keep the local failure issue through restart, prune and failed adoption |
| 1 | REFACTOR | 9d61e9f | refactor(11-14): clear the named local failure through the shared delete helper |
| 2 | RED | 008ebdd | test(11-14): add failing test for the start cleanup of local failure issues without a record |
| 2 | GREEN | 77653b8 | feat(11-14): delete local failure issues without a record after a successful local load |
| 3 | RED | 8c7c373 | test(11-14): add failing doc test for the local failure issue lifecycle |
| 3 | GREEN | 2e552a3 | docs(11-14): say that the local failure issue survives restart, prune and failed adoption |
| 3 | ledger | 6ed518f | docs(11-14): set ledger row F-01 to FIXED and resolve gap G-01 |

## RED semantic assessments

- **Task 1** (`tdd/11-14-task1-red.json`, RED_EVIDENCE_OK). The target ran and failed on its first behavior assertion, restart survival. After the issue registry was written to its own storage and loaded again, the issue came back `active=False` with `data=None`, because it was created non-persistent. The premise assertions passed first, and there was no setup or fixture fault. The tombstone/adoption pin passed at RED, as planned.
- **Task 2** (`tdd/11-14-task2-red.json`, RED_EVIDENCE_OK). The target ran and failed on its first deletion assertion. The stale persistent issue of a device without a record was still active after setup, because the start had no cleanup yet. The keep pin and the refused-load pin passed at RED as characterizations.
- **Task 3** (`tdd/11-14-task3-red.json`, RED_EVIDENCE_OK). The target ran and failed on the phrase "survives a restart". The entry still listed the prune among the events that remove the issue.

## The one flipped existing assertion

In `tests/test_local_actions_manager.py::test_local_failure_raises_an_independent_issue_naming_the_trigger_and_error`, `assert issue.is_persistent is False` became `assert issue.is_persistent is True`. The new message says that the issue survives a Home Assistant restart with its trigger identity (G-01). That flag is exactly what G-01 changes. No other existing assertion was changed.

## Ledger row change

- F-01: `ROUTED` became `FIXED`. The Gap column changed from `G-01` to `G-01 fixed in 6f381cb`. The regression test id is unchanged.
- The G-01 YAML now has `status: resolved` and `fixed_in: "6f381cb (plan 11-14)"`.
- Ledger summary: 3 routed (F-02 to F-04), 1 fixed (F-01). The routed-gap line now says 1 of 4 is fixed. F-02, F-03 and F-04 still read ROUTED.

## Decisions Made

- The new tests seed and reload the issue registry through `hass_storage` and `registry.async_load()`. The PHACC test Store of the issue registry writes nothing, so the helper first calls `registry._store.async_save(...)` only to consume the pending delayed write.
- In the Task 1 test the prune runs before the failed adoption. The prune helper needs a cached mirror that was not seen again, and the adoption rollback restores the mirror as seen. The plan allows any order the helpers need.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Accuracy] Docstrings of `_async_drop_mirror` and `async_remove_mirror` updated**
- **Found during:** Task 1 GREEN
- **Issue:** Both docstrings said that every per-device issue is deleted. That is no longer true for the local failure issue.
- **Fix:** Both now name the exception. Part of commit 6f381cb.

**2. [Rule 3 - Convention] Reflowed the `local_action_failed` troubleshooting paragraph**
- **Found during:** Task 3
- **Issue:** One line of the entry was already longer than 120 characters before this plan, and the plan requires the limit.
- **Fix:** Reflowed the edited part of the entry. All pinned phrases are kept. Commit 2e552a3.

**3. [Minor] RED evidence files committed with each RED commit**
- The plan says to commit the RED test "with the test file only". As in plans 11-07 and 11-12, the `tdd/*-red.{json,xml}` evidence went into the same commit. No production file is in any `test(11-14)` commit, which is what the verify command checks.

**Total deviations:** 3 minor (docstring accuracy, line reflow, evidence placement). **Impact:** none on behavior or scope.

## TDD Gate Compliance

- RED then GREEN commits exist for every task, in order: ffb67f9 then 6f381cb, 008ebdd then 77653b8, 8c7c373 then 2e552a3 (a docs GREEN). REFACTOR 9d61e9f ran with the tests green.
- Tracer gate (Task 1): `human_verify_mode` is end-of-phase and the verify step is automated only. The tracer `<verify>` was re-run and passed, so expansion went ahead.

## Verification

- `uv run pytest -q` on the G-01 target: 1 passed.
- Five modules (lifecycle, manager, parallel, hub_removal, diagnostics): 143 passed.
- Task 2: 3 passed. Lifecycle, manager and store: 99 passed.
- `tests/test_docs.py`: 34 passed.
- `uv run ruff check .` and `uv run ruff format --check .`: clean.
- `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`: **2062 passed, 2 xfailed**, with nothing deselected or skipped (baseline 2056).
- Ledger verify command: passed. `const.py` is unchanged since the first 11-14 commit.

## Issues Encountered

None.

## Next Phase Readiness

Ready for 11-15 (G-02). Plan 11-13 still halts on its precondition until F-02, F-03 and F-04 read FIXED.

## Self-Check: PASSED

- All 6 modified files and 6 RED evidence files exist.
- All 8 commits (ffb67f9, 6f381cb, 9d61e9f, 008ebdd, 77653b8, 8c7c373, 2e552a3, 6ed518f) are ancestors of HEAD.
