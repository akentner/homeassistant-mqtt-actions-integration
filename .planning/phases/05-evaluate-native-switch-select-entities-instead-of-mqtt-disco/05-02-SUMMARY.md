---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 02
subsystem: migration
tags: [entity-registry, device-registry, takeover, mqtt-discovery, migration]

requires:
  - phase: 05-01
    provides: ADR 0001 (Accepted) and the core-behavior pins and test helpers in tests/test_takeover.py
provides:
  - takeover.py with legacy_device, is_legacy_entity, TakeoverStatus, TakeoverTarget and async_take_over
  - Module tests against real core MQTT discovery for owners, mirrors, switches and selects
affects: [05-05, 05-06]

plan_head_before: ed8a59a790198fdd935c311d63dd7014967d60ce
plan_head_after: a8d69a4631b0436fbfdce237fb1f275a781d45af
actuals:
  tokens: 7800
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Registry-only module: no publish, no import of the MQTT integration; broker order stays with the caller"
    - "Takeover order: wait until unloaded (entity_sources), entities, device, companion merge"
    - "Duplicate guard by (domain, platform, unique id) before every platform move"

key-files:
  created:
    - custom_components/mqtt_actions/takeover.py
  modified:
    - tests/test_takeover.py

key-decisions:
  - "A takeover that moved nothing and finds the native device already present removes the emptied legacy device; otherwise the legacy device is moved and the companion merged into it"
  - "A legacy device that still carries an entry of the MQTT entry that was not moved stays under MQTT, with one fixed warning, because moving it would remove that entry"

patterns-established:
  - "Tests start the takeover as a plain loop task (not a hass task) so async_block_till_done of the message helpers does not wait for it"

requirements-completed: [MIG-01]

duration: 30min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 02: Registry Takeover Module Summary

**`takeover.py` moves legacy core-MQTT switch/select devices, their test buttons and the companion mode select into the hub entry with every registry identity intact, proven against real core MQTT discovery.**

## Performance

- **Duration:** about 30 min
- **Tasks:** 2 (1 tracer, 1 hardening), both TDD with a separate RED commit
- **Files:** 1 created, 1 modified

## Accomplishments

- `async_take_over` returns NOTHING (no legacy device), DEFERRED (an entity is still in `entity_sources` after the bounded wait, registry untouched) or DONE. The wait is polling with `asyncio.sleep`, 10 s and 0.25 s by default, both overridable per call.
- Identity check (`is_legacy_entity`) requires platform `mqtt`, the MQTT entry, the MQTT device, a switch/select/button domain and the unique-id shape; the device is found only by the identifier `(mqtt, mqtt_actions_<id>)`. A foreign MQTT entity carrying the device id as unique id is left alone (T-5-01).
- Fixed order: entities (`async_update_entity_platform`, subentry left UNDEFINED for a mirror), then the device (`new_config_entry_id`, `new_config_subentry_id`), then the companion merge (companion entities move to the device, companion removed, identifier replaced by `(mqtt_actions, <id>)`).
- Duplicate guard (T-5-09): when `(domain, mqtt_actions, unique_id)` exists, the legacy entry is deleted instead of moved; an emptied legacy device is removed when the native device exists. This also cleans a late-replay twin at the next call.
- Disabled entries are collected with `include_disabled_entities=True` and keep `disabled_by`; ghosts need no broadcast and return DONE at once.
- 16 new tests (26 in the file); full suite 1283 passed; Ruff check and format clean.

## Task Commits

1. **Task 1 RED:** `257ab0e` (test) - tracer, NOTHING, DEFERRED tests
2. **Task 1 GREEN:** `c600b84` (feat) - takeover module
3. **Task 2 RED:** `54c4013` (test) - hardening tests
4. **Task 2 GREEN:** `a8d69a4` (feat) - duplicate guard, device rule, leftover guard

## Files Created/Modified

- `custom_components/mqtt_actions/takeover.py` - the registry takeover module
- `tests/test_takeover.py` - module tests next to the core pins of plan 05-01

## Decisions Made

- Late-replay twins are loaded when they appear, so the caller must deliver the migrate payload before calling again; the module waits for unload and never deletes a loaded entry (deleting a loaded MQTT entry would make core publish an empty discovery). Plan 05-05 owns that broadcast.
- The device rule was refined beyond the plan text: "native device exists" only removes the legacy device when nothing was moved, because the companion device carries the same identifier as a native device and must instead be merged when entities did move.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff PLR0913 on the planned signature**
- **Found during:** Task 1
- **Issue:** `async_take_over` has six parameters (fixed by the plan) and `_async_wait_unloaded` had six.
- **Fix:** `_async_wait_unloaded` takes a `collect` callable; `async_take_over` carries `# noqa: PLR0913` like other modules of the repo.
- **Commit:** c600b84

**2. [Rule 1 - Test design] Foreign-entity test uses a button, not a switch**
- **Found during:** Task 2
- **Issue:** a foreign MQTT switch with the unique id of the real switch would collide on the registry key `(switch, mqtt, id)`, so core could not create it.
- **Fix:** the foreign entity is a button with the device id as unique id (domain is in the legacy set, so only the device and entry checks protect it). `test_is_legacy_entity_needs_every_part_of_the_identity` additionally pins each identity part.
- **Commit:** 54c4013, a8d69a4

**3. [Rule 2 - Missing critical] Unrecognized entry on the legacy device**
- **Issue:** moving the device removes entries of the old entry that are still attached (pinned by `test_moving_the_device_first_removes_its_entities`), so a foreign registry entry on the MQTT device would be lost.
- **Fix:** the device is left where it is with one fixed warning; `test_the_device_stays_when_an_unrecognized_entry_remains_on_it`.
- **Commit:** a8d69a4

### TDD note

Because the identity filter, ghost/disabled handling, select/button support and the mirror variant are all part of the Task 1 design the plan prescribed, five of the seven Task 2 tests (foreign entity, ghost, disabled, select, mirror) were already green at the Task 2 RED commit. They pin behavior and A3 rather than driving new code; the three that failed for the intended reason (duplicate key, late replay, leftover entry) drove the Task 2 code.

## Issues Encountered

None.

## Verification

- `grep -c "homeassistant.components" custom_components/mqtt_actions/takeover.py` prints 0; `grep -c async_publish` prints 0.
- `uv run pytest tests -q`: 1283 passed. `uv run ruff check .` and `uv run ruff format --check .` pass.
- Nothing calls the module yet; no existing behavior changed.

## Known Stubs

None.

## Threat Flags

None. The module adds no network or auth surface; it only mutates registries after the identity check (T-5-01, T-5-08, T-5-09 mitigated and tested).

## Self-Check: PASSED

- `custom_components/mqtt_actions/takeover.py` and `tests/test_takeover.py` exist.
- Commits 257ab0e, c600b84, 54c4013, a8d69a4 exist; `commits: 4` measured from `plan_head_before`.
