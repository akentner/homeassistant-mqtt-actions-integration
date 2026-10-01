---
phase: 03-trust-central-config-and-ownership
verified: 2026-10-01T18:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .planning/phases/03-trust-central-config-and-ownership/03-01-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-01-SUMMARY.md
  - .planning/phases/03-trust-central-config-and-ownership/03-02-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-02-SUMMARY.md
  - .planning/phases/03-trust-central-config-and-ownership/03-03-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-03-SUMMARY.md
  - .planning/phases/03-trust-central-config-and-ownership/03-04-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-04-SUMMARY.md
  - .planning/phases/03-trust-central-config-and-ownership/03-05-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-05-SUMMARY.md
  - .planning/phases/03-trust-central-config-and-ownership/03-06-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-06-SUMMARY.md
  - .planning/phases/03-trust-central-config-and-ownership/03-07-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-07-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/breaker.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/trust.py
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
  - tests/test_config_flow_select.py
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
covered_digest: "v2:sha256:750d1a2f3f755df09ba5a87eda137939d35fc897c30cdbb04b5f08e4b24e697b"
behavior_unverified: 0
overrides_applied: 0
gaps: []
advisory:
  - finding: "WR-04: run_mode, breaker_max_runs and breaker_window are outside actions_hash, so an owner (or a forger of the config topic) can change them after approval without a new request"
    category: security
    reason: "Deliberately open pending a user decision (03-REVIEW-DISPOSITION.md); the README trust model says the approval is bound to 'the hash of the actions' and does not state that run mode and breaker limits are remote-controlled"
    evidence_status: "code read: document.py actions_hash() hashes kind, run_on_startup and the (StateValue, actions) pairs only"
  - finding: "Iteration-2 WR-01: a document the pre-publish guard refuses (name over 64 characters from an old build, more than 256 KiB, nesting deeper than 32) is dropped with one log line; no Repairs issue, and followers keep running the previously approved retained document"
    category: other
    reason: "Open in 03-REVIEW-DISPOSITION.md; only reachable at sizes and depths the device forms do not bound, or for names stored before CR-03"
    evidence_status: "code read: manager.py async_publish_config except branch logs and returns"
  - finding: "IN-02/IN-05 (iteration 2): cached mirrors with an invalid id are restored from the Store but can never be updated or removed by messages; a foreign claim replayed during startup is healed without an ownership_claim issue"
    category: other
    reason: "Info-level, open in the disposition; neither lets a foreign actor run actions"
    evidence_status: "code read: manager.py _parse_mirrors has no is_valid_device_id check; sync.py _async_ingest skips owned ids"
  - finding: "repairs.py imports voluptuous (iteration-1 IN-01) although the project stack rule says probatio"
    category: other
    reason: "Works through core's alias; open info finding"
    evidence_status: "grep: repairs.py line 11 'import voluptuous as vol'"
human_verification:
  - test: "Open the approval request in Repairs on a real Home Assistant frontend for a mirrored device whose name, owner name and actions contain markdown characters (backticks, underscores, pipes) and a templated service name"
    expected: "The dialog renders device, owner, the YAML in one code block, the short hash, the startup flag sentence, the templated and residual lists and no injected markup; Submit approves, closing the dialog leaves the mirror paused"
    why_human: "Markdown rendering of translation placeholders in the Repairs dialog depends on the real frontend; tests only assert the placeholder strings"
  - test: "Delete a device through the generic Home Assistant subentry delete button on the integration page (not through the integration's own Delete the device menu step) on an instance with at least one follower online"
    expected: "Home Assistant's generic confirmation appears (it cannot name the other instances), and after confirming the retained discovery, config (tombstone) and state disappear and the mirror vanishes on the follower. The integration's own menu step shows the all-instances text with the online count"
    why_human: "Requirement SYN-06 asks for a confirmation stating removal on all instances; HA offers no veto or custom text for its generic dialog (documented in README and 03-CONTEXT). The user must accept this limitation or ask for a different mechanism"
  - test: "Run two real Home Assistant instances against one real Mosquitto broker with one MQTT user each (use the ACL from docs/broker-acl.md). Create a Switch on instance A, then delete the resulting entity on instance B"
    expected: "The device and its entities appear on B through core MQTT Discovery without a restart; B shows an approval request; A republishes the discovery within the throttle window after B deletes the entity; after approval a toggle on either side runs the actions on both"
    why_human: "The acceptance scenarios run two real hass objects on an in-memory fake broker gateway; core MQTT discovery on a follower, the real client reconnect and real frontend behavior are not exercised end to end"
  - test: "Open the hub options and enable 'Delete all devices when this integration is removed', then remove the hub on a real instance; repeat with the option off"
    expected: "With the option on, the broker holds no retained config, discovery or state for this instance's devices and followers remove their mirrors; with it off, everything stays retained and followers show orphans as unavailable"
    why_human: "async_remove_entry runs after unload in the real removal flow; the tests call it directly with a fake gateway, so MQTT availability at that moment is only checkable on a real instance"
  - test: "Read the lock scope in Manager.async_start (manager.py lines 405-410, the CR-02 fix) and decide whether holding the manager lock across the three subscribes and the first publish is acceptable"
    expected: "A slow broker may delay stop, reconnect republish and prune but cannot deadlock; the re-review (03-REVIEW.md question a) already found no deadlock"
    why_human: "Flagged for a human look in 03-REVIEW-FIX.md; a latency trade-off, not a defect found here"
---

# Phase 3: Trust, Central Config and Ownership Verification Report

**Phase Goal:** As a user with several HA instances, I want devices created on one instance to appear on the others once I approve them, so that every instance runs the actions locally.
**Verified:** 2026-10-01T18:00:00Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

The goal is achieved in the code: an owner publishes one retained, validated document per device; followers build read-only mirrors that run nothing until the user approves the exact action hash in Repairs; after approval a state change runs the actions locally on every approving instance; only the owner can delete, and deletion propagates as a tombstone. The suite (814 tests, including 11 real-Mosquitto tests and 25 multi-instance scenarios) passes and Ruff is clean, but I read the code behind each claim and did not rely on SUMMARY.md. No gap blocks the goal. The status is `human_needed` because five items need a real Home Assistant frontend or a real broker flow, and one trust-model decision (WR-04) is still open with the user.

### Observable Truths (roadmap contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A device created on one instance is published as one retained, versioned config document; a second instance creates a read-only mirror; the owner republishes on every reconnect; a missing message never deletes a mirror (only tombstone or grace window) | VERIFIED | `document.py` `build_document` (schema_version, owner, rev, hash, content) and strict `parse_document`; `manager.py` `async_publish_config` (rev only grows with the content hash, persisted in `STORE_REVS`); `_on_connection_status` -> `sync.on_reconnect()` + `_async_republish()` publishes documents, then discovery, then availability; mirrors live in `Manager.mirrors`, never in `devices` or subentries; `sync.py` `_async_remove` (tombstone) and `_async_prune` (needs `device_id not in _seen` and `instance_status(owner) == online`). Tests: `test_follower_mirrors_the_owners_device`, `test_absence_alone_never_removes_a_mirror`, `test_reconnect_republishes_config_before_availability`, `test_wiped_broker_heals_without_pruning`, `test_prune_waits_for_the_owner_to_be_online` pass |
| 2 | A mirror's actions do not run until approved in Repairs; approval is bound to the action hash so changed actions need re-approval; every broker action sequence is schema-validated; denylisted services are refused at execution time; docs include a broker ACL example per instance | VERIFIED | `manager.py` `_async_refresh_mirror_script`: no Script unless `_approvals[id] == info.actions_hash`, not denied and has actions; `async_approve` stores only the exact shown hash; `repairs.py` `ApprovalRepairFlow` binds `_shown_hash` and aborts on change; `actions_hash` covers kind, run_on_startup and (StateValue, actions) pairs. `sync.py` `_async_ingest_locked` runs `parse_document` + `validate_spec_structure` before anything is stored. `runner.py` restricted build -> `_refuse_denied` (static) + `trust.guard_actions` -> `GuardedTemplate` raising `DeniedServiceCallError` (a plain `Exception`, so `continue_on_error` cannot swallow it). `docs/broker-acl.md` binds each instance to its own availability topic and `tests/broker/test_acl.py` enforces the very block read from the document on a real Mosquitto (11 broker tests pass, none skipped). Tests: `test_unapproved_mirror_runs_nothing`, `test_race_owner_edits_while_the_dialog_is_open_aborts`, `test_blocked_mirror_is_not_approvable_and_never_built`, `test_denied_call_aborts_the_run_even_with_continue_on_error`, `test_owner_edit_requires_reapproval_on_followers` |
| 3 | After approval a real state change (HA UI on any instance or an external MQTT message) runs the actions locally on every participating instance | VERIFIED | `manager.py` `_on_message` resolves owned devices and mirrors alike (`_device`), same tracker/breaker/runner path. `test_fanout_runs_on_every_approved_instance_and_only_there` (owner A, approving follower B, non-approving follower C): UI-style publish through B's gateway and an external broker publish give `{on:1, off:1}` on A and B and nothing on C; the test topic and a restart of unapproved C also run nothing there. `test_approved_mirror_runs_actions_on_both_instances`, `test_owner_offline_follower_still_runs_actions` pass |
| 4 | Only the owner can edit or delete a device; followers pin the owner and raise a Repairs issue on conflicting claims; if a follower removes the discovered entity the owner republishes its discovery | VERIFIED | Mirrors are not subentries, so no flow edits or deletes them. `sync.py` `_async_ingest_locked`: first owner is pinned, another owner's document only calls `_conflict` (issue `owner_conflict_<id>` naming both claims) and changes nothing; owner side `_claimed`/`_overwritten` republish and raise `ownership_claim_`/`doc_overwritten_`; `_on_discovery_message` heals an emptied discovery of an owned device with a 60 s trailing throttle and a repeated-removal hint. Tests: `test_pinned_owner_ignores_another_owner`, `test_ownership_conflict_between_three_instances`, `test_follower_entity_deletion_heals_the_discovery`, `test_heal_is_throttled_with_one_trailing_republish`. Broker-level enforcement of "only the owner" is cooperative and says so in `docs/broker-acl.md` |
| 5 | Deleting a device requires an explicit confirmation stating it is removed on all connected instances, then its central config and discovery are unpublished and the device disappears everywhere | VERIFIED (with caveat, see human item 2) | `config_flow.py` `async_step_delete_device` is a menu with only `delete_confirmed`/`keep_device`; the text (`translations/en.json`, `de.json`) states "removed on all connected instances" plus the online count from `Manager.online_instance_count`; both the Switch reconfigure menu and the Select menu reach it. `manager.py` `_async_remove_device` pops the device first, then clears discovery, unsubscribes, publishes the config tombstone, clears state; a failed clear keeps the id in the published set for a retry. Followers drop the mirror on the tombstone (`test_owner_delete_removes_the_mirror_everywhere`, `test_delete_removes_the_device_everywhere`). Caveat: the generic HA subentry delete button cannot be vetoed and does not show this text; README and 03-CONTEXT document it and the removal sequence is identical |

**Score:** 5/5 roadmap truths verified (0 present, behavior-unverified). The plan-level truths and prohibitions I traced are subsumed by these; every one of the 34 distinct `verification:` test references named in the PLAN prohibitions exists and passes.

Plan-level decisions honored (spot-checked against 03-CONTEXT.md): D-01 no hub-wide policy (no ask/auto mode anywhere); D-03/D-04/D-05 fixed denylist in `const.py`, recursive walker, runtime guard; D-08 mirrors in the Store not subentries; D-09 live tombstone; D-10 grace window with owner-online condition; D-11 keep default / delete via hub options (`HubOptionsFlow`, `async_remove_entry`); D-12 document at `<base>/v1/devices/<id>/config`; D-14 schema_too_new keeps last state and raises an issue; D-15 hash decides, owner republishes on reconnect; D-16 delete order; D-17 first owner wins; D-18 throttled discovery healing; D-19 availability untouched.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/document.py` | Wire contract, hashes, strict parser, denylist walker | VERIFIED | 505 lines, all functions substantive; used by manager, sync, runner, trust |
| `custom_components/mqtt_actions/sync.py` | Owner defense, follower ingest, tombstone, prune, presence | VERIFIED | 617 lines; instantiated as `Manager.sync`, started under the start lock |
| `custom_components/mqtt_actions/trust.py` | `GuardedTemplate`, approval view | VERIFIED | imported by runner and manager; core version coupling pinned by a test |
| `custom_components/mqtt_actions/repairs.py` | Fix flow | VERIFIED | `async_create_fix_flow` found by core by module name; manager issue carries `is_fixable=True` |
| `custom_components/mqtt_actions/manager.py` | Owner publish, mirrors, approvals, delete order | VERIFIED | 1193 lines, wired from `__init__.py` |
| `custom_components/mqtt_actions/config_flow.py` | Delete menu, `HubOptionsFlow` | VERIFIED | reachable from both subentry flows and the hub entry |
| `docs/broker-acl.md` + `tests/broker/test_acl.py` | Tested ACL | VERIFIED | real Mosquitto, block read from the document |
| `tests/fake_broker.py` | Fake broker with retain semantics | VERIFIED | used by the three-instance scenarios |
| `README.md` | Multi-instance, trust, deletion, limitations | VERIFIED | sections present and match the code (see advisory on WR-04 wording) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `manager.py` | `document.py` | `async_publish_config` -> `build_document`, `serialize_document`, then `parse_document` guard | WIRED | |
| `manager.py` | `sync.py` | `sync.async_start` under lock, `note_published`, `on_reconnect`, `forget` | WIRED | |
| `sync.py` | `manager.py` | ingest/heal/remove tasks take `Manager.lock` and call `async_apply_mirror`, `async_remove_mirror`, `async_publish_config` | WIRED | |
| `manager.py` | `runner.py` | `async_build_device(spec, restricted=True)` only when approved hash equals actions hash | WIRED | |
| `runner.py` | `trust.py` | `guard_actions`, `DeniedServiceCallError` caught first in `_async_run` | WIRED | |
| `repairs.py` | `manager.py` | `async_approval_view` then `async_approve` with the displayed hash | WIRED | |
| `__init__.py` | `manager.py` | `async_remove_entry` -> `async_remove_all_devices` / `async_remove_local_state` | WIRED | |
| `tests/broker/test_acl.py` | `docs/broker-acl.md` | extracts fenced `acl` block | WIRED | |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Mirror `Device.spec` | parsed document | retained message on the config wildcard -> `parse_document` -> `async_apply_mirror` | Yes (broker payload, persisted in `STORE_MIRRORS`, parsed again at load) | FLOWING |
| Approval dialog placeholders | `ApprovalView` | `Manager.async_approval_view` from the mirror's current spec at show time | Yes | FLOWING |
| Delete confirmation `count` | online instances | availability wildcard -> `SyncManager._instances` | Yes (0 while the entry is not loaded) | FLOWING |
| Mirror entities | owner's discovery | owner publishes; core MQTT on the follower creates entities | Not testable in this repo, see human item 3 | NOT EXERCISED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `uv run pytest -q` | 814 passed in 44 s | PASS |
| Lint | `uv run ruff check .` | All checks passed | PASS |
| Real-broker tier | `uv run pytest tests/broker -q -rs` | 11 passed, none skipped (mosquitto installed) | PASS |
| Acceptance scenarios | `uv run pytest tests/test_multi_instance.py -k "fanout or wiped or delete_removes or owner_edit or hub_removal or conflicting or forged or follower_deletes"` | 10 passed | PASS |
| All PLAN-named prohibition tests exist | grep of the `file::test` references | 34 of 34 found | PASS |
| Debt markers (TBD/FIXME/XXX/TODO/HACK) in source, tests, docs | grep | none | PASS |

### Probe Execution

SKIPPED: no `probe-*.sh` scripts exist and none are declared in the plans (the tooling for this phase is the pytest suite above).

### Requirements Coverage

All 12 phase IDs appear in at least one PLAN `requirements:` field and in REQUIREMENTS.md mapped to Phase 3. No orphaned Phase 3 requirement. DSC-04 and the other Phase 4 IDs are correctly still pending.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SYN-01 | 03-01 | Owner publishes one retained, versioned config document per device | SATISFIED | `build_document`, `async_publish_config`, `test_document.py`, `test_sync_owner.py` |
| SYN-02 | 03-04 | Another instance creates the same devices as read-only mirrors | SATISFIED | `async_apply_mirror`, `test_follower_mirrors_the_owners_device` (entities come from the owner's discovery; real-core check is human item 3) |
| SYN-03 | 03-02, 03-04 | One owner per device; only the owner edits or deletes; followers pin and raise Repairs on conflicting claims | SATISFIED | mirrors are not subentries (no edit/delete path); pinning and `owner_conflict_`/`ownership_claim_` issues tested. Enforcement is by the integration, not the broker (documented as cooperative) |
| SYN-04 | 03-01, 03-07 | Owner reconciles and republishes on every reconnect | SATISFIED | `_on_connection_status` -> `_async_republish` (documents, discovery, availability); wiped-broker scenario |
| SYN-05 | 03-05, 03-07 | Followers never delete because a message is absent; tombstone or grace window | SATISFIED | `_async_prune` conditions; `test_absence_alone_never_removes_a_mirror`, `test_wiped_broker_heals_without_pruning` |
| SYN-06 | 03-02, 03-03, 03-07 | Delete requires explicit confirmation stating all instances, then unpublishes config and discovery | SATISFIED with caveat | holds for the integration's own delete step; the generic HA delete dialog bypasses the confirmation text (human item 2) |
| TRU-01 | 03-04, 03-06 | Remote actions not executed by default | SATISFIED | no Script without matching approval; `test_unapproved_mirror_runs_nothing` |
| TRU-02 | 03-06 | Approve per instance via Repairs, bound to the action hash | SATISFIED | `ApprovalRepairFlow`, `async_approve`; real-frontend rendering is human item 1 |
| TRU-03 | 03-01, 03-04, 03-06 | Schema validation of received sequences and execution-time denylist | SATISFIED | `validate_spec_structure` at ingest, `GuardedTemplate` at run time |
| TRU-04 | 03-07 | Docs include a broker ACL example per instance | SATISFIED | `docs/broker-acl.md`, tested on real Mosquitto |
| STA-03 | 03-04, 03-06, 03-07 | Actions run locally on every participating instance on a real state change | SATISFIED | `test_fanout_runs_on_every_approved_instance_and_only_there` |
| DSC-03 | 03-02 | Owner republishes discovery removed by a follower deleting the entity | SATISFIED | `_on_discovery_message`, `test_follower_entity_deletion_heals_the_discovery` |

**REQUIREMENTS.md reconciliation (SYN-03, SYN-06):** In the committed file all 12 Phase 3 IDs are `[x]` and `Complete`, and the traceability table agrees with the checkboxes. The over-ticking happened in the plan-completion commits (1a18c7c ticked SYN-03 after plan 02, before pinning existed in plan 04; SYN-06 was claimed by plan 02 before the confirmation step of plan 03). At the end of the phase the code delivers both, so the final state is accurate and I recommend no change to the checkboxes. Two precision notes if you want the file to be strictly honest: SYN-03 is enforced in the integration, not at the broker (cooperative ownership, documented in `docs/broker-acl.md`); SYN-06's confirmation text exists only in the integration's own flow, not in HA's generic delete dialog. I did not edit REQUIREMENTS.md.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `custom_components/mqtt_actions/document.py` | 110-117 | `actions_hash` excludes `run_mode`, `breaker_max_runs`, `breaker_window` (WR-04, open) | Warning | A remote change weakens a follower's loop protection or switches serial to restart without re-approval; README does not say so |
| `custom_components/mqtt_actions/manager.py` | 1005-1017 | Unpublishable document is dropped with a log line only (iteration-2 WR-01) | Warning | Owner sees no error, followers keep the stale approved document; reachable only beyond the form's unvalidated size/depth limits or with pre-CR-03 names |
| `custom_components/mqtt_actions/manager.py` | 192-216 | `_parse_mirrors` skips `is_valid_device_id` (IN-02) | Info | Old cached mirrors with odd ids are never updated or removed by messages |
| `custom_components/mqtt_actions/sync.py` | 319-333 | Foreign claim replayed during start is healed without an issue (IN-05) | Info | Missing diagnostic only |
| `custom_components/mqtt_actions/repairs.py` | 11 | `import voluptuous` instead of `probatio` (IN-01) | Info | Stack rule deviation, works through core alias |
| `.planning/phases/03-.../03-VALIDATION.md` | - | still `status: draft`, `nyquist_compliant: false` | Info | Bookkeeping; `/gsd-validate-phase` was not run |

No blocker anti-patterns and no unreferenced debt markers.

### Human Verification Required

#### 1. Approval dialog in a real Repairs frontend

**Test:** Trigger an approval request for a mirror with markdown characters in the names and a templated service name, open it in Repairs.
**Expected:** Escaped names, one YAML code block, hash, startup sentence, templated/residual lists; submit approves; closing leaves the mirror paused.
**Why human:** Placeholder rendering depends on the real frontend.

#### 2. Generic subentry delete dialog

**Test:** Delete a device with HA's generic delete button, then through the integration's own "Delete the device" menu step, with a follower online.
**Expected:** The generic path deletes everywhere without naming other instances; the own path shows the all-instances text and the online count; the follower's mirror disappears in both cases.
**Why human:** HA offers no veto or custom text for the generic dialog. You must decide whether SYN-06 as written is met by the own-flow confirmation plus the README note.

#### 3. Two real instances on one real broker

**Test:** Two HA instances, real Mosquitto with the documented ACL; create a Switch on A, delete its entity on B.
**Expected:** Device appears on B through core MQTT Discovery, approval request appears, A republishes discovery after the entity deletion, toggles run actions on both after approval.
**Why human:** The scenarios use an in-memory fake broker gateway; core discovery and real reconnects are outside it.

#### 4. Hub removal in the real removal flow

**Test:** Set the "delete all devices" hub option on, remove the hub; repeat with the option off.
**Expected:** On: no retained config/discovery/state left, followers drop their mirrors. Off: everything stays, followers show orphans as unavailable.
**Why human:** `async_remove_entry` runs after unload; MQTT availability at that moment is only visible on a real instance.

#### 5. Lock scope in `Manager.async_start` (optional)

**Test:** Review the CR-02 fix at `manager.py` lines 405-410.
**Expected:** Latency only, no deadlock (the re-review analyzed every callee).
**Why human:** Flagged for a human look in 03-REVIEW-FIX.md.

### Decision Needed (not a gap)

**WR-04:** Either bind `run_mode` and the breaker limits into `actions_hash` (wire-contract change, invalidates existing approvals, fine now because nothing is released), or clamp mirrored breaker limits to a local floor, or at least document in the README trust model that those three settings follow the owner without re-approval. Until decided, the README sentence "The approval is bound to the hash of the actions" overstates what the hash covers.

### Gaps Summary

No gaps. Every roadmap success criterion is implemented, wired and covered by passing behavioral tests, including the concurrency and ordering invariants (delete order, startup lock against foreign claims, throttle with trailing republish, race between owner edit and open approval dialog). The phase cannot be marked `passed` yet because of the five human checks above and the open WR-04 decision. The ROADMAP phase list still shows Phase 3 unchecked (`[ ]`); the orchestrator should update it after the human checks.

---

_Verified: 2026-10-01T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
