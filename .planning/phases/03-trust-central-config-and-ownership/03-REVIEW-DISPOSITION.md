---
phase: 03
review: 03-REVIEW.md
---

# Review Disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| CR-01 colliding Select labels hide actions in the approval dialog (trust.py, document.py) | critical | fixed (60a1f22) |
| CR-02 foreign claim for an owned device becomes a mirror during startup (manager.py, sync.py) | critical | fixed (2115d45) |
| CR-03 names over 64 characters make the owner's own document unparseable (config_flow.py, sync.py) | critical | fixed (379243f) |
| WR-01 parse_document raises TypeError for unhashable kind/run_mode (document.py) | warning | fixed (5cf3967) |
| WR-02 approval dialog omits run_on_startup, which the hash binds (trust.py) | warning | fixed (fa4ec30) |
| WR-03 denylist misses further host-level services (const.py, README) | warning | fixed (0cd598d) |
| WR-04 run_mode and breaker settings are outside the approval hash | warning | open (needs user decision: changes wire contract / invalidates approvals) |
| WR-05 mirror device ids are not length/format validated | warning | fixed (6b2ad50) |
| IN-01 repairs.py imports voluptuous instead of probatio | info | open |
| IN-02 duplicated service-name detection logic | info | open |
| IN-03 runner logs broker-derived validation text for mirrors | info | open |

## Iteration 2 (re-review of fix commits 60a1f22..6b2ad50, REVIEW.md overwritten)

Iteration-1 findings CR-01..CR-03, WR-01..WR-03, WR-05 confirmed fixed. IDs below refer to the current 03-REVIEW.md.

| Finding | Severity | Disposition |
|---------|----------|-------------|
| WR-01 unpublishable document is dropped silently, no Repairs issue; stale retained document stays approved on followers (manager.py, config_flow.py) | warning | open |
| IN-01 guard skips validate_spec_structure and catches only DocumentRejectedError | info | open |
| IN-02 _parse_mirrors does not validate ids | info | open |
| IN-03 async_remove_mirror owned-id guard leaves mirror behind (uuid4 collision only) | info | open |
| IN-04 approval dialog nits (duplicate labels, English true/false, run_mode/breaker outside hash) | info | open |
| IN-05 foreign claim replayed during start is healed without an issue | info | open |

Carried over from iteration 1: old WR-04 (run_mode/breaker outside the approval hash) stays open, needs a user decision (wire contract). Old IN-01..IN-03 stay open.
