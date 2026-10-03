---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 01
subsystem: architecture
tags: [adr, mqtt-discovery, entity-registry, takeover, go-no-go]

requires:
  - phase: 04-operations-recovery-and-release
    provides: v0.1.0 MQTT-Discovery-based switch/select devices that the migration has to take over
provides:
  - Regression tests pinning the core takeover behavior (entity id, registry id, device id, area and name survive the fixed-order takeover)
  - ADR 0001 with the Go decision for native switch/select entities, status Accepted
  - Phase 5 requirements registered (ENT-01..03, MIG-01..03, DEC-01) with a ROADMAP goal and success criteria
affects: [05-02, 05-03, 05-04, 05-05, 05-06, 05-07, 05-08, 05-09]

plan_head_before: f59f20578ff0d9c10a4a81ba4e0cc5008560b388
plan_head_after: 402f624ae20ec8b2a3bd5fefcf4019c0223f8ab7
actuals:
  tokens: 8400
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Takeover order: discovery-remove retained payload, wait for registry removal, then register native entity with the same unique id"
    - "Core behavior pinned as tests against the installed HA version, so a core upgrade that changes registry semantics fails loudly"

key-files:
  created:
    - tests/test_takeover.py
    - docs/adr/0001-native-entities-instead-of-mqtt-discovery.md
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "Go: replace MQTT-Discovery entities with native switch/select platforms (ADR 0001, Accepted)"
  - "Cutover design D-09, D-10, D-12 recorded in the ADR; points only the UAT can settle are listed there as open"

patterns-established:
  - "Public helper setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry, *, name='Lamp') in tests/test_takeover.py, reused by plans 05-02 and 05-05"

requirements-completed: [DEC-01, MIG-01]

duration: 24min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 01: Takeover Tracer and Go/No-Go ADR Summary

**Core MQTT-discovery-to-native takeover behavior pinned by 368 lines of regression tests against real HA core, and ADR 0001 accepted with a Go for native switch/select entities.**

## Performance

- **Duration:** about 24 min (excluding the wait for the human decision)
- **Started:** 2026-10-03T10:18Z
- **Completed:** 2026-10-03T10:42Z
- **Tasks:** 3 (1 tracer, 1 docs, 1 blocking-human decision)
- **Files modified:** 4

## Accomplishments

- Pinned core behavior in `tests/test_takeover.py`: the ordered takeover keeps entity id, registry id, device id, area and user-chosen name; an empty discovery payload on a loaded entity deletes its registry entry; a loaded entity refuses the platform move; moving the device before the entities removes them; core does not guard a duplicate unique id.
- Wrote ADR 0001 weighing all four D-02 criteria with evidence, plus the cutover design and open points.
- Registered ENT-01, ENT-02, ENT-03, MIG-01, MIG-02, MIG-03 and DEC-01 in REQUIREMENTS.md with Phase 5 traceability, and gave the ROADMAP Phase 5 entry a goal, requirement ids and success criteria.
- The user answered "go" at the blocking-human gate; the ADR line is `Status: Accepted`, the precondition for later one-way tasks.

## Task Commits

1. **Task 1: Tracer, takeover tests** - `33befed` (test)
2. **Task 2: ADR and requirements/roadmap registration** - `ee61b54` (docs)
3. **Task 3: Go/No-Go decision (Go), ADR set to Accepted** - `402f624` (docs)

**Plan metadata:** recorded in the closing docs commit of this plan.

## Files Created/Modified

- `tests/test_takeover.py` - takeover scenarios as regression tests plus shared helpers
- `docs/adr/0001-native-entities-instead-of-mqtt-discovery.md` - decision record, Accepted
- `.planning/REQUIREMENTS.md` - Phase 5 requirements and traceability
- `.planning/ROADMAP.md` - Phase 5 goal, requirements, success criteria

## Decisions Made

- Go for native entities (user decision, 2026-10-03). See the ADR for the criteria and consequences.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Helper signature needs `mqtt_mock`**
- **Found during:** Task 1
- **Issue:** Setting up a legacy discovery device requires the `mqtt_mock` fixture, so the helper could not have the signature the plan sketched.
- **Fix:** `setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry, *, name="Lamp")`.
- **Impact:** plans 05-02 and 05-05 must pass `mqtt_mock` when calling the helper.
- **Commit:** 33befed

## Issues Encountered

None. Full suite after the plan: `uv run pytest tests -q` gives 1264 passed.

## Verification

- `git diff --name-only f59f205 HEAD` lists no path under `custom_components/` (prohibition holds).
- Full test suite green (1264 passed).

## Known Stubs

None.

## Threat Flags

None. No production code or network surface changed.

## Self-Check: PASSED

- tests/test_takeover.py, the ADR, REQUIREMENTS.md and ROADMAP.md exist.
- Commits 33befed, ee61b54, 402f624 exist; `commits: 3` measured from `plan_head_before`.
