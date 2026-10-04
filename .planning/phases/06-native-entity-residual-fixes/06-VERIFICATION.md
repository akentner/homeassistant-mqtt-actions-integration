---
phase: 06-native-entity-residual-fixes
verified: 2026-10-04T13:10:00Z
status: passed
score: 11/11 must-haves verified
covered_files:
  - .planning/phases/06-native-entity-residual-fixes/06-01-PLAN.md
  - .planning/phases/06-native-entity-residual-fixes/06-01-SUMMARY.md
  - .planning/phases/06-native-entity-residual-fixes/06-02-PLAN.md
  - .planning/phases/06-native-entity-residual-fixes/06-02-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/takeover.py
  - tests/test_docs.py
  - tests/test_native_entities.py
  - tests/test_native_replay.py
  - tests/test_native_start.py
  - tests/test_takeover.py
covered_digest: "v2:sha256:5db3d18b01a908f74bf326e3dd9a66b62730d05c047b61a405328eacdf94d6b0"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "A replay that core MQTT delivers later than the 5 s one-shot catch (for example after a broker reconnect while running) is cleaned only at the next start (review WR-03)"
    addressed_in: "Phase 8"
    evidence: "Phase 8 SC2: 'After re-publishing retained legacy Discovery and restarting twice, no _2 duplicate entities exist on the instance, which proves MIG-05 outside the test harness.'"
---

# Phase 6: Native Entity Residual Fixes Verification Report

**Phase Goal:** A native mirror stays native after a restart even when its config document is near the size limit, and a retained legacy Discovery replay during startup never leaves a duplicate entity behind the takeover (review residuals IN-02 and IN-03).
**Verified:** 2026-10-04
**Status:** passed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria, then plan must-haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | A native mirror whose document is exactly `MAX_DOCUMENT_BYTES` is still native after a restart: not rebuilt as legacy, no test-topic subscription, no extra reload on the next document | VERIFIED | `tests/test_native_start.py:783` pads an unmarked document to exactly `MAX_DOCUMENT_BYTES` (asserted at line 779), restarts through the Store, then asserts `is_native`, `unsubscribe_test is None` and `schedule_reload.assert_not_called()`. Passes. Code: `NativeState.mirrors` (manager.py), `_build_mirror(... keep_native=parsed.device_id in self._native.mirrors)`, `_data_to_save` writes `native.mirrors`. The payload marker writer `with_native_marker` is deleted (no `git grep` hit in `custom_components` or `tests`). |
| SC2 | Replay of retained legacy Discovery between the registry move and the retained clear yields no `_2` duplicate; migrated entities keep registry ids and entity ids; a test delivers the replay at exactly that point | VERIFIED | `tests/test_native_replay.py::test_a_replay_right_after_the_move_is_removed_before_the_clear` (replay injected right after `takeover.async_take_over`), `test_a_replay_during_the_pass_leaves_no_duplicate[before_the_clear / after_the_clear]` (replay injected around `DiscoveryPublisher.async_clear_device`), and the mirror and finished-owner variants. Each first asserts the replay really created 3 legacy entities, then asserts none remain, replayed entity ids and states are gone, and `_assert_moved_and_native` / the explicit loop checks that registry id, platform and entity id of the moved entities are unchanged. Code: `takeover.remove_replay_twins` plus the call in `_async_native_takeover` (before the registry flush and the clear) and `_async_replay_catch` timer path. |
| SC3 | Both regression tests fail on v1.0.0 code and pass with the fixes; takeover, native-entity and cutover suites stay green | VERIFIED | Run by me, see "RED check" below: 3 IN-02 tests fail at `e335375` on unchanged v1.0.0 production code; all 4 original IN-03 tests (and the `34aec1c` test and the arm test, 6 of 6) fail on v1.0.0 production code with the `34aec1c` test files. Full suite: `uv run pytest tests/ -q` gives 1480 passed; `uv run ruff check .` all checks passed. |
| SC4 | README Limitations no longer lists the size-limit and boot-time replay residuals | VERIFIED | `git diff v1.0.0 HEAD -- README.md` removes exactly the two-line bullet ("close to the size limit ... can briefly create a duplicate entity"). `grep` of README for `size limit`, `replay`, `MAX_DOCUMENT` finds nothing in Limitations. Guarded by `tests/test_docs.py::test_readme_limitations_no_longer_list_the_native_residuals`. |
| 06-01-a | Flag persisted as a set of ids under the native Store key, not in the payload; payload stored as received | VERIFIED | `_mirror_info` now stores `parsed.payload` unchanged; `_remember_native_mirror` adds to `self._native.mirrors`. |
| 06-01-b | A 1.0.0 Store (marker only in payload, no `mirrors` key) still loads native and migrates into the set on the first save | VERIFIED | `test_native_mirror_set_takes_over_a_marker_only_store_of_the_previous_release` and the retained `test_a_cached_native_mirror_is_native_again_after_a_restart` pass; `_mirror_info` still reads the parsed marker. |
| 06-01-c | The flag is sticky and ends only with the mirror (tombstone, prune, adoption; rollback re-adds on failed adoption) | VERIFIED | `mirrors.discard` at `async_remove_mirror` and `_async_drop_mirror`, re-add before `async_restore_mirror` in the adoption rollback, `intersection_update(self.mirrors)` in `async_start`. Tests: tombstone, adoption, failed adoption, stale id never turns a later legacy mirror native. All pass. |
| 06-01-d | `mirrors` key written only when non-empty so exact-dict Store assertions of the cutover suite stay green; malformed or foreign ids never make a legacy mirror native | VERIFIED | `_data_to_save` gates on `if self._native.mirrors`; `_parse_native` validates with `is_valid_device_id` and caps at `MAX_MIRRORS`. `tests/test_cutover.py` is part of the green full run; parser tests pass. |
| 06-02-a | The catch removes a replayed entry only when it has a native twin under this entry and does not carry the identity; never a loaded native entity, foreign MQTT entity or entry without a twin; empties the replayed device only when nothing remains | VERIFIED | `takeover.remove_replay_twins` reads as specified; 5 `test_takeover.py::test_remove_replay_twins_*` tests cover removal, no twin, identity-carrying, foreign entity and no legacy device. All pass. |
| 06-02-b | Catch is registry-only (no publish, no migrate payload for a mirror); runs twice (after the move before the clear, and a timer-started task after the quiet period over every native owner and mirror) | VERIFIED | `takeover.py` gained no import and no publish; `_arm_replay_catch` in `async_start` after `_arm_cutover`; mirror test asserts no `migrate_discovery` publish and only empty payloads on the discovery topic. |
| 06-02-c | No wait or sleep under the lock or in the start; timer is cancelled when the manager stops | VERIFIED | `async_call_later` plus `async_create_background_task`; no sleep. The stop cancellation is not covered by a committed test (review IN-03). I ran a throwaway probe (not added to the repo): after arming the timer on a native instance, unloading the entry set `_cancel_replay_catch` to `None` and firing time 30 s ahead did not call `_async_replay_catch`. Passed. The callbacks also re-check `_running`. |

**Score:** 11/11 truths verified (0 present, behavior-unverified)

### RED check (success criterion 3)

Run in isolated git worktrees (removed afterwards); `custom_components` was confirmed to import from the worktree.

| Commit | Production code | Result |
|--------|-----------------|--------|
| `e335375` (test only; production equals v1.0.0, empty diff) | v1.0.0 | `test_a_native_mirror_at_the_size_limit_stays_native_after_a_restart`, `test_native_mirror_set_ignores_malformed_and_unlisted_ids`, `test_native_mirror_set_takes_over_a_marker_only_store_of_the_previous_release`: 3 failed |
| `5e22ba8` test files, v1.0.0 production overlaid | v1.0.0 | `test_native_replay.py`: 4 failed (duplicate `lamp_2`, `lamp_test_on_2` entities registered) |
| `34aec1c` test files, v1.0.0 production overlaid | v1.0.0 | `test_native_replay.py`: 6 failed, including `test_a_replay_right_after_the_move_is_removed_before_the_clear` |
| `cc02481` (06-01 lifecycle tests) | not re-run separately | Its three tests exercise the lifecycle of a set that does not exist in v1.0.0; recorded RED in 06-01-SUMMARY. The size-limit regression test itself was red on v1.0.0 as shown above. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/manager.py` | `NativeState.mirrors`, parse/save, lifecycle, replay catch timer | VERIFIED | Substantive and wired (`_build_mirror`, `_update_mirror`, `async_apply_mirror`, `_async_subscribe_mirror`, `async_start`, `async_stop`, `_async_native_takeover`) |
| `custom_components/mqtt_actions/takeover.py` | `remove_replay_twins`, `REPLAY_QUIET_SECONDS` | VERIFIED | Called from `Manager._remove_replay_twins` |
| `custom_components/mqtt_actions/document.py` | marker writer removed, strict reader kept | VERIFIED | `with_native_marker` gone; `parse_document` untouched |
| `custom_components/mqtt_actions/const.py` | `STORE_NATIVE` comment names `mirrors` | VERIFIED | |
| `tests/test_native_replay.py` | new IN-03 tests | VERIFIED | 5 tests, all pass |
| `tests/test_native_start.py`, `tests/test_native_entities.py`, `tests/test_takeover.py`, `tests/test_docs.py` | updated and new tests | VERIFIED | All pass |
| `README.md` | Limitations without the two residuals | VERIFIED | See SC4 |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| `_build_mirror` | `NativeState.mirrors` | WIRED | `keep_native=parsed.device_id in self._native.mirrors` |
| `_data_to_save` | Store key `native` | WIRED | writes `mirrors` only when non-empty |
| `_async_native_takeover` | `takeover.remove_replay_twins` | WIRED | via `_remove_replay_twins` for each DONE target, before flush and clear |
| `async_start` | replay timer | WIRED | `_arm_replay_catch` -> `_on_replay_catch_due` -> background `_async_replay_catch` under the lock; cancelled in `async_stop` |
| `tests/test_native_start.py` | manager | WIRED | Store round trip through `_restart` |

### Data-Flow Trace (Level 4)

Not applicable in the UI sense. The persisted set is read from and written to the real HA Store (`_parse_native` / `_data_to_save`) and the round trip is exercised by the size-limit test; the catch reads the real entity and device registries.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `uv run pytest tests/ -q` | 1480 passed in 101 s | PASS |
| Lint | `uv run ruff check .` | All checks passed | PASS |
| RED on v1.0.0 | worktree runs above | 3 and 4/6 failures as listed | PASS |
| Timer cancelled on stop | throwaway probe (not committed) | passed | PASS |

### Probe Execution

SKIPPED (no probe scripts are declared by the plans).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MIG-04 | 06-01 (also listed by 06-02) | A native mirror stays native after a restart near `MAX_DOCUMENT_BYTES` | SATISFIED | SC1, 06-01-a..d |
| MIG-05 | 06-02 | No duplicate entity when core MQTT replays retained legacy Discovery during startup; a test delivers the replay between registry move and clear | SATISFIED | SC2, 06-02-a..c |

PLAN frontmatter IDs are MIG-04 (06-01) and MIG-05, MIG-04 (06-02). REQUIREMENTS.md maps exactly MIG-04 and MIG-05 to Phase 6; there are no orphaned IDs. REQUIREMENTS.md already marks both Complete. UAT-02 (Phase 8) is the real-instance proof of MIG-05 and is out of scope here.

### Anti-Patterns Found

None. No TBD, FIXME, XXX, TODO or HACK in lines added since v1.0.0 across `custom_components`, `tests` and `README.md`.

### Review Findings (06-REVIEW.md, 3 open warnings)

None of them breaks a must-have or a success criterion, so none is reported as a gap.

- **WR-01** (removing a replayed mirror entity makes core MQTT publish an empty retained discovery onto the owner's topic): Plan 06-02 must-have 4 explicitly accepts this ("the only broker side effect is core MQTT's own empty retained discovery per removed loaded duplicate, which the session decision accepts"), and `takeover.py` documents it. The code publishes nothing itself; the test asserts no migrate payload and only empty payloads on the topic. The residual edge case (sticky native mirror re-pinned to a legacy owner) lies outside SC1 to SC4. Recommend a follow-up decision.
- **WR-02** (an identity-carrying or customized replayed entry is never resolved for a finished owned device): The edge case (user renamed or customized the replayed entity) is outside SC2, whose scenario (an unmodified replay with newer `created_at`) is covered and tested. The "left alone" half is pinned by a test. Recommend a log line or follow-up.
- **WR-03** (second catch is a single 5 s timer, not a real quiet period): SC2 and MIG-05 require the replay between the move and the clear, and the replay at start, to be handled; both are covered by tests. A replay arriving later (broker reconnect while running) is cleaned at the next start, which the test comment states. The README bullet that used to describe the window is gone, so this remaining limit is undocumented. Real-instance behavior is the subject of Phase 8 SC2 (UAT-02), so it is recorded as deferred. Recommend a short README note or reconnect re-arm as a follow-up.

Review infos IN-01 (stale docstring at `manager.py:1999` about the marker), IN-02 (partial failure skips the flush) and IN-03 (no committed test for the timer cancellation on stop; my probe confirms the behavior) are non-blocking cleanup.

### Human Verification Required

None for this phase. The real-instance proof of MIG-05 is already scheduled as Phase 8 UAT-02.

### Gaps Summary

No gaps. Both residuals (IN-02 and IN-03) are fixed in code, covered by regression tests that are red on the v1.0.0 production code and green now, the full suite and lint are clean, and the README no longer lists them. Three review warnings remain open as non-blocking follow-ups.

---

_Verified: 2026-10-04_
_Verifier: Claude (gsd-verifier)_
