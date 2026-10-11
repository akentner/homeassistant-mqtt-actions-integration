---
phase: 04-operations-recovery-and-release
verified: 2026-10-11T17:30:00Z
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
  - .planning/phases/08-real-instance-verification/08-UAT.md
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
  - tests/test_entity_ids.py
  - tests/test_export_guard_receiver.py
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
covered_digest: "v3:sha256:70cbb2e009b568f369390c841ee34b89f52fd33dda8baa899ae50278c33e25c0"
behavior_unverified: 0
overrides_applied: 2
overrides:
  - must_have: "User can run a manual resync that republishes config and discovery of all owned devices (ROADMAP SC3, DSC-04: discovery clause)"
    reason: "superseded by Phase 5: native switch and select entities replaced MQTT Discovery as the default (ADR 0001, docs/adr/0001-native-entities-instead-of-mqtt-discovery.md, decisions D-03 and D-11). A native device publishes no Discovery on resync; Discovery is republished only on the legacy compatibility path and as the optional export. Test proving the new behavior: tests/test_discovery_export.py::test_a_native_device_publishes_the_export_when_enabled and ::test_the_export_is_off_by_default (publish path Manager.async_publish_discovery, manager.py:2335-2362, called by _async_publish_owned from async_resync); tests/test_native_entities.py::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select. The config documents, availability and heartbeat are still republished (tests/test_hub_entities.py::test_resync_button_republishes_in_the_phase_3_order and tests/test_services.py::test_resync_service_republishes_in_the_phase_3_order, both on the legacy path the fixtures pin)."
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
**Verified:** 2026-10-11 (build sha `b8232252540a55969145ca0034d8fd86b4be3b7c`, the receiver-guard build pinned in `.planning/phases/08-real-instance-verification/08-evidence/00-preflight/build.txt`; the working tree code is byte-identical to it: `git diff --stat b8232252 HEAD -- custom_components tests .github pyproject.toml uv.lock README.md docs` is empty)
**Status:** passed
**Re-verification:** Yes - the second re-verification of the archived phase. The first (2026-10-04, plan 07-05) judged the frozen sha `81db888c`; this one judges the receiver-guard build of Phase 8 (plans 08-12 and 08-17 changed `manager.py`, `takeover.py`, `README.md`, `docs/troubleshooting.md` and the tests). Output path overridden to the archived directory (D-02, D-06 of Phase 8); plan 08-15 Task 2, path A (the product diff against the first pin `b7f52b34` is non-empty).

## Summary

The phase was re-judged against the code at the build sha. No SUMMARY claim was taken as evidence: the five truths were re-read in code and tied to tests that were run in this verification.

- **No Phase 4 truth regressed.** The two parts of the evidence base that Phase 5 replaced on purpose keep their `superseded by Phase 5` overrides (D-03); they are carried unchanged and not re-litigated.
- **What changed since the previous report** (`git diff 81db888c b8232252 -- custom_components tests .github pyproject.toml uv.lock README.md docs`: six files, 814 insertions, 2 deletions): `custom_components/mqtt_actions/manager.py` (a registry listener `_arm_duplicate_guard`, armed in `async_start` at line 808 before `_async_publish_owned`, disarmed on stop at line 1231; `_duplicate_guard_ids`, `_on_duplicate_registry_updated`, `_disable_duplicates`), `takeover.py` (`EXPORT_DOMAINS`, `disable_duplicates`), `README.md` and `docs/troubleshooting.md` (documentation of the guard), `tests/test_discovery_export.py` and the new `tests/test_export_guard_receiver.py`. The guard only disables an enabled core-MQTT duplicate of a native device in the entity registry; it publishes nothing and touches none of the Phase 4 modules (`retrigger.py`, `presence.py`, `portability.py`, `services.py`, `diagnostics.py`, `modes.py`, `repairs.py`, `sensor.py`, `runner.py`, `button.py`, `select.py` are unchanged). `.github/`, `pyproject.toml` and `uv.lock` did not change. Because `manager.py` is the file that hosts resync, adoption, effective mode and the repair hooks, those paths were re-read (the line numbers below are the current ones; the guard shifted the lines after 808 by 85) and their tests re-run.
- **Test evidence run by this verifier at the build sha** (code identical to HEAD, see above): 725 passed in 50.0 s over `tests/test_retrigger.py tests/test_presence.py tests/test_portability.py tests/test_services.py tests/test_modes.py tests/test_runner_modes.py tests/test_companions.py tests/test_diagnostics.py tests/test_repairs_flow.py tests/test_translations.py tests/test_docs.py tests/test_multi_instance_ops.py tests/test_multi_instance.py tests/test_sync_follower.py tests/test_hub_entities.py tests/test_takeover.py tests/test_repo_structure.py tests/test_toolchain.py tests/test_native_entities.py tests/test_export_guard_receiver.py tests/test_discovery_export.py`; and 69 passed in 23.3 s over `tests/broker tests/test_cutover_instances.py tests/test_native_start.py tests/test_cutover.py` with `MQTT_ACTIONS_REQUIRE_BROKER=1` against the local `/usr/bin/mosquitto`. The full suite was not re-run here; the unit, broker and multi-instance tiers and the CI and release runs are cited from `.planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md` (three local full-suite runs of 1490 passed, three CI dispatch runs, a green Validate run and the green release run on `v1.0.1-rc1`), which proves the code of the first pin. The receiver-guard build adds tests only for the guard; the workflows are byte-identical to the proven ones.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Re-trigger service (non-retained, `request_id` dedupe, rate-limited); the caller sees which instances acknowledged and executed | VERIFIED | `retrigger.py` (unchanged since the first report): request published `retain=False` (line 295), receiver drops retained requests (line 369), dedupe via `self._seen` (383-385), per-device receiver rate limit (386-389), caller rate limit `REASON_RATE_LIMITED` (259), acks non-retained to the requester (472), run path `test=True` (450) so tracker, baseline and breaker stay untouched. Service `retrigger` registered with `SupportsResponse.OPTIONAL` (`services.py:329`). Tests passing in this run: `tests/test_retrigger.py::test_retained_requests_are_ignored`, `::test_stale_and_future_requests_are_dropped`, `::test_duplicate_request_ids_run_once`, `::test_receiver_rate_limit_per_device`, `::test_statuses`, `::test_caller_rate_limit_and_state_selection`; multi-instance tier `tests/test_multi_instance_ops.py::test_retrigger_runs_approved_instances_and_touches_no_state`, `::test_retrigger_returns_before_the_window_when_everyone_answered`, `::test_roster_offline_and_silent_instances_are_no_answer`, `::test_retrigger_honors_modes_and_breaker_in_the_multi_instance_tier`, `::test_unapproved_mirror_answers_not_approved_and_runs_nothing`, `::test_acknowledgements_per_request_are_capped`; real broker tier `tests/broker/test_acl.py::test_retrigger_topic_is_a_live_trigger_for_home_assistant_users_only`, `::test_ack_topic_is_readable_only_by_its_instance`, `::test_any_instance_may_answer_a_requester`. The state-transition and ordering invariants (dedupe, rate limit, retained refusal, no state change on a test run) are exercised by those passing tests, so no truth is left present-but-unexercised. |
| 2 | Roster with presence heartbeat; a duplicate instance id is detected and reported | VERIFIED | `presence.py` heartbeat (non-retained, 30 s) and 90 s offline rule; `RosterSensor` (`sensor.py:19`, added by `async_setup_entry`, line 59); duplicate detection `presence.py:415-433` -> `Manager.on_duplicate_id_changed` (`manager.py:1628`, issue `ISSUE_DUPLICATE_INSTANCE_ID` created at 1648) -> fixable Repairs issue -> `repairs.DuplicateIdRepairFlow` (`repairs.py:96`, dispatched at 167-168). Tests passing in this run: `tests/test_presence.py::test_heartbeat_is_published_non_retained_with_qos_0`, `::test_heartbeat_tick_publishes_every_30_seconds`, `::test_duplicate_detection_needs_two_foreign_session_heartbeats`, `::test_duplicate_clears_after_90_seconds_of_silence`, `::test_a_capability_claim_never_replaces_a_fresh_legacy_row`; `tests/test_hub_entities.py::test_hub_device_and_roster_sensor_exist`, `::test_roster_sensor_follows_the_heartbeats`; `tests/test_multi_instance_ops.py::test_instances_see_each_other_through_heartbeats`, `::test_roster_marks_a_peer_offline_after_90_seconds`, `::test_duplicate_detection_changes_nothing_by_itself`, `::test_duplicate_id_fix_leaves_the_originals_topics_byte_identical`; `tests/test_repairs_flow.py::test_duplicate_issue_is_created_once_and_cleared`, `::test_duplicate_flow_form_and_confirmation`. |
| 3 | Manual resync that republishes config and discovery of all owned devices; export to JSON and import; transfer ownership of a device or adopt an orphaned one | VERIFIED; the "and discovery of all owned devices" clause is PASSED (override, superseded by Phase 5) | Resync: `Manager.async_resync` (`manager.py:1268`) -> `_async_republish` (1286) -> `_async_publish_owned` (1320): documents, then discovery, then `online`, then heartbeat; throttled; button `ResyncButton` (`button.py:27`, added at 128) and service `resync` share it. The receiver-side guard (armed once in `async_start`, `manager.py:808`) is registry-only and is not on the resync path. Tests: `tests/test_hub_entities.py::test_resync_button_republishes_in_the_phase_3_order`, `::test_resync_is_throttled`, `tests/test_services.py::test_resync_service_republishes_in_the_phase_3_order`, `::test_resync_service_is_admin_only`, `::test_resync_service_throttled_raises_a_translated_error`, `tests/test_native_start.py::test_a_failed_retained_clear_after_the_move_keeps_the_device_native_and_is_retried`. Discovery clause: on the default (native) path a resync no longer republishes Discovery, see the override (ADR 0001, D-03/D-11): `Manager.async_publish_discovery` (`manager.py:2335`) publishes the export only when `export_enabled`, and `tests/test_discovery_export.py::test_the_export_is_off_by_default` passes. Export/import: `portability.py` (private file `<config>/mqtt_actions/`, `export_file_path` at line 107, never `www`), services `export_devices`, `import_devices`; `tests/test_portability.py::test_write_export_creates_a_private_file`, `::test_prepare_import_assigns_new_ids_and_owner`, `::test_parse_and_prepare_reject_hostile_input`, `::test_denied_services_are_rejected`, `::test_read_import_refuses_a_symlinked_directory`. Transfer or adopt: SC3 says "transfer ... or adopt"; `Manager.async_adopt` (`manager.py:1514`), service `adopt_device` (`services.py:332`), `TransferredRepairFlow` for the old owner (`repairs.py:126`); `tests/test_multi_instance_ops.py::test_adoption_end_to_end`, `::test_adoption_clears_nothing_on_the_broker`, `::test_adoption_needs_the_owner_offline_or_force`, `::test_old_owner_recognizes_the_transfer_after_a_restart`, `::test_transferred_away_device_is_not_republished`; `tests/test_repairs_flow.py::test_release_flow_follows_the_adopter`; `tests/test_native_start.py::test_adopting_a_native_mirror_keeps_the_device_native_on_a_legacy_instance`. The guard excludes devices transferred away (`_duplicate_guard_ids` subtracts `sync.transferred_away`), consistent with the adoption tests that pass. Scope note (unchanged since the first report): D-09 of 04-CONTEXT.md implements adoption (with `force`) and defers an active hand-off; the criterion's "or" is satisfied, so no override is needed. |
| 4 | Per instance and device mode (run / observe / disabled); diagnostics download with sensitive data redacted | VERIFIED; the companion-device layout is PASSED (override, superseded by Phase 5) | `modes.py` (`most_restrictive`), `Manager.effective_mode` (`manager.py:627`, `most_restrictive(self._instance_mode, self.device_mode(device_id))` at 629), gating at 2372 (`MODE_DISABLED`), 2450 (`MODE_OBSERVE`) and 2586 (`MODE_RUN`); `select.py`; `diagnostics.py` (allow-list plus `async_redact_data` over the finished result at line 109, hook `async_get_config_entry_diagnostics` at line 98). Tests passing in this run: `tests/test_modes.py::test_observe_logs_and_runs_nothing_but_tracks_the_baseline`, `::test_effective_mode_is_the_most_restrictive`, `::test_hub_mode_select_sets_the_whole_instance`, `::test_mode_persists_across_restart`, `::test_disabled_ignores_state_and_leaves_the_baseline`; `tests/test_native_entities.py::test_observe_and_disabled_modes_block_the_press`; `tests/test_diagnostics.py::test_diagnostics_structure`, `::test_sentinel_strings_never_appear_in_the_output`, `::test_output_has_exactly_the_documented_keys`, `::test_roster_rows_are_shortened_and_include_offline_peers`, `::test_redaction_safety_net_removes_leaked_keys`. Layout of the mode selects after Phase 5: see the second override. |
| 5 | README and docs cover setup, trust model and limitations; a tagged release is built automatically with the manifest version matching the tag; CI runs the unit, real-Mosquitto and multi-instance tiers | VERIFIED | README sections `Setup`, `Trust model and approval`, `Operations`, `Limitations`, `Releases` plus `docs/operations.md`, `docs/diagnostics.md`, `docs/troubleshooting.md`, `docs/broker-acl.md`; plan 08-12 and 08-17 added documentation of the duplicate guard to `README.md` and `docs/troubleshooting.md` (ten and sixteen lines) and the structural docs tests still pass: `tests/test_docs.py::test_docs_links_resolve`, `::test_troubleshooting_covers_every_issue_key`, `::test_readme_documents_the_release_process`, `::test_readme_documents_the_test_tiers`, `::test_readme_limitations_are_current`, `::test_acl_document_names_every_topic_family`. Workflows at the build sha (byte-identical to the frozen sha): `ci.yml` jobs `lint`, `unit`, `broker` (`MQTT_ACTIONS_REQUIRE_BROKER=1`), `multi-instance`; `release.yml` `check-version` and `release` with `needs: [check-version, ci, validate]` (line 51); `validate.yml` hassfest plus HACS; every job on `ubuntu-24.04`. Tests: `tests/test_repo_structure.py::test_ci_has_one_job_per_tier`, `::test_tiers_partition_the_suite`, `::test_release_checks_the_manifest_version_against_the_tag`, `::test_release_needs_the_version_check_and_every_tier`, `::test_every_job_runs_on_one_pinned_runner`, `::test_validate_workflow_has_hassfest_and_hacs_jobs`, all passing in this run. Real runs (cited from 07-PROOF, for the unchanged workflows): ci.yml dispatch runs 37205596675, 37205721595, 37205851615 and Validate run 37205956233 success at sha `d92b87f`; release run 37206309249 on `v1.0.1-rc1` all 8 jobs success, prerelease created and cleaned up; `v0.1.0` and `v1.0.0` releases exist. Not re-run since the receiver-guard build (the guard changed no workflow, manifest or dependency file); a CI run of the guard commits belongs to the owner's push of the branch. |

**Score:** 5/5 truths verified (2 of them carry a superseded-by-Phase-5 clause recorded as an override; 0 present, behavior-unverified)

### Superseded by Phase 5 (D-03)

| Item | Phase 4 claim | Phase 5 decision | Evidence of the new behavior |
|------|---------------|------------------|------------------------------|
| Resync republishes Discovery of all owned devices (SC3, DSC-04) | Every owned device's Discovery is republished | Discovery is no longer the default; it is an optional export, off by default (ADR 0001 D-03, D-11) | `tests/test_discovery_export.py::test_a_native_device_publishes_the_export_when_enabled`, `::test_the_export_is_off_by_default`, `::test_a_legacy_device_never_publishes_the_export`; `manager.py:2335-2362` |
| Mode selects on a companion device beside the core-MQTT device (SC4 evidence, D-13 workaround, UAT test 4) | Mirror and owned device with the same name appear as separate companion devices | One device per config entry; companion merged into it (ADR 0001 "Cutover design") | `tests/test_native_entities.py::test_the_mode_select_shares_the_device_of_the_native_entities`, `::test_a_marked_mirror_is_a_native_entity_directly_under_the_entry`; `tests/test_takeover.py::test_full_takeover_sequence_keeps_identity`, `::test_a_mirror_moves_directly_under_the_entry` |

The legacy Discovery and companion paths are not removed; they remain as the compatibility path while an online peer is not native-capable (ADR 0001 D-10), and their Phase 4 tests still pass (`tests/test_companions.py`, `tests/test_modes.py::test_owned_device_has_a_companion_device_under_its_subentry`, `tests/test_hub_entities.py`, `tests/test_services.py`). No other truth was replaced. The receiver-side guard of Phase 8 is not a supersession of a Phase 4 truth: it adds a registry safeguard for the optional export and leaves resync, re-trigger, roster, modes, diagnostics and release behavior as they were.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `retrigger.py`, `presence.py`, `portability.py`, `services.py`, `services.yaml`, `sensor.py`, `button.py`, `select.py`, `entities.py`, `diagnostics.py`, `modes.py`, `repairs.py`, `document.py`, `sync.py`, `manager.py` | Operations features | VERIFIED | Substantive and wired as listed under the truths; only `manager.py` (and `takeover.py`, not a Phase 4 module) changed since the first report, by the registry-only guard; the targeted tests pass |
| `translations/en.json`, `de.json` | hassfest-valid, en/de parity, one text source per fixable issue | VERIFIED | `tests/test_translations.py` passes; the files are unchanged since the first report (`git diff 81db888c b8232252 --stat -- custom_components` lists only `manager.py` and `takeover.py`) |
| `.github/workflows/ci.yml`, `release.yml`, `validate.yml` | Tiered CI, gated release | VERIFIED | Read in this run (jobs, `needs`, runner); unchanged and proven by real runs (07-PROOF) |
| `docs/*.md`, `README.md`, `docs/broker-acl.md` | Documentation, tested ACL | VERIFIED | `tests/test_docs.py`, `tests/broker/test_acl.py::test_documented_acl_block_is_the_tested_acl` pass |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `__init__.py` `async_setup` | `services.async_setup_services` | direct call (line 30), services outlive an unload | WIRED (`tests/test_services.py`) |
| `services._async_handle_retrigger` | `RetriggerCoordinator.async_retrigger` | `manager.retrigger` (`manager.py:524`, started at 802, stopped at 1234) | WIRED |
| `Manager._on_message` (2365) / test path | `effective_mode` | direct call (2372, 2450, 2586) | WIRED |
| `PresenceManager` -> `Manager.on_duplicate_id_changed` -> issue -> `DuplicateIdRepairFlow` | `repairs.async_create_fix_flow` | `ISSUE_DUPLICATE_INSTANCE_ID` | WIRED |
| `sync` transfer detection -> `TransferredRepairFlow` | `async_release_device_locally` | `ISSUE_TRANSFERRED_PREFIX` | WIRED |
| `async_resync` -> `_async_republish` -> `_async_publish_owned` -> `async_publish_discovery` | legacy Discovery or export | `is_native` branch | WIRED (see override 1) |
| `release.yml` `release` job | `ci.yml` and `validate.yml` | `needs: [check-version, ci, validate]` | WIRED |
| `Manager.async_start` -> `_arm_duplicate_guard` (808) -> `takeover.disable_duplicates` | entity registry | `EVENT_ENTITY_REGISTRY_UPDATED` listener, disarmed in the stop path (1231) | WIRED (Phase 8 addition, not a Phase 4 must-have; `tests/test_export_guard_receiver.py` passes) |

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
| Phase 4 test files, Phase 5 evidence tests and the guard tests | `uv run --locked pytest -q -p no:cacheprovider <21 files listed in the Summary>` | 725 passed in 50.0 s | PASS |
| Real Mosquitto tier and Phase 5 cutover/native-start tests | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider tests/broker tests/test_cutover_instances.py tests/test_native_start.py tests/test_cutover.py` | 69 passed in 23.3 s | PASS |
| Full suite, three local runs | cited from 07-PROOF (head `0f9ad70`, first-pin code); not re-run | 1490 passed x3 | PASS (cited) |
| CI on ubuntu-24.04, Validate, release | cited from 07-PROOF (workflows unchanged) | all success | PASS (cited) |
| Build sha equals the checked-out code | `git diff --stat b8232252540a55969145ca0034d8fd86b4be3b7c HEAD -- custom_components tests .github pyproject.toml uv.lock README.md docs` | empty | PASS |
| Anti-patterns | `grep -rn -E "TBD\|FIXME\|XXX" custom_components .github docs README.md tests` | no match | PASS |

### Probe Execution

No `probe-*.sh` is declared or present. Skipped.

### Requirements Coverage

Every ID in the plan frontmatter (04-01 to 04-14: DSC-04, OPS-01 to OPS-06, SYN-07 to SYN-10) and every ID mapped to Phase 4 in `.planning/milestones/v1.0-REQUIREMENTS.md` is accounted for; no orphans.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| OPS-01 | 04-10 | SATISFIED | truth 1 |
| OPS-02 | 04-10 | SATISFIED | truth 1 (acks and service response) |
| OPS-03 | 04-03, 04-04 | SATISFIED | truth 2 |
| OPS-04 | 04-07 | SATISFIED | truth 4 (diagnostics tests) |
| OPS-05 | 04-01, 04-13, 04-14 | SATISFIED | truth 5 |
| OPS-06 | 04-01 | SATISFIED | three tiers in CI (`tests/test_repo_structure.py::test_ci_has_one_job_per_tier`); 17 broker, 165 multi-instance tests in the cited CI run |
| SYN-07 | 04-11, 04-12 | SATISFIED (adoption, per D-09 and the criterion's "or") | truth 3 |
| SYN-08 | 04-08, 04-09 | SATISFIED | truth 3 (export/import) |
| SYN-09 | 04-02, 04-05, 04-06 | SATISFIED | truth 4 and `tests/test_repairs_flow.py::test_flow_states_the_startup_flag_the_hash_binds` |
| SYN-10 | 04-12, 04-14 | SATISFIED | truth 2 |
| DSC-04 | 04-04, 04-08 | SATISFIED (Discovery clause superseded by Phase 5, override 1) | truth 3 |

### Anti-Patterns Found

`grep -rn -E "TBD|FIXME|XXX"` over `custom_components`, `.github`, `docs`, `README.md`, `tests`: no match. No stub patterns in the Phase 4 modules (each is substantive and exercised by the tests above). The new guard code in `manager.py` catches a broad `Exception` on purpose (`# noqa: BLE001`, logged without registry or broker content) so that it can never keep the manager from running; that is a documented design choice of plan 08-17, not a stub.

### Code review (advisory, `04-REVIEW.md`, `04-REVIEW-DISPOSITION.md`)

Unchanged: 0 critical, 12 warnings, 4 info, all recorded as open. None falsifies a must-have. Not re-triaged here.

### Human verification items of the previous report (D-04)

The first report carried 11 human-verification items (all passed in `04-UAT.md` on 2026-10-03, on the 0.1.0 code). Each stays mapped to the automated tier that exercises its substance on the current code, with the same residuals. Real-instance and real-client re-runs of Phase 4 operations are not part of the Phase 8 ledger (`.planning/phases/08-real-instance-verification/08-UAT.md` names UAT-01 to UAT-04 and the ten items of Phases 1 to 3, and states that Phase 4 has no human item and stays `passed`); the guard build changed no text, service, option or Repairs issue that these items judged, so the result on unchanged text stands.

| # | UAT item | Automated coverage on the current code | Residual |
|---|----------|----------------------------------------|----------|
| 1 | Validate (hassfest + HACS) green | Validate run 37205956233 and the Validate jobs of release run 37206309249 (07-PROOF); `tests/test_translations.py::test_issue_has_one_text_source`, `::test_issue_guard_detects_the_hassfest_violations`, `tests/test_repo_structure.py::test_validate_workflow_has_hassfest_and_hacs_jobs` (passing now) | none |
| 2 | First release by tag | Release run 37206309249 on `v1.0.1-rc1` (07-PROOF); `tests/test_repo_structure.py::test_release_checks_the_manifest_version_against_the_tag`, `::test_release_needs_the_version_check_and_every_tier` (passing now) | none |
| 3 | Diagnostics content in a real HA | `tests/test_diagnostics.py::test_diagnostics_structure`, `::test_sentinel_strings_never_appear_in_the_output`, `::test_output_has_exactly_the_documented_keys`, `::test_roster_rows_are_shortened_and_include_offline_peers` | Browser click on the core "Download diagnostics" button (the UAT did not click it either): real-client, not named by Phase 8 |
| 4 | Mirror and owned device as companions, mode select changes behavior | Superseded layout, see override 2; behavior: `tests/test_companions.py::test_observe_stops_an_approved_mirror`, `tests/test_modes.py::test_observe_logs_and_runs_nothing_but_tracks_the_baseline`, `tests/test_native_entities.py::test_the_mode_select_shares_the_device_of_the_native_entities` | Real two-instance run: Phase 8 UAT-03 (command across two real instances, block 3, pass on the receiver-guard build, evidence `uat-03-rerun2`) exercised two real instances; it is not a mode-select check |
| 5 | Mode selects with translated labels | `tests/test_modes.py::test_hub_mode_select_sets_the_whole_instance`, `::test_effective_mode_is_the_most_restrictive`, `tests/test_entity_ids.py` (en/de entity names), `tests/test_translations.py` (en/de parity); translation files unchanged since the first report | Frontend rendering of the select: Phase 8 block P1-2 (English and German strings, pass) covers the integration's UI strings, not this select specifically |
| 6 | Re-trigger from Developer Tools with two instances | Multi-instance tier `tests/test_multi_instance_ops.py::test_retrigger_runs_approved_instances_and_touches_no_state`, `::test_roster_offline_and_silent_instances_are_no_answer`, `::test_retrigger_honors_modes_and_breaker_in_the_multi_instance_tier`, `::test_unapproved_mirror_answers_not_approved_and_runs_nothing`; `tests/test_retrigger.py::test_statuses`; real broker tier `tests/broker/test_acl.py::test_retrigger_topic_is_a_live_trigger_for_home_assistant_users_only`, `::test_documented_acl_block_is_the_tested_acl`, `tests/test_docs.py::test_acl_document_names_every_topic_family` | Real two-instance run of the re-trigger service itself is not in any ledger block |
| 7 | Import/export in a real HA; file not reachable via `/local` | `tests/test_portability.py::test_write_export_creates_a_private_file` (0700/0600), `::test_export_file_name_rules`, `::test_prepare_import_assigns_new_ids_and_owner`, `tests/test_services.py` export/import cases; location is `<config>/mqtt_actions/` by construction (`portability.py:109`), never `www` (`docs/operations.md:292`); `tests/test_repairs_flow.py::test_approval_issue_is_created_fixable_with_hash_data` | Real HA web server check (`/local` returns 404): not in any ledger block |
| 8 | Duplicate instance id and reworded confirm text | `tests/test_presence.py::test_duplicate_detection_needs_two_foreign_session_heartbeats`, `tests/test_multi_instance_ops.py::test_duplicate_id_fix_leaves_the_originals_topics_byte_identical`, `tests/test_repairs_flow.py::test_duplicate_flow_form_and_confirmation`, `tests/test_translations.py::test_fixable_issue_text_keeps_its_explanation`; the en/de text is unchanged | The UAT's note on a brief owner disagreement after the repair has no automated test and is a follow-up, not a must-have |
| 9 | Adoption and returning old owner | `tests/test_multi_instance_ops.py::test_adoption_end_to_end`, `::test_old_owner_recognizes_the_transfer_after_a_restart`, `tests/test_repairs_flow.py::test_release_flow_follows_the_adopter`; text unchanged | Real instances: not in any ledger block |
| 10 | README and docs read-through, navigable to the Repairs issue entry | `tests/test_docs.py::test_docs_links_resolve`, `::test_troubleshooting_covers_every_issue_key`, `::test_troubleshooting_covers_the_operating_problems`, `::test_readme_documents_phase4_behavior`, `::test_readme_documents_the_release_process` (passing now) | The structural claim is tested. Prose quality of the README is a human judgment; the README was rewritten by Phases 5 and 6 and gained a guard paragraph in Phase 8 after the UAT read-through, and no phase names a new read-through. Not part of any must-have; noted for the owner |
| 11 | Wording of the approval dialog (de, en) | The approval texts are unchanged since the text the owner approved on 2026-10-03; structure and placeholders: `tests/test_translations.py`, `tests/test_repairs_flow.py::test_confirm_form_placeholders_include_settings`, `::test_flow_states_the_startup_flag_the_hash_binds` | none (human result stands on unchanged text) |

No item is left without an automated tier or a recorded result on unchanged text, so no item is `human_needed`. The same two observations as in the first report stand, neither changes the status: the Phase 8 ledger names no Phase 4 operations check (re-trigger, import/export, duplicate id, adoption, diagnostics download button), which therefore last ran on real instances on the 0.1.0 code and rest on the multi-instance and real-broker tiers above; and the current README prose has not been read by a human since Phases 5, 6 and 8 changed it.

### Gaps Summary

No gaps. All five roadmap truths hold on the receiver-guard build, the two Phase 4 evidence elements that Phase 5 replaced on purpose stay recorded as superseded (D-03), and the Phase 8 change to `manager.py` and `takeover.py` is a registry-only guard that does not touch any Phase 4 behavior: the Phase 4 tests, the real-broker tier and the guard tests pass at the build sha.

---

_Verified: 2026-10-11_
_Verifier: Claude (gsd-verifier)_
