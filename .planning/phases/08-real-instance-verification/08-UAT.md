---
status: complete
phase: 08-real-instance-verification
source:
  - .planning/phases/08-real-instance-verification/08-CONTEXT.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md
  - .planning/milestones/v1.0-phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-UAT.md
started: 2026-10-04T18:55:00Z
updated: 2026-10-11T13:45:00Z
---

## Current Test

[testing complete]

number: none
name: testing complete (plan 08-14, 2026-10-11): all 14 checks recorded and pass; the UAT-04 gap (Gaps entry test: 4) is resolved by the receiver-guard re-run
expected: |
  Nothing is left to test on the bench. `status: complete` because no block is `issue`: blocks 2, 3, 4 and 9 were re-run on the
  receiver-guard build (plan 08-18, evidence suffix `-rerun2`) and pass; the other ten blocks stay on their recorded evidence
  (owner confirmations UAT04-GAP-DISPOSITION and UAT04-RECEIVER-GUARD). The verifier runs of plan 08-15 follow.
awaiting: the verifier runs of plan 08-15; no test is awaited

## Build under test

The containers bind-mount `custom_components/mqtt_actions` of the main checkout read-only. The pinned identity is recorded in
`08-evidence/00-preflight/build.txt`; a later `check-preflight.sh --quick` re-asserts it before every wave (D-03).

- sha: b8232252540a55969145ca0034d8fd86b4be3b7c
- previous sha: caf2fe5dc003ea834104f4016d1996be4132e0c8 (the re-pin of plan 08-13, the guard of plan 08-12)
- previous sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 (the first pin, blocks 1, 5 to 8 and 10 to 14 stay recorded on it)
- branch: gsd/phase-08-real-instance-verification
- commit time: 2026-10-11T14:24:01+02:00
- image: ghcr.io/home-assistant/home-assistant:2026.9 (HA 2026.9.4)
- ha-a (Test HA One, port 8123): instance id 3851f34f-fa67-4f3c-bba0-122465013c3d
- ha-b (Test HA Two, port 8124): instance id b4cf285b-428f-426b-9500-8e269634356e (the hub was re-added in plan 08-08; the first record named a09499e4-5674-48d5-b3d6-4860d5226fcb)

The blocks that were not re-run on the receiver-guard build (UAT-01, P1-1 to P1-4, P1-6, P2-1, P2-2, P3-1, P3-2) keep their recorded sha (the first pin); see the Observations entry on the checks that were not re-run. Blocks 2, 3, 4 and 9 carry the new sha.

Phase 1 item P1-1 (HACS client install) records the release tag it really installed instead, because HACS downloads the newest
release and not this checkout (D-03).

## Results (D-05)

| Check | Requirement or source | Result | Date | Build SHA | Evidence |
|-------|-----------------------|--------|------|-----------|----------|
| UAT-01 | UAT-01, ROADMAP criterion 1, 05-UAT test 4 | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/uat-01 |
| UAT-02 | UAT-02, ROADMAP criterion 2, 05-UAT test 5 | pass | 2026-10-11 | b8232252540a55969145ca0034d8fd86b4be3b7c | .planning/phases/08-real-instance-verification/08-evidence/uat-02-rerun2 |
| UAT-03 | UAT-03, ROADMAP criterion 3, 05-UAT test 6 | pass | 2026-10-11 | b8232252540a55969145ca0034d8fd86b4be3b7c | .planning/phases/08-real-instance-verification/08-evidence/uat-03-rerun2 |
| UAT-04 | UAT-04, ROADMAP criterion 4, 05-UAT test 7 | pass | 2026-10-11 | b8232252540a55969145ca0034d8fd86b4be3b7c | .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun2 |
| P1-1 | Phase 1 item 1 (07-PROOF) | pass | 2026-10-07 | d0f660cb2422c7688d22a674cf54f955a8c26c7f | .planning/phases/08-real-instance-verification/08-evidence/p1-1 |
| P1-2 | Phase 1 item 2 (07-PROOF) | pass | 2026-10-07 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-2 |
| P1-3 | Phase 1 item 3 (07-PROOF) | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-3 |
| P1-4 | Phase 1 item 4 (07-PROOF) | pass | 2026-10-06 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-4 |
| P1-5 | Phase 1 item 5 (07-PROOF) | pass | 2026-10-11 | b8232252540a55969145ca0034d8fd86b4be3b7c | .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun2 |
| P1-6 | Phase 1 item 6 (07-PROOF) | pass | 2026-10-07 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/p1-6 |
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
sha: b8232252540a55969145ca0034d8fd86b4be3b7c
date: 2026-10-11
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-02-rerun2
note: Re-run on the receiver-guard build (plans 08-17 and 08-18; final re-run, `-rerun2` folder) with the unchanged expectations E1 to E4 (`verdict.txt`: E1 to E4 hold in round 1 and round 2 on ha-a and ha-b). Superseded and kept untouched as history: the first record in `uat-02` (build b7f52b34, 2026-10-04) and the re-run of plan 08-13 in `uat-02-rerun` (build caf2fe5d, PASS). First record, still true of the check itself: two startup rounds with retained legacy Discovery published while ha-a and ha-b were stopped; after each graceful stop both registries held no `mqtt` row, no `_2` id, no legacy `mqtt` device and the `mqtt_actions` rows (entity id, registry id, unique id, device id) identical to the baseline; the replay really created the twins and they were removed. On this build the guard disables a replayed row before the catch removes it, so the null tombstones of Lampe Test and Bar Select turned into `disabled_by` integration; plan 08-18 flipped them back before UAT-04 (see block 4). Live variant (observation only, first record): published while running, six `_2` entities appeared on both instances within 20 s, stayed through a graceful stop, and were gone after the next start.

### 3. UAT-03: command across two real instances
expected: A command issued on one of two real instances runs the actions exactly once on every approved instance, and an unknown payload is ignored and leaves the state unchanged.
result: pass
sha: b8232252540a55969145ca0034d8fd86b4be3b7c
date: 2026-10-11
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-03-rerun2
note: Re-run on the receiver-guard build (plan 08-18, final re-run, `-rerun2` folder, fresh marker `87c29b56-8abe-4531-b03c-c402a2f10cb8`) with the unchanged steps A to D (`verdict.txt`: A, B, C and D hold on both instances). Superseded and kept untouched as history: `uat-03` (first run, build b7f52b34, 2026-10-04) and `uat-03-rerun` (plan 08-13, build caf2fe5d, PASS). Steps as in the first record: marker device "UAT Marker" (owner ha-a, inert system_log.write actions) counted per instance in one process lifetime, each step followed by a wait. A (unapproved control, command on ha-a): ha-a +1, ha-b 0. Approval of the mirror on ha-b through the Repairs fix flow API. B (command on ha-a): +1 on ha-a and +1 on ha-b after 60 s. C (command on the ha-b mirror): +1 on ha-a and +1 on ha-b after 60 s. D (`banana`, QoS 1, not retained, published by uat_bridge): marker deltas 0 on both, `Ignoring unknown payload` +1 on each instance, entity state on both unchanged (on), retained broker value read back unchanged (ON). A subscriber's capture shows retain=0 for every live message, so the not-retained proof is the unchanged retained read-back.

### 4. UAT-04: Discovery export and core prefix
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: pass
sha: b8232252540a55969145ca0034d8fd86b4be3b7c
date: 2026-10-11
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun2
note: Final re-run of plan 08-18 on the receiver-guard build (plan 08-17), expectations X1 to X10 unchanged (the check scripts are byte-identical to the scrubbed copies of plan 08-13, shown by `cmp` in plan 08-18 Task 1; the suffix patch of 08-13 is `uat-04-rerun/script-patches.diff`). Disposition `guard-and-document`, modifier `full-rerun` (decisions UAT04-GAP-DISPOSITION, D08-WAIVER and UAT04-RECEIVER-GUARD; isolation classification TOMBSTONE-ONLY). The run started from the regression state: tombstones with `disabled_by` null for the Lampe Test switch and the Bar Select select on both instances (the failing state of the first run), live mqtt rows 0 on both, restored by plan 08-18 before the run by flipping `disabled_by` back on four existing registry records and proven in the line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0" of `uat-04-rerun2/prepare.txt`. The options flow was applied on ha-a only, so ha-a exported and ha-b only received the export. Result: clause 1 holds (default prefix, X1 to X6), clause 2 holds on BOTH instances (core prefix, no restart: one mqtt row per exported device with `disabled_by` integration, no enabled mqtt row, native rows present and enabled; X7 to X9), clause 3 holds (export off, X10). The cases that failed in the 08-13 re-run (ha-b: Lampe Test and Bar Select with `disabled_by` null) now pass. Guard log (plan 08-18 observation): the INFO line "Disabled 1 duplicate entities that core MQTT created for native devices" appears twice on ha-a and twice on ha-b when the export arrived on the core prefix (one pass for the switch, one for the select; `guard-log-a.txt`, `guard-log-b.txt`); the marker needed none (it had no tombstone, core created its row disabled). After one graceful restart both instances hold 0 live mqtt rows (`post-restart.txt`). History, never edited and superseded by this run: the first run in `uat-04` and `uat-04-isolation` (build b7f52b34, issue: clause 2 failed for Lampe Test and Bar Select on both instances) and the re-run of plan 08-13 in `uat-04-rerun` (build caf2fe5d, FAIL on ha-b because receivers of the export were not covered by the guard).

### 5. P1-1: HACS client install on a production host
expected: On a real host: custom repository added, integration downloaded, Home Assistant restarted, MQTT Actions added, a second add aborts, the icon is shown; then the integration and the repository are removed again (add and remove only, no device created).
result: pass
override_by: Alexander Kentner
sha: d0f660cb2422c7688d22a674cf54f955a8c26c7f
date: 2026-10-07
evidence: .planning/phases/08-real-instance-verification/08-evidence/p1-1
note: owner-signed 2026-10-07 (chat, verbatim: the decision "P1-1, Pfad host-with-integration:", then "Wie vorgeschlagen" to the orchestrator's proposed line "production host 1, override Alexander Kentner, HACS v1.0.0, P1-1 approved, nicht gelaufen: erstes Hinzufügen und Entfernen"; relayed to the executor). Abbreviated path host-with-integration (PROD-HOST) on production host 1, which already runs MQTT Actions: the repository card in HACS with its installed version, Redownload/Update, restart, the icon on the integration page, a second Add integration > MQTT Actions aborts as already configured. Steps NOT run (hence the override in the owner's own name, D-07): the first add of the integration (impossible on a host that already runs the single-instance integration), the removal of the integration and the removal of the repository. HACS-reported version v1.0.0 = the newest non-prerelease release; `sha:` is the release tag SHA from `p1-1/release-identity.txt` (`git rev-parse v1.0.0`, `gh release view v1.0.0`: published 2026-10-03, not a prerelease; `git diff --stat v1.0.0 HEAD` over hacs.json, the manifest and the brand files is empty), not the bench SHA (see Build under test). No cleanup needed: nothing installed or removed, no temporary hub under the base topic `phase8_hacs_check` created, no residue on the production broker (T-08-26 did not arise). The owner performed every step; Claude did not connect to the production host or broker (D-01, D-02).

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
sha: b8232252540a55969145ca0034d8fd86b4be3b7c
date: 2026-10-11
evidence: .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun2
note: Re-run on the receiver-guard build (plan 08-18, final re-run, `-rerun2` folder) with the unchanged steps (`verdict.txt`: toggle +1, restart 0, mqtt entry reload 0, positive control +1, on both instances). Superseded and kept untouched as history: `p1-5` (first run, build b7f52b34, 2026-10-04) and `p1-5-rerun` (plan 08-13, build caf2fe5d, PASS). Steps as in the first record: counted marker lines of the "UAT Marker" device (startup flag off, read from the retained config document) per instance. 1 toggle (the service call the frontend toggle makes, `switch.turn_on` on ha-a, state off before): +1 on ha-a and +1 on ha-b. 2 full restart (`podman restart ha-a ha-b`, new process lifetime, 90 s margin): 0 lines on both while the retained state was replayed. 3 broker reconnect (reload of the core `mqtt` config entry on each instance through `POST /api/config/config_entries/entry/{id}/reload`, response `require_restart: false`; 60 s): still 0 on both. 4 positive control (`switch.turn_off` on ha-a): +1 on both. `mosq` was not restarted (StartedAt unchanged). The toggle was the service call, not a click in the rendered frontend; rendering is not what P1-5 judges.

### 10. P1-6: core version of hassio-n2plus
expected: The core version of the second real host (hassio-n2plus, "Backup"), read in Settings > About, is 2026.9.0 or newer (informational, no code consequence).
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-07
evidence: .planning/phases/08-real-instance-verification/08-evidence/p1-6
note: owner statement 2026-10-07 (chat, verbatim, answered to the orchestrator and relayed): "P1-6: 2026.9.4". The owner read the core version in Settings > About of hassio-n2plus (D-02); Claude did not connect to the host. 2026.9.4 is at or above the 2026.9.0 floor of hacs.json (`tests/test_toolchain.py` `test_home_assistant_floor` compares the tuple against (2026, 9, 0)), so the item passes; it is informational with no code consequence. `sha:` is the phase's pinned bench SHA like every block except P1-1, although the host's core version does not depend on this build.

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
passed: 14
issues: 0
pending: 0
skipped: 0
blocked: 0

## Requirement verdicts

For the orchestrator that closes the phase: a requirement is complete only when its block is `pass`. An `issue` block keeps its
requirement open until the owner either leaves it as a gap for follow-up work (the default, D-08) or records an override in the
owner's own name (`override_by:` in the block plus an Owner decisions entry, D-07); plan 08-10 Task 2 asks that question. The
verdict column repeats the block's `result:` and is checked against it by `~/ha-test/bin/check-final.sh`.

| Requirement | Block | Verdict | Evidence |
|-------------|-------|---------|----------|
| UAT-01 | 1 | pass | 08-evidence/uat-01 (2026-10-06, policy observation for the v0.1.0 companion selects) |
| UAT-02 | 2 | pass | 08-evidence/uat-02-rerun2 (2026-10-11, receiver-guard build, two startup rounds; the live variant is an accepted limit, WR03-LIVE-REPLAY; first record in uat-02 and 08-13 re-run in uat-02-rerun superseded) |
| UAT-03 | 3 | pass | 08-evidence/uat-03-rerun2 (2026-10-11, receiver-guard build, one run per approved instance, unknown payload ignored; uat-03 and uat-03-rerun superseded) |
| UAT-04 | 4 | pass | 08-evidence/uat-04-rerun2 (2026-10-11, receiver-guard build, from the restored null-tombstone state on both instances; Gaps entry test: 4 resolved; uat-04 FAIL and uat-04-rerun FAIL kept as history) |

ROADMAP success criterion 6 (the ten human items, no requirement id) is judged per archived phase report by the verifier, not
here. Item-to-block mapping: Phase 1 items 1 to 6 are blocks 5 to 10, Phase 2 items 1 and 2 are blocks 11 and 12, Phase 3 items
1 and 2 are blocks 13 and 14; all ten blocks are `pass` (block 5 with `override_by: Alexander Kentner` on the abbreviated path,
PROD-HOST). Phase 4 has no human item and stays `passed`. Block 4 belongs to no archived report (Phase 5 UAT test 7).

## Verification refresh

The archived Phase 1 to 3 reports were regenerated by the gsd-verifier agent (one run per phase, 2026-10-08), not edited by hand. Each carries a
`covered_digest` copied from `verification.fingerprint`, and each human item is resolved with a `resolution:` that names its ledger block, evidence
folder, recorded sha and date. Before Phase 8 every report read `human_needed`.

| Phase | Before | After | Score | Human items resolved | Human-item overrides |
|-------|--------|-------|-------|----------------------|----------------------|
| 1 (walking skeleton) | human_needed | passed | 8/8 | 6 (blocks 5 to 10) | 1 (P1-1, `override_by: Alexander Kentner`, abbreviated host-with-integration path) |
| 2 (select devices) | human_needed | passed | 10/10 | 2 (blocks 11 and 12) | 0 |
| 3 (trust and ownership) | human_needed | passed | 5/5 | 2 (blocks 13 and 14) | 0 |

Each report also keeps the recorded Phase 5 supersession override (D-03) of the truths that Phase 5 replaced on purpose; that override sits in the score,
not in the human-item column. Phase 4 was already `passed` (Phase 7) and still reads `passed`. Block 4 (UAT-04) is a Phase 5 item and is not a truth of Phases 1 to 3. At that refresh it was an `issue` and an open gap (owner decision UAT04-DISPOSITION);
plans 08-12 to 08-18 closed it (block 4 `pass` on the receiver-guard build, 2026-10-11).

## Gaps

<!-- Replace the empty list with entries in the gap format of ~/.claude/gsd-core/templates/UAT.md when a check fails (D-08):
     one entry per failed block, with `test:` set to the block number. -->
- truth: "With the export on the core MQTT prefix, every exported device yields only a disabled duplicate on every instance that listens (no enabled mqtt entity)"
  status: resolved
  resolution: "Resolved 2026-10-11 by the guard and its receiver-side extension (plans 08-12 and 08-17, owner decisions UAT04-GAP-DISPOSITION and UAT04-RECEIVER-GUARD, disposition guard-and-document) and proven by the final re-run of plan 08-18 on build b8232252540a55969145ca0034d8fd86b4be3b7c (evidence 08-evidence/uat-04-rerun2, PASS on the regression state of null tombstones on both instances for the Lampe Test switch and the Bar Select select, ha-b receiving only); no pruned-state qualifier applies, the pass is on the failing state."
  reason: "Scripted result (plan 08-04, UAT-04 clause 2): after `export_prefix` was set to `homeassistant` (no restart), ha-a and ha-b each held an ENABLED mqtt row for Lampe Test (`switch.lampe_test_2`) and Bar Select (`select.bar_select_2`); only the UAT Marker duplicate was `disabled_by: integration`. The export payload itself has `enabled_by_default` false on every component. The enabled rows follow core's restore of `disabled_by` from tombstones of earlier legacy entities (UAT-02 replay twins) with the same unique id. Needs an owner decision: product gap (for example a documented warning or a guard when legacy twins existed) or bench artifact of running UAT-02 before UAT-04 on the same instances. Re-run of plan 08-13 on build caf2fe5dc003ea834104f4016d1996be4132e0c8 (the guard of plan 08-12): ha-a passes, ha-b fails X7 for Lampe Test and Bar Select (one mqtt row each, `disabled_by` null) and X8 (`select.bar_select_2` and `switch.lampe_test_2` enabled), because the guard arms only on the exporting instance and receivers of the export are not covered; follow-up plans 08-16 to 08-18 (owner decision UAT04-RECEIVER-GUARD), plan 08-18 re-ran everything on the receiver-guard build and UAT-04 passes (`uat-04-rerun2/verdict.txt`), recorded by plan 08-14."
  severity: minor
  test: 4
  root_cause: "Observed, not inferred (plan 08-11, classification TOMBSTONE-ONLY): in one export window on the core prefix `homeassistant`, read on the live registries of ha-a and ha-b before any restart, the fresh device ISO-CLEAN (no mqtt-platform tombstone, proven from the flushed registry files) got exactly one mqtt row with `disabled_by` integration on both instances, while the fresh device ISO-TWIN (a real tombstone with `disabled_by` null left by the legacy-Discovery replay catch) got exactly one mqtt row with `disabled_by` null, so enabled, on both instances. HA core restores `disabled_by` from the deleted entity with the same domain, platform and unique id; a clean id is not affected. Evidence: `08-evidence/uat-04-isolation/classification.txt`, `result.txt`, `twin-round.txt`"
  artifacts:
    - path: ".planning/phases/08-real-instance-verification/08-evidence/uat-04/tombstone-cause.txt"
      issue: "core source lines and the tombstones that explain the enabled rows (the inference this plan confirmed)"
    - path: ".planning/phases/08-real-instance-verification/08-evidence/uat-04-isolation/classification.txt"
      issue: "TOMBSTONE-ONLY: ISO-CLEAN disabled on both instances, ISO-TWIN enabled on both instances"
    - path: ".planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun/verdict.txt"
      issue: "08-13 re-run on the guard build: FAIL on ha-b (X7 for Lampe Test and Bar Select, X8 two enabled rows), the guard does not cover receivers of the export (history, superseded)"
    - path: ".planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun2/verdict.txt"
      issue: "final re-run on the receiver-guard build: PASS on both instances from the restored null-tombstone state (resolves the gap)"
  missing: []
  debug_session: ".planning/phases/08-real-instance-verification/08-evidence/uat-04-isolation/classification.txt"

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
- Bench check defect, `check-uat02.sh clean` (plan 08-11, Rule 3, authorized by the owner in chat): since plan 08-08 re-added the hub of ha-b under a new config entry id, `clean` compared ha-b's hub-owned `mqtt_actions` rows (unique ids `{hub entry id}_resync`, `_instance_mode`, `_roster`) with `uat-02/baseline-b.json`, which still holds the rows of the old hub, and failed although nothing else had moved. Fix, bench script only: `do_clean` now compares the native rows of both sides without the three hub-owned unique id suffixes; E1 to E3 are unchanged, the baseline file is not edited, and no product, test or workflow file changed (stale anchor empty). The scrubbed copy in `08-evidence/00-preflight/bench-scripts/check-uat02.sh` is refreshed; plan 08-13 uses the same fix.
- Delete step placeholder (plan 08-08): the integration's `delete_device` menu step on ha-b rendered the hostile device name as a markdown-escaped plain-text placeholder (every backtick, pipe, underscore and angle bracket backslash-escaped; count 1), consistent with P3-2; the raw placeholder is in the Task 3 output quoted in `08-08-SUMMARY.md`.

- Release HACS reports (plan 08-09, P1-1, research assumption A9): the HACS client on production host 1 reported v1.0.0, the newest non-prerelease release (`gh release list` marks it Latest; the prerelease v1.0.1-rc1 of Phase 7 is deleted). Its tag SHA `d0f660cb2422c7688d22a674cf54f955a8c26c7f` differs from the bench SHA; hacs.json, the manifest and the brand files are identical between the tag and HEAD (`p1-1/release-identity.txt`). P1-1 ran on the abbreviated path (the host already runs the integration), so no temporary hub, no base topic `phase8_hacs_check` and no retained topic came into being on the production broker; P1-6 read 2026.9.4 on hassio-n2plus. Both answers were given by the owner to the orchestrator in chat and relayed to the executor; Claude touched neither production host nor the production broker.

- UAT-04 isolation (plan 08-11, classification TOMBSTONE-ONLY): two fresh inert switches, `UAT Iso Clean` (never had an mqtt-platform entity) and `UAT Iso Twin` (given a real tombstone through the UAT-02 field path: retained legacy Discovery replayed at start, the replay catch removes the enabled legacy twin), were exported on the core prefix in one window and both live registries read before any restart. Results (ha-a and ha-b identical): ISO-CLEAN one mqtt row, `disabled_by` integration; ISO-TWIN one mqtt row, `disabled_by` null (enabled). The tombstone proof (T1 to T3, read from the flushed registry files before the export) held on both instances; Lampe Test and Bar Select read enabled and the UAT Marker disabled, as predicted. The expectations and classification rules were coded in the script header before the run (header sha256 `da30841ec8c1c9532ea50ee8824c0792e8d29877fc5ec6d962a36925723f8288` in `result.txt`); the tracer (clean arm only) read CLEAN-ARM-DISABLED. Evidence: `08-evidence/uat-04-isolation/`.
- Catch asymmetry again (plan 08-11, verification finding 5): in the twin round the replay catch logged its INFO line "Removed 3 duplicate entities…" on ha-b only (count 1) and not on ha-a (count 0), although both registries held the three null-disabled_by tombstones of ISO-TWIN afterwards (`08-evidence/uat-04-isolation/twin-round.txt`). The path that removed the twins on ha-a without the log line is still not identified; the registry result is the same on both.
- Effect of the cleanup restart (plan 08-11): after the export was switched off, one `podman restart ha-a ha-b` (90 s margin) removed the leftover disabled export rows again (`check-uat04.sh clean` PASS, no mqtt-platform row, no `_2` entity id), the same as research assumption A4. The restart has to come BEFORE the owner delete of a fixture: the replay catch removes the leftover disabled export row only while its device still has the native twin; the tracer and the main run therefore restart first and delete afterwards (`08-evidence/uat-04-isolation/cleanup.txt`).
- Bench-script facts (plan 08-11, Rule 3): the mirror of a fixture on ha-b is detected through a registry row of platform `mqtt_actions` on ha-b, not through a config subentry (mirrors are entities, not subentries); the planner's clarification that the native row is judged on ha-a only (ha-b's mirror is never approved) is coded in the header of `check-uat04-iso.sh`.

- UAT-04 re-run on the guard build (plan 08-13): UAT-02, UAT-03 and P1-5 re-run PASS and UAT-04 re-run FAIL on build `caf2fe5dc003ea834104f4016d1996be4132e0c8` (the guard of plan 08-12), after a host reboot found at plan start (mosq started again and its StartedAt anchor re-anchored, the old value kept as `.mosq-started-before-phase8.pre-reboot`). Evidence in `08-evidence/uat-02-rerun`, `uat-03-rerun`, `p1-5-rerun` and `uat-04-rerun` (verdict `uat-04-rerun/verdict.txt`: ha-b X7 for Lampe Test and Bar Select, X8 two enabled rows), untouched. These runs are history: the result recorded for blocks 2, 3, 4 and 9 will be the re-run of plan 08-18 on the receiver-guard build (owner decision UAT04-RECEIVER-GUARD, plans 08-16 to 08-18; plan 08-14 records it) and the 08-13 FAIL stays in the record.
  Final result (plan 08-14, from plan 08-18): the first run (build b7f52b34, `uat-04`) failed clause 2 on both instances; the re-run of plan 08-13 (build caf2fe5d, guard on the exporting instance only) passed on ha-a and failed on ha-b; the final re-run on the receiver-guard build `b8232252540a55969145ca0034d8fd86b4be3b7c` (`uat-02-rerun2`, `uat-03-rerun2`, `p1-5-rerun2`, `uat-04-rerun2`) passes in all four checks with the original expectations. On this build the UAT-02 replay turns the null tombstones of Lampe Test and Bar Select into `disabled_by` integration (the guard disables a replayed row before the catch removes it); plan 08-18 therefore restored the failing state before UAT-04 by flipping `disabled_by` back to null on exactly those four existing records (both entity registries backed up, validated, nothing fabricated; `uat-04-rerun2/prepare.txt` holds the projections before and after and the exact state line), and UAT-04 passed from that state. Guard log: two INFO lines on ha-a and two on ha-b at the moment the core-prefix export arrived (one for the switch, one for the select); after one restart both hold 0 live mqtt rows. A bench defect found by plan 08-18: `check-uat03.sh` starts a background `mosquitto_sub` that outlives the check and can write into an earlier evidence folder; it was stopped by hand and the single affected file restored, and the script was not changed.

- Checks not re-run on the receiver-guard build (plan 08-14, D-03; owner confirmations UAT04-GAP-DISPOSITION and UAT04-RECEIVER-GUARD in Owner decisions): UAT-01, P2-2 and the owner-judged frontend items P1-1 to P1-4, P1-6, P2-1, P3-1 and P3-2 stay on their recorded evidence at the first pin `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`. Reason: the guard is armed on every native instance but triggers only on a core MQTT row of a native id, which none of these checks creates (UAT-01 shows no `mqtt` row on any instance, the frontend items run with the export off and publish no Discovery), and no translation, service, option or Repairs issue changed; the product diff against both earlier pins names only `manager.py` and `takeover.py` (`uat-04-rerun2/prepare.txt`). Not scoped: the modifier is `full-rerun`, so UAT-03 and P1-5 WERE re-run (blocks 3 and 9). Superseded and untouched: the first runs (`uat-04` FAIL, `uat-02`, `uat-03`, `p1-5`) and the re-run of plan 08-13 on build `caf2fe5dc003ea834104f4016d1996be4132e0c8` (`uat-04-rerun` FAIL on ha-b because receivers of the export were not covered, `uat-02-rerun`, `uat-03-rerun` and `p1-5-rerun` PASS).

## Owner decisions

| Decision id | Option | Date |
|-------------|--------|------|
| API-ACCESS | owner-tokens (token a ok, token b ok; files mode 0600 in ~/ha-test, outside the repo; revoke after the phase) | 2026-10-04 |
| WR03-LIVE-REPLAY | accepted-limit (no reason given; relayed to the executor by the orchestrator from the owner's chat answer) | 2026-10-04 |
| UAT01-WORDING | observation (the v0.1.0 companion mode selects are recorded under Observations and UAT-01 can still pass; it fails only on `mqtt`-platform rows for migrated devices, on switch or button rows of `mqtt_actions` for them, or on any error; chosen by the owner in chat, relayed by the orchestrator) | 2026-10-06 |
| PROD-HOST | host-with-integration (P1-1 on production host 1, which already runs MQTT Actions; abbreviated path: repository card, Redownload/Update, restart, icon, second add aborts; the first add and the removal of integration and repository are not run; override in the owner's own name: Alexander Kentner; the owner's replies in chat to the orchestrator were "P1-1, Pfad host-with-integration:" and, to the proposed line "production host 1, override Alexander Kentner, HACS v1.0.0, P1-1 approved, nicht gelaufen: erstes Hinzufügen und Entfernen", "Wie vorgeschlagen"; relayed to the executor) | 2026-10-07 |
| UAT04-DISPOSITION | leave-as-gap (the Gaps entry test: 4, severity minor, stays open for follow-up work; no override; chosen by the owner in answer to the orchestrator's question, "Als Gap offen lassen (Standard)") | 2026-10-08 |
| UAT04-GAP-DISPOSITION | guard-and-document, modifier full-rerun (the whole scripted group is re-run on the new build); the owner confirmed UAT-01, P2-2 and the owner-judged frontend items (P1-1 to P1-4, P1-6, P2-1, P3-1, P3-2) as not affected, they stay on their recorded evidence at the pinned build; classification TOMBSTONE-ONLY; the owner's words, relayed by the orchestrator: "guard-and-document, confirm-not-affected. Ja, ich meinte 999.1, das sollten wir dann auf eine folgende Phase umlabeln" (the 999.1 remark concerns the ROADMAP backlog, not this plan); recorded in `08-evidence/uat-04-isolation/disposition.txt` | 2026-10-10 |
| D08-WAIVER | waive the D-08 clause that keeps fixes out of Phase 8 for the gap closure of UAT-04 clause 2; a product fix (guard) may land in Phase 8; guard, guard-and-document, document and bench-artifact all stay open (the failure rule of D-08 stands; chosen by the owner in answer to the orchestrator's question, relayed by the orchestrator; confirmed directly by the owner in chat on 2026-10-11 with "ja" to the question whether the exception for the UAT-04 fix in Phase 8 applies) | 2026-10-08 |
| UAT04-RECEIVER-GUARD | extend-and-confirm (extends the D08-WAIVER exception to plans 08-16 to 08-18 for UAT-04 clause 2 only: the guard against enabled core-prefix export duplicates is armed on every native instance independent of its own export option, with the full scripted group re-run on the new build; the owner confirmed UAT-01, P2-2 and the owner-judged frontend items (P1-1 to P1-4, P1-6, P2-1, P3-1, P3-2) as not affected, on the replacement argument "the guard triggers only on a core MQTT row of a native id, which these checks do not create"; the failure rule of D-08 stands; no extra checks to widen; chosen by the owner in answer to the orchestrator's question "Plan 08-16 (Wave 14) braucht deine Entscheidung UAT04-RECEIVER-GUARD ...", relayed by the orchestrator; recorded in `08-evidence/uat-04-receiver-guard/decision.txt`) | 2026-10-11 |

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
- Gap closure 08-11 (UAT-04 isolation): two backups of both `core.entity_registry` files, mode 0700, taken with both instances stopped before each run: `~/ha-test/_backup-pre-gap-uat04-20261008T210459Z` (tracer) and `~/ha-test/_backup-pre-gap-uat04-20261008T211551Z` (main run; pointer `~/ha-test/.current-backup-gap08`); `~/ha-test/.fixtures-gap.env` (ids only: `TRACER_ISO_CLEAN_ID`, `ISO_CLEAN_ID`, `ISO_TWIN_ID`). The fixtures are deleted and the bench is back at its baseline (export off, no mqtt-platform row, nothing retained on `homeassistant/#` or `mqtt_actions_export/#`). The retired fixture unique ids carry deleted-entity tombstones on BOTH instances: platform mqtt for `e51269d3-f6e2-4cad-998d-37579c3f7c8f`, `6f62cac5-49c9-49bc-88d5-1b804b775ac4` (both `disabled_by` integration) and `020b9715-2939-44bb-aafb-2340305e18d5` (null, the real twin tombstone) and for `e8a6edf6-45ba-43c8-b171-88ca668c31f2` (integration, an aborted attempt); `51c0db03-84d3-434a-b2d5-1ec4f110ff41` (an aborted attempt) left only `mqtt_actions` tombstones. Harmless: the unique ids are retired and never reused.
- Gap closure 08-13 and 08-18 (UAT-04 re-runs): `~/ha-test/_backup-pre-gap-rerun2-20261011T125246Z` (`a` and `b` with `core.device_registry`
  and `core.entity_registry`, mode 0700, taken with both instances stopped before the re-pin; pointer `~/ha-test/.current-backup-gap08-rerun2`)
  with the subfolder `reseed-20261011T131823Z` (the backup `reseed-tombstones.sh` took before it flipped `disabled_by` back to null on the four
  existing records of the Lampe Test switch and the Bar Select select). The marker was created again twice: `~/ha-test/.fixtures.env` holds the
  current `MARKER_ID` (ids only), `.fixtures.env.pre-08-13` and `.fixtures.env.pre-08-18` hold the earlier ones; the old markers leave harmless
  `mqtt_actions` and mqtt-platform tombstones. The host reboot found by plan 08-13 re-anchored `~/ha-test/.mosq-started-before-phase8`, the old
  value is kept as `.mosq-started-before-phase8.pre-reboot`. The platform-mqtt tombstones that the retired fixtures and the re-runs left in both
  entity registries are harmless; the records of Lampe Test and Bar Select are on purpose in the regression state (`disabled_by` null, see
  `uat-04-rerun2/prepare.txt`). A core-prefix export leaves disabled mqtt rows until the next restart; the last run ended with one restart of both
  instances, so none is left (export off, nothing retained under `mqtt_actions_export/` or `homeassistant/device/`). No `.current-backup-gap08-prune`
  and no prune backup exist (the disposition is guard-and-document). `check-uat03.sh` can leave a background `mosquitto_sub` running after the
  check (none runs now; the script was not changed).
- Helper scripts in `~/ha-test/bin/` (outside the repository; the scrubbed copy is `08-evidence/00-preflight/bench-scripts/`,
  plan 08-10, with a README that names the one scrub, the patches and additions of plans 08-11, 08-13 and 08-18 and the amended gate of plan
  08-15, and the files that were not copied). Added or patched by the gap closure: `check-uat04-iso.sh`, `repin.sh`, `repin-rerun2.sh`,
  `reseed-tombstones.sh`, the evidence suffix patch of `check-uat02.sh`, `check-uat03.sh`, `check-p15.sh`, `check-uat04.sh`, `setup-marker.sh`
  and `run-all-scripted.sh`, and `check-final.sh`; no `prune-mqtt-tombstones.sh` exists.
- Containers at the end of the phase (reconciled 2026-10-11, plan 08-15): `ha-a` and `ha-b` running (the read-only bind mount of the
  main checkout's `custom_components/mqtt_actions`, pinned to the receiver-guard build `b8232252540a55969145ca0034d8fd86b4be3b7c`,
  stale anchor empty; the earlier pins are kept in `08-evidence/00-preflight/build-caf2fe5d.txt` and `build-b7f52b34.txt`), `ha-c` stopped
  with exit code 0 (not removed), `mosq` running since the host reboot found by plan 08-13 (`~/ha-test/.mosq-started-before-phase8` holds
  the re-anchored StartedAt, the earlier value is kept in `.mosq-started-before-phase8.pre-reboot`; persistence is off, a restart would
  drop every retained message). Nothing is torn down by Phase 8; the removal commands below are for the owner afterwards.
- Backups (three, all under `~/ha-test`): `_backup-pre-phase8-20261004T184824Z` (a, b, mosquitto; pointer `.current-backup-phase8`;
  manifest and restore steps in `08-evidence/00-preflight/backup-manifest.txt`), `_backup-pre-p12-b-20261006T195117Z` (b only,
  ha-b before its hub was removed; pointer `.current-backup-p12`), and the older `_backup-pre-phase5-uat-20261003-181937` (a, b,
  mosquitto; Phase 5 UAT, pointer `.current-backup`), which predates Phase 8 and is left alone. No `_snap-pre-live` directory
  exists (none was taken). Remove them last, when nothing has to be restored any more. Gap closure backups: see the bullets below
  (`_backup-pre-gap-uat04-*` twice, `_backup-pre-gap-rerun2-*`); no `_backup-pre-gap-prune-*` exists.
- ACL copies before each edit: `~/ha-test/mosquitto/acl.bak-phase8-04`, `acl.bak-phase8-05`, `acl.bak-phase8-08` (and `acl.bak-uat`
  from Phase 5). The live `acl` ends with the blocks `ha_one`, `ha_two` (two availability write lines: the old and the new
  instance id of ha-b), `bridge`, `uat_probe`, `uat_bridge`, `ha_three`.
- Bench-only files with ids, no secrets: `~/ha-test/.instance-ids.env` (`INSTANCE_ID_B`), `.fixtures.env` (`MARKER_ID`),
  `.fixtures-frontend.env` (`P14_ID`, `P32A_ID`, `P32B_ID`, `P21_ID`, `LOOP_ID`, `P31_ID`; the devices are deleted, the ids stay for
  the cleanup gates). Secret-bearing files (mode 0600, never copied into the repository): `.mqtt-uat.env`, `.token-a`, `.token-b`,
  `.token-c`, `.ha-c-owner`, `.frontend-baseline.txt`.
- Devices and retained topics: the native devices Lampe Test, Bar Select and UAT Marker owned by ha-a with their mirrors on ha-b;
  the four orphan mirrors of the old ha-b owner id on ha-b (Baz, dfgfdgd, dfsfasdf, Modus Schlaf), whose retained config topics are
  still on the broker; the old id's retained availability reads `offline`; `homeassistant/#` and `mqtt_actions_export/#` hold
  nothing retained (export off). The throwaway devices of plans 08-06 to 08-08 (UAT P1-4, UAT Loop, UAT P3-1, the P3-2 pair) are
  deleted.
- Run leftovers in `~/ha-test`: `_uat02-run.out`, `_uat02-live.out` (console output of plan 08-02), `uat1-snapshot-before.json`,
  `d2.log`, `disc.log` (Phase 5), and `~/ha-test/v010` (the v0.1.0 checkout mounted read-only into ha-c).
- Removal commands for the owner, after the follow-up gap plan: `~/ha-test/bin/bench-users.sh remove` (uat_probe, uat_bridge);
  `mosquitto_passwd -D ~/ha-test/mosquitto/passwd ha_three`, delete the `user ha_three` block from the ACL, then
  `podman kill --signal HUP mosq`; `podman rm ha-c` and `rm -r ~/ha-test/c ~/ha-test/v010`; revoke the three tokens in the
  profile security pages of ha-a and ha-b (ha-c after a start, or drop it with the container) and `rm ~/ha-test/.token-a
  ~/ha-test/.token-b ~/ha-test/.token-c ~/ha-test/.ha-c-owner`; delete the `logger:` blocks from both `configuration.yaml` and
  restart ha-a and ha-b; remove the two `mqtt_actions_export/#` rows and the old-id availability line from the ACL and HUP mosq;
  delete the UAT Marker on ha-a (owner delete, clears its retained topics everywhere) and the four orphans on ha-b (empty retained
  publish on each `mqtt_actions/v1/devices/{id}/config` as uat_probe, then delete the device entries; the current UAT Marker is the
  id in `~/ha-test/.fixtures.env`); `rm ~/ha-test/.fixtures.env.pre-08-13 ~/ha-test/.fixtures.env.pre-08-18 ~/ha-test/.fixtures-gap.env
  ~/ha-test/.mosq-started-before-phase8.pre-reboot`; the backups and the pointer files last (`rm -r ~/ha-test/_backup-pre-gap-uat04-20261008T210459Z
  ~/ha-test/_backup-pre-gap-uat04-20261008T211551Z ~/ha-test/_backup-pre-gap-rerun2-20261011T125246Z`, `rm ~/ha-test/.current-backup-gap08
  ~/ha-test/.current-backup-gap08-rerun2`, then the three older backups and their pointers). The same list, without the ledger context, is
  `08-evidence/00-preflight/bench-state-final.txt`.

## Owner follow-ups

1. DECIDED: the UAT-04 gap (Gaps entry test: 4; clause 2, enabled core-prefix duplicates of Lampe Test and Bar Select after legacy
   twins). DECISION TAKEN (2026-10-10, plan 08-11, owner decision UAT04-GAP-DISPOSITION): guard-and-document with the full scripted
   re-run, UAT-01, P2-2 and the frontend items confirmed as not affected; the guard and the documentation are plans 08-12 to 08-15.
   Plan 08-16 extended the decision to the receiver (UAT04-RECEIVER-GUARD, extend-and-confirm). Decided and closed (plan 08-14,
   2026-10-11): UAT-04 was re-run on the receiver-guard build (plan 08-18) and passes; the Gaps entry is resolved.
2. Revoke the three long-lived tokens (ha-a and ha-b profile security pages; ha-c after a start, or drop it with the container)
   when the follow-up work is done, then delete the token files (owner decision API-ACCESS).
3. Tear down the bench state listed above when nothing has to be re-run any more (removal commands in the list above and in
   `bench-state-final.txt`); the three backups and their pointer files go last.
4. WR-03 live-republish duplicates (gone at the next start) stay an accepted known limit (owner decision WR03-LIVE-REPLAY): no
   action; recorded under Observations.
