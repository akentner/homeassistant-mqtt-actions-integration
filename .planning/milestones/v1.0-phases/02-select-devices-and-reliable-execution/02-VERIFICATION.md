---
phase: 02-select-devices-and-reliable-execution
verified: 2026-10-08T12:00:00Z
status: passed
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
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md
  - .planning/phases/08-real-instance-verification/08-UAT.md
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
  - tests/test_docs.py
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
covered_digest: "v3:sha256:f7872a5817b2d9ef1a404da558e5c2d9a84f0e64cbc9d97547c70211533bd284"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "Plan truth (02-03): test-button lifecycle follows options (add, rename keeps unique_id, remove tombstones the entity, device delete clears all)"
    reason: "superseded by Phase 5: native switch and select entities with native test buttons replaced MQTT Discovery as the default (ADR 0001, D-03). A native test button needs no tombstone and no discovery clear: removing an option removes its registry entry, a rename follows live and keeps the unique id (derived from the immutable trigger key), and the test topic is not subscribed for a native device. The Discovery tombstone path stays only as the compatibility path for devices that are not native yet and its tests still pass. Evidence: docs/adr/0001-native-entities-instead-of-mqtt-discovery.md; tests/test_native_entities.py::test_removing_an_option_removes_its_native_button_entry, ::test_a_native_device_subscribes_no_test_topic, ::test_new_native_test_buttons_are_diagnostic_and_disabled_by_default, ::test_an_existing_test_button_entry_is_left_as_it_is, ::test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing; legacy path: tests/test_test_buttons.py::test_removed_option_removes_its_button_entity, ::test_renamed_option_renames_button_and_keeps_unique_id, ::test_delete_device_clears_buttons_with_the_discovery_clear"
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T16:00:00Z"
gaps: []
deferred: []
---

# Phase 2: Select Devices and Reliable Execution Verification Report

**Phase Goal:** As a Home Assistant user, I want to create Select devices whose options each run their own actions, so that multi-state MQTT devices drive my setup predictably.
**Verified:** 2026-10-08T12:00:00Z
**Status:** passed
**Re-verification:** Yes. The previous report (2026-10-04, `human_needed`, 10/10) left two human items open. This run judges the current code at the Phase 8 build under test, `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3` (08-evidence/00-preflight/build.txt). The `custom_components` tree at that sha is identical to the current HEAD `fab7c80` (`git diff --stat b7f52b34 HEAD -- custom_components` is empty), and `custom_components`, `tests`, `.github`, `README.md` and `docs` are unchanged between the earlier frozen sha `81db888c5e49389ea7dc27626100f6e090535e61` and `b7f52b34`, so the code-level truths of the previous run carry over unchanged. They were re-checked here against the code and the tests, not copied.

## Goal Achievement

The goal holds on the current code. All five roadmap success criteria and the five plan truths have a substantive, wired implementation and passing behavioral tests. One truth stays carried as superseded by Phase 5 (the Discovery test-button lifecycle, owner decision D-03; supersession record kept as recorded, not re-litigated). No truth failed, so there is no gap and no regression.

The two human items of the previous report are resolved by blocks 11 and 12 of the Phase 8 ledger (`08-UAT.md`, P2-1 and P2-2), both `result: pass` on the recorded build sha. Their note lines say which parts were scripted and which were judged by the owner; that split is repeated below and is not overstated.

Phase 5 changed how the user-visible entities are produced (ADR 0001): a native `DeviceSelect` and native test buttons are the default, and the Discovery select with mapping templates and the test topic is the compatibility path for a device that is not native yet (`Manager.is_native`, manager.py:636). The behavior that Phase 2 promises (options run their own actions, unknown payloads are ignored, run modes, test press, circuit breaker) lives in code both paths share (`Manager._on_message`, `_run_trigger`, `ActionRunner`, `CircuitBreaker`, `StateTracker`).

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: User can create a Select device with several options (StateValue, StateFriendlyName, actions); choosing an option in the UI or publishing its StateValue to the state topic runs that option's actions | ✓ VERIFIED | `SelectSubentryFlow` (config_flow.py:392) is registered in `async_get_supported_subentry_types` (config_flow.py:138); `model.spec_from_data` builds one `TriggerSpec` per option; `Manager._on_message` (manager.py:2285) decides on the accepted map and `_run_trigger` (manager.py:2363) enqueues only the matching trigger. Native UI half: `DeviceSelect.async_select_option` (select.py:33, 120) maps the friendly name to the StateValue and calls `Manager.async_send_state` (manager.py:2349), which publishes the StateValue. Tests (pass in this run): tests/test_config_flow_select.py::test_tracer_select_flow_creates_two_option_device_that_runs_actions; tests/test_manager_select.py::test_tracer_select_option_payload_runs_only_that_option, ::test_select_payload_is_trimmed_and_case_insensitive; tests/test_native_entities.py::test_choosing_an_option_publishes_the_state_value_not_the_friendly_name, ::test_native_select_offers_the_friendly_names_and_shows_the_current_one; legacy path: tests/test_discovery_select.py::test_select_entity_options_and_state_round_trip. Real instances: Phase 8 UAT-03 (block 3, pass 2026-10-04) ran a command across two real instances; P2-1 (block 11) ran the flow in the real frontend. |
| 2 | SC2: User can later edit an option's StateFriendlyName and actions; StateValue is locked after creation | ✓ VERIFIED | `async_step_edit_option_details` (config_flow.py:563) has no StateValue field and calls `validate_option(..., editing=True)` (config_flow.py:576); the flow edits a deep-copied draft and replaces the stored data only at Done. Tests: tests/test_config_flow_select.py::test_edit_option_form_has_no_state_value_field, ::test_edit_option_changes_friendly_name_and_actions_only, ::test_flow_never_mutates_stored_data_before_done, ::test_reconfigure_replaces_data_and_keeps_device_id; tests/test_native_entities.py::test_renaming_an_option_is_followed_live. Real HA: p2-1/flow-precheck.txt steps 9 to 11 (edit form carries the state value only as a placeholder, rename stored as "One edited", state value `one` unchanged). |
| 3 | SC3: A Select payload that matches no StateValue is ignored and logged; no actions run and the entity keeps its state | ✓ VERIFIED | `state.decide` returns `ignored=True` without moving the baseline (state.py:47); `Manager._on_message` logs it through `_log_ignored` (manager.py:2527) and returns; `_record_value` (manager.py:2307) records only accepted values. Tests: tests/test_manager_select.py::test_select_unknown_payload_is_ignored_and_logged, ::test_select_unknown_retained_payload_sets_no_baseline; tests/test_native_entities.py::test_an_unknown_select_payload_keeps_the_state; legacy: tests/test_discovery_select.py::test_select_unknown_payload_keeps_state_without_core_warning. Real instances: UAT-03 step D (`banana`, QoS 1, not retained): marker deltas 0 on both instances, `Ignoring unknown payload` logged once on each, entity state unchanged, retained broker value unchanged. |
| 4 | SC4: Per device serial (default) or restart run mode, and a test button that runs a device's actions locally without changing state | ✓ VERIFIED | One `Script` per device with `script_mode="queued"` (serial) or `"restart"`, `max_runs=SERIAL_QUEUE_LIMIT`, `max_exceeded="WARNING"` (runner.py:131-133); a missing `run_mode` maps to serial (model.py). The native `DeviceTestButton.async_press` (button.py:94, 115) calls `Manager.async_press_test` (manager.py:2492), which goes through the mode gate and never touches tracker, baseline, breaker or the state topic. Behavioral tests (named, pass in this run): tests/test_runner_modes.py::test_restart_mode_newer_change_cancels_running_run, ::test_restart_mode_cancels_across_select_options, ::test_serial_mode_keeps_order_across_select_options, ::test_serial_queue_is_bounded_and_overflow_is_dropped_with_warning; tests/test_native_entities.py::test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing, ::test_observe_and_disabled_modes_block_the_press; legacy: tests/test_test_buttons.py::test_press_runs_only_that_triggers_actions_locally. Phase 5 note: a new native test button is diagnostic and disabled by default, so the user enables it first; the criterion (a button that runs the actions locally without changing state) holds. |
| 5 | SC5: An action that toggles its own device is stopped by a per-device circuit breaker and the user is told why | ✓ VERIFIED | `CircuitBreaker.record` (breaker.py:27) trips on the call after `max_runs` within the window; `_run_trigger` calls it before `enqueue` (manager.py:2381); `_trip` (manager.py:2402) warns, creates the Repairs issue `circuit_breaker_<id>`, stores the tripped hash and stops queued and running runs; the issue text is in en.json and de.json. Tests: tests/test_manager_breaker.py::test_self_toggling_action_is_stopped, ::test_change_after_max_runs_trips_pauses_and_informs, ::test_trip_stops_running_and_queued_runs, ::test_test_press_is_not_counted_and_works_while_paused; tests/test_breaker.py. Real instance: Phase 8 P2-2 (block 12), scripted verdict PASS on real Mosquitto and a real HA 2026.9.4 process (p2-2/verdict.txt): after the external ON the loop produced 6 live messages (accepted range 5 to 8) and exactly one breaker warning; the Repairs issue was listed; the card rendering in English and German was judged by the owner (see item 2). |
| 6 | Plan truth (02-02): each device runs through one Script that dispatches on the trigger, so ordering and cancellation hold across triggers; a cancelled or dropped run never raises or clears an issue wrongly | ✓ VERIFIED | `choose` dispatch on the hashed trigger key in one Script per device (runner.py); `CancelledError` is a `BaseException` and is never caught. Behavior-dependent truth, backed by named passing behavioral tests (run in this verification): tests/test_runner_modes.py::test_one_script_per_device, ::test_superseded_run_does_not_clear_failure_issue, ::test_dropped_run_does_not_clear_failure_issue, ::test_unload_stops_running_and_queued_runs, ::test_restart_mode_action_less_trigger_change_does_not_cancel_running_run. |
| 7 | Plan truth (02-03): test-button lifecycle follows options (add, rename keeps unique_id, remove tombstones the entity, device delete clears all) | ✓ PASSED (override) | Superseded by Phase 5 (D-03), see the `overrides` entry and the Superseded Items section. The user-visible outcome holds on the native default through registry removal, not Discovery tombstones. |
| 8 | Plan truth (02-04): tripped state persists across restart as a config hash, is released by a config change or unload/reload, and is cleaned up on delete and hub removal | ✓ VERIFIED | `_tripped` is saved with the base data and parsed by `_parse_tripped`; `_restore_tripped` (manager.py:2424) compares the hash and re-pauses or drops it; a config change pops it in `_async_change_device`; `release_all_breakers` (manager.py:1173) is called from the unload path (`__init__.py:77`); delete, hub removal, release and mirror drop pop the entry. Behavior-dependent truth. Named tests (pass in this run): tests/test_manager_breaker.py::test_tripped_device_stays_paused_after_restart, ::test_tripped_entry_with_different_hash_is_dropped_at_start, ::test_config_change_releases_the_breaker, ::test_unchanged_save_does_not_release, ::test_reload_releases_the_breaker, ::test_stop_without_unload_keeps_the_tripped_state, ::test_delete_device_forgets_tripped_entry_and_deletes_issue, ::test_hub_removal_deletes_breaker_issues, ::test_malformed_tripped_store_is_dropped_and_setup_succeeds. Real instance (P2-2, verdict.txt, scripted): after the trip the device stayed paused (an external OFF produced exactly one live message and no actions), the issue was still listed after `podman restart ha-a`, a further external ON again produced exactly one live message (still paused), and a hub reload released the pause and removed the issue. |
| 9 | Plan truth (02-05/D-04): option validation (at least two options, StateValue non-empty, unique ignoring case, no surrounding whitespace, friendly name required, unique, never `none`); breaker fields range-validated; Phase 1 Switch data prefills defaults | ✓ VERIFIED | `model.validate_option` and `validate_breaker`, called from the flow; the menu hides Done below two options. Tests: tests/test_config_flow_select.py::test_add_option_validation, ::test_edit_option_validation, ::test_menu_visibility, ::test_select_flow_settings_validation, ::test_select_flow_stores_settings_as_ints, ::test_reconfigure_prefills_defaults_for_a_select_without_settings; tests/test_model.py. Real HA: p2-1/flow-precheck.txt steps 2 to 6 and 14 (Done offered only from two options, Remove only from three, hidden again at two). |
| 10 | Regression: Phase 1 Switch behavior and Phase 1 must-haves still hold | ✓ VERIFIED | `SWITCH_ACCEPTED` keeps ON/OFF (state.py); baseline and run-on-startup logic are unchanged in `state.decide`. Automated-tier proof for the code at the frozen sha: 1490 passed in each of three local runs and in three CI dispatch runs (1308 unit, 17 broker, 165 multi-instance), Ruff and format clean (07-PROOF.md, cited; code unchanged since). Re-run in this verification: 384 passed (see Behavioral Spot-Checks), including tests/test_state.py and tests/test_native_entities.py::test_native_switch_state_follows_the_state_topic. |

**Score:** 10/10 truths verified (9 VERIFIED, 1 PASSED by override), 0 present and behavior-unverified. Truths 4, 5, 6 and 8 are behavior-dependent (cancellation, cleanup and ordering invariants); each has a named passing behavioral test run in this verification, and truths 5 and 8 additionally have the real-instance P2-2 evidence.

### Superseded Items (Phase 5, D-03)

Recorded as in the previous report; not re-judged.

| Item | What changed | Evidence of the new behavior | Scored as |
|------|--------------|------------------------------|-----------|
| Truth 7: Discovery button tombstones and discovery clear for test buttons | Native test buttons need no tombstone: a removed option removes the registry entry, the test topic is not subscribed for a native device, new buttons are diagnostic and disabled by default | ADR 0001 (decision D-03, criterion b); tests/test_native_entities.py::test_removing_an_option_removes_its_native_button_entry, ::test_a_native_device_subscribes_no_test_topic, ::test_new_native_test_buttons_are_diagnostic_and_disabled_by_default | PASSED (override), 1 override entry |
| Review finding IN-06 (button tombstones are memory-only) | Moot for native devices; remains only on the legacy path | same as above | informational |
| Mechanism evidence of Truths 1 and 3 (Discovery select with `value_template` and `command_template`) | The default select is the native `DeviceSelect`; the Discovery select remains the compatibility path and its tests still pass | tests/test_native_entities.py::test_native_select_offers_the_friendly_names_and_shows_the_current_one, ::test_an_unknown_select_payload_keeps_the_state, ::test_removing_the_selected_option_leaves_the_state_unknown; ADR 0001 | the truths themselves are VERIFIED on the native evidence, no override needed |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/model.py` | Pure DeviceSpec/TriggerSpec, `spec_from_data`, `validate_option`, `validate_breaker` | ✓ VERIFIED | Used by manager, runner, discovery, flow and the native entities |
| `custom_components/mqtt_actions/state.py` | `decide()` and `StateTracker` driven by the accepted map | ✓ VERIFIED | `ignored` decision at state.py:47, wired from `spec.accepted` |
| `custom_components/mqtt_actions/runner.py` | One Script per device, run modes, queue bound | ✓ VERIFIED | `script_mode`, `max_runs`, `max_exceeded` at runner.py:131-133 |
| `custom_components/mqtt_actions/breaker.py` | Pure sliding-window breaker, injected clock | ✓ VERIFIED | `record` at breaker.py:27, used by `_new_breaker` (manager.py:2393) |
| `custom_components/mqtt_actions/manager.py` | Select-capable manager, breaker, tripped persistence, native press and send | ✓ VERIFIED | Paths read above; shared by the legacy and the native path |
| `custom_components/mqtt_actions/config_flow.py` | `SelectSubentryFlow` with the option menu loop | ✓ VERIFIED | Registered in the supported subentry types (config_flow.py:138) |
| `custom_components/mqtt_actions/select.py`, `button.py`, `entities.py` | Native `DeviceSelect`, `DeviceTestButton`, `RestorePreviousButton` (Phase 5, the default) | ✓ VERIFIED | Platform setup adds them per owned device and mirror when `is_native` |
| `custom_components/mqtt_actions/discovery.py`, `topics.py` | Legacy Select/button discovery, `test_topic` (compatibility path) | ✓ VERIFIED | Still published for a device that is not native; tests pass |
| `translations/en.json`, `translations/de.json` | Flow steps, errors, Repairs text | ✓ VERIFIED | tests/test_translations.py passes (key parity); real rendering judged in P2-1 and P2-2 |
| `README.md` | Select, run mode, test buttons, breaker docs | ✓ VERIFIED | Pinned by tests/test_docs.py |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| manager.py | model.py | `spec_from_subentry` builds the DeviceSpec for tracker, runner, discovery, entities | WIRED | `_async_add_device` |
| model.py | state.py | `DeviceSpec.accepted` handed to `StateTracker` | WIRED | `_on_message` uses `device.tracker.handle` |
| manager.py | runner.py | `_run_trigger` and the test enqueue call `runner.enqueue` | WIRED | manager.py:2363 ff., `async_press_test` 2492 ff. |
| manager.py | breaker.py | `_run_trigger` calls `device.breaker.record()` before `enqueue`, `_trip` on False | WIRED | manager.py:2381 |
| `__init__.py` | manager.py | unload calls `release_all_breakers` | WIRED | `__init__.py:77` |
| select.py / button.py | manager.py | `async_send_state`, `async_press_test`, `async_restore_previous` | WIRED | select.py:33, 120; button.py:39, 94, 115 |
| config_flow.py | manager.py | update listener reconciles after `async_create_entry` / `async_update_and_abort` | WIRED | tests/test_config_flow_select.py::test_reconfigure_replaces_data_and_keeps_device_id |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Native `DeviceSelect` | `options`, `current_option` | `device.spec.triggers` and `device.value`, recorded by `_record_value` from the state topic | Yes, tests drive real core select entities; the real instances ran UAT-03 | ✓ FLOWING |
| Script per device | `sequence` | `trigger.actions` validated per trigger from stored options | Yes | ✓ FLOWING |
| Breaker issue text | `device`, `max_runs`, `window` | `device.name`, `spec.breaker_*` | Yes (P2-2: the issue was listed on the real instance) | ✓ FLOWING |
| Native test button name | `trigger.friendly_name` | live spec, refreshed by `_on_signal` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 2 test files plus native entities (breaker, flow, discovery select, manager select and breaker, run modes, test buttons, model, state, translations, native entities) | `uv run --locked pytest -q -p no:cacheprovider tests/test_breaker.py tests/test_config_flow_select.py tests/test_discovery_select.py tests/test_manager_select.py tests/test_manager_breaker.py tests/test_runner_modes.py tests/test_test_buttons.py tests/test_model.py tests/test_state.py tests/test_translations.py tests/test_native_entities.py` | 384 passed in 26.20s | ✓ PASS |
| Full suite and CI on the code (cited, not re-run) | 07-PROOF.md | 1490 passed, three local runs plus three CI dispatch runs; the code is unchanged since | ✓ PASS (cited) |
| Build identity | `git diff --stat b7f52b34 HEAD -- custom_components` | empty (tree identical to the Phase 8 build under test) | ✓ PASS |
| Debt markers | `grep -rnE "TBD\|FIXME\|XXX\|TODO\|HACK" custom_components README.md` | no matches | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED. The plans declare no `probe-*.sh` scripts and none exist.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DEV-03 | 02-01, 02-05 | Create a Select device with multiple options (StateValue, StateFriendlyName, actions) | ✓ SATISFIED | Truth 1; P2-1 |
| DEV-04 | 02-05 | Edit StateFriendlyName and actions of an option; StateValue immutable | ✓ SATISFIED | Truth 2 |
| DEV-06 | 02-02, 02-05 | Per-device run mode, serial default or restart | ✓ SATISFIED | Truths 4 and 6 |
| DEV-07 | 02-03 | Test button runs actions locally without changing state | ✓ SATISFIED | Truths 4 and 7 (native buttons, diagnostic and disabled by default since Phase 5) |
| STA-06 | 02-04, 02-05 | Per-device circuit breaker stops self-triggering loops | ✓ SATISFIED | Truths 5 and 8; P2-2 |
| STA-07 | 02-01 | Select payload matching no StateValue is ignored and logged | ✓ SATISFIED | Truth 3; UAT-03 step D |

REQUIREMENTS.md (v1.0) maps exactly these six IDs to Phase 2; all six are claimed by plans, none is orphaned.

### Anti-Patterns Found

No debt markers, stubs, placeholder returns or hollow props in the files of this phase. The advisory review findings of 02-REVIEW.md stay recorded as `open` in 02-REVIEW-DISPOSITION.md and are not blockers (none defeats a success criterion); they are unchanged by this re-verification, except IN-06, which Phase 5 made moot for native devices. The one open Phase 8 gap (UAT-04, block 4, owner decision UAT04-DISPOSITION: leave as gap) concerns the Phase 5 Discovery export and the core MQTT prefix, not a Phase 2 truth.

### Human-Verification Items

Both items of the previous report are resolved by the Phase 8 ledger (`.planning/phases/08-real-instance-verification/08-UAT.md`). Each block was read in full; both are `result: pass`, carry no `override_by:` line and no contradicting `status:`.

#### 1. Select flow in the real frontend: RESOLVED

resolution: block 11 (P2-1, select subentry flow) of 08-UAT.md, `result: pass`, evidence folder `.planning/phases/08-real-instance-verification/08-evidence/p2-1`, recorded sha `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`, date 2026-10-06.

What was scripted and what was owner-judged (as the block's note says): the data path through the subentry flow REST API was scripted (`flow-precheck.txt`, 16 steps, PASS: menu entries by option count, Done only from two options, Remove only from three and hidden again at two, edit with the state value locked, remove with the confirmation menu, add, reconfigure saved with the retained document holding "One edited", three, four). The rendering and wording in English and German (menu loop, option list, ActionSelector, labels) in the real frontend were judged by the owner in their own browser on ha-a: statement of 2026-10-06, per item, verbatim "Vollständig, ok". The owner first answered "Noch nicht geprüft" and "Nur teilweise gesehen" before confirming this item completely when asked per item. There are no screenshots (browser MCP was unavailable). In this build the "Done" menu entry is labelled "Save the device" (DE "Gerät speichern"). The ActionSelector and the `device_id` warning rendering are not named separately in the block; the owner's confirmation covers the whole item as the block records it.

#### 2. Circuit breaker end to end on a real broker and a real HA: RESOLVED

resolution: block 12 (P2-2, breaker loop) of 08-UAT.md, `result: pass`, evidence folder `.planning/phases/08-real-instance-verification/08-evidence/p2-2`, recorded sha `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`, date 2026-10-06.

What was scripted and what was owner-judged: the loop, trip, pause, restart and release were scripted against a real Mosquitto and the real HA process on ha-a (`verdict.txt` PASS): 6 live messages on the state topic after the trip (accepted 5 to 8), exactly one breaker warning, a paused device produced exactly one live message per external change, the issue was still listed after `podman restart ha-a` and the pause held, a hub reload released the pause and removed the issue, and a further external OFF re-ran and re-tripped it. The rendering of the Repairs card in English and German (device, limits 5 runs / 10 s, pause explanation, release hint) was judged by the owner in their own browser: statement of 2026-10-06, per item, verbatim "Vollständig, ok", again after first answering "Noch nicht geprüft" and "Nur teilweise gesehen". No screenshots exist. The note also records that the ha-b mirror of the loop device is a `blocked_` issue rather than an approval request, because `mqtt.publish` is denied for broker-received actions; this is expected and not a Phase 2 gap.

### Gaps Summary

No gaps, no regression, no open human item. Every truth holds on the current code (identical to the Phase 8 build under test), one is carried as superseded by Phase 5, and both human items of the previous report are resolved by passing real-instance ledger blocks whose scripted and owner-judged parts are stated above.

---

_Verified: 2026-10-08T12:00:00Z_
_Verifier: Claude (gsd-verifier)_

## Digest refresh (2026-10-08)

`covered_digest` was refreshed from `verification.fingerprint` over this report's own `covered_files` after `08-UAT.md` gained its `## Verification refresh` section (a ledger edit made after the verifier ran, plan 08-10 Task 3). No other content of this report changed; the digest was copied from the tool output, not written by hand. Previous digest: `v3:sha256:ba704071aef5edb9d00bf6fb9582dedb8c074f73f7ecead23e981bdfa2e54916`.
