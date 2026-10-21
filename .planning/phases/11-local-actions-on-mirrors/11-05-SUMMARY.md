---
phase: 11-local-actions-on-mirrors
plan: 05
subsystem: runtime
tags: [local-actions, manager, store, policy, breaker, lock, tdd]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-01: expected-RED Manager target and seeded v1 record shape"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-03: build_effective_trigger_plans, EffectivePolicy / LOCAL_SAFE_POLICY, ActionRunner.async_build_effective"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-04: LocalActionsStore, per-instance local Store keys in the fake-broker harness"
provides:
  - Manager local_store_key injection; local Store loaded first in async_start, before mirror restore and state subscribe
  - Mirror Scripts built from effective plans (owner ineligibility drops only the owner branch)
  - Read APIs local_action_devices / local_action_triggers / local_action_counts (copies and counts only)
  - Locked mutation APIs async_set_local_action / async_remove_local_action with LocalActionError reasons
  - One EffectivePolicy snapshot per mirror for tracker, breaker and Script (ActionRunner.policy_for, on_swap)
affects: [11-06, 11-07, 11-08, 11-09, 11-10]

# Actuals (#2632)
actuals:
  tokens: 14470
  tasks: 3
  commits: 8
plan_head_before: 530ace8c2e0e3eaed014ed942aff9b2c69584138
plan_head_after: 19b55b693f80b93874cf0706fa4bb96063f5a9a2

tech-stack:
  added: []
  patterns:
    - "Save the complete candidate record set first, then swap memory, rebuild one device, then release its breaker"
    - "Policy hand-over at the Script swap: runner calls on_swap with no await between swap and tracker/breaker update"
    - "Mirrors start on LOCAL_SAFE_POLICY; owner execution metadata applies only for the exact approved hash"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-05-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-05-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-05-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-05-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-05-task3-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-05-task3-red.json
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/runner.py
    - tests/fake_broker.py
    - tests/test_local_actions_manager.py
    - tests/test_sync_follower.py

key-decisions:
  - "A local Store that cannot be read (newer version, unreadable) starts the Manager without overlays; the Store keeps refusing saves, so the file is never overwritten; logged by exception type only"
  - "Valid edit targets: a current trigger of a current mirror (active), or an identity that already has a saved record (orphan, kind mismatch, no mirror; stays inactive). Anything else, and owned-device ids without a record, raise LocalActionError(stale_target)"
  - "A saved record's label is the trigger's friendly_name (switch: ON/OFF, select: option name), kept for orphan display (D-11)"
  - "A durable edit or removal on a current mirror rebuilds it first and then releases its breaker (reset, issue deleted, persisted trip dropped); failed or stale edits change nothing"
  - "Pending/blocked/no-actions mirrors carry LOCAL_SAFE_POLICY in tracker and breaker even without local records; owner values apply after exact approval. Approval changes adjust breaker limits in place and keep a trip"
  - "Removal from the hub (async_remove_local_state / async_remove_all_devices local key) is left to Plan 11-09, which owns D-08"

patterns-established:
  - "Run-decision coherence probe: collect tracker/breaker/Script policy mismatches inside _run_trigger instead of asserting there (the MQTT dispatcher swallows assertions)"

requirements-completed: [MIR-02, MIR-06, MIR-09, MIR-11]

coverage:
  - id: D1
    description: "Local Store loads before mirror restore and state subscription; a persisted additive record survives restart and runs on the cache-restored pending mirror; orphan-only records stay listed without running and without startup GC"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py -k 'load_before_mirrors or restart or persisted_additive_record or orphan_only'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Plan 11-01 expected-RED target is GREEN with unchanged assertions; the unit tier passes unfiltered"
    requirement: MIR-02
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_pending_mirror_with_persisted_additive_record_gains_local_branch"
        status: pass
      - kind: other
        ref: "uv run pytest -q -m \"not broker and not multi_instance\" (1766 passed, 2 xfailed, no --deselect)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Locked per-trigger edit/remove: stale targets and invalid actions/mode refused without save; immediate durable write; failed save keeps record, Script and trip; success rebuilds only that device, runs nothing and releases only its breaker; repeated edit is idempotent"
    requirement: MIR-09
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py -k 'edit or remove or save_failure or idempotent or breaker'"
        status: pass
    human_judgment: false
  - id: D4
    description: "Safe policy false/serial/5/10/10 until exact approval; approval and owner changes switch tracker, breaker and Script together; concurrent approval/edits never expose two generations; observe, disabled and tripped refuse local runs"
    requirement: MIR-11
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py -k 'policy or approved_exact_hash or refuse_local_runs'"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-21
---

# Phase 11 Plan 05: Manager Ownership of Local Overlays and Effective Policy Summary

**The Manager now loads the separate local Store before any mirror exists. Mirror Scripts are built from effective plans. Edits and removals go through one locked API that saves first and applies after. Each mirror's tracker, breaker and Script follow one `EffectivePolicy` snapshot, which is fixed at false/serial/5/10/10 until the owner's exact hash is approved.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-10-21T00:52:59Z
- **Completed:** 2026-10-21T01:18:04Z
- **Tasks:** 3 (1 tracer, 2 TDD). There are 8 commits: 3 RED, 3 GREEN and 2 REFACTOR.
- **Files:** 2 production modules and 3 test modules modified, 6 evidence files created.

## Manager API (for Plans 11-06 to 11-09)

All in `custom_components/mqtt_actions/manager.py`:

- `Manager(hass, entry, *, gateway=None, store_key=STORE_KEY, local_store_key=LOCAL_ACTIONS_STORE_KEY)`
- Read APIs. They return copies or counts, never shared data:
  - `local_action_devices() -> tuple[LocalActionDevice(device_id, name, kind, mirrored, records), ...]`. It lists the current mirrors first, then the devices that only have records, sorted by id.
  - `local_action_triggers(device_id) -> tuple[LocalActionTrigger(identity, state_value, label, present, record), ...]`. It lists the current triggers in owner order with their friendly names, then the inactive records sorted by identity.
  - `local_action_counts() -> LocalActionCounts`. This is the pure `local_action_counts` applied to the current mirror specs.
- Mutations. Both take `Manager.lock`, and both raise `LocalActionError(reason)`, where `reason` is one of `not_running`, `stale_target`, `invalid_mode`, `invalid_actions` or `save_failed`:
  - `async_set_local_action(identity, mode, actions) -> LocalActionChange(identity, record, active)`
  - `async_remove_local_action(identity) -> LocalActionChange(identity, None, active=False)`
- Order of a mutation:
  1. Normalize the identity.
  2. Re-check the target.
  3. Validate with `async_validate_actions`. The raw deep copy is what gets persisted.
  4. Save the complete candidate set with `LocalActionsStore.async_save_records`.
  5. Swap `_local_records`.
  6. Rebuild only the affected mirror through `_async_refresh_mirror_script`.
  7. Release that mirror's breaker.
- There is no cancel API. A flow draft that is never submitted never reaches the Manager.

## Effective-policy generation contract

- `_async_refresh_mirror_script(device)` runs under the Manager lock. It computes `approval` once, and from that one `policy = effective_policy(spec, approval)` and the plans.
- It then calls `runner.async_build_effective(spec, plans, policy=policy, on_swap=partial(_apply_policy, device, policy))`.
- At the moment the Script is replaced, or removed by an unload, the runner records `policy_for(device_id)` and calls `on_swap`. No `await` sits in between. `_apply_policy` sets `device.policy`, `tracker.run_on_startup` and the breaker limits.
  - The breaker keeps its window and any trip. Only a changed owner document or a durable local edit releases it.
- Mirrors start on `LOCAL_SAFE_POLICY` in `_build_mirror`. `_update_mirror` keeps the current generation until the rebuild that follows.
- The policy is recomputed on startup restore, new mirrors, owner content changes, approval and local edit/remove. A re-pin (same content) leaves the plans identical and is not rebuilt.
- Owned devices are unchanged: `device.policy` is `None`, and they keep their subentry values.

## TDD Evidence

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 (tracer) | `f111281` | `tests/test_local_actions_manager.py::test_restart_keeps_persisted_additive_record_and_runs_local_branch` | RED_EVIDENCE_OK (junit, 1 test, 1 failure) | `56df44d` | none needed |
| 2 | `494b72c` | `tests/test_local_actions_manager.py::test_edit_saves_immediately_and_applies_without_restart_or_retroactive_run` | RED_EVIDENCE_OK | `8aa3ff9` | `3b38bb2` |
| 3 | `b650daa` | `tests/test_local_actions_manager.py::test_pending_local_policy_is_false_serial_5_10_10_whatever_the_owner_says` | RED_EVIDENCE_OK | `ef770d4` | `19b55b6` |

Semantic assessments (full text in `tdd/11-05-task{1,2,3}-red.json`):

- **RED 1:** valid. The restart and the cache restore passed, and so did the pending premise. The test failed on "the restored local branch ran 0 times, expected 1". The order and orphan-only tests also failed on their planned assertions: the order test found no `local_load`, and the orphan-only test got an empty device list from the skeleton.
- **RED 2:** valid. The test failed on the immediate-write assertion, because the skeleton saves nothing. The other mutation tests failed on DID NOT RAISE, on the stored rows, or on the trip premise; none failed on an import error.
- **RED 3:** valid. The test failed on "an unapproved owner's run_on_startup must not start local actions", because the retained replay ran the local action. The approval-switch and race tests failed on `device.policy None`, and the race test reported incoherent generations. The observe, disabled and tripped cases were already green at RED and serve as characterization tests.

### GREEN evidence that retired the Plan 11-01 expected-RED target

- Node: `tests/test_local_actions_manager.py::test_pending_mirror_with_persisted_additive_record_gains_local_branch`. Run alone after `56df44d`, it reports `1 passed in 0.90s`.
- The assertions are byte-identical to the 11-01 commit `fb8fb92`. A diff of the function body shows no change. No seeded-fixture alignment was needed, because the 11-04 v1 shape is the seeded shape. Only the module import lines grew.
- Unit tier, unfiltered:
  - After Task 1: `uv run pytest -q -m "not broker and not multi_instance"` reported 1750 passed, 2 xfailed. The xfails are the older ones in `tests/test_takeover.py`.
  - Final run: 1766 passed, 2 xfailed. No `--deselect` was used. The "191 deselected" in pytest's output comes from the marker filter only.
- Multi-instance tier: 173 passed. Broker tier: 18 passed.
- `tests/test_startup_order.py` and `tests/test_runner_modes.py`: 17 passed.

## Task Commits

1. **Task 1 (tracer): load before mirrors, restart, orphan-only.** `f111281` (test), `56df44d` (feat). The tracer gate re-ran `<verify>` green before expansion.
2. **Task 2: locked durable edits.** `494b72c` (test), `8aa3ff9` (feat), `3b38bb2` (refactor).
3. **Task 3: coherent device-wide policy.** `b650daa` (test), `ef770d4` (feat), `19b55b6` (refactor).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] An existing follower test encoded pre-D-03 trust in unapproved owner metadata**
- **Found during:** Task 3 GREEN, in the full unit tier.
- **Issue:** `tests/test_sync_follower.py::test_mirror_carries_the_documents_settings` asserted that a pending mirror's tracker and breaker carry the owner's `run_on_startup` and breaker limits. D-03 and T-11-12 forbid that before exact approval.
- **Fix:** The test now asserts the safe values (False, 5/10) while the mirror is pending, approves the exact hash, and then asserts the owner values (True, 3/7). The spec, signature and run-mode assertions are unchanged.
- **Files modified:** `tests/test_sync_follower.py` (not in `files_modified`)
- **Commit:** `ef770d4`

**2. [Rule 1 - Bug] Breaker issue text named the spec limits instead of the applied ones**
- **Found during:** Task 3 GREEN.
- **Issue:** `_create_breaker_issue` and the trip log read `device.spec.breaker_*`. A pending mirror trips on the safe limits, so the issue would have shown the owner's numbers.
- **Fix:** Both now read `device.breaker.max_runs` and `int(device.breaker.window)`. This is identical for owned devices and for approved mirrors.
- **Commit:** `ef770d4`

**3. [Test fixture] Live delivery of the changed owner document**
- The Task 3 approval-switch test first delivered the changed document as retained. The follower does not apply a second retained document as an update, and other suites send updates live too (for example `test_companions.py`). The delivery now uses `retain=False`.
- No assertion changed. The change landed in the GREEN commit `ef770d4`.

**4. [Naming] The internal snapshot builders are inline**
- The plan named `_effective_policy(device_id, approval_state)` and `_effective_trigger_plans(device_id)`. The same work is done inline in `_async_refresh_mirror_script`, from one `approval` read, using the pure `effective_policy` and `build_effective_trigger_plans`. No separate methods exist.

**5. [Characterization] Extra tests that were green on arrival**
- `test_editor_rows_list_current_triggers_then_inactive_records_as_copies` was added in the Task 2 GREEN commit, so it never had a RED run.
- The observe, disabled and tripped refusal cases in Task 3 were already green at RED. They pin existing gates for local runs.

**Total deviations:** 2 auto-fixed bugs (Rule 1), 1 fixture correction, 1 naming note and 1 characterization note. **Impact:** all of them tighten D-03 and T-11-12. Overlay-free Script sequences and owned devices are unchanged.

## Hand-offs and Known Limits

- **Plan 11-06:**
  - The tombstone and adoption paths should discard records through `_local_candidate` and `_async_commit_local_records`, or an equivalent locked save.
  - `async_remove_mirror` does not touch `_local_records` today, so transient prune already keeps them.
- **Plan 11-07:**
  - Test buttons and re-trigger use `runner.can_run`, which already covers local-only triggers.
  - The breaker gate in `_enqueue_test` is still mode-only, as before.
- **Plan 11-08:** map the `LocalActionError.reason` values to base errors. `LocalActionChange.active` tells the flow whether a saved record is live.
- **Plan 11-09:** hub removal must delete `LocalActionsStore(hass, local_store_key)`. `local_action_counts()` provides the diagnostics counts. `async_remove_local_state` and `async_remove_all_devices` do not take a local key yet.
- **Approval with a tripped breaker:** the trip stays, and only the limits change. This matches today's rule that approval never releases a trip.

## Known Stubs

None.

## Threat Flags

None. The new surface is the T-11-12 to T-11-15 register of this plan.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None.

## Next Phase Readiness

Plans 11-06 to 11-09 have their Manager entry points. The expected-RED exception has expired, and every later wave gate runs the unfiltered unit tier.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

All 11 created/modified files exist, all 8 task commits are ancestors of HEAD, and the three RED records re-classify as RED_EVIDENCE_OK.
