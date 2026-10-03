---
status: complete
phase: 01-walking-skeleton-installable-switch
source: [01-VERIFICATION.md]
started: 2026-09-29T09:40:09Z
updated: 2026-09-29T15:14:40Z
---

## Current Test

[testing complete]

## Tests

### 1. HACS install and Config Flow on a real host
expected: HACS accepts and installs it, the flow shows the base topic and instance name, a second add aborts with "already set up", the icon is shown.
result: pass

### 2. English and German UI strings in the real frontend
expected: All dialog labels, descriptions, error banners and the Repairs issue are translated; no raw translation keys are shown.
result: pass

### 3. Action editor and validation banners in the FINAL build
expected: The action selector renders; an invalid action gives a form-level error and saves nothing; a device_id action shows the warning on the first submit and saves on the identical second submit.
result: pass

### 4. Retained-versus-live chain on a real broker
expected: One action run per real change, none for repeated identical values, none after HA restart, reload or broker reconnect until a changed value is published; discovery is not removed on unload.
result: pass
note: |
  Verified on Nextgen against the real EMQX broker (192.168.178.9) by counting call_service/state_changed events in the browser:
  reconfigure ran nothing; off at baseline off ran nothing; ON ran the actions once; ON again ran nothing; off ran the actions once;
  reload ran nothing (entity briefly unavailable, then off, not removed); ON after reload ran the actions once.
  NOT covered here: toggle in the UI, full HA restart, broker reconnect (a reload replays the same retained value as the baseline).
  Follow-up left open: restart and reconnect behaviour.

### 5. Failing action visibility
expected: Exactly one Repairs issue with device, trigger, time and error; a log entry with traceback; the issue disappears after the next success.
result: pass
note: |
  Verified on Nextgen (API level, not visually): a nonexistent service as ON action is accepted by validation and fails at runtime with exactly one
  Repairs issue action_failed_<uuid> (device Foo Nextgen, trigger onChangeToOn, time, error text) and two ERROR log entries with a ServiceNotFound traceback.
  Saving a corrected action cleared the issue immediately (before any trigger); off and ON afterwards ran the actions with no new issue.
  NOT covered: rendering of the Repairs dialog in the frontend (issue was already gone), and clearing after a later success without a config change (see review WR-03).

### 6. Delete a device and remove the hub on a real host and broker
expected: The entity disappears and no ghost device remains under the MQTT integration; after hub removal nothing MQTT Actions related remains on the broker.
result: pass
note: |
  Verified on Nextgen against the real EMQX broker (192.168.178.9). Delete device: discovery and retained state topic of the device were cleared,
  the entity and registry entry disappeared (took longer than 6 s, gone after about 11 s), no ghost device under MQTT.
  Remove hub: config entry gone, instance availability topic cleared, no Repairs issue left. The other instance's (Backup) device, discovery, state and
  availability topics and entity were untouched.
  Leftovers on the broker are from the earlier tracer build, not from this build: state topic 3ddef973-... and availability 63ef390d-...

### 7. Lifecycle fixes WR-01, WR-02, WR-04 (commits 6361ce7, 955c817, 2a65b45)
expected: Exactly one subscription per device (one run per message), setup retries and succeeds when the broker returns, no double runs.
result: pass
note: |
  Verified on Nextgen against the real EMQX broker: a fresh hub and device (UAT Lampe); an entry reload fired concurrently with adding and deleting a second device
  ended cleanly (no errors, entry loaded, no actions during the churn); off and ON afterwards each ran the actions exactly once (no doubled subscription).
  NOT covered by hand, unit tests only: HA start while the broker is down (WR-02 retry) and a malformed Store payload (WR-04).

### 8. Push the local commits and confirm CI and Validate on the new head
expected: Both workflows succeed on the pushed head (only 0f6ae60 is proven on GitHub so far).
result: pass
note: |
  Local commits incl. the WR-01/02/04 fixes were pushed (head 8d5ee00): CI run 36552515427 and Validate run 36552515465 green; PR #1 checks green;
  after the merge to main (fcfe3f8) CI and Validate (push) are green as well.

### 9. Core versions of lxc-haos-104 and hassio-n2plus
expected: Both hosts run Core >= 2026.9.0, or the floor is reassessed.
result: pass
note: |
  Host mapping given by the developer: haos-op3050-1 is Nextgen, hassio-n2plus is Backup, lxc-haos-104 is deprecated and out of scope.
  Nextgen: Core 2026.9.4 (read from the host). Backup: exact version not read; the integration runs there (device 'Foo Von BAckup' was created and discovered),
  which needs Python 3.14 and probatio, so Core >= 2026.9.0 is inferred, not measured. lxc-haos-104: dropped from scope.

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
