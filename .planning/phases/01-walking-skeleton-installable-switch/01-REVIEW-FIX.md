---
phase: 01-walking-skeleton-installable-switch
fixed_at: 2026-09-29T00:00:00Z
review_path: .planning/phases/01-walking-skeleton-installable-switch/01-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-09-29
**Source review:** .planning/phases/01-walking-skeleton-installable-switch/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (limited by the developer to WR-01, WR-02, WR-04)
- Fixed: 3
- Skipped: 0 (in scope)
- Not in the developer's requested scope: WR-03, WR-05, WR-06, WR-07, IN-01 to IN-06

**Verification:** run in the main checkout (no worktree), branch `gsd/phase-01-walking-skeleton-installable-switch`. After each fix: `uv run pytest -q` (185 -> 186 -> 187 -> 188 passed), `uv run ruff check .` and `uv run ruff format --check .` all green. Each fix has a regression test that was seen failing before the fix. No README change was needed.

## Fixed Issues

### WR-01: Reconcile has no `_running` guard

**Files modified:** `custom_components/mqtt_actions/manager.py`, `tests/test_manager.py`
**Commit:** 6361ce7
**Applied fix:** `async_reconcile` returns early under the lock when `_running` is False (`async_start` sets it before its own reconcile). Test `test_reconcile_after_stop_does_not_revive_manager` adds a subentry after unload, calls the stopped manager's reconcile, and asserts no device, no discovery publish and no action run.
**Status:** fixed: requires human verification (lifecycle/logic change; the guard is a one-line condition).

### WR-02: A failing `async_start` leaks subscriptions and scripts

**Files modified:** `custom_components/mqtt_actions/__init__.py`, `custom_components/mqtt_actions/manager.py`, `custom_components/mqtt_actions/runner.py`, `tests/test_manager.py`
**Commit:** 955c817
**Applied fix:**
- `async_setup_entry` registers the update listener before `async_start`. It wraps the start: a `HomeAssistantError` calls `manager.async_stop()` and raises `ConfigEntryNotReady`; any other exception stops the manager and re-raises. HA runs the on-unload callbacks of a failed setup (verified in core `config_entries.py`), so the listener and the connection-status subscription are released too.
- `Manager.async_stop` now also calls a new `ActionRunner.async_unload_all()`. Scripts are registered in the runner before a device enters `self.devices`, so a failure in between would otherwise leak them. It also skips the offline publish when the publisher does not exist yet (start failed early).
- Test `test_failed_start_releases_subscriptions_and_retries_cleanly` makes the second device's subscribe raise. It asserts SETUP_RETRY, that the first device's subscription is gone, and that after a reload one message runs the action exactly once.
**Status:** fixed: requires human verification (error-handling logic; adds one small runner method beyond the review's suggestion).

### WR-04: A malformed Store payload raises `TypeError`

**Files modified:** `custom_components/mqtt_actions/manager.py`, `tests/test_manager.py`
**Commit:** 2a65b45
**Applied fix:** `_async_load_store` keeps only entries whose key and value are `str` before the ON/OFF membership check. Test `test_malformed_store_last_acted_is_dropped_and_setup_succeeds` preloads list, dict, int and unknown values and asserts setup succeeds with only the valid baseline kept.
**Status:** fixed

## Skipped Issues

Not in the developer's requested scope (not failures):

- WR-03: skipped: not in the developer's requested scope
- WR-05: skipped: not in the developer's requested scope
- WR-06: skipped: not in the developer's requested scope
- WR-07: skipped: not in the developer's requested scope
- IN-01 to IN-06: skipped: not in the developer's requested scope

---

_Fixed: 2026-09-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
