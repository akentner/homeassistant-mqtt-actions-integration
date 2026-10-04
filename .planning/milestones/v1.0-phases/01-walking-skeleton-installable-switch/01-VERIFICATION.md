---
phase: 01-walking-skeleton-installable-switch
verified: 2026-10-04T13:46:34Z
status: human_needed
score: 8/8 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .github/workflows/validate.yml
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-01-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-01-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-02-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-02-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-03-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-03-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-04-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-04-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-05-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-05-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-06-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-06-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/brand/icon.png
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/switch.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - hacs.json
  - pyproject.toml
  - tests/__init__.py
  - tests/broker/__init__.py
  - tests/broker/conftest.py
  - tests/broker/test_retain_semantics.py
  - tests/conftest.py
  - tests/test_config_flow.py
  - tests/test_cutover.py
  - tests/test_device_ids.py
  - tests/test_discovery.py
  - tests/test_hub_removal.py
  - tests/test_manager.py
  - tests/test_multi_instance.py
  - tests/test_native_cleanup.py
  - tests/test_native_entities.py
  - tests/test_repo_structure.py
  - tests/test_state.py
  - tests/test_toolchain.py
  - tests/test_topics.py
  - tests/test_tracer.py
  - tests/test_translations.py
covered_digest: "v2:sha256:5fe3bc97b752f641ea86e64c7f1636a542f5b374eb05afd9ae882457296acbb9"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "The Switch appears in HA through MQTT Discovery (UUID unique_id, availability, device info)"
    reason: "superseded by Phase 5: native switch and select entities replace MQTT Discovery as the default (ADR 0001, docs/adr/0001-native-entities-instead-of-mqtt-discovery.md, D-03). The unique_id stays the device UUID (DeviceSwitch._attr_unique_id = device_id). Discovery remains as the compatibility path for an instance that has not cut over (is_native False) and as an optional, disabled-by-default export. Proof of the new default: tests/test_cutover.py::test_a_legacy_install_without_peers_cuts_over_after_the_settle_time, tests/test_native_entities.py::test_native_switch_is_registered_under_the_subentry, tests/test_native_entities.py::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select. Proof the compatibility path is intact: tests/test_native_entities.py::test_an_instance_without_the_native_flag_keeps_the_legacy_path, tests/test_discovery.py::test_discovery_creates_switch_entity, tests/test_tracer.py::test_switch_end_to_end."
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T00:00:00Z"
gaps: []
deferred: []
human_verification:
  - test: "HACS client install on a real host. Add the repository as a custom repository in HACS (category Integration), download, restart, add MQTT Actions, accept defaults, try adding it a second time."
    expected: "HACS accepts and installs it, the flow shows base topic (default mqtt_actions) and instance name, a second add aborts with 'already set up', the icon is shown."
    why_human: "No automated test drives the HACS client or the frontend. Automated: repository shape (tests/test_repo_structure.py::test_manifest_has_hacs_required_keys, ::test_hacs_json_keys_allowed_and_floor, ::test_brand_icon_is_valid_png), HACS validation (9 checks green on the release run of v1.0.1-rc1, 07-PROOF.md) and the flow (tests/test_config_flow.py::test_hub_flow_creates_entry_with_instance_id, ::test_hub_flow_aborts_without_mqtt, ::test_hub_flow_single_instance). Phase 8 (UAT-01..04) names none of it. The owner recorded a pass for this on real hosts on 2026-09-29 (01-UAT.md test 1), on the build before Phase 5 and 6."
  - test: "English and German strings in the real frontend (switch profile language, open the hub flow, the Add switch device dialog, the Repairs text)."
    expected: "All labels, descriptions, error banners and the Repairs issue are translated, no raw translation keys."
    why_human: "Key and placeholder parity is automated (tests/test_translations.py::test_en_and_de_have_identical_keys, ::test_placeholders_match_between_languages, ::test_required_keys_present; 240 flattened keys each, empty symmetric difference), real rendering and wording quality is not. Phase 8 does not name it. Owner pass on the older build: 01-UAT.md test 2."
  - test: "Action editor and validation banners in the current build: add a switch device, enter an invalid action in YAML mode, then a service action with a literal device_id and submit twice."
    expected: "The action selector renders, an invalid action shows a form-level error and saves nothing, the device_id action warns on the first submit and saves on the identical second submit."
    why_human: "Flow level is automated (tests/test_config_flow.py::test_switch_flow_schema_serializes_action_selector, ::test_switch_flow_rejects_invalid_actions, ::test_switch_flow_device_id_warns_then_saves_on_resubmit, ::test_switch_flow_entity_targets_do_not_warn, ::test_switch_reconfigure_applies_validation_and_warning, tests/test_device_ids.py), the frontend rendering of the ActionSelector and the base-error banner is not. Phase 8 does not name it. Owner pass on the older build: 01-UAT.md test 3."
  - test: "Repairs dialog of a failing action: call a non-existent service in an action, trigger it, open Settings > Repairs."
    expected: "One Repairs issue shows device, trigger, time and error text, and it clears after the next successful run."
    why_human: "Issue creation, update in place, dismissal, truncation and clearing are automated (tests/test_manager.py::test_issue_created_when_action_fails, ::test_issue_updated_in_place_on_repeated_failure, ::test_issue_cleared_after_next_success, ::test_issue_dismissed_stays_dismissed_while_failing, ::test_issue_error_text_is_truncated, ::test_issue_for_invalid_stored_actions_at_setup; tests/test_runner_modes.py::test_dropped_run_does_not_clear_failure_issue). Rendering in the real frontend is not. The owner's 2026-09-29 check was API-level only (01-UAT.md test 5: 'not visually'). Phase 8 does not name it."
  - test: "Retained-versus-live chain on the current build with a real HA core MQTT client and a real retaining broker: toggle the entity in the UI, restart HA fully, reconnect the broker."
    expected: "One action run per real change, none for repeated identical values, none after a full HA restart or broker reconnect until a changed value is published, nothing removed on unload."
    why_human: "The decision logic and the broker semantics are automated: tests/state tests (tests/test_state.py), tests/test_manager.py::test_retain_replay_sets_baseline_without_actions, ::test_retain_replay_after_reconnect_runs_nothing, ::test_startup_flag_runs_retained_state_once, ::test_startup_flag_not_reapplied_on_replay, ::test_baseline_persisted_across_reload, ::test_reload_keeps_single_subscription, ::test_unload_publishes_offline_and_never_clears_discovery, tests/test_native_entities.py::test_the_echo_runs_the_actions_once, and against a real Mosquitto tests/broker/test_retain_semantics.py::test_replay_on_subscribe_has_retain_true, ::test_live_forward_has_retain_false, ::test_resubscribe_replays_last_value_with_retain_true. No automated test joins the HA core client with a real retaining broker, and Phase 8 (UAT-02 restarts for duplicates, UAT-03 one command on two instances) does not check that a restart or reconnect runs no actions. The owner's 2026-09-29 EMQX run covered edges, repeated values and a reload, and explicitly left UI toggle, full restart and broker reconnect open (01-UAT.md test 4)."
  - test: "Core version of the second real host (hassio-n2plus, called Backup): read it in Settings > About."
    expected: "Core 2026.9.0 or newer, or the floor is reassessed."
    why_human: "Not a code truth. The floor itself is tested (tests/test_toolchain.py::test_home_assistant_floor, ::test_python_floor, tests/test_repo_structure.py::test_hacs_json_keys_allowed_and_floor). The host that carries it was never read: Nextgen is 2026.9.4 (read), Backup is only inferred (01-UAT.md test 9), lxc-haos-104 was dropped by the owner. Phase 8 does not name it. Informational, no code consequence."
---

# Phase 1: Walking Skeleton - Installable Switch Verification Report

**Phase Goal:** As a Home Assistant user, I want to create a Switch device whose MQTT state changes run my configured actions, so that I need no YAML automation. (Mode: mvp)
**Verified:** 2026-10-04T13:46:34Z
**Status:** human_needed
**Re-verification:** Yes. Regenerated for plan 07-05 (QLT-01) against the final code at frozen sha `81db888c5e49389ea7dc27626100f6e090535e61` (HEAD `ad98080` differs from it only by the Phase 7 ledger `07-PROOF.md`; code, tests, workflows and manifest are byte-identical). The previous report (2026-09-29, `status: human_needed` in its body, `passed` in its frontmatter, against local head `950d30c`) is replaced; history stays in Git.

The story format is valid (`As a ..., I want to ..., so that ... .`), so MVP-mode verification applies.

## What changed since the previous report

Phases 2 to 6 changed the code Phase 1 rests on. Every Phase 1 truth was re-judged on the current code, not carried over.

- Phase 5 (ADR 0001, D-03): native switch and select entities replace MQTT Discovery as the default. Discovery is now the compatibility path of an instance that has not cut over, plus an optional export. One Phase 1 truth is recorded as superseded (below).
- Phase 4 (D-11): hub removal keeps the devices on the broker by default and deletes them only on the hub option. This is not a Phase 1 success criterion (DSC-02 is about explicit device delete), so it is not an override, but it changes the previous human item 6 (see Human Verification).
- Phase 7: the CI is split into four tiers on a pinned runner, `release.yml` exists, the flaky delete test was fixed.

## User Flow Coverage (MVP mode)

| Story step | Expected | Evidence in codebase | Status |
| --- | --- | --- | --- |
| Install and set up | Installs via HACS, hub added once, MQTT required | `hacs.json`, `manifest.json` (`dependencies: [mqtt]`, `single_config_entry`, `requirements: []`), `config_flow.py:93` aborts `mqtt_required`, `config_flow.py:114` uuid4 instance id; `test_hub_flow_*` | VERIFIED (HACS client itself: human) |
| Create a Switch device with actions | Name + onChangeToOn/Off via ActionSelector, invalid rejected, device_id warned | `config_flow.py:210-220` (`async_validate_actions`, `invalid_actions`, `device_id_warning`), `config_flow.py:361-362` `selector.ActionSelector()`; `test_switch_flow_*` | VERIFIED (frontend rendering: human) |
| MQTT state change runs actions locally | Entity (native by default), UI toggle or external publish triggers actions on real edges only | `manager._on_message` -> `StateTracker.handle` -> `_run_trigger`; `switch.py::DeviceSwitch`; `test_switch_end_to_end`, `test_edge_*`, `test_the_echo_runs_the_actions_once` | VERIFIED |
| So that no YAML automation is needed | Whole path works without YAML, failures visible | Config Flow only (`CONFIG_SCHEMA = cv.config_entry_only_config_schema`), `runner.py` log plus Repairs issue, `test_issue_*` | VERIFIED |

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria plus PLAN must-haves)

SC4 is split into its Discovery clause (superseded) and its behavior clause so that the supersession is exact and nothing else in SC4 rides on the override.

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| SC1 | HACS install, one-time Config Flow requiring MQTT with persistent instance ID, UI strings in EN and DE | VERIFIED | `manifest.json`: domain `mqtt_actions` = folder, `dependencies:["mqtt"]`, `single_config_entry:true`, `requirements:[]`; `hacs.json` floor 2026.9.0; `brand/icon.png` 256x256 RGBA (+ `icon@2x.png` 512x512); hub flow aborts `mqtt_required`, stores `str(uuid.uuid4())` as `CONF_INSTANCE_ID`. Passing: `test_hub_flow_creates_entry_with_instance_id`, `test_hub_flow_aborts_without_mqtt`, `test_hub_flow_single_instance`, `test_hub_flow_rejects_invalid_base_topic`, `tests/test_translations.py` (en/de 240 keys each, no diff, placeholders equal). Real HACS client and rendering: human items 1 and 2. |
| SC2 | Every push runs hassfest, HACS validation, Ruff and pytest in CI, and the pipeline passes | VERIFIED | `ci.yml` (Ruff, Unit, Broker with Mosquitto, Multi-instance tiers) and `validate.yml` (hassfest, HACS) trigger on `push` with only `tags-ignore: v*.*.*` (tags run once through `release.yml`), plus `pull_request`, dispatch and call; SHA-pinned actions, `permissions: {}`. Guards: `tests/test_repo_structure.py::test_push_trigger_has_no_branch_filter`, `::test_all_action_refs_are_pinned_by_sha`, `::test_workflows_have_empty_permissions`, `::test_ci_has_one_job_per_tier`, `::test_tiers_partition_the_suite`, `::test_hacs_action_has_category_and_no_ignore`. Green runs (07-PROOF.md, ubuntu-24.04 image 20260927.320.1): three consecutive CI dispatch runs 37205596675, 37205721595, 37205851615 (each 1308 unit + 17 broker + 165 multi-instance), Validate run 37205956233 (hassfest, HACS `All (9) checks passed`), release run 37206309249 (8 of 8 jobs success). Three local full-suite runs: 1490 passed each, Ruff clean. Cited, not re-run. |
| SC3 | Create a Switch with name and action lists via the action selector; invalid actions rejected on input; actions targeting `device_id`s show a warning | VERIFIED | `config_flow.py:210-220` validates through `async_validate_actions` (cv.SCRIPT_SCHEMA plus deep validation, `actions.py:21-29`) and returns `base: invalid_actions`; `find_device_ids` plus a fingerprint gives `device_id_warning` on the first submit and saves on the identical resubmit. Passing: `test_switch_flow_creates_subentry`, `test_switch_flow_schema_serializes_action_selector`, `test_switch_flow_rejects_invalid_actions`, `test_switch_flow_truncates_long_validation_errors`, `test_switch_flow_device_id_warns_then_saves_on_resubmit`, `test_switch_flow_entity_targets_do_not_warn`, `test_switch_reconfigure_applies_validation_and_warning`, `tests/test_device_ids.py`. |
| SC4a | The Switch appears in HA through MQTT Discovery (UUID `unique_id`, availability, device info) | PASSED (override): superseded by Phase 5 | Phase 5 replaced Discovery as the default with native entities owned by this integration (ADR 0001 D-03). The UUID `unique_id` survives (`switch.py`: `_attr_unique_id = device_id`), the entity sits under its subentry on the integration page. New default proven by `tests/test_cutover.py::test_a_legacy_install_without_peers_cuts_over_after_the_settle_time` (a fresh instance without legacy peers goes native by itself), `tests/test_native_entities.py::test_native_switch_is_registered_under_the_subentry`, `::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select`. The old clause is still true on the compatibility path (`manager.is_native` False before the cutover; `discovery.py::build_discovery` unchanged: UUID `unique_id`, availability list, device block, retained QoS 1): `tests/test_native_entities.py::test_an_instance_without_the_native_flag_keeps_the_legacy_path`, `tests/test_discovery.py::test_build_discovery_switch_payload_unchanged`, `::test_discovery_creates_switch_entity`, `::test_discovery_availability_toggles_entity`, `tests/test_tracer.py::test_switch_end_to_end` (all pass). Override recorded in frontmatter (D-03). |
| SC4b | Toggling the entity in the UI or publishing to its retained state topic runs the matching actions locally on each real change; a failing action is visible in the log and as a Repairs issue instead of being swallowed | VERIFIED | Toggle publishes retained at QoS 1 and the broker echo is the single trigger source: `DeviceSwitch.async_turn_on/off` -> `manager.async_send_state`; legacy path `tests/test_discovery.py::test_discovery_toggle_publishes_retained_on_and_off`, native path `tests/test_native_entities.py::test_turn_on_publishes_the_exact_value_retained_at_qos_1`, `::test_the_echo_runs_the_actions_once`. Edges: `tests/test_manager.py::test_edge_live_on_runs_on_actions_once`, `::test_edge_off_runs_off_actions`, `::test_edge_duplicate_live_value_is_ignored`, `::test_edge_payload_case_insensitive`, `::test_live_message_without_baseline_acts`, `::test_actions_run_serially_in_order`. Failure: `runner._async_run` logs the exception and creates/updates one `ir.async_create_issue` (`runner.py:239-263`), cleared only by a completed latest run; `test_issue_created_when_action_fails`, `test_issue_updated_in_place_on_repeated_failure`, `test_issue_cleared_after_next_success`, `test_issue_and_log_do_not_leak_action_data`. |
| SC5 | After restart, reload or reconnect: clean start even without MQTT, retained state only sets the baseline (unless run-on-startup), only real changes trigger, the entity stays until the user explicitly deletes the device | VERIFIED | `__init__.py`: `ConfigEntryNotReady` when `async_wait_ready()` is False, failed start releases subscriptions; `state.decide`: retained is baseline only, `startup_pending and run_on_startup` is the opt-in; Store-backed baseline; `Manager.async_stop` publishes offline only and never clears discovery or state; clears happen only in `_async_remove_device` and hub removal with the delete option. Passing behavioral tests: `test_setup_retry_without_mqtt`, `test_retain_replay_sets_baseline_without_actions`, `test_retain_replay_after_reconnect_runs_nothing`, `test_startup_flag_runs_retained_state_once`, `test_startup_flag_not_reapplied_on_replay`, `test_startup_flag_applies_again_after_reload`, `test_new_device_ignores_startup_flag`, `test_baseline_persisted_across_reload`, `test_reload_keeps_single_subscription`, `test_reconnect_republishes_availability_and_discovery`, `test_unload_publishes_offline_and_never_clears_discovery`, `test_unload_then_setup_republishes_without_clearing`, `test_delete_clears_discovery_then_unsubscribes_then_config_tombstone_then_state`, `test_delete_device_own_subscription_never_sees_state_clear`, `test_failed_start_releases_subscriptions_and_retries_cleanly`, `test_malformed_store_last_acted_is_dropped_and_setup_succeeds` (all in `tests/test_manager.py`); native path `tests/test_native_cleanup.py::test_deleting_a_native_device_clears_everything_and_removes_its_entities`, `tests/test_native_replay.py`, `tests/test_native_start.py::test_a_second_start_runs_no_pass`; real Mosquitto `tests/broker/test_retain_semantics.py::test_replay_on_subscribe_has_retain_true`, `::test_live_forward_has_retain_false`. |
| P1 | Only `mqtt_gateway.py` imports the mqtt component, callbacks are `@callback`, the raw broker payload never reaches Script variables | VERIFIED | `tests/test_tracer.py::test_only_gateway_imports_mqtt_component` (AST) passes against the current 27-module package; `mqtt_gateway.py` `_forward` functions are `@callback`; `switch.py` imports only the switch platform. |
| P2 | Zero runtime dependencies, toolchain pinned | VERIFIED | `manifest.json` `requirements: []`; `tests/test_toolchain.py` (4 tests) passes; `uv run --locked` is used by CI and by every run above. |

**Score:** 8/8 truths verified (7 VERIFIED plus 1 PASSED (override), 0 present-but-behavior-unverified). Every behavior-dependent truth (retain/baseline, cleanup on unload, delete ordering, single subscription after reload, failed-start teardown) has a named test that passes on the final code.

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `custom_components/mqtt_actions/{__init__,manager,runner,state,switch,entities,discovery,mqtt_gateway,config_flow,actions,topics,model,const}.py` | Working integration | VERIFIED | Substantive and wired (`__init__` -> `Manager`, `MqttGateway`, platforms; `manager` -> gateway, discovery publisher, runner, tracker; `switch.py` reads the running manager; `config_flow` -> `actions`, `topics`). Phase 1 modules are grown by later phases, not replaced. |
| `translations/en.json`, `de.json` | EN/DE strings | VERIFIED | 240 flattened keys each, empty symmetric difference. |
| `manifest.json`, `hacs.json`, `brand/icon.png`, `LICENSE` | HACS metadata | VERIFIED | Present, `test_manifest_has_hacs_required_keys`, `test_domain_matches_folder_name`, `test_brand_icon_is_valid_png`, `test_license_is_mit_with_holder` pass. |
| `.github/workflows/ci.yml`, `validate.yml` (and `release.yml`, `dependabot.yml`) | CI | VERIFIED | SHA-pinned, empty permissions, four CI tiers. |
| `README.md` | Install, contract, limitations, trust model | VERIFIED | `test_readme_documents_install_limits_and_trust` passes. |
| `tests/` | Coverage of the above | VERIFIED | Targeted run below plus the ledger's three full runs (1490 passed). |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| subentry create/update | `Manager.async_reconcile` | `entry.add_update_listener(_async_entry_updated)` | WIRED | `__init__.py`, registered before `async_start`. |
| `manager._on_message` | `StateTracker.handle` / `runner` | `_run_trigger` on `decision.act` | WIRED | `manager.py:2285-2305`. |
| `DeviceSwitch.async_turn_on/off` | state topic | `manager.async_send_state` | WIRED | `switch.py`. |
| platforms | running manager | `async_forward_entry_setups` after `async_start` | WIRED | `__init__.py:45-55`. |
| remove path | clear before unsubscribe | `_async_remove_device` | WIRED | Order tested. |
| connection status | republish | `async_subscribe_connection_status` -> `_on_connection_status` | WIRED | `test_reconnect_republishes_availability_and_discovery`. |
| `config_flow` | `actions.async_validate_actions`, `find_device_ids` | direct | WIRED | |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
| --- | --- | --- | --- | --- |
| `runner._async_run` | Script sequence | subentry action list -> `async_validate_actions` -> `Script` | Yes | FLOWING |
| `DeviceSwitch.is_on` | `device.value` | accepted StateValue of the state topic (`_record_value`) | Yes | FLOWING |
| manager baseline | `last_acted` | Store load plus live and retained messages | Yes | FLOWING |
| Repairs issue | error text | exception string, capped | Yes | FLOWING |

### Behavioral Spot-Checks

Run at HEAD `ad98080` (code identical to the frozen sha). The full suite was not re-run: the ledger holds three local full runs (1490 passed each) and three CI dispatch runs on the same code.

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 1 core tiers incl. real Mosquitto | `uv run --locked pytest -q -p no:cacheprovider tests/test_state.py tests/test_topics.py tests/test_config_flow.py tests/test_translations.py tests/test_repo_structure.py tests/test_device_ids.py tests/test_discovery.py tests/test_manager.py tests/test_toolchain.py tests/test_tracer.py tests/test_native_entities.py tests/test_native_replay.py tests/test_native_start.py tests/test_native_cleanup.py tests/test_cutover.py tests/broker` | 453 passed in 51.04s, no skips | PASS |
| Multi-instance, hub removal, roster | `uv run --locked pytest -q -p no:cacheprovider tests/test_multi_instance.py tests/test_hub_removal.py tests/test_multi_instance_ops.py tests/test_hub_entities.py` | 93 passed in 8.81s | PASS |
| en/de key parity | flatten both files, symmetric difference | 240 / 240 keys, empty difference | PASS |
| Debt markers in code, tests, workflows | `grep -n -E "TBD\|FIXME\|XXX" -r custom_components tests .github` | no output | PASS |

### Probe Execution

Step 7c: SKIPPED (no `probe-*.sh` declared or present).

### Requirements Coverage

All 15 IDs of Phase 1 are claimed by a PLAN `requirements:` field (01-01 FND-02; 01-02 FND-01,03, DEV-01,02, STA-01,02, DSC-01; 01-03 FND-03,04, DEV-01,02,05; 01-04 STA-02,04,05, DEV-08; 01-05 FND-05, STA-01, DSC-01,02; 01-06 FND-01,02). No orphans.

| Requirement | Status | Evidence |
| --- | --- | --- |
| FND-01 | SATISFIED (real HACS client: human item 1) | `hacs.json`, manifest, icon; HACS 9/9 on the ledger runs |
| FND-02 | SATISFIED | SC2 evidence |
| FND-03 | SATISFIED | hub flow tests |
| FND-04 | SATISFIED (rendering: human item 2) | `tests/test_translations.py` |
| FND-05 | SATISFIED | `test_setup_retry_without_mqtt`, `test_reconnect_republishes_availability_and_discovery` |
| DEV-01, DEV-02 | SATISFIED | `test_switch_flow_creates_subentry`, `test_switch_flow_schema_serializes_action_selector` |
| DEV-05 | SATISFIED | `test_switch_flow_rejects_invalid_actions`, `test_switch_flow_device_id_warns_then_saves_on_resubmit` |
| DEV-08 | SATISFIED (Repairs rendering: human item 4) | `test_issue_*` |
| STA-01 | SATISFIED | `test_discovery_toggle_publishes_retained_on_and_off`, `test_turn_on_publishes_the_exact_value_retained_at_qos_1` |
| STA-02 | SATISFIED | `test_edge_*`, `test_the_echo_runs_the_actions_once` |
| STA-04 | SATISFIED | retain and startup tests, `tests/broker/test_retain_semantics.py` |
| STA-05 | SATISFIED | `test_baseline_persisted_across_reload`, `test_edge_duplicate_live_value_is_ignored` |
| DSC-01 | SATISFIED on the compatibility path, superseded as default by Phase 5 (override above) | discovery tests, native tests |
| DSC-02 | SATISFIED | `test_unload_publishes_offline_and_never_clears_discovery`, `test_delete_clears_discovery_then_unsubscribes_then_config_tombstone_then_state`, `test_deleting_a_native_device_clears_everything_and_removes_its_entities` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| code, tests, workflows | - | TBD/FIXME/XXX | none | grep clean |

The open review findings of the previous report (WR-03, WR-05, WR-06, WR-07, IN-01..06) were not re-litigated. None of them falsified a success criterion then and none is a Phase 1 truth now; later phases touched the same code (hub removal in Phase 4, breaker and run modes in Phase 2).

### Human Verification Required

#### Covered by the automated tiers (D-04), no human step left

| Previous human item | Automated coverage on the final code |
| --- | --- |
| Failing action visibility (logic) | `tests/test_manager.py::test_issue_*` (see SC4b). The rendering half stays human (item 4 below). |
| Delete a device on a real broker | `tests/test_manager.py::test_delete_clears_discovery_then_unsubscribes_then_config_tombstone_then_state`, `::test_delete_device_stops_actions_and_cleans_state`, `::test_delete_device_keeps_id_for_orphan_cleanup_when_mqtt_fails`, `::test_orphan_discovery_is_cleared_at_start`, `tests/test_native_cleanup.py::test_deleting_a_native_device_clears_everything_and_removes_its_entities`, `tests/test_multi_instance.py::test_delete_removes_the_device_everywhere`, `::test_owner_delete_removes_the_mirror_everywhere`; the broker semantics of the retained clear against a real Mosquitto: `tests/broker/test_retain_semantics.py::test_retained_clear_is_a_live_empty_message`. Owner-recorded real EMQX pass on the older build: 01-UAT.md test 6. |
| Remove the hub on a real broker | `tests/test_hub_removal.py::test_remove_with_delete_clears_everywhere`, `::test_remove_with_default_keeps_everything_retained`, `::test_keep_leaves_the_offline_availability`, `::test_both_modes_remove_store_and_every_issue_prefix`, `::test_delete_mode_survives_unavailable_mqtt`, `tests/test_manager.py::test_remove_entry_clears_all_owned_topics`, `tests/test_multi_instance.py::test_hub_removal_delete_clears_everywhere_for_followers`, `::test_hub_removal_keep_leaves_orphans_that_followers_keep`, `tests/test_native_cleanup.py::test_hub_removal_clears_the_export_topics_too`. Note: since Phase 4 (D-11) the default of hub removal keeps the broker topics (so the previous expectation "nothing remains on the broker" holds with the hub's delete option, not by default). This is a deliberate later decision, not a Phase 1 success criterion, and it is not an override. |
| Lifecycle fixes WR-01/02/04 | `tests/test_manager.py::test_reload_keeps_single_subscription`, `::test_failed_start_releases_subscriptions_and_retries_cleanly`, `::test_setup_retry_without_mqtt`, `::test_malformed_store_last_acted_is_dropped_and_setup_succeeds`, `::test_reconcile_after_stop_does_not_revive_manager`, `::test_delete_device_own_subscription_never_sees_state_clear` (50 of 50 under CPU stress, 07-PROOF.md). The fixes were pushed and merged (01-UAT.md test 7 and 8). |
| Push and confirm CI and Validate | `07-PROOF.md`: three CI runs, Validate, release run, all success on ubuntu-24.04. |
| Real retained-versus-live chain | Mostly covered, residual listed as item 5 below. |

#### Still human (no automated test, not named by Phase 8, so not turned into passed)

See the `human_verification` list in the frontmatter (6 items):

1. HACS client install, flow and icon on a real host.
2. EN and DE rendering in the real frontend.
3. Action editor and validation banners in the current build.
4. Repairs dialog rendering for a failing action.
5. HA core client with a real retaining broker: UI toggle, full HA restart, broker reconnect run no extra actions.
6. Core version of the second real host (Backup).

The owner recorded a pass for items 1 to 4 and part of 5 and 6 on real hosts on 2026-09-29 (`01-UAT.md`, status complete), on the build before Phases 5 and 6. That is real evidence, but of an older build, and Phase 8 (UAT-01..04) does not repeat it. It is the owner's call whether to accept these as an override under the owner's name or to run them again. Phase 8's four checks (v0.1.0 peer next to a native instance, no `_2` duplicates after two restarts, one command executed once on two real instances, the discovery export) cover real instances for the native path and touch item 5 only partially.

### Gaps Summary

No gaps. Every roadmap success criterion is backed by code and by named passing tests on the final code, with one intended supersession (SC4a, Discovery as the default mechanism, replaced by native entities in Phase 5 and recorded as an override under D-03). The status is `human_needed` solely because six real-client checks (HACS client, frontend rendering, Repairs dialog, real HA-core-plus-broker restart and reconnect, one host version) have no automated test and are not named by Phase 8; they are returned to the owner instead of being passed by assumption.

---

_Verified: 2026-10-04T13:46:34Z_
_Verifier: Claude (gsd-verifier)_
