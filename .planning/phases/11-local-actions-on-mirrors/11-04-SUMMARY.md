---
phase: 11-local-actions-on-mirrors
plan: 04
subsystem: persistence
tags: [local-actions, store, migration, isolation, tdd, fake-broker]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-03: parse_local_record / local_record_data (v1 row), LocalActionRecord, LocalActionIdentity"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-01: seeded v1 envelope under mqtt_actions.local_actions, invariant tests reading Instance.local_store_key"
provides:
  - LOCAL_ACTIONS_STORE_KEY / LOCAL_ACTIONS_STORE_VERSION / LOCAL_ACTIONS_STORE_MINOR_VERSION / LOCAL_ACTIONS_RECORDS constants
  - HA-free parse_local_actions_payload, local_actions_payload, migrate_local_actions_payload, copy_local_records
  - LocalActionsStore (load/save/remove adapters, migration hook, newer-version refusal, write-error reporting)
  - Per-instance local Store keys in the fake-broker harness (instance_store_keys, Instance.local_store_key)
affects: [11-05, 11-06, 11-07, 11-09]

# Actuals (#2632)
actuals:
  tokens: 9016
  tasks: 2
  commits: 5
plan_head_before: 592d547436aed6478413f78cd252d9be8fb55073
plan_head_after: 9257a6a591d6213af45fd200abd602aabaa11796

tech-stack:
  added: []
  patterns:
    - "Store subclass overrides the installed _async_migrate_func hook and delegates to an HA-free migrator"
    - "Store subclass overrides _async_write_data to capture the write errors the base Store only logs"
    - "Snapshot replaced only after a proven write; every record handed out is a deep copy"

key-files:
  created:
    - custom_components/mqtt_actions/local_actions_store.py
    - tests/test_local_actions_store.py
    - tests/test_local_actions_store_instances.py
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-04-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-04-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-04-task2-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-04-task2-red.json
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/local_actions.py
    - tests/fake_broker.py

key-decisions:
  - "Local Store payload v1 is {records: [row, ...]} in the HA envelope {version 1, minor_version 1, key, data}; a row is exactly the 11-01/11-03 shape {device_id, kind, state_value, label, mode, actions}"
  - "HA's Store logs and swallows WriteError/SerializationError, so LocalActionsStore overrides _async_write_data to capture them; async_save_records raises LocalActionsStoreError and keeps the previous snapshot on any write failure"
  - "A newer major version fails the load with HA's UnsupportedStorageVersionError (before the hook runs), and the adapter then refuses every save, so the newer file is never overwritten; any other unknown major raises LocalActionsStoreVersionError from the pure migrator"
  - "Duplicate identities: the parser keeps the first row (same rule as match_local_records) and counts the rest as dropped; a save with two records of one identity is refused"
  - "A save before a successful load is refused; removal is always allowed, even after a refused load"
  - "Test instances get f'{LOCAL_ACTIONS_STORE_KEY}.{name}' through instance_store_keys; a bare Instance defaults to the production key"

patterns-established:
  - "Load never rewrites the local Store (no startup garbage collection); only the migration hook saves"
  - "Malformed rows dropped one by one and logged by count only, never with stored content"

requirements-completed: [MIR-04, MIR-06, MIR-07]

coverage:
  - id: D1
    description: "One overlay round-trips through its own versioned Store, with the shown and canonical StateValue, label, mode and raw actions"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "tests/test_local_actions_store.py -k round_trip"
        status: pass
    human_judgment: false
  - id: D2
    description: "Strict per-row load: malformed rows and duplicate identities dropped independently, orphan and kind-mismatched rows kept, no rewrite on load"
    requirement: MIR-07
    verification:
      - kind: integration
        ref: "tests/test_local_actions_store.py -k 'malformed or orphan'"
        status: pass
    human_judgment: false
  - id: D3
    description: "A newer major version fails the load and is never overwritten; the pure migrator refuses unknown majors and copies a minor-only difference"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "tests/test_local_actions_store.py -k 'newer or migrate'"
        status: pass
    human_judgment: false
  - id: D4
    description: "Today's main save and a simulated v1.0.1 main serializer leave the local Store byte-identical"
    requirement: MIR-04
    verification:
      - kind: integration
        ref: "tests/test_local_actions_store.py#test_old_main_store_save_leaves_the_local_store_byte_identical"
        status: pass
    human_judgment: false
  - id: D5
    description: "A failed write (swallowed WriteError or raised OSError) raises LocalActionsStoreError and keeps the previous durable and in-memory snapshot"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "tests/test_local_actions_store.py#test_failed_save_keeps_the_previous_durable_and_in_memory_snapshot"
        status: pass
    human_judgment: false
  - id: D6
    description: "Distinct per-instance main and local Store keys; two factory instances on one broker see only their own overlays; removal deletes only the selected key"
    requirement: MIR-04
    verification:
      - kind: integration
        ref: "tests/test_local_actions_store_instances.py"
        status: pass
      - kind: integration
        ref: "tests/test_local_actions_store.py -k 'instance or remove'"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-10-21
---

# Phase 11 Plan 04: Separate Local-Actions Store Summary

**A separate, versioned `LocalActionsStore` (`mqtt_actions.local_actions`, v1.1) behind an HA-free parser and migrator. It refuses newer payloads without overwriting them, reports write failures that HA's base Store only logs, and keeps the previous snapshot when a save fails. Each fake-broker test instance gets its own injected local Store key.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-21T00:37:55Z
- **Completed:** 2026-10-21T00:48:04Z
- **Tasks:** 2 (tracer + TDD), 5 commits (2 RED, 2 GREEN, 1 REFACTOR)
- **Files:** 1 production module created, 2 modified; 2 test modules created, 1 modified; 4 evidence files

## Final Store payload shape (for Plan 11-05)

```json
{
  "version": 1,
  "minor_version": 1,
  "key": "mqtt_actions.local_actions",
  "data": {
    "records": [
      {"device_id": "...", "kind": "switch|select", "state_value": "<as shown>", "label": "<last label>",
       "mode": "additive|replacement", "actions": [ /* raw JSON action list */ ]}
    ]
  }
}
```

- This is exactly the envelope Plan 11-01 seeded in `tests/test_local_actions_manager.py`, so Plan 11-05 needs no fixture change.
- Raw JSON actions and schema metadata only. No Templates, owner hash, owner id or mirror revision.

## Injected-key contract

- **Production:** `LocalActionsStore(hass)` uses `LOCAL_ACTIONS_STORE_KEY = "mqtt_actions.local_actions"`.
- **Tests:** `tests.fake_broker.instance_store_keys(name)` returns `("mqtt_actions.state.<name>", "mqtt_actions.local_actions.<name>")`.
  - `InstanceFactory` passes both keys to `Instance`, which exposes them as `store_key` and `local_store_key`.
  - A bare `Instance` defaults to the production keys.
- **Plan 11-05 hand-off:**
  - Add a `local_store_key` seam to `Manager` (and to `async_remove_local_state` / `async_remove_all_devices` for D-08).
  - Pass `instance.local_store_key` in `Instance.start` and the `InstanceFactory` constructors.
  - Extend `_real[hass]` in `_patch_gateways` to carry the local key.
  - The invariant tests already seed `getattr(instance, "local_store_key")`.

## Adapter API (`custom_components/mqtt_actions/local_actions_store.py`)

- `LocalActionsStore(hass, key=LOCAL_ACTIONS_STORE_KEY)` is constructed with `private=True` and `atomic_writes=True`.
- `async_load_records()` returns a tuple of deep-copied records.
  - A missing file or an empty list gives `()`.
  - A malformed payload shape gives `()`, with a warning.
  - Dropped rows are logged by count only.
  - A newer major version raises `UnsupportedStorageVersionError`, and the Store then refuses saves.
- `async_save_records(records)` writes the complete set at once, under its own lock.
  - It returns copies of what was saved.
  - It raises `LocalActionsStoreError` in four cases: before a load, after a refused load, for duplicate identities, or on any write failure. In every case the previous snapshot stays.
- `async_remove_records()` deletes only this key and forgets the records. It is allowed even after a refused load.
- `records` returns copies of the last successful load or save.
- Pure helpers in `local_actions.py`:
  - `parse_local_actions_payload(data) -> ParsedLocalActions(records, dropped, shape_valid)`
  - `local_actions_payload(records)`
  - `migrate_local_actions_payload(major, minor, data)`
  - `copy_local_records(records)`
  - `LocalActionsStoreVersionError`

## TDD Evidence

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 (tracer) | `47cb369` | `tests/test_local_actions_store.py::test_round_trip_one_additive_record_through_a_separate_store` | RED_EVIDENCE_OK (junit, 1 test, 1 failure) | `f995780` | none needed |
| 2 | `8c9ff7a` | `tests/test_local_actions_store.py::test_instance_local_stores_see_only_their_own_records` | RED_EVIDENCE_OK (junit, 1 test, 1 failure) | `d9c353c` | `9257a6a` |

Semantic assessments (full text in `tdd/11-04-task{1,2}-red.json`):

- **RED 1:** valid. Imports resolved against a compile-only skeleton: the constants, the pure functions returning trivial values, and adapters returning `()`. The target failed on its first planned assertion, because `async_save_records` returned `()` instead of `(record,)`.
  - In the module, 11 tests failed and 9 passed. Two of the failures were not assertion failures but consequences of the empty skeleton load: a tuple-unpack `ValueError` and a `KeyError` on the never-written key. This is disclosed rather than counted as assertion RED.
  - The 9 that passed include the missing-file, shape and main-key characterizations.
- **RED 2:** valid. The skeleton `instance_store_keys` returned the global production local key for every instance, so the owner Store loaded the follower's record. That is the T-11-11 collision itself.
  - The removal test and the key-contract test also failed on their planned assertions.
  - The real-factory test in `test_local_actions_store_instances.py` failed on its distinct-key assertion.
- **Gate sequence:** a `test(11-04)` commit precedes each `feat(11-04)` commit. The tracer gate re-ran Task 1's `<verify>` green (20 passed) before expansion.

## Task Commits

1. **Task 1 (tracer): round-trip one overlay through a separate versioned Store.** `47cb369` (test), `f995780` (feat).
2. **Task 2: old-main-Store isolation, failed-save behavior, per-instance keys.** `8c9ff7a` (test), `d9c353c` (feat), `9257a6a` (refactor).

## Verification

- `uv run pytest -q tests/test_local_actions_store.py`: 27 passed. With the instance module: 28 passed.
- Ruff `check` and `format --check` are clean for all of `custom_components/` and `tests/`.
- Wave-3 unit gate with only the expected-RED node deselected: 1746 passed, 2 xfailed (the older `tests/test_takeover.py` ones).
- The expected-RED node alone still reports exactly `1 failed`, as the interval gate requires.
- Multi-instance tier: 173 passed, including the new real-factory test and `tests/test_local_invariants.py`, which now seeds the injected per-instance keys.
- No new runtime dependency. No change to manifest, pyproject or lock. No manual path or file I/O in the adapter. `local_actions.py` stays HA-free.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HA's base Store swallows write failures, so they had to be captured**
- **Found during:** Task 1 GREEN (reading the installed `storage.py:569-589`).
- **Issue:** `Store._async_handle_write_data` catches `WriteError` and `SerializationError`, logs them and returns normally. A plain `async_save` would have acknowledged a failed disk write, which breaks D-22 and T-11-10 ("never acknowledge before durable save").
- **Fix:** `LocalActionsStore` overrides `_async_write_data` to remember the error. `async_save_records` raises `LocalActionsStoreError` and only then replaces the snapshot. The fix is tested with both a swallowed `WriteError` and a raised `OSError`.
- **Files modified:** `custom_components/mqtt_actions/local_actions_store.py`
- **Commit:** `f995780`
- **TDD note:** this landed in Task 1's GREEN, so Task 2's failed-save test was already green at Task 2 RED and acts as a characterization test. Task 2's RED target is the per-instance isolation test instead.

**2. [Rule 2 - Missing critical] Refusals that protect stored data**
- **Found during:** Task 1 GREEN.
- **Issue:** the plan names the newer-version case only for the load. A later save on the same Store object would still have overwritten the newer file. The parser and the save path also had no rule for duplicate identities.
- **Fix:**
  - After a refused or missing load, a save raises.
  - A save with two records of one identity raises.
  - The parser keeps the first row of an identity, which is the same rule as `match_local_records`.
- **Files modified:** `local_actions.py`, `local_actions_store.py`
- **Commits:** `f995780` (tests in `8c9ff7a`)

**3. [Rule 3 - Blocking] Extra test module for the real-factory test**
- **Found during:** Task 2 RED.
- **Issue:** `tests/test_repo_structure.py::test_tiers_partition_the_suite` requires that any module using `make_instance` carries a module-level `pytestmark = pytest.mark.multi_instance`. Adding that to `tests/test_local_actions_store.py` would have moved every Store test out of the unit tier.
- **Fix:** the real `InstanceFactory` test lives in the new `tests/test_local_actions_store_instances.py` (multi-instance tier). The unit module covers the same contract through `instance_store_keys`, plus two Stores on the shared storage mock.
- **Files added:** `tests/test_local_actions_store_instances.py` (not in `files_modified`)
- **Commit:** `8c9ff7a`

**Total deviations:** 3 auto-fixed (1 Rule 1, 1 Rule 2, 1 Rule 3). **Impact:** all three tighten T-11-09, T-11-10 and T-11-11. None of them changes the main Store, the Manager or any wire path.

## Known Limits and Hand-offs

- **Shutdown:** while HA is `stopping`, the base `Store.async_save` defers the write to the final-write listener. In that window a save returns before the bytes are on disk. This is standard HA behavior, and Manager edits happen while running.
- **Load errors propagate:** a refused load raises (`UnsupportedStorageVersionError` or `LocalActionsStoreVersionError`). Plan 11-05 decides how the Manager reacts. Recommended: start without overlays, keep the Store refusing saves, and log or raise an issue (11-07 family).
- **Minor versions:** a newer minor of major 1 is read, and the hook's save relabels it as minor 1 with the payload unchanged. Unknown row keys are dropped only by a later save.
- **Not wired yet:** the Manager does not load the Store until Plan 11-05 Task 1, so the expected-RED Manager node is untouched and stays RED.

## Known Stubs

None.

## Threat Flags

None. The surface is the T-11-09 to T-11-11 register of the plan.

## Issues Encountered

None beyond the swallowed-write-error behavior above.

## User Setup Required

None.

## Next Phase Readiness

Plan 11-05 can construct `LocalActionsStore(hass, local_store_key)`, load it before mirrors are restored, and feed `records` into `build_effective_trigger_plans`.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

All 7 created files exist, all 5 task commits are ancestors of HEAD, and both RED records re-classify as RED_EVIDENCE_OK.
