# Phase 11 Cross-File Review Ledger (D-23)

**Plan:** 11-11 (review only: this ledger is the only file the plan changes)
**Reviewed build:** branch `gsd/phase-11-local-actions-on-mirrors` at `e5cedd5`. The Phase 11 production diff is
`git diff 762a3db..HEAD -- custom_components/`: 15 files, +2423/-128.
**Method:** the review follows data paths, not file order. Every path below was traced through the current source,
and each claim cites `file:line`. A green suite (2056 passed, 2 xfailed at the start of this plan) was not taken as
proof that a path is safe. Each finding was checked against the code before it was recorded.

**Not claimed here:** no downgrade round trip (MIR-F4), no final-build bench, no cross-instance real-broker
verification and no release. These stay with Phase 12. Plan 11-13 runs the final Phase 11 gate after this ledger.

## Status vocabulary

A finding row has exactly one status. Open means recorded but not yet routed. Routed means a bounded Phase 11 gap
(`G-NN`) owns the fix, and a gap-closure plan sets the row to fixed together with the commit and the regression test
id. No-change is allowed only for an observation that violates no D/MIR/threat contract, and the row carries the
evidence. Severity `Info` marks those observations; `Critical`, `High`, `Medium` and `Low` mark product defects. No
finding is deferred to Phase 12.

## Runtime review

### Path R1: owner approval and a local record become the effective policy and plan

| Step | Location | Verified behavior |
|------|----------|-------------------|
| Approval word | `manager.py:1959-1969` | `approved` only when the stored approval equals the current `actions_hash`; blocked and no-actions are separate words |
| One snapshot | `manager.py:2075-2096` | `approval` is read once; `effective_policy` and `build_effective_trigger_plans` both use it; runs under the Manager lock on every caller (apply, approve, commit, adoption rollback via ingest) |
| Owner eligibility | `local_actions.py:309-334` | owner branch = `approved` AND owner actions AND not replaced; local branch = attached record with actions, whatever the approval (D-02) |
| Exact identity | `local_actions.py:320-321`, `local_actions.py:345-362` | a record attaches only by device id + kind + strip/lower StateValue; the parser rejects padded or case-duplicate values (`document.py:330-336`), so owner and local normalization agree |
| Safe policy | `local_actions.py:390-410` | false/serial/5/10/queue until the exact hash is approved; no-actions and blocked mirrors stay on the safe policy |
| Atomic hand-over | `runner.py:169-229`, `manager.py:2098-2107` | tracker, breaker and Script switch together in `on_swap`; no await in between; a trip is kept |
| Startup | `manager.py:2275-2300` | a restored mirror starts on `LOCAL_SAFE_POLICY`; the build before the subscription hands over the effective policy, so an unapproved owner's `run_on_startup` never starts local actions |

### Path R2: independent validation and the owner-only guard become one Script (Trust-level mixing)

| Step | Location | Verified behavior |
|------|----------|-------------------|
| Overlay-free mirror | `runner.py:203-210` | no customization: the byte-identical `async_build_device(restricted=True)`, or unload when the owner is not eligible (D-21) |
| Separate validation | `runner.py:231-263` | owner: static denylist then `async_validate_actions`; local: `async_validate_actions` only; a failing branch is dropped and the other stays (D-01) |
| Assembly | `runner.py:53-61`, `runner.py:265-305` | both branches form one native `parallel` (owner 0, local 1) inside the single `choose` dispatcher; one Script, one run mode, one queue |
| Guard | `runner.py:290-293` | `guard_actions` wraps only the subtree at `plan.owner_path` after final validation; local templates stay unguarded (owned-device trust) |
| Local denylist | `actions.py:21-31` | Manager-side validation of local input is the HA schema plus `async_validate_actions_config`; no remote-action denylist |
| Shared variables | `README.md` (Parallel runs) | branches share one variable namespace; values are data, never re-rendered as templates (see F-05) |

**Trust-level mixing (T-11-05, D-02, D-23) classification:** the owner (untrusted, approved) and local (trusted)
branches meet only in one `parallel` step. The owner subtree alone is guarded and statically denied. A denied owner
call raises `DeniedServiceCallError`, which is a plain `Exception` (`trust.py:64`), so an owner `continue_on_error`
cannot swallow it. The owner cannot cut the local branch short: `parallel` lets the sibling finish
(`tests/test_local_parallel.py::test_owner_failure_lets_the_delayed_local_branch_finish`,
`test_normal_stop_ends_the_whole_run_after_the_sibling_settles`). Owner data can reach local templates only as
variable values (F-05). No defect.

### Path R3: a run's trace becomes an outcome, and the outcome raises or clears the local issue

| Step | Location | Verified behavior |
|------|----------|-------------------|
| Task-local trace | `runner.py:454` | `trace_get()` in the run's own background task, only for a plan with a local path |
| Owner/local split | `runner.py:79-94`, `runner.py:466-482` | an exception placed only under the local path never reaches `action_failed`; owner `clear_issue` only when the owner branch took part |
| Delivery in `finally` | `runner.py:483-493` | also on cancellation; `proven` = ran + same Script + same generation + same stop epoch + HA not stopping |
| Reducer | `local_actions.py:539-560` | any local error = failure (continued ones too); success needs `proven`, no stop anywhere, and the last top-level local step reached and not a false condition |
| Build-time failure | `runner.py:244-262` | invalid local actions at build raise the local outcome (generation 0), never an owner setup error |
| Issue | `manager.py:1790-1849` | one issue per device; a failure is shown only while its record exists; only a proven success of the same identity, or its removal, clears it |

**Continued errors classification:** a local step that fails under `continue_on_error` is a local failure. It raises
or updates `local_action_failed`, and the authored continuation still runs (`local_actions.py:552-554`;
`tests/test_local_parallel.py::test_outcome_continued_local_error_stays_a_failure_and_the_continuation_runs`). This
is RESEARCH resolved question 2. No defect. Issue persistence across restart and prune is a separate finding (F-01).

### Path R4: entry points run what a state change runs

| Step | Location | Verified behavior |
|------|----------|-------------------|
| State change | `manager.py:2725-2753` | `can_run` (effective plan) → observe → breaker count → enqueue with canonical `state` only |
| Shared manual gate | `manager.py:2886-2931` | mode → breaker → effective runnability; test runs never count, publish or move the baseline |
| Re-trigger | `retrigger.py:71-79`, `retrigger.py:420-431` | maps each gate result to an existing status/reason pair; receiver gates (`_admit`, size caps) unchanged |
| Legacy test topic | `manager.py:2842-2857` | retained messages never run; only accepted StateValues; same gate |

## Persistence review

### Path P1: local form input becomes the locked durable record

| Step | Location | Verified behavior |
|------|----------|-------------------|
| Flow submit | `config_flow.py:356-378`, `config_flow.py:441-461` | draft lives in the flow; the confirmed submit goes to the Manager; nothing is written to entry options or subentries |
| Recheck under lock | `manager.py:1733-1772` | running check, identity normalization, target recheck (current trigger, or an existing record for orphans) |
| Validate | `manager.py:1757-1770` | HA schema + `async_validate_actions_config`; the raw deep copy is what is stored |
| Save first | `manager.py:1901-1922`, `local_actions_store.py:101-127` | complete candidate set written; HA's swallowed write errors are captured; memory changes only after a durable save |
| Apply | `manager.py:1913-1922` | rebuild of the one mirror, approval count refresh, then breaker release (MIR-09) |
| Store isolation | `local_actions_store.py:42-51`, `const.py` `LOCAL_ACTIONS_STORE_KEY` | separate key and version; the main Store never carries local content (D-07) |
| Refused load | `local_actions_store.py:77-99`, `manager.py:1218-1232` | a newer or unreadable file is never overwritten; the instance starts without overlays (see F-02, F-12) |

**Save rollback classification:** a failed save raises `LocalActionError(save_failed)` and leaves records, Script and
breaker unchanged (`tests/test_local_actions_manager.py::test_save_failure_keeps_previous_record_script_and_breaker`).
No defect.

### Path P2: prune, tombstone, adoption and hub removal

| Step | Location | Verified behavior |
|------|----------|-------------------|
| Prune | `sync.py:281-310`, `manager.py:2109-2127` | `TRANSIENT_PRUNE` unloads the mirror and keeps records byte-identical |
| Tombstone | `sync.py:489-507`, `manager.py:2126-2137` | `TOMBSTONE` discards records also without a mirror; an owned id is never touched; a failed save keeps the records |
| Startup | `manager.py:935-983` | records load first and are never filtered at start (D-05, D-22) |
| Adoption | `manager.py:1389-1492` | approval gate unchanged; durable discard before anything changes; rollback restores records, then the mirror |
| Hub removal | `manager.py:533-598`, `__init__.py:82-96` | both modes delete the local Store and every per-device issue; the Manager is stopped and its Store closed before |
| Hub creation | `config_flow.py:127-153` | nothing removes a leftover local Store before a new hub starts (F-03) |

**Tombstone after prune classification:** a prune keeps the records. A tombstone that arrives later, with no mirror,
still reaches `async_remove_mirror(cause=TOMBSTONE)` because `_async_remove` no longer requires a mirror
(`sync.py:500-505`) and the discard runs outside the mirror branch (`manager.py:2124-2127`). Pinned by
`tests/test_local_actions_lifecycle.py::test_tombstone_after_prune_still_discards_records`. No defect.

**Adoption rollback classification:** the local discard is durable before the subentry exists. A failed local save
raises before anything changed. A failed subentry creation restores approval, native flag, records and mirror
(`manager.py:1466-1481`). Two parts of the device state are not restored: the tripped breaker (F-04) and the local
failure issue (F-01).

## Transport review

### Path T1: broker, export, diagnostics and adoption boundaries

| Boundary | Location | Verified behavior |
|----------|----------|-------------------|
| Documents and hashes | no change in `document.py`, `discovery.py` | local records never enter `build_content`, `actions_hash` or the canonical document; pinned by `tests/test_local_invariants.py` byte oracles |
| Every publish | `tests/test_local_invariants.py::test_every_lifecycle_transition_publishes_no_local_content` | 18 named transitions, each publish scanned, silent transitions must publish nothing |
| Acks | `retrigger.py:66-79` | only existing status/reason words; `ManualRunResult` stays local |
| Adoption payload | `manager.py:1430-1436`, `services.py:308-319` | owner-only subentry; response adds an integer count only |
| Diagnostics | `diagnostics.py:82-131` | four instance integers and two per-device integers from `LocalActionCounts`; no record, label or StateValue |
| Repairs placeholders | `manager.py:310-312`, `manager.py:1825-1849` | cut, then markdown-escaped; no action, trace or variable |
| Logs | `manager.py:1804-1812`, `runner.py:249` | local logs may contain local validation text; logs are local and not a D-04 boundary |

### Path T2: NativeMigration, shared-topic and registry seams

| Seam | Evidence |
|------|----------|
| NativeMigration | `git diff 762a3db..HEAD` shows no change in `native_migration.py`, `takeover.py`, `discovery.py`, `document.py`, `presence.py`, `entities.py`, `model.py`, `topics.py` or `portability.py` |
| Startup order | `manager.py:935-983`: local load is added before the main Store load; the locked subscribe → reconcile → takeover → duplicate guard → publish order is unchanged |
| Shared-topic clears | `_async_clear_topics` callers unchanged (`manager.py:498-530`, `manager.py:2488-2543`); Phase 11 adds no publish or clear |
| Registry | `_clean_registry`, `_rebind_native_registry` unchanged; adoption of a native mirror still keeps its companion |

## UI review

### Path U1: hub options editor

| Step | Location | Verified behavior |
|------|----------|-------------------|
| Menu | `config_flow.py:199-201` | settings and local actions; no new subentry type (D-06) |
| Loaded check | `config_flow.py:252-257` | the Manager is read at every step and never kept |
| Pickers | `config_flow.py:259-341`, `config_flow.py:527-563` | option value is the stable identity; labels show name, StateValue and the mode or inactive markers (D-11, D-16) |
| Confirmations | `config_flow.py:356-418` | an empty replacement needs its own confirmation; removal has its own; a cancelled draft never reaches the Manager (D-13 to D-15) |
| Escaping | `config_flow.py:510-517` | device, trigger and StateValue placeholders escaped; select labels are plain text |
| Removal warning | `config_flow.py:203-247`, `manager.py:601-618` | distinct device count in both removal modes (D-08) |
| Translations | `translations/en.json`, `translations/de.json` | key sets identical; German texts present for every new key |

## Findings

| ID | Severity | Status | Location | Violated | Fix requirement | Regression test | Gap |
|----|----------|--------|----------|----------|-----------------|-----------------|-----|
| F-01 | Low | OPEN | `manager.py:1835-1849` creates `local_action_failed` without `is_persistent`, so HA reloads it inactive with `data=None` after a restart (installed `issue_registry.py:287-296`); `manager.py:2162` deletes it on a transient prune through `_delete_device_issues` (`const.py:351`); `manager.py:1525` deletes it on adoption and the rollback at `manager.py:1466-1481` does not restore it; `docs/troubleshooting.md:208-209` documents the prune deletion | D-19, MIR-13, T-11-21; 11-06 hand-off ("must survive owner content changes and restarts") | The issue disappears only on a proven success of its trigger, on removal or discard of its customization (removal, tombstone discard, completed adoption) or on hub removal. It survives a restart, a transient prune and a failed adoption while the record exists. An issue whose record is gone is deleted at startup | `tests/test_local_actions_lifecycle.py::test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal` | - |
| F-02 | Low | OPEN | `manager.py:1218-1232` catches every local Store load error, starts with `_local_records = ()` and logs one warning; `local_actions.py:320-334` then makes approved owner branches eligible on replaced and muted triggers; `manager.py:1906-1911` refuses later edits as a generic `save_failed` | D-05, MIR-05, MIR-06 (saved replacements and mutes silently stop applying); T-11-09 (refusal holds, but its effect is invisible) | Keep the refusal and never overwrite the file. When the local Store cannot be read, raise one instance-level Repairs issue in en and de: saved local actions, replacements and mutes are not applied and edits are refused. Delete it on a later successful load and on hub removal, and document it in troubleshooting | `tests/test_local_actions_manager.py::test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay` | - |
| F-03 | Low | OPEN | `config_flow.py:145-153` creates a hub without touching a leftover local Store; `manager.py:657` and `manager.py:1218-1226` load any `mqtt_actions.local_actions` file; `local_actions.py:217-219` binds no hub to the payload; `manager.py:550-553` only logs a failed delete at removal; a removal on v1.0.1 cannot delete the file at all | D-08 (removing the integration deletes its local Store); D-02 trust expectation (stale trusted local actions run without any approval on a new hub) | A newly created hub (single config entry, so no hub exists at that moment) never starts with records left by an earlier hub: remove a leftover local actions Store before the entry is created. The README states that a removal on 1.0.1 leaves the file until a hub is added again on 1.1 | `tests/test_hub_removal.py::test_new_hub_never_loads_local_actions_left_by_an_earlier_hub` | - |
| F-04 | Low | OPEN | `manager.py:1527` (`_async_drop_mirror`) pops `_tripped` and `manager.py:1525` deletes the breaker issue; the main Store is saved without the trip before the subentry is created; the rollback at `manager.py:1466-1481` does not restore `_tripped`, so `_restore_tripped` (`manager.py:2790-2810`) finds nothing for the restored mirror | MIR-09 (the breaker applies to local actions, and only a local edit, a changed document or a reload releases it); Phase 2 D-17; T-11-17 (rollback restores the device). Pre-existing since Phase 4; it now also releases local actions | A failed adoption restores the tripped hash, saves it and leaves the restored mirror paused with its breaker issue | `tests/test_local_actions_lifecycle.py::test_failed_adoption_keeps_a_tripped_breaker_paused` | - |
| F-05 | Info | OPEN | `runner.py:53-61`; `README.md` "Parallel runs" | none: RESEARCH pitfall 4 and the "not a security sandbox" note accept the shared namespace; owner values reach local templates only as data | Evidence only | `tests/test_local_parallel.py::test_same_response_variable_is_one_shared_name_without_isolation` | - |
| F-06 | Info | OPEN | `runner.py:290-293` guards the owner subtree after the assembled validation, while D-02 says "before assembly" | none: validation creates new Template objects, so a guard before assembly would be lost; the owner subtree alone is guarded | Evidence only | `tests/test_local_parallel.py::test_one_additive_runner_applies_the_owner_only_guard_and_leaves_local_unwrapped` | - |
| F-07 | Info | OPEN | `manager.py:2902-2905`: with a tripped breaker, a test press is refused only when the trigger runs local actions; the re-trigger refuses every paused device (11-07 choice) | none: MIR-09 holds for every local run; the Phase 2 D-13 owner-only bypass is kept (RESEARCH pitfall 8); README "Trust, approval and the gates" documents it | Evidence only | `tests/test_local_actions_manager.py::test_test_button_and_retrigger_refuse_local_runs_while_the_breaker_is_tripped`, `::test_test_button_of_an_overlay_free_mirror_still_runs_while_paused` | - |
| F-08 | Info | OPEN | `manager.py:2920-2931`, `retrigger.py:78`: a muted trigger answers `error`/`no_actions` (11-07 choice) | none: MIR-10 forbids new words, and none was added; the earlier `not_approved` would be wrong, because approval would not make a muted trigger run; `docs/operations.md` Re-trigger section documents it | Evidence only | `tests/test_local_actions_manager.py::test_retrigger_acknowledgement_vocabulary_is_unchanged` | - |
| F-09 | Info | OPEN | `manager.py:1801-1803`: a failure outcome whose customization is gone raises no issue (11-07 choice) | none: such an issue could never clear (no local branch runs, and the removal already happened), so dropping it keeps D-19 | Evidence only | `tests/test_local_actions_manager.py::test_failure_outcome_of_a_removed_customization_raises_no_local_issue` | - |
| F-10 | Info | OPEN | `config_flow.py:519-527`: picker markers use `hass.config.language` (11-08 choice) | none: D-06 requires en and de texts, which exist; the frontend does not translate dynamic option labels; README "Editing local actions" documents it | Evidence only | `tests/test_local_actions_flow.py::test_trigger_labels_follow_the_language_of_the_instance` | - |
| F-11 | Info | OPEN | `local_actions_store.py:129-137`, `manager.py:1105`: a stopped Manager closes its local Store (11-09 choice) | none: defence in depth; every mutation already needs `_running` under the lock; a reload builds a new Store object; hub removal uses its own Store object | Evidence only | `tests/test_hub_removal.py::test_a_late_save_cannot_recreate_the_local_store` | - |
| F-12 | Info | OPEN | `local_actions_store.py:84-99`, `local_actions_store.py:112-114`: a refused load keeps refusing saves until the next load (11-05 choice) | none: T-11-09 requires that a newer file is never overwritten; the invisible effect is F-02 | Evidence only | `tests/test_local_actions_store.py::test_newer_major_version_refuses_and_keeps_the_stored_bytes` | - |
| F-13 | Info | OPEN | `local_actions.py:555`: any `stop` in a run, also an authored last local `stop`, is no local success | none: RESEARCH resolved question 2 makes this the conservative D-18/D-19 reading; README and troubleshooting state it; removal or dismissal still ends the issue | Evidence only | `tests/test_local_parallel.py::test_outcome_normal_stop_and_condition_abort_are_no_local_success` | - |
| F-14 | Info | OPEN | `sync.py:480-505`, `manager.py:2124-2127`: any empty retained payload on a config topic counts as a tombstone and discards local records | none: D-05 gives tombstones that authority; an approval has the same lifetime (A10, `manager.py:2166-2167`); the broker without auth is a deliberate project decision; the discard is logged with its count | Evidence only | `tests/test_local_actions_lifecycle.py::test_tombstone_discards_records_saves_at_once_and_publishes_nothing` | - |
| F-15 | Info | OPEN | `manager.py:1660-1681`: records of a device deleted while this instance was offline are kept by the prune and are never discarded | none: D-05 and MIR-08 forbid a discard at startup or prune; the editor lists the device as not mirrored, so its records can be removed | Evidence only | `tests/test_local_actions_lifecycle.py::test_startup_cleanup_of_a_cached_mirror_keeps_local_records`, `tests/test_local_actions_manager.py::test_orphan_only_record_stays_queryable_after_startup_without_running` | - |
| F-16 | Info | OPEN | `manager.py:2842-2857`, `retrigger.py:420-431`: broker-originated test presses and re-triggers run trusted local actions | none: MIR-10 requires effective actions; run variables are only the device id, the canonical StateValue, the trigger key and `test`; the existing retained, rate, mode and breaker gates apply | Evidence only | `tests/test_local_multi_instance.py::test_retrigger_runs_each_followers_own_local_actions_with_the_existing_answer_words` | - |
| F-17 | Info | OPEN | `translations/en.json` and `de.json` `options.step.settings.description` read "1 devices" / "1 Geräte" for one device; `manager.py:612-617` counts an unreadable file as 0 (11-09 choice) | none: D-08 requires the count, which is shown; grammar is cosmetic; the unreadable case becomes visible through F-02 | Evidence only | `tests/test_hub_removal.py::test_removal_settings_text_renders_the_device_count` | - |
| F-18 | Info | OPEN | `runner.py:483-493`, `manager.py:1801-1812`: a run of the previous local actions that fails after an edit can still raise the issue | none: the failure did happen, and D-18 names the latest failed trigger; the next proven success of that trigger clears it | Evidence only | `tests/test_local_actions_manager.py::test_local_failure_issue_clears_on_proven_success_after_an_edit_and_on_removal` | - |
| F-19 | Info | OPEN | `manager.py:1494-1505`: when the restore save after a failed adoption also fails, memory has the records and disk the smaller set until the next saved edit | none: a double failure, logged by count; T-11-17 restores the runtime mirror and records | Evidence only | `tests/test_local_actions_lifecycle.py::test_adoption_subentry_failure_restores_mirror_and_records_and_publishes_nothing` | - |
| F-20 | Info | OPEN | `manager.py:2045-2065`: the approval request has no issue description; the replaced count and the owner-only text are shown in its fix flow (`repairs.py:83-84`) | none: a fixable issue opens its fix flow, which carries the D-17 count and wording | Evidence only | `tests/test_repairs_flow.py::test_approval_issue_is_created_fixable_with_hash_data` | - |

## Coverage

### Requirements

| ID | Implemented at | Evidence | Findings |
|----|----------------|----------|----------|
| MIR-01 | `config_flow.py:178-563`, `manager.py:1733-1788` | `tests/test_local_actions_flow.py` (12 tests); 11-02 frontend smoke PASS | F-10 |
| MIR-02 | `local_actions.py:309-334`, `runner.py:169-229` | `tests/test_local_action_plans.py` 24-row oracle; `tests/test_local_actions_manager.py::test_pending_mirror_with_persisted_additive_record_gains_local_branch` | - |
| MIR-03 | `runner.py:53-61`, `runner.py:265-305` | `tests/test_local_parallel.py` (pins and one-Script tracer) | F-05, F-06 |
| MIR-04 | no change in `document.py`; `diagnostics.py:82-131`; `services.py:308-319` | `tests/test_local_invariants.py` (hash, document, adoption, export, diagnostics and publication oracles) | - |
| MIR-05 | `local_actions.py:276-277`, `config_flow.py:380-418` | `tests/test_local_actions_flow.py::test_empty_replacement_needs_the_mute_confirmation_before_any_save` | F-02 |
| MIR-06 | `manager.py:1311-1355`, `manager.py:1924-1944` | `tests/test_local_actions_lifecycle.py::test_records_survive_*` | F-02 |
| MIR-07 | `local_actions.py:345-362`, `manager.py:1683-1713` | `tests/test_local_actions_lifecycle.py::test_removed_option_orphans_the_record_and_exact_return_reattaches` | - |
| MIR-08 | `manager.py:2109-2149`, `manager.py:1418-1492`, `sync.py:304`, `sync.py:505` | `tests/test_local_actions_lifecycle.py` prune, tombstone and adoption tests | F-14, F-15, F-19 |
| MIR-09 | `manager.py:2725-2753`, `manager.py:2886-2918`, `manager.py:1913-1922` | `tests/test_local_actions_manager.py::test_observe_disabled_and_tripped_breaker_refuse_local_runs` | F-04, F-07 |
| MIR-10 | `manager.py:2886-2931`, `retrigger.py:71-79` | `tests/test_local_actions_manager.py::test_test_button_legacy_test_and_retrigger_run_what_a_state_change_runs` | F-08, F-16 |
| MIR-11 | `local_actions.py:390-410`, `manager.py:2075-2107` | `tests/test_local_actions_manager.py::test_pending_local_policy_is_false_serial_5_10_10_whatever_the_owner_says` | - |
| MIR-12 | `manager.py:1992-2073`, `trust.py`, `repairs.py:83-84` | `tests/test_local_actions_lifecycle.py::test_every_trigger_replaced_keeps_pending_owner_hash_yaml_and_refused_adoption` | F-20 |
| MIR-13 | `manager.py:1790-1860`, `runner.py:79-94` | `tests/test_local_actions_manager.py::test_local_failure_raises_an_independent_issue_naming_the_trigger_and_error` | F-01, F-09, F-13, F-18 |
| MIR-14 | `diagnostics.py:82-131`, `manager.py:1715-1731` | `tests/test_diagnostics.py::test_local_sentinels_never_appear_and_the_shared_hash_is_unchanged` | - |
| MIR-15 | `README.md`, `docs/operations.md`, `docs/troubleshooting.md`, both translation files | `tests/test_docs.py` local-actions tests; `tests/test_translations.py` | F-01, F-03, F-17 |

### Decisions

| ID | Where it holds | Status in this review |
|----|----------------|-----------------------|
| D-01 | `runner.py:53-61`, `runner.py:296-305` (one Script, device-wide mode) | holds |
| D-02 | `runner.py:231-263`, `runner.py:290-293`, `local_actions.py:323` | holds (F-05, F-06 observations) |
| D-03 | `local_actions.py:390-410`, `manager.py:2886-2918`, `manager.py:1913-1922` | holds (F-07, F-08 observations) |
| D-04 | `tests/test_local_invariants.py`, `diagnostics.py:82-131`, `manager.py:1992-2005` | holds |
| D-05 | `manager.py:2109-2149`, `manager.py:1418-1492`, `manager.py:1924-1944` | holds, except that a refused load does not apply records (F-02) |
| D-06 | `config_flow.py:199-201`, translations, README | holds (F-10 observation) |
| D-07 | `local_actions_store.py`, `const.py` local key | holds |
| D-08 | `manager.py:533-618`, `config_flow.py:203-247` | gap: a leftover Store reaches a new hub (F-03) |
| D-09 | README "Downgrading to 1.0.1", `11-release-notes.md` | holds; F-03 adds the removal-on-1.0.1 case |
| D-10 | `local_actions.py:60-76` | holds |
| D-11 | `config_flow.py:527-563`, `manager.py:1924-1944` | holds |
| D-12 | `manager.py:1683-1713`, `manager.py:1747-1752` | holds |
| D-13 | `config_flow.py:356-461` | holds |
| D-14 | `config_flow.py:404-439`, `manager.py:1774-1788` | holds |
| D-15 | `config_flow.py:356-402` | holds |
| D-16 | `config_flow.py:535-563` | holds |
| D-17 | `manager.py:2045-2073`, `repairs.py:83-84`, approval translations | holds (F-20 observation) |
| D-18 | `manager.py:1790-1849`, `runner.py:79-94` | holds |
| D-19 | `manager.py:1790-1823`, `local_actions.py:539-560` | gap: restart, prune and failed adoption delete the issue (F-01) |
| D-20 | `tests/test_local_parallel.py` Core pins | holds |
| D-21 | 11-01 to 11-12 commit order; `runner.py:203-210` | holds |
| D-22 | `manager.py:935-940`, `manager.py:1901-1922` | holds |
| D-23 | this ledger; T-11-05 entry above | holds once the routed gaps are fixed |

### Threats T-11-01 to T-11-33

| Threat | Mitigation found at | Status in this review |
|--------|---------------------|-----------------------|
| T-11-01 | `tests/test_local_invariants.py` publication oracle | holds |
| T-11-02 | `local_actions.py:309-334`; `tests/test_local_action_plans.py` | holds |
| T-11-03 | `tests/test_local_parallel.py` masked/continued pins | holds |
| T-11-04 | `11-FRONTEND-SMOKE.md` `Verdict: PASS`, human approval | holds |
| T-11-05 | Path R2 above | holds (F-05, F-06 observations) |
| T-11-06 | `local_actions.py:95-117`, `local_actions.py:332-333`, `runner.py:55-56` | holds |
| T-11-07 | `local_actions.py:539-560`, `runner.py:483-493` | holds (F-13 observation) |
| T-11-08 | `local_actions.py:506-526`, `runner.py:500-502` (trace cleared) | holds |
| T-11-09 | `local_actions.py:193-232`, `local_actions_store.py:77-127` | holds; effect invisible (F-02) |
| T-11-10 | `local_actions_store.py:64-70`, `local_actions_store.py:115-127` | holds |
| T-11-11 | `tests/fake_broker.py` `instance_store_keys` | holds |
| T-11-12 | `local_actions.py:390-410`, `manager.py:2075-2107` | holds |
| T-11-13 | `manager.py:1733-1772`, `manager.py:1901-1922` | holds |
| T-11-14 | Manager lock on every local mutation, approval and ingest | holds |
| T-11-15 | `manager.py:1913-1922` (release after durable save, target device only) | holds; a failed adoption also releases (F-04) |
| T-11-16 | `const.py` `MirrorRemovalCause`, `manager.py:2109-2149` | holds |
| T-11-17 | `manager.py:1418-1492` | partly: trip and local issue are not restored (F-04, F-01) |
| T-11-18 | `manager.py:1411-1412` (approval gate unchanged) | holds |
| T-11-19 | `services.py:308-319`, `manager.py:1483-1484` | holds |
| T-11-20 | `retrigger.py:420-431` | holds (F-16 observation) |
| T-11-21 | `manager.py:1790-1823` | gap: issue lost without success or removal (F-01) |
| T-11-22 | `trust.py` `replaced_trigger_count`, `manager.py:1992-2005` | holds |
| T-11-23 | `manager.py:310-312`, `manager.py:1835-1849` | holds |
| T-11-24 | `config_flow.py:252-257`, `config_flow.py:565-567`, Manager recheck | holds |
| T-11-25 | `config_flow.py:380-439`, approval wording | holds |
| T-11-26 | `config_flow.py:510-517` | holds |
| T-11-27 | `diagnostics.py:82-131` | holds |
| T-11-28 | `manager.py:533-598`, `local_actions_store.py:129-137` | holds for removal; creation side is F-03 |
| T-11-29 | `tests/test_docs.py` downgrade tests, release draft gate | holds |
| T-11-30 | `tests/test_local_multi_instance.py` | holds |
| T-11-31 | `tests/test_local_multi_instance.py::test_followers_keep_exact_approvals_and_safe_policies_on_identical_shared_bytes` | holds |
| T-11-32 | Path T2 above (no change in migration and shared-topic modules) | holds |
| T-11-33 | breaker and queue limits from the policy, `runner.py:296-305` | holds |
