---
phase: 03-trust-central-config-and-ownership
verified: 2026-10-02T09:00:00Z
status: passed
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
  - .planning/phases/03-trust-central-config-and-ownership/03-08-PLAN.md
  - .planning/phases/03-trust-central-config-and-ownership/03-08-SUMMARY.md
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
  - tests/test_config_flow_escaping.py
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
covered_digest: "v2:sha256:c74130937b80f2bc8ca7d19fde0b8ddf8bb91635b8d290797dc985673c389ad5"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "G-03-2 (UAT): the integration's own delete confirmation and the Select menu, option removal and option edit dialogs rendered user text as Markdown/HTML; fixed by plan 03-08"
  gaps_remaining: []
  regressions: []
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
  - finding: "config_flow.py passes the action-check placeholders (field, error, device_ids) to form descriptions unescaped (lines 344, 494, 575 spread)"
    category: other
    reason: "Plan 03-08 deliberately scoped these out: they feed form error alerts, not a Markdown description, and were not checked against a frontend; the values are field names and HA validation text, plus device ids, not free user text"
    evidence_status: "code read of config_flow.py _async_check_actions callers; not exercised in a frontend"
---

# Phase 3: Trust, Central Config and Ownership Verification Report

**Phase Goal:** As a user with several HA instances, I want devices created on one instance to appear on the others once I approve them, so that every instance runs the actions locally.
**Verified:** 2026-10-02T09:00:00Z
**Status:** passed
**Re-verification:** Yes - after gap-closure plan 03-08 (UAT gap G-03-2) and completion of the manual UAT (5 of 5 passed)

## Goal Achievement

The goal is achieved in the code and in the real-world UAT. An owner publishes one retained, validated document per device; followers build read-only mirrors that run nothing until the user approves the exact action hash in Repairs; after approval a state change runs the actions locally on every approving instance; only the owner can delete, and deletion propagates as a tombstone.

This run re-checked what changed since the last report (commits after 305ce73): `git diff 305ce73 HEAD` outside `.planning/` touches exactly three files: `custom_components/mqtt_actions/config_flow.py` (14 lines), the new `tests/test_config_flow_escaping.py`, and `tests/test_translations.py`. No sync, trust, runner, manager or document code changed, so the prior code-level verification of truths 1-4 stands; I re-ran the whole suite instead of trusting the old counts.

The five human items of the earlier report are resolved by `03-UAT.md` (5 of 5 pass: real Repairs frontend, two real HA instances on a real Mosquitto with `docs/broker-acl.md`, hub removal on and off, lock scope). UAT test 2 first found a defect (G-03-2: device name rendered as Markdown/HTML in the integration's own delete dialog); it was fixed by plan 03-08 and re-tested in a real frontend (0 code spans, 0 injected elements).

### Observable Truths (roadmap contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A device created on one instance is published as one retained, versioned config document; a second instance creates a read-only mirror; the owner republishes on every reconnect; a missing message never deletes a mirror (only tombstone or grace window) | VERIFIED | Code unchanged since the earlier read-through (`document.py` `build_document`/`parse_document`, `manager.py` `async_publish_config`, `_async_republish`, `sync.py` `_async_remove`/`_async_prune`). Suite passes (823 tests), including `test_follower_mirrors_the_owners_device`, `test_absence_alone_never_removes_a_mirror`, `test_wiped_broker_heals_without_pruning`. UAT 3 confirmed on two real HA instances: device appears on B through core MQTT Discovery |
| 2 | A mirror's actions do not run until approved in Repairs; approval is bound to the action hash; every broker action sequence is schema-validated; denylisted services are refused at execution time; docs include a broker ACL example per instance | VERIFIED | `manager.py` `async_approve` stores the approval only when the shown hash equals `info.actions_hash`; the Script is built only when `_approvals.get(device_id) == info.actions_hash` (line ~671). `docs/broker-acl.md` is enforced by `tests/broker/test_acl.py` against a real Mosquitto (11 passed, none skipped, re-run now). UAT 1 confirmed the approval dialog in a real Repairs frontend; UAT 3 ran with `allow_anonymous false` and the documented ACL |
| 3 | After approval a real state change (HA UI on any instance or external MQTT message) runs the actions locally on every participating instance | VERIFIED | `test_fanout_runs_on_every_approved_instance_and_only_there` passes in the full run (owner A, approving B, non-approving C); UAT 3 confirmed a toggle running actions on both real instances |
| 4 | Only the owner can edit or delete; followers pin the owner and raise a Repairs issue on conflicting claims; if a follower removes the discovered entity the owner republishes its discovery | VERIFIED | Mirrors are not subentries (no edit/delete path); `test_pinned_owner_ignores_another_owner`, `test_ownership_conflict_between_three_instances`, `test_follower_entity_deletion_heals_the_discovery` pass. UAT 3: discovery republished 13 s after the delete on a real broker |
| 5 | Deleting a device requires an explicit confirmation stating it is removed on all connected instances, then its central config and discovery are unpublished and the device disappears everywhere | VERIFIED | `config_flow.py` `async_step_delete_device` is a menu with only `delete_confirmed`/`keep_device`; text states removal on all connected instances plus the online count. Since 03-08 the `name` placeholder is `escape_markdown(self._get_reconfigure_subentry().title)` (line 212), so the dialog shows the name as plain text; `test_delete_confirmation_shows_the_device_name_as_plain_text` passes for Switch and Select. UAT 2 (retested) and UAT 4 confirmed deletion everywhere and the hub-removal option on and off. Caveat unchanged and documented: HA's generic subentry delete button cannot be vetoed or given custom text; the user accepted this in UAT (test 2 pass) |

**Score:** 5/5 roadmap truths verified (0 present, behavior-unverified).

### Gap-closure check: plan 03-08 (G-03-2)

| 03-08 must-have | Status | Evidence |
|-----------------|--------|----------|
| Delete confirmation `name` is the escaped form for both device types | VERIFIED | `config_flow.py:212`; test constant pinned to `escape_markdown` by `test_expected_constants_match_escape_markdown` |
| Select menu escapes name and both parts of each option line, leaving list marker, parentheses and newline join | VERIFIED | `config_flow.py:451-456`; `test_select_menu_escapes_the_name_and_every_option_line` |
| Option removal escapes friendly name and state value; option edit escapes the state value | VERIFIED | `config_flow.py:575` and `:596-597`; `test_remove_confirmation_escapes_friendly_name_and_state_value`, `test_edit_option_details_escapes_the_state_value` |
| Plain-text widgets (chooser labels, suggested values) are not over-escaped | VERIFIED | `test_option_chooser_labels_stay_plain_text`; `_chooser_schema` untouched in the diff |
| No translation wraps an escaped placeholder in markup | VERIFIED | `test_escaped_flow_placeholders_are_not_wrapped_in_markup` (en, de); translations untouched in the diff |
| Escaped strings are display text only, never written back | VERIFIED | The diff changes only `description_placeholders` values; no draft or subentry assignment touched |

`grep -v '^\s*#' config_flow.py | grep -c "escape_markdown("` returns the six call sites the plan required (import line present once).

### Deferred Items

None.

### Advisory (New Scope, Unevidenced)

| # | Finding | Category | Why Advisory |
|---|---------|----------|--------------|
| 1 | WR-04: `run_mode` and breaker limits are outside `actions_hash` | security | Open by user decision; not a roadmap truth, wire-contract change; README wording overstates the hash coverage |
| 2 | Unpublishable document dropped with a log line only (iteration-2 WR-01) | other | Reachable only beyond form limits or with pre-CR-03 names |
| 3 | IN-02 / IN-05 (iteration 2) | other | Info; no foreign actor can run actions |
| 4 | `repairs.py` imports `voluptuous` instead of `probatio` | other | Works through core alias |
| 5 | Action-check placeholders (`field`, `error`, `device_ids`) not escaped | other | Deliberately out of 03-08 scope; not free user text |

None of these blocks a roadmap success criterion. WR-04 remains the one item that needs an explicit owner decision (bind the three settings into the hash, clamp local limits, or document that they follow the owner); until then the README sentence "The approval is bound to the hash of the actions" is broader than what the hash covers.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/document.py` | Wire contract, hashes, strict parser, denylist walker, `escape_markdown` | VERIFIED | 505 lines; imported by manager, sync, runner, trust and now config_flow |
| `custom_components/mqtt_actions/sync.py` | Owner defense, follower ingest, tombstone, prune, presence | VERIFIED | 617 lines, unchanged since last verification |
| `custom_components/mqtt_actions/trust.py` | `GuardedTemplate`, approval view | VERIFIED | 185 lines, wired from runner and manager |
| `custom_components/mqtt_actions/repairs.py` | Approval fix flow | VERIFIED | 96 lines; real frontend checked in UAT 1 |
| `custom_components/mqtt_actions/manager.py` | Owner publish, mirrors, approvals, delete order | VERIFIED | 1193 lines, unchanged |
| `custom_components/mqtt_actions/config_flow.py` | Delete menu, hub options, escaped placeholders | VERIFIED | 643 lines; six escape call sites |
| `docs/broker-acl.md` + `tests/broker/test_acl.py` | Tested ACL | VERIFIED | 11 broker tests pass on real Mosquitto |
| `tests/test_config_flow_escaping.py` | Regression tests for 03-08 | VERIFIED | 5 flow tests plus constants pin; all pass |
| `README.md` | Multi-instance, trust, deletion, limitations | VERIFIED | Present; see WR-04 advisory on wording |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config_flow.py` | `document.py` | `from .document import escape_markdown` | WIRED | import at line 51, used at the six call sites |
| `manager.py` | `document.py` / `sync.py` / `runner.py` | publish, ingest, restricted build only when approved hash equals actions hash | WIRED | unchanged, covered by passing tests |
| `repairs.py` | `manager.py` | `async_approval_view`, then `async_approve` with the displayed hash | WIRED | UAT 1 |
| `__init__.py` | `manager.py` | `async_remove_entry` -> `async_remove_all_devices` / `async_remove_local_state` | WIRED | UAT 4 |
| `tests/broker/test_acl.py` | `docs/broker-acl.md` | extracts the fenced `acl` block | WIRED | 11 passed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Delete dialog `name` | subentry title | `_get_reconfigure_subentry().title` through `escape_markdown` | Yes | FLOWING |
| Select menu `options` | draft options | `self._draft` through `escape_markdown` per part | Yes | FLOWING |
| Mirror `Device.spec` | parsed document | retained message -> `parse_document` -> `async_apply_mirror` | Yes (UAT 3 on real broker) | FLOWING |
| Mirror entities | owner's discovery | core MQTT on the follower | Yes (UAT 3) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `uv run pytest -q` | 823 passed in 46.5 s | PASS |
| Real-broker tier | `uv run pytest tests/broker -q -rs` | 11 passed, none skipped | PASS |
| 03-08 tests and translation guard | `uv run pytest tests/test_config_flow_escaping.py tests/test_translations.py -q` | 27 passed | PASS |
| Lint | `uv run ruff check .` | All checks passed | PASS |
| Format | `uv run ruff format --check .` | 54 files already formatted | PASS |
| Debt markers (TBD/FIXME/XXX/TODO/HACK) in source, tests, docs, README | grep | none | PASS |
| Spot-checked prohibition tests still exist | grep for 6 named tests | all found | PASS |

### Probe Execution

SKIPPED: no `probe-*.sh` scripts exist and none are declared in the plans; verification tooling is the pytest suite above.

### Requirements Coverage

All 12 phase IDs (SYN-01..06, TRU-01..04, STA-03, DSC-03) appear in at least one PLAN `requirements:` field and in REQUIREMENTS.md as `[x]` / `Complete` mapped to Phase 3 (checkboxes lines 31, 41, 46-51, 59-62; traceability table lines 128-150). No orphaned Phase 3 requirement; DSC-04, SYN-07..10 are Phase 4 and correctly pending.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SYN-01 | 03-01 | Owner publishes one retained, versioned config document per device | SATISFIED | `build_document`, `async_publish_config`; document and owner tests |
| SYN-02 | 03-04 | Other instance creates read-only mirrors | SATISFIED | `async_apply_mirror`; UAT 3 real instances |
| SYN-03 | 03-02, 03-04 | One owner; only owner edits/deletes; pinning and Repairs on conflict | SATISFIED | no edit/delete path for mirrors; conflict tests. Enforced by the integration, cooperative at the broker (documented in `docs/broker-acl.md`) |
| SYN-04 | 03-01, 03-07 | Owner republishes on every reconnect | SATISFIED | `_async_republish`; wiped-broker scenario |
| SYN-05 | 03-05, 03-07 | Absence never deletes; tombstone or grace window | SATISFIED | `_async_prune` conditions; absence tests |
| SYN-06 | 03-02, 03-03, 03-07, 03-08 | Delete requires confirmation naming all instances, then unpublishes config and discovery | SATISFIED | own delete step with count; name now rendered as plain text (03-08); UAT 2 and 4. Generic HA delete dialog limitation documented and accepted in UAT |
| TRU-01 | 03-04, 03-06 | Remote actions not executed by default | SATISFIED | no Script without matching approval |
| TRU-02 | 03-06 | Approval per instance via Repairs, bound to the hash | SATISFIED | `ApprovalRepairFlow`, `async_approve`; UAT 1 |
| TRU-03 | 03-01, 03-04, 03-06 | Schema validation and execution-time denylist | SATISFIED | `validate_spec_structure` at ingest, `GuardedTemplate` at run time |
| TRU-04 | 03-07 | Docs include a broker ACL example per instance | SATISFIED | `docs/broker-acl.md`, tested on real Mosquitto; UAT 3 |
| STA-03 | 03-04, 03-06, 03-07 | Actions run locally on every participating instance | SATISFIED | fan-out test; UAT 3 |
| DSC-03 | 03-02 | Owner republishes discovery removed by a follower | SATISFIED | `_on_discovery_message`; UAT 3 (13 s) |

The ROADMAP phase list still shows Phase 3 as `[ ]`; updating that checkbox is left to the orchestrator.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `custom_components/mqtt_actions/document.py` | 110-117 | `actions_hash` excludes `run_mode`, `breaker_max_runs`, `breaker_window` (WR-04, open) | Warning | Remote change of loop protection or run mode without re-approval; README wording overstates hash coverage |
| `custom_components/mqtt_actions/manager.py` | ~1005-1017 | Unpublishable document dropped with a log line only | Warning | Owner sees no error; followers keep the stale approved document |
| `custom_components/mqtt_actions/manager.py` | 192-216 | `_parse_mirrors` skips `is_valid_device_id` | Info | Old cached mirrors with odd ids never updated by messages |
| `custom_components/mqtt_actions/sync.py` | 319-333 | Foreign claim replayed during start healed without an issue | Info | Missing diagnostic only |
| `custom_components/mqtt_actions/repairs.py` | 11 | `import voluptuous` instead of `probatio` | Info | Stack-rule deviation, works through alias |

No blocker anti-patterns and no unreferenced debt markers.

### Human Verification Required

None. The five items from the earlier report were executed in `03-UAT.md` (5 of 5 pass; test 2 retested after plan 03-08). Remaining open items (WR-04 and the info findings) are advisory decisions, not verification gaps.

### Gaps Summary

No gaps. Every roadmap success criterion is implemented, wired, covered by passing tests (823 tests, 11 of them against a real Mosquitto) and confirmed in a real-world UAT on two Home Assistant instances. The only code change since the previous report is the gap-closure escaping in `config_flow.py`, which is verified above. Recommended follow-up, not blocking: decide WR-04 and, if the hash is left as is, adjust the README trust-model sentence.

---

_Verified: 2026-10-02T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
