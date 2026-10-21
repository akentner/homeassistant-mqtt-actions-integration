---
phase: "11"
slug: "local-actions-on-mirrors"
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-17"
audited: "2026-10-21"
---

# Phase 11 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3, pytest-homeassistant-custom-component 0.13.367, Core 2026.9.4 |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest -q tests/test_core_contracts.py tests/test_repo_structure.py` |
| Unit tier | `uv run pytest -q -m "not broker and not multi_instance"` |
| Full suite command | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q` |
| Estimated runtime | Measure during execution; no unmeasured timing guarantee |

## Sampling Rate

- Before production changes (Plan 11-01), commit:
  - green characterization for unchanged hashes, adoption bytes and all fake-broker publications;
  - the green 24-case approval × local-mode × owner-actions oracle;
  - the green Core pins;
  - exactly one semantic RED target (see Expected-RED Exception).
- Every implementation task: run its focused behavioral tests, then relevant existing regressions. Every test-first task records the expected RED and subsequent GREEN evidence inside its own plan.
- Every wave: the complete unit tier is green, plus the applicable multi-instance and real-broker tests. The only allowed deviation is the single expected-RED target below, during its authorized interval and under its two-command gate. From the GREEN of Plan 11-05 Task 1 onward, every wave runs the complete unit tier unfiltered. No three consecutive tasks without an automated check.
- Phase gate: Ruff lint/format, required-broker full suite, applicable hassfest/HACS validation, and milestone-wide cross-file review with product fixes before Phase 12.
- Feedback latency: measure focused tests during execution and split slow feedback groups if needed.

## Expected-RED Exception

D-21 requires the invariant tests before production. A pure or runner test of the planned API cannot fail on an assertion before production exists; it would fail on import, which the TDD contract rejects. Plan 11-03 also keeps every existing runner path byte-identical. The authority behavior is therefore committed RED once, through current public Manager seams, and kept out of every module that an earlier plan must turn green.

| Property | Value |
|----------|-------|
| Target (exact node id) | `tests/test_local_actions_manager.py::test_pending_mirror_with_persisted_additive_record_gains_local_branch` |
| Planned failing assertion | Pending mirror plus persisted additive record: local mock service called once, owner service never. Current code calls neither. |
| Authorized by | Plan 11-01 Task 2 |
| Evidence | `.planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.xml` and `tdd/11-01-task2-red.json` (`RED_EVIDENCE_OK` plus `semanticAssessment`) |
| Interval | From the Plan 11-01 Task 2 commit through waves 1–3 (Plans 11-01, 11-02, 11-03, 11-04) until Plan 11-05 Task 1 |
| Expiry | Plan 11-05 Task 1 GREEN, with assertions unchanged (seeded-fixture alignment to the 11-04 schema only) and GREEN evidence in 11-05-SUMMARY.md |
| Not covered | Any other failing, erroring or skipped unit test. Each one fails the wave gate. |

Wave gate during the interval, both commands required:
- `uv run pytest -q -m "not broker and not multi_instance" --deselect "tests/test_local_actions_manager.py::test_pending_mirror_with_persisted_additive_record_gains_local_branch"` exits 0. All other unit tests are green.
- `bash -c 'uv run pytest -q "tests/test_local_actions_manager.py::test_pending_mirror_with_persisted_additive_record_gains_local_branch" 2>&1 | tail -n 1 | grep -Eq "^1 failed(, [0-9]+ warnings?)? in "'` succeeds. The target still fails, as exactly one failed test with no error.

The interval gate fails in these cases:
- The target turns green before Plan 11-05. That is unexpected green: investigate which plan moved Manager behavior early.
- The target errors instead of failing.
- A second test fails.
- `--deselect` appears in any gate after Plan 11-05 Task 1.

After expiry, the gate is the unfiltered `uv run pytest -q -m "not broker and not multi_instance"`.

## Per-Task Verification Map

The planner fills final task IDs, waves and threat references from PLAN frontmatter before the checker runs. Every MIR-01–MIR-15 requirement must appear below; commands reference files created by preceding test tasks.

| Task ID | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-T1 | MIR-04, MIR-10, MIR-14 | T-11-01 | Owner bytes and every publish exclude local content | characterization | `uv run pytest -q tests/test_local_invariants.py -k "hash or adoption or publication"` | New in phase | ✅ green |
| 11-01-T2 | MIR-02, MIR-05, MIR-11 | T-11-02 | Exact 24-case authority oracle exists green before feature code; the one Manager-backed target is semantic RED (expiry 11-05-T1) | oracle + semantic RED | `uv run pytest -q tests/test_local_action_plans.py` and `node /home/akentner/.codex/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/11-local-actions-on-mirrors/tdd/11-01-task2-red.json --raw` | New in phase | ✅ green |
| 11-01-T3 | MIR-03, MIR-13 | T-11-03 | Core parallel/trace contracts expose masked and continued errors | Core contract | `uv run pytest -q tests/test_local_parallel.py` | New in phase | ✅ green |
| 11-02-T1 | MIR-01, MIR-15 | T-11-04 | Real pinned frontend evidence exists | bench evidence | `test -s .planning/phases/11-local-actions-on-mirrors/11-FRONTEND-SMOKE.md` | New in phase | ✅ green |
| 11-02-T2 | MIR-01, MIR-15 | T-11-04 | Human verifies actual section/ActionSelector rendering | manual frontend | Human checkpoint in 11-02 | New in phase | ✅ manual (approved 2026-10-21) |
| 11-03-T1 | MIR-02, MIR-03 | T-11-05 | One Script runs separately validated owner/local branches | integration | `uv run pytest -q tests/test_local_parallel.py -k "one_additive or owner_only_guard"` | New in phase | ✅ green |
| 11-03-T2 | MIR-02, MIR-05, MIR-11 | T-11-06 | Identity, mute, orphan and 24-case plan behavior are pure | pure | `uv run pytest -q tests/test_local_action_plans.py` | New in phase | ✅ green |
| 11-03-T3 | MIR-03, MIR-13 | T-11-07, T-11-08 | Conservative per-branch outcomes cannot falsely clear | Core/integration | `uv run pytest -q tests/test_local_parallel.py tests/test_local_action_plans.py` | New in phase | ✅ green |
| 11-04-T1 | MIR-04, MIR-06, MIR-07 | T-11-09 | Separate Store migrates/loads strict records safely | storage | `uv run pytest -q tests/test_local_actions_store.py -k "round_trip or migrate or newer or malformed"` | New in phase | ✅ green |
| 11-04-T2 | MIR-04, MIR-06 | T-11-10, T-11-11 | Old-main saves, failures and other instances cannot alter records | storage | `uv run pytest -q tests/test_local_actions_store.py` | New in phase | ✅ green |
| 11-05-T1 | MIR-02, MIR-06 | T-11-12 | Overlay load precedes mirror restore and survives restart; 11-01 expected-RED target turns GREEN and the exception expires | integration + unit tier | `uv run pytest -q tests/test_local_actions_manager.py -k "load_before_mirrors or restart or persisted_additive_record"` then `uv run pytest -q -m "not broker and not multi_instance"` (unfiltered) | Created in 11-01, extended | ✅ green |
| 11-05-T2 | MIR-06, MIR-09 | T-11-13, T-11-15 | Locked immediate-save edits preserve old state on failure | integration | `uv run pytest -q tests/test_local_actions_manager.py -k "edit or remove or save_failure or idempotent or breaker"` | New in phase | ✅ green |
| 11-05-T3 | MIR-09, MIR-11 | T-11-12, T-11-14 | Safe local policy is coherent under edit/approval races | integration | `uv run pytest -q tests/test_local_actions_manager.py` | New in phase | ✅ green |
| 11-06-T1 | MIR-06, MIR-07 | T-11-16 | Owner evolution retains records; exact return reattaches | lifecycle | `uv run pytest -q tests/test_local_actions_lifecycle.py -k "survive or orphan or repin or kind"` | New in phase | ✅ green |
| 11-06-T2 | MIR-07, MIR-08 | T-11-16 | Prune retains; tombstone deletes even after prune | lifecycle | `uv run pytest -q tests/test_local_actions_lifecycle.py -k "prune or tombstone"` | New in phase | ✅ green |
| 11-06-T3 | MIR-08, MIR-12 | T-11-17, T-11-18, T-11-19 | Adoption discard is reported and rolls back on failure; existing adoption suites stay green | lifecycle/service | `uv run pytest -q tests/test_local_actions_lifecycle.py tests/test_multi_instance_ops.py tests/test_services.py -k adopt` | New/existing | ✅ green |
| 11-07-T1 | MIR-09, MIR-10 | T-11-20 | State/test/retrigger share effective gates and wire vocabulary | integration | `uv run pytest -q tests/test_local_actions_manager.py -k "test_button or retrigger" tests/test_retrigger.py` | New/existing | ✅ green |
| 11-07-T2 | MIR-03, MIR-13 | T-11-21, T-11-23 | Local issue clears only for exact proven recovery/removal | integration | `uv run pytest -q tests/test_local_parallel.py tests/test_local_actions_manager.py -k "issue or failure or clear"` | New in phase | ✅ green |
| 11-07-T3 | MIR-12 | T-11-22 | Approval count/text never changes owner authority | Repairs | `uv run pytest -q tests/test_local_actions_lifecycle.py tests/test_trust.py tests/test_repairs_flow.py` | New/existing | ✅ green |
| 11-08-T1 | MIR-01, MIR-15 | T-11-24 | Save/reopen flow is a thin Manager client | flow | `uv run pytest -q tests/test_local_actions_flow.py -k "save and reopen"` | New in phase | ✅ green |
| 11-08-T2 | MIR-05, MIR-07 | T-11-25, T-11-26 | Mute/remove/orphan/cancel semantics are explicit | flow | `uv run pytest -q tests/test_local_actions_flow.py` | New in phase | ✅ green |
| 11-08-T3 | MIR-12, MIR-15 | T-11-25 | en/de options and issue texts have exact parity | static | `uv run pytest -q tests/test_translations.py tests/test_local_actions_flow.py` | Mixed | ✅ green |
| 11-09-T1 | MIR-08, MIR-15 | T-11-28 | Both hub-removal modes delete local Store/issues; bilingual device-count warning | integration | `uv run pytest -q tests/test_hub_removal.py tests/test_translations.py` | Existing | ✅ green |
| 11-09-T2 | MIR-04, MIR-14 | T-11-27 | Diagnostics expose integers only, including orphans | diagnostics | `uv run pytest -q tests/test_diagnostics.py` | Existing | ✅ green |
| 11-10-T1 | MIR-02, MIR-06, MIR-09, MIR-10, MIR-11 | T-11-30, T-11-31, T-11-33 | Followers execute isolated local choices on one broker | multi-instance | `uv run pytest -q -m multi_instance tests/test_local_multi_instance.py` | New in phase | ✅ green |
| 11-10-T2 | MIR-04, MIR-08 | T-11-32 | All lifecycle publishes and native/shared-topic guards hold | regression | `uv run pytest -q tests/test_local_invariants.py tests/test_local_actions_lifecycle.py tests/test_core_contracts.py tests/test_native_replay.py tests/test_takeover.py tests/test_export_guard_receiver.py tests/test_sync_owner.py tests/test_sync_follower.py` | Mixed | ✅ green |
| 11-12-T1 | MIR-08, MIR-15 | T-11-29 | Docs are complete, name the adopt response key and do not claim deferred evidence | static | `uv run pytest -q tests/test_docs.py tests/test_diagnostics.py` | Existing | ✅ green |
| 11-12-T2 | MIR-15 | T-11-29 | Release draft is unpublished and keeps the downgrade round trip deferred | static | `test -s .planning/phases/11-local-actions-on-mirrors/11-release-notes.md` plus status-line/MIR-F4 greps in 11-12 | New in phase | ✅ green |
| 11-11-T1 | MIR-01–MIR-15 | T-11-34 | Cross-file review covers every decision/threat/path | review | `test -s .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md` plus header/path greps in 11-11 | New in phase | ✅ green |
| 11-11-T2 | MIR-01–MIR-15 | T-11-37 | Every product finding is NO-CHANGE with evidence or ROUTED to a bounded Phase 11 gap; none deferred to Phase 12 | review routing | ledger gate in 11-11 (no OPEN row; every ROUTED row has a G-NN gap) | New in phase | ✅ green |
| 11-14-T1 | MIR-13 | T-11-38, T-11-39 | Local failure issue survives restart, prune and failed adoption; it goes only on success, removal, saved tombstone discard, completed adoption or hub removal (G-01) | lifecycle | `uv run pytest -q "tests/test_local_actions_lifecycle.py::test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal"` | New (gap) | ✅ green |
| 11-14-T2 | MIR-13 | T-11-40 | Start deletes a local issue whose record is gone, only after a successful local load | lifecycle | `uv run pytest -q tests/test_local_actions_lifecycle.py` | Existing | ✅ green |
| 11-14-T3 | MIR-15 | T-11-38 | Troubleshooting states survival; ledger F-01 FIXED | static | `uv run pytest -q tests/test_docs.py` | Existing | ✅ green |
| 11-15-T1 | MIR-05, MIR-06 | T-11-41, T-11-42 | Refused local load raises one instance issue; file untouched; no overlay applied (G-02) | integration | `uv run pytest -q "tests/test_local_actions_manager.py::test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay"` | New (gap) | ✅ green |
| 11-15-T2 | MIR-15 | T-11-43 | en/de issue text without placeholders and troubleshooting entry; ledger F-02 FIXED | static | `uv run pytest -q tests/test_local_actions_manager.py tests/test_translations.py tests/test_docs.py` | Existing | ✅ green |
| 11-16-T1 | MIR-02 | T-11-44 | A new hub removes a leftover local Store before its entry exists (G-03) | flow | `uv run pytest -q "tests/test_hub_removal.py::test_new_hub_never_loads_local_actions_left_by_an_earlier_hub"` | New (gap) | ✅ green |
| 11-16-T2 | MIR-02, MIR-15 | T-11-45 | An existing hub's Store is never removed; a failed removal fails closed with an en/de error | flow | `uv run pytest -q tests/test_hub_removal.py tests/test_translations.py` | Existing | ✅ green |
| 11-16-T3 | MIR-15 | T-11-44 | README removal-under-1.0.1 sentence; ledger F-03 FIXED | static | `uv run pytest -q tests/test_docs.py` | Existing | ✅ green |
| 11-17-T1 | MIR-09 | T-11-46 | A failed adoption keeps a tripped breaker paused and saved (G-04) | lifecycle | `uv run pytest -q "tests/test_local_actions_lifecycle.py::test_failed_adoption_keeps_a_tripped_breaker_paused"` | New (gap) | ✅ green |
| 11-17-T2 | MIR-09 | T-11-46 | All tiers green; the ledger has no OPEN or ROUTED row | phase gate | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q` | Existing | ✅ green |
| 11-13-T1 | MIR-01–MIR-15 | T-11-35, T-11-36 | Precondition: no OPEN/ROUTED finding; Phase 11 suites, FIXED regression ids, Ruff/format, full required-broker suite, hassfest/HACS pass | phase gate | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q` | Existing | ✅ green (HACS 6b not run locally, see Manual-Only) |
| 11-13-T2 | MIR-01–MIR-15 | T-11-35 | Phase 12 boundary frozen; frontend verdict PASS; MIR-F4 deferred | handoff | ledger section greps in 11-13 | New in phase | ✅ green |

## Wave 0 Requirements

- [x] Permanent hash/adoption/publication invariants and all 24 matrix cases; no placeholder skip/xfail.
- [x] Parallel/trace pins: both failures, owner stop masking local failure, continued errors, response variables, cancellation, dropped and superseded runs.
- [x] Pure overlay identity, record validation, mute and orphan tests.
- [x] Separate Store migration/load/save-failure/removal tests with separate keys per test instance.
- [x] Lifecycle and flow regression suites, including tombstone after prune and adoption rollback.
- [x] Existing framework suffices; no framework installation planned.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Early section + ActionSelector rendering | MIR-01, MIR-15; D-20, D-22 | Backend schemas do not prove actual frontend rendering | Render minimal options form on actual target, record Core/frontend versions and screenshot, verify save/reopen/cancel before full editor expansion. |
| Full final-build cross-instance bench | Phase 12 / QLT-05 | Explicit phase boundary | Retain Phase 12 scope; do not mark it passed from Phase 11 probes. |
| HACS validation of this build | MIR-01–MIR-15 phase gate (11-13 gate 6b) | `hacs/action` fetches the repo from GitHub; the branch is not pushed yet | On the first push of `gsd/phase-11-local-actions-on-mirrors`, the `HACS` job of `validate.yml` must pass before Phase 12 release work. |
| Real downgrade round trip | MIR-F4 deferred | Explicit owner deferral | Do not claim executed; README/release notes warn approved owner actions may run again on v1.0.1. |

## Validation Sign-Off

- [x] Final task IDs and unique threat references assigned by planner.
- [x] Every runnable automated command has its own observable `fails_when` in the plan.
- [x] All referenced new test files have creation tasks before use.
- [x] Wave 0 RED evidence and subsequent GREEN results recorded.
- [x] Expected-RED exception used only for its exact node id. Its interval gate passed in waves 1–3, and it expired at Plan 11-05 Task 1 with GREEN evidence. No `--deselect` appears in any later gate.
- [x] Every finding routed by Plan 11-11 was FIXED by a Phase 11 gap-closure plan before Plan 11-13 ran.
- [x] No watch-mode checks or skipped regression substitutes.
- [x] Manual frontend evidence captured honestly.
- [x] Set `nyquist_compliant: true` only after validation actually passes.

**Approval:** approved 2026-10-21 (Nyquist audit: every per-task command re-run green; full required-broker suite 2072 passed, 2 pre-Phase-11 xfailed).

## Validation Audit 2026-10-21

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
