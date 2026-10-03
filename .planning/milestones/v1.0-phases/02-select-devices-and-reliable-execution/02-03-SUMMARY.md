---
phase: 02-select-devices-and-reliable-execution
plan: 03
subsystem: discovery
tags: [home-assistant, mqtt-discovery, button, tombstone, test-button, tdd]

requires:
  - phase: 02-select-devices-and-reliable-execution
    provides: One Script per device with run variables and trigger_key dispatch (plan 02-02), DeviceSpec triggers (plan 02-01)
provides:
  - test_topic(base, device_id), the non-retained topic the test buttons publish to
  - One Discovery button per trigger (Switch ON and OFF, one per Select option) with UUID-based unique ids
  - Manager._on_test_message, which runs a trigger's actions locally with the run variable test true
  - Run variable test on every run (true for a press, false for a state-driven run)
  - Tombstones {"platform": "button"} for buttons of removed options, kept for every republish while the process lives
affects: [02-04 circuit breaker, 02-05 option editor flow and README, phase 3 trust gate and ACL documentation]

actuals:
  tokens: 11050
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "A discovery button carries no logic: it publishes the exact StateValue to a dedicated non-retained topic and the manager runs the press itself"
    - "Removing one discovered component needs an explicit tombstone; an omitted component is never removed by core MQTT discovery"
    - "Retired component keys live in memory on the Device and ride on every discovery publish, including the reconnect republish"

key-files:
  created:
    - tests/test_test_buttons.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/topics.py
    - custom_components/mqtt_actions/discovery.py
    - custom_components/mqtt_actions/runner.py
    - custom_components/mqtt_actions/manager.py
    - tests/test_topics.py
    - tests/test_discovery.py
    - tests/test_discovery_select.py

key-decisions:
  - "Component key test_<trigger_key> and unique_id <device_id>_test_<trigger_key> derive from the immutable StateValue hash, so a rename never changes the entity identity"
  - "The press handler never calls StateTracker.handle, never publishes and never consults the breaker; retained messages on the test topic return immediately (T-02-09)"
  - "Tombstones are in memory only and dropped at the next start (accepted edge T-02-11)"
  - "Test buttons use entity_category config (A4)"

patterns-established:
  - "Use topics.test_topic via the module in test files: importing a function named test_topic into a test module would make pytest collect it"
  - "Pin core behavior with a characterization test (omitted versus tombstoned component) next to the code that depends on it"

requirements-completed: [DEV-07]

coverage:
  - id: D1
    description: "Every trigger has a test button created through MQTT Discovery: Switch gets Test ON and Test OFF, Select one per option in creation order, unique ids stable across renames; pressing publishes exactly the StateValue on the test topic with qos 1 and retain false"
    requirement: DEV-07
    verification:
      - kind: unit
        ref: "tests/test_test_buttons.py#test_switch_discovery_has_two_test_buttons"
        status: pass
      - kind: unit
        ref: "tests/test_test_buttons.py#test_select_discovery_has_one_test_button_per_option_in_order"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_buttons_are_created_and_press_publishes_payload_on_test_topic"
        status: pass
      - kind: unit
        ref: "tests/test_topics.py#test_test_topic_shape"
        status: pass
    human_judgment: false
  - id: D2
    description: "A press runs only that trigger's actions locally with test true, without publishing to the state topic, changing the entity state, the baseline or the startup window; a state-driven run has test false; a Select press is normalized like a state payload"
    requirement: DEV-07
    verification:
      - kind: integration
        ref: "tests/test_test_buttons.py#test_press_runs_only_that_triggers_actions_locally"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_state_driven_run_has_test_variable_false"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_select_press_runs_that_options_actions"
        status: pass
    human_judgment: false
  - id: D3
    description: "Retained and unknown test payloads run nothing (unknown ones logged like state payloads, empty at debug only), a failing press uses the normal Repairs issue, an action-less trigger runs nothing"
    requirement: DEV-07
    verification:
      - kind: integration
        ref: "tests/test_test_buttons.py#test_retained_test_message_is_ignored"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_unknown_test_payload_is_logged_and_ignored"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_test_run_failure_uses_normal_repairs_issue"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_press_on_action_less_trigger_runs_nothing"
        status: pass
    human_judgment: false
  - id: D4
    description: "Buttons follow the option lifecycle: a new option adds a button, a rename changes only the name, a removed option removes its button entity through a tombstone that survives reconnect republishes and is dropped on re-add, deleting the device removes all buttons"
    requirement: DEV-07
    verification:
      - kind: integration
        ref: "tests/test_discovery_select.py#test_omitted_component_is_not_removed_but_tombstone_is"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_removed_option_removes_its_button_entity"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_tombstone_is_kept_for_every_republish_while_running"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_readded_state_value_drops_the_tombstone"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_renamed_option_renames_button_and_keeps_unique_id"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_new_option_adds_a_button"
        status: pass
      - kind: integration
        ref: "tests/test_test_buttons.py#test_delete_device_clears_buttons_with_the_discovery_clear"
        status: pass
    human_judgment: false
  - id: D5
    description: "The test topic subscription is released on device removal and on unload; an existing Phase 1 Switch device gets its two test buttons on the next discovery publish"
    requirement: DEV-07
    verification:
      - kind: integration
        ref: "tests/test_test_buttons.py#test_test_subscription_is_released_on_delete_and_unload"
        status: pass
      - kind: integration
        ref: "tests/test_discovery.py#test_build_discovery_switch_payload_unchanged"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-09-29
plan_head_before: bdfbd0c8d941031fac7053893a666ecfe5969823
plan_head_after: 0aa14c66ea297664405a21984dfdf5b403b151c6
commits: 4
status: complete
---

# Phase 2 Plan 3: Test Buttons Summary

**Every trigger of a Switch or Select now has a Discovery test button that runs exactly that trigger's actions locally (run variable `test` true) via a non-retained test topic, with no state publish, baseline or startup-window change, and button tombstones that remove the entity of a deleted option and survive reconnect republishes.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-09-29T17:38:39Z
- **Completed:** 2026-09-29T17:44:01Z (plus SUMMARY)
- **Tasks:** 2 (tracer: press runs actions; lifecycle: add, rename, tombstone, delete, release)
- **Files modified:** 9 (1 created, 8 modified)

## Accomplishments

- `topics.test_topic` and one `button` component per trigger in the device payload (component key `test_<trigger_key>`, `unique_id` `<device_id>_test_<trigger_key>`, name `Test <friendly name>`, `payload_press` the exact StateValue, `retain` false, `qos` 1, `entity_category` config). A real core discovery run creates the buttons and `button.press` publishes exactly `(test topic, StateValue, 1, False)`.
- `Manager._on_test_message` runs a press through the existing per-device Script with `test=True`. It returns on retained messages (T-02-09), logs unknown payloads through `_log_ignored` (T-02-10), ignores triggers without actions, and never touches the tracker, the state topic or (later) the breaker.
- `runner.enqueue(..., *, test=False)` puts `test` next to `trigger_key` into the run variables of every run, so templates can rely on it in state-driven runs as well.
- Tombstones: `build_discovery(..., retired=())` adds `{"platform": "button"}` for retired keys; `Device.retired_components` is updated in `_async_change_device` (keys that disappeared are added, keys of the new spec are removed) and rides on every `_async_publish_discovery`, including the reconnect republish. A characterization test pins that core ignores an omitted component.
- The test subscription is released next to the state subscription on device removal and on stop; the Phase 1 event order (discovery clear, unsubscribe, state clear) is unchanged.

## Task Commits

1. **Task 1: Tracer, a test button press runs that trigger's actions locally**
   - RED `3e4cb37` (test), GREEN `73a5b46` (feat)
2. **Task 2: Button lifecycle with tombstones (D-13)**
   - RED `9e6bcb8` (test), GREEN `0aa14c6` (feat)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `custom_components/mqtt_actions/topics.py` - `test_topic`
- `custom_components/mqtt_actions/const.py` - `BUTTON_KEY_PREFIX`
- `custom_components/mqtt_actions/discovery.py` - `button_component_key`, button components, tombstones, publisher `retired` keyword
- `custom_components/mqtt_actions/runner.py` - `test` run variable and `enqueue(test=...)`
- `custom_components/mqtt_actions/manager.py` - test subscription, `_on_test_message`, `Device.unsubscribe_test`, `Device.retired_components`
- `tests/test_test_buttons.py` - 18 test cases across payload shape, press handling and lifecycle
- `tests/test_topics.py`, `tests/test_discovery.py`, `tests/test_discovery_select.py` - topic shape, updated payload-shape assertions, omit-versus-tombstone characterization

## Decisions Made

- Button identity (component key, unique id, topic) is derived from the trigger hash, matching the plan's reversibility note: it is registered in HA's entity registry from the first release with buttons.
- The upgrade path for existing Phase 1 Switch devices needs no code: the next discovery publish adds their two buttons (open question 3 default, no opt-out). README and release notes belong to plan 02-05.
- Tombstones stay in memory only; a removal during an MQTT outage can leave an orphaned registry entry the user can delete (T-02-11, accepted).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Three Phase 1 and 2 payload-shape tests asserted the old component list**
- **Found during:** Task 1 (GREEN, full suite)
- **Issue:** `test_build_discovery_switch_payload_unchanged`, `test_build_discovery_select_component` and `test_select_device_publishes_select_discovery_through_manager` asserted `components == ["switch"]` or `["select"]`, which is no longer the contract once buttons exist.
- **Fix:** The assertions now pin the primary component first, the component count (switch plus 2, select plus one per option) and that no switch appears in a Select payload; the button shape is pinned in `tests/test_test_buttons.py`.
- **Files modified:** tests/test_discovery.py, tests/test_discovery_select.py
- **Verification:** `uv run pytest tests -q` 309 passed
- **Committed in:** 73a5b46

**2. [Rule 3 - Blocking] Ruff `PLR0913` on `ActionRunner.enqueue`**
- **Found during:** Task 1 (GREEN)
- **Issue:** The new keyword-only `test` parameter makes six arguments; `select = ["ALL"]` rejects it.
- **Fix:** `# noqa: PLR0913` on `enqueue`, the same handling `_async_run` already has.
- **Files modified:** custom_components/mqtt_actions/runner.py
- **Committed in:** 73a5b46

---

**Total deviations:** 2 auto-fixed (1 bug in outdated test assertions, 1 blocking lint)
**Impact on plan:** Both necessary and minimal, no scope creep.

## TDD Gate Compliance

Both tasks have a `test(02-03)` commit before the `feat(02-03)` commit (`3e4cb37` before `73a5b46`, `9e6bcb8` before `0aa14c6`). RED was confirmed intentional for both with `gsd_run check tdd-red-evidence` (verdict `RED_EVIDENCE_OK`, reason `target_test_failed`, class-level target `tests.test_test_buttons`, JUnit XML as output). Task 1 RED failed on the missing `test_topic` and `button_component_key` API plus behavior assertions (`test` variable undefined, no button entity in the registry); Task 2 RED failed on assertion (removed button entity stays alive, tombstone missing after reconnect and re-add). The omit-versus-tombstone characterization, rename, new-option, delete and subscription-release tests passed at their RED commit because they pin core behavior or Task 1 GREEN behavior, as the plan expected. Tracer gate: after `73a5b46` the full suite, `test_only_gateway_imports_mqtt_component`, `test_delete_device_clears_discovery_then_state`, `ruff check` and `ruff format --check` passed, so expansion went ahead. No REFACTOR commit was needed.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. The new test topic subscription is the trust boundary T-02-08 names; T-02-08, T-02-09 and T-02-10 are mitigated and tested (StateValue-only payloads, retained messages ignored, unknown payloads logged truncated). The README (plan 02-05) must name the test topic as a second trigger source, and Phase 3 (TRU-04) must cover it in the ACL guidance.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 02-04 (circuit breaker): `_on_test_message` never consults or feeds a breaker, so test presses stay outside the counted runs and usable while a device is paused (A2). The counted enqueue point remains `_on_message`.
- Ready for 02-05: the option editor flow can rely on removed options retiring their buttons through `_async_change_device`; README and release notes must mention the new buttons on existing Switch devices and the `/test` topic.
- Full suite: 309 passed; `ruff check` and `ruff format --check` clean.

## Self-Check: PASSED

- FOUND: tests/test_test_buttons.py, custom_components/mqtt_actions/discovery.py, custom_components/mqtt_actions/manager.py, custom_components/mqtt_actions/topics.py
- FOUND commits: 3e4cb37, 73a5b46, 9e6bcb8, 0aa14c6 (`git rev-list --count` from the plan ledger base: 4)
- `grep -c "def test_topic" topics.py` = 1, `grep -c "def button_component_key" discovery.py` = 1, `grep -c "_on_test_message" manager.py` = 2, `def test_retained_test_message_is_ignored` present
- `uv run pytest tests -q`: 309 passed; ruff check and format check clean

---
*Phase: 02-select-devices-and-reliable-execution*
*Completed: 2026-09-29*
