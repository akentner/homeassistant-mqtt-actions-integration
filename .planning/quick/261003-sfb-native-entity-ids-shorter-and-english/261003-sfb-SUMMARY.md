---
phase: quick-261003-sfb
plan: 261003-sfb
subsystem: native-entities
tags: [entity-registry, entity-id, translations, tdd]
requires:
  - phase: quick-261003-rmy
    provides: restore button and diagnostic test buttons that get the new id parts
provides:
  - MqttActionsEntity._entity_id_part and a suggested_object_id override that returns it
  - short English id parts for every new entity (_restore, _test_<StateValue>, _mode, _resync, _instances, _instance_mode)
affects: [native entities, README, docs/operations.md]
tech-stack:
  added: []
  patterns:
    - "Override Entity.suggested_object_id once in the base class; the class attribute carries the part"
key-files:
  created:
    - tests/test_entity_ids.py
  modified:
    - custom_components/mqtt_actions/entities.py
    - custom_components/mqtt_actions/button.py
    - custom_components/mqtt_actions/select.py
    - custom_components/mqtt_actions/sensor.py
    - tests/test_native_start.py
    - tests/test_docs.py
    - README.md
    - docs/operations.md
key-decisions:
  - "S-01: override the suggested_object_id property in MqttActionsEntity; never preset entity_id, so the area and device parts stay"
  - "S-03: the test button part is test_<StateValue>, which is immutable, not the renamable friendly name"
  - "S-04: no rename, migration or registry write; existing entries keep entity id and registry id"
requirements-completed: []
duration: ~25 min
completed: 2026-10-03
status: complete
commits: 6
plan_head_before: 69537ee1e7db53ff255061436738c857add67c05
plan_head_after: 89019df0eeb25f5a231eff64d931307caedb1198
actuals:
  tokens: 9500
  tasks: 3
  commits: 6
---

# Quick Task 261003-sfb: Short English entity ids Summary

Every newly created entity of the integration gets a short English entity id part (`_restore`, `_test_<StateValue>`, `_mode`, `_resync`, `_instances`, `_instance_mode`) whatever the Home Assistant UI language is, through one `suggested_object_id` override in the base class; displayed names stay translated and existing registry entries are never renamed.

## What was built

- **Task 1 (tracer):** `MqttActionsEntity._entity_id_part` (default `None`) and a `suggested_object_id` property (`@override`) that returns it, else the core value. `RestorePreviousButton` uses `restore`. Tests build the instance with a chosen language and an optional area "Küche" (builder `prepare`/`setup` in `tests/test_entity_ids.py`).
- **Task 2:** `ResyncButton` `resync`, `DeviceModeSelect` `mode`, `InstanceModeSelect` `instance_mode`, `RosterSensor` `instances`, `DeviceTestButton` `test_<trigger.value>` (set once in `__init__`). Table test over en/de and with/without area, keep-the-id guard for every kind, hostile StateValue test, takeover test parametrized over en and de.
- **Task 3:** `tests/test_docs.py` pins the suffixes to the classes; README (upgrade notes and test button paragraph) and docs/operations.md (upgrade notes, mode paragraph) list the suffixes, state that existing ids are never renamed and that names stay translated.

## TDD

Three RED commits precede their implementation commits (`1516415`, `3c695ae`, `b1de1f9`). The keep-the-id guards and the German takeover test pass before the change by design (Home Assistant never renames an existing entry); the new-entry assertions, the table and the hostile-value test fail for the right reason (translated or friendly-name based parts).

## Task commits

| Commit | Type | Description |
|--------|------|-------------|
| 1516415 | test | failing tests for short English entity ids |
| 08910bb | feat | restore button gets `_restore` (base-class mechanism) |
| 3c695ae | test | failing tests for the id parts of every entity |
| f540fc1 | feat | resync, mode, instance mode, roster, test buttons get their parts |
| b1de1f9 | test | failing docs test for the suffixes |
| 89019df | docs | README and docs/operations.md describe the suffixes |

## Deviations from Plan

None in the code. Notes:

- The plan's guard text says the unregistered second device (area test, German) gets `button.modus_bad_restore`; the test builder puts every device in the area as specified, so the test asserts `button.kuche_modus_bad_restore`. The behavior is the same (English part after area and device parts).
- The hostile-value test also asserts that the id starts with `button.modus_test_` and contains `_c_d_e_`, so it fails before the change (the friendly name "Hostile" gave a valid id already) and pins that the part comes from the StateValue.
- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` failed once in the full run (known flake) and passed on rerun alone.

## Verification

`uv run pytest tests -q` (1459 tests, all green apart from the known flake that passes alone), `uv run ruff check .` and `uv run ruff format --check .` clean. The grep sweep finds no old generated id in README, docs, custom_components or tests outside `tests/test_entity_ids.py`; the translation files are unchanged against 69537ee.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

All created and modified files exist; commits 1516415, 08910bb, 3c695ae, f540fc1, b1de1f9, 89019df are in `git log`.
