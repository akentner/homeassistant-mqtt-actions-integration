---
phase: 04-operations-recovery-and-release
plan: 05
subsystem: infra
tags: [home-assistant, select, device-registry, device-modes, observe, disabled, mqtt]

requires:
  - phase: 04-operations-recovery-and-release
    provides: MqttActionsEntity base, hub_device_info and the platform wiring (plan 04-04)
  - phase: 03-multi-instance-sync
    provides: Manager with owned devices and mirrors resolved through one _device lookup
provides:
  - run, observe and disabled as a local mode per owned device (companion device select) and per instance (hub select)
  - effective mode = most restrictive of hub and device mode, applied in the state path and the test-topic path
  - re-baseline on leaving disabled (baseline and startup window cleared, state topic subscribed again)
  - companion device per owned device under its subentry, kept in line on rename and removed on delete
affects: [04-06 mirror mode selects, 04-07 diagnostics, 04-08 resync service, 04-12 instance id change]

actuals:
  tokens: 15500
  tasks: 3
  commits: 6
plan_head_before: 17fabda36481a0c71f2477465c8f4dd8615a2f04
plan_head_after: 1bb4a8d9d908028d66dc826513a2a9ed78efe150

tech-stack:
  added: []
  patterns:
    - "Mode state lives in the Store only (two additive keys, no STORE_VERSION bump) and is parsed defensively like every other key"
    - "Select platform adds entities per device with config_subentry_id and follows SIGNAL_DEVICES_CHANGED for later devices"
    - "One _async_change_mode computes the effective mode before and after a change, so hub and device setters share the re-baseline decision"
    - "Broker-influenced text in log lines goes through model.shown (quoted, capped)"

key-files:
  created:
    - custom_components/mqtt_actions/modes.py
    - custom_components/mqtt_actions/select.py
    - tests/test_modes.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/model.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/entities.py
    - custom_components/mqtt_actions/__init__.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_model.py
    - tests/test_translations.py
    - tests/test_multi_instance_ops.py
    - tests/test_manager_breaker.py

key-decisions:
  - "The mode gate sits in _run_trigger between can_run and the circuit breaker, so an observed run is logged but never counted and never enqueued"
  - "Disabled returns before the tracker in _on_message, so neither the baseline nor the startup window moves while disabled"
  - "A device that leaves disabled is re-baselined with unsubscribe then subscribe of its state topic; with nothing retained the first live message counts as a real change"
  - "The test topic obeys the same effective mode (observe and disabled run nothing, debug line only), so the buttons cannot bypass a mode"
  - "The select shows the device's own mode, not the effective one; the hub select shows the instance mode"
  - "Companion lookup uses async_get_device_by_identifier with the entry id, because async_get_device is deprecated and raises under the test harness"
  - "A rename leaves a companion device alone when it has a name_by_user"

patterns-established:
  - "Entities for a device attach to its subentry through config_subentry_id of async_add_entities; core clears them with the subentry"
  - "Tests that need a symbol that does not exist yet import it inside the test function so RED is a test failure, not a collection error"

requirements-completed: [SYN-09]

coverage:
  - id: D1
    description: "Every owned device has a config-category select with run, observe and disabled on a companion device (identifier (mqtt_actions, uuid), model Switch device or Select device) attached to its subentry; the core MQTT discovery device is a different registry entry"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_modes.py#test_owned_device_has_a_companion_device_under_its_subentry"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_select_device_companion_model"
        status: pass
    human_judgment: false
  - id: D2
    description: "Observe tracks the baseline, logs each suppressed run with the quoted device and trigger names, runs nothing and never counts toward the circuit breaker"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_modes.py#test_observe_logs_and_runs_nothing_but_tracks_the_baseline"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_shown_quotes_and_caps_text"
        status: pass
    human_judgment: false
  - id: D3
    description: "Disabled processes nothing and leaves the baseline; leaving disabled clears the baseline and the startup window and replays the retained value as baseline only, so no stale edge ever runs"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_modes.py#test_disabled_ignores_state_and_leaves_the_baseline"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_leaving_disabled_rebaselines_without_running"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_leaving_disabled_without_retained_state_counts_the_next_live_change"
        status: pass
    human_judgment: false
  - id: D4
    description: "The test topic follows the same effective mode: a press runs only in run mode"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_modes.py#test_test_topic_respects_the_mode"
        status: pass
    human_judgment: false
  - id: D5
    description: "A hub select on the hub device sets the mode of the whole instance and the effective mode is the most restrictive of hub and device mode; leaving disabled through the hub re-baselines only devices that are not disabled on their own"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_modes.py#test_effective_mode_is_the_most_restrictive"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_hub_mode_select_sets_the_whole_instance"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_set_mode_rejects_bad_input"
        status: pass
    human_judgment: false
  - id: D6
    description: "Modes are local: never published, never in a document or a hash, saved in the Store, restored at start; malformed and orphan entries are dropped"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_modes.py#test_mode_change_never_publishes"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_modes_are_not_part_of_the_document"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_mode_persists_across_restart"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_hub_mode_persists_across_restart"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_orphan_mode_entries_are_pruned_at_start"
        status: pass
    human_judgment: false
  - id: D7
    description: "Renaming a device renames its companion device (a user-chosen name stays); deleting it removes the companion device, the select and the stored mode; the select of a gone device is unavailable"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_modes.py#test_rename_updates_the_companion_device_name"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_rename_keeps_a_name_the_user_chose"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_deleted_device_loses_companion_entity_and_mode"
        status: pass
      - kind: integration
        ref: "tests/test_modes.py#test_mode_select_unavailable_for_unknown_device"
        status: pass
    human_judgment: false
  - id: D8
    description: "In a real Home Assistant the Mode select (Configuration) of an owned device and the Instance mode select of the hub offer Run, Observe and Disabled in the user's language, and with Observe set a toggle logs that the actions were not run; with Disabled set and the state topic changed from another client, setting Run runs nothing and the next real change runs the actions"
    verification: []
    human_judgment: true
    rationale: "Appearance on the integration page, the translated option labels and the behavior against a real broker are the plan's human-checks; no automated test sees the real UI or a real Mosquitto with a running Home Assistant"

duration: 15min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 05: Run, observe and disabled modes Summary

**A local run, observe or disabled mode per owned device (select on a companion device under its subentry) and per instance (hub select), gated before the circuit breaker and on the test topic, with a re-baseline on leaving disabled so a stale retained value never runs**

## Performance

- **Duration:** 15 min
- **Started:** 2026-10-02T08:02:48Z
- **Completed:** 2026-10-02T08:17:28Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments
- `modes.py` (pure): `is_mode` accepts exactly the three words (no bools, numbers or other text), `most_restrictive` ranks disabled over observe over run and returns run for no arguments. Words, store keys and the two dispatcher signals are in `const.py`.
- `manager.py`: `instance_mode`, `device_mode`, `effective_mode`, `subentry_id_of`, `has_device`, `async_set_device_mode` and `async_set_instance_mode` (both raise `ValueError` for a bad word or unknown id); both modes are loaded defensively from, and saved to, the Store (`instance_mode` word, `device_modes` with only non-run entries) and pruned for unknown ids at start and on device removal. Observe logs `Observe mode: device 'Lamp' would have run 'onChangeToOn', no actions were run` and returns before the breaker; disabled returns before the tracker.
- `_async_change_mode` / `_async_rebaseline`: one change reads the effective mode of every owned and mirrored device before and after, and each device that left disabled gets its baseline and startup window cleared, its stored baseline dropped and its state topic subscribed again under the manager lock (assumption A17).
- `_on_test_message` returns for observe and disabled right after the retained check, so a button cannot bypass a mode (T-04-19).
- `select.py`: `DeviceModeSelect` (unique id `<uuid>_mode`, config category, shows the device's own mode, unavailable once the device is gone) on a `companion_device_info` device attached with `config_subentry_id`, and `InstanceModeSelect` (unique id `<entry id>_instance_mode`) on the hub device; later devices get their select through `SIGNAL_DEVICES_CHANGED`.
- A reconfigured title renames the companion device unless the user named it; deleting a subentry removes the companion device, the select and the stored mode (pinned by tests, core clears the registries).
- `entity.select.device_mode` and `entity.select.instance_mode` names and the three states in English and German; pinned in `REQUIRED_KEYS`.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Tracer, observe from the select on a companion device** - `51d4407` (test), `77dd424` (feat)
2. **Task 2: Disabled mode, re-baseline on leaving it, test-topic gate and hub mode** - `53d9501` (test), `5d80888` (feat)
3. **Task 3: Companion device lifecycle for owned devices** - `c5add96` (test), `1bb4a8d` (feat)

**Plan metadata:** committed with this summary (docs: complete plan)

## TDD Gate Compliance

RED precedes GREEN for all three tasks (`test(04-05)` `51d4407`, `53d9501`, `c5add96` before `feat(04-05)` `77dd424`, `5d80888`, `1bb4a8d`). No refactor commits were needed.

- **Task 1 RED:** all seven tests failed on the planned assertions (`assert companion is not None`, `assert entity_id is not None`, `ModuleNotFoundError: ...modes` for the pure helper test). The helper import is inside the test function, so a missing module fails that one test instead of the whole collection (no INVALID_RED). A first draft used the deprecated `async_get_device`, and a module-level `from topics import test_topic` was collected by pytest as a test; both were fixed before the RED commit.
- **Task 2 RED:** 18 tests failed (`AttributeError` for the missing `async_set_instance_mode`, assertion failures for the disabled gate, the test topic still running, the missing hub select, the missing translation keys, the baseline that moved while disabled). `test_shown_quotes_and_caps_text` passed already at RED because the plan builds `shown` in Task 1.
- **Task 3 RED:** only `test_rename_updates_the_companion_device_name` failed (`assert 'Lamp' == 'Floor lamp'`); the delete, pruning and unavailable tests passed because Tasks 1 and 2 already drop the mode, notify and gate availability, as the plan expected ("fix any gap the tests show": none).
- `gsd_run check tdd-red-evidence` parses TAP and Surefire output, not pytest, so the RED evidence above is recorded here by hand (target test name, assertion, observed failure).
- **Tracer gate:** the Task 1 verify chain (`tests/test_modes.py`, full suite 919 passed, `test_only_gateway_imports_mqtt_component`, `ruff check`, `ruff format --check`) was re-run on the committed GREEN state and passed before expansion; `Tracer verified end-to-end - expanding`. The tracer's `<verify>` also carries a `<human-check>`; this run is dispatched in `mode: yolo` with `human_verify_mode: end-of-phase` (as plans 04-03 and 04-04), so that real-Home-Assistant check is deferred to the phase verification (coverage D8).

## Files Created/Modified
- `custom_components/mqtt_actions/modes.py` - pure `is_mode` and `most_restrictive`
- `custom_components/mqtt_actions/select.py` - device and instance mode selects, dynamic entity creation per subentry
- `custom_components/mqtt_actions/manager.py` - mode state, setters, gate, re-baseline, companion rename, Store keys, device-changed signal
- `custom_components/mqtt_actions/entities.py` - `companion_device_info`
- `custom_components/mqtt_actions/const.py` - mode words, store keys, signals
- `custom_components/mqtt_actions/model.py` - `shown`
- `custom_components/mqtt_actions/__init__.py` - `Platform.SELECT`
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - select names and states
- `tests/test_modes.py` (new), `tests/test_model.py`, `tests/test_translations.py`, `tests/test_multi_instance_ops.py`, `tests/test_manager_breaker.py` - tests

## Decisions Made
- The gate lives in a new `_run_trigger` extracted from `_on_message`: observe returns after `can_run` and before the breaker, so only a change that would really run is logged as suppressed and nothing counts toward the breaker. The extraction also keeps `_on_message` under the Ruff return-statement limit once the disabled branch exists.
- Disabled returns before the tracker, so the startup window stays open as well; it is closed explicitly by the re-baseline.
- `async_set_device_mode` and `async_set_instance_mode` share `_async_change_mode`, which decides re-baselining from the effective mode before and after, so the hub select and a device select cannot disagree about who left disabled.
- A re-subscribe that fails (MQTT unavailable) is logged and leaves the device without a state subscription until the next start, matching how other MQTT failures in the manager are handled; it is never raised into the select service.
- The select shows the device's own mode (not the effective one), so the user sees what they set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Deprecated device registry lookup**
- **Found during:** Task 1 (RED test draft) and Task 3 (companion rename)
- **Issue:** The plan names `dr.async_get(hass).async_get_device(identifiers=...)`. In the installed Home Assistant that call is deprecated and raises under the test harness (`report_usage` with an error behavior), because identifiers are now unique per config entry only.
- **Fix:** Used `async_get_device_by_identifier((DOMAIN, device_id), entry_id)` in `Manager._rename_companion` and in the tests.
- **Files modified:** `custom_components/mqtt_actions/manager.py`, `tests/test_modes.py`
- **Verification:** `tests/test_modes.py` (30 passed); the plan's acceptance grep for `async_update_device` still prints 1
- **Committed in:** `1bb4a8d`, `51d4407`

**2. [Rule 1 - Bug] Store key-set assertion of the breaker tests**
- **Found during:** Task 1 (full suite after GREEN)
- **Issue:** `test_trip_is_persisted_as_config_hash` pins the exact set of Store keys; the two additive keys of this plan (`instance_mode`, `device_modes`) made it fail.
- **Fix:** Added both constants to the expected set; the test still guards against any other key.
- **Files modified:** `tests/test_manager_breaker.py`
- **Verification:** full suite passes
- **Committed in:** `77dd424`

**3. [Rule 3 - Blocking] Lint limits**
- **Found during:** Task 1 (`ruff check`)
- **Issue:** `_on_message` exceeded the return-statement limit (PLR0911) and a class-level `list` default tripped RUF012.
- **Fix:** Extracted `_run_trigger`; the select sets `_attr_options` in `__init__`.
- **Files modified:** `custom_components/mqtt_actions/manager.py`, `custom_components/mqtt_actions/select.py`
- **Verification:** `ruff check .` and `ruff format --check .` clean
- **Committed in:** `77dd424`

**4. [Rule 2 - Missing Critical] `Manager.has_device`**
- **Found during:** Task 1 (select availability)
- **Issue:** The plan requires the select to be available only while the device is owned or mirrored but names no public manager method for that; reading the private `_device` from an entity would break the encapsulation the other entities keep.
- **Fix:** Added a public `has_device(device_id)`.
- **Files modified:** `custom_components/mqtt_actions/manager.py`
- **Verification:** `test_mode_select_unavailable_for_unknown_device`
- **Committed in:** `77dd424`

---

**Total deviations:** 4 auto-fixed (1 bug, 1 missing critical, 2 blocking)
**Impact on plan:** All four are small and needed for correctness or to pass the project's own gates. No scope creep, no change to a locked decision.

## Issues Encountered
- One full-suite run failed `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` once (that test asserts no WARNING record during a subentry removal). The same run logged an asyncio 6 second slow-task warning, the test passed in 4 isolated runs, 12 repeated `-k delete_device` runs and in every later full run (919, 936, 945 passed). Treated as a load-dependent flake of the caplog assertion, not caused by this plan; if it recurs it is worth a look because a subentry removal now also removes a companion device and a select.
- A test in `tests/test_modes.py` first filtered log lines by the word "payload" and matched Home Assistant's own MQTT debug lines; the filter now only looks at records of `custom_components.mqtt_actions`.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Mirrors are covered by the gate (`_on_message` resolves owned devices and mirrors alike, and `_async_change_mode` re-baselines mirrors too), but their companion devices and selects are plan 04-06 as the plan states; that is a planned slice boundary, not a stub.

## Next Phase Readiness
- Plan 04-06 can add mirror companion devices and selects: `companion_device_info(..., mirror=True)`, `DeviceModeSelect` (already reads `device.mirror`), `has_device` and the gate are in place; only entity creation for mirrors without a subentry is missing.
- The human-check (D8) for both mode selects in a real Home Assistant is left to the phase verification.

## Self-Check: PASSED

- Created files exist: `modes.py`, `select.py`, `tests/test_modes.py` and this summary (checked with `[ -f ]`).
- Commits found in `git log`: `51d4407`, `77dd424`, `53d9501`, `5d80888`, `c5add96`, `1bb4a8d`.
- Plan-level verification: `uv run pytest tests -q` 945 passed, `uv run ruff check .` and `uv run ruff format --check .` clean, `test_only_gateway_imports_mqtt_component` passes.
- Acceptance greps: `def most_restrictive` 1, `_async_rebaseline` 3, `async_update_device` 1.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
