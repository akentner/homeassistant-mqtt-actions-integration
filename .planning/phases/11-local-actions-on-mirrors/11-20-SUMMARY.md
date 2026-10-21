---
phase: 11-local-actions-on-mirrors
plan: 20
subsystem: local-actions
tags: [storage, repairs, issue-registry, local-actions, docs, translations, tdd, gap-closure]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-15 local_actions_unreadable issue (G-02), 11-16 new-hub cleanup (G-03), 11-19 suite baseline 2077"
provides:
  - "LocalActionsStoreUnreadableError: a shape-invalid payload and a missing file beside a .corrupt copy of the key refuse the load and every save"
  - "LocalActionsStore.async_remove_records deletes the .corrupt copies of its own key; an OSError fails closed with LocalActionsStoreError"
  - "Store, Manager and hub-removal regression tests for both unreadable cases and the copy removal"
  - "en/de issues.local_actions_unreadable.description and the troubleshooting section describe the corrupt copy and three recovery paths"
affects: [11-21, 11-22, phase-12-release]

plan_head_before: cd92e0239e889aaf613e915305f87164196e6e45
plan_head_after: c71f2c54e9f91120aeb2be399a6446b6a3834826
actuals:
  tokens: 5907
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Every way the local Store can be unreadable ends in the same state: the load raises, _loaded stays False, every save is refused, the Manager raises local_actions_unreadable"
    - "Filesystem lookups next to a Store file (iterdir, unlink) run in one executor job, never in the event loop"
    - "Tests that create files beside a Store point hass.config.config_dir at a temporary directory before any Store exists"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-20-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-20-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-20-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-20-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-20-task3-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-20-task3-red.xml
  modified:
    - custom_components/mqtt_actions/local_actions_store.py
    - tests/test_local_actions_store.py
    - tests/test_local_actions_manager.py
    - tests/test_hub_removal.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/troubleshooting.md

key-decisions:
  - "A local Store payload that is not a mapping with a record list is unreadable (LocalActionsStoreUnreadableError), not an empty Store; this reverses the 11-15 edge-probe assumption per the owner decision of 2026-10-21 (WR-03)"
  - "A None load next to a <file>.corrupt.<time> copy of the same key is unreadable at every start until the copy is restored or deleted; null data and a missing file without a copy stay an empty, writable Store"
  - "async_remove_records also deletes the corrupt copies of its own key, so hub removal and the new-hub cleanup leave a readable Store (D-08); copies of other keys are never touched"

patterns-established:
  - "Unreadable local Store: raise from async_load_records and leave _loaded False; never log or raise stored content"

requirements-completed: [MIR-05, MIR-06, MIR-15]

coverage:
  - id: D1
    description: "A shape-invalid local Store (list, text, empty mapping, records as text or mapping) refuses the load and every save, keeps its bytes, and the Manager raises local_actions_unreadable with no overlay, through an edit and an owner rename"
    requirement: MIR-05
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_shape_invalid_local_store_raises_the_unreadable_issue_and_is_never_overwritten"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_malformed_payload_shape_refuses_the_load_and_every_save"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_null_payload_loads_no_records_like_a_missing_file"
        status: pass
    human_judgment: false
  - id: D2
    description: "A missing local Store file beside a .corrupt copy of its key is unreadable at Store and Manager level until the copy is deleted; a copy of another key never counts"
    requirement: MIR-06
    verification:
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_corrupt_copy_beside_a_missing_file_refuses_the_load_and_every_save"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_corrupt_copy_of_another_key_never_counts"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_corrupt_copy_beside_a_missing_local_store_raises_the_unreadable_issue"
        status: pass
    human_judgment: false
  - id: D3
    description: "Removal deletes the corrupt copies of its own key only and fails closed; hub removal in both modes and the new-hub flow leave a readable Store"
    requirement: MIR-06
    verification:
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_remove_records_deletes_the_corrupt_copies_of_its_own_key_only"
        status: pass
      - kind: integration
        ref: "tests/test_hub_removal.py#test_hub_removal_and_a_new_hub_delete_the_corrupt_copies_of_the_local_store"
        status: pass
    human_judgment: false
  - id: D4
    description: "en/de issue text and troubleshooting explain the .corrupt copy, Home Assistant's own repair issue and the recovery paths"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_local_actions_manager.py#test_unreadable_issue_text_explains_the_corrupt_copy_and_how_to_recover"
        status: pass
      - kind: other
        ref: "Task 3 verify 2: troubleshooting phrase check (not applied, refused, not changed, newer version, backup, .corrupt, record list, delete)"
        status: pass
    human_judgment: true
    rationale: "Whether the German wording reads naturally and the recovery steps are understandable to a user is a language judgment that the phrase checks cannot make"

duration: 9min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 20: Unreadable local Store for every damaged shape Summary

**A local actions Store without a record list, or missing next to a Home Assistant `.corrupt` copy, now raises LocalActionsStoreUnreadableError, so `local_actions_unreadable` is raised and no save can overwrite it. Removal deletes the copies of its own key, and the en/de issue text explains the copy and how to recover.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-10-21T07:57:38Z
- **Completed:** 2026-10-21T08:07:06Z
- **Tasks:** 3
- **Files modified:** 13 (7 source/test/doc files, 6 RED evidence files)

## Accomplishments

- A payload that is not a mapping with a record list now fails the load with `LocalActionsStoreUnreadableError`. Before, it loaded as empty and the next edit, label refresh or adoption discard overwrote it. `_loaded` stays False, so every save is refused, and the Manager raises the existing `local_actions_unreadable` issue.
- After a JSON decode error, Core renames the file and returns None. A None load with a `<file>.corrupt.<time>` copy of the same key beside it now fails the same way, at every start, until the copy is restored or deleted. The lookup runs in one executor job.
- `async_remove_records` also deletes the corrupt copies of its own key. Hub removal in both modes and the new-hub cleanup (G-03) therefore leave a readable, empty Store. An unlink error raises `LocalActionsStoreError`, so G-03 shows `local_actions_not_removed`.
- The en/de issue text and `docs/troubleshooting.md` now describe what really happens to a damaged file. They give the recovery paths: update, restore from a backup, repair the file or its copy, or delete both to start without the saved local actions.

## Task Commits

1. **Task 1 (tracer): shape-invalid local Store is unreadable end to end**
   - RED `65b6b56` test(11-20): add failing tests for a shape-invalid local Store that must be unreadable
   - GREEN `6c09f99` feat(11-20): treat a local Store without a record list as unreadable
   - Tracer gate: interactive, `end-of-phase`, automated-only verify. Verify was re-run and passed (18 passed), then expansion continued.
2. **Task 2: corrupt copy beside a missing file; removal deletes the copies**
   - RED `31b6dcd` test(11-20): add failing tests for a corrupt copy beside a missing local Store
   - GREEN `de9948e` feat(11-20): a corrupt copy beside a missing local Store is unreadable; removal deletes its copies
3. **Task 3: en/de issue text and troubleshooting**
   - RED `5200273` test(11-20): add failing text test for the corrupt copy and recovery in the unreadable issue
   - GREEN `c71f2c5` docs(11-20): explain the corrupt copy and how to recover in the unreadable local actions issue

## RED Evidence and Semantic Assessments

- **Task 1** (`tdd/11-20-task1-red.json`, RED_EVIDENCE_OK): the target ran (1 test, 0 errors, 0 skipped). It failed on the planned first assertion, that `_unreadable_issue(hass)` is not None. The old Store logged a shape warning, loaded no records and set `_loaded = True`. This is a valid semantic RED, not an import, collection or fixture fault.
- **Task 2** (`tdd/11-20-task2-red.json`, RED_EVIDENCE_OK): the target ran (1 test). It failed with `DID NOT RAISE <class 'homeassistant.exceptions.HomeAssistantError'>` on the load, as the plan predicted, because the old Store never looked for a corrupt copy. Valid semantic RED. Before GREEN, `test_corrupt_copy_of_another_key_never_counts` already passed, as expected: it guards against over-matching, not a missing behavior.
- **Task 3** (`tdd/11-20-task3-red.json`, RED_EVIDENCE_OK): the target ran (1 test). It failed on the first phrase assertion, `en: the description names '.corrupt'`. Valid semantic RED.

## How Each Test Isolates the Configuration Directory

- `tests/test_local_actions_store.py`: overrides the PHACC fixture `hass_config_dir` with `hass_tmp_config_dir` for the whole module, the same pattern as `tests/test_services.py:57-60`. Every Store in the module resolves `.storage` inside a per-test temporary copy of `testing_config`.
- `tests/test_local_actions_manager.py` (`test_corrupt_copy_beside_a_missing_local_store_raises_the_unreadable_issue`) and `tests/test_hub_removal.py` (`test_hub_removal_and_a_new_hub_delete_the_corrupt_copies_of_the_local_store`): each runs `monkeypatch.setattr(hass.config, "config_dir", hass_tmp_config_dir)` first, before any entry or Store exists. `Store.path` is a `cached_property`, so it must be set first. The rest of these large modules is unchanged.
- After the full suite, `find <PHACC testing_config> -name "*.corrupt.*"` finds nothing.

## Corrupt-Copy Naming Assumption (flagged)

- Core `homeassistant/helpers/storage.py` (installed 2026.9.x, `_async_load_data`) renames a file that fails JSON decoding to `f"{self.path}.corrupt.{isotime}"`. It then creates its own `storage_corruption_<key>_<isotime>` issue and returns None.
- `_corrupt_copies()` matches entries in the directory of `self.path` whose name starts with `f"{Path(self.path).name}.corrupt."`.
- **Test limit:** the tests create the copy under that name themselves; they never drive Core's rename. If Core changes the naming scheme, no test fails, and the Store would treat a renamed-away file as missing again (the old behavior). Re-check this on HA bumps.

## Final Issue Text

**en** (`issues.local_actions_unreadable.description`):

> The saved local actions of this instance cannot be read. A newer version of MQTT Actions saved them, or the file is damaged.
>
> Until they can be read, local actions, replacements and mutes are not applied. Approved owner actions run on every trigger, also on triggers you replaced or muted here. Editing local actions is refused, and MQTT Actions does not change the file.
>
> If a newer version saved them, update MQTT Actions to that version. Home Assistant moves a file it cannot read at all aside in the `.storage` folder as `mqtt_actions.local_actions.corrupt.` followed by a time, and shows its own repair issue for it. To recover, restore the file from a backup, or repair the file or that copy and save it as `.storage/mqtt_actions.local_actions`. To start without the saved local actions, delete the file and any such copy. Then restart Home Assistant or reload the integration.

**de:**

> Die gespeicherten lokalen Aktionen dieser Instanz können nicht gelesen werden. Eine neuere Version von MQTT Actions hat sie gespeichert, oder die Datei ist beschädigt.
>
> Bis sie wieder lesbar sind, werden lokale Aktionen, Ersetzungen und Stummschaltungen nicht angewendet. Freigegebene Aktionen der Besitzerin laufen bei jedem Auslöser, auch bei Auslösern, die du hier ersetzt oder stummgeschaltet hast. Lokale Aktionen können nicht bearbeitet werden, und MQTT Actions ändert die Datei nicht.
>
> Hat eine neuere Version sie gespeichert, aktualisiere MQTT Actions auf diese Version. Eine Datei, die Home Assistant gar nicht lesen kann, verschiebt es im Ordner `.storage` unter dem Namen `mqtt_actions.local_actions.corrupt.` mit einer angehängten Zeit und zeigt dafür in den Reparaturen ein eigenes Problem an. Zum Wiederherstellen stelle die Datei aus einem Backup wieder her, oder repariere die Datei oder diese Kopie und speichere sie als `.storage/mqtt_actions.local_actions`. Willst du ohne die gespeicherten lokalen Aktionen starten, lösche die Datei und jede solche Kopie. Starte danach Home Assistant neu oder lade die Integration neu.

Neither text has a placeholder, and neither puts single quotes around words.

## Verification

- Task 1: the targeted run had 18 passed. The Store, Manager, lifecycle and hub-removal modules had 133 passed. Verify 3 (RED record, class present, old warning and old test gone, no skip/xfail, RED commit touches no `custom_components/`, `manager.py` and `local_actions.py` unchanged) passed.
- Task 2: the five named tests had 5 passed. The six listed modules had 149 passed. Verify 3 (executor-job lookup, no `.corrupt` file in PHACC `testing_config`, no skip/xfail, `manager.py` and `config_flow.py` unchanged) passed.
- Task 3: the Manager, translations and docs modules had 160 passed. The troubleshooting phrase check passed, and `ruff check .` and `ruff format --check .` are clean (111 files).
- Full required-broker suite (`MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`, all tiers, nothing deselected), against the 11-19 baseline of 2077:

Full suite: 2084 passed, 2 xfailed

- Accounting: 6 parametrized cases of the old shape test were removed. 13 tests were added: 5 parametrized shape cases, the null test, 3 corrupt-copy Store tests, the Manager tracer, the Manager corrupt-copy test, the hub-removal test and the text test. 2077 - 6 + 13 = 2084.

## Must-Haves Prohibition

- "MUST NOT overwrite, reduce or replace a local actions Store this release cannot read, or treat it as an empty Store that a later edit may write" stays flagged `unverified` (judgment). Three things now pin it: the bytes-unchanged assertions after an edit and an owner rename (Task 1), the no-entry-written assertion beside a corrupt copy (Task 2), and every save raising for each shape-invalid payload. Rows that fail parse inside a shape-valid payload can still be lost on the next save. That half is Plan 11-21.

## Files Created/Modified

- `custom_components/mqtt_actions/local_actions_store.py`: adds `LocalActionsStoreUnreadableError`, the shape-invalid raise, the corrupt-copy raise, and the sync helpers `_corrupt_copies` and `_remove_corrupt_copies` (both run in an executor job). `async_remove_records` now deletes the copies. Class and method docstrings are updated.
- `tests/test_local_actions_store.py`: adds the module `hass_config_dir` override and the `_corrupt_copy` helper. The parametrized shape test replaces `test_malformed_payload_shape_loads_no_records`. Adds the null test and three corrupt-copy tests.
- `tests/test_local_actions_manager.py`: adds the Task 1 tracer, the Task 2 corrupt-copy issue test and the Task 3 text test.
- `tests/test_hub_removal.py`: adds `test_hub_removal_and_a_new_hub_delete_the_corrupt_copies_of_the_local_store`.
- `custom_components/mqtt_actions/translations/en.json` and `de.json`: `issues.local_actions_unreadable.description`.
- `docs/troubleshooting.md`: the `local_actions_unreadable` section (why, what to do, removal deletes the copies).
- `.planning/phases/11-local-actions-on-mirrors/tdd/11-20-task{1,2,3}-red.{json,xml}`: RED evidence.

## Decisions Made

- The corrupt-copy rule applies only when the load returns None. A shape-valid file next to an old copy is readable, so a copy left behind after a successful restore never blocks the Store.
- An envelope with null data counts as a missing file, because Core returns None for both. So a null envelope next to a copy of the key is unreadable too. No test covers that edge, and the plan did not ask for one.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The Store shape test's log assertion caught PHACC's own DEBUG log**
- **Found during:** Task 1 (GREEN run)
- **Issue:** The RED version asserted `MARKER not in caplog.text`. PHACC's `mock_storage` logs every loaded payload at DEBUG (`Loading data for ...`), so the `records-mapping` case failed even though the integration logs nothing.
- **Fix:** The assertion now checks only log records of `custom_components.mqtt_actions`. That is the planned intent: no log line of the integration carries stored content.
- **Files modified:** tests/test_local_actions_store.py
- **Verification:** All 5 shape cases pass. The error message is also checked for the marker.
- **Committed in:** 6c09f99 (Task 1 GREEN)

**2. [Rule 1 - Bug] The Manager corrupt-copy test expected the wrong label after the recovery edit**
- **Found during:** Task 2 (GREEN run)
- **Issue:** The RED version compared the saved row to `_replacement_on(...)`, whose label is "On". An edit takes the label from the current trigger, which is "ON".
- **Fix:** It now compares state value, mode and actions, which is the behavior under test ("an edit saves again").
- **Files modified:** tests/test_local_actions_manager.py
- **Verification:** All 5 named Task 2 tests pass.
- **Committed in:** de9948e (Task 2 GREEN)

---

**Total deviations:** 2 auto-fixed (2 Rule 1, both test assertions written in RED). **Impact:** no production behavior change and no scope change. Both RED targets failed on their planned assertion before these lines were reached.

## TDD Gate Compliance

- RED `test(11-20)` commits come before each GREEN: 65b6b56 before 6c09f99, 31b6dcd before de9948e, 5200273 before c71f2c5.
- Task 3's GREEN commit is `docs(11-20)`, as the plan specified, because it changes only text. There are two `feat(11-20)` commits (Tasks 1 and 2). No REFACTOR commit was needed.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- WR-03 stays **open** in `11-REVIEW-DISPOSITION.md`. This plan closes its first half (shape-invalid, corrupt copy, text). Plan 11-21 completes it: rows that fail parse must survive the next save. 11-21 also sets the disposition row.
- Plan 11-21 reads its full-suite baseline from the single result line in the Verification section above (2084).

## Self-Check: PASSED

- All 7 modified files and all 6 RED evidence files exist.
- Commits 65b6b56, 6c09f99, 31b6dcd, de9948e, 5200273 and c71f2c5 are ancestors of HEAD (6 commits since cd92e02).
- The installed PHACC `testing_config` holds no `.corrupt` file.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*
