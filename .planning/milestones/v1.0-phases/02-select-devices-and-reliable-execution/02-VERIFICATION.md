---
phase: 02-select-devices-and-reliable-execution
verified: 2026-10-04T16:00:00Z
status: human_needed
score: 10/10 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-01-PLAN.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-01-SUMMARY.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-02-PLAN.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-02-SUMMARY.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-03-PLAN.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-03-SUMMARY.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-04-PLAN.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-04-SUMMARY.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-05-PLAN.md
  - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-05-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/breaker.py
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/select.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - docs/adr/0001-native-entities-instead-of-mqtt-discovery.md
  - tests/broker/test_acl.py
  - tests/broker/test_retain_semantics.py
  - tests/conftest.py
  - tests/test_breaker.py
  - tests/test_config_flow_select.py
  - tests/test_discovery_select.py
  - tests/test_manager_breaker.py
  - tests/test_manager_select.py
  - tests/test_model.py
  - tests/test_multi_instance.py
  - tests/test_native_entities.py
  - tests/test_retrigger.py
  - tests/test_runner_modes.py
  - tests/test_state.py
  - tests/test_sync_follower.py
  - tests/test_test_buttons.py
  - tests/test_translations.py
covered_digest: "v2:sha256:848ac826e92b4db4cbe4a467aa29c09ed2e2008d753664eac9ebdc21625f4d05"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "Plan truth (02-03): test-button lifecycle follows options (add, rename keeps unique_id, remove tombstones the entity, device delete clears all)"
    reason: "superseded by Phase 5: native switch and select entities with native test buttons replaced MQTT Discovery as the default (ADR 0001, D-03). A native test button needs no tombstone and no discovery clear: removing an option removes its registry entry, a rename follows live and keeps the unique id (derived from the immutable trigger key), and the test topic is not subscribed for a native device. The Discovery tombstone path stays only as the compatibility path for devices that are not native yet and its tests still pass. Evidence: docs/adr/0001-native-entities-instead-of-mqtt-discovery.md; tests/test_native_entities.py::test_removing_an_option_removes_its_native_button_entry, ::test_a_native_device_subscribes_no_test_topic, ::test_new_native_test_buttons_are_diagnostic_and_disabled_by_default, ::test_an_existing_test_button_entry_is_left_as_it_is, ::test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing; legacy path: tests/test_test_buttons.py::test_removed_option_removes_its_button_entity, ::test_renamed_option_renames_button_and_keeps_unique_id, ::test_delete_device_clears_buttons_with_the_discovery_clear"
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T16:00:00Z"
gaps: []
deferred: []
human_verification:
  - test: "Open the real HA frontend and run the Select subentry flow (Add select device, name and settings, three options with actions from the action editor, Done), then reconfigure it (edit an option, add one, remove one with the confirmation), in English and in German."
    expected: "The menu loop renders, Done appears only after two options, the option list text and the translated labels are correct, the ActionSelector renders inside the option step, invalid actions and device_id targets show the warning, and StateValue is not editable on reconfigure."
    why_human: "The flow is covered through the flow manager API (tests/test_config_flow_select.py) and the translation key parity (tests/test_translations.py), but no automated test renders the frontend, and Phase 8 (UAT-01 to UAT-04) does not name this check. The owner recorded a pass in 02-UAT.md on 2026-09-30, but config_flow.py and the translations changed afterwards (03-08 escaping, Phase 4 flows, Phase 5 native entities), so that pass is not evidence for the final code. Accept it as an override under the owner's name or run it again."
  - test: "Against a real broker and a real Home Assistant, build a device whose action publishes the opposite value to its own state topic (default breaker, 5 runs in 10 seconds), trigger it once, check the rendered Repairs card in English and German, release it by reconfigure or reload, and restart HA while it is paused."
    expected: "The loop stops after 5 runs, a warning is logged, the 'circuit breaker' Repairs card names the device and the limits and explains the release, a test button still works while paused, release removes the issue, and the paused state and issue are back after a real HA restart."
    why_human: "The loop, the trip, the release paths and the persistence across a manager restart are covered with the mqtt_mock and the fake broker (tests/test_manager_breaker.py), but no automated test runs the self-flipping loop through a real Mosquitto and a real HA process, and none renders the Repairs card. Phase 8 UAT-03 names a command across two real instances and an unknown payload, not the breaker loop. Accept as an override under the owner's name, add a test, or run it in Phase 8."
---

# Phase 2: Select Devices and Reliable Execution Verification Report

**Phase Goal:** As a Home Assistant user, I want to create Select devices whose options each run their own actions, so that multi-state MQTT devices drive my setup predictably.
**Verified:** 2026-10-04T16:00:00Z
**Status:** human_needed
**Re-verification:** Yes. The previous report (2026-09-29, status passed in frontmatter, human_needed in the body, 10/10) was judged against the pre-Phase-5 code, and its stored `covered_files` named the pre-archive `.planning/phases/` paths, so the tooling read it as stale. This run judges the frozen sha `81db888c5e49389ea7dc27626100f6e090535e61`, which contains Phases 5, 6 and the Phase 7 test and CI changes (HEAD `ad98080` differs from it only by the ledger `07-PROOF.md`).

## Goal Achievement

The goal still holds on the current code. All five roadmap success criteria and the five plan truths have a substantive, wired implementation and passing behavioral tests. One truth is carried as `superseded by Phase 5` (the Discovery test-button lifecycle), under the owner decision D-03. No truth failed, so there is no regression and no gap. The status is `human_needed` because two of the six previous human items still have a part that no automated test covers and Phase 8 does not name (frontend rendering of the Select flow; the breaker loop end to end on a real broker and a real HA with the rendered Repairs card).

Phase 5 changed how the user-visible entities are produced (ADR 0001): a native `DeviceSelect` and native test buttons are the default, and the Phase 2 Discovery select with mapping templates and the test topic is only the compatibility path for a device that is not native yet (`Manager.is_native`, manager.py:636). The behavior that Phase 2 promises (options run their own actions, unknown payloads are ignored, run modes, test press, circuit breaker) lives in code that both paths share (`Manager._on_message`, `_run_trigger`, `ActionRunner`, `CircuitBreaker`, `StateTracker`) and is unchanged in substance.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: User can create a Select device with several options (StateValue, StateFriendlyName, actions); choosing an option in the UI or publishing its StateValue to the state topic runs that option's actions | ✓ VERIFIED | `SelectSubentryFlow` (config_flow.py:392) is registered in `async_get_supported_subentry_types` (config_flow.py:136); `model.spec_from_data` builds one `TriggerSpec` per option; `Manager._on_message` (manager.py:2285) decides on the accepted map and `_run_trigger` (manager.py:2363) enqueues only the matching trigger. Native UI half: `DeviceSelect.async_select_option` (select.py:~145) maps the friendly name to the StateValue and calls `Manager.async_send_state`, which publishes the exact StateValue retained at QoS 1 (manager.py:2349). Tests (all pass): tests/test_config_flow_select.py::test_tracer_select_flow_creates_two_option_device_that_runs_actions; tests/test_manager_select.py::test_tracer_select_option_payload_runs_only_that_option, ::test_select_payload_is_trimmed_and_case_insensitive; tests/test_native_entities.py::test_choosing_an_option_publishes_the_state_value_not_the_friendly_name, ::test_native_select_offers_the_friendly_names_and_shows_the_current_one; legacy path: tests/test_discovery_select.py::test_select_entity_options_and_state_round_trip. |
| 2 | SC2: User can later edit an option's StateFriendlyName and actions; StateValue is locked after creation | ✓ VERIFIED | `async_step_edit_option_details` (config_flow.py:563) has no StateValue field and calls `validate_option(..., editing=True)` (config_flow.py:576); the flow works on a deep-copied draft and replaces the data only at Done. Tests: tests/test_config_flow_select.py::test_edit_option_form_has_no_state_value_field, ::test_edit_option_changes_friendly_name_and_actions_only, ::test_flow_never_mutates_stored_data_before_done, ::test_reconfigure_replaces_data_and_keeps_device_id; native follow-through of a rename: tests/test_native_entities.py::test_renaming_an_option_is_followed_live. |
| 3 | SC3: A Select payload that matches no StateValue is ignored and logged; no actions run and the entity keeps its state | ✓ VERIFIED | `state.decide` returns `ignored=True` without moving the baseline (state.py:46); `Manager._on_message` logs it through `_log_ignored` (manager.py:2527, device name and truncated repr, a warning; the empty retained clear is only debug) and returns; `_record_value` (manager.py:2307) records only accepted values, so the native entity keeps its current option. Tests: tests/test_manager_select.py::test_select_unknown_payload_is_ignored_and_logged, ::test_select_unknown_retained_payload_sets_no_baseline; tests/test_native_entities.py::test_an_unknown_select_payload_keeps_the_state (state stays, also for the empty retained clear); legacy path: tests/test_discovery_select.py::test_select_unknown_payload_keeps_state_without_core_warning, ::test_template_and_tracker_normalize_identically. |
| 4 | SC4: Per device serial (default) or restart run mode, and a test button that runs a device's actions locally without changing state | ✓ VERIFIED | One `Script` per device with `script_mode="queued"` (serial) or `"restart"`, `max_runs=SERIAL_QUEUE_LIMIT`, `max_exceeded="WARNING"` (runner.py:131-133); a missing `run_mode` maps to serial (model.py:179); the Switch and Select flows offer the field. The native test button `DeviceTestButton.async_press` (button.py:~95) calls `Manager.async_press_test` (manager.py:2492), which goes through the mode gate `_test_blocked`, never touches tracker, baseline, breaker or the state topic, and publishes nothing. Behavioral tests: tests/test_runner_modes.py::test_restart_mode_newer_change_cancels_running_run, ::test_restart_mode_cancels_across_select_options, ::test_serial_mode_keeps_order_across_select_options, ::test_serial_queue_is_bounded_and_overflow_is_dropped_with_warning; tests/test_native_entities.py::test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing, ::test_observe_and_disabled_modes_block_the_press, ::test_press_of_an_unknown_trigger_does_nothing; legacy test topic: tests/test_test_buttons.py::test_press_runs_only_that_triggers_actions_locally, ::test_retained_test_message_is_ignored, ::test_test_run_failure_uses_normal_repairs_issue. Phase 5 note: a new native test button is diagnostic and disabled by default (an existing registry entry keeps its state), so the user enables it first; the criterion (a button that runs the actions locally without changing state) holds. |
| 5 | SC5: An action that toggles its own device is stopped by a per-device circuit breaker and the user is told why | ✓ VERIFIED | `CircuitBreaker.record` (breaker.py:27) trips on the call after `max_runs` within the window; `_run_trigger` counts only real changes that would run (manager.py:2386-2390); `_trip` (manager.py:2402) warns, creates Repairs issue `circuit_breaker_<id>`, stores the tripped hash and stops queued and running runs; the issue text exists in en.json and de.json (`circuit_breaker_tripped`). Tests: tests/test_manager_breaker.py::test_self_toggling_action_is_stopped (a real flipping service is called exactly `max_runs` times, breaker tripped, issue present), ::test_change_after_max_runs_trips_pauses_and_informs, ::test_trip_stops_running_and_queued_runs, ::test_test_press_is_not_counted_and_works_while_paused; tests/test_breaker.py. |
| 6 | Plan truth (02-02): each device runs through one Script that dispatches on the trigger, so ordering and cancellation hold across triggers; a cancelled or dropped run never raises or clears an issue wrongly | ✓ VERIFIED | `choose` dispatch on the hashed trigger key in one Script per device (runner.py); `CancelledError` is a `BaseException` and is never caught (runner.py:209 comment and handling). Tests: tests/test_runner_modes.py::test_one_script_per_device, ::test_superseded_run_does_not_clear_failure_issue, ::test_dropped_run_does_not_clear_failure_issue, ::test_unload_stops_running_and_queued_runs, ::test_restart_mode_action_less_trigger_change_does_not_cancel_running_run. Behavior-dependent truth; backed by named passing behavioral tests. |
| 7 | Plan truth (02-03): test-button lifecycle follows options (add, rename keeps unique_id, remove tombstones the entity, device delete clears all) | ✓ PASSED (override) | Superseded by Phase 5 (D-03), see the `overrides` entry and the Superseded Items section. The user-visible outcome (add, rename keeps unique id, remove drops the entity, delete clears all) holds on the native default through registry removal, not Discovery tombstones. |
| 8 | Plan truth (02-04): tripped state persists across restart as a config hash, is released by a config change or unload/reload, and is cleaned up on delete and hub removal | ✓ VERIFIED | `_tripped` is saved in `_base_data_to_save` (manager.py:1349) and parsed by `_parse_tripped` (manager.py:221); `_restore_tripped` (manager.py:2424) compares the hash and re-pauses or drops it; `_async_change_device` pops it on a config change (manager.py:2105); `release_all_breakers` (manager.py:1173) is called from the unload path (__init__.py:77); delete, hub removal, release and mirror drop pop the entry (manager.py:1542, 1631, 1808, 2158). Tests (all pass): tests/test_manager_breaker.py::test_tripped_device_stays_paused_after_restart, ::test_tripped_entry_with_different_hash_is_dropped_at_start, ::test_config_change_releases_the_breaker, ::test_unchanged_save_does_not_release, ::test_reload_releases_the_breaker, ::test_stop_without_unload_keeps_the_tripped_state, ::test_delete_device_forgets_tripped_entry_and_deletes_issue, ::test_hub_removal_deletes_breaker_issues, ::test_malformed_tripped_store_is_dropped_and_setup_succeeds; mirrors: tests/test_sync_follower.py::test_update_releases_a_tripped_breaker_and_sanitizes_the_baseline. |
| 9 | Plan truth (02-05/D-04): option validation (at least two options, StateValue non-empty, unique ignoring case, no surrounding whitespace, friendly name required, unique, never `none`); breaker fields range-validated; Phase 1 Switch data prefills defaults | ✓ VERIFIED | `model.validate_option` (model.py:202) and `validate_breaker` (model.py:242), called from the flow; the menu hides Done below two options. Tests: tests/test_config_flow_select.py::test_add_option_validation, ::test_edit_option_validation, ::test_menu_visibility, ::test_select_flow_settings_validation, ::test_select_flow_stores_settings_as_ints, ::test_reconfigure_prefills_defaults_for_a_select_without_settings; tests/test_model.py. |
| 10 | Regression: Phase 1 Switch behavior and Phase 1 must-haves still hold | ✓ VERIFIED | `SWITCH_ACCEPTED` keeps ON/OFF (state.py:12); baseline and run-on-startup logic are unchanged in `state.decide`. The full suite is green on the frozen code: 1490 passed in each of three local runs and in three CI dispatch runs (1308 unit, 17 broker, 165 multi-instance), Ruff and format clean (07-PROOF.md, sections "Local three-run proof" and "CI proof on ubuntu-24.04"). Targeted re-run in this verification: tests/test_state.py, tests/test_discovery.py, tests/test_config_flow.py pass. The native Switch counterpart is tests/test_native_entities.py::test_native_switch_state_follows_the_state_topic, ::test_the_echo_runs_the_actions_once. |

**Score:** 10/10 truths verified (9 VERIFIED, 1 PASSED by override), 0 present and behavior-unverified. Truths 4, 5, 6 and 8 are behavior-dependent (cancellation, cleanup and ordering invariants) and each has a named passing behavioral test that was run in this verification.

### Superseded Items (Phase 5, D-03)

| Item | What changed | Evidence of the new behavior | Scored as |
|------|--------------|------------------------------|-----------|
| Truth 7: Discovery button tombstones and discovery clear for test buttons | Native test buttons need no tombstone: a removed option removes the registry entry, the test topic is not subscribed for a native device, new buttons are diagnostic and disabled by default | ADR 0001 (decision D-03, criterion b); tests/test_native_entities.py::test_removing_an_option_removes_its_native_button_entry, ::test_a_native_device_subscribes_no_test_topic, ::test_new_native_test_buttons_are_diagnostic_and_disabled_by_default | PASSED (override), 1 override entry |
| Review finding IN-06 (button tombstones are memory-only) | Moot for native devices; remains only on the legacy path | same as above | informational |
| Mechanism evidence of Truths 1 and 3 (Discovery select with `value_template` and `command_template`) | The default select is the native `DeviceSelect`; the Discovery select remains the compatibility path and its tests still pass | tests/test_native_entities.py::test_native_select_offers_the_friendly_names_and_shows_the_current_one, ::test_an_unknown_select_payload_keeps_the_state, ::test_removing_the_selected_option_leaves_the_state_unknown; ADR 0001 consequence "A select no longer stays on a stale state after an option is renamed or removed" | the truths themselves are VERIFIED on the native evidence, no override needed |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/model.py` | Pure DeviceSpec/TriggerSpec, `spec_from_data`, `validate_option`, `validate_breaker` | ✓ VERIFIED | Used by manager, runner, discovery, flow and the native entities |
| `custom_components/mqtt_actions/state.py` | `decide()` and `StateTracker` driven by the accepted map | ✓ VERIFIED | 70 lines, wired from `spec.accepted` |
| `custom_components/mqtt_actions/runner.py` | One Script per device, run modes, queue bound | ✓ VERIFIED | `script_mode`, `max_runs`, `max_exceeded` at runner.py:131-133 |
| `custom_components/mqtt_actions/breaker.py` | Pure sliding-window breaker, injected clock | ✓ VERIFIED | 47 lines, used by `_new_breaker` |
| `custom_components/mqtt_actions/manager.py` | Select-capable manager, breaker, tripped persistence, native press and send | ✓ VERIFIED | Paths read above; shared by the legacy and the native path |
| `custom_components/mqtt_actions/config_flow.py` | `SelectSubentryFlow` with the option menu loop | ✓ VERIFIED | Registered in the supported subentry types |
| `custom_components/mqtt_actions/select.py`, `button.py`, `entities.py` | Native `DeviceSelect`, `DeviceTestButton`, `RestorePreviousButton` (Phase 5, the default) | ✓ VERIFIED | Platform setup adds them per owned device and mirror when `is_native` |
| `custom_components/mqtt_actions/discovery.py`, `topics.py` | Legacy Select/button discovery, `test_topic` (compatibility path) | ✓ VERIFIED | Still published for a device that is not native; tests pass |
| `translations/en.json`, `translations/de.json` | Flow steps, errors, Repairs text | ✓ VERIFIED | tests/test_translations.py passes (key parity) |
| `README.md` | Select, run mode, test buttons, breaker docs | ✓ VERIFIED | Pinned by tests/test_docs.py in the Phase 7 runs |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| manager.py | model.py | `spec_from_subentry` builds the DeviceSpec for tracker, runner, discovery, entities | WIRED | read in `_async_add_device` |
| model.py | state.py | `DeviceSpec.accepted` handed to `StateTracker` | WIRED | `_on_message` uses `device.tracker.handle` |
| manager.py | runner.py | `_run_trigger` and `_enqueue_test` call `runner.enqueue` | WIRED | manager.py:2386-2397, 2512 |
| manager.py | breaker.py | `_run_trigger` calls `device.breaker.record()` before `enqueue`, `_trip` on False | WIRED | manager.py:2388-2390 |
| `__init__.py` | manager.py | unload calls `release_all_breakers` | WIRED | __init__.py:77 |
| select.py / button.py | manager.py | `async_send_state`, `async_press_test`, `async_restore_previous` | WIRED | select.py, button.py |
| config_flow.py | manager.py | update listener reconciles after `async_create_entry` / `async_update_and_abort` | WIRED | tests/test_config_flow_select.py::test_reconfigure_replaces_data_and_keeps_device_id |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Native `DeviceSelect` | `options`, `current_option` | `device.spec.triggers` and `device.value`, recorded by `_record_value` from the state topic | Yes, tests drive real core select entities | ✓ FLOWING |
| Script per device | `sequence` | `trigger.actions` validated per trigger from stored options | Yes | ✓ FLOWING |
| Breaker issue text | `device`, `max_runs`, `window` | `device.name`, `spec.breaker_*` | Yes | ✓ FLOWING |
| Native test button name | `trigger.friendly_name` | live spec, refreshed by `_on_signal` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 2 test files (breaker, flow, discovery select, manager select and breaker, run modes, test buttons, model, state, translations) | `uv run --locked pytest -q -p no:cacheprovider tests/test_breaker.py tests/test_config_flow_select.py tests/test_discovery_select.py tests/test_manager_select.py tests/test_manager_breaker.py tests/test_runner_modes.py tests/test_test_buttons.py tests/test_model.py tests/test_state.py tests/test_translations.py` | 320 passed in 20.08s | ✓ PASS |
| Native entities, multi-instance, follower, retrigger, real-Mosquitto tier, config flow, discovery | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider tests/test_native_entities.py tests/test_multi_instance.py tests/test_sync_follower.py tests/test_retrigger.py tests/broker tests/test_config_flow.py tests/test_discovery.py` | 291 passed in 37.14s | ✓ PASS |
| Full suite on the final code (cited, not re-run) | 07-PROOF.md | 1490 passed, three local runs plus three CI dispatch runs, Validate and the release run on `v1.0.1-rc1` green | ✓ PASS (cited) |
| Debt markers | `grep -nE "TBD\|FIXME\|XXX\|TODO\|HACK"` over custom_components, translations, README | no matches | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED. The plans declare no `probe-*.sh` scripts and none exist.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DEV-03 | 02-01, 02-05 | Create a Select device with multiple options (StateValue, StateFriendlyName, actions) | ✓ SATISFIED | Truth 1 |
| DEV-04 | 02-05 | Edit StateFriendlyName and actions of an option; StateValue immutable | ✓ SATISFIED | Truth 2 |
| DEV-06 | 02-02, 02-05 | Per-device run mode, serial default or restart | ✓ SATISFIED | Truths 4 and 6 |
| DEV-07 | 02-03 | Test button runs actions locally without changing state | ✓ SATISFIED | Truths 4 and 7 (native buttons, diagnostic and disabled by default since Phase 5) |
| STA-06 | 02-04, 02-05 | Per-device circuit breaker stops self-triggering loops | ✓ SATISFIED | Truths 5 and 8 |
| STA-07 | 02-01 | Select payload matching no StateValue is ignored and logged | ✓ SATISFIED | Truth 3 |

REQUIREMENTS.md (v1.0) maps exactly these six IDs to Phase 2 and marks them complete; all six are claimed by plans, none is orphaned.

### Anti-Patterns Found

No debt markers, stubs, placeholder returns or hollow props in the files of this phase. The advisory review findings of 02-REVIEW.md stay recorded as `open` in 02-REVIEW-DISPOSITION.md and are not blockers (none defeats a success criterion); they are unchanged by this re-verification, except IN-06, which Phase 5 made moot for native devices.

### Human-Verification Items of the Previous Report (D-04)

Each of the six items of the previous report is covered by the automated tier named below, or is reported as a human item. The owner's 02-UAT.md (six passes on 2026-09-30) was recorded on the pre-Phase-5, pre-Phase-4 code and is history, not evidence for the final code.

| # | Previous item | Automated tier that covers it (test node ids) | Remaining |
|---|---------------|-----------------------------------------------|-----------|
| 1 | Create a Select device in the real UI | Flow manager API: tests/test_config_flow_select.py::test_tracer_select_flow_creates_two_option_device_that_runs_actions, ::test_menu_visibility, ::test_add_option_validation; translations: tests/test_translations.py | Frontend rendering has no automated test and is not named in Phase 8: **human item 1** (status human_needed). The earlier expectation of "one Test button per option appears" is superseded: a new native test button is diagnostic and disabled by default. |
| 2 | Select round trip against a real broker | Real Mosquitto tier: tests/broker/test_retain_semantics.py::test_replay_on_subscribe_has_retain_true, ::test_live_forward_has_retain_false, ::test_retained_clear_is_a_live_empty_message; tests/broker/test_acl.py::test_external_publisher_can_only_write_state; the two halves: tests/test_native_entities.py::test_choosing_an_option_publishes_the_state_value_not_the_friendly_name and tests/test_manager_select.py::test_select_payload_is_trimmed_and_case_insensitive, ::test_select_unknown_payload_is_ignored_and_logged; multi-instance fan-out: tests/test_multi_instance.py::test_fanout_runs_on_every_approved_instance_and_only_there | The command and unknown-payload check on real instances is Phase 8 UAT-03. Covered, no human item. |
| 3 | Reconfigure and option lifecycle | Real HA core registries in the hass fixture: tests/test_native_entities.py::test_renaming_an_option_is_followed_live, ::test_removing_the_selected_option_leaves_the_state_unknown, ::test_removing_an_option_removes_its_native_button_entry; tests/test_config_flow_select.py::test_edit_option_form_has_no_state_value_field, ::test_edit_option_changes_friendly_name_and_actions_only; legacy: tests/test_test_buttons.py::test_renamed_option_renames_button_and_keeps_unique_id, ::test_removed_option_removes_its_button_entity | The editing form rendering falls under human item 1. Covered, no separate item. |
| 4 | Run modes with real delays | tests/test_runner_modes.py::test_restart_mode_newer_change_cancels_running_run, ::test_serial_mode_keeps_order_across_select_options, ::test_superseded_run_does_not_clear_failure_issue (a real core `Script` with a service held on an event; cancellation, queueing and the absence of a Repairs issue are the integration's logic, a `delay` action blocks in the same way) | None. Covered; the tests use a held service, not a literal `delay` action. |
| 5 | Circuit breaker end to end | tests/test_manager_breaker.py::test_self_toggling_action_is_stopped, ::test_tripped_device_stays_paused_after_restart, ::test_reload_releases_the_breaker, ::test_config_change_releases_the_breaker, ::test_test_press_is_not_counted_and_works_while_paused; translations: tests/test_translations.py | The loop through a real Mosquitto and a real HA process, the rendered EN/DE Repairs card and a real HA restart are not exercised, and Phase 8 does not name them: **human item 2** (status human_needed). |
| 6 | Test buttons in the UI | tests/test_native_entities.py::test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing, ::test_observe_and_disabled_modes_block_the_press, ::test_every_new_test_button_is_diagnostic_and_disabled_and_the_restore_button_is_not; legacy: tests/test_test_buttons.py::test_press_runs_only_that_triggers_actions_locally, ::test_test_run_failure_uses_normal_repairs_issue | A frontend press calls the same `button.press` service the tests call through real core. The expectation "buttons are listed under Configuration" is superseded by Phase 5 (diagnostic, disabled by default). Covered, no human item. |

### Human Verification Required

#### 1. Select flow in the real frontend

**Test:** Run "Add select device" and a reconfigure in a real HA frontend, in English and German.
**Expected:** Menu loop, option list text, ActionSelector, warnings and labels render correctly; Done appears only after two options; StateValue is not editable on reconfigure.
**Why human:** No automated test renders the frontend, Phase 8 does not name it, and the code changed after the owner's 2026-09-30 pass.

#### 2. Circuit breaker end to end on a real broker and a real HA

**Test:** A device whose action flips its own state through a real Mosquitto, with the default limits; check the Repairs card in both languages, release it, restart HA while paused.
**Expected:** The loop stops after 5 runs, the card names the device and limits, release removes the issue, and the paused state survives a real restart.
**Why human:** Only the mqtt_mock and fake-broker tiers exercise the loop; no test renders the card or restarts a real HA, and Phase 8 UAT-03 does not cover the breaker.

Both items return to the orchestrator: the owner either accepts them as overrides under his own name, asks for a test in a fix plan, or runs them. They are not turned into passed here.

### Gaps Summary

No gaps and no regression: every truth holds on the frozen code, one is carried as superseded by Phase 5. The status is `human_needed` solely because of the two human items above.

---

_Verified: 2026-10-04T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
