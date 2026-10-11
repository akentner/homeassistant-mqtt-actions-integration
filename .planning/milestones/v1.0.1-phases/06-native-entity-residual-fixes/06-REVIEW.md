---
phase: 06-native-entity-residual-fixes
reviewed: 2026-10-04T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/takeover.py
  - README.md
  - tests/test_docs.py
  - tests/test_native_entities.py
  - tests/test_native_replay.py
  - tests/test_native_start.py
  - tests/test_takeover.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-10-04
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the persisted native mirror id set (IN-02) and the replay duplicate catch (IN-03). The 149 tests in the touched
suites pass and `ruff check` is clean.

The mirror set lifecycle holds up. Ids are added only after a mirror is registered. They are discarded on tombstone,
prune and adoption. The adoption rollback re-adds the id before it re-ingests the payload. A start-time
`intersection_update` removes ids that did not restore. The parser validates ids and caps the set. No path was found
where a stale id turns a later legacy mirror native.

The replay catch is correct for its main scenario. The twin guard, the legacy-device identity check and the
device-removal condition are sound. The timer is cancelled in `async_stop`, and the callback re-checks `_running` under
the lock. One path was not verified: a catch task that was already created before `async_stop` runs. It re-checks
`_running` under the lock, but no test covers it.

The findings below concern the limits of the catch, not its main path. No BLOCKER was found.

## Warnings

### WR-01: Removing a replayed mirror entity makes core MQTT publish a retained clear on a topic another instance owns

**File:** `custom_components/mqtt_actions/takeover.py:188-221`, `custom_components/mqtt_actions/manager.py:833-851`

**Issue:** `entity_registry.async_remove(legacy.entity_id)` on a loaded MQTT entity triggers core's
`async_removed_from_registry`, which calls `async_remove_discovery_payload`. That publishes `None` retained to the
entity's discovery topic. This is verified in the installed core, `mqtt/entity.py:1211-1220` and `758-767`.

For an owned device that is harmless, because the clear is intended anyway. For a native mirror, the follower now writes
a retained empty payload onto the owner's discovery topic. The docstring and the manager comment say "nothing is
published" and cite T-5-02. The code in this repo publishes nothing, but the side effect is real.

Combined with the sticky native flag (D-03, T-5-11), a mirror stays native even after a re-pin to an owner that is
legacy. A native follower can then wipe the live discovery of a legacy owner. The owner's discovery healing (DSC-03)
would republish it, and the next replay would repeat the cycle once per start.

The cutover gate protects the normal flow. Nothing in `_native_device_ids()` or `remove_replay_twins` checks that the
mirror's pinned owner is native.

**Fix:** For mirrors, run the catch only when the pinned owner's last-known heartbeat is native. Alternatively, accept
the behaviour and state it. Correct the docstrings to say that core MQTT clears the retained discovery topic of a
removed entity. Add a test with a mirror that is native by flag but whose pinned owner is legacy.

### WR-02: An older or customized replayed entry is never resolved for a finished owned device

**File:** `custom_components/mqtt_actions/takeover.py:212-214`, `custom_components/mqtt_actions/manager.py:960`

**Issue:** `remove_replay_twins` skips a legacy entry when `_carries_the_identity(legacy, twin)` is true. For example,
the user renamed the replayed `_2` entity, or `created_at` ties (`<=` favours the legacy entry). The docstring says "an
older or customized legacy entry is left to the takeover pass".

For an owned device that pass runs only while the device is pending: `owned = sorted(self._native_pending &
self.devices.keys())`. A finished owned device never gets it again. The duplicate then stays forever with no log line.
Native mirrors do get the pass at each start, which makes the behaviour inconsistent. The tests pin only the "left
alone" half (`test_remove_replay_twins_leaves_an_older_entry_that_carries_the_identity_to_the_takeover`), not that
something resolves it afterwards.

**Fix:** Either log a warning when candidates are skipped so the user can act on it, or let the catch remove the twin
when the legacy entry carries the identity, using the same resolution as `async_take_over`. In `async_take_over` the
legacy entry stays when it is the identity. It should also only remove a twin that is not loaded.

### WR-03: The second catch is a one-shot timer fixed 5 s after start, not a quiet period

**File:** `custom_components/mqtt_actions/manager.py:853-863`, `custom_components/mqtt_actions/takeover.py:39-41`

**Issue:** The docs and the constant call this a quiet period, but nothing observes quiet. A single
`async_call_later(5.0)` is armed at the end of `async_start`. A replay that core MQTT delivers later is not caught until
the next start. Core processes retained discovery at its own pace, and a broker reconnect re-delivers retained messages
while running.

This matters most for native mirrors, because the follower never clears the topic. If the owner is offline or its clear
is unconfirmed, the retained discovery stays on the broker. Every reconnect then recreates the duplicates. The test
`..._cleaned_at_the_next_start` states this limit in a comment ("A running instance has no catch that listens").

The README Limitations bullet was removed entirely, so this remaining window is now undocumented.

**Fix:** Re-arm the catch (debounced) on MQTT reconnect, using the existing `gateway.async_subscribe_connection_status`
hook. Alternatively, re-arm it when a new `mqtt`-platform entity appears for a native device id. If the heuristic stays,
rename the constant and comments to "delay", and keep a short README note that a replay later than the delay is cleaned
at the next start.

## Info

### IN-01: Stale docstring still says the stored mirror record carries the marker

**File:** `custom_components/mqtt_actions/manager.py:1999`

**Issue:** "The final save of the stop persists the mirror records, marker included." The marker is no longer written.
`with_native_marker` is gone, and the flag lives in the `native.mirrors` Store set.

**Fix:** Change it to "persists the mirror records and the set of native mirrors".

### IN-02: A partial failure in the second catch loses the flush

**File:** `custom_components/mqtt_actions/takeover.py:188-221`, `custom_components/mqtt_actions/manager.py:870-881`

**Issue:** `remove_replay_twins` returns a count only on a clean pass. If it raises after it already removed some
entries, `_remove_replay_twins` swallows the error and contributes 0. `_async_replay_catch` then skips
`async_flush_registries`, so a partial removal is left to HA's scheduled save. The impact is small. The registry loses
nothing meaningful on a crash, and the next start re-checks.

**Fix:** Count removals in the manager by comparing the registry before and after. Alternatively, flush whenever the
catch ran for any device and did not return early.

### IN-03: No test pins the cancellation of the replay timer on stop

**File:** `tests/test_native_replay.py:182-199`

**Issue:** `_cancel_replay_catch` is asserted only for "None on a legacy instance, set on a native one". Nothing
asserts that `async_stop` cancels a pending timer, or that a background task created just before the stop returns
without touching the registry. The stop path (`manager.py:1149-1151`) and the `_running` re-checks (`manager.py:869`,
`manager.py:875`) are therefore unguarded.

**Fix:** Add a test that stops the entry before the quiet period. Fire time past `REPLAY_QUIET_SECONDS` and assert that
no registry change happened and that the timer is `None`.

---

_Reviewed: 2026-10-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
