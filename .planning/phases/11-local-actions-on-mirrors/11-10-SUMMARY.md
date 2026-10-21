---
phase: 11-local-actions-on-mirrors
plan: 10
subsystem: testing
tags: [local-actions, multi-instance, invariants, lifecycle, regression, tdd]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plans 11-04/11-05: per-instance local Store keys, Manager load, effective plans and policy"
  - phase: 11-local-actions-on-mirrors
    provides: "Plans 11-06/11-07: prune/tombstone/adoption lifecycle, test button and re-trigger gates"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-09: local Store deletion in both hub removal modes"
provides:
  - tests/test_local_multi_instance.py (multi_instance): two followers with different local plans on one owner and one broker
  - tests/test_local_invariants.py REQUIRED_TRANSITIONS / SILENT_TRANSITIONS / LIFECYCLE table and the per-transition publication oracle
affects: [11-11, 11-12, 11-13]

# Actuals (#2632)
actuals:
  tokens: 9506
  tasks: 2
  commits: 2
plan_head_before: 39c29338372debfe2e54a8ee20583ccd2fc32e5c
plan_head_after: 396a54f2ad16d797c9fb3d3d64b7132889d0d1b6

tech-stack:
  added: []
  patterns:
    - "Multi-instance expectations as one table (trigger -> instance -> services) checked on every entry point"
    - "Lifecycle oracle as a named step table; each step's gateway publications are scanned on their own"
    - "Unexpected GREEN in a test-only plan: RED evidence from a reverted mutation probe, never committed"

key-files:
  created:
    - tests/test_local_multi_instance.py
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-10-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-10-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-10-task1-unmutated.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-10-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-10-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-10-task2-unmutated.xml
  modified:
    - tests/test_local_invariants.py

key-decisions:
  - "No production change: both tasks were green against unmodified production, because Plans 11-04 to 11-09 already deliver the behavior. RED evidence comes from mutation probes that were reverted at once and never committed"
  - "The lifecycle oracle is a new test next to the existing one; the existing invariant tests and every preserved safeguard suite stay unchanged (D-23)"
  - "Local-only transitions (edit, remove, approval, native and legacy test press, refused or failed adoption, keep-mode hub removal) must publish nothing at all, not merely nothing marked"
  - "Re-trigger tests pin the manager clock of every instance: receivers rate-limit per device on their own clock too"

patterns-established:
  - "EXPECTED_RUNS / EXPECTED_ANSWERS tables: one place states what each instance runs and answers per trigger"

requirements-completed: [MIR-02, MIR-04, MIR-06, MIR-09, MIR-10, MIR-11]

coverage:
  - id: D1
    description: "Two followers save different additive/replacement/mute records for one owner's Switch, Select (with an empty option) and action-less Switch; each Store holds only its own records; saving publishes nothing and changes no retained byte; the owner cannot customize its own device"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "tests/test_local_multi_instance.py#test_followers_save_separate_records_and_publish_nothing"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner approval stays exact per follower and bound to the owner-only hash; pending and no-actions mirrors run on LOCAL_SAFE_POLICY, approved ones on the owner settings; both followers hold byte-identical documents and hashes"
    requirement: MIR-11
    verification:
      - kind: integration
        ref: "tests/test_local_multi_instance.py#test_followers_keep_exact_approvals_and_safe_policies_on_identical_shared_bytes"
        status: pass
    human_judgment: false
  - id: D3
    description: "State change, native test button and re-trigger run exactly each instance's effective plan (6 triggers x 3 instances); re-trigger answers use only the existing status/reason words"
    requirement: MIR-10
    verification:
      - kind: integration
        ref: "tests/test_local_multi_instance.py -k 'state_changes or test_buttons or retrigger'"
        status: pass
    human_judgment: false
  - id: D4
    description: "After a restart of both followers each reloads and runs only its own records"
    requirement: MIR-02
    verification:
      - kind: integration
        ref: "tests/test_local_multi_instance.py#test_follower_restarts_reload_only_their_own_records"
        status: pass
    human_judgment: false
  - id: D5
    description: "All 18 named lifecycle transitions run; no transition publishes a local marker; local-only transitions publish nothing; re-trigger answers keep the existing vocabulary"
    requirement: MIR-04
    verification:
      - kind: integration
        ref: "tests/test_local_invariants.py#test_every_lifecycle_transition_publishes_no_local_content"
        status: pass
    human_judgment: false
  - id: D6
    description: "Preserved native migration, shared-topic, kept-peer, export, registry and core-contract suites stay green unchanged"
    requirement: MIR-09
    verification:
      - kind: regression
        ref: "uv run pytest -q tests/test_local_invariants.py tests/test_local_actions_lifecycle.py tests/test_core_contracts.py tests/test_native_replay.py tests/test_takeover.py tests/test_export_guard_receiver.py tests/test_sync_owner.py tests/test_sync_follower.py (274 passed, 2 xfailed)"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-10-21
---

# Phase 11 Plan 10: Multi-Instance Isolation and Lifecycle Oracle Summary

**Two followers on one broker now keep different local plans for the same owner devices, and the tests prove that each follower runs only its own plan on every entry point. Approvals stay exact, pending mirrors use the safe policy, and every shared byte is identical. A named 18-transition lifecycle table checks every gateway publish for each transition separately. No production code changed: everything was already green, and reverted mutation probes show that the tests catch the defects they target.**

## Performance

- **Duration:** about 14 min (2026-10-21T02:46:52Z to 03:00:27Z)
- **Tasks:** 2 (1 tracer TDD, 1 TDD). There are 2 commits, both `test(11-10)`. No `feat` was needed, see TDD Gate Compliance.
- **Files:** 1 test module created, 1 test module extended, 6 evidence files created.

## Scenario matrix (tests/test_local_multi_instance.py)

Owner `alpha` owns three devices:
- **Lamp:** a Switch with `owner_on` and `owner_off`, plus `restart` 20/60.
- **Mode:** a Select whose `cozy` option runs `owner_cozy` and whose `bright` option is empty, plus 30/60.
- **Bare:** a Switch with no actions.

`beta` approves Lamp and `gamma` approves Mode.

| Trigger | alpha | beta (records) | gamma (records) |
|---------|-------|----------------|-----------------|
| Lamp ON | owner_on | approved + additive: owner_on, beta_lamp_on | pending + replacement: gamma_lamp_on |
| Lamp OFF | owner_off | approved + mute: nothing | pending + additive: gamma_lamp_off only |
| Mode cozy | owner_cozy | pending + replacement: beta_cozy | approved, no record: owner_cozy |
| Mode bright | nothing | pending, empty option: nothing | approved + additive on empty option: gamma_bright |
| Bare ON | nothing | no-actions owner + additive: beta_bare_on | nothing |
| Bare OFF | nothing | nothing | nothing |

- The same table must hold for a state change, a native test press on each instance and a re-trigger requested by alpha.
- Re-trigger answers: `executed`, `error/no_actions` (mute, empty), and `not_approved` (beta Mode bright). All of them are in `_STATUS_WORDS` and `_REASON_WORDS`.
- Policies:
  - beta Lamp `restart/20/60`.
  - gamma Mode `serial/30/60`.
  - Every pending or no-actions mirror uses `LOCAL_SAFE_POLICY`.
  - The breaker limits match the policy.
- `_approvals` holds only the owner-only hash of the approved device on each follower.
- Every local service name carries `sentinel`. No publication or retained message of any instance contains one.

## Lifecycle table (tests/test_local_invariants.py)

`REQUIRED_TRANSITIONS`: startup_with_local_store, local_edit, local_remove, owner_approval, owner_content_change, state_change, native_test_button, legacy_test_topic, retrigger, reconnect, resync, transient_prune, reattach, tombstone_after_prune, adoption_failure (owner online, forced subentry failure), adoption_success, hub_removal_keep, hub_removal_delete.

- Each step checks its own premise, for example that a prune keeps the Store bytes, that a reattach makes cozy/bright active again, and that adoption discards 1 record.
- After each step, the publishes of both gateways are scanned for every marker.
- `SILENT_TRANSITIONS` must publish 0 messages. Every other transition must publish at least 1, so its scan is not vacuous.
- The complete history and the retained state are scanned again at the end. The ack words are checked against the existing vocabulary.
- The prune is simulated with a silent retained-document loss while the owner is online.

## TDD Gate Compliance

Both tasks were **unexpected GREEN** against unmodified production. Plans 11-04 to 11-09 already implement every behavior these tests describe. Following fail-fast rule 1, I investigated. The tests are a regression oracle, so a pre-implementation RED is impossible.

To prove the tests are not vacuous, each one ran against temporary production mutations. Each mutation was reverted with `git checkout -- <file>` right after its run and never committed.

| Task | RED commit | Target node | Mutation (reverted) | Classifier |
|------|-----------|-------------|---------------------|-----------|
| 1 (tracer) | `70f4a9c` | `test_state_changes_run_only_each_followers_own_local_actions` | A local record admits the pending owner branch (`local_actions.py` build_effective_trigger_plan) | RED_EVIDENCE_OK |
| 2 | `396a54f` | `test_every_lifecycle_transition_publishes_no_local_content` | A tombstone after a prune keeps the records (`manager.py` async_remove_mirror) | RED_EVIDENCE_OK |

Other probes, all reverted:
- **Task 1, global local Store key:** the store-isolation and restart tests fail.
- **Task 1, owner settings trusted before approval:** the policy test fails.
- **Task 1, admitting the pending owner branch:** the state, test-button, re-trigger and restart tests fail.
- **Task 2, keep-mode removal skipping the local Store:** the hub_removal_keep row fails.
- **Task 2, local labels added to every ack:** the leak table fails on exactly the `retrigger` row.

`semanticAssessment` in `tdd/11-10-task{1,2}-red.json` holds the full text. The `*-unmutated.xml` files show that the unmutated runs pass.

- There is no `feat(11-10)` commit because no production code was needed. This is a gate deviation by design, and it is advisory.
- There is no `refactor` commit. The shared setup (`_started` / `_save_records` / `_scenario`) was factored before the first commit.
- **Tracer gate:** after Task 1 the `<verify>` ran again (6 passed) before Task 2.

## Verification

- Task 1: `uv run pytest -q -m multi_instance tests/test_local_multi_instance.py` gave 6 passed.
- Task 2: `uv run pytest -q tests/test_local_invariants.py tests/test_local_actions_lifecycle.py tests/test_core_contracts.py tests/test_native_replay.py tests/test_takeover.py tests/test_export_guard_receiver.py tests/test_sync_owner.py tests/test_sync_follower.py` gave 274 passed, 2 xfailed. The 2 xfails are the same pre-existing ones in `tests/test_takeover.py`.
- Full tiers, with no `--deselect`:
  - Unit: 1853 passed, 2 xfailed.
  - Multi-instance: 180 passed (was 173).
  - Broker: 18 passed.
  - In total that is 2051 passed and 2 xfailed, up from 2044.
- `uv run ruff check` is clean on `custom_components` and `tests`, and `ruff format --check` is clean too. No skip or xfail was added.

## Task Commits

1. **Task 1 (tracer): two followers run isolated local plans on one broker.** `70f4a9c` (test)
2. **Task 2: lifecycle publication oracle over every named transition.** `396a54f` (test)

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

### Notes

**1. [Characterization] Unexpected GREEN, with RED from mutation probes**
- **Found during:** Task 1 RED and Task 2 RED.
- **Issue:** Production already implements the behavior, so the new tests passed at once.
- **Handling:** I ran the reverted mutation probes described above, ran the classifier on their JUnit evidence, and made no production change.
- **Commits:** `70f4a9c`, `396a54f`.

**2. [Scope] `tests/test_local_actions_manager.py` and `tests/test_local_actions_lifecycle.py` unchanged**
- Both are listed in the plan's `files_modified`. Neither needed a change: the multi-instance cases live in their own `multi_instance` module, and the lifecycle suite runs unchanged in the Task 2 regression command.

**3. [Rule 1 - Test bug, fixed before commit] Re-trigger receivers rate-limit on their own clock**
- The first draft pinned only the requester's clock, so receivers dropped the second request per device and answered `no_answer`. That is correct product behavior (`_admit`). The test now pins the manager clock of all three instances.

**Total deviations:** 0 production fixes, plus 1 characterization note, 1 scope note and 1 test-only fix. **Impact:** none. No product defect was found.

## Known Stubs

None.

## Threat Flags

None. The tests cover the plan register as follows:
- **T-11-30:** distinct Store keys, the global-key probe, and the restart of both followers.
- **T-11-31:** exact approval and safe policy for each follower, plus the owner-branch probe.
- **T-11-32:** the preserved suites run unchanged, together with the lifecycle table.
- **T-11-33:** the breaker and queue limits for each follower are asserted against the policy.

## Hand-offs

- **Plan 11-12 (docs):** you can cite the scenario matrix as the multi-instance guarantee. Two followers may disagree, and nothing local reaches the broker.
- **Plan 11-13 / UAT:** the bench check for two followers with different overlays matches the table above.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Multi-instance isolation and the lifecycle oracle are complete. 11-12 can run next in wave 9.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

Both task commits (`70f4a9c`, `396a54f`) are ancestors of HEAD. The new test module and the evidence files exist. Both RED records classify as RED_EVIDENCE_OK. The production tree is unchanged (`git diff 39c2933..HEAD -- custom_components` is empty).
