---
phase: 11-local-actions-on-mirrors
plan: 07
subsystem: runtime
tags: [local-actions, retrigger, test-buttons, repairs, approval, breaker, tdd]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-03: BranchOutcome, ActionRunner.on_local_outcome, plan_for, conservative reducer"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-05: effective plans per mirror, policy snapshot, local Store records and locked edits"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-06: explicit removal causes; owner change clears only the owner issue"
provides:
  - Manager.run_manual, the one gate of native test press, legacy test topic and re-trigger (const.ManualRunResult)
  - Independent local failure issue local_action_failed_<device id> (ISSUE_LOCAL_ACTION_FAILED_PREFIX, translation key local_action_failed)
  - Manager.async_report_local_outcome and Manager.async_clear_local_failure_for_removed_trigger
  - BranchOutcome.identity and BranchOutcome.device_name; local_actions.branch_error
  - ApprovalView.replaced_trigger_count, Manager.local_replaced_trigger_count, approval placeholder `replaced`
affects: [11-08, 11-09, 11-10, 11-12]

# Actuals (#2632)
actuals:
  tokens: 12574
  tasks: 3
  commits: 8
plan_head_before: 2b9031805186190424868f387b995ab5324a1949
plan_head_after: 59a5fa035ab6e05c13e2d31ba4ac6ed7c8ff2fdc

tech-stack:
  added: []
  patterns:
    - "One manual-run gate (mode, breaker, effective runnability) shared by every non-state entry point; the re-trigger maps its result to existing ack words"
    - "A Repairs issue carries the identity it names in its data, so success and removal match it after a reload"
    - "An exception is attributed to the owner issue only when the trace cannot place it under the local branch alone"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-07-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-07-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-07-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-07-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-07-task3-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-07-task3-red.xml
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/local_actions.py
    - custom_components/mqtt_actions/runner.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/retrigger.py
    - custom_components/mqtt_actions/trust.py
    - custom_components/mqtt_actions/repairs.py
    - tests/test_local_actions_manager.py
    - tests/test_local_parallel.py
    - tests/test_local_actions_lifecycle.py
    - tests/test_repairs_flow.py

key-decisions:
  - "A tripped breaker refuses a test press only when the trigger's effective plan has a local branch; owner-only test presses keep bypassing the pause (Phase 2 D-13), and the re-trigger keeps refusing every paused device"
  - "A muted trigger (active replacement without actions) answers the re-trigger with error/no_actions whatever the approval; other non-runnable answers keep the previous rule"
  - "The local failure issue stores the identity of the named trigger (kind, normalized StateValue) in its issue data; success and removal match that, so a reload does not strand it"
  - "A failure outcome whose customization no longer exists is dropped, because nothing could ever clear the issue it would raise"
  - "An exception goes to the owner issue unless the trace shows errors under the local path and none under the owner path; the owner issue is cleared only by a run in which the owner branch took part"
  - "The replaced-trigger count includes muted triggers (both are replacement records that exclude the owner branch); a local edit updates an existing approval request in place, keeping a dismissal"

patterns-established:
  - "Literal issue prefixes in RED tests so a missing constant fails on an assertion, not on an import"

requirements-completed: [MIR-03, MIR-09, MIR-10, MIR-12, MIR-13]

coverage:
  - id: D1
    description: "State change, native test button, legacy test topic and re-trigger run the same effective actions for owner-only, additive, replacement and mute, pending and approved; test runs leave baseline, startup window, breaker count/trip, revision and shared publishes unchanged"
    requirement: MIR-10
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_test_button_legacy_test_and_retrigger_run_what_a_state_change_runs (8 cases)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Observe, disabled and a tripped breaker refuse test and re-trigger runs of local actions; an overlay-free mirror's test press still bypasses the pause"
    requirement: MIR-09
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_actions_manager.py -k 'test_button or retrigger' tests/test_retrigger.py (89 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Acknowledgement status and reason vocabularies are byte-identical"
    requirement: MIR-10
    verification:
      - kind: unit
        ref: "tests/test_local_actions_manager.py#test_retrigger_acknowledgement_vocabulary_is_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "One independent local failure issue per device: escaped bounded device/trigger/time/error, latest failed trigger named, cleared only by that trigger's proven success or removal of its customization; owner success, other trigger, continued error, stop, mute, owner change and orphan keep it; invalid local actions at build raise it"
    requirement: MIR-13
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_parallel.py tests/test_local_actions_manager.py -k 'issue or failure or clear' (22 passed)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Owner action_failed issue is never set by a local-only exception nor cleared by a local-only success; owner failure and owner clear behavior is unchanged when the owner branch takes part"
    requirement: MIR-03
    verification:
      - kind: integration
        ref: "tests/test_local_parallel.py -k 'owner_failure_issue or owner_issue'"
        status: pass
    human_judgment: false
  - id: D6
    description: "Approval view and issue show the active replaced-trigger count; every-trigger-replaced keeps pending state, owner-only YAML, exact hash and refused adoption"
    requirement: MIR-12
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_actions_lifecycle.py tests/test_trust.py tests/test_repairs_flow.py (89 passed; 63 in trust+repairs)"
        status: pass
    human_judgment: false
  - id: D7
    description: "Translated wording of local_action_failed and of the approval count/owner-only explanation"
    verification: []
    human_judgment: true
    rationale: "Translations are owned by Plan 11-08 Task 3; until then the issue and the confirm step render without the new text"

duration: 19min
completed: 2026-10-21
---

# Phase 11 Plan 07: Unified Entry Points, Local Failure Issue and Approval Count Summary

**Test buttons, the legacy test topic and the re-trigger now run through one Manager gate (`run_manual`: mode, breaker, effective runnability), so they run exactly what a state change runs and the ack words are unchanged. Each mirror has one independent `local_action_failed_<id>` issue that names the latest failed local trigger and clears only on that trigger's proven success or on removal of its customization. The owner approval view and issue show how many triggers are replaced locally, without changing what is approved.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-10-21T01:41:56Z
- **Completed:** 2026-10-21T02:01:50Z
- **Tasks:** 3 (1 tracer, 2 TDD), 8 commits: 3 RED, 3 GREEN, 2 REFACTOR
- **Files:** 7 production modules and 4 test modules modified, 6 evidence files created

## Issue ids and placeholders

| Issue | Id | Fixable | Translation key | Placeholders |
|-------|----|---------|-----------------|--------------|
| Local failure (new) | `local_action_failed_<device id>` (`ISSUE_LOCAL_ACTION_FAILED_PREFIX`, in `ISSUE_DEVICE_PREFIXES`) | no, not persistent, severity error | `local_action_failed` | `device`, `trigger`, `time`, `error` |
| Owner approval (extended) | `approval_<device id>` (unchanged) | yes | `approval_required` | `device`, `owner`, `hash`, **`replaced`** |
| Approval confirm step (extended) | flow of `approval_<device id>` | - | `approval_required.fix_flow` | the 11 existing keys plus **`replaced`** |

- Local issue placeholders are cut first (`device`/`trigger` to `MAX_TEXT_LENGTH` 64, `error` to `MAX_ISSUE_ERROR_LENGTH` 500) and then markdown-escaped. They never contain actions, traces or variables.
- The local issue data is `{"kind", "state_value"}` (normalized). This is the identity that a success or a removal must match.
- `replaced` is the count of active replacement records on the mirror, muted ones included. Additive, orphan, other-kind and other-device records are not counted.

## Acknowledgement vocabulary (unchanged)

- Status words: `executed`, `not_approved`, `paused`, `observing`, `disabled`, `error`.
- Reason words: `unknown_device`, `bad_state`, `no_actions`, `not_runnable`, `offline`.
- Both sets are pinned by `test_retrigger_acknowledgement_vocabulary_is_unchanged`. `ManualRunResult` is local only, and `retrigger._ANSWERS` maps each result to an existing pair.

## Entry-point gate (Task 1)

`Manager.run_manual(device, trigger, *, pause_spares_owner)`:

1. Disabled answers `DISABLED`, and observe answers `OBSERVING`.
2. A tripped breaker answers `PAUSED` in two cases: always for the re-trigger, and for a test press only when the trigger's current plan has a local branch.
3. A trigger that cannot run answers through `_not_runnable`:
   - A muted trigger answers `NO_ACTIONS`.
   - A pending or blocked owner answers `NOT_APPROVED`.
   - Any other trigger answers `NOT_RUNNABLE`, or `NO_ACTIONS` when it has no actions.
4. Otherwise it enqueues `test=True` and answers `EXECUTED`. It never touches the tracker, baseline, breaker count, revision or state topic.

## Local failure lifecycle (Task 2)

- The runner hands every local outcome to `Manager.async_report_local_outcome`. Each outcome carries `identity` and `device_name`, and a build-time failure has generation 0.
  - **Failure:** the issue is created or updated only while the customization still exists.
  - **Success:** the issue is deleted only when its stored identity equals the outcome's identity.
- `async_remove_local_action` calls `async_clear_local_failure_for_removed_trigger` after the durable save.
- 11-03 hand-offs, all closed:
  - (a) A local-only forwarded exception no longer reaches the owner `report_failure`. `_owner_error` uses the owner trace error when there is one.
  - (b) The owner `clear_issue` runs only when the owner branch was part of the run.
  - (c) Invalid local actions at build time raise the local issue.
- 11-06 hand-off: an owner content change keeps the unrelated local issue (pinned in `test_local_failure_issue_survives_owner_success_continued_error_stop_mute_and_owner_change`).
- Device removal (prune, tombstone, adoption, release) deletes the local issue with every other per-device family through `ISSUE_DEVICE_PREFIXES`. This happens because the device is gone, not because of a recovery.

## TDD Evidence

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 (tracer) | `8afd613` | `tests/test_local_actions_manager.py::test_test_button_and_retrigger_refuse_local_runs_while_the_breaker_is_tripped` | RED_EVIDENCE_OK | `99232a5` | `ab5344c` |
| 2 | `82e28e5` | `tests/test_local_actions_manager.py::test_local_failure_raises_an_independent_issue_naming_the_trigger_and_error` | RED_EVIDENCE_OK | `a0600bd` | `28e52b0` |
| 3 | `5689312` | `tests/test_repairs_flow.py::test_approval_issue_is_created_fixable_with_hash_data` | RED_EVIDENCE_OK | `59a5fa0` | none needed |

Semantic assessments (the full text is in `tdd/11-07-task{1,2,3}-red.json`):

- **RED 1:** valid. Both test presses ran the local branches although the breaker was tripped: the counts were (4, 3) instead of (3, 2).
  - In the same run, the `mute_pending` and `mute_approved` parity rows failed on the re-trigger answer (`not_approved` and `error/not_runnable`). Their run sets already matched.
  - The other 10 tests passed as characterization tests.
- **RED 2:** valid. No local issue existed, and the forwarded exception went to the owner path.
  - The other Manager tests failed on their first local-issue assertion.
  - The constant test failed on its assertion, because `getattr` returned None.
  - The removed-customization test raised TypeError on the new `BranchOutcome` keywords. It was not a target and is disclosed here.
  - The 4 runner tests failed on planned assertions.
- **RED 3:** valid. The exact placeholder equality differed only by the missing `replaced: "0"`. The assertion was extended, not relaxed.
  - The flow key-set test failed the same way.
  - The 2 lifecycle tests failed on the missing `replaced_trigger_count` (AttributeError). They were not targets and are disclosed here.

The tracer gate after Task 1 re-ran `<verify>` green (89 passed) before expansion.

## Verification

- Task 1: `uv run pytest -q tests/test_local_actions_manager.py -k "test_button or retrigger" tests/test_retrigger.py` → 89 passed.
- Task 2: `uv run pytest -q tests/test_local_parallel.py tests/test_local_actions_manager.py -k "issue or failure or clear"` → 22 passed.
- Task 3: `uv run pytest -q tests/test_local_actions_lifecycle.py tests/test_trust.py tests/test_repairs_flow.py` → 89 passed. The trust and repairs suites ran unfiltered: 63 tests collected and passed.
- Full tiers, with no `--deselect`:
  - Unit (`-m "not broker and not multi_instance"`): 1819 passed, 2 xfailed. The xfails are the older ones in `tests/test_takeover.py`.
  - Multi-instance: 173 passed.
  - Broker: 18 passed.
- `uv run ruff check` and `ruff format --check` are clean on `custom_components` and `tests`.

## Task Commits

1. **Task 1 (tracer): entry-point parity and gates.** `8afd613` (test), `99232a5` (feat), `ab5344c` (refactor).
2. **Task 2: independent local failure issue.** `82e28e5` (test), `a0600bd` (feat), `28e52b0` (refactor).
3. **Task 3: approval replaced-trigger count.** `5689312` (test), `59a5fa0` (feat).

## Decisions Made

See `key-decisions` in the frontmatter. The two choices that go beyond the plan text:

- **Pause semantics.** A test press on an owner-only plan keeps the Phase 2 D-13 bypass. The pin `test_test_press_is_not_counted_and_works_while_paused` stays green. The reason is RESEARCH pitfall 8: keep the historical bypass unless MIR-09 requires a change.
- **Mute answer.** A muted trigger answers `error/no_actions`. Previously it answered `not_approved` or `not_runnable`. Approving the owner would not make a muted trigger run, so both old answers were misleading. The word sets are unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Failure outcome of a customization removed during an in-flight run**
- **Found during:** Task 2 GREEN, while designing the clear conditions.
- **Issue:** A removal rebuilds the mirror, but the old run can still report a failure. That would raise an issue that nothing can clear.
- **Fix:** A failure is shown only while the record of its identity exists. This is pinned by `test_failure_outcome_of_a_removed_customization_raises_no_local_issue`.
- **Commit:** `a0600bd`

**2. [Rule 2 - Missing critical] Approval request count kept current without resetting a dismissal**
- **Found during:** Task 3 GREEN.
- **Issue:** `_sync_approval_issues` deletes and recreates the request, which would un-dismiss it. Without a refresh, a local edit would leave a stale count.
- **Fix:** `_refresh_approval_count` updates an existing request in place after each durable local commit. It never creates, deletes or reclassifies a request.
- **Commit:** `59a5fa0`

**3. [Test fixture] Select premise in the orphan test**
- **Found during:** Task 2 GREEN.
- **Issue:** The RED version reduced the owner Select to one option. The document parser does not accept that, so the owner change never applied.
- **Fix:** The owner now swaps `cozy` for `party`. No assertion changed.
- **Commit:** `a0600bd`

**4. [Interface] `BranchOutcome` gained `identity` and `device_name`**
- The new mirror's Script is built before the mirror is registered, so the Manager cannot resolve the device for a build-time failure.
- The plan's key link ("BranchOutcome callback carries trigger identity") asked for this. Both fields are keyword fields with defaults, so existing constructions are unchanged.

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2), 1 fixture correction and 1 interface note. **Impact:** all of them tighten D-17 and D-19. There is no scope creep and no wire change.

## Known Stubs

- `local_action_failed` has no title or description in `translations/en.json` and `de.json` yet. The approval confirm text does not use `{replaced}` yet, and does not yet state that local actions may already run and that approval concerns owner actions only.
  - Plan 11-08 Task 3 owns that bilingual wording. It is recorded in `.planning/WINDOWS.md` as a stub for phase 11.
  - The runtime placeholders are already supplied.

## Threat Flags

None. The surface is T-11-20 to T-11-23 of this plan's register:
- The receiver gates and order are unchanged, and no ack word was added.
- Recovery requires the same identity plus a proven success.
- The count is count-only, and the hash, YAML and approval state are unchanged.
- Placeholders are escaped and bounded, with no actions or traces.

## Hand-offs

- **Plan 11-08:**
  - Add the `issues.local_action_failed` title and description (placeholders `device`, `trigger`, `time`, `error`) in en and de.
  - Add the approval confirm wording with `{replaced}` and the owner-only explanation.
  - Extend `tests/test_translations.py` for the new variables.
- **Plan 11-10:** `Manager.run_manual` is the single production path for test and re-trigger in multi-instance scenarios. `ManualRunResult` never reaches the wire.
- **Plan 11-12:** troubleshooting must document `local_action_failed`: when it clears, and that removing the device deletes it.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None.

## Next Phase Readiness

Plans 11-08 to 11-13 can rely on one manual-run gate, the local issue family and the approval count. Every wave gate still runs the unfiltered unit tier.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

All 17 created/modified files exist, all 8 task commits are ancestors of HEAD, and the three RED records classify as RED_EVIDENCE_OK.
