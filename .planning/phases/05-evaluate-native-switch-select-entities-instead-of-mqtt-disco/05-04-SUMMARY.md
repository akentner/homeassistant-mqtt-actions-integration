---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 04
subsystem: entities
tags: [native-entities, mirror, config-document, marker, availability]

requires:
  - phase: 05-02
    provides: takeover.py (registry takeover)
  - phase: 05-03
    provides: DeviceSwitch, DeviceSelect, DeviceTestButton, NativeDeviceEntity, device_info_for, Manager.is_native
provides:
  - NATIVE_KEY and NATIVE_VALUE, the unhashed additive marker of the config document (build_document native=, ParsedDocument.native)
  - MirrorInfo.native and Manager.is_native for mirrors, one-way per mirror
  - native mirror entities (switch, select, test buttons) directly under the entry, marked with the owner in the device model
  - mirror availability that follows the announced presence of the pinned owner
affects: [05-05, 05-06, 05-07, 05-09]

plan_head_before: 44563b0a85b173d96968cf26502cd2081a502b90
plan_head_after: 8ce4d2a3faa561ab1129212fed87dd7712ee7f7e
actuals:
  tokens: 7700
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Additive document key: written only when set, outside the hashed content, read strictly (exact value) and never a reason to reject"
    - "A stored mirror payload carries the native marker when native-ness was carried over, so no Store key is needed"
    - "Presence signal only when a native mirror follows the changed owner, so the roster signal contract of Phase 4 stays untouched"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/document.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/entities.py
    - custom_components/mqtt_actions/button.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/presence.py
    - tests/documents.py
    - tests/test_document.py
    - tests/test_native_entities.py

key-decisions:
  - "Marker is the top-level key `entities` with the exact string value `native`; any other value reads as not native and the document is still accepted"
  - "Native-ness of a mirror is one-way: replacing the record keeps native and rewrites the stored payload to carry the marker (with_native_marker)"
  - "The presence signal is sent only when an announced presence changed for the owner of a native mirror and the roster signal did not already fire"

patterns-established:
  - "Core drops a second retained message per subscription, so tests that change a retained topic twice send the later change live (retain=False)"

requirements-completed: []

duration: about 45min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 04: Native Mirrors Summary

**A foreign document that carries the unhashed `entities: native` marker now makes its mirror a native switch or select, with test buttons and mode select, directly under the entry and named after its owner; availability follows the owner's announced presence, native-ness is one-way, and a v0.1.0 reader ignores the marker by construction.**

## Performance

- **Duration:** about 45 min
- **Tasks:** 2 (1 tracer, 1 auto), both with a separate RED commit
- **Files:** 0 created, 9 modified

## Accomplishments

- `document.py`: `NATIVE_KEY = "entities"`, `NATIVE_VALUE = "native"`. `build_document(..., native=False)` writes the key only when set and outside the content, so hashes and every unmarked byte are unchanged; `parse_document` sets `ParsedDocument.native` with `document.get(NATIVE_KEY) == NATIVE_VALUE` and never rejects for the key. `SCHEMA_VERSION` stays 1.
- `Manager.is_native` is true for a mirror whose `MirrorInfo.native` is set. A native mirror subscribes no test topic. `device_info_for` names the owner: `Switch device (mirror of <owner name>)`; a legacy mirror keeps `(mirror)`.
- `button.py` now adds test buttons for native mirrors as well (no subentry); pressing runs the trigger locally behind the approval and the mode gate and publishes nothing.
- `NativeDeviceEntity` is available only while `sync.instance_status(owner) == "online"` for a mirror and listens to `SIGNAL_ROSTER_UPDATED`. `SyncManager` signals an announced presence change when a native mirror follows that owner.
- A mirror that was native stays native when a later document of the same owner lacks the marker (also after a restart); a competing owner's marker is the existing owner conflict and changes nothing; a marker that appears on unchanged content turns a legacy mirror native and refreshes its device model.
- Removal and rename needed no new code: the tests prove the native device, switch, buttons, mode select and stored mode go on a tombstone and a core MQTT device with its entities stays unchanged.
- 22 new tests; full suite 1325 passed; Ruff check and format clean.

## Task Commits

1. **Task 1 RED:** `92002ed` (test) - marker and native mirror tests
2. **Task 1 GREEN:** `d08bb70` (feat) - marker, MirrorInfo.native, mirror buttons, owner in the device model
3. **Task 2 RED:** `64bf921` (test) - availability and lifecycle tests
4. **Task 2 GREEN:** `8ce4d2a` (feat) - availability, one-way status, legacy to native follow

## Decisions Made

- The presence signal is conditional (an owner of a native mirror changed and the roster did not already signal). An unconditional signal, as the plan sketched, made `tests/test_multi_instance_ops.py::test_roster_marks_a_peer_offline_after_90_seconds` see three roster signals instead of one; the conditional version leaves every existing signal count untouched.
- `PresenceTracker.on_availability_changed` now returns whether the roster set changed (it was `None`), so `sync.py` can avoid a duplicate signal. It runs before the new signal rather than after, because the result is needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] A native mirror reverted to legacy after a restart**
- **Found during:** Task 2
- **Issue:** the stored payload is the received document text; after an unmarked update of a native mirror the stored text has no marker, so the mirror would restore as legacy (T-5-11 violated across a restart).
- **Fix:** when native-ness is carried over, `_mirror_info(keep_native=True)` stores `with_native_marker(payload)` (new pure helper in `document.py`; a payload that cannot take the marker is returned unchanged). No new Store key.
- **Files modified:** custom_components/mqtt_actions/document.py, manager.py
- **Commit:** 8ce4d2a

**2. [Rule 2 - Missing critical functionality] A marker on unchanged content never reached the mirror**
- **Found during:** Task 2
- **Issue:** `_async_ingest_locked` applied a document only when the content hash differed, so an owner that switches to native without changing content would never make its mirrors native.
- **Fix:** also apply when `parsed.native and not info.native`; the mirror then drops its test topic, refreshes the model of its companion device and notifies the platforms (`_follow_native_status`).
- **Files modified:** custom_components/mqtt_actions/sync.py, manager.py
- **Commit:** 8ce4d2a

**3. [Rule 3 - Blocking] The roster signal count test broke with an unconditional signal**
- See Decisions Made; fixed in the same commit by scoping the signal to owners of native mirrors.
- **Commit:** 8ce4d2a

### Scope notes

- `button.py` and `presence.py` are outside the plan's `files_modified`: the buttons of native mirrors are named in the plan's truth (test buttons appear), and `presence.py` carries the return value above.
- The test-topic subscription of a native mirror is skipped (MIG-03 consistency); not named in the plan.

## Issues Encountered

None. The known flake `test_delete_device_own_subscription_never_sees_state_clear` did not trip in the full runs.

## Verification

- `uv run pytest tests -q`: 1325 passed. `uv run ruff check .` and `uv run ruff format --check .` pass.
- `grep -c NATIVE_KEY document.py` 4, `grep -c "native: bool" manager.py` 3, `grep -c SIGNAL_ROSTER_UPDATED sync.py` 2.
- The `test(05-04)` commit precedes the `feat(05-04)` commit in both tasks.
- Tracer gate: `uv run pytest tests -q` re-run after the tracer commit, green, before Task 2.
- Human check (plan 05-09 UAT): a real v0.1.0 follower ignores the marker; rests on the parser contract that unknown keys are ignored (`test_a_marker_next_to_unknown_extra_keys_parses_unchanged`).

## Requirements

ENT-01 and ENT-02 were already marked complete by 05-03; this plan delivers their mirror half. MIG-02 stays open: the owner side (writing the marker, keeping the legacy path while an online peer is not native-capable, the heartbeat marker) is plans 05-05 and 05-06.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-5-03 (forged marker) and T-5-11 (revert) are covered by `test_a_marker_of_a_competing_owner_changes_nothing` and `test_an_unmarked_document_never_reverts_a_native_mirror`.

## Self-Check: PASSED

- All modified files exist; commits 92002ed, d08bb70, 64bf921, 8ce4d2a exist; `commits: 4` measured from `plan_head_before`.
