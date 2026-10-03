---
status: testing
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
source: [05-VERIFICATION.md]
started: 2026-10-03T13:38:23Z
updated: 2026-10-03T17:45:43Z
---

## Current Test

number: 7
name: Discovery export on/off and homeassistant prefix
expected: |
  enabled_by_default false, no buttons; core prefix yields only disabled duplicates; off clears topics
awaiting: user response

## Tests

### 1. Upgrade path on a real 0.1.0 instance (ha-one)
expected: Entity ids, registry ids, device ids, area, name and history intact; no retained discovery topic left
result: pass
note: fresh 0.1.0 -> 0.2.0 run on ha-a/ha-b; registry ids, entity ids, names, areas kept; discovery topics cleared; mode selects moved to the main device by design

### 2. Integration page counting (A1) on the follower
expected: All devices and entities of the other instance appear, owner named in the model text, counts match
result: pass

### 3. Mixed fleet and live follower cutover (A5)
expected: native_cutover_waiting names the v0.1.0 instance; after its update both switch, follower reloads on its own
result: pass
note: accepted by the user without a reproduction on ha-a/ha-b (mixed fleet not rebuilt); covered by automated tests with a fake broker (test_cutover_instances.py), not observed on real instances

### 4. Straggler v0.1.0 instance after cutover
expected: Keeps running actions, shows no entities for migrated devices, raises no error
result: skipped
reason: user skipped; needs a real mixed fleet (0.1.0 next to a native instance), not rebuilt

### 5. Late replay race (A4)
expected: Re-published legacy retained discovery plus two restarts yields no _2 duplicates (see IN-03)
result: skipped
reason: user skipped; IN-03 stays open

### 6. Commands across two real instances
expected: Actions run exactly once on every approved instance; unknown payload ignored, state unchanged
result: skipped
reason: user skipped; will be tested on the production instances

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
passed: 3
issues: 0
pending: 3
skipped: 3
blocked: 0

## Gaps
