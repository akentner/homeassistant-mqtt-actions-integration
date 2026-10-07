---
status: testing
phase: 08-real-instance-verification
source:
  - .planning/phases/08-real-instance-verification/08-CONTEXT.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md
  - .planning/milestones/v1.0-phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-UAT.md
started: 2026-10-04T18:55:00Z
updated: 2026-10-04T20:15:00Z
---

## Current Test

number: 2
name: UAT-02 late legacy Discovery replay, two starts (MIG-05)
expected: |
  No `mqtt` platform entry and no `_2` entity exists on ha-a and ha-b after retained legacy Discovery was published while the
  instance was stopped and the instance was started twice; entity ids, registry ids and device ids are unchanged.
awaiting: plan 08-02 (scripted run on the pinned bench)

## Build under test

The containers bind-mount `custom_components/mqtt_actions` of the main checkout read-only. The pinned identity is recorded in
`08-evidence/00-preflight/build.txt`; a later `check-preflight.sh --quick` re-asserts it before every wave (D-03).

- sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
- branch: gsd/phase-08-real-instance-verification
- commit time: 2026-10-04T17:21:42+02:00
- image: ghcr.io/home-assistant/home-assistant:2026.9 (HA 2026.9.4)
- ha-a (Test HA One, port 8123): instance id 3851f34f-fa67-4f3c-bba0-122465013c3d
- ha-b (Test HA Two, port 8124): instance id a09499e4-5674-48d5-b3d6-4860d5226fcb

Phase 1 item P1-1 (HACS client install) records the release tag it really installed instead, because HACS downloads the newest
release and not this checkout (D-03).

## Results (D-05)

| Check | Requirement or source | Result | Date | Build SHA | Evidence |
|-------|-----------------------|--------|------|-----------|----------|
| UAT-01 | UAT-01, ROADMAP criterion 1, 05-UAT test 4 | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/uat-01 |
| UAT-02 | UAT-02, ROADMAP criterion 2, 05-UAT test 5 | pass | 2026-10-04 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/uat-02 |
| UAT-03 | UAT-03, ROADMAP criterion 3, 05-UAT test 6 | pass | 2026-10-04 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/uat-03 |
| UAT-04 | UAT-04, ROADMAP criterion 4, 05-UAT test 7 | issue | 2026-10-04 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/uat-04 |
| P1-1 | Phase 1 item 1 (07-PROOF) | pending | - | - | - |
| P1-2 | Phase 1 item 2 (07-PROOF) | pass | 2026-10-07 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-2 |
| P1-3 | Phase 1 item 3 (07-PROOF) | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-3 |
| P1-4 | Phase 1 item 4 (07-PROOF) | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-4 |
| P1-5 | Phase 1 item 5 (07-PROOF) | pass | 2026-10-04 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-5 |
| P1-6 | Phase 1 item 6 (07-PROOF) | pending | - | - | - |
| P2-1 | Phase 2 item 1 (07-PROOF) | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p2-1 |
| P2-2 | Phase 2 item 2 (07-PROOF) | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p2-2 |
| P3-1 | Phase 3 item 1 (07-PROOF) | pass | 2026-10-07 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p3-1 |
| P3-2 | Phase 3 item 2 (07-PROOF) | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p3-2 |

Allowed result tokens: pending, pass, issue, blocked. `skipped` is not allowed because D-07 waives nothing. An owner override of a
failed item stays `result: issue` plus an `override_by:` line with the owner's own name. A recorded block carries `sha:` (40 hex),
`date:` (ISO date), `evidence:` (a folder under 08-evidence) and `note:` after `result:`; an issue also carries `reported:` and
`severity:`. The recorder gate is `~/ha-test/bin/check-recorded.sh {check id}`.

## Tests

### 1. UAT-01: straggler v0.1.0 instance
expected: A v0.1.0 instance (ha-c) next to the native instances keeps running its actions for the migrated devices, shows no `mqtt`-platform entity and no switch or button entity of `mqtt_actions` for them and raises no error; the v0.1.0 companion mode selects (`select.{name}_mode`, unique id `{device id}_mode`) are recorded under Observations and do not fail the check (owner decision UAT01-WORDING, observation).
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-06
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-01
note: Policy `observation` (UAT01-WORDING, coded in `check-uat01.sh` before the run). ha-c ran the v0.1.0 component (26 `.py` files equal to the tag, manifest 0.1.0) with its own MQTT user and ACL block (availability read back online, heartbeat heard) next to the native ha-a and ha-b; seven migrated devices on the broker, the marker approved on ha-c, the others left unapproved. Outcome 1 (runs its actions): two marker state changes on ha-a (`switch.turn_on`, then `switch.turn_off`, the bench state was off; 60 s after each) gave a delta of exactly +1 on ha-a, ha-b and ha-c each, 0 for the other text on ha-c. Outcome 2 (no entities): ha-c's registry holds no `mqtt` row, no row with a unique id equal to a device id or `{id}_test_*`, no switch or button of `mqtt_actions` for a migrated device and no switch state; the 7 companion mode selects (`select.{name}_mode`) exist and are recorded below. Outcome 3 (no error): no ERROR or CRITICAL naming `custom_components.mqtt_actions` or `homeassistant.components.mqtt` in the container output of ha-c (all lifetimes) or on ha-a and ha-b since ha-c arrived; Repairs on ha-c hold one approval request (Lampe Test) plus two core bench artifacts; no retained topic under `homeassistant/`, the only new retained topics are ha-c's availability and the marker's config and state. ha-c was stopped afterwards; its retained availability still read `online` and was cleared by hand (see Observations).

### 2. UAT-02: late legacy Discovery replay, two starts (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-04
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-02
note: Two startup rounds with retained legacy Discovery published while ha-a and ha-b were stopped; after each graceful stop both registries held no `mqtt` row, no `_2` id, no legacy `mqtt` device and the 30 `mqtt_actions` rows (entity id, registry id, unique id, device id) identical to the baseline (E1 to E4). The replay really created the twins (six `_2` tombstones per instance in `deleted_entities`) and they were removed. Live variant (observation only): published while running, six `_2` entities appeared on both instances within 20 s, stayed through a graceful stop, and were gone after the next start.

### 3. UAT-03: command across two real instances
expected: A command issued on one of two real instances runs the actions exactly once on every approved instance, and an unknown payload is ignored and leaves the state unchanged.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-04
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-03
note: Marker device "UAT Marker" (owner ha-a, inert system_log.write actions) counted per instance in one process lifetime, each step followed by a wait. A (unapproved control, command on ha-a): ha-a +1, ha-b 0. Approval of the mirror on ha-b through the Repairs fix flow API. B (command on ha-a): +1 on ha-a and +1 on ha-b after 60 s. C (command on the ha-b mirror): +1 on ha-a and +1 on ha-b after 60 s. D (`banana`, QoS 1, not retained, published by uat_bridge): marker deltas 0 on both, `Ignoring unknown payload` +1 on each instance, entity state on both unchanged (on), retained broker value read back unchanged (ON). A subscriber's capture shows retain=0 for every live message, so the not-retained proof is the unchanged retained read-back.

### 4. UAT-04: Discovery export and core prefix
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: issue
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-04
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-04
reported: 2026-10-04, scripted run of plan 08-04 (`check-uat04.sh run`, expectations coded before the run)
severity: minor
note: Clause 1 holds (export on, default prefix `mqtt_actions_export`, ACL rows added first, read back by a second client): a retained payload exists for each of the three owned native devices (Lampe Test, Bar Select, UAT Marker), every component is `switch` or `select` with `enabled_by_default` false, no button, no `test_` key, no `/test` topic, and nothing is retained on `homeassistant/device`. Clause 3 holds (export off): `mqtt_actions_export/#` and `homeassistant/device/#` read back empty. Clause 2 FAILS for two of three devices on BOTH instances (export prefix `homeassistant`, no restart): the UAT Marker (control) got exactly one `mqtt` row, unique id = device id, `disabled_by` integration, as expected, but Lampe Test and Bar Select got an ENABLED `mqtt` row (`switch.lampe_test_2`, `select.bar_select_2`, `disabled_by` null) on ha-a and on ha-b; the native rows stayed present and enabled. The published payload is correct (enabled_by_default false, X3 passes); the enabled state is the likely effect of core MQTT restoring `disabled_by` from the deleted-entity tombstones that the UAT-02 legacy replay left for the same (domain, platform, unique id) on these two devices (HA 2026.9.4 `entity_registry.py` lines 1498-1508; `uat-04/tombstone-cause.txt`). The marker never had a tombstone. This is an inference from the control and the core source, not an isolated reproduction.

### 5. P1-1: HACS client install on a production host
expected: On a real host: custom repository added, integration downloaded, Home Assistant restarted, MQTT Actions added, a second add aborts, the icon is shown; then the integration and the repository are removed again (add and remove only, no device created).
result: pending

### 6. P1-2: English and German strings
expected: The hub flow, the Add switch device dialog and the Repairs text render correctly in the real frontend in English and in German.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-07
evidence: .planning/phases/08-real-instance-verification/08-evidence/p1-2
note: owner-signed 2026-10-07 ("approved P1-2 P3-1", chat, verbatim). The browser MCP (chrome-devtools) was available to the orchestrator session of plan 08-08, so there are screenshots: the hub flow on ha-b was opened in English and aborted (`01`), opened in German and finished with the hostile instance name `Haus \`x\` | _ab_ <b>fett</b>` typed as text (`02`, `03`, `04`, `05`), the Add switch device dialog was captured in German and English and closed without creating a device (`06`, `08`), and the Repairs text is the approval dialog on ha-a in German and English (`p3-1/01..06`). The orchestrator drove the browser (not the owner, not the executor); the owner judged the screenshots / the live view. Scripted around it (executor): ha-b backed up first, hub removed through the config entries REST endpoint (devices kept), new instance id `b4cf285b-428f-426b-9500-8e269634356e` with its own ACL line, availability `1 online` and heartbeat read back by the probe, no `native_cutover_waiting`, marker mirror re-approved on ha-b. Profile language ends at English on both instances (verified through the frontend, `hass.language`).

### 7. P1-3: action editor and validation banners
expected: The action editor works in the current build; an invalid YAML action is rejected with a banner, and a literal `device_id` submitted twice warns the first time and saves on the resubmit.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-06
evidence: .planning/phases/08-real-instance-verification/08-evidence/p1-3
note: owner-signed 2026-10-06 ("approved P1-3 P1-4 P3-2", chat, verbatim). The owner performed the click path in their own browser on ha-a; the browser MCP was unavailable in the executing session, so there are no screenshots. Claude pre-checked the data path through the subentry flow REST API (invalid action gives `invalid_actions` with field onChangeToOn, a literal `device_id` gives `device_id_warning` on the first submit; flow aborted, nothing saved). No UAT P1-3a or P1-3b device was on ha-a at recording time.

### 8. P1-4: Repairs dialog of a failing action
expected: A failing action of an owned device creates a Repairs issue whose dialog renders correctly in the real frontend.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-06
evidence: .planning/phases/08-real-instance-verification/08-evidence/p1-4
note: owner-signed 2026-10-06 ("approved P1-3 P1-4 P3-2", chat, verbatim). Fixture `UAT P1-4` (action `uat_missing.nothing`) created with `import_devices` and toggled on: the Repairs issue `action_failed_{uuid}` (trigger onChangeToOn, error "Action uat_missing.nothing not found") was listed before the owner looked live in their own browser; no screenshots (browser MCP unavailable). ha-a and ha-b were restarted afterwards by the orchestrator; the device was removed in task 3.

### 9. P1-5: retained-versus-live chain
expected: On the current build with a real HA core MQTT client and a real retaining broker (toggle in the UI, full HA restart, broker reconnect), no action runs for replayed state.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-04
evidence: .planning/phases/08-real-instance-verification/08-evidence/p1-5
note: Counted marker lines of the "UAT Marker" device (startup flag off, read from the retained config document) per instance. 1 toggle (the service call the frontend toggle makes, `switch.turn_on` on ha-a, state off before): +1 on ha-a and +1 on ha-b. 2 full restart (`podman restart ha-a ha-b`, new process lifetime, 90 s margin): 0 lines on both while the retained state was replayed. 3 broker reconnect (reload of the core `mqtt` config entry on each instance through `POST /api/config/config_entries/entry/{id}/reload`, response `require_restart: false`; 60 s): still 0 on both. 4 positive control (`switch.turn_off` on ha-a): +1 on both. `mosq` was not restarted (StartedAt unchanged). The toggle was the service call, not a click in the rendered frontend; rendering is not what P1-5 judges.

### 10. P1-6: core version of hassio-n2plus
expected: The core version of the second real host (hassio-n2plus, "Backup"), read in Settings > About, is 2026.9.0 or newer (informational, no code consequence).
result: pending

### 11. P2-1: select subentry flow
expected: In the real frontend: add a select device, enter three options, Done after two, reconfigure with edit, add and remove, in English and in German.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-06
evidence: .planning/phases/08-real-instance-verification/08-evidence/p2-1
note: owner statement 2026-10-06, per item, verbatim: "Vollständig, ok" (chat; the owner first answered "Noch nicht geprüft" and "Nur teilweise gesehen" before confirming this item completely when asked per item). Scripted: the select subentry flow data path over the REST endpoints (flow-precheck.txt). Owner-judged: rendering and wording in English and German in their own browser on ha-a; browser MCP unavailable, so there are no screenshots. In this build "Done" is labelled "Save the device".

### 12. P2-2: breaker loop
expected: A device whose action flips its own state topic trips the breaker (5 runs in 10 seconds) against a real Mosquitto and a real HA process; the Repairs card renders in English and German; release by reconfigure or reload works; a restart while paused stays paused.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-06
evidence: .planning/phases/08-real-instance-verification/08-evidence/p2-2
note: verdict PASS (verdict.txt: 6 live messages after the trip, one breaker warning, pause survives podman restart ha-a, hub reload releases). Owner statement 2026-10-06, per item, verbatim: "Vollständig, ok" (chat; same sequence as P2-1) for the Repairs card in English and German; no screenshots (browser MCP unavailable). The ha-b mirror of UAT Loop is a blocked_ issue, not an approval request, because mqtt.publish is denied for broker-received actions.

### 13. P3-1: approval request rendering
expected: The approval request of a mirrored device in Settings > Repairs renders a device name, owner name and action YAML with backticks, underscores, pipes and a templated service name as plain text in the real frontend.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-07
evidence: .planning/phases/08-real-instance-verification/08-evidence/p3-1
note: owner-signed 2026-10-07 ("approved P1-2 P3-1", chat, verbatim). Roles reversed against the research table (planner decision): ha-b owns the hostile device `UAT P3-1 \`code\` | _u_ <b>bold</b>` (33 printable characters, imported through the guard, `import-shape.txt`) under the hostile instance name `Haus \`x\` | _ab_ <b>fett</b>`, with `{{ 'system_log' }}.write` as a templated service name and a message holding backticks, underscores and a pipe; ha-a is the follower. The approval dialog on ha-a was opened, scrolled and closed (never submitted) in German and English through the chrome-devtools browser MCP by the orchestrator; the owner judged the screenshots / the live view (`01..06`). Never approved on ha-a. Deleted afterwards on ha-b through the integration's own delete step (name placeholder markdown-escaped plain text, count 1, abort `device_deleted`); `topics-after-delete.txt` shows the retained config topic empty, the subentry gone and the approval request gone from ha-a.

### 14. P3-2: delete dialogs
expected: Deleting a device whose name contains backticks and `<b>` shows the name as plain text in the integration's own delete step and in the generic core dialog (whose text an integration cannot change; documented limitation in the README).
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-06
evidence: .planning/phases/08-real-instance-verification/08-evidence/p3-2
note: owner-signed 2026-10-06 ("approved P1-3 P1-4 P3-2", chat, verbatim). The owner judged the two delete dialogs for the devices named with backticks and a bold tag in their own browser; no screenshots (browser MCP unavailable). The owner did not confirm the deletes, so Claude performed them over the guard through the same paths (integration step: placeholder name escaped plain text, count 1; generic path: WS subentry delete); the broker read-back shows both retained config topics empty (`topics-after-delete.txt`, `deletes.txt`).

## Summary

total: 14
passed: 11
issues: 1
pending: 2
skipped: 0
blocked: 0

## Gaps

<!-- Replace the empty list with entries in the gap format of ~/.claude/gsd-core/templates/UAT.md when a check fails (D-08):
     one entry per failed block, with `test:` set to the block number. -->
- truth: "With the export on the core MQTT prefix, every exported device yields only a disabled duplicate on every instance that listens (no enabled mqtt entity)"
  status: failed
  reason: "Scripted result (plan 08-04, UAT-04 clause 2): after `export_prefix` was set to `homeassistant` (no restart), ha-a and ha-b each held an ENABLED mqtt row for Lampe Test (`switch.lampe_test_2`) and Bar Select (`select.bar_select_2`); only the UAT Marker duplicate was `disabled_by: integration`. The export payload itself has `enabled_by_default` false on every component. The enabled rows follow core's restore of `disabled_by` from tombstones of earlier legacy entities (UAT-02 replay twins) with the same unique id. Needs an owner decision: product gap (for example a documented warning or a guard when legacy twins existed) or bench artifact of running UAT-02 before UAT-04 on the same instances."
  severity: minor
  test: 4
  root_cause: "Likely: HA core `async_get_or_create` restores `disabled_by` from a deleted entity with the same (domain, platform, unique_id); inferred from the marker control and the core source, not reproduced in isolation"
  artifacts:
    - path: ".planning/phases/08-real-instance-verification/08-evidence/uat-04/tombstone-cause.txt"
      issue: "core source lines and the tombstones that explain the enabled rows"
  missing: []
  debug_session: ""

## Observations

Non-gap facts recorded while running the checks (companion mode selects of v0.1.0, the live-republish duplicate, the cleanup at the
next start after a core-prefix export, the release HACS reports).

- Mapping: 05-UAT tests 4, 5, 6, 7 are UAT-01, UAT-02, UAT-03, UAT-04.
- Live-republish (WR-03, plan 08-02): with legacy Discovery published while ha-a and ha-b were running, six `mqtt`-platform `_2` entities appeared on each instance within 20 s, stayed through 45 s and a graceful stop, and were gone after the next start (see `08-evidence/uat-02/live-variant.txt`). Classified by the owner as an accepted known limit (`WR03-LIVE-REPLAY`): it stays documented, there is no Gaps entry, and UAT-02's own result (startup replay) is unchanged.
- Catch asymmetry (plan 08-02): in the startup rounds ha-b logged the INFO line "Removed 3 duplicate entities…" while ha-a logged none, although both registries ended clean and both hold six `_2` tombstones; the path that cleaned ha-a is not identified (evidence: `08-evidence/uat-02/log-a.txt`, `twin-tombstones.txt`).

- Reload path (plan 08-03): research assumption A5 named `POST /api/config_entries/entry/{id}/reload`, which answers 404 on HA 2026.9.4; the working path is `POST /api/config/config_entries/entry/{id}/reload`. The first P1-5 run aborted at that point (bench problem, no result) after one restart; the check was re-run completely and the recorded evidence is that second run.
- Repairs API (plan 08-03): the approval of a mirrored device works headless through `POST /api/repairs/issues/fix` (handler `mqtt_actions`, issue id `approval_{uuid}`) followed by `POST /api/repairs/issues/fix/{flow_id}` with `{}` (ends in `create_entry`). Plans needing an approval can reuse it.

- Restart cleanup of the core-prefix duplicates (plan 08-04, research assumption A4, Pitfall 4): after the export was switched off, the live registries of ha-a and ha-b still held one disabled leftover `mqtt` row each (`switch.uat_marker_2`, `disabled_by` integration; the two enabled duplicates of Lampe Test and Bar Select were already gone with the clear). After one `podman restart ha-a ha-b` (90 s margin, graceful stop, file read) both registries held zero `mqtt` rows and zero `_2` entity ids, and 34 `mqtt_actions` rows each (evidence: `08-evidence/uat-04/registry-after-off-{a,b}.json`, `post-restart-{a,b}.json`). A4 is confirmed: the start removes the leftovers. This is an observation, not a failure.
- Enabled export duplicates (plan 08-04, UAT-04 clause 2): on the core prefix the duplicates of Lampe Test and Bar Select were enabled, the one of the UAT Marker disabled; see the Gaps entry for test 4 and `08-evidence/uat-04/tombstone-cause.txt`. The clear step removed the enabled duplicates from the registry (they became tombstones) and left the disabled one until the next start.
- Options flow path (plan 08-04): the hub options flow works headless through `POST /api/config/config_entries/options/flow` (body `{"handler": "<entry id>"}`) and `POST /api/config/config_entries/options/flow/{flow_id}`; like the reload endpoint the prefix is `/api/config/`, not `/api/` as the plan text assumed. The export option applies without a reload. The stored prefix was reset to the default at the end (export off), so the hub options of ha-a now read `discovery_export` false, `export_prefix` `mqtt_actions_export`.

- Companion mode selects (plan 08-05, UAT-01, policy `observation`): the v0.1.0 straggler ha-c created one `select.{name}_mode` per mirrored device, 7 of 7 (`select.bar_select_mode`, `select.baz_mode`, `select.dfgfdgd_mode`, `select.dfsfasdf_mode`, `select.lampe_test_mode`, `select.modus_test_mode`, `select.uat_marker_mode`; platform `mqtt_actions`, unique id `{device id}_mode`, entity category config), next to the instance entities of its own hub (sensor, resync button, instance mode select). They are the v0.1.0 design and are not the switch, select or buttons of the migrated device; evidence: `08-evidence/uat-01/registry-c.json`.
- Stopped straggler stays online (plan 08-05): after `podman stop -t 60 ha-c` (a clean shutdown, exit code 0) the retained availability `mqtt_actions/v1/instances/{ha-c id}/availability` still read `online`; the v0.1.0 instance did not publish `offline` on an HA shutdown. It was cleared by hand with an empty retained publish so a hub re-added in plan 08-08 does not hit `native_cutover_waiting` (Pitfall 10). Not judged here (no gap raised); the heartbeat topic is not retained, so peers that rely on the 90 s heartbeat rule would still see it go stale (inference from `v010/presence.py`, not observed).
- Fresh-instance HTTP config (plan 08-05, bench only): HA 2026.9.4 stores the YAML `http:` block of a new instance as a pending config and reverts to the stable default (port 8123, held by ha-a) with a restart if nobody confirms it within 5 minutes; ha-c ended in recovery mode at 20:08 because of that. Fixed in the bench by promoting the pending config in `~/ha-test/c/.storage/http` (`ha-c-setup.sh --step 9`). Not an integration finding.
- Core Repairs issues on ha-c (plan 08-05): besides the approval request, a fresh instance carries `homeassistant/country_not_configured` and `http/yaml_still_present_after_migration` (the second one is on ha-b as well); both are unrelated to the integration and were allowed explicitly in the check, listed in `uat-01/issues-c.txt`.

- ha-b re-added (plan 08-08, D-03): ha-b now has a NEW hub with the new instance id `b4cf285b-428f-426b-9500-8e269634356e` and the hostile instance name `Haus \`x\` | _ab_ <b>fett</b>` (hub entry title). Its earlier fixtures, the four devices formerly owned by the old id `a09499e4-5674-48d5-b3d6-4860d5226fcb` (Baz, dfgfdgd, dfsfasdf, Modus Schlaf), were removed from the hub with the removal and now appear on ha-b as "Switch/Select device (mirror of Test HA Two)": retained orphans of the old owner id that the new hub does not recognise as its own (visible in `p1-2/04..07`). `~/ha-test/_backup-pre-p12-b-20261006T195117Z` holds ha-b's previous state (`cp -a` of `~/ha-test/b`, taken with ha-b stopped); restore it with BOTH containers stopped if an earlier scripted check has to be re-run on the old state. `~/ha-test/.instance-ids.env` carries the new id and `lib.sh` prefers it, so the later gates look for the new id; the `ha_two` ACL block keeps the old availability line next to the new one (`p1-2/acl-diff.txt`, copy before the edit `~/ha-test/mosquitto/acl.bak-phase8-08`). The old id's retained availability reads `offline`.
- Profile language (plan 08-08): switched EN -> DE -> EN on ha-b and DE -> EN on ha-a through the profile page by the orchestrator; it ends at English on both instances, verified through the frontend (`hass.language == "en"` on localhost:8123 and localhost:8124 after the captures). Unlike plans 08-06 and 08-07, the chrome-devtools browser MCP WAS available to the orchestrator in this run, so P1-2 and P3-1 have real screenshots; the owner judged them.
- Delete step placeholder (plan 08-08): the integration's `delete_device` menu step on ha-b rendered the hostile device name as a markdown-escaped plain-text placeholder (every backtick, pipe, underscore and angle bracket backslash-escaped; count 1), consistent with P3-2; the raw placeholder is in the Task 3 output quoted in `08-08-SUMMARY.md`.

## Owner decisions

| Decision id | Option | Date |
|-------------|--------|------|
| API-ACCESS | owner-tokens (token a ok, token b ok; files mode 0600 in ~/ha-test, outside the repo; revoke after the phase) | 2026-10-04 |
| WR03-LIVE-REPLAY | accepted-limit (no reason given; relayed to the executor by the orchestrator from the owner's chat answer) | 2026-10-04 |
| UAT01-WORDING | observation (the v0.1.0 companion mode selects are recorded under Observations and UAT-01 can still pass; it fails only on `mqtt`-platform rows for migrated devices, on switch or button rows of `mqtt_actions` for them, or on any error; chosen by the owner in chat, relayed by the orchestrator) | 2026-10-06 |

## Bench state left behind

Recorded so nothing is forgotten when the phase ends (T-08-04). All of it is on the test bench in `~/ha-test`; the production
broker and hosts are untouched.

- Broker users `uat_probe` (read and write `#`) and `uat_bridge` (state topics only) with random passwords in `~/ha-test/.mqtt-uat.env`
  (mode 0600). Removal: `~/ha-test/bin/bench-users.sh remove`.
- An INFO `logger` block for `custom_components.mqtt_actions` in the `configuration.yaml` of ha-a and ha-b.
- Backup of the instances and the broker configuration taken before the first restart (path in `08-evidence/00-preflight/backup-manifest.txt`).
- Long-lived tokens `~/ha-test/.token-a` and `~/ha-test/.token-b` (mode 0600, owner decision API-ACCESS). The owner revokes them in the
  two profile security pages after the phase.
- ACL rows `topic readwrite mqtt_actions_export/#` in the `ha_one` and `ha_two` blocks of `~/ha-test/mosquitto/acl` (plan 08-04; copy
  before the edit: `~/ha-test/mosquitto/acl.bak-phase8-04`; diff: `08-evidence/uat-04/acl-diff.txt`).
- The "UAT Marker" device (plan 08-03) on ha-a and its approved mirror on ha-b, retained on the broker; to be removed at phase end.
- Instance `ha-c` (plan 08-05): container created, now STOPPED (not removed), directory `~/ha-test/c`, port 8125, v0.1.0 component mounted read-only from `~/ha-test/v010`; its owner password in `~/ha-test/.ha-c-owner` and long-lived token `~/ha-test/.token-c` (both mode 0600; the owner revokes the token with the others); broker user `ha_three` (password in `~/ha-test/.mqtt-uat.env`) with an ACL block in `~/ha-test/mosquitto/acl` (copy before the edit: `~/ha-test/mosquitto/acl.bak-phase8-05`; diff: `08-evidence/uat-01/acl-diff.txt`). Its retained availability topic was cleared; remove the container, `~/ha-test/c` and the user at phase end.
- ha-b's re-added hub (plan 08-08): new instance id `b4cf285b-428f-426b-9500-8e269634356e`, hostile instance name as the hub entry title, four orphan mirrors of the old owner id on ha-b (see Observations); `~/ha-test/.instance-ids.env` (new id, not a secret), `~/ha-test/_backup-pre-p12-b-20261006T195117Z` (ha-b before the removal, path in `~/ha-test/.current-backup-p12`), ACL line for the new id in the `ha_two` block (copy before the edit: `~/ha-test/mosquitto/acl.bak-phase8-08`; diff: `08-evidence/p1-2/acl-diff.txt`). The hostile P3-1 device is deleted; `P31_ID` stays in `~/ha-test/.fixtures-frontend.env` for the cleanup gate.
- Helper scripts in `~/ha-test/bin/` (outside the repository; a scrubbed copy is added to the evidence by plan 08-10).
