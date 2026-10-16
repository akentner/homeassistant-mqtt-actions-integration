---
phase: 10-review-findings-and-native-migration-extraction
plan: 03
subsystem: testing
tags: [start-up-order, spy-test, mutation-testing, tdd, fix-02, pitfall-8]
status: complete

requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-02 (tests/helpers.py with unloaded_legacy_device, loop_back_discovery, setup_legacy_device, quiet_period_passes; green baseline 1731 passed, 2 xfailed)"
provides:
  - "tests/test_startup_order.py: the 18-step start-up sequence of an upgrading owner with lock flags, both timers, and the survivor pin of the survey"
  - "mutation/mutate.py: the reusable mutation runner for plan 10-04 (file, class, method list, test command, --merge, --note)"
  - "mutation/pre-move.tsv: 28 of 28 moved methods killed (27 by the existing suite, 1 by a new pin)"
affects: [10-04 (the move: the ordering test stays byte-identical, the post-move run can require all 28 killed without test edits)]

actuals:
  tokens: 6100
  tasks: 2
  commits: 2
plan_head_before: 7e2cccbb0607a764496bd9f458ae0ce42d6436af
plan_head_after: 57eb119619a387197ab115ee313645aa9a62856b

tech-stack:
  added: []
  patterns:
    - "Start-up order pinned through functools.wraps spies on seams that do not move, each call recorded with the manager lock state read at call time"
    - "Mutation survey per moved method: ast-located body splice to one neutral return chosen from the return annotation, original bytes restored in a finally, git diff check at the end"

key-files:
  created:
    - tests/test_startup_order.py
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/mutate.py
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/pre-move.tsv
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/junit-pre/ (28 subset reports + 1 full-suite report)
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/junit-pin/_disarm_duplicate_guard.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-03-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-03-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-03-task2-red-_disarm_duplicate_guard.json
  modified: []

key-decisions:
  - "The derived 18-entry start-up order matched the unchanged tree on the first run, so the stop rule never fired and the expectation was not adjusted"
  - "The only survivor, Manager._disarm_duplicate_guard, is pinned by a listener-count invariant over two load/unload cycles: after a stop the devices are cleared, so a leaked guard can no longer disable a row and the plan's example (a later core duplicate stays enabled) cannot tell the mutant apart"
  - "mutate.py got two options beyond the plan's CLI, --merge and --note, so the pin proof updates one row of pre-move.tsv in place; the survey's own junit-pre reports stay as recorded and the proof run writes to junit-pin"

patterns-established:
  - "A pin for a moved method lives in tests/test_startup_order.py, is named test_pin_<method>_<what it proves>, and carries a RED record from the survey mutant"

requirements-completed: [FIX-02]

coverage:
  - id: D1
    description: "The start-up order of an upgrading owner and the lock boundary are an executable 18-entry assertion, proven red against the guard-after-publish mutant"
    requirement: FIX-02
    verification:
      - kind: unit
        ref: "tests/test_startup_order.py#test_the_start_up_order_of_an_upgrading_owner_is_fixed"
        status: pass
      - kind: other
        ref: "gsd-tools check tdd-red-evidence tdd/10-03-task1-red.json (RED_EVIDENCE_OK)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The replay catch and the cutover check run only after their delay (behavior, not async_call_later spies)"
    requirement: FIX-02
    verification:
      - kind: unit
        ref: "tests/test_startup_order.py#test_the_replay_catch_runs_only_after_the_quiet_period"
        status: pass
      - kind: unit
        ref: "tests/test_startup_order.py#test_the_cutover_check_waits_for_the_settle_time"
        status: pass
    human_judgment: false
  - id: D3
    description: "Pre-move mutation survey: all 28 moved methods killed; the one survivor is pinned and proven red against its mutant"
    requirement: FIX-02
    verification:
      - kind: other
        ref: "mutation/pre-move.tsv (28 rows, 28 killed, 0 survived)"
        status: pass
      - kind: unit
        ref: "tests/test_startup_order.py#test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener"
        status: pass
      - kind: other
        ref: "gsd-tools check tdd-red-evidence tdd/10-03-task2-red-_disarm_duplicate_guard.json (RED_EVIDENCE_OK)"
        status: pass
    human_judgment: false
  - id: D4
    description: "No product change, full suite and Ruff green"
    requirement: FIX-02
    verification:
      - kind: other
        ref: "git diff --quiet 7e2cccb HEAD -- custom_components/"
        status: pass
      - kind: unit
        ref: "uv run pytest -q (1735 passed, 2 xfailed)"
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-10-16
---

# Phase 10 Plan 03: Start-up Ordering Test and Pre-move Mutation Survey Summary

**tests/test_startup_order.py pins the 18-step start-up order of an upgrading owner with the lock flag of every step through spies on seams that do not move. It also pins both timers. The pre-move mutation survey killed all 28 Manager methods that plan 10-04 moves: 27 through the existing suite, and `_disarm_duplicate_guard` through a new pin (FIX-02, Pitfall 8).**

## Performance

- **Duration:** 19 min
- **Started:** 2026-10-16T12:43:14Z
- **Completed:** 2026-10-16T13:02:30Z
- **Tasks:** 2
- **Files:** 1 test module created; under `.planning/`, the runner, the TSV, 30 JUnit reports and 3 TDD records

## Recorded start-up order (asserted literally)

`test_the_start_up_order_of_an_upgrading_owner_is_fixed` uses `unloaded_legacy_device` plus `loop_back_discovery`. The list up to and including the first heartbeat is exactly this, as (label, lock held):

| # | Label | Seam | Lock |
|---|---|---|---|
| 1 | discovery_check | `Manager._check_discovery_enabled` | False |
| 2 | sync | `SyncManager.async_start` | True |
| 3 | presence | `PresenceManager.async_start` | True |
| 4 | retrigger | `RetriggerCoordinator.async_start` | True |
| 5 | orphans | `Manager._async_orphan_cleanup` | True |
| 6 | reconcile | `Manager._async_reconcile_locked` | True |
| 7 | migrate | `DiscoveryPublisher.async_publish_migrate` | True |
| 8 | take_over | `takeover.async_take_over` | True |
| 9 | replay_twins | `takeover.remove_replay_twins` | True |
| 10 | flush | `takeover.async_flush_registries` | True |
| 11 | migrate | `DiscoveryPublisher.async_publish_migrate` | True |
| 12 | clear | `DiscoveryPublisher.async_clear_device` | True |
| 13 | guard | `takeover.disable_duplicates` | True |
| 14 | config | `Manager.async_publish_config` | True |
| 15 | discovery | `Manager.async_publish_discovery` | True |
| 16 | discovery_check | `Manager._check_discovery_enabled` | True |
| 17 | availability | `Manager._async_publish_availability` | False |
| 18 | heartbeat | `PresenceManager.async_publish_heartbeat` | False |

The order was derived from `Manager.async_start` and `_async_native_takeover`. It matched the unchanged tree on the first run. None of the spied members is one that plan 10-04 moves. The grep from the verify step, `Manager, "_(arm|async_native|...)`, finds nothing.

The two timer tests check behavior only. `SyncManager.discovery_content`, which only the catch reads, has zero calls when the setup returns and at least one after `quiet_period_passes`. `PresenceManager.blocking_peers`, which only the cutover check calls, has zero calls when the setup of a legacy instance returns and at least one after 6 s (with `enable_native_cutover`).

## Mutation survey (mutation/pre-move.tsv)

- **Runner:** `mutate.py` (standard library only). It locates each method with `ast` and keeps the docstring. It splices the body to one neutral return taken from the return annotation: `None`, `False`, `0`, `[]`, `set()`, `frozenset()`, `TopicVerdict(False, False, False)` or `TakeoverStatus.NOTHING`. The original bytes are restored in a `finally`, and `git diff --quiet` runs at the end.
- **Subset:** the 13 migration test modules from the plan, with `-x -q`. The baseline subset run took 33 s. `--full-on-survive` and `--junit-dir mutation/junit-pre` were set.
- **Result:** 28 rows, **28 killed, 0 survived, 0 equivalent**.
  - 27 were killed by the existing suite. The cutover methods were killed by `test_cutover.py`, the deferral and unconfirmed-clear methods by `test_native_start.py`, and the takeover, replay and guard methods by `test_native_replay.py`.
  - `_disarm_duplicate_guard` (`return None`) survived both the subset and the full suite (`junit-pre/_disarm_duplicate_guard-full.xml`). It was then killed by the new pin: its row reads `killed`, first failing `tests/test_startup_order.py::test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener`, and the note names the pin.
- **Why only this one survived:** the method is called only at start (before arming) and at stop. After the stop, `devices` and `mirrors` are cleared, so a guard listener that leaked can no longer disable any row. The only observable effect is that one entity registry listener leaks per unload or reload and keeps the stopped manager alive. The pin asserts exactly that through `hass.bus.async_listeners()`. A native owner is loaded and unloaded twice, and the `EVENT_ENTITY_REGISTRY_UPDATED` listener count after the second cycle must equal the count after the first. As a premise, the guard adds a listener while the entry is loaded.

## RED records

| Record | Target | Mutant | Verdict |
|---|---|---|---|
| `tdd/10-03-task1-red.json` (+ `.xml`) | `test_the_start_up_order_of_an_upgrading_owner_is_fixed` | `self._arm_duplicate_guard()` moved below `await self._async_publish_owned()` in `Manager.async_start` | RED_EVIDENCE_OK. It failed on the sequence assertion `At index 12 diff: ('config', True) != ('guard', True)` |
| `tdd/10-03-task2-red-_disarm_duplicate_guard.json` (report `mutation/junit-pin/_disarm_duplicate_guard.xml`) | `test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener` | survey mutant `_disarm_duplicate_guard` -> `return None`, applied by mutate.py | RED_EVIDENCE_OK. It failed on the final equality `assert 5 == 4`; 417 tests, 1 failure, 0 errors |

Both mutants were reverted before each commit. `git diff --quiet -- custom_components/` was clean, and `git diff 7e2cccb HEAD -- custom_components/` is empty.

## Task Commits

1. **Task 1 (tracer): start-up order, lock boundary, timers.** `8da1699` (test). Tracer gate: the mode is end-of-phase and the verify is automated-only, so the verify was re-run. It passed (3 passed, product unchanged, Ruff clean, no moved-member spy, RED_EVIDENCE_OK), and the plan expanded.
2. **Task 2: survivor pin.** `57eb119` (test). `mutate.py`, `pre-move.tsv`, the JUnit reports and the TDD records go into the SUMMARY commit, as the plan says.

## Files Created/Modified

- `tests/test_startup_order.py`: `START_UP_SEAMS`, `_spy`, `_record_start_up`, `_count_calls`, the three planned tests, and `test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener`. It has its own autouse `fast_takeover` (`TAKEOVER_RETRY_INTERVAL = 0.01`).
- `mutation/mutate.py`: the runner, reused by plan 10-04.
- `mutation/pre-move.tsv`: columns method, mutant, exit, first_failing, verdict, note.
- `mutation/junit-pre/`: one report per method, plus `_disarm_duplicate_guard-full.xml` from the full-suite re-run of the survivor.
- `mutation/junit-pin/_disarm_duplicate_guard.xml`: the proof run of the pin.

## Decisions Made

- **The pin uses a listener count, not the plan's example.** The plan's example was "after unload, a core duplicate stays enabled". That holds with and without the mutant, because the stopped manager has no devices left. The listener count is the behavior that tells the two apart, and it uses only public HA API (`hass.bus.async_listeners()`).
- **The pin compares two load/unload cycles, not the count before the first setup.** The first attempt compared against the count before the setup. That failed on the unchanged tree (2 vs 3), because the loaded legacy core MQTT entities held their own registry tracking until the takeover moved them. The two-cycle invariant is independent of that.
- **mutate.py has `--merge` and `--note`.** The proof of a pin updates its row in `pre-move.tsv` in place with the pin id, and the survey's own reports in `junit-pre/` stay untouched.
- **Pin name.** The name drops the leading underscore of the method (`test_pin_disarm_duplicate_guard_...`) instead of `test_pin__disarm...`.

## Deviations from Plan

None in the plan's scope. The two refinements above, the `--merge`/`--note` options and the pin's chosen assertion, are recorded as decisions. They change no product file and no existing test.

## Issues Encountered

- The first version of the pin compared against the listener count before the first setup and failed on the unchanged tree. It was rewritten as the two-cycle invariant before any RED or commit.

## TDD Gate Compliance

- Both tasks are pin tasks with no product change. Fail-first was proven against named temporary mutants (execution rules of 10-01). RED `test(10-03)` `8da1699` and `57eb119` each come with a RED_EVIDENCE_OK record.
- There is no `feat`/`fix(10-03)` commit, by design. Per the Phase 10 rules, a pin is committed as `test(10-NN)` after its mutant is reverted.

## User Setup Required

None.

## Next Phase Readiness

- Plan 10-04 can move the 28 methods. `tests/test_startup_order.py` spies only on seams that stay, so it needs no edit.
- The post-move run is `uv run python .planning/phases/10-review-findings-and-native-migration-extraction/mutation/mutate.py --file custom_components/mqtt_actions/native_migration.py --class NativeMigration --methods <the 28, as named after the move> --out mutation/post-move.tsv --tests "<same subset>"`. It can require every mutant killed without touching tests (D-10).
- Full suite: 1735 passed, 2 xfailed (1731 + the 4 new tests). Ruff check and format are green.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*

## Self-Check: PASSED

- FOUND: tests/test_startup_order.py, mutation/mutate.py, mutation/pre-move.tsv, mutation/junit-pre/ (29 reports), mutation/junit-pin/_disarm_duplicate_guard.xml, tdd/10-03-task1-red.xml, tdd/10-03-task1-red.json, tdd/10-03-task2-red-_disarm_duplicate_guard.json
- FOUND commits: 8da1699, 57eb119 (both ancestors of HEAD)
- Task verifies: Task 1 (3 passed; product unchanged; Ruff; no moved-member spy; RED_EVIDENCE_OK) and Task 2 (28 method rows, no unargued survivor, product unchanged since the first test(10-03) commit; Ruff and the full suite green)
