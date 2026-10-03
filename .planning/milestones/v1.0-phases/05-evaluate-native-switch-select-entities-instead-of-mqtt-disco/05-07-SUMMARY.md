---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 07
subsystem: migration
tags: [native-entities, cutover, follower, reload, multi-instance, test-harness]

requires:
  - phase: 05-04
    provides: the marker on documents, MirrorInfo.native, the sync branch that hands a marker on unchanged content to the manager
  - phase: 05-05
    provides: the takeover pass at start that moves the legacy entities of owned and native mirrored devices before the platform forward
  - phase: 05-06
    provides: the owner side of the cutover (settle timer, roster gate, instance flag, reload)
provides:
  - Manager._schedule_native_reload, a guarded single reload per manager lifetime
  - A running legacy mirror that turns native stays legacy for this run and reloads, so the takeover keeps every identity
  - InstanceFactory real_setup option and Instance.manager as a property of the entry runtime data
  - tests.documents.heartbeat_payload for peers of either generation
  - tests/test_cutover_instances.py, the two-instance acceptance scenarios of the cutover
affects: [05-08, 05-09]

plan_head_before: 88fbf8526f2bc039733f6be61a5636359f74c064
plan_head_after: a420c3ff09b925a15b743b659d1d9493651d4736
actuals:
  tokens: 7800
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "A legacy mirror that flips to native is parked in _legacy_this_run and the entry reloads; the takeover of the next setup moves the entities before any native entity can exist"
    - "The multi-instance factory patches the gateway and manager constructors once and dispatches by the hass they receive, so the real async_setup_entry and its reloads run on fake gateways"

key-files:
  created:
    - tests/test_cutover_instances.py
  modified:
    - custom_components/mqtt_actions/manager.py
    - tests/test_cutover.py
    - tests/fake_broker.py
    - tests/documents.py
    - tests/test_fake_broker.py

key-decisions:
  - "A flipped mirror is added to _legacy_this_run instead of becoming native live: the switch platform would otherwise register a native entity next to the legacy one, and the takeover would then delete the legacy registry entries (T-5-09) instead of moving them, which loses the entity ids"
  - "The reload flag lives on the manager, so the manager built by the reload starts clean and one reload per manager lifetime covers a burst of flips (T-5-15)"

patterns-established:
  - "Live document deliveries in follower tests use retain=False, like a broker delivers to a running subscriber"

requirements-completed: [MIG-02, ENT-01, ENT-02]

duration: about 45min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 07: Follower Flip and Multi-Instance Cutover Summary

**A running follower now follows its owner into native entities with one automatic reload and every identity kept, and two real Home Assistant instances on one broker prove the whole cutover, the legacy-peer block and the native toggle.**

## Accomplishments

- A legacy mirror that receives the pinned owner's first marked document, with unchanged or changed content, is recorded as native, parked on the legacy path for this run and the entry is reloaded once. The reload starts with the takeover pass of plan 05-05, so entity ids, registry ids, device id, area and name stay (D-09, D-12).
- `Manager._schedule_native_reload` is guarded by `_reload_scheduled`: a burst of flips, and a later marked change, call `async_schedule_reload` once (T-5-15). An unmarked document and a marked document of a competing owner schedule nothing and leave the mirror legacy.
- `InstanceFactory.__call__(..., real_setup=True)` runs the real `async_setup_entry` with platforms, with the fake gateway patched in per hass; `Instance.manager` is now a property of `entry.runtime_data`, so a reload shows the new manager and the same gateway. The default path is unchanged: all 165 multi-instance tests pass, the earlier ones untouched.
- `tests/test_cutover_instances.py` proves with two real instances: the owner switches (migrate live, then the empty retained discovery, document with the marker), the running follower reloads into native entities; an online v0.1.0-shaped peer keeps the owner legacy and its `offline` releases it at once; a toggle of the native follower switch publishes `ON` retained at QoS 1 and runs the actions exactly once on both instances, while an unknown payload runs nothing and changes no state.

## Task Commits

1. **Task 1 RED:** `58ec801` (test) - follower flip tests (same content, changed content, burst, no marker or competing owner)
2. **Task 1 GREEN:** `af6db0f` (feat) - flip handling and the guarded reload in `manager.py`
3. **Task 2 RED:** `a3bbd86` (test) - real-setup harness test and the cutover scenarios
4. **Task 2 GREEN:** `a420c3f` (feat) - `real_setup`, `heartbeat_payload`, `Instance.manager` property

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] A live flip would have created a native entity next to the legacy one**
- **Found during:** Task 1 RED run (the burst test log showed `switch.mqtt_actions` entities registered at the flip)
- **Issue:** `_follow_native_status` notified the platforms at once, so a native switch with the same unique id was registered under this integration while the legacy entities still existed. The takeover of the reload would then find a native entry for every legacy unique id and delete the legacy entries (T-5-09), so the entity ids would change, which breaks the plan's own truth that identities are kept.
- **Fix:** a mirror that was not native before is added to `_legacy_this_run` (so `is_native` stays False until the reload), the test-topic subscription stays, nothing is notified, and the reload is scheduled.
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Commit:** af6db0f

### Plan assumptions adjusted

- **No change to `sync.py`.** The plan asked for a new branch in `_async_ingest_locked`; plan 05-04 had already added `(parsed.native and not info.native)` to the existing branch (`parsed.native` appears there), and the competing-owner path is reached before it. The behavior is covered by the new tests, so no production edit was needed.
- **The reload call sits in `_follow_native_status`**, which `async_apply_mirror` calls from both its same-content and its update branch, instead of inline in `async_apply_mirror`; `grep -c _schedule_native_reload` prints 2.
- **The factory also patches `custom_components.mqtt_actions.Manager`**, next to the two `MqttGateway` patches. Without it the real setup would build every manager with the shared default store key, and the mocked storage is shared across the hass objects of one process, so two instances would overwrite each other's Store. The patched constructor passes the gateway and a per-instance store key, which are the existing test seams of `Manager`. The real `async_setup_entry` still runs.
- **The fallback of marking `mqtt` as set up** was applied up front for every real-setup hass (`hass.config.components.add("mqtt")`), since the manifest depends on it and core MQTT is replaced by the fake gateway. No other component was needed.
- **`FakeGateway.qos`** is a new list parallel to `published`, so the toggle test can assert QoS 1 without changing the tuple shape the existing tests unpack.
- **The test file for the heartbeat helper** is `test_cutover_instances.py` (`test_the_peer_helpers_build_the_two_generations`), as that is where the behavior list placed it.
- **Commit hygiene:** the Task 2 RED commit contained one line over 120 characters in a docstring; it was fixed in the GREEN commit (Ruff is not a commit hook here).

## Issues Encountered

- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` failed once in a full run under load and passed alone, the known flake.
- The migrate payload on the fake gateway is the compact JSON of Home Assistant's `json_dumps`, so the scenario tests compare against `{"migrate_discovery":true}` text rather than a spaced one.

## Verification

- `uv run pytest tests -q`: 1366 passed (the one flake passes on rerun). `uv run pytest -q -m multi_instance`: 165 passed. `uv run ruff check .` and `uv run ruff format --check .` pass.
- Mutation check: with the reload call removed, the two-instance cutover and toggle scenarios fail.
- Acceptance greps: `_schedule_native_reload` 2 in `manager.py`, `parsed.native` 1 in `sync.py`, `real_setup` 8 in `tests/fake_broker.py`, `pytest.mark.multi_instance` in `tests/test_cutover_instances.py`.
- The `test(05-07)` commit precedes the `feat(05-07)` commit in both tasks. The tracer gate (full suite and Ruff green on the Task 1 commit) was run before Task 2.
- Assumption A5 of the research (a live follower cutover on a real Home Assistant) is covered here with two real instances and the fake broker; the UAT of plan 05-09 still confirms it against a real broker.

## Requirements

MIG-02, ENT-01 and ENT-02 are complete and were already checked in `REQUIREMENTS.md` by earlier plans; this plan adds the follower side and the cross-instance proof and changes nothing about their status. MIG-03 stays open (healing, ghost cleanup and the issues for legacy devices only); it is not part of this plan's requirements.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register (T-5-15 mitigated and tested).

## Self-Check: PASSED

- `tests/test_cutover_instances.py` and this file exist; commits 58ec801, af6db0f, a3bbd86 and a420c3f exist; `commits: 4` measured from `plan_head_before`.
