---
phase: 04-operations-recovery-and-release
plan: 09
subsystem: services
tags: [home-assistant, services, import, admin-only, supports-response, security, mqtt]

requires:
  - phase: 04-operations-recovery-and-release
    provides: service layer, resolve_device and the export document with its private file rules (plan 04-08), parse_document and the static denylist (phase 3)
provides:
  - mqtt_actions.import_devices service (admin only, optional response) that turns an export into new owned devices, all or nothing
  - portability.parse_export, prepare_import, PreparedDevice, subentry_payload (reused by the adoption plan), parse_import_text and read_import
  - MAX_IMPORT_DEVICES and MAX_IMPORT_BYTES caps
  - translated import_rejected error with the placeholders index and reason, plus bad_file_name, file_unreadable and import_needs_exactly_one_source
affects: [04-11 adoption (reuses subentry_payload), 04-13 docs (operations page: import trust note, T-04-39)]

actuals:
  tokens: 13146
  tasks: 2
  commits: 4
plan_head_before: 2fc3f2c228d5ecb492080d7ff718fd14b52279e2
plan_head_after: 52588fda92b76307e16b7250d54e2478183dc9b9

tech-stack:
  added: []
  patterns:
    - "An import item becomes a throw-away broker document (item overlaid with this instance's bookkeeping) and runs through parse_document, the structure check and the static denylist before deep validation"
    - "Rejections carry a fixed reason code and a 1-based position and never content; the log carries the same two values"
    - "Files are read by bare name from a real private directory with a no-follow open, a regular-file check and the size checked on the descriptor"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/portability.py
    - custom_components/mqtt_actions/services.py
    - custom_components/mqtt_actions/services.yaml
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_portability.py
    - tests/test_services.py
    - tests/test_translations.py

key-decisions:
  - "A TOO_LARGE rejection of an item by parse_document is reported as the reason too_large (with the position); every other document rejection is invalid_device"
  - "Any import file that cannot be opened, is not a regular file, sits in a symlinked directory or is not strict UTF-8 is file_unreadable, so an error never tells a probe which file exists"
  - "The size of a data source is the UTF-8 length of its JSON text; data that is not plain JSON is bad_format"
  - "The import_rejected message lists every reason code with a short meaning, because the placeholder is the code"
  - "Deep validation is the same call as the UI flows (async_validate_actions); it does not check that a service exists, so an unknown service name is accepted and an unresolved device action is the deep failure"

patterns-established:
  - "PortabilityError carries reason and an optional index; the service maps file reasons to their own translation keys and all other reasons to import_rejected"
  - "Pure pipeline tests (text parser, envelope, preparation) run without Home Assistant; the service tests assert the all-or-nothing and no-echo rules end to end"

requirements-completed: [SYN-08]

coverage:
  - id: D1
    description: "An export (JSON object) is imported as new owned devices with new uuids, this instance as owner and revision 1; they publish like devices made in the UI and a round trip restores equal content hashes"
    requirement: SYN-08
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_import_creates_owned_devices_that_publish"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_export_import_round_trip"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_prepare_import_assigns_new_ids_and_owner"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_parse_export_accepts_the_export_envelope"
        status: pass
    human_judgment: false
  - id: D2
    description: "Forged owner, device id, rev, hash and schema version inside an item are ignored"
    requirement: SYN-08
    verification:
      - kind: unit
        ref: "tests/test_portability.py#test_forged_bookkeeping_keys_are_ignored"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every item passes the strict broker-document path, the structure check, the static denylist and deep validation; hostile items are refused with a fixed reason code and a position"
    requirement: SYN-08
    verification:
      - kind: unit
        ref: "tests/test_portability.py#test_parse_and_prepare_reject_hostile_input"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_denied_services_are_rejected"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_a_templated_service_name_is_accepted"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_deep_validation_rejects_an_unresolved_device_action"
        status: pass
    human_judgment: false
  - id: D4
    description: "The import is all or nothing: a bad item rejects the call with its position and nothing is created or published"
    requirement: SYN-08
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_import_is_all_or_nothing"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_import_envelope_problem_has_no_position"
        status: pass
    human_judgment: false
  - id: D5
    description: "Error texts and logs of a rejected import never contain action content"
    requirement: SYN-08
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_import_errors_never_echo_content"
        status: pass
    human_judgment: false
  - id: D6
    description: "Imports are bounded (100 devices, 4 MiB, 256 KiB per item) and the file source reads only a regular file by bare name from the private directory, never through a symlink"
    requirement: SYN-08
    verification:
      - kind: unit
        ref: "tests/test_portability.py#test_read_import_refuses_what_is_not_a_plain_file"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_read_import_refuses_a_file_above_the_cap_before_reading"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_read_import_refuses_a_bad_name"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_read_import_refuses_a_symlinked_directory"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_import_from_file_and_source_rules"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_import_file_problems_have_their_own_errors"
        status: pass
    human_judgment: false
  - id: D7
    description: "The import is admin only and has translated service and error texts in English and German"
    requirement: SYN-08
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_import_is_admin_only"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_required_import_keys_exist_in_both_languages"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_required_import_error_keys_exist_in_both_languages"
        status: pass
    human_judgment: false
  - id: D8
    description: "In Developer Tools, Actions, import_devices with an earlier export (as data, then as a file name) shows the devices on the integration page and on the other instances as mirrors that ask for approval"
    verification: []
    human_judgment: true
    rationale: "The plan's human-check: the real UI call and the appearance of mirrors that ask for approval on other instances are not asserted by one automated test"

duration: 8min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 09: Import service Summary

**mqtt_actions.import_devices restores an export as new owned devices (new uuid, this instance as owner, revision 1) through the strict broker-document path, a static denylist check and deep action validation, all or nothing, with 100-device and 4 MiB caps and a private no-follow file source**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-02T08:43:32Z
- **Completed:** 2026-10-02T08:51:33Z
- **Tasks:** 2 (tracer plus hardening)
- **Files modified:** 9 (no new files)

## Accomplishments

- `parse_export` checks the envelope (`format`, `export_version` not above 1, `devices` list of at most 100). `prepare_import` turns every item into a throw-away document (the item overlaid with this instance's `schema_version`, a fresh uuid4, owner, owner name and rev 1, so forged keys lose) and runs it through `parse_document`, `validate_spec_structure` and the static denylist (`analyze_spec(...).denied`). A templated service name is accepted.
- `import_devices` (admin only, optional response) deep-validates every trigger's actions with `async_validate_actions` and creates the subentries only after every item passed. The update listener reconciles, so the manager publishes document and discovery of each new device. The response is `{"imported": [{"index", "uuid", "name"}]}`.
- Rejections raise `import_rejected` with the placeholders `index` (1-based, or a dash for an envelope problem) and `reason`; the log carries the same two values only.
- Bounds: 100 devices, 4 MiB for the whole JSON (data source and file), 256 KiB per item. `read_import` reads by bare name from `<config>/mqtt_actions/` with `O_NOFOLLOW`, a regular-file check and the size checked on the descriptor before a bounded read, refuses a symlinked directory, and decodes strict UTF-8.
- Exactly one of `data` and `file_name` is accepted; a bad name, an unreadable file and a source mistake have their own translated errors, in English and German.

## Task Commits

1. **Task 1: Tracer - import a JSON export** - RED `3b65310` (test), GREEN `fbac103` (feat)
2. **Task 2: Hostile files, caps, the private file source and the all-or-nothing rule** - RED `47cfed6` (test), GREEN `52588fd` (feat)

**Plan metadata:** recorded in the docs commits that follow this summary.

Tracer gate: the tracer's automated verify (full suite 1017 passed, Ruff check and format) passed after Task 1 and its `<verify>` carries no human check, so the run continued to Task 2 ("Tracer verified end-to-end - expanding").

## Files Created/Modified

- `custom_components/mqtt_actions/portability.py` - `PortabilityError.index`, `PreparedDevice`, `parse_export`, `parse_import_text`, `read_import`, `subentry_payload`, `prepare_import`
- `custom_components/mqtt_actions/services.py` - `IMPORT_SCHEMA`, `_async_handle_import`, `_import_rejected`, `_checked_size`, deep validation of each prepared device
- `custom_components/mqtt_actions/services.yaml` - `import_devices` (object selector for `data`, text for `file_name`)
- `custom_components/mqtt_actions/const.py` - `MAX_IMPORT_DEVICES`, `MAX_IMPORT_BYTES`
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - `services.import_devices.*`, `exceptions.import_rejected`, `import_needs_exactly_one_source`, `file_unreadable`
- `tests/test_portability.py`, `tests/test_services.py`, `tests/test_translations.py` - new and extended tests (45 new test cases in total)

## Decisions Made

See `key-decisions` above. Creating the subentries is not transactional (as the plan documents): a failure halfway would leave the earlier devices. `async_add_subentry` with a fresh uuid does not fail in practice.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Plan premise wrong] Deep validation does not reject an unknown service name**
- **Found during:** Task 2 (RED tests)
- **Issue:** The plan's `test_deep_validation_rejects_an_unknown_service` assumes `async_validate_actions` refuses a service that does not exist on this instance. Core's `async_validate_action_config` never resolves service names (a provider may load later); it resolves device actions, conditions and triggers.
- **Fix:** The test is `test_deep_validation_rejects_an_unresolved_device_action`: a device action of an unknown integration is rejected with `invalid_actions` and its position. No service-existence check was added, because it would reject legitimate items and the UI flows do not do it either.
- **Files modified:** `tests/test_services.py`
- **Committed in:** `47cfed6`

**2. [Rule 1 - Plan premise wrong] The oddly-written service name case of the denylist test**
- **Found during:** Task 2 (RED tests)
- **Issue:** A name such as `" Homeassistant.Restart "` never reaches the denylist walk: the script schema already refuses it as invalid structure (`invalid_actions`), which is the safer outcome.
- **Fix:** The case was removed from `test_denied_services_are_rejected`; denied domain, denied service and nesting inside a `choose` remain.
- **Files modified:** `tests/test_portability.py`
- **Committed in:** `47cfed6`

**3. [Rule 2 - Missing critical] Additional hardening beyond the plan text**
- A symlinked `mqtt_actions` directory is refused for reading as it is for writing (`test_read_import_refuses_a_symlinked_directory`); the open uses `O_NONBLOCK` so a FIFO planted under the name cannot block the executor (the regular-file check then refuses it); data that is not plain JSON (non-string keys, NaN) is `bad_format` or `invalid_device` instead of an untranslated exception; the read is bounded (`MAX_IMPORT_BYTES + 1`) in case the file grows after the size check.
- **Committed in:** `fbac103`, `52588fd`

**4. [Test fix] Helper refactor slip in the Task 1 GREEN commit**
- `test_parse_export_accepts_the_export_envelope` called `_envelope([])` after the helper became keyword-only; corrected to `_envelope()` in the `fbac103` commit together with the implementation (the RED run had failed earlier on the missing function, so the RED evidence is unaffected).

---

**Total deviations:** 4 (2 Rule 1 plan premises, 1 Rule 2 hardening, 1 test slip)
**Impact on plan:** No scope creep; the two plan premises were checked against core's behavior and the safer outcome already held.

## TDD Gate Compliance

Both tasks have a `test(04-09)` commit before the `feat(04-09)` commit. Task 1 RED failed on `AttributeError` for the missing portability functions, `ServiceNotFound` for the service and missing translation keys. Task 2 RED failed on the missing `read_import` and `parse_import_text`, the missing source rule (the call was accepted as `import_rejected`/`bad_format`), the missing item cap (DID NOT RAISE) and missing translation keys. Several Task 2 cases (hostile items, denied services, all-or-nothing, no echo) already passed after Task 1, because Task 1's strict path covers them; they stay as regression tests for the plan's prohibitions.

## Issues Encountered

- Ruff line-length hits in the new test comments and one docstring; fixed.
- The known flaky `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` did not fail in the full runs (1017 and 1056 passed) and passed twice when run alone.

## Authentication Gates

None.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-04-36 to T-04-38 and T-04-40 to T-04-41 are mitigated and tested. T-04-39 keeps its residual risk (an administrator imports content they did not read); the operations page of plan 04-13 should state it.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `subentry_payload(content, device_id)` is in place for the adoption plan (04-11).
- The docs plan (04-13) should describe the import service, its all-or-nothing rule, the denylist for imports (a legitimate item that calls a denied service has to be created in the UI) and the residual risk of T-04-39.
- Human check still open: call `mqtt_actions.import_devices` from Developer Tools with an earlier export as data and as a file name, then look at the integration page and at a second instance.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*

## Self-Check: PASSED

Files exist, the four commits (`3b65310`, `fbac103`, `47cfed6`, `52588fd`) exist, `uv run pytest tests -q` (1056 passed), `uv run ruff check .` and `uv run ruff format --check .` pass; the acceptance greps (`async_add_subentry` count 1, `def read_import` count 1) and the test-before-feat order hold.
