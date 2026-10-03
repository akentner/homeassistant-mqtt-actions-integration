---
phase: quick-261003-rmy
plan: 261003-rmy
subsystem: native-entities
tags: [button, select, store, entity-registry, tdd]
requires:
  - phase: 05
    provides: native Switch/Select/test-button entities, Manager.async_send_state, mirrors
provides:
  - RestorePreviousButton for native Select devices (owned and mirrors)
  - previous_state attribute on DeviceSelect, persisted in the additive `previous_states` Store key
  - new native test buttons diagnostic and disabled by default, existing registry entries untouched
affects: [native entities, manager Store, README, docs/operations.md]
tech-stack:
  added: []
  patterns:
    - "Additive Store key written only when non-empty (same as `native`)"
    - "Existing registry entry hands its own entity_category back so HA does not rewrite it"
key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/button.py
    - custom_components/mqtt_actions/select.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/conftest.py
    - tests/test_native_entities.py
    - tests/test_translations.py
    - tests/test_docs.py
    - README.md
    - docs/operations.md
key-decisions:
  - "P-01: previous_states = {device id: {last, previous}} written only with history; no STORE_VERSION bump"
  - "P-02: restore button unique id is `{device_id}_restore_previous`"
  - "P-03: restore reuses Manager.async_send_state, no extra approval or mode gate"
  - "P-05: _test_button_category reads the registry so only new entries become DIAGNOSTIC; disabled default is class-level (creation-only)"
requirements-completed: []
duration: ~45 min
completed: 2026-10-03
status: complete
commits: 7
plan_head_before: e29f5b71bf3bc673318a4286f932bc7b0a2350a2
plan_head_after: c7a537cbd9122fa10cf07b023b6298399f8fcb15
actuals:
  tokens: 8600
  tasks: 3
  commits: 7
---

# Quick Task 261003-rmy: Restore previous state and diagnostic test buttons Summary

Native Select devices (owned and mirrors) track and persist their previous value, show it as the `previous_state` attribute and get a visible "Restore previous state" button; new native test buttons are diagnostic and disabled by default while existing registry entries stay untouched.

## What was built

- **Task 1 (tracer):** `Manager` records a `SelectHistory(last, previous)` per native Select in `_record_value` (`_track_previous`), exposes `previous_value()` and `async_restore_previous()`; `RestorePreviousButton` (`{device_id}_restore_previous`, no category, enabled) publishes through `async_send_state` (retained, QoS 1). No-op without a known previous state. Translations en/de.
- **Task 2:** `DeviceSelect.extra_state_attributes["previous_state"]` (friendly name, live, None for a removed option); strict `_parse_previous_states`; additive `previous_states` Store key written only with history (`tests/test_manager_breaker.py` unchanged and green); filtered to kept ids at start; dropped on device delete, mirror tombstone and local release, kept on adoption.
- **Task 3:** `DeviceTestButton` is `_attr_entity_registry_enabled_default = False` and takes its category from `_test_button_category` (existing entry keeps its own, new one gets DIAGNOSTIC). README, docs/operations.md and a docs test describe it.

## TDD

Three RED commits precede their implementation commits (`6df8aa7`, `e611224`, `fc955d3`). The existing-entry guard test (`no-category-enabled`) fails against a naive class-level category, proving the registry lookup is needed.

## Task commits

| Commit | Type | Description |
|--------|------|-------------|
| 6df8aa7 | test | failing tests for the restore button |
| da76d95 | feat | restore previous state button |
| e611224 | test | failing tests for previous_state, persistence, mirrors |
| 7a749e1 | feat | previous_state attribute and persistence |
| fc955d3 | test | failing tests for diagnostic disabled test buttons and docs |
| 442d52e | feat | diagnostic, disabled-by-default new test buttons |
| c7a537c | docs | README and docs/operations.md |

## Deviations from Plan

None - plan executed as written. Notes:

- The tests use a local literal `STORE_PREVIOUS_STATES = "previous_states"` instead of importing the constant, so the RED commit fails per test instead of at import and the wire key is pinned.
- The restart test of the plan is split in two tests (one config entry per test, the integration is single-entry).
- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` failed once in the full run (known flake) and passed alone.

## Verification

`uv run pytest tests -q` (1446 tests, all green apart from the known flake that passes on rerun), `uv run ruff check .` and `uv run ruff format --check .` clean.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

All 12 modified files exist; commits 6df8aa7, da76d95, e611224, 7a749e1, fc955d3, 442d52e, c7a537c are in `git log`.
