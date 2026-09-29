---
phase: 01-walking-skeleton-installable-switch
verified: 2026-09-29T12:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .github/workflows/validate.yml
  - .planning/phases/01-walking-skeleton-installable-switch/01-01-PLAN.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-01-SUMMARY.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-02-PLAN.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-02-SUMMARY.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-03-PLAN.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-03-SUMMARY.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-04-PLAN.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-04-SUMMARY.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-05-PLAN.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-05-SUMMARY.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-06-PLAN.md
  - .planning/phases/01-walking-skeleton-installable-switch/01-06-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - hacs.json
  - pyproject.toml
  - tests/__init__.py
  - tests/broker/__init__.py
  - tests/broker/conftest.py
  - tests/broker/test_retain_semantics.py
  - tests/conftest.py
  - tests/test_config_flow.py
  - tests/test_device_ids.py
  - tests/test_discovery.py
  - tests/test_manager.py
  - tests/test_repo_structure.py
  - tests/test_state.py
  - tests/test_toolchain.py
  - tests/test_topics.py
  - tests/test_tracer.py
  - tests/test_translations.py
covered_digest: "v2:sha256:a5c98b1a05a6e102a4366312fc90f316988b5f41f0344bae1f013deeaafda379"
behavior_unverified: 0
overrides_applied: 0
gaps: []
deferred: []
human_verification:
  - test: "HACS install and Config Flow on a real host. Add https://github.com/akentner/homeassistant-mqtt-actions-integration as a custom repository in HACS (category Integration), download, restart, add MQTT Actions, accept defaults; try adding it a second time."
    expected: "HACS accepts and installs it, the flow shows the base topic (default mqtt_actions) and instance name, a second add aborts with 'already set up', the icon is shown."
    why_human: "HACS client behavior and real frontend cannot be exercised by pytest; CI HACS validation (9/9 checks) only proves repository shape."
  - test: "English and German UI strings in the real frontend (switch profile language, open hub flow, Add switch device dialog, Repairs issue text)."
    expected: "All dialog labels, descriptions, error banners and the Repairs issue are translated; no raw translation keys are shown."
    why_human: "Parity of keys and template variables is tested (en/de, 40 keys each, no diff), but real rendering and wording quality is not."
  - test: "Action editor and validation banners in the FINAL build (only the tracer build was seen during the D-13 gate). Add a switch device; enter an invalid action in YAML mode; enter a service action with a literal device_id and submit twice."
    expected: "Action selector renders; invalid action gives a form-level error and saves nothing; device_id action shows the warning banner on first submit and saves on the identical second submit."
    why_human: "Frontend rendering of the base-error banner and the ActionSelector in a subentry dialog is only asserted at flow level."
  - test: "Real chain for retained-versus-live: deploy the final build, toggle the entity in the UI and publish on/off/ON to mqtt_actions/v1/devices/{uuid}/state with the real broker; then restart HA, reload the integration, and restart the broker/reconnect."
    expected: "One action run per real change, none for repeated identical values, none after restart/reload/reconnect until a changed value is published; discovery is not removed on unload."
    why_human: "Unit tests use the HA mqtt mock (retain flag injected) and a Mosquitto test that talks paho directly; the HA core client plus a real retaining broker is not exercised end to end."
  - test: "Failing action visibility: call a non-existent service in an action, trigger it, check log and Settings > Repairs; then fix and trigger again."
    expected: "Exactly one Repairs issue with device, trigger, time, error; log entry with traceback; issue disappears after the next success."
    why_human: "Repairs UI rendering and placeholders in the real frontend."
  - test: "Delete a device and remove the hub on a real host and broker."
    expected: "Entity disappears and no ghost device remains under the MQTT integration; after hub removal nothing MQTT Actions related remains on the broker (mosquitto_sub -v -t '#' -R style check)."
    why_human: "Broker-side delete semantics are only simulated by HA test mocks."
  - test: "Lifecycle fixes WR-01/WR-02/WR-04 (6361ce7, 955c817, 2a65b45) on a host: reload the integration while adding/deleting a subentry, start HA while the broker is down then bring it up."
    expected: "Exactly one subscription per device (one run per message), setup retries and succeeds when the broker returns, no double runs."
    why_human: "These commits are local only, not pushed and not proven by GitHub CI; the review disposition itself marks them 'requires human verification'."
  - test: "Push the local commits and confirm CI and Validate are green for the new head (currently only 0f6ae60 is proven on GitHub)."
    expected: "Both workflows succeed on the pushed head."
    why_human: "Requires a push, which this verification was told not to do. Locally: 188 passed, ruff check clean, ruff format check clean."
  - test: "Core versions of lxc-haos-104 and hassio-n2plus (D-13 step, UAT step 8)."
    expected: "Both hosts run Core >= 2026.9.0, or the floor is reassessed."
    why_human: "Never verified (probes denied in 01-02); does not affect the tested floor of 2026.9.0."
---

# Phase 1: Walking Skeleton - Installable Switch Verification Report

**Phase Goal:** As a Home Assistant user, I want to create a Switch device whose MQTT state changes run my configured actions, so that I need no YAML automation. (Mode: mvp)
**Verified:** 2026-09-29
**Status:** human_needed
**Re-verification:** No, initial verification

Verified against local HEAD `950d30c` (8 commits ahead of pushed `0f6ae60`). The story format is valid (`As a ..., I want to ..., so that ... .`), so MVP-mode verification applies.

## User Flow Coverage (MVP mode)

| Story step | Expected | Evidence in codebase | Status |
| --- | --- | --- | --- |
| Install and set up | Integration installs via HACS, hub added once, MQTT required | `hacs.json`, `manifest.json` (`dependencies: [mqtt]`, `single_config_entry`), `config_flow.py:50-92`, tests `test_hub_flow_*`; HACS + hassfest green on 0f6ae60 | VERIFIED (HACS client itself: human) |
| Create a Switch device with actions | Name + onChangeToOn/Off via ActionSelector, invalid rejected, device_id warned | `config_flow.py` `SwitchSubentryFlow` (raw selector output stored, base errors, warn-then-confirm fingerprint), `actions.py` | VERIFIED (frontend rendering: human) |
| MQTT state change runs actions locally | Discovery entity, UI toggle or external publish triggers actions on real edges only | `discovery.py`, `state.py::decide`, `manager.py::_on_message`, `runner.py`; `test_switch_end_to_end`, `test_edge_*` | VERIFIED |
| So that no YAML automation is needed | Whole path works without YAML; failures visible | Config Flow only, `runner.py` log + Repairs issue, `test_issue_*` | VERIFIED |

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria plus PLAN must-haves)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| SC1 | HACS install, one-time Config Flow requiring MQTT with persistent instance ID, UI strings in EN and DE | VERIFIED | `manifest.json` has domain `mqtt_actions` = folder name, `dependencies:["mqtt"]`, `single_config_entry:true`; `hacs.json` floor 2026.9.0; icon is a 256x256 RGBA PNG; hub flow aborts `mqtt_required`, generates `uuid4` `instance_id` (`config_flow.py:74-80`), tests for abort, single instance, invalid base topics; `en.json`/`de.json` have 40 flattened keys each, symmetric difference empty, `test_translations.py` passes. Real HACS install/rendering: human item 1, 2. |
| SC2 | Every push runs hassfest, HACS validation, Ruff, pytest; pipeline passes | VERIFIED (pushed head only) | `ci.yml` + `validate.yml` trigger on `push` with no branch filter, SHA-pinned actions, `permissions: {}`. `gh run list`: CI (36545688728) and Validate (36545688756) `success` on 0f6ae60. Local head: `uv run pytest -q` 188 passed (mosquitto installed, no skips), `ruff check` clean, `ruff format --check` 26 files formatted. The 8 local commits are not proven on GitHub (human item 8). |
| SC3 | Create Switch with name and action lists via selector; invalid rejected on input; device_id warning | VERIFIED | `SwitchSubentryFlow._async_check_actions`: `async_validate_actions` (cv.SCRIPT_SCHEMA + deep validation) returns `base: invalid_actions`; `find_device_ids` + fingerprint gives `device_id_warning` first submit, saves on identical resubmit. Tests: `test_switch_flow_rejects_invalid_actions`, `..._device_id_warns_then_saves_on_resubmit`, `..._entity_targets_do_not_warn`, reconfigure variants, `test_device_ids.py`. |
| SC4 | Discovery (UUID unique_id, availability, device info); UI toggle or state-topic publish runs actions on each real change; failing action visible in log and Repairs | VERIFIED | `discovery.py::build_switch_discovery` (device-based payload, `unique_id=device_id`, availability list, `command_topic == state_topic`, retain, qos 1); real core-MQTT tests `test_discovery_creates_switch_entity`, `test_discovery_toggle_publishes_retained_on_and_off`, `test_discovery_availability_toggles_entity`. Trigger: `manager._on_message` -> `StateTracker.handle` -> `runner.enqueue` (background task, FIFO lock). Failure: `runner._async_run` calls `LOGGER.exception` + `ir.async_create_issue`; tests `test_issue_created_when_action_fails`, `..._updated_in_place...`, `..._issue_for_invalid_stored_actions_at_setup`. See warning W-03 on Repairs clearing semantics. |
| SC5 | Restart/reload/reconnect safe: clean start without MQTT, retained only sets baseline (unless run-on-startup), only real changes trigger, entity stays until explicit delete | VERIFIED | `__init__.py` raises `ConfigEntryNotReady` if `async_wait_for_mqtt_client` is False (`test_setup_retry_without_mqtt`); `state.decide` retained => baseline only, `startup_pending and run_on_startup` opt-in; Store-backed baseline (`_async_load_store`, `_schedule_save`, final save in `async_stop`); unload publishes offline only, never clears discovery; clears happen only in `_async_remove_device` / hub removal. Behavioral tests (each passing in the 188-test run): `test_retain_replay_sets_baseline_without_actions`, `test_retain_replay_after_reconnect_runs_nothing`, `test_startup_flag_runs_retained_state_once`, `test_startup_flag_not_reapplied_on_replay`, `test_new_device_ignores_startup_flag`, `test_baseline_persisted_across_reload`, `test_reload_keeps_single_subscription`, `test_reconnect_republishes_availability_and_discovery`, `test_unload_publishes_offline_and_never_clears_discovery`, `test_unload_then_setup_republishes_without_clearing`, `test_delete_device_clears_discovery_then_state`, `test_delete_device_own_subscription_never_sees_state_clear`, `test_failed_start_releases_subscriptions_and_retries_cleanly`; broker tests `test_replay_on_subscribe_has_retain_true`, `test_live_forward_has_retain_false`. Real broker end-to-end: human item 4, 6. |
| P1 | Only `mqtt_gateway.py` imports the mqtt component; callbacks are `@callback`; raw broker payload never reaches Script variables | VERIFIED | `test_only_gateway_imports_mqtt_component` (AST); `_forward` functions decorated with `@callback`; `_on_message` passes only `{"device_id", "state": decision.value}` (normalised ON/OFF). |
| P2 | Zero runtime dependencies; toolchain pinned | VERIFIED | `manifest.json` `requirements: []`; `test_toolchain.py` passes. |

**Score:** 5/5 roadmap truths verified; 0 present-but-behavior-unverified. Every behavior-dependent truth (retain/baseline, cleanup on unload, delete ordering, single subscription after reload, failed-start teardown) has a named passing test.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `custom_components/mqtt_actions/{__init__,manager,runner,state,discovery,mqtt_gateway,config_flow,actions,topics,const}.py` | Working integration (1194 lines) | VERIFIED | Substantive, no TBD/FIXME/XXX/TODO/HACK markers (grep clean), all wired (manager -> gateway/discovery/runner/state; `__init__` -> manager; config_flow -> actions/topics). |
| `translations/en.json`, `de.json` | EN/DE strings | VERIFIED | Key parity, includes `issues.*` and subentry strings. |
| `manifest.json`, `hacs.json`, `brand/icon.png`, `LICENSE` | HACS metadata | VERIFIED | Present, valid; icon 256x256 PNG. |
| `.github/workflows/ci.yml`, `validate.yml`, `dependabot.yml` | CI | VERIFIED | SHA pinned, empty permissions. |
| `README.md` | Install, contract, limitations, trust model | VERIFIED | Sections present and match code behavior. |
| `tests/` (188 tests incl. `tests/broker`) | TDD coverage | VERIFIED | 188 passed. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| subentry create/update | `Manager.async_reconcile` | `entry.add_update_listener(_async_entry_updated)` | WIRED | Registered before `async_start` (post WR-02 fix). |
| `manager._on_message` | `StateTracker.handle` / `decide` | direct call | WIRED | |
| `manager._on_message` | `runner.enqueue` | on `decision.act` | WIRED | |
| `discovery.build_switch_discovery` | `topics.state_topic` | state + command topic | WIRED | |
| remove path | `async_clear_device` before unsubscribe | `_async_remove_device` | WIRED | Order tested. |
| connection status | republish | `async_subscribe_connection_status` -> `_async_republish` | WIRED | |
| `__init__.async_remove_entry` | Store + clears | `async_remove_all_devices` | WIRED | |
| `config_flow` | `topics.validate_base_topic`, `actions.find_device_ids` | direct | WIRED | |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
| --- | --- | --- | --- | --- |
| `runner._async_run` | Script sequence | raw subentry action list -> `async_validate_actions` -> `Script` | Yes | FLOWING |
| `manager` baseline | `last_acted` | Store load + live/retained messages -> `_data_to_save` | Yes | FLOWING |
| Repairs issue | error text | exception string, capped at 500 chars | Yes | FLOWING |
| discovery payload | device id, name, topics | subentry data + manifest version | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Full suite (run once) | `uv run pytest -q` | 188 passed in 9.3s (also with `-rs`: no skips) | PASS |
| Lint | `uv run ruff check .` | All checks passed | PASS |
| Format | `uv run ruff format --check .` | 26 files already formatted | PASS |
| Retain-flag semantics vs real Mosquitto | `pytest tests/broker` (part of the suite) | pass | PASS |
| CI on pushed head | `gh run list --branch gsd/phase-01-...` | CI + Validate success on 0f6ae60 | PASS |
| en/de key parity | flatten + symmetric diff | empty set, 40 keys | PASS |

### Probe Execution

Step 7c: SKIPPED (no `probe-*.sh` declared or present).

### Requirements Coverage

All 15 IDs in the ROADMAP for Phase 1 are claimed by at least one PLAN `requirements:` field (union: 01-01 FND-02; 01-02 FND-01,03, DEV-01,02, STA-01,02, DSC-01; 01-03 FND-03,04, DEV-01,02,05; 01-04 STA-02,04,05, DEV-08; 01-05 FND-05, STA-01, DSC-01,02; 01-06 FND-01,02). No orphaned requirements (REQUIREMENTS.md maps no additional Phase 1 IDs).

| Requirement | Source plan(s) | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| FND-01 | 01-02, 01-06 | HACS install | SATISFIED (real install: human) | hacs.json/manifest/icon; HACS validate green on 0f6ae60 |
| FND-02 | 01-01, 01-06 | CI on every push | SATISFIED (pushed head) | workflows + green runs; local head unpushed |
| FND-03 | 01-02, 01-03 | Config Flow, one hub, MQTT, instance ID | SATISFIED | hub flow tests |
| FND-04 | 01-03 | EN + DE strings | SATISFIED (rendering: human) | parity test |
| FND-05 | 01-05 | Wait for MQTT, resume after reconnect | SATISFIED | `test_setup_retry_without_mqtt`, reconnect republish tests |
| DEV-01 | 01-02, 01-03 | Create Switch with name | SATISFIED | subentry flow tests |
| DEV-02 | 01-02, 01-03 | onChangeToOn/Off with action selector | SATISFIED | `ActionSelector` in schema, `test_switch_flow_schema_serializes_action_selector` |
| DEV-05 | 01-03 | Validation + device_id warning | SATISFIED | flow tests |
| DEV-08 | 01-04 | Failures in log and Repairs | SATISFIED (see W-03) | runner + `test_issue_*` |
| STA-01 | 01-02, 01-05 | UI toggle publishes to shared retained topic | SATISFIED | `test_discovery_toggle_publishes_retained_on_and_off` |
| STA-02 | 01-02, 01-04 | External message triggers same actions | SATISFIED | `test_edge_*` |
| STA-04 | 01-04 | Retained only sets baseline; run-on-startup flag | SATISFIED | retain/startup tests + broker tests |
| STA-05 | 01-04 | Persisted last state, only real edges | SATISFIED | `test_baseline_persisted_across_reload`, `test_edge_duplicate_live_value_is_ignored` |
| DSC-01 | 01-02, 01-05 | Owner publishes discovery (UUID, availability, device info) | SATISFIED | discovery tests |
| DSC-02 | 01-05 | Discovery removed only on explicit delete | SATISFIED | unload/delete tests |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| (all phase files) | - | TBD/FIXME/XXX/TODO/HACK | none | grep clean |
| `manager.py` | 122-128 | Hub removal drops the Store even if the broker clear failed (WR-05, open) | Warning | Ghost entities possible after failed hub removal; not a success criterion, not in README limitations |
| `runner.py` | 77-78 | One Repairs issue per device deleted by any success (WR-03, open) | Warning | See below |
| `runner.py`/`manager.py` | - | Unbounded queued runs and unthrottled unknown-payload warning (WR-06, open) | Warning | Amplifies the documented trust boundary |
| `discovery.py` | 48-49 | `value_template` lacks `trim` (WR-07, open) | Warning | Whitespace payload: manager acts, entity state goes stale |
| misc | - | IN-01..IN-06 open | Info | Prefix change orphaning, error text may echo action data, blanket `expected_lingering_timers`, bare KeyError catch, silent drop of queued runs on reconfigure, `.gitignore` lacks `.gsd/`, `.planning/state.json`, `.planning/milestone.lock` |

### Open Review Findings vs Success Criteria

| Finding | Breaks a success criterion? | Reasoning |
| --- | --- | --- |
| WR-03 | No (weakens SC4 edge case) | Every failure is always logged and always raises/updates the Repairs issue. The clear-on-next-success behaviour is exactly locked decision D-09 ("cleared automatically after the next successful run"), and the tests pin it. The weakness: ON permanently broken, OFF succeeds, issue vanishes although ON is still broken; a setup issue for invalid stored actions can be cleared the same way. Invalid actions cannot normally be stored because the flow validates them. Recommend fixing in a follow-up (per-trigger issue ids). |
| WR-05 | No | Destructive hub removal is a documented Phase 1 limitation (D-15, Phase 3 redesign); the failure-to-clear-on-broker-down case is not documented. |
| WR-06 | No | Trust boundary is documented in README; amplification is not. |
| WR-07 | No | Only affects whitespace-padded payloads, outside the documented `ON`/`OFF` contract. |
| IN-01..06 | No | Hygiene or edge cases. IN-06 is a publication risk: an accidental `git add -A` would commit `.gsd/` and `.planning/state.json` to a public repo. |

### Human Verification Required

See the `human_verification` list in the frontmatter (10 items): HACS install and Config Flow, EN/DE rendering, final-build action editor and banners, real broker retained/live chain across restart/reload/reconnect, Repairs rendering, delete/hub-removal on a real broker, the three unpushed lifecycle fixes on a host, CI for the unpushed head, and Core versions of the two other hosts. The full manual UAT list is in `01-06-SUMMARY.md` ("Manual UAT").

### Bookkeeping Warnings (non-blocking)

- `.planning/REQUIREMENTS.md` marks only FND-01 and FND-02 complete; FND-03, FND-04, FND-05, DEV-01, DEV-02, DEV-05, DEV-08, STA-01, STA-02, STA-04, STA-05, DSC-01, DSC-02 are still `[ ]` / `Pending`. The ROADMAP Phase 1 checkbox is still `[ ]`. Update after human verification passes.
- `01-04-SUMMARY.md` has `requirements-completed: []` although the plan owns STA-02, STA-04, STA-05, DEV-08 (the union of the other summaries misses STA-04, STA-05, DEV-08). Code and tests do cover them; this is metadata only.
- README says broker tests "are skipped when mosquitto is not installed"; locally mosquitto is installed (`/usr/bin/mosquitto`) and CI installs it, so the retain-semantics proof runs in both.

### Gaps Summary

No blocking gaps. Every roadmap success criterion is backed by code and by passing behavioral tests (188 passed locally, Ruff clean). The status is `human_needed` because the goal is an installed, host-visible behavior and several parts (HACS client, real frontend rendering of the final build, real-broker retained/reconnect/delete semantics, and the three locally-only lifecycle fixes) are, by the phase's own plan, only confirmable on a real host. Open review findings WR-03/05/06/07 are recommended follow-ups and none of them falsifies a success criterion.

---

_Verified: 2026-09-29_
_Verifier: Claude (gsd-verifier)_
