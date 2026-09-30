---
phase: 02-select-devices-and-reliable-execution
verified: 2026-09-29T18:00:00Z
status: passed
score: 10/10 must-haves verified
covered_files:
  - .planning/phases/02-select-devices-and-reliable-execution/02-01-PLAN.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-01-SUMMARY.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-02-PLAN.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-02-SUMMARY.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-03-PLAN.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-03-SUMMARY.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-04-PLAN.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-04-SUMMARY.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-05-PLAN.md
  - .planning/phases/02-select-devices-and-reliable-execution/02-05-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/breaker.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - tests/__init__.py
  - tests/conftest.py
  - tests/test_breaker.py
  - tests/test_config_flow.py
  - tests/test_config_flow_select.py
  - tests/test_device_ids.py
  - tests/test_discovery.py
  - tests/test_discovery_select.py
  - tests/test_manager.py
  - tests/test_manager_breaker.py
  - tests/test_manager_select.py
  - tests/test_model.py
  - tests/test_repo_structure.py
  - tests/test_runner_modes.py
  - tests/test_state.py
  - tests/test_test_buttons.py
  - tests/test_toolchain.py
  - tests/test_topics.py
  - tests/test_tracer.py
  - tests/test_translations.py

covered_digest: "v2:sha256:39207b84898088ecda1ef3685249ff88dc29a50b1788e6dfcb5410c5cb62d1dd"
behavior_unverified: 0
overrides_applied: 0
gaps: []
deferred: []
human_verification:
  - test: "Create a Select device in a real HA UI. On the MQTT Actions integration page choose 'Add select device', enter a name and settings, add three options (StateValue, StateFriendlyName, actions built with the action editor), then Done."
    expected: "The menu loop works in the frontend (Done only appears after two options, the option list is shown in the menu text, the action editor renders in the option step, invalid actions and device_id targets produce the warning). A select entity plus one 'Test <name>' button per option appear."
    why_human: "The flow is verified through the flow manager API only; frontend rendering of menus, the ActionSelector inside a subentry step, and the translated labels cannot be checked without a real HA UI."
  - test: "Against a real broker, choose each option in the select entity in the HA UI, then publish each StateValue (also with different case and surrounding whitespace) with an external client (mosquitto_pub) to <base>/v1/devices/<id>/state, and publish an unknown payload."
    expected: "Exactly the chosen option's actions run once per real change and no other option's. The unknown payload is ignored: a warning naming the device is logged, no action runs, and the entity keeps its state."
    why_human: "Tests use the mqtt_mock fixture and async_fire_mqtt_message; the UI-to-broker-to-manager round trip is covered in two halves (publish of the exact StateValue, and message to actions), not across a real broker."
  - test: "Reconfigure the Select device: edit an option's friendly name and actions, add an option, remove an option (confirmation), and check that the StateValue is not editable. Remove or rename the currently selected option."
    expected: "Only StateFriendlyName and actions are editable. A renamed option renames its test button and keeps the button's unique_id. A removed option's button entity disappears from the entity list. The select entity shows 'unknown' after the current option is renamed or removed and recovers on the next valid payload."
    why_human: "Button-entity removal by tombstone and the unknown display are pinned against real HA core MQTT discovery in tests, but the registry and UI behavior across a real running instance is not observable in tests."
  - test: "Set a device to run mode 'restart', give an option actions with a delay of about 10 seconds plus a marker (for example a persistent notification), and switch state twice quickly. Repeat with 'serial'."
    expected: "Restart: the first run is cancelled and produces no Repairs issue and no error log, only the second run finishes. Serial: both runs complete one after another in order."
    why_human: "The tests use a held test service; real-time behavior with real delay actions and the HA trace/UI is not exercised."
  - test: "Create a device whose action flips its own state (for example a Switch whose ON and OFF actions call mqtt.publish to its own state topic with the opposite value), with the default breaker (5 runs in 10 seconds). Trigger it once."
    expected: "The loop stops after 5 runs, the device is paused, a warning is logged, and a Repairs issue 'circuit breaker' appears in English and German naming the device and the limits and explaining how to release. Reconfiguring the device (or reloading the integration) releases it and the issue disappears. A test button still works while paused. After an HA restart the paused state and the issue are still there."
    why_human: "The automated loop test simulates the broker with async_fire_mqtt_message. A real broker delivering a message from another task, the rendered Repairs text and a real HA restart persistence are not covered."
  - test: "Press the test buttons in the HA UI (Switch: Test ON and Test OFF, Select: one per option), including on a device that is already in that state."
    expected: "The trigger's actions run locally, the entity state does not change, nothing is published to the state topic, and a failing action shows the normal Repairs issue. Buttons are listed under Configuration."
    why_human: "Button entity creation and pressing through the frontend cannot be exercised in tests."
---

# Phase 2: Select Devices and Reliable Execution Verification Report

**Phase Goal:** As a Home Assistant user, I want to create Select devices whose options each run their own actions, so that multi-state MQTT devices drive my setup predictably.
**Verified:** 2026-09-29T18:00:00Z
**Status:** human_needed
**Re-verification:** No, initial verification (no previous 02-VERIFICATION.md existed)

## Goal Achievement

The goal is achieved in the code. Every roadmap success criterion has an implementation that is substantive, wired and covered by a passing test. The status is `human_needed` only because the surfaces that need a real HA frontend or a real broker were not, and cannot be, exercised by the automated tests (see Human Verification Required). No gap was found, and none of the four review warnings blocks a must-have.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: User can create a Select device with several options (StateValue, StateFriendlyName, actions); choosing an option in the UI or publishing its StateValue to the state topic runs that option's actions | ✓ VERIFIED | `SelectSubentryFlow` (config_flow.py:282-552) registered in `async_get_supported_subentry_types` (config_flow.py:120); `model.spec_from_data` builds one `TriggerSpec` per option; `Manager._on_message` (manager.py:454-485) maps the decided value to `trigger_key` and enqueues only that trigger. Tests: `test_tracer_select_flow_creates_two_option_device_that_runs_actions`, `test_tracer_select_option_payload_runs_only_that_option`, `test_select_payload_is_trimmed_and_case_insensitive`, `test_select_entity_options_and_state_round_trip` (real core select entity: `select_option` service publishes the exact StateValue retained, qos 1). UI half and payload half are separate tests; see human item 2. |
| 2 | SC2: User can later edit an option's StateFriendlyName and actions; StateValue is locked after creation | ✓ VERIFIED | `async_step_reconfigure` loads a deep-copied draft (config_flow.py:297-314); `async_step_edit_option_details` schema has no StateValue field (config_flow.py:472-478) and calls `validate_option(..., editing=True)`; `Done` replaces data and re-injects the device id (config_flow.py:527-545). Tests: `test_edit_option_form_has_no_state_value_field`, `test_edit_option_changes_friendly_name_and_actions_only`, `test_flow_never_mutates_stored_data_before_done`, `test_reconfigure_replaces_data_and_keeps_device_id`. |
| 3 | SC3: A Select payload that matches no StateValue is ignored and logged; no actions run and the entity keeps its state | ✓ VERIFIED | `state.decide` returns `ignored=True` for an unknown payload without moving the baseline (state.py:45-47); `Manager._log_ignored` logs device name and truncated repr (manager.py:588-595); the discovery `value_template` renders `''` for unknown values, which core ignores. Tests: `test_select_unknown_payload_is_ignored_and_logged`, `test_select_unknown_retained_payload_sets_no_baseline`, `test_select_unknown_payload_keeps_state_without_core_warning` (real core: state stays, no warning), `test_template_and_tracker_normalize_identically`. |
| 4 | SC4: Per device serial (default) or restart run mode, and a test button that runs a device's actions locally without changing state | ✓ VERIFIED | `ActionRunner._async_build_script` builds ONE `Script` per device with `script_mode="queued"` (serial) or `"restart"`, `max_runs=SERIAL_QUEUE_LIMIT` (runner.py:93-102); missing `run_mode` maps to serial (model.py:168); the flow offers the run mode for Switch and Select (config_flow.py:156-175). Buttons: `discovery._button_component` per trigger with a non-retained test topic; `Manager._on_test_message` (manager.py:562-586) enqueues with `test=True` and never touches tracker, baseline, state topic or breaker; retained messages ignored. Behavioral tests: `test_restart_mode_newer_change_cancels_running_run`, `test_restart_mode_cancels_across_select_options`, `test_serial_mode_keeps_order_across_select_options`, `test_serial_queue_is_bounded_and_overflow_is_dropped_with_warning`, `test_press_runs_only_that_triggers_actions_locally`, `test_test_run_failure_uses_normal_repairs_issue`, `test_retained_test_message_is_ignored`. |
| 5 | SC5: An action that toggles its own device is stopped by a per-device circuit breaker and the user is told why | ✓ VERIFIED | `CircuitBreaker.record` (breaker.py:27-38); `Manager._on_message` counts only real changes that would run (manager.py:471-477); `_trip` logs a warning, creates Repairs issue `circuit_breaker_<id>` and stops queued runs (manager.py:496-515); issue text present in en.json and de.json (`circuit_breaker_tripped`, key parity 128/128 checked). Behavioral test: `test_self_toggling_action_is_stopped` (a real flipping service is called exactly `max_runs` times, breaker tripped, issue present), plus `test_change_after_max_runs_trips_pauses_and_informs`, `test_trip_stops_running_and_queued_runs`. |
| 6 | Plan truth (02-02): each device runs through one Script that dispatches on the trigger, so ordering and cancellation hold across triggers; a cancelled or dropped run never raises or clears an issue wrongly | ✓ VERIFIED | `choose` dispatch on hashed `trigger_key` only (runner.py:75-87); `CancelledError` is never caught (runner.py:177-187); generation guard on `clear_issue`. Tests: `test_one_script_per_device`, `test_superseded_run_does_not_clear_failure_issue`, `test_dropped_run_does_not_clear_failure_issue`, `test_unload_stops_running_and_queued_runs`, `test_restart_mode_action_less_trigger_change_does_not_cancel_running_run`. |
| 7 | Plan truth (02-03): test-button lifecycle follows options (add, rename keeps unique_id, remove tombstones the entity, device delete clears all) | ✓ VERIFIED | `button_component_key`, `build_discovery` tombstones (`{"platform": "button"}`) for `retired` keys (discovery.py:113-137); `_async_change_device` maintains `retired_components` (manager.py:379-383). Tests: `test_removed_option_removes_its_button_entity`, `test_renamed_option_renames_button_and_keeps_unique_id`, `test_omitted_component_is_not_removed_but_tombstone_is` (characterization against real core discovery), `test_delete_device_clears_buttons_with_the_discovery_clear`. Limitation: tombstones are memory-only (review IN-06). |
| 8 | Plan truth (02-04): tripped state persists across restart as a config hash, is released by a config change or unload/reload, and is cleaned up on delete and hub removal | ✓ VERIFIED | `_tripped` map saved via `_data_to_save` (manager.py:316-326); `_restore_tripped` compares the hash (manager.py:518-537); `release_all_breakers` called from `async_unload_entry` (__init__.py:46-49); `async_stop` deliberately does not release. Tests: `test_tripped_device_stays_paused_after_restart`, `test_tripped_entry_with_different_hash_is_dropped_at_start`, `test_config_change_releases_the_breaker`, `test_unchanged_save_does_not_release`, `test_reload_releases_the_breaker`, `test_stop_without_unload_keeps_the_tripped_state`, `test_delete_device_forgets_tripped_entry_and_deletes_issue`, `test_hub_removal_deletes_breaker_issues`, `test_malformed_tripped_store_is_dropped_and_setup_succeeds`. |
| 9 | Plan truth (02-05/D-04): option validation (at least two options, StateValue non-empty, unique ignoring case, no surrounding whitespace, friendly name required, unique, never `none`); breaker fields range-validated; Phase 1 Switch data prefills defaults | ✓ VERIFIED | `model.validate_option` (model.py:186-218) and `validate_breaker` (model.py:226-233), called from the flow; menu hides Done below two options and Remove at two (config_flow.py:348-371). Tests: `test_add_option_validation`, `test_edit_option_validation`, `test_menu_visibility`, `test_select_flow_settings_validation`, `test_select_flow_stores_settings_as_ints`, `test_reconfigure_prefills_defaults_for_a_select_without_settings`. |
| 10 | Regression: Phase 1 Switch behavior and Phase 1 must-haves still hold | ✓ VERIFIED | Phase 1 tests (`test_tracer.py`, `test_state.py`, `test_manager.py`, `test_discovery.py`, `test_config_flow.py`, `test_device_ids.py`, and the broker tier) are part of the passing run: 422 passed in the main tier plus 4 passed in `tests/broker`. `SWITCH_ACCEPTED` keeps ON/OFF semantics; run-on-startup and baseline logic unchanged in `state.decide`. See WR-02 for one Switch inconsistency (whitespace-padded payload). |

**Score:** 10/10 truths verified (0 present, behavior-unverified). Truths 4, 5, 6 and 8 are behavior-dependent (cancellation, cleanup and ordering invariants) and each is backed by a named passing behavioral test, not by symbol presence.

### Required Artifacts

`verify.artifacts` against 02-05-PLAN.md: 5/5 passed. Manual checks for the other plans:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/model.py` | Pure DeviceSpec/TriggerSpec, `spec_from_data`, `validate_option`, `validate_breaker` | ✓ VERIFIED | 233 lines, tolerant loader, used by manager, runner, discovery and flow |
| `custom_components/mqtt_actions/state.py` | `decide()` and `StateTracker` driven by accepted map | ✓ VERIFIED | 70 lines; `accepted` map wired from `spec.accepted` |
| `custom_components/mqtt_actions/runner.py` | One Script per device, run modes, queue bound | ✓ VERIFIED | `SERIAL_QUEUE_LIMIT`, `async_build_device`, `enqueue`, `async_stop_runs` |
| `custom_components/mqtt_actions/discovery.py` | Select and button components, mapping templates, tombstones | ✓ VERIFIED | `build_value_template`, `build_command_template`, `button_component_key` |
| `custom_components/mqtt_actions/topics.py` | `test_topic` | ✓ VERIFIED | Used by discovery and manager |
| `custom_components/mqtt_actions/breaker.py` | Pure sliding-window breaker | ✓ VERIFIED | 47 lines, injected clock |
| `custom_components/mqtt_actions/manager.py` | Select-capable manager, test topic, breaker, tripped persistence | ✓ VERIFIED | 595 lines, all paths reviewed above |
| `custom_components/mqtt_actions/config_flow.py` | `SelectSubentryFlow` with menu loop | ✓ VERIFIED | Registered in supported subentry types |
| `translations/en.json`, `translations/de.json` | New steps, errors, selector options, Repairs text | ✓ VERIFIED | Key sets identical (128 leaf keys each); `tests/test_translations.py` parity test passes |
| `README.md` | Select, run mode, test buttons, breaker, unknown-state and test-topic docs | ✓ VERIFIED | Sections "Select devices" and "Run mode, test buttons and the circuit breaker" present |

### Key Link Verification

`verify.key-links` on 02-04-PLAN.md: 3/3 verified. Remaining links checked by reading the code:

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| manager.py | model.py | `spec_from_subentry` builds the DeviceSpec used by tracker, runner, discovery | WIRED | manager.py:337, 377 |
| model.py | state.py | `DeviceSpec.accepted` handed to `StateTracker` | WIRED | manager.py:343-348, 386 |
| discovery.py | `json_dumps` | every user string enters templates as a `json_dumps` literal | WIRED | discovery.py:26-33; hostile-string tests through real Template |
| runner.py | `Script` | `script_mode` queued or restart, `max_runs`, `max_exceeded` | WIRED | runner.py:93-102 |
| discovery.py | topics.py | button `command_topic` is `test_topic(...)` | WIRED | discovery.py:128-130 |
| manager.py | runner.py | `_on_test_message` enqueues with `test=True`, never touches tracker | WIRED | manager.py:579-586 |
| manager.py | breaker.py | `_on_message` calls `breaker.record()` between `decision.act` and `enqueue` | WIRED | manager.py:475 |
| `__init__.py` | manager.py | `async_unload_entry` calls `release_all_breakers` before `async_stop` | WIRED | __init__.py:46-49 |
| config_flow.py | manager.py (via update listener) | `async_create_entry` and `async_update_and_abort` trigger `_async_entry_updated` and `async_reconcile` | WIRED | __init__.py:39-42 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Select discovery payload | `options`, `value_template`, `command_template` | `spec.triggers` built from stored subentry options | Yes, round-trip test with real core discovery | ✓ FLOWING |
| Script per device | `sequence` | `trigger.actions` validated per trigger from stored options | Yes | ✓ FLOWING |
| Breaker issue text | `device`, `max_runs`, `window` | `device.name`, `spec.breaker_*` from stored data | Yes | ✓ FLOWING |
| Flow menu placeholders | `options`, `count`, `name` | in-memory draft | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Main test tier | `uv run pytest tests -q --ignore=tests/broker` | 422 passed in 19.89s | ✓ PASS |
| Real-Mosquitto tier | `uv run pytest tests/broker -q` | 4 passed | ✓ PASS |
| Lint | `uv run ruff check .` | All checks passed | ✓ PASS |
| Format | `uv run ruff format --check .` | 36 files already formatted | ✓ PASS |
| Translation parity | key-set comparison of en.json and de.json | equal, 128 keys | ✓ PASS |
| Artifact check | `verify.artifacts` 02-05-PLAN.md | 5/5 passed | ✓ PASS |
| Key links | `verify.key-links` 02-04-PLAN.md | 3/3 verified | ✓ PASS |

The full workspace suite was run once. Per-truth evidence names the tests by enumeration in `tests/`; they are part of that run.

### Probe Execution

Step 7c: SKIPPED. The plans declare no `probe-*.sh` scripts and no `scripts/*/tests/probe-*.sh` exist.

### Requirements Coverage

Requirement IDs declared in PLAN frontmatter: 02-01 DEV-03, STA-07; 02-02 DEV-06; 02-03 DEV-07; 02-04 STA-06; 02-05 DEV-03, DEV-04, DEV-06, STA-06. REQUIREMENTS.md maps exactly DEV-03, DEV-04, DEV-06, DEV-07, STA-06, STA-07 to Phase 2. All six are claimed by at least one plan; no orphaned requirement.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DEV-03 | 02-01, 02-05 | Create a Select device with multiple options (StateValue, StateFriendlyName, actions) | ✓ SATISFIED | Truth 1; `SelectSubentryFlow`, `model._select_triggers`, tracer tests. Frontend rendering: human item 1 |
| DEV-04 | 02-05 | Edit StateFriendlyName and actions of an option; StateValue immutable | ✓ SATISFIED | Truth 2; edit step has no StateValue field, `editing=True` skips the check |
| DEV-06 | 02-02, 02-05 | Per-device run mode, serial default or restart | ✓ SATISFIED | Truth 4 and 6; Script mode mapping plus flow field. Real-time behavior: human item 4 |
| DEV-07 | 02-03 | Test button runs actions locally without changing state | ✓ SATISFIED | Truth 4 and 7; `_on_test_message`. UI press: human item 6 |
| STA-06 | 02-04, 02-05 | Per-device circuit breaker stops self-triggering loops | ✓ SATISFIED | Truth 5 and 8. Real broker loop and Repairs rendering: human item 5 |
| STA-07 | 02-01 | Select payload matching no StateValue is ignored and logged | ✓ SATISFIED | Truth 3 |

REQUIREMENTS.md already marks all six `[x]` and "Complete" in the traceability table, which matches the evidence.

### Anti-Patterns Found

Debt-marker scan (`TBD|FIXME|XXX|TODO|HACK`) across `custom_components/`, translations and README: no matches. No stubs, placeholder returns, or hollow props in the phase files.

The advisory code review (02-REVIEW.md: 0 critical, 4 warnings, 6 info) is recorded with all findings still `open` in 02-REVIEW-DISPOSITION.md. I re-read the cited code and confirmed each warning is real. None defeats a roadmap success criterion, so none is a blocker, but they should be triaged.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| manager.py | 333-366 | WR-01: `self.devices[device_id]` set before subscribe and discovery succeed; a `HomeAssistantError` during a live reconcile leaves a dead device that later reconciles skip until reload | ⚠️ Warning | Only in a live reconcile when the MQTT client errors on subscribe; startup path converts it to `ConfigEntryNotReady` |
| discovery.py | 67 | WR-02: Switch `value_template` is `{{ value \| upper }}` without `trim`, while the tracker trims; a payload like `" ON"` runs the actions but the entity ignores it | ⚠️ Warning | Entity and actions can disagree for whitespace-padded Switch payloads; Select is correct (`trim \| lower`) |
| manager.py | 561-586 | WR-03: the test topic bypasses the breaker (documented as D-13 intent, but the README does not call out that this second trigger path has no loop protection) | ⚠️ Warning | Does not affect SC5 (state-path loops); an action that publishes to the test topic could loop |
| runner.py | 52-61, 104-108, 186-187 | WR-04: invalid-trigger setup error and runtime failure share the issue id `action_failed_<id>`; a successful run of another option clears the setup issue | ⚠️ Warning | An invalid option can stay broken with no persistent Repairs issue |
| runner.py | 104-108 | IN-01: setup Repairs issue omits the offending option name | ℹ️ Info | Harder to locate the broken option |
| manager.py | 576-578 | IN-02: test press on a trigger without runnable actions is silent | ℹ️ Info | No user feedback |
| model.py / discovery.py | 125-143 / 71-85 | IN-03: all-invalid stored options publish `"options": []` | ℹ️ Info | Only for corrupted storage |
| config_flow.py | 410-422, 482 | IN-04: reconfigure indexes option keys the loader treats as optional | ℹ️ Info | `KeyError` on malformed stored option |
| manager.py | 92-98 | IN-05: `signature_hash` only used by tests | ℹ️ Info | Possible drift between test helper and production path |
| manager.py | 69, 379-383 | IN-06: button tombstones are memory-only | ℹ️ Info | Relevant to Phase 3 multi-instance; should be noted in the Phase 3 plan |

### Human Verification Required

These need a real HA frontend or a real broker, so they are not guessed here.

#### 1. Create a Select device in the UI

**Test:** On the integration page choose "Add select device", enter a name and settings, add three options with actions from the action editor, then Done.
**Expected:** The menu loop, the option list text, the action editor and the German/English labels render correctly; Done only appears after two options; a select entity and one test button per option appear.
**Why human:** The flow is tested through the flow manager API only.

#### 2. Select round trip against a real broker

**Test:** Choose each option in the select entity, then publish each StateValue (varied case, surrounding whitespace) and an unknown payload with `mosquitto_pub` to the state topic.
**Expected:** Only the chosen option's actions run, once per real change; the unknown payload is logged and ignored, and the entity keeps its state.
**Why human:** Tests use `mqtt_mock`; the UI publish and the message-to-actions halves are verified separately.

#### 3. Reconfigure and option lifecycle

**Test:** Edit an option's friendly name and actions, add an option, remove one after the confirmation, and remove or rename the currently selected option.
**Expected:** StateValue is not editable; the button is renamed keeping its unique_id; a removed option's button disappears; the select shows `unknown` until the next valid payload.
**Why human:** Entity-registry and UI behavior on a running instance.

#### 4. Run modes with real delays

**Test:** Restart mode with an option that delays about 10 seconds, switch twice quickly; then the same in serial mode.
**Expected:** Restart cancels the first run silently (no Repairs issue, no error log); serial completes both in order.
**Why human:** Tests use a held service; real-time behavior is not exercised.

#### 5. Circuit breaker end to end

**Test:** Build a device whose action publishes the opposite state to its own state topic, keep defaults (5 in 10 seconds), trigger it once, then release by reconfiguring or reloading, and restart HA while paused.
**Expected:** The loop stops after 5 runs, a warning is logged, the Repairs issue appears in English and German with the release instructions, the test button still works while paused, release removes the issue, and a restart keeps the paused state.
**Why human:** The automated loop test simulates the broker; real broker delivery, rendered Repairs text and real restart persistence are not covered.

#### 6. Test buttons in the UI

**Test:** Press each test button, including for the option that is already selected.
**Expected:** Actions run locally, the entity state does not change, nothing is published to the state topic, a failing action creates the normal Repairs issue, and the buttons are listed under Configuration.
**Why human:** Frontend button entities cannot be pressed in tests.

### Gaps Summary

No gaps. All five roadmap success criteria and five plan-level truths are verified against the code with passing behavioral tests (422 main tier, 4 real-Mosquitto tier, Ruff and format clean, translations in parity). All six requirement IDs (DEV-03, DEV-04, DEV-06, DEV-07, STA-06, STA-07) are declared by plans and satisfied, with none orphaned.

The status is `human_needed` because six checks (listed above) require a real HA UI or broker. The four review warnings (WR-01 to WR-04) are all still open in 02-REVIEW-DISPOSITION.md. They are not blockers but should be triaged, ideally WR-02 (one-line template fix) and WR-04 (separate issue id) before release. WR-03 should at least be documented, and IN-06 belongs in the Phase 3 plan.

---

_Verified: 2026-09-29T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
