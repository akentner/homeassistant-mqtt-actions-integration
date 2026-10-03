---
phase: 02-select-devices-and-reliable-execution
plan: 04
subsystem: reliability
tags: [home-assistant, circuit-breaker, repairs, store, loop-protection, tdd]

requires:
  - phase: 02-select-devices-and-reliable-execution
    provides: DeviceSpec with breaker_max_runs and breaker_window (plan 02-01), one Script per device (plan 02-02), test buttons that stay off the state path (plan 02-03)
provides:
  - CircuitBreaker, a pure sliding-window breaker with an injected clock (record, trip, reset, tripped)
  - Per-device breaker in the manager, counting only real changes that would enqueue a run
  - Pause on a trip: baseline still tracked, no actions, running and queued runs stopped, one warning, Repairs issue circuit_breaker_<device id>
  - Tripped state persisted as a per-device config hash (additive store key, no version bump), restored at start
  - Release paths (changed title or data, unload or reload) and cleanup on device deletion and hub removal
  - English and German Repairs text for circuit_breaker_tripped
affects: [02-05 option editor flow and README, phase 3 trust gate and multi-instance delete]

actuals:
  tokens: 13110
  tasks: 3
  commits: 6

plan_head_before: 360db659ac2b12f4b9f324b35274700c6aefbf61
plan_head_after: 53881b14c98bb0d0a1ae4e238ca248fc8129901c

tech-stack:
  added: []
  patterns:
    - "Pure breaker module without Home Assistant imports and an injectable clock; the manager hands out a bound _breaker_clock so a test can replace Manager.clock after construction"
    - "Persist a hash of the device fingerprint next to a runtime flag: a matching hash at start restores the state, a stale one releases it"
    - "Release is tied to lifecycle events (config change, user unload or reload) and never to Manager.async_stop, which a failed setup also calls"

key-files:
  created:
    - custom_components/mqtt_actions/breaker.py
    - tests/test_breaker.py
    - tests/test_manager_breaker.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/runner.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/__init__.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_translations.py
    - tests/test_runner_modes.py

key-decisions:
  - "Exactly max_runs runs per window are allowed and the next change trips and does not run; a stamp exactly one window old is pruned"
  - "A trip stops running and queued runs through Script.async_stop in a background task of the entry (A3); the Script stays usable"
  - "The tripped map stores sha256 of the same JSON fingerprint the manager uses to detect a changed subentry, so one definition of a change serves both"
  - "Manager.async_stop never releases; only async_unload_entry calls release_all_breakers before the final save, so a restart keeps the pause and a reload releases it"
  - "The trip warning and the issue carry only the device name and the two limits, never action data (T-02-18)"

patterns-established:
  - "Store flush in tests: use the freezer fixture to tick past STORE_SAVE_DELAY and then async_fire_time_changed; the store compares against loop time, which only the frozen clock moves"
  - "A test that feeds a device's own state topic from inside a running Script delivers the message with an empty contextvars.Context, as a broker would, or Home Assistant's recursion detection blocks the run"

requirements-completed: [STA-06]

coverage:
  - id: D1
    description: "A device whose actions toggle its own device is stopped after the configured number of runs (defaults 5 in 10 seconds), and the tripping change does not run"
    requirement: STA-06
    verification:
      - kind: unit
        ref: "tests/test_breaker.py#test_allows_max_runs_then_trips_on_the_next"
        status: pass
      - kind: unit
        ref: "tests/test_breaker.py#test_window_boundary_prunes_at_exactly_window"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_self_toggling_action_is_stopped"
        status: pass
    human_judgment: false
  - id: D2
    description: "A tripped device is paused: baseline tracking continues, no actions run, running and queued runs are stopped, one warning and one Repairs issue name the device and the limits"
    requirement: STA-06
    verification:
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_change_after_max_runs_trips_pauses_and_informs"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_paused_device_updates_baseline_without_running"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_trip_stops_running_and_queued_runs"
        status: pass
    human_judgment: false
  - id: D3
    description: "Only real changes that would enqueue a run count; test presses, triggers without actions, unknown payloads and retained messages do not, and the test button works while paused"
    requirement: STA-06
    verification:
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_uncounted_changes"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_test_press_is_not_counted_and_works_while_paused"
        status: pass
    human_judgment: false
  - id: D4
    description: "The tripped state survives a restart as a config hash and is released only by a real configuration change or an unload or reload; an unchanged save and a bare async_stop do not release"
    requirement: STA-06
    verification:
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_trip_is_persisted_as_config_hash"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_tripped_device_stays_paused_after_restart"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_config_change_releases_the_breaker"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_reload_releases_the_breaker"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_unchanged_save_does_not_release"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_stop_without_unload_keeps_the_tripped_state"
        status: pass
    human_judgment: false
  - id: D5
    description: "Device deletion and hub removal delete the breaker issue and forget the stored entry; orphan and malformed tripped store data never fails setup"
    requirement: STA-06
    verification:
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_delete_device_forgets_tripped_entry_and_deletes_issue"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_hub_removal_deletes_breaker_issues"
        status: pass
      - kind: integration
        ref: "tests/test_manager_breaker.py#test_malformed_tripped_store_is_dropped_and_setup_succeeds"
        status: pass
    human_judgment: false
  - id: D6
    description: "The circuit breaker Repairs issue has an English and German title and description that name the device and the limits and explain how to release the device"
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_issue_strings_use_expected_variables"
        status: pass
      - kind: other
        ref: "docker run ghcr.io/home-assistant/hassfest (exit 0, Invalid integrations: 0)"
        status: pass
    human_judgment: true
    rationale: "Whether the wording explains the cause and the release steps clearly to a user is a reading judgment no test asserts"

duration: 48min
completed: 2026-09-29
status: complete
---

# Phase 2 Plan 04: Circuit Breaker Summary

**Per-device sliding-window circuit breaker (5 runs in 10 seconds by default) that pauses a self-toggling device, stops its runs, raises a bilingual Repairs issue and keeps the pause across restarts as a config hash until the device is changed or the integration is reloaded**

## Performance

- **Duration:** 48 min
- **Started:** 2026-09-29T17:47:34Z
- **Completed:** 2026-09-29T18:35:48Z
- **Tasks:** 3 (1 tracer, 2 auto, all TDD)
- **Files modified:** 11 (3 created, 8 modified)

## Accomplishments

- STA-06: an action that changes its own device is stopped. The `test_self_toggling_action_is_stopped` test wires a service that delivers the opposite payload to the device's own state topic on every call, capped at 20 calls; it is called exactly `max_runs` times and the device ends paused with its issue.
- The pure `CircuitBreaker` allows exactly `max_runs` runs per window, prunes a stamp exactly one window old, and stays tripped when time passes. The manager counts only a real change that would enqueue a run, between the `can_run` check and `runner.enqueue`; test presses, triggers without actions, unknown payloads, retained messages and changes of a paused device never count.
- On a trip the device keeps tracking its baseline but runs nothing, the held and queued runs are stopped (`ActionRunner.async_stop_runs`), one warning names the device and both limits, and one non-fixable Repairs issue `circuit_breaker_<device id>` carries `device`, `max_runs`, `window`.
- The tripped state is persisted as `tripped[device id] = sha256(fingerprint)` in the existing store (additive key, no version bump, no timestamps). A matching hash restores the pause and recreates the issue at start; a stale hash or an orphan id is dropped; malformed store values are ignored.
- Release paths: a changed title or data (fresh breaker, issue deleted, entry forgotten), a user unload or reload (`release_all_breakers` before the final save). An unchanged save and a bare `Manager.async_stop` do not release. Device deletion and hub removal delete the issue.

## Task Commits

Each task was committed atomically, RED before GREEN:

1. **Task 1: Tracer, a self-toggling device is stopped by the breaker** - `cd2a13d` (test), `7e1a9ac` (feat)
2. **Task 2: Persist the tripped state and define the release paths** - `1dc9724` (test), `21ad3ef` (feat)
3. **Task 3: Repairs issue text in English and German** - `f154413` (test), `53881b1` (feat)

**Plan metadata:** the docs commit that follows this summary.

## Files Created/Modified

- `custom_components/mqtt_actions/breaker.py` - pure `CircuitBreaker(max_runs, window, clock)` with `record`, `trip`, `reset`
- `custom_components/mqtt_actions/manager.py` - breaker counting in `_on_message`, `_trip`, `_restore_tripped`, `release_all_breakers`, `signature_hash`, `_parse_tripped`, tripped persistence
- `custom_components/mqtt_actions/runner.py` - `async_stop_runs(device_id)`
- `custom_components/mqtt_actions/__init__.py` - unload releases all breakers before the final save
- `custom_components/mqtt_actions/const.py` - `ISSUE_CIRCUIT_BREAKER_PREFIX`, `STORE_TRIPPED`
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - `issues.circuit_breaker_tripped`
- `tests/test_breaker.py`, `tests/test_manager_breaker.py` - pure and integration coverage of every behavior
- `tests/test_translations.py` - required keys and variables for the new issue
- `tests/test_runner_modes.py` - the bounded-queue burst test raises its breaker limit

## Decisions Made

- The tripped hash reuses the manager's own subentry fingerprint (`_fingerprint`), so "what counts as a change" is defined once for reconcile and for release.
- `release_all_breakers` is a synchronous callback on the manager and runs before `async_stop` in `async_unload_entry`; `async_stop` stays release-free because a failed setup calls it too and a Home Assistant restart never unloads (D-17 against D-15).
- The trip stops runs in a background task of the entry rather than awaiting inside the message callback, so `_on_message` stays a synchronous `@callback`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing burst test hit the new default breaker**
- **Found during:** Task 1 (full-suite verify)
- **Issue:** `test_serial_queue_is_bounded_and_overflow_is_dropped_with_warning` fires 12 rapid changes to prove the queue bound of 10. With the default breaker (5 runs in 10 seconds) the device now trips after 5 runs, so the queue bound is never reached.
- **Fix:** the test's device sets `breaker_max_runs=100` (the flow's upper bound), with a comment; the queue-bound behavior it proves is unchanged.
- **Files modified:** tests/test_runner_modes.py
- **Verification:** full suite passes (321 tests after Task 1)
- **Committed in:** 7e1a9ac

**2. [Plan wording - RED scaffolds] Small production additions in the RED commits**
- **Found during:** Task 1 and Task 2 RED
- **Issue:** the plan says the RED step adds constants only. Without a `breaker.py` the pure tests can only fail on an import error, which is not a valid RED; without `signature_hash` every persistence test would fail on the import.
- **Fix:** the Task 1 RED commit carries a `breaker.py` whose `record` always returns True (so the pure tests fail on assertions); the Task 2 RED commit carries `STORE_TRIPPED` and the pure `signature_hash` helper the tests compute expectations with. No behavior under test exists in either.
- **Files modified:** custom_components/mqtt_actions/breaker.py, manager.py, const.py
- **Committed in:** cd2a13d, 1dc9724

---

**Total deviations:** 2 (1 Rule 1 test fix, 1 RED scaffolding note)
**Impact on plan:** No scope creep. The first is a direct consequence of the feature; the second keeps the RED evidence valid.

## TDD Gate Compliance

All three tasks have their `test(02-04)` commit before the `feat(02-04)` commit. RED failed on behavior: the pure tests on `assert True is False`, the manager tests on the missing `Device.breaker` or on counts and missing `tripped` keys. The self-toggling test failed at the cap (`20 < 20`), proving a missing breaker fails instead of hanging. The malformed-store cases were already green in RED (the value was not read yet) and stay as regression guards. Tracer gate: the verify command was re-run end to end after Task 1 and passed, so expansion continued.

## Issues Encountered

- **Held run in RED hung the suite.** The A3 test blocked on a run that never ends without a breaker; the test now settles with event-loop yields instead of `async_block_till_done(wait_background_tasks=True)` for the tripping change.
- **Home Assistant recursion detection.** Delivering the flip message synchronously from inside the running Script made HA refuse the nested run ("Disallowed recursion"), because the detection follows the context. A real broker delivers from its own task, so the test schedules the message with an empty `contextvars.Context`.
- **Delayed store save never fired.** `async_fire_time_changed` alone did not write the store, because the store pushes a write back by comparing against loop time, which real time does not advance. The `freezer` fixture ticking past `STORE_SAVE_DELAY` fixes it.

## Known Stubs

None.

## Threat Flags

None. The plan's threat model covers the new surface; T-02-13 to T-02-16 and T-02-18 are mitigated and each has a test, T-02-17 is accepted by design.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-05 (option editor flow and README) can rely on `breaker_max_runs` (1..100) and `breaker_window` (1..3600) reaching the breaker and on the release rule "change the device or reload the integration; saving without a change does not release", which the README must state.
- Phase 3 must decide how a paused device and test presses behave when several instances share a broker; the breaker is per instance and per process and its window is volatile by design.

## Self-Check: PASSED

- Created files exist: `custom_components/mqtt_actions/breaker.py`, `tests/test_breaker.py`, `tests/test_manager_breaker.py`
- Commits found: cd2a13d, 7e1a9ac, 1dc9724, 21ad3ef, f154413, 53881b1
- `uv run pytest tests -q`: 337 passed; `uv run ruff check .` and `uv run ruff format --check .` clean; hassfest via Docker exits 0

---
*Phase: 02-select-devices-and-reliable-execution*
*Completed: 2026-09-29*
