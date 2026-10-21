---
phase: 11-local-actions-on-mirrors
verified: 2026-10-21T10:30:00Z
status: human_needed
score: 12/14 must-haves verified (1 deferred to Phase 12, 1 needs human)
covered_files:
  - .planning/phases/11-local-actions-on-mirrors/11-01-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-01-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-02-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-02-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-03-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-03-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-04-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-04-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-05-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-05-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-06-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-06-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-07-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-07-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-08-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-08-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-09-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-09-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-10-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-10-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-11-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-11-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-12-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-12-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-13-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-13-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-14-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-14-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-15-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-15-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-16-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-16-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-17-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-17-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/diagnostics.py
  - custom_components/mqtt_actions/local_actions.py
  - custom_components/mqtt_actions/local_actions_store.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/retrigger.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/services.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/trust.py
  - docs/diagnostics.md
  - docs/operations.md
  - docs/troubleshooting.md
  - tests/fake_broker.py
  - tests/helpers.py
  - tests/test_diagnostics.py
  - tests/test_discovery_export.py
  - tests/test_docs.py
  - tests/test_hub_removal.py
  - tests/test_local_action_plans.py
  - tests/test_local_actions_flow.py
  - tests/test_local_actions_lifecycle.py
  - tests/test_local_actions_manager.py
  - tests/test_local_actions_store.py
  - tests/test_local_actions_store_instances.py
  - tests/test_local_invariants.py
  - tests/test_local_multi_instance.py
  - tests/test_local_parallel.py
  - tests/test_native_cleanup.py
  - tests/test_repairs_flow.py
  - tests/test_services.py
  - tests/test_sync_follower.py
  - tests/test_translations.py
covered_digest: "v3:sha256:e0128a4ef35b9b43c307fbe4e892182bc0b8889f8f6a76e0ae2eb8f9f490e25c"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "11-13: HACS validation passes on the Phase 11 build (with Ruff, format and hassfest)"
    addressed_in: "Phase 12"
    evidence: "Phase 12 success criterion 4: 'the release workflow, hassfest and HACS are green'. Ruff/format re-run clean here; hassfest ran via podman (11-CROSS-FILE-REVIEW Final Gate). HACS NOT RUN because hacs/action fetches from GitHub and the branch is unpushed; hacs.json, manifest.json and brand/ are byte-unchanged since merge base 3dc9093 (git diff --stat empty)."
human_verification:
  - test: "Render the real hub options flow on the bench (Core 2026.9.4, frontend 20260826.7) in en and de: Settings > Integrations > MQTT Actions > Configure > menu 'init' > local actions > device picker (mirrors plus orphan-only devices) > trigger picker (status markers additive/replacement/muted/orphan/other kind) > editor (expanded section, mode select, ActionSelector) > save; then mute confirmation and remove confirmation; then the Settings step with the local-action device count"
    expected: "Every step renders with translated titles, descriptions, menu options and selector labels (no raw keys) in both languages; save returns to the trigger picker and the change applies without restart; the mute and remove confirmations are distinct and readable"
    why_human: "Only the disposable 11-02 smoke form was rendered in a browser. The production HubOptionsFlow menus, pickers and confirmations are covered by backend flow tests only (tests/test_local_actions_flow.py); visual rendering and label quality cannot be grep-verified (11-UI-REVIEW 19/24, 11-13 boundary assigns this to Phase 11 human UAT)"
  - test: "Review judgment-tier prohibition 11-03: 'MUST NOT make local replacement or trusted-local execution confer approval on owner actions or make an unapproved mirror adoptable'"
    expected: "Holds. Non-authoritative verifier verdict: approval_state() never reads local records (manager.py:2004-2027); build_effective_trigger_plan gates owner on approval == approved AND not replaced (local_actions.py:322-323); async_adopt_device refuses PENDING/BLOCKED (manager.py:1446-1447); tests test_every_trigger_replaced_keeps_pending_owner_hash_yaml_and_refused_adoption, test_adoption_refused_for_a_pending_owner_keeps_records_even_with_every_trigger_replaced and test_replacement_never_grants_the_owner_branch pass"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged: true in the plan)"
  - test: "Review judgment-tier prohibition 11-08: 'MUST NOT present empty replacement as deletion/owner-only behavior or imply that local replacement approves owner actions'"
    expected: "Holds. Non-authoritative verdict: options.step.local_actions_confirm_mute (en/de) says the trigger runs neither owner nor local actions, that muting neither approves nor rejects, and that muting is not removal; local_actions_confirm_remove says removal restores owner actions only while approved; edit data_description says local actions never approve owner actions"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged: true in the plan)"
  - test: "Review judgment-tier prohibition 11-12: 'MUST NOT claim that the real v1.1 to v1.0.1 to v1.1 downgrade round trip or Phase 12 final-build verification has been performed'"
    expected: "Holds. Non-authoritative verdict: README 'Downgrading to 1.0.1' states 'This downgrade round trip has not been verified on real instances; that check is deferred (MIR-F4)'; 11-release-notes.md is labeled 'Unpublished draft' and says the round trip 'is deferred as MIR-F4 and has not been run'"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged: true in the plan)"
  - test: "Decide the four open code-review warnings (11-REVIEW-DISPOSITION.md, all 'open'): WR-01 stray empty config payload discards local records permanently; WR-02 local_action_failed cannot clear after the user mutes the trigger or empties its additive actions; WR-03 JSON-corrupt or wrong-shape local Store loads as empty without local_actions_unreadable; WR-04 hub-removal warning says 0 devices when the local Store is unreadable"
    expected: "Owner records accept or fix for each (fix = inserted Phase 11.x gap plan before Phase 12 starts, because Phase 12 allows no product changes). Verifier assessment: none defeats a ROADMAP success criterion or a plan must-have as written (details in the report)"
    why_human: "Each is a design trade-off or edge case inside the specified behavior; choosing between accept and fix is an owner decision"
---

# Phase 11: Local Actions on Mirrors Verification Report

**Phase Goal:** On a follower, the user gives a mirrored device its own actions per trigger, in addition to or instead of the owner's actions. They run locally without approval under the device's mode and breaker, survive owner changes, and never leave the instance (MIR-01, backlog 999.1).
**Verified:** 2026-10-21T10:30:00Z
**Status:** human_needed
**Re-verification:** No (initial verification)

## Goal Achievement

The production code delivers the goal. I read the code paths, not the SUMMARY claims:
- `local_actions.py`: pure model, effective plan, policy, outcome reducer.
- `runner.py` `async_build_effective`: one Script, a native `parallel` with owner branch 0 and local branch 1, and `guard_actions` on the owner subtree only.
- `manager.py`:
  - local Store loaded first in `async_start` (line 942), before `_async_restore_mirrors`;
  - locked set/remove with save-before-apply;
  - breaker release only after a durable edit;
  - safe policy while the owner hash is unapproved;
  - lifecycle causes;
  - adoption discard/rollback;
  - independent persistent `local_action_failed`.
- `config_flow.py` `HubOptionsFlow`: thin client of the Manager APIs.
- `diagnostics.py`: integer counts only.
- `services.py`: `local_actions_discarded`.
- `sync.py`: TOMBSTONE cause.

I re-ran 17 Phase 11 test files (570 passed). They exercise every behavior-dependent truth below.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: On a follower the user opens options, picks mirror + trigger (switch on/off, Select option), chooses "in addition to"/"instead of", edits actions; applies without restart; en+de texts (MIR-01, MIR-15) | ✓ VERIFIED (backend); rendering in Human Verification | `config_flow.py:210-512` menu init→local_actions→device→trigger→edit→confirm_mute/confirm_remove; `async_set_local_action` saves and rebuilds at once (`manager.py:1788-1827`, `1959-1980`). Tests: `test_save_and_reopen_additive_switch_trigger`, `test_save_and_reopen_select_option_and_switch_off_reach_the_same_editor`, `test_edit_saves_immediately_and_applies_without_restart_or_retroactive_run`; `test_translations.py` en/de parity green |
| 2 | SC2: Local runs without approval also while owner is pending/blocked/empty; owner runs only on exact approved hash; empty "instead of" mutes; unapproved owner → safe defaults for run_on_startup, run mode and breaker (MIR-02, MIR-05, MIR-11) | ✓ VERIFIED | `build_effective_trigger_plan` (`local_actions.py:309-334`): owner requires `approval == "approved"` and `not replaced`; local requires only record actions; `effective_policy` returns `LOCAL_SAFE_POLICY` unless approved (`:400-410`); `_build_mirror` starts on the safe policy (`manager.py:2336-2361`). Tests: 24-row gate matrix bound to production (`test_production_plan_matches_gate_row`), `test_one_additive_pending_trigger_runs_only_the_local_branch`, `test_pending_local_policy_is_false_serial_5_10_10_whatever_the_owner_says`, `test_empty_replacement_needs_the_mute_confirmation_before_any_save` |
| 3 | SC3: Additive = owner+local in parallel in the single device Script, a failure of one does not stop the other; mode (observe/disabled) and breaker apply to local runs; a local edit releases a tripped breaker; test buttons and re-trigger run the effective actions; local failures get their own Repairs issue (MIR-03, MIR-09, MIR-10, MIR-13) | ✓ VERIFIED | `runner.py:53-60`, `:169-229`: one `parallel`, one Script (`script_count == 1`). `_run_trigger` gates on mode then breaker (`manager.py:2786-2814`); `run_manual` is the single gate for buttons, the legacy test topic and the re-trigger (`:2958-2991`); breaker reset after a durable save (`:1976-1980`); `local_action_failed_<id>` is a separate prefix (`:1880-1907`). Tests: `test_owner_failure_beside_a_local_branch_still_raises_the_owner_issue` (the local branch still succeeds), `test_local_failure_beside_a_clean_owner_branch_never_raises_the_owner_issue`, `test_observe_disabled_and_tripped_breaker_refuse_local_runs`, `test_successful_edit_releases_only_the_target_breaker_and_runs_nothing`, `test_test_button_legacy_test_and_retrigger_run_what_a_state_change_runs`, `test_local_failure_issue_family_is_a_separate_device_issue_prefix` |
| 4 | SC4: Nothing local leaves the instance: central config, actions hash, export, diagnostics content and adoption payload byte-identical; approvals stay valid; no new re-trigger words; diagnostics counts only; approval issue states replaced-trigger count while staying pending and adoption refused (MIR-04, MIR-10, MIR-12, MIR-14) | ✓ VERIFIED | `DeviceSpec` is never mutated, and plans are deep copies. `ManualRunResult` maps onto the existing ACK/REASON words (`retrigger.py:66-78`). `diagnostics.py:82-112` emits only ints. `{replaced}` is rendered in `issues.approval_required.fix_flow.step.confirm` (en/de line 424) via `repairs.py:84`. Tests: `test_owner_hash_and_document_bytes_equal_the_owner_only_baseline`, `test_adoption_subentry_and_adopted_document_bytes_equal_the_owner_only_baseline`, `test_export_publication_bytes_equal_the_owner_only_baseline`, `test_every_lifecycle_transition_publishes_no_local_content`, `test_retrigger_acknowledgement_vocabulary_is_unchanged`, `test_every_trigger_replaced_keeps_pending_owner_hash_yaml_and_refused_adoption`, `test_approval_view_and_issue_count_active_replacements_only` |
| 5 | SC5: Survive owner content change, rename, rev bump, restart, re-pin; removed Select option → inactive, listed as orphan, removable, reattaches on same StateValue; tombstone/adoption discard with log and `adopt_device` count; start-up and transient prune discard nothing; README documents modes, mute, parallel, lifecycle, downgrade and `{{ state }}` (MIR-06, MIR-07, MIR-08, MIR-15) | ✓ VERIFIED | Identity = device id + kind + normalized StateValue (`local_actions.py:65-76`). `async_remove_mirror` discards only on TOMBSTONE (`manager.py:2167-2197`); `sync.py:489-505` passes TOMBSTONE also without a mirror. Adoption discards before publishing and restores on failure (`:1453-1531`). README sections at 272-397. Tests: `test_records_survive_owner_{content_change,rename,revision_bump,restart,repin}`, `test_removed_option_orphans_the_record_and_exact_return_reattaches`, `test_orphan_record_stays_removable`, `test_transient_prune_keeps_local_records_byte_identical`, `test_startup_cleanup_of_a_cached_mirror_keeps_local_records`, `test_tombstone_discards_records_saves_at_once_and_publishes_nothing`, `test_adopt_service_reports_the_discarded_count`; `test_docs.py` |
| 6 | 11-04: Separate versioned Store that a v1.0.1 main-Store save neither reads nor rewrites; newer major refused without overwrite; no startup GC | ✓ VERIFIED | `local_actions_store.py` own key/version, `_loaded=False` refuses saves after a failed load. Tests: `test_old_main_store_save_leaves_the_local_store_byte_identical`, `test_newer_major_version_refuses_and_keeps_the_stored_bytes`, `test_round_trip_keeps_orphan_and_kind_mismatched_records_without_rewriting` |
| 7 | 11-10: Two followers keep different overlays for the same owner mirror, each runs only its own, shared bytes identical | ✓ VERIFIED | `tests/test_local_multi_instance.py` (6 tests, multi_instance tier) passed in this run |
| 8 | 11-14 (G-01): `local_action_failed` survives restart, transient prune and failed adoption; clears only on proven success, removal, saved tombstone discard, completed adoption, hub removal | ✓ VERIFIED | `is_persistent=True` (`manager.py:1898`), `keep_local_failure=True` in prune/drop (`:2223`, `:1580`), start cleanup only in the load success branch (`:1250-1252`). Tests: `test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal`, `test_refused_local_load_keeps_every_local_failure_issue` |
| 9 | 11-15 (G-02): An unreadable local Store raises one non-fixable `local_actions_unreadable` issue (en/de); file never overwritten; edits refused; deleted on next good load and on hub removal | ✓ VERIFIED (with WR-03 residual, see Warnings) | `manager.py:1222-1252`, `:558-568`. Tests: `test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay` (bytes unchanged, `save_failed`), `test_readable_local_store_deletes_the_unreadable_issue_at_the_next_start`, `test_hub_removal_deletes_the_unreadable_local_store_issue` |
| 10 | 11-16 (G-03): A new hub removes a leftover local Store before entry creation; never touches an existing hub; fail closed with `local_actions_not_removed` | ✓ VERIFIED | `config_flow.py:146-164`. `tests/test_hub_removal.py` green |
| 11 | 11-17 (G-04): A failed adoption keeps a tripped breaker paused and saves the trip at once | ✓ VERIFIED | `_async_restore_adopted_mirror` (`manager.py:1533-1546`). Test: `test_failed_adoption_keeps_a_tripped_breaker_paused` |
| 12 | 11-11/11-13: Review ledger has zero OPEN/ROUTED rows before the final gate; no finding deferred to Phase 12 | ✓ VERIFIED | `11-CROSS-FILE-REVIEW.md`: F-01..F-04 FIXED (6f381cb, 44c5fe6, c9c9c63, 8eb4734), F-05..F-20 NO-CHANGE; grep for OPEN/ROUTED rows is empty |
| 13 | 11-13: MIR suites, unit/multi-instance/broker tiers, Ruff, format, hassfest **and HACS** pass with no new skip/xfail | DEFERRED (HACS only) | Ruff check + format --check are clean (re-run here). The orchestrator's full run was 2072 passed / 2 pre-existing xfail. hassfest passed via podman per the ledger. HACS was NOT RUN; Phase 12 SC4 covers it (see Deferred) |
| 14 | 11-13: Manual frontend evidence is honestly PASS | ? UNCERTAIN → human | `11-FRONTEND-SMOKE.md` is a real, human-approved PASS for a disposable form with the same section + ActionSelector shape. The production `HubOptionsFlow` (menus, pickers, confirmations) has never been rendered |

**Score:** 12/14 truths verified. 1 is deferred to Phase 12 (HACS). 1 is uncertain and routed to human verification. 0 are present but behavior-unverified.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | HACS validation of the Phase 11 build | Phase 12 | SC4: "the release workflow, hassfest and HACS are green". HACS-relevant files (`hacs.json`, `manifest.json`, `brand/`) are unchanged since 3dc9093 (`git diff --stat` empty). The ledger states that Phase 12 release work must wait for the first-push HACS result |

The bench check on real instances (QLT-05), the final-build re-verification, and the version bump, tag and release belong to Phase 12. The downgrade round trip belongs to MIR-F4. None of these is counted here.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/local_actions.py` | HA-free overlay model, plans, policy, reducer | ✓ VERIFIED | 560 lines. Imported by runner, manager, Store, flow and diagnostics |
| `custom_components/mqtt_actions/local_actions_store.py` | Separate versioned Store | ✓ VERIFIED | Used by manager (load/save/remove/close), `__init__` removal, config_flow G-03 |
| `custom_components/mqtt_actions/runner.py` | One-Script effective dispatcher, branch outcomes | ✓ VERIFIED | `async_build_effective` called from `_async_refresh_mirror_script` (`manager.py:2151`); `on_local_outcome` is wired to `async_report_local_outcome` |
| `custom_components/mqtt_actions/manager.py` | Overlay load, mutation, lifecycle, policy, issues | ✓ VERIFIED | Load first in `async_start`; APIs consumed by flow, diagnostics, services, sync |
| `custom_components/mqtt_actions/config_flow.py` | Hub options menu, editor, confirmations, G-03 | ✓ VERIFIED | Calls `async_set_local_action` / `async_remove_local_action`. Writes no ConfigEntry options for local data |
| `custom_components/mqtt_actions/diagnostics.py` | Count-only local summary | ✓ VERIFIED | Integers from `local_action_counts*` only |
| `custom_components/mqtt_actions/services.py` | `local_actions_discarded` in the adopt response | ✓ VERIFIED | Line 318 |
| `custom_components/mqtt_actions/translations/{en,de}.json` | All new texts | ✓ VERIFIED | `test_translations.py` parity green |
| `README.md`, `docs/{operations,troubleshooting,diagnostics}.md` | MIR-15 docs | ✓ VERIFIED | `tests/test_docs.py` green; content read |
| `tests/test_local_*.py` (9 files) | Invariant, gate, lifecycle, flow, multi-instance and parallel coverage | ✓ VERIFIED | All passing |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `manager._async_refresh_mirror_script` | `runner.async_build_effective` | effective plans + policy snapshot, `on_swap=_apply_policy` | WIRED (`manager.py:2146-2153`) |
| `runner._async_build_effective_script` | `trust.guard_actions` | `_replace_at(owner_path)` only | WIRED (`runner.py:291-293`) |
| `manager.async_start` | `LocalActionsStore.async_load_records` | `_async_load_local_actions` before `_async_restore_mirrors` | WIRED (`manager.py:942`, `952`) |
| `sync._async_remove` | `manager.async_remove_mirror(cause=TOMBSTONE)` | empty config payload, also without a mirror | WIRED (`sync.py:505`) |
| `services` adopt handler | `manager.async_adopt_device` | `AdoptionResult.local_actions_discarded` | WIRED (`services.py:318`) |
| `retrigger` | `manager.run_manual` | `pause_spares_owner=False`, existing ACK map | WIRED (`retrigger.py:428`) |
| `HubOptionsFlow` | Manager read/set/remove APIs | `entry.runtime_data` | WIRED |
| `__init__.async_remove_entry` | `async_remove_local_state` | both removal modes | WIRED; `test_hub_removal.py` green |
| `config_flow.async_step_user` | `LocalActionsStore.async_remove_records` | before `async_create_entry` | WIRED (`config_flow.py:152`) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Trigger picker rows | `manager.local_action_triggers()` | `_local_records` (Store) + `mirrors[*].spec` | Yes | ✓ FLOWING |
| Settings warning count | `async_local_action_device_count` | Manager records or a Store read | Yes (0 when unreadable, WR-04) | ✓ FLOWING |
| Diagnostics `local_actions` | `local_action_counts()` | `_local_records` | Yes | ✓ FLOWING |
| Approval confirm `{replaced}` | `ApprovalView.replaced_trigger_count` | `local_replaced_trigger_count` | Yes | ✓ FLOWING |
| `adopt_device` response | `AdoptionResult.local_actions_discarded` | `_async_discard_local_records` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 11 targeted suites (plans, flow, lifecycle, manager, store, invariants, multi-instance, parallel, hub removal, diagnostics, docs, translations, services, retrigger, test buttons, repairs) | `uv run python -m pytest -q -n 8 <17 files>` | 570 passed in 12.38s | ✓ PASS |
| Lint and format | `uv run ruff check custom_components tests` and `ruff format --check` | All checks passed; 104 files formatted | ✓ PASS |
| HACS-relevant files unchanged since the last green HACS run | `git diff --stat 3dc9093..HEAD -- hacs.json manifest.json brand/` | empty | ✓ PASS (supporting only) |

I did not re-run the full suite. The orchestrator gate gave 2072 passed and 2 pre-existing Phase 8 xfails.

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists, and no plan declares one. Step 7c does not apply. (`11-parallel-probe.py` is a research artifact. Its contract is pinned permanently in `tests/test_local_parallel.py`, which passes.)

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| MIR-01 | 11-02, 11-08, 11-11, 11-13 | ✓ SATISFIED (rendering: human) | Truth 1 |
| MIR-02 | 11-01, 11-03, 11-05, 11-10, 11-16 | ✓ SATISFIED | Truth 2, 10 |
| MIR-03 | 11-01, 11-03, 11-07 | ✓ SATISFIED | Truth 3 |
| MIR-04 | 11-01, 11-04, 11-09, 11-10 | ✓ SATISFIED | Truth 4 |
| MIR-05 | 11-01, 11-03, 11-08, 11-15 | ✓ SATISFIED | Truth 2, 9 |
| MIR-06 | 11-04, 11-05, 11-06, 11-10, 11-15 | ✓ SATISFIED | Truth 5, 6 |
| MIR-07 | 11-04, 11-06, 11-08 | ✓ SATISFIED | Truth 5 |
| MIR-08 | 11-06, 11-09, 11-12 | ✓ SATISFIED | Truth 5 (see WR-01) |
| MIR-09 | 11-05, 11-07, 11-10, 11-17 | ✓ SATISFIED | Truth 3, 11 |
| MIR-10 | 11-01, 11-07, 11-10 | ✓ SATISFIED | Truth 3, 4 |
| MIR-11 | 11-01, 11-03, 11-05, 11-10 | ✓ SATISFIED | Truth 2 |
| MIR-12 | 11-06, 11-07, 11-08 | ✓ SATISFIED | Truth 4 |
| MIR-13 | 11-01, 11-03, 11-07, 11-14 | ✓ SATISFIED | Truth 3, 8 (see WR-02) |
| MIR-14 | 11-01, 11-09 | ✓ SATISFIED | Truth 4 |
| MIR-15 | 11-02, 11-08, 11-09, 11-12, 11-14, 11-15, 11-16 | ✓ SATISFIED | Truth 1, 5 |

All 15 IDs that REQUIREMENTS.md maps to Phase 11 are claimed by at least one plan. No requirement is orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (all 38 phase-modified files) | - | TBD/FIXME/XXX, TODO/HACK/PLACEHOLDER, "not yet implemented" | none found | - |
| `sync.py` / `manager.py` | 489-505 / 2167-2197 | WR-01: any empty retained config payload counts as a tombstone and permanently discards local records. Before Phase 11 this case healed itself, because the owner republishes. | ⚠️ Warning | It matches MIR-08 as written, and owners publish a config tombstone only on device deletion (`manager.py:507`, `2572`). A stray clear from a third-party client is irreversible data loss on this instance, so the owner should decide |
| `manager.py` | 1788-1827 | WR-02: muting the trigger or emptying its additive actions leaves a `local_action_failed` issue that can never clear unless the customization is removed, and removal restores the owner actions | ⚠️ Warning | It matches the 11-07/11-14 clear rules and the README as written. It is a UX defect, not a broken invariant |
| `local_actions_store.py` | 87-99 | WR-03: a JSON-corrupt file is renamed to `.corrupt.*` by Core, which raises its own CRITICAL `storage_corruption` issue, so the integration's `local_actions_unreadable` does not appear. A valid-JSON file with the wrong shape loads as empty, and the next save overwrites it | ⚠️ Warning | 11-15 scoped "refused" to newer major / unknown version / read error and documented the wrong-shape assumption (11-15-PLAN:95). In the corrupt case the bytes survive in the `.corrupt` copy and the user gets a Repairs issue (Core's) |
| `manager.py` | 605-622 | WR-04: the removal warning shows 0 devices when the Store is unreadable, but removal deletes the file | ⚠️ Warning | Edge case of the downgrade scenario. 11-09 truth holds for readable Stores |
| `manager.py`, `runner.py`, `services.py` | various | IN-01..IN-07 (unused issue-level placeholder, test-only seams, double mode gate, sort docstring, double log, shared response variables across trust levels, untranslated adopt save error) | ℹ️ Info | None blocks a truth. IN-06 is a documentation gap at the trust boundary and is worth a README sentence |

### Human Verification Required

#### 1. Real HubOptionsFlow rendering (en/de)

**Test:** On the bench (Core 2026.9.4, frontend 20260826.7), go to MQTT Actions > Configure. Walk the path: menu, local actions, device picker, trigger picker, editor, save. Then open the mute confirmation and the remove confirmation. Then open Settings and check the local-action device count. Use a pending mirror, an approved mirror, and an orphan Select option.
**Expected:** Every title, description, menu option and selector label is translated, with no raw keys, in both languages. Status markers are readable. The section is expanded. Save returns to the picker and applies at once.
**Why human:** Only the disposable 11-02 smoke form was rendered in a browser. The production flow has backend tests only.

#### 2-4. Judgment-tier prohibitions (11-03, 11-08, 11-12)

**Test:** Review each prohibition against the cited code, text and tests (see the frontmatter).
**Expected:** Each holds. The verifier's verdict is non-authoritative.
**Why human:** unverified-prohibition, human review recommended (judgment tier, flagged).

#### 5. Disposition of the open code-review warnings WR-01..WR-04

**Test:** Decide accept or fix for each warning. A fix needs an inserted Phase 11.x, because Phase 12 allows no product change.
**Expected:** A recorded disposition in `11-REVIEW-DISPOSITION.md`.
**Why human:** These are trade-offs within the specified behavior. WR-01 (irreversible discard on an unauthenticated empty payload) and WR-02 (an issue that cannot clear after a mute) are the two with user-visible impact.

### Gaps Summary

There are no blocking gaps. All five ROADMAP success criteria and the plan must-haves hold in the code. I checked them with the 570 tests I re-ran, not with the SUMMARY narrative. The open items:
- One deferred item: HACS validation, which Phase 12 SC4 covers.
- One uncertain truth: the production options flow has never been rendered.
- Three flagged judgment-tier prohibitions. Each holds by inspection.
- Four open review warnings, all inside the specified behavior.

None of these defeats the phase goal. The real-UI render and the WR dispositions should be settled before Phase 12 starts. A WR fix would need an inserted Phase 11.x, because Phase 12 allows no product changes.

---

_Verified: 2026-10-21T10:30:00Z_
_Verifier: Claude (gsd-verifier)_
