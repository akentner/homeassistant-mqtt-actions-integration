---
phase: 08-real-instance-verification
reviewed: 2026-10-11T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/takeover.py
  - docs/troubleshooting.md
  - README.md
  - tests/test_discovery_export.py
  - tests/test_export_guard_receiver.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-10-11
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

I reviewed the receiver-side duplicate guard (`_arm_duplicate_guard`, `_on_duplicate_registry_updated`, `_disable_duplicates`
in `manager.py`, and `takeover.disable_duplicates`). I also reviewed the native-mirror persistence that came with it, the
two docs, and both test modules. `uv run pytest` on `test_export_guard_receiver.py`, `test_discovery_export.py` and
`test_takeover.py` passes (74 tests). `ruff check` is clean.

The trust model holds. The guard only touches registry rows, never publishes, and acts only when all of these are true:
- the row sits on the core MQTT device `mqtt_actions_<id>`;
- the row's unique id equals the id;
- a native twin of this config entry exists.

A broker-supplied device id therefore cannot disable an unrelated entity. No broker content reaches the logs. Nothing in
the phase lets a broker document run actions without approval. The native flag of a mirror only decides the entity type.

I found no Critical issues. The two warnings are both gaps between what the guard is meant to guarantee (no duplicate
tombstone, no foreign retained topic cleared) and what the code around it still does.

## Warnings

### WR-01: `remove_replay_twins` removes enabled, loaded rows, which clears the retained discovery topic and leaves an enabled tombstone; it runs before the guard is armed

**File:** `custom_components/mqtt_actions/takeover.py:191-223` (removal at 212), `custom_components/mqtt_actions/manager.py:806-809` and `1074-1078`
**Issue:** `remove_replay_twins` calls `entity_registry.async_remove(legacy.entity_id)` on every legacy row that has a
twin. Unlike `async_take_over`, it never checks that the row is unloaded (`entity_sources`) or disabled. Core MQTT
publishes an empty retained payload to the row's own discovery topic when a loaded entity leaves the registry
(`homeassistant/components/mqtt/entity.py:1211-1220`, `async_removed_from_registry` calling
`async_remove_discovery_payload`). The docstring acknowledges this. The consequences:

1. For a row that was created from another instance's export on the core prefix, the receiver wipes the exporter's
   retained export topic. The module's own `_clean_registry` comment calls this "Pitfall 10".
2. Removing an enabled row leaves a deleted-entity record with `disabled_by=None`. That is the tombstone class UAT-04
   traced (`08-evidence/uat-04/tombstone-cause.txt`), and the guard exists only to repair its symptom later.

In `async_start` the guard is armed at line 808, after `_async_native_takeover`, which already calls
`_remove_replay_twins` at line 1074. Rows that exist at takeover time are therefore removed while still enabled and
loaded, not disabled first. The 5-second replay catch (`_async_replay_catch`) is mostly safe only because the guard has
usually disabled the row by then. The code does not enforce that dependency.

**Fix:** Make the removal itself safe. Disable an enabled row before removing it, so the tombstone carries `integration`
and nothing is loaded when the row goes:
```python
for legacy in _legacy_entries(hass, device, device_id, mqtt_entry_id):
    ...
    if legacy.disabled_by is None:
        entity_registry.async_update_entity(legacy.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    entity_registry.async_remove(legacy.entity_id)
```
Alternatively, arm the guard before `_async_native_takeover` and skip loaded rows in `remove_replay_twins`, as
`async_take_over` does. Add a test that asserts no empty publish to the core-prefix topic when the takeover pass meets an
enabled duplicate. The current tests only assert `_publishes(...) == []` on the guard path.

### WR-02: `disable_duplicates` claims the duplicate definition of `remove_replay_twins` but drops its identity check, so it can disable the entity the user customized

**File:** `custom_components/mqtt_actions/takeover.py:226-252` (docstring 233-235, loop 244-251)
**Issue:** The docstring says a candidate matches "the definition of a duplicate that `remove_replay_twins` uses".
That is not true. `remove_replay_twins` leaves a row alone when `_carries_the_identity(legacy, twin)` is true, meaning
the legacy row carries the user's customizations or is the older one. `disable_duplicates` only requires a twin under
this config entry and `disabled_by is None`. An enabled core-MQTT row that holds the user's name, area or labels, and
whose native twin is the newer generated one, is disabled on every start and on every create event. That removes the
entity automations and dashboards use, and the next start can then delete it. The replay catch exists to protect exactly
this case ("an older or customized legacy entry is left to the takeover pass"). Disabled-by-integration is reversible,
but the guard never re-enables the row, and the user is not told which row was disabled because the log line is a count
only.

**Fix:** Apply the same identity test as the removal path:
```python
twin = entity_registry.entities[twin_id]
if twin.config_entry_id != entry_id or _carries_the_identity(entry, twin):
    continue
```
Add a G3-style test with a customized enabled legacy row next to an older/newer native twin. If the intent is to treat
such a row as a duplicate anyway, correct the docstring and the README text instead.

## Info

### IN-01: A row the user re-enables is silently disabled again on every start, and the docs do not say so

**File:** `custom_components/mqtt_actions/manager.py:910-916` and `926-928`, `README.md:105-106`, `docs/troubleshooting.md:111-113`
**Issue:** The sweep in `_arm_duplicate_guard` disables every enabled row of a native device at each start. The docstring
of `_on_duplicate_registry_updated` states that an enabled row survives only "until the next start" (T-08-36). The docs
tell the user that an enabled duplicate they still see "points to a row you enabled yourself" and to disable it by hand.
They never say that enabling a row is undone at the next start or reload, and no option exists to opt out.
**Fix:** Add one sentence to both docs, for example: "A duplicate you enable yourself is disabled again at the next start
of MQTT Actions."

### IN-02: Tests import private helpers across test modules

**File:** `tests/test_export_guard_receiver.py:16-19`
**Issue:** The module pulls `_mqtt_row`, `_deliver`, `_entity_id`, `_manager`, `_presence`, `_publishes`, `_setup`,
`_quiet_period_passes`, `_legacy_mirror` and `_restart` from four other test modules. Renaming a helper in any of them
breaks this module at import time and takes all its tests with it. The `_mqtt_row`, `_mqtt_device` and
`_mqtt_rows_of_the_device` helpers also duplicate each other across the two guard test modules.
**Fix:** Move the shared helpers into `tests/helpers.py` (or `conftest.py` fixtures) and import them from there.

### IN-03: A guard test does not prove the event path it claims to cover

**File:** `tests/test_export_guard_receiver.py:413-418`
**Issue:** In "a second create event", the row is removed and recreated through `async_get_or_create`. Core restores the
disabled state from the `integration` tombstone, so the row is born disabled and the assertion `again.disabled_by is
INTEGRATION` holds even with the listener removed. The check `calls == [duplicate.entity_id]` is also true if the listener
never ran. The test shows that the registry restores the state, not that the guard idempotently ignores a second create.
**Fix:** Spy on `manager._disable_duplicates` (or on `takeover.disable_duplicates`) and assert that it ran for the second
event and returned 0.

### IN-04: Private registry API and a very large module

**File:** `custom_components/mqtt_actions/takeover.py:284`, `custom_components/mqtt_actions/manager.py` (2613 lines)
**Issue:** `async_flush_registries` calls `registry._store.async_save(registry._data_to_save())`, which are private
internals of Home Assistant. They can change in any 2026.x release, and the `except Exception` turns that into a warning
log with a silent loss of the early write. `Manager` now has more than 2600 lines and mixes lifecycle, sync ingest,
adoption and the takeover, replay-catch and duplicate-guard logic, which makes ordering mistakes like WR-01 hard to see.
**Fix:** Add a unit test that fails loudly if `_store` or `_data_to_save` disappear. Consider moving the takeover, replay
catch and guard orchestration (`manager.py:819-960`) into a small collaborator next to `takeover.py`.

---

_Reviewed: 2026-10-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
