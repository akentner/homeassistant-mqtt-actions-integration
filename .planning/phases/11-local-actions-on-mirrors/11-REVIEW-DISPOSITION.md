---
phase: 11
review: 11-REVIEW.md
titles: json
findings:
  - id: WR-05
    severity: warning
    disposition: open
    title: "Unknown keys inside a parseable row are dropped on save, contradicting the new \"saving here keeps them\" promise"
  - id: WR-06
    severity: warning
    disposition: open
    title: "An in-flight failing run re-creates the local failure issue after a mute or empty-additive save cleared it (WR-02 fix is racy)"
  - id: IN-08
    severity: info
    disposition: open
    title: "Preserved rows are invisible to every device-scoped operation, so they outlive adoption and \"Remove local customization\" and can resurface after an upgrade"
  - id: IN-09
    severity: info
    disposition: open
    title: "Hub removal deletes Core's `.corrupt` copy but leaves Core's persistent `storage_corruption_*` repair pointing at it"
  - id: IN-10
    severity: info
    disposition: open
    title: "Text drift after the WR-01 and WR-03 fixes"
  - id: IN-01
    severity: info
    disposition: open
    title: "The `replaced` placeholder of the approval issue is never rendered, so `_refresh_approval_count` does no visible work (carried forward)"
  - id: IN-02
    severity: info
    disposition: open
    title: "Production-dead state and API kept only for tests (carried forward)"
  - id: IN-03
    severity: info
    disposition: open
    title: "The test topic applies the mode gate twice (carried forward)"
  - id: IN-04
    severity: info
    disposition: open
    title: "`local_action_devices` docstring says \"sorted by id\", but mirrors are listed in dict order (carried forward)"
  - id: IN-05
    severity: info
    disposition: open
    title: "A build-time local validation failure is logged twice at ERROR and refreshes the issue time on every rebuild (carried forward)"
  - id: IN-06
    severity: info
    disposition: open
    title: "Shared response variables let an approved owner branch feed values into unguarded local templates (carried forward)"
  - id: IN-07
    severity: info
    disposition: open
    title: "`adopt_device` surfaces an untranslated internal error when the local discard cannot be saved (carried forward)"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Any tombstone on a config topic permanently discards local actions, while the mirror itself self-heals"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "The local failure issue cannot clear after the user mutes the trigger or empties its additive actions"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "A corrupt or shape-invalid local Store is treated as empty: no `local_actions_unreadable` issue, mutes revert, and the next save overwrites it"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "The hub-removal warning reports 0 devices when the local Store is unreadable, but removal deletes the file anyway"
open: 12
total: 16
recorded: 2026-10-21T08:41:32.564Z
---

# Phase 11: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| IN-08 | info | open | - |
| IN-09 | info | open | - |
| IN-10 | info | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| WR-01 | warning | fixed | plan 11-18, 17865da (not in the current review) |
| WR-02 | warning | fixed | plan 11-19, 5bc5ed4 (not in the current review) |
| WR-03 | warning | fixed | plans 11-20 6c09f99, 11-21 936e0d9 (not in the current review) |
| WR-04 | warning | fixed | plan 11-22, 142dd3c (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
