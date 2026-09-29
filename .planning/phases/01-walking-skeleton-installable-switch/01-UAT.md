---
status: testing
phase: 01-walking-skeleton-installable-switch
source: [01-VERIFICATION.md]
started: 2026-09-29T09:40:09Z
updated: 2026-09-29T09:40:09Z
---

## Current Test

number: 1
name: HACS install and Config Flow on a real host
expected: |
  HACS accepts and installs the repository as a custom repository (category Integration). The flow shows the base topic (default mqtt_actions) and the instance name, a second add aborts with "already set up", and the icon is shown.
awaiting: user response

## Tests

### 1. HACS install and Config Flow on a real host
expected: HACS accepts and installs it, the flow shows the base topic and instance name, a second add aborts with "already set up", the icon is shown.
result: [pending]

### 2. English and German UI strings in the real frontend
expected: All dialog labels, descriptions, error banners and the Repairs issue are translated; no raw translation keys are shown.
result: [pending]

### 3. Action editor and validation banners in the FINAL build
expected: The action selector renders; an invalid action gives a form-level error and saves nothing; a device_id action shows the warning on the first submit and saves on the identical second submit.
result: [pending]

### 4. Retained-versus-live chain on a real broker
expected: One action run per real change, none for repeated identical values, none after HA restart, reload or broker reconnect until a changed value is published; discovery is not removed on unload.
result: [pending]

### 5. Failing action visibility
expected: Exactly one Repairs issue with device, trigger, time and error; a log entry with traceback; the issue disappears after the next success.
result: [pending]

### 6. Delete a device and remove the hub on a real host and broker
expected: The entity disappears and no ghost device remains under the MQTT integration; after hub removal nothing MQTT Actions related remains on the broker.
result: [pending]

### 7. Lifecycle fixes WR-01, WR-02, WR-04 (commits 6361ce7, 955c817, 2a65b45)
expected: Exactly one subscription per device (one run per message), setup retries and succeeds when the broker returns, no double runs.
result: [pending]

### 8. Push the local commits and confirm CI and Validate on the new head
expected: Both workflows succeed on the pushed head (only 0f6ae60 is proven on GitHub so far).
result: [pending]

### 9. Core versions of lxc-haos-104 and hassio-n2plus
expected: Both hosts run Core >= 2026.9.0, or the floor is reassessed.
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps
