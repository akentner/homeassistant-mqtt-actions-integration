---
phase: "10"
slug: "review-findings-and-native-migration-extraction"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-17"
---

# Phase 10 — Validation Strategy

> Per-phase validation contract, reconstructed retroactively (validate-phase State B) from the ten plans, their
> summaries, 10-VERIFICATION.md and 10-UAT.md. Audit run on HEAD `a0efc32` on 2026-10-17;
> gaps filled by the Nyquist auditor in `7e7a5ca`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pinned by PHACC 0.13.367), `asyncio_mode = "auto"` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest -q tests/test_core_contracts.py tests/test_startup_order.py tests/test_kept_duplicates.py tests/test_export_guard_receiver.py tests/test_hub_removal.py tests/test_repo_structure.py tests/test_docs.py tests/test_translations.py` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Lint command** | `uv run ruff check . && uv run ruff format --check .` |
| **Estimated runtime** | ~11 s wall, 186 tests (quick), ~2 min 15 s, 1775 tests (full) |

Audit results: full suite 1767 passed, 2 xfailed in 134.81s on `a0efc32`; after the gap fill 1773 passed, 2 xfailed in 132 s on `7e7a5ca` (the 2 xfails are pre-existing Phase 8 params in `tests/test_takeover.py`); Ruff check "All checks passed!", format "99 files already formatted".

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite plus the lint command
- **Before `/gsd-verify-work`:** Full suite and Ruff green
- **Max feedback latency:** 15 seconds (quick)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | FIX-01 (D-05, D-06, D-08) | T-10-02 | The private registry flush writes both registries at once, `_store`/`_data_to_save` stay pinned, a refused write falls back to the scheduled save; never skipped | core contract (tracer, TDD) | `uv run pytest -q tests/test_core_contracts.py -k "registry_flush or flush_api or refused_early_write"` | ✅ | ✅ green |
| 10-01-02 | 01 | 1 | FIX-01 (folded todo ci-push-trigger-branches) | T-10-01 | CI and Validate run on every branch push and never twice on a version tag; permissions unchanged | repo structure | `uv run pytest -q tests/test_repo_structure.py -k "push_trigger or skip_tag_pushes or one_job_per_tier"` | ✅ | ✅ green |
| 10-02-01 | 02 | 2 | FIX-03 (D-11) | T-10-03 | The structure guard fails on any import between test modules; diagnostics key sets live in `tests/helpers.py` | repo structure + refactor (tracer, TDD) | `uv run pytest -q tests/test_docs.py tests/test_diagnostics.py && uv run pytest -q tests/test_repo_structure.py -k another_test_module` | ✅ | ✅ green |
| 10-02-02 | 02 | 2 | FIX-03 (D-11) | T-10-03 | Takeover and native-start helpers move unchanged; seven consumers import from `tests.helpers` | test refactor (suite unchanged) | `uv run pytest -q tests/test_takeover.py tests/test_native_start.py tests/test_cutover.py tests/test_native_cleanup.py tests/test_discovery_content.py tests/test_presence.py tests/test_native_replay.py` | ✅ | ✅ green |
| 10-02-03 | 02 | 2 | FIX-03 (D-10, D-11) | T-10-03 | Native-entity, export and replay helpers move; no `from tests.test_` import remains; count N0 + 1 | repo structure | `uv run pytest -q tests/test_repo_structure.py -k another_test_module` | ✅ | ✅ green |
| 10-03-01 | 03 | 3 | FIX-02 (D-09, D-10) | T-10-04 | Start-up order of an upgrading owner, the lock boundary and both timers are pinned on seams that do not move | integration (spies, fake clock, tracer) | `uv run pytest -q tests/test_startup_order.py` | ✅ | ✅ green |
| 10-03-02 | 03 | 3 | FIX-02 (D-10) | T-10-04 | Every pre-move survivor of the 28-method mutation survey is pinned or argued equivalent (pin: duplicate-guard unload leaves no listener) | mutation survey + pin | `uv run pytest -q tests/test_startup_order.py -k test_pin_disarm_duplicate_guard_unload_leaves_no_registry_listener` (artifact: `mutation/pre-move.tsv` 28 rows, 0 unargued survivors, re-checked) | ✅ | ✅ green |
| 10-04-01 | 04 | 4 | FIX-02 (D-09, D-10) | T-10-05 | `NativeMigration` owns the cutover (timer, check, hint issue, roster delegation, stop); conftest patches the new module | integration (pure move, tracer) | `uv run pytest -q tests/test_cutover.py tests/test_cutover_instances.py tests/test_startup_order.py` | ✅ | ✅ green |
| 10-04-02 | 04 | 4 | FIX-02 (D-09, D-10) | T-10-05, T-10-06 | Takeover pass, unconfirmed-clear retry, replay catch with its gate and the duplicate guard move with unchanged order and conditions | integration (pure move) | `uv run pytest -q tests/test_native_replay.py tests/test_takeover.py tests/test_export_guard_receiver.py tests/test_native_start.py tests/test_discovery_export.py tests/test_native_cleanup.py tests/test_sync_owner.py tests/test_sync_follower.py tests/test_presence.py tests/test_startup_order.py` | ✅ | ✅ green |
| 10-04-03 | 04 | 4 | FIX-02 (D-10) | T-10-06 | AST audit per moved method; every moved-method mutant killed | AST audit + mutation (point-in-time) | `uv run python .planning/phases/10-.../mutation/move_audit.py --base 3bb3677^` (committed `move-audit.txt`: 28 PASS / 0 FAIL at `cbf5383`; at HEAD 24 PASS / 4 FAIL from the planned 10-05/10-09 edits); the two `mutation/post-move.tsv` survivors are now pinned: `uv run pytest -q tests/test_native_start.py -k "stays_legacy_until_the_reload or starts_clean_in_the_same_run"` (both fail under their mutant) | ✅ | ✅ green |
| 10-05-01 | 05 | 5 | FIX-06 | T-10-07, T-10-08 | A row raising mid-loop in the catch leaves no emptied device, keeps the partial count and still flushes | integration (tracer, TDD) | `uv run pytest -q tests/test_native_replay.py -k "raises_mid_loop_in_the_catch or owner_cleared_the_topic or follower"` | ✅ | ✅ green |
| 10-05-02 | 05 | 5 | FIX-06 (edge boundary, precision) | T-10-07, T-10-08 | Raise on the first row still flushes and keeps the device; only rows whose removal returned count; `ReplayTwinsError` carries the count | unit + integration | `uv run pytest -q tests/test_native_replay.py tests/test_takeover.py -k "first_row_still_flushes or counts_only_rows_whose_removal_returned or raises_with_the_partial_count"` | ✅ | ✅ green |
| 10-06-01 | 06 | 5 | FIX-04 (D-08) | T-10-09 | The guard listener ran for the second create event and returned 0 (spy, not only registry state) | integration (tracer, TDD) | `uv run pytest -q tests/test_export_guard_receiver.py -k second_create_event` | ✅ | ✅ green |
| 10-06-02 | 06 | 5 | FIX-04 (edge idempotency) | T-10-09 | After a restart the start-up sweep ran for the device and returned 0 | integration | `uv run pytest -q tests/test_export_guard_receiver.py` (incl. `-k never_nest`: two creates in one loop iteration run two deferred passes, none nested; fails if `call_soon` is replaced by a direct call) | ✅ | ✅ green |
| 10-07-01 | 07 | 5 | FIX-07 (D-07, D-08) | T-10-10 | The start-up takeover path removes a loaded, enabled replay row with no publish on the shared topic; pinned against core, never skipped | core contract (tracer, TDD) | `uv run pytest -q tests/test_core_contracts.py -k takeover_path_removes` | ✅ | ✅ green |
| 10-07-02 | 07 | 5 | FIX-07 (D-07, D-08) | T-10-10 | The replay catch removes loaded, enabled replay rows of a follower with no publish on the shared topic | core contract | `uv run pytest -q tests/test_core_contracts.py` | ✅ | ✅ green |
| 10-08-01 | 08 | 5 | FIX-05 | T-10-11 | README says a re-enabled duplicate is disabled again at the next start | docs (TDD) | `uv run pytest -q tests/test_docs.py -k readme_says_a_re_enabled_duplicate` | ✅ | ✅ green |
| 10-08-02 | 08 | 5 | FIX-05 | T-10-11 | Troubleshooting says the same | docs (TDD) | `uv run pytest -q tests/test_docs.py -k troubleshooting_says_a_re_enabled_duplicate` | ✅ | ✅ green |
| 10-09-01 | 09 | 6 | FIX-08 (D-01 to D-04) | T-10-12, T-10-13 | A customized duplicate kept enabled shows in one non-fixable Repairs warning (en/de) after a restart; the row is untouched | integration (tracer, TDD) | `uv run pytest -q tests/test_kept_duplicates.py tests/test_translations.py tests/test_export_guard_receiver.py tests/test_discovery_export.py` | ✅ | ✅ green |
| 10-09-02 | 09 | 6 | FIX-08 (D-01 to D-04) | T-10-12, T-10-13, T-10-14 | Warning follows the list (rejected twins, disappearance, dismissal, evaluation points, cap); guard and warning split the same candidates | integration + unit | `uv run pytest -q tests/test_kept_duplicates.py tests/test_takeover.py -k "kept_duplicates or warning or dismissal or split_the_guard_candidates or placeholders"` plus `uv run pytest -q tests/test_kept_duplicates.py -k "restored_inactive or raises or no_mqtt_entry"` (WR-02 branches) | ✅ | ✅ green |
| 10-10-01 | 10 | 7 | FIX-08 (D-02) | T-10-15 | Removing the hub deletes the kept-duplicates warning in both modes; placeholders pinned in en and de | integration (tracer, TDD) | `uv run pytest -q tests/test_hub_removal.py tests/test_translations.py` | ✅ | ✅ green |
| 10-10-02 | 10 | 7 | FIX-08 (D-02, D-03) | T-10-16 | README and troubleshooting describe the warning and advise disabling, not deleting | docs (TDD) | `uv run pytest -q tests/test_docs.py -k "kept_duplicates or every_issue_key"` | ✅ | ✅ green |
| 10-UAT-1 | 09/10 | — | FIX-08 (review WR-01) | T-10-14 | Owner decision on non-persistent warning (dismissal across restarts) | checkpoint:decision | n/a (passed UAT 2026-10-17; WR-01 still `open` in 10-REVIEW-DISPOSITION.md) | n/a | ⬜ manual |
| 10-UAT-2 | 09/10 | — | FIX-08 | T-10-13 | Repairs dialog renders the warning readably in en and de, no Fix button, goes away after disable + restart | bench (manual) | n/a (passed UAT 2026-10-17) | n/a | ⬜ manual |

*Status: ⬜ pending/manual · ✅ green · ❌ red · ⚠️ flaky*

Notes on point-in-time verify commands: the second `<automated>` block of most plans checks git history
(`git diff --quiet "$T^" HEAD -- custom_components/` since the plan's first test commit, commit numstat, RED evidence
JSON). These held when each plan ran and are not regression gates; several cannot pass at HEAD by design because later
plans changed `custom_components/`. The pytest commands above are the re-runnable part.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Kept-duplicates warning persistence across restarts (review WR-01) | FIX-08 (D-02) | Product decision, not a behavior gap | Record the decision in `10-REVIEW-DISPOSITION.md`; if `is_persistent=True`, update code, docs and `test_the_docs_describe_the_kept_duplicates_warning`. UAT item 1 passed 2026-10-17 |
| Repairs dialog rendering in en and de | FIX-08 | Tests pin placeholders and translation keys, not frontend rendering (Markdown escaping, the dash, count-1 wording IN-05) | Bench: one customized duplicate kept enabled and one next to a disabled native twin; open Settings > Repairs in both languages. UAT item 2 passed 2026-10-17 |

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Gaps Resolved

| task_id | requirement | gap_type | test added (`7e7a5ca`) | mutant evidence |
|---------|-------------|----------|------------------------|-----------------|
| 10-04-03 | FIX-02 (D-10, T-10-06) | MISSING | `tests/test_native_start.py::test_a_running_mirror_whose_owner_turns_native_stays_legacy_until_the_reload` | `defer_for_run` → `return None`: FAILED |
| 10-04-03 | FIX-02 (D-10, T-10-06) | MISSING | `tests/test_native_start.py::test_a_deferred_device_released_here_starts_clean_in_the_same_run` | `forget` → `return None`: FAILED |
| 10-09-02 | FIX-08 (D-02, T-10-14; review WR-02) | PARTIAL | `tests/test_kept_duplicates.py::test_an_issue_restored_inactive_and_dismissed_is_created_again_active_and_undismissed`, `::test_a_list_that_raises_leaves_the_warning_alone_and_logs_no_entity_id`, `::test_no_mqtt_entry_means_nothing_is_kept_and_the_warning_is_deleted` | drop `current.active and`: FAILED; drop `return` after except: ERROR; no-MQTT branch has no distinct mutant |
| 10-06-02 | FIX-04 (edge concurrency) | MISSING | `tests/test_export_guard_receiver.py::test_two_create_events_in_one_loop_iteration_schedule_two_passes_and_never_nest` | `call_soon(...)` → direct call: FAILED |

No implementation file changed (`git diff --exit-code custom_components/` clean). The 3a test pins the current
non-persistent behavior (`is_persistent` stays False); the WR-01 decision is still open in `10-REVIEW-DISPOSITION.md`.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (manual items: the two UAT checkpoints)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s (quick)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-10-17
