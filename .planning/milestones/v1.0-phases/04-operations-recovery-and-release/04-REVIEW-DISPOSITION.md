---
phase: 04
review: 04-REVIEW.md
---

# Review Disposition

0 critical, 12 warnings, 4 info. All findings are open and untriaged; none was fixed during execution.

| Finding | Severity | Disposition |
|---------|----------|-------------|
| WR-01 re-trigger rate limiter records state before the device-exists check (retrigger.py) | warning | open |
| WR-02 forged transferred_from marker or forged heartbeats can raise destructive Repairs flows (sync.py, presence.py, repairs.py, manager.py) | warning | open |
| WR-03 actions_hash lower-cases StateValues but the runtime passes original case to templates (document.py) | warning | open |
| WR-04 adopting an approved mirror builds the Script unrestricted (manager.py) | warning | open |
| WR-05 import applies the broker denylist, so a user's own export may not restore (portability.py) | warning | open |
| WR-06 import skips the UI option rules (portability.py) | warning | open |
| WR-07 _is_template ignores the {# marker (document.py, actions.py) | warning | open |
| WR-08 a failing store save in async_stop skips the rest of teardown (manager.py, __init__.py) | warning | open |
| WR-09 hub removal with delete devices clears topics of adopted-away devices (manager.py) | warning | open |
| WR-10 _checked_size does not catch RecursionError (services.py) | warning | open |
| WR-11 every heartbeat writes entity state with no per-peer throttle (presence.py) | warning | open |
| WR-12 release.yml publishes a release for a tag on any commit; hacs job has no permissions (release.yml, validate.yml) | warning | open |
| IN-01..IN-04 diagnostics NaN/peer names, runner logs broker text, mirror rename resets breaker, workflow timeouts | info | open |
