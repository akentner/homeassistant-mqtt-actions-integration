---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
verified: 2026-10-03T20:00:00Z
status: passed
score: 5/5 must-haves verified
covered_files:
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-01-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-01-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-02-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-02-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-03-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-03-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-04-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-04-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-05-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-05-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-06-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-06-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-07-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-07-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-08-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-08-SUMMARY.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-09-PLAN.md
  - .planning/phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-09-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/presence.py
  - custom_components/mqtt_actions/select.py
  - custom_components/mqtt_actions/sensor.py
  - custom_components/mqtt_actions/switch.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/takeover.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - docs/adr/0001-native-entities-instead-of-mqtt-discovery.md
  - docs/assets/icon.svg
  - docs/broker-acl.md
  - docs/operations.md
  - docs/troubleshooting.md
  - tests/conftest.py
  - tests/documents.py
  - tests/fake_broker.py
  - tests/test_cutover.py
  - tests/test_cutover_instances.py
  - tests/test_discovery_export.py
  - tests/test_docs.py
  - tests/test_document.py
  - tests/test_entity_ids.py
  - tests/test_fake_broker.py
  - tests/test_hub_removal.py
  - tests/test_native_cleanup.py
  - tests/test_native_entities.py
  - tests/test_native_start.py
  - tests/test_presence.py
  - tests/test_takeover.py
  - tests/test_translations.py
covered_digest: "v2:sha256:f09e8b67108193a5f609f6eabf796f7a7591bfcc8dc2ecd331ea0678313b9854"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
gaps: []
---

# Phase 5: Evaluate native switch/select entities instead of MQTT Discovery Verification Report

**Phase Goal:** Switch and select entities owned by the MQTT Actions config entry replace MQTT Discovery as the default way device entities are created, so every device and entity of every instance, mirrors included, shows on the integration page; existing installations migrate automatically with entity ids, history and registry customizations intact; MQTT Discovery stays only as an optional export.
**Verified:** 2026-10-03
**Status:** passed
**Re-verification:** Yes. The previous report (human_needed) went stale because source changed afterwards: quick tasks 261003-rmy and 261003-sfb, the new brand icon and the 1.0.0 version bump. UAT is `complete` (05-UAT.md); the previously open human items are now either passed in UAT or explicitly accepted by the owner.

## Goal Achievement

Everything that can be proven in the repository is proven in this run. Full suite `uv run pytest tests -q -p no:cacheprovider`: 1458 passed, 1 failed. The failure is the known flake `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` (the assertion at test_manager.py:950 caught an asyncio "Executing ... took 0.125 seconds" slow-callback log record under full-suite load, not a behavior defect); rerun alone three times it passed each time (1 passed). `uv run ruff check .` clean, `uv run ruff format --check .` clean (88 files).

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every owned device and every mirror shows its switch or select, test buttons and mode select as entities of this integration | VERIFIED | `switch.py` DeviceSwitch, `select.py` DeviceSelect / DeviceModeSelect, `button.py` DeviceTestButton are platform entities of the hub entry; owned devices use `config_subentry_id=manager.subentry_id_of(device_id)`, mirrors `None`. Tests `test_native_switch_is_registered_under_the_subentry`, `test_a_marked_mirror_is_a_native_entity_directly_under_the_entry`. UAT test 2 (page counting on the follower) passed on a real instance. Quick task rmy makes NEW test buttons diagnostic and disabled by default: they are still registry entities of this integration (listed as disabled on the page) and existing entries are untouched, so the criterion holds; the restore button is an addition |
| 2 | Toggling a native entity on any instance publishes to the shared retained state topic and actions run locally on every participating instance as before | VERIFIED | `Manager.async_send_state` publishes retained at QoS 1 and changes nothing locally. `test_a_native_toggle_runs_the_actions_on_every_instance` passes in the full run. New `async_restore_previous` reuses `async_send_state` (no second publish path); `_track_previous` only records history on the echo and never alters triggering (the diff of `_record_value` adds the old-value capture and one call, the trigger path is unchanged) |
| 3 | An installation upgraded from 0.1.0 keeps entity ids, registry ids, device ids, areas, names and history without a manual step | VERIFIED | `takeover.py` is unchanged since c43deaf and still has 0 matches for `homeassistant.components|async_publish`. Takeover tests (`test_full_takeover_sequence_keeps_identity`, `test_an_upgrade_takes_over_the_legacy_entities_and_marks_the_document`, reload identity pin) pass. Quick-task regression check: the only entity-id mechanism added is the `suggested_object_id` override in `entities.py`, which Home Assistant consults only when a NEW registry entry is created; `tests/test_entity_ids.py::test_every_existing_entity_keeps_its_old_german_id` pre-registers old German ids for resync, roster, instance mode, device mode, restore and test button and asserts entity id, registry id and unique id are identical after setup; the sfb takeover test is parametrized over en and de. `_test_button_category` hands an existing entry its own category back and `_attr_entity_registry_enabled_default` is creation-only, so taken-over buttons keep category and enabled state. UAT test 1 passed on a real 0.1.0 -> 0.2.0 run (ids, registry ids, names, areas kept, discovery topics cleared) |
| 4 | The owner switches to native only when no online peer is a legacy instance, and a mixed fleet keeps working throughout | VERIFIED (automated); real mixed fleet accepted as debt | `presence.py`, `sync.py`, `document.py` unchanged since c43deaf. The version bump to 1.0.0 is not used for any capability decision: presence compares the `native` capability flag only (the `version` field is display text), so 1.0.0 cannot flip legacy detection. `tests/test_cutover.py`, `tests/test_cutover_instances.py`, `tests/test_native_start.py` pass. UAT test 3 accepted without reproduction, test 4 skipped (see accepted debt) |
| 5 | MQTT Discovery is published only as an optional export; documentation, ACL page and translations say so | VERIFIED | `discovery.py` unchanged since c43deaf (`build_export`: `enabled_by_default: False`, no buttons); hub option default off, default prefix `mqtt_actions_export`. `tests/test_discovery_export.py`, `tests/test_native_cleanup.py`, `tests/test_docs.py`, `tests/test_translations.py` pass. README "MQTT Discovery export", `docs/broker-acl.md`, en/de option texts present. New quick-task documentation (restore button, diagnostic test buttons, id suffixes) is pinned by `tests/test_docs.py` |

**Score:** 5/5 truths verified (0 behavior-unverified; the behavior-dependent truths 2, 3 and 4 each have passing behavioral tests)

### Changes since the previous verification (regression review)

| Change | Regression check | Result |
|--------|------------------|--------|
| Quick 261003-rmy: restore button, `previous_state` attribute, Store key `previous_states` | Store key is additive and written only when non-empty (`_data_to_save`), strict parser drops malformed items, no STORE_VERSION bump, entries filtered to kept ids, dropped on delete, tombstone and release; `tests/test_manager_breaker.py` (exact Store key set) unchanged and green. Restore publishes through the existing retained QoS 1 path. No document or hash change | no regression |
| Quick 261003-rmy: new test buttons diagnostic + disabled by default | Creation-only; existing entries keep category and enabled state (existing-entry guard test). Design change to the default visibility of NEW test buttons, documented in README and operations.md, not a violation of success criterion 1 | no regression |
| Quick 261003-sfb: short English id parts via `suggested_object_id` | Existing ids never renamed (keep-the-id guard test for every kind, takeover test in en and de); unique ids unchanged (`{device_id}`, `_test_<key>`, `_mode`, `_restore_previous`); no registry write or migration added | no regression |
| New brand icon (`brand/icon.png`, `icon@2x.png`, `docs/assets/icon.svg`) | Asset only | no regression |
| Version 1.0.0 (manifest, README, docs, `tests/test_docs.py`) | Documentation pins 1.0.0; heartbeat `version` is informational; release tag/notes are an owner step | no regression |

### Required Artifacts and Key Links

All artifacts exist, are substantive and wired (entities register through `PLATFORMS` SWITCH, SELECT, BUTTON, SENSOR; `Manager` feeds them via dispatcher signals; takeover is called from `Manager._async_native_takeover`). No stubs: native entities read manager state and publish through `async_send_state`.

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `DeviceSwitch.is_on` / `DeviceSelect.current_option` | `device.value` | `_on_message` on the shared state topic (accepted StateValue only), dispatcher signal | Yes | FLOWING |
| `DeviceSelect.extra_state_attributes["previous_state"]` | `Manager.previous_value` | `_track_previous` on the echo, persisted in the Store | Yes | FLOWING |
| `NativeDeviceEntity.available` | owner presence | `sync.instance_status(owner)` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Whole suite (run once) | `uv run pytest tests -q -p no:cacheprovider` | 1458 passed, 1 failed (known flake) | PASS with flake |
| Known flake alone | `uv run pytest tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear -q` (3 runs) | 1 passed each | PASS |
| Lint and format | `uv run ruff check .`, `uv run ruff format --check .` | clean, 88 files formatted | PASS |
| takeover.py purity | `grep -c "homeassistant.components\|async_publish" custom_components/mqtt_actions/takeover.py` | 0 | PASS |
| Debt markers | grep TBD/FIXME/XXX in custom_components, tests, docs, README | none | PASS |

Probe Execution: no `probe-*.sh` declared or present, skipped.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| ENT-01 | Native Switch, Select, test-button entities under subentry or entry, unique ids unchanged | SATISFIED | switch.py, select.py, button.py; unique ids equal the legacy ones |
| ENT-02 | State from the shared topic, retained QoS 1 commands, availability follows the owner | SATISFIED | `async_send_state`, `NativeDeviceEntity.available`, toggle test |
| ENT-03 | Optional export, off by default, `enabled_by_default` false, prefix, duplicate warning | SATISFIED | discovery.py `build_export`, options flow, translations, README |
| MIG-01 | Takeover with identity intact, no manual step | SATISFIED | takeover.py, `_async_native_takeover`, identity tests, UAT 1 pass |
| MIG-02 | Owner keeps legacy while an online peer is not native-capable; additive unhashed markers | SATISFIED | presence.py, document.py, cutover tests |
| MIG-03 | Healing, ghost cleanup, issues, test topic only on the legacy path | SATISFIED | `heals_discovery` / `is_native` gates, `tests/test_native_cleanup.py` |
| DEC-01 | ADR with Go/No-Go against the four criteria | SATISFIED | docs/adr/0001-native-entities-instead-of-mqtt-discovery.md, Status: Accepted |

No orphaned requirements: REQUIREMENTS.md maps no further ID to Phase 5 (rows ENT-01..DEC-01 all Complete).

### Anti-Patterns Found

None blocking. No unreferenced TBD/FIXME/XXX in modified files; no empty implementations on a rendering path.

### Accepted human-verification debt (not gaps)

Recorded in 05-UAT.md (`complete`; 5 passed, 4 skipped, 0 issues). The owner accepted these explicitly:

| UAT test | Item | Disposition |
|----------|------|-------------|
| 3 | Mixed fleet and live follower cutover (A5) | Accepted without reproduction; covered by `tests/test_cutover_instances.py` on a fake broker |
| 4 | Straggler 0.1.0 instance after the cutover | Skipped by owner (needs a real mixed fleet) |
| 5 | Late replay race (A4) | Skipped by owner; ties to IN-03, accepted |
| 6 | Commands across two real instances | Skipped by owner; will be exercised in the production rollout; automated two-instance fake-broker test passes |
| 7 | Discovery export on/off and `homeassistant` prefix | Skipped by owner; automated export tests pass |

Passed in UAT on real instances: 1 (upgrade path), 2 (integration page counting), 8 (delete and removal), 9 (owner decision on review items).

### Accepted warnings (owner decision, documented in README Limitations)

- **WR-03 (partial):** a forged retained `offline` availability still lifts a cutover block and a peer cleanly offline at the 5 s check is not waited for.
- **IN-02:** `with_native_marker` drops the marker near `MAX_DOCUMENT_BYTES`.
- **IN-03:** the takeover can race a boot-time retained legacy replay; duplicates are cleaned at the next pass (`test_a_late_replay_duplicate_is_cleaned_at_the_next_call`).

### Housekeeping for the orchestrator

- `.planning/ROADMAP.md` still shows the Phase 5 checkbox (line 21) unchecked; update it when closing the phase.
- Release tag and GitHub release for 1.0.0 are an owner step.

### Gaps Summary

No gaps. All five roadmap success criteria and all seven requirement IDs are backed by existing, substantive, wired code and passing tests. The quick tasks, icon and version bump do not regress any criterion; existing entity ids are never renamed and the takeover identity guarantees are unchanged and still pinned by tests. Remaining real-instance checks are owner-accepted debt, not failures.

---

_Verified: 2026-10-03_
_Verifier: Claude (gsd-verifier)_
