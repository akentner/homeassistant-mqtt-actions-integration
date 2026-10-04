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
| UAT-01 | UAT-01, ROADMAP criterion 1, 05-UAT test 4 | pending | - | - | - |
| UAT-02 | UAT-02, ROADMAP criterion 2, 05-UAT test 5 | pass | 2026-10-04 | b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 | .planning/phases/08-real-instance-verification/08-evidence/uat-02 |
| UAT-03 | UAT-03, ROADMAP criterion 3, 05-UAT test 6 | pending | - | - | - |
| UAT-04 | UAT-04, ROADMAP criterion 4, 05-UAT test 7 | pending | - | - | - |
| P1-1 | Phase 1 item 1 (07-PROOF) | pending | - | - | - |
| P1-2 | Phase 1 item 2 (07-PROOF) | pending | - | - | - |
| P1-3 | Phase 1 item 3 (07-PROOF) | pending | - | - | - |
| P1-4 | Phase 1 item 4 (07-PROOF) | pending | - | - | - |
| P1-5 | Phase 1 item 5 (07-PROOF) | pending | - | - | - |
| P1-6 | Phase 1 item 6 (07-PROOF) | pending | - | - | - |
| P2-1 | Phase 2 item 1 (07-PROOF) | pending | - | - | - |
| P2-2 | Phase 2 item 2 (07-PROOF) | pending | - | - | - |
| P3-1 | Phase 3 item 1 (07-PROOF) | pending | - | - | - |
| P3-2 | Phase 3 item 2 (07-PROOF) | pending | - | - | - |

Allowed result tokens: pending, pass, issue, blocked. `skipped` is not allowed because D-07 waives nothing. An owner override of a
failed item stays `result: issue` plus an `override_by:` line with the owner's own name. A recorded block carries `sha:` (40 hex),
`date:` (ISO date), `evidence:` (a folder under 08-evidence) and `note:` after `result:`; an issue also carries `reported:` and
`severity:`. The recorder gate is `~/ha-test/bin/check-recorded.sh {check id}`.

## Tests

### 1. UAT-01: straggler v0.1.0 instance
expected: A v0.1.0 instance (ha-c) next to the native instances keeps running its actions for the migrated devices, shows no switch, select or button entities for them and raises no error; the pass wording for the companion mode selects is fixed by the owner decision of plan 08-05.
result: pending

### 2. UAT-02: late legacy Discovery replay, two starts (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
date: 2026-10-04
evidence: .planning/phases/08-real-instance-verification/08-evidence/uat-02
note: Two startup rounds with retained legacy Discovery published while ha-a and ha-b were stopped; after each graceful stop both registries held no `mqtt` row, no `_2` id, no legacy `mqtt` device and the 30 `mqtt_actions` rows (entity id, registry id, unique id, device id) identical to the baseline (E1 to E4). The replay really created the twins (six `_2` tombstones per instance in `deleted_entities`) and they were removed. Live variant (observation only): published while running, six `_2` entities appeared on both instances within 20 s, stayed through a graceful stop, and were gone after the next start.

### 3. UAT-03: command across two real instances
expected: A command issued on one of two real instances runs the actions exactly once on every approved instance, and an unknown payload is ignored and leaves the state unchanged.
result: pending

### 4. UAT-04: Discovery export and core prefix
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: pending

### 5. P1-1: HACS client install on a production host
expected: On a real host: custom repository added, integration downloaded, Home Assistant restarted, MQTT Actions added, a second add aborts, the icon is shown; then the integration and the repository are removed again (add and remove only, no device created).
result: pending

### 6. P1-2: English and German strings
expected: The hub flow, the Add switch device dialog and the Repairs text render correctly in the real frontend in English and in German.
result: pending

### 7. P1-3: action editor and validation banners
expected: The action editor works in the current build; an invalid YAML action is rejected with a banner, and a literal `device_id` submitted twice warns the first time and saves on the resubmit.
result: pending

### 8. P1-4: Repairs dialog of a failing action
expected: A failing action of an owned device creates a Repairs issue whose dialog renders correctly in the real frontend.
result: pending

### 9. P1-5: retained-versus-live chain
expected: On the current build with a real HA core MQTT client and a real retaining broker (toggle in the UI, full HA restart, broker reconnect), no action runs for replayed state.
result: pending

### 10. P1-6: core version of hassio-n2plus
expected: The core version of the second real host (hassio-n2plus, "Backup"), read in Settings > About, is 2026.9.0 or newer (informational, no code consequence).
result: pending

### 11. P2-1: select subentry flow
expected: In the real frontend: add a select device, enter three options, Done after two, reconfigure with edit, add and remove, in English and in German.
result: pending

### 12. P2-2: breaker loop
expected: A device whose action flips its own state topic trips the breaker (5 runs in 10 seconds) against a real Mosquitto and a real HA process; the Repairs card renders in English and German; release by reconfigure or reload works; a restart while paused stays paused.
result: pending

### 13. P3-1: approval request rendering
expected: The approval request of a mirrored device in Settings > Repairs renders a device name, owner name and action YAML with backticks, underscores, pipes and a templated service name as plain text in the real frontend.
result: pending

### 14. P3-2: delete dialogs
expected: Deleting a device whose name contains backticks and `<b>` shows the name as plain text in the integration's own delete step and in the generic core dialog (whose text an integration cannot change; documented limitation in the README).
result: pending

## Summary

total: 14
passed: 1
issues: 0
pending: 13
skipped: 0
blocked: 0

## Gaps

<!-- Replace the empty list with entries in the gap format of ~/.claude/gsd-core/templates/UAT.md when a check fails (D-08):
     one entry per failed block, with `test:` set to the block number. -->
[]

## Observations

Non-gap facts recorded while running the checks (companion mode selects of v0.1.0, the live-republish duplicate, the cleanup at the
next start after a core-prefix export, the release HACS reports).

- Mapping: 05-UAT tests 4, 5, 6, 7 are UAT-01, UAT-02, UAT-03, UAT-04.
- Live-republish (WR-03, plan 08-02): with legacy Discovery published while ha-a and ha-b were running, six `mqtt`-platform `_2` entities appeared on each instance within 20 s, stayed through 45 s and a graceful stop, and were gone after the next start (see `08-evidence/uat-02/live-variant.txt`). Classified by the owner as an accepted known limit (`WR03-LIVE-REPLAY`): it stays documented, there is no Gaps entry, and UAT-02's own result (startup replay) is unchanged.
- Catch asymmetry (plan 08-02): in the startup rounds ha-b logged the INFO line "Removed 3 duplicate entities…" while ha-a logged none, although both registries ended clean and both hold six `_2` tombstones; the path that cleaned ha-a is not identified (evidence: `08-evidence/uat-02/log-a.txt`, `twin-tombstones.txt`).

## Owner decisions

| Decision id | Option | Date |
|-------------|--------|------|
| API-ACCESS | owner-tokens (token a ok, token b ok; files mode 0600 in ~/ha-test, outside the repo; revoke after the phase) | 2026-10-04 |
| WR03-LIVE-REPLAY | accepted-limit (no reason given; relayed to the executor by the orchestrator from the owner's chat answer) | 2026-10-04 |

## Bench state left behind

Recorded so nothing is forgotten when the phase ends (T-08-04). All of it is on the test bench in `~/ha-test`; the production
broker and hosts are untouched.

- Broker users `uat_probe` (read and write `#`) and `uat_bridge` (state topics only) with random passwords in `~/ha-test/.mqtt-uat.env`
  (mode 0600). Removal: `~/ha-test/bin/bench-users.sh remove`.
- An INFO `logger` block for `custom_components.mqtt_actions` in the `configuration.yaml` of ha-a and ha-b.
- Backup of the instances and the broker configuration taken before the first restart (path in `08-evidence/00-preflight/backup-manifest.txt`).
- Long-lived tokens `~/ha-test/.token-a` and `~/ha-test/.token-b` (mode 0600, owner decision API-ACCESS). The owner revokes them in the
  two profile security pages after the phase.
- Helper scripts in `~/ha-test/bin/` (outside the repository; a scrubbed copy is added to the evidence by plan 08-10).
