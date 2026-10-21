---
phase: 11-local-actions-on-mirrors
plan: 13
subsystem: testing
tags: [phase-gate, review-ledger, hassfest, hacs, broker-tests, handoff]
status: complete

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-11 review ledger (F-01 to F-20, gaps G-01 to G-04); gap-closure plans 11-14, 11-15, 11-16 and 11-17 that set F-01 to F-04 to FIXED; 11-02 frontend smoke (Verdict: PASS)"
provides:
  - "## Final Gate section in 11-CROSS-FILE-REVIEW.md: exact commands, exit codes and measured counts for every tier on 9bec171"
  - "## Phase 12 Boundary section in 11-CROSS-FILE-REVIEW.md: Phase 11 evidence and what stays with Phase 12 and MIR-F4"
  - "Open item: HACS validation of this build runs on the first push of the branch"
affects: [phase-12 re-verification and v1.1.0 release, /gsd-verify-work 11]

actuals:
  tokens: 2500
  tasks: 2
  commits: 2
plan_head_before: 9bec171f1bb70c9a8b22240772c2bd8cf4315f2f
plan_head_after: 63fd955227a4a26c6b33dd0d77437957f8c255d4

tech-stack:
  added: []
  patterns:
    - "Phase gate records the exact command, exit code and pass/fail/skip/xfail count per tier, and checks that the tiers add up to the full suite"

key-files:
  created: []
  modified:
    - .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md

key-decisions:
  - "HACS validation is recorded as NOT RUN on this build: hacs/action fetches the repository from the GitHub API at a ref, and the branch is not pushed (pushing is the user's job). The passing scheduled Validate run on main at the merge base 3dc9093 is cited as supporting evidence only, and the user's personal token was not passed to the third-party container"
  - "hassfest ran locally through podman with the same image the workflow action uses (ghcr.io/home-assistant/hassfest), as in Phases 1, 2 and 4"
  - "The real HubOptionsFlow menus, pickers and confirmations (11-08 coverage D6) are not covered by the 11-02 smoke; the boundary assigns them to the human UAT of Phase 11, not to backend tests"

patterns-established: []

requirements-completed: [MIR-01, MIR-02, MIR-03, MIR-04, MIR-05, MIR-06, MIR-07, MIR-08, MIR-09, MIR-10, MIR-11, MIR-12, MIR-13, MIR-14, MIR-15]

coverage:
  - id: D1
    description: "Phase 11 targeted suites, the four FIXED regression ids, Ruff lint and format, unit and multi_instance tiers and the required-broker full suite pass on the final Phase 11 code with no new skip or xfail and no --deselect"
    requirement: MIR-01
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_local_action_plans.py tests/test_local_parallel.py tests/test_local_actions_store.py tests/test_local_actions_manager.py tests/test_local_actions_lifecycle.py tests/test_local_actions_flow.py tests/test_local_invariants.py tests/test_local_multi_instance.py (exit 0, 265 passed)"
        status: pass
      - kind: other
        ref: "uv run ruff check . && uv run ruff format --check . (exit 0)"
        status: pass
      - kind: integration
        ref: "MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q (exit 0, 2072 passed, 2 xfailed, 0 skipped)"
        status: pass
    human_judgment: false
  - id: D2
    description: "hassfest validation of this build"
    verification:
      - kind: other
        ref: "podman run --rm --pull=always -v <repo>:/github/workspace:Z --workdir /github/workspace ghcr.io/home-assistant/hassfest (exit 0, Invalid integrations: 0)"
        status: pass
    human_judgment: false
  - id: D3
    description: "HACS validation of this build"
    verification:
      - kind: other
        ref: "validate.yml job HACS (hacs/action 22.5.0) on the first push of gsd/phase-11-local-actions-on-mirrors"
        status: unknown
    human_judgment: true
    rationale: "Not run: the HACS action validates the repository on GitHub at a ref, and this branch is not pushed yet. Someone must confirm the HACS job result after the user's push"
  - id: D4
    description: "Phase 12 boundary frozen in the ledger: Phase 11 evidence, frontend verdict as recorded, review dispositions, and the deferral of the final-build bench, re-verification, release and MIR-F4"
    requirement: MIR-15
    verification:
      - kind: other
        ref: "bash -c 'f=.planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md; grep -q \"^## Final Gate\" \"$f\" && grep -q \"^## Phase 12 Boundary\" \"$f\" && grep -q MIR-F4 \"$f\" && grep -Eq \"^Verdict: PASS$\" .planning/phases/11-local-actions-on-mirrors/11-FRONTEND-SMOKE.md && ! grep -Eq ...OPEN|ROUTED... \"$f\"' (exit 0)"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-10-21
---

# Phase 11 Plan 13: Final Phase 11 Gate and Phase 12 Handoff Summary

**On 9bec171 every automated tier passes (2072 passed, 2 pre-Phase-11 xfails, 0 skipped under the required-broker flag), Ruff and hassfest are clean, HACS is an honest NOT RUN open item, and the ledger freezes what Phase 12 and MIR-F4 still owe.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-10-21T05:03:53Z
- **Completed:** 2026-10-21T05:12:57Z
- **Tasks:** 2
- **Files modified:** 1

## Gap-closure plans that ran before this gate

| Plan | Gap | Finding | Fix commit | Regression test (passed in this gate) |
|------|-----|---------|------------|----------------------------------------|
| 11-14 | G-01 | F-01 local failure issue lifecycle | `6f381cb` | `tests/test_local_actions_lifecycle.py::test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal` |
| 11-15 | G-02 | F-02 unreadable local Store is visible | `44c5fe6` | `tests/test_local_actions_manager.py::test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay` |
| 11-16 | G-03 | F-03 no leftover local Store on a new hub | `c9c9c63` | `tests/test_hub_removal.py::test_new_hub_never_loads_local_actions_left_by_an_earlier_hub` |
| 11-17 | G-04 | F-04 failed adoption keeps a tripped breaker | `8eb4734` | `tests/test_local_actions_lifecycle.py::test_failed_adoption_keeps_a_tripped_breaker_paused` |

## Final gate results

Precondition: `! grep -Eq "\| (Critical|High|Medium|Low) \| (OPEN|ROUTED) \|"` on the ledger exits 0 (F-01 to F-04 FIXED, F-05 to F-20 NO-CHANGE).

| # | Gate | Exit | Result |
|---|------|------|--------|
| 1 | Phase 11 targeted suites (8 modules, plan command verbatim) | 0 | 265 passed |
| 2 | Four FIXED regression ids | 0 | 4 passed |
| 3a | `uv run ruff check .` | 0 | All checks passed |
| 3b | `uv run ruff format --check .` | 0 | 111 files already formatted |
| 4a | `uv run pytest -q -m "not broker and not multi_instance"` | 0 | 1874 passed, 198 deselected, 2 xfailed |
| 4b | `uv run pytest -q -m multi_instance` | 0 | 180 passed, 1894 deselected |
| 5 | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q` | 0 | 2072 passed, 2 xfailed, 0 skipped |
| 5b | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q -m broker` | 0 | 18 passed |
| 6a | hassfest container (podman, `ghcr.io/home-assistant/hassfest`) | 0 | Integrations: 1, Invalid integrations: 0 |
| 6b | HACS (`hacs/action` 22.5.0) | n/a | NOT RUN on this build |

- The tiers add up: 1874 + 180 + 18 = 2072 passed.
- The 2 xfails are the `[entity_id_rename]` cases in `tests/test_takeover.py`, marked in `4bc91d8` (Phase 8).
- `git diff 762a3db..HEAD -- tests/` adds no skip or xfail marker, and no gate uses `--deselect`.
- Environment: Python 3.14.8, HA 2026.9.4, PHACC 0.13.367, Ruff 0.16.10, mosquitto 2.1.2. `uv lock --check` exits 0.

## Phase 12 boundary

- **Phase 11 proved:** all automated tiers on the final Phase 11 code, hassfest, the 11-02 frontend smoke (`Verdict: PASS`, en and de, approved by the user; scope is the section and the ActionSelector on a disposable form), and 20 review dispositions (4 FIXED, 16 NO-CHANGE, none open, routed or deferred).
- **Stays with Phase 12:** the final-build cross-instance bench (QLT-05), the full historical re-verification (QLT-01), the 1.1.0 bump with UAT-02 and UAT-04 on that SHA (QLT-04), and the tag, release, hassfest and HACS runs of v1.1.0 (REL-02).
- **Stays deferred (MIR-F4):** the real v1.1 → v1.0.1 → v1.1 downgrade round trip.
- **Open before Phase 12 release work:** the `HACS` job on the first push of this branch, and the human look at the real options menus (11-08 coverage D6) in the Phase 11 UAT.

## Task Commits

1. **Task 1: Run the complete Phase 11 quality/security gate on the fixed code** - `6dcd5f3` (docs)
2. **Task 2: Freeze the honest Phase 12 handoff** - `63fd955` (docs)

## Files Created/Modified

- `.planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md` - new `## Final Gate` and `## Phase 12 Boundary` sections

## Decisions Made

See `key-decisions` in the frontmatter: HACS recorded as NOT RUN with an open item, hassfest via podman, real-menu frontend look assigned to the Phase 11 UAT.

## Deviations from Plan

### Acceptance item not met

**1. [Not run] HACS validation of this build**
- **Found during:** Task 1, step 6
- **Issue:** The plan's acceptance criterion requires hassfest and HACS to both exit zero. The pinned `hacs/action` image (`ghcr.io/hacs/action:main`) does not read the local workspace. Its entry point (`action/action.py` in `hacs/integration`) fetches the repository from the GitHub API at a ref and needs a token. `origin` has no `gsd/phase-11-local-actions-on-mirrors` branch, and pushing is the user's job.
- **What was done:** No local run. The user's personal GitHub token was not passed to the third-party container. Supporting evidence was recorded instead: the scheduled Validate run 39532934013 on `main` at the merge base `3dc9093` passed `hassfest` and `HACS`, and `hacs.json`, `manifest.json` and `brand/` are unchanged since then (only README text and workflow triggers changed).
- **Follow-up:** The `HACS` job of `validate.yml` must pass on the first push of this branch, before Phase 12 starts release work. Recorded in the ledger and in WINDOWS.md as an unrun verify.
- **Commit:** `6dcd5f3`

**Total deviations:** 1 (an acceptance item not run, no code change). **Impact:** every runnable gate passed. HACS stays open until CI runs it on the pushed branch.

## Issues Encountered

None besides the HACS deviation above.

## Next Phase Readiness

- Phase 11 has 17/17 summaries after this plan. Next: `/gsd-verify-work 11` (includes the D6 real-menu look), then the user pushes the branch and checks the `HACS` job.
- Phase 12 receives `9bec171` code (last code commit `8eb4734`) with the boundary in `11-CROSS-FILE-REVIEW.md`.

## Self-Check: PASSED

- FOUND: `.planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md` with `## Final Gate` and `## Phase 12 Boundary`
- FOUND: commit `6dcd5f3`, commit `63fd955` (ancestors of HEAD)
- Task 2 verify command exits 0; precondition grep still exits 0
- Exception, not a pass: HACS validation of this build is NOT RUN (see Deviations)
