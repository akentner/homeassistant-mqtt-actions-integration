---
phase: 03-trust-central-config-and-ownership
plan: 05
subsystem: sync
tags: [mqtt, follower, tombstone, prune, registry-cleanup, presence, retained-messages, tdd]

requires:
  - phase: 03-trust-central-config-and-ownership
    provides: "Follower mirrors, Manager.mirrors, owner pinning, FIFO ingest under Manager.lock (plan 03-04); instance presence and instance_status (plan 03-03); owner republish order documents, discovery, online (plan 03-02); FakeBroker tier (plan 03-01)"
provides:
  - "Manager.async_remove_mirror: releases subscriptions, Script state, Store entries (payload, baseline, tripped) and every per-device issue, then cleans leftover registry entries"
  - "Live-entity guarded registry cleanup: device and entity registry entries are removed only when no entity of the device is live in core"
  - "Follower tombstone branch: an empty live or retained config payload removes the mirror in arrival order behind pending ingests"
  - "Grace-window prune: a mirror is removed only when its document was not seen since the last (re)connect or setup, the window passed and its pinned owner is announced online"
  - "SyncManager seen set, presence reset on reconnect (on_reconnect), arm_prune, owner-online re-arm, timer cancelled on stop"
  - "Instance.stop, start and restart helpers in the fake broker tier"
affects: [03-06, 03-07, 04-operations]

requirements-completed: []

plan_head_before: be8bde7522776a9cd7bc4679f330a4c5c156f8e9
plan_head_after: 3807cbc62bfca5566f5a65ecc3048c819fce3c5d

actuals:
  tokens: 8800
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "A tombstone is queued as a background task exactly like a document, so a document and its tombstone for one device apply in arrival order under the FIFO manager lock"
    - "Removal is only ever driven by positive evidence: an empty payload, or an online owner plus a document unseen since the last reconnect; absence, a wiped broker and an unknown or offline owner never remove anything"
    - "A reconnect forgets presence as well as the seen set, because a wiped broker replays neither and an unknown owner must never look online"
    - "Registry cleanup never removes an entry whose entity is live: core would answer with an empty retained discovery and clear the device for every instance (Pitfall 10)"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/manager.py
    - tests/fake_broker.py
    - tests/test_sync_follower.py
    - tests/test_multi_instance.py

key-decisions:
  - "The seen set holds only ids of existing mirrors plus ids of mirrors created since the last reconnect (marked in the config callback when the id has a mirror, and by the ingest on creation), so it is bounded by MAX_MIRRORS and random ids on the broker cannot grow it; the plan's literal wording would mark every non-empty payload"
  - "Registry cleanup treats an entity as live when hass.states has a state for it that is not flagged restored; with a live entity the whole cleanup is skipped (planner's reading of D-09 and Pitfall 10, A1)"
  - "PRUNE_GRACE_SECONDS = 30.0 (A2); every owner transition to online re-arms the timer, so a flapping availability can only postpone a prune, never cause one"
  - "Approvals are not retained after a tombstone (A10): a forged tombstone forces re-approval, the owner's republish restores the mirror unapproved, documented for the README in plan 03-07"
  - "The reconnect hook runs in Manager._on_connection_status next to the republish task and clears both the seen set and the presence cache before the replay arrives"

patterns-established:
  - "Instance.restart() and the separate stop() and start() give multi-instance tests a way to be offline while the broker changes; the factory stops whichever manager the instance runs at the end"
  - "Time in multi-instance tests is advanced with the freezer fixture and async_fire_time_changed on any hass, since all instances share one event loop"

coverage:
  - id: D1
    description: "A live or retained empty payload removes the mirror at once: subscriptions released, Script state unloaded, Store payload, baseline and tripped hash forgotten, every per-device issue deleted; an unknown id and an owned device are untouched; a removed mirror can return as a fresh device"
    requirement: SYN-05
    verification:
      - kind: unit
        ref: "tests/test_sync_follower.py#test_live_tombstone_removes_the_mirror_at_once"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_retained_empty_payload_also_removes"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_tombstone_for_an_unknown_id_is_a_noop"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_tombstone_does_not_touch_owned_devices"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_removed_mirror_can_return"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_owner_delete_removes_the_mirror_everywhere"
        status: pass
    human_judgment: false
  - id: D2
    description: "Registry cleanup removes only genuine leftovers: entries without a live entity go, with live core discovery the registries stay and no empty discovery is published, and a missing MQTT entry or registry device is no error"
    requirement: SYN-05
    verification:
      - kind: unit
        ref: "tests/test_sync_follower.py#test_tombstone_removes_leftover_registry_entries"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_live_entities_keep_their_registry_entries"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_registry_cleanup_is_guarded"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_prune_cleans_registry_leftovers"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mirrors the owner deleted while the follower was away are pruned after the grace window, only with the owner online and the document unseen; an offline owner keeps them until it turns online, a seen mirror stays"
    requirement: SYN-05
    verification:
      - kind: integration
        ref: "tests/test_multi_instance.py#test_prune_removes_a_mirror_the_owner_deleted_while_the_follower_was_offline"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_prune_waits_for_the_owner_to_be_online"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_seen_mirror_is_not_pruned"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_prune_only_touches_mirrors"
        status: pass
    human_judgment: false
  - id: D4
    description: "Absence alone, a wiped broker and a reconnect never prune: seen set and presence are forgotten on reconnect, the timer is re-armed, and it is cancelled when the manager stops"
    requirement: SYN-05
    verification:
      - kind: integration
        ref: "tests/test_multi_instance.py#test_absence_alone_never_removes_a_mirror"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_wiped_broker_heals_without_pruning"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_reconnect_resets_seen_and_presence_and_rearms"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_prune_timer_is_cancelled_on_stop"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_absence_alone_never_removes_a_mirror_single_instance"
        status: pass
    human_judgment: false
  - id: D5
    description: "PRUNE_GRACE_SECONDS = 30, the live-entity definition (state present and not restored), the choice to build no approval retention after a tombstone, and the decision that every owner-online transition re-arms the timer are planner assumptions"
    verification: []
    human_judgment: true
    rationale: "A tunable and trust-policy choices (what a forged tombstone costs, how long to wait) are judgments no test can assert are the right ones"

duration: 25 min
completed: 2026-10-01
status: complete
---

# Phase 3 Plan 05: Tombstone and Prune Summary

**Followers remove a mirror on a live or retained tombstone, including genuine registry leftovers, and prune a deletion they missed only with positive evidence: the document unseen since the last reconnect and the pinned owner announced online; absence, a wiped broker and an offline owner never delete anything**

## Performance

- **Duration:** about 25 min
- **Completed:** 2026-10-01
- **Tasks:** 2 (Task 1 tracer, Task 2 auto, both TDD)
- **Files modified:** 6 (0 created, 6 modified)

## Accomplishments

- `Manager.async_remove_mirror(device_id)` pops the mirror (a no-op when absent), releases both subscriptions, unloads the Script state with `remove_issue=True`, deletes the breaker issue and every per-device issue, forgets the baseline and the tripped hash, cleans the registry and schedules a save. Nothing is published: the topics stay the owner's.
- The registry cleanup helper uses `async_get_device_by_identifier(("mqtt", "mqtt_actions_<id>"), mqtt_entry_id)` (never the deprecated `async_get_device`), does nothing without an MQTT entry or a registry device, and leaves everything alone while any entity of the device has a live (not restored) state. Otherwise it removes the device, which removes its entities. A mutation that disabled the guard made `test_live_entities_keep_their_registry_entries` fail.
- `SyncManager._on_config_message` queues a background task for an empty payload on a non-owned id, through the same FIFO lock as documents, so a document and its tombstone apply in arrival order. The removal logs one debug line with the capped id and never above debug for an unknown id. Empty payloads for owned ids still go to the owner branch only.
- Prune: `_seen` (ids with a document since the last reconnect or setup), `arm_prune()` (cancel then `async_call_later` with `PRUNE_GRACE_SECONDS`), `on_reconnect()` (clear seen and the presence cache, re-arm), `_async_prune()` under the manager lock (removes mirrors not seen whose pinned owner's `instance_status` is `online`, one info line with the count). The timer is armed at the end of `async_start`, on every reconnect and when an instance's availability turns online from none or offline; `async_stop` cancels it.
- `Manager._on_connection_status(True)` calls `sync.on_reconnect()` before starting the republish task. The fake broker's `reconnect()` runs the status callbacks before the replay, so the reset precedes the replayed documents.
- Fake broker tier: `Instance.stop()`, `start()` and `restart()` (new Manager on the same hass, entry, gateway and store key); the factory stops whichever manager the instance runs at close. New multi-instance tests cover owner delete, offline follower, offline owner, reconnect, wiped broker in both reconnect orders, timer cancellation and owned devices.

## Task Commits

1. **Task 1: Tracer, live tombstone removes the mirror and leftover registry entries** - `165ab24` (test, RED), `107be26` (feat, GREEN)
2. **Task 2: Grace-window prune gated by owner availability** - `7099a05` (test, RED), `3807cbc` (feat, GREEN)

**Plan metadata:** added by the docs commit that follows this file.

## TDD Gate Compliance

Both tasks have a `test(03-05)` commit before the `feat(03-05)` commit; no refactor commits. Tracer gate: Task 1's verify is automated only, so after the GREEN commit both test modules, the full suite, Ruff check and format were re-run end to end (697 passed) before Task 2 expanded. RED evidence (`check tdd-red-evidence` was not run):

- Task 1: seven tests failed on the planned behavior (the mirror was still in `manager.mirrors` after the empty payload, or the registry device still existed); `test_tombstone_for_an_unknown_id_is_a_noop` and `test_tombstone_does_not_touch_owned_devices` passed at RED because they pin existing behavior that the new branch must not break.
- Task 2: six tests failed on the planned behavior (mirror not pruned, `instance_status` not reset by a reconnect, no timer to cancel); the negative tests (`absence alone`, `seen mirror`, `only touches mirrors`) passed at RED for the same reason as above. After GREEN three mutations were run by hand and each made the intended tests fail: no presence reset, no owner-online gate, no seen reset on reconnect. The `PRUNE_GRACE_SECONDS` constant (no behavior) was added in the RED commit so the tests fail on behavior and not at collection.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Constant moved into the RED commit**
- **Found during:** Task 2 RED
- **Issue:** the new tests import `PRUNE_GRACE_SECONDS`; a missing name is an import error at collection, which is INVALID_RED, not a failing assertion for the behavior (same precedent as plans 03-04 deviation 2).
- **Fix:** the constant is added in the RED commit; it carries no behavior.
- **Files modified:** `custom_components/mqtt_actions/const.py`
- **Commit:** `7099a05`

**2. [Rule 2 - Missing critical] The seen set is bounded**
- **Found during:** Task 2 design
- **Issue:** the plan marks every non-empty payload on a non-owned id as seen, which lets random ids on the broker grow the set without bound (T-03-12 class of risk).
- **Fix:** the config callback marks an id seen only when it already has a mirror, and the ingest marks it when it creates one; a tombstone and a prune discard the id. A mirror's document is therefore always marked (valid or not) and the set stays within the mirror ids plus recent creations. Behavior for the plan's scenarios is unchanged.
- **Files modified:** `custom_components/mqtt_actions/sync.py`
- **Commit:** `3807cbc`

**3. [Rule 3 - Blocking] The fake broker factory stopped a replaced manager twice**
- **Found during:** Task 2 RED (the plan's `Instance.restart()` swaps the manager)
- **Issue:** the factory registered `manager.async_stop` of the first manager at creation, so a restarted instance would be stopped through the old manager and the new one would never stop.
- **Fix:** the factory registers `Instance.stop`, which stops whichever manager the instance currently runs unless it already stopped. `stop()` and `start()` exist separately because tests need the follower to be offline while the owner deletes.
- **Files modified:** `tests/fake_broker.py`
- **Commit:** `7099a05`

---

**Total deviations:** 3 (2 Rule 3, 1 Rule 2). **Impact on plan:** no scope change, no existing assertion weakened.

## Issues Encountered

- Registry leftovers cannot be exercised on the fake broker tier because `FakeGateway.mqtt_entry_id()` returns None, so the cleanup there is a guarded no-op. The leftover and live-entity behavior is covered at the `mqtt_mock` tier with real core registries, including a prune test (`test_prune_cleans_registry_leftovers`).
- The retained-replay semantic that makes the prune safe (an online owner's `online` is replayed after its documents on a reconnect) rests on the owner's publish order from plan 03-02; the fake broker pins replay and live delivery, the wiped-broker tests cover both reconnect orders.

## Known Stubs

None.

## Threat Flags

None. The surfaces are those of the plan's threat model: broker to tombstone handler (T-03-20, accepted: a forged tombstone removes mirrors and approvals, the owner republishes and the mirror returns unapproved; the broker ACL is the control, to be documented in plan 03-07), availability to prune decision (T-03-21, mitigated and covered), follower to core registries (T-03-22, mitigated by the live-entity guard and covered), and stale retained online after an owner crash (T-03-23, accepted: the combination means the owner removed the device). T-03-SC: no package was installed.

## Next Phase Readiness

- Plan 03-06 (approval) owns its approval Store key and must forget it where `async_remove_mirror` forgets the other per-mirror entries; the A10 default is that approvals do not outlive a tombstone. The removal path to extend is `Manager.async_remove_mirror`.
- Plan 03-07 documents the accepted risk of a forged tombstone (T-03-20), the broker ACL as the control, the no-Last-Will limitation behind T-03-23 and that orphaned devices stay after a hub removal with keep because their owner is offline.
- Needs user confirmation at review: `PRUNE_GRACE_SECONDS = 30.0`, the live-entity rule for registry cleanup and the decision not to retain approvals after a tombstone.
- Requirement bookkeeping: SYN-05 is declared by this plan and by plan 03-07 (README and ACL documentation); it is not ticked here, the phase verification does it.

## Self-Check: PASSED

- Modified files exist: `custom_components/mqtt_actions/const.py`, `sync.py`, `manager.py`, `tests/fake_broker.py`, `tests/test_sync_follower.py`, `tests/test_multi_instance.py` (FOUND)
- Commits exist: `165ab24`, `107be26`, `7099a05`, `3807cbc` (FOUND); each `test(03-05)` commit precedes its `feat(03-05)` commit
- Acceptance: `grep -c async_get_device_by_identifier` on `manager.py` prints 1 and non-comment `async_get_device(` prints 0; `PRUNE_GRACE_SECONDS` occurs in `const.py` (1) and `sync.py` (2); `test_live_entities_keep_their_registry_entries` asserts no empty payload on the discovery topic; `test_wiped_broker_heals_without_pruning` reconnects both instances and asserts the mirror after two windows
- `uv run pytest -q` 708 passed; `uv run ruff check .` and `uv run ruff format --check .` clean
