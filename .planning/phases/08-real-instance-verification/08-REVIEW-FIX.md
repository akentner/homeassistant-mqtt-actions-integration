---
phase: 08-real-instance-verification
fixed_at: 2026-10-11T00:00:00Z
review_path: .planning/phases/08-real-instance-verification/08-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 8: Code Review Fix Report

**Fixed at:** 2026-10-11
**Source review:** .planning/phases/08-real-instance-verification/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, WR-02; the scope was narrowed by the caller to the two warnings, IN-01 to IN-04 were not touched)
- Fixed: 2
- Skipped: 0

**Source files changed:** `custom_components/mqtt_actions/takeover.py` only. `custom_components/mqtt_actions/manager.py`
was NOT changed. Test file changed: `tests/test_takeover.py`.

**Workflow:** TDD, one finding at a time (failing test commit, then fix commit). `workflow.use_worktrees` is `false`, so
all edits and commits ran in the main checkout (no worktree, no recovery sentinel). `.planning/config.json` carried an
unrelated uncommitted change and was never staged. Nothing was pushed.

## Fixed Issues

### WR-01: `remove_replay_twins` removes enabled, loaded rows, which clears the retained discovery topic and leaves an enabled tombstone

**Files modified:** `custom_components/mqtt_actions/takeover.py`, `tests/test_takeover.py`
**Commits:** `f66caca` (failing test), `3f1b61e` (fix)
**Applied fix:** In `remove_replay_twins`, a legacy row whose `disabled_by` is `None` is now set to
`RegistryEntryDisabler.INTEGRATION` before `async_remove`. Core then unloads the entity and no empty retained payload
goes to the discovery topic, and the deleted record carries the `integration` state. This is the reviewer's first fix
option. It sits in `takeover.py`, so every caller is covered, including the `_remove_replay_twins` call in
`Manager._async_native_takeover`, which runs before the guard is armed. The docstring was updated (it no longer says
core publishes a clear). `manager.py` needed no change.
**Test:** `test_remove_replay_twins_disables_a_loaded_row_first_so_nothing_is_cleared_and_no_enabled_tombstone_stays`
asserts on a loaded, enabled replayed duplicate that no publish with an empty or `None` payload goes to the discovery
topic and that all three deleted records have `disabled_by is INTEGRATION`. Core clears with a `None` payload, which the
existing `_discovery_clears` helper (empty string) does not see, so the test filters on `not payload`. Before the fix it
failed on the clear assertion (3 empty publishes on the topic).
**Status:** fixed (logic change; requires human verification per the verification strategy, although the behavior is
covered by the new test and the full suite).

### WR-02: `disable_duplicates` claims the duplicate definition of `remove_replay_twins` but drops its identity check

**Files modified:** `custom_components/mqtt_actions/takeover.py`, `tests/test_takeover.py`
**Commits:** `e8acb50` (first failing test, see deviation), `4097b15` (corrected failing test), `1ae6ad0` (fix)
**Applied fix:** `disable_duplicates` now skips an entry that holds the user's choices while its native twin does not
(`_is_customized(entry) and not _is_customized(twin)`). The docstring was rewritten to state the actual definition.
**Test:** `test_disable_duplicates_leaves_a_customized_entry_enabled_next_to_an_untouched_native_twin` (failed before
the fix with `1 == 0`) and a positive control, `test_disable_duplicates_disables_a_legacy_entry_when_the_native_twin_carries_the_identity`
(only the twin is customized, so the legacy entry is still disabled; it passed before and after).
**Status:** fixed: requires human verification (logic change, and a deliberate deviation from the review's suggested fix).

**Deviation from the suggested fix:** The review proposed reusing `_carries_the_identity(entry, twin)`, which also
includes the age rule (older entry wins). I applied that first and it broke 4 existing tests
(`test_the_guard_does_not_depend_on_the_export_option[options2]`, `test_switching_the_export_off_leaves_the_guard_armed`,
`test_the_guard_publishes_nothing_and_stops_with_the_manager`, and
`test_a_duplicate_that_exists_before_the_device_is_held_is_disabled_when_the_native_entity_appears`). The reason is
substantive and not a test artifact: a row that core restores from a deleted-entity record (the UAT-04 tombstone
scenario this guard exists for) keeps the original `created_at`, so it looks "older" than the native twin and the age
rule would leave exactly that duplicate enabled. The same holds when the row exists before the native twin appears
(E2). Only the customization half of the identity test is therefore applied, and the docstring says why age is
deliberately excluded. That attempt was rolled back (`git checkout -- takeover.py`) before commit. The first test commit
`e8acb50` encoded the age-based expectation (older uncustomized row stays enabled) and was superseded by `4097b15`
rather than rewriting history; the final fix commit `1ae6ad0` is consistent with the corrected test.

**Open question for the owner:** if both the legacy row and the native twin are customized, the guard still disables the
legacy row (the native twin keeps its choices). The review did not specify this case.

## Verification

Run in the main checkout (no worktree), `uv run`, Python 3.14:
- Affected modules (`tests/test_takeover.py`, `tests/test_export_guard_receiver.py`, `tests/test_discovery_export.py`,
  `tests/test_native_start.py`, `tests/test_native_replay.py`): 106 passed.
- Full suite `uv run pytest`: 1516 passed.
- `uv run ruff check .`: all checks passed. `uv run ruff format --check .`: clean.

---

_Fixed: 2026-10-11_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
