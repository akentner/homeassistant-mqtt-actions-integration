---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 08
subsystem: discovery
tags: [native-entities, discovery-export, options-flow, legacy-only, cleanup]

requires:
  - phase: 05-03
    provides: Manager.is_native and the native-only early return of async_publish_discovery
  - phase: 05-05
    provides: the takeover pass, _native_pending and _legacy_this_run
  - phase: 05-07
    provides: the multi-instance cutover and the follower flip
provides:
  - build_export and DiscoveryPublisher.async_publish_export / async_clear_export for the optional export
  - Hub options discovery_export (off by default) and export_prefix (default mqtt_actions_export), validated like a base topic
  - Manager._async_apply_export_options, which follows an option change from the entry update without a reload
  - Manager.heals_discovery, the single gate for healing and the removal count (legacy owned devices only)
  - A discovery-disabled issue that is raised only while discovery is still needed
  - Delete, orphan cleanup and hub removal that also clear the export topic
affects: [05-09]

plan_head_before: 8e0651a616e2790f36a9d4ca9495a6c877242b17
plan_head_after: 764bc4b44d50e6db29735701fb3ff6fa38654cf9
actuals:
  tokens: 21500
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "The export is a second, best-effort publish path: no subscription watches its prefix, nothing heals it, and clearing is always safe because an empty retained payload on an empty topic is a no-op"
    - "One predicate, Manager.heals_discovery, decides every legacy-only discovery behavior of the owner side"

key-files:
  created:
    - tests/test_discovery_export.py
    - tests/test_native_cleanup.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/discovery.py
    - custom_components/mqtt_actions/config_flow.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_hub_removal.py

key-decisions:
  - "A native device exports one component with enabled_by_default false, no test buttons, no test topic and no tombstones; the default prefix is one Home Assistant does not listen to, so enabling the export creates no duplicate unless the user chooses the core prefix"
  - "heals_discovery treats a device that waits for the takeover pass as not healed but a device in _legacy_this_run (deferred) as legacy again, so a deferred device keeps its 0.1.0 healing while the owner's own clear during the pass is never counted"
  - "The republish on an option change lives in Manager.async_reconcile (the update listener already reaches it), so __init__.py is unchanged and no reload is needed"

patterns-established:
  - "Options are stored only as submitted; an omitted export key means the default (off, default prefix)"

requirements-completed: [MIG-03]

duration: about 60min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 08: Discovery Export and Legacy-Only Machinery Summary

**MQTT Discovery now survives only as an optional, disabled-by-default, unhealed export of native devices with its own hub options, and healing, the discovery issues and the test topic belong to the legacy path alone.**

## Accomplishments

- `build_export` publishes one disabled-by-default component per native device (switch or select) with the same device block, origin and availability list as the legacy payload, retained at QoS 1 on `<export prefix>/device/<id>/config`. A legacy device never publishes it and the export is off unless the hub option is on (D-03, D-11).
- Against real core MQTT, an export on the core prefix becomes a registry entry of platform `mqtt` that is disabled by the integration, and the native entity is the only enabled one (T-5-17).
- The hub options flow has the export switch and the prefix. The prefix goes through `validate_base_topic` (`invalid_export_prefix` otherwise, nothing stored), only submitted keys are stored, and both languages carry the strings, including the duplicate warning.
- Changing the switch or the prefix republishes from the entry update: old export topics cleared, new ones published for each owned native device, legacy devices skipped.
- `heals_discovery` gates `SyncManager._on_discovery_message` and the trailing heal, so a native owner neither heals nor counts removals, and the retained clear it publishes itself during the takeover pass is not a foreign removal (MIG-03).
- `_check_discovery_enabled` is re-evaluated after the pass and after an export option change; the issue exists only for an instance that is not native, a device or mirror still on the legacy path, or an export on the core prefix.
- Delete, orphan cleanup and `async_remove_all_devices` clear the export topic along with the legacy discovery, config and state topics; core removes device and entities of the deleted subentry, and `_remove_companion` does it for a native mirror (proved in tests).

## Task Commits

1. **Task 1 RED:** `f37f7c6` (test) - export payload, publish, off by default, core-prefix duplicate, legacy, no healing
2. **Task 1 GREEN:** `1328460` (feat) - constants, `build_export`, publisher methods, native branch of `async_publish_discovery`
3. **Task 2 RED:** `7b6e07a` (test) - options form, prefix validation, republish tests
4. **Task 2 GREEN:** `e7c4096` (feat) - options flow, `_async_apply_export_options`, strings
5. **Task 3 RED:** `e1e5e9b` (test) - legacy-only conditionals and native delete tests
6. **Task 3 GREEN:** `764bc4b` (feat) - `heals_discovery`, conditional issue, export-aware clearing

The tracer gate (full suite and Ruff green on the Task 1 commit, `test_delete_device_own_subscription_never_sees_state_clear` aside, see below) ran before Task 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The existing options-flow test pinned the old form**
- **Found during:** Task 2 GREEN run
- **Issue:** `tests/test_hub_removal.py::test_hub_has_options_flow_with_delete_choice` asserted that the form has exactly one field, one schema key and no truthy suggested value. The plan's own behavior (a form with the export switch and the prefix, prefix suggested as the default) makes that assertion impossible, although its stored-options assertion still holds as the plan expected.
- **Fix:** the test now expects the three fields, reads the delete key's suggested value by name and keeps the stored-options assertions unchanged.
- **Files modified:** tests/test_hub_removal.py
- **Commit:** e7c4096

**2. [Rule 2 - Missing critical] A queued trailing heal could outlive the legacy path**
- **Found during:** Task 3 design
- **Issue:** the trailing throttle of the discovery heal could fire after the gate had already turned false (a device that became native in between) and, with the export on, publish the export, which contradicts "no healing".
- **Fix:** `_start_discovery_heal` asks `heals_discovery` again before it starts the republish.
- **Files modified:** custom_components/mqtt_actions/sync.py
- **Commit:** 764bc4b

### Plan assumptions adjusted

- **`heals_discovery` is slightly wider than the plan text.** The plan said "True only for an owned legacy device that is not pending". A device whose takeover was deferred stays pending but runs on the legacy path for this run, so it is healed again once it is in `_legacy_this_run`; only the window of the pass itself is excluded.
- **`_async_subscribe_mirror` and the deferred-mirror test subscription needed no change.** Plan 05-05 had already made the test topic of a mirror conditional on `is_native` and added the subscription in `_async_defer_takeover`; this plan adds the parametrized test that pins both outcomes.
- **Some new tests pass without a production change** (the mirror test topic, the native mirror tombstone, the deferred-device discovery issue), because those behaviors came with earlier plans; they are regression pins for MIG-03.
- **The export check on the discovery issue also reruns in `_async_apply_export_options`**, so switching the export onto the core prefix with discovery disabled raises the issue at once.
- **Imports of underscore helpers from `tests/test_native_start.py`** in `tests/test_native_cleanup.py` (`_legacy_mirror`, `_loop_back_discovery`, `_block_discovery_delivery`, `_store_the_mirror_as_native`) reuse the real-core takeover scaffolding instead of copying it.

## Issues Encountered

- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` failed in two full runs (once on the untouched baseline, once after Task 1) and passes alone and in the final full run; it is the known load-dependent flake.

## Verification

- `uv run pytest tests -q`: 1398 passed. `uv run ruff check .` and `uv run ruff format --check .` pass.
- Task 3 command (`tests/test_native_cleanup.py tests/test_sync_owner.py tests/test_manager.py tests/test_hub_removal.py`) passes; the legacy heal, delete and hub-removal tests are unchanged.
- Acceptance greps: `def build_export` 1, `enabled_by_default` 1 in `discovery.py`; `invalid_export_prefix` 1 in each translation file; `CONF_DISCOVERY_EXPORT` 5 in `config_flow.py`; `heals_discovery` 2 in `sync.py`, `def heals_discovery` 1 in `manager.py`.
- The `test(05-08)` commit precedes the `feat(05-08)` commit in all three tasks.
- Mutation check by design of the tests: without `heals_discovery` the native owner test fails on the first publish, the takeover test counts two removals, and the discovery issue tests fail for the native cases.

## Requirements

MIG-03 is complete: healing, ghost cleanup (`_clean_registry` only ever finds legacy registry entries), the discovery-removed and discovery-disabled issues and the test topic apply only to devices still on the legacy path.

ENT-03 stays open. The code delivers the optional export (off by default, `enabled_by_default` false, configurable prefix, duplicate warning in the options text), but its "documented" part belongs to the README and docs pages of plan 05-09, which marks it.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register: T-5-16 accepted, T-5-17 mitigated (prefix validation, disabled duplicate proven against real core MQTT, warning text).

## Self-Check: PASSED

- `tests/test_discovery_export.py`, `tests/test_native_cleanup.py` and this file exist; commits f37f7c6, 1328460, 7b6e07a, e7c4096, e1e5e9b and 764bc4b exist; `commits: 6` measured from `plan_head_before`.
