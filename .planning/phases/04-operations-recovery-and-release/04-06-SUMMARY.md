---
phase: 04-operations-recovery-and-release
plan: 06
subsystem: infra
tags: [home-assistant, select, device-registry, mirrors, device-modes, companion-device, mqtt]

requires:
  - phase: 04-operations-recovery-and-release
    provides: DeviceModeSelect, companion_device_info(mirror=...), has_device and the mode gate (plan 04-05)
  - phase: 03-multi-instance-sync
    provides: mirrors, async_apply_mirror, async_remove_mirror and the registry cleanup that spares live entities
provides:
  - companion device (no subentry, model "... (mirror)") with a mode select for every mirrored device of another instance
  - mode of a mirror persisted and applied after a restart; cached mirrors get their companion at start
  - Manager._remove_companion, companion rename on a changed document, mode and companion dropped with the mirror
affects: [04-07 diagnostics, 04-11 adoption (reuses _remove_companion), 04-12 instance id change]

actuals:
  tokens: 5700
  tasks: 2
  commits: 4
plan_head_before: 331c2b58b6220d472ad1d5d065066d246465d29d
plan_head_after: 860d23f8ba442cd85da79adc43b23b5c5e64841d

tech-stack:
  added: []
  patterns:
    - "A mirror has no subentry, so core never cleans its companion: the manager removes it by the (mqtt_actions, id) identifier only"
    - "One added-bookkeeping set in the select platform covers owned devices and mirrors, forgets ids gone from both"

key-files:
  created:
    - tests/test_companions.py
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/select.py

key-decisions:
  - "The select platform adds mirrors through the same _add_new_devices loop as owned devices; config_subentry_id comes from subentry_id_of, which is None for a mirror"
  - "async_apply_mirror signals SIGNAL_DEVICES_CHANGED only for a new mirror; async_remove_mirror signals after the removal"
  - "_remove_companion looks up with async_get_device_by_identifier and the entry id (the non-deprecated lookup, as in plan 04-05) and never touches the mqtt domain identifier"
  - "The companion rename reuses _rename_companion of plan 04-05 (name_by_user wins, no-op for an equal name)"

patterns-established:
  - "Removal of a mirror drops the stored mode in the same step as the companion, so nothing lingers until the next start prune"

requirements-completed: [SYN-09]

coverage:
  - id: D1
    description: "Every mirrored device appears as a companion device of the entry without a subentry (manufacturer MQTT Actions, model of a mirror) with a config-category mode select in state run; two mirrors have separate devices and selects"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_companions.py#test_mirror_has_a_companion_device_and_select"
        status: pass
      - kind: integration
        ref: "tests/test_companions.py#test_two_mirrors_have_separate_companions"
        status: pass
    human_judgment: false
  - id: D2
    description: "Observe stops an approved mirror (no run, baseline follows) and run resumes with exactly one run; the mode survives a restart and a cached mirror has its companion and select at start"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_companions.py#test_observe_stops_an_approved_mirror"
        status: pass
      - kind: integration
        ref: "tests/test_companions.py#test_mirror_mode_survives_restart"
        status: pass
      - kind: integration
        ref: "tests/test_companions.py#test_cached_mirror_restored_at_start_has_its_companion"
        status: pass
    human_judgment: false
  - id: D3
    description: "A tombstone or a prune removes the mirror's companion device, its select and its stored mode, and nothing else"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_companions.py#test_mirror_removal_removes_the_companion_and_its_mode"
        status: pass
      - kind: integration
        ref: "tests/test_companions.py#test_prune_removes_the_companion_too"
        status: pass
      - kind: integration
        ref: "tests/test_companions.py#test_remove_companion_is_idempotent"
        status: pass
    human_judgment: false
  - id: D4
    description: "Removing a mirror never touches the core MQTT registry device or its live entities and publishes no empty discovery"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_companions.py#test_removal_never_touches_the_mqtt_registry_device"
        status: pass
    human_judgment: false
  - id: D5
    description: "A changed document of the pinned owner renames the companion device unless the user named it"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_companions.py#test_mirror_rename_updates_the_companion"
        status: pass
      - kind: integration
        ref: "tests/test_companions.py#test_mirror_rename_keeps_a_name_the_user_chose"
        status: pass
    human_judgment: false
  - id: D6
    description: "With two real Home Assistant instances on one broker, the device created on the first appears on the second instance's MQTT Actions integration page with its Mode select, and the core MQTT device of the same name on the MQTT page does not read as a confusing duplicate"
    verification: []
    human_judgment: true
    rationale: "How two devices with one name look in the real frontend (assumption A14) and the behavior against a real broker with two running instances are the plan's human-check; no automated test sees the real UI"

duration: 7min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 06: Mirror companion devices Summary

**Every mirrored device of another instance gets a companion device (no subentry) with its own run/observe/disabled select, kept in line on rename and removed with the mirror, while the core MQTT registry entries are provably never touched**

## Performance

- **Duration:** about 7 min (start time was not recorded at launch; estimated from the previous plan's end)
- **Completed:** 2026-10-02T08:25Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `select.py`: the `_add_new_devices` loop now covers `manager.devices` and `manager.mirrors`; a mirror's select is added with `config_subentry_id` None (from `subentry_id_of`), its device info built with `companion_device_info(..., mirror=True)`. The bookkeeping set forgets ids gone from both sets, so a returning mirror gets its select again.
- `manager.py`: `async_apply_mirror` sends `SIGNAL_DEVICES_CHANGED` after it created a new mirror; the cached mirrors restored at start need no signal because the select platform is set up after `async_start`. A changed document of the pinned owner calls `_rename_companion` (user-chosen names stay).
- `manager.py`: `_remove_companion(device_id)` removes only the registry device with the identifier `(mqtt_actions, device_id)` of this entry; `async_remove_mirror` calls it, drops the stored mode and signals the select platform. `_clean_registry` is unchanged. Unknown ids and repeated calls do nothing.
- Pinned by 11 tests in `tests/test_companions.py`, among them the plan's two prohibitions (`test_observe_stops_an_approved_mirror`, `test_removal_never_touches_the_mqtt_registry_device`, which compares the MQTT device, its entity registry entries and states before and after and checks that no empty discovery was published).

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Tracer, a mirror gets a companion device and a mode select** - `839e47f` (test), `85ce951` (feat)
2. **Task 2: Companion life cycle of mirrors** - `b043351` (test), `860d23f` (feat)

**Plan metadata:** committed with this summary (docs: complete plan)

## TDD Gate Compliance

RED precedes GREEN for both tasks (`test(04-06)` `839e47f`, `b043351` before `feat(04-06)` `85ce951`, `860d23f`). No refactor commits were needed.

- **Task 1 RED:** all five tests failed on the planned assertions (`assert companion is not None` / `assert entity_id is not None`: only owned devices had a select). One test beyond the plan's four (`test_cached_mirror_restored_at_start_has_its_companion`) pins the restore-at-start half of D-15 with a seeded Store, because the unload/setup test alone cannot prove that the registry entries were created at start.
- **Task 2 RED:** 5 of 6 tests failed (companion still present after tombstone and prune, `'Lamp' == 'Floor lamp'`, and an `AttributeError` for the missing `_remove_companion` in the idempotency test). `test_mirror_rename_keeps_a_name_the_user_chose` passed at RED because nothing renames yet; it guards the GREEN step against overwriting a user name.
- `gsd_run check tdd-red-evidence` parses TAP and Surefire output, not pytest, so the RED evidence is recorded here by hand (as in plan 04-05).
- **Tracer gate:** the Task 1 verify chain (`tests/test_companions.py tests/test_modes.py` 35 passed, full suite 950 passed, `ruff check`, `ruff format --check`) was re-run on the GREEN state and passed before expansion; `Tracer verified end-to-end - expanding`. The tracer's `<verify>` also carries a `<human-check>`; the run is dispatched in `mode: yolo` with `human_verify_mode: end-of-phase` (as plans 04-03 to 04-05), so the two-instance check is deferred to the phase verification (coverage D6).

## Files Created/Modified
- `custom_components/mqtt_actions/select.py` - device mode selects for mirrors next to owned devices
- `custom_components/mqtt_actions/manager.py` - new-mirror signal, `_remove_companion`, companion rename, mode and companion dropped on mirror removal
- `tests/test_companions.py` - 11 tests for the companion device, select, mode and life cycle of mirrors

## Decisions Made
- Mirrors share the owned devices' add loop in the select platform instead of a second loop: the "already added" set stays one source of truth and `subentry_id_of` already returns None for a mirror.
- `_remove_companion` uses the entry-scoped `async_get_device_by_identifier`, like `_rename_companion`, because `async_get_device` is deprecated and raises under the test harness (same finding as plan 04-05). The new code contains no `mqtt` identifier lookup and no `async_remove_config_entry_device`.
- The rename calls the existing `_rename_companion` unconditionally on a changed document; it already ignores an equal name and a `name_by_user`.

## Deviations from Plan

None - plan executed exactly as written, with two small test-side additions: the extra restart test noted above, and a one-line docstring shortened for the 120-character Ruff limit in `select.py`.

## Issues Encountered
- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` (flaky once in plan 04-05) did not fail in any of my full-suite runs (950 and 956 passed).
- A run with `-p no:logging` made two caplog-based tests of `tests/test_modes.py` error with "recursive dependency involving fixture caplog"; that was my own flag, the tests pass normally.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None. The mirror name reaches the device registry only after `parse_document` validated it (T-04-24), `_clean_registry` is untouched and the companion removal is scoped to this integration's identifier (T-04-25), the stored mode and the companion are dropped together (T-04-26).

## Next Phase Readiness
- Plan 04-11 (adoption) can reuse `_remove_companion` as planned.
- The human-check (D6: two real instances, real frontend) is left to the phase verification.

## Self-Check: PASSED

- Created and modified files exist: `tests/test_companions.py`, `select.py`, `manager.py` and this summary (checked with `[ -f ]`).
- Commits found in `git log`: `839e47f`, `85ce951`, `b043351`, `860d23f`; `git rev-list --count` from the plan's recorded base gives 4.
- Plan-level verification: `uv run pytest tests -q` 956 passed, `uv run ruff check .` and `uv run ruff format --check .` clean.
- Acceptance greps: `mirrors` in `select.py` 3, `_remove_companion` in `manager.py` 2, no `async_remove_config_entry_device` in the integration.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
