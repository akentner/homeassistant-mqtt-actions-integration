---
phase: 10-review-findings-and-native-migration-extraction
verified: 2026-10-16T15:01:18Z
status: human_needed
score: 5/5 must-haves verified (roadmap success criteria; 53/53 plan truths verified)
covered_files:
  - ".github/workflows/ci.yml"
  - ".github/workflows/validate.yml"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-01-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-01-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-02-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-02-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-03-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-03-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-04-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-04-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-05-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-05-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-06-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-06-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-07-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-07-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-08-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-08-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-09-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-09-SUMMARY.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-10-PLAN.md"
  - ".planning/phases/10-review-findings-and-native-migration-extraction/10-10-SUMMARY.md"
  - "README.md"
  - "custom_components/mqtt_actions/const.py"
  - "custom_components/mqtt_actions/manager.py"
  - "custom_components/mqtt_actions/mqtt_gateway.py"
  - "custom_components/mqtt_actions/native_migration.py"
  - "custom_components/mqtt_actions/takeover.py"
  - "custom_components/mqtt_actions/translations/de.json"
  - "custom_components/mqtt_actions/translations/en.json"
  - "docs/troubleshooting.md"
  - "tests/conftest.py"
  - "tests/helpers.py"
  - "tests/test_core_contracts.py"
  - "tests/test_cutover.py"
  - "tests/test_diagnostics.py"
  - "tests/test_discovery_content.py"
  - "tests/test_discovery_export.py"
  - "tests/test_docs.py"
  - "tests/test_export_guard_receiver.py"
  - "tests/test_hub_removal.py"
  - "tests/test_kept_duplicates.py"
  - "tests/test_native_cleanup.py"
  - "tests/test_native_entities.py"
  - "tests/test_native_replay.py"
  - "tests/test_native_start.py"
  - "tests/test_presence.py"
  - "tests/test_repo_structure.py"
  - "tests/test_startup_order.py"
  - "tests/test_takeover.py"
  - "tests/test_translations.py"
covered_digest: "v3:sha256:b3d012fba83d98bfcfba711201fd282b7a1785032845f66b85abb9ab74f8ac04"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Owner decision on review WR-01: keep the kept_duplicates warning non-persistent (a dismissal returns after every Home Assistant restart while a kept duplicate exists), or create it with is_persistent=True so a dismissal of an unchanged list survives restarts"
    expected: "A recorded decision in 10-REVIEW-DISPOSITION.md. If kept: reword the README and troubleshooting rationale 'because Home Assistant does not keep the text of this warning across a restart', which presents an integration choice as an HA limitation. If changed: is_persistent=True, docs and test_the_docs_describe_the_kept_duplicates_warning updated."
    why_human: "The shipped behavior matches the plan (10-09 decision, 10-10 must-have) and D-02, so it is no gap; whether a supported steady state (a duplicate the user keeps on purpose) should nag after every restart is a product decision"
  - test: "On a bench instance with one customized MQTT duplicate kept enabled next to its native twin (and one next to a native twin the user disabled), open Settings > Repairs in English and in German"
    expected: "One non-fixable warning 'Duplicate MQTT entities stay enabled' / 'Doppelte MQTT-Entitäten bleiben aktiviert', no Fix button, entity ids rendered readably per reason, the dash for an empty reason, the advice to disable rather than delete; it goes away after the duplicate is disabled and the integration restarts"
    why_human: "Tests pin placeholders and translation keys, not the Repairs dialog rendering (Markdown escaping, the dash, the count-1 wording of IN-05)"
---

# Phase 10: Review Findings and Native Migration Extraction Verification Report

**Phase Goal:** The info findings of both Phase 8 reviews are closed, and the takeover, replay-catch and duplicate-guard orchestration lives in its own module, so `manager.py` is smaller and quiet before MIR-01 edits it.
**Verified:** 2026-10-16T15:01:18Z
**Status:** human_needed
**Re-verification:** No (initial verification)

## Goal Achievement

### Observable Truths (roadmap success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Takeover, replay-catch and duplicate-guard orchestration lives in its own module outside `manager.py`; pure move proven by the suite and a start-up ordering test written before the move (FIX-02) | ✓ VERIFIED | `native_migration.py:90` `class NativeMigration`; `manager.py:518` `self.migration = NativeMigration(self)`; delegation at `manager.py:650,655,671,808,810,816,856,861,933,1000,1406,1748`; `grep` finds no remove_replay_twins / disable_duplicates / replay_catch / cutover / _legacy_this_run in `manager.py`. `manager.py` 2956 -> 2296 lines (limit 2400). Verifier re-ran `mutation/move_audit.py --base dbfbf81` on `cbf5383` in an isolated worktree: 28/28 PASS, 3/3 CHECK ok, exit 0. `tests/test_startup_order.py` committed in `8da1699`/`57eb119` (before `3bb3677`), unchanged since (`git diff 57eb119 HEAD` empty); it spies only on non-moved seams and asserts the lock state per step; 4/4 pass. Move commits touch only `conftest.py` and `test_native_replay.py`, access paths and patch targets only. Post-move mutation: 28/28 moved methods killed. |
| 2 | Loud tests (never skip/xfail) for the private flush API and the eager-task no-clear basis; guard test proves listener ran for a second create event and returned 0; shared helpers in one module, no cross-imports between test modules (FIX-01, FIX-03, FIX-04, FIX-07) | ✓ VERIFIED | `tests/test_core_contracts.py`: 5 tests pass (flush writes both registries without time advance with `FLUSH_FALLBACK_HINT`; structural `_store`/`_data_to_save` pin; refused write falls back; two `EAGER_TASK_HINT` outcome pins on takeover path and replay catch). No skip/xfail markers in the file; the 2 suite xfails are pre-existing Phase 8 params in `test_takeover.py:1383` (`4bc91d8`). `test_export_guard_receiver.py:445` asserts `passes == [(device_id, 0)]`; passes. `tests/helpers.py` (310 lines) holds the shared helpers; `test_no_test_module_imports_from_another_test_module` passes; `grep "from tests.test_"` in tests/ is empty. |
| 3 | A row that raises mid-loop in the replay catch leaves no emptied device and the partial count is still reported (FIX-06) | ✓ VERIFIED | `takeover.py:319-337` `_remove_planned` returns (removed, err); `takeover.py:395-404` removes the emptied device, logs the count, then `raise ReplayTwinsError(removed) from failure`. `native_migration.py:217-260` adds `err.removed`, sets `errored`; catch flushes on `removed or errored` (`native_migration.py` catch body). Tests pass: `test_a_row_that_raises_mid_loop_in_the_catch_leaves_no_emptied_device_and_keeps_the_count`, `test_a_raise_on_the_first_row_still_flushes_and_keeps_the_device`, `test_remove_replay_twins_raises_with_the_partial_count_after_removing_the_emptied_device`, `test_remove_replay_twins_counts_only_rows_whose_removal_returned`. |
| 4 | While customized duplicates are kept enabled (incl. WR-03), the user sees one non-fixable Repairs warning listing them in en and de; it disappears once none remain; no registry row is removed (FIX-08) | ✓ VERIFIED | `takeover.py:418-505` `_guard_candidates` shared by `disable_duplicates` and `kept_duplicates`; `native_migration.py:690-738` `_refresh_kept_duplicates` (read-only, `is_fixable=False`, delete-then-create on change, delete on empty); called at both `async_takeover` returns, after every `_disable_duplicates`, and on both catch exit paths. Hub removal deletes it (`manager.py:417-426`). en/de texts present. 7/7 `test_kept_duplicates.py`, 11 partition params, 2 hub-removal params pass. See WR-01 (human decision) below. |
| 5 | README and troubleshooting state that a duplicate the user re-enables is disabled again at the next start (FIX-05) | ✓ VERIFIED | README `MQTT Discovery export` and troubleshooting enabled-duplicate section contain the sentence (diff since `7163c7d`); pinned in `test_docs.py`. Behavior backing it: `test_an_enabled_row_that_exists_when_the_instance_starts_is_disabled` passes. |

**Score:** 5/5 roadmap truths verified (0 present, behavior-unverified). Plan truths: 53/53 verified.

### Plan-level truths (condensed)

| Plan | Truths | Status | Notes |
|------|--------|--------|-------|
| 10-01 | 6 | ✓ | `takeover.py` untouched by 10-01 commits; `ci.yml`/`validate.yml` `branches: ["**"]` + `tags-ignore`; `release.yml` tag-only; todo in `todos/completed/` |
| 10-02 | 5 | ✓ | no product commit; guard test RED evidence `tdd/10-02-task1-red.json` |
| 10-03 | 6 | ✓ | `mutation/pre-move.tsv` 28/28 killed; pin `test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener` |
| 10-04 | 6 | ✓ | audit reproduced; glue survivors `defer_for_run`, `forget` carry the written pre-move-equivalence note in `deferred-items.md` (same statements deleted at `dbfbf81` also survived) |
| 10-05 | 6 | ✓ | see SC 3 |
| 10-06 | 5 | ✓ | backstop truth (two create events in one loop iteration): no suite test; verifier observed it directly with a throwaway probe: no pass ran inside the registry event, then two passes returned 1 and 0 |
| 10-07 | 5 | ✓ | outcome pins; no Entity internals patched (`grep` in `test_core_contracts.py`) |
| 10-08 | 4 | ✓ | no product commit; docs advise disabling, never deleting |
| 10-09 | 7 | ✓ | see SC 4 |
| 10-10 | 3 | ✓ | `NEW_ISSUES['kept_duplicates']` placeholders pinned; docs phrases pinned |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/native_migration.py` | NativeMigration, TwinRemoval, _refresh_kept_duplicates | ✓ VERIFIED | 895 lines, wired from Manager |
| `custom_components/mqtt_actions/manager.py` | migration removed, delegators, ISSUE_KEPT_DUPLICATES cleanup | ✓ VERIFIED | 2296 lines |
| `custom_components/mqtt_actions/mqtt_gateway.py` | `async_attempt` | ✓ VERIFIED | imported by native_migration |
| `custom_components/mqtt_actions/takeover.py` | ReplayTwinsError, KeptReason, _guard_candidates, kept_duplicates | ✓ VERIFIED | |
| `custom_components/mqtt_actions/const.py` | ISSUE_KEPT_DUPLICATES, KEPT_DUPLICATES_MAX_SHOWN | ✓ VERIFIED | not in ISSUE_DEVICE_PREFIXES |
| `tests/helpers.py`, `tests/test_startup_order.py`, `tests/test_core_contracts.py`, `tests/test_kept_duplicates.py` | phase tests | ✓ VERIFIED | all pass |
| `mutation/mutate.py`, `pre-move.tsv`, `post-move.tsv`, `move_audit.py`, `move-audit.txt` | move proof | ✓ VERIFIED | audit re-run by verifier |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| manager.py | native_migration.py | `self.migration.*` (async_takeover, arm_duplicate_guard, arm_timers, stop, async_retry_unconfirmed_clears, forget, defer_for_run, is_deferred, clear_pending, on_roster_changed, on_discovery_emptied) | ✓ WIRED |
| native_migration.py | takeover.py | module-attribute calls (`takeover.remove_replay_twins`, `.disable_duplicates`, `.kept_duplicates`, `.async_flush_registries`, `.ReplayTwinsError`); no by-name imports from takeover/ir/er/dr | ✓ WIRED |
| native_migration.py | issue_registry | `ir.async_delete_issue` then `ir.async_create_issue(..., is_fixable=False, translation_key=ISSUE_KEPT_DUPLICATES)` | ✓ WIRED |
| tests/conftest.py | native_migration.py | patches `CUTOVER_SETTLE_SECONDS` on the native_migration module | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Contract, ordering, kept-duplicates, guard, hub removal | `uv run pytest tests/test_core_contracts.py tests/test_startup_order.py tests/test_kept_duplicates.py ...` | 20 passed | ✓ PASS |
| Docs and translations | `uv run pytest tests/test_docs.py tests/test_translations.py` (in the combined run) | 112 passed | ✓ PASS |
| FIX-06 and guard partition | `uv run pytest tests/test_native_replay.py tests/test_takeover.py -k ...` | 43 passed, 1 xfailed (pre-existing) | ✓ PASS |
| Pure move | `move_audit.py --base dbfbf81` on `cbf5383` worktree | 28 PASS, exit 0 | ✓ PASS |
| WR-02 branches (throwaway probe, not committed) | restored-inactive issue / refresh failure / no MQTT entry | 3 passed: comes back undismissed; issue unchanged, WARNING+DEBUG without entity id; issue deleted | ✓ PASS (not in suite) |
| 10-06 backstop (throwaway probe) | two create events in one sync step | no nested pass; passes `[(id,1),(id,0)]` | ✓ PASS (not in suite) |

### Probe Execution

Step 7c: not applicable. No `scripts/*/tests/probe-*.sh` is declared by the phase.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| FIX-01 | 10-01 | ✓ SATISFIED | SC 2 |
| FIX-02 | 10-03, 10-04 | ✓ SATISFIED | SC 1 |
| FIX-03 | 10-02 | ✓ SATISFIED | SC 2 |
| FIX-04 | 10-06 | ✓ SATISFIED | SC 2 |
| FIX-05 | 10-08 | ✓ SATISFIED | SC 5 |
| FIX-06 | 10-05 | ✓ SATISFIED | SC 3 |
| FIX-07 | 10-07 | ✓ SATISFIED | SC 2 |
| FIX-08 | 10-09, 10-10 | ✓ SATISFIED | SC 4 |

No orphaned requirement: REQUIREMENTS.md maps exactly FIX-01..FIX-08 to Phase 10, and every ID is claimed by a plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (all changed files) | - | TBD/FIXME/XXX/TODO/HACK | none found | - |
| `native_migration.py` | 724-736 | issue created non-persistent (review WR-01) | ⚠️ Warning | dismissal never survives an HA restart; doc rationale misleading |
| `tests/test_kept_duplicates.py` | - | restored-inactive, failure and no-MQTT branches of `_refresh_kept_duplicates` untested (review WR-02) | ⚠️ Warning | behavior correct today (verifier probe), no regression guard |
| `native_migration.py` | 148-157 | `defer_for_run`, `forget` mutants survive (deferred-items.md) | ⚠️ Warning | gap existed before the move; no regression guard |
| `takeover.py` / translations | 500-504 | TWIN_REJECTED text says "you disabled" for any `disabled_by` (review IN-01) | ℹ️ Info | wording |
| `translations/en.json` | kept_duplicates | "1 MQTT entities" (review IN-05) | ℹ️ Info | wording |

### Human Verification Required

### 1. Owner decision on WR-01 (dismissal across restarts)

**Test:** Decide whether the kept_duplicates warning stays non-persistent or becomes `is_persistent=True`.
**Expected:** A recorded decision in `10-REVIEW-DISPOSITION.md`. If it stays: reword the rationale in the README and in troubleshooting. If it changes: update the code, the docs and the doc test.
**Why human:** The behavior matches the plan and D-02. Whether a supported steady state should come back after every restart is a product decision.

### 2. Repairs dialog rendering (en and de)

**Test:** On the bench, keep one customized duplicate and one duplicate next to a disabled native twin, then open Settings > Repairs in both languages.
**Expected:** One non-fixable warning without a Fix button, with readable entity ids per reason, the dash for an empty reason and the advice to disable rather than delete. It disappears after the duplicate is disabled and the integration restarts.
**Why human:** The tests check the placeholders, not how the frontend renders them.

### Gaps Summary

No goal gap. All five roadmap success criteria and all 53 plan truths hold in the code. Behavior-dependent truths are backed by passing named tests or by direct observation. The move is proven pure: the verifier re-ran the AST audit, and every moved-method mutant is killed.

The open items need a decision or more tests. None of them is a missing behavior:

- WR-01 needs an owner decision, see Human Verification 1.
- WR-02 and the two glue survivors are regression-guard gaps. Recommended: a test-only gap plan before MIR-01 edits these files, because Phase 11 builds on `native_migration.py` and `manager.py`.
- IN-01 and IN-05 are wording issues for the review disposition.

---

_Verified: 2026-10-16T15:01:18Z_
_Verifier: Claude (gsd-verifier)_
