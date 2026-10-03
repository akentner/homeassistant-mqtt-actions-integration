---
phase: quick-261003-sfb
plan: 261003-sfb
type: execute
wave: 1
depends_on: []
files_modified:
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/select.py
  - custom_components/mqtt_actions/sensor.py
  - tests/test_entity_ids.py
  - tests/test_native_start.py
  - tests/test_docs.py
  - README.md
  - docs/operations.md
autonomous: true
requirements:
  - ENT-01
  - MIG-01

estimate:
  tokens: 30000
  raw_tokens: 30000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "With hass.config.language = de (and en), every entity this integration newly creates gets a short English entity id part, whatever the UI language: restore button `_restore`, test button `_test_<StateValue>` (for example `_test_on`), device mode select `_mode`, resync button `_resync`, roster sensor `_instances`, instance mode select `_instance_mode`. Home Assistant still puts the area and device parts of its own entity-id setting in front (for example `button.kuche_modus_kuche_restore`)."
    - "The main Switch and Select entity ids are unchanged: they have no translated name part (`_attr_name = None`), so they are already identical in every language (`switch.<device>`, `select.<device>`, with the area prefix when the device has an area)."
    - "An entity that already has a registry entry keeps its entity id, registry id, unique id and user customisations: there is no rename migration and no registry write that touches an entity id; a legacy test button (unique id `{device_id}_test_{key}`) taken over from core MQTT keeps its old id, also in a German instance."
    - "Displayed names stay translated: the registry `original_name` is German in a de instance; en.json, de.json and every translation key are untouched."
    - "README and docs/operations.md name the suffixes and say existing ids are never renamed; tests/test_docs.py pins the suffixes to the code."
    - "No test, fixture or doc relies on the old generated ids."
  artifacts:
    - path: "custom_components/mqtt_actions/entities.py"
      provides: "MqttActionsEntity._entity_id_part and the suggested_object_id property that returns it"
    - path: "custom_components/mqtt_actions/button.py"
      provides: "English id parts of ResyncButton, RestorePreviousButton and DeviceTestButton"
    - path: "custom_components/mqtt_actions/select.py"
      provides: "English id parts of DeviceModeSelect and InstanceModeSelect"
    - path: "custom_components/mqtt_actions/sensor.py"
      provides: "English id part of RosterSensor"
    - path: "tests/test_entity_ids.py"
      provides: "German and English instance tests of the generated ids, with and without an area, and the keep-the-id guards"
  key_links:
    - "MqttActionsEntity.suggested_object_id -> EntityPlatform._async_derive_object_ids -> registry object_id_base -> EntityRegistry._async_generate_entity_id (area, device, entity parts)"
    - "existing registry entry -> EntityRegistry.async_get_or_create -> _async_update_entity (entity_id changes only through new_entity_id, never at add)"
---

<objective>
MQTT Actions (branch gsd/phase-05-..., version 0.2.0 not released): the entity id of every NEWLY created entity must be short and English whatever the Home Assistant UI language is. Displayed names stay translated (en/de); only the generated entity id changes. Existing registry entries keep their ids.

Purpose: with a German instance the ids came out as long German strings (`button.kuche_modus_kuche_vorherigen_zustand_wiederherstellen`, `select.lampe_test_modus`), which are awkward in automations, templates and dashboards and differ between instances.
Output: one base-class mechanism, a short English id part per entity class, tests that run with a German UI language, and the docs.

Request items (locked, from the task description; a quick task has no CONTEXT.md):
- R-01: new entity ids are short and English regardless of the UI language, for Switch, Select, mode select, test buttons, restore button and the hub entities (resync button, instances sensor, instance mode select).
- R-02: target suffixes `_restore`, `_test_<value>` (for example `_test_on`), `_mode`, `_resync`, and a short English suffix for the instances sensor and the instance mode select.
- R-03: friendly names stay translated, translation keys stay; only the generated entity_id changes.
- R-04: existing registry entries and their ids do not change: no rename migration, the identity kept by the 0.1.x takeover (takeover.py) stays intact, a legacy test button keeps its old id, unique ids unchanged.
- R-05: verify the mechanism in the installed Home Assistant, explain the `kuche_` prefix, say what can and cannot be controlled (findings below).
- R-06: nothing may rely on the old generated ids (tests, test_takeover.py and test_native_entities.py fixtures, README.md, docs/*.md); update docs where ids are mentioned.
- R-07: TDD, failing test commit first; tests run with a German UI language and prove that a registered entity keeps its id.

Findings (R-05), verified in the installed Home Assistant 2026.9.4 under .venv and by a throwaway probe that was deleted again (nothing was guessed):

1. Why the ids were German. `helpers/entity_platform.py` lines 224 to 244: `object_id_language` is `hass.config.language` when it is in `languages.NATIVE_ENTITY_IDS` (generated/languages.py, contains `de`), else `en`. `Entity.suggested_object_id` (helpers/entity.py line 748, a plain property) resolves the entity name from those object-id translations. So `de` makes a German name and a German id from the `entity.<domain>.<translation_key>.name` keys of de.json; there is no English fallback for `de`.
2. The mechanism that exists. There is NO `_attr_suggested_object_id` in 2026.9.4. Two ways control the id independently of the translated name: (a) override the property `suggested_object_id` (core does this: components/aosmith/select.py line 50 and components/tesla_wall_connector/sensor.py line 258); (b) set `entity_id` on the entity before it is added. `entity_platform.py` `_async_derive_object_ids` (lines 1299 to 1329) turns (a) into the registry field `object_id_base` and (b) into `suggested_object_id`.
3. How they interact with the device prefix. `helpers/entity_registry.py` `_async_generate_entity_id` (lines 1344 to 1387) and `_async_get_full_entity_name` (line 493): a registry `suggested_object_id` is used VERBATIM, without any area or device part; an `object_id_base` is joined with the area, device and entity parts in the order of `registry.settings.entity_id_parts`, default (AREA, DEVICE, ENTITY), then slugified, and a collision gets `_2`. The device part is `device.name_by_user or device.name` (for an owned device the title of the subentry, user data) and the area part is the effective area of the device. `has_entity_name` is true for all our entities and does not change this.
4. Why `kuche_modus_kuche_...`. It is not a translation effect. It is the area part (area "Küche" of the device) plus the device part (device "Modus Küche") plus the entity part. Home Assistant does not remove an area name that the device name repeats. Reproduced with the probe: de, area Küche, device "Modus Küche" gave `button.kuche_modus_kuche_vorherigen_zustand_wiederherstellen`, `select.kuche_modus_kuche_modus`, `button.test_instance_neu_synchronisieren`, `sensor.test_instance_verbundene_instanzen`, `select.test_instance_instanzmodus`.
5. What can be controlled: the entity part only. With the property overridden the same setup gives `button.kuche_modus_kuche_restore`, `select.kuche_modus_kuche_mode`, `button.test_instance_resync`, `sensor.test_instance_instances`, `select.test_instance_instance_mode`, identical under en and de (probe). The main select is `select.kuche_modus_kuche` in every variant: the Switch and Select entities have no name part (`_attr_name = None`) and need no change.
6. What cannot (and should not) be controlled: the area part, the device part and the order. They come from the user's device data and from the Home Assistant wide setting `entity_id_parts`. Option (b) would drop all of them, override that user setting and need an own device lookup, so it is rejected (S-01).
7. Existing entries. `entity_registry.async_get_or_create` (line 1456) finds an existing entry by (domain, platform, unique_id) and calls `_async_update_entity`, which changes an entity id only for an explicit `new_entity_id`. `async_regenerate_entity_id` is called only by the websocket command of the UI (components/config/entity_registry.py line 358). So adding the override renames nothing, needs no migration, and the takeover (which moves entries with `async_update_entity_platform` and keeps the entity id) is not involved. The only visible effect on an existing entry is that its stored `object_id_base` field changes, which is not an id; this plan adds no code that listens for it (none exists in custom_components).
8. Sweep of reliance on old ids. Native entities are resolved in tests through `entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)` (tests/test_native_entities.py, test_native_start.py, test_hub_entities.py, test_modes.py, test_takeover.py); the only literal ids in tests are core-MQTT discovery entities of the legacy path (`switch.lamp`, `select.mode`) and the takeover fixture id `switch.my_lamp`, none generated by this integration; no test asserts a generated id of a translated entity. README.md and docs/*.md mention no generated id, only that ids are kept and the downgrade `_2` effect, which stay true. So nothing breaks; docs gain the suffixes (Task 3) and the takeover test gains a German variant (Task 2).

Design decisions made in this plan (planner, all verified above; the executor does not re-decide them):
- S-01 Mechanism: override the property `suggested_object_id` once in `MqttActionsEntity` (entities.py), returning the class attribute `_entity_id_part` when it is set and the core value otherwise. Do not preset `entity_id`.
- S-02 Suffix table: `_restore` (RestorePreviousButton), `_test_<StateValue>` (DeviceTestButton), `_mode` (DeviceModeSelect), `_resync` (ResyncButton), `_instances` (RosterSensor), `_instance_mode` (InstanceModeSelect). Claude's discretion for the last two: `instances` and `instance_mode` keep the hub entities recognisable next to a device `_mode` in templates and searches while staying short.
- S-03 The test button part is built from the StateValue, not from the friendly name: the StateValue is immutable after creation (the same source as the key in the unique id), technical, and for a Switch it is `ON` or `OFF`, which gives `_test_on` and `_test_off`; a friendly name is renamable user text. Characters and length are handled by Home Assistant (slugify, 255 cap, `_2` on a collision).
- S-04 No code touches existing entries (finding 7); a test pins that they keep their id.
- S-05 Translations and display names are not touched.
- S-06 The Switch and Select main entities are not touched; tests pin that their ids do not depend on the language.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.claude/CLAUDE.md
@.planning/quick/261003-rmy-native-entities-test-buttons-disabled-by/261003-rmy-SUMMARY.md
@custom_components/mqtt_actions/entities.py
@custom_components/mqtt_actions/button.py
@custom_components/mqtt_actions/select.py
@custom_components/mqtt_actions/sensor.py

Facts verified in the code (do not re-derive):
- entities.py: `MqttActionsEntity(Entity)` is the base of every entity of the integration (`_attr_has_entity_name = True`); `NativeDeviceEntity` extends it. Class order is `class X(MqttActionsEntity, <Platform>Entity)`, so a property defined on `MqttActionsEntity` wins over core. No platform base class (sensor, select, button, switch) defines `suggested_object_id`.
- Unique ids (unchanged by this plan): switch and select `{device_id}`, mode select `{device_id}_mode`, restore button `{device_id}_restore_previous`, test button `{device_id}_test_{trigger.key}` with key from `model.trigger_key(StateValue)` (`SWITCH_ON_KEY`, `SWITCH_OFF_KEY` for a Switch), resync `{entry_id}_resync`, roster `{entry_id}_roster`, instance mode `{entry_id}_instance_mode`.
- Test buttons are disabled by default (creation only), so their registry entries exist with their entity id but no state; tests read their ids from the registry. `DeviceTestButton` takes `trigger: TriggerSpec` (`trigger.value` is the StateValue, `trigger.friendly_name` the display text) and sets `_attr_name = f"Test {trigger.friendly_name}"`, which stays.
- Tests: tests/conftest.py has `make_hub_entry` (instance name "Test instance", so the hub device prefix is `test_instance`), `make_switch_subentry`, `make_select_subentry(name, [(value, friendly, actions)])`, autouse enabling of custom integrations. tests/test_native_entities.py shows the native seeding (`_seed_native`: Store key with `native: {instance: True, pending: [], devices: []}`), `_setup`, `_entity_id(hass, domain, unique_id)`. The harness language defaults to en; the entity platform loads its translations at platform setup, so the language must be set before the entry is set up. tests/test_native_start.py::test_an_upgrade_takes_over_the_legacy_entities_and_marks_the_document is the takeover test that keeps entity ids.
- Prior verify commands (reused verbatim from the previous quick task): `uv run pytest tests -q`, `uv run ruff check .`, `uv run ruff format --check .`. Known flake: tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear fails rarely in a full run and passes alone.
</context>

<tasks>

<task type="tracer">
  <name>Task 1: A new restore button gets an English id in a German instance, an existing one keeps its id (tracer)</name>
  <files>custom_components/mqtt_actions/entities.py, custom_components/mqtt_actions/button.py, tests/test_entity_ids.py</files>
  <read_first>
    custom_components/mqtt_actions/entities.py (MqttActionsEntity)
    custom_components/mqtt_actions/button.py (RestorePreviousButton)
    .venv/lib/python3.14/site-packages/homeassistant/helpers/entity.py lines 735 to 770 (suggested_object_id)
    .venv/lib/python3.14/site-packages/homeassistant/helpers/entity_platform.py lines 1290 to 1330 (_async_derive_object_ids)
    tests/test_native_entities.py lines 1 to 100 and the `_native_select` helper (seeding and setup pattern)
    tests/conftest.py (make_hub_entry, make_select_subentry)
  </read_first>
  <behavior>
    Builder in tests/test_entity_ids.py (reused by Task 2), in two steps so a test can pre-register registry entries in between: a prepare helper takes the language, an `area` flag and the subentries, sets `hass.config.language` BEFORE the entry is added and set up, seeds the native Store key like tests/test_native_entities.py does, adds the entry to hass, and, when `area` is true, creates the area "Küche" and registers the device of every subentry in the device registry under its subentry (identifiers `(DOMAIN, device_id)`, the subentry title as name) with that area, so Home Assistant adds the area part; it returns the entry and the device ids WITHOUT setting the entry up. A second helper sets the entry up and waits for the background tasks.
    - One Select device "Modus Küche" with the options (`kitchen_on`, "Küche an") and (`off`, "Aus"), run for language en and de, with and without the area. The restore button (unique id `{device_id}_restore_previous`) has the registry entity id `button.modus_kuche_restore` without the area and `button.kuche_modus_kuche_restore` with it, identical in en and de.
    - That button is enabled and has a state (hass.states.get is not None), and pressing it through the button.press service on that id raises nothing and publishes nothing (no previous state is known).
    - Its registry `original_name` is "Restore previous state" in en and "Vorherigen Zustand wiederherstellen" in de: the displayed name stays translated while the id is English.
    - Guard (passes before and after the change, state this in the red commit): in a de instance with two Select devices "Modus Küche" and "Modus Bad", the restore button of the first is pre-registered before the setup with the old German id `button.kuche_modus_kuche_vorherigen_zustand_wiederherstellen` (entity registry `async_get_or_create` for domain button, platform DOMAIN, the unique id above, config entry, suggested_object_id set to the old object id so it is used verbatim). After the setup it still has exactly that entity id and that registry id, and has a state under it; the restore button of the second device, which was not registered, gets `button.modus_bad_restore`.
  </behavior>
  <action>
    Implements R-01, R-02, R-03, R-04, R-07 and S-01, S-04, S-05 for the first entity kind.

    RED first: create tests/test_entity_ids.py with the builder and the tests of the behavior block (parametrize language and area), run it and confirm the new-id tests fail for the right reason, that is the id still carries the translated name (German words in de, `restore_previous_state` in en), and commit it alone as `test(quick-261003-sfb): add failing tests for short English entity ids`; the commit body says the keep-the-id guard passes already because existing entries are never renamed.

    Then implement. In entities.py give MqttActionsEntity a class attribute `_entity_id_part` typed `str | None` with default None, and a property `suggested_object_id` that returns the attribute when it is not None and the core value (`super().suggested_object_id`) otherwise. Add a docstring that says why: Home Assistant builds the entity id of a NEW registry entry from this property, adds the area and device parts in front according to its own entity-id setting, and by default derives it from the name translated into the language of the instance; a fixed English part makes the id independent of the language, and an existing registry entry is never renamed by it. If ruff asks for an explicit override marker, use `typing.override` as core does (components/aosmith/select.py). Do not set `entity_id` on any entity, do not touch `_attr_name`, `_attr_translation_key` or the translation files (S-01, S-05). In button.py set `_entity_id_part = "restore"` on RestorePreviousButton and nothing else. Commit as `feat(quick-261003-sfb): give the restore button a short English entity id`.
  </action>
  <verify>
    <automated>uv run pytest tests/test_entity_ids.py tests/test_native_entities.py -q && uv run ruff check . && uv run ruff format --check .</automated>
  </verify>
  <done>The red tests were committed alone first and failed for the right reason; in a de and an en instance, with and without an area, a new restore button has the id part `_restore` after the area and device parts, keeps its translated original name, works through the button.press service, and an already registered restore button keeps its old German entity id and registry id; ruff check and format are clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Every other new entity gets its English id part; full table, keep-the-id guard for every kind and the takeover guard</name>
  <files>custom_components/mqtt_actions/button.py, custom_components/mqtt_actions/select.py, custom_components/mqtt_actions/sensor.py, tests/test_entity_ids.py, tests/test_native_start.py</files>
  <read_first>
    custom_components/mqtt_actions/button.py (ResyncButton, DeviceTestButton and its __init__)
    custom_components/mqtt_actions/select.py (DeviceModeSelect, InstanceModeSelect)
    custom_components/mqtt_actions/sensor.py (RosterSensor)
    tests/test_entity_ids.py (the builder of Task 1)
    tests/test_native_start.py lines 135 to 190 (takeover test) and the imports of tests/test_takeover.py it uses
    custom_components/mqtt_actions/model.py (trigger_key, SWITCH_ON_KEY, SWITCH_OFF_KEY, MAX text cap in const.py MAX_TEXT_LENGTH)
  </read_first>
  <behavior>
    - Table test, parametrized over language en and de and over area false and true: one Select device "Modus Küche" (options `kitchen_on` and `off`), one Switch device "Lampe" and the hub "Test instance". Set up natively. The set of ALL entity ids registered for the config entry equals exactly this mapping from (domain, unique id) to entity id, where P is the device prefix (`modus_kuche` or `kuche_modus_kuche` for the Select device, `lampe` or `kuche_lampe` for the Switch device, with the area on both devices):
      select `{id}` -> `select.P`; select `{id}_mode` -> `select.P_mode`; button `{id}_restore_previous` -> `button.P_restore`; button `{id}_test_{trigger_key("kitchen_on")}` -> `button.P_test_kitchen_on`; button `{id}_test_{trigger_key("off")}` -> `button.P_test_off`;
      switch `{id}` -> `switch.P`; select `{id}_mode` -> `select.P_mode`; buttons `{id}_test_{SWITCH_ON_KEY}` -> `button.P_test_on` and `{id}_test_{SWITCH_OFF_KEY}` -> `button.P_test_off`;
      hub: button `{entry_id}_resync` -> `button.test_instance_resync`, sensor `{entry_id}_roster` -> `sensor.test_instance_instances`, select `{entry_id}_instance_mode` -> `select.test_instance_instance_mode`.
      The Switch and Select main entities (`switch.P`, `select.P`) are identical in en and de. The registry `original_name` of the hub resync button is "Neu synchronisieren" in de and "Resync" in en.
    - Keep-the-id guard in a de instance: before the setup pre-register one entry of every kind (resync, roster sensor, instance mode select, device mode select, restore button, and ONE of the two test buttons) with its old German object id verbatim (examples of the old ids: `button.test_instance_neu_synchronisieren`, `sensor.test_instance_verbundene_instanzen`, `select.test_instance_instanzmodus`, `select.kuche_modus_kuche_modus`). After the setup every pre-registered entry has the same entity id and registry id, and the other test button, which was not registered, got `button.P_test_<value>`.
    - Hostile StateValue: an owned Select option whose StateValue is within MAX_TEXT_LENGTH and made of spaces, slashes, dots, colons, an umlaut and a trailing digit gives a test button whose registry entity id passes `valid_entity_id`, starts with `button.` and is at most 255 characters; the setup does not raise. (Core slugify and the `_2` collision handling do the work; this pins that a value from the broker of a mirror cannot produce an invalid id.)
    - Takeover guard (passes before and after the change; say so in the red commit): tests/test_native_start.py::test_an_upgrade_takes_over_the_legacy_entities_and_marks_the_document is parametrized over language en and de (the language set on hass first), and after the takeover asserts for every legacy entity (the switch and both test buttons) that `entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)` still returns the entity id it had under core MQTT, so the legacy test buttons keep their old ids and unique ids in a German instance.
  </behavior>
  <action>
    Implements R-01, R-02, R-03, R-04, R-06, R-07 and S-02, S-03, S-04, S-06.

    RED first: extend tests/test_entity_ids.py with the table, the keep-the-id and the hostile-value tests, and parametrize the takeover test in tests/test_native_start.py as described. Run them, confirm the table, keep-the-id (the not-registered test button) and hostile-value tests fail for the right reason (the old translated or friendly-name based parts) and that the takeover guard passes, and commit as `test(quick-261003-sfb): add failing tests for the English id parts of every entity`.

    Then implement, one attribute each, no other change. In button.py: `_entity_id_part = "resync"` on ResyncButton; in `DeviceTestButton.__init__` set the instance attribute `_entity_id_part` to the text `test_` followed by `trigger.value` (S-03); it is set once and is not recomputed in `_on_signal`, because the StateValue never changes while the friendly name does, and the display name `Test <friendly name>` stays as it is. In select.py: `_entity_id_part = "mode"` on DeviceModeSelect and `"instance_mode"` on InstanceModeSelect. In sensor.py: `_entity_id_part = "instances"` on RosterSensor. Do not touch DeviceSwitch, DeviceSelect, unique ids, translation keys or translations (S-05, S-06). Commit as `feat(quick-261003-sfb): give every new entity a short English entity id`.
  </action>
  <verify>
    <automated>uv run pytest tests/test_entity_ids.py tests/test_native_entities.py tests/test_native_start.py tests/test_takeover.py tests/test_hub_entities.py tests/test_modes.py tests/test_companions.py -q && uv run ruff check . && uv run ruff format --check .</automated>
  </verify>
  <done>The red tests were committed first; every new entity kind (restore, test buttons, mode select, resync, roster, instance mode) gets its English part in en and de with and without an area; the Switch and Select main entity ids are language independent; every pre-registered entry keeps its entity id and registry id; a hostile StateValue gives a valid id; the German takeover run keeps the legacy ids and unique ids; ruff check and format are clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Describe the entity id suffixes in the docs, pin them, sweep for the old ids</name>
  <files>tests/test_docs.py, README.md, docs/operations.md</files>
  <read_first>
    tests/test_docs.py (helpers `_page`, `_section`, `_normalize`; the test test_docs_describe_the_restore_button_and_the_diagnostic_test_buttons as the pattern)
    README.md (section Upgrading from 0.1.x, the bullet Test buttons; section Run mode, test buttons and the circuit breaker)
    docs/operations.md (the paragraph about the Mode select and the test buttons; section Upgrade notes, the bullet Test buttons)
  </read_first>
  <behavior>
    - A docs test, written first, imports the code so the docs cannot drift: for README.md and docs/operations.md the normalized text of the upgrade section (README: the section "upgrading from 0.1"; operations: the section "upgrade notes") contains, with a leading underscore, the `_entity_id_part` of ResyncButton, RestorePreviousButton, DeviceModeSelect, InstanceModeSelect and RosterSensor read from the classes, the text `_test_<statevalue>` (the normalized form of `_test_<StateValue>`), the word "english" and the phrase "never renamed".
    - The README section "run mode, test buttons" contains `_test_<statevalue>` and the example `_test_on`.
  </behavior>
  <action>
    Implements R-03, R-06, R-07 and S-02, S-03.

    RED first: add the docs test to tests/test_docs.py and commit it alone as `test(quick-261003-sfb): add failing docs test for the entity id suffixes`.

    Then write the docs. README.md, in the section Upgrading from 0.1.x after the bullet Test buttons, add a bullet `Entity ids.` that says: ids of entities that exist are never renamed; entities created from 0.2.0 on get a short English id part whatever the language of Home Assistant, listed as the suffixes `_mode`, `_restore`, `_resync`, `_instances`, `_instance_mode` and `_test_<StateValue>` (for example `_test_on`), after the area and device parts that Home Assistant adds according to its own entity ID setting; the displayed names stay translated; to get the short ids for old entities the user renames them by hand or uses the Home Assistant function that regenerates entity ids, which is the user's choice. In the section Run mode, test buttons and the circuit breaker add one sentence after the sentence that names `Test ON` and `Test OFF`: the id of a test button ends in `_test_<StateValue>`, for example `_test_on`, and does not change when the option is renamed. docs/operations.md: add the same bullet (same wording, same suffix list) to the Upgrade notes after its Test buttons bullet, and one sentence to the paragraph that describes the Mode select and the test buttons pointing to the suffixes. Do not rewrite the existing sentences about kept entity ids and the downgrade `_2` effect; they stay true. No new page, no change to docs/troubleshooting.md or the ADR. Commit as `docs(quick-261003-sfb): describe the English entity id suffixes`.

    Finally run the sweep for reliance on the old ids (R-06): the three commands of the verify block. Tests, fixtures, README and docs must not contain an old generated id (the German id fragments exist only in tests/test_entity_ids.py, where they are the pre-registered old ids of the keep-the-id guard); if the sweep finds one, fix that file in this task and mention it in the SUMMARY.
  </action>
  <verify>
    <automated>uv run pytest tests -q && uv run ruff check . && uv run ruff format --check . && test -z "$(grep -rnE '(button|select|sensor|switch)\.[a-z0-9_]*(neu_synchronisieren|verbundene_instanzen|instanzmodus|vorherigen_zustand|_modus)\b' README.md docs custom_components)" && test -z "$(grep -rlE '(button|select|sensor|switch)\.[a-z0-9_]*(neu_synchronisieren|verbundene_instanzen|instanzmodus|vorherigen_zustand|_modus)\b' tests | grep -v '^tests/test_entity_ids.py$')" && git diff --quiet 69537ee -- custom_components/mqtt_actions/translations</automated>
  </verify>
  <done>The docs test was committed red first and now passes; README and docs/operations.md list the suffixes, say that existing ids are never renamed and that names stay translated; the whole suite, ruff check and ruff format pass; the sweep finds no old generated id outside tests/test_entity_ids.py; the translation files are unchanged.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| broker -> mirror document -> StateValue -> test button entity id part | A foreign owner's StateValue text now shapes part of a locally generated entity id |
| integration -> entity registry | Existing registry entries carry user customisations and the ids automations depend on; the integration must not rewrite them |

## STRIDE Threat Register

Threat IDs continue after the highest of the previous quick task of the day (T-261003-06), so none is used twice.

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-261003-07 | Tampering | `DeviceTestButton` entity id part built from a StateValue that a foreign owner of a mirror controls | low | mitigate | The part is only a suggestion to the entity registry: Home Assistant slugifies it, caps the entity id at 255 characters and appends `_2` on a collision, so it can neither be invalid nor take an existing id. A test with a hostile value (spaces, slashes, dots, colons, umlaut) asserts `valid_entity_id`. The unique id, which decides identity, is unchanged (S-03). |
| T-261003-08 | Tampering | Existing entity ids of automations, dashboards and history (integrity of identity) | medium | mitigate | No code renames or migrates anything (S-04); the override only changes the id of a registry entry that does not exist yet (finding 7). A keep-the-id test for every entity kind in a de instance and the German takeover test pin that ids, registry ids and unique ids of existing entries, including legacy test buttons, stay. |
| T-261003-09 | Information Disclosure | Device or area names inside entity ids | low | accept | Unchanged behaviour: the device and area parts were already in the ids; only the entity part changes, and it contains no secret (a StateValue is already shown in the UI as the test button name). |
| T-261003-SC | Tampering | npm/pip/cargo installs | high | accept | No package-manager install in this plan; no dependency is added or changed. |
</threat_model>

<verification>
- `uv run pytest tests -q` (whole suite, with tests/test_native_entities.py, tests/test_native_start.py, tests/test_takeover.py, tests/test_hub_entities.py, tests/test_modes.py, tests/test_companions.py and tests/test_translations.py unchanged apart from the one parametrization in test_native_start.py) passes; `uv run ruff check .` and `uv run ruff format --check .` are clean. The known flake of tests/test_manager.py passes when rerun alone.
- Git history shows three RED commits (`test(quick-261003-sfb): ...`) each before its `feat` or `docs` commit; no file deleted; the translation files, unique ids, STORE_VERSION and the Store keys are unchanged; no code mentions `new_entity_id`, `async_update_entity` for an id, or any rename.
- Source coverage audit (all four source types):
  - GOAL (task description): short English ids for new entities in a German instance -> Tasks 1 and 2; existing ids untouched -> Tasks 1 and 2 (guards) and finding 7; docs -> Task 3; TDD with a German language -> every task.
  - REQ: ENT-01 (native entities with unchanged unique ids: S-04, S-06) and MIG-01 (existing entities keep entity id, registry id, device id, area, name: the keep-the-id tests and the German takeover guard) are protected, not changed.
  - RESEARCH: none for a quick task; the source checks of R-05 are findings 1 to 8 in the objective.
  - CONTEXT: R-01 -> Tasks 1 and 2; R-02 -> S-02, Tasks 1 and 2; R-03 -> S-05, Tasks 1 and 2 (original_name); R-04 -> S-04, Tasks 1 and 2; R-05 -> findings 1 to 8; R-06 -> finding 8, Tasks 2 and 3 (sweep); R-07 -> all.
- Residual risk, stated: the override relies on `Entity.suggested_object_id` being a plain overridable property, true in the installed 2026.9.4 and used by core integrations; the floor of hacs.json is 2026.9.0, which could not be checked here. The new tests pin the behaviour against every Home Assistant version the suite runs on (Renovate bumps PHACC together with Home Assistant).
- Not decided here, for the user: the area and device parts stay (finding 6). If the user wants ids without them too, that is a different decision (preset the entity id, S-01 rejected) with the costs named in finding 6.
</verification>

<success_criteria>
- In a German instance a new device gets `..._restore`, `..._test_on`, `..._mode` and, on the hub, `..._resync`, `..._instances`, `..._instance_mode` ids, the same as in an English instance, while the displayed names stay German.
- Every entity that existed before keeps its id, registry id and unique id; a legacy test button taken over from core MQTT keeps its old id.
- The suite and ruff are green; README and docs/operations.md name the suffixes; no test or doc relies on an old generated id.
</success_criteria>

<output>
Create `.planning/quick/261003-sfb-native-entity-ids-shorter-and-english/261003-sfb-SUMMARY.md` when done
</output>
