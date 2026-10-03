---
phase: 02-select-devices-and-reliable-execution
plan: 02
subsystem: runtime
tags: [home-assistant, script, run-mode, queued, restart, repairs, tdd]

requires:
  - phase: 02-select-devices-and-reliable-execution
    provides: Device-level runner API and DeviceSpec.run_mode (plan 02-01)
provides:
  - One Home Assistant Script per device with choose dispatch on the hashed trigger_key
  - Run mode serial (script mode queued) and restart, missing run_mode means serial
  - SERIAL_QUEUE_LIMIT (10) as fixed queue bound with logged drops
  - Run-outcome handling that never lets a dropped or superseded run clear the failure issue
affects: [02-03 test buttons, 02-04 circuit breaker, 02-05 option editor flow]

actuals:
  tokens: 8200
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "One Script per device; triggers are choose branches whose template conditions compare the run variable trigger_key with the hex key"
    - "Native Script modes (queued, restart) instead of locks or hand-rolled cancellation"
    - "CancelledError is never caught in the runner: a cancelled run leaves no issue and no error log"
    - "Per-device enqueue generation counter guards the failure-issue clear"

key-files:
  created:
    - tests/test_runner_modes.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/runner.py
    - tests/test_manager.py

key-decisions:
  - "Run mode maps to Script mode one to one: serial is queued, restart is restart, both with max_runs=SERIAL_QUEUE_LIMIT and max_exceeded WARNING; the runner adds no second overflow log line"
  - "Only the hashed hex trigger key enters the generated choose conditions; option names and StateValues never enter a template of the Script (T-02-07)"
  - "A run clears the failure issue only when the Script returned a result and its generation equals the device's latest enqueue (T-02-06, A10)"
  - "The Manager and every runner caller stay untouched: the public runner surface from plan 02-01 is unchanged"

patterns-established:
  - "Held-service test helper (Held) that records start, end and cancellation, used to pin cancel, queue and unload semantics"
  - "Direct runner.enqueue with a patched Script.async_run to test run outcomes (None, result, superseded) without timing games"

requirements-completed: [DEV-06]

coverage:
  - id: D1
    description: "Restart cancels the running run across all triggers of a Switch or Select without an issue or a WARNING log; serial keeps first-in first-out order across triggers; a missing run_mode behaves as serial"
    requirement: DEV-06
    verification:
      - kind: integration
        ref: "tests/test_runner_modes.py#test_restart_mode_newer_change_cancels_running_run"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_restart_mode_cancels_across_select_options"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_serial_mode_keeps_order_across_select_options"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_missing_run_mode_behaves_as_serial"
        status: pass
    human_judgment: false
  - id: D2
    description: "A device owns exactly one Script covering all runnable triggers; an invalid trigger is reported as the setup issue and left out while the others keep running"
    requirement: DEV-06
    verification:
      - kind: integration
        ref: "tests/test_runner_modes.py#test_one_script_per_device"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_invalid_trigger_actions_are_left_out_others_still_run"
        status: pass
    human_judgment: false
  - id: D3
    description: "The serial queue is bounded at SERIAL_QUEUE_LIMIT; 12 rapid changes run 10 in order and drop 2 with a warning naming the device"
    requirement: DEV-06
    verification:
      - kind: integration
        ref: "tests/test_runner_modes.py#test_serial_queue_is_bounded_and_overflow_is_dropped_with_warning"
        status: pass
    human_judgment: false
  - id: D4
    description: "Dropped and superseded runs never clear an existing failure issue; the latest completed run with a result does"
    requirement: DEV-06
    verification:
      - kind: integration
        ref: "tests/test_runner_modes.py#test_dropped_run_does_not_clear_failure_issue"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_superseded_run_does_not_clear_failure_issue"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_completed_run_with_result_clears_failure_issue"
        status: pass
    human_judgment: false
  - id: D5
    description: "Unload and reconfigure stop running and queued runs quietly; a change of an action-less trigger does not cancel a running restart run (A5)"
    requirement: DEV-06
    verification:
      - kind: integration
        ref: "tests/test_runner_modes.py#test_unload_stops_running_and_queued_runs"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_reconfigure_stops_run_of_retired_script_without_issue"
        status: pass
      - kind: integration
        ref: "tests/test_runner_modes.py#test_restart_mode_action_less_trigger_change_does_not_cancel_running_run"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-09-29
plan_head_before: 6573ed1732b84cc6454372525088db1f02b5f0c4
plan_head_after: 231270a672e638b6387683a99002d7f26c7692da
commits: 4
status: complete
---

# Phase 2 Plan 2: Run Modes and Reliable Execution Summary

**Each device now runs all its actions through one Home Assistant Script (queued for serial, restart for restart) that dispatches on the hashed trigger key, giving native FIFO ordering, a fixed queue bound of 10 with logged drops, quiet restart cancellation across triggers, and a generation guard so dropped or superseded runs never clear a failure issue.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-09-29T17:32:27Z
- **Completed:** 2026-09-29T17:36:45Z (plus SUMMARY)
- **Tasks:** 2 (tracer, queue bound and run outcomes)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- The per-trigger Scripts and the per-device `asyncio.Lock` are gone. `async_build_device` validates every trigger's actions on its own, assembles one `choose` (one branch per runnable trigger, template condition `trigger_key == '<hex>'`), validates it once and builds `Script(script_mode="queued" | "restart", max_runs=SERIAL_QUEUE_LIMIT, max_exceeded="WARNING")`.
- Restart cancels the running run across triggers of the same device (Switch ON versus OFF, Select option A versus B); the cancelled run ends as a cancelled task with no Repairs issue and no WARNING-or-above record from the integration or the script helper.
- Serial (default, also when `run_mode` is missing from stored data) runs first-in first-out across triggers; 12 rapid alternating changes execute exactly 10 runs in order and the Script logs two "Maximum number of runs exceeded" warnings naming the device.
- `_async_run` clears the `action_failed_` issue only for a run that returned a result and is the latest enqueue of its device; dropped runs (result `None`) and superseded runs leave it alone. Failures are still reported every time.
- The public runner surface (`can_run`, `script_for`, `script_count`, `enqueue`, `async_unload`, `async_unload_all`, `report_failure`, `clear_issue`) is unchanged, so the Manager needed no edit.

## Task Commits

1. **Task 1: Tracer, one Script per device**
   - RED `53b5dd0` (test), GREEN `6b5a7a7` (feat)
2. **Task 2: Queue bound, dropped and superseded runs, unload semantics**
   - RED `5ef8219` (test), GREEN `231270a` (feat)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `custom_components/mqtt_actions/runner.py` - one Script per device, run mode selection, choose assembly, generation guard
- `custom_components/mqtt_actions/const.py` - `SERIAL_QUEUE_LIMIT = 10` (fixed, D-12)
- `tests/test_runner_modes.py` - 13 tests: restart, serial, missing run mode, invalid trigger, one Script, bound, dropped, superseded, completed, unload, A5, reconfigure
- `tests/test_manager.py` - one assertion: `script_count == 1` after reconfigure

## Decisions Made

- Serial maps to Script mode `queued` and restart to `restart` directly; the runner adds no overflow log of its own because the Script already logs the drop with the device name.
- The retired-Script check in `_async_run` compares the registered Script of the device (a rebuild or unload before the run starts turns the task into a no-op).
- The assembly step reports a rare invalid combined sequence as the `setup` issue and registers nothing, mirroring the per-trigger path; it cannot occur when every trigger validated on its own, but it keeps the runner from raising out of `async_build_device`.

## Deviations from Plan

None - plan executed exactly as written.

Notes within the plan's scope:

- The bound test (`test_serial_queue_is_bounded_...`) and several Task 2 unload, A5 and reconfigure tests passed at their RED commit because Task 1's GREEN already provides `queued` with `max_runs=SERIAL_QUEUE_LIMIT` and the retired-Script behavior; they pin the semantics on purpose. The two run-outcome tests (`test_dropped_run_...`, `test_superseded_run_...`) failed on assertion and drove the GREEN change.
- The Task 2 tests were written in one go but committed with Task 2 (imports trimmed for the Task 1 commit) so each RED commit contains only its own task's tests.
- Ruff `select = ["ALL"]` needed `# noqa: PLR0913` on `_async_run` again (argument count).

## TDD Gate Compliance

Both tasks have a `test(02-02)` commit before the `feat(02-02)` commit (`53b5dd0` before `6b5a7a7`, `5ef8219` before `231270a`). RED was confirmed intentional for both with `gsd_run check tdd-red-evidence` (verdict `RED_EVIDENCE_OK`, reason `target_test_failed`, class-level target `tests.test_runner_modes`): Task 1 failed on assertion (running run not cancelled, `script_count` 2 instead of 1), Task 2 on assertion (a dropped or superseded run deleted the issue). The tracer gate held: after the Task 1 GREEN commit the full suite (282 tests), `ruff check` and `ruff format --check` passed before expansion. No REFACTOR commit was needed.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None. T-02-05 (bounded queue), T-02-06 (no false success or failure from dropped, cancelled or superseded runs) and T-02-07 (only the hex key in generated templates) are implemented and covered by tests; no new endpoint, auth path or trust-boundary surface was added.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 02-03 (test buttons): `runner.enqueue` already takes run variables; a `test` variable can be added next to `trigger_key`, and test runs go through the same Script so they honor the run mode.
- Ready for 02-04 (circuit breaker): the Script is the one place to stop in-flight runs; `async_unload` shows the quiet-stop semantics, and `enqueue` is the single point where counted runs are known.
- Full suite: 289 passed; `ruff check` and `ruff format --check` clean.

## Self-Check: PASSED

- FOUND: tests/test_runner_modes.py, custom_components/mqtt_actions/runner.py, custom_components/mqtt_actions/const.py
- FOUND commits: 53b5dd0, 6b5a7a7, 5ef8219, 231270a
- `grep -c SERIAL_QUEUE_LIMIT` runner.py = 2, const.py = 1
- `uv run pytest tests -q`: 289 passed; ruff check and format check clean

---
*Phase: 02-select-devices-and-reliable-execution*
*Completed: 2026-09-29*
