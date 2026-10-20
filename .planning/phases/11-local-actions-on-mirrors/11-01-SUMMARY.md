---
phase: 11-local-actions-on-mirrors
plan: 01
subsystem: testing
tags: [pytest, phacc, home-assistant-script, parallel, trace, fake-broker, tdd, invariants]

# Dependency graph
requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: loud installed-Core contract test style, FakeGateway publish history, InstanceFactory store-key seam
provides:
  - Owner-byte and every-publication leakage guards against a sentinel local-actions Store (tests/test_local_invariants.py)
  - Exact 24-row approval x customization x owner-trigger gate oracle plus separate mute/additive-empty/orphan/kind-mismatch rows (tests/test_local_action_plans.py)
  - The single expected-RED Manager target with RED_EVIDENCE_OK evidence (tests/test_local_actions_manager.py, tdd/11-01-task2-red.{xml,json})
  - Permanent Core 2026.9.4 parallel, trace and owner-only guard pins with a reference branch reducer (tests/test_local_parallel.py)
affects: [11-03, 11-04, 11-05, 11-07, 11-10]

# Actuals (#2632)
actuals:
  tokens: 18670
  tasks: 3
  commits: 3
plan_head_before: 762a3db8d4d4897bea302bab6f56d6b36282b7bc
plan_head_after: 4b07fb04d52d4b91438671a8a61c5fe35ab4f39a

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sentinel Store A/B oracle: owner artifacts compared byte-for-byte with builders fed only the subentry data"
    - "Publication oracle scans every FakeGateway.published tuple (retained and transient) plus the retained broker state"
    - "Core pins classify branch outcomes from trace paths and service callbacks, never from the outer result"

key-files:
  created:
    - tests/test_local_invariants.py
    - tests/test_local_action_plans.py
    - tests/test_local_actions_manager.py
    - tests/test_local_parallel.py
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.json
  modified: []

key-decisions:
  - "tests/test_local_invariants.py carries pytestmark multi_instance: it uses make_instance, and test_repo_structure enforces that tier marker; it runs in the multi-instance tier and in direct file runs, not in the unit tier"
  - "Seeded local Store v1 record shape for Plan 11-04: envelope {version 1, minor_version 1, key, data: {records: [...]}}; record keys device_id, kind, state_value, label, mode (additive|replacement), actions (raw list)"
  - "Invariant seeds use the literal key mqtt_actions.local_actions plus getattr(instance, 'local_store_key'), and every instance is stopped, seeded and started again, so Plan 11-04/11-05 key injection is picked up without editing these tests"
  - "Pinned Core behavior beyond the probe: a false condition ends only its parallel branch, async_stop/unload/restart return a normal ScriptRunResult for the cancelled run, a queued overflow returns None before any branch starts"

patterns-established:
  - "Expected-RED evidence: JUnit XML from the real run embedded in a JSON record with semanticAssessment, expiry and exceptionRef, checked by gsd-tools check tdd-red-evidence"
  - "Every assertion of a Core pin carries a hint naming Core 2026.9.4 and the D-20 rule"

requirements-completed: [MIR-02, MIR-03, MIR-04, MIR-05, MIR-10, MIR-11, MIR-13, MIR-14]

coverage:
  - id: D1
    description: "Owner actions hash, document bytes, adoption subentry bytes, export payload and diagnostics are unchanged with a sentinel local Store loaded"
    requirement: MIR-04
    verification:
      - kind: integration
        ref: "tests/test_local_invariants.py -k 'hash or adoption or publication'"
        status: pass
      - kind: integration
        ref: "tests/test_local_invariants.py#test_diagnostics_hash_rows_carry_no_local_content"
        status: pass
    human_judgment: false
  - id: D2
    description: "No integration publish (retained or transient) carries local markers through startup, approval, state/test/retrigger, reconnect, resync, prune, tombstone and hub removal"
    requirement: MIR-14
    verification:
      - kind: integration
        ref: "tests/test_local_invariants.py#test_no_publication_carries_local_content_across_the_lifecycle"
        status: pass
      - kind: unit
        ref: "tests/test_local_invariants.py#test_publication_oracle_sees_markers_in_transient_and_retained_publishes"
        status: pass
    human_judgment: false
  - id: D3
    description: "Exact 24-case gate oracle with separate mute, additive-empty, orphan and kind-mismatch rows and identity self-checks, no production import"
    requirement: MIR-05
    verification:
      - kind: unit
        ref: "tests/test_local_action_plans.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Single Manager-backed expected-RED target with valid semantic RED evidence (expiry Plan 11-05 Task 1)"
    requirement: MIR-02
    verification:
      - kind: other
        ref: "node /home/akentner/.codex/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.json --raw"
        status: pass
    human_judgment: false
  - id: D5
    description: "Core 2026.9.4 parallel, trace, stop, continue_on_error, response-variable, cancellation, drop, rebuild, supersession and owner-only guard pins"
    requirement: MIR-03
    verification:
      - kind: unit
        ref: "tests/test_local_parallel.py"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 01: Invariant and Core-Contract Test Boundary Summary

**Sentinel local-Store oracles for owner bytes and every fake-broker publish, a 24-row approval x customization x owner-trigger gate oracle, one Manager-backed expected-RED target with RED_EVIDENCE_OK evidence, and 19 loud Core 2026.9.4 parallel/trace pins. All of it was committed before any Phase 11 production edit.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-10-20T23:28:07Z
- **Completed:** 2026-10-20T23:43:43Z
- **Tasks:** 3
- **Files created:** 6 (4 test modules, 2 evidence files); no production file touched

## Accomplishments

- **Characterization and leak guards (green, 7 tests).** `tests/test_local_invariants.py` seeds a local Store full of markers (data, template, target, label, orphan StateValue, authored publish topic). With that Store present, the tests prove byte equality with the owner-only baseline for:
  - `actions_hash` (mirror info, running specs and stored approvals)
  - the canonical document (every publish, the retained copy, the follower cache and the main Store)
  - the adoption subentry (canonical JSON and dict) and the adopted document
  - the export payload
  - the diagnostics hashes

  It then scans the complete `FakeGateway.published` history of both instances plus the retained state across the whole lifecycle. A self-check proves the oracle reports markers in transient payloads, retained payloads and topics.
- **Gate oracle (green, 43 tests).** `tests/test_local_action_plans.py` holds `EXPECTED_GATE_CASES` with exactly 24 unique rows covering the full axis product. Eight separate rows sit outside the matrix: two empty-replacement mutes, two additive-empty, two orphan and two kind-mismatch. A test-local reference rule and property checks cover:
  - the owner branch needs the exact approval
  - local eligibility does not depend on approval
  - an absent customization behaves as owner-only
  - a replacement never grants the owner branch

  Identity checks cover kind separation and StateValue normalization. The module imports nothing from `custom_components`.
- **Expected-RED target (1 failing test, by design).** `tests/test_local_actions_manager.py::test_pending_mirror_with_persisted_additive_record_gains_local_branch` fails only on the planned local call-count assertion.
- **Core pins (green, 19 tests).** `tests/test_local_parallel.py` covers the ten probe cases plus continued, nested continued and nested uncaught local errors, condition abort, cancellation, queued drop, rebuild, restart supersession and the choose dispatcher (different trigger and owner-only). Every assertion carries the Core 2026.9.4 / D-20 hint.

## RED Evidence handed to Plan 11-05 Task 1

- **Node id:** `tests/test_local_actions_manager.py::test_pending_mirror_with_persisted_additive_record_gains_local_branch`
- **Command:** `uv run pytest -q "<node id>" --junitxml=.planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.xml`, exit 1, `1 failed`
- **Checker:** `node /home/akentner/.codex/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.json --raw` returned `RED_EVIDENCE_OK`, reason `target_test_failed`, format `junit`, 1 test, 1 failure, matched `tests.test_local_actions_manager#test_pending_mirror_with_persisted_additive_record_gains_local_branch`, no report errors.
- **Expected:** local mock service `test.local_on` called once, owner `test.owner_on` called 0 times, approval stays `pending`.
- **Actual:** local called 0 times (`AssertionError: the local branch of the pending mirror ran 0 times, expected 1`), owner called 0 times.
- **semanticAssessment:** valid semantic RED. The target was collected and executed with no setup, import, fixture or collection fault, and the premise assertion (`pending`) passed. It fails on the planned assertion because the Manager never reads `mqtt_actions.local_actions`, and `_async_refresh_mirror_script` unloads the whole Script of an unapproved mirror.
- **Expiry:** Plan 11-05 Task 1. GREEN keeps the assertions unchanged; only the seeded fixture may be aligned to the 11-04 schema. Exception reference: `11-VALIDATION.md` "Expected-RED Exception".
- **Interval gate check (both commands):**
  - The unit tier with the node deselected passes: 1652 passed, 191 deselected. It also reports 2 xfailed; those tests are older and live in `tests/test_takeover.py`.
  - The node alone reports `1 failed in 0.95s`, and the tail-line grep succeeds.

## Seeded v1 record shape for Plan 11-04

```json
{"version": 1, "minor_version": 1, "key": "mqtt_actions.local_actions",
 "data": {"records": [{"device_id": "<uuid>", "kind": "switch", "state_value": "ON", "label": "On",
                       "mode": "additive", "actions": [{"action": "test.local_on", "data": {"source": "local"}}]}]}}
```

- `kind` is `switch` or `select` (const `SUBENTRY_SWITCH` / `SUBENTRY_SELECT`).
- `mode` is `additive` or `replacement`. An empty `actions` with `replacement` is a mute.
- The invariant tests also seed orphan and kind-mismatched rows of the same shape.

## Task Commits

1. **Task 1: Pin immutable owner bytes and every broker publication** - `610b47a` (test). Tracer gate: verify re-run green, expansion continued.
2. **Task 2: 24-case gate oracle and Manager-backed semantic RED target** - `fb8fb92` (test, RED)
3. **Task 3: Core parallel, trace and trust pins** - `4b07fb0` (test)

## Files Created/Modified

- `tests/test_local_invariants.py`: owner hash/document/adoption/export/diagnostics byte oracles and the lifecycle publication oracle (multi_instance tier).
- `tests/test_local_action_plans.py`: pure 24-row oracle, separate rows, reference rule and self-checks (unit tier).
- `tests/test_local_actions_manager.py`: the single expected-RED target (unit tier); Plan 11-05 extends this module.
- `tests/test_local_parallel.py`: installed-Core parallel/trace/guard pins with a reference branch reducer (unit tier).
- `.planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.xml`, `.json`: the RED evidence.

## Decisions Made

- **Tier for the invariants module.** `tests/test_local_invariants.py` is `pytestmark = pytest.mark.multi_instance`, because `test_repo_structure.test_tiers_partition_the_suite` requires that marker for any module using `make_instance`. Its gates are direct file runs (`-k "hash or adoption or publication"` and 11-10-T2), so the unit-tier wave gate does not include it. Wave gates must also run the multi-instance tier, as 11-VALIDATION.md requires.
- **Forward-compatible seeding.** Each instance is stopped, seeded under `mqtt_actions.local_actions` plus any `Instance.local_store_key` that exists, and started again. Once Plans 11-04/11-05 inject per-instance keys, the seeds attach to real mirror identities with no test edit.
- **Authored `mqtt.publish` in local actions.** The test treats it as execution data. It goes to a mocked service and never to the gateway, so it is excluded from the serialization oracle by construction, and a final assertion checks that no gateway topic carries the authored topic.
- **Extra Core facts, pinned on purpose.** The reducer in Plan 11-03 must not read these as a local success:
  - A false condition ends only its own parallel branch, and the outer run continues.
  - `async_stop`, `async_unload` and restart supersession all return a normal `ScriptRunResult` for the cancelled run.
  - A queued overflow returns `None`, and no branch of that run starts.

## Deviations from Plan

None. The plan was executed as written. The tier marker above follows from an existing repository rule. It is not a change in scope.

## TDD Gate Compliance

This is an `execute` plan with one `tdd="true"` task, and that task is RED-only by design.
- RED commit: `fb8fb92` (`test(11-01): ...`).
- No GREEN commit exists in this plan. GREEN belongs to Plan 11-05 Task 1, under the 11-VALIDATION.md Expected-RED Exception. It is not a gate violation.

## Issues Encountered

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plan 11-03 binds `EXPECTED_GATE_CASES` and the separate rows to `build_effective_trigger_plan` without changing rows. It builds its reducer against the `test_local_parallel.py` pins.
- Plan 11-04 should adopt the seeded v1 record shape above. Plan 11-05 Task 1 turns the expected-RED target GREEN.
- Wave gates in the interval must use both commands of the Expected-RED Exception.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED
