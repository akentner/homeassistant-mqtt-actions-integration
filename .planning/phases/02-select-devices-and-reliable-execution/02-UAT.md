---
status: testing
phase: 02-select-devices-and-reliable-execution
source: [02-VERIFICATION.md]
started: 2026-09-29T18:59:44Z
updated: 2026-09-29T18:59:44Z
---

## Current Test

number: 1
name: Create a Select device in the real HA UI
expected: |
  The menu loop (settings, add, edit, remove, done) and the action editor in the option steps render and work; English and German labels are shown.
awaiting: user response

## Tests

### 1. Create a Select device in the real HA UI
expected: Menu loop and action editor render; EN and DE labels correct.
result: [pending]

### 2. Select round trip against a real broker
expected: Choosing an option in the UI publishes its StateValue; mosquitto_pub with varied case and whitespace runs the matching option once; an unknown payload is ignored.
result: [pending]

### 3. Reconfigure and option lifecycle
expected: StateValue is locked, a renamed option keeps its button unique_id, a removed option's button disappears, the select shows unknown until the next valid payload.
result: [pending]

### 4. Run modes with real delay actions
expected: restart cancels the first run silently; serial completes both runs in order.
result: [pending]

### 5. Circuit breaker end to end
expected: A self-flipping loop trips the breaker; EN/DE Repairs text renders; a reconfigure or reload releases it; the test button works while paused; the paused state survives an HA restart.
result: [pending]

### 6. Test buttons in the UI
expected: A press changes no state and publishes nothing to the state topic; a failing action creates the Repairs issue; buttons are listed under Configuration.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
