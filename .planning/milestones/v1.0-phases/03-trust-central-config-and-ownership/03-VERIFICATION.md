---
phase: 03-trust-central-config-and-ownership
verified: 2026-10-04T13:48:18Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-01-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-01-SUMMARY.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-02-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-02-SUMMARY.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-03-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-03-SUMMARY.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-04-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-04-SUMMARY.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-05-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-05-SUMMARY.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-06-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-06-SUMMARY.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-07-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-07-SUMMARY.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-08-PLAN.md
  - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-08-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/breaker.py
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/presence.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/select.py
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
  - tests/__init__.py
  - tests/broker/__init__.py
  - tests/broker/conftest.py
  - tests/broker/test_acl.py
  - tests/broker/test_retain_semantics.py
  - tests/conftest.py
  - tests/documents.py
  - tests/fake_broker.py
  - tests/test_breaker.py
  - tests/test_config_flow.py
  - tests/test_config_flow_delete.py
  - tests/test_config_flow_escaping.py
  - tests/test_config_flow_select.py
  - tests/test_cutover_instances.py
  - tests/test_device_ids.py
  - tests/test_discovery.py
  - tests/test_discovery_select.py
  - tests/test_document.py
  - tests/test_fake_broker.py
  - tests/test_hub_removal.py
  - tests/test_manager.py
  - tests/test_manager_breaker.py
  - tests/test_manager_select.py
  - tests/test_model.py
  - tests/test_multi_instance.py
  - tests/test_native_cleanup.py
  - tests/test_native_entities.py
  - tests/test_repairs_flow.py
  - tests/test_repo_structure.py
  - tests/test_runner_modes.py
  - tests/test_state.py
  - tests/test_sync_follower.py
  - tests/test_sync_owner.py
  - tests/test_test_buttons.py
  - tests/test_toolchain.py
  - tests/test_topics.py
  - tests/test_tracer.py
  - tests/test_translations.py
  - tests/test_trust.py
covered_digest: "v2:sha256:d0b91d0e0ef912939cde4bab354091bfca2ae057d0428ea5476d52b395758214"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "If a follower removes the discovered entity the owner republishes its discovery (roadmap truth 4, second clause; DSC-03)"
    reason: "Superseded by Phase 5 (ADR 0001, D-03/D-11, MIG-03): native switch and select entities are the default, so a native device has no MQTT Discovery entity that a follower could remove and the owner heals nothing for it. The healing remains only on the legacy compatibility path. New behavior is proven by tests/test_native_cleanup.py::test_a_native_owner_never_heals_its_discovery; the legacy path is still proven by tests/test_multi_instance.py::test_follower_entity_deletion_heals_the_discovery and tests/test_sync_owner.py::test_empty_discovery_for_an_owned_device_republishes_discovery"
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T13:48:18Z"
re_verification:
  previous_status: passed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
gaps: []
advisory:
  - finding: "Iteration-2 WR-01: a document the pre-publish guard refuses (name over 64 characters from an old build, more than 256 KiB, nesting deeper than 32) is dropped with one log line; no Repairs issue, and followers keep running the previously approved retained document"
    category: other
    reason: "Still the behavior at the frozen sha (manager.py async_publish_config logs once per device and returns); only reachable beyond the bounds the device forms enforce. tests/test_multi_instance.py::test_overlong_name_is_not_published_and_never_loops pins the no-loop guarantee"
    evidence_status: "code read: manager.py async_publish_config except branch"
  - finding: "IN-05 (iteration 2): a foreign claim replayed during startup is healed without an ownership_claim issue"
    category: other
    reason: "Info-level; tests/test_multi_instance.py::test_foreign_claim_replayed_during_startup_never_becomes_a_mirror proves it never becomes a mirror and never runs"
    evidence_status: "code read: sync.py _async_ingest skips owned ids"
  - finding: "config_flow.py passes the action-check placeholders (field, error, device_ids) to form descriptions unescaped"
    category: other
    reason: "Deliberately outside plan 03-08; they feed form error alerts, not a Markdown description, and carry field names, HA validation text and device ids"
    evidence_status: "code read of config_flow.py _async_check_actions callers; not exercised in a frontend"
human_verification:
  - test: "Open the approval request of a mirrored device (Settings, Repairs) in a real Home Assistant frontend on the current build, using a device name, owner name and action YAML with backticks, underscores, pipes and a templated service name; submit once"
    expected: "Device, owner, short hash, startup flag, run mode and breaker limits, YAML in one code block, templated and residual lists, no injected markup; submit approves and the issue disappears; closing the dialog leaves the mirror paused"
    why_human: "Frontend rendering of Markdown cannot be asserted by the pytest tiers. tests/test_repairs_flow.py::test_flow_shows_device_owner_yaml_hash_and_templates, test_flow_states_the_startup_flag_the_hash_binds and test_submit_approves_and_the_issue_disappears pin the placeholder content, tests/test_trust.py pins the gate, but no test renders it, and Phase 8 (UAT-01..04) does not name this dialog. Real-frontend evidence exists only from earlier UAT runs (03-UAT.md test 1, 2026-10-02; 04-UAT.md test 11 after plan 04-02 added the bound-settings paragraph); the rendering sources (trust.py, repairs.py approval flow, approval translation text) are unchanged since those runs, but it was not re-run at the frozen sha"
  - test: "Delete a device with a name containing backticks and <b> from the subentry menu in a real frontend: look at the integration's own delete menu step and at the generic Home Assistant delete dialog"
    expected: "The own step names the device as plain text and states removal on all connected instances with the online count; the generic dialog is core's text only (documented limitation, README Limitations)"
    why_human: "Frontend rendering and the wording of a core dialog that an integration cannot change. tests/test_config_flow_escaping.py::test_delete_confirmation_shows_the_device_name_as_plain_text, tests/test_config_flow_delete.py and tests/test_multi_instance.py::test_delete_removes_the_device_everywhere pin the placeholders and the effect, but no test renders the dialog and Phase 8 does not name it. Real-frontend evidence: 03-UAT.md test 2 (retested after plan 03-08, 0 code spans and 0 injected elements); the dialog code and its translation text are unchanged since that retest, not re-run at the frozen sha"
---

# Phase 3: Trust, Central Config and Ownership Verification Report

**Phase Goal:** As a user with several HA instances, I want devices created on one instance to appear on the others once I approve them, so that every instance runs the actions locally.
**Verified:** 2026-10-04T13:48:18Z
**Status:** human_needed
**Re-verification:** Yes - against the final code of the v1.0 milestone work (frozen sha `81db888c5e49389ea7dc27626100f6e090535e61`, which contains Phases 4, 5, 6 and the Phase 7 test and CI changes), after the previous `passed` report of 2026-10-02 had gone stale

## Goal Achievement

The goal is achieved in the code at the frozen sha. An owner publishes one retained, validated document per device; followers build read-only mirrors that run nothing until the user approves the exact action hash in Repairs; after approval a state change runs the actions locally on every approving instance; only the owner can delete, and deletion propagates as a tombstone. Since this report was last written, Phase 5 made native switch and select entities the default way those mirrors and owned devices appear (ADR 0001), and Phase 4 widened the approval hash. Neither weakened a Phase 3 guarantee; one clause (discovery healing) was replaced on purpose and is recorded as an override below.

The status is `human_needed` and not `passed` for one reason only: two real-frontend rendering checks (the approval dialog and the integration's own delete dialog) have no automated test and are not named by Phase 8 (UAT-01..04). They passed in earlier real UAT runs on source that is unchanged, but they were not re-run at the frozen sha, and an assumption is not evidence. No truth failed and nothing regressed.

How the evidence was produced: the code was read at the frozen sha (HEAD adds only a ledger commit under `.planning/`; `git diff 81db888 HEAD` touches `07-PROOF.md` only). `git diff 0f9ad70 81db888 -- custom_components tests .github pyproject.toml uv.lock README.md docs` is empty, so the Phase 7 proof ledger (`.planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md`) applies to this code: three local full-suite runs `1490 passed` (111.42 s, 111.42 s, 110.26 s), three CI dispatch runs on ubuntu-24.04 (1308 unit + 17 broker + 165 multi-instance, all success), Validate (hassfest, HACS `All (9) checks passed`) and the release run on `v1.0.1-rc1` with 8 successful jobs. On top of that this run executed the targeted Phase 3 tiers itself (see Behavioral Spot-Checks).

### Observable Truths (roadmap contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A device created on one instance is published as one retained, versioned config document; a second instance creates the same device as a read-only mirror; the owner republishes on every reconnect; a missing message never deletes a mirror (only tombstone or grace window) | VERIFIED | `document.py` `build_document` (schema_version, owner, rev, hash, content) and `parse_document`; `manager.py` `async_publish_config` (rev grows only when the hash changes, parse-before-publish guard) and `_async_republish`; `sync.py` `_async_ingest_locked` creates mirrors via `manager.async_apply_mirror`, `_async_remove` only on a tombstone, `_async_prune` only for mirrors not seen since reconnect whose pinned owner is ONLINE. Tests (run now, pass): `tests/test_multi_instance.py::test_follower_mirrors_the_owners_device`, `::test_absence_alone_never_removes_a_mirror`, `::test_prune_waits_for_the_owner_to_be_online`, `::test_reconnect_republishes_config_before_availability`, `::test_wiped_broker_heals_without_pruning`, `tests/test_sync_follower.py::test_absence_alone_never_removes_a_mirror_single_instance`. The mirror is a native entity directly under the hub entry by default: `tests/test_native_entities.py::test_a_marked_mirror_is_a_native_entity_directly_under_the_entry` |
| 2 | A mirror's actions do not run until approved in Repairs; approval is bound to the action hash so changed actions need re-approval; every broker action sequence is schema-validated; denylisted services are refused at execution time; docs include a broker ACL example binding each instance to its own topics | VERIFIED | `manager.py` `async_approve` stores the approval only when the shown hash equals `info.actions_hash`; `_async_refresh_mirror_script` builds a Script only when `_approvals.get(device_id) == info.actions_hash` and always `restricted=True` (`runner.py` -> `trust.guard_actions` / `GuardedTemplate` raises `DeniedServiceCallError` at render time). `sync.py` `_async_ingest_locked` runs `parse_document` and `validate_spec_structure` on every received document. `document.py` `actions_hash` now binds kind, startup flag, run mode, breaker limits and the trigger mapping. Tests: `tests/test_trust.py::test_unapproved_mirror_runs_nothing`, `::test_approval_requires_the_current_hash`, `::test_changed_actions_lapse_the_approval`, `::test_run_mode_or_breaker_change_lapses_the_approval`, `::test_rename_keeps_the_approval`, `::test_blocked_mirror_is_not_approvable_and_never_built`; `tests/test_document.py::test_actions_hash_binds_mapping_startup_run_mode_and_breaker`; `tests/test_repairs_flow.py::test_submit_approves_and_the_issue_disappears`; `tests/test_multi_instance.py::test_owner_edit_requires_reapproval_on_followers`. `docs/broker-acl.md` is the tested block: `tests/broker/test_acl.py::test_documented_acl_block_is_the_tested_acl` and 12 sibling tests on a real Mosquitto (run now with `MQTT_ACTIONS_REQUIRE_BROKER=1`, none skipped) |
| 3 | After approval, a real state change (HA UI on any instance or an external MQTT message) runs the actions locally on every participating instance | VERIFIED | Legacy path: `tests/test_multi_instance.py::test_fanout_runs_on_every_approved_instance_and_only_there` (owner A, approving B, non-approving C) and `::test_approved_mirror_runs_actions_on_both_instances`. Native default path (Phase 5): `tests/test_cutover_instances.py::test_a_native_toggle_runs_the_actions_on_every_instance`. Both pass in this run and in the three full-suite runs of the ledger. Real two-instance confirmation of the command path is Phase 8 UAT-03 |
| 4 | Only the owner can edit or delete; followers pin the owner and raise a Repairs issue on conflicting claims; if a follower removes the discovered entity the owner republishes its discovery | VERIFIED for the first two clauses; third clause PASSED (override), superseded by Phase 5 | Mirrors are not subentries, so there is no edit or delete path; `sync.py` `_may_repin`/`_conflict` pin the first owner and raise the conflict issue: `tests/test_sync_follower.py::test_pinned_owner_ignores_another_owner`, `tests/test_multi_instance.py::test_ownership_conflict_between_three_instances`, `::test_foreign_claim_replayed_during_startup_never_becomes_a_mirror`, `::test_forged_tombstone_followers_recover_unapproved`. Third clause: see "Superseded by Phase 5" below |
| 5 | Deleting a device requires an explicit confirmation stating it is removed on all connected instances, after which its central config and discovery are unpublished and the device disappears everywhere | VERIFIED | `config_flow.py` `async_step_delete_device` is a menu whose only options are `delete_confirmed` and `keep_device`, with the escaped `name` placeholder (`escape_markdown`, six call sites in the file) and the online-instance count. `manager.py` `_async_remove_device` takes the device out of `devices` first, then clears discovery (core topic and the export prefix when on), unsubscribes, clears the config document (tombstone) and clears the retained state; a failed clear keeps the id in the published set for a retry. Tests: `tests/test_config_flow_delete.py`, `tests/test_config_flow_escaping.py::test_delete_confirmation_shows_the_device_name_as_plain_text`, `tests/test_multi_instance.py::test_delete_removes_the_device_everywhere`, `::test_owner_delete_removes_the_mirror_everywhere`, `tests/test_native_cleanup.py::test_deleting_a_native_device_clears_everything_and_removes_its_entities`, `::test_deleting_a_native_mirror_removes_its_device_and_entities`. The generic HA delete button cannot be vetoed or given custom text; the limitation is documented in README Limitations (line 283) and was accepted by the owner in 03-UAT test 2 |

**Score:** 5/5 roadmap truths verified (one clause of truth 4 counted through the D-03 override; 0 behavior-unverified).

Behavior-dependent truths (state transitions and ordering invariants: absence never deletes, approval gate, delete order, owner pinning) each have a passing behavioral test named above, so none is left at presence-only.

### Superseded by Phase 5 (D-03)

| Item | Old behavior | What replaced it | Evidence | Disposition |
|------|--------------|------------------|----------|-------------|
| Roadmap truth 4, third clause, and requirement DSC-03: "if a follower removes the discovered entity the owner republishes its discovery" | The device reached every instance as a core MQTT Discovery device; deleting one entity on a follower made core clear the whole discovery topic, and the owner healed it (throttled, Repairs hint after repeated removals) | Native switch and select entities owned by the hub entry are the default (ADR 0001, `docs/adr/0001-native-entities-instead-of-mqtt-discovery.md`, Status Accepted); a native device has no discovery to heal. Healing is gated by `Manager.heals_discovery()` and `sync.py` `_on_discovery_message` / `_start_discovery_heal`, so it runs only for an owned device still on the legacy path. REQUIREMENTS.md DSC-03 carries the Phase 5 annotation "applies to the legacy path and the optional export" | New behavior: `tests/test_native_cleanup.py::test_a_native_owner_never_heals_its_discovery` (native device: no republish, no removed-issue; legacy device next to it: healed, issue raised) and `::test_the_takeover_clear_is_not_a_foreign_removal`. Compatibility path still proven: `tests/test_multi_instance.py::test_follower_entity_deletion_heals_the_discovery`, `tests/test_sync_owner.py::test_empty_discovery_for_an_owned_device_republishes_discovery`, `::test_discovery_republish_is_throttled_with_one_trailing_republish` | Recorded as an `overrides` entry, `accepted_by: D-03 (owner decision, Phase 7 context, 2026-10-04)`. Not a regression |

The other Phase 3 behaviors that Phase 5 touched were checked and are not superseded: mirror creation and removal, approval, fan-out, ownership pinning and deletion all still hold (Truths 1 to 5 above), only the mechanism that shows the entities changed. The earlier report's evidence "device appears on B through core MQTT Discovery" describes the legacy mechanism; the truth itself ("creates the same device as a read-only mirror") is met by the native mirror and by the legacy path.

### Human-verification items of the previous report (D-04)

The previous report named five items, all resolved by `03-UAT.md` (5 of 5 pass, 2026-10-02) on the code of that day. Each is covered by the automated tier that exercises it; what only a real client can show is stated separately.

| # | Item of the previous report | Automated tier and test node ids | Real-instance/real-client part | Result |
|---|-----------------------------|----------------------------------|--------------------------------|--------|
| 1 | Approval dialog renders in a real Repairs frontend | `tests/test_repairs_flow.py::test_flow_shows_device_owner_yaml_hash_and_templates`, `::test_flow_states_the_startup_flag_the_hash_binds`, `::test_submit_approves_and_the_issue_disappears`, `::test_too_long_actions_refuse_approval`; `tests/test_trust.py::test_approval_requires_the_current_hash`; `tests/test_document.py::test_approval_sections_label_and_omit_empty` | Markdown rendering in the real frontend: not automatable here, not named by Phase 8 | **human_needed** (item 1 below) |
| 2 | Generic HA subentry delete dialog vs the integration's own confirmation (SYN-06) | `tests/test_config_flow_delete.py`, `tests/test_config_flow_escaping.py::test_delete_confirmation_shows_the_device_name_as_plain_text`, `::test_select_menu_escapes_the_name_and_every_option_line`, `tests/test_multi_instance.py::test_delete_removes_the_device_everywhere`, `tests/test_native_cleanup.py::test_deleting_a_native_device_clears_everything_and_removes_its_entities` | Rendering of the own dialog and the wording of core's generic dialog: not automatable, not named by Phase 8; the limitation itself is documented in the README and the owner accepted it in 03-UAT test 2 | **human_needed** (item 2 below) |
| 3 | Two real HA instances on one real Mosquitto with `docs/broker-acl.md`: device appears on B, approval request, discovery republished after a follower delete, toggle runs on both | Broker ACL on a real Mosquitto: `tests/broker/test_acl.py::test_documented_acl_block_is_the_tested_acl` and the other tests of that file; retain semantics: `tests/broker/test_retain_semantics.py`; two and three instances on the fake broker: `tests/test_multi_instance.py::test_follower_mirrors_the_owners_device`, `::test_fanout_runs_on_every_approved_instance_and_only_there`; follower side: `tests/test_sync_follower.py`; native toggle: `tests/test_cutover_instances.py::test_a_native_toggle_runs_the_actions_on_every_instance`. The discovery-republish step is the superseded legacy path (override above) | Real HA instances: the command running exactly once on every approved real instance is Phase 8 UAT-03 | Covered; no open item |
| 4 | Hub removal with the delete option on and off | `tests/test_hub_removal.py`, `tests/test_sync_owner.py::test_hub_removal_path_clears_the_config_topic`, `tests/test_multi_instance.py::test_hub_removal_delete_clears_everywhere_for_followers`, `::test_hub_removal_keep_leaves_orphans_that_followers_keep`, `tests/test_native_cleanup.py::test_hub_removal_clears_the_export_topics_too` | none beyond what 03-UAT test 4 and 05-UAT test 8 recorded | Covered; no open item |
| 5 | Lock scope in `Manager.async_start` (CR-02 fix) | Ordering invariant the lock exists for: `tests/test_multi_instance.py::test_foreign_claim_replayed_during_startup_never_becomes_a_mirror`; start, stop and reconnect: `tests/test_sync_owner.py::test_stop_releases_subscription_and_timers`, `tests/test_manager.py::test_reconcile_after_stop_does_not_revive_manager`; every manager test starts through `async_start` (now with the takeover pass inside the same lock), so a self-deadlock would hang the suite, which ran green three times | `manager.py` lines 766-806 read at the frozen sha: one `async with self._lock` from the first subscribe to the end of the publish; no nested acquisition. A slow-broker stop delay is not exercised by a test; the UAT item was marked optional | Covered; residual noted, no open item |

### Deferred Items

None.

### Advisory (New Scope, Unevidenced)

| # | Finding | Category | Why Advisory |
|---|---------|----------|--------------|
| 1 | Unpublishable document (iteration-2 WR-01) is dropped with a log line only | other | Unchanged; reachable only beyond the form limits or with pre-CR-03 names |
| 2 | Foreign claim replayed during startup is healed without an ownership_claim issue (IN-05) | other | Info; it never becomes a mirror and never runs |
| 3 | Action-check placeholders (`field`, `error`, `device_ids`) not escaped | other | Deliberately out of 03-08 scope; not free user text |

Carried-over items from the previous report that are now resolved in the code at the frozen sha: WR-04 (run mode and breaker limits outside the approval hash) is closed, `document.py` `actions_hash` binds them, `tests/test_trust.py::test_run_mode_or_breaker_change_lapses_the_approval` and `tests/test_document.py::test_actions_hash_binds_mapping_startup_run_mode_and_breaker` pass, and the README sentence (lines 224-227) now states exactly what the hash covers; IN-01 (`repairs.py` imported `voluptuous`) is closed, line 13 reads `import probatio`; IN-02 (cached mirrors with an invalid id) is closed, `manager.py` `_parse_mirrors` checks `is_valid_device_id` (line 365).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/document.py` | Wire contract, hashes, strict parser, denylist walker, `escape_markdown` | VERIFIED | 586 lines; used by manager, sync, runner, trust, repairs and config_flow |
| `custom_components/mqtt_actions/sync.py` | Owner defense, follower ingest, tombstone, prune, presence | VERIFIED | 777 lines; ingest, remove, prune, conflict and legacy healing paths read |
| `custom_components/mqtt_actions/trust.py` | `GuardedTemplate`, `ApprovalView`, approval states | VERIFIED | 211 lines, wired from runner, manager and repairs |
| `custom_components/mqtt_actions/repairs.py` | Approval fix flow | VERIFIED | 171 lines; `ApprovalRepairFlow` binds the shown hash |
| `custom_components/mqtt_actions/manager.py` | Owner publish, mirrors, approvals, delete order | VERIFIED | 2532 lines; `async_approve`, `_async_refresh_mirror_script`, `async_publish_config`, `_async_remove_device`, `async_remove_mirror` read |
| `custom_components/mqtt_actions/config_flow.py` | Delete menu, hub options, escaped placeholders | VERIFIED | 672 lines; delete menu and six `escape_markdown` call sites |
| `docs/broker-acl.md` + `tests/broker/test_acl.py` | Tested ACL | VERIFIED | 17 broker-tier tests (13 ACL, 4 retain semantics) pass on a real Mosquitto (`MQTT_ACTIONS_REQUIRE_BROKER=1`) |
| `README.md` | Multi-instance, trust, deletion, limitations | VERIFIED | trust paragraph (lines 223-227) and generic delete dialog limitation (line 283) present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sync.py` | `document.py` / `actions.py` | `parse_document` then `validate_spec_structure` before `async_apply_mirror` | WIRED | `_async_ingest_locked` |
| `manager.py` | `runner.py` / `trust.py` | restricted Script build only when the approved hash equals the actions hash | WIRED | `_async_refresh_mirror_script`; `runner.async_build_device(..., restricted=True)` -> `guard_actions` |
| `repairs.py` | `manager.py` | `async_approval_view`, then `async_approve` with the displayed hash | WIRED | `ApprovalRepairFlow` |
| `config_flow.py` | `document.py` | `from .document import escape_markdown` | WIRED | line 54, six call sites |
| `manager.py` | `sync.py` | `heals_discovery()` gates discovery healing to the legacy path | WIRED | `sync.py` lines 723 and 757 |
| `tests/broker/test_acl.py` | `docs/broker-acl.md` | extracts the fenced `acl` block | WIRED | `test_documented_acl_block_is_the_tested_acl` passes |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Delete dialog `name` | subentry title | `_get_reconfigure_subentry().title` through `escape_markdown` | Yes | FLOWING |
| Approval dialog values | `ApprovalView` | `build_approval_view(spec, info, ...)` from the parsed mirror document | Yes | FLOWING |
| Mirror `Device.spec` | parsed document | retained message -> `parse_document` -> `async_apply_mirror` | Yes | FLOWING |
| Native mirror entities | `device.value` | shared retained state topic -> `_on_message` -> dispatcher | Yes (`test_a_native_toggle_runs_the_actions_on_every_instance`) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 3 tiers (broker, multi-instance, follower, owner, trust, repairs, document, escaping, delete, native cleanup, hub removal, native entities) | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider tests/broker tests/test_multi_instance.py tests/test_sync_follower.py tests/test_sync_owner.py tests/test_trust.py tests/test_repairs_flow.py tests/test_document.py tests/test_config_flow_escaping.py tests/test_config_flow_delete.py tests/test_native_cleanup.py tests/test_hub_removal.py tests/test_native_entities.py` | `480 passed in 50.11s` | PASS |
| Native cutover, export, takeover and the formerly flaky test | `uv run --locked pytest -q -p no:cacheprovider tests/test_cutover_instances.py tests/test_cutover.py tests/test_native_start.py tests/test_discovery_export.py tests/test_takeover.py tests/test_sync_owner.py::test_hub_removal_path_clears_the_config_topic tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` | `105 passed in 13.00s` | PASS |
| Whole suite, stability, CI | cited from `07-PROOF.md` (code identical to the frozen sha) | 3 local runs `1490 passed`; 3 CI dispatch runs success (1308 + 17 + 165); Validate success; release run on `v1.0.1-rc1` success, 8 jobs | PASS (cited) |
| Lint and format | `uv run ruff check .`, `uv run ruff format --check .` | `All checks passed!`, `91 files already formatted` | PASS |
| Debt markers (TBD/FIXME/XXX/TODO/HACK) in `custom_components`, `tests`, `docs`, `README.md`, `.github` | grep | none | PASS |

### Probe Execution

SKIPPED: no `probe-*.sh` scripts exist and none are declared in the Phase 3 plans; the verification tooling is the pytest suite above.

### Requirements Coverage

All 12 phase IDs are mapped to Phase 3 in `.planning/milestones/v1.0-REQUIREMENTS.md` (checked `[x]`, traceability rows Complete). No orphaned Phase 3 requirement.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SYN-01 | 03-01 | Owner publishes one retained, versioned config document per device | SATISFIED | `build_document`, `async_publish_config`; `tests/test_document.py`, `tests/test_sync_owner.py` |
| SYN-02 | 03-04 | Other instance creates read-only mirrors | SATISFIED | `async_apply_mirror`; `test_follower_mirrors_the_owners_device`; native mirror test |
| SYN-03 | 03-02, 03-04 | One owner; only owner edits/deletes; pinning and Repairs on conflict | SATISFIED | no edit/delete path for mirrors; conflict tests (cooperative at the broker, documented in `docs/broker-acl.md`) |
| SYN-04 | 03-01, 03-07 | Owner republishes on every reconnect | SATISFIED | `_async_republish`; `test_reconnect_republishes_config_before_availability` |
| SYN-05 | 03-05, 03-07 | Absence never deletes; tombstone or grace window | SATISFIED | `_async_prune` conditions; absence and prune tests |
| SYN-06 | 03-02, 03-03, 03-07, 03-08 | Delete requires confirmation naming all instances, then unpublishes config and discovery | SATISFIED | own delete step with count and escaped name; delete-order tests; generic dialog limitation documented and accepted. Rendering of the dialogs is human item 2 |
| TRU-01 | 03-04, 03-06 | Remote actions not executed by default | SATISFIED | no Script without matching approval; `test_unapproved_mirror_runs_nothing` |
| TRU-02 | 03-06 | Approval per instance via Repairs, bound to the hash | SATISFIED | `ApprovalRepairFlow`, `async_approve`; hash now also binds run mode and breaker. Rendering is human item 1 |
| TRU-03 | 03-01, 03-04, 03-06 | Schema validation and execution-time denylist | SATISFIED | `validate_spec_structure` at ingest, `GuardedTemplate` at run time; `tests/test_trust.py`, `tests/test_document.py` |
| TRU-04 | 03-07 | Docs include a broker ACL example per instance | SATISFIED | `docs/broker-acl.md`, tested on a real Mosquitto |
| STA-03 | 03-04, 03-06, 03-07 | Actions run locally on every participating instance | SATISFIED | fan-out tests on the legacy and the native path |
| DSC-03 | 03-02 | Owner republishes discovery removed by a follower | SATISFIED on the legacy path; superseded as default by Phase 5 | override above; REQUIREMENTS.md carries the Phase 5 annotation |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `custom_components/mqtt_actions/manager.py` | `async_publish_config` except branch | Unpublishable document dropped with a log line only | Info | Owner sees no Repairs issue (advisory 1) |
| `custom_components/mqtt_actions/sync.py` | `_async_ingest` owned-id skip | Foreign claim replayed during startup healed without an issue | Info | Missing diagnostic only (advisory 2) |

No blocker anti-patterns, no stubs, no unreferenced debt markers.

### Human Verification Required

#### 1. Approval dialog in a real Repairs frontend

**Test:** On a real Home Assistant instance on the current build, let a mirrored device with a hostile-looking name, owner name and action YAML (backticks, underscores, pipes, a templated service name) raise its approval request; open it from Settings, Repairs; submit once, and separately close it without submitting.
**Expected:** Device, owner, short hash, startup flag, run mode and breaker limits, the YAML in one code block, the templated and residual lists, no injected markup; submit approves and the issue disappears; closing leaves the mirror paused.
**Why human:** Markdown rendering in the real frontend is not covered by any test, and Phase 8 (UAT-01..04) does not name this dialog. The pytest tiers pin the placeholder content and the approval gate. Earlier real-frontend runs passed (03-UAT.md test 1; 04-UAT.md test 11 after plan 04-02) on source that is unchanged since (`trust.py`, the approval flow in `repairs.py`, the approval translation text), but it was not re-run at the frozen sha. The owner can accept this as an override under the owner's name, or add it to Phase 8.

#### 2. Own delete dialog and the generic delete dialog

**Test:** In a real frontend, delete a device whose name contains backticks and `<b>bold</b>` from the subentry menu: open the integration's own Delete step and, separately, press the generic Home Assistant delete button of the subentry.
**Expected:** The own step shows the name as plain text and states removal on all connected instances with the online count; the generic dialog shows only core's text (documented limitation, README Limitations).
**Why human:** Frontend rendering and the wording of a core dialog that an integration cannot change; no test renders them and Phase 8 does not name them. `tests/test_config_flow_escaping.py` and `tests/test_config_flow_delete.py` pin the placeholders, the delete effect is automated. Real-frontend evidence: 03-UAT.md test 2 (retested after plan 03-08, 0 code spans, 0 injected elements); the dialog code and translation text are unchanged since, not re-run at the frozen sha. The owner can accept this as an override, or add it to Phase 8.

### Gaps Summary

No gaps and no regression. Every roadmap success criterion is implemented, wired and backed by passing tests at the frozen sha (480 Phase 3 tests run now plus the 1490-test full-suite proof, three CI runs and the release run of Phase 7). One clause (discovery healing after a follower removes the entity) was replaced on purpose by Phase 5 and is recorded as a D-03 override with the new behavior's test. The report stays `human_needed` because two real-frontend rendering checks have no automated test and no Phase 8 item; both passed in earlier real UAT on unchanged source and need only the owner's acceptance or a Phase 8 line to close.

---

_Verified: 2026-10-04T13:48:18Z_
_Verifier: Claude (gsd-verifier)_
