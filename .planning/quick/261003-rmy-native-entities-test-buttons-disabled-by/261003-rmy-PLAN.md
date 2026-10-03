---
phase: quick-261003-rmy
plan: 261003-rmy
type: execute
wave: 1
depends_on: []
files_modified:
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
autonomous: true
requirements:
  - ENT-01
  - ENT-02

estimate:
  tokens: 36000
  raw_tokens: 36000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A native test button that is newly created (owned device or mirror) has EntityCategory.DIAGNOSTIC and is disabled by default; a test button that is already in the entity registry keeps its category and its enabled state, nothing is migrated."
    - "Every native Select device, owned or mirrored, has a normal visible button 'Restore previous state' (no entity category, enabled by default); native devices only, Switch devices and legacy-path devices get none."
    - "The select entity carries the attribute previous_state: the friendly name of the last different value shown before the current one, tracked per instance on every change of the shown value (broker echo, local or remote), None when unknown or when that option no longer exists."
    - "Pressing the restore button publishes the previous StateValue exactly like choosing an option (retained, QoS 1, shared state topic, through Manager.async_send_state) and does nothing when no previous state is known."
    - "previous_state survives a restart through a new additive Store key that is written only when at least one device has history, so a Store without history keeps its exact key set (tests/test_manager_breaker.py stays untouched)."
    - "README, docs/operations.md and translations en/de describe the restore button, the previous_state attribute and the diagnostic, disabled-by-default test buttons."
  artifacts:
    - path: "custom_components/mqtt_actions/button.py"
      provides: "RestorePreviousButton, DeviceTestButton with diagnostic category and disabled default that spares existing registry entries"
    - path: "custom_components/mqtt_actions/manager.py"
      provides: "SelectHistory tracking in _record_value, previous_value, async_restore_previous, persisted previous_states"
    - path: "custom_components/mqtt_actions/select.py"
      provides: "previous_state attribute of DeviceSelect"
    - path: "custom_components/mqtt_actions/const.py"
      provides: "STORE_PREVIOUS_STATES"
    - path: "custom_components/mqtt_actions/translations/en.json"
      provides: "entity.button.restore_previous.name"
    - path: "custom_components/mqtt_actions/translations/de.json"
      provides: "entity.button.restore_previous.name"
  key_links:
    - "RestorePreviousButton.async_press -> Manager.async_restore_previous -> Manager.async_send_state -> state_topic (retained, QoS 1)"
    - "Manager._record_value -> Manager._track_previous -> Manager._data_to_save (key previous_states) -> Store -> Manager._async_load_store"
    - "button.async_setup_entry._sync_test_buttons -> _test_button_category (entity registry lookup) -> DeviceTestButton.entity_category"
---

<objective>
Native entities of MQTT Actions (branch gsd/phase-05-..., version 0.2.0 not released yet), two changes in one atomic quick task:

1. The native test buttons become EntityCategory.DIAGNOSTIC and disabled by default, for owned devices and for mirrors, but only for registry entries that are newly created (Q-01).
2. A native Select (owned or mirror) tracks its previous state per instance, shows it as attribute `previous_state`, persists it in the manager Store and gets a visible button "Restore previous state" that publishes it exactly like a select choice (Q-02, Q-03, Q-04).

README, docs/operations.md and the translations en/de follow (Q-05). Tests are pytest plus ruff, TDD: each task commits its failing tests first, then the implementation (Q-06).

Purpose: the test buttons are a tool, not a daily control, so they leave the default device page; going back to the last select value is a daily need and today needs a manual option lookup.
Output: the changed files above plus the SUMMARY of this quick task.

Request items (locked, from the task description; there is no CONTEXT.md for a quick task):
- Q-01: test buttons diagnostic + disabled by default, owned and mirrors, new registry entries only, existing entries untouched.
- Q-02: `previous_state` attribute on the select: last different value before the current one, per instance, persisted in the manager Store, tracked on every shown-value change (broker echo, local or remote).
- Q-03: button "Restore previous state" publishes it via the existing Manager.async_send_state path (retained, QoS 1, shared state topic); does nothing when no previous state is known.
- Q-04: the restore button is a normal visible button (no entity category, enabled by default); owned selects and mirrors of selects, native devices only.
- Q-05: README, docs/operations.md, translations en/de.
- Q-06: pytest + ruff, TDD (failing test commit first).

Design decisions made in this plan (planner, verified against the code and the installed Home Assistant, all stated so the executor does not re-decide):
- P-01 Store location: a new additive top-level key `previous_states` (const STORE_PREVIOUS_STATES), device id -> {"last": StateValue, "previous": StateValue}. `last` is stored so a change made while the instance was down is recognised after the restart (the first retained echo of a start is compared with `last`, not with nothing). The key is written only when at least one device has a `previous`; devices that never changed value have no entry. This is the same pattern as the `native` key, so the exact key set pinned by tests/test_manager_breaker.py::test_trip_is_persisted_as_config_hash (a legacy Switch instance) cannot change. No Store version bump. Entries are dropped when the device is deleted, the mirror is removed or the device is released locally; they are NOT dropped by an adoption (the map is keyed by device id, and `_async_drop_mirror` must not touch it).
- P-02 Unique id of the restore button: `{device_id}_restore_previous`. It cannot collide with `{device_id}_test_{12 hex}` (other literal after the id), with `{device_id}_mode` or the select's `{device_id}` (other domain), or with `{entry_id}_resync`.
- P-03 Gate of a restore on a mirror: the same as the select choice, which is none beyond entity availability (a mirror is unavailable while its owner is not online) and the validation inside Manager.async_send_state. No approval and no mode check: approval and mode gate the running of actions on each receiving instance when the echo arrives, not the publishing of a StateValue to the shared topic. The restore reuses `Manager.async_send_state`, so the retained/QoS 1/exact-StateValue contract and the T-5-10 refusal of foreign values are inherited, not re-implemented.
- P-04 Entity name: translation key `restore_previous`, name "Restore previous state" (en) and "Vorherigen Zustand wiederherstellen" (de), `entity.button.restore_previous.name`, has_entity_name from MqttActionsEntity. The attribute value is the friendly name (what the select shows and what `select.select_option` accepts), computed live like `current_option`, so a rename follows and a removed option gives None. Pressing the restore button twice toggles between the two values, because every echo changes the shown value.
- P-05 Existing installations: verified in the installed Home Assistant (`helpers/entity_registry.py`, `helpers/entity_platform.py`): `disabled_by` is applied at creation only ("does not affect existing entities"), but `entity_category` is passed on every add and `_async_update_entity` writes it to an existing entry. A plain class-level DIAGNOSTIC would therefore rewrite every already-registered test button (including the 0.1.x discovery buttons the takeover moved, category config) at the next start. So `_sync_test_buttons` reads the registry once per button: an existing entry hands its own `entity_category` to the button, a new one gets DIAGNOSTIC. Disabled default is class-level `_attr_entity_registry_enabled_default = False`, which is safe because it is creation-only. No migration, no registry write.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.claude/CLAUDE.md
@custom_components/mqtt_actions/button.py
@custom_components/mqtt_actions/select.py
@custom_components/mqtt_actions/entities.py
@.planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-03-SUMMARY.md
@.planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-04-SUMMARY.md

Facts verified in the code (do not re-derive):
- Manager (custom_components/mqtt_actions/manager.py): `Device.value` is the last accepted StateValue of the state topic, None until one arrived. `_record_value(device, payload)` is the single place where the shown value changes; it returns early on an unknown payload or an unchanged value and then sends SIGNAL_DEVICE_STATE, which every NativeDeviceEntity listens to. `_on_message` calls it before the disabled-mode gate. `async_send_state(device_id, value)` accepts owned devices and mirrors, raises ValueError for an unknown device or a value that is not exactly one of the device's StateValues, and publishes retained at QoS 1 to `state_topic`. `is_native(device_id)` is True for native owned devices and for mirrors whose owner marked the document native.
- Store: `_async_load_store` parses each key with a strict `_parse_*` helper; `_data_to_save` = `_base_data_to_save()` (always-written keys) plus the `native` key only when `self._native != NativeState()`. `async_start` filters stored maps to the kept ids (`kept = current | self.mirrors.keys()`). `_device_modes.pop(device_id, None)` happens in the mirror removal method and in `_async_remove_device`; `async_release_locally` pops `_stored_last_acted` and calls `_forget_native`.
- button.py: `DeviceTestButton` has `_attr_entity_category = EntityCategory.CONFIG`, unique id `{device_id}_test_{trigger.key}`, and `_sync_test_buttons` builds the expected set from `manager.devices` + `manager.mirrors` filtered by `manager.is_native`, removes registry entries of removed options, and adds new buttons per device with `config_subentry_id=manager.subentry_id_of(device_id)`.
- select.py: `DeviceSelect` (unique id = device id) computes `options` and `current_option` live from `device.spec.triggers` (`trigger.friendly_name`, `trigger.value`); `_add_new_native_devices` qualifies devices by `spec.kind == SUBENTRY_SELECT and manager.is_native(...)` over `manager.devices` and `manager.mirrors`.
- entities.py: `NativeDeviceEntity` is available only while the device exists and, for a mirror, its owner is online; it listens to SIGNAL_DEVICES_CHANGED, SIGNAL_ROSTER_UPDATED and SIGNAL_DEVICE_STATE of its device.
- Tests: tests/test_native_entities.py holds the helpers `_seed_native`, `_setup`, `_manager`, `_state`, `_entity_id`, `_publishes`, `_native_switch`, `_native_select`, `_select_entity_id`, `_button_id`, `_press`, `_deliver`, `_presence`, `SELECT_OPTIONS` (a="Alpha", "Mixed Case"="Bravo", c="Charlie"); tests/documents.py has `make_spec`/`document_payload(spec, native=True)`. The mocked MQTT client loops a publish back and core drops a second retained message per subscription (05-03 SUMMARY), so a test asserts the (payload, qos, retain) tuple of the publish and drives any follow-up echo by hand with a live, non-retained `_state` call. A PropertyMock patch of `DeviceTestButton.entity_registry_enabled_default` was verified to flip the creation default of the button entries.
- Prior verify commands (reused verbatim from 05-03/05-04): `uv run pytest tests -q`, `uv run ruff check .`, `uv run ruff format --check .`.
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Restore previous state end to end for a native Select (tracer)</name>
  <files>custom_components/mqtt_actions/manager.py, custom_components/mqtt_actions/button.py, custom_components/mqtt_actions/translations/en.json, custom_components/mqtt_actions/translations/de.json, tests/test_native_entities.py, tests/test_translations.py</files>
  <read_first>
    custom_components/mqtt_actions/manager.py (Device, SelectHistory neighbours NativeState/_parse_native, _record_value, async_send_state, is_native)
    custom_components/mqtt_actions/button.py (ResyncButton, DeviceTestButton, async_setup_entry)
    custom_components/mqtt_actions/select.py (_add_new_native_devices, DeviceSelect.current_option)
    tests/test_native_entities.py (helpers and the select section)
    tests/test_translations.py (the required-key list around entity.button.resync.name)
  </read_first>
  <behavior>
    - A native Select device (owned) has a button entity with unique id `{device_id}_restore_previous`, platform mqtt_actions, no entity category, enabled by default, on the subentry and on the same device as the select, with a state (not unavailable).
    - Values a, then Mixed Case are shown (a retained, the second live); pressing the restore button publishes exactly ("a", qos 1, retain True) on the state topic; after a hand-driven live echo of "a" the select shows Alpha.
    - With only one value ever shown, and with no value at all, a press publishes nothing.
    - Tracking ignores a repeated value and an unknown or empty payload; a to Mixed Case to c gives previous_value "Mixed Case" (the StateValue) after the last step.
    - A native Switch device gets no restore button.
    - en.json and de.json both carry entity.button.restore_previous.name (the required-key list in tests/test_translations.py names it).
  </behavior>
  <action>
    Implements Q-02 (tracking), Q-03, Q-04, P-02, P-03, P-04. RED first: add the tests of the behavior block in a new section "Quick 261003-rmy: restore previous state" at the end of tests/test_native_entities.py, add "entity.button.restore_previous.name" next to "entity.button.resync.name" in the required-key list of tests/test_translations.py, run them, confirm they fail for the right reason and commit them alone as `test(quick-261003-rmy): add failing tests for the restore previous state button`. Then implement and commit as `feat(quick-261003-rmy): add the restore previous state button`.

    manager.py: add a small frozen slots dataclass SelectHistory (fields `last`, `previous`, both StateValues) next to NativeState and an in-memory dict `self._previous: dict[str, SelectHistory]` created in `__init__`. Change `_record_value` to read the old value before it assigns the new one and, after the assignment and before the dispatcher signal, call a new `_track_previous(device, old, value)`. `_track_previous` returns at once unless `device.spec.kind == SUBENTRY_SELECT` and `self.is_native(device.device_id)`. Its `before` is `old`; when `old` is None it is the `last` of an existing entry (so the first echo after a restart is compared with the value from before the restart). Only when `before` is not None and differs from `value` does it store `SelectHistory(last=value, previous=before)` for the device id. Add `previous_value(device_id) -> str | None`: None for an unknown device, a non-Select device, no entry, or a stored previous that is not any more one of `device.spec.accepted.values()`; otherwise the StateValue. Add `async_restore_previous(device_id) -> bool`: returns False when `previous_value` is None, otherwise awaits `self.async_send_state(device_id, previous)` and returns True. Nothing is changed locally by it: the echo of the broker is the state source (as for a select choice), and that echo is what makes the shown value and the history change.

    button.py: add `_restore_button_unique_id(device_id)` returning the device id plus `_restore_previous` and a class RestorePreviousButton(NativeDeviceEntity, ButtonEntity) with `_attr_translation_key = "restore_previous"`, the unique id from the helper, no `_attr_entity_category` and no change of the registry default (it stays enabled). Its `async_press` awaits `manager.async_restore_previous(device_id)` and logs a debug line when it returned False (a press without a known previous state is a quiet no-op, Q-03). In `async_setup_entry` add a second callback next to `_sync_test_buttons` that mirrors the add loop of `_add_new_native_devices` in select.py: qualifying ids are the devices and mirrors with `spec.kind == SUBENTRY_SELECT` and `manager.is_native(id)`, a set of already added ids is intersected with the qualifying ones, new ids are added with `config_subentry_id=manager.subentry_id_of(device_id)`, and the callback runs once at setup and is connected to SIGNAL_DEVICES_CHANGED with `entry.async_on_unload`. Import SUBENTRY_SELECT from .const. Do not touch DeviceTestButton in this task. The press follows the select choice gate and adds none of its own (P-03): no approval check and no mode check in the button or in `async_restore_previous`.

    Translations: add "restore_previous": {"name": "Restore previous state"} under entity.button in en.json (after resync) and {"name": "Vorherigen Zustand wiederherstellen"} in de.json. Keep the JSON formatting of the files as it is.

    Persistence is deliberately not part of this task: the dict is in memory only here; task 2 adds the Store key. The tracer proves the path entity -> manager -> broker publish -> echo -> history end to end.
  </action>
  <verify>
    <automated>uv run pytest tests/test_native_entities.py tests/test_translations.py -q && uv run ruff check . && uv run ruff format --check .</automated>
  </verify>
  <done>Tests of the behavior block pass and were committed red first; the restore button of an owned native Select publishes the previous StateValue retained at QoS 1 to the state topic and does nothing without a previous state; Switch devices get none; both translation files carry the entity name; ruff check and format are clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: previous_state attribute, persistence across restarts, lifecycle cleanup, mirrors</name>
  <files>custom_components/mqtt_actions/const.py, custom_components/mqtt_actions/manager.py, custom_components/mqtt_actions/select.py, tests/test_native_entities.py</files>
  <read_first>
    custom_components/mqtt_actions/manager.py (_async_load_store, _data_to_save, _parse_native, the start filter to `kept`, _async_remove_device, the mirror removal method, async_release_locally, _async_drop_mirror)
    custom_components/mqtt_actions/const.py (STORE_* block)
    custom_components/mqtt_actions/select.py (DeviceSelect)
    tests/test_manager_breaker.py (test_trip_is_persisted_as_config_hash, must stay green and unchanged)
    tests/test_native_cleanup.py (patterns for removing a device and a mirror in tests)
  </read_first>
  <behavior>
    - The select state carries attribute `previous_state`: the key is always present, None before any history; after a then Mixed Case it is "Alpha"; after the option "Alpha" is renamed it shows the new name; after that option is removed it is None and a restore press publishes nothing.
    - `manager._data_to_save()` has key `previous_states` == {device_id: {"last": "Mixed Case", "previous": "a"}} after two distinct values; the key is absent for a device that only ever showed one value, for a native Switch, and for a legacy-path Select instance (no native flag) after any number of changes.
    - A Store seeded with a valid `previous_states` entry (plus the native flag) shows previous_state at the first state write, before any message; a retained echo equal to `last` keeps previous; a retained echo that differs from `last` (changed during downtime) makes previous the old `last` and last the new value.
    - A malformed `previous_states` (not a dict, bad device ids, non-dict entries, non-string or empty values, last equal to previous, ids of unknown devices) is ignored without an error; ids of unknown devices are gone from the next save.
    - Deleting the device, the tombstone of a mirror and a local release drop the entry; the entry is kept when a native mirror is adopted.
    - A native Select mirror (owner online, unapproved, even in observe mode) tracks the echoes of its owner and its restore button publishes the previous StateValue retained at QoS 1 to the shared state topic exactly as `select.select_option` on that mirror would; with the owner offline the restore button is unavailable.
  </behavior>
  <action>
    Implements Q-02 (attribute, persistence per instance in the manager Store), Q-04 (mirrors), P-01, P-03, P-04. RED first: write the tests of the behavior block in tests/test_native_entities.py (extend the Task 1 section; add a small helper that adds a `previous_states` dict to the data that `_seed_native` writes into `hass_storage`; for the mirror tests use `make_spec(SUBENTRY_SELECT, options=...)`, `document_payload(spec, native=True)`, `_deliver` and `_presence`), run them, confirm they fail for the right reason and commit them alone as `test(quick-261003-rmy): add failing tests for previous_state, its persistence and mirrors`. Then implement and commit as `feat(quick-261003-rmy): expose and persist the previous state of a native select`.

    const.py: add STORE_PREVIOUS_STATES = "previous_states" with a comment in the style of its neighbours (device id -> last and previous StateValue of a native Select, local, never part of a document or a hash).

    manager.py: add a strict `_parse_previous_states(stored)` beside `_parse_native`: only a dict is read; an item is kept only when its key is a str accepted by `is_valid_device_id`, its value is a dict whose `last` and `previous` are non-empty str, and the two differ; anything else is dropped; the result maps ids to SelectHistory. Load it in `_async_load_store` into `self._previous`. In `async_start` filter it to `kept` next to the other maps. In `_data_to_save` (the method that already adds `native` conditionally, not `_base_data_to_save`) write STORE_PREVIOUS_STATES only when `self._previous` is non-empty, as device id -> {"last": ..., "previous": ...} with sorted ids. Call `self._schedule_save()` in `_track_previous` whenever an entry is stored. Pop the device id from `self._previous` where `_device_modes.pop` runs in the mirror removal method and in `_async_remove_device`, and in `async_release_locally` next to the `_stored_last_acted` pop; do not pop it in `_async_drop_mirror` (an adoption keeps the history of the device id), and make sure a save is scheduled or already awaited in each of those paths (they already save).

    select.py: add `extra_state_attributes` to DeviceSelect returning a dict with the single key `previous_state`: the `friendly_name` of the trigger whose `value` equals `manager.previous_value(device_id)`, else None, computed at every read exactly like `current_option` (device None gives None). The existing SIGNAL_DEVICE_STATE and SIGNAL_DEVICES_CHANGED wiring of NativeDeviceEntity already rewrites the state when the value or the spec changes, so no new signal is needed.

    Do not edit tests/test_manager_breaker.py: its exact key-set assertion passing unchanged is the proof of P-01. Do not add new Store keys other than STORE_PREVIOUS_STATES and do not bump STORE_VERSION.
  </action>
  <verify>
    <automated>uv run pytest tests/test_native_entities.py tests/test_manager_breaker.py tests/test_manager_select.py tests/test_native_cleanup.py -q && uv run ruff check . && uv run ruff format --check .</automated>
  </verify>
  <done>All behavior tests pass and were committed red first; previous_state is on the select, survives a restart through the previous_states key, the key is absent without history, the entry is dropped on delete, tombstone and local release but kept on adoption, mirrors work with the same publish contract as a select choice; tests/test_manager_breaker.py is unchanged and green; ruff clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Test buttons diagnostic and disabled by default for new entries; docs</name>
  <files>custom_components/mqtt_actions/button.py, tests/conftest.py, tests/test_native_entities.py, tests/test_docs.py, README.md, docs/operations.md</files>
  <read_first>
    custom_components/mqtt_actions/button.py (DeviceTestButton, _sync_test_buttons)
    tests/test_native_entities.py (test_native_test_buttons_exist_per_trigger and the tests that call _press on a native button: test_pressing_a_test_button_runs_that_trigger_once_and_changes_nothing, test_observe_and_disabled_modes_block_the_press, test_a_native_mirror_has_test_buttons_that_run_locally_once_approved)
    tests/conftest.py (fixtures)
    tests/test_docs.py (the _normalize, _section and _headings helpers and how en.json/const are read)
    README.md (sections "Select devices", "Run mode, test buttons and the circuit breaker", "Upgrading from 0.1.x")
    docs/operations.md (sections "Modes and devices" and "Upgrade notes")
  </read_first>
  <behavior>
    - A fresh native instance: every test button registry entry of an owned Switch, an owned Select and a native mirror has entity_category DIAGNOSTIC and disabled_by RegistryEntryDisabler.INTEGRATION and no state; the restore button of the Select has no category, disabled_by None and a state.
    - Existing entries are untouched: a test button entry registered before the setup with category CONFIG and disabled_by None keeps CONFIG, stays enabled and has a state after setup; one registered with disabled_by USER keeps USER; neither is rewritten (registry id unchanged).
    - The three existing tests that press a native test button still pass because they run with the test buttons enabled; test_native_test_buttons_exist_per_trigger now expects DIAGNOSTIC.
    - The docs name the entity "Restore previous state" (read from en.json, so the docs follow the translation), the attribute `previous_state`, and say that the test buttons are diagnostic and disabled by default, that existing entries keep their state and that nothing is migrated.
  </behavior>
  <action>
    Implements Q-01, Q-05, P-05. RED first: (a) add a fixture `enabled_test_buttons` to tests/conftest.py that patches `DeviceTestButton.entity_registry_enabled_default` with `unittest.mock.patch.object(..., new_callable=PropertyMock, return_value=True)` for the duration of the test (import DeviceTestButton from custom_components.mqtt_actions.button), so tests that must press a native test button create it enabled; (b) in tests/test_native_entities.py request that fixture in the three press tests named in the behavior block, change the category assertion of test_native_test_buttons_exist_per_trigger to DIAGNOSTIC (rename the test and fix its docstring to say diagnostic and disabled by default; it must not request the fixture), and add the new tests of the behavior block, including the pre-registered existing-entry tests (build the subentry first, register the button entries through `er.async_get(hass).async_get_or_create("button", DOMAIN, f"{device_id}_test_{key}", ...)` with the category and disabled_by of the case before `_setup`; the key is `SWITCH_ON_KEY` or `trigger_key(value)`); (c) add a test in tests/test_docs.py that reads the entity name from en.json and asserts README.md and docs/operations.md contain it and `previous_state`, and that the README section on test buttons says diagnostic and disabled by default. Run them, confirm they fail for the right reason (the existing-entry tests pass already and are the guard that a naive class-level category would break) and commit alone as `test(quick-261003-rmy): add failing tests for diagnostic disabled test buttons and the docs`. Then implement and commit as `feat(quick-261003-rmy): make new native test buttons diagnostic and disabled by default` (code) and, if the docs are a separate step, `docs(quick-261003-rmy): describe the restore button and the diagnostic test buttons`.

    button.py: on DeviceTestButton remove `_attr_entity_category = EntityCategory.CONFIG`, add `_attr_entity_registry_enabled_default = False`, and let `__init__` take an `entity_category: EntityCategory | None` argument that it stores in `self._attr_entity_category`. Add a module function `_test_button_category(registry, device_id, key)` that returns the `entity_category` of the existing registry entry for ("button", DOMAIN, unique id of the test button) when there is one and `EntityCategory.DIAGNOSTIC` otherwise. In `_sync_test_buttons` pass `_test_button_category(registry, device_id, trigger.key)` for every new button; the `registry` object is already fetched there. Explain the why in a short comment on the helper: Home Assistant writes the category of an entity to an existing registry entry at every add, but applies the enabled default only at creation, so an existing entry has to hand its own category back to stay untouched (P-05). Update the class docstring and the module docstring: the test buttons are diagnostic and disabled by default for new entries. The restore button of task 1 is not changed: visible, no category (Q-04). Apply nothing to the registry entries yourself: no migration, no enable, no category rewrite.

    README.md: in "Run mode, test buttons and the circuit breaker" replace the "(listed under Configuration)" remark and the sentence that existing Switch devices get their two test buttons with no opt-out by the new facts: new test buttons are in the Diagnostic category and disabled by default, enable one on its entity page when needed; a test button that already exists (including the ones migrated from 0.1.x) keeps its category and enabled state, nothing is migrated; this holds for owned devices and mirrors. In "Select devices" add a bullet each for: the attribute `previous_state` (friendly name of the value shown before the current one, per instance, kept across restarts, empty until the value changed once or when that option was removed) and the button **Restore previous state** (visible by default, publishes that value exactly like choosing the option, retained at QoS 1 on the state topic so every instance reacts, does nothing without a previous state, pressing it twice toggles between the two values, native devices only, on a mirror it needs the owner online and no approval, because approval gates only the running of actions on this instance). Add one short bullet to "Upgrading from 0.1.x" that points at the test button behavior.

    docs/operations.md: in "Modes and devices", where it lists what the device of MQTT Actions carries, add the restore button of a Select and say the test buttons are diagnostic and disabled by default; in "Upgrade notes" extend the Native entities bullet with the same existing-entries-unchanged sentence. State that the restore button publishes to the same state topic a choice does, so the broker ACL needs no new line, and that the previous state is local to the instance and not part of a config document.

    If another native-path test fails only because it relied on a native test button having a state, enable the buttons for that test with the fixture; never change production code for it.
  </action>
  <verify>
    <automated>uv run pytest tests -q && uv run ruff check . && uv run ruff format --check .</automated>
  </verify>
  <done>New native test buttons (owned and mirror) are diagnostic and disabled by default, existing registry entries keep category, enabled state and registry id, the restore button stays visible; the full suite, ruff check and ruff format pass; README, docs/operations.md and both translation files describe the behavior and test_docs pins it.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HA user / automation -> restore button | A press publishes a StateValue to the shared state topic, which makes every connected instance run the matching actions |
| broker -> state topic -> Manager._record_value | Foreign payloads (from any client or instance) decide the tracked history |
| local Store file -> Manager._async_load_store | Persisted `previous_states` is read at every start |
| integration -> entity registry | Existing registry entries (user customisations) must not be rewritten |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-261003-01 | Elevation of Privilege | RestorePreviousButton on a mirror publishes to the shared state topic | medium | mitigate | The button calls `Manager.async_send_state`, which refuses unknown devices and any value that is not exactly one of the device's StateValues (T-5-10), publishes the same retained/QoS 1 message as a select choice and adds no new topic or ACL line (P-03). Approval and mode still gate the running of actions on each receiving instance when the echo arrives, so the restore grants nothing a select choice does not. A mirror is unavailable while its owner is offline. |
| T-261003-02 | Tampering | persisted `previous_states` in the Store | low | mitigate | Strict `_parse_previous_states` (types, valid device ids, non-empty distinct strings), filtered to the kept ids at start, and `previous_value` re-validates against the current `spec.accepted` values at every use, so a forged or stale entry can never publish a foreign value. |
| T-261003-03 | Tampering | foreign payloads steering the tracked history | low | accept | Only payloads that map to a StateValue of the device change the shown value (existing `_record_value` rule); unknown and empty payloads change nothing. The history is as trustworthy as the shown state, which every instance already follows. |
| T-261003-04 | Denial of Service | growth of `previous_states` | low | mitigate | Entries exist only for native Select devices that are owned or mirrored (mirrors are capped by MAX_MIRRORS), hold two StateValues each (bounded by the document parser), and are dropped on delete, tombstone and local release and filtered at start. |
| T-261003-05 | Information Disclosure | attribute `previous_state` | low | accept | It exposes a friendly name that the select already lists as an option; no action content, no ids. |
| T-261003-06 | Tampering | entity registry entries of existing test buttons | low | mitigate | The category of an existing entry is handed back unchanged and `disabled_by` is creation-only (verified in the installed Home Assistant); tests pin CONFIG/enabled and USER-disabled entries as untouched. |
| T-261003-SC | Tampering | npm/pip/cargo installs | high | accept | This task installs no package and changes no dependency; pyproject.toml and uv.lock stay untouched, so there is no package legitimacy surface. |
</threat_model>

<verification>
- `uv run pytest tests -q` (whole suite, including tests/test_manager_breaker.py, tests/test_native_start.py, tests/test_takeover.py and tests/test_translations.py unchanged apart from the one required-key line) passes; `uv run ruff check .` and `uv run ruff format --check .` are clean.
- Git history of the task shows three RED commits (`test(quick-261003-rmy): ...`) each before its `feat`/`docs` commit; no file deleted; STORE_VERSION unchanged; no other Store key added.
- Source coverage audit (all four source types covered):
  - GOAL (task description): test buttons diagnostic and disabled -> Task 3; previous_state and restore button -> Tasks 1 and 2; docs and translations -> Tasks 1 and 3; tests/TDD -> every task.
  - REQ: ENT-01 (native Select and test-button entities, unique ids unchanged: P-02, Task 3) and ENT-02 (commands publish retained at QoS 1 to the shared state topic: restore through async_send_state, Task 1) are extended, not changed.
  - RESEARCH: none for a quick task.
  - CONTEXT: Q-01 -> Task 3; Q-02 -> Tasks 1 and 2; Q-03 -> Task 1; Q-04 -> Tasks 1 and 2; Q-05 -> Tasks 1 and 3; Q-06 -> all. Open design points (store location, unique id, mirror gate, name/translation key, existing installations) are decided as P-01 to P-05 in the objective.
</verification>

<success_criteria>
- A new install shows the restore button next to the select and the test buttons only after they are enabled in the diagnostic list; an upgraded or migrated install shows exactly the test buttons it showed before.
- previous_state and the restore button work for owned selects and mirrors of native devices, survive a restart and do nothing without history.
- The suite and ruff are green and the README, docs/operations.md and both translations say what the code does.
</success_criteria>

<output>
Create `.planning/quick/261003-rmy-native-entities-test-buttons-disabled-by/261003-rmy-SUMMARY.md` when done
</output>
