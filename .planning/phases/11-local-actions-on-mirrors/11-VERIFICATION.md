---
phase: 11-local-actions-on-mirrors
verified: 2026-10-21T11:15:00Z
status: gaps_found
score: 18/22 must-haves verified (2 failed with one root cause, 1 deferred to Phase 12, 1 needs human)
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
  - .planning/phases/11-local-actions-on-mirrors/11-18-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-18-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-19-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-19-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-20-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-20-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-21-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-21-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-22-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-22-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-23-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-23-SUMMARY.md
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
  - tests/test_retrigger.py
  - tests/test_services.py
  - tests/test_sync_follower.py
  - tests/test_test_buttons.py
  - tests/test_translations.py
covered_digest: "v3:sha256:744ad9c5d84b08c5b7133ee0c090438427d77b0c26532199d192037feab82846"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 12/14
  gaps_closed:
    - "WR-01: a tombstone no longer discards local records (11-18; MIR-08 and SC5 amended by 11-23)"
    - "WR-02: a durable save of the named trigger without local actions clears local_action_failed (11-19)"
    - "WR-03: a payload without a record list and a corrupt copy beside a missing file are unreadable; unparseable rows are kept (11-20, 11-21)"
    - "WR-04: the removal settings say 'cannot be read' instead of a device count (11-22)"
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "11-20 truth 1 (clause 'the stored bytes never change') and 11-22 truth 3 (clause 'opening the settings never writes the local Store'): a local Store this release cannot read, or only reads, is never rewritten"
    status: partial
    reason: >-
      LocalActionsStore lets Core's Store migration path run for any version mismatch, and Core's
      `_async_load_data` (homeassistant/helpers/storage.py:430-460) calls `async_save(stored)` after the migrate hook.
      So loading a file of a NEWER MINOR version (the forward-compatibility case Plans 11-20/11-21 explicitly design
      for) rewrites the file and re-stamps it as minor_version 1. This happens before the integration's shape check,
      so it also happens for a shape-invalid newer-minor payload that the integration then reports unreadable, and it
      happens on the unloaded-hub removal-count path that runs when the user opens the hub settings. Reproduced by
      probe: an unloaded hub's settings count turned {version 1, minor 2, records [...]} into {version 1, minor 1,
      records [...]}; a {version 1, minor 2, records: "text"} Store raised LocalActionsStoreUnreadableError and was
      still rewritten (minor 2 -> 1; bytes unchanged: False). The data content itself is preserved verbatim; the
      envelope changes. All regression tests use minor_version 1 fixtures, so they pass by fixture only. The same
      root cause underlies the second half of WR-05 and its first half (parseable rows with unknown keys are applied
      without the unknown key's semantics and lose that key on the next save, including a broker-triggered label
      refresh). Consequence: after a v1.1 -> v1.x(minor 2) -> v1.1 -> v1.x path, the newer release sees a minor-1
      stamp on minor-2 data and re-runs its migration; the judgment prohibition of 11-20 ('MUST NOT overwrite ... a
      local actions Store this release cannot read') is breached at the envelope level.
    artifacts:
      - path: "custom_components/mqtt_actions/local_actions_store.py"
        issue: "_async_migrate_func returns a copy for a newer minor, and the base Store then saves it (line 71-75 docstring says 'the Store saves the result'); async_load_records is reached only after that save"
      - path: "custom_components/mqtt_actions/manager.py"
        issue: "async_local_action_device_count (line 604-625) builds a writable LocalActionsStore and loads it; docstring 'Reading never writes the Store' is false for a newer-minor file"
      - path: "custom_components/mqtt_actions/local_actions.py"
        issue: "parse_local_record ignores keys outside RECORD_KEYS and local_record_data writes back only RECORD_KEYS (WR-05 part 1)"
      - path: "tests/test_local_actions_store.py"
        issue: "test_migrate_newer_minor_version_loads_the_rows asserts the rows load but not that the file stays untouched; every unreadable/no-write test uses minor_version 1"
      - path: "tests/test_hub_removal.py"
        issue: "test_unloaded_hub_counts_unknown_for_every_unreadable_store_shape and the readable-count tests use minor_version 1 only"
    missing:
      - "Never save on load for a newer minor version: e.g. load through a read-only path (Core's Store `read_only=True` exists, storage.py:239/583) for the unloaded-hub count, and make the Manager's load skip the Core re-save for minor_version > LOCAL_ACTIONS_STORE_MINOR_VERSION (or refuse to downgrade the minor stamp on later saves)"
      - "Decide WR-05 part 1: keep unknown per-row keys and write them back, or route rows with unknown keys to `preserved` (never applied); align the README 'Newer versions' bullet with the decision"
      - "Regression tests with minor_version 2 fixtures: settings count leaves hass_storage byte-identical; a shape-invalid minor-2 Store stays byte-identical; a minor-2 row with an extra key survives an edit and a label refresh"
      - "Fix the manager.py:615 docstring; record in migrate_local_actions_payload that future minor migrations must be idempotent if any re-stamp path remains"
behavior_unverified_items: []
coincidental_reliance_items:
  - truth: "11-19 truth 1: a durable save of the named trigger without local actions deletes local_action_failed (WR-02, D-19 amended, MIR-13)"
    reason: undeclared-precondition
    harden: "The clear holds only while no run of that trigger is in flight. A run already running at save time is cancelled by the rebuild, the runner's finally reports FAILURE, and async_report_local_outcome drops failures only when the record is gone, not when it has no actions; the issue comes back naming a trigger without local actions (WR-06, reproduced by probe). Declare/enforce: drop a FAILURE outcome whose current record has no actions, and add the in-flight regression test."
  - truth: "11-20 / 11-22 / 11-15 'unreadable Store bytes never change' and 'opening the settings never writes' tests"
    reason: fixture-only
    harden: "Every fixture is minor_version 1; production also receives newer-minor files (the case 11-21 designs for), where Core re-saves on load. Covered by the gap above."
deferred:
  - truth: "11-13: HACS validation passes on the Phase 11 build (with Ruff, format and hassfest)"
    addressed_in: "Phase 12"
    evidence: "Phase 12 success criterion 4: 'the release workflow, hassfest and HACS are green'. Ruff check and format --check re-run clean here. hacs.json, manifest.json and brand/ unchanged since merge base 3dc9093."
human_verification:
  - test: "Render the real hub options flow on the bench (Core 2026.9.4, frontend 20260826.7) in en and de: Settings > Integrations > MQTT Actions > Configure > menu 'init' > local actions > device picker (mirrors, orphan-only devices, and now tombstoned 'not mirrored' devices) > trigger picker (additive/replacement/muted/orphan/other kind) > editor (expanded section, mode select, ActionSelector) > save; mute and remove confirmations; the Settings step with the device count AND the new settings_unreadable step (rename .storage/mqtt_actions.local_actions to a wrong shape, restart)"
    expected: "Every step renders translated titles, descriptions, menu options and selector labels (no raw keys) in both languages; save returns to the trigger picker and applies without restart; mute and remove confirmations are distinct; settings_unreadable shows no number and says the local actions cannot be read and are deleted on removal"
    why_human: "Only the disposable 11-02 smoke form was rendered in a browser; the production HubOptionsFlow and the new settings_unreadable step have backend flow tests only (UAT test 1, still pending)"
  - test: "Review judgment-tier prohibition 11-03: 'MUST NOT make local replacement or trusted-local execution confer approval on owner actions or make an unapproved mirror adoptable'"
    expected: "Holds. Non-authoritative verdict: approval_state() (manager.py:2036) reads no local record; build_effective_trigger_plan gates owner on approval == APPROVED and not replaced (local_actions.py:344-345); async_adopt_device refuses PENDING/BLOCKED (manager.py:1453-1454); covering tests pass"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged; UAT test 2 pending)"
  - test: "Review judgment-tier prohibition 11-08: 'MUST NOT present empty replacement as deletion/owner-only behavior or imply that local replacement approves owner actions'"
    expected: "Holds. Non-authoritative verdict: local_actions_confirm_mute (en/de) says neither owner nor local actions run and muting neither approves nor rejects"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged; UAT test 3 pending)"
  - test: "Review judgment-tier prohibition 11-12: 'MUST NOT claim that the real v1.1 to v1.0.1 to v1.1 downgrade round trip or Phase 12 final-build verification has been performed'"
    expected: "Holds. Non-authoritative verdict: README:404 says the round trip has not been verified (MIR-F4); 11-release-notes.md is 'Unpublished draft' and says the round trip has not been run"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged; UAT test 4 pending)"
  - test: "Review judgment-tier prohibition 11-18: 'MUST NOT discard, rewrite or save local action records because of a broker message that carries no owner provenance, such as an empty retained config payload'"
    expected: "Holds for the named class. Non-authoritative verdict: sync._async_remove (sync.py:488-506) acts only on an existing mirror and async_remove_mirror (manager.py:2199-2226) never writes the local Store; the only remaining Store writes are edits, removals, adoption discard/restore and the D-11 label refresh (manager.py:2014-2034), which an owner config document (not an empty payload) triggers. test_tombstone_never_writes_the_local_store passes. Note: the label refresh save is where WR-05 strips unknown row keys"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-19: 'MUST NOT clear the local failure issue of a trigger that still has local actions to run, except on a proven success of exactly that trigger or the removal of its customization'"
    expected: "Holds. Non-authoritative verdict: async_set_local_action clears only `if not record.actions` after the durable commit (manager.py:1855-1857); test_only_a_durable_save_of_the_named_trigger_without_local_actions_clears_the_issue passes"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-21: 'MUST NOT erase, reorder ahead of parsed records, or execute stored local action rows that this release cannot parse'"
    expected: "Holds as written. Non-authoritative verdict: unparseable rows go to `preserved`, are written after the records (local_actions.py local_actions_payload) and are never records. Spirit caveat: rows that parse but carry keys this release does not know are executed without those keys' semantics and lose them on save (WR-05, part of the gap)"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-22: 'MUST NOT state a number of devices in the removal warning when the saved local actions could not be read'"
    expected: "Holds at Store level. Non-authoritative verdict: None selects step settings_unreadable without placeholders (config_flow.py:255-259); loaded hubs return None while _local_actions_readable is False; unloaded hubs return None on any read error. Edge (IN-08): a readable file holding only unparseable rows without a string device_id shows '0 devices' although removal deletes them"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-23: 'MUST NOT change any requirement, success criterion or decision text other than MIR-08, Phase 11 success criterion 5, the D-05 pointer and the new Amendments block'"
    expected: "Holds. Non-authoritative verdict: commit 1e426b5 changes exactly one line each in REQUIREMENTS.md (MIR-08) and ROADMAP.md (SC5) plus the release-notes Lifecycle bullet; commit b3ecda2 changes the D-05 line and adds the Amendments block only"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Decide WR-06 (11-REVIEW.md): an in-flight failing local run re-creates local_action_failed after a mute or empty-additive save cleared it"
    expected: "Owner records accept or fix. Verifier assessment: the 11-19 truth holds at the moment of the save and re-saving the mute clears it again, so no must-have is falsified as written, but the README/troubleshooting promise 'saving that trigger without local actions ... ends it' does not hold for a run in flight. If fixed, it can ride in the same gap plan as the Store gap (one-line guard in async_report_local_outcome plus a probe-based regression test)"
    why_human: "Design trade-off inside the amended D-19; the failure being reported is real, so accepting it is defensible"
---

# Phase 11: Local Actions on Mirrors Verification Report

**Phase Goal:** On a follower, the user gives a mirrored device its own actions per trigger, in addition to or instead of the owner's actions. They run locally without approval under the device's mode and breaker, survive owner changes, and never leave the instance (MIR-01, backlog 999.1).
**Verified:** 2026-10-21T11:15:00Z
**Status:** gaps_found
**Re-verification:** Yes. The previous report (human_needed, 12/14) went stale when gap-closure plans 11-18 to 11-23 changed covered files.

## Summary

The phase goal itself holds. All five ROADMAP success criteria (SC5 as amended on 2026-10-21) are met in code, and their tests pass. I re-ran 18 Phase 11 test files: 648 passed. The four earlier review warnings WR-01 to WR-04 are fixed in code, not only in the SUMMARY files:
- `MirrorRemovalCause` is gone, and a tombstone never writes the local Store.
- A save without actions clears the issue after a durable commit.
- A payload without a record list and a corrupt copy beside a missing file now raise `LocalActionsStoreUnreadableError`.
- The removal count is `int | None`, and `None` shows `settings_unreadable`.

**One gap remains.** It is in plan-level must-haves of the gap-closure round itself (11-20 and 11-22), not in a ROADMAP criterion or a MIR requirement. A local Store of a newer minor version is rewritten on load, because Core saves the result of the migration hook. The rewrite happens even when the integration then calls the file unreadable, and even when the user only opens the hub settings. The data content stays, but the envelope is re-stamped as minor 1. I reproduced this with a probe; the tests miss it because every fixture is minor 1. WR-05 has the same root cause.

WR-06 is real (I reproduced it as well), but it does not falsify a must-have as written. I record it as coincidental reliance and as an owner decision.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: options → mirror → trigger → "in addition to"/"instead of" → action editor; applies without restart; en+de texts (MIR-01, MIR-15) | ✓ VERIFIED (backend); rendering → human | `config_flow.py` HubOptionsFlow menu/pickers/editor/confirmations call `async_set_local_action`/`async_remove_local_action` (`manager.py:1814`, `:1860`); `test_local_actions_flow.py` and `test_translations.py` pass |
| 2 | SC2: local runs without approval also when owner pending/blocked/empty; owner only on exact approved hash; empty "instead of" mutes; safe defaults while unapproved (MIR-02, MIR-05, MIR-11) | ✓ VERIFIED | `build_effective_trigger_plan` (`local_actions.py:332-357`): owner = `approval == APPROVED and trigger.actions and not replaced`; local needs only record actions. `effective_policy` → `LOCAL_SAFE_POLICY` (`:414-430`). Gate-matrix tests in `test_local_action_plans.py` and `test_local_invariants.py` pass |
| 3 | SC3: additive = one Script `parallel`, one branch's failure does not stop the other; mode and breaker gate local runs; edit releases breaker; test buttons/re-trigger run effective actions; own Repairs issue (MIR-03, MIR-09, MIR-10, MIR-13) | ✓ VERIFIED | `runner.py:58` single `parallel` of owner+local; `guard_actions` only on the owner path (`:293`); `_run_trigger` (`manager.py:2815`) and `run_manual` (`:2988`); `local_action_failed_*` persistent (`:1930`). `test_local_parallel.py`, `test_test_buttons.py`, `test_retrigger.py` pass |
| 4 | SC4: nothing local leaves the instance (config, hash, export, diagnostics content, adoption payload byte-identical); approvals valid; no new re-trigger words; count-only diagnostics; approval issue count while pending + adoption refused (MIR-04, MIR-10, MIR-12, MIR-14) | ✓ VERIFIED | `approval_state()` (`manager.py:2036`) reads no local record; adoption refuses PENDING/BLOCKED (`:1453-1454`); byte-identity tests in `test_local_invariants.py` pass (adapted by 11-18 only for the tombstone case) |
| 5 | SC5 (amended): survive content change/rename/rev bump/restart/re-pin; removed option orphaned, removable, reattaches; adoption discards with log + `adopt_device` count; start-up, prunes **and tombstones** discard nothing; README documents all (MIR-06, MIR-07, MIR-08, MIR-15) | ✓ VERIFIED | `sync._async_remove` (`sync.py:488-506`) only removes an existing mirror; `async_remove_mirror` (`manager.py:2199-2226`) logs the kept count and never writes the Store; `_async_discard_local_records` is called only from adoption (`:1483`). Tests `test_tombstone_keeps_records_byte_identical_and_publishes_nothing`, `..._after_prune_...`, `..._without_a_mirror_...`, `test_tombstone_never_writes_the_local_store`, `test_tombstoned_device_records_apply_again_when_the_owner_publishes_it_again`, `test_adopt_service_reports_the_discarded_count` pass; README:367-384 |
| 6 | 11-04: separate versioned Store; v1.0.1 main-Store save never touches it; newer major refused without overwrite; no startup GC | ✓ VERIFIED | `test_newer_major_version_refuses_and_keeps_the_stored_bytes` passes (Core raises before its migrate-save for a newer major) |
| 7 | 11-10: two followers keep different overlays, shared bytes identical | ✓ VERIFIED | `test_local_multi_instance.py` passes |
| 8 | 11-14 (G-01): `local_action_failed` survives restart/prune/failed adoption; clears only on proven success, removal, completed adoption, hub removal (+ the amended save-without-actions) | ✓ VERIFIED | `test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal`, `test_tombstone_keeps_and_completed_adoption_deletes_the_local_failure_issue` pass |
| 9 | 11-15 (G-02): unreadable Store → one `local_actions_unreadable` issue (en/de); never overwritten; edits refused; cleared on good load / hub removal | ✓ VERIFIED (its scope: newer major / read error) | `manager.py:1236-1259`. The newer-minor case belongs to the gap under truth 17 |
| 10 | 11-16 (G-03): a new hub removes a leftover local Store (now including its `.corrupt` copies) before entry creation; fails closed | ✓ VERIFIED | `test_hub_removal_and_a_new_hub_delete_the_corrupt_copies_of_the_local_store`, `test_new_hub_flow_shows_an_error_when_leftover_local_actions_cannot_be_removed` pass |
| 11 | 11-17 (G-04): failed adoption keeps a tripped breaker paused | ✓ VERIFIED | `test_failed_adoption_keeps_a_tripped_breaker_paused` passes |
| 12 | 11-11/11-13: cross-file review ledger has no OPEN/ROUTED rows | ✓ VERIFIED | Unchanged since previous run |
| 13 | 11-13: Ruff, format, hassfest **and HACS** green | DEFERRED (HACS only) | Ruff check and format --check are clean (re-run here; 104 files). HACS runs in Phase 12 |
| 14 | 11-13: manual frontend evidence is honestly PASS | ? UNCERTAIN → human | The production HubOptionsFlow, and now the `settings_unreadable` step, have never been rendered (UAT test 1 pending) |
| 15 | 11-18: an empty retained config payload removes the mirror but never discards, rewrites or saves local records; device stays listed "not mirrored"; records reattach when it returns; failure issue stays; adoption/explicit/hub removal still delete | ✓ VERIFIED | See truth 5; `local_action_devices` lists record-only devices; README "Tombstone" bullet; `test_docs_say_a_tombstone_keeps_local_actions` passes; disposition WR-01 fixed |
| 16 | 11-19: durable save of the named trigger without local actions deletes its `local_action_failed`; failed save, other trigger, save with actions, stop, owner results keep it; en/de/README/troubleshooting name it | ✓ VERIFIED (coincidental-reliance) | `manager.py:1855-1857` clears after `_async_commit_local_records` only when `not record.actions`. `test_saving_the_named_trigger_without_local_actions_clears_its_local_failure_issue` and `test_only_a_durable_save_...` pass; `test_local_failure_texts_name_every_way_the_issue_clears` passes. **WR-06:** the issue returns when a run was in flight at save time (probe) |
| 17 | 11-20: a payload that is not a mapping with a record list is unreadable: load raises, Store unloaded and refuses saves, issue raised, no overlay, **stored bytes never change** | ✗ FAILED (partial) | Everything holds for minor_version 1 (`test_shape_invalid_local_store_raises_the_unreadable_issue_and_is_never_overwritten`). For a minor_version 2 envelope, Core migrates and saves before the shape check. Probe: `{"records": "text", "v2": {...}}` at minor 2 raised `LocalActionsStoreUnreadableError` and was rewritten with minor 1 (`bytes unchanged: False`) |
| 18 | 11-20: corrupt copy beside a missing file is unreadable at every start; null data / missing file load empty; another key's copy never counts; `async_remove_records` deletes own copies; en/de/troubleshooting texts | ✓ VERIFIED | `local_actions_store.py:113-118`, `:179-215`. `test_corrupt_copy_*` (store and manager), `test_null_payload_loads_no_records_like_a_missing_file`, `test_remove_records_deletes_the_corrupt_copies_of_its_own_key_only`, `test_unreadable_issue_text_explains_the_corrupt_copy_and_how_to_recover` pass |
| 19 | 11-21: unparseable rows and extra top-level keys kept verbatim after records on every save; never applied, counted or shown; later duplicates not preserved; `preserved_device_ids`; README; WR-03 fixed | ✓ VERIFIED (as written) | `parse_local_actions_payload`/`local_actions_payload` (`local_actions.py`), Store `_preserved`/`_extra` written back in `async_save_records`. `test_preserved_rows_and_unknown_keys_are_written_back_after_the_records`, `test_duplicate_identity_rows_are_not_preserved`, `test_rows_this_release_cannot_parse_survive_a_local_edit` pass. Rows that *parse* but carry unknown keys are a separate case (WR-05, in the gap) |
| 20 | 11-22: unreadable Store (loaded or unloaded hub) never shows a count; `settings_unreadable` step (en/de) stores the same options and errors; `local_actions_readable` True/False | ✓ VERIFIED | `config_flow.py:255-269`, `manager.py:604-625`, `:1783-1800`. `test_removal_settings_say_the_saved_local_actions_cannot_be_read`, `test_settings_unreadable_step_stores_the_options_and_shows_field_errors`, `test_manager_reports_whether_its_local_actions_were_readable`, `test_unloaded_hub_counts_unknown_for_every_unreadable_store_shape` pass |
| 21 | 11-22: a readable Store keeps the count, now including preserved-row devices, for loaded and unloaded hubs; **opening the settings never writes the local Store** | ✗ FAILED (partial) | The count part holds (`test_removal_count_includes_devices_of_preserved_rows`). The no-write clause is false for a newer-minor file. In the probe, `async_local_action_device_count` on an unloaded hub turned minor 2 into minor 1 in `hass_storage`. The function's own docstring ("Reading never writes the Store", `manager.py:615`) is wrong for that case |
| 22 | 11-23: amendments recorded in 11-CONTEXT.md; MIR-08, SC5 and release notes carry the amended tombstone rule; nothing else changed | ✓ VERIFIED | `git show 1e426b5` changes one line each in REQUIREMENTS.md and ROADMAP.md, plus the release-notes Lifecycle bullet; `b3ecda2` changes the D-05 pointer and adds the Amendments block; the draft is still labeled "Unpublished draft" |

**Score:** 18/22 truths verified. 2 failed (truths 17 and 21, one root cause), 1 deferred (HACS → Phase 12), 1 uncertain (production UI render → human). 0 are present but behavior-unverified.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | HACS validation of the Phase 11 build | Phase 12 | SC4: "the release workflow, hassfest and HACS are green" |

The gap is **not** deferrable. Phase 12 allows no product changes, so a fix needs an inserted Phase 11.x plan. MIR-F4 (bench downgrade round trip) is a future requirement, not a phase of this milestone.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/local_actions.py` | Pure model, plans, policy, preserved/extra payload | ✓ VERIFIED | `ParsedLocalActions.preserved/.extra`; `local_actions_payload(records, *, preserved, extra)` |
| `custom_components/mqtt_actions/local_actions_store.py` | Separate Store; `LocalActionsStoreUnreadableError`; corrupt-copy handling; `preserved_device_ids` | ⚠️ VERIFIED with gap | Substantive and wired (manager, `__init__`, config_flow). The newer-minor load path re-saves through Core (gap) |
| `custom_components/mqtt_actions/manager.py` | Tombstone keeps; save-without-actions clears; `local_actions_readable`; `local_action_removal_device_count`; `int \| None` count | ✓ VERIFIED | All symbols present and used by config_flow, sync and tests |
| `custom_components/mqtt_actions/sync.py` | `_async_remove` removes only an existing mirror | ✓ VERIFIED | `sync.py:497-504` |
| `custom_components/mqtt_actions/const.py` | `MirrorRemovalCause` removed | ✓ VERIFIED | `grep` finds no reference anywhere |
| `custom_components/mqtt_actions/config_flow.py` | `settings_unreadable` step | ✓ VERIFIED | Delegates to `async_step_settings` |
| `translations/{en,de}.json` | `settings_unreadable`, updated `local_action_failed` and `local_actions_unreadable` texts | ✓ VERIFIED | Read en/de; `test_translations.py` parity passes |
| `README.md`, `docs/troubleshooting.md` | Tombstone keeps; save-without-actions clears; newer versions; cannot-be-read removal | ✓ VERIFIED (text drift IN-10; "Newer versions" scope, see WR-05) | `test_docs.py` passes |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `sync._async_remove` / `_async_prune` | `manager.async_remove_mirror(device_id)` | no cause; no Store write | WIRED (`sync.py:303`, `:504`) |
| `manager` adoption | `_async_discard_local_records` | only caller | WIRED (`manager.py:1483`) |
| `async_set_local_action` | `_clear_local_failure_naming` | after the durable commit, only without actions | WIRED (`manager.py:1855-1857`) |
| `LocalActionsStore.async_load_records` | `Manager._async_load_local_actions` | `LocalActionsStoreUnreadableError` → issue, `_local_actions_readable=False` | WIRED (`manager.py:1236-1259`) |
| `LocalActionsStore.async_save_records` | `local_actions_payload` | `preserved=self._preserved, extra=self._extra` | WIRED |
| `async_local_action_device_count` / `local_action_removal_device_count` | `LocalActionsStore.preserved_device_ids` | set union | WIRED (`manager.py:625`, `:1799`) |
| `HubOptionsFlow.async_step_settings` | `settings_unreadable` | count `None` | WIRED (`config_flow.py:258-259`) |
| `async_remove_records` | `_remove_corrupt_copies` | executor job | WIRED; used by `__init__` removal and the G-03 new-hub cleanup |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Settings / settings_unreadable | `local_devices` | Manager records ∪ preserved ids, or a fresh Store read; `None` when unreadable | Yes | ✓ FLOWING (a newer-minor read writes the Store, see gap) |
| Device picker "not mirrored" | `local_action_devices()` | `_local_records` kept after a tombstone | Yes | ✓ FLOWING |
| `local_action_failed` clear | issue data identity | `_clear_local_failure_naming(identity)` | Yes | ✓ FLOWING (WR-06 race) |
| `adopt_device` response | `local_actions_discarded` | `_async_discard_local_records` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 11 suites (18 files: diagnostics, docs, hub_removal, local_* ×10, repairs_flow, retrigger, services, sync_follower, test_buttons, translations) | `uv run python -m pytest -q -n 8 <18 files>` | 648 passed in 14.06s | ✓ PASS |
| Lint and format | `uv run ruff check custom_components tests`; `ruff format --check` | All checks passed; 104 files already formatted | ✓ PASS |
| Settings count of an unloaded hub leaves a newer-minor Store untouched (11-22 truth 3) | probe `test_probe_newer_minor` (scratchpad) | minor_version 2 → 1 rewritten; count 1 | ✗ FAIL |
| Shape-invalid newer-minor Store stays byte-identical (11-20 truth 1) | probe `test_probe_newer_minor_unreadable` | raised `LocalActionsStoreUnreadableError`; `bytes unchanged: False` | ✗ FAIL |
| Mute save during an in-flight failing local run keeps the issue cleared (WR-06) | reviewer probe `test_probe_mute_race.py`, re-run here | absent right after save; present after settle naming `switch/on`, record actions `[]` | ✗ FAIL (no must-have falsified as written; see coincidental reliance) |

Probe files:
- `/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-mqtt-actions-integration/667d23fa-9fde-4c75-b77c-e0d2d74cb17b/scratchpad/verify/test_probe_newer_minor.py`
- `/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-mqtt-actions-integration/667d23fa-9fde-4c75-b77c-e0d2d74cb17b/scratchpad/verify/test_probe_mute_race.py`

Run them from the repo root with `PYTHONPATH=. uv run python -m pytest --rootdir=<dir> -c pyproject.toml -s -p no:logging <file>`; the `conftest.py` in that directory re-exports `tests.conftest`.

I did not re-run the full suite. The orchestrator gate gave 2100 passed and 2 pre-existing xfails.

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists, and no plan declares one. Step 7c does not apply.

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| MIR-01 | 11-02, 11-08, 11-11, 11-13 | ✓ SATISFIED (rendering: human) | Truth 1 |
| MIR-02 | 11-01, 11-03, 11-05, 11-10, 11-16 | ✓ SATISFIED | Truths 2, 10, 15 (reattach) |
| MIR-03 | 11-01, 11-03, 11-07 | ✓ SATISFIED | Truth 3 |
| MIR-04 | 11-01, 11-04, 11-09, 11-10 | ✓ SATISFIED | Truth 4 |
| MIR-05 | 11-01, 11-03, 11-08, 11-15, 11-19, 11-20 | ✓ SATISFIED | Truths 2, 16. An empty "instead of" mutes. The 11-20 gap touches only the forward-compat Store envelope, not muting |
| MIR-06 | 11-04, 11-05, 11-06, 11-10, 11-15, 11-20, 11-21 | ✓ SATISFIED | Truths 5, 6, 19. Survival of owner changes, restarts and re-pins holds. The newer-minor re-stamp is the plan-level gap, not this requirement's wording |
| MIR-07 | 11-04, 11-06, 11-08, 11-18 | ✓ SATISFIED | Truths 5, 15 |
| MIR-08 (amended) | 11-06, 11-09, 11-12, 11-18, 11-22, 11-23 | ✓ SATISFIED | Truths 5, 15, 22 |
| MIR-09 | 11-05, 11-07, 11-10, 11-17 | ✓ SATISFIED | Truths 3, 11 |
| MIR-10 | 11-01, 11-07, 11-10 | ✓ SATISFIED | Truths 3, 4 |
| MIR-11 | 11-01, 11-03, 11-05, 11-10 | ✓ SATISFIED | Truth 2 |
| MIR-12 | 11-06, 11-07, 11-08 | ✓ SATISFIED | Truth 4 |
| MIR-13 | 11-01, 11-03, 11-07, 11-14, 11-19 | ✓ SATISFIED | Truths 3, 8, 16 (WR-06 race noted) |
| MIR-14 | 11-01, 11-09 | ✓ SATISFIED | Truth 4 |
| MIR-15 | 11-02, 11-08, 11-09, 11-12, 11-14..11-16, 11-18..11-22 | ✓ SATISFIED (with doc caveats) | en/de parity and `test_docs.py` pass. The README "Newer versions" bullet is accurate for unparseable rows only (WR-05). Troubleshooting text drift (IN-10) |

REQUIREMENTS.md maps exactly MIR-01 to MIR-15 to Phase 11, and every ID is claimed by at least one plan. No requirement is orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| Phase-modified files | - | TBD/FIXME/XXX/TODO/HACK/"not yet implemented" | none | Only the identifiers `ADOPT_PLACEHOLDERS` and `*_PLACEHOLDERS` in tests match |
| `local_actions_store.py` / `manager.py` | 71-75 / 604-625 | A newer-minor load re-saves through Core's migration path | 🛑 Blocker (plan must-haves 11-20 T1, 11-22 T3) | Gap above. Deterministic evidence: two probes |
| `local_actions.py` | `parse_local_record` / `local_record_data` | WR-05: unknown keys of parseable rows are ignored when applied and dropped on save | ⚠️ Warning (in the gap's fix scope) | Forward-compat data loss once a newer minor adds a row field |
| `manager.py` | 1876-1905 | WR-06: an in-flight FAILURE outcome re-creates the issue after a mute save | ⚠️ Warning | It can be undone by saving the mute again. Owner decision, or a one-line guard in the gap plan |
| `manager.py`, `local_actions_store.py`, `docs/troubleshooting.md` | various | IN-08 (preserved rows outlive adoption/removal; "0 devices" for rows without `device_id`), IN-09 (Core `storage_corruption_*` issue left after the copy is deleted), IN-10 (text drift), IN-01..IN-07 carried forward | ℹ️ Info | None falsifies a truth |

### Human Verification Required

These are listed in the frontmatter `human_verification`. They are still pending after the gap is resolved:
1. **Real HubOptionsFlow rendering (en/de), including the new `settings_unreadable` step and the "not mirrored" device after a tombstone.** This carries forward UAT test 1, which is still pending.
2. **Judgment-tier prohibitions 11-03, 11-08, 11-12** (UAT tests 2-4, still pending) and **11-18, 11-19, 11-21, 11-22, 11-23** (new). For each, the frontmatter gives a non-authoritative verdict that it holds, with the caveats noted.
   - The 11-20 prohibition is not on this list: the probe shows it breached at the envelope level, so it is part of the gap.
3. **WR-06 disposition:** accept or fix.

UAT test 5 (the WR-01 to WR-04 dispositions) is resolved: the owner decided on 2026-10-21 (11-CONTEXT Amendments), and all four rows read `fixed`. `11-UAT.md` should drop it, and add the new items when the next UAT runs.

### Gaps Summary

**Gap G-1: newer-minor local Store is rewritten on load.** This is one root cause behind two failed plan truths (11-20 T1, 11-22 T3) and the 11-20 prohibition.
- `LocalActionsStore` relies on Core's `Store._async_load_data`. For any version mismatch, Core migrates and then calls `async_save`.
- For a newer minor version, the forward-compatibility case that the 11-20/11-21 round was built for, three things follow:
  - opening the hub settings on an unloaded hub writes the Store;
  - an unreadable newer-minor Store is rewritten before it is reported unreadable;
  - the file is re-stamped as minor 1 (data content unchanged).
- Together with WR-05, a newer release's row fields are applied without their meaning and erased on the next save.
- No released version writes minor 2 today, so there is no data loss on any real instance yet. But v1.1's behavior is frozen once it ships.
- The fix is small:
  - load read-only for the count path, and skip the Core re-save for newer minors;
  - keep or preserve unknown row keys;
  - add minor-2 regression tests.
- It needs an inserted Phase 11.x plan before Phase 12, because Phase 12 allows no product changes.

**This may look intentional.** D-22 ("Loading never rewrites the Store except through the migration hook") already accepts writes from the migration hook, and the data content survives. If the owner accepts the re-stamp for v1.1 and leaves forward compatibility to the next minor release (with idempotent migrations), add this to the frontmatter:

```yaml
overrides:
  - must_have: "opening the settings never writes the local Store and the stored bytes never change for a local actions Store this release cannot read"
    reason: "Only a newer-minor envelope is re-stamped by Core's migration save (D-22 allows migration-hook writes); data content is preserved; no minor-2 writer exists; the next minor release must keep migrations idempotent"
    accepted_by: "akentner"
    accepted_at: "2026-10-21T00:00:00Z"
```

The override would not cover WR-05 part 1 (row keys lost on save), which then stays an open warning to decide.

---

_Verified: 2026-10-21T11:15:00Z_
_Verifier: Claude (gsd-verifier)_
