---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 06
subsystem: migration
tags: [native-entities, cutover, presence, heartbeat, repairs, mixed-fleet]

requires:
  - phase: 05-03
    provides: NativeState (instance, pending, devices) persisted in the Store, Manager.is_native
  - phase: 05-04
    provides: NATIVE_KEY and NATIVE_VALUE, the additive marker of documents
  - phase: 05-05
    provides: the takeover pass at start that runs after the flag and the pending set are persisted
provides:
  - Heartbeat.native and the capability key in every published heartbeat
  - PresenceManager.blocking_peers, Roster.listening_seconds, SyncManager.online_instance_ids
  - Manager settle timer, on_roster_changed and _async_cutover_check (the one place that sets the instance flag)
  - Repairs hint native_cutover_waiting (en, de, troubleshooting entry)
  - test fixtures disable_native_cutover (autouse) and enable_native_cutover
affects: [05-07, 05-09]

plan_head_before: 7a90895cb7487ef0bbadc3e66ec47337fa99d13c
plan_head_after: f0527e03c50e50d15767b0ae1401541fba4a9a5d
actuals:
  tokens: 11500
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "A callback-only trigger (timer, roster refresh) starts a background task of the entry that takes the manager lock; the decision runs under the lock"
    - "Persist the flag, then schedule the reload; the reload runs the takeover pass, so the switch is idempotent across restarts"
    - "Test default is legacy: an autouse fixture sets the manager's CUTOVER_SETTLE_SECONDS to None, cutover tests opt in"

key-files:
  created:
    - tests/test_cutover.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/presence.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/troubleshooting.md
    - tests/conftest.py
    - tests/test_presence.py
    - tests/test_translations.py

key-decisions:
  - "The gate re-runs on every roster refresh (heartbeat, availability, tick) once the settle time passed; the hint is only rebuilt when the set of blocking peers changed, so heartbeats do not churn the issue registry"
  - "A peer announced online without a heartbeat is released by the 30 second heartbeat tick after the listening time reached the offline timeout; no extra timer"
  - "Devices that are already listed as native (adopted native mirrors) are not made pending at the flip"
  - "The hint is not deleted on a plain unload, like mqtt_discovery_disabled; it is deleted when the cutover proceeds and with the local state of the hub"

patterns-established:
  - "Live availability changes in tests are fired with retain=False: core MQTT drops a second retained replay of a topic it already handled"

requirements-completed: [MIG-02]

duration: about 60min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 06: Cutover Decision Summary

**An instance now switches itself to native entities exactly once, five seconds after start and again whenever its roster changes, but only while no online peer is a legacy instance; a v0.1.0 peer (no capability key in its heartbeat) or a silent announced-online peer keeps it on the 0.1.0 path and a Repairs warning names the peers it waits for.**

## Accomplishments

- Every published heartbeat carries `entities: native`; `parse_heartbeat` reads it into `Heartbeat.native`, a heartbeat without it counts as legacy. Version strings are never compared.
- `PresenceManager.blocking_peers()` returns the display names of online peers whose heartbeat lacks the capability, plus the 8-character ids of instances announced online that sent no heartbeat while this instance listened for less than the offline timeout. Offline peers, stale heartbeats and long-silent announced instances never block.
- `Manager` arms a settle timer at the end of `async_start` (only while the flag is unset and the value is not None), cancels it in `async_stop`, and `_async_cutover_check` (under the lock) sets the flag, makes every owned non-native device pending, saves the Store and schedules a reload only when something is pending. The reload runs the pass of plan 05-05 (D-12).
- `PresenceManager._refresh` and the heartbeat handler call `manager.on_roster_changed()`, so a peer's clean `offline` or a fresh capable heartbeat triggers the check at once, and the heartbeat tick releases time-based blockers.
- The hint issue `native_cutover_waiting` (warning, not fixable) lists at most 5 names, markdown escaped, with an ellipsis when more were cut. It is deleted when the cutover proceeds and in `async_remove_local_state`. Names are never logged.
- A device created while waiting stays legacy and is pending at the later flip; a device created after the flip is native at once (existing `is_native` rules, no new production code).
- 17 new test functions in `tests/test_cutover.py` (18 cases, one parametrized), full suite 1357 passed, Ruff check and format clean.

## Task Commits

1. **Task 1 RED:** `9e1b2cf` (test) - nine gate tests, the autouse and the enable fixture, the constants
2. **Task 1 GREEN:** `184ede1` (feat) - capability, blocking peers, settle timer, cutover check
3. **Task 2 RED:** `8b22bf6` (test) - hint, cap, deletion and device-creation tests, `NEW_ISSUES` entry
4. **Task 2 GREEN:** `f0527e0` (feat) - hint issue, en/de strings, troubleshooting entry

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] An existing test pinned the heartbeat to exactly five keys**
- **Found during:** Task 1
- **Issue:** `tests/test_presence.py::test_heartbeat_is_published_non_retained_with_qos_0` asserted the exact key set, which the additive capability key necessarily changes.
- **Fix:** the expected set now includes `entities` and the value is asserted. This is the only existing test changed (the plan's "no existing test changed" meant behavior; the pinned key set is a direct consequence of the plan).
- **Files modified:** tests/test_presence.py
- **Commit:** 184ede1

**2. [Rule 2 - Missing critical functionality] The hint would have churned on every heartbeat**
- **Found during:** Task 2 design
- **Issue:** the check re-runs on every roster refresh; deleting and creating the issue each time rebuilds the registry entry every 30 seconds per peer.
- **Fix:** the manager remembers the shown set of blocking peers and rebuilds the issue only when it changed (`test_the_hint_is_not_rebuilt_while_the_blockers_stay_the_same`).
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Commit:** f0527e0

### Plan assumptions adjusted

- **Constants added in the RED commit.** `CUTOVER_SETTLE_SECONDS`, `ISSUE_NATIVE_CUTOVER_WAITING` and `CUTOVER_HINT_MAX_NAMES` went into `const.py` with the failing tests, so the fixtures import and the tests fail on behavior rather than on a missing name. The autouse fixture used `raising=False` in the RED commit only (the manager had no such name yet) and the GREEN commit removed it.
- **Pending excludes natively listed devices.** The plan said "every owned device"; devices already in the persisted native `devices` set (adopted native mirrors) are skipped, since a takeover for them would only publish a pointless migrate and clear. For legacy devices the behavior is exactly the plan's.
- **The tracer's takeover assertions** run against real core MQTT discovery with the loop-back helper of plan 05-05; the "pending before the reload" state is asserted in `test_a_device_created_while_waiting_stays_legacy` with the reload mocked.

## Issues Encountered

- A retained `offline` after a retained `online` on the same availability topic is dropped by core's retained-replay handling in the test harness; the live-change tests fire it with `retain=False`, which is also what a broker delivers to a running subscriber.
- `test_delete_device_own_subscription_never_sees_state_clear` (known flake) did not trip in the full runs.

## Verification

- `uv run pytest tests -q`: 1357 passed. `uv run ruff check .` and `uv run ruff format --check .` pass.
- `grep -c "def blocking_peers" presence.py` 1, `grep -c "_async_cutover_check" manager.py` 3, `grep -c "def enable_native_cutover" tests/conftest.py` 1, `native_cutover_waiting` present in en.json, de.json and docs/troubleshooting.md.
- `test(05-06)` commits precede the `feat(05-06)` commits in both tasks.
- Tracer gate: the full suite and Ruff were re-run green on the tracer commit before Task 2.
- T-5-13: `test_the_cutover_runs_once` counts one reload and one migrate payload across further roster changes and time. T-5-14: `test_the_hint_names_the_blocking_peers` and `test_the_hint_is_capped`.

## Requirements

MIG-02 is complete: the owner keeps the legacy path while an online peer is not native-capable (this plan), and documents and heartbeats carry the additive unhashed marker (plans 05-04, 05-05 and this plan). MIG-03 stays open for plan 05-07 (healing, ghost cleanup and the issues for legacy devices only).

## Known Stubs

None.

## Threat Flags

None beyond the plan's register (T-5-04 accepted, T-5-13 and T-5-14 mitigated and tested).

## Self-Check: PASSED

- `tests/test_cutover.py` and this file exist; commits 9e1b2cf, 184ede1, 8b22bf6 and f0527e0 exist; `commits: 4` measured from `plan_head_before`.
