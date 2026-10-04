# Phase 7 Proof Ledger

Evidence ledger of Phase 7 (Verification, Stable Tests and Pinned CI). It is the source for the proof section of the
phase VERIFICATION (D-13). Plans 07-03, 07-04 and 07-05 append their sections below.

## QLT-02 stress proof (plan 07-02)

- **Date:** 2026-10-04 (run started 2026-10-04T12:57:58Z)
- **Head:** `f8e271e927061fc413d79f8afc793f566bc7e7b5` (all three 07-02 code commits included)
- **Test:** `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear`
- **Result line:** `repetitions passed: 50 of 50`
- **Wall-clock time:** 354 seconds
- **Load:** four busy loops (`while :; do :; done`, each bounded by `timeout 900`) and every repetition pinned with
  `taskset -c 0,1`, so spinners and test share two cores
- **Probe:** the permanent autouse fixture `always_slow_event_loop` (`tests/conftest.py`) was on during every
  repetition, so asyncio's slow-callback WARNING was present in every run
- **Cleanup:** no busy loop left running afterwards (`ps -eo args | grep -c '[w]hile :; do :; done'` printed 0)
- **Retries:** none; the loop stops at the first failure and none occurred

## Local three-run proof (plan 07-03)

- **Date:** 2026-10-04 (loop ran 2026-10-04T13:07:32Z to 2026-10-04T13:13:11Z)
- **Head:** `0f9ad70a9fe54d28c73d31ca3d7f8acc577789aa` (contains the 07-01 and 07-02 commits; working tree clean before and during the runs)
- **Local broker:** `mosquitto version 2.1.2` (CI installs 2.0.18 from the Ubuntu 24.04 archive, so this does not prove the CI broker tier)
- **Command (each run):** `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider`, one invocation over the
  unit, broker and multi-instance tiers, no xdist, no marker filter, always-slow probe on
- **Retries:** none; three sequential runs, each accepted only on `N passed` with no skipped, failed, error or deselected

| Run | Summary line | Duration |
|-----|--------------|----------|
| 1 | `1490 passed in 111.42s (0:01:51)` | 111.42 s |
| 2 | `1490 passed in 111.42s (0:01:51)` | 111.42 s |
| 3 | `1490 passed in 110.26s (0:01:50)` | 110.26 s |

Runs 1 and 2 report the same duration to the hundredth of a second. They are separate runs (separate log files written
about 113 seconds apart); the equal figure is a coincidence of the rounded pytest timer.

- **Ruff:** `uv run ruff check .` printed `All checks passed!`; `uv run ruff format --check .` printed `91 files already formatted`

## CI proof on ubuntu-24.04 (plan 07-03)

- **Date:** 2026-10-04 (runs 13:26Z to 13:33Z)
- **Remote branch:** `gsd/phase-06-native-entity-residual-fixes` (owner decision `push-branch-as-is`; created on origin by
  `git push origin HEAD:refs/heads/gsd/phase-06-native-entity-residual-fixes`; no tag, no release)
- **Proven sha:** `d92b87f3ebf427c6f63d3ccf0d95dd14c93af961` (the local-proof docs commit; code identical to the head of the
  local three-run proof `0f9ad70`, which differs only by planning documents)
- **Runner image (read from each job log):** `Image: ubuntu-24.04`, `Version: 20260927.320.1`, Ubuntu 24.04.5 LTS
- **Broker in CI (read from the broker job log):** Ubuntu archive package `mosquitto 2.0.18-1build3` (local broker is 2.1.2)
- **Retries:** none; each run was dispatched once, after the previous one had finished, and the next run id was taken only
  after it was newer than the previous one

| Run | Workflow | URL | Conclusion | Jobs (all success) | Image | Test counts |
|-----|----------|-----|------------|--------------------|-------|-------------|
| 1 | ci.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205596675 | success | Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests | ubuntu-24.04 / 20260927.320.1 | 1308 unit, 17 broker, 165 multi-instance |
| 2 | ci.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205721595 | success | Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests | ubuntu-24.04 / 20260927.320.1 | 1308 unit, 17 broker, 165 multi-instance |
| 3 | ci.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205851615 | success | Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests | ubuntu-24.04 / 20260927.320.1 | 1308 unit, 17 broker, 165 multi-instance |
| V | validate.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205956233 | success | hassfest, HACS | ubuntu-24.04 / 20260927.320.1 | HACS: `All (9) checks passed` |

All four runs report `headSha` `d92b87f3ebf427c6f63d3ccf0d95dd14c93af961`. The three CI runs are consecutive dispatch runs
(no failure in between). 1308 + 17 + 165 = 1490, the same total as the local runs.

- **Push-event runs (informational, not counted):** none. `gh run list --branch gsd/phase-06-native-entity-residual-fixes
  --event push` returned an empty list at the dispatch time and again after the last run; GitHub did not start push-event
  runs for the branch creation.

## Release proof (plan 07-04)

- **Approval (D-13):** owner answered `approve` at the blocking-human checkpoint (Task 1) in the session of 2026-10-04,
  before any bump, tag or push; the executor was dispatched with that answer.
- **PRE (commit before the bump):** `3a37790d6774f4f0826da07f44e515f82a558735`
- **Bump commit:** `4d24fb429514c627fab2f3298ca66f9dfabaaecf` (`chore(07-04): manifest 1.0.1-rc1 for the release proof`)
- **Local pre-push check:** `tests/test_repo_structure.py tests/test_discovery.py tests/test_presence.py tests/test_docs.py`:
  147 passed with the manifest at 1.0.1-rc1
- **Tag:** `v1.0.1-rc1` on `4d24fb4`, pushed 2026-10-04T13:37:59Z together with
  `HEAD:refs/heads/gsd/phase-06-native-entity-residual-fixes` (fast-forward `d92b87f..4d24fb4`)
- **Run URL:** https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37206309249
  (event push, head branch `v1.0.1-rc1`, headSha `4d24fb429514c627fab2f3298ca66f9dfabaaecf` = the tag commit)
- release run conclusion: success

| Job | Conclusion |
|-----|------------|
| Tag matches manifest version | success |
| CI / Ruff | success |
| CI / Unit tests | success |
| CI / Broker tests (Mosquitto) | success |
| CI / Multi-instance tests | success |
| Validate / hassfest | success |
| Validate / HACS | success |
| Create GitHub release | success |

- **Job count:** `gh run view ... --json jobs` returned 8 jobs.
- **Runner image (from `gh run view --log`):** `Image: ubuntu-24.04` appears 8 times and is the only distinct image value
  (one per job); `Version: 20260927.320.1` (runner image version) appears 8 times
- **Prerelease flag:** `gh release view v1.0.1-rc1 --json isPrerelease` returned `isPrerelease: true`
- **A1 (Latest marker):** while the prerelease existed `gh release list` showed `v1.0.1-rc1 Pre-release`, `v1.0.0 Latest`,
  `v0.1.0`; v1.0.0 kept the Latest marker (assumption A1 confirmed)

### Cleanup (Task 3, ran after the green run)

- `gh release delete v1.0.1-rc1 --cleanup-tag --yes` removed the release and the remote tag; the follow-up
  `git tag -d v1.0.1-rc1` reported the local tag as already absent (the `gh` call or the earlier state had removed it)
- Manifest reset: `git restore --source=3a37790... --staged --worktree -- custom_components/mqtt_actions/manifest.json`;
  `git diff --exit-code 3a37790... -- custom_components/mqtt_actions/manifest.json` exited 0 (byte-identical);
  `jq -r .version` printed `1.0.0`
- Reset commit: `8a93a2f5d6252471038a993a67c0d9b3b534232b` (`chore(07-04): reset the manifest version after the release proof`),
  pushed `4d24fb4..8a93a2f` to `gsd/phase-06-native-entity-residual-fixes`
- `git ls-remote --tags origin v1.0.1-rc1`: empty; `git tag -l v1.0.1-rc1`: empty
- `gh release list --limit 5`: `v1.0.0 Latest`, `v0.1.0` only
- Remote branch manifest (`git show origin/gsd/phase-06-native-entity-residual-fixes:custom_components/mqtt_actions/manifest.json`): version `1.0.0`
- **A2 (tag deletion starts no workflow):** `gh run list --workflow release.yml --limit 3` after the cleanup showed the rc run
  `37206309249` as the newest release run; no run started from the deletion (assumption A2 confirmed)
- **Push-event runs (informational):** none for the branch pushes `d92b87f..4d24fb4` and `4d24fb4..8a93a2f`;
  `gh run list --branch gsd/phase-06-native-entity-residual-fixes` still lists only the four dispatch runs of plan 07-03

## QLT-01 re-verification (plan 07-05)

### Freeze (Task 1)

- **Frozen sha the verifiers judge:** `81db888c5e49389ea7dc27626100f6e090535e61` (branch `gsd/phase-07-verification-stable-tests-and-pinned-ci`,
  `git status --porcelain` empty before this section was written; this ledger section is the only change after the freeze and
  touches no covered file)
- Preconditions: manifest version `1.0.0`; no local or remote tag `v1.0.1-rc1`; ledger holds `release run conclusion: success`

### Before state (`verification status ARCHIVED_DIR --pick status`)

| Phase | Archived directory | Status before | PLAN + SUMMARY files |
|-------|--------------------|---------------|----------------------|
| 1 | `.planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch` | stale | 12 |
| 2 | `.planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution` | stale | 10 |
| 3 | `.planning/milestones/v1.0-phases/03-trust-central-config-and-ownership` | stale | 16 |
| 4 | `.planning/milestones/v1.0-phases/04-operations-recovery-and-release` | stale | 28 |
| 5 (surfaced, out of scope) | `.planning/milestones/v1.0-phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco` | stale | 18 |

- `init.manager` lists only phases 6, 7, 8 and 999.1 (milestone v1.0.1); it never listed Phases 1 to 5, so it was vacuously
  clean (`verification_stale_check_indeterminate: false` for all four) and cannot be the gate.
- Phase 5 reads stale for the same cause (stored `covered_files` name pre-archive paths). QLT-01 names Phases 1 to 4 only, so it is
  not re-verified in this plan; surfaced for the owner.

### Result (Task 3): QLT-01 gate NOT fully met

The four `gsd-verifier` runs (orchestrator-spawned, Task 2) regenerated the four archived reports. `verification status
ARCHIVED_DIR --pick status` afterwards prints **human_needed, human_needed, human_needed, passed**, not four times `passed`.
No report has `gaps_found`: no truth regressed. Phases 1 to 3 read `human_needed` because the verifier found checks that only a
real HA frontend, a real HACS client or a real HA core with a real broker can make, and that Phase 8 (UAT-01 to UAT-04) does not name.

**Owner decision 2026-10-04:** these open human-verification items are **deferred to Phase 8 (UAT)**. They are not accepted as
overrides, and the reports were not edited to read `passed` (no frontmatter was changed by hand). The acceptance gate of plan
07-05 ("`passed` for all four") is therefore **not met for Phases 1 to 3**; it is met for Phase 4.

| Phase | Status before | Status after | Verified | Score | Covered files | Overrides | Open human items |
|-------|---------------|--------------|----------|-------|---------------|-----------|------------------|
| 1 | stale | **human_needed** | 2026-10-04T13:46:34Z | 8/8 | 54 | 1 | 6 |
| 2 | stale | **human_needed** | 2026-10-04T16:00:00Z | 10/10 | 46 | 1 | 2 |
| 3 | stale | **human_needed** | 2026-10-04T13:48:18Z | 5/5 | 83 | 1 | 2 |
| 4 | stale | **passed** | 2026-10-04T13:50:00Z | 5/5 | 102 | 2 | 0 |

Other checks: each report carries a `covered_digest: "v2:sha256:..."` line; no report lists a `.planning/phases/` path in
`covered_files` (0 of 0 in each); `git ls-files .planning/phases` holds no directory for Phases 1 to 5 (only 06, 07, 999.1);
`init.manager` lists phases 6 (passed), 7, 8 and 999.1 (missing, not yet verified) with `verification_stale_check_indeterminate: false`
and no stale phase (it still never listed Phases 1 to 4).

#### Items superseded by Phase 5 (D-03, `accepted_by: D-03 (owner decision, Phase 7 context, 2026-10-04)`)

- **Phase 1** (1): "The Switch appears in HA through MQTT Discovery (UUID unique_id, availability, device info)". Native entities
  replace Discovery as the default (ADR 0001, `docs/adr/0001-native-entities-instead-of-mqtt-discovery.md`); the unique_id stays the
  device UUID. Evidence: `tests/test_cutover.py::test_a_legacy_install_without_peers_cuts_over_after_the_settle_time`,
  `tests/test_native_entities.py::test_native_switch_is_registered_under_the_subentry`,
  `::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select`; compatibility path intact:
  `tests/test_native_entities.py::test_an_instance_without_the_native_flag_keeps_the_legacy_path`,
  `tests/test_discovery.py::test_discovery_creates_switch_entity`, `tests/test_tracer.py::test_switch_end_to_end`.
- **Phase 2** (1): "Plan truth 02-03: test-button lifecycle follows options (rename keeps unique_id, remove tombstones the entity,
  device delete clears all)". Native test buttons need no tombstone. Evidence:
  `tests/test_native_entities.py::test_removing_an_option_removes_its_native_button_entry`,
  `::test_a_native_device_subscribes_no_test_topic`, `::test_new_native_test_buttons_are_diagnostic_and_disabled_by_default`,
  `::test_an_existing_test_button_entry_is_left_as_it_is`, `::test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing`;
  legacy path: `tests/test_test_buttons.py::test_removed_option_removes_its_button_entity`,
  `::test_renamed_option_renames_button_and_keeps_unique_id`, `::test_delete_device_clears_buttons_with_the_discovery_clear`.
- **Phase 3** (1): "If a follower removes the discovered entity the owner republishes its discovery (roadmap truth 4, second
  clause; DSC-03)". A native device has no Discovery entity to remove. Evidence:
  `tests/test_native_cleanup.py::test_a_native_owner_never_heals_its_discovery`; legacy path:
  `tests/test_multi_instance.py::test_follower_entity_deletion_heals_the_discovery`,
  `tests/test_sync_owner.py::test_empty_discovery_for_an_owned_device_republishes_discovery`.
- **Phase 4** (2):
  - "Manual resync republishes config and discovery of all owned devices (ROADMAP SC3, DSC-04, discovery clause)". A native device
    publishes no Discovery on resync. Evidence: `tests/test_discovery_export.py::test_a_native_device_publishes_the_export_when_enabled`,
    `::test_the_export_is_off_by_default`,
    `tests/test_native_entities.py::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select`;
    config, availability and heartbeat still republished: `tests/test_hub_entities.py::test_resync_button_republishes_in_the_phase_3_order`,
    `tests/test_services.py::test_resync_service_republishes_in_the_phase_3_order`.
  - "Per instance and device mode selects live on a separate companion device (ROADMAP SC4 evidence, D-13, UAT test 4)". The
    companion device is merged into the native device (ADR 0001, "Cutover design"). Evidence:
    `tests/test_native_entities.py::test_the_mode_select_shares_the_device_of_the_native_entities`,
    `::test_a_marked_mirror_is_a_native_entity_directly_under_the_entry`,
    `tests/test_takeover.py::test_full_takeover_sequence_keeps_identity`, `::test_a_mirror_moves_directly_under_the_entry`;
    companion path for legacy instances still tested: `tests/test_companions.py`,
    `tests/test_modes.py::test_owned_device_has_a_companion_device_under_its_subentry`.

#### Open human-verification items: deferred to Phase 8 by owner decision 2026-10-04 (QLT-01 gate not fully met)

None of these is an override and none is marked verified. Each is a check no automated tier performs; the tests cited are the
automated coverage the verifier found for the surrounding behavior. Phase 4 has none (`human_verification: []`).

**Phase 1 (6 items, `human_needed`)**

1. HACS client install on a real host (custom repository, download, restart, add MQTT Actions, second add aborts, icon shown).
   Cited: `tests/test_repo_structure.py::test_manifest_has_hacs_required_keys`, `::test_hacs_json_keys_allowed_and_floor`,
   `::test_brand_icon_is_valid_png`; HACS validation green on the release run of `v1.0.1-rc1` (this ledger);
   `tests/test_config_flow.py::test_hub_flow_creates_entry_with_instance_id`, `::test_hub_flow_aborts_without_mqtt`,
   `::test_hub_flow_single_instance`. Earlier owner pass on the pre-Phase-5 build: 01-UAT.md test 1 (2026-09-29).
2. English and German strings in the real frontend (hub flow, Add switch device dialog, Repairs text). Cited:
   `tests/test_translations.py::test_en_and_de_have_identical_keys`, `::test_placeholders_match_between_languages`,
   `::test_required_keys_present` (240 flattened keys each). Earlier pass: 01-UAT.md test 2.
3. Action editor and validation banners in the current build (invalid YAML action, literal `device_id` submitted twice). Cited:
   `tests/test_config_flow.py::test_switch_flow_schema_serializes_action_selector`, `::test_switch_flow_rejects_invalid_actions`,
   `::test_switch_flow_device_id_warns_then_saves_on_resubmit`, `::test_switch_flow_entity_targets_do_not_warn`,
   `::test_switch_reconfigure_applies_validation_and_warning`, `tests/test_device_ids.py`. Earlier pass: 01-UAT.md test 3.
4. Repairs dialog of a failing action in the real frontend. Cited: `tests/test_manager.py::test_issue_created_when_action_fails`,
   `::test_issue_updated_in_place_on_repeated_failure`, `::test_issue_cleared_after_next_success`,
   `::test_issue_dismissed_stays_dismissed_while_failing`, `::test_issue_error_text_is_truncated`,
   `::test_issue_for_invalid_stored_actions_at_setup`, `tests/test_runner_modes.py::test_dropped_run_does_not_clear_failure_issue`.
   Earlier owner check was API-level only (01-UAT.md test 5).
5. Retained-versus-live chain on the current build with a real HA core MQTT client and a real retaining broker (toggle in UI, full
   HA restart, broker reconnect: no action run for replayed state). Cited: `tests/test_state.py`,
   `tests/test_manager.py::test_retain_replay_sets_baseline_without_actions`, `::test_retain_replay_after_reconnect_runs_nothing`,
   `::test_startup_flag_runs_retained_state_once`, `::test_startup_flag_not_reapplied_on_replay`,
   `::test_baseline_persisted_across_reload`, `::test_reload_keeps_single_subscription`,
   `::test_unload_publishes_offline_and_never_clears_discovery`, `tests/test_native_entities.py::test_the_echo_runs_the_actions_once`,
   `tests/broker/test_retain_semantics.py::test_replay_on_subscribe_has_retain_true`, `::test_live_forward_has_retain_false`,
   `::test_resubscribe_replays_last_value_with_retain_true`. Phase 8 UAT-02 and UAT-03 do not check this. Earlier partial pass:
   01-UAT.md test 4 (UI toggle, full restart and broker reconnect left open).
6. Core version of the second real host (hassio-n2plus, "Backup"): read it in Settings > About, expect 2026.9.0 or newer.
   Informational, no code consequence. Cited: `tests/test_toolchain.py::test_home_assistant_floor`, `::test_python_floor`,
   `tests/test_repo_structure.py::test_hacs_json_keys_allowed_and_floor`. 01-UAT.md test 9 (inferred only).

**Phase 2 (2 items, `human_needed`)**

1. Select subentry flow in the real frontend (add select device, three options, Done after two, reconfigure edit/add/remove, English
   and German). Cited: `tests/test_config_flow_select.py` (flow manager API), `tests/test_translations.py`. The owner pass of
   02-UAT.md (2026-09-30) predates later changes to `config_flow.py` and the translations, so it is not evidence for the final code.
2. Breaker loop (a device whose action flips its own state topic, 5 runs in 10 seconds) against a real Mosquitto and a real HA
   process, rendered Repairs card in English and German, release by reconfigure or reload, restart while paused. Cited:
   `tests/test_manager_breaker.py` (mqtt_mock and fake broker). Phase 8 UAT-03 does not name the breaker loop.

**Phase 3 (2 items, `human_needed`)**

1. Approval request of a mirrored device in the real frontend (Settings > Repairs) with a device name, owner name and action YAML
   containing backticks, underscores, pipes and a templated service name. Cited:
   `tests/test_repairs_flow.py::test_flow_shows_device_owner_yaml_hash_and_templates`,
   `::test_flow_states_the_startup_flag_the_hash_binds`, `::test_submit_approves_and_the_issue_disappears`, `tests/test_trust.py`.
   Earlier real-frontend evidence: 03-UAT.md test 1 (2026-10-02) and 04-UAT.md test 11; rendering sources unchanged since, not re-run
   at the frozen sha.
2. Delete of a device with a name containing backticks and `<b>` in a real frontend (own delete step and the generic core dialog,
   whose text an integration cannot change; documented limitation in the README). Cited:
   `tests/test_config_flow_escaping.py::test_delete_confirmation_shows_the_device_name_as_plain_text`,
   `tests/test_config_flow_delete.py`, `tests/test_multi_instance.py::test_delete_removes_the_device_everywhere`. Earlier
   real-frontend evidence: 03-UAT.md test 2 (retested after plan 03-08); dialog code and text unchanged since.

**Consequence for QLT-01 and success criterion 1:** the criterion "`verification status` prints `passed` for the four archived
directories" holds for Phase 4 only. Phases 1 to 3 stay `human_needed` until Phase 8 runs these ten checks (or the owner later
accepts any of them as an override under the owner's name) and the verifier or `/gsd-verify-work` is re-run. This is recorded
honestly; no status was edited. Phase 8 should add these ten checks to its UAT scope or its own owner decision should name them.

**Later edits (expected re-staling):** an edit of a file covered by a Phase 1 to 4 report (`tests/conftest.py`,
`tests/test_repo_structure.py`, `tests/test_manager_breaker.py`, `tests/test_hub_removal.py`, the three workflows, `manifest.json`)
turns that phase stale again; refresh the digest from `verification.fingerprint` with a dated note and re-check the status.
