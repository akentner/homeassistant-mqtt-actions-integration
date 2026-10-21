---
phase: 11-local-actions-on-mirrors
plan: 19
subsystem: local-actions
tags: [repairs, issue-registry, local-actions, docs, translations, tdd, gap-closure]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-18 WR-01 fix (tombstone keeps local actions), 11-23 contract amendments (D-19 amended 2026-10-21)"
provides:
  - "Manager.async_set_local_action clears local_action_failed after a durable save of the named trigger without local actions"
  - "WR-02 regression tests and the renamed D-19 survival test"
  - "en/de issue text, troubleshooting, README and release-notes draft name the save without local actions"
  - "11-REVIEW-DISPOSITION WR-02 = fixed, open 9"
affects: [11-20, 11-21, 11-22, phase-12-release]

plan_head_before: 0abff2600117c6b38848670de05b5368ee705f8f
plan_head_after: 6d4b9e2584da5e6d1076ec0d11208c51db44e654
actuals:
  tokens: 9982
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "A local failure issue clears on a durable state change only after _async_commit_local_records returned, so a failed save never clears"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-19-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-19-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-19-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-19-task2-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - tests/test_local_actions_manager.py
    - tests/test_docs.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/troubleshooting.md
    - README.md
    - .planning/phases/11-local-actions-on-mirrors/11-release-notes.md
    - .planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md
    - .planning/phases/11-local-actions-on-mirrors/11-18-SUMMARY.md

key-decisions:
  - "A durable save of the named trigger whose record has no local actions (mute, or additive with []) clears local_action_failed; the clear runs after the save and only while the issue names that identity (D-19 amended, WR-02)"
  - "An inactive record (orphan or other kind) saved without actions clears the issue that names it too, because it can never fail locally (flagged assumption of the plan, implemented as is)"

patterns-established:
  - "Clearing a local failure issue is either an outcome (proven success) or a durable record change (save without actions, removal); nothing else"

requirements-completed: [MIR-05, MIR-13, MIR-15]

coverage:
  - id: D1
    description: "A durable save of the named trigger without local actions (mute or empty additive) deletes its local_action_failed issue"
    requirement: MIR-13
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_saving_the_named_trigger_without_local_actions_clears_its_local_failure_issue"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_local_failure_issue_survives_owner_success_continued_error_stop_and_owner_change"
        status: pass
    human_judgment: false
  - id: D2
    description: "A failed save, a save of another trigger and a save with local actions keep the issue (T-11-49)"
    requirement: MIR-05
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_only_a_durable_save_of_the_named_trigger_without_local_actions_clears_the_issue"
        status: pass
    human_judgment: false
  - id: D3
    description: "en/de issue text, troubleshooting and README name the save without local actions; placeholders unchanged"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_local_failure_texts_name_every_way_the_issue_clears"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "German wording of the issue text reads naturally in the Repairs UI"
    verification: []
    human_judgment: true
    rationale: "Tests check the phrase and placeholders, not how the sentence reads to a German user"

duration: 7min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 19: Save Without Local Actions Clears the Local Failure Issue Summary

**A durable save of the named trigger without local actions (a mute or empty additive actions) now deletes its `local_action_failed` issue. A failed save, a save of another trigger and a save with local actions keep it. en/de text, troubleshooting, README and the release-notes draft name this third way to clear the issue (WR-02).**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-21T07:46:03Z
- **Completed:** 2026-10-21T07:53:06Z
- **Tasks:** 3
- **Files modified:** 14 (including 4 RED evidence files)

## Accomplishments

- `Manager.async_set_local_action` calls `_clear_local_failure_naming(identity)` when `not record.actions`. The call comes after `_async_commit_local_records` returned and is still under the lock. A failed save raises before that line.
- The docstrings of `async_set_local_action`, `async_report_local_outcome` and `_create_local_failure_issue` name the save without local actions as a way to end the issue.
- Muting a failed trigger now ends its stale issue, and the mute (owner actions suppressed) stays in effect.
- The en and de issue text, the troubleshooting `local_action_failed` entry, the README `### Local failures and diagnostics` bullet and the release-notes Repairs bullet all list three ways the issue clears.
- 11-REVIEW-DISPOSITION.md: WR-02 is fixed (plan 11-19, 5bc5ed4), `open: 9`.

## Task Commits

1. **Task 1 (tracer): a save without local actions clears the issue**
   - RED `335ed96` (test)
   - GREEN `5bc5ed4` (feat)
2. **Task 2: en/de issue text, troubleshooting and README**
   - RED `343ca9e` (test)
   - GREEN `ce88aba` (docs)
3. **Task 3: release-notes draft, full gate and disposition WR-02 fixed:** `6d4b9e2` (docs)

**Plan metadata:** recorded in the final docs(11-19) commit.

## TDD Gate Compliance

- **Task 1 RED** (`tdd/11-19-task1-red.json`, RED_EVIDENCE_OK, JUnit):
  - The target `test_saving_the_named_trigger_without_local_actions_clears_its_local_failure_issue` ran (1 test, 0 errors, 0 skipped) and its premise held: the ON edge raised the issue naming ON.
  - It failed on the planned `_local_issue(...) is None` assertion right after the mute save.
  - The companion tests failed at their planned points too: the renamed survival test on its mute step (line 1002), and the T-11-49 test only on the final durable empty save (line 1104), after its other-trigger, non-empty-save and failed-save checks had passed.
  - Semantic assessment: valid RED.
- **Task 1 GREEN:** the three target tests pass, and the four local-action modules pass (132 tests).
- **Task 2 RED** (`tdd/11-19-task2-red.json`, RED_EVIDENCE_OK, JUnit): `test_local_failure_texts_name_every_way_the_issue_clears` executed and failed on the planned en phrase assertion. It was not an import or fixture fault. Semantic assessment: valid RED.
- **Task 2 GREEN:** `tests/test_docs.py` and `tests/test_translations.py` pass (110 tests).
- The RED commits precede their GREEN commits. There was no REFACTOR.

## Survival Test Rename

- **Old:** `test_local_failure_issue_survives_owner_success_continued_error_stop_mute_and_owner_change`
- **New:** `test_local_failure_issue_survives_owner_success_continued_error_stop_and_owner_change`
- The mute step now asserts the issue is gone ("muting the named trigger ends its local failure issue (WR-02)").
- The test then raises the issue again (additive flaky ON, failing set back to `{"on"}`, OFF then ON edge) before the owner-content-change step. That step still asserts the issue survives.

## Final Issue Text (last sentence)

- **en:** "It disappears when the local actions of that trigger run successfully, when you save that trigger without local actions, or when you remove its local customization in the options of MQTT Actions."
- **de:** "Es verschwindet, wenn die lokalen Aktionen dieses Auslösers erfolgreich laufen, wenn du diesen Auslöser ohne lokale Aktionen speicherst oder wenn du seine lokale Anpassung in den Optionen von MQTT Actions entfernst."
- The placeholders are still exactly {device}, {trigger}, {time} and {error} in both languages.

## Disposition Change

- WR-02 changed from `open` to `fixed`. The row reads `| WR-02 | warning | fixed | plan 11-19, 5bc5ed4 |`.
- Frontmatter `open` went from 10 to 9. WR-01 stays fixed, and WR-03, WR-04 and IN-01..IN-07 stay open.

## Verification

- Ruff check and format check are clean (111 files).
- Full required-broker suite (`MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`, all tiers, nothing deselected):

Full suite: 2077 passed, 2 xfailed

- The baseline from 11-18 was 2074; the 3 new tests account for the increase.

## Files Created/Modified

- `custom_components/mqtt_actions/manager.py`: the conditional clear after a durable save, plus three docstrings.
- `tests/test_local_actions_manager.py`: two WR-02 tests and the renamed survival test.
- `tests/test_docs.py`: `test_local_failure_texts_name_every_way_the_issue_clears`.
- `custom_components/mqtt_actions/translations/en.json` and `de.json`: `issues.local_action_failed.description`.
- `docs/troubleshooting.md`: the "What to do" text of `local_action_failed` names three ways to clear the issue. The paragraph was reflowed to 120 columns.
- `README.md`: the first bullet of Local failures and diagnostics names the same three ways.
- `.planning/phases/11-local-actions-on-mirrors/11-release-notes.md`: Repairs bullet. The draft is still labelled unpublished.
- `.planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md`: WR-02 fixed.
- `.planning/phases/11-local-actions-on-mirrors/11-18-SUMMARY.md`: hand-off line reworded (see Deviations).

## Decisions Made

- The troubleshooting text keeps the literal "Only a later successful run of the same trigger clears the issue" and limits it with "while that trigger still has local actions". It then names the save without local actions and the removal. This keeps the existing `test_troubleshooting_explains_when_the_local_failure_issue_clears` phrases unchanged, and the text stays accurate.
- The flagged assumption of the plan is implemented as is: an inactive record saved without actions also clears the issue that names it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The 11-18-SUMMARY baseline line was not unique**
- **Found during:** Task 3 (full-suite gate)
- **Issue:** 11-18-SUMMARY.md had two lines that match `Full suite: [0-9]+ passed`: the result line 122 and the hand-off line 242, which quoted it in backticks. The gate requires exactly one match and would have exited 3 before running the suite.
- **Fix:** Reworded hand-off line 242 to "the full-suite count recorded above (2074 passed, 2 xfailed)". The result line is unchanged.
- **Files modified:** .planning/phases/11-local-actions-on-mirrors/11-18-SUMMARY.md
- **Verification:** `grep -cE` returns 1. The gate passed with baseline 2074 and result 2077.
- **Committed in:** 6d4b9e2

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No code or behavior impact. This SUMMARY carries the `Full suite` literal on one line only, so the 11-20 gate can read it.

## Issues Encountered

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- WR-02 is closed. WR-03, WR-04 and IN-01..IN-07 remain open for the next gap-closure plans.
- Plan 11-20 reads its full-suite baseline from the single result line in the Verification section above.

## Self-Check: PASSED

- All 4 RED evidence files exist, and all 10 modified files are present.
- Commits 335ed96, 5bc5ed4, 343ca9e, ce88aba and 6d4b9e2 are ancestors of HEAD.
- `grep -cE "Full suite: [0-9]+ passed"` on this file returns 1.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*
