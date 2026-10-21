---
phase: 11-local-actions-on-mirrors
plan: 15
subsystem: repairs
tags: [issue-registry, repairs, local-actions, local-store, gap-closure, tdd]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-05 local Store load before mirrors and refused-load start; 11-09 hub removal of the local Store (D-08); 11-11 ledger finding F-02 / gap G-02; 11-14 success-branch cleanup in _async_load_local_actions"
provides:
  - "ISSUE_LOCAL_ACTIONS_UNREADABLE = \"local_actions_unreadable\" (manager.py): one instance issue, id and translation key"
  - "_async_load_local_actions raises it on a refused load (not fixable, not persistent, ERROR, no placeholders) and deletes it on a successful load"
  - "async_remove_local_state deletes it by id in both removal modes"
  - "issues.local_actions_unreadable in en.json and de.json; troubleshooting entry; ledger row F-02 FIXED"
affects: [11-13 final gate precondition, 11-16, 11-17 (also change manager.py)]

actuals:
  tokens: 2922
  tasks: 2
  commits: 5
plan_head_before: 1c7a806f2e2f5d0d2d99dc2ebe094005d2e0a5f3
plan_head_after: 22eaebfff3cfea23b6cc25e7459fe9aa2adc32b7

tech-stack:
  added: []
  patterns:
    - "A refused Store load is surfaced as a fixed-id, non-persistent instance issue; every start decides again"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-15-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-15-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-15-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-15-task2-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - tests/test_local_actions_manager.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/troubleshooting.md
    - .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md

key-decisions:
  - "G-02: a refused local Store load raises the instance issue local_actions_unreadable (non-fixable, non-persistent, ERROR, no placeholders); a successful load and hub removal delete it; LocalActionsStore and its never-overwrite refusal are unchanged (T-11-09)"
  - "G-02 edge assumption: an envelope that is readable but has no record list is a readable, empty Store and raises no issue; only a newer major, an unknown version or an unreadable file count as refused"

patterns-established:
  - "Instance issues that hub removal must delete go into the instance_issues set of async_remove_local_state"

requirements-completed: [MIR-05, MIR-06, MIR-15]

coverage:
  - id: D1
    description: "A refused local Store load raises one instance issue, keeps the file bytes, applies no overlay (the approved owner action runs on the replaced trigger) and refuses an edit with save_failed"
    requirement: MIR-05
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay"
        status: pass
    human_judgment: false
  - id: D2
    description: "The issue is deleted at the next start whose local load succeeds, and by hub removal in keep and delete mode"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_readable_local_store_deletes_the_unreadable_issue_at_the_next_start"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_hub_removal_deletes_the_unreadable_local_store_issue"
        status: pass
    human_judgment: false
  - id: D3
    description: "English and German issue text without placeholders, and a troubleshooting entry for local_actions_unreadable"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_local_actions_manager.py#test_unreadable_local_store_issue_has_english_and_german_text_without_placeholders"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_en_and_de_have_identical_keys"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_troubleshooting_covers_every_issue_key"
        status: pass
    human_judgment: false
  - id: D4
    description: "Natural, accurate German wording of the issue text"
    requirement: MIR-15
    human_judgment: true
    rationale: "No test can judge whether the German text reads naturally; the tests only pin presence, placeholders and difference from English"
  - id: D5
    description: "Ledger row F-02 FIXED with the Task 1 GREEN commit and the regression test id; F-01 FIXED, F-03 and F-04 still ROUTED"
    verification:
      - kind: other
        ref: "plan 11-15 Task 2 ledger verify command (grep of row F-02, sha ancestry and feat(11-15) subject)"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 15: Visible refused local Store load (G-02) Summary

**A local actions Store that this release cannot read now raises one non-fixable instance issue, `local_actions_unreadable`, in English and German. The refusal itself is unchanged: the file is never overwritten, edits fail with `save_failed`, and no overlay applies. The issue goes away at the next start that can read the file, and on hub removal.**

## Performance

- **Duration:** about 8 min (2026-10-21T04:30:06Z to 2026-10-21T04:38:01Z)
- **Tasks:** 2 of 2
- **Files modified:** 6 source/test/doc/ledger files plus 4 RED evidence files

## Accomplishments

- `manager.py` has a new module constant, `ISSUE_LOCAL_ACTIONS_UNREADABLE = "local_actions_unreadable"`. It serves as both the issue id and the translation key.
- The except branch of `_async_load_local_actions` keeps `_local_records = ()` and the warning. It then creates the issue with `is_fixable=False`, `is_persistent=False` and `severity=ERROR`, with no placeholders and no record content.
- The success (`else`) branch deletes the issue, just before the 11-14 call of `_delete_local_failure_issues_without_record()`.
- `async_remove_local_state` has the new id in its `instance_issues` set, so both removal modes delete it.
- `LocalActionsStore` and `const.py` are unchanged.
- `issues.local_actions_unreadable` is in en.json and de.json, and `docs/troubleshooting.md` has a `### \`local_actions_unreadable\`` section right after `local_action_failed`.
- Ledger row F-02 is FIXED and gap G-02 is resolved.

## Task Commits

| Task | Gate | Commit | Message |
|------|------|--------|---------|
| 1 | RED | ccd7299 | test(11-15): add failing test for the instance issue of an unreadable local Store |
| 1 | GREEN | 44c5fe6 | feat(11-15): raise one instance issue while the local actions Store cannot be read |
| 2 | RED | 8612fb9 | test(11-15): add failing test for the English and German text of the unreadable issue |
| 2 | GREEN | e22667f | feat(11-15): explain the unreadable local actions issue in English, German and the docs |
| 2 | ledger | 22eaebf | docs(11-15): set ledger row F-02 to FIXED and resolve gap G-02 |

No REFACTOR commit was needed.

## RED semantic assessments

- **Task 1** (`tdd/11-15-task1-red.json`, RED_EVIDENCE_OK). The target ran: 1 test, 0 errors, 0 skipped. Setup with the version 2 envelope, delivery of the owner document and the retained OFF state all succeeded. The test failed on its first planned assertion, that the issue exists (`assert None is not None`), because the refused-load branch only logged a warning. This is exactly G-02, not a setup or fixture fault. The two recovery tests also failed at RED, on their premise that the issue exists.
- **Task 2** (`tdd/11-15-task2-red.json`, RED_EVIDENCE_OK). The target ran and failed on the planned assertion for the English title (`en: issues.local_actions_unreadable.title is missing or empty`). It did not fail with a KeyError, because the lookup uses `.get`.

## Final issue texts

**en**
- Title: "Local actions cannot be read"
- Description: "The saved local actions of this instance cannot be read. A newer version of MQTT Actions saved them, or the file is damaged.

  Until they can be read, local actions, replacements and mutes are not applied. Approved owner actions run on every trigger, also on triggers you replaced or muted here. Editing local actions is refused, and the file is not changed.

  Update MQTT Actions to the version that saved them, or restore the file from a backup. Then restart Home Assistant or reload the integration."

**de**
- Title: "Lokale Aktionen können nicht gelesen werden"
- Description: "Die gespeicherten lokalen Aktionen dieser Instanz können nicht gelesen werden. Eine neuere Version von MQTT Actions hat sie gespeichert, oder die Datei ist beschädigt.

  Bis sie wieder lesbar sind, werden lokale Aktionen, Ersetzungen und Stummschaltungen nicht angewendet. Freigegebene Aktionen der Besitzerin laufen bei jedem Auslöser, auch bei Auslösern, die du hier ersetzt oder stummgeschaltet hast. Lokale Aktionen können nicht bearbeitet werden, und die Datei bleibt unverändert.

  Aktualisiere MQTT Actions auf die Version, die sie gespeichert hat, oder stelle die Datei aus einem Backup wieder her. Starte danach Home Assistant neu oder lade die Integration neu."

## Edge-probe assumption

An envelope that is readable but has no record list counts as a readable, empty Store, so it raises no issue. The 11-04 parser decision stays out of scope. This issue covers only a refused load: a newer major version, an unknown version or an unreadable file. Because the issue id is fixed, there is at most one issue per instance. A second refused start updates it in place.

## Ledger row change

- F-02: `ROUTED` became `FIXED`. The Gap column changed from `G-02` to `G-02 fixed in 44c5fe6`. The regression test id is unchanged.
- The G-02 YAML now reads `status: resolved` with `fixed_in: "44c5fe6 (plan 11-15)"`.
- Ledger summary: 2 routed (F-03, F-04) and 2 fixed (F-01, F-02). The routed-gap line now says that 2 of 4 are fixed. No other row changed.

## Decisions Made

- The hub-removal test runs keep mode and then delete mode one after the other in one test, with no parametrization. That way the plan's verify command reports exactly "3 passed" for the three node ids.
- The tests use the issue id as a literal (`UNREADABLE_ISSUE_ID`), following the 11-07 pattern. A RED run therefore fails on an assertion, not on an import.

## Deviations from Plan

### Auto-fixed Issues

**1. [Minor] RED evidence files committed with each RED commit**
- The plan says to commit the RED test "with the test file only". As in plans 11-07, 11-12 and 11-14, the `tdd/*-red.{json,xml}` evidence went into the same commit. No `test(11-15)` commit contains a production file, which is what the verify command checks.

**2. [Minor] Hub-removal modes in one test instead of parametrization**
- With `@pytest.mark.parametrize`, the node id would collect 2 tests, and the Task 1 verify command requires "3 passed". Both modes are still covered. Commit ccd7299.

**Total deviations:** 2 minor (evidence placement, test shape). **Impact:** none on behavior or scope.

## TDD Gate Compliance

- Every task has its RED commit before its GREEN commit: ccd7299 then 44c5fe6, and 8612fb9 then e22667f.
- Tracer gate (Task 1): `human_verify_mode` is end-of-phase and the verify step is automated only. The tracer `<verify>` was re-run (3 passed, 134 passed in the five-module set, the RED/commit/scope script passed), so expansion went ahead.

## Verification

- Task 1: the three target tests gave 3 passed. Manager, lifecycle, store, hub_removal and kept_duplicates gave 134 passed. The RED evidence, commit scope and unchanged-file script passed.
- Task 2: manager, translations and docs gave 153 passed. RED evidence, the troubleshooting phrases ("not applied", "refused", "not changed", "newer version", "backup"), `ruff check .` and `ruff format --check .` all passed.
- `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`: **2068 passed, 2 xfailed**, with nothing deselected or skipped (baseline 2056).
- The ledger verify command passed.

## Issues Encountered

- `docs/troubleshooting.md` already has four lines of 121 characters, at lines 63, 171, 232 and 259. They were there before this plan and are out of scope. The new section stays within 120 characters.

## Next Phase Readiness

Ready for 11-16 (G-03). Plan 11-13 still halts on its precondition until F-03 and F-04 read FIXED.

## Self-Check: PASSED

- All 6 modified files and 4 RED evidence files exist.
- All 5 commits (ccd7299, 44c5fe6, 8612fb9, e22667f, 22eaebf) are ancestors of HEAD.
