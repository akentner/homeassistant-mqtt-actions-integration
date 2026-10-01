---
phase: 03
review: 03-REVIEW.md
---

# Review Disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| CR-01 colliding Select labels hide actions in the approval dialog (trust.py, document.py) | critical | open |
| CR-02 foreign claim for an owned device becomes a mirror during startup (manager.py, sync.py) | critical | open |
| CR-03 names over 64 characters make the owner's own document unparseable (config_flow.py, sync.py) | critical | open |
| WR-01 parse_document raises TypeError for unhashable kind/run_mode (document.py) | warning | open |
| WR-02 approval dialog omits run_on_startup, which the hash binds (trust.py) | warning | open |
| WR-03 denylist misses further host-level services (const.py, README) | warning | open |
| WR-04 run_mode and breaker settings are outside the approval hash | warning | open |
| WR-05 mirror device ids are not length/format validated | warning | open |
| IN-01 repairs.py imports voluptuous instead of probatio | info | open |
| IN-02 duplicated service-name detection logic | info | open |
| IN-03 runner logs broker-derived validation text for mirrors | info | open |
