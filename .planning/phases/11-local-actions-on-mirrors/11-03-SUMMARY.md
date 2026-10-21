---
phase: 11-local-actions-on-mirrors
plan: 03
subsystem: runtime
tags: [local-actions, effective-plan, parallel, trace, trust, tdd, runner]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-01: 24-row gate oracle, Core 2026.9.4 parallel/trace pins, seeded v1 record shape"
provides:
  - HA-free overlay model in custom_components/mqtt_actions/local_actions.py (records, identity, matching, EffectiveTriggerPlan, EffectivePolicy, counts, outcome reducer)
  - ActionRunner.async_build_effective (one Script, owner branch 0 and local branch 1 in native parallel, owner-only guard)
  - Per-branch BranchOutcome delivery through ActionRunner.on_local_outcome with Script/generation/stop-epoch proof
affects: [11-04, 11-05, 11-06, 11-07, 11-09]

# Actuals (#2632)
actuals:
  tokens: 21723
  tasks: 3
  commits: 7
plan_head_before: 016b2b91065351d0e94b3c8771866267c6153f3b
plan_head_after: e23c6d80e56c19bb1a17d9bd1c252f9ff2bf2377

tech-stack:
  added: []
  patterns:
    - "EffectiveTriggerPlan is the runtime unit; owner DeviceSpec stays the immutable shared input and is only ever deep-copied"
    - "Trace paths double as config paths: the owner guard is applied at plan.owner_path in the validated tree"
    - "Branch outcomes come from a task-local trace summary, delivered from a finally block, never from the outer result"

key-files:
  created:
    - custom_components/mqtt_actions/local_actions.py
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-03-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-03-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-03-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-03-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-03-task3-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-03-task3-red.json
  modified:
    - custom_components/mqtt_actions/runner.py
    - tests/test_local_action_plans.py
    - tests/test_local_parallel.py

key-decisions:
  - "Overlay-free mirrors take today's path unchanged: async_build_effective delegates to async_build_device(restricted=True) when no plan has a customization, or unloads when no owner branch is eligible"
  - "Branch paths are steps prefixes: both branches -> 0/choose/<i>/sequence/0/parallel/{0,1}/sequence; one branch -> 0/choose/<i>/sequence; a local-only trigger keeps its authored steps directly in the choose option (no wrapper)"
  - "Local success = no error under the local path AND proven run (current Script, latest generation, unchanged runner stop epoch, HA not stopping) AND no stop step anywhere AND the last top-level local step reached and not a false condition"
  - "Outcomes are delivered from finally: inside the choose dispatcher a stopped/unloaded/restarted run ends as CancelledError (new Core pin), so a local error recorded before a cancel is still reported"
  - "Safe local policy (startup off, serial, breaker 5/10 s, queue 10) is EffectivePolicy.LOCAL_SAFE_POLICY; async_build_effective takes an optional policy snapshot and defaults to effective_policy(spec, approval)"
  - "Invalid local actions at build time are logged only (bounded); the local Repairs issue family is Plan 11-07"

patterns-established:
  - "Interface skeleton in the RED commit so a new-API test fails on its assertion, not on import"
  - "Pure trace helpers (summarize_trace, reduce_local_outcome) duck-type TraceElement.as_dict and read only error/stop/condition results"

requirements-completed: [MIR-02, MIR-03, MIR-05, MIR-11, MIR-13]

coverage:
  - id: D1
    description: "One approved additive trigger runs owner branch 0 and local branch 1 inside one device Script; a pending one runs only the local branch"
    requirement: MIR-02
    verification:
      - kind: integration
        ref: "tests/test_local_parallel.py -k 'one_additive or owner_only_guard'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner-only static refusal and GuardedTemplate; the identical templated local call runs unwrapped"
    requirement: MIR-03
    verification:
      - kind: integration
        ref: "tests/test_local_parallel.py#test_one_additive_runner_applies_the_owner_only_guard_and_leaves_local_unwrapped"
        status: pass
    human_judgment: false
  - id: D3
    description: "Overlay-free mirror build is node-for-node equal to today's restricted dispatcher; unapproved without customization builds no Script"
    requirement: MIR-02
    verification:
      - kind: integration
        ref: "tests/test_local_parallel.py#test_one_additive_overlay_free_mirror_build_is_identical_to_the_direct_dispatcher"
        status: pass
    human_judgment: false
  - id: D4
    description: "All 24 gate rows and 8 separate rows bound to build_effective_trigger_plan; identity, malformed, aliasing, orphan reattach, cross-kind, policy and counts"
    requirement: MIR-05
    verification:
      - kind: unit
        ref: "tests/test_local_action_plans.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "Conservative per-branch outcomes: masked, continued and pre-cancel local errors are failures; stop, abort, stop/rebuild/restart, other-trigger and owner-only runs never prove success; bounded error, no trace content"
    requirement: MIR-13
    verification:
      - kind: integration
        ref: "tests/test_local_parallel.py -k 'outcome or dispatcher_wrapped'"
        status: pass
    human_judgment: false
  - id: D6
    description: "Pending local-only Script runs with the safe local policy, not the unapproved owner's run mode"
    requirement: MIR-11
    verification:
      - kind: integration
        ref: "tests/test_local_parallel.py#test_pending_local_only_script_uses_the_safe_local_policy"
        status: pass
    human_judgment: false

duration: 17min
completed: 2026-10-21
---

# Phase 11 Plan 03: Effective Plans and One-Script Local Branches Summary

**HA-free `EffectiveTriggerPlan` model plus `ActionRunner.async_build_effective`: one device Script runs the approved owner branch 0 and the trusted local branch 1 in native `parallel`. The owner subtree alone is guarded. Each local branch run is reduced from a task-local trace to one bounded `BranchOutcome`, and success needs proof from the current Script, generation and stop epoch.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-10-20T23:53:26Z
- **Completed:** 2026-10-21T00:10:20Z
- **Tasks:** 3 (tracer + 2 TDD), 7 commits (3 RED, 3 GREEN, 1 REFACTOR)
- **Files:** 1 production module created, 1 modified, 2 test modules extended, 6 evidence files

## Accomplishments

- **Tracer (Task 1).** An approved additive switch-ON record runs `test.owner_on` and `test.local_on` in one Script. The recorded paths are `0/choose/0/sequence/0/parallel/0/sequence` (owner) and `.../parallel/1/sequence` (local). A pending mirror runs only the local branch, with local path `0/choose/0/sequence`. `script_count == 1` holds in both cases. The tracer gate re-ran green before expansion.
- **Trust separation (T-11-05).** Owner and local actions are validated separately, and a branch that fails is dropped without removing the other. The static denylist covers owner actions only. `guard_actions` runs after the final validation and only at `plan.owner_path`. The same templated `{{ 'mqtt.publish' }}` call is denied on the owner branch and runs on the local branch.
- **Byte-identity (D-21).** Without any customization, the effective build delegates to today's `async_build_device(restricted=True)`, or unloads when the owner is not approved. A test proves the Script sequence and the template classes are equal.
- **Pure model (Task 2).**
  - Identity is device id, kind and strip/lower StateValue. The original value and the last label are kept separately.
  - Records are strict and deep-copied in and out.
  - A replacement excludes the owner branch and leaves the approval word unchanged.
  - An empty replacement mutes the trigger. An empty additive record adds no branch.
  - Orphan and kind-mismatch records stay inactive and reattach on exact return.
  - Also added: `EffectivePolicy` with `LOCAL_SAFE_POLICY`, and count-only `LocalActionCounts`.
- **Outcomes (Task 3).** `summarize_trace` reads only error, stop and condition results. `reduce_local_outcome` is conservative. The runner delivers the outcome from `finally`, so a local error recorded before a cancellation is still a failure.

## Finalized interface for Plans 11-04 / 11-05 (and 11-07, 11-09)

`custom_components/mqtt_actions/local_actions.py` (no HA imports; imports `.const` only):

- `LocalActionMode` (`ADDITIVE="additive"`, `REPLACEMENT="replacement"`) and `PlanComposition` (`owner_and_local`, `owner_only`, `local_only`, `nothing`, `muted`).
- `LocalActionIdentity(device_id, kind, state_value)`: frozen and ordered, `state_value` normalized. Build it with `local_trigger_identity(device_id, kind, value)`.
- `LocalActionRecord(identity, state_value, label, mode, actions)` with `copy_actions()` and `with_label(label)`.
  - `make_local_record(device_id, kind, state_value, *, label, mode, actions)` raises `LocalActionRecordInvalid(ValueError)`.
  - `parse_local_record(row)` and `local_record_data(record)` read and write the v1 row `{device_id, kind, state_value, label, mode, actions}`. This is exactly the shape Plan 11-01 seeded, so 11-04 can use it unchanged.
- `match_local_records(spec, records) -> LocalMatch(active: {trigger_key: record}, inactive: tuple sorted by identity)`. Records of other devices are ignored, and the first record wins for each identity.
- `build_effective_trigger_plan(device_id, kind, trigger, approval, record)` and `build_effective_trigger_plans(spec, approval, records)`. Plans follow owner trigger order.
- `EffectiveTriggerPlan(device_id, kind, trigger_key, state_value, label, approval, customization, owner_actions, local_actions, owner_path=None, local_path=None)`.
  - Properties: `owner_eligible`, `local_eligible`, `composition` and `runnable`.
  - Methods: `restricted_to(owner=, local=)` and `at_dispatch(prefix)`.
- `EffectivePolicy(run_on_startup, run_mode, breaker_max_runs, breaker_window, queue_limit)`, plus `LOCAL_SAFE_POLICY` and `effective_policy(spec, approval)`.
- `local_action_counts(records, specs_by_device_id) -> LocalActionCounts(records, devices, active, inactive, replaced, muted, orphan_only_devices)`.
- `OutcomeStatus` (`success`, `failure`, `no_success`), `BranchOutcome(device_id, trigger_key, label, status, error, generation)`, `StepTrace`, `summarize_trace(trace)` and `reduce_local_outcome(plan, steps, *, proven)`.

`ActionRunner` (runner.py):

- `async_build_effective(spec, plans, *, policy=None)`: the mirror build entry point for 11-05. It replaces the manager's "approved: `async_build_device(restricted=True)`, else unload" gate.
- `plan_for(device_id, key)` returns the built plan with its paths. `on_local_outcome: Callable[[BranchOutcome], None] | None` is the listener 11-07 attaches.
- `async_stop_runs` bumps a per-device stop epoch. `async_unload` and `async_build_device` drop the per-device plans, and `async_unload` also drops the stop epoch.

## TDD Evidence

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 | `d858726` | `tests/test_local_parallel.py::test_one_additive_approved_trigger_runs_owner_and_local_branches_in_one_script` | RED_EVIDENCE_OK (junit, 1 test, 1 failure) | `9aa9737` | none needed |
| 2 | `f2b08f0` | `tests/test_local_action_plans.py::test_production_plan_matches_gate_row[approved-replacement-owner_actions]` | RED_EVIDENCE_OK | `2e29b78` | none needed |
| 3 | `fd38f8c` | `tests/test_local_parallel.py::test_outcome_both_failures_report_the_local_failure` | RED_EVIDENCE_OK | `cf07d09` | `e23c6d8` |

Semantic assessments (full text in `tdd/11-03-task{1,2,3}-red.json`):

- **RED 1:** valid. Imports resolve against a compile-only skeleton (records and an `async_build_effective` that delegated to today's build). The target failed on its first planned assertion, "the local branch ran 0 times, expected 1".
- **RED 2:** valid for the target. The binding row failed on its assertion (`(True, True, 'owner_and_local')` instead of `(False, True, 'local_only')`), because Task 1 treated every record as additive.
  - In the module, 17 tests failed on planned assertions: the replacement, mute and kind rows, 11 DID NOT RAISE, aliasing and renamed-label mute.
  - Six tests failed on API that did not exist yet (`parse_local_record`, `local_trigger_identity`, `match_local_records` (2 tests), `LOCAL_SAFE_POLICY` and `local_action_counts`), which GREEN added. This is disclosed rather than counted as assertion RED.
- **RED 3:** valid. All 8 failures were planned assertions: an empty outcome list, and Script mode `restart` instead of `queued`.

GREEN verification:

- `tests/test_local_parallel.py` and `tests/test_local_action_plans.py`: 129 passed.
- Wave gate (unit tier, with the expected-RED node deselected): 1719 passed, 191 deselected, 2 xfailed (the older ones in `tests/test_takeover.py`).
- The expected-RED node alone still reports `1 failed`.
- Multi-instance tier: 172 passed.

## Task Commits

1. **Task 1 (tracer): one additive trigger through one Script.** `d858726` (test), `9aa9737` (feat).
2. **Task 2: pure identity, mute, orphan and 24-case model.** `f2b08f0` (test), `2e29b78` (feat).
3. **Task 3: conservative per-branch outcomes.** `fd38f8c` (test), `cf07d09` (feat) and `e23c6d8` (refactor).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Outcome delivery moved into `finally` after a Core behavior differed from the top-level pin**
- **Found during:** Task 3 GREEN.
- **Issue:** The 11-01 pins show that a stopped run with a top-level `parallel` returns a normal result. In the production shape, the parallel sits inside the choose dispatcher, and there the stop, unload or restart re-raises `CancelledError`. A delivery placed after the `try` therefore never ran, so a local error recorded before the cancel would have been lost.
- **Fix:** The outcome is reduced and delivered in `finally`. Because `ran` stays False, a cancelled run is never proven. Two tests were added: a new loud Core pin (`test_dispatcher_wrapped_parallel_cancellation_raises_instead_of_returning`) and `test_outcome_local_error_before_a_cancel_stays_a_local_failure`.
- **Files modified:** `custom_components/mqtt_actions/runner.py`, `tests/test_local_parallel.py`
- **Commit:** `cf07d09`

**2. [Scope note] Safe policy wired into the runner now**
- The policy has two parts. The pure `EffectivePolicy` and `effective_policy` were among this plan's artifacts. `async_build_effective` also gained an optional `policy` and uses it for the Script mode and queue bound, so a pending local-only Script never inherits the unapproved owner's restart mode (D-03).
- Plan 11-05 Task 3 still owns feeding the same snapshot to the StateTracker and CircuitBreaker.

**Total deviations:** 1 auto-fixed (Rule 1) and 1 scope note. **Impact:** both strengthen D-03/D-19, and neither changes the overlay-free paths.

## Hand-offs and Known Limits

- **Plan 11-05:** call `async_build_effective(spec, build_effective_trigger_plans(spec, approval, records), policy=...)` from `_async_refresh_mirror_script` in place of the approval gate.
- **Plan 11-07:**
  - Attach `runner.on_local_outcome`. Failures arrive even from superseded or cancelled runs (`proven` only gates success).
  - The outer exception path still calls the owner `report_failure` for any exception, including one forwarded from the local branch. Owner `clear_issue` still fires on any returned result of the device, as it did before.
  - Local setup errors (invalid local actions at build) are only logged today.
  - All three need the separate local issue family.
- **Reducer edge (documented):** any `stop` step anywhere in a run counts as no local success. That includes an authored local stop as the last step. This is conservative, and an existing issue is left intact.
- The Plan 11-01 expected-RED Manager node is untouched and stays RED until Plan 11-05 Task 1.

## Known Stubs

None. `_branch_sequence` returns `[]` only for a plan with no runnable branch, and such a plan is filtered out before assembly.

## Threat Flags

None. The trace collector and the trust-level split are the T-11-05 to T-11-08 surface already in the plan's threat model.

## Issues Encountered

None beyond the Core cancellation difference above.

## User Setup Required

None.

## Next Phase Readiness

Plan 11-04 can adopt `parse_local_record` / `local_record_data` for the Store v1 rows. Plan 11-05 has its build entry point and policy snapshot.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

All 10 created/modified files exist, all 7 task commits are ancestors of HEAD, and the three RED records re-classify as RED_EVIDENCE_OK.
