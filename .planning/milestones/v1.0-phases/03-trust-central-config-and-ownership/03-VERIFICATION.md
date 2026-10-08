---
phase: 03-trust-central-config-and-ownership
verified: 2026-10-08T19:09:17Z
status: passed
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
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md
  - .planning/phases/08-real-instance-verification/08-UAT.md
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
covered_digest: "v3:sha256:2e88c06b594c9bf91a2a0703b307fb867b969ea7af60378c61c24b11d57e6efd"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "If a follower removes the discovered entity the owner republishes its discovery (roadmap truth 4, second clause; DSC-03)"
    reason: "Superseded by Phase 5 (ADR 0001, D-03/D-11, MIG-03): native switch and select entities are the default, so a native device has no MQTT Discovery entity that a follower could remove and the owner heals nothing for it. The healing remains only on the legacy compatibility path. New behavior is proven by tests/test_native_cleanup.py::test_a_native_owner_never_heals_its_discovery; the legacy path is still proven by tests/test_multi_instance.py::test_follower_entity_deletion_heals_the_discovery and tests/test_sync_owner.py::test_empty_discovery_for_an_owned_device_republishes_discovery"
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T13:48:18Z"
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
gaps: []
advisory:
  - finding: "Iteration-2 WR-01: a document the pre-publish guard refuses (name over 64 characters from an old build, more than 256 KiB, nesting deeper than 32) is dropped with one log line; no Repairs issue, and followers keep running the previously approved retained document"
    category: other
    reason: "Still the behavior at the build sha (manager.py async_publish_config logs once per device and returns); only reachable beyond the bounds the device forms enforce. tests/test_multi_instance.py::test_overlong_name_is_not_published_and_never_loops pins the no-loop guarantee"
    evidence_status: "code read: manager.py async_publish_config except branch"
  - finding: "IN-05 (iteration 2): a foreign claim replayed during startup is healed without an ownership_claim issue"
    category: other
    reason: "Info-level; tests/test_multi_instance.py::test_foreign_claim_replayed_during_startup_never_becomes_a_mirror proves it never becomes a mirror and never runs"
    evidence_status: "code read: sync.py _async_ingest skips owned ids"
  - finding: "config_flow.py passes the action-check placeholders (field, error, device_ids) to form descriptions unescaped"
    category: other
    reason: "Deliberately outside plan 03-08; they feed form error alerts, not a Markdown description, and carry field names, HA validation text and device ids"
    evidence_status: "code read of config_flow.py _async_check_actions callers; not exercised in a frontend"
resolved_human_items:
  - item: "1. Approval dialog in a real Repairs frontend"
    resolved_by: "08-UAT.md block 13 (P3-1), result: pass"
    evidence: ".planning/phases/08-real-instance-verification/08-evidence/p3-1"
    sha: "b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3"
    date: "2026-10-07"
  - item: "2. Own delete dialog and the generic delete dialog"
    resolved_by: "08-UAT.md block 14 (P3-2), result: pass"
    evidence: ".planning/phases/08-real-instance-verification/08-evidence/p3-2"
    sha: "b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3"
    date: "2026-10-06"
---

# Phase 3: Trust, Central Config and Ownership Verification Report

**Phase Goal:** As a user with several HA instances, I want devices created on one instance to appear on the others once I approve them, so that every instance runs the actions locally.
**Verified:** 2026-10-08T19:09:17Z
**Status:** passed
**Re-verification:** Yes - against the current code at the Phase 8 build sha `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`, using the real-instance evidence of Phase 8. The previous report (2026-10-04, `human_needed`, frozen sha `81db888c5e49389ea7dc27626100f6e090535e61`) left exactly two real-frontend items open; both are now resolved by Phase 8 ledger blocks.

## Goal Achievement

The goal is achieved in the code at the build sha. An owner publishes one retained, validated document per device; followers build read-only mirrors that run nothing until the user approves the exact action hash in Repairs; after approval a state change runs the actions locally on every approving instance; only the owner can delete, and deletion propagates as a tombstone. Native switch and select entities (Phase 5, ADR 0001) are the default way mirrors and owned devices appear; that replaced one clause on purpose (discovery healing) and is recorded as the D-03 override below.

How the evidence was produced:

- **Code identity.** `git diff --stat 81db888 b7f52b3 -- custom_components tests .github pyproject.toml uv.lock README.md docs` and `git diff --stat b7f52b3 HEAD -- <same paths>` are both empty. The code, tests, workflow and docs of the previous report, of the Phase 8 bench build (`build.txt`: sha `b7f52b34...`, `custom_components` mounted read-only and byte-identical on ha-a and ha-b, HA 2026.9.4) and of the current HEAD are the same. The Phase 7 proof (`07-PROOF.md`, code-identical to this tree through the previous report's `0f9ad70` to `81db888` check) therefore applies: three local full-suite runs `1490 passed`, three CI dispatch runs on ubuntu-24.04 (1308 unit + 17 broker + 165 multi-instance, all success), Validate (hassfest, HACS `All (9) checks passed`).
- **Run now.** The targeted Phase 3 tiers (see Behavioral Spot-Checks) passed in this run: `484 passed in 51.50s`, with `MQTT_ACTIONS_REQUIRE_BROKER=1` so the real-Mosquitto tier could not skip. Ruff: `All checks passed!`. No debt marker (TBD/FIXME/XXX/TODO/HACK) in `custom_components`, `tests`, `docs`, `README.md`, `.github`.
- **Code read now.** `manager.py` (`async_approve` line 1406, `heals_discovery` line 655, `is_valid_device_id` guards in `_parse_mirrors`, `runner.async_build_device(..., restricted=True)` line 1782), `config_flow.py` (`async_step_delete_device` line 230, `escape_markdown` import plus six call sites), `README.md` (generic delete dialog limitation, line 283).

No truth failed, nothing regressed, and no human item is open.

### Observable Truths (roadmap contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A device created on one instance is published as one retained, versioned config document; a second instance creates the same device as a read-only mirror; the owner republishes on every reconnect; a missing message never deletes a mirror (only tombstone or grace window) | VERIFIED | `document.py` `build_document` / `parse_document`; `manager.py` `async_publish_config` (rev grows only when the hash changes, parse-before-publish guard) and `_async_republish`; `sync.py` `_async_ingest_locked` creates mirrors, `_async_remove` only on a tombstone, `_async_prune` only for mirrors not seen since reconnect whose pinned owner is online. Tests (run now, pass): `tests/test_multi_instance.py::test_follower_mirrors_the_owners_device`, `::test_absence_alone_never_removes_a_mirror`, `::test_prune_waits_for_the_owner_to_be_online`, `::test_reconnect_republishes_config_before_availability`, `::test_wiped_broker_heals_without_pruning`, `tests/test_sync_follower.py::test_absence_alone_never_removes_a_mirror_single_instance`; native mirror: `tests/test_native_entities.py::test_a_marked_mirror_is_a_native_entity_directly_under_the_entry`. Real instances: Phase 8 P3-1 imported a device on ha-b (owner) and ha-a (follower) raised its approval request for it (`08-evidence/p3-1`) |
| 2 | A mirror's actions do not run until approved in Repairs; approval is bound to the action hash so changed actions need re-approval; every broker action sequence is schema-validated; denylisted services are refused at execution time; docs include a broker ACL example binding each instance to its own topics | VERIFIED | `manager.py` `async_approve` stores the approval only when the shown hash equals the current actions hash; the mirror Script is built only when the approved hash matches and always `restricted=True` (`trust.guard_actions` / `GuardedTemplate`). `sync.py` runs `parse_document` and `validate_spec_structure` on every received document. `document.py` `actions_hash` binds kind, startup flag, run mode, breaker limits and the trigger mapping. Tests (run now): `tests/test_trust.py::test_unapproved_mirror_runs_nothing`, `::test_approval_requires_the_current_hash`, `::test_changed_actions_lapse_the_approval`, `::test_run_mode_or_breaker_change_lapses_the_approval`, `::test_blocked_mirror_is_not_approvable_and_never_built`; `tests/test_document.py::test_actions_hash_binds_mapping_startup_run_mode_and_breaker`; `tests/test_repairs_flow.py::test_submit_approves_and_the_issue_disappears`; `tests/test_multi_instance.py::test_owner_edit_requires_reapproval_on_followers`. `docs/broker-acl.md` is the tested block: `tests/broker/test_acl.py::test_documented_acl_block_is_the_tested_acl` and the other broker tests on a real Mosquitto. Real instances: the P3-1 mirror on ha-a was never approved and stayed an approval request (`list_issues` after the captures, `p3-1/screens.txt`) |
| 3 | After approval, a real state change (HA UI on any instance or an external MQTT message) runs the actions locally on every participating instance | VERIFIED | Legacy path: `tests/test_multi_instance.py::test_fanout_runs_on_every_approved_instance_and_only_there`, `::test_approved_mirror_runs_actions_on_both_instances`. Native default path: `tests/test_cutover_instances.py::test_a_native_toggle_runs_the_actions_on_every_instance`. All pass in this run. Real two-instance confirmation: Phase 8 block 3 (UAT-03, `result: pass`, `08-evidence/uat-03`, one run per approved instance) |
| 4 | Only the owner can edit or delete; followers pin the owner and raise a Repairs issue on conflicting claims; if a follower removes the discovered entity the owner republishes its discovery | VERIFIED for the first two clauses; third clause PASSED (override), superseded by Phase 5 | Mirrors are not subentries, so there is no edit or delete path; `sync.py` `_may_repin` / `_conflict` pin the first owner and raise the conflict issue: `tests/test_sync_follower.py::test_pinned_owner_ignores_another_owner`, `tests/test_multi_instance.py::test_ownership_conflict_between_three_instances`, `::test_foreign_claim_replayed_during_startup_never_becomes_a_mirror`, `::test_forged_tombstone_followers_recover_unapproved` (all pass now). Third clause: see "Superseded by Phase 5" |
| 5 | Deleting a device requires an explicit confirmation stating it is removed on all connected instances, after which its central config and discovery are unpublished and the device disappears everywhere | VERIFIED | `config_flow.py` `async_step_delete_device` is a menu whose only options are `delete_confirmed` and `keep_device`, with the escaped `name` placeholder and the online-instance count. `manager.py` `_async_remove_device` removes the device from `devices` first, then clears discovery, unsubscribes, clears the config document (tombstone) and the retained state. Tests (run now): `tests/test_config_flow_delete.py`, `tests/test_config_flow_escaping.py::test_delete_confirmation_shows_the_device_name_as_plain_text`, `tests/test_multi_instance.py::test_delete_removes_the_device_everywhere`, `::test_owner_delete_removes_the_mirror_everywhere`, `tests/test_native_cleanup.py::test_deleting_a_native_device_clears_everything_and_removes_its_entities`. Real instances: Phase 8 P3-1 and P3-2 both ended with a delete whose broker read-back shows the retained config topic empty and the subentry gone (`p3-1/topics-after-delete.txt`, `p3-2/topics-after-delete.txt`, `p3-2/deletes.txt`). The generic HA delete button cannot be vetoed or given custom text; README Limitations (line 283) documents it |

**Score:** 5/5 roadmap truths verified (one clause of truth 4 counted through the D-03 override; 0 behavior-unverified).

Behavior-dependent truths (absence never deletes, approval gate, delete order, owner pinning) each have a passing behavioral test named above, so none is left at presence-only.

### Superseded by Phase 5 (D-03)

| Item | Old behavior | What replaced it | Evidence | Disposition |
|------|--------------|------------------|----------|-------------|
| Roadmap truth 4, third clause, and requirement DSC-03: "if a follower removes the discovered entity the owner republishes its discovery" | The device reached every instance as a core MQTT Discovery device; deleting one entity on a follower made core clear the whole discovery topic, and the owner healed it | Native switch and select entities owned by the hub entry are the default (ADR 0001, `docs/adr/0001-native-entities-instead-of-mqtt-discovery.md`); a native device has no discovery to heal. Healing is gated by `Manager.heals_discovery()` (`manager.py` line 655) and `sync.py` `_on_discovery_message` / `_start_discovery_heal`, so it runs only for an owned device still on the legacy path. REQUIREMENTS.md DSC-03 carries the Phase 5 annotation | New behavior: `tests/test_native_cleanup.py::test_a_native_owner_never_heals_its_discovery`, `::test_the_takeover_clear_is_not_a_foreign_removal` (pass now). Compatibility path: `tests/test_multi_instance.py::test_follower_entity_deletion_heals_the_discovery`, `tests/test_sync_owner.py::test_empty_discovery_for_an_owned_device_republishes_discovery` (pass now) | Recorded as an `overrides` entry, `accepted_by: D-03 (owner decision, Phase 7 context, 2026-10-04)`. Not a regression, and not re-litigated here |

The other Phase 3 behaviors that Phase 5 touched are not superseded: mirror creation and removal, approval, fan-out, ownership pinning and deletion all hold (Truths 1 to 5); only the mechanism that shows the entities changed.

### Human-verification items

#### Items of this report (from the previous `human_needed` report)

| # | Item | Ledger block | Result | Sha | Date | Evidence folder | Disposition |
|---|------|--------------|--------|-----|------|-----------------|-------------|
| 1 | Approval dialog (Settings, Repairs) renders hostile device name, owner name and action YAML as plain text in a real frontend | `08-UAT.md` block 13 (P3-1) | `result: pass`, no contradicting `status:` | `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3` | 2026-10-07 | `.planning/phases/08-real-instance-verification/08-evidence/p3-1` | RESOLVED |
| 2 | Own delete dialog and generic core delete dialog with a device name containing backticks and `<b>` | `08-UAT.md` block 14 (P3-2) | `result: pass`, no contradicting `status:` | `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3` | 2026-10-06 | `.planning/phases/08-real-instance-verification/08-evidence/p3-2` | RESOLVED |

No block carries an `override_by:` line; neither item is an override.

**Item 1 (block 13), who did what.** Scripted by the executor: the hostile device `UAT P3-1 \`code\` | _u_ <b>bold</b>` was imported on ha-b (owner, hub named `Haus \`x\` | _ab_ <b>fett</b>`) through the guard, with `{{ 'system_log' }}.write` as a templated service name and a message holding backticks, underscores and a pipe; ha-a is the follower. Driven by the orchestrator session through the chrome-devtools browser MCP: the approval dialog on ha-a was opened, scrolled and closed (never submitted) in German and English, producing six screenshots (`01..06`, present in the folder; `screens.txt` also records the Repairs list cards and that the issue was still listed after close). Judged by the owner: the owner's verbatim statement "approved P1-2 P3-1" (2026-10-07) is the rendering verdict, made on the screenshots / the live view. The orchestrator's a11y-tree remark (names as bold text, literal `<b>` visible as characters, YAML in one block, templated service under the templated heading) is explicitly "not judged here". Scope as recorded: the block exercised opening, scrolling and closing; submitting the approval in a real frontend was not part of it (never approved on ha-a), and that path stays covered by `tests/test_repairs_flow.py::test_submit_approves_and_the_issue_disappears` and `tests/test_trust.py`. The previous report's "closing leaves the mirror paused" part is supported by the issue still being listed after close and the mirror never approved.

**Item 2 (block 14), who did what.** Judged by the owner in their own browser: the verbatim statement "approved P1-3 P1-4 P3-2" (2026-10-06) covers the two delete dialogs for the devices named with backticks and a bold tag. No screenshots exist (browser MCP unavailable); the verdict rests on the owner's statement alone. Scripted by Claude: because the owner did not confirm the deletes, the two deletes were performed headless over the guard through the same code paths (integration step on ha-a: placeholders `name = "UAT P3-2a \`code\` \<b\>bold\</b>"` markdown-escaped plain text, `count = 1`, abort `device_deleted`; generic path: WebSocket `config_entries/subentries/delete`), and the broker read-back shows both retained config topics empty and both subentries gone (`deletes.txt`, `topics-after-delete.txt`). Those scripted deletes evidence the removal and the placeholder content, not the rendering. The wording of the generic core dialog is core's own text (documented limitation, README line 283).

#### Items of the earlier reports

The previous report named five items from the original report, resolved by `03-UAT.md` (5 of 5 pass, 2026-10-02): items 3 (two real instances on one Mosquitto, covered by the broker tier and Phase 8 UAT-03), 4 (hub removal with the delete option on and off: `tests/test_hub_removal.py`, `tests/test_multi_instance.py::test_hub_removal_delete_clears_everywhere_for_followers`, `::test_hub_removal_keep_leaves_orphans_that_followers_keep`, `tests/test_native_cleanup.py::test_hub_removal_clears_the_export_topics_too`) and 5 (lock scope in `Manager.async_start`: `tests/test_multi_instance.py::test_foreign_claim_replayed_during_startup_never_becomes_a_mirror`, `tests/test_manager.py::test_reconcile_after_stop_does_not_revive_manager`) remain covered by the automated tiers that passed in this run. Residual as before: a slow-broker stop delay is not exercised by a test; the original UAT item was optional.

### Deferred Items

None.

### Advisory (New Scope, Unevidenced)

| # | Finding | Category | Why Advisory |
|---|---------|----------|--------------|
| 1 | Unpublishable document (iteration-2 WR-01) is dropped with a log line only | other | Unchanged; reachable only beyond the form limits or with pre-CR-03 names |
| 2 | Foreign claim replayed during startup is healed without an ownership_claim issue (IN-05) | other | Info; it never becomes a mirror and never runs |
| 3 | Action-check placeholders (`field`, `error`, `device_ids`) not escaped | other | Deliberately out of 03-08 scope; not free user text |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/document.py` | Wire contract, hashes, strict parser, denylist walker, `escape_markdown` | VERIFIED | used by manager, sync, runner, trust, repairs, config_flow; tests pass |
| `custom_components/mqtt_actions/sync.py` | Owner defense, follower ingest, tombstone, prune, presence | VERIFIED | ingest, remove, prune, conflict and legacy healing paths exercised by the passing tiers |
| `custom_components/mqtt_actions/trust.py` | `GuardedTemplate`, `ApprovalView`, approval states | VERIFIED | wired from runner, manager, repairs; `tests/test_trust.py` passes |
| `custom_components/mqtt_actions/repairs.py` | Approval fix flow | VERIFIED | `ApprovalRepairFlow` binds the shown hash; rendered in the real frontend (block 13) |
| `custom_components/mqtt_actions/manager.py` | Owner publish, mirrors, approvals, delete order | VERIFIED | `async_approve`, `async_publish_config`, `_async_remove_device` read and tested |
| `custom_components/mqtt_actions/config_flow.py` | Delete menu, hub options, escaped placeholders | VERIFIED | delete menu at line 230, six `escape_markdown` call sites |
| `docs/broker-acl.md` + `tests/broker/test_acl.py` | Tested ACL | VERIFIED | broker tier passes on a real Mosquitto with `MQTT_ACTIONS_REQUIRE_BROKER=1` |
| `README.md` | Multi-instance, trust, deletion, limitations | VERIFIED | generic delete dialog limitation present (line 283) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sync.py` | `document.py` / `actions.py` | `parse_document` then `validate_spec_structure` before `async_apply_mirror` | WIRED | `_async_ingest_locked` |
| `manager.py` | `runner.py` / `trust.py` | restricted Script only when the approved hash equals the actions hash | WIRED | `runner.async_build_device(..., restricted=True)` (line 1782) |
| `repairs.py` | `manager.py` | `async_approval_view`, then `async_approve` with the displayed hash | WIRED | `ApprovalRepairFlow` |
| `config_flow.py` | `document.py` | `escape_markdown` | WIRED | six call sites |
| `manager.py` | `sync.py` | `heals_discovery()` gates discovery healing to the legacy path | WIRED | `manager.py` line 655 |
| `tests/broker/test_acl.py` | `docs/broker-acl.md` | extracts the fenced `acl` block | WIRED | `test_documented_acl_block_is_the_tested_acl` passes |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Delete dialog `name` | subentry title | `_get_reconfigure_subentry().title` through `escape_markdown` | Yes (real placeholder captured in `p3-2/deletes.txt`) | FLOWING |
| Approval dialog values | `ApprovalView` | `build_approval_view(spec, info, ...)` from the parsed mirror document | Yes (real dialog screenshots, `p3-1/01..06`) | FLOWING |
| Mirror `Device.spec` | parsed document | retained message -> `parse_document` -> `async_apply_mirror` | Yes | FLOWING |
| Native mirror entities | `device.value` | shared retained state topic -> `_on_message` -> dispatcher | Yes (`test_a_native_toggle_runs_the_actions_on_every_instance`) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 3 tiers plus native cutover (broker, multi-instance, follower, owner, trust, repairs, document, escaping, delete, native cleanup, hub removal, native entities, cutover instances) | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider tests/broker tests/test_multi_instance.py tests/test_sync_follower.py tests/test_sync_owner.py tests/test_trust.py tests/test_repairs_flow.py tests/test_document.py tests/test_config_flow_escaping.py tests/test_config_flow_delete.py tests/test_native_cleanup.py tests/test_hub_removal.py tests/test_native_entities.py tests/test_cutover_instances.py` | `484 passed in 51.50s` | PASS |
| Whole suite, stability, CI | cited from `07-PROOF.md` (code identical to the build sha) | 3 local runs `1490 passed`; 3 CI dispatch runs success (1308 + 17 + 165); Validate success | PASS (cited) |
| Lint | `uv run --locked ruff check .` | `All checks passed!` | PASS |
| Debt markers | grep TBD/FIXME/XXX/TODO/HACK in `custom_components tests docs README.md .github` | none | PASS |

### Probe Execution

SKIPPED: no `probe-*.sh` scripts exist and none are declared in the Phase 3 plans.

### Requirements Coverage

All 12 phase IDs are mapped to Phase 3 in `.planning/milestones/v1.0-REQUIREMENTS.md` (checked, traceability Complete). No orphaned Phase 3 requirement.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SYN-01 | 03-01 | Owner publishes one retained, versioned config document per device | SATISFIED | `build_document`, `async_publish_config`; `tests/test_document.py`, `tests/test_sync_owner.py` |
| SYN-02 | 03-04 | Other instance creates read-only mirrors | SATISFIED | `async_apply_mirror`; `test_follower_mirrors_the_owners_device`; real follower on ha-a (P3-1) |
| SYN-03 | 03-02, 03-04 | One owner; only owner edits/deletes; pinning and Repairs on conflict | SATISFIED | no edit/delete path for mirrors; conflict tests |
| SYN-04 | 03-01, 03-07 | Owner republishes on every reconnect | SATISFIED | `_async_republish`; `test_reconnect_republishes_config_before_availability` |
| SYN-05 | 03-05, 03-07 | Absence never deletes; tombstone or grace window | SATISFIED | `_async_prune` conditions; absence and prune tests |
| SYN-06 | 03-02, 03-03, 03-07, 03-08 | Delete requires confirmation naming all instances, then unpublishes config and discovery | SATISFIED | own delete step with count and escaped name; delete-order tests; real-instance delete read-back and owner-judged dialogs (block 14) |
| TRU-01 | 03-04, 03-06 | Remote actions not executed by default | SATISFIED | no Script without matching approval; `test_unapproved_mirror_runs_nothing` |
| TRU-02 | 03-06 | Approval per instance via Repairs, bound to the hash | SATISFIED | `ApprovalRepairFlow`, `async_approve`; dialog rendered in a real frontend (block 13) |
| TRU-03 | 03-01, 03-04, 03-06 | Schema validation and execution-time denylist | SATISFIED | `validate_spec_structure` at ingest, `GuardedTemplate` at run time |
| TRU-04 | 03-07 | Docs include a broker ACL example per instance | SATISFIED | `docs/broker-acl.md`, tested on a real Mosquitto |
| STA-03 | 03-04, 03-06, 03-07 | Actions run locally on every participating instance | SATISFIED | fan-out tests on legacy and native path; Phase 8 UAT-03 |
| DSC-03 | 03-02 | Owner republishes discovery removed by a follower | SATISFIED on the legacy path; superseded as default by Phase 5 | override above |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `custom_components/mqtt_actions/manager.py` | `async_publish_config` except branch | Unpublishable document dropped with a log line only | Info | Owner sees no Repairs issue (advisory 1) |
| `custom_components/mqtt_actions/sync.py` | `_async_ingest` owned-id skip | Foreign claim replayed during startup healed without an issue | Info | Missing diagnostic only (advisory 2) |

No blocker anti-patterns, no stubs, no unreferenced debt markers.

### Gaps Summary

No gaps, no regression and no open human item. Every roadmap success criterion is implemented, wired and backed by passing tests at the build sha (484 Phase 3 tests run now, plus the 1490-test full-suite proof, three CI runs and Validate of Phase 7). One clause (discovery healing after a follower removes the entity) was replaced on purpose by Phase 5 and stays recorded as the D-03 override. The two real-frontend items that kept the previous report at `human_needed` are resolved by Phase 8 blocks 13 and 14 (both `result: pass` at sha `b7f52b34...`, owner-judged; block 13 on screenshots, block 14 on the owner's statement without screenshots). Phase 8 block 4 (UAT-04, `issue`) belongs to Phase 5 and not to this phase.

---

_Verified: 2026-10-08T19:09:17Z_
_Verifier: Claude (gsd-verifier)_

## Digest refresh (2026-10-08)

`covered_digest` was refreshed from `verification.fingerprint` over this report's own `covered_files` after `08-UAT.md` gained its `## Verification refresh` section (a ledger edit made after the verifier ran, plan 08-10 Task 3). No other content of this report changed; the digest was copied from the tool output, not written by hand. Previous digest: `v3:sha256:edadee704f3a6930dcb9302baa112af836ee78db085ee82c9b0ec4632675494e`.
