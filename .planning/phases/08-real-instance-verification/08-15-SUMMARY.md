---
phase: 08-real-instance-verification
plan: 15
subsystem: verification-gap-closure
tags: [final-gate, verifier, archived-reports, stale-anchor, bench-state, uat-04]
requires:
  - phase: 08-real-instance-verification
    provides: ledger complete (14 of 14 pass), guard-and-document disposition, receiver-guard build b8232252540a55969145ca0034d8fd86b4be3b7c (plans 08-14, 08-16 to 08-18)
provides:
  - check-final.sh amended (resolved Gaps entries, first-token verdict compare, verification-status assertion, amended --commit-shape allow-list)
  - stale-anchor-final.txt, bench-state-final.txt and the scrubbed bench-scripts copy current for the gap closure
  - archived Phase 1 to 4 reports re-run by gsd-verifier, all read passed
  - Phase 8 report re-verified, reads passed (UAT-04 gap closed, no pruned-state qualifier)
  - 08-15 ticked in ROADMAP.md (18 of 18), three 08-15 rows filled in 08-VALIDATION.md
affects: [phase-08-verification, milestone-v1.1-close]
coverage:
  - id: D1
    description: "Final gate understands a resolved Gaps entry and a qualified verdict; anchor file, bench state and script copy current and clean"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-final.sh --pre, check-stale-anchor.sh, check-evidence-clean.sh (PASS), check-uat04-iso.sh disposition (guard-and-document)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Archived Phase 1 to 4 reports and the Phase 8 report read passed with fingerprints from the verifier run"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-final.sh (full, PASS) and verification status of the five phase directories (passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Last commit shape is only reports, ROADMAP.md and the validation map; no product, test or workflow file changed in this plan"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-final.sh --commit-shape (PASS) and git log --grep='(08-15)' over custom_components tests .github pyproject.toml uv.lock (empty)"
        status: pass
    human_judgment: false
actuals:
  tokens: 69000
  tasks: 3
  commits: 2
tech-stack:
  added: []
  patterns:
    - "reports re-run by the verifier after a product change, never digest-refreshed by hand (D-06, T-08-42)"
    - "ledger frozen once the verifiers ran: facts of the refresh live in the reports and the SUMMARY"
key-files:
  created: []
  modified:
    - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-VERIFICATION.md
    - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-VERIFICATION.md
    - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-VERIFICATION.md
    - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-VERIFICATION.md
    - .planning/phases/08-real-instance-verification/08-VERIFICATION.md
    - .planning/phases/08-real-instance-verification/08-VALIDATION.md
    - .planning/ROADMAP.md
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/stale-anchor-final.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-state-final.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/README.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/check-final.sh
key-decisions:
  - "All four archived reports were re-run by the verifier (path A) because the guard build changed product code and tests since the pinned sha b7f52b34; zero digest refreshes by hand"
  - "08-UAT.md not edited after the verifiers ran, so no digest went stale"
  - "Phase checkbox in ROADMAP.md left to the orchestrator's roadmap tooling, as the plan directs"
requirements-completed: [UAT-01, UAT-02, UAT-03, UAT-04]
duration: not measured
completed: 2026-10-11
status: complete
commits: 2
plan_head_before: 7b2bedc5d57c6c8a17ac2e6f5c8480fff25d986a
plan_head_after: 36d8f95762bc0dc64ce8177019f3bad874dcac70
---

# Phase 8 Plan 15: Final gate, archived report refresh and Phase 8 re-verification Summary

**The final gate (`check-final.sh`) now reads a resolved gap, and with it every report reads `passed`: Phases 1 to 4 re-run by the verifier, Phase 8 re-verified with the UAT-04 gap closed on the receiver-guard build, ROADMAP at 18 of 18 plans.**

## What was done

- **Task 1 (f65a174), gate, anchor, bench state:**
  - `check-final.sh`: Gaps rule accepts a `resolved` entry whose block is `pass` and that carries a `resolution:` line; `--commit-shape` allows the four archived reports, `08-VERIFICATION.md`, `ROADMAP.md` and `08-VALIDATION.md` (at most seven files, owner's `.planning/config.json` modification tolerated); full mode asserts `verification status` of Phase 8 reads `passed` exactly when no block is an issue and every Gaps entry is resolved; verdict cells are compared by their first token.
  - `stale-anchor-final.txt`, `bench-state-final.txt` (gap-closure leftovers and removal commands) and the scrubbed `bench-scripts/` copy (README line, current `check-final.sh`) refreshed; `check-evidence-clean.sh` PASS over the copy and the whole evidence tree.
- **Task 2 (orchestrator-run checkpoint, answered `done`):**
  - Path A: `git diff --stat b7f52b34 HEAD -- custom_components tests .github` was non-empty (guard build), so the gsd-verifier agent re-ran Phases 1, 2, 3 and 4. Phase 8 re-verified in re-verification mode (previous score 5/6, now 6/6).
  - Result: 01 passed (8/8), 02 passed (10/10), 03 passed (5/5), 04 passed (5/5), 08 passed (6/6, gaps none). Digest refreshes by hand: 0.
- **Task 3 (36d8f95), gate and commit:**
  - `check-final.sh` (full): PASS; Phase 1 to 4 and Phase 8 reports read `passed`; stale anchor empty; evidence tree and script copy clean.
  - ROADMAP.md: 08-15 ticked, Plans line 18/18, progress row 18/18 (scoped edit; phase checkbox left to tooling). 08-VALIDATION.md: the three 08-15 rows filled green.
  - Committed the five reports, ROADMAP.md and 08-VALIDATION.md as `docs(08-15): refresh the verification reports after the UAT-04 gap closure`.

## Verification

- `check-final.sh` PASS (full), run before and again after the commit.
- `check-final.sh --commit-shape` PASS: last commit (36d8f95) holds 7 files, all allowed; no Phase 1 to 5 directory under `.planning/phases/`; working tree clean apart from `.planning/config.json`.
- `check-uat04-iso.sh disposition` prints `guard-and-document`; `check-stale-anchor.sh` PASS.
- `git log --format=%H --grep='(08-15)' -- custom_components tests .github pyproject.toml uv.lock` prints nothing: no code, test, workflow or manifest file changed in this plan.

## Deviations from Plan

None - plan executed as written. `.planning/config.json` carries the owner's unrelated modification and was never staged. The validation rows for 08-15-T3 were filled before `--commit-shape` ran against the new commit and verified green right after; the SUMMARY and metadata commit that follow are outside the `--commit-shape` window by design (the gate checks the report commit).

## Known Stubs

None.

## Threat Flags

None. T-08-42 mitigated (verifier re-run, no hand-written digest or status); T-08-43 mitigated (script copy and evidence tree scanned clean).

## Self-Check: PASSED

- Commits `f65a174` and `36d8f95` are in the branch.
- The five reports, `ROADMAP.md`, `08-VALIDATION.md` and the evidence files exist; `check-final.sh` PASS.
