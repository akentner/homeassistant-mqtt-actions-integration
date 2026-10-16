---
phase: 10-review-findings-and-native-migration-extraction
plan: 02
subsystem: testing
tags: [test-helpers, refactor, ast-guard, tdd, fix-03, d-11]
status: complete

requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-01 (green baseline 1730 passed, 2 xfailed; tests/test_repo_structure.py with ROOT/TESTS constants)"
provides:
  - "tests/helpers.py: the single module of test helpers shared by several test modules, public names (D-11)"
  - "test_no_test_module_imports_from_another_test_module in tests/test_repo_structure.py (ast guard over tests/**/*.py)"
  - "replay_discovery (former _replay of test_native_replay) ready for plan 10-07"
affects: [10-03 (start-up ordering test), 10-07 (core-contract pins, replay_discovery), 10-09 (FIX-08 tests), 10-04 (move plan starts from an unchanged suite)]

actuals:
  tokens: 50300
  tasks: 3
  commits: 4
plan_head_before: 4f580340d42ad8a7775cd0ba88d2225ad5d2fbe6
plan_head_after: 8e0e9e041bfa7598966782e66c56d859d8b15845

tech-stack:
  added: []
  patterns:
    - "Shared test helpers live in tests/helpers.py with public names; test modules never import from another test_* module (guarded by an ast walk)"
    - "Helper moves are verified by AST: every surviving top-level def of a touched module and every moved body is ast.dump-identical to the original with the module-scoped renames applied"

key-files:
  created:
    - tests/helpers.py
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-02-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-02-task1-red.json
  modified:
    - tests/test_repo_structure.py
    - tests/test_diagnostics.py
    - tests/test_docs.py
    - tests/test_takeover.py
    - tests/test_native_start.py
    - tests/test_cutover.py
    - tests/test_native_cleanup.py
    - tests/test_discovery_content.py
    - tests/test_presence.py
    - tests/test_native_replay.py
    - tests/test_native_entities.py
    - tests/test_discovery_export.py
    - tests/test_export_guard_receiver.py

key-decisions:
  - "All default public names of the plan were kept: the module-scoped collision check (def, class, assignment, annotation, parameter of the new name, outside import statements) found no hit in any defining or consuming module"
  - "The guard also catches `from tests import test_x` and `from tests.<pkg> import test_x` and any dotted tests.*.test_* module, so tests/broker/ is covered"
  - "Renames are scoped per module: a consumer's own private helper with an old name (for example the local _manager, _setup, _publishes or _seed of test_cutover, test_native_cleanup and test_presence) is left alone"
  - "test_export_guard_receiver's import of _legacy_mirror and _restart moved in the Task 2 commit, so every commit of the plan collects and runs green (Rule 3)"

patterns-established:
  - "tests/helpers.py is the only place a test module imports a shared helper from; new shared helpers go there with a public name that shadows no local of a consumer"

requirements-completed: [FIX-03]

coverage:
  - id: D1
    description: "No test module imports from another test module; the ast guard fails on any import of a tests.test_* module and names importer and imported module"
    requirement: FIX-03
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_no_test_module_imports_from_another_test_module"
        status: pass
      - kind: other
        ref: "grep -rnE '^\\s*(from tests\\.test_|from tests import test_|import tests\\.test_)' tests/ (empty)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Shared helpers live in tests/helpers.py under public names; moved bodies are unchanged and the suite is unchanged apart from the new guard (1733 collected = N0 1732 + 1; 1731 passed, 2 xfailed)"
    requirement: FIX-03
    verification:
      - kind: unit
        ref: "uv run pytest -q (1731 passed, 2 xfailed)"
        status: pass
      - kind: other
        ref: "uv run pytest --co -q | tail -1 (1733 tests collected)"
        status: pass
      - kind: other
        ref: "AST comparison of every moved body and every surviving top-level def (0 mismatches)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-10-16
---

# Phase 10 Plan 02: Shared Test Helpers Summary

**tests/helpers.py now holds 38 shared test names (4 key sets, 6 constants, LegacyDevice, 27 functions) under public names; an ast guard in tests/test_repo_structure.py fails on any import of a tests.test_* module, and no test module imports another any more (FIX-03, D-11).**

## Performance

- **Duration:** 12 min
- **Started:** 2026-10-16T12:28:09Z
- **Completed:** 2026-10-16T12:40:10Z
- **Tasks:** 3
- **Files modified:** 14 (13 test modules + tests/helpers.py), plus 2 TDD records

## Accomplishments

- `test_no_test_module_imports_from_another_test_module`: parses every `*.py` under `tests/` (recursively, including `helpers.py`, `documents.py`, `log_helpers.py`, `fake_broker.py` and `tests/broker/`) and lists each violation as `<importing file> -> <imported module>`. It was red on the 10-01 tree with the eight planned importers and is green now.
- `tests/helpers.py` follows the model of `tests/log_helpers.py`: module docstring, `from __future__ import annotations`, typing-only imports under `TYPE_CHECKING`.
- Every moved body is AST-identical to its original once the renames are applied (34 moved definitions, 0 mismatches). Every surviving top-level def in the 13 touched modules is AST-identical too (0 changed, 0 added). The test-function counts of each module are unchanged.
- Test count: **N0 = 1732** collected at the start, **1733** at the end (N0 + 1, the new guard). Full suite: 1731 passed, 2 xfailed (baseline 1730 passed, 2 xfailed). Ruff check and format are green. `custom_components/` is unchanged.

## RED record (Task 1)

- **Command:** `uv run pytest -q tests/test_repo_structure.py -k another_test_module --junitxml=.planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-02-task1-red.xml`
- **Record:** `tdd/10-02-task1-red.json`, verdict `RED_EVIDENCE_OK` (`target_test_failed`, JUnit, 1 test, 1 failure).
- **Semantic assessment:** the target ran and failed on its only assertion (`assert not violations`). The message listed 15 violations from exactly the eight planned importers: test_cutover, test_discovery_content, test_docs, test_export_guard_receiver, test_native_cleanup, test_native_replay, test_native_start and test_presence. They import from the six defining modules. There was no import, collection or fixture fault.
- **GREEN:** the move commits are `refactor(10-02)` by design. Per the Phase 10 execution rules, a pure move commits as `refactor`. The guard turned green with `8e0e9e0`.

## Task Commits

1. **Task 1 (tracer): structure guard + diagnostics key sets.** RED `94788e4` (test), then slice `877b003` (refactor). Tracer gate: end-of-phase mode with an automated-only verify, so the verify was re-run, passed, and the plan expanded.
2. **Task 2: takeover and native-start helper family.** `ce9cfca` (refactor)
3. **Task 3: native-entity, export and replay helper family; the guard turns green.** `8e0e9e0` (refactor)

## Name map (old module and name -> new name in tests/helpers.py)

| Old module | Old name | New name |
|---|---|---|
| test_diagnostics | `TOP_KEYS`, `HUB_KEYS`, `ROSTER_KEYS`, `DEVICE_KEYS` | unchanged |
| test_takeover | `PREFIX`, `MIGRATE_PAYLOAD`, `CLEAR_PAYLOAD` | unchanged |
| test_takeover | `LegacyDevice` | `LegacyDevice` |
| test_takeover | `setup_legacy_device` | `setup_legacy_device` |
| test_takeover | `_published_payload` | `last_published_payload` |
| test_takeover | `_mqtt_entry_id` | `core_mqtt_entry_id` |
| test_takeover | `customize_mqtt_device` | `customize_mqtt_device` |
| test_takeover | `legacy_entity_ids` | `legacy_entity_ids` |
| test_takeover | `_discovery_clears` | `discovery_clears` |
| test_takeover | `_falsy_publishes` | `falsy_publishes` |
| test_native_start | `BASE` | `BASE` |
| test_native_start | `_seed` | `seed_store` |
| test_native_start | `_seed_native` | `seed_native_pending` |
| test_native_start | `_loop_back_discovery` | `loop_back_discovery` |
| test_native_start | `_block_discovery_delivery` | `block_discovery_delivery` |
| test_native_start | `_publishes` | `topic_publishes` |
| test_native_start | `_setup` | `setup_entry` |
| test_native_start | `_restart` | `restart_entry` |
| test_native_start | `_manager` | `manager_of` |
| test_native_start | `_legacy_mirror` | `legacy_mirror` |
| test_native_start | `_store_the_mirror_as_native` | `store_the_mirror_as_native` |
| test_native_start | `_mqtt_device_of` | `mqtt_device_of` |
| test_native_start | `_unloaded_legacy_device` | `unloaded_legacy_device` |
| test_native_start | `_assert_moved_and_native` | `assert_moved_and_native` |
| test_native_entities | `_entity_id` | `native_entity_id` |
| test_native_entities | `_publishes` | `topic_publishes_with_qos` |
| test_native_entities | `_deliver` | `deliver_config` |
| test_native_entities | `_presence` | `announce_presence` |
| test_native_entities | `_setup`, `_manager`, `BASE` | deleted (identical copies); `setup_entry`, `manager_of`, `BASE` are used |
| test_discovery_export | `CORE_PREFIX` | `CORE_PREFIX` |
| test_discovery_export | `_mqtt_row` | `create_mqtt_row` |
| test_native_replay | `QUIET_PERIOD_PASSED` (with its comment) | `QUIET_PERIOD_PASSED` |
| test_native_replay | `_quiet_period_passes` | `quiet_period_passes` |
| test_native_replay | `_replay` | `replay_discovery` (for plan 10-07) |
| test_export_guard_receiver | `_mqtt_device` | deleted; `mqtt_device_of` is used (review IN-02) |

**Names chosen differently from the defaults:** none. Before using each new name I grepped every defining and consuming module for a `def`, `class`, assignment, annotation or parameter with that name, outside import statements. There were no hits. Private helpers that no other module imports stay where they are, including `fast_takeover`, `_mqtt_device`, `_deliver`, `_subentry`, `_move_entities` and `_run_takeover` in test_takeover, and `_stored_pending` and `_all_topics` in test_native_start.

## Assertion-line review (acceptance criteria)

- **Task 2 (`ce9cfca`):** 184 `assert` lines changed. After the renames, 80 of 80 removed lines appear unchanged among the added lines. The remaining added lines are rename-only:
  - 24 are calls of `_assert_moved_and_native`, which now starts with `assert_` and so matches the grep.
  - One `assert keeps_enabled_legacy_row(... mqtt_entry_id=core_mqtt_entry_id(hass))` passed 120 columns with the longer name, and `ruff format` wrapped it onto three lines.
  - The rest are the bodies of the moved helpers, now in tests/helpers.py.
- **Task 3 (`8e0e9e0`):** 56 removed and 55 added `assert` lines. The one unmatched removed line, `assert await hass.config_entries.async_setup(entry.entry_id)`, is the body of the deleted duplicate `_setup` of test_native_entities. That body is identical to `setup_entry`.
- `ruff format` also wrapped a few other lines in test_takeover and test_native_replay that the longer names pushed past 120 columns. These are formatting only: the AST comparison shows no code change.

## Files Created/Modified

- `tests/helpers.py`: the shared helpers (diagnostics key sets, broker and registry constants, LegacyDevice, legacy-device, registry, store, broker-loopback, entry, replay and presence helpers)
- `tests/test_repo_structure.py`: `_is_test_module`, `_test_module_imports` and the guard test
- 12 consumer and defining modules: the import blocks are repointed to `tests.helpers`, and uses are renamed with word boundaries scoped to each module

## Decisions Made

- The guard reads the `tests` package broadly: any dotted module `tests.…test_*` and any `from tests[.pkg] import test_*` is a violation. That covers `tests/broker/`.
- Renames are scoped per module, never global. A consumer's own private helper that shares an old name stays untouched. This matters because test_cutover, test_native_cleanup and test_presence define their own `_manager`, `_setup`, `_publishes` or `_seed`.
- `mqtt_device_of` replaces `_mqtt_device` of test_export_guard_receiver. Both do the same registry lookup and return `dr.DeviceEntry | None`; only the docstring and a local variable differ.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_export_guard_receiver's import from test_native_start was repointed in the Task 2 commit**
- **Found during:** Task 2
- **Issue:** `tests/test_export_guard_receiver.py` (a Task 3 file) imports `_legacy_mirror` and `_restart` from `tests.test_native_start`. Task 2 deletes those names there. Committing Task 2 with only its eight listed files would have left a commit where that module fails collection (`ImportError`, 1718 collected, 1 error). That is exactly the IN-02 failure the plan removes.
- **Fix:** in the same commit, that one import line now points at `tests.helpers` (`legacy_mirror`, `restart_entry`), and its 5 uses are renamed. Its other imports from test modules stayed for Task 3.
- **Files modified:** tests/test_export_guard_receiver.py (6 changed lines)
- **Verification:** `uv run pytest --co -q` collected 1733 with 0 errors after Task 2; the module passed (15 passed).
- **Committed in:** `ce9cfca`. That commit therefore touches nine files, not the eight of the acceptance criterion. The file is in the plan's `files_modified`.

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** keeps every commit of the plan green and bisectable. No scope change.

## Issues Encountered

- My move and check scripts started out with global renames and a collision regex that also matched import blocks. Both gave false positives. I reverted the eight affected files with `git checkout -- <file>` (per file), scoped the renames per module, and reran. No such state was committed.

## TDD Gate Compliance

- RED `test(10-02)` `94788e4` comes first, with RED_EVIDENCE_OK.
- There is no `feat(10-02)` commit, by design. This is a pure move plan (type `execute`). The Phase 10 execution rules commit a pure move as `refactor(10-NN)`, so the GREEN step is the refactor commits `877b003`, `ce9cfca` and `8e0e9e0`, and the guard turns green in the last of them. The plan prescribes no behavior change.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plans 10-03, 10-07 and 10-09 can import from `tests.helpers`, for example `setup_entry`, `manager_of`, `restart_entry`, `seed_native_pending`, `replay_discovery`, `quiet_period_passes`, `discovery_clears` and `falsy_publishes`.
- The suite is unchanged apart from the new guard, so the move plan 10-04 starts from 1731 passed, 2 xfailed.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*

## Self-Check: PASSED

- FOUND: tests/helpers.py, tests/test_repo_structure.py, tdd/10-02-task1-red.xml, tdd/10-02-task1-red.json
- FOUND commits: 94788e4, 877b003, ce9cfca, 8e0e9e0 (all ancestors of HEAD)
- Guard green, cross-test import grep empty, 1733 collected, full suite and Ruff green, custom_components/ unchanged
