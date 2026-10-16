---
phase: 10-review-findings-and-native-migration-extraction
plan: 04
subsystem: native-migration
tags: [refactor, pure-move, native-migration, ast-audit, mutation-testing, fix-02, d-09, d-10]
status: complete

requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-03 (tests/test_startup_order.py, mutation/mutate.py, mutation/pre-move.tsv with 28 of 28 killed)"
provides:
  - "custom_components/mqtt_actions/native_migration.py: NativeMigration owns the cutover, the takeover pass, the replay catch with the shared-topic gate, the duplicate guard and the per-run sets"
  - "Manager accessors native_state, publisher, async_save_now, schedule_save, test_message_handler; delegators on_roster_changed, on_discovery_emptied"
  - "mqtt_gateway.async_attempt (moved unchanged from manager._async_attempt)"
  - "mutation/move_audit.py + move-audit.txt (28 PASS), mutation/post-move.tsv (28 of 28 moved killed)"
affects: [10-05 to 10-10 (FIX-04 to FIX-08 edit native_migration.py, not manager.py), 11 (MIR-01 edits a quieter manager.py)]

actuals:
  tokens: 32768
  tasks: 3
  commits: 2
plan_head_before: dbfbf81e1aa875b4b0c33e374972336771110a7b
plan_head_after: cbf5383c02bbdc61389b4515b900a2a28d8fc646

tech-stack:
  added: []
  patterns:
    - "Collaborator with a back-reference (like SyncManager, PresenceManager, RetriggerCoordinator) that reads the manager only through public members; a needed private member gets a one-line public accessor"
    - "Move by AST block extraction plus a fixed list of access-path substitutions, proven by an audit that rewrites the old method with exactly that list and compares the whole AST"

key-files:
  created:
    - custom_components/mqtt_actions/native_migration.py
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/move_audit.py
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/move-audit.txt
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/post-move.tsv
    - .planning/phases/10-review-findings-and-native-migration-extraction/mutation/junit-post/ (34 subset reports + 2 full-suite reports)
    - .planning/phases/10-review-findings-and-native-migration-extraction/deferred-items.md
    - .planning/WINDOWS.md
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/mqtt_gateway.py
    - tests/conftest.py
    - tests/test_native_replay.py

key-decisions:
  - "The AST audit goes beyond the plan's per-method fields: it also rewrites each old Manager method with exactly the documented access paths and compares the whole AST, so a reorder, a negation or a changed text cannot pass (proven in memory against three such edits)"
  - "The two glue survivors defer_for_run and forget carry an equivalent note that is equivalence to the pre-move tree, not to the product: the same deletion inline in Manager at dbfbf81 also survives the full suite, so the move lost no guard; the pins go to a later plan because D-10 forbids a new test here (deferred-items.md, WINDOWS.md ids 1 and 2)"
  - "The comment on the replay-catch arm moved with the call into NativeMigration.arm_timers, next to self._arm_replay_catch()"

patterns-established:
  - "Migration code lives in native_migration.py; Manager calls it only through self.migration.<public member>"

requirements-completed: [FIX-02]

coverage:
  - id: D1
    description: "The cutover, takeover pass, replay catch, duplicate guard and per-run sets live in NativeMigration; manager.py shrank from 2956 to 2291 lines"
    requirement: FIX-02
    verification:
      - kind: other
        ref: "Task 2 verify (moved names absent from manager.py, kept_legacy_ids stays, async_attempt in mqtt_gateway.py, wc -l <= 2400, no by-name import of takeover or registry functions)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The move is pure: start-up order test byte-identical and green, same test count, only access-path test edits, AST audit 28 PASS"
    requirement: FIX-02
    verification:
      - kind: unit
        ref: "tests/test_startup_order.py (unchanged since dbfbf81)"
        status: pass
      - kind: other
        ref: "uv run python mutation/move_audit.py --base dbfbf81 (28 PASS, 3 CHECK ok, exit 0)"
        status: pass
      - kind: unit
        ref: "uv run pytest -q (1735 passed, 2 xfailed; 1737 collected before and after)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Post-move mutation run: every mutant of the 28 moved methods killed by the unchanged suite; 4 glue methods killed, 2 with an equivalence-to-base note"
    requirement: FIX-02
    verification:
      - kind: other
        ref: "mutation/post-move.tsv (34 rows: 32 killed, 2 survived with equivalent: note)"
        status: pass
    human_judgment: false

duration: 34min
completed: 2026-10-16
---

# Phase 10 Plan 04: Native Migration Extraction Summary

**The native-migration orchestration moved out of `manager.py` into `NativeMigration` (`native_migration.py`) as a pure move. The cutover, the takeover pass with its finish, deferral and unconfirmed-clear retry, the replay catch with the 09.2 gate, the duplicate guard and the per-run sets all live there now. `manager.py` dropped from 2956 to 2291 lines. The start-up order test is byte-identical and green. The suite was untouched apart from 14 access-path lines. An AST audit passes all 28 methods, and the post-move mutation run kills every mutant of the 28 moved methods (FIX-02, D-09, D-10).**

## Performance

- **Duration:** 34 min
- **Started:** 2026-10-16T13:04:16Z
- **Completed:** 2026-10-16T13:38:21Z
- **Tasks:** 3
- **Files:** 3 product files (1 new), 2 test files; under `.planning/` the audit script and its output, the TSV, 36 JUnit reports, `deferred-items.md` and `WINDOWS.md`

## Baseline and counts

| Item | Value |
|---|---|
| B0 (HEAD before the first edit) | `dbfbf81e1aa875b4b0c33e374972336771110a7b` |
| Collected tests before / after | 1737 / 1737 |
| Full suite before / after | 1735 passed, 2 xfailed / 1735 passed, 2 xfailed |
| `manager.py` lines before / after | 2956 / 2291 |
| `native_migration.py` lines | 779 |
| Unchanged since B0 | `tests/test_startup_order.py`, `presence.py`, `sync.py`, `takeover.py` (`git diff --quiet dbfbf81 HEAD`) |
| `main` | `601a41c6ac9f4824b9a548a4d47848b5840384f9` (unchanged); HEAD on `gsd/phase-10-review-findings-and-native-migration-extraction` |

## What moved

- **Into `NativeMigration` (names unchanged):** `_arm_cutover`, `_on_cutover_due`, `on_roster_changed`, `_start_cutover_check`, `_async_cutover_check`, `_show_cutover_hint`, `_clear_cutover_hint`, `_async_take_over_one`, `_async_finish_takeover`, `_async_defer_takeover`, `_native_device_ids`, `_topic_verdict`, `_ids_that_may_empty_the_topic`, `_remove_replay_twins`, `_arm_replay_catch`, `on_discovery_emptied`, `_on_replay_catch_due`, `_async_replay_catch`, `_rearm_or_log_replay_catch`, `_async_publish_migrates`, `_may_clear`, `_duplicate_guard_ids`, `_disarm_duplicate_guard`, `_on_duplicate_registry_updated`, `_disable_duplicates`.
- **Renamed to public:** `_async_native_takeover` became `async_takeover`, `_arm_duplicate_guard` became `arm_duplicate_guard`, and `_async_retry_unconfirmed_clears` became `async_retry_unconfirmed_clears`.
- **State that moved, with its comments:** `_legacy_this_run`, `_clear_unconfirmed`, `cutover_settle_seconds`, `_cancel_cutover`, `_cancel_replay_catch`, `_replay_catch_retries`, `_replay_catch_armed`, `_cancel_duplicate_guard`, `_cutover_ready`, `_cutover_hint`.
- **New glue:** `arm_timers` (cutover arm, then catch arm), `stop` (the old `async_stop` lines in their order), `is_deferred`, `clear_pending`, `defer_for_run`, `forget`.
- **Stays in Manager:** `NativeState` (`self._native`), `kept_legacy_ids` with `_kept_failure_logged`, `_schedule_native_reload` with `_reload_scheduled`, `_native_pending` and `_native_devices`.
- **Manager additions:** `self.migration = NativeMigration(self)` right after the retrigger coordinator. One-line accessors: the `native_state` and `publisher` properties, plus `async_save_now()`, `schedule_save()` and `test_message_handler(device_id)`. One-line delegators: `on_roster_changed()` and `on_discovery_emptied(device_id)`. `async_start` calls `self.migration.async_takeover()` and `self.migration.arm_duplicate_guard()` in the old slots, and `self.migration.arm_timers()` after the heartbeat. `async_stop` calls `self.migration.stop()` right after `_running = False`.
- **`mqtt_gateway.async_attempt`:** the body and docstring of `manager._async_attempt` are unchanged. Every call site in manager.py changed only the name.
- **Module-attribute calls:** `native_migration.py` imports `takeover`, `ir` and `er` only as modules. `CUTOVER_SETTLE_SECONDS` and `async_call_later` are module-level names there, which are the conftest patch target and the timer spy target.

## Changed test lines (every one, with its category)

| File:line | Change | Category |
|---|---|---|
| `tests/conftest.py:14` | `import manager as manager_module` to `import native_migration as native_migration_module` | import of the module that now holds the patch target |
| `tests/conftest.py:69` | `setattr(manager_module, "CUTOVER_SETTLE_SECONDS", None)` to `native_migration_module` | patch target (`disable_native_cutover`) |
| `tests/conftest.py:84` | the same for `enable_native_cutover` | patch target |
| `tests/test_native_replay.py:15` | `import manager as manager_module` to `import native_migration as native_migration_module` | import |
| `tests/test_native_replay.py:20` | `from ...manager import Manager` removed (no other use left) | import |
| `tests/test_native_replay.py:21` | `from ...native_migration import NativeMigration` added | import |
| `tests/test_native_replay.py:235` | `manager_of(legacy.entry)._cancel_replay_catch` to `.migration._cancel_replay_catch` | access path |
| `tests/test_native_replay.py:243` | the same | access path |
| `tests/test_native_replay.py:1388` | `original = Manager._async_replay_catch` to `NativeMigration._async_replay_catch` | patch target (wrapped original) |
| `tests/test_native_replay.py:1390` | `_counted(manager: Manager)` to `_counted(manager: NativeMigration)` | annotation of the patch wrapper (parameter name kept) |
| `tests/test_native_replay.py:1394` | `setattr(Manager, "_async_replay_catch", ...)` to `NativeMigration` | patch target |
| `tests/test_native_replay.py:1421` | `original = manager_module.async_call_later` to `native_migration_module.async_call_later` | patch target (wrapped original) |
| `tests/test_native_replay.py:1424` | timer spy filter `Manager._on_replay_catch_due` to `NativeMigration._on_replay_catch_due` | patch target (spy identity) |
| `tests/test_native_replay.py:1442` | `setattr(manager_module, "async_call_later", ...)` to `native_migration_module` | patch target |
| `tests/test_native_replay.py:1493` | `manager._replay_catch_retries` to `manager.migration._replay_catch_retries` | access path |

`grep -E "^[-+]\s*assert"` over `git diff -U0 3bb3677^ HEAD -- tests/` prints exactly three -/+ pairs. In each pair, the `+` line contains `.migration.` and the `-` line is the old access path of the same assertion. No assertion value, test, parameter name or other line changed.

## Patch-target audit

Every `monkeypatch.setattr`, `patch.object` and `patch("...")` target under `tests/` whose owner is `Manager`, the manager module or a manager instance was checked with `uv run python -c`. Each still exists:

| Target | Used at | Exists |
|---|---|---|
| `custom_components.mqtt_actions.manager.MqttGateway` | `tests/fake_broker.py:306` | OK |
| `Manager.kept_legacy_ids` | `tests/test_presence.py:144`, `:181` | OK (stays in Manager per D-09) |
| `manager._store.async_save` / `async_delay_save` (Store) | `tests/test_multi_instance_ops.py:1183-1184` | OK; `async_save_now` and `schedule_save` still go through `self._store` |
| `manager.runner.async_unload` | `tests/test_sync_follower.py:773` | OK |
| `manager.gateway.mqtt_entry_id` | `tests/test_sync_follower.py:918` | OK; the moved code reads `self._manager.gateway`, the same object |
| `manager_module.async_remove_all_devices` / `async_remove_local_state` | `tests/test_hub_removal.py:298`, `:314`, `:320` (calls, not patches) | OK |

The new targets on the native_migration side all resolve: `native_migration_module.CUTOVER_SETTLE_SECONDS`, `native_migration_module.async_call_later`, `NativeMigration._async_replay_catch` and `NativeMigration._on_replay_catch_due`. The suite is green with them, and the mutants of these methods are killed. No test patches `custom_components.mqtt_actions.manager.takeover`, `.ir` or `.er`. Tests that patch `takeover.*` still intercept, because `native_migration.py` calls through the module.

## AST audit (mutation/move-audit.txt)

`uv run python mutation/move_audit.py --base dbfbf81` exits 0 with **28 PASS, 0 FAIL**. It also reports three `CHECK ok` lines: Manager at HEAD defines none of the 28 names except the two delegators, every `@callback` method of NativeMigration is a plain def, and no moved def became an async def.

For each of the 28 methods the audit compares kind, decorators, docstring, the multiset of string constants, the `ast.dump` of every f-string, the ordered `takeover.<name>` calls and references, and the ordered (LOGGER method, first argument) pairs. It also compares the whole method AST, after it rewrites the old method with exactly the access paths of the move (`self._hass` to `self._manager.hass`, `self._native*` to `self._manager.native_state*`, the Store save to `async_save_now()`, `partial(self._on_test_message, ...)` to `test_message_handler(...)`, `_async_attempt` to `async_attempt`, the three renames). All 28 are equal under that rewrite. To show the audit is not vacuous, it was fed three in-memory edits of the moved code: two swapped statements, a changed log text and a negated return. It reported each one as a difference.

## Post-move mutation run (mutation/post-move.tsv)

- **Command:** `mutate.py --file custom_components/mqtt_actions/native_migration.py --class NativeMigration --methods <28 moved + 6 glue> --full-on-survive --junit-dir mutation/junit-post`, with the same 13-module `-x -q` subset as the pre-move run.
- **28 moved methods: 28 killed, none survived, no test edit.** The first failing tests match the pre-move pattern. `_disarm_duplicate_guard` is killed again by the 10-03 pin `test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener`.
- **Glue:** `arm_timers`, `stop`, `is_deferred` and `clear_pending` are killed. `defer_for_run` and `forget` survived the subset and the full suite (`junit-post/<name>-full.xml`).
  - **Why they are not move defects:** the call paths are intact. `Manager._follow_native_status` calls `self.migration.defer_for_run` and `Manager._forget_native` calls `self.migration.forget`. The pre-move tree has the same gap. On a scratch export of `dbfbf81`, deleting `self._legacy_this_run.add(device.device_id)` in `Manager._follow_native_status` left the full suite green (1735 passed, 2 xfailed). Deleting the two per-run discards in `Manager._forget_native` did the same.
  - Neither statement was in the 28-method survey of 10-03. Each row carries an `equivalent:` note that states this is equivalence to the pre-move tree and **not** behavior equivalence, and names the unpinned behavior.
  - The pins are left to a later plan, because D-10 forbids a new test in the move plan. They are recorded in `deferred-items.md` and as WINDOWS ledger entries 1 and 2 (`unmet-truth`, open).

## Task Commits

1. **Task 1 (tracer): cutover into NativeMigration, conftest repointed.** `3bb3677` (refactor). Changes exactly `native_migration.py` (new), `manager.py` and `tests/conftest.py`. Tracer gate: the mode is end-of-phase and the verify is automated-only, so the verify was re-run. It passed: 33 passed on the subset, the guarded files were byte-identical, Ruff was clean, and the full suite was green. The plan then expanded.
2. **Task 2: takeover pass, replay catch, duplicate guard and per-run sets into NativeMigration; `async_attempt` into mqtt_gateway.** `cbf5383` (refactor). Changes exactly the four listed files.
3. **Task 3: audit and mutation proof.** There is no product or test commit. The audit script, `move-audit.txt`, `post-move.tsv`, the JUnit reports, `deferred-items.md` and `WINDOWS.md` go into the SUMMARY commit, as the plan says.

## Files Created/Modified

- `custom_components/mqtt_actions/native_migration.py` (new): module docstring per D-09, class `NativeMigration` with 6 glue methods and 28 moved methods.
- `custom_components/mqtt_actions/manager.py`: the migration code was removed. Added `migration`, the accessors and the delegators. Unused imports were dropped (`async_call_later`, `CUTOVER_*`, `HEARTBEAT_INTERVAL_SECONDS`, `DiscoveryContent`, `EXPIRY_MARGIN_SECONDS`, `Awaitable`, `Collection`, `Event`).
- `custom_components/mqtt_actions/mqtt_gateway.py`: `async_attempt`, plus the `LOGGER` and `Awaitable` imports.
- `tests/conftest.py`, `tests/test_native_replay.py`: only the lines in the table above.
- `mutation/move_audit.py`, `mutation/move-audit.txt`, `mutation/post-move.tsv`, `mutation/junit-post/` (36 reports).
- `deferred-items.md`, `.planning/WINDOWS.md`.

## Decisions Made

- **Whole-AST comparison in the audit.** The plan's field list could miss a reordered or negated statement. The rewrite-and-compare check closes that gap, and it is proven to fail on such edits.
- **Equivalence notes for the two glue survivors, scoped honestly.** The plan allows an `equivalent:` note for a glue survivor. The note says "equivalent to the pre-move tree", backs it with the base-mutant runs, and names the behavior that stays unpinned. A test would break D-10, and a product change would break the pure-move rule.
- **The replay-catch comment moved with its call.** The comment about the quiet period now sits above `self._arm_replay_catch()` in `arm_timers`. It is no longer above `self.migration.arm_timers()` in `async_start`, where it would read as a comment on the cutover too.

## Deviations from Plan

None in the product or tests. The plan was executed as written. The two glue survivors are handled by the plan's own `equivalent:` branch, and the audit got one extra check on top of the planned ones (both are recorded as decisions above).

## Issues Encountered

- Two glue mutants (`defer_for_run`, `forget`) survived. As shown above, the gap predates the move, and it is logged for a later plan.
- `.planning/` is excluded from Ruff (`.ruff.toml` `extend-exclude`), so `move_audit.py` is formatted but not linted under the project rules, like `mutate.py`.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- Plans 10-05 to 10-10 (FIX-04 to FIX-08) edit the migration in `native_migration.py`.
- Open WINDOWS entries 1 and 2 ask for two test-only pins: a running legacy mirror that turns native stays non-native until the reload, and a deferred, released id starts clean in the same run. They fit a test plan of this phase or the next one.

---
*Phase: 10-review-findings-and-native-migration-extraction*
*Completed: 2026-10-16*

## Self-Check: PASSED

- FOUND: native_migration.py, move_audit.py, move-audit.txt, post-move.tsv, junit-post/ (36 reports), deferred-items.md, .planning/WINDOWS.md
- FOUND commits: 3bb3677, cbf5383 (both ancestors of HEAD)
- Task verifies: Task 1 (subset 33 passed, structure greps, byte-identical guard, Ruff, full suite), Task 2 (subset 372 passed, 2 xfailed; structure greps; manager.py 2291 lines; no by-name imports; Ruff; full suite), Task 3 (28 PASS / 0 FAIL; 34 method rows; survivors carry `equivalent:`; product tree clean; full suite 1735 passed, 2 xfailed)
