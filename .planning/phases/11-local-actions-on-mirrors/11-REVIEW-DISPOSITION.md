---
phase: 11
review: 11-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Any tombstone on a config topic permanently discards local actions, while the mirror itself self-heals"
  - id: WR-02
    severity: warning
    disposition: open
    title: "The local failure issue cannot clear after the user mutes the trigger or empties its additive actions"
  - id: WR-03
    severity: warning
    disposition: open
    title: "A corrupt or shape-invalid local Store is treated as empty: no `local_actions_unreadable` issue, mutes revert, and the next save overwrites it"
  - id: WR-04
    severity: warning
    disposition: open
    title: "The hub-removal warning reports 0 devices when the local Store is unreadable, but removal deletes the file anyway"
  - id: IN-01
    severity: info
    disposition: open
    title: "The `replaced` placeholder of the approval issue is never rendered, so `_refresh_approval_count` does no visible work"
  - id: IN-02
    severity: info
    disposition: open
    title: "Production-dead state and API kept only for tests"
  - id: IN-03
    severity: info
    disposition: open
    title: "The test topic applies the mode gate twice"
  - id: IN-04
    severity: info
    disposition: open
    title: "`local_action_devices` docstring says \"sorted by id\", but mirrors are listed in dict order"
  - id: IN-05
    severity: info
    disposition: open
    title: "A build-time local validation failure is logged twice at ERROR and refreshes the issue time on every rebuild"
  - id: IN-06
    severity: info
    disposition: open
    title: "Shared response variables let an approved owner branch feed values into unguarded local templates"
  - id: IN-07
    severity: info
    disposition: open
    title: "`adopt_device` surfaces an untranslated internal error when the local discard cannot be saved"
open: 10
total: 11
recorded: 2026-10-21T05:43:58.334Z
---

# Phase 11: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | plan 11-18, 17865da |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
