---
phase: 02-select-devices-and-reliable-execution
plan: 05
subsystem: config-flow
tags: [home-assistant, config-flow, subentries, select, menu-loop, translations, readme, tdd]

requires:
  - phase: 02-select-devices-and-reliable-execution
    provides: DeviceSpec and Select runtime (plan 02-01), run modes (02-02), test buttons (02-03), circuit breaker (02-04)
provides:
  - SelectSubentryFlow, a menu loop over an in-memory draft (settings, add, edit, remove with confirmation, done) for creating and reconfiguring Select devices
  - Shared _DeviceSubentryFlow base with a generalized warn-then-confirm action check and the run mode and breaker settings helpers
  - validate_option and validate_breaker, pure UI validation in model.py
  - Run mode and circuit breaker fields in the Switch flow, with Phase 1 data prefilling the defaults
  - English and German texts for every new step, menu entry, error and the run mode selector
  - README sections for Select devices, run mode, test buttons, circuit breaker and the test topic as a second trigger source
affects: [phase 3 trust gate and multi-instance test fan-out, phase 4 release notes]

actuals:
  tokens: 30133
  tasks: 3
  commits: 6

plan_head_before: a46d985a814be9fb3ade81d13ec5f3ca8a8e4062
plan_head_after: 4d4813286a1c1ecf9b700ee399f0cbc722c49637

tech-stack:
  added: []
  patterns:
    - "Menu loop flow: a menu cannot show errors, so invalid states are unreachable (Done hidden below two options, Remove hidden at two, Add hidden at 50) and validation lives in the form steps"
    - "The flow edits a copy.deepcopy draft and commits once through async_create_entry or async_update_and_abort, so stored subentry data is never mutated in place"
    - "Number selector without min and max, range checked by a pure validator, so an out-of-range value returns a translated field error instead of a schema failure"

key-files:
  created:
    - tests/test_config_flow_select.py
  modified:
    - custom_components/mqtt_actions/config_flow.py
    - custom_components/mqtt_actions/model.py
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - README.md
    - tests/test_config_flow.py
    - tests/test_model.py
    - tests/test_translations.py
    - tests/test_repo_structure.py

key-decisions:
  - "The number selectors for the breaker carry no min and max: core rejects an out-of-range value as invalid data before the flow runs, and the plan requires translated errors on the fields; validate_breaker owns the 1..100 and 1..3600 ranges and also rejects non-integral values"
  - "A whitespace-only StateValue reports state_value_required, not state_value_invalid: it is blank, and the required message is the accurate one"
  - "The edit and remove entries are part of the shared menu, so they are also offered while creating a device once options exist (remove only above two options)"
  - "Done in a reconfigure flow replaces the stored data and re-injects the immutable device id; a save that changes nothing leaves the data equal, so the update is a no-op and releases no breaker (A12)"

patterns-established:
  - "Flow tests drive menus with async_configure(flow_id, {next_step_id: step}) and read menu_options, description_placeholders and suggested values from the result"

requirements-completed: [DEV-03, DEV-04, DEV-06, STA-06]

coverage:
  - id: D1
    description: "A user can create a Select device: a settings form leads to an option menu, Done appears from two options, and the created device holds a uuid4 device id equal to its unique id, the options in creation order and int breaker settings; its actions run after the reconcile"
    requirement: DEV-03
    verification:
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_tracer_select_flow_creates_two_option_device_that_runs_actions"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_menu_visibility"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_nothing_is_stored_before_done"
        status: pass
    human_judgment: false
  - id: D2
    description: "Option validation follows D-04: at least two options, StateValue and friendly name rules on the field, none reserved, duplicates ignoring case, friendly name stored stripped, invalid actions and device_id warning per option"
    requirement: DEV-03
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_validate_option_table"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_add_option_validation"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_add_option_invalid_actions_and_device_id_warning"
        status: pass
    human_judgment: false
  - id: D3
    description: "A Select device can be reconfigured from a menu: edit the friendly name and actions with the StateValue locked, add options at the end, remove options after a confirmation while two remain, and nothing is stored or mutated before Done"
    requirement: DEV-04
    verification:
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_edit_option_form_has_no_state_value_field"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_edit_option_changes_friendly_name_and_actions_only"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_remove_option_needs_confirmation"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_removed_option_payload_is_unknown_afterwards"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_flow_never_mutates_stored_data_before_done"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every device flow offers run mode and circuit breaker limits with integer coercion and range validation; old Switch data prefills serial, 5 and 10"
    requirement: DEV-06
    verification:
      - kind: integration
        ref: "tests/test_config_flow.py#test_switch_flow_stores_run_mode_and_breaker_settings"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow.py#test_switch_flow_rejects_out_of_range_breaker_values"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow.py#test_switch_reconfigure_prefills_defaults_for_old_data"
        status: pass
      - kind: integration
        ref: "tests/test_config_flow_select.py#test_settings_from_the_menu_update_run_mode_and_breaker"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_validate_breaker_boundaries"
        status: pass
    human_judgment: false
  - id: D5
    description: "All new strings exist in English and German with matching keys and variables, hassfest accepts the translation schema, and the README documents Select devices, run mode, test buttons, the circuit breaker and the test topic"
    requirement: STA-06
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_required_keys_present"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_en_and_de_have_identical_keys"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_readme_documents_phase2_behavior"
        status: pass
      - kind: other
        ref: "docker run ghcr.io/home-assistant/hassfest (exit 0, Invalid integrations: 0)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The menu loop and the action selector inside repeated option steps render and read well in the real Home Assistant dialog in English and German, and the texts explain the unknown state after renaming or removing the selected option"
    requirement: DEV-03
    verification: []
    human_judgment: true
    rationale: "Dialog rendering and the clarity of the wording cannot run in the test harness; the plan lists it as the manual end-of-phase check"

duration: 12min
completed: 2026-09-29
status: complete
---

# Phase 2 Plan 05: Select Device Flow and Documentation Summary

**Menu-loop subentry flow to create and reconfigure Select devices (options with locked StateValue, confirmed removal, nothing stored until Done), run mode and circuit breaker fields for Switch and Select, full English and German texts and a README that documents Phase 2 and its limits**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-29T18:38:00Z
- **Completed:** 2026-09-29T18:50:00Z
- **Tasks:** 3 (1 tracer, 2 auto, all TDD)
- **Files modified:** 12 (1 created, 11 modified)

## Accomplishments

- DEV-03: `SelectSubentryFlow` starts with a settings form (name, run on startup, run mode, breaker limits) and continues in a menu. Add is hidden at 50 options, Done is hidden below two, and the device is created once with a fresh uuid4 that equals the subentry unique id. The tracer test creates a two-option device through the flow, fires a live payload and checks that only that option's actions run and that the discovery `options` list holds the two friendly names.
- DEV-04: reconfigure loads a `copy.deepcopy` draft and opens the same menu. The edit form has exactly the fields `friendly_name` and `actions` (a test asserts the field set and that an extra `state_value` key is rejected as invalid data), options are appended at the end, and removal goes through a confirmation menu and is not offered at two options. `test_flow_never_mutates_stored_data_before_done` proves the stored data is equal to the original after every kind of edit until Done.
- DEV-06 and STA-06 in the UI: a shared base provides the run mode dropdown and the two number fields. Values are validated with `validate_breaker` and stored as ints; the Switch flow uses the same helpers, and a Phase 1 Switch without the keys prefills serial, 5 and 10 and saves them without a migration step.
- `validate_option` and `validate_breaker` are pure functions with table tests: printable text, 64 characters, no edge whitespace in the StateValue, unique ignoring case, `none` reserved, ranges 1..100 and 1..3600, and an `editing` mode that skips the locked StateValue.
- English and German texts for every step, menu entry, error and the run mode selector, with matching keys and variables; the discovery Repairs issue now speaks of entities instead of switch entities. The README documents Select devices, run mode, test buttons, the circuit breaker (default 5 runs in 10 seconds, how to release, restart behavior), the test topic in the contract and as a second trigger source for broker ACLs, and the limitation that a test press fans out to every subscribing instance.

## Task Commits

Each task was committed atomically, RED before GREEN:

1. **Task 1: Tracer, the UI flow creates a two-option Select device that runs its options' actions** - `63b85b9` (test), `3a80974` (feat)
2. **Task 2: Reconfigure a Select device, edit, add and remove options** - `2b70455` (test), `9c2f15b` (feat)
3. **Task 3: Run mode and breaker limits in the Switch flow, translations parity, README** - `946cd9c` (test), `4d48132` (feat)

**Plan metadata:** the docs commit that follows this summary.

## Files Created/Modified

- `custom_components/mqtt_actions/config_flow.py` - `_DeviceSubentryFlow` base, `SelectSubentryFlow` with the menu, add, edit, remove, settings and done steps, Switch flow with the shared settings
- `custom_components/mqtt_actions/model.py` - `validate_option`, `validate_breaker`
- `custom_components/mqtt_actions/const.py` - `MIN_OPTIONS`, `MAX_OPTIONS`, `MAX_TEXT_LENGTH`, `BREAKER_MAX_RUNS_LIMIT`, `BREAKER_WINDOW_LIMIT`
- `custom_components/mqtt_actions/manager.py` - the discovery-disabled log line names entities
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - `config_subentries.select.*`, new Switch fields and errors, `selector.run_mode`, reworded discovery issue
- `README.md` - Select devices, run mode, test buttons, circuit breaker, contract, limitations and security updates
- `tests/test_config_flow_select.py` (new), `tests/test_config_flow.py`, `tests/test_model.py`, `tests/test_translations.py`, `tests/test_repo_structure.py`

## Decisions Made

- Breaker number selectors have no min and max, so that an out-of-range number returns `breaker_max_runs_range` or `breaker_window_range` on its field. With min and max set, core raises invalid data before the flow runs and the user would see no translated message. The ranges live in one pure validator and are stated in the field descriptions.
- A whitespace-only StateValue is reported as required rather than invalid.
- The menu is shared between create and reconfigure, so edit and remove are also available while creating a device that already has options.
- No separate release notes file exists in the repository, so the README carries the upgrade notes (test buttons on existing Switch devices, the test topic, the release rule of the breaker, the input limits).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Breaker number selectors created without min and max**
- **Found during:** Task 1 (settings form)
- **Issue:** The plan asks for a number selector with min and max and, in the same task, for range errors on the fields for 0, 101 and 3601. Core validates a number selector before the flow step runs, so out-of-range input would raise invalid data and the specified field errors could never appear.
- **Fix:** No min and max on the selectors; `validate_breaker` enforces 1..100 and 1..3600 (and whole numbers) and returns translated field errors. The range is stated in the field descriptions in both languages.
- **Files modified:** `custom_components/mqtt_actions/config_flow.py`, `custom_components/mqtt_actions/model.py`
- **Verification:** `test_select_flow_settings_validation`, `test_switch_flow_rejects_out_of_range_breaker_values`, `test_validate_breaker_boundaries`
- **Commit:** `3a80974`

**Total deviations:** 1 auto-fixed (1 bug in the plan's own requirements). **Impact:** the frontend shows no numeric bounds on the two fields; the bounds appear in the description and as an error on submit.

## Auth Gates

None.

## Issues Encountered

None. Full suite 426 passed, broker tier 4 passed (mosquitto installed), Ruff check and format clean, hassfest exit 0 after each task.

## Known Stubs

None.

## TDD Gate Compliance

All three tasks have a `test(02-05)` commit before the matching `feat(02-05)` commit. The RED runs failed on behavior: the flow did not support the `select` subentry or the `reconfigure` step, `validate_option` and `validate_breaker` did not exist, the Switch schema rejected the new keys, and the README and translations lacked the keys and phrases.

## Threat Flags

None. The new surface (Select flow input, test topic) is covered by the plan's threat model; T-02-19 to T-02-24 are mitigated as planned (pure validation, option and text caps, int coercion with range checks, capped errors that never echo action data, per-option device_id warning, deep-copied draft).

## Manual Verification Left for the End of the Phase

The menu loop, the action selector inside repeated option steps and the German and English wording need a look in the real Home Assistant dialog (D6 above). On a real broker: select an option in the UI, publish with `mosquitto_pub`, trip the breaker with a self-toggling action and release it by reload.

## Next Phase Readiness

Phase 2 is complete. Phase 3 inherits two documented constraints: a test press fans out to every instance subscribed to the test topic, and the broker ACL must cover the test topic next to the state topic.

## Self-Check: PASSED

- Files found: `tests/test_config_flow_select.py`, `custom_components/mqtt_actions/config_flow.py`, `custom_components/mqtt_actions/model.py`, `README.md`
- Commits found: `63b85b9`, `3a80974`, `2b70455`, `9c2f15b`, `946cd9c`, `4d48132`
- Acceptance: tracer test collected and passing, full suite 426 passed, broker tier 4 passed, hassfest exit 0, README states the default of 5 runs in 10 seconds
