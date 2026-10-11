---
phase: 01-walking-skeleton-installable-switch
verified: 2026-10-11T13:44:55Z
status: passed
score: 8/8 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - .github/workflows/validate.yml
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-01-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-01-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-02-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-02-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-03-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-03-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-04-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-04-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-05-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-05-SUMMARY.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-06-PLAN.md
  - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-06-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-UAT.md
  - .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun2/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun2/verdict.txt
  - LICENSE
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/brand/icon.png
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/switch.py
  - custom_components/mqtt_actions/takeover.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - docs/adr/0001-native-entities-instead-of-mqtt-discovery.md
  - docs/troubleshooting.md
  - hacs.json
  - pyproject.toml
  - tests/__init__.py
  - tests/broker/__init__.py
  - tests/broker/conftest.py
  - tests/broker/test_retain_semantics.py
  - tests/conftest.py
  - tests/test_config_flow.py
  - tests/test_cutover.py
  - tests/test_device_ids.py
  - tests/test_discovery.py
  - tests/test_discovery_export.py
  - tests/test_export_guard_receiver.py
  - tests/test_hub_entities.py
  - tests/test_hub_removal.py
  - tests/test_manager.py
  - tests/test_multi_instance.py
  - tests/test_multi_instance_ops.py
  - tests/test_native_cleanup.py
  - tests/test_native_entities.py
  - tests/test_native_replay.py
  - tests/test_native_start.py
  - tests/test_repo_structure.py
  - tests/test_runner_modes.py
  - tests/test_state.py
  - tests/test_toolchain.py
  - tests/test_topics.py
  - tests/test_tracer.py
  - tests/test_translations.py
  - uv.lock
covered_digest: "v3:sha256:fae04ae0a34d3e6a5eb27f3e6986e38d7d30a0a9f17cb12474dcce9fe37a9735"
behavior_unverified: 0
overrides_applied: 2
overrides:
  - must_have: "The Switch appears in HA through MQTT Discovery (UUID unique_id, availability, device info)"
    reason: "superseded by Phase 5: native switch and select entities replace MQTT Discovery as the default (ADR 0001, docs/adr/0001-native-entities-instead-of-mqtt-discovery.md, D-03). The unique_id stays the device UUID (DeviceSwitch._attr_unique_id = device_id). Discovery remains as the compatibility path for an instance that has not cut over (is_native False) and as an optional, disabled-by-default export. Proof of the new default: tests/test_cutover.py::test_a_legacy_install_without_peers_cuts_over_after_the_settle_time, tests/test_native_entities.py::test_native_switch_is_registered_under_the_subentry, tests/test_native_entities.py::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select. Proof the compatibility path is intact: tests/test_native_entities.py::test_an_instance_without_the_native_flag_keeps_the_legacy_path, tests/test_discovery.py::test_discovery_creates_switch_entity, tests/test_tracer.py::test_switch_end_to_end."
    accepted_by: "D-03 (owner decision, Phase 7 context, 2026-10-04)"
    accepted_at: "2026-10-04T00:00:00Z"
  - must_have: "HACS client install on a real host. Add the repository as a custom repository in HACS (category Integration), download, restart, add MQTT Actions, accept defaults, try adding it a second time (removal of the integration and of the repository afterwards)"
    reason: "Abbreviated path host-with-integration (owner decision PROD-HOST, 2026-10-07) on production host 1, which already runs MQTT Actions. Run by the owner: repository card with installed version v1.0.0, Redownload/Update, restart, icon on the integration page, second Add integration > MQTT Actions aborts as already configured. NOT run: the first add of the integration (impossible on a host that already runs the single-instance integration), removal of the integration, removal of the repository. Build installed is release v1.0.0 (tag SHA d0f660cb2422c7688d22a674cf54f955a8c26c7f), not the bench SHA b8232252540a55969145ca0034d8fd86b4be3b7c; hacs.json, manifest and brand files are identical between the tag and HEAD."
    accepted_by: "Alexander Kentner"
    accepted_at: "2026-10-07T00:00:00Z"
gaps: []
deferred: []
human_verification:
  - test: "HACS client install on a real host. Add the repository as a custom repository in HACS (category Integration), download, restart, add MQTT Actions, accept defaults, try adding it a second time."
    expected: "HACS accepts and installs it, the flow shows base topic (default mqtt_actions) and instance name, a second add aborts with 'already set up', the icon is shown."
    why_human: "No automated test drives the HACS client or the frontend."
    resolution: "Override in the owner's name, ledger block 5 (P1-1) of .planning/phases/08-real-instance-verification/08-UAT.md, result: pass with override_by: Alexander Kentner, evidence .planning/phases/08-real-instance-verification/08-evidence/p1-1, recorded sha d0f660cb2422c7688d22a674cf54f955a8c26c7f (release tag v1.0.0, not the bench SHA), date 2026-10-07. Abbreviated path host-with-integration (PROD-HOST) on production host 1: repository card, Redownload/Update, restart, icon, second add aborts. NOT run: first add of the integration, removal of the integration, removal of the repository. Owner ran every step; Claude never touched the host."
    accepted_by: "Alexander Kentner"
    accepted_at: "2026-10-07T00:00:00Z"
  - test: "English and German strings in the real frontend (switch profile language, open the hub flow, the Add switch device dialog, the Repairs text)."
    expected: "All labels, descriptions, error banners and the Repairs issue are translated, no raw translation keys."
    why_human: "Key and placeholder parity is automated (240 flattened keys each, empty symmetric difference); real rendering and wording quality is not."
    resolution: "Resolved by ledger block 6 (P1-2) of 08-UAT.md, result: pass, evidence .planning/phases/08-real-instance-verification/08-evidence/p1-2 (screenshots 01..08 plus ../p3-1/01..06), sha b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 (first pin), date 2026-10-07. Owner-signed (\"approved P1-2 P3-1\"). The orchestrator session drove the browser (not the owner); the owner judged the screenshots and the live view. The Repairs text shown is the approval dialog on ha-a in German and English; the failing-action Repairs dialog is item 4. Scripted around it: hub removal and re-add of ha-b. Carried across the re-pin to b8232252: translation files, flows and frontend-facing code are byte-identical between the two builds (the diff touches manager.py and takeover.py only, registry logic)."
  - test: "Action editor and validation banners in the current build: add a switch device, enter an invalid action in YAML mode, then a service action with a literal device_id and submit twice."
    expected: "The action selector renders, an invalid action shows a form-level error and saves nothing, the device_id action warns on the first submit and saves on the identical second submit."
    why_human: "Flow level is automated; the frontend rendering of the ActionSelector and the base-error banner is not."
    resolution: "Resolved by ledger block 7 (P1-3) of 08-UAT.md, result: pass, evidence .planning/phases/08-real-instance-verification/08-evidence/p1-3, sha b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 (first pin), date 2026-10-06. Owner-signed (\"approved P1-3 P1-4 P3-2\"); the owner performed the click path in their own browser on ha-a. No screenshots (browser MCP unavailable); the pass rests on the owner statement. Claude's REST pre-check of the flow data path (invalid_actions on the invalid action, device_id_warning on the first submit) aborted the flows and saved nothing, so the save on the identical second submit in the real frontend is covered by the owner statement and by tests/test_config_flow.py::test_switch_flow_device_id_warns_then_saves_on_resubmit only. config_flow.py is byte-identical between the first pin and b8232252."
  - test: "Repairs dialog of a failing action: call a non-existent service in an action, trigger it, open Settings > Repairs."
    expected: "One Repairs issue shows device, trigger, time and error text, and it clears after the next successful run."
    why_human: "Issue creation, update, dismissal, truncation and clearing are automated; rendering in the real frontend is not."
    resolution: "Resolved by ledger block 8 (P1-4) of 08-UAT.md, result: pass, evidence .planning/phases/08-real-instance-verification/08-evidence/p1-4, sha b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 (first pin), date 2026-10-06. Owner-signed (\"approved P1-3 P1-4 P3-2\"). Fixture UAT P1-4 (action uat_missing.nothing) created the Repairs issue action_failed_{uuid} (trigger onChangeToOn, error \"Action uat_missing.nothing not found\"), listed through the API before the owner looked at it live in their own browser; no screenshots. The clearing after the next successful run was not part of the owner's check; it rests on tests/test_manager.py::test_issue_cleared_after_next_success. runner.py is byte-identical between the first pin and b8232252."
  - test: "Retained-versus-live chain on the current build with a real HA core MQTT client and a real retaining broker: toggle the entity in the UI, restart HA fully, reconnect the broker."
    expected: "One action run per real change, none for repeated identical values, none after a full HA restart or broker reconnect until a changed value is published, nothing removed on unload."
    why_human: "No automated test joins the HA core client with a real retaining broker."
    resolution: "Resolved by ledger block 9 (P1-5) of 08-UAT.md, result: pass, evidence .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun2 (result.txt, counts.txt, verdict.txt, logs; verdict.txt reads PASS), recorded sha b8232252540a55969145ca0034d8fd86b4be3b7c (the receiver-guard build, the one judged here), date 2026-10-11. Fully scripted, no owner judgment: counted marker lines per instance, startup flag off. Toggle (service call) +1 on ha-a and ha-b; podman restart of both: 0 and 0 while the retained state was replayed; reload of the core mqtt config entry on each instance: 0 and 0; positive control +1 and +1. Earlier runs on the first pin (p1-5) and on caf2fe5d (p1-5-rerun) stay as history. Limits carried: the toggle was the service call the frontend toggle makes, not a click; the 'broker reconnect' step was a reload of the core mqtt config entry (require_restart false), the Mosquitto container was not restarted (StartedAt unchanged), so a real broker disconnect was not exercised; 'nothing removed on unload' was not checked in this run (covered by tests/test_manager.py::test_unload_publishes_offline_and_never_clears_discovery)."
  - test: "Core version of the second real host (hassio-n2plus, called Backup): read it in Settings > About."
    expected: "Core 2026.9.0 or newer, or the floor is reassessed."
    why_human: "Not a code truth; the floor itself is tested (tests/test_toolchain.py::test_home_assistant_floor)."
    resolution: "Resolved by ledger block 10 (P1-6) of 08-UAT.md, result: pass, evidence .planning/phases/08-real-instance-verification/08-evidence/p1-6, recorded sha b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 (the first pin; the host's core version does not depend on the build), date 2026-10-07. Owner statement in chat: 2026.9.4, read in Settings > About of hassio-n2plus; 2026.9.4 is at or above the 2026.9.0 floor of hacs.json. Informational, no code consequence; Claude did not connect to the host."
---

# Phase 1: Walking Skeleton - Installable Switch Verification Report

**Phase Goal:** As a Home Assistant user, I want to create a Switch device whose MQTT state changes run my configured actions, so that I need no YAML automation. (Mode: mvp)
**Verified:** 2026-10-11T13:44:55Z
**Status:** passed
**Re-verification:** Yes. Regenerated after the UAT-04 gap closure (plans 08-16 to 08-18), against the receiver-guard build. The previous report (2026-10-08T19:09:50Z, `passed`, judged on the first pin) is replaced; history stays in Git.

**Build judged:** `.planning/phases/08-real-instance-verification/08-evidence/00-preflight/build.txt` records sha `b8232252540a55969145ca0034d8fd86b4be3b7c` (previous pins `caf2fe5d` and the first pin `b7f52b34`, re-pin reason: receiver-side guard of plan 08-17). The working tree at HEAD `f65a174` is byte-identical to that sha for `custom_components`, `tests`, `.github`, `pyproject.toml`, `hacs.json` and `uv.lock` (`git diff --stat b8232252 HEAD -- custom_components tests .github pyproject.toml hacs.json uv.lock` is empty), so every check below ran against the judged code. The automated-tier proof of `07-PROOF.md` (frozen sha `81db888c`) applies to the code that did not change; the guard delta is covered by the runs below. The P1-1 install ran release `v1.0.0` (see item 1).

The story format is valid (`As a ..., I want to ..., so that ... .`), so MVP-mode verification applies.

## What changed since the previous report

- Product delta against the first pin `b7f52b34` (read in full): `manager.py` (+82) and `takeover.py` (+34) add a duplicate guard (`_arm_duplicate_guard`, `_on_duplicate_registry_updated`, `_disable_duplicates`, `takeover.disable_duplicates`) that listens to entity-registry creations and disables an enabled core-MQTT duplicate of a native device. It is registry logic only: it publishes nothing, does not touch `StateTracker`, `runner`, `config_flow`, `switch.py` or the subscription path, and a failure inside it is caught and logged without keeping the manager from running. Documentation additions in `README.md` and `docs/troubleshooting.md`. New tests `tests/test_discovery_export.py` and `tests/test_export_guard_receiver.py`.
- Every truth was re-judged on this code (targeted runs below), not carried over. All 453 tests of the Phase 1 core tiers (including the real Mosquitto tier) and 135 multi-instance, hub, export and guard tests pass.
- The Phase 8 ledger changed: block 9 (P1-5, retained-versus-live) was re-run on the guard build (`p1-5-rerun2`, sha `b8232252`, PASS). The blocks of items 1 to 4 and 6 keep their first-pin evidence; the code those items rest on (`config_flow.py`, `runner.py`, translations, `hacs.json`, manifest, brand) is byte-identical to the guard build.
- The Phase 7 supersession of SC4a (Discovery as the default replaced by native entities, D-03) is kept as recorded, not re-litigated.
- Block 4 of the ledger (UAT-04, Discovery export on the core prefix) is Phase 5's check (05-UAT test 7); it now reads `pass` on the guard build (`uat-04-rerun2`, X1 to X10). It touches no Phase 1 truth; the guard it exercised does not change any Phase 1 behavior (see SC5 and the data-flow trace).

## User Flow Coverage (MVP mode)

| Story step | Expected | Evidence in codebase and on real instances | Status |
| --- | --- | --- | --- |
| Install and set up | Installs via HACS, hub added once, MQTT required | `hacs.json`, `manifest.json` (`dependencies: [mqtt]`, `single_config_entry: true`, `requirements: []`), `config_flow.py:93` aborts `mqtt_required`, `config_flow.py:114` uuid4 instance id; `test_hub_flow_*`; real host: HACS repository card, update, restart, icon, second add aborts (block 5, abbreviated path) | VERIFIED |
| Create a Switch device with actions | Name + onChangeToOn/Off via ActionSelector, invalid rejected, device_id warned | `config_flow.py:213` (`invalid_actions`), `:220` (`device_id_warning`), `:361-362` `selector.ActionSelector()`; `test_switch_flow_*`; real frontend click path by the owner (block 7) | VERIFIED |
| MQTT state change runs actions locally | Entity (native by default), UI toggle or external publish triggers actions on real edges only | `manager._on_message` -> `StateTracker.handle` -> `_run_trigger`; `switch.py::DeviceSwitch`; `test_switch_end_to_end`, `test_edge_*`, `test_the_echo_runs_the_actions_once`; real HA core plus real Mosquitto on the guard build: toggle +1 on both instances, restart and mqtt reload 0, positive control +1 (block 9, `p1-5-rerun2/verdict.txt` PASS) | VERIFIED |
| So that no YAML automation is needed | Whole path works without YAML, failures visible | Config Flow only (`cv.config_entry_only_config_schema`), `runner.py` log plus Repairs issue, `test_issue_*`; real Repairs issue `action_failed_{uuid}` listed and judged by the owner (block 8) | VERIFIED |

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria plus PLAN must-haves)

SC4 is split into its Discovery clause (superseded) and its behavior clause so that the supersession is exact and nothing else in SC4 rides on the override.

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| SC1 | HACS install, one-time Config Flow requiring MQTT with persistent instance ID, UI strings in EN and DE | VERIFIED | `manifest.json`: domain `mqtt_actions` = folder, `dependencies:["mqtt"]`, `single_config_entry:true`, `requirements:[]`; `hacs.json` floor 2026.9.0; `brand/icon.png`; hub flow aborts `mqtt_required` (`config_flow.py:93`), stores `str(uuid.uuid4())` as `CONF_INSTANCE_ID` (`:114`). Passing now: `test_hub_flow_creates_entry_with_instance_id`, `test_hub_flow_aborts_without_mqtt`, `test_hub_flow_single_instance`, `tests/test_translations.py` (en and de 240 flattened keys each, re-computed now: empty symmetric difference). Real instances: block 6 (EN and DE rendering, owner judged), block 5 (HACS card, icon, second add aborts; limits in item 1). |
| SC2 | Every push runs hassfest, HACS validation, Ruff and pytest in CI, and the pipeline passes | VERIFIED | `ci.yml` (Ruff, Unit, Broker with Mosquitto, Multi-instance tiers) and `validate.yml` (hassfest, HACS) trigger on `push` (only `tags-ignore: v*.*.*`, tags run once through `release.yml`), `pull_request`, dispatch, call; SHA-pinned actions, `permissions: {}` (the `.github` tree is unchanged since the first pin). Guards in `tests/test_repo_structure.py` pass now. Green runs cited from `07-PROOF.md`, not re-run: three consecutive CI dispatch runs 37205596675, 37205721595, 37205851615, Validate run 37205956233 (HACS `All (9) checks passed`), release run 37206309249; plus Validate scheduled runs on `main` through 2026-10-11 (`gh run list`: success). Limit: no CI run on the guard-build commits is in the evidence available to this verifier (the branch is not part of the listed runs); the same tiers pass locally (453 and 135 tests below) and the workflow files are unchanged. |
| SC3 | Create a Switch with name and action lists via the action selector; invalid actions rejected on input; actions targeting `device_id`s show a warning | VERIFIED | `config_flow.py:213` returns `base: invalid_actions` from `async_validate_actions`; `find_device_ids` plus a fingerprint gives `device_id_warning` on the first submit (`:220`) and saves on the identical resubmit. Passing now: `test_switch_flow_creates_subentry`, `test_switch_flow_schema_serializes_action_selector`, `test_switch_flow_rejects_invalid_actions`, `test_switch_flow_device_id_warns_then_saves_on_resubmit`, `test_switch_flow_entity_targets_do_not_warn`, `tests/test_device_ids.py`. Real frontend: block 7 (owner click path; no screenshots). |
| SC4a | The Switch appears in HA through MQTT Discovery (UUID `unique_id`, availability, device info) | PASSED (override): superseded by Phase 5 | Phase 5 replaced Discovery as the default with native entities (ADR 0001 D-03, `docs/adr/0001-native-entities-instead-of-mqtt-discovery.md`). The UUID `unique_id` survives (`switch.py:33` `_attr_unique_id = device_id`). New default: `tests/test_cutover.py::test_a_legacy_install_without_peers_cuts_over_after_the_settle_time`, `tests/test_native_entities.py::test_native_switch_is_registered_under_the_subentry`, `::test_native_device_publishes_no_legacy_discovery_and_shares_one_device_with_the_mode_select`. Compatibility path still true: `tests/test_native_entities.py::test_an_instance_without_the_native_flag_keeps_the_legacy_path`, `tests/test_discovery.py::test_discovery_creates_switch_entity`, `tests/test_tracer.py::test_switch_end_to_end` (all pass in the 453-test run). Override recorded in frontmatter (D-03). |
| SC4b | Toggling the entity in the UI or publishing to its retained state topic runs the matching actions locally on each real change; a failing action is visible in the log and as a Repairs issue | VERIFIED | Toggle publishes retained at QoS 1 and the broker echo is the single trigger source (`DeviceSwitch.async_turn_on/off` -> `manager.async_send_state`): `tests/test_discovery.py::test_discovery_toggle_publishes_retained_on_and_off`, `tests/test_native_entities.py::test_turn_on_publishes_the_exact_value_retained_at_qos_1`, `::test_the_echo_runs_the_actions_once`; edges `tests/test_manager.py::test_edge_*`, `::test_actions_run_serially_in_order`. Failure: `runner._async_run` logs and creates/updates one Repairs issue; `test_issue_created_when_action_fails`, `test_issue_updated_in_place_on_repeated_failure`, `test_issue_cleared_after_next_success`. Real instances on the guard build: toggle +1 on both (block 9, `p1-5-rerun2`), real Repairs issue created and judged (block 8, first pin, `runner.py` unchanged). |
| SC5 | After restart, reload or reconnect: clean start even without MQTT, retained state only sets the baseline (unless run-on-startup), only real changes trigger, the entity stays until the user explicitly deletes the device | VERIFIED | `__init__.py:37-39` raises `ConfigEntryNotReady` when `async_wait_ready()` is False; `state.decide`: retained is baseline only, run-on-startup is the opt-in; Store-backed baseline; unload publishes offline only, clears happen only in the delete paths. The new guard in `manager.py` is armed in `async_start` before `_async_publish_owned`, disarmed in stop, acts only on registry `create` events of core-MQTT rows or this integration's native twins, and only ever sets `disabled_by` on a core `mqtt` duplicate that has a native twin (`takeover.disable_duplicates`); it removes and enables nothing and never writes to the baseline. Behavioral tests (all pass in the 453-test run): `test_setup_retry_without_mqtt`, `test_retain_replay_sets_baseline_without_actions`, `test_retain_replay_after_reconnect_runs_nothing`, `test_startup_flag_runs_retained_state_once`, `test_baseline_persisted_across_reload`, `test_reload_keeps_single_subscription`, `test_unload_publishes_offline_and_never_clears_discovery`, `test_failed_start_releases_subscriptions_and_retries_cleanly`, `tests/test_native_start.py::test_a_second_start_runs_no_pass`, real Mosquitto `tests/broker/test_retain_semantics.py`; guard and export tests `tests/test_export_guard_receiver.py`, `tests/test_discovery_export.py` (135-test run with the multi-instance tiers). Real core client plus broker on the guard build (block 9, scripted, `p1-5-rerun2/verdict.txt` PASS): full restart of both instances gave 0 runs while the retained state replayed, a reload of the core mqtt entry gave 0, the positive control gave +1. A real broker restart was not part of that run. |
| P1 | Only `mqtt_gateway.py` imports the mqtt component, callbacks are `@callback`, the raw broker payload never reaches Script variables | VERIFIED | `tests/test_tracer.py::test_only_gateway_imports_mqtt_component` (AST) passes against the current package including the new `takeover.py` helper (it uses the literal `MQTT_DOMAIN = "mqtt"`, no import); the only `homeassistant.components import mqtt` in the package is `mqtt_gateway.py:6` (grep). |
| P2 | Zero runtime dependencies, toolchain pinned | VERIFIED | `manifest.json` `requirements: []`; `tests/test_toolchain.py` passes; CI uses `uv sync --locked`; `uv.lock` unchanged. |

**Score:** 8/8 truths verified (7 VERIFIED plus 1 PASSED (override)), 0 present-but-behavior-unverified. Every behavior-dependent truth has a named passing test, and the retain/baseline chain additionally has real-instance evidence on the judged build.

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `custom_components/mqtt_actions/{__init__,manager,runner,state,switch,entities,discovery,mqtt_gateway,config_flow,actions,topics,model,const,takeover}.py` | Working integration | VERIFIED | Substantive and wired (`__init__` -> `Manager`, `MqttGateway`, platforms; `manager` -> gateway, runner, tracker, takeover guard; `switch.py` reads the running manager; `config_flow` -> `actions`, `topics`). |
| `translations/en.json`, `de.json` | EN/DE strings | VERIFIED | 240 flattened keys each, empty symmetric difference (computed this run). |
| `manifest.json`, `hacs.json`, `brand/icon.png`, `LICENSE` | HACS metadata | VERIFIED | Present; `tests/test_repo_structure.py` passes; the real HACS client accepted the release (block 5). |
| `.github/workflows/ci.yml`, `validate.yml` (and `release.yml`) | CI | VERIFIED | SHA-pinned, empty permissions, four CI tiers; unchanged since the first pin. |
| `README.md`, `docs/troubleshooting.md`, `tests/` | Docs and coverage | VERIFIED | Targeted runs below; the guard documentation matches `manager.py`/`takeover.py` behavior. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| subentry create/update | `Manager.async_reconcile` | `entry.add_update_listener` | WIRED | `__init__.py`, registered before `async_start`. |
| `manager._on_message` | `StateTracker.handle` / `runner` | `_run_trigger` on `decision.act` | WIRED | tested by `test_edge_*`. |
| `DeviceSwitch.async_turn_on/off` | state topic | `manager.async_send_state` | WIRED | `switch.py`. |
| platforms | running manager | `async_forward_entry_setups` after `async_start` | WIRED | `__init__.py`. |
| remove path | clear before unsubscribe | `_async_remove_device` | WIRED | order tested. |
| connection status | republish | `async_subscribe_connection_status` | WIRED | `test_reconnect_republishes_availability_and_discovery`. |
| `config_flow` | `actions.async_validate_actions`, `find_device_ids` | direct | WIRED | |
| `Manager.async_start` | duplicate guard | `_arm_duplicate_guard()` before `_async_publish_owned`, `_disarm_duplicate_guard()` on stop | WIRED | `manager.py`; tests in `tests/test_export_guard_receiver.py`. |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
| --- | --- | --- | --- | --- |
| `runner._async_run` | Script sequence | subentry action list -> `async_validate_actions` -> `Script` | Yes | FLOWING |
| `DeviceSwitch.is_on` | `device.value` | accepted StateValue of the state topic | Yes | FLOWING |
| manager baseline | `last_acted` | Store load plus live and retained messages; the guard does not write it | Yes | FLOWING |
| Repairs issue | error text | exception string, capped | Yes (real issue observed, block 8) | FLOWING |

### Behavioral Spot-Checks

Run at HEAD `f65a174` (code identical to the recorded build `b8232252`). The full suite was not re-run; the two tiers below cover every Phase 1 truth plus the guard delta, and `07-PROOF.md` holds three local full runs and three CI runs on the code before the guard.

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 1 core tiers incl. real Mosquitto | `uv run --locked pytest -q -p no:cacheprovider tests/test_state.py tests/test_topics.py tests/test_config_flow.py tests/test_translations.py tests/test_repo_structure.py tests/test_device_ids.py tests/test_discovery.py tests/test_manager.py tests/test_toolchain.py tests/test_tracer.py tests/test_native_entities.py tests/test_native_replay.py tests/test_native_start.py tests/test_native_cleanup.py tests/test_cutover.py tests/broker` | 453 passed in 47.92s | PASS |
| Multi-instance, hub removal, roster, export and receiver guard | `uv run --locked pytest -q -p no:cacheprovider tests/test_multi_instance.py tests/test_hub_removal.py tests/test_multi_instance_ops.py tests/test_hub_entities.py tests/test_discovery_export.py tests/test_export_guard_receiver.py` | 135 passed in 13.55s | PASS |
| en/de key parity | flatten both files, symmetric difference | 240 / 240, empty | PASS |
| Debt markers | `grep -rnE "TBD\|FIXME\|XXX" custom_components tests .github` | no output | PASS |
| Real instances, guard build | `08-evidence/p1-5-rerun2/verdict.txt` | PASS (toggle +1, restart 0, mqtt entry reload 0, positive control +1, on both) | PASS |

### Probe Execution

Step 7c: SKIPPED (no `probe-*.sh` declared or present).

### Requirements Coverage

All 15 IDs of Phase 1 are claimed by a PLAN `requirements:` field (01-01 FND-02; 01-02 FND-01,03, DEV-01,02, STA-01,02, DSC-01; 01-03 FND-03,04, DEV-01,02,05; 01-04 STA-02,04,05, DEV-08; 01-05 FND-05, STA-01, DSC-01,02; 01-06 FND-01,02). No orphans.

| Requirement | Status | Evidence |
| --- | --- | --- |
| FND-01 | SATISFIED | `hacs.json`, manifest, icon; HACS 9/9 on the ledger runs; real HACS client on a production host (block 5, abbreviated path, override under the owner's name) |
| FND-02 | SATISFIED | SC2 evidence |
| FND-03 | SATISFIED | hub flow tests |
| FND-04 | SATISFIED | `tests/test_translations.py`; real frontend EN and DE (block 6) |
| FND-05 | SATISFIED | `test_setup_retry_without_mqtt`, `test_reconnect_republishes_availability_and_discovery` |
| DEV-01, DEV-02 | SATISFIED | `test_switch_flow_creates_subentry`, `test_switch_flow_schema_serializes_action_selector` |
| DEV-05 | SATISFIED | `test_switch_flow_rejects_invalid_actions`, `test_switch_flow_device_id_warns_then_saves_on_resubmit`; block 7 |
| DEV-08 | SATISFIED | `test_issue_*`; real Repairs dialog (block 8) |
| STA-01 | SATISFIED | `test_discovery_toggle_publishes_retained_on_and_off`, `test_turn_on_publishes_the_exact_value_retained_at_qos_1` |
| STA-02 | SATISFIED | `test_edge_*`, `test_the_echo_runs_the_actions_once`; block 9 on the guard build |
| STA-04 | SATISFIED | retain and startup tests, `tests/broker/test_retain_semantics.py`; block 9 on the guard build |
| STA-05 | SATISFIED | `test_baseline_persisted_across_reload`, `test_edge_duplicate_live_value_is_ignored` |
| DSC-01 | SATISFIED on the compatibility path, superseded as default by Phase 5 (override above) | discovery tests, native tests |
| DSC-02 | SATISFIED | `test_unload_publishes_offline_and_never_clears_discovery`, `test_delete_clears_discovery_then_unsubscribes_then_config_tombstone_then_state`, `tests/test_native_cleanup.py::test_deleting_a_native_device_clears_everything_and_removes_its_entities` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| code, tests, workflows | - | TBD/FIXME/XXX | none | grep clean |
| `manager.py` `_disable_duplicates` | - | broad `except Exception` with `noqa: BLE001` | info | Intentional: the guard must never keep the manager from running; logs a type name only, no broker content. |

The open review findings of the earlier reports (WR-03, WR-05, WR-06, WR-07, IN-01..06) were not re-litigated; none falsifies a Phase 1 success criterion. WR-03 (live-republished legacy Discovery creates `_2` entities until the next start) is recorded by the owner as an accepted known limit (WR03-LIVE-REPLAY, `08-UAT.md`); the receiver-side guard of plan 08-17 additionally disables such a replayed duplicate when core creates it.

### Human Verification Required

None open. The six items of the earlier reports are resolved by the Phase 8 ledger (`.planning/phases/08-real-instance-verification/08-UAT.md`, blocks 5 to 10, all `result: pass`), each carrying a `resolution:` in the frontmatter. What each block did and did not cover, so that no pass is read wider than it was:

| # | Item | Ledger block | Recorded sha, date | Resolution | How it was judged and what it does not cover |
| --- | --- | --- | --- | --- | --- |
| 1 | HACS client install | 5 (P1-1) | `d0f660cb2422c7688d22a674cf54f955a8c26c7f` (release v1.0.0), 2026-10-07 | Override, `accepted_by: Alexander Kentner` (block carries `override_by`) | Owner only, on production host 1 that already runs the integration (PROD-HOST): repository card, update, restart, icon, second add aborts. Not run: first add, removal of the integration, removal of the repository. Installed build is v1.0.0, not the bench SHA; `hacs.json`, manifest and brand files are identical between the tag and HEAD, the later code differences (Phase 6, the guard) are not covered by this item. |
| 2 | EN and DE strings in the real frontend | 6 (P1-2) | `b7f52b34...` (first pin), 2026-10-07 | Resolved | Orchestrator drove the browser, owner judged the screenshots and live view. The Repairs text covered here is the approval dialog; the failing-action dialog is item 4. Translations and flows are byte-identical to the guard build. |
| 3 | Action editor and validation banners | 7 (P1-3) | `b7f52b34...` (first pin), 2026-10-06 | Resolved | Owner statement after the click path in their own browser, no screenshots. Claude's REST pre-check saved nothing, so the save on the identical resubmit in the frontend rests on the owner statement and the automated test. `config_flow.py` is byte-identical to the guard build. |
| 4 | Repairs dialog of a failing action | 8 (P1-4) | `b7f52b34...` (first pin), 2026-10-06 | Resolved | Owner looked live in their own browser after the issue was listed through the API; no screenshots. Clearing after the next success was not part of the owner check (automated test only). `runner.py` is byte-identical to the guard build. |
| 5 | Retained-versus-live chain, real core plus real broker | 9 (P1-5) | `b8232252...` (guard build), 2026-10-11 | Resolved (re-run on the judged build) | Scripted, no owner judgment (`p1-5-rerun2`, verdict PASS). Toggle was the service call, not a click; the reconnect step reloaded the core mqtt entry and did not restart Mosquitto; unload behavior not checked in that run (automated test). |
| 6 | Core version of hassio-n2plus | 10 (P1-6) | `b7f52b34...` (first pin), 2026-10-07 | Resolved | Owner statement 2026.9.4 read in Settings > About; informational, independent of the build. |

### Gaps Summary

No gaps. Every roadmap success criterion is backed by the code at the guard build `b8232252` and named passing tests (453 plus 135 passed), with one intended supersession (SC4a, recorded as an override under D-03). The receiver-guard delta (`manager.py`, `takeover.py`) is registry-only and touches no Phase 1 truth; the one behavior-dependent real-instance item (P1-5) was re-run on that build and passes. The six real-client checks are recorded as `pass` in the Phase 8 ledger; five are plain resolutions and one (HACS install, abbreviated path) is an override in the owner's own name with its limitations listed above. One limit is stated rather than hidden: the evidence available to this verifier holds no CI run on the guard-build commits (SC2 rests on unchanged workflows, the earlier green runs and the local runs above).

---

_Verified: 2026-10-11T13:44:55Z_
_Verifier: Claude (gsd-verifier)_
