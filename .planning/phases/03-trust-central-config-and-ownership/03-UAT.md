---
status: testing
phase: 03-trust-central-config-and-ownership
source: [03-VERIFICATION.md]
started: 2026-10-01T07:56:44Z
updated: 2026-10-01T07:56:44Z
---

## Current Test

number: 1
name: Approval dialog renders in a real Repairs frontend
expected: |
  The dialog renders device, owner, the YAML in one code block, the short hash, the startup flag sentence, the templated and residual lists and no injected markup; Submit approves, closing the dialog leaves the mirror paused
awaiting: user response

## Tests

### 1. Approval dialog renders in a real Repairs frontend
expected: Device, owner, YAML in one code block, short hash, startup sentence, templated/residual lists, no injected markup (use a name/owner/actions with backticks, underscores, pipes and a templated service name). Submit approves; closing leaves the mirror paused.
result: [pending]

### 2. Generic HA subentry delete dialog vs. the integration's own confirmation (SYN-06)
expected: The generic dialog cannot name other instances; after confirming, retained discovery/config/state are gone and the follower's mirror vanishes. The integration's own Delete menu step shows the all-instances text with the online count. User decides whether SYN-06 is met as written.
result: [pending]

### 3. Two real HA instances on one real Mosquitto with docs/broker-acl.md
expected: Device appears on B via core MQTT Discovery, B shows an approval request, A republishes discovery within the throttle window after B deletes the entity, after approval a toggle on either side runs the actions on both.
result: [pending]

### 4. Hub removal with the delete option on and off
expected: Option on: no retained config/discovery/state remains and followers drop their mirrors. Option off: everything stays retained, followers show orphans as unavailable.
result: [pending]

### 5. Lock scope in Manager.async_start (CR-02 fix, manager.py ~405-410)
expected: A slow broker may delay stop, reconnect republish and prune but cannot deadlock (re-review found no deadlock). Optional human look.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
