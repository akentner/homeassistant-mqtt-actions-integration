---
phase: 03-trust-central-config-and-ownership
plan: 03
subsystem: config-flow
tags: [mqtt, config-flow, subentries, options-flow, delete-confirmation, presence, hub-removal, translations, tdd]

requires:
  - phase: 03-trust-central-config-and-ownership
    provides: "Delete order with config tombstone, SyncManager owner side, ISSUE_DEVICE_PREFIXES, Manager public surface (plan 03-02)"
provides:
  - "All-instances delete confirmation in both device flows (delete_device menu, delete_confirmed, keep_device) with the device name and the count of other online instances"
  - "Instance presence from the availability wildcard: SyncManager.online_instance_count(), instance_status(), cap MAX_TRACKED_INSTANCES = 256"
  - "Switch reconfigure is a menu (edit_device, delete_device); Select menu gains delete_device in reconfigure mode only"
  - "HubOptionsFlow with the delete_devices_on_remove boolean; async_remove_entry keeps devices by default and deletes everywhere only on the option"
  - "async_remove_local_state (Store and issues, both removal modes) and async_remove_all_devices(gateway=, store_key=) test seams"
  - "English and German texts for every new step, abort reason, menu item and the hub option"
affects: [03-04, 03-05, 03-06, 03-07, 04-operations]

requirements-completed: []

plan_head_before: 1a18c7ce7178fceb49c83d3130fbdbc80f5f6351
plan_head_after: eed68d8b548ac6047317a208528c19b991569074

actuals:
  tokens: 11556
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Confirm-menu shape for destructive steps: a menu step with the confirm and keep items, and a menu accepts only its own items, so the removal step cannot be reached without passing the confirmation"
    - "Presence cache keyed by instance id with a hard cap, status limited to online and offline, empty payload forgets; own id excluded from the count at read time"
    - "Removal choice stored as an entry option before removal because async_remove_entry runs after the unload and offers no dialog"

key-files:
  created:
    - tests/test_config_flow_delete.py
    - tests/test_hub_removal.py
  modified:
    - custom_components/mqtt_actions/config_flow.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/__init__.py
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_config_flow.py
    - tests/test_config_flow_select.py
    - tests/test_manager.py
    - tests/test_manager_select.py
    - tests/test_sync_owner.py
    - tests/test_translations.py

key-decisions:
  - "The generic Home Assistant subentry delete cannot be vetoed, so both deletion paths end in the same reconcile-driven tombstone sequence; the confirmation wording lives in this flow and in the README (Open Question 1 default)"
  - "D-16 'listing the instances as far as known' is met as a count of other instances seen online; there is no instance-name roster before Phase 4 (A11)"
  - "Hub removal keeps every device retained on the broker by default; deletion everywhere only when the hub option was set before removal; the local Store and every integration issue go in both modes (D-11)"
  - "The hub still has no reconfigure step; the choice is a plain OptionsFlow whose save runs the normal update listener and publishes nothing"
  - "The confirmation reports count 0 while the hub entry is not loaded, and deletion still works then"

patterns-established:
  - "Device flows share delete_device and delete_confirmed in _DeviceSubentryFlow; each type supplies only keep_device, which returns to its own menu"
  - "Removal functions take optional gateway and store_key keywords as test seams; production callers pass neither"

coverage:
  - id: D1
    description: "A device is deleted from its dialog only after an explicit confirmation naming the device and the number of other online instances; keep returns to the device menu and changes nothing; the edit form is unchanged under edit_device"
    requirement: SYN-06
    verification:
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_delete_confirmation_states_count_and_name"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_delete_confirmed_removes_subentry_and_aborts"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_keep_returns_to_the_menu_and_removes_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_switch_edit_device_form_behaves_as_before"
        status: pass
    human_judgment: false
  - id: D2
    description: "Instance presence from the availability wildcard counts only other online instances, forgets on an empty payload, ignores other payloads and cannot grow past the cap"
    requirement: SYN-06
    verification:
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_presence_counts_other_online_instances"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_presence_is_capped"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_own_instance_never_counts"
        status: pass
    human_judgment: false
  - id: D3
    description: "The generic Home Assistant delete ends in the same ordered clear publishes as the confirmed flow path, and the confirmation works while the entry is unloaded"
    requirement: SYN-06
    verification:
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_generic_delete_path_tombstones_the_same_topics"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_delete.py#test_confirmation_works_when_the_entry_is_not_loaded"
        status: pass
    human_judgment: false
  - id: D4
    description: "Removing the hub keeps every device retained by default, deletes everywhere only on the stored option, always removes Store and issues, and keep mode never touches MQTT"
    verification:
      - kind: unit
        ref: "tests/test_hub_removal.py#test_remove_with_default_keeps_everything_retained"
        status: pass
      - kind: unit
        ref: "tests/test_hub_removal.py#test_remove_with_delete_clears_everywhere"
        status: pass
      - kind: unit
        ref: "tests/test_hub_removal.py#test_keep_mode_needs_no_mqtt"
        status: pass
      - kind: unit
        ref: "tests/test_hub_removal.py#test_hub_has_options_flow_with_delete_choice"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every new flow step, abort reason, menu item and the hub option has English and German text with matching placeholders"
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_required_keys_present"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_delete_placeholders_are_the_ones_the_flow_supplies"
        status: pass
    human_judgment: false
  - id: D6
    description: "How the confirmation and hub option texts read and render in the real Home Assistant dialogs, the German phrasing, and that the generic Home Assistant delete dialog still bypasses the confirmation text"
    verification: []
    human_judgment: true
    rationale: "Dialog rendering and wording are UI and language judgments no test asserts; the generic dialog limit is a Home Assistant constraint recorded for the README and the manual UAT row of plan 03-07"

duration: 10 min
completed: 2026-10-01
status: complete
---

# Phase 3 Plan 03: Owner-Facing Delete and Hub Removal Summary

**Device delete needs an explicit all-instances confirmation that names the device and the count of other online instances (capped presence cache from the availability wildcard), and hub removal keeps devices retained by default and deletes them everywhere only when chosen in a hub options flow**

## Performance

- **Duration:** about 10 min (start time not recorded, estimated from the previous plan's completion)
- **Completed:** 2026-10-01
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto, all TDD)
- **Files modified:** 15 (2 created, 13 modified)

## Accomplishments

- Both device flows gained the D-16 confirmation. `delete_device` is a menu with `delete_confirmed` and `keep_device`, its description placeholders are the device title and the number of other instances seen online. A menu only accepts its own items, so `delete_confirmed` cannot be reached without passing the confirmation. Confirming removes the subentry, which runs the existing reconcile removal in the D-16 order (discovery, unsubscribe, config tombstone, state), and aborts with `device_deleted`. Keeping returns to the Switch reconfigure menu or the Select device menu and publishes nothing.
- The Switch reconfigure entry point is now a menu (`edit_device`, `delete_device`); the old form lives unchanged under the step id `edit_device`. The Select menu appends `delete_device` only in reconfigure mode, so creation flows are untouched.
- `SyncManager` subscribes the availability wildcard and keeps `instance id -> online|offline`. Only those two payloads count (strip, lower), an empty payload forgets the instance, everything else is ignored, the own id is excluded from `online_instance_count()`, and a new id beyond `MAX_TRACKED_INSTANCES = 256` is skipped with one log line (T-03-12). `instance_status()` is ready for plan 03-05.
- Hub removal no longer deletes silently. `HubOptionsFlow` stores `delete_devices_on_remove` (default off); `async_remove_entry` calls `async_remove_all_devices` only when it is set and otherwise `async_remove_local_state`, which removes the Store and every integration issue. Keep mode publishes nothing, so the `offline` availability from the unload stays and orphans show as unavailable. The hub still has no reconfigure step.
- English and German texts for the Switch reconfigure menu, `edit_device`, both `delete_device` confirmations, `device_deleted`, the Select menu item and the hub option; `delete_device` uses exactly `{name}` and `{count}` in both languages.

## Task Commits

1. **Task 1: Tracer, delete confirmation with instance count** - `7702436` (test, RED), `8eae01e` (feat, GREEN)
2. **Task 2: Hub removal keep or delete** - `60530e8` (test, RED), `dd26a4d` (feat, GREEN)
3. **Task 3: Delete, menu and options texts** - `34d218a` (test, RED), `eed68d8` (feat, GREEN)

**Plan metadata:** added by the docs commit that follows this file.

## TDD Gate Compliance

Every task has a `test(03-03)` commit before its `feat(03-03)` commit; no refactor commits. Tracer gate: Task 1's verify is automated only, so it was re-run end to end after the GREEN commit (full suite, Ruff check and format) and passed before expansion. RED evidence (`check tdd-red-evidence` was not run):

- Task 1: 19 tests failed on the intended causes (missing `Manager.online_instance_count`, missing `MAX_TRACKED_INSTANCES`, reconfigure returning a form instead of a menu, `next_step_id` not a valid option, menu without `delete_device`). The four existing Switch reconfigure tests and the Select menu assertion were updated to navigate the new menu and failed for the same reason.
- Task 2: six tests failed (options flow `UnknownHandler`, default removal publishing four empty payloads, offline availability replaced by an empty payload, keep mode calling MQTT, `gateway` keyword rejected). Already green at RED because they pin behavior the old code had: `test_remove_with_delete_clears_everywhere`, `test_delete_mode_survives_unavailable_mqtt`, `test_both_modes_remove_store_and_every_issue_prefix`. They fail under the new branching if it keeps the wrong side, and the keep-mode tests are the discriminating ones.
- Task 3: three tests failed (`test_required_keys_present` in both languages, `test_delete_placeholders_are_the_ones_the_flow_supplies`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] A fifth existing removal test needed the delete opt-in**
- **Found during:** Task 2 RED
- **Issue:** the plan names four existing tests that go through `hass.config_entries.async_remove`; `tests/test_sync_owner.py::test_hub_removal_path_clears_the_config_topic` asserts the config tombstones of a hub removal and would fail in keep mode.
- **Fix:** its hub entry carries `options={CONF_DELETE_DEVICES_ON_REMOVE: True}`, like the other four. The two issue-cleanup tests in the same file (`path == "hub"` cases) hold in both modes and were not changed.
- **Files modified:** `tests/test_sync_owner.py`
- **Commit:** `60530e8`

**2. [Rule 3 - Blocking] The option constant was added in the RED commit**
- **Found during:** Task 2 RED
- **Issue:** the new tests import `CONF_DELETE_DEVICES_ON_REMOVE`; a missing name is an import error, which is INVALID_RED, not a failing assertion for the behavior.
- **Fix:** the constant (no behavior) moved from the GREEN commit into the RED commit, and the tests reach `async_remove_all_devices` and `async_remove_local_state` as attributes of the `manager` module inside the test bodies, so the two seams that do not exist yet fail on the planned assertion and not at collection.
- **Files modified:** `custom_components/mqtt_actions/const.py`, `tests/test_hub_removal.py`
- **Commit:** `60530e8`

**3. [Rule 1 - Bug] Async fixtures cannot be requested with `getfixturevalue`**
- **Found during:** Task 1 RED
- **Issue:** a first draft parametrized the delete tests over fixture names and resolved them with `request.getfixturevalue`, which raised `Runner.run() cannot be called from a running event loop` for the async hub fixtures.
- **Fix:** one parametrized async fixture `device_hub` builds the hub with a Switch or a Select device and returns the entry with its subentry type.
- **Files modified:** `tests/test_config_flow_delete.py`
- **Commit:** `7702436`

---

**Total deviations:** 3 (2 Rule 3, 1 Rule 1). **Impact on plan:** no scope change, no existing assertion weakened.

## Issues Encountered

- The plan's acceptance wording for Task 3 (`grep -c delete_devices_on_remove`) is satisfied literally: 2 per file, equal in both languages.

## Known Stubs

None.

Open items by design:

- Presence comes from retained availability topics, so an instance that crashed without publishing `offline` keeps counting as online (the known limitation noted in `manager.py`, AVL-01 deferred). The count in the confirmation is therefore an upper bound.
- The generic Home Assistant subentry delete (websocket command and frontend dialog) cannot be vetoed and its text is not customizable (A4); the wording lives in this flow, in the README and in the manual UAT row of plan 03-07 (T-03-13, accepted).
- Requirement SYN-06 is declared by plans 03-02, 03-03 and 03-07 and already reads Complete in REQUIREMENTS.md since plan 03-02. This plan did not tick anything; the shared-ID gate would block it while 03-07 has no summary. The README wording and UAT row of 03-07 still belong to it.

## Threat Flags

None. The one new surface is the availability wildcard subscription (broker to presence cache), which is T-03-12 of the plan's threat model and is capped. T-03-11 (silent hub deletion) is mitigated by default keep; T-03-13 is accepted and documented.

## Next Phase Readiness

- Plan 03-05 can read `Manager.sync.instance_status(owner_id)` for the owner-liveness decisions.
- Needs user confirmation at review: `MAX_TRACKED_INSTANCES = 256`, the English and German confirmation and option wording, and that hub removal keeps devices by default.
- Plan 03-07 documents the generic-delete limit, the stale-online presence caveat and the keep-by-default hub removal in the README, and reconciles the `.claude/CLAUDE.md` "local opt-in flag" wording.

## Self-Check: PASSED

- Created files exist: `tests/test_config_flow_delete.py`, `tests/test_hub_removal.py` (FOUND)
- Commits exist: `7702436`, `8eae01e`, `60530e8`, `dd26a4d`, `34d218a`, `eed68d8` (FOUND); every `test(03-03)` commit precedes its `feat(03-03)` commit
- Acceptance: `grep -c` of the three delete steps in `config_flow.py` prints 4 (at least 3); `delete_devices_on_remove` count is 2 in `en.json` and 2 in `de.json`; `test_keep_returns_to_the_menu_and_removes_nothing` asserts no publish and unchanged `entry.subentries`; `test_remove_with_default_keeps_everything_retained` asserts no empty publish; `test_hub_flow_has_no_reconfigure_step` passes
- `uv run pytest -q` 651 passed; `uv run ruff check .` and `uv run ruff format --check .` clean
