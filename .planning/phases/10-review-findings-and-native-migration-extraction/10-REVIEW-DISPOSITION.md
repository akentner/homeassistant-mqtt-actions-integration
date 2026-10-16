---
phase: 10
review: 10-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "The kept-duplicates dismissal never survives a restart, and the documented reason is wrong"
  - id: WR-02
    severity: warning
    disposition: open
    title: "The restart, failure and no-MQTT branches of `_refresh_kept_duplicates` are untested"
  - id: IN-01
    severity: info
    disposition: open
    title: "TWIN_REJECTED blames the user for any `disabled_by` on the native twin"
  - id: IN-02
    severity: info
    disposition: open
    title: "The catch's refresh is not in a `finally`, so the docstring contract can break"
  - id: IN-03
    severity: info
    disposition: open
    title: "The kept-duplicates issue goes stale when the hub is disabled or a device is deleted"
  - id: IN-04
    severity: info
    disposition: open
    title: "\"lists every duplicate\" is not accurate when more than 10 are kept per reason"
  - id: IN-05
    severity: info
    disposition: open
    title: "The English issue text is ungrammatical for a count of 1"
  - id: IN-06
    severity: info
    disposition: open
    title: "Each commit to a PR branch now runs CI and Validate twice"
  - id: IN-07
    severity: info
    disposition: open
    title: "Duplicate constants in the shared test helpers"
  - id: IN-08
    severity: info
    disposition: open
    title: "The contract-pin spy depends on a positional argument index"
open: 10
total: 10
recorded: 2026-10-16T14:54:04.350Z
---

# Phase 10: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
