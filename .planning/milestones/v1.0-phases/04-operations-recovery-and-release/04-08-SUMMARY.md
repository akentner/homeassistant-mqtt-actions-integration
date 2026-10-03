---
phase: 04-operations-recovery-and-release
plan: 08
subsystem: services
tags: [home-assistant, services, admin-only, export, supports-response, hassfest, mqtt]

requires:
  - phase: 04-operations-recovery-and-release
    provides: Manager.async_resync with its cooldown (plan 04-04), companion devices of owned devices and mirrors (plans 04-05, 04-06)
provides:
  - services layer registered once in async_setup behind a config-entry-only CONFIG_SCHEMA, admin only, optional response
  - mqtt_actions.resync service on top of the hub button's manager method, translated errors for the cooldown and for an unloaded entry
  - resolve_device mapping the registry id of a companion device to the device uuid (hub, foreign and unknown devices refused)
  - mqtt_actions.export_devices service returning the export as the response and optionally writing it to a private file
  - portability module (build_export, export_file_path, write_export) with the file-name pattern, 0700 directory, 0600 file, atomic replace and symlink refusal
affects: [04-09 import and adopt services, 04-10 re-trigger service, 04-13 docs]

actuals:
  tokens: 11186
  tasks: 2
  commits: 4
plan_head_before: c25119495dc61c1a83e4367290e2a47d822456ce
plan_head_after: 7a3c405fbbfb69ac028364ff5f696a02a32955f9

tech-stack:
  added: []
  patterns:
    - "Services are registered in async_setup with async_register_admin_service; handlers look up the loaded manager at call time through async_get_loaded_manager"
    - "A device named by a service field is a Home Assistant device selected with a device selector (field device_id) and mapped to the uuid through the (mqtt_actions, uuid) identifier"
    - "User-supplied file names reach the disk only as a bare name matching a full-match pattern below a fixed private directory"

key-files:
  created:
    - custom_components/mqtt_actions/services.py
    - custom_components/mqtt_actions/services.yaml
    - custom_components/mqtt_actions/portability.py
    - tests/test_services.py
    - tests/test_portability.py
  modified:
    - custom_components/mqtt_actions/__init__.py
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_translations.py

key-decisions:
  - "A resync that returns False on a manager that is not running raises not_loaded; on a running manager it raises resync_throttled"
  - "Export file errors other than a bad name (symlink, foreign or non-private directory, OS errors) raise HomeAssistantError export_write_failed and log only the reason code or the error class, never the file name or content"
  - "The export file text is json.dumps(document, indent=2, ensure_ascii=False) plus a newline; the response holds the same document"
  - "The export device selection is deduplicated by uuid, keeping the order of the selection"
  - "The export directory is refused when it is a symlink, not a directory, or not ours and not 0700; an own directory with another mode is closed to 0700"

patterns-established:
  - "Tests that write files override hass_config_dir with hass_tmp_config_dir so nothing lands in the installed PHACC package"
  - "Admin-only services are tested with hass_read_only_user (Unauthorized, nothing published or written) and hass_admin_user"

requirements-completed: [DSC-04, SYN-08]

coverage:
  - id: D1
    description: "Services are registered once in async_setup (not the entry setup) behind CONFIG_SCHEMA, survive an unload, and are admin only"
    requirement: DSC-04
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_services_are_registered_at_setup_not_at_entry_setup"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_resync_service_is_admin_only"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_export_is_admin_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "The resync service republishes documents, discovery and online in the Phase 3 order, answers resynced, and a repeat inside the cooldown or an unloaded entry raises a translated error"
    requirement: DSC-04
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_resync_service_republishes_in_the_phase_3_order"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_resync_service_throttled_raises_a_translated_error"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_service_without_a_loaded_entry_raises_not_loaded"
        status: pass
    human_judgment: false
  - id: D3
    description: "The device_id field resolves a companion device to the uuid and refuses the hub device, unknown and foreign devices and, for export, a mirror"
    requirement: SYN-08
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_resolve_device_maps_the_companion_device_to_the_uuid"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_export_refuses_a_mirror_and_the_hub_device"
        status: pass
    human_judgment: false
  - id: D4
    description: "export_devices returns the owned devices (all or a selection) as the response without ids, owner, rev or hash, and can write them to a private file"
    requirement: SYN-08
    verification:
      - kind: unit
        ref: "tests/test_portability.py#test_build_export_has_format_version_and_content_only"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_export_returns_all_owned_devices_as_a_response"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_export_selection_by_device"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_export_writes_a_file_in_the_private_directory"
        status: pass
    human_judgment: false
  - id: D5
    description: "An export file name never leaves the private directory: bare name pattern, 0700 directory, 0600 file, atomic replace, symlink refused"
    requirement: SYN-08
    verification:
      - kind: unit
        ref: "tests/test_portability.py#test_export_file_name_rules"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_write_export_creates_a_private_file"
        status: pass
      - kind: unit
        ref: "tests/test_portability.py#test_write_export_refuses_a_symlink"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_export_bad_file_name_is_rejected"
        status: pass
    human_judgment: false
  - id: D6
    description: "In Developer Tools, Actions, export_devices shows the response and a given file name creates the file under mqtt_actions/ of the configuration directory, not reachable below /local/"
    verification: []
    human_judgment: true
    rationale: "The plan's human-check: real UI call and the web-server reachability of the directory are not asserted by an automated test (the hassfest and services.yaml loading are covered by tests/test_services.py#test_services_yaml_describes_both_services)"

duration: 7min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 08: Service layer, resync and export Summary

**Admin-only services registered once in async_setup (resync on the hub button's manager method, export_devices returning the id-free export or writing it to a 0600 file in a 0700 mqtt_actions directory), with a device_id selector field resolved safely to the device uuid**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-02T08:33:58Z
- **Completed:** 2026-10-02T08:41:00Z
- **Tasks:** 2 (tracer plus export)
- **Files modified:** 10 (3 created source files, 2 created test files)

## Accomplishments

- `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)` and `async_setup` register the services once; the entry setup registers none and the services survive an unload. Every service goes through `async_register_admin_service` with `SupportsResponse.OPTIONAL`.
- `resync` calls `Manager.async_resync` (same method as the hub button, Phase 3 publish order) and answers `{"resynced": true}`; a repeat inside `RESYNC_MIN_INTERVAL_SECONDS` raises `resync_throttled`, a missing loaded entry raises `not_loaded`.
- `resolve_device` maps the registry id of a companion device to the uuid via the `(mqtt_actions, uuid)` identifier; the hub device (entry id as identifier value), devices of other integrations and unknown ids are refused, and `owned_only` refuses mirrors.
- `export_devices` returns `{"export": {"format": "mqtt_actions_export", "export_version": 1, "devices": [...]}, "file": ...}` for all owned devices or a selection; the content is `build_content` of each spec and carries no device id, owner, rev or hash.
- A file name writes to `<config>/mqtt_actions/<name>` only: full-match pattern, directory 0700 (an own, too open directory is closed), file 0600 via `mkstemp` plus `os.replace`, symlink target or directory refused.
- Service, field and error texts in English and natural German; tests extended with the new required keys.

## Task Commits

1. **Task 1: Tracer - service layer with the resync service**: RED `f38f0a8` (test), GREEN `bf7661a` (feat)
2. **Task 2: Export service with a private file**: RED `94ca17d` (test), GREEN `7a3c405` (feat)

**Plan metadata:** recorded in the docs commit that follows this summary.

Tracer gate: the tracer's automated verify (full suite, Ruff check and format) was re-run after Task 1 and passed before the expansion task ("Tracer verified end-to-end, expanding").

## Files Created/Modified

- `custom_components/mqtt_actions/services.py` - `async_setup_services`, `async_get_loaded_manager`, `resolve_device`, resync and export handlers and schemas
- `custom_components/mqtt_actions/portability.py` - `PortabilityError`, `build_export`, `export_file_path`, `write_export`; no Home Assistant import
- `custom_components/mqtt_actions/services.yaml` - `resync` and `export_devices` (device selector filtered to this integration, text field)
- `custom_components/mqtt_actions/__init__.py` - `CONFIG_SCHEMA` and `async_setup`
- `custom_components/mqtt_actions/const.py` - `SERVICE_RESYNC`, `SERVICE_EXPORT_DEVICES`, `SERVICE_IMPORT_DEVICES`, `EXPORT_FORMAT`, `EXPORT_VERSION`, `EXPORT_DIRECTORY`
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - `services.*` and `exceptions.*`
- `tests/test_services.py`, `tests/test_portability.py`, `tests/test_translations.py` - new and extended tests

## Decisions Made

See `key-decisions` above. The file-name rule is the plan's pattern `[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.json`, which counts the 64 characters before `.json`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Translated error for other export-file failures**
- **Found during:** Task 2
- **Issue:** The plan maps only the name rules to `bad_file_name`. A symlink target, a symlinked or foreign directory or an OS error would surface as an untranslated exception (and a symlink is not a bad name).
- **Fix:** Added the translation key `exceptions.export_write_failed` (en and de) and raise `HomeAssistantError` with it for those cases; the log carries only the reason code or error class, never the file name or content.
- **Files modified:** `custom_components/mqtt_actions/services.py`, both translation files, `tests/test_translations.py`, `tests/test_services.py` (`test_export_write_failure_is_a_translated_error`)
- **Verification:** the symlink test passes and the linked file is unchanged
- **Committed in:** `7a3c405`

**2. [Rule 3 - Blocking, ordering] `export_not_owned` and the service constants arrive earlier than planned**
- **Found during:** Task 1 and Task 2 RED commits
- **Issue:** The Task 1 resolve test requires that `owned_only` refuses a mirror, so `export_not_owned` (listed under Task 2) is already used in Task 1; and the RED tests must collect, so the `const.py` names were added in the RED commits instead of GREEN. The `test_portability.py` module still fails at collection in RED because `portability.py` did not exist, as the plan states.
- **Fix:** `export_not_owned` text added in the Task 1 GREEN commit with the other exception texts; constants added in the RED commits.
- **Files modified:** `custom_components/mqtt_actions/const.py`, translation files
- **Committed in:** `f38f0a8`, `94ca17d`, `bf7661a`

**3. [Rule 2 - Missing critical] Additional tests**
- `test_write_export_refuses_a_symlinked_directory`, `test_export_file_name_accepts`, `test_build_export_of_nothing_is_an_empty_list` and `test_services_yaml_describes_both_services` were added to pin the directory-symlink refusal, the accepted names, the empty export and the validity of `services.yaml`.

---

**Total deviations:** 3 (2 Rule 2, 1 Rule 3 ordering)
**Impact on plan:** No scope creep; the extra error key is a correctness requirement of the file handling.

## Issues Encountered

- Ruff (`ASYNC240`, `EM101`, `SIM105`, `TC003`) flagged blocking Path calls in async tests and string literals in exceptions; resolved with sync helpers and reason-code constants.
- The known flaky `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` did not fail in the two full runs (1008 passed).

## Authentication Gates

None.

## Known Stubs

None. `SERVICE_IMPORT_DEVICES` is defined for plan 04-09 and not yet registered; this is planned.

## Threat Flags

None beyond the plan's threat model (T-04-31 to T-04-35 are mitigated by the admin-only registration, the file-name pattern and the symlink refusal, the 0700/0600 private directory, and the shared resync cooldown; T-04-34 is accepted).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `services.py` is the scaffold for the import, adopt and re-trigger services: `async_get_loaded_manager`, `resolve_device` and the admin-only registration are reusable; `SERVICE_IMPORT_DEVICES` is already in `const.py`.
- The docs plan has to reconcile the project rule against `device_id` targets in shipped examples (the field is allowed, targets are not).
- Human check still open: call `mqtt_actions.export_devices` from Developer Tools with and without a file name.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*

## Self-Check: PASSED

Files and the four commits exist; `uv run pytest tests -q` (1008 passed), `uv run ruff check .` and `uv run ruff format --check .` pass; both acceptance grep counts and the mode assertions (0700, 0600) are in place.
