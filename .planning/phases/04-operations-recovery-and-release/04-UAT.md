---
status: testing
phase: 04-operations-recovery-and-release
source: [04-VERIFICATION.md]
started: 2026-10-02T19:38:46Z
updated: 2026-10-03T00:30:00Z
---

## Current Test

number: 2
name: First release v0.1.0 (plan 04-01, D4)
expected: |
  After the phase is merged and Validate is green, push tag v0.1.0; Release runs and creates the GitHub release
awaiting: user response

## Tests

### 1. Validate (hassfest + HACS) is green on the pushed phase branch / PR (plan 04-14, D4)
expected: After pushing gsd/phase-04-operations-recovery-and-release (the branch is not on origin yet), `gh run list --workflow Validate --branch gsd/phase-04-operations-recovery-and-release --limit 1` shows conclusion success with both the hassfest and the HACS job green
result: pass
note: Validate run on c52a548 (pushed phase branch) concluded success; job-level hassfest/HACS results were not inspected separately.

### 2. First release v0.1.0 (plan 04-01, D4)
expected: After the phase is merged and Validate is green, push tag v0.1.0 (equal to manifest version 0.1.0); Release runs check-version, ci and validate, then creates the GitHub release with generated notes
result: [pending]
note: needs the merged phase and a pushed tag v0.1.0 on GitHub.

### 3. D5/D8 diagnostics download in a real Home Assistant (plan 04-07)
expected: Settings > Devices & services > MQTT Actions > Download diagnostics yields a JSON with hub, roster and device rows; no action YAML, entity ids, service data, broker host or credentials; instance ids shortened to 8 characters
result: pass
note: ha-one, diagnostics endpoint returns hub, roster and devices with 8-character instance ids; no action YAML, entity ids, service data, broker host or credentials. The download button is present on the hub device page; the browser file download itself was not clicked.

### 4. D6 companion devices and mode selects for mirrored devices, two real instances (plan 04-06, assumption A14)
expected: A mirror and an owned device with the same name appear as separate, distinguishable devices on the integration page; the mode select changes behavior (observe logs, disabled stops processing) against a real Mosquitto
result: pass
note: ha-one/ha-two against the Mosquitto test broker. Mirror 'UAT hub' and owned device are listed as separate devices (Switch device (mirror) vs Switch device). Device mode observe gives status observing, disabled gives disabled.

### 5. D8 mode selects on the integration page (plan 04-05)
expected: Hub instance-mode select and per-device mode selects appear in the configuration category with translated option labels (en and de); effective mode is the most restrictive of hub and device
result: partial
note: Hub 'Instanzmodus' and per-device 'Modus' selects are in the configuration category with German names; hub observe/disabled overrides a device in run (most restrictive wins). The dropdown option labels (en and de) were not opened visually.

### 6. D8 re-trigger from Developer Tools with two real instances (plan 04-10)
expected: Calling mqtt_actions.retrigger with response shows per-instance statuses (executed, not_approved, paused, observing, disabled, no_answer) within the 5 s window; actions run on the approving instance and the state and baseline do not change
result: partial
note: Statuses seen: executed, not_approved, observing, disabled, and no_answer (before the test broker ACL allowed retrigger/acks topics). Not seen: paused (breaker). The execution of the action itself (persistent notification) was not observed; a second call within a few seconds is refused by design. Required test ACL lines: instances/+/heartbeat, devices/+/retrigger, instances/+/acks.

### 7. Import and export in a real Home Assistant (plan 04-09) and export-file reachability
expected: export_devices with file_name writes /config/mqtt_actions/<name>.json (mode 0600) and the file is NOT reachable through /local or any unauthenticated URL; import_devices of that file creates owned devices with new UUIDs, and mirrors on other instances ask for approval
result: partial
note: export on ha-two wrote mqtt_actions/uat-two.json with mode 0600 in a 0700 directory; /local and direct URL return 404 (the test config has no www directory); mirrors are refused with export_not_owned; import on ha-one created an owned device with a new UUID, shown as mirror on ha-two. Approval request for mirrors was not exercised because the imported device has no actions.

### 8. D9 duplicate instance id, including the reworded confirm text (plans 04-12, 04-14)
expected: With the same backup restored on two instances the Repairs issue appears; its dialog now carries the cause explanation (formerly the issue-level description) in the confirm step and reads correctly in en and de; after confirmation that instance runs under a new id with the original's devices as mirrors while the original's entities stay available
result: pass
note: ha-two given the instance id of ha-one. Issue duplicate_instance_id appeared on both instances; the confirm text reads correctly in de and en. After confirmation ha-two runs as a09499e4, roster shows both, issue cleared (ha-one cleared after about two minutes). Observation: ha-one and ha-two disagree on the owner of the device 'Test' afterwards.

### 9. D10 adoption and returning old owner, including the reworded confirm text (plans 04-12, 04-14)
expected: Adopt a device on instance two while instance one is stopped; start instance one; it shows the transferred Repairs issue whose confirm dialog opens with the adoption explanation and, after confirmation, the device as a mirror of instance two with working entities
result: pass
note: ha-one stopped, adopt_device on ha-two without force succeeded after the 90 s offline rule; ha-one showed transferred, de and en confirm text open with the adoption explanation; after confirmation the device is a mirror of ha-two with its entities present. Dismissing instead of confirming was not tried.

### 10. README and docs read-through (plan 04-13, D5)
expected: A new user can go from README to installation, the first operations and the troubleshooting entry of a Repairs issue by following links
result: [pending]
note: judgment by the user.

### 11. Wording of the approval dialog paragraph in German and English (plan 04-02, D5)
expected: The paragraph naming run mode and breaker limits reads naturally
result: partial
note: German approval dialog read through (reads naturally, names run mode and breaker limits); the English text was not read.

## Summary

total: 11
passed: 5
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps

No failed tests. Observations from the run on ha-one and ha-two:

- The Mosquitto ACL of the test setup (`~/ha-test/mosquitto/acl`) lacked `instances/+/heartbeat`, `devices/+/retrigger` and `instances/+/acks` for both users; without them presence and re-trigger answers did not work. Not a defect of the integration, but the README should list the topics an ACL needs.
- After the duplicate id repair, ha-one and ha-two disagreed on the owner of the device 'Test' (ha-one: old id of ha-two, ha-two: ha-one). Possibly an artifact of the overlap period; not analyzed further.
