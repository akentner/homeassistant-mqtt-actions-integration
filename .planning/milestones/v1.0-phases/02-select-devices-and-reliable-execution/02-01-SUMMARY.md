---
phase: 02-select-devices-and-reliable-execution
plan: 01
subsystem: runtime
tags: [home-assistant, mqtt-discovery, select, device-model, jinja-templates, tdd]

requires:
  - phase: 01-walking-skeleton-installable-switch
    provides: Switch runtime (manager, runner, state tracker, discovery publisher, store, gateway)
provides:
  - Pure DeviceSpec/TriggerSpec model with trigger_key and spec_from_data/spec_from_subentry for Switch and Select
  - StateTracker and decide() driven by an accepted-values map (Switch default keeps ON and OFF)
  - Device-level runner API (async_build_device, can_run, script_for, script_count, enqueue by trigger key)
  - Select discovery (one select component, value_template and command_template built from json_dumps literals)
  - Manager generalized over DeviceSpec; both subentry types enumerated for reconcile, orphan cleanup and hub removal
affects: [02-02 run modes, 02-03 test buttons, 02-04 circuit breaker, 02-05 option editor flow, phase 3 central config]

actuals:
  tokens: 16700
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "One pure DeviceSpec per subentry; only spec_from_data knows the storage layout"
    - "trigger_key = sha256(lowercased StateValue)[:12], derived and never stored"
    - "User strings enter Jinja only as json_dumps literals"
    - "Stored data is loaded defensively: malformed options are dropped, never raised"

key-files:
  created:
    - custom_components/mqtt_actions/model.py
    - tests/test_model.py
    - tests/test_manager_select.py
    - tests/test_discovery_select.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/state.py
    - custom_components/mqtt_actions/runner.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/discovery.py
    - tests/conftest.py
    - tests/test_state.py
    - tests/test_manager.py
    - tests/test_discovery.py

key-decisions:
  - "device_id (subentry UUID) stays the only device identity; triggers inside a device are keyed by trigger_key derived from the immutable StateValue"
  - "A stored baseline that is not a StateValue of its device is sanitized to no baseline at add and at change time (A11)"
  - "Renaming or removing the currently selected option leaves the HA select entity at unknown until the next valid payload; no republish (open question 1), pinned by a real-core test"
  - "Select payload normalization is str.strip().lower() in tracker and Jinja (trim | lower), never casefold; a shared-table test guards the parity"

patterns-established:
  - "Tolerant spec loader: isinstance guards, first-wins on case-insensitive duplicates, coercion helper for numeric settings"
  - "Hostile-string test table (HOSTILE_OPTIONS) rendered through real Template and real core MQTT discovery"

requirements-completed: [DEV-03, STA-07]

coverage:
  - id: D1
    description: "A Select device runs exactly the actions of the option whose StateValue arrives (any case, trimmed), once, and no other option's actions"
    requirement: DEV-03
    verification:
      - kind: integration
        ref: "tests/test_manager_select.py#test_tracer_select_option_payload_runs_only_that_option"
        status: pass
      - kind: integration
        ref: "tests/test_manager_select.py#test_select_payload_is_trimmed_and_case_insensitive"
        status: pass
      - kind: unit
        ref: "tests/test_state.py#test_decide_select_table"
        status: pass
    human_judgment: false
  - id: D2
    description: "Select is published as one device-based select entity; friendly names map to StateValues and back, safely for hostile strings, and the UI choice publishes the exact StateValue retained with qos 1"
    requirement: DEV-03
    verification:
      - kind: integration
        ref: "tests/test_discovery_select.py#test_select_entity_options_and_state_round_trip"
        status: pass
      - kind: unit
        ref: "tests/test_discovery_select.py#test_value_template_maps_hostile_strings"
        status: pass
      - kind: unit
        ref: "tests/test_discovery_select.py#test_command_template_maps_hostile_strings"
        status: pass
      - kind: unit
        ref: "tests/test_discovery_select.py#test_template_and_tracker_normalize_identically"
        status: pass
    human_judgment: false
  - id: D3
    description: "Unknown payloads are ignored and logged with the device name and a truncated repr; nothing runs, the baseline stays, core logs no warning, an unknown retained payload sets no baseline"
    requirement: STA-07
    verification:
      - kind: integration
        ref: "tests/test_manager_select.py#test_select_unknown_payload_is_ignored_and_logged"
        status: pass
      - kind: integration
        ref: "tests/test_manager_select.py#test_select_unknown_retained_payload_sets_no_baseline"
        status: pass
      - kind: integration
        ref: "tests/test_discovery_select.py#test_select_unknown_payload_keeps_state_without_core_warning"
        status: pass
    human_judgment: false
  - id: D4
    description: "Retained state only sets the baseline; run_on_startup runs the retained option once per start; a removed StateValue becomes unknown and resets the baseline; exact-string baselines survive reloads"
    requirement: DEV-03
    verification:
      - kind: integration
        ref: "tests/test_manager_select.py#test_select_retained_state_is_baseline_only_and_startup_flag_runs_once"
        status: pass
      - kind: integration
        ref: "tests/test_manager_select.py#test_select_removed_state_value_becomes_unknown"
        status: pass
      - kind: integration
        ref: "tests/test_manager_select.py#test_select_baseline_persisted_across_reload"
        status: pass
    human_judgment: false
  - id: D5
    description: "Switch devices behave as before through the generalized path; missing run_mode and breaker keys mean serial, 5 runs, 10 seconds; malformed stored options never crash a reconcile; Select devices are cleaned up as orphans and on hub removal"
    requirement: DEV-03
    verification:
      - kind: integration
        ref: "uv run pytest tests -q (276 passed, includes all 188 Phase 1 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_spec_select_drops_malformed_options"
        status: pass
      - kind: integration
        ref: "tests/test_manager_select.py#test_remove_entry_clears_select_device_topics"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-09-29
plan_head_before: 0c1f6c84a0868f6f144a2ef36e1db006e2b8ff25
plan_head_after: 1d4158ed7abb5eec23188a7464bdc4b699e90d58
commits: 6
status: complete
---

# Phase 2 Plan 1: Select Devices Runtime Summary

**Select devices run as first-class devices: one pure DeviceSpec per subentry drives the tracker, runner and a select discovery whose Jinja mapping templates are built from json_dumps literals and survive hostile strings against real core MQTT.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-29T17:19:52Z
- **Completed:** 2026-09-29T17:29:40Z (plus SUMMARY)
- **Tasks:** 3 (tracer, discovery, semantics and hardening)
- **Files modified:** 13 (4 created, 9 modified)

## Accomplishments

- A stored Select subentry starts as a device; a live payload equal to an option's StateValue (any case, whitespace-trimmed) runs exactly that option's actions once.
- Switch runtime moved onto the same generic path (`DeviceSpec`, accepted-values map, device-level runner API); all 188 Phase 1 tests stay green, with only assertions on removed internals rewritten.
- Select is published as one device-based `select` component; `value_template` and `command_template` map StateValue to friendly name and back. Seven hostile pairs (`{{ 1+1 }}`, `{% if x %}`, `{# c #}`, `}} {{`, quotes, backslashes, emoji, non-ASCII) round trip through real Template rendering and real core MQTT discovery, and UI choices publish the exact StateValue with `(qos 1, retain True)`.
- Unknown payloads (STA-07) are ignored and logged with device name and truncated repr; an unknown retained payload sets no baseline; core logs no warning for them.
- Stored data is defensive: malformed, duplicate (case-insensitive) and unencodable options are dropped, breaker settings are coerced, a baseline that is no longer a StateValue becomes unknown, and Select devices are enumerated by reconcile, orphan cleanup and hub removal.

## Task Commits

1. **Task 1: Tracer, Select device runs the option's actions**
   - RED `c1e7b58` (test), GREEN `76a7731` (feat)
2. **Task 2: Select discovery with generated mapping templates**
   - RED `36997fd` (test), GREEN `3307b4f` (feat)
3. **Task 3: Payload semantics, malformed-data hardening, lifecycle**
   - RED `625e103` (test), GREEN `1d4158e` (feat)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `custom_components/mqtt_actions/model.py` - pure DeviceSpec/TriggerSpec, trigger_key, tolerant spec_from_data and spec_from_subentry
- `custom_components/mqtt_actions/state.py` - `SWITCH_ACCEPTED`, `decide(..., accepted=)`, `StateTracker.accepted`
- `custom_components/mqtt_actions/runner.py` - device-level API (`async_build_device`, `can_run`, `script_for`, `script_count`, key-based `enqueue`)
- `custom_components/mqtt_actions/manager.py` - `Device(spec, ...)`, `_device_subentries`, baseline sanitizing, store pruning, key-based dispatch
- `custom_components/mqtt_actions/discovery.py` - `build_discovery`, `build_value_template`, `build_command_template`
- `custom_components/mqtt_actions/const.py` - Select, run mode and breaker constants
- `tests/test_model.py`, `tests/test_manager_select.py`, `tests/test_discovery_select.py` - new; `tests/conftest.py` (`make_select_subentry`, Switch kwargs omitted when None), `tests/test_state.py`, `tests/test_manager.py`, `tests/test_discovery.py` extended or adapted

## Decisions Made

- `trigger_key` is derived from the lowercased StateValue and never stored, so it is stable across renames and adds nothing to the future central-config document (costly-to-reverse wire contract, as flagged by the plan).
- `_async_run` in the runner keeps the per-device lock and now takes `trigger_key`, `script` and `run_variables` keyword-only; the "retired Script" skip check compares the registered Script of that key.
- The manager prunes the loaded baseline map to current subentry ids at start, so a deleted device's baseline cannot resurface.
- Open question 1 stands as planned: no republish of `last_acted` on rename or removal; the entity shows `unknown` until the next valid payload, pinned by `test_select_rename_and_remove_current_option_show_unknown`.

## Deviations from Plan

None - plan executed exactly as written.

Notes on execution detail that stay within the plan:

- The Task 1 accessor test derives the Switch trigger keys locally with `hashlib` (the documented key contract) instead of importing `SWITCH_ON_KEY`/`SWITCH_OFF_KEY`, so RED failed on the missing runner API rather than on a missing module. It doubles as an independent check of the key contract. `tests/test_manager.py` imports the model constants once they exist (GREEN commit), as the plan lists that edit under GREEN.
- Ruff `select = ["ALL"]` needed `# noqa: PLR0913` on `decide` and `ActionRunner._async_run` (argument counts), consistent with the existing `FBT001` noqa style.

## TDD Gate Compliance

Every task has a `test(02-01)` commit preceding its `feat(02-01)` commit (`c1e7b58` before `76a7731`, `36997fd` before `3307b4f`, `625e103` before `1d4158e`). RED was confirmed intentional for each task with `gsd_run check tdd-red-evidence` (verdict `RED_EVIDENCE_OK`); the checker's Surefire parser reads the pytest JUnit `classname`, so the target was given at class (module) level. Failures were assertion, `TypeError` on the not-yet-existing `accepted` keyword, or missing API, never collection errors.

Some Task 3 tests pin behavior that Task 1 already provided (unknown payload logging, retained baseline and startup flag, removed StateValue reset, dropped non-StateValue baseline); they passed at their RED commit by design, while the model hardening tests, breaker coercion, exact-string baseline persistence and the orphan test with a kept Select baseline failed and drove the GREEN change.

## Issues Encountered

None that changed scope. The tracer gate was satisfied end to end: after the Task 1 GREEN commit the full suite, the `-k tracer` selection, Ruff check and Ruff format check all passed before expansion.

## Known Stubs

None. Run mode and breaker fields are stored and coerced here; their runtime effect is plans 02-02 and 02-04, as scoped by the plan.

## Threat Flags

None. The plan's threat register (T-02-01 to T-02-04) is covered: hostile-string template tests, accepted-map-only dispatch with only device id and canonical value in run variables, truncated payload repr in logs, and a tolerant loader.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 02-02 (run modes): the runner exposes the per-trigger Script API and `DeviceSpec` already carries `run_mode`, `breaker_max_runs` and `breaker_window` with defaults.
- Plan 02-03 can add button components per `TriggerSpec` using `trigger.key`, and 02-05 can build the option editor over the stored option shape `spec_from_data` reads.
- Full suite: 276 passed; `ruff check` and `ruff format --check` clean.

## Self-Check: PASSED

---
*Phase: 02-select-devices-and-reliable-execution*
*Completed: 2026-09-29*
