---
phase: 10-review-findings-and-native-migration-extraction
plan: 09
subsystem: native-migration
tags: [fix-08, review-2-in-03, repairs, duplicate-guard, takeover, tdd, pin-tests]
status: complete
requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-05 (native_migration.py with TwinRemoval and the replay catch, takeover._remove_planned); plan 10-02 (tests/helpers.py)"
provides:
  - "takeover.KeptReason (CUSTOMIZED, TWIN_REJECTED), takeover._guard_candidates, takeover.kept_duplicates"
  - "native_migration.kept_duplicates_placeholders and NativeMigration._refresh_kept_duplicates at the three evaluation points"
  - "const.ISSUE_KEPT_DUPLICATES (one issue per instance, outside ISSUE_DEVICE_PREFIXES) and KEPT_DUPLICATES_MAX_SHOWN"
  - "issues.kept_duplicates in en.json and de.json"
affects: [10-10 (hub-removal cleanup of ISSUE_KEPT_DUPLICATES, the placeholder pin, README and troubleshooting text), 11 (MIR-01)]
actuals:
  tokens: 10300
  tasks: 2
  commits: 4
plan_head_before: 90a3f5c02b27c6124562574cd44ad8e6c9842533
plan_head_after: 2f5663716c76fe4665f365e9cc03873fd9e54fae
tech-stack:
  added: []
  patterns:
    - "A Repairs issue that follows a list compares its new placeholders with the registry entry: active and equal is left alone (a dismissal holds), anything else is deleted and created again"
    - "Two registry functions that must partition the same rows iterate one shared candidate iterator"
key-files:
  created:
    - tests/test_kept_duplicates.py
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-dismissal.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-refresh.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-rejected.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-rejected.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-names.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-names.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-goes-away.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-goes-away.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-changed.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-changed.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-cap.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-cap.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-partition.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-09-task2-red-partition.json
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/takeover.py
    - custom_components/mqtt_actions/native_migration.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/troubleshooting.md
    - tests/test_takeover.py
key-decisions:
  - "The kept-duplicates warning is one non-fixable issue per instance (kept_duplicates) with the placeholders count, customized and rejected; the ids are sorted, escaped and capped at 10 per reason, with a dash for an empty group"
  - "Dismissal: an active issue with equal placeholders is left alone; a changed list or an issue restored inactive after a Home Assistant restart is deleted and created again; an empty list deletes it. A dismissed warning therefore comes back once after a Home Assistant restart while duplicates remain"
  - "Reason precedence: a row next to a twin the user turned off is TWIN_REJECTED even when it is customized too"
  - "disable_duplicates and kept_duplicates iterate the shared takeover._guard_candidates, so every candidate is either disabled or reported as kept"
  - "The refresh runs at the end of every async_takeover path, at the end of _disable_duplicates once the guard ran, and at the end of every replay catch run past its running check; no new listener (D-04)"
patterns-established:
  - "Follow-the-list Repairs issue: compare placeholders and active state, then delete-then-create"
requirements-completed: [FIX-08]
coverage:
  - id: D1
    description: "A customized duplicate kept enabled is listed in one non-fixable warning after a restart; the row stays enabled"
    requirement: FIX-08
    verification:
      - kind: integration
        ref: "tests/test_kept_duplicates.py#test_a_customized_duplicate_kept_enabled_is_listed_in_one_warning"
        status: pass
    human_judgment: false
  - id: D2
    description: "A duplicate kept next to a native twin the user disabled is listed as rejected"
    requirement: FIX-08
    verification:
      - kind: integration
        ref: "tests/test_kept_duplicates.py#test_a_duplicate_kept_because_the_native_twin_was_turned_off_is_listed_as_rejected"
        status: pass
      - kind: integration
        ref: "tests/test_takeover.py#test_kept_duplicates_names_customized_and_rejected_rows_and_nothing_else"
        status: pass
    human_judgment: false
  - id: D3
    description: "The warning goes away once no kept duplicate remains, and the kept row's registry entry is equal before and after each refresh"
    requirement: FIX-08
    verification:
      - kind: integration
        ref: "tests/test_kept_duplicates.py#test_the_warning_goes_away_once_no_kept_duplicate_remains_and_no_row_is_touched"
        status: pass
    human_judgment: false
  - id: D4
    description: "A dismissal holds while the list does not change; a changed list shows the warning again"
    requirement: FIX-08
    verification:
      - kind: integration
        ref: "tests/test_kept_duplicates.py#test_an_unchanged_list_keeps_a_dismissal_within_a_run"
        status: pass
      - kind: integration
        ref: "tests/test_kept_duplicates.py#test_a_changed_list_shows_the_warning_again_after_a_dismissal"
        status: pass
    human_judgment: false
  - id: D5
    description: "The list is refreshed after a guard pass for a create event and after the replay catch"
    requirement: FIX-08
    verification:
      - kind: integration
        ref: "tests/test_kept_duplicates.py#test_the_warning_is_refreshed_after_a_guard_pass_and_after_the_catch"
        status: pass
    human_judgment: false
  - id: D6
    description: "The placeholders are sorted, escaped and capped at KEPT_DUPLICATES_MAX_SHOWN per reason"
    requirement: FIX-08
    verification:
      - kind: unit
        ref: "tests/test_kept_duplicates.py#test_the_placeholders_cap_and_escape_the_entity_ids"
        status: pass
    human_judgment: false
  - id: D7
    description: "The guard and the warning split the guard candidates over every guard case"
    requirement: FIX-08
    verification:
      - kind: integration
        ref: "tests/test_takeover.py#test_disable_duplicates_and_kept_duplicates_split_the_guard_candidates"
        status: pass
    human_judgment: false
  - id: D8
    description: "The en and de warning texts read naturally and advise disabling, never deleting"
    requirement: FIX-08
    verification:
      - kind: unit
        ref: "tests/test_translations.py (key and placeholder parity)"
        status: pass
    human_judgment: true
    rationale: "Translation parity is tested. Whether the German text reads naturally in the Repairs dialog needs a human reader"
  - id: D9
    description: "No regression: full suite, Ruff check and Ruff format green"
    verification:
      - kind: other
        ref: "uv run ruff check . && uv run ruff format --check . && uv run pytest -q (1764 passed, 2 xfailed)"
        status: pass
    human_judgment: false
duration: 17min
completed: 2026-10-16
---

# Phase 10 Plan 09: Repairs Warning for Duplicates Kept Enabled Summary

**One non-fixable Repairs warning, `kept_duplicates`, lists the core MQTT duplicates that the guard keeps enabled next to a native entity: the ones the user customized (WR-02) and the ones next to a native entity the user turned off (WR-03). It is in English and German. It is refreshed after the takeover pass, after every guard pass and after every replay catch run. A dismissal holds while the list stays the same. The warning goes away once no such duplicate is left, and it never touches a registry row (FIX-08, review 2 IN-03, D-01 to D-04).**

## Performance

- **Duration:** about 17 min
- **Started:** 2026-10-16T14:13:33Z
- **Completed:** 2026-10-16T14:30:12Z
- **Tasks:** 2 (Task 1 tracer, Task 2 auto)
- **Files modified:** 8 source, test and doc files, plus 17 RED evidence files

## Accomplishments

- `takeover.KeptReason` and `takeover.kept_duplicates(hass, entry_id, device_id, *, mqtt_entry_id)`. It only reads the registry and returns `(entity_id, reason)` for the enabled candidates the guard keeps. A twin the user turned off gives `TWIN_REJECTED` first, then a customized row gives `CUSTOMIZED`.
- `takeover._guard_candidates`: the (row, twin) pairs the guard decides on. `disable_duplicates` (behavior and docstring unchanged) and `kept_duplicates` both iterate it, so they cannot drift apart.
- `native_migration.kept_duplicates_placeholders(rows)`: `count`, `customized` and `rejected`. The ids are sorted, escaped with `escape_markdown`, capped at 10 per reason and followed by " …" when more are kept. A group without ids shows "—".
- `NativeMigration._refresh_kept_duplicates()` (`@callback`). It returns when the manager is not running. It collects `takeover.kept_duplicates` for every id of `_duplicate_guard_ids()`. An active issue with equal placeholders is left alone. Otherwise the issue is deleted and created again (`is_fixable=False`, severity warning) and one count-only INFO line is logged. An empty list deletes the issue. On an exception it logs one count-free WARNING and a DEBUG line with the type name, and leaves the issue as it is.
- Evaluation points (D-04): every return path of `async_takeover`; the end of `_disable_duplicates` once the guard ran, also when it disabled nothing; and both paths of `_async_replay_catch` after its running check (the early return without an MQTT entry or publisher, and the end). `native_migration.py` still has exactly one `async_listen` (the guard).
- `const.ISSUE_KEPT_DUPLICATES = "kept_duplicates"` (line 185, outside `ISSUE_DEVICE_PREFIXES`) and `KEPT_DUPLICATES_MAX_SHOWN = 10`.

## Final en and de texts

- **en title:** Duplicate MQTT entities stay enabled
- **en description:** "{count} MQTT entities stay enabled next to the native entity of their device.\n\n- Customized by you: {customized}\n- Kept because you disabled or hid the native entity: {rejected}\n\nMQTT Actions never deletes or disables these entities. If you do not need one, disable it under **Settings**, **Devices & services**, **Entities**, but do not delete it: deleting an MQTT entity can make Home Assistant clear a Discovery message that other instances still use. This warning is updated at the next start."
- **de title:** Doppelte MQTT-Entitäten bleiben aktiviert
- **de description:** "{count} MQTT-Entitäten bleiben neben der nativen Entität ihres Geräts aktiviert.\n\n- Von dir angepasst: {customized}\n- Behalten, weil du die native Entität deaktiviert oder ausgeblendet hast: {rejected}\n\nMQTT Actions löscht oder deaktiviert diese Entitäten nie. Wenn du eine davon nicht brauchst, deaktiviere sie unter **Einstellungen**, **Geräte & Dienste**, **Entitäten**, aber lösche sie nicht: Wird eine MQTT-Entität gelöscht, kann Home Assistant eine Discovery-Nachricht leeren, die andere Instanzen noch nutzen. Diese Warnung wird beim nächsten Start aktualisiert."

## Task Commits

1. **Task 1 (tracer): a customized duplicate kept enabled shows up in one warning.** RED `772de45` (test), GREEN `d9a0fbb` (feat)
2. **Task 2: the warning follows the list, and the guard and the warning split the candidates.** RED `0c7b2a3` (test), GREEN `2f56637` (feat)

**Plan metadata:** the docs commit that follows this SUMMARY

Tracer gate after Task 1: interactive run, `human_verify_mode` end-of-phase, and only `<automated>` verify steps. Both verify commands were re-run and passed, and the full suite was green (1746 passed, 2 xfailed), so the plan continued to Task 2 without a checkpoint.

## TDD Records

| Record | Target test | How it went red | Verdict |
|--------|-------------|-----------------|---------|
| `tdd/10-09-task1-red.{xml,json}` | `test_a_customized_duplicate_kept_enabled_is_listed_in_one_warning` | Real RED on the 10-08 code: `_kept_issue(hass) is None` at line 69 (no warning) | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red.xml` + `-dismissal.json` | `test_an_unchanged_list_keeps_a_dismissal_within_a_run` | Real RED on the Task 1 code. Task 1 deletes and creates on every refresh, so `dismissed_version` was None after the restart | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red.xml` + `-refresh.json` | `test_the_warning_is_refreshed_after_a_guard_pass_and_after_the_catch` | Real RED on the Task 1 code. The guard pass added no call (`assert 1 == 1 + 1`) | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red-rejected.{xml,json}` | `test_a_duplicate_kept_because_the_native_twin_was_turned_off_is_listed_as_rejected` | Pin. Mutant "twin-off rows reported as CUSTOMIZED": the TWIN_REJECTED append in `kept_duplicates` was changed to `KeptReason.CUSTOMIZED`. Result: `rejected` stayed "—" | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red-names.{xml,json}` | `test_kept_duplicates_names_customized_and_rejected_rows_and_nothing_else` | Pin. Same mutant. Result: CUSTOMIZED != TWIN_REJECTED at test_takeover.py:1555 | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red-goes-away.{xml,json}` | `test_the_warning_goes_away_once_no_kept_duplicate_remains_and_no_row_is_touched` | Pin. Mutant "an empty list returns before the delete". Result: the issue stayed | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red-changed.{xml,json}` | `test_a_changed_list_shows_the_warning_again_after_a_dismissal` | Pin, the mutant the plan names: "the refresh creates without deleting". Result: `dismissed_version` stayed `'2026.9.4'` with count 2 | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red-cap.{xml,json}` | `test_the_placeholders_cap_and_escape_the_entity_ids` | Pin, the mutant the plan names: "the cap check removed". Result: all 12 ids listed, no ellipsis | RED_EVIDENCE_OK |
| `tdd/10-09-task2-red-partition.{xml,json}` | `test_disable_duplicates_and_kept_duplicates_split_the_guard_candidates[untouched]` | Pin. Mutant "every kept candidate counted as customized" (`elif _is_customized(entry):` changed to `else:`). Result: the row was both disabled and reported | RED_EVIDENCE_OK |

How each RED was checked:
- Every target ran and failed on its planned assertion. The premise assertions passed, so no RED came from an import, collection, fixture or setup error.
- Each mutant was applied by an exact single-match replacement and reverted with `git checkout -- <file>`. `git diff --quiet -- custom_components/` passed after every revert.
- No mutant was committed.

## Files Created/Modified

- `custom_components/mqtt_actions/const.py`: `ISSUE_KEPT_DUPLICATES`, `KEPT_DUPLICATES_MAX_SHOWN`
- `custom_components/mqtt_actions/takeover.py`: `KeptReason`, `_guard_candidates`, `kept_duplicates`; `disable_duplicates` now uses the shared iterator
- `custom_components/mqtt_actions/native_migration.py`: `NONE_SHOWN`, `kept_duplicates_placeholders`, `_refresh_kept_duplicates`, the three call sites, and docstrings
- `custom_components/mqtt_actions/translations/en.json`, `de.json`: `issues.kept_duplicates`
- `docs/troubleshooting.md`: a `kept_duplicates` entry under "Repairs issues" (see Deviations)
- `tests/test_kept_duplicates.py` (new): seven FIX-08 tests
- `tests/test_takeover.py`: `_kept_duplicates_of`, `GUARD_CASES`, and the two unit tests

## Decisions Made

- These follow the plan's decisions D-01 to D-04, the reason precedence, the scope and the no-drift rule.
- Dismissal mechanism (Claude's discretion, as the plan describes it): the refresh compares `active` and `translation_placeholders`. Core keeps no placeholders for a non-persistent issue across a Home Assistant restart, so a restored inactive entry counts as changed. A dismissed warning therefore comes back once after a Home Assistant restart while duplicates remain. That is the safe side of Pitfall 15. Plan 10-10 documents it.
- The em dash for an empty group is the module constant `NONE_SHOWN`. The list separator is ", ", as in the cutover hint.
- The test-button rows and a device another instance adopted are not listed, like in the guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The troubleshooting page needs an entry for every issue key**
- **Found during:** Task 1 (full-suite run before the GREEN commit)
- **Issue:** `tests/test_docs.py::test_troubleshooting_covers_every_issue_key` failed. It requires a `` `key` `` entry in `docs/troubleshooting.md` for every issue in en.json. The new `kept_duplicates` issue had none. The page belongs to plan 10-10, but this plan's gate needs the full suite green.
- **Fix:** I added a short `### kept_duplicates` entry (Meaning, Why, What to do) under "Repairs issues". It sits after `native_cutover_waiting`. It does not touch the section "An enabled duplicate after the export prefix was set to the core prefix", which plan 10-10 edits, and it does not use the word "dismiss", so the 10-10 acceptance check "neither file contains the word before this plan" still holds.
- **Files modified:** docs/troubleshooting.md
- **Verification:** full suite green (1746 passed at Task 1, 1764 passed at the end)
- **Committed in:** d9a0fbb (Task 1 GREEN)
- **Note for 10-10:** `grep -q "kept_duplicates" docs/troubleshooting.md` already passes because of this entry. The 10-10 RED is the section-scoped doc test, so it is not affected.

### Interpretation (no code deviation)

- The Task 1 action already asks `kept_duplicates` to report `TWIN_REJECTED`, while the Task 2 RED reasons expect `rejected` to stay "—" until Task 2. I followed the Task 1 action. The rejected-twin tests were therefore green at once and are proven fail-first with a named mutant, as the pin rule of the plan allows. The same applies to the disappearance, changed-list, cap, names and partition tests. The dismissal and refresh tests went red for real.
- The partition test parametrizes over the `CUSTOMIZATIONS` values without their marks. This includes the entity-id rename, which is a strict xfail only for `_is_customized`. The partition holds for it: the guard disables the row and the warning does not list it.

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** one doc entry outside `files_modified`, needed for the plan's own full-suite gate. No product scope added.

## Issues Encountered

None.

## Threat Model

- T-10-12: `kept_duplicates` and `_guard_candidates` only read the registry, and the refresh touches only the issue registry. The goes-away test asserts that the kept row's registry entry is equal before and after the refreshes.
- T-10-13: the entity ids are local registry data. They are escaped and capped at 10 per reason, and the logs carry counts only.
- T-10-14: delete-then-create on a changed list or an inactive entry is tested with a dismissed warning and a changed list.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Ready for plan 10-10. It adds `ISSUE_KEPT_DUPLICATES` to the hub-removal cleanup in `manager.async_remove_local_state`, pins the placeholders in `tests/test_translations.py`, and adds the README and troubleshooting text.
- Branch `gsd/phase-10-review-findings-and-native-migration-extraction` is unchanged, and `main` was not touched.

## Self-Check: PASSED

- All created files exist: tests/test_kept_duplicates.py and the 17 tdd/10-09-* files.
- The commits 772de45, d9a0fbb, 0c7b2a3 and 2f56637 are ancestors of HEAD.
- `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest -q` are green (1764 passed, 2 xfailed).
- All nine RED records are RED_EVIDENCE_OK.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*
