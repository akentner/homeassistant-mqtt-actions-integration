---
phase: 04-operations-recovery-and-release
verified: 2026-10-04T13:50:00Z
status: passed
score: 5/5 must-haves verified
covered_files:
  - .github/dependabot.yml
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - .github/workflows/validate.yml
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-01-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-01-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-02-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-02-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-03-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-03-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-04-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-04-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-05-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-05-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-06-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-06-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-07-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-07-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-08-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-08-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-09-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-09-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-10-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-10-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-11-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-11-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-12-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-12-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-13-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-13-SUMMARY.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-14-PLAN.md
  - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-14-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/brand/icon.png
  - custom_components/mqtt_actions/breaker.py
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/diagnostics.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/modes.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/portability.py
  - custom_components/mqtt_actions/presence.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/retrigger.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/select.py
  - custom_components/mqtt_actions/sensor.py
  - custom_components/mqtt_actions/services.py
  - custom_components/mqtt_actions/services.yaml
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/switch.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/takeover.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/trust.py
  - docs/adr/0001-native-entities-instead-of-mqtt-discovery.md
  - docs/broker-acl.md
  - docs/diagnostics.md
  - docs/operations.md
  - docs/troubleshooting.md
  - pyproject.toml
  - renovate.json
  - tests/broker/conftest.py
  - tests/broker/test_acl.py
  - tests/broker/test_retain_semantics.py
  - tests/conftest.py
  - tests/fake_broker.py
  - tests/test_companions.py
  - tests/test_cutover.py
  - tests/test_cutover_instances.py
  - tests/test_diagnostics.py
  - tests/test_discovery_export.py
  - tests/test_docs.py
  - tests/test_hub_entities.py
  - tests/test_modes.py
  - tests/test_multi_instance.py
  - tests/test_multi_instance_ops.py
  - tests/test_native_entities.py
  - tests/test_native_start.py
  - tests/test_portability.py
  - tests/test_presence.py
  - tests/test_repairs_flow.py
  - tests/test_repo_structure.py
  - tests/test_retrigger.py
  - tests/test_runner_modes.py
  - tests/test_services.py
  - tests/test_sync_follower.py
  - tests/test_takeover.py
  - tests/test_toolchain.py
  - tests/test_translations.py
  - uv.lock
covered_digest: "v2:sha256:610a1c58597b30fe948706812c0412ffb3bde712871126d48619aaebcf50ccd0"
behavior_unverified: 0
overrides_applied: 2
overrides:
  - must_have: "User can run a manual resync that republishes config and discovery of all owned devices (ROADMAP SC3, DSC-04: discovery clause)"
    reason: "superseded by Phase 5: native switch and select entities replaced MQTT Discovery as the default (ADR 0001, docs/adr/0001-native-entities-instead-of-mqtt-discovery.md, decisions D-03 and D-11). A native device publishes no Discovery on resync; Discovery is republished only on the legacy compatibility path and as the optional export. Test proving the new behavior: tests/test_discovery_export.py::test_a_native_device_publishes_the_export_when_enabled and ::test_the_export_is_off_by_default (publish path Manager.async_publish_discovery, manager.py:2255-2282, called by _async_publish_owned from async_resync); tests/test_native_entities.py::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select. The config documents, availability and heartbeat are still republished (tests/test_hub_entities.py::test_resync_button_republishes_in_the_phase_3_order and tests/test_services.py::test_resync_service_republishes_in_the_phase_3_order, both on the legacy path the fixtures pin)."
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T13:50:00Z"
  - must_have: "Per instance and device mode selects live on a separate companion device next to the core-MQTT device (ROADMAP SC4 evidence, Phase 4 D-13 companion workaround, UAT test 4)"
    reason: "superseded by Phase 5: native entities belong to this integration, so the companion device is merged into the device and the switch or select, the test buttons and the mode select share one device (owned under its subentry, mirror directly under the entry), ADR 0001 'Cutover design'. The mode behavior itself (run, observe, disabled, most restrictive wins) is unchanged and tested. Tests proving the new layout: tests/test_native_entities.py::test_the_mode_select_shares_the_device_of_the_native_entities, ::test_a_marked_mirror_is_a_native_entity_directly_under_the_entry, tests/test_takeover.py::test_full_takeover_sequence_keeps_identity, ::test_a_mirror_moves_directly_under_the_entry. The companion path remains for legacy instances and is still tested (tests/test_companions.py, tests/test_modes.py::test_owned_device_has_a_companion_device_under_its_subentry)."
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T13:50:00Z"
re_verification:
  previous_status: passed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification: []
---

# Phase 4: Operations, Recovery and Release Verification Report

**Phase Goal:** As a user running several HA instances, I want to re-trigger actions, see who is connected and recover devices, so that I can operate the setup with confidence.
**Verified:** 2026-10-04 (frozen sha `81db888c5e49389ea7dc27626100f6e090535e61`; HEAD `ad98080` adds only the Phase 7 ledger `07-PROOF.md`, which no covered file includes)
**Status:** passed
**Re-verification:** Yes - QLT-01 re-verification of the archived phase against the final v1.0.1 code (plan 07-05, D-01 to D-04). Output path overridden to the archived directory (D-02).

## Summary

The phase was re-judged against the code at the frozen sha, which contains Phase 5 (native entities), Phase 6 (residual fixes) and the Phase 7 test and CI changes. No SUMMARY claim was taken as evidence: every truth below was re-read in code and tied to tests that run today.

- No Phase 4 truth regressed. Two parts of the evidence base were replaced on purpose by Phase 5 and are recorded as `superseded by Phase 5` overrides under D-03 (the Discovery clause of the resync criterion and the companion-device layout of the mode selects). Everything else is unchanged behavior.
- Code since the previous verification (`19ae5d6`): `custom_components` grew by Phase 5 and 6 (`switch.py`, `takeover.py`, native paths in `manager.py`, `button.py`, `select.py`, `presence.py`, `sync.py`). The Phase 4 modules `retrigger.py`, `portability.py`, `services.py`, `diagnostics.py`, `modes.py`, `repairs.py`, `sensor.py`, `runner.py` were not touched by Phase 5; their tests pass on the final code.
- Test evidence: the Phase 7 ledger `.planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md` records three local full-suite runs (1490 passed each, unit plus broker plus multi-instance, Mosquitto 2.1.2), three CI dispatch runs on ubuntu-24.04 (1308 unit, 17 broker, 165 multi-instance, Mosquitto 2.0.18), a green Validate run (hassfest, HACS `All (9) checks passed`) and the green release run on `v1.0.1-rc1` (8 jobs, prerelease, cleaned up). The code between the proven head `0f9ad70` and the frozen sha differs only by the rc manifest bump and its byte-identical reset: `git diff --stat 0f9ad70 81db888 -- custom_components tests .github pyproject.toml uv.lock` is empty (verified).
- Verifier-run targeted checks at the frozen sha: 683 passed in 48 s over `tests/test_retrigger.py tests/test_presence.py tests/test_portability.py tests/test_services.py tests/test_modes.py tests/test_runner_modes.py tests/test_companions.py tests/test_diagnostics.py tests/test_repairs_flow.py tests/test_translations.py tests/test_docs.py tests/test_multi_instance_ops.py tests/test_multi_instance.py tests/test_sync_follower.py tests/test_hub_entities.py tests/test_takeover.py tests/test_repo_structure.py tests/test_toolchain.py tests/test_native_entities.py`; and 88 passed in 26 s over `tests/broker tests/test_cutover_instances.py tests/test_discovery_export.py tests/test_native_start.py tests/test_cutover.py` with `MQTT_ACTIONS_REQUIRE_BROKER=1` (real Mosquitto). The full suite was not re-run (allowed by the plan; cited from the ledger).

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Re-trigger service (non-retained, `request_id` dedupe, rate-limited); the caller sees which instances acknowledged and executed | VERIFIED | `retrigger.py` (not changed by Phase 5): request published `retain=False` (line 295), receiver drops retained requests (line 369), dedupe via `self._seen` (383-385), per-device receiver rate limit (389), caller rate limit `REASON_RATE_LIMITED` (259), acks non-retained to the requester (472), run path `test=True` (450) so tracker, baseline and breaker stay untouched. Service `retrigger` registered admin only with `SupportsResponse.OPTIONAL` (`services.py:328-330`). Tests passing today: `tests/test_retrigger.py::test_retained_requests_are_ignored`, `::test_stale_and_future_requests_are_dropped`, `::test_duplicate_request_ids_run_once`, `::test_receiver_rate_limit_per_device`, `::test_statuses`, `::test_caller_rate_limit_and_state_selection`; multi-instance tier `tests/test_multi_instance_ops.py::test_retrigger_runs_approved_instances_and_touches_no_state`, `::test_retrigger_returns_before_the_window_when_everyone_answered`, `::test_roster_offline_and_silent_instances_are_no_answer`, `::test_retrigger_honors_modes_and_breaker_in_the_multi_instance_tier`, `::test_unapproved_mirror_answers_not_approved_and_runs_nothing`, `::test_acknowledgements_per_request_are_capped`; real broker tier `tests/broker/test_acl.py::test_retrigger_topic_is_a_live_trigger_for_home_assistant_users_only`, `::test_ack_topic_is_readable_only_by_its_instance`, `::test_any_instance_may_answer_a_requester`. |
| 2 | Roster with presence heartbeat; a duplicate instance id is detected and reported | VERIFIED | `presence.py` heartbeat (non-retained, 30 s) and 90 s offline rule; `RosterSensor` (`sensor.py:19`, added by `async_setup_entry`, line 59); duplicate detection `presence.py:418/433` -> `Manager.on_duplicate_id_changed` (`manager.py:1548`) -> fixable Repairs issue -> `repairs.DuplicateIdRepairFlow` (`repairs.py:96`, dispatched at 168). Phase 5 added a native-capability key to the heartbeat; the rows and the duplicate rule are covered: `tests/test_presence.py::test_heartbeat_is_published_non_retained_with_qos_0`, `::test_heartbeat_tick_publishes_every_30_seconds`, `::test_duplicate_detection_needs_two_foreign_session_heartbeats`, `::test_duplicate_clears_after_90_seconds_of_silence`, `::test_a_capability_claim_never_replaces_a_fresh_legacy_row`; `tests/test_hub_entities.py::test_hub_device_and_roster_sensor_exist`, `::test_roster_sensor_follows_the_heartbeats`; `tests/test_multi_instance_ops.py::test_instances_see_each_other_through_heartbeats`, `::test_roster_marks_a_peer_offline_after_90_seconds`, `::test_duplicate_detection_changes_nothing_by_itself`, `::test_duplicate_id_fix_leaves_the_originals_topics_byte_identical`; `tests/test_repairs_flow.py::test_duplicate_issue_is_created_once_and_cleared`, `::test_duplicate_flow_form_and_confirmation`. |
| 3 | Manual resync that republishes config and discovery of all owned devices; export to JSON and import; transfer ownership of a device or adopt an orphaned one | VERIFIED; the "and discovery of all owned devices" clause is PASSED (override, superseded by Phase 5) | Resync: `Manager.async_resync` (`manager.py:1188`) -> `_async_republish` -> documents, then discovery, then `online`, then heartbeat; throttled; button `ResyncButton` (`button.py:27`, added at 128) and service `resync` share it. Tests: `tests/test_hub_entities.py::test_resync_button_republishes_in_the_phase_3_order`, `::test_resync_is_throttled`, `tests/test_services.py::test_resync_service_republishes_in_the_phase_3_order`, `::test_resync_service_is_admin_only`, `::test_resync_service_throttled_raises_a_translated_error`, `tests/test_native_start.py::test_a_failed_retained_clear_after_the_move_keeps_the_device_native_and_is_retried`. Discovery clause: on the default (native) path a resync no longer republishes Discovery, see the override (ADR 0001, D-03/D-11) and `tests/test_discovery_export.py::test_the_export_is_off_by_default`. Export/import: `portability.py` (private file `<config>/mqtt_actions/`, 0700/0600, never `www`), services `export_devices`, `import_devices`; `tests/test_portability.py::test_write_export_creates_a_private_file`, `::test_prepare_import_assigns_new_ids_and_owner`, `::test_parse_and_prepare_reject_hostile_input`, `::test_denied_services_are_rejected`, `::test_read_import_refuses_a_symlinked_directory`. Transfer or adopt: SC3 says "transfer ... or adopt"; `Manager.async_adopt` (`manager.py:1434`), service `adopt_device` (`services.py:310`), `TransferredRepairFlow` for the old owner (`repairs.py:126`); `tests/test_multi_instance_ops.py::test_adoption_end_to_end`, `::test_adoption_clears_nothing_on_the_broker`, `::test_adoption_needs_the_owner_offline_or_force`, `::test_old_owner_recognizes_the_transfer_after_a_restart`, `::test_transferred_away_device_is_not_republished`; `tests/test_repairs_flow.py::test_release_flow_follows_the_adopter`; Phase 5 adoption rules in `tests/test_native_start.py::test_adopting_a_native_mirror_keeps_the_device_native_on_a_legacy_instance`. Scope note (unchanged since the previous report): D-09 of 04-CONTEXT.md implements adoption (with `force`) and defers an active hand-off; the criterion's "or" is satisfied, so no override is needed. |
| 4 | Per instance and device mode (run / observe / disabled); diagnostics download with sensitive data redacted | VERIFIED; the companion-device layout is PASSED (override, superseded by Phase 5) | `modes.py`, `Manager.effective_mode` (`manager.py:625`, `most_restrictive`), `select.py`, `diagnostics.py` (allow-list plus `async_redact_data`, hook `async_get_config_entry_diagnostics` at line 98). Tests: `tests/test_modes.py::test_observe_logs_and_runs_nothing_but_tracks_the_baseline`, `::test_effective_mode_is_the_most_restrictive`, `::test_hub_mode_select_sets_the_whole_instance`, `::test_mode_persists_across_restart`, `::test_disabled_ignores_state_and_leaves_the_baseline`; `tests/test_native_entities.py::test_observe_and_disabled_modes_block_the_press`; `tests/test_diagnostics.py::test_diagnostics_structure`, `::test_sentinel_strings_never_appear_in_the_output`, `::test_output_has_exactly_the_documented_keys`, `::test_roster_rows_are_shortened_and_include_offline_peers`, `::test_redaction_safety_net_removes_leaked_keys`. Layout of the mode selects after Phase 5: see the second override. |
| 5 | README and docs cover setup, trust model and limitations; a tagged release is built automatically with the manifest version matching the tag; CI runs the unit, real-Mosquitto and multi-instance tiers | VERIFIED | README sections `Setup`, `Trust model and approval`, `Operations`, `Limitations`, `Releases` plus `docs/operations.md`, `docs/diagnostics.md`, `docs/troubleshooting.md`, `docs/broker-acl.md`; `tests/test_docs.py::test_docs_links_resolve`, `::test_troubleshooting_covers_every_issue_key`, `::test_readme_documents_the_release_process`, `::test_readme_documents_the_test_tiers`, `::test_readme_limitations_are_current`, `::test_acl_document_names_every_topic_family`. Workflows at the frozen sha: `ci.yml` jobs `lint`, `unit` (`-m "not broker and not multi_instance"`), `broker` (installs mosquitto, `MQTT_ACTIONS_REQUIRE_BROKER=1`, `-m broker`), `multi-instance` (`-m multi_instance`); `release.yml` `check-version` compares `GITHUB_REF_NAME` with `manifest.json`, `release` needs `[check-version, ci, validate]`; `validate.yml` hassfest plus HACS; all jobs pinned to `ubuntu-24.04`, actions pinned by SHA. Tests: `tests/test_repo_structure.py::test_ci_has_one_job_per_tier`, `::test_tiers_partition_the_suite`, `::test_release_checks_the_manifest_version_against_the_tag`, `::test_release_needs_the_version_check_and_every_tier`, `::test_every_job_runs_on_one_pinned_runner`, `::test_validate_workflow_has_hassfest_and_hacs_jobs`. Real runs (07-PROOF): ci.yml dispatch runs 37205596675, 37205721595, 37205851615 and Validate run 37205956233 all success at sha `d92b87f`; release run 37206309249 on `v1.0.1-rc1` all 8 jobs success, GitHub prerelease created and cleaned up; `v0.1.0` and `v1.0.0` releases exist. |

**Score:** 5/5 truths verified (2 of them carry a superseded-by-Phase-5 clause recorded as an override; 0 present, behavior-unverified)

### Superseded by Phase 5 (D-03)

| Item | Phase 4 claim | Phase 5 decision | Evidence of the new behavior |
|------|---------------|------------------|------------------------------|
| Resync republishes Discovery of all owned devices (SC3, DSC-04) | Every owned device's Discovery is republished | Discovery is no longer the default; it is an optional export, off by default (ADR 0001 D-03, D-11) | `tests/test_discovery_export.py::test_a_native_device_publishes_the_export_when_enabled`, `::test_the_export_is_off_by_default`, `::test_a_legacy_device_never_publishes_the_export`; `manager.py:2255-2282` |
| Mode selects on a companion device beside the core-MQTT device (SC4 evidence, D-13 workaround, UAT test 4) | Mirror and owned device with the same name appear as separate companion devices | One device per config entry; companion merged into it (ADR 0001 "Cutover design") | `tests/test_native_entities.py::test_the_mode_select_shares_the_device_of_the_native_entities`, `::test_a_marked_mirror_is_a_native_entity_directly_under_the_entry`; `tests/test_takeover.py::test_full_takeover_sequence_keeps_identity`, `::test_a_mirror_moves_directly_under_the_entry` |

The legacy Discovery and companion paths are not removed; they remain as the compatibility path while an online peer is not native-capable (ADR 0001 D-10), and their Phase 4 tests still pass (`tests/test_companions.py`, `tests/test_modes.py::test_owned_device_has_a_companion_device_under_its_subentry`, `tests/test_hub_entities.py`, `tests/test_services.py`). No other truth was replaced.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `retrigger.py`, `presence.py`, `portability.py`, `services.py`, `services.yaml`, `sensor.py`, `button.py`, `select.py`, `entities.py`, `diagnostics.py`, `modes.py`, `repairs.py`, `document.py`, `sync.py`, `manager.py` | Operations features | VERIFIED | Substantive and wired as listed under the truths; Phase 5 additions in `button.py`, `select.py`, `entities.py`, `manager.py`, `presence.py`, `sync.py` keep the Phase 4 behavior (targeted tests pass) |
| `translations/en.json`, `de.json` | hassfest-valid, en/de parity, one text source per fixable issue | VERIFIED | `tests/test_translations.py` passes; hassfest green in Validate run 37205956233 and in the release run; the `approval_required`, `duplicate_instance_id`, `transferred` issue and select texts are byte-identical to the state the 2026-10-03 UAT approved (compared at `0816e05`) |
| `.github/workflows/ci.yml`, `release.yml`, `validate.yml` | Tiered CI, gated release | VERIFIED | Read in full at the frozen sha; proven by real runs (07-PROOF) |
| `docs/*.md`, `README.md`, `docs/broker-acl.md` | Documentation, tested ACL | VERIFIED | `tests/test_docs.py`, `tests/broker/test_acl.py::test_documented_acl_block_is_the_tested_acl` |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `__init__.py` `async_setup` | `services.async_setup_services` | direct call (line 30), services outlive an unload | WIRED (`tests/test_services.py`) |
| `services._async_handle_retrigger` | `RetriggerCoordinator.async_retrigger` | `manager.retrigger` (`manager.py:524`, started at 800) | WIRED |
| `Manager._on_message` / test path | `effective_mode` | direct call (`manager.py:2292`) | WIRED |
| `PresenceManager` -> `Manager.on_duplicate_id_changed` -> issue -> `DuplicateIdRepairFlow` | `repairs.async_create_fix_flow` | `ISSUE_DUPLICATE_INSTANCE_ID` | WIRED |
| `sync` transfer detection -> `TransferredRepairFlow` | `async_release_device_locally` | `ISSUE_TRANSFERRED_PREFIX` | WIRED |
| `async_resync` -> `_async_republish` -> `_async_publish_owned` -> `async_publish_discovery` | legacy Discovery or export | `is_native` branch | WIRED (see override 1) |
| `release.yml` `release` job | `ci.yml` and `validate.yml` | `needs: [check-version, ci, validate]` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `RosterSensor` | online count, rows | `presence.rows()` from validated heartbeats | Yes | FLOWING |
| Diagnostics | roster, devices | `manager.presence`, `manager.devices`, `manager.mirrors` | Yes | FLOWING |
| Re-trigger response | `instances` | acks collected in `_Pending` | Yes | FLOWING |
| Repairs confirm text | instance, devices, device, claimant | live `Manager` state per flow | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 4 test files plus Phase 5 evidence tests | `uv run --locked pytest -q -p no:cacheprovider <19 files listed in the Summary>` | 683 passed in 48.00 s | PASS |
| Real Mosquitto tier and Phase 5 cutover/export tests | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider tests/broker tests/test_cutover_instances.py tests/test_discovery_export.py tests/test_native_start.py tests/test_cutover.py` | 88 passed in 26.25 s | PASS |
| Full suite, three local runs | cited from 07-PROOF (head `0f9ad70`, code identical to the frozen sha) | 1490 passed x3 | PASS (cited) |
| CI on ubuntu-24.04, Validate, release | cited from 07-PROOF | all success | PASS (cited) |
| Code unchanged since the proven head | `git diff --stat 0f9ad70 81db888 -- custom_components tests .github pyproject.toml uv.lock` | empty | PASS |

### Probe Execution

No `probe-*.sh` is declared or present. Skipped.

### Requirements Coverage

Every ID in the plan frontmatter (04-01 to 04-14) and every ID mapped to Phase 4 in `.planning/milestones/v1.0-REQUIREMENTS.md` is accounted for; no orphans.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| OPS-01 | 04-10 | SATISFIED | truth 1 |
| OPS-02 | 04-10 | SATISFIED | truth 1 (acks and service response) |
| OPS-03 | 04-03, 04-04 | SATISFIED | truth 2 |
| OPS-04 | 04-07 | SATISFIED | truth 4 (diagnostics tests) |
| OPS-05 | 04-01, 04-13, 04-14 | SATISFIED | truth 5 |
| OPS-06 | 04-01 | SATISFIED | three tiers in CI; 17 broker, 165 multi-instance tests in the CI run |
| SYN-07 | 04-11, 04-12 | SATISFIED (adoption, per D-09 and the criterion's "or") | truth 3 |
| SYN-08 | 04-08, 04-09 | SATISFIED | truth 3 (export/import) |
| SYN-09 | 04-02, 04-05, 04-06 | SATISFIED | truth 4 and `tests/test_repairs_flow.py::test_flow_states_the_startup_flag_the_hash_binds` |
| SYN-10 | 04-12, 04-14 | SATISFIED | truth 2 |
| DSC-04 | 04-04, 04-08 | SATISFIED (Discovery clause superseded by Phase 5, override 1) | truth 3 |

### Anti-Patterns Found

`grep -n -E "TBD|FIXME|XXX"` over `custom_components`, `.github`, `docs`, `README.md`, `tests`: no match. No stub patterns in the Phase 4 modules (each is substantive and exercised by the tests above).

### Code review (advisory, `04-REVIEW.md`, `04-REVIEW-DISPOSITION.md`)

Unchanged: 0 critical, 12 warnings, 4 info, all recorded as open. None falsifies a must-have. Not re-triaged here.

### Human verification items of the previous report (D-04)

The previous report carried 11 human-verification items (all passed in `04-UAT.md` on 2026-10-03, on the 0.1.0 code). Each is mapped to the automated tier that exercises its substance on the final code. Real-instance and real-client re-runs are not repeated here; the owner assigned them to Phase 8.

| # | UAT item | Automated coverage on the final code | Residual |
|---|----------|--------------------------------------|----------|
| 1 | Validate (hassfest + HACS) green | Validate run 37205956233 and the Validate jobs of release run 37206309249 (07-PROOF); local guards `tests/test_translations.py::test_issue_has_one_text_source`, `::test_issue_guard_detects_the_hassfest_violations`, `tests/test_repo_structure.py::test_validate_workflow_has_hassfest_and_hacs_jobs` | none |
| 2 | First release by tag | Release run 37206309249 on `v1.0.1-rc1`: check-version, CI tiers, Validate, Create GitHub release all success, prerelease flag, cleanup (07-PROOF); `tests/test_repo_structure.py::test_release_checks_the_manifest_version_against_the_tag`, `::test_release_needs_the_version_check_and_every_tier` | none |
| 3 | Diagnostics content in a real HA | `tests/test_diagnostics.py::test_diagnostics_structure`, `::test_sentinel_strings_never_appear_in_the_output`, `::test_output_has_exactly_the_documented_keys`, `::test_roster_rows_are_shortened_and_include_offline_peers` | Browser click on the core "Download diagnostics" button (the UAT also did not click it): real-client, in the category the owner assigned to Phase 8 |
| 4 | Mirror and owned device as companions, mode select changes behavior | Superseded layout, see override 2; behavior: `tests/test_companions.py::test_observe_stops_an_approved_mirror`, `tests/test_modes.py::test_observe_logs_and_runs_nothing_but_tracks_the_baseline`, `tests/test_native_entities.py::test_the_mode_select_shares_the_device_of_the_native_entities` | Real two-instance run: Phase 8 category |
| 5 | Mode selects with translated labels | `tests/test_modes.py::test_hub_mode_select_sets_the_whole_instance`, `::test_effective_mode_is_the_most_restrictive`, `tests/test_entity_ids.py` (en/de entity names), `tests/test_translations.py` (en/de parity); the select translation block is byte-identical to the state the UAT read in the frontend (compared at `0816e05`) | Frontend rendering: Phase 8 category |
| 6 | Re-trigger from Developer Tools with two instances | Multi-instance tier `tests/test_multi_instance_ops.py::test_retrigger_runs_approved_instances_and_touches_no_state`, `::test_roster_offline_and_silent_instances_are_no_answer`, `::test_retrigger_honors_modes_and_breaker_in_the_multi_instance_tier`, `::test_unapproved_mirror_answers_not_approved_and_runs_nothing`; `tests/test_retrigger.py::test_statuses`; real broker tier `tests/broker/test_acl.py::test_retrigger_topic_is_a_live_trigger_for_home_assistant_users_only` and the ACL lines the UAT found missing (`tests/broker/test_acl.py::test_documented_acl_block_is_the_tested_acl`, `tests/test_docs.py::test_acl_document_names_every_topic_family`) | Real two-instance run: Phase 8 category |
| 7 | Import/export in a real HA; file not reachable via `/local` | `tests/test_portability.py::test_write_export_creates_a_private_file` (0700/0600), `::test_export_file_name_rules`, `::test_prepare_import_assigns_new_ids_and_owner`, `tests/test_services.py` export/import cases; location is `<config>/mqtt_actions/` by construction (`portability.py` line 111), never `www` (`docs/operations.md` line 292); mirrors on other instances ask for approval: `tests/test_repairs_flow.py::test_approval_issue_is_created_fixable_with_hash_data` | Real HA web server check (`/local` returns 404): real-instance, Phase 8 category |
| 8 | Duplicate instance id and reworded confirm text | `tests/test_presence.py::test_duplicate_detection_needs_two_foreign_session_heartbeats`, `tests/test_multi_instance_ops.py::test_duplicate_id_fix_leaves_the_originals_topics_byte_identical`, `tests/test_repairs_flow.py::test_duplicate_flow_form_and_confirmation`, `tests/test_translations.py::test_fixable_issue_text_keeps_its_explanation`; the en/de issue text is byte-identical to the UAT-approved text | Real instances; the UAT's own note on a brief owner disagreement after the repair (not analyzed then) has no automated test and is a follow-up, not a must-have |
| 9 | Adoption and returning old owner | `tests/test_multi_instance_ops.py::test_adoption_end_to_end`, `::test_old_owner_recognizes_the_transfer_after_a_restart`, `tests/test_repairs_flow.py::test_release_flow_follows_the_adopter`; text byte-identical to the UAT-approved text | Real instances: Phase 8 category |
| 10 | README and docs read-through, navigable to the Repairs issue entry | `tests/test_docs.py::test_docs_links_resolve`, `::test_troubleshooting_covers_every_issue_key`, `::test_troubleshooting_covers_the_operating_problems`, `::test_readme_documents_phase4_behavior`, `::test_readme_documents_the_release_process` | The structural claim (links resolve, every issue key has an entry) is tested. Prose quality of the README is a human judgment: the README was rewritten by Phase 5 and 6 after the UAT read-through, and no phase names a new read-through. Not part of any must-have; noted for the owner |
| 11 | Wording of the approval dialog (de, en) | The approval texts are byte-identical to the text the owner approved on 2026-10-03 (`approval_required` en and de compared at `0816e05`); structure and placeholders: `tests/test_translations.py`, `tests/test_repairs_flow.py::test_confirm_form_placeholders_include_settings`, `::test_flow_states_the_startup_flag_the_hash_binds` | none (human result stands on unchanged text) |

No item is left without an automated tier or a recorded result on unchanged text, so no item is `human_needed`. Two honest observations for the owner, neither of which changes the status:

- Phase 8 (UAT-01 to UAT-04) names only Phase 5 native-entity checks (legacy peer, replay duplicates, command fan-out, Discovery export). It names none of the Phase 4 operations checks (re-trigger, import/export, duplicate id, adoption, diagnostics download button). Those last ran on real instances on the 0.1.0 code; on the final code they rest on the multi-instance and real-broker tiers above.
- Item 10: the current README prose has not been read by a human since Phases 5 and 6 changed it.

### Gaps Summary

No gaps. All five roadmap truths hold on the final code, two Phase 4 evidence elements are recorded as intentionally superseded by Phase 5 (D-03), and every previous human-verification item is covered by a named automated test, a cited CI/release run, or a recorded human result on byte-identical text.

---

_Verified: 2026-10-04_
_Verifier: Claude (gsd-verifier)_
