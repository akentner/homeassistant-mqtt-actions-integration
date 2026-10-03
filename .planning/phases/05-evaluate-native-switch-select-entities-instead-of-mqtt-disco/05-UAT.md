---
status: testing
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
source: [05-VERIFICATION.md]
started: 2026-10-03T13:38:23Z
updated: 2026-10-03T13:38:23Z
---

## Current Test

number: 1
name: Upgrade path on a real 0.1.0 instance (ha-one)
expected: |
  Entity ids, registry ids and device ids unchanged; area and name kept; recorder history continuous;
  entities listed on the MQTT Actions integration page; no retained discovery topic left for the device
awaiting: user response

## Tests

### 1. Upgrade path on a real 0.1.0 instance (ha-one)
expected: Entity ids, registry ids, device ids, area, name and history intact; no retained discovery topic left
result: [pending]

### 2. Integration page counting (A1) on the follower
expected: All devices and entities of the other instance appear, owner named in the model text, counts match
result: [pending]

### 3. Mixed fleet and live follower cutover (A5)
expected: native_cutover_waiting names the v0.1.0 instance; after its update both switch, follower reloads on its own
result: [pending]

### 4. Straggler v0.1.0 instance after cutover
expected: Keeps running actions, shows no entities for migrated devices, raises no error
result: [pending]

### 5. Late replay race (A4)
expected: Re-published legacy retained discovery plus two restarts yields no _2 duplicates (see IN-03)
result: [pending]

### 6. Commands across two real instances
expected: Actions run exactly once on every approved instance; unknown payload ignored, state unchanged
result: [pending]

### 7. Discovery export on/off and homeassistant prefix
expected: enabled_by_default false, no buttons; core prefix yields only disabled duplicates; off clears topics
result: [pending]

### 8. Device delete and integration removal
expected: Device and entities disappear; retained document, state and discovery topics cleared per options
result: [pending]

### 9. Owner decision on open review items WR-03 (partial), IN-02, IN-03
expected: Accept for 0.2.0 (documented) or schedule a follow-up
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps
