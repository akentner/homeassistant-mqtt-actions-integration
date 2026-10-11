---
phase: 08-real-instance-verification
plan: 17
subsystem: verification-gap-closure
tags: [uat-04, uat-02, guard, entity-registry, receiver, discovery-export, docs, tdd]
requires:
  - phase: 08-real-instance-verification
    provides: owner decision UAT04-RECEIVER-GUARD = extend-and-confirm (plan 08-16), the export-bound guard of plan 08-12, the failed 08-13 re-run on ha-b
provides:
  - duplicate guard armed whenever the manager runs, independent of the own export option and prefix
  - guard covers every native device this instance holds (owned and mirrored, not transferred away), with a native-twin requirement
  - triggers for both orders (core MQTT row created, native switch or select created) and a sweep at arm
  - one content-free INFO line with a count when a pass disables something
  - README and troubleshooting text for what is now true
affects: [08-18, 08-14, 08-15]
tech-stack:
  patterns: [registry-driven guard armed for the lifetime of the manager, disable-only, twin interlock]
key-files:
  created:
    - tests/test_export_guard_receiver.py
    - .planning/phases/08-real-instance-verification/08-evidence/uat-04-receiver-guard/ (red-1 to red-6 with JUnit XML)
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/takeover.py
    - tests/test_discovery_export.py
    - README.md
    - docs/troubleshooting.md
decisions:
  - "The guard no longer reads the export option or prefix: a receiver cannot know who exports, and the filter (native id held, core MQTT device identity, exact unique id, switch or select, disabled_by None, native twin) is what keeps it from touching a live entity"
  - "disable_export_duplicates became disable_duplicates (takeover.py) and takes the entry id for the native-twin check; the private manager names no longer say export"
  - "Core creating the row for a second delivery of an identical payload is not reproducible in this harness, so the idempotence and export-off-cycle tests recreate the row through the registry call core uses (the deleted-entity record decides the disabled state)"
metrics:
  duration: about 15 minutes of commits (14:12 to 14:23 CEST, 2026-10-11)
  completed: 2026-10-11
status: complete
commits: 6
plan_head_before: a175e9ce0e6775262d6a1f0e0a65a7619e3b8f49
plan_head_after: d7354c827fc7687ae381437b2a14ff6c78af4f07
actuals:
  tokens: 11400
  tasks: 3
  commits: 6
---

# Phase 8 Plan 17: receiver-side duplicate guard Summary

The registry-only duplicate guard of plan 08-12 now runs on every instance that holds a device natively, owner or receiver, whether or not that instance exports and whatever its prefix is. A receiver with the export off and a native mirror ends with exactly one mqtt row for the device id, `disabled_by` integration, when another instance's retained export on the core prefix reaches its core MQTT and its registry holds a null tombstone. The native row stays enabled and is the only enabled row of that unique id. This closes, in the product, the receiver case that failed in plan 08-13 (ha-b X7 and X8). No bench script ran.

## What was done

- **Task 1, tracer (RED a8b1c96, GREEN 23e40da):** `manager._duplicate_guard_ids` (named `_export_guard_ids` at that commit) returns `_native_device_ids()` minus `sync.transferred_away`. The arming no longer reads the export option or prefix; it stays at the old place in `async_start` (after the takeover pass, before the owned discovery is published), disarms in `async_stop`, and `_async_apply_export_options` no longer re-arms it.
- **Task 2, expansion (RED e80270d, GREEN f2138a3, REFACTOR 06c12dd):**
  - `takeover.disable_duplicates(hass, entry_id, device_id, *, mqtt_entry_id)`: a candidate is a switch or select entry of the core MQTT device of the id, unique id equal to the id, `disabled_by` None, and with a native twin (same domain, platform mqtt_actions, same unique id) under this config entry. It only disables.
  - The registry listener now also looks at `create` events of a mqtt_actions switch or select (the native twin appeared) next to the core MQTT row; both schedule one pass for that unique id on the next loop iteration; an update never triggers a pass.
  - One INFO line, `Disabled %d duplicate entities that core MQTT created for native devices`, with the count as the only argument, when a pass disables at least one row. A failure keeps the content-free warning.
  - Refactor renamed the private guard names (`_arm_duplicate_guard`, `_disarm_duplicate_guard`, `_duplicate_guard_ids`, `_on_duplicate_registry_updated`, `_disable_duplicates`, `_cancel_duplicate_guard`) and the helper; the refactor commit touches only `manager.py` and `takeover.py`.
- **Task 3, documentation (d7354c8):** README export section and the troubleshooting entry state that every instance holding the device natively disables such a duplicate itself right after Home Assistant creates it, whichever instance publishes the export, that disabled leftovers stay until the next restart which removes them, and keep the advice for an enabled duplicate that is still found. The two pinned README sentences are unchanged. No test or translation file was edited.

## TDD Gate Compliance

RED commits precede their GREEN commits (`a8b1c96` before `23e40da`, `e80270d` before `f2138a3`). Every record was produced by `red_record.py` style capture (pytest `--junitxml` with `-p no:logging`, XML in `output`, `reportPath`, run and report times) and classified by `gsd_run check tdd-red-evidence` as `RED_EVIDENCE_OK`; records are `08-evidence/uat-04-receiver-guard/red-1..6.json` with their JUnit XML. The `-p no:logging` flag made `caplog` unusable, so test E3 collects records through its own handler on the integration logger.

| Record | Target test | Failed on | Semantic assessment |
|--------|-------------|-----------|---------------------|
| red-1 | `test_a_receiver_disables_the_duplicate_that_a_foreign_core_prefix_export_restores` (R1) | the single mqtt row is enabled (None), expected integration | The premises (export off, native mirror, null tombstone, core MQTT device) passed first; it failed on its own assertion, not on import, fixture or collection. |
| red-2 | `test_the_guard_does_not_depend_on_the_export_option[options0]` (I1) | row enabled with the options empty | The sibling case with the export on the default prefix fails the same way (combined run: 2 failed, 1 passed); the core-prefix case passes on the unchanged code, as planned. |
| red-3 | `test_switching_the_export_off_leaves_the_guard_armed` (I2) | row enabled after the export was switched off | Premises (options empty, tombstone with `disabled_by` None) held. |
| red-4 | `test_a_row_without_a_native_twin_is_no_duplicate_and_stays_enabled` (E1) | row disabled although the native twin was removed | Premises (mirror native, twin gone) held; the Task 1 guard has no twin requirement. |
| red-5 | `test_a_duplicate_that_exists_before_the_device_is_held_is_disabled_when_the_native_entity_appears` (E2) | row stays enabled after the mirror and its entity appeared | Premises (not native, no native row, row enabled) held; the native entity was created. |
| red-6 | `test_a_pass_that_disables_something_logs_one_line_with_a_count_and_nothing_else` (E3) | no INFO record that reports disabled duplicates | The duplicate was disabled (premise assertion passed) and the line assertion failed. |

I1 has three cases in the final suite (options empty, export on the default prefix, export on the core prefix). For the core-prefix case the test first leaves an enabled tombstone, because with the export on, core had already created the disabled row at setup.

**Green on arrival (kept as regression tests, acceptable because they pin what the guard must not do and the paths that Task 1 already implemented):** G1 (select receiver), G2 (start sweep, the re-premised sweep test), G3 (legacy mirror rows, user-disabled row, row on another MQTT device, test-button row, native rows untouched, an id the instance holds nothing for with a foreign export), G4 (a second create event and a restart perform no update), G5 (fresh install, no update), G6 (export-off cycle). The core-prefix case of I1 was green on arrival as well.

## Existing tests that changed their contract (on purpose, in `tests/test_discovery_export.py`)

1. `test_the_guard_is_inert_while_the_export_is_off_or_on_another_prefix` became `test_the_guard_does_not_depend_on_the_export_option` (inverted: the row ends disabled; gained the core-prefix case).
2. `test_switching_the_export_off_removes_the_guard` became `test_switching_the_export_off_leaves_the_guard_armed` (inverted).
3. `test_an_enabled_row_that_exists_when_the_export_is_switched_on_is_disabled` became `test_an_enabled_row_that_exists_when_the_instance_starts_is_disabled` (start premise: set up once, unload, seed the enabled row, set up again, export off).

No other existing test was changed. The remaining plan 08-12 tests stayed green without edits. No existing test outside the guard modules needed a change.

## Verification

- Guard and neighbouring modules (`test_export_guard_receiver`, `test_discovery_export`, `test_native_replay`, `test_takeover`, `test_native_start`, `test_native_entities`): 167 passed.
- Full unit suite 1496 passed (baseline of 08-12 was 1481), broker tier 17 passed (baseline 17), `ruff check` and `ruff format --check` clean.
- `tests/test_docs.py` and `tests/test_translations.py`: 86 passed.
- `git diff --name-only caf2fe5dc003ea834104f4016d1996be4132e0c8 HEAD -- custom_components` names only `manager.py` and `takeover.py`; no translation file or `services.yaml` changed.
- The refactor commit changes no file under `tests/`; red-1 to red-6 all classify `RED_EVIDENCE_OK`.
- No bench script ran: the containers bind-mount the main checkout, so the new code reaches them only at the restart of plan 08-18.

## Deviations from Plan

**1. [Rule 3 - Blocking] Test construction for a second row creation.** In this harness core MQTT ignores a second live delivery of an identical (or changed) payload after the row was removed, as already seen in plan 08-12. G4 (second create event) and the last step of G6 (the export returns after the restart) therefore recreate the row through the same registry call core uses (`async_get_or_create` with the deleted-entity record deciding the disabled state), without passing a disabled state. The first arrival of the export, the receiver sequence of R1, G1, G4 and G6, is delivered to core live. The real broker round trip is left to plan 08-18.

**2. [Rule 3 - Blocking] E3 collects log records with its own handler.** The RED record procedure uses `-p no:logging`, which removes `caplog`; the test attaches a handler to the integration's logger and removes it again.

**3. Precondition tolerance.** The precondition of Task 1 tolerates only ` M .planning/config.json` as a dirty path. `.planning/STATE.md` was also modified at the start, by the orchestrator's begin-phase step (stated in the executor prompt). It was treated as the orchestrator's own change and is committed with the final metadata commit; `config.json` was never staged.

## Findings for plan 08-18

- A legacy Discovery replay on a native instance now has its switch or select row disabled by the guard before the catch removes it, so the tombstone that the catch leaves carries `disabled_by` integration instead of null. Plan 08-18 must restore null tombstones before UAT-04 (as the plan 08-17 design section states).
- On a restart the takeover pass for a native mirror with a legacy MQTT device can remove the disabled duplicate itself (the twin carries the identity); the replay catch does it otherwise. Both leave a tombstone with `disabled_by` integration (covered by the G6 test).
- The bench observation of the export-off cycle (leftovers stay until the next restart) is the one plan 08-18 should record.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register: T-08-48 (filter with native id, core MQTT device identity, exact unique id, switch or select, `disabled_by` None and native twin; disable only; trust matrix G3 and E1), T-08-49 (executes and publishes nothing, no new topic), T-08-50 (listener returns at once unless a create event of a candidate row; cancelled in `async_stop`), T-08-51 (text limited to tested behavior), T-08-52 (the log line carries a count only, asserted in E3).

## Requirements

UAT-04 and UAT-02 stay Pending: the receiver case closes in the product here, and the requirement closes only when the re-run on the new build is recorded (plans 08-18, 08-14 and 08-15).

## Self-Check: PASSED

- Commits a8b1c96, 23e40da, e80270d, f2138a3, 06c12dd and d7354c8 are in the branch, test commits precede their fix commits.
- `tests/test_export_guard_receiver.py` and `red-1.json` to `red-6.json` exist; the full unit suite, the broker tier and ruff are green; the diff constraint on `custom_components` holds.
