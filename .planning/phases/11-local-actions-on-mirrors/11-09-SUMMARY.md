---
phase: 11-local-actions-on-mirrors
plan: 09
subsystem: lifecycle
tags: [local-actions, hub-removal, diagnostics, translations, privacy, tdd]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-04: LocalActionsStore with async_remove_records"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-05: Manager local_action_counts and LocalActionCounts"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-07: ISSUE_LOCAL_ACTION_FAILED_PREFIX in ISSUE_DEVICE_PREFIXES"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-08: hub options menu with the retained settings step and tests.helpers.open_hub_settings"
provides:
  - async_remove_local_state / async_remove_all_devices with a local_store_key seam that delete the local actions Store
  - LocalActionsStore.async_close, called by Manager.async_stop, so a late save cannot recreate a removed file
  - async_local_action_device_count (distinct device ids with records, orphan-only included; loaded or unloaded hub)
  - Settings step placeholder local_action_device_count with en/de description text
  - Manager.local_action_counts_by_device (counts only)
  - Diagnostics keys local_actions.{devices,triggers,orphaned_triggers,orphan_only_devices} and per-device local_action_triggers, local_action_orphans
  - tests.helpers.LOCAL_ACTIONS_KEYS and the extended TOP_KEYS / DEVICE_KEYS
affects: [11-10, 11-12, 11-13]

# Actuals (#2632)
actuals:
  tokens: 10563
  tasks: 2
  commits: 5
plan_head_before: ce464e6c44d02db0c29dd15654d81372efd39d75
plan_head_after: f4b5a31b9690b010f6b75b2bda4fc08ccbc20eec

tech-stack:
  added: []
  patterns:
    - "Stopping the Manager closes its local Store under the Store lock; only the next load reopens it"
    - "A count for the UI comes from the Manager when loaded and from a read of the Store file when not"
    - "Diagnostics take integer counts from the Manager; no record object reaches the builder"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-09-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-09-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-09-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-09-task2-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/__init__.py
    - custom_components/mqtt_actions/config_flow.py
    - custom_components/mqtt_actions/local_actions_store.py
    - custom_components/mqtt_actions/diagnostics.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/diagnostics.md
    - tests/test_hub_removal.py
    - tests/test_diagnostics.py
    - tests/test_docs.py
    - tests/helpers.py

key-decisions:
  - "The local Store is deleted in async_remove_local_state, which both removal modes and the unloaded path share; a failed local delete is logged by exception type and does not stop the issue cleanup"
  - "Late callbacks are cut off at Manager.async_stop: LocalActionsStore.async_close refuses every later save until the next load, so a stopped Manager can never recreate a removed file"
  - "The removal warning counts distinct device ids in the saved records (orphan-only included). A loaded hub asks the Manager; an unloaded hub reads the Store file; an unreadable file counts as 0, the same as a starting Manager"
  - "The warning is part of the settings step description and is shown in either removal mode, because D-08 deletes local actions in keep mode too"
  - "Diagnostics: triggers = saved records, orphaned_triggers = records that match no current trigger (removed option, other kind, no mirror). An owned device or a device without a mirror counts all its records as orphaned"
  - "A device that is known only from local records gets no device row and is never named; it appears only in the aggregate counts"

patterns-established:
  - "Removal seams name every Store key they delete (store_key, local_store_key); production passes none"

requirements-completed: [MIR-04, MIR-08, MIR-14, MIR-15]

coverage:
  - id: D1
    description: "Keep, delete and unloaded hub removal delete the main Store, the local actions Store and every issue, local failure issues included"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_every_removal_path_deletes_the_local_store_and_local_issues (keep, delete, unloaded)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A save arriving through the stopped Manager's local Store after the removal is refused and does not recreate the file"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_a_late_save_cannot_recreate_the_local_store"
        status: pass
    human_judgment: false
  - id: D3
    description: "The settings step shows the number of distinct devices with records (3 for 5 records, orphan-only devices counted, a mirror without records not counted), loaded and unloaded, and 0 without records; en and de render it"
    requirement: MIR-15
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py -k 'device_count or count_zero or renders_the_device_count'"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_hub_removal.py tests/test_translations.py (94 passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Diagnostics carry the exact local_actions keys and per-device counts as nonnegative integers; orphan-only devices count without a row; zero counts without records"
    requirement: MIR-04
    verification:
      - kind: integration
        ref: "tests/test_diagnostics.py -k 'local_actions_appear or local_counts_are_zero or orphan_only_devices or exactly_the_documented_keys'"
        status: pass
    human_judgment: false
  - id: D5
    description: "No record, label, StateValue, action, entity, Template, service data, error or trace sentinel and no orphan-only device id appears in the serialized diagnostics; the shared content hash is unchanged"
    requirement: MIR-14
    verification:
      - kind: integration
        ref: "tests/test_diagnostics.py#test_local_sentinels_never_appear_and_the_shared_hash_is_unchanged"
        status: pass
    human_judgment: false
  - id: D6
    description: "docs/diagnostics.md lists the same keys as the exact-key tests and the excluded local content"
    requirement: MIR-14
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_diagnostics_page_lists_the_included_keys_and_the_exclusions"
        status: pass
    human_judgment: false
  - id: D7
    description: "Readability of the new removal warning sentence in the real options dialog, in en and de"
    requirement: MIR-15
    verification: []
    human_judgment: true
    rationale: "Backend tests prove the placeholder and the rendered text; how the longer settings description reads in the frontend needs a look on the bench (Plan 11-13 UAT)"

duration: 8min
completed: 2026-10-21
---

# Phase 11 Plan 09: Hub Cleanup and Count-Only Diagnostics Summary

**Every hub removal path (keep, delete, unloaded) now deletes the separate local actions Store next to the main Store and every issue. A stopped Manager closes its local Store, so a late save cannot bring the file back. The settings step warns how many distinct devices lose their local actions (`local_action_device_count`, en and de). Diagnostics add only integers: four aggregate counts and two per-device counts, with no record content of any kind.**

## Performance

- **Duration:** about 8 min of execution (2026-10-21T02:32:45Z to 02:40Z)
- **Tasks:** 2 (1 tracer TDD, 1 TDD). There are 5 commits: 2 RED, 2 GREEN and 1 REFACTOR.
- **Files:** 7 production files and 1 doc changed, 4 test modules changed, 4 evidence files created.

## Cleanup paths

| Path | Entry point | What goes |
|------|-------------|-----------|
| Keep (default) | `async_remove_entry` -> `async_remove_local_state` | Main Store, local actions Store, every `mqtt_actions` issue (per-device prefixes incl. `local_action_failed_`, instance issues by id) |
| Delete everywhere | `async_remove_entry` -> `async_remove_all_devices` -> `async_remove_local_state` | Retained topics and availability first, then the same local state |
| Unloaded hub | Same as keep or delete; HA always unloads before `async_remove_entry` | Same; the Manager is already stopped and its local Store closed |

- Both functions take `store_key` and `local_store_key` seams. Production passes neither.
- `Manager.async_stop` calls `LocalActionsStore.async_close()` before its final main Store save. A save still running finishes first, because both take the Store lock. Every later save raises `LocalActionsStoreError` until the next `async_load_records`.
- A failed local delete is logged with the exception type only, and the issue cleanup still runs.

## Removal warning placeholder (for Plan 11-12)

- Step `options.step.settings.description`, placeholder `{local_action_device_count}`, supplied by `HubOptionsFlow.async_step_settings` through `async_local_action_device_count`.
- en: "Removing this integration also deletes the local actions of {local_action_device_count} devices on this instance, in either case."
- de: "Beim Entfernen dieser Integration werden in jedem Fall auch lokale Aktionen für {local_action_device_count} Geräte auf dieser Instanz gelöscht."
- The number counts distinct device ids, including orphan-only ids. Triggers and action steps are not counted. A mirror without records adds nothing. The settings step never writes the Store.

## Diagnostic keys

| Key | Meaning |
|-----|---------|
| `local_actions.devices` | Distinct device ids with saved records, orphan-only devices included |
| `local_actions.triggers` | Saved records (customized triggers) in total |
| `local_actions.orphaned_triggers` | Records that match no current trigger: removed option, other kind, or no mirror |
| `local_actions.orphan_only_devices` | Devices with records of which none is active |
| `devices[].local_action_triggers` | Records of that device |
| `devices[].local_action_orphans` | Inactive records of that device |

- The values come from `Manager.local_action_counts()` and `Manager.local_action_counts_by_device()`. These return `LocalActionCounts` integers only. The builder casts each value to `int`.
- The `hash` of a device row is still the shared content hash.

## TDD Evidence

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 (tracer) | `d82d912` | `tests/test_hub_removal.py::test_every_removal_path_deletes_the_local_store_and_local_issues[keep]` | RED_EVIDENCE_OK | `9d0d384` | `25160c0` (docstring only) |
| 2 | `7a5e347` | `tests/test_diagnostics.py::test_local_actions_appear_as_counts_only` | RED_EVIDENCE_OK | `f4b5a31` | none needed |

- **RED 1:** valid. The seeded local Store loaded and the issues were created. The test then failed on the first assertion after removal, because `mqtt_actions.local_actions` was still in storage. The other new tests failed for their planned reasons: no placeholder, no translation text, and the missing `local_store_key` keyword.
- **RED 2:** valid. The mirror premise passed, and the test failed on the missing `local_actions` summary. The sentinel and hash test passed already as a characterization: nothing leaks today, and it pins that this stays so.
- **Tracer gate:** after Task 1 the `<verify>` ran again (94 passed) before the expansion.

## Verification

- Task 1: `uv run pytest -q tests/test_hub_removal.py tests/test_translations.py` gave 94 passed.
- Task 2: `uv run pytest -q tests/test_diagnostics.py` gave 12 passed. With `tests/test_docs.py` it gave 40 passed.
- Full tiers, with no `--deselect`:
  - Unit (`-m "not broker and not multi_instance"`): 1853 passed, 2 xfailed. These are the same pre-existing xfails in `tests/test_takeover.py`.
  - Multi-instance: 173 passed.
  - Broker: 18 passed.
- `uv run ruff check` and `ruff format --check` are clean on `custom_components` and `tests`.

## Task Commits

1. **Task 1 (tracer): local Store and issue cleanup in every removal path, plus the device-count warning.** `d82d912` (test), `9d0d384` (feat), `25160c0` (refactor).
2. **Task 2: count-only local actions diagnostics.** `7a5e347` (test), `f4b5a31` (feat).

## Decisions Made

See `key-decisions` in the frontmatter. Two choices go beyond the plan text:

- **Unloaded count source.** The options flow can open on an unloaded hub. The count then comes from a read of the Store file. An unreadable or newer file counts as 0, which matches what a starting Manager would see. This read never writes for the only existing version, v1.1.
- **Warning in both modes.** The sentence is part of the settings description, not of the delete-toggle text, because keep mode deletes local actions too (D-08).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The late-save guard needs a Store method**
- **Found during:** Task 1 GREEN.
- **Issue:** The Manager cannot stop its local Store from writing without reaching into private state. `local_actions_store.py` is not in `files_modified`.
- **Fix:** Added `LocalActionsStore.async_close()`, which sets the Store unloaded under its lock. `Manager.async_stop` calls it.
- **Files modified:** `custom_components/mqtt_actions/local_actions_store.py`
- **Commit:** `9d0d384`

**2. [Rule 3 - Blocking] Diagnostics key sets live in shared test helpers**
- **Found during:** Task 2 RED.
- **Issue:** The exact-key sets `TOP_KEYS` and `DEVICE_KEYS` are in `tests/helpers.py`, and `tests/test_docs.py` checks the docs page against them. Neither file is in `files_modified`.
- **Fix:** Extended both sets, added `LOCAL_ACTIONS_KEYS`, and made the docs test require the new keys plus one exclusion sentence for local content.
- **Files modified:** `tests/helpers.py`, `tests/test_docs.py`
- **Commit:** `7a5e347`

**Total deviations:** 2 auto-fixed (both Rule 3). **Impact:** No scope creep. Both changes are what the planned behavior needed.

## Known Stubs

None.

## Threat Flags

None beyond the plan register:
- T-11-27 is covered by the integer allow-list and the multi-sentinel test. The sentinels cover record, label, StateValue, entity, Template, service data, error and trace, plus the orphan-only id.
- T-11-28 is covered by the common cleanup, `async_close` at stop, and the assertions that every Store key and issue is gone.

## Hand-offs

- **Plan 11-12:** The README and the troubleshooting page can name the warning and the four `local_actions` counts. `docs/diagnostics.md` is already complete for this plan.
- **Plan 11-13 / UAT:** Check how the longer settings description reads in en and de (coverage D7).

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Cleanup and diagnostics are complete. 11-10 and 11-12 can run in wave 9.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

All 5 task commits are ancestors of HEAD. The modified production, test and evidence files exist. Both RED records classify as RED_EVIDENCE_OK.
