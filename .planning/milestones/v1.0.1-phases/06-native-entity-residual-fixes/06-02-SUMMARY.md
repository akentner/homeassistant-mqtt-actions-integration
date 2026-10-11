---
phase: 06-native-entity-residual-fixes
plan: 02
subsystem: sync
tags: [home-assistant, mqtt, discovery, registry, native-entities, tdd]

requires:
  - phase: 06-native-entity-residual-fixes
    provides: the persisted native flag of a mirror (plan 06-01), so every native mirror is known at start
  - phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
    provides: the registry takeover (takeover.py) and the native owner and follower passes in the manager
provides:
  - takeover.remove_replay_twins, a registry-only catch for the duplicates a replayed legacy Discovery creates
  - REPLAY_QUIET_SECONDS, the quiet period of the second catch
  - the first catch inside the takeover pass (after the move, before the registry flush and the retained clear)
  - the timer-started second catch over every native owned device and native mirror on every start
  - README Limitations without the two accepted residuals, with a docs guard
affects: [phase-8-uat, native-entity-residual-fixes]

actuals:
  tokens: 8700
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Quiet period as an async_call_later timer that starts an entry background task, never a sleep"
    - "Replay delivered in tests by wrapping the publisher clear or takeover.async_take_over, with retain=False"

key-files:
  created:
    - tests/test_native_replay.py
  modified:
    - custom_components/mqtt_actions/takeover.py
    - custom_components/mqtt_actions/manager.py
    - tests/test_native_start.py
    - tests/test_takeover.py
    - tests/test_docs.py
    - README.md

key-decisions:
  - "The catch is registry logic only: no import and no publish in takeover.py, and no migrate payload for a mirror (T-06-07)"
  - "The quiet period is an async_call_later timer (5.0 s, equal to core's discovery cooldown) that starts a background task, because a sleeping task hangs the freezer fixture"
  - "A replayed entry is removed only with a native twin under this entry, and only when the twin carries the identity; the twin is never removed"
  - "The emptied replayed MQTT device is removed only when nothing at all remains on it, because removing a device removes the entries on it"

patterns-established:
  - "remove_replay_twins reuses legacy_device, _legacy_entries and _carries_the_identity of the takeover"
  - "_native_device_ids is the one definition of which devices the second catch covers"

requirements-completed: [MIG-05, MIG-04]

coverage:
  - id: D1
    description: "A retained legacy Discovery replay that lands after the registry move, before or after the retained clear, leaves no mqtt entry of the device id once the quiet period passed; the migrated entries keep registry id, platform, entity id and state"
    requirement: MIG-05
    verification:
      - kind: unit
        ref: "tests/test_native_replay.py#test_a_replay_during_the_pass_leaves_no_duplicate"
        status: pass
    human_judgment: false
  - id: D2
    description: "The first catch removes a replay that lands right after the move before the retained clear is published"
    requirement: MIG-05
    verification:
      - kind: unit
        ref: "tests/test_native_replay.py#test_a_replay_right_after_the_move_is_removed_before_the_clear"
        status: pass
    human_judgment: false
  - id: D3
    description: "A native mirror and a finished native owner (two restarts) are cleaned by the registry alone; no migrate payload is published and only empty payloads appear on the discovery topic"
    requirement: MIG-05
    verification:
      - kind: unit
        ref: "tests/test_native_replay.py#test_a_replay_after_the_takeover_of_a_native_mirror_leaves_no_duplicate_and_no_publish"
        status: pass
      - kind: unit
        ref: "tests/test_native_replay.py#test_a_replay_before_a_restart_of_a_finished_native_owner_is_cleaned_at_the_next_start"
        status: pass
    human_judgment: false
  - id: D4
    description: "The helper removes only a replayed entry with a native twin that does not carry the identity, never a foreign MQTT entity, never publishes, and keeps a device that still has entries"
    requirement: MIG-05
    verification:
      - kind: unit
        ref: "tests/test_takeover.py#test_remove_replay_twins_removes_the_loaded_duplicates_and_the_emptied_device"
        status: pass
      - kind: unit
        ref: "tests/test_takeover.py#test_remove_replay_twins_leaves_an_entry_without_a_native_twin_and_keeps_the_device"
        status: pass
      - kind: unit
        ref: "tests/test_takeover.py#test_remove_replay_twins_leaves_an_older_entry_that_carries_the_identity_to_the_takeover"
        status: pass
      - kind: unit
        ref: "tests/test_takeover.py#test_remove_replay_twins_never_touches_a_foreign_mqtt_entity"
        status: pass
      - kind: unit
        ref: "tests/test_takeover.py#test_remove_replay_twins_without_a_legacy_device_does_nothing_and_publishes_nothing"
        status: pass
    human_judgment: false
  - id: D5
    description: "The catch timer is armed only for an instance with a native device"
    requirement: MIG-05
    verification:
      - kind: unit
        ref: "tests/test_native_replay.py#test_the_replay_catch_is_armed_only_for_an_instance_with_a_native_device"
        status: pass
    human_judgment: false
  - id: D6
    description: "The README Limitations section no longer lists the near-limit native mirror and the boot-time replay residuals"
    requirement: MIG-04
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_limitations_no_longer_list_the_native_residuals"
        status: pass
    human_judgment: false

duration: 13 min
completed: 2026-10-04
status: complete
plan_head_before: dc66fe117edace9b2bc90afb49168924ba172f07
plan_head_after: 4883f70f7f4763b3cd4956333561f8c759e5ffd2
commits: 5
---

# Phase 6 Plan 02: Duplicate catch for a replayed legacy Discovery Summary

**A registry-only catch removes the duplicate `mqtt` entities that a replayed retained legacy Discovery creates after the native takeover, once right after the registry move and again from a 5 s `async_call_later` timer for every native owner and mirror on every start; the migrated entities keep their registry ids, entity ids and state, and the README no longer lists the two residuals.**

## Performance

- **Duration:** about 13 min (start time was not captured at the very start of the run, so it is estimated from the end of plan 06-01)
- **Completed:** 2026-10-04T10:46Z
- **Tasks:** 3
- **Files modified:** 7 (one new)

## Accomplishments

- IN-03 / MIG-05 fixed. `takeover.remove_replay_twins(hass, entry_id, device_id, *, mqtt_entry_id)` returns 0 without a core MQTT device for the id; otherwise it removes each legacy entry that has a native twin under this config entry and does not carry the identity (`_carries_the_identity`), then the emptied replayed MQTT device. It never removes the twin, never publishes and `takeover.py` gained no import.
- Catch 1 runs in `_async_native_takeover` for every DONE target (owners and mirrors) before the registry flush, so the move and the removal are on disk before the retained clear goes out.
- Catch 2: `_arm_replay_catch` (after `_arm_cutover` in `async_start`) sets an `async_call_later` timer of `REPLAY_QUIET_SECONDS`; `_on_replay_catch_due` starts an entry background task; `_async_replay_catch` takes the lock, re-checks `running`, runs the catch over `_native_device_ids()` and flushes the registries when something went. A legacy instance arms nothing. `async_stop` cancels the timer. Nothing sleeps or waits under the lock.
- README: the Limitations bullet about the near-limit native mirror and the boot-time replay is gone; the 100 mirrors / 256 KiB bullet stays; `test_readme_limitations_no_longer_list_the_native_residuals` keeps the phrases out.
- `_loop_back_discovery` in `tests/test_native_start.py` now hands `""` on when core's own removal of a loaded duplicate publishes None.

## Task Commits

1. **Task 1 (tracer): the registry-only catch after the quiet period over every native device**
   - `5e22ba8` test (RED, four tests)
   - `ce00638` fix (GREEN, plus the guard test and five helper tests)
2. **Task 2: catch 1, right after the registry move**
   - `34aec1c` test (RED)
   - `43315ee` fix (GREEN)
3. **Task 3: README Limitations and docs guard**
   - `4883f70` docs

**Plan metadata:** committed after this SUMMARY (docs: complete plan).

## Files Created/Modified

- `custom_components/mqtt_actions/takeover.py` - `REPLAY_QUIET_SECONDS`, `remove_replay_twins`, module docstring
- `custom_components/mqtt_actions/manager.py` - `_cancel_replay_catch`, `_native_device_ids`, `_remove_replay_twins`, `_arm_replay_catch`, `_on_replay_catch_due`, `_async_replay_catch`, catch 1 in `_async_native_takeover`, timer cancel in `async_stop`
- `tests/test_native_replay.py` (new) - five replay tests, one parametrized, so six cases
- `tests/test_takeover.py` - five helper tests
- `tests/test_native_start.py` - `_loop_back_discovery` hands `""` on instead of None
- `tests/test_docs.py`, `README.md` - the Limitations edit and its guard

## Decisions Made

- Followed the plan as specified (D-04, D-05, D-06, the session decision on scope, quiet period as a timer). One deliberate tightening of the device removal, see Deviations.
- The twin config-entry check in the helper (`twin.config_entry_id != entry_id`) is a defensive guard for T-06-06 that no test pins: a mutation that disables it leaves the suite green, because a twin under another hub entry cannot be built with the available fixtures. It stays as a cheap guard.

## TDD Gate Compliance

The plan is `type: execute` with `tdd="true"` tasks, so the per-task gate applies: a `test(06-02)` commit that is red on the unchanged production code, then the `fix(06-02)` commit (commit-type note of plan 06-01). Verdicts come from `gsd_run check tdd-red-evidence`, fed with the pytest JUnit XML of the RED run (the `classname` and `name` attributes swapped, the same parser quirk as in plan 06-01).

| Commit | Target test | Failed on | Verdict |
|--------|-------------|-----------|---------|
| `5e22ba8` | `test_a_replay_during_the_pass_leaves_no_duplicate[before_the_clear]` | `legacy_entity_ids == []` in `_assert_clean`: `switch.lamp_2`, `button.lamp_test_on_2`, `button.lamp_test_off_2` remain | RED_EVIDENCE_OK |
| `5e22ba8` | `test_a_replay_during_the_pass_leaves_no_duplicate[after_the_clear]` | same assertion | RED_EVIDENCE_OK |
| `5e22ba8` | `test_a_replay_after_the_takeover_of_a_native_mirror_leaves_no_duplicate_and_no_publish` | same assertion (three `mqtt` entries of the mirror) | RED_EVIDENCE_OK |
| `5e22ba8` | `test_a_replay_before_a_restart_of_a_finished_native_owner_is_cleaned_at_the_next_start` | same assertion, after the first restart | RED_EVIDENCE_OK |
| `34aec1c` | `test_a_replay_right_after_the_move_is_removed_before_the_clear` | `left_at_the_clear == [[]]`: the list held the three duplicates | RED_EVIDENCE_OK |

All four RED tests of the first commit fail on the assertion that duplicates remain, not on an import, fixture or collection error. The RED commits are exactly the 1.0.0 production behavior for the replay (06-01 changed only the native flag), so these runs are the proof that the replay tests fail on the 1.0.0 code. The size-limit test of plan 06-01 has its own RED record in `06-01-SUMMARY.md`.

GREEN: all five pass after `ce00638` and `43315ee`. The helper and guard tests were added with the fix and are green by design; the helper tests were mutation-checked (dropping the twin check, the identity check or the device-empty check turns the matching test red; dropping the twin config-entry check does not, see Decisions Made).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Device removal waits for an empty device, not only for no MQTT entries**
- **Found during:** Task 1 (writing `remove_replay_twins`)
- **Issue:** The plan removes the emptied replayed MQTT device "unless entries this integration did not create remain". Core removes the entries of a device when the device goes. If a takeover finished with leftovers (a case where the moved entities stay on the original MQTT device) and the user later removed the leftover, a check on MQTT entries alone would delete the moved native entities with the device.
- **Fix:** The device is removed only when `async_entries_for_device(..., include_disabled_entities=True)` is empty. In every plan scenario the replayed device is empty after the removal, so behavior there is unchanged.
- **Files modified:** `custom_components/mqtt_actions/takeover.py`
- **Verification:** `test_remove_replay_twins_*` and the replay tests pass; the "no native twin" test pins that a device with a remaining entry is kept.
- **Commit:** `ce00638`

### Test-shape adjustments (no behavior change)

- The parametrized test names its parameter `replay_at`, because the plan's `before` collides with the `before` dict of `_unloaded_legacy_device`.
- The finished-owner test replays before each of the two restarts, so the second restart cleans a real replay instead of passing trivially.
- The arming guard unloads and sets up the same entry (seeded native, no pending) instead of adding a second hub entry that would share the Store key.
- The acceptance grep for `async_call_later(self._hass, takeover.REPLAY_QUIET_SECONDS` does not match literally: `ruff format` wraps the call over three lines. The constant is read at call time as planned (`manager.py` line 862 to 864).

**Total deviations:** 1 auto-fixed (Rule 1), 4 test-shape adjustments. **Impact:** none on the plan's goals.

## Issues Encountered

- A full run with `-p no:logging` (used for fast RED runs) reports 44 errors because the caplog-based tests need the logging plugin; the real full run is clean.
- `.planning/config.json` has an uncommitted change that is not part of this plan; it was left alone.

## Verification

- `uv run pytest tests/ -q`: 1480 passed (1468 after plan 06-01, plus 12 new: 6 replay cases, 5 helper tests, 1 docs test)
- `uv run pytest tests/test_native_replay.py -q`: 6 passed; with `tests/test_takeover.py -k replay` the same command reports 12 passed (11 at the end of Task 1)
- `uv run pytest tests/test_takeover.py tests/test_native_start.py tests/test_native_entities.py tests/test_native_cleanup.py tests/test_cutover.py -q`: 157 passed
- `uv run pytest tests/test_docs.py tests/test_repo_structure.py -q`: 64 passed
- `uv run ruff check .` and `uv run ruff format --check .`: clean
- `git diff -U0 dc66fe1 -- custom_components/mqtt_actions/takeover.py` shows no added `import` line; `manager.py` gained no `sleep`
- `git diff --name-only dc66fe1 -- pyproject.toml uv.lock` prints nothing (T-06-SC)

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path or file access. T-06-06, T-06-07, T-06-09, T-06-11 and T-06-12 are mitigated as planned; T-06-08 and T-06-10 are accepted as planned.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 6 has no further plan: both residuals (IN-02 in 06-01, IN-03 here) are fixed and the README no longer lists them. Ready for phase verification and the phase 8 UAT items that watch a real broker replay.

## Self-Check: PASSED

---
*Phase: 06-native-entity-residual-fixes*
*Completed: 2026-10-04*
