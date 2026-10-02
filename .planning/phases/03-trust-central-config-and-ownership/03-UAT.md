---
status: complete
phase: 03-trust-central-config-and-ownership
source: [03-VERIFICATION.md]
started: 2026-10-01T07:56:44Z
updated: 2026-10-02T01:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Approval dialog renders in a real Repairs frontend
expected: Device, owner, YAML in one code block, short hash, startup sentence, templated/residual lists, no injected markup (use a name/owner/actions with backticks, underscores, pipes and a templated service name). Submit approves; closing leaves the mirror paused.
result: pass
source: automated (chrome-devtools against a real HA 2026.9 frontend), confirmed by user

### 2. Generic HA subentry delete dialog vs. the integration's own confirmation (SYN-06)
expected: The generic dialog cannot name other instances; after confirming, retained discovery/config/state are gone and the follower's mirror vanishes. The integration's own Delete menu step shows the all-instances text with the online count. User decides whether SYN-06 is met as written.
result: pass
previous_result: issue
previous_reported: "Generic dialog says only 'Zugehörige Geräte und Entitäten werden dauerhaft gelöscht.' (as expected). The integration's own dialog names all instances and the online count (1), and after confirming config/discovery/state are gone and the mirror vanished on the follower. But the device name is rendered as Markdown/HTML in that dialog: backticks become <code> and <b>fett</b> becomes a real <b> element (name 'UAT `bt` a_b_c | <b>fett</b>')."
retested: 2026-10-02 after gap-closure plan 03-08 (G-03-2); real HA frontend on ha-a, the delete dialog shows the name as plain text (0 code, 0 injected elements)

### 3. Two real HA instances on one real Mosquitto with docs/broker-acl.md
expected: Device appears on B via core MQTT Discovery, B shows an approval request, A republishes discovery within the throttle window after B deletes the entity, after approval a toggle on either side runs the actions on both.
result: pass
source: automated (two HA containers, Mosquitto with allow_anonymous false and the ACL from docs/broker-acl.md); discovery republished 13 s after the delete

### 4. Hub removal with the delete option on and off
expected: Option on: no retained config/discovery/state remains and followers drop their mirrors. Option off: everything stays retained, followers show orphans as unavailable.
result: pass
source: automated

### 5. Lock scope in Manager.async_start (CR-02 fix, manager.py ~405-410)
expected: A slow broker may delay stop, reconnect republish and prune but cannot deadlock (re-review found no deadlock). Optional human look.
result: pass
source: code read plus several real restarts and reloads with retained documents on the broker

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-03-2
  truth: "The integration's own delete confirmation shows the device name as plain text"
  status: resolved
  resolved_by: 03-08-PLAN.md
  resolved_at: 2026-10-02
  reason: "User reported: the name is rendered as Markdown/HTML in the delete dialog (backticks become <code>, <b> becomes a real element)"
  severity: minor
  test: 2
  root_cause: "config_flow.py passes the raw subentry title as the `name` description placeholder of the delete_device menu (line ~211) without escape_markdown; the same raw pattern is used for `name` in the select option menu (~450) and `friendly_name`/`state_value` in remove_confirm (~593). The approval dialog and the sync issues already use document.escape_markdown."
  artifacts:
    - path: "custom_components/mqtt_actions/config_flow.py"
      issue: "raw user text in description_placeholders of delete_device, menu and remove_confirm steps"
  missing:
    - "Pass the name (and friendly_name/state_value) through escape_markdown in those placeholders"
    - "A regression test that asserts the placeholders are escaped for a name with backticks, underscores, pipes and <b>"
  debug_session: ""
