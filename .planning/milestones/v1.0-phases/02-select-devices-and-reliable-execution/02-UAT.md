---
status: complete
phase: 02-select-devices-and-reliable-execution
source: [02-VERIFICATION.md]
started: 2026-09-29T20:12:19Z
updated: 2026-09-30T21:25:17Z
---

## Current Test

[testing complete]

## Tests

### 1. Create a Select device in the real HA UI
expected: Menu loop and action editor render; EN and DE labels correct.
result: pass

### 2. Select round trip against a real broker
expected: Choosing an option in the UI publishes its StateValue; mosquitto_pub with varied case and whitespace runs the matching option once; an unknown payload is ignored.
result: pass

### 3. Reconfigure and option lifecycle
expected: StateValue is locked, a renamed option keeps its button unique_id, a removed option's button disappears, the select shows unknown until the next valid payload.
result: pass

### 4. Run modes with real delay actions
expected: restart cancels the first run silently; serial completes both runs in order.
result: pass

### 5. Circuit breaker end to end
expected: A self-flipping loop trips the breaker; EN/DE Repairs text renders; a reconfigure or reload releases it; the test button works while paused; the paused state survives an HA restart.
result: pass

### 6. Test buttons in the UI
expected: A press changes no state and publishes nothing to the state topic; a failing action creates the Repairs issue; buttons are listed under Configuration.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

## Deferred Follow-Ups

- test: 1
  idea: "Der Flow gefällt mir nicht, den müssen wir nochmal anfassen (Select-Anlage: mit nur einer Option ist 'Gerät speichern' im Menü nicht sichtbar, Details offen)"
  deferred_at: 2026-09-29
