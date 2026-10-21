---
phase: 11-local-actions-on-mirrors
plan: 22
subsystem: local-actions
tags: [options-flow, translations, hub-removal, local-actions, docs, tdd, gap-closure]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-20 LocalActionsStoreUnreadableError and the corrupt-copy rule; 11-21 LocalActionsStore.preserved_device_ids; suite baseline 2090"
provides:
  - "Manager.local_actions_readable (False before a load and after a refused one, True after a successful load)"
  - "Manager.local_action_removal_device_count() -> int | None: None while unreadable, else the union of record device ids and preserved_device_ids"
  - "async_local_action_device_count(...) -> int | None: loaded hubs ask the Manager; unloaded hubs return None on any read error, else the same union"
  - "HubOptionsFlow step settings_unreadable (same fields and options as settings, no placeholders) and async_step_settings_unreadable delegating to async_step_settings"
  - "en/de options.step.settings_unreadable; README Lifecycle sentence; release-notes sentence; disposition WR-04 fixed (open 7)"
affects: [phase-11-verification, phase-12-release]

plan_head_before: 350eafaa06e2e3e069fbf4a33626df663525b04e
plan_head_after: 6d2795bb10c01de66d59c5c9144bbc1edaac8851
actuals:
  tokens: 4211
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "An unknown count is None end to end and selects a dedicated form step with fixed text; it is never rendered as a number"
    - "A second options step id for the same form delegates to the first, so validation, errors and stored options stay in one place"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-22-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-22-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-22-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-22-task2-red.xml
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/config_flow.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_hub_removal.py
    - tests/test_translations.py
    - tests/test_docs.py
    - README.md
    - .planning/phases/11-local-actions-on-mirrors/11-release-notes.md
    - .planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md

key-decisions:
  - "The removal warning count is None (unknown) whenever the saved local actions cannot be read, for loaded and unloaded hubs; the options flow then shows step settings_unreadable with fixed en/de text instead of a number (WR-04, D-08 extended by the owner 2026-10-21)"
  - "Readable removal counts include devices named only by preserved rows (11-21), because removal deletes those rows too"
  - "The unloaded branch catches any exception of the read (BLE001), not only HomeAssistantError and ValueError: an unexpected read error is just as unknown, and must not crash the settings form"
  - "A loaded hub whose Store is damaged while it runs keeps the count of its start; the Manager does not re-read the file to show a form (flagged assumption)"

patterns-established:
  - "Manager readability flag: set True only in the success branch of _async_load_local_actions, False in its except branch"

requirements-completed: [MIR-08, MIR-15]

coverage:
  - id: D1
    description: "A loaded hub whose local load was refused shows settings_unreadable without placeholders; opening it never changes the Store"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_removal_settings_say_the_saved_local_actions_cannot_be_read"
        status: pass
    human_judgment: false
  - id: D2
    description: "The settings_unreadable step stores the same options as settings and shows the export prefix error on itself"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_settings_unreadable_step_stores_the_options_and_shows_field_errors"
        status: pass
    human_judgment: false
  - id: D3
    description: "Manager.local_actions_readable is False after a refused load and True after a successful one"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_manager_reports_whether_its_local_actions_were_readable"
        status: pass
    human_judgment: false
  - id: D4
    description: "An unloaded hub shows settings_unreadable for a newer version, a shape-invalid payload and a corrupt copy beside a missing file; neither the Store entry nor the copy changes"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_unloaded_hub_with_an_unreadable_local_store_says_cannot_be_read"
        status: pass
      - kind: integration
        ref: "tests/test_hub_removal.py#test_unloaded_hub_counts_unknown_for_every_unreadable_store_shape"
        status: pass
    human_judgment: false
  - id: D5
    description: "Readable counts include devices of preserved rows, loaded and unloaded; existing count tests unchanged and green"
    requirement: MIR-08
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_removal_count_includes_devices_of_preserved_rows"
        status: pass
      - kind: integration
        ref: "tests/test_hub_removal.py#test_removal_settings_name_the_distinct_device_count"
        status: pass
    human_judgment: false
  - id: D6
    description: "en/de settings_unreadable text says the saved local actions cannot be read and are deleted anyway; README and release-notes sentences"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_hub_removal.py#test_removal_settings_unreadable_text_says_cannot_be_read_and_deleted"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_every_local_actions_topic"
        status: pass
    human_judgment: true
    rationale: "Whether the warning reads clearly in German and English is a language judgment that phrase checks cannot make"
  - id: D7
    description: "Disposition WR-01..WR-04 fixed, IN-01..IN-07 open, open: 7"
    verification:
      - kind: other
        ref: "Task 3 verify 3: disposition frontmatter/table agreement and feat(11-22) ancestry"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 22: Removal warning says "cannot be read" instead of 0 devices Summary

**When the saved local actions cannot be read, the hub settings now show a dedicated `settings_unreadable` step. Its en/de text says the local actions cannot be read and that removal deletes them anyway, and it shows no number. The count is `None` for a refused Manager load and for any read error of an unloaded hub. Readable counts now include devices that only preserved rows name. WR-04 is fixed, so all four review warnings of Phase 11 are fixed.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-10-21T08:21:06Z
- **Completed:** 2026-10-21T08:31Z
- **Tasks:** 3
- **Files modified:** 14 (10 source/test/doc/planning files, 4 RED evidence files)

## Accomplishments

- `Manager._local_actions_readable` starts False. It becomes True in the success branch of `_async_load_local_actions` and False in its except branch, and the `local_actions_readable` property exposes it.
- `Manager.local_action_removal_device_count()` returns None while the Store is unreadable. Otherwise it returns the number of distinct device ids across `_local_records` and `_local_store.preserved_device_ids`.
- `async_local_action_device_count` now returns `int | None`. A loaded hub asks the Manager. An unloaded hub returns None on any read error, which is logged by type name as before. Otherwise it returns the same union. The docstring says that None means unknown and must never be shown as a number.
- `HubOptionsFlow.async_step_settings` builds the same form either way. When the count is None it uses `step_id="settings_unreadable"` without `description_placeholders`. `async_step_settings_unreadable` delegates to `async_step_settings`, so a submit stores the same options and an invalid prefix shows the same error on the same step.
- README `### Lifecycle`, `**Removing the integration**`: "If the saved local actions cannot be read, the removal settings say so instead of a number, and removing the integration deletes them as well."
- Release-notes draft (still labelled unpublished): "... the removal settings name how many devices are affected, or say that the saved local actions cannot be read."

## Final settings_unreadable Text

- **en** `title`: "MQTT Actions options" (same as `settings`). The `description` replaces the count sentence of `settings` with: "The saved local actions of this instance cannot be read, so their number is unknown. Removing this integration deletes them in either case." `data` and `data_description` are copies of `settings`.
- **de** `title`: "MQTT-Actions-Optionen". The `description` replaces the count sentence with: "Die gespeicherten lokalen Aktionen dieser Instanz können nicht gelesen werden, daher ist ihre Anzahl unbekannt. Beim Entfernen dieser Integration werden sie in jedem Fall gelöscht." `data` and `data_description` are copies of `settings`.
- Neither description contains a placeholder.

## Task Commits

1. **Task 1 (tracer): a loaded hub whose local load was refused shows settings_unreadable in en and de**
   - RED `669148c` test(11-22): add failing tests for removal settings of unreadable local actions
   - GREEN `142dd3c` feat(11-22): show settings_unreadable instead of a count when local actions cannot be read
   - Tracer gate: interactive, `end-of-phase`, verify is automated only. All three verify commands were re-run and passed (10 passed; 205 passed in the five modules; verify 3 rc 0). Then expansion continued.
2. **Task 2: unloaded hubs answer unknown, readable counts include preserved rows, README sentence**
   - RED `adba65c` test(11-22): add failing tests for unknown counts of an unloaded hub and preserved rows
   - GREEN `96e20d4` feat(11-22): unloaded hubs count unreadable local actions as unknown and count preserved rows
3. **Task 3: release notes, all tiers, disposition WR-04 fixed**
   - `6d2795b` docs(11-22): WR-04 fixed; release notes name the cannot-be-read removal warning

## RED Evidence and Semantic Assessments

- **Task 1** (`tdd/11-22-task1-red.json`, RED_EVIDENCE_OK). The target `test_removal_settings_say_the_saved_local_actions_cannot_be_read` was collected and ran: 1 test, 0 errors, 0 skipped. Hub setup ran, and the refused local load was logged (`UnsupportedStorageVersionError`). The first planned assertion failed: `'settings' == 'settings_unreadable'`. This is the WR-04 defect itself, a refused load counted as 0 devices, and a valid semantic RED. The four other new tests failed on their own planned assertions: the step id, `AttributeError` for `local_actions_readable`, and the missing `settings_unreadable` text.
- **Task 2** (`tdd/11-22-task2-red.json`, RED_EVIDENCE_OK). The target `test_unloaded_hub_with_an_unreadable_local_store_says_cannot_be_read` ran: 1 test. Setup, the refused load and the unload passed. The step-id assertion failed with `'settings'`, because the unloaded branch returned 0. This is a valid semantic RED. Both shape cases also failed on the step id after their premise passed (the `local_actions_unreadable` issue existed). Both preserved-row cases failed on `'1' != '2'` after their premise passed (one record device). The docs test failed on `'cannot be read' (integration removal)`.

## Flagged Assumption

- A loaded hub whose Store is damaged while it runs still shows the count from its start. The Manager does not re-read the file to show a form. The next start raises `local_actions_unreadable`, and from then on the settings show the dedicated text.

## Final Disposition Table

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | plan 11-18, 17865da |
| WR-02 | warning | fixed | plan 11-19, 5bc5ed4 |
| WR-03 | warning | fixed | plans 11-20 6c09f99, 11-21 936e0d9 |
| WR-04 | warning | fixed | plan 11-22, 142dd3c |
| IN-01..IN-07 | info | open | - (out of scope by owner decision) |

The frontmatter reads `open: 7`.

## Verification

- Task 1: verify 1 had 10 passed and verify 2 had 205 passed (hub removal, translations, local actions flow, config flow, local actions manager). Verify 3 passed: RED_EVIDENCE_OK, the property and the delegating step are present, no skip/xfail was added, the RED commit touches no `custom_components/`, and `local_actions_store.py`, `local_actions.py` and `__init__.py` are unchanged.
- Task 2: verify 1 had 14 passed and verify 2 had 158 passed. Verify 3 passed: RED_EVIDENCE_OK, `preserved_device_ids` is used in manager.py, the README sentence is present, no `.corrupt` file is left in PHACC's `testing_config`, and no skip/xfail was added.
- Task 3: the release-notes check passed. `ruff check .` and `ruff format --check .` are clean (111 files). The disposition verify passed.
- Full required-broker suite (`MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`, all tiers, nothing deselected or skipped), against the 11-21 baseline of 2090:

Full suite: 2100 passed, 2 xfailed

- Accounting: 2090 + 5 Task 1 tests (one parametrized en/de) + 5 Task 2 tests (two parametrized pairs) = 2100. The docs test gained a phrase, not a test.

## Must-Haves Prohibition

- "MUST NOT state a number of devices in the removal warning when the saved local actions could not be read" stays flagged `unverified` (judgment). Every unreadable state the plan names pins it, through `step_id == "settings_unreadable"` and empty `description_placeholders`: a loaded hub with a refused load, and an unloaded hub with a newer version, a shape-invalid payload, or a corrupt copy beside a missing file. The en/de text test also asserts that the dedicated description has no `{` placeholder.

## Files Created/Modified

- `custom_components/mqtt_actions/manager.py`: adds the readability flag and property, `local_action_removal_device_count()`, and the `int | None` count with the preserved-row union, plus updated docstrings.
- `custom_components/mqtt_actions/config_flow.py`: the `settings_unreadable` branch in `async_step_settings` and the delegating `async_step_settings_unreadable`.
- `custom_components/mqtt_actions/translations/en.json`, `de.json`: add `options.step.settings_unreadable`.
- `tests/test_hub_removal.py`: adds `_seed_newer_local_store` and eight new test functions (ten test cases).
- `tests/test_translations.py`: `OPTION_STEPS` gains `settings_unreadable` (see Deviations).
- `tests/test_docs.py`: the `integration removal` topic gains "cannot be read".
- `README.md`: the Lifecycle removal sentence.
- `.planning/phases/11-local-actions-on-mirrors/11-release-notes.md`: the removal sentence.
- `.planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md`: WR-04 fixed, `open: 7`.
- `.planning/phases/11-local-actions-on-mirrors/tdd/11-22-task{1,2}-red.{json,xml}`: RED evidence.

## Decisions Made

- The unloaded branch catches `Exception` (with `# noqa: BLE001`) rather than only `(HomeAssistantError, ValueError)`. The plan says "on any exception". An unexpected read error, such as an `OSError` from the corrupt-copy lookup, is just as unknown, and the settings form must still open. The Manager's own load already uses the same broad catch.
- The RED evidence files went into the RED `test(11-22)` commits with the tests, following the 11-20 and 11-21 convention. The verify only requires that `custom_components/` is untouched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The fixed option step set in test_translations.py did not know the new step id**
- **Found during:** Task 1 GREEN
- **Issue:** `test_option_keys_are_fixed_words_never_broker_text[en/de]` asserts that the `options.step` keys equal a fixed `OPTION_STEPS` set. The new `settings_unreadable` step failed it. That breaks Task 1 verify 2, which runs `tests/test_translations.py`.
- **Fix:** add `"settings_unreadable"` to `OPTION_STEPS`. The test still guards against broker text becoming a key, because the new id is a fixed word.
- **Files modified:** tests/test_translations.py
- **Verification:** Task 1 verify 2 had 205 passed.
- **Committed in:** 142dd3c (Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** It was needed for the planned step id, and the scope did not grow.

## TDD Gate Compliance

- Each RED `test(11-22)` commit comes before its GREEN `feat(11-22)` commit: 669148c before 142dd3c, and adba65c before 96e20d4. No REFACTOR commit was needed.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Phase 11 has no open code-review warning left. Only the out-of-scope info findings IN-01..IN-07 remain open.
- Next: re-verify Phase 11 (`/gsd-verify-work 11`), then Phase 12.

## Self-Check: PASSED

- All 10 modified files and all 4 RED evidence files exist.
- Commits 669148c, 142dd3c, adba65c, 96e20d4 and 6d2795b are ancestors of HEAD (5 commits since 350eafa).

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*
