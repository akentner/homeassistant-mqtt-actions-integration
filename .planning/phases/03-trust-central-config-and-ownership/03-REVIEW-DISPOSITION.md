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
