---
phase: 04-operations-recovery-and-release
plan: 04
subsystem: infra
tags: [home-assistant, sensor, button, device-registry, roster, resync, mqtt]

requires:
  - phase: 04-operations-recovery-and-release
    provides: PresenceManager (online_count, rows, SIGNAL_ROSTER_UPDATED) from plan 04-03
  - phase: 03-multi-instance-sync
    provides: Manager._async_republish (documents, discovery, online order)
provides:
  - hub device keyed by the config entry id with manufacturer MQTT Actions and model Hub
  - diagnostic roster sensor (state = online instances including this one, attribute instances = rows of name, id, version, last_seen, online)
  - resync button (config category) backed by Manager.async_resync with a 5 s cooldown
  - entity platform plumbing: PLATFORMS, forward after the manager started, unload before it stops
  - entities.py base class MqttActionsEntity and hub_device_info for the mode selects of plans 04-05 and 04-06
affects: [04-05 mode select, 04-06 mode select, 04-07 diagnostics, 04-08 resync service, 04-12 instance id change]

actuals:
  tokens: 7768
  tasks: 3
  commits: 6
plan_head_before: 11028f86693e75ecf441d0216b6720a6ed036f2f
plan_head_after: 681402ef494d0a5d0b8ee9daec02a3c50f5c9da9

tech-stack:
  added: []
  patterns:
    - "Hub entities share MqttActionsEntity: has_entity_name, no polling, dispatcher signals listed per class and connected in async_added_to_hass"
    - "Platforms are forwarded last in setup and unloaded first in unload, so every entity reads a running manager"
    - "Throttle on Manager.clock: the accepted time is remembered before the publish is awaited"

key-files:
  created:
    - custom_components/mqtt_actions/entities.py
    - custom_components/mqtt_actions/sensor.py
    - custom_components/mqtt_actions/button.py
    - tests/test_hub_entities.py
  modified:
    - custom_components/mqtt_actions/__init__.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_translations.py
    - tests/test_test_buttons.py

key-decisions:
  - "The hub device identifier is (mqtt_actions, config entry id), so it survives a change of the instance id"
  - "The roster state counts this instance and the attribute list starts with this instance"
  - "The sensor truncates the rows to MAX_TRACKED_INSTANCES + 1 itself, independent of the roster cap in presence.py"
  - "Manager.async_resync returns False when throttled or stopped; the button only logs that at debug level"
  - "A failed platform forward stops the manager before re-raising; a platform that refuses to unload leaves the entry loaded and untouched"

patterns-established:
  - "Entity unique ids are <entry id>_<name> (roster, resync); later hub entities follow it"
  - "Tests count discovered MQTT buttons through the entity registry platform, not by domain, because the hub adds a button of its own"

requirements-completed: [OPS-03, DSC-04]

coverage:
  - id: D1
    description: "The integration page has a hub device with a diagnostic roster sensor that counts the online instances including this one and follows the heartbeats"
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/test_hub_entities.py#test_hub_device_and_roster_sensor_exist"
        status: pass
      - kind: integration
        ref: "tests/test_hub_entities.py#test_roster_sensor_follows_the_heartbeats"
        status: pass
    human_judgment: false
  - id: D2
    description: "The roster attribute lists every instance with name, id, version, last seen and online, keeps an expired peer listed as offline, is unrecorded and capped"
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/test_hub_entities.py#test_roster_attributes_list_every_instance"
        status: pass
      - kind: integration
        ref: "tests/test_hub_entities.py#test_peer_turns_offline_in_the_sensor_after_90_seconds"
        status: pass
      - kind: integration
        ref: "tests/test_hub_entities.py#test_roster_attribute_is_unrecorded_and_capped"
        status: pass
    human_judgment: false
  - id: D3
    description: "The resync button republishes documents, discovery and online in the Phase 3 order without a clearing payload and a second press inside the cooldown does nothing"
    requirement: DSC-04
    verification:
      - kind: integration
        ref: "tests/test_hub_entities.py#test_resync_button_republishes_in_the_phase_3_order"
        status: pass
      - kind: integration
        ref: "tests/test_hub_entities.py#test_resync_is_throttled"
        status: pass
      - kind: integration
        ref: "tests/test_hub_entities.py#test_resync_returns_false_when_not_running"
        status: pass
      - kind: integration
        ref: "tests/test_hub_entities.py#test_resync_button_entity"
        status: pass
    human_judgment: false
  - id: D4
    description: "Unloading the entry removes the hub entities, stops the manager and a new setup works"
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/test_hub_entities.py#test_unload_removes_hub_entities_and_stops_the_manager"
        status: pass
    human_judgment: false
  - id: D5
    description: "In a real Home Assistant the hub device shows Instances online under Diagnostic and Resync under Configuration, and a resync leaves every entity in place"
    verification: []
    human_judgment: true
    rationale: "Appearance on the integration page and the behavior against a real broker are the plan's human-check; no automated test sees the real UI or a real Mosquitto with a running Home Assistant"

duration: 10min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 04: Hub device, roster sensor and resync button Summary

**A hub device per instance with a diagnostic roster sensor (count plus a capped, unrecorded list of name, id, version, last seen and online per instance) and a config-category resync button backed by a 5 s throttled Manager.async_resync, with platforms forwarded after the manager starts and unloaded before it stops**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-02T07:50:43Z
- **Completed:** 2026-10-02T08:00:30Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- `entities.py`: `hub_device_info(manager)` (identifier `(mqtt_actions, entry id)`, instance name, manufacturer `MQTT Actions`, model `Hub`, `sw_version`, service entry type) and the `MqttActionsEntity` base that connects the listed dispatcher signals through `async_on_remove`.
- `sensor.py`: `RosterSensor` (unique id `<entry id>_roster`, diagnostic) whose state is `presence.online_count()` and which rewrites itself on `SIGNAL_ROSTER_UPDATED`; attribute `instances` holds the rows mapped to exactly `name`, `id`, `version`, `last_seen`, `online`, truncated to `MAX_TRACKED_INSTANCES + 1`, declared in `_unrecorded_attributes`.
- `button.py` and `Manager.async_resync`: `ResyncButton` (unique id `<entry id>_resync`, config category); `async_resync` returns False when stopped or inside `RESYNC_MIN_INTERVAL_SECONDS` (5 s, on `Manager.clock`), otherwise remembers the time, runs the existing `_async_republish` (documents, discovery, `online`, then the non-retained heartbeat) and returns True.
- `__init__.py`: `PLATFORMS = [SENSOR, BUTTON]`, `async_forward_entry_setups` after the manager started (failure stops the manager), `async_unload_platforms` first on unload (only on success the breakers are released and the manager stops).
- `entity.sensor.instances_online.name` and `entity.button.resync.name` in English and German; both pinned in `REQUIRED_KEYS`.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Tracer, a hub device with a roster sensor that follows the heartbeats** - `27f69b9` (test), `509861a` (feat)
2. **Task 2: Roster attributes, unrecorded and capped, and expiry reaches the sensor** - `9a87978` (test), `afa04c4` (feat)
3. **Task 3: The resync button on the hub device with a cooldown** - `714905c` (test), `681402e` (feat)

**Plan metadata:** committed with this summary (docs: complete plan)

## TDD Gate Compliance

RED precedes GREEN for all three tasks (`test(04-04)` `27f69b9`, `9a87978`, `714905c` before `feat(04-04)` `509861a`, `afa04c4`, `681402e`). No refactor commits were needed.

- **Task 1 RED:** the three hub tests failed on the planned assertions (`assert device is not None`, `assert entity_id is not None`), and the two `test_required_keys_present` cases failed on the missing translation key. The first draft of the test called the deprecated `async_get_device`, which raised a `RuntimeError` instead; that was fixed to `async_get_device_by_identifier` before the RED commit, so the committed RED is assertion-level.
- **Task 2 RED:** the three tests failed with `KeyError: 'instances'` (no attribute yet) and `assert 'instances' in frozenset()` (nothing unrecorded yet).
- **Task 3 RED:** the button tests failed on `entity_id is not None`, the Manager tests on `AttributeError: no attribute 'async_resync'`, the translation test on the missing key. The cooldown constant was read as `const_module.RESYNC_MIN_INTERVAL_SECONDS` inside one test so that a missing constant would not turn the whole module into a collection `ImportError` (INVALID_RED); the GREEN commit switched it to a normal import.
- **Tracer gate:** the Task 1 verify chain (hub and translation tests, full suite 904 passed, `ruff check`, `ruff format --check`) was re-run on the committed GREEN state and passed before expansion; `⚡ Tracer verified end-to-end — expanding`. The tracer's `<verify>` also carries a `<human-check>`; this run is dispatched in `mode: yolo` with `human_verify_mode: end-of-phase`, so that real-Home-Assistant check is deferred to the phase verification (coverage D5) instead of stopping mid-plan.

## Files Created/Modified
- `custom_components/mqtt_actions/entities.py` - hub device info and the base entity class
- `custom_components/mqtt_actions/sensor.py` - roster sensor and sensor platform setup
- `custom_components/mqtt_actions/button.py` - resync button and button platform setup
- `custom_components/mqtt_actions/__init__.py` - PLATFORMS, forwarding after the start, unloading before the stop
- `custom_components/mqtt_actions/manager.py` - `Manager.async_resync` with the cooldown state
- `custom_components/mqtt_actions/const.py` - `RESYNC_MIN_INTERVAL_SECONDS`
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - new `entity` section
- `tests/test_hub_entities.py` - 11 tests with a real entry setup on `mqtt_mock`
- `tests/test_translations.py` - `REQUIRED_KEYS` extended
- `tests/test_test_buttons.py` - trigger-button counts exclude the hub's resync button

## Decisions Made
- Device identity is the entry id, not the instance id (plan 04-12 can change the instance id without orphaning the hub device).
- The sensor applies its own cap to the rows even though the roster is capped at the same number, so the size bound holds regardless of how presence changes.
- The recorded attributes of the sensor are only the standard ones; the 16384-byte recorder limit is therefore not reachable by the roster. The test measures the recorded share (everything except `instances`) against the limit with a full 256-peer flood of maximal names and versions.
- The throttle time is stored before the republish is awaited; two near-simultaneous presses cannot both pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in existing tests] Trigger-button counts included the new resync button**
- **Found during:** Task 3 (full suite)
- **Issue:** `test_removed_option_removes_its_button_entity`, `test_new_option_adds_a_button` and `test_delete_device_clears_buttons_with_the_discovery_clear` counted every state in the `button` domain; with the hub's resync button present they were off by one (and the final `== []` after a device delete could never hold again).
- **Fix:** a `_trigger_buttons(hass)` helper counts only buttons registered by the `mqtt` platform (the discovered test buttons); the five assertions use it. The behavior under test (a removed option removes its test button, a new one adds one, a delete clears them) is unchanged. The plan allowed adapting existing tests where they assumed that no platform exists.
- **Files modified:** `tests/test_test_buttons.py`
- **Verification:** `uv run pytest tests -q` 912 passed
- **Committed in:** `681402e` (Task 3 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 existing-test bug)
**Impact on plan:** Test-only; no production behavior changed beyond the plan.

## Issues Encountered
- The Task 3 GREEN commit was first created while three existing tests failed: the verification command was chained with `&&` after a `tail`, which hid the failing exit status. The failures were fixed immediately (deviation 1) and the unpushed commit was amended before anything else was built on it; the final `681402e` is green.
- `presence.py` needed no change: the expiry timer already sends `SIGNAL_ROSTER_UPDATED` when a peer turns offline (confirmed by `test_peer_turns_offline_in_the_sensor_after_90_seconds`).

## Known Stubs
None.

## Threat Flags
None. The new surface (a button any HA user can press, and peer-supplied names in the sensor attributes) is covered by T-04-15 (cooldown, `test_resync_is_throttled`), T-04-16 (unrecorded and capped, `test_roster_attribute_is_unrecorded_and_capped`), T-04-17 and T-04-18 (accepted).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `entities.py` (`MqttActionsEntity`, `hub_device_info`) and the platform forwarding are ready for the mode selects of plans 04-05 and 04-06 (add `Platform.SELECT` to `PLATFORMS`).
- Plan 04-08 can call `Manager.async_resync()` and raise a translated error when it returns False.
- The real-Home-Assistant check of the hub device and the resync against a real broker (coverage D5) is left to the phase verification.

## Self-Check: PASSED

- Created files exist: `entities.py`, `sensor.py`, `button.py`, `tests/test_hub_entities.py` found on disk.
- Commits found in `git log`: `27f69b9`, `509861a`, `9a87978`, `afa04c4`, `714905c`, `681402e`; `git rev-list --count 11028f8..HEAD` printed 6 before this summary; `test(04-04)` precedes `feat(04-04)` for every task.
- Acceptance criteria re-run: `grep -c async_forward_entry_setups` 1, `grep -c async_unload_platforms` 1, `grep -c _unrecorded_attributes` (sensor.py) 1, `grep -c RESYNC_MIN_INTERVAL_SECONDS` (const.py) 1, `test_only_gateway_imports_mqtt_component` passed.
- Plan verification re-run: `uv run pytest tests -q` 912 passed; `uv run ruff check .` and `uv run ruff format --check .` clean.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
