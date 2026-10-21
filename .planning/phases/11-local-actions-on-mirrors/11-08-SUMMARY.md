---
phase: 11-local-actions-on-mirrors
plan: 08
subsystem: ui
tags: [local-actions, options-flow, translations, repairs, approval, tdd]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-02: frontend smoke PASS (expanded section, base-error channel, no ActionSelector data_description, raw selector data)"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-05: Manager local_action_devices/triggers, async_set_local_action, async_remove_local_action, LocalActionError reasons"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-07: local_action_failed issue and the approval placeholder replaced"
provides:
  - HubOptionsFlow menu (init) with the retained settings step and the local actions editor
  - Flow step ids local_actions, local_actions_device, local_actions_trigger, local_actions_edit, local_actions_confirm_mute, local_actions_mute_confirmed, local_actions_confirm_remove, local_actions_remove_confirmed
  - en/de texts for options.step.*, options.error.*, options.abort.*, selector.local_mode, selector.local_trigger_status, issues.local_action_failed and the approval confirm wording with {replaced}
  - tests/helpers.open_hub_settings for every test that opens the hub settings
affects: [11-09, 11-12, 11-13]

# Actuals (#2632)
actuals:
  tokens: 27360
  tasks: 3
  commits: 5
plan_head_before: 076e29a1d55b8012d45f9ddc63c9826deed6b5e2
plan_head_after: 295795a11172490c15d91bc5115511fb0982f8fd

tech-stack:
  added: []
  patterns:
    - "Options flow as a thin Manager client: identity values in selectors, a flow-private draft, every durable change through one Manager call, the Manager read again at each step"
    - "Dynamic select labels with translated markers looked up through async_get_translations in the instance language"
    - "Flow tests assert that every shown step text exists in en and de and uses only supplied placeholders"

key-files:
  created:
    - tests/test_local_actions_flow.py
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-08-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-08-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-08-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-08-task2-red.xml
  modified:
    - custom_components/mqtt_actions/config_flow.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/troubleshooting.md
    - tests/helpers.py
    - tests/test_translations.py
    - tests/test_hub_removal.py
    - tests/test_discovery_export.py
    - tests/test_native_cleanup.py
    - .planning/WINDOWS.md

key-decisions:
  - "The hub options open as a menu (init: settings, local_actions); the former init form is the settings step, so Plan 11-09 adds its removal count there"
  - "Picker option values are the stable identity json [kind, normalized StateValue]; labels are display only and a submit is matched against freshly read rows"
  - "Trigger markers are translated in the instance language (hass.config.language) through async_get_translations, because select option labels are plain text the frontend does not translate"
  - "A trigger label shows friendly name and StateValue unless both are identical (Switch ON/OFF); the old case-insensitive collapse hid a Select StateValue and was dropped"
  - "Instead of with no actions always goes through local_actions_confirm_mute; the confirmation offers mute, back to the editor (draft kept) and discard (draft dropped)"
  - "A saved trigger opens a menu: edit, Remove local customization (own confirmation), back; an unsaved trigger opens the editor directly"
  - "The approval closing line changed from Nothing runs until you submit to The owner actions do not run until you submit, because local actions may already run (D-17)"

patterns-established:
  - "Every hub options test reaches the settings form through tests.helpers.open_hub_settings"

requirements-completed: [MIR-01, MIR-05, MIR-07, MIR-12, MIR-15]

coverage:
  - id: D1
    description: "Menu -> device -> trigger -> editor: a new trigger defaults additive, saves through the Manager at once, returns to the picker, runs without restart and reopens with the saved values; no options or subentry data"
    requirement: MIR-01
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_actions_flow.py -k 'save and reopen' (2 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Stale target and unloaded hub submits return base errors and save nothing; invalid actions show a capped base error and keep the draft"
    requirement: MIR-01
    verification:
      - kind: integration
        ref: "tests/test_local_actions_flow.py#test_stale_target_submit_returns_a_base_error_and_saves_nothing, #test_stale_manager_submit_returns_a_base_error_and_saves_nothing, #test_invalid_local_actions_show_a_base_error_and_save_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "Direct markers (additional, instead of, muted, orphan, kind mismatch, not mirrored) with friendly name and StateValue; orphan-only devices listed; orphan edits stay inactive"
    requirement: MIR-07
    verification:
      - kind: integration
        ref: "tests/test_local_actions_flow.py#test_picker_labels_show_the_mode_and_inactive_markers_directly, #test_editing_an_orphan_saves_it_but_never_activates_it, #test_trigger_labels_follow_the_language_of_the_instance"
        status: pass
    human_judgment: false
  - id: D4
    description: "Distinct mute and removal confirmations; nothing saved before confirmation; removal deletes instead of muting; cancel and discard keep earlier saved triggers"
    requirement: MIR-05
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_local_actions_flow.py (12 passed)"
        status: pass
    human_judgment: false
  - id: D5
    description: "en/de parity, exact placeholders and fixed keys for every new options, selector and issue text; approval wording owner-only with replaced count; troubleshooting covers local_action_failed"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_translations.py tests/test_local_actions_flow.py tests/test_docs.py tests/test_repairs_flow.py (137 passed)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Rendering of the real menu, pickers and confirmations in the browser (en/de), and the readability of the marker and approval wording"
    requirement: MIR-12
    verification: []
    human_judgment: true
    rationale: "The 11-02 smoke covered only the section and ActionSelector; the menus, dynamic labels and new texts were verified by backend tests only and need a UI look on the bench"

duration: 17min
completed: 2026-10-21
---

# Phase 11 Plan 08: Hub Options Local Actions Editor Summary

**The hub options are now a menu with the retained settings and a Local actions editor: mirrored device, then trigger (labels with friendly name, StateValue and translated additional, instead-of, muted, orphan, kind-mismatch or not-mirrored markers), then mode and actions in one expanded section. Saves and removals go straight to the Manager. An empty replacement and a removal each need their own confirmation, and a draft that is never confirmed never reaches the Manager. The local failure issue and the owner-only approval wording with the replaced count are translated in English and German.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-10-21T02:09:02Z
- **Completed:** 2026-10-21T02:26Z
- **Tasks:** 3 (1 tracer TDD, 1 TDD, 1 auto). Commits: 2 RED, 3 feature. No refactor commit was needed.
- **Files:** 4 production files (flow, 2 translations, troubleshooting) and 6 test files changed, 1 test module and 4 evidence files created.

## Flow step ids

| Step id | Kind | What it does |
|---------|------|--------------|
| `init` | menu | `settings`, `local_actions` |
| `settings` | form | The former `init` form (delete choice, export, prefix); the only step that writes `entry.options` |
| `local_actions` | form | Device picker: current mirrors by name, then devices known only from records (`<id> — not mirrored` marker). Aborts `not_loaded` or `no_local_devices` |
| `local_actions_device` | form | Trigger picker; value = `json.dumps([kind, normalized StateValue])`. Returning here drops any draft |
| `local_actions_trigger` | menu | Saved trigger: `local_actions_edit`, `local_actions_confirm_remove`, `local_actions_device` |
| `local_actions_edit` | form | Section `local_actions` (`collapsed: False`) with `mode` (`local_mode` selector, default additive) and `actions` (ActionSelector) |
| `local_actions_confirm_mute` | menu | `local_actions_mute_confirmed`, `local_actions_edit` (draft kept), `local_actions_device` (draft dropped) |
| `local_actions_mute_confirmed` | action | Saves replacement with `[]` through the Manager |
| `local_actions_confirm_remove` | menu | `local_actions_remove_confirmed`, `local_actions_device` (keep) |
| `local_actions_remove_confirmed` | action | `Manager.async_remove_local_action`, then back to the picker |

- `LocalActionError.reason` maps to `options.error`: `not_running` to `not_loaded`, `stale_target`, `invalid_mode`, `invalid_actions` to `invalid_local_actions` (`{error}` = capped cause message), and `save_failed`. An unloaded hub at submit is `not_loaded`.
- Placeholders `device`, `trigger` and `state_value` are passed through `escape_markdown`. Select labels are plain text and are not escaped.

## Translation namespaces

- `options.step.{init,settings,local_actions,local_actions_device,local_actions_trigger,local_actions_edit,local_actions_confirm_mute,local_actions_confirm_remove}`
- `options.error.{invalid_export_prefix,not_loaded,stale_target,invalid_mode,invalid_local_actions,save_failed}` and `options.abort.{not_loaded,no_local_devices}`
- `selector.local_mode.options.{additive,replacement}` and `selector.local_trigger_status.options.{additive,replacement,muted,orphan,kind_mismatch,no_mirror}`
- `issues.local_action_failed.{title,description}` with `device`, `trigger`, `time` and `error`
- `issues.approval_required.fix_flow.step.confirm.description` now uses `{replaced}`. It says local actions may already run, that the approval concerns only the owner actions, and that a local replacement never approves them.

## TDD Evidence

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 (tracer) | `80d5d9b` | `tests/test_local_actions_flow.py::test_save_and_reopen_additive_switch_trigger` | RED_EVIDENCE_OK | `d71de7e` | none needed |
| 2 | `c5f8c92` | `tests/test_local_actions_flow.py::test_picker_labels_show_the_mode_and_inactive_markers_directly` | RED_EVIDENCE_OK | `08ccc8e` | none needed |
| 3 (auto) | tests written first in the same commit | `tests/test_translations.py`, `tests/test_local_actions_flow.py` | n/a (not tdd) | `295795a` | - |

Semantic assessments (the full text is in `tdd/11-08-task{1,2}-red.json`):

- **RED 1:** valid. The follower and mirror premise passed. The test failed on its first planned assertion: the hub options opened a form, not a menu.
  - The other four flow tests failed at the same assertion.
  - The settings test failed with InvalidData, because `next_step_id` was submitted to the old form. It was not a target and is disclosed here.
- **RED 2:** valid. The test failed on the device picker labels. The orphan-only device showed its bare id, and the marker had no translation yet.
  - The test helper renders a missing marker text as `<missing key>` instead of raising KeyError, so the failure is an assertion.
  - Non-target results of that run:
    - The mute test failed on the menu assertion.
    - The removal test failed on the menu options.
    - The cancellation test failed with InvalidData, because the confirmation menu did not exist yet.
    - The orphan edit test failed on the marker suffix.
    - The invalid-actions test passed. It characterizes the Task 1 base-error path.
- **Tracer gate:** after Task 1 the `<verify>` ran again and passed (2 passed) before the expansion.

## Verification

- Task 1: `uv run pytest -q tests/test_local_actions_flow.py -k "save and reopen"` → 2 passed.
- Task 2: `uv run pytest -q tests/test_local_actions_flow.py` → 12 passed.
- Task 3: `uv run pytest -q tests/test_translations.py tests/test_local_actions_flow.py` with docs and repairs → 137 passed.
- Full tiers, with no `--deselect`:
  - Unit (`-m "not broker and not multi_instance"`): 1839 passed, 2 xfailed. The xfails are the older ones in `tests/test_takeover.py`.
  - Multi-instance: 173 passed.
  - Broker: 18 passed.
- `uv run ruff check` and `ruff format --check` are clean on `custom_components` and `tests`.

## Task Commits

1. **Task 1 (tracer): menu, pickers, editor, save and reopen.** `80d5d9b` (test), `d71de7e` (feat).
2. **Task 2: markers, mute and removal confirmations, orphans, cancel.** `c5f8c92` (test), `08ccc8e` (feat).
3. **Task 3: local failure issue and owner-only approval wording.** `295795a` (feat, tests included).

## Decisions Made

See `key-decisions` in the frontmatter. Three choices go beyond the plan text:

- **Instance-language markers.** The markers in the pickers follow `hass.config.language`, not the browser language of the user. A user whose UI language differs from the server language sees the markers in the server language. Step texts, menus and the mode selector are still translated by the frontend.
- **Approval closing line.** "Nothing runs until you submit" would contradict "local actions may already run". The en and de lines now name the owner actions, and the `FIXABLE_WORDING` pin was updated to match.
- **Label collapse.** A label is shown once only when the friendly name equals the StateValue exactly. This keeps "Party (party)" readable as both, as D-11 requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Existing hub options tests opened the old init form**
- **Found during:** Task 1 GREEN, in the full unit tier.
- **Issue:** 16 tests in `test_hub_removal.py`, `test_discovery_export.py` and `test_native_cleanup.py` submitted settings to `init`, which is now a menu. `test_translations.py` required `options.step.init.data.*`.
- **Fix:** A new helper, `tests.helpers.open_hub_settings`, opens the menu and chooses `settings`. Every caller uses it. The required keys now name `options.step.settings.*` plus the two menu options.
- **Commit:** `d71de7e`

**2. [Rule 3 - Blocking] Troubleshooting must document every issue key**
- **Found during:** Task 3.
- **Issue:** `test_docs.py::test_troubleshooting_covers_every_issue_key` fails as soon as `issues.local_action_failed` exists. `docs/troubleshooting.md` is not in `files_modified`.
- **Fix:** Added a `local_action_failed` entry. It covers meaning, cause, the fix in the options, the clear conditions, and that device removal deletes the issue. Plan 11-12 may extend it.
- **Commit:** `295795a`

**3. [Rule 1 - Bug] Select StateValue hidden by a case-insensitive label collapse**
- **Found during:** Task 2 GREEN.
- **Issue:** The first label rule collapsed "Party (party)" to "Party".
- **Fix:** The rule now collapses on exact equality only.
- **Commit:** `08ccc8e`

**Total deviations:** 3 auto-fixed (2 Rule 3, 1 Rule 1). **Impact:** No scope creep. The settings behavior is unchanged behind one extra menu click.

## Known Stubs

None. Broken-windows entry 3 (the missing `local_action_failed` and approval translations) is marked fixed.

## Threat Flags

None beyond the plan register:
- T-11-24 is covered by identity values, the Manager read at each step and the Manager recheck.
- T-11-25 is covered by separate confirmations and the owner-only wording.
- T-11-26 is covered by escaped placeholders, while select labels stay plain text.

## Hand-offs

- **Plan 11-09:** add `local_action_device_count` to the `settings` step (`options.step.settings.description`). `HubOptionsFlow.async_step_settings` is the place to supply it.
- **Plan 11-12:** README and the troubleshooting entry can extend the editor walkthrough. Documentation should note that the picker markers follow the server language.
- **Plan 11-13 / UAT:** look at the real menus, the dynamic labels and both confirmations in en and de on the bench (coverage D6).

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None.

## Next Phase Readiness

The editor is complete for 11-09 to 11-13. Every wave gate still runs the unfiltered tiers.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

All created and modified files exist. All 5 task commits are ancestors of HEAD. Both RED records classify as RED_EVIDENCE_OK.
