---
phase: 01-walking-skeleton-installable-switch
plan: 04
subsystem: trigger-path
tags: [home-assistant, mqtt, state, store, repairs, script, mosquitto]

requires:
  - phase: 01-03
    provides: validated RAW-stored subentry data, translation keys issues.action_failed and issues.mqtt_discovery_disabled
provides:
  - StateTracker (baseline, startup window, run_on_startup) on top of the pure decide()
  - Store-backed baseline (last_acted) and published-id set with delayed save and flush on stop
  - Per-device FIFO run queue with log plus one Repairs issue per device (create, update in place, delete on success)
  - ActionRunner.report_failure and async_unload(device_id, remove_issue) for the device remove path
  - Real-Mosquitto proof of the retain flag semantics (broker marker, mosquitto_port fixture)
affects: [01-05, 01-06]

actuals:
  tokens: 14000
  tasks: 3
  commits: 5
plan_head_before: 3953a24660b5dbd0a4f28141f4b81298ba441b4e
plan_head_after: 60b1036da6f45005a3b1edd163d195e5c6af4b7c

tech-stack:
  added: []
  patterns:
    - "Retained means baseline, live means edge; the startup window is closed by the first message of any kind"
    - "Store.async_delay_save on baseline change, one async_save in async_stop (never per message)"
    - "One asyncio.Lock per device id; Script mode single stays, the lock prevents dropped overlapping runs"
    - "Issue id action_failed_{device_id}; async_create_issue updates in place and keeps a dismissal, async_delete_issue on success"
    - "Log lines carry device and trigger names and a truncated repr of unknown payloads, never action data"

key-files:
  created:
    - tests/test_state.py
    - tests/test_manager.py
    - tests/broker/__init__.py
    - tests/broker/conftest.py
    - tests/broker/test_retain_semantics.py
  modified:
    - custom_components/mqtt_actions/state.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/runner.py
    - custom_components/mqtt_actions/const.py
    - pyproject.toml

key-decisions:
  - "async_reconcile(startup=...) carries the D-05 rule: only devices built by async_start get startup_pending=True; devices added later by the update listener get False"
  - "Runner API takes plain strings, enqueue(device_id, device_name, trigger, script, run_variables), so runner.py does not import the manager's Device class (no import cycle)"
  - "The runner owns the built Scripts per device id (async_build_script registers them), which is what lets async_unload(device_id) work without the manager passing scripts around"
  - "A run queued for a device that was unloaded meanwhile is skipped, so a stop cannot produce a RuntimeError-based failure issue"
  - "Stored data is validated on load (only ON or OFF values, only string ids) because the Store file is a trust boundary"

requirements-completed: []

coverage:
  - id: D1
    description: "Only real edges run actions: live ON/OFF once, duplicate live value nothing, case and whitespace insensitive"
    requirement: STA-02
    verification:
      - kind: unit
        ref: "tests/test_manager.py#test_edge_live_on_runs_on_actions_once"
        status: pass
      - kind: unit
        ref: "tests/test_manager.py#test_edge_duplicate_live_value_is_ignored"
        status: pass
      - kind: unit
        ref: "tests/test_state.py#test_decide_table"
        status: pass
    human_judgment: false
  - id: D2
    description: "Retained messages only set the baseline; run_on_startup acts once after start or reload; runtime-created devices never get it"
    requirement: STA-04
    verification:
      - kind: unit
        ref: "tests/test_manager.py#test_retain_replay_sets_baseline_without_actions"
        status: pass
      - kind: unit
        ref: "tests/test_manager.py#test_startup_flag_runs_retained_state_once"
        status: pass
      - kind: unit
        ref: "tests/test_manager.py#test_new_device_ignores_startup_flag"
        status: pass
    human_judgment: false
  - id: D3
    description: "The last processed state is persisted with Store and restored on reload; nothing is persisted before the first valid message"
    requirement: STA-05
    verification:
      - kind: unit
        ref: "tests/test_manager.py#test_baseline_persisted_across_reload"
        status: pass
      - kind: unit
        ref: "tests/test_manager.py#test_baseline_not_persisted_before_first_message"
        status: pass
    human_judgment: false
  - id: D4
    description: "A failing action is logged and shown as one non-fixable Repairs issue per device, updated in place, cleared by success, dismissal kept, text capped, no action data leaked"
    requirement: DEV-08
    verification:
      - kind: unit
        ref: "tests/test_manager.py#test_issue_created_when_action_fails"
        status: pass
      - kind: unit
        ref: "tests/test_manager.py#test_issue_dismissed_stays_dismissed_while_failing"
        status: pass
      - kind: unit
        ref: "tests/test_manager.py#test_issue_and_log_do_not_leak_action_data"
        status: pass
    human_judgment: false
  - id: D5
    description: "Runs per device are first-in first-out and none is dropped"
    requirement: DEV-08
    verification:
      - kind: unit
        ref: "tests/test_manager.py#test_actions_run_serially_in_order"
        status: pass
    human_judgment: false
  - id: D6
    description: "Real broker: replay on subscribe has retain=True, live forward retain=False, resubscribe replays with retain=True, retained clear is a live empty message"
    requirement: STA-04
    verification:
      - kind: integration
        ref: "tests/broker/test_retain_semantics.py (4 tests, Mosquitto 2.1.2)"
        status: pass
    human_judgment: false
  - id: D7
    description: "How the Repairs issue text and the German wording read in the real frontend"
    requirement: DEV-08
    verification: []
    human_judgment: true
    rationale: "Rendering of the placeholders and tone of the text is not asserted by any test; needs a look in the HA UI during UAT"

duration: about 25min
completed: 2026-09-29
status: complete
---

# Phase 1 Plan 04: Trigger Path Summary

**Retained replays only move the baseline and live changes run their actions exactly once through a per-device FIFO queue, the baseline survives reloads through a delay-saved Store, failures show up as one updatable, clearable Repairs issue per device, and a real Mosquitto test pins the retain-flag semantics all of this rests on.**

## Performance

- **Duration:** about 25 min (start 2026-09-29T08:05Z, end 08:13Z for code; SUMMARY after)
- **Tasks:** 3 (Tasks 1 and 2 TDD with RED then GREEN, Task 3 plain auto)
- **Files created:** 5, modified: 5
- **Commits:** 5 (measured from `plan_head_before`)
- **Suite:** 126 passed (63 before, 63 new including 4 broker tests)

## Accomplishments

- **Task 1, decision and baseline:** the tracer's `decide()` already covered the table; it now has table-driven tests (22 rows) and a `StateTracker` dataclass (`last_acted`, `run_on_startup`, `startup_pending`, `handle`). `Device` carries a tracker. `Manager` loads the Store in `async_start` before any subscription, seeds trackers from the stored map, gives the startup window only to devices built during start or reload (`async_reconcile(startup=True)`), saves with `async_delay_save` after a baseline change and with `async_save` in `async_stop`. `_data_to_save` writes `last_acted` only for devices with a baseline (D-07) and the sorted `published` ids (consumed by plan 01-05 T2). Unknown non-empty payloads log a warning with the device name and a repr cut at 40 characters plus an ellipsis; an empty payload logs at debug.
- **Task 2, serial runs and failures:** `ActionRunner` now owns the Scripts per device, runs every transition inside a per-device `asyncio.Lock` in an entry background task, logs `LOGGER.exception` with device and trigger names, and calls `report_failure` which creates the `action_failed_{device_id}` issue (non-fixable, ERROR, placeholders device, trigger, time to the second, error capped at 500). Success deletes the issue. Invalid stored actions at setup raise the same issue with trigger `setup`, leave that transition without a script and keep the other transition and the baseline working. `async_unload(device_id, remove_issue=...)` unloads scripts, drops the lock and optionally deletes the issue.
- **Task 3, broker proof:** `broker` marker registered, `mosquitto_port` fixture (skips without `mosquitto`, free port, temp config, poll for readiness, terminate at teardown), four tests with the paho client shipped with Home Assistant. All four observations from research Pattern 3 hold on Mosquitto 2.1.2, so the retained-versus-live baseline strategy is confirmed on a real broker.

## Task Commits

1. **Task 1 RED:** `a0fd002` test(01-04): add failing state tests
2. **Task 1 GREEN:** `0805363` feat(01-04): complete the decision function and persist the baseline
3. **Task 2 RED:** `c86e8ac` test(01-04): add failing failure-surfacing tests
4. **Task 2 GREEN:** `da51c63` feat(01-04): serialise runs and surface failures in Repairs
5. **Task 3:** `60b1036` test(01-04): pin retain flag semantics against a real broker

## Verification Results

- `uv run pytest -q`: 126 passed
- `uv run pytest tests/test_state.py tests/test_manager.py -k "retain or startup" -q`: 14 passed
- `uv run pytest tests/test_manager.py -k "edge or baseline" -q`: 10 passed
- `uv run pytest tests/test_manager.py -k issue -q`: 8 passed
- `uv run pytest -m broker -q`: 4 passed, none skipped (mosquitto 2.1.2 at /usr/bin/mosquitto); no stray mosquitto process left behind
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 23 files already formatted
- No dependency added: only a `markers` line in `pyproject.toml`; `uv.lock` untouched
- The `test(01-04)` commit precedes the `feat(01-04)` commit for both TDD tasks; no test drives edge semantics through the publish loopback

## TDD Gate Compliance

Task 1 and Task 2 have a `test(01-04)` commit before their `feat(01-04)` commit. No refactor commits. At Task 1 RED, 16 tests failed on behavior (missing `StateTracker`, no tracker attribute, no persistence, startup flag on runtime devices); the decision-table rows and several manager tests already passed because the plan 01-02 tracer implemented the table. At Task 2 RED, 9 of 10 new tests failed on behavior (no issue, no lock, no `remove_issue` parameter); only the empty-list test passed already.

## Deviations from Plan

### Auto-fixed Issues

None.

### Notes

**1. [Note] Runner signature.** The plan names `enqueue(device, transition, script)`. Implemented as `enqueue(device_id, device_name, trigger, script, run_variables)` so `runner.py` does not need the manager's `Device` class (import cycle). `async_build_script` gained a leading `device_id` argument so the runner can own the Scripts for `async_unload`.

**2. [Note] Extra tests beyond the plan list.** `test_retain_replay_after_reconnect_runs_nothing`, `test_startup_flag_applies_again_after_reload`, `test_baseline_saved_with_delay_after_change` (proves no per-message write), `test_baseline_store_records_published_ids`, `test_issue_deleted_when_runner_unloads_removed_device`, `test_tracker_without_flag_never_acts_on_retain`, `test_tracker_live_duplicate_keeps_baseline`.

**3. [Note] Issue test expectation about log records.** Home Assistant's own `Script` logs an ERROR line through our logger without a traceback (`Error executing script ... : boom`). The test therefore asserts on the record with `exc_info` (the runner's line) instead of the first ERROR record.

**4. [Note] pytest-socket.** The Home Assistant test plugin blocks sockets, so the `mosquitto_port` fixture requests the `socket_enabled` fixture. Without it, both the port probe and the client connection fail.

**5. [Note] Ledger and REQUIREMENTS.md.** The plan commit ledger was written to the worktree git dir without problems this time. REQUIREMENTS.md was not touched: STA-02 and further IDs of this plan are also declared by plan 01-02 and 01-06, so the shared-ID gate would block them, and the orchestrator owns shared tracking in this wave (`requirements-completed` is left empty on purpose).

**6. [Note] hassfest not re-run.** No manifest, translation or service change was made in this plan; `tests/test_translations.py` (parity, issue variables) still passes.

**Total deviations:** 0 auto-fixed, 6 notes. **Impact:** none on scope.

## Findings for Later Plans (observations, not fixes here)

- **Setup issue cleared by any success (plan 01-05):** the issue id is per device, so a successful OFF run also deletes a `setup` issue that belongs to an invalid ON sequence. This matches D-09 literally ("after the next successful run") but hides a still-broken transition. Reconfigure (plan 01-05 T2) rebuilds the Scripts; that path should clear or re-raise the setup issue explicitly rather than rely on a later run.
- **Removal wiring (plan 01-05):** `ActionRunner.async_unload(device_id, remove_issue=True)` exists and is tested; `Manager.async_reconcile` still only adds devices. The remove and change paths, the `published - current` orphan cleanup using `STORE_PUBLISHED`, and clearing `_stored_last_acted` entries for removed devices belong to 01-05.
- **Stored baseline of removed devices:** `_data_to_save` builds `last_acted` from running devices, so a removed device drops out of the Store on the next save. A device deleted while the entry is not loaded keeps its stale entry until the next save after start; harmless because ids are UUIDs.
- **Validation text in logs:** the setup-failure log line and the issue carry the capped Home Assistant validation message. Probatio messages name keys and positions, and may echo an offending value in rare cases; the same text is already shown to the admin in the config flow. Keep this in mind before reusing the path for broker-delivered sequences in Phase 3.
- **Unbounded queue:** the FIFO lock has no bound (T-01-11, accepted); the circuit breaker is STA-06 in Phase 2.
- **Broker test in CI:** the broker tests need `mosquitto` on PATH; add `sudo apt-get install -y mosquitto` to the CI test job in plan 01-06, otherwise they skip there silently.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-10 (capped issue text, names-only logging, canary test), T-01-12 (retained replays baseline-only, persisted baseline, opt-in flag, broker-pinned retain semantics) are mitigated as planned; T-01-11 is accepted as planned.

## Next Phase Readiness

Plan 01-05 can build on `Manager._published`/`STORE_PUBLISHED`, `Device.tracker`, `ActionRunner.async_unload(remove_issue=True)` and `report_failure`. No blockers.

## Self-Check: PASSED

- Files exist: `state.py`, `manager.py`, `runner.py`, `const.py`, `tests/test_state.py`, `tests/test_manager.py`, `tests/broker/__init__.py`, `tests/broker/conftest.py`, `tests/broker/test_retain_semantics.py` (verified before the SUMMARY commit)
- Commits `a0fd002`, `0805363`, `c86e8ac`, `da51c63`, `60b1036` exist on branch `worktree-agent-a708096f98d68eb28`
- Acceptance criteria re-run: full pytest (126 passed), the three `-k` selections, `-m broker`, ruff check and format all pass
