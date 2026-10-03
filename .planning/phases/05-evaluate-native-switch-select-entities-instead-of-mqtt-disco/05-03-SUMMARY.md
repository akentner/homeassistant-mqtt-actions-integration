---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 03
subsystem: entities
tags: [native-entities, switch, select, button, mqtt, entity-platform]

requires:
  - phase: 05-01
    provides: ADR 0001 (Accepted), the Go decision for native entities
  - phase: 05-02
    provides: takeover.py (registry takeover, not called yet)
provides:
  - switch.py with DeviceSwitch and the late-device add loop
  - DeviceSelect in select.py, DeviceTestButton in button.py
  - NativeDeviceEntity and device_info_for in entities.py (one device per concept, shared with the mode select)
  - Manager.is_native, Device.value, async_send_state, async_press_test, persisted native Store key
affects: [05-04, 05-05, 05-06]

plan_head_before: 52d382e0f6359f9af6656c8644af074f6b57dd6d
plan_head_after: 771ca3368a3c94db3ae29e269aec7290692f996a
actuals:
  tokens: 11000
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Native state comes only from the broker echo: commands publish retained at QoS 1 and never change the entity themselves"
    - "The shown value is recorded in _on_message before the disabled-mode gate; unknown and empty payloads change nothing"
    - "Select options and current option are computed live from the spec at every read, so rename and removal need no bookkeeping"
    - "Additive Store key written only when it differs from the default, so an instance that never used it keeps its Store byte for byte"

key-files:
  created:
    - custom_components/mqtt_actions/switch.py
    - tests/test_native_entities.py
  modified:
    - custom_components/mqtt_actions/__init__.py
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/entities.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/select.py
    - custom_components/mqtt_actions/button.py
    - tests/test_takeover.py

key-decisions:
  - "The native Store key is written only when it holds something other than the defaults; a legacy instance's persisted data is unchanged (keeps test_trip_is_persisted_as_config_hash untouched)"
  - "companion_device_info is replaced by device_info_for(manager, device_id) as the single device info builder; values are unchanged for legacy devices"
  - "Manager.async_send_state accepts mirrors too (any known device id); plan 05-04 decides how mirrors are exposed"

patterns-established:
  - "Tests that need to see a command wait for the echo must hold the gateway publish with a patch, because the mocked MQTT client loops publishes back (and core drops a second retained message per subscription)"

requirements-completed: [ENT-01, ENT-02, MIG-03]

duration: about 40min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 03: Native Switch, Select and Test Button Entities Summary

**Owned devices of an instance in native mode are now native Switch, Select and test-button entities of the hub entry on one shared device, with state from the broker echo and commands retained at QoS 1; instances without the native flag behave exactly as in 0.1.0.**

## Performance

- **Duration:** about 40 min
- **Tasks:** 3 (1 tracer, 2 auto), all TDD with a separate RED commit
- **Files:** 2 created, 7 modified

## Accomplishments

- `DeviceSwitch` and `DeviceSelect` have the unique id the legacy discovery entity had (the device id), take the device name, sit on the subentry (`config_subentry_id`) and on the device `(mqtt_actions, <id>)`, the same one the mode select uses (D-08).
- `Manager.is_native` reads the persisted `native` Store key (`instance`, `pending`, `devices`; malformed data means the defaults). Native devices publish no discovery and subscribe no test topic.
- `_on_message` records `Device.value` before the disabled gate and announces it with `SIGNAL_DEVICE_STATE`, so a disabled device still shows its real state; unknown and empty payloads change nothing.
- `Manager.async_send_state` publishes only an exact StateValue of a known device, retained at QoS 1; otherwise `ValueError` (T-5-10). Entities never set state optimistically.
- Select options and current option are computed live, so a rename follows and a removed option shows unknown; `_async_change_device` now notifies the platforms.
- `DeviceTestButton` keeps the legacy unique id (`<id>_test_<key>`), name `Test <friendly name>` and configuration category; `Manager.async_press_test` runs the trigger locally through the same mode gate and `runner.can_run`, publishing nothing. Removed options remove their button registry entry.
- 20 new tests; full suite 1303 passed; Ruff check and format clean.

## Task Commits

1. **Task 1 RED:** `cdc4f96` (test) - native switch tests
2. **Task 1 GREEN:** `a689e30` (feat) - switch platform, manager state, device_info_for, NativeDeviceEntity
3. **Task 2 RED:** `a9d3472` (test) - native select tests
4. **Task 2 GREEN:** `1e39a7e` (feat) - DeviceSelect, reconfigure notification
5. **Task 3 RED:** `df04508` (test) - native test button tests
6. **Task 3 GREEN:** `771ca33` (feat) - DeviceTestButton, async_press_test, shared `_enqueue_test`

## Decisions Made

- The `native` Store key is omitted while it holds only defaults. Writing it always changed the exact key set that `tests/test_manager_breaker.py::test_trip_is_persisted_as_config_hash` pins; omitting it keeps every legacy Store identical and the plan's "no legacy test changes" intact.
- The mode gate of a test run lives in `_test_blocked`, called by both the test-topic handler (before parsing, so a disabled device still logs nothing about unknown payloads) and `async_press_test`; `_enqueue_test` holds `can_run` and the enqueue. Legacy behavior is identical.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The mock switch platform of the 05-02 takeover tests collided with the real platform**
- **Found during:** Task 1
- **Issue:** `tests/test_takeover.py::_forward_native_switch` forwards a mock `mqtt_actions.switch` platform to an entry that, from now on, already forwards the real switch platform at setup, so the mock was never loaded and two takeover tests lost their entity state.
- **Fix:** the helper first unloads the entry's switch platform, then forwards the mock (two lines).
- **Files modified:** tests/test_takeover.py
- **Commit:** a689e30

**2. [Rule 1 - Test design] Mocked MQTT client loops publishes back**
- **Found during:** Task 1
- **Issue:** the plan expected `switch.turn_on` against `mqtt_mock` to leave the state unchanged until an echo; the mocked paho client echoes every publish at once, and core drops a second retained message per subscription, so a second echo never arrives.
- **Fix:** `test_turn_on_publishes_the_exact_value_retained_at_qos_1` holds the first command at the gateway with a patch (proving the state waits for the echo), fires the echo itself, and checks the real gateway call flags with the second command.
- **Commit:** a689e30

### Plan sequencing note

The "native device subscribes no test topic" and "no legacy discovery" parts of the manager changes were needed for the Task 1 tracer behavior and landed in the Task 1 commit; at the Task 3 RED commit the parametrized `test_a_native_device_subscribes_no_test_topic` was therefore already green. The five other Task 3 tests drove the Task 3 code.

## Issues Encountered

`tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` failed in two consecutive full runs with an asyncio slow-callback warning ("Executing ... took X seconds", WARNING level) in the captured log; it passes alone, in its file (three runs) and in the next three full runs. It is a load-dependent timing flake that asserts on any WARNING record; not caused by this plan's logic (no related code path), logged here for the verifier.

## Verification

- `uv run pytest tests -q`: 1303 passed. `uv run ruff check .` and `uv run ruff format --check .` pass.
- Acceptance greps: `class DeviceSwitch` 1, `def is_native` 1, `Platform.SWITCH` 1, `class DeviceSelect` 1, `device_info_for` in select.py 2, `class DeviceTestButton` 1, `def async_press_test` 1.
- No file deleted by any commit of the plan.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-5-05 (broker-supplied names in entity names and options) is covered by the existing `parse_document` limits; T-5-10 is enforced and tested in `Manager.async_send_state` (unknown device and foreign value raise `ValueError`, a foreign option raises `HomeAssistantError` before it).

## Self-Check: PASSED

- switch.py, tests/test_native_entities.py and all modified files exist.
- Commits cdc4f96, a689e30, a9d3472, 1e39a7e, df04508, 771ca33 exist; `commits: 6` measured from `plan_head_before`; each `test(05-03)` commit precedes its `feat(05-03)` commit.
