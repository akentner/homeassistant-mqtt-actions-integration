---
phase: 10-review-findings-and-native-migration-extraction
plan: 07
subsystem: testing
tags: [fix-07, review-2-in-02, core-contract, eager-task, cr-01, pin-tests, tdd]
status: complete

requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-01 (tests/test_core_contracts.py), plan 10-04 (NativeMigration calls takeover.remove_replay_twins through the module), plan 10-05 (_remove_planned holds the disable-first step)"
provides:
  - "tests/test_core_contracts.py: EAGER_TASK_HINT, autouse fast_takeover fixture, _record_loaded_at_removal(monkeypatch, hass)"
  - "FIX-07 pins of the no-clear removal of a loaded, enabled row on the takeover path and in the replay catch, both against real core MQTT"
affects: [10-08 to 10-10, 11 (MIR-01 edits the takeover and catch paths these pins guard)]

actuals:
  tokens: 2426
  tasks: 2
  commits: 2
plan_head_before: 41b58f07802ed19c3b22b607c070632b3b6918db
plan_head_after: 72936effcfac6bcdb8f9fcb8eff9072277e1e85f

tech-stack:
  added: []
  patterns:
    - "Premise recorder at the module seam: wrap takeover.remove_replay_twins and record, before the original runs, the content passed and whether each legacy row was loaded (entity_sources) and enabled"

key-files:
  created:
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-07-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-07-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-07-task2-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-07-task2-red.json
  modified:
    - tests/test_core_contracts.py

key-decisions:
  - "The recorder stores the content the caller passed (DiscoveryContent), not a content-given flag: after 10-04 NativeMigration._remove_replay_twins always passes content=, so the takeover path is identified by UNKNOWN and the catch by a content read from the topic (LEGACY here)"
  - "The mutant sits in takeover._remove_planned (where 10-05 moved the disable-first loop), replacing the async_update_entity(..., disabled_by=INTEGRATION) of an enabled row by pass"

patterns-established:
  - "Pin a core-internal ordering by its observable outcome (no publish on the shared topic, rows gone) plus an asserted premise at the call, never by patching core internals"

requirements-completed: [FIX-07]

coverage:
  - id: D1
    description: "Takeover-path pin: a follower's replay right after the takeover leaves three loaded, enabled rows; the takeover path removes them and nothing is published on the shared topic; RED against the disable-first mutant"
    requirement: FIX-07
    verification:
      - kind: integration
        ref: "tests/test_core_contracts.py#test_the_takeover_path_removes_a_loaded_enabled_row_without_a_clear_on_the_shared_topic"
        status: pass
      - kind: other
        ref: "node ~/.claude/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-07-task1-red.json --raw"
        status: pass
    human_judgment: false
  - id: D2
    description: "Replay-catch pin: on a running follower the catch removes the two loaded, enabled test buttons, keeps the integration-disabled switch twin, and nothing is published on the shared topic; RED against the same mutant"
    requirement: FIX-07
    verification:
      - kind: integration
        ref: "tests/test_core_contracts.py#test_the_replay_catch_removes_a_loaded_enabled_row_without_a_clear_on_the_shared_topic"
        status: pass
      - kind: other
        ref: "node ~/.claude/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-07-task2-red.json --raw"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-10-16
---

# Phase 10 Plan 07: FIX-07 eager-task pins Summary

**Two pins in `tests/test_core_contracts.py` check, against real core MQTT, that a loaded, enabled replay row leaves the registry without any publish on the shared core-prefix topic. One covers the start-up takeover path, the other the replay catch. Both fail with `EAGER_TASK_HINT` if Home Assistant drops the eager task in `Entity._async_registry_updated`.**

## Performance

- **Duration:** about 5 min
- **Started:** 2026-10-16T13:59:52Z
- **Completed:** 2026-10-16T14:04:40Z
- **Tasks:** 2
- **Files modified:** 1 test module, plus 4 RED records

## Accomplishments

- `EAGER_TASK_HINT` names the core spot (`Entity._async_registry_updated`, `homeassistant/helpers/entity.py`), the eager task, the CR-01 consequence and the next step: wait until the disabled entity has left `entity_sources`, or publish the migrate first.
- **Takeover path:** a follower's native mirror is taken over and a live replay lands right after the real `takeover.async_take_over`. At the takeover-path call (content UNKNOWN) all three replayed rows are loaded and enabled. Afterwards no legacy row is left and no publish of any kind went out on the shared topic.
- **Replay catch:** a follower is running after its takeover, and a live replay arrives within the quiet period. The guard disables the switch, and both buttons stay loaded and enabled. At the catch call the content is LEGACY and the flags are `[False, True, True]`. After the quiet period both buttons are gone, the integration-disabled switch twin stays (09.2 D-05), and nothing was published on the shared topic.
- Both pins were shown to fail first against a disable-first mutant: core then published retained `None` clears (3 on the takeover path, 2 in the catch). This is the same thing a core without the eager task would do.

## Task Commits

1. **Task 1 (tracer): takeover-path pin** - `ffe5603` (test)
2. **Task 2: replay-catch pin** - `72936ef` (test)

Both are `test(...)` commits only. This plan pins core behavior and changes no product code, so no `feat`/`fix` commit is expected (D-07).

## RED records and the mutant

**Mutant (temporary, never committed), in `custom_components/mqtt_actions/takeover.py` `_remove_planned`:**

```python
            if disable_first:
                pass  # MUTANT 10-07: the disable-first step is dropped
            entity_registry.async_remove(legacy.entity_id)
```

It replaces `entity_registry.async_update_entity(legacy.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)`. Without that line the enabled row is removed while its entity is still loaded, so core MQTT publishes its clear-on-remove. A core without the eager unsubscribe would have the same effect. The mutant was reverted with `git checkout` before each commit, and `git diff --quiet -- custom_components/` was clean.

- **Task 1 RED:** `tdd/10-07-task1-red.json` / `.xml`, RED_EVIDENCE_OK. Fails at `tests/test_core_contracts.py:241`, on `topic_publishes(mqtt_mock, topic) == []` with the hint: `[(None, True), (None, True), (None, True)] == []`. Every premise assertion held. Semantic assessment: the target ran and failed on the planned assertion because of the named mutant. No import, collection or fixture fault.
- **Task 2 RED:** `tdd/10-07-task2-red.json` / `.xml`, RED_EVIDENCE_OK. Fails at `tests/test_core_contracts.py:295`, on the same publish assertion: `[(None, True), (None, True)] == []`. The buttons were still removed and the switch twin was kept, so only the publish check caught the mutant. That is the intended reason.

## Files Created/Modified

- `tests/test_core_contracts.py`: adds `EAGER_TASK_HINT`, the autouse `fast_takeover` fixture (`TAKEOVER_RETRY_INTERVAL` = 0.01), `_record_loaded_at_removal` and the two FIX-07 tests. `pytest` is now imported at runtime because of the fixture.
- `tdd/10-07-task1-red.{xml,json}`, `tdd/10-07-task2-red.{xml,json}`: the RED evidence.

## Decisions Made

- The recorder returns `list[tuple[DiscoveryContent, list[bool]]]` instead of the planned `list[tuple[bool, list[bool]]]` (see Deviations).
- Task 2 clears no list. It installs the recorder after the setup takeover and first asserts `calls == []` before the quiet period. Every recorded call after that comes from the catch, and only calls with a content other than UNKNOWN are counted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan premise] "Was a content keyword passed" cannot tell the two call sites apart**
- **Found during:** Task 1
- **Issue:** The plan says the catch passes `content` and the takeover path does not. Since 10-04, `NativeMigration._remove_replay_twins` passes `content=` on every call, including UNKNOWN for the takeover path, so a "content given" flag would be True at both sites.
- **Fix:** The recorder stores the `DiscoveryContent` value that was passed. The takeover-path premise asserts UNKNOWN on the first call. The catch premise takes the calls with content other than UNKNOWN (LEGACY in this scenario).
- **Files modified:** tests/test_core_contracts.py
- **Verification:** The debug run showed `[(UNKNOWN, [True, True, True])]` on the takeover path and `[(LEGACY, [False, True, True])]` in the catch. Both pins are green on the unchanged tree and RED against the mutant.
- **Committed in:** ffe5603, 72936ef

**2. [Rule 3 - Blocking] The mutant location**
- **Found during:** Task 1
- **Issue:** The plan puts the mutant in `takeover.remove_replay_twins`. Since 10-05 the disable-first step lives in its helper `takeover._remove_planned`.
- **Fix:** Applied the mutant in `_remove_planned`. It is the same step, and `remove_replay_twins` still runs it.
- **Files modified:** none committed (temporary mutant)
- **Committed in:** n/a

---

**Total deviations:** 2 auto-fixed (1 plan-premise bug, 1 blocking location shift)
**Impact on plan:** Both pins assert what the plan intended. No product change and no scope creep.

## Issues Encountered

None. On the unchanged tree neither scenario showed any publish on the shared topic, so the D-07 premise holds and the stop rule did not trigger.

## User Setup Required

None. No external service configuration is required.

## Verification

- `uv run pytest -q tests/test_core_contracts.py`: 5 passed (3 FIX-01 pins, 2 FIX-07 pins). No skip or xfail marker.
- No product file changed in this plan: `git diff --quiet ffe5603^ HEAD -- custom_components/` passes, and the working tree is clean under `custom_components/`.
- `uv run ruff check .` and `uv run ruff format --check .` are green.
- `uv run pytest -q`: 1741 passed, 2 xfailed. That is the baseline of 1739 plus the 2 new pins.

## Next Phase Readiness

- FIX-07 is closed: the no-clear guarantee is pinned at both call sites, so a core change of the eager task turns CI red (D-08).
- Ready for 10-08.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*

## Self-Check: PASSED
