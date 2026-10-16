---
phase: 10-review-findings-and-native-migration-extraction
plan: 10
subsystem: native-migration
tags: [fix-08, review-2-in-03, repairs, hub-removal, docs, tdd]
status: complete
requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-09 (const.ISSUE_KEPT_DUPLICATES, issues.kept_duplicates in en and de, the dismissal mechanism of _refresh_kept_duplicates, the short troubleshooting entry); plan 10-08 (the re-enable sentence in README and troubleshooting, the FIX-05 doc tests)"
provides:
  - "manager.async_remove_local_state deletes ISSUE_KEPT_DUPLICATES in both hub removal modes"
  - "tests/test_translations.py NEW_ISSUES pins kept_duplicates to count, customized and rejected in en and de"
  - "README export section and troubleshooting enabled-duplicate section describe the kept-duplicates warning, pinned by tests/test_docs.py"
affects: [11 (MIR-01)]
actuals:
  tokens: 2350
  tasks: 2
  commits: 4
plan_head_before: 07953eed593b5867b36bea7e2051cb47a358a6c2
plan_head_after: 15052f5531d224e78d66324543be63e259e3306a
tech-stack:
  added: []
  patterns:
    - "Per-instance issues are deleted by id from one named set in async_remove_local_state; per-device families stay in ISSUE_DEVICE_PREFIXES"
key-files:
  created:
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-10-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-10-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-10-task2-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-10-task2-red.json
  modified:
    - custom_components/mqtt_actions/manager.py
    - tests/test_hub_removal.py
    - tests/test_translations.py
    - tests/test_docs.py
    - README.md
    - docs/troubleshooting.md
key-decisions:
  - "The per-instance issue ids of the hub-removal cleanup are a named local set (instance_issues) instead of an inline set literal, because Ruff format split the four-item inline set over seven lines; behavior unchanged"
  - "The doc text is the same paragraph in README and troubleshooting, inserted right after the 10-08 re-enable sentence; troubleshooting adds the D-03 sentence that integration-disabled duplicates are not listed and are removed at a later start, as described below in that section"
  - "The 10-09 '### kept_duplicates' entry under Repairs issues stays as it is; the new text sits in the two duplicate sections, so nothing is duplicated under Repairs issues"
patterns-established:
  - "Section-scoped doc test: a phrase must appear inside a named markdown section, so a file-wide mention elsewhere cannot satisfy it"
requirements-completed: [FIX-08]
coverage:
  - id: D1
    description: "Removing the hub deletes the kept-duplicates warning in keep and delete mode; every other issue cleanup is unchanged"
    requirement: FIX-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_hub_removal_deletes_the_kept_duplicates_warning"
        status: pass
      - kind: integration
        ref: "tests/test_hub_removal.py#test_both_modes_remove_store_and_every_issue_prefix"
        status: pass
    human_judgment: false
  - id: D2
    description: "The kept_duplicates title and description exist in en and de with exactly count, customized and rejected"
    requirement: FIX-08
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_issue_texts_exist_in_both_languages"
        status: pass
    human_judgment: false
  - id: D3
    description: "README and troubleshooting name the warning, say it never deletes or disables, advise disabling instead of deleting, say when it goes away, describe the dismissal behavior, and troubleshooting says integration-disabled duplicates are not listed"
    requirement: FIX-08
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_the_docs_describe_the_kept_duplicates_warning"
        status: pass
    human_judgment: false
  - id: D4
    description: "The added doc paragraph reads clearly for a user and gives correct advice (disable, never delete)"
    requirement: FIX-08
    verification: []
    human_judgment: true
    rationale: "The doc test pins phrases; whether the paragraph reads well in context needs a human reader"
  - id: D5
    description: "No regression: full suite, Ruff check and Ruff format green; HEAD on the phase branch; main unchanged"
    verification:
      - kind: other
        ref: "uv run ruff check . && uv run ruff format --check . && uv run pytest -q (1767 passed, 2 xfailed); git rev-parse main == 601a41c"
        status: pass
    human_judgment: false
duration: 8min
completed: 2026-10-16
---

# Phase 10 Plan 10: Kept-Duplicates Warning Cleanup and Docs Summary

**Removing the hub now deletes the `kept_duplicates` Repairs warning in both removal modes. Its placeholders `count`, `customized` and `rejected` are pinned in English and German. The README export section and the troubleshooting enabled-duplicate section say what the warning lists, that MQTT Actions never deletes or disables those duplicates, that you should disable a duplicate instead of deleting it, when the warning goes away, and how a dismissal behaves (FIX-08, D-02, D-03).**

## Performance

- **Duration:** about 8 min
- **Started:** 2026-10-16T14:33:34Z
- **Completed:** 2026-10-16T14:41:04Z
- **Tasks:** 2 (Task 1 tracer, Task 2 auto)
- **Files modified:** 6 source, test and doc files, plus 4 RED evidence files

## Accomplishments

- `manager.async_remove_local_state` imports `ISSUE_KEPT_DUPLICATES` and deletes it by id, together with `ISSUE_DISCOVERY_DISABLED`, `ISSUE_DUPLICATE_INSTANCE_ID` and `ISSUE_NATIVE_CUTOVER_WAITING`. These ids are now in a named local set, `instance_issues`. `ISSUE_DEVICE_PREFIXES` is unchanged (D-02: one issue per instance).
- `tests/test_hub_removal.py::test_hub_removal_deletes_the_kept_duplicates_warning[keep, delete]`. The test creates the warning with its three placeholders, removes the hub, and checks that the integration has no issue left.
- `tests/test_translations.py` `NEW_ISSUES["kept_duplicates"] = {"count", "customized", "rejected"}`. The existing parity test now checks the title and the description variables of this issue in en and de.
- README `## MQTT Discovery export` and troubleshooting `### An enabled duplicate after the export prefix was set to the core prefix` both have the new warning paragraph:
  - what the warning lists, grouped by reason
  - "never deletes or disables"
  - disable a duplicate instead of deleting it, and why (CR-01)
  - the warning goes away at the next start once none is left
  - a dismissal holds while the list is unchanged; the warning shows again when the list changes, and it comes back after a Home Assistant restart while duplicates remain
  - troubleshooting only: duplicates that MQTT Actions disabled itself are not listed (D-03)
- `tests/test_docs.py::test_the_docs_describe_the_kept_duplicates_warning` checks these phrases inside both sections: `kept_duplicates`, `never deletes`, `repairs`, `dismiss`, `after a home assistant restart`. In troubleshooting it also checks `not listed`.

## Task Commits

1. **Task 1 (tracer): removing the hub deletes the kept-duplicates warning in both modes, and its placeholders are pinned in en and de.** RED `08e51dc` (test), GREEN `177b7d7` (fix)
2. **Task 2: README and troubleshooting describe the kept-duplicates warning, pinned by a doc test.** RED `f147451` (test), GREEN `15052f5` (docs)

**Plan metadata:** the docs commit that follows this SUMMARY

Tracer gate after Task 1: this was an interactive run with `human_verify_mode` set to end-of-phase, and the verify block has only `<automated>` steps. I re-ran the verify block (VERIFY_OK). The full suite was green (1766 passed, 2 xfailed), so the plan went on to Task 2 without a checkpoint.

## TDD Records

| Record | Target test | How it went red | Verdict |
|--------|-------------|-----------------|---------|
| `tdd/10-10-task1-red.{xml,json}` | `test_hub_removal_deletes_the_kept_duplicates_warning[keep]` (and `[delete]`) | Real RED on the 10-09 code: `assert ['kept_duplicates'] == []` at tests/test_hub_removal.py:261, in both modes | RED_EVIDENCE_OK |
| `tdd/10-10-task2-red.{xml,json}` | `test_the_docs_describe_the_kept_duplicates_warning` | Real RED on the 10-09 docs: "the README export section never says: kept_duplicates" | RED_EVIDENCE_OK |

How each RED was checked:
- Task 1: both parametrized targets ran (2 tests, 2 failures, 0 errors). Each failed on its last assertion. The premise checks before it passed: the issue existed before the removal, and `async_remove` returned True.
- Task 2: the check is limited to the two sections. The `### kept_duplicates` entry that 10-09 added under "Repairs issues" is outside both sections, so a grep over the whole file would already pass. The section test did not. `_section` returned the README export text (it is shown in the assertion message), so the RED does not come from an empty section.
- The translation pin was green from the start, because plan 10-09 shipped the texts. It is a pin, not a RED target.
- No mutant was used or committed.

## Files Created/Modified

- `custom_components/mqtt_actions/manager.py`: the import and the `instance_issues` set in `async_remove_local_state`
- `tests/test_hub_removal.py`: the `ISSUE_KEPT_DUPLICATES` import and the parametrized cleanup test
- `tests/test_translations.py`: the `NEW_ISSUES` entry
- `tests/test_docs.py`: the FIX-08 doc test
- `README.md`: the warning paragraph in the export section
- `docs/troubleshooting.md`: the warning paragraph and the D-03 sentence in the enabled-duplicate section

## Decisions Made

- The ids go into a named local set because Ruff format split the inline four-item set over seven lines. Behavior is unchanged, and `test_both_modes_remove_store_and_every_issue_prefix` passes without changes.
- Both documents get the same paragraph, so they cannot drift apart. The wording matches the en.json text from plan 10-09: "never deletes or disables", and disable instead of delete because of the Discovery message other instances use.
- The 10-09 entry under "Repairs issues" is left as it is. It already points to the enabled-duplicate section, and that section now has the full text.

## Deviations from Plan

None. The plan was executed as written. The named local set is formatting only, and Ruff format forced it.

## Issues Encountered

None.

## Threat Model

- T-10-15: `async_remove_local_state` deletes the warning in both modes, and both modes are tested.
- T-10-16: both documents say to disable a duplicate instead of deleting it, and say why (CR-01). Neither tells the user to delete an MQTT duplicate.
- T-10-SC: no package was installed.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- FIX-08 is complete: the warning (10-09), its cleanup with the hub, the en and de placeholder pin, and the docs (10-10).
- This is the last plan of phase 10, so the phase is ready for verification.
- HEAD is on `gsd/phase-10-review-findings-and-native-migration-extraction`, and `main` is still at `601a41c`.

## Self-Check: PASSED

- All four tdd/10-10-* files exist.
- The commits 08e51dc, 177b7d7, f147451 and 15052f5 are ancestors of HEAD.
- `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest -q` are green (1767 passed, 2 xfailed).
- Both RED records are RED_EVIDENCE_OK.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*
