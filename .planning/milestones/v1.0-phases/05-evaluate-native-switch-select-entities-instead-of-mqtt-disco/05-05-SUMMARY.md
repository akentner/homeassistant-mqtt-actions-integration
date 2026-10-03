---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 05
subsystem: migration
tags: [native-entities, takeover, migration, adoption, mqtt-discovery, manager]

requires:
  - phase: 05-02
    provides: takeover.py (registry takeover, never publishes)
  - phase: 05-03
    provides: NativeState (instance, pending, devices) persisted in the Store, Manager.is_native
  - phase: 05-04
    provides: the native marker in documents, MirrorInfo.native, native mirror entities
provides:
  - DiscoveryPublisher.async_publish_migrate (live, not retained, QoS 1)
  - Manager._async_native_takeover, the pass at start (owner broadcast, registry takeover, retained clear, in that order)
  - the legacy-this-run fallback for a device that cannot be taken over yet (T-5-08)
  - the final is_native rule and the native marker in published documents
  - adoption rules between native and legacy devices (T-5-12)
affects: [05-06, 05-07, 05-09]

plan_head_before: ed829220f164ed9f76d40e988cb371076faa9be9
plan_head_after: 0b464cc6951cab7b0ad447dca1f503c9373464ad
actuals:
  tokens: 9000
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Pass at start under the held lock: after the reconcile, before any document, before the platform forward"
    - "Devices of one pass are taken over concurrently with asyncio.gather(return_exceptions=True); an exception defers the device, it never fails the start"
    - "Timeouts are read from the takeover module at call time, so tests monkeypatch the constants"
    - "Tests block the paho loopback of discovery topics through plugins.async_fire_mqtt_message to model a migrate payload core never heard"

key-files:
  created:
    - tests/test_native_start.py
  modified:
    - custom_components/mqtt_actions/discovery.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/entities.py

key-decisions:
  - "A pending owned device always gets the migrate payload, even without a legacy device of its own, because followers' core MQTT entities may be loaded and a bare clear would delete their registry entries"
  - "A device whose migrate payload could not be published is deferred untouched; a device whose retained clear could not be published stays pending and legacy for this run"
  - "is_native is False for any id in the legacy-this-run set, for a pending owned device, and True for a native mirror otherwise; a finished takeover does not add the id to the devices set, the instance flag covers it"
  - "Adoption: a native mirror joins the persisted devices set; a legacy mirror on a native instance joins pending and the entry is reloaded; the all-legacy case is unchanged"

patterns-established:
  - "mqtt_mock loops every publish back with the publish's own retain flag; a retained empty clear is therefore a retained replay for core"

requirements-completed: []

duration: about 75min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 05: Native Start Takeover Summary

**An upgraded owner now migrates its legacy core-MQTT entities automatically at setup, in the fixed broker order migrate payload, registry takeover, retained clear, and publishes documents with the native marker; followers take over their native mirrors silently, a device that cannot move yet stays on the legacy path until the next setup, and adoption never produces duplicate entities.**

## Performance

- **Duration:** about 75 min
- **Tasks:** 3 (1 tracer, 2 auto), 5 commits
- **Files:** 1 created, 3 modified

## Accomplishments

- `Manager._async_native_takeover` runs in `async_start` right after `_async_reconcile_locked(startup=True)` and before `_async_publish_owned()`, under the held lock, so the marker only ever follows the owner's own clear and the pass is done before the platform forward.
- Order for an owned device: live `{"migrate_discovery": true}` (retain False), `takeover.async_take_over`, then the retained empty clear; the stale test-topic subscription of the device ends and the id leaves `pending`; the Store is saved at the end of the pass.
- Only ids that are owned devices and pending are ever published for (T-5-02): other ids are dropped from `pending` before any publish (`test_the_pass_never_publishes_for_an_id_that_is_not_owned`).
- Followers take over every native mirror that has a core MQTT device (cheap `legacy_device` lookup), publish and clear nothing.
- A DEFERRED device, an unexpected exception from the takeover (one fixed warning, no registry or broker content) and a failed migrate publish all end in the legacy-this-run set: nothing moved, nothing cleared or marked, the id stays pending, legacy discovery and an unmarked document go out, the next setup retries. A deferred native mirror gets its test-topic subscription back so its legacy test buttons keep working.
- `async_publish_config` builds the document with `native=self.is_native(device_id)`.
- Adoption: a native mirror joins the persisted `devices` set and stays native and marked on a non-native instance; a legacy mirror adopted by a native instance joins `pending` and the entry is reloaded; both marks are rolled back with the rest when adding the subentry fails.
- 11 new tests in `tests/test_native_start.py` on real core MQTT discovery; full suite 1337 passed; Ruff check and format clean.

## Task Commits

1. **Task 1 RED:** `ecd8437` (test) - upgrade tracer, fresh install, non-owned id, second start
2. **Task 1 GREEN:** `7049053` (feat) - migrate publisher, the pass, final is_native rule, marker in documents
3. **Task 2:** `cd2c6ec` (test) - follower takeover, deferral of owner and mirror, error path (see TDD note)
4. **Task 3 RED:** `cbba367` (test) - adoption tests
5. **Task 3 GREEN:** `0b464cc` (feat) - adoption rules

## Decisions Made

- The pass never clears a retained discovery that was not preceded by the migrate payload for the same device; this is what the migrate-first rule of the phase protects (a clear on a loaded core entity deletes its registry entry).
- A finished takeover leaves the id out of `devices`: the instance flag already makes every non-pending owned device native, and adding every device id would grow the persisted set for no behavior.
- A live transition of a legacy mirror to native after the start (marker appears later) still only shows native entities next to ghost legacy entries until the next setup runs the follower takeover; the duplicate guard of `takeover.py` cleans the ghosts then. Not part of this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] A deferred native mirror had no test-topic subscription**
- **Found during:** Task 2
- **Issue:** a native mirror is built without the test-topic subscription (it has native buttons). When its takeover is deferred it runs as legacy and its legacy test buttons would publish to a topic nobody listens to.
- **Fix:** `_async_defer_takeover` subscribes the test topic for a deferred mirror.
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Commit:** 7049053

**2. [Rule 1 - Bug] The device model of a deferred mirror said "mirror of <owner>"**
- **Issue:** `device_info_for` read `device.mirror.native`, which stays set for a deferred mirror, so its legacy companion was renamed as a native one.
- **Fix:** it reads `manager.is_native(device_id)`.
- **Files modified:** custom_components/mqtt_actions/entities.py (outside the plan's `files_modified`)
- **Commit:** 7049053

### Plan assumptions that did not hold

- **`_native_pending` and `_native_devices` are not separate sets.** Plan 05-03 already persists `NativeState(instance, pending, devices)`; adding second copies would have diverged. They are read-only properties that return those very sets, so the plan's names and greps hold.
- **The mocked client does loop publishes back** (with the publish's own retain flag), contrary to the plan's harness note. The tracer helper still delivers discovery publishes live, because the retained loop-back of the empty clear is dropped by core's retained-replay handling. The deferral tests need the opposite, a migrate payload core never hears, so they patch `plugins.async_fire_mqtt_message` to drop discovery-topic loop-backs.

### TDD note

Task 1's GREEN step implemented the whole pass, including the follower half, the deferral and the error path that the Task 2 text describes, because they are one function. The four Task 2 tests were therefore green when written and there is no separate Task 2 `feat` commit. Mutation checks (disabling the mirror half; removing the deferred-mirror subscription) turned the follower and deferred-mirror tests red, so they pin real behavior. Task 3 has the usual RED then GREEN pair.

## Issues Encountered

- A first version of the deferred owner test failed because the loop-back had already delivered the migrate payload (see the harness note above).
- The known flake `test_delete_device_own_subscription_never_sees_state_clear` did not trip in the full runs.

## Verification

- `uv run pytest tests -q`: 1337 passed. `uv run ruff check .` and `uv run ruff format --check .` pass.
- `grep -c "_async_native_takeover" manager.py` 2, `grep -c "async_publish_migrate" discovery.py` 1, `grep -c "_legacy_this_run" manager.py` 4, `grep -c "_native_devices" manager.py` 5, `grep -c "async_schedule_reload" manager.py` 2.
- `test_an_upgrade_takes_over_the_legacy_entities_and_marks_the_document` asserts that the migrate publish (retain False) precedes the empty retained publish and that entity ids, registry ids, device id, area and user name survive.
- `test_a_deferred_takeover_leaves_the_device_legacy_for_this_run` asserts that no empty retained discovery payload was published and that a second setup completes the takeover.
- The `test(05-05)` commit precedes the `feat(05-05)` commit in Tasks 1 and 3.
- Tracer gate: the full suite and Ruff were re-run on the tracer commit, green, before Task 2.

## Requirements

MIG-01 was already complete (05-02) and this plan wires it in. MIG-02 stays open: the owner still has no rule that keeps the legacy path while an online peer is not native-capable, and nothing sets an instance native yet (plan 05-06). MIG-03 stays open: healing, ghost cleanup and the issues are plan 05-07. Nothing was marked complete here.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-5-02 is covered by `test_the_pass_never_publishes_for_an_id_that_is_not_owned`, T-5-08 by the two deferral tests and the error-path test, T-5-12 by the three adoption tests.

## Self-Check: PASSED

- `tests/test_native_start.py` and this file exist; commits ecd8437, 7049053, cd2c6ec, cbba367, 0b464cc exist; `commits: 5` measured from `plan_head_before`.
