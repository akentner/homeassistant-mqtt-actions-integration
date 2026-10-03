---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
verified: 2026-10-03T00:00:00Z
status: human_needed
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
  - custom_components/mqtt_actions/switch.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/takeover.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - docs/adr/0001-native-entities-instead-of-mqtt-discovery.md
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
  - tests/test_fake_broker.py
  - tests/test_hub_removal.py
  - tests/test_native_cleanup.py
  - tests/test_native_entities.py
  - tests/test_native_start.py
  - tests/test_presence.py
  - tests/test_takeover.py
  - tests/test_translations.py
covered_digest: "v2:sha256:1d59d5274b22057fbe925da88f0254c08279f0476ed935758bb669af15359104"
behavior_unverified: 0
overrides_applied: 0
re_verification: false
gaps: []
human_verification:
  - test: "Upgrade path (A4): upgrade a real 0.1.0 instance (ha-one) to this build with a customized legacy device (area, user name, history)"
    expected: "Entity ids, registry ids and device ids unchanged; area and name kept; recorder history continuous; entities listed on the MQTT Actions integration page; no retained discovery topic left for the device"
    why_human: "Needs a real HA with a real recorder and real core MQTT; the tests use the core MQTT discovery in-process but cannot show recorder continuity or the real frontend"
  - test: "Integration page counting (A1): open the MQTT Actions page on the follower instance"
    expected: "All devices and entities of the other instance (mirrors) appear, the owner is named in the model text, counts match what the owner has"
    why_human: "How the frontend counts and groups devices and entities per config entry and subentry is an assumption (A1) that only a browser on a real instance settles"
  - test: "Mixed fleet and live follower cutover (A5): run ha-one on this build and ha-two on v0.1.0, then update ha-two"
    expected: "Repairs issue native_cutover_waiting names the v0.1.0 instance and nothing is switched; after the update both instances switch with no manual step, the running follower reloads on its own, customizations are kept"
    why_human: "Needs two real instances, a real broker and a real reload; the harness proves it with a fake broker only"
  - test: "Straggler: keep one v0.1.0 instance running after the cutover of the others"
    expected: "It keeps running actions, shows no entities for migrated devices, raises no error"
    why_human: "Needs a real v0.1.0 build next to a native fleet"
  - test: "Late replay race (A4): re-publish the legacy retained discovery payload of a migrated device, then restart twice"
    expected: "No _2 duplicate entity appears and the registry stays single (see warning IN-03)"
    why_human: "Depends on when real core MQTT processes retained discovery relative to async_wait_ready; not reproducible with the in-process mock"
  - test: "Commands: toggle a native switch or select on each approved instance, then publish a payload that matches no StateValue"
    expected: "The actions run exactly once on every approved instance; the unknown payload is ignored and the state does not change"
    why_human: "Real broker retain and QoS 1 delivery across two real instances"
  - test: "Export: switch the discovery export on with prefix mqtt_actions_export, then with prefix homeassistant, then off"
    expected: "Retained payloads carry enabled_by_default false and no buttons; the core prefix yields only disabled duplicates; off clears the topics"
    why_human: "Real core MQTT discovery and a real broker are needed to see the disabled duplicates"
  - test: "Delete and removal: delete an owned device, then remove the integration"
    expected: "The device and its entities disappear from the registry and the integration page; retained document, state and discovery topics are cleared as the options say"
    why_human: "Real registry UI and broker retained state"
  - test: "Open review items (decision, not verification): WR-03 (forged retained offline availability still lifts a block; a peer cleanly offline at the 5 s check is not waited for), IN-02 (with_native_marker drops the marker near the size limit), IN-03 (takeover can race a boot-time retained replay)"
    expected: "Owner decides to accept for 0.2.0 (documented) or schedule a follow-up"
    why_human: "05-REVIEW-DISPOSITION.md marks them intentionally open pending an owner decision (ACL, settle time, persisted native set, publish order)"
---

# Phase 5: Evaluate native switch/select entities instead of MQTT Discovery Verification Report

**Phase Goal:** Switch and select entities owned by the MQTT Actions config entry replace MQTT Discovery as the default way device entities are created, so every device and entity of every instance, mirrors included, shows on the integration page; existing installations migrate automatically with entity ids, history and registry customizations intact; MQTT Discovery stays only as an optional export.
**Verified:** 2026-10-03
**Status:** human_needed
**Re-verification:** No, initial verification (covers the code review fixes 225557a..c43deaf)

## Goal Achievement

Everything that can be proven in the repository is proven: the code exists, is wired, and is exercised by tests that pass in this run (`uv run pytest tests -q`: 1414 passed in 94.6 s; ruff check and ruff format --check clean). What cannot be proven here is behavior against a real Home Assistant frontend, recorder and broker, which is reported as human verification, not as failure.

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every owned device and every mirror shows its switch or select, test buttons and mode select as entities of this integration | VERIFIED (code and tests); page counting is human item 2 | `switch.py` `DeviceSwitch`, `select.py` `DeviceSelect`/`DeviceModeSelect`, `button.py` `DeviceTestButton` are platform entities of the hub entry (`PLATFORMS` in `__init__.py` includes SWITCH, SELECT, BUTTON). Owned devices use `config_subentry_id=manager.subentry_id_of(device_id)`, mirrors pass `None` (directly under the entry). `device_info_for` shares one device for entity, mode select and buttons and names the owner on mirrors. Tests: `test_native_switch_is_registered_under_the_subentry`, `test_a_marked_mirror_is_a_native_entity_directly_under_the_entry` |
| 2 | Toggling a native entity on any instance publishes to the shared retained state topic and actions run locally on every participating instance as before | VERIFIED | `Manager.async_send_state` publishes the exact StateValue to `state_topic` with `retain=True, qos=1`, changes nothing locally; state comes from `_on_message` -> `_record_value` -> `SIGNAL_DEVICE_STATE`, then the unchanged trigger path. Two real setups on a fake broker: `test_a_native_toggle_runs_the_actions_on_every_instance` asserts `("ON", True, 1)`, exactly one run per instance, unknown payload ignored. Passes |
| 3 | An installation upgraded from 0.1.0 keeps entity ids, registry ids, device ids, areas, names and history without a manual step | VERIFIED in tests; real-instance and history confirmation is human item 1 | `takeover.py` `async_take_over`: identity check (platform, entry, device, domain, unique-id shape), bounded wait for unload, entities first then device then companion merge, no publish and no MQTT import (grep count 0). `manager._async_native_takeover` orders migrate payload, move, registry flush, retained clear. Tests: `test_full_takeover_sequence_keeps_identity`, `test_an_upgrade_takes_over_the_legacy_entities_and_marks_the_document` (asserts registry id, entity id, device id, area, name_by_user, subentry, published order `migrate` then retained clear), core negative controls in `tests/test_takeover.py`, reload identity pin 950a6c0. History is keyed by entity id, which the tests pin as unchanged; recorder continuity itself is not testable here |
| 4 | The owner switches to native only when no online peer is a legacy instance, and a mixed fleet keeps working throughout | VERIFIED | `presence.blocking_peers` (legacy online, silent announced-online, saturated roster; offline and stale never block); `Manager._async_cutover_check` persists the flag once, makes devices pending, schedules the reload; `_show_cutover_hint` raises Repairs `native_cutover_waiting` (translated en and de). Live follower flip via `async_apply_mirror` / `_follow_native_status`. Tests: `test_a_legacy_install_without_peers_cuts_over_after_the_settle_time`, `test_a_legacy_peer_online_blocks_the_owner_and_going_offline_releases_it`, `test_the_owner_cuts_over_and_a_running_follower_follows` (single follower reload), adoption tests in `tests/test_native_start.py` |
| 5 | MQTT Discovery is published only as an optional export; documentation, ACL page and translations say so | VERIFIED | `discovery.build_export` emits one component with `enabled_by_default: False`, no buttons, no test topic; `async_publish_discovery` publishes the export for a native device only when the hub option is on (default off, default prefix `mqtt_actions_export`); legacy payload only on the legacy path. Healing, discovery issues and test-topic subscription gated by `heals_discovery` / `is_native` (MIG-03). README sections "Upgrading from 0.1.x" and "MQTT Discovery export", `docs/broker-acl.md` `<export prefix>/` row, en and de option texts with the duplicate warning. Tests: `tests/test_discovery_export.py`, `tests/test_native_cleanup.py`, `tests/test_docs.py` (5 new), `tests/test_translations.py` |

**Score:** 5/5 truths verified (0 present-but-behavior-unverified; the behavior-dependent truths 2, 3 and 4 each have a passing behavioral test)

### Plan-level must-haves and prohibitions

| Item | Status | Evidence |
|------|--------|----------|
| 05-01: spike scenarios pinned as core regression tests, ADR with four criteria, requirements registered, Go gate | VERIFIED | `tests/test_takeover.py` (test_full_takeover_sequence_keeps_identity, plain clear deletes entry, migrate-then-clear, loaded entity refuses move, device-first removes entities, duplicate unguarded); ADR 0001 `Status: Accepted`, all four criteria; REQUIREMENTS.md rows |
| 05-01 prohibition: no `custom_components/` change in the plan's commits | VERIFIED | `git show --name-only` of 33befed, ee61b54, 402f624 lists no `custom_components` path |
| 05-02 prohibition: takeover.py never publishes or imports MQTT | VERIFIED | `grep -c "homeassistant.components\|async_publish" takeover.py` prints 0 |
| 05-02 prohibition: failing identity check never moves an entry | VERIFIED | `test_a_foreign_mqtt_entity_with_the_same_unique_id_is_left_alone` passes |
| 05-05 prohibitions (clear never precedes takeover; no publish for a non-owned pending id) | VERIFIED | `test_an_upgrade_takes_over_...` asserts publish order; `test_the_pass_never_publishes_for_an_id_that_is_not_owned` passes (test-tier, enforcement wired and run green) |
| 05-03/04: marker never hashed, SCHEMA_VERSION stays 1, one-way native mirror | VERIFIED | `document.NATIVE_KEY/NATIVE_VALUE`, strict parse, `tests/test_document.py`; one-way caveat in warning IN-02 |
| 05-06: heartbeat capability, settle timer, Repairs hint, suite disables timer by default | VERIFIED | `presence.py` capability key, `conftest.py` autouse fixture, `tests/test_cutover.py` |
| 05-07: real-setup harness, marker-only documents reach the manager | VERIFIED | `tests/fake_broker.py` `real_setup`, `sync.py` `parsed.native` path |
| 05-08: export options, republish on change, legacy-only machinery, native delete lifecycle | VERIFIED | `config_flow.py` `CONF_DISCOVERY_EXPORT`, `Manager._async_apply_export_options`, `tests/test_discovery_export.py`, `tests/test_native_cleanup.py`, `tests/test_hub_removal.py` |
| 05-09: documentation pinned, project record, version 0.2.0 | VERIFIED | `manifest.json` version 0.2.0; five documentation tests green |

### Code review fixes (225557a..c43deaf)

CR-01, WR-01, WR-02, WR-04, IN-01 and IN-04 are in the code (flush via `takeover.async_flush_registries` before the clear, `has_moved_entities` and `_clear_unconfirmed` for WR-02, `_carries_the_identity` for WR-04, no dead tail in `_follow_native_status`) and covered by tests in the green suite. WR-03 is fixed only in part and IN-02 and IN-03 are open by decision (see Warnings).

### Requirements Coverage

| Requirement | Source plans (PLAN frontmatter) | Description | Status | Evidence |
|-------------|--------------------------------|-------------|--------|----------|
| ENT-01 | 05-03, 05-04, 05-07, 05-09 | Native switch, select and test-button entities under subentry or entry, unique ids unchanged | SATISFIED | switch.py, select.py, button.py; unique ids `device_id`, `<id>_test_<key>`, `<id>_mode` equal the legacy ones |
| ENT-02 | 05-03, 05-04, 05-07, 05-09 | State from the shared topic, commands retained QoS 1, availability follows the owner | SATISFIED | `async_send_state`, `NativeDeviceEntity.available` via `instance_status(owner)`, toggle test |
| ENT-03 | 05-08, 05-09 | Optional export: off by default, `enabled_by_default` false, configurable prefix, duplicate warning | SATISFIED | `build_export`, options flow, translations, README |
| MIG-01 | 05-01, 05-02, 05-05, 05-09 | Takeover with identity intact, no manual step | SATISFIED (tests); real-instance UAT pending | takeover.py, `_async_native_takeover` |
| MIG-02 | 05-04, 05-05, 05-06, 05-07, 05-09 | Mixed versions: owner keeps legacy while an online peer is not capable; additive unhashed markers | SATISFIED | presence.py, document.py, cutover tests |
| MIG-03 | 05-03, 05-05, 05-06, 05-08, 05-09 | Healing, ghost cleanup, issues and test topic only on the legacy path | SATISFIED | `heals_discovery`, `is_native` gates in manager.py and sync.py, `tests/test_native_cleanup.py` |
| DEC-01 | 05-01, 05-09 | ADR with Go/No-Go against the four criteria | SATISFIED | docs/adr/0001-native-entities-instead-of-mqtt-discovery.md, Status: Accepted |

All seven IDs from the phase are claimed by at least one PLAN and defined in REQUIREMENTS.md (lines 75-81, traceability rows 167-173, all marked Complete). No orphaned requirements: REQUIREMENTS.md maps no further ID to Phase 5.

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `DeviceSwitch.is_on` / `DeviceSelect.current_option` | `device.value` | `_on_message` on the shared state topic, accepted StateValue only, dispatcher signal | Yes (broker echo) | FLOWING |
| `NativeDeviceEntity.available` | owner presence | `sync.instance_status(owner)` from retained availability | Yes | FLOWING |
| Mirror entities | `Manager.mirrors` / `MirrorInfo.native` | pinned owner's document `entities` marker | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Whole suite (run once) | `uv run pytest tests -q -p no:cacheprovider` | 1414 passed in 94.6 s | PASS |
| Lint and format | `uv run ruff check .` / `uv run ruff format --check .` | all checks passed, 87 files formatted | PASS |
| takeover.py purity | `grep -c "homeassistant.components\|async_publish" custom_components/mqtt_actions/takeover.py` | 0 | PASS |
| Named acceptance tests exist | grep for the 10 plan-named tests | all found | PASS |

Probe Execution: no `probe-*.sh` is declared or present, skipped.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (changed files) | - | TBD / FIXME / XXX markers | none found | no unreferenced debt markers in `custom_components`, `tests`, `docs`, `README.md` |

No stubs: every native entity reads real manager state and publishes through the gateway.

### Warnings (not gaps; carried from 05-REVIEW-DISPOSITION.md, intentionally open)

- **WR-03 (partial):** a capability claim can no longer replace a blocking legacy row and a saturated roster blocks, but a forged retained `offline` availability still lifts a block, and a peer cleanly offline at the 5 s check is not waited for. The cutover is one-way, so such a peer loses its UI entities (its actions keep running). Documented in the README upgrade section; needs an owner decision (ACL, settle time).
- **IN-02:** `with_native_marker` returns the unmarked payload near `MAX_DOCUMENT_BYTES`; the stored copy of such a native mirror reads as legacy after a restart (T-5-11 broken for oversize documents). Edge case, needs a design decision.
- **IN-03:** the takeover waits only for loaded entities, so a retained legacy replay at boot could race it; the duplicates are cleaned at the next pass (`test_a_late_replay_duplicate_is_cleaned_at_the_next_call`). Moderate confidence; covered by human item 5.

### Housekeeping for the orchestrator

- `.planning/ROADMAP.md` still shows Phase 5 as "9/9 | In Progress" with an empty completed date and the phase checkbox on line 21 unchecked. Update after the human items are settled.
- Tag `v0.2.0` and the GitHub release are not created (by design, per 05-09).

### Human Verification Required

See the `human_verification` list in the frontmatter: the 8 UAT items from 05-09-SUMMARY (upgrade path A4, integration page counting A1, mixed fleet and live follower cutover A5, straggler, late replay A4, commands, export, delete and removal) plus the owner decision on the open review items. None of them is a failure; each needs real instances (ha-one, ha-two, Mosquitto in `~/ha-test`) that this verification cannot start.

### Gaps Summary

No gaps. All five roadmap success criteria, all plan-level truths and prohibitions, and all seven requirement IDs are backed by existing, substantive, wired code and by passing tests (1414 passed). The status is `human_needed` only because real-instance confirmation (frontend counting, recorder history, live two-instance cutover, real core MQTT replay) cannot be performed from the repository.

---

_Verified: 2026-10-03_
_Verifier: Claude (gsd-verifier)_
