---
status: testing
phase: 11-local-actions-on-mirrors
source: [11-VERIFICATION.md]
started: 2026-10-21T10:45:00Z
updated: 2026-10-21T10:45:00Z
---

## Current Test

number: 1
name: Render the real hub options flow on the bench in en and de
expected: |
  Every step renders with translated titles, descriptions, menu options and selector labels (no raw keys)
  in both languages; save returns to the trigger picker and the change applies without restart; the mute
  and remove confirmations are distinct and readable
awaiting: user response

## Tests

### 1. Render the real hub options flow on the bench in en and de
Path (Core 2026.9.4, frontend 20260826.7): Settings > Integrations > MQTT Actions > Configure > menu 'init' >
local actions > device picker (mirrors plus orphan-only devices) > trigger picker (status markers
additive/replacement/muted/orphan/other kind) > editor (expanded section, mode select, ActionSelector) > save;
then mute confirmation and remove confirmation; then the Settings step with the local-action device count.
expected: Every step renders with translated titles, descriptions, menu options and selector labels (no raw keys) in both languages; save returns to the trigger picker and the change applies without restart; the mute and remove confirmations are distinct and readable
result: [pending]

### 2. Review judgment-tier prohibition 11-03
'MUST NOT make local replacement or trusted-local execution confer approval on owner actions or make an
unapproved mirror adoptable'
expected: Holds. Verifier evidence (non-authoritative): approval_state() never reads local records (manager.py:2004-2027); build_effective_trigger_plan gates owner on approval == approved AND not replaced (local_actions.py:322-323); async_adopt_device refuses PENDING/BLOCKED (manager.py:1446-1447); covering tests pass
result: [pending]

### 3. Review judgment-tier prohibition 11-08
'MUST NOT present empty replacement as deletion/owner-only behavior or imply that local replacement approves
owner actions'
expected: Holds. Verifier evidence (non-authoritative): options.step.local_actions_confirm_mute (en/de) says the trigger runs neither owner nor local actions, that muting neither approves nor rejects, and that muting is not removal; local_actions_confirm_remove says removal restores owner actions only while approved; edit data_description says local actions never approve owner actions
result: [pending]

### 4. Review judgment-tier prohibition 11-12
'MUST NOT claim that the real v1.1 to v1.0.1 to v1.1 downgrade round trip or Phase 12 final-build verification
has been performed'
expected: Holds. Verifier evidence (non-authoritative): README 'Downgrading to 1.0.1' states the round trip has not been verified on real instances and is deferred (MIR-F4); 11-release-notes.md is labeled 'Unpublished draft' and says the round trip is deferred as MIR-F4 and has not been run
result: [pending]

### 5. Decide the four open code-review warnings (11-REVIEW-DISPOSITION.md)
- WR-01: a stray empty config payload discards local records permanently
- WR-02: local_action_failed cannot clear after the user mutes the trigger or empties its additive actions
- WR-03: a JSON-corrupt or wrong-shape local Store loads as empty without local_actions_unreadable
- WR-04: the hub-removal warning says 0 devices when the local Store is unreadable
expected: Owner records accept or fix for each (fix = inserted Phase 11.x gap plan before Phase 12 starts, because Phase 12 allows no product changes). Verifier assessment: none defeats a ROADMAP success criterion or a plan must-have as written
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
