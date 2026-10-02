---
status: testing
phase: 04-operations-recovery-and-release
source: [04-VERIFICATION.md]
started: 2026-10-02T19:38:46Z
updated: 2026-10-02T19:38:46Z
---

## Current Test

number: 1
name: Validate (hassfest + HACS) is green on the pushed phase branch / PR (plan 04-14, D4)
expected: |
  After pushing gsd/phase-04-operations-recovery-and-release (the branch is not on origin yet), `gh run list --workflow Validate --branch gsd/phase-04-operations-recovery-and-release --limit 1` shows conclusion success with both the hassfest and the HACS job green
awaiting: user response

## Tests

### 1. Validate (hassfest + HACS) is green on the pushed phase branch / PR (plan 04-14, D4)
expected: After pushing gsd/phase-04-operations-recovery-and-release (the branch is not on origin yet), `gh run list --workflow Validate --branch gsd/phase-04-operations-recovery-and-release --limit 1` shows conclusion success with both the hassfest and the HACS job green
result: [pending]

### 2. First release v0.1.0 (plan 04-01, D4)
expected: After the phase is merged and Validate is green, push tag v0.1.0 (equal to manifest version 0.1.0); Release runs check-version, ci and validate, then creates the GitHub release with generated notes
result: [pending]

### 3. D5/D8 diagnostics download in a real Home Assistant (plan 04-07)
expected: Settings > Devices & services > MQTT Actions > Download diagnostics yields a JSON with hub, roster and device rows; no action YAML, entity ids, service data, broker host or credentials; instance ids shortened to 8 characters
result: [pending]

### 4. D6 companion devices and mode selects for mirrored devices, two real instances (plan 04-06, assumption A14)
expected: A mirror and an owned device with the same name appear as separate, distinguishable devices on the integration page; the mode select changes behavior (observe logs, disabled stops processing) against a real Mosquitto
result: [pending]

### 5. D8 mode selects on the integration page (plan 04-05)
expected: Hub instance-mode select and per-device mode selects appear in the configuration category with translated option labels (en and de); effective mode is the most restrictive of hub and device
result: [pending]

### 6. D8 re-trigger from Developer Tools with two real instances (plan 04-10)
expected: Calling mqtt_actions.retrigger with response shows per-instance statuses (executed, not_approved, paused, observing, disabled, no_answer) within the 5 s window; actions run on the approving instance and the state and baseline do not change
result: [pending]

### 7. Import and export in a real Home Assistant (plan 04-09) and export-file reachability
expected: export_devices with file_name writes /config/mqtt_actions/<name>.json (mode 0600) and the file is NOT reachable through /local or any unauthenticated URL; import_devices of that file creates owned devices with new UUIDs, and mirrors on other instances ask for approval
result: [pending]

### 8. D9 duplicate instance id, including the reworded confirm text (plans 04-12, 04-14)
expected: With the same backup restored on two instances the Repairs issue appears; its dialog now carries the cause explanation (formerly the issue-level description) in the confirm step and reads correctly in en and de; after confirmation that instance runs under a new id with the original's devices as mirrors while the original's entities stay available
result: [pending]

### 9. D10 adoption and returning old owner, including the reworded confirm text (plans 04-12, 04-14)
expected: Adopt a device on instance two while instance one is stopped; start instance one; it shows the transferred Repairs issue whose confirm dialog opens with the adoption explanation and, after confirmation, the device as a mirror of instance two with working entities
result: [pending]

### 10. README and docs read-through (plan 04-13, D5)
expected: A new user can go from README to installation, the first operations and the troubleshooting entry of a Repairs issue by following links
result: [pending]

### 11. Wording of the approval dialog paragraph in German and English (plan 04-02, D5)
expected: The paragraph naming run mode and breaker limits reads naturally
result: [pending]

## Summary

total: 11
passed: 0
issues: 0
pending: 11
skipped: 0
blocked: 0

## Gaps
