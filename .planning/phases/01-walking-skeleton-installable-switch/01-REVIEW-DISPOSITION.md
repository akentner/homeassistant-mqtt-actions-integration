---
phase: 01-walking-skeleton-installable-switch
source: 01-REVIEW.md
status: partially_triaged
findings:
  total: 13
  open: 10
  fixed: 3
  skipped: 0
  deferred: 0
---

# Phase 1 code review: disposition ledger

One row per finding, defaulting to `open`. Set a row to `fixed`, `skipped` or `deferred` by hand and write the reason in the Source cell.

| ID | Title | Disposition | Source |
|----|-------|-------------|--------|
| WR-01 | Reconcile has no `_running` guard, so a late update-listener call revives a stopped manager | fixed | fixed in 6361ce7; see 01-REVIEW-FIX.md |
| WR-02 | A failing `async_start` leaks subscriptions and scripts, and a retry doubles them | fixed | fixed in 955c817 (lifecycle change, needs human verification); see 01-REVIEW-FIX.md |
| WR-03 | The single per-device Repairs issue lets a success on one trigger erase a permanent failure on the other | open | 01-REVIEW.md |
| WR-04 | A malformed Store payload raises `TypeError` and the entry can never start | fixed | fixed in 2a65b45; see 01-REVIEW-FIX.md |
| WR-05 | Hub removal deletes the Store even when clearing the broker failed, so ghost entities are never retried | open | 01-REVIEW.md |
| WR-06 | The broker-writable state topic can queue unbounded runs and flood the log | open | 01-REVIEW.md |
| WR-07 | The entity `value_template` does not trim, so the entity and the manager disagree on whitespace payloads | open | 01-REVIEW.md |
| IN-01 | A changed MQTT discovery prefix is never noticed, so old discovery topics are orphaned | open | 01-REVIEW.md |
| IN-02 | The "never log action data" claim (T-01-10) is weaker than the comments state | open | 01-REVIEW.md |
| IN-03 | `expected_lingering_timers` returns True for the whole suite | open | 01-REVIEW.md |
| IN-04 | The gateway catches a bare `KeyError`, and one decode branch is effectively dead | open | 01-REVIEW.md |
| IN-05 | Queued runs of retired scripts are dropped silently on reconfigure | open | 01-REVIEW.md |
| IN-06 | Hygiene nits | open | 01-REVIEW.md |
