---
phase: 07-verification-stable-tests-and-pinned-ci
plan: 05
subsystem: verification
tags: [verification, gsd-verifier, covered-digest, qlt-01, human-needed]

requires:
  - phase: 07-04
    provides: "release proof and the clean frozen tree the verifiers judged"
provides:
  - "Regenerated archived VERIFICATION.md for Phases 1 to 4 with v2 covered_digest over archived paths"
  - "Phase 4 reads passed; Phases 1 to 3 read human_needed (no gaps_found anywhere)"
  - "Ledger section 'QLT-01 re-verification (plan 07-05)' with before/after table, superseded items and the ten open human items"
affects: [phase-08-uat, qlt-01]

actuals:
  tokens: 10500
  tasks: 3
  commits: 2

plan_head_before: 81db888c5e49389ea7dc27626100f6e090535e61
plan_head_after: a590aa0989ce0111a1d23cf4db97a9dda583214b

tech-stack:
  added: []
  patterns:
    - "verification status on the archived directory is the gate; init.manager never listed Phases 1 to 4"

key-files:
  created: []
  modified:
    - .planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-VERIFICATION.md
    - .planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-VERIFICATION.md
    - .planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-VERIFICATION.md
    - .planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-VERIFICATION.md
    - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md

key-decisions:
  - "Owner decision 2026-10-04: the open human-verification items of Phases 1 to 3 are deferred to Phase 8 (UAT); they are not accepted as overrides and no report was edited to read passed"

requirements-completed: []

status: partial
---

# Phase 7 Plan 05: Re-verify Phases 1 to 4 Summary

**Gate NOT fully met: `verification status` now prints human_needed, human_needed, human_needed, passed for Phases 1 to 4 (before: stale for all four). No truth regressed (no `gaps_found`), but ten checks that need a real frontend, HACS client or real HA plus broker remain open for Phases 1 to 3 and were deferred to Phase 8 by owner decision, not overridden.**

## Outcome

| Phase | Before | After | Score | Covered files | Overrides (superseded by Phase 5) | Open human items |
|-------|--------|-------|-------|---------------|-----------------------------------|------------------|
| 1 | stale | human_needed | 8/8 | 54 | 1 | 6 |
| 2 | stale | human_needed | 10/10 | 46 | 1 | 2 |
| 3 | stale | human_needed | 5/5 | 83 | 1 | 2 |
| 4 | stale | passed | 5/5 | 102 | 2 | 0 |

- The stale cause (covered_files naming pre-archive `.planning/phases/` paths) is fixed in all four: each report lists archived paths only, carries a `covered_digest: "v2:sha256:..."` line, and no longer reads stale. The four statuses were re-checked after the commit and are unchanged.
- Frozen sha judged by the verifiers: `81db888c5e49389ea7dc27626100f6e090535e61`.
- `init.manager` lists phases 6 (passed), 7, 8 and 999.1 (missing); no phase is stale. It never listed Phases 1 to 4, so it was never the gate.
- No phase directory for Phases 1 to 5 exists under `.planning/phases/`; no side-by-side file; no code, test, workflow or manifest file was changed by this plan.

## QLT-01 gate status: not fully met

Plan acceptance required `passed` for all four. Met for Phase 4 only. Phases 1 to 3 are `human_needed` because the verifier found checks only a real HA frontend, a real HACS client, or a real HA core with a real retaining broker can perform, and Phase 8 (UAT-01 to UAT-04) does not name them. The owner decided on 2026-10-04 to defer these items to Phase 8. They are not accepted as overrides and the reports were not edited. The full list with the tests each cites is in `07-PROOF.md`, section "QLT-01 re-verification (plan 07-05)".

Items deferred to Phase 8 (ten):
- Phase 1: HACS install on a real host; EN/DE strings in the real frontend; action editor and validation banners; Repairs dialog of a failing action; retained-versus-live chain with real core MQTT client and real broker (UI toggle, full restart, broker reconnect); core version of the second host (informational).
- Phase 2: Select subentry flow in the real frontend (EN/DE); breaker loop against real Mosquitto and a real HA process with the rendered Repairs card.
- Phase 3: approval-request Markdown rendering in the real frontend; device delete dialogs in the real frontend.

Phase 8's own scope or an owner decision should name these ten checks. Until then Phases 1 to 3 stay `human_needed`, and success criterion 1 of Phase 7 and requirement QLT-01 are only partially satisfied (hence `requirements-completed: []`).

## Superseded by Phase 5 (D-03)

Five overrides across the four reports, each citing ADR 0001 and the tests that prove the new native behavior and the intact legacy path (Phase 1: Discovery creates the switch; Phase 2: test-button lifecycle; Phase 3: owner heals a removed discovery entity; Phase 4: resync republishes discovery, and the companion device). Details and cited tests are in the ledger.

## Task Commits

1. **Task 1:** `ad98080` docs(07-05): record the before state of the Phase 1 to 4 verification
2. **Task 2:** four `gsd-verifier` runs by the orchestrator (no commit of their own; reports left in the working tree)
3. **Task 3:** `a590aa0` docs(07-05): re-verify phases 1 to 4 against the final code (four reports and the ledger)

The `commits:` count of 2 is measured with `git rev-list --count ${plan_head_before}..${plan_head_after}`; the commit of this SUMMARY follows `plan_head_after`.

## Deviations from Plan

- **Task 3 acceptance not met (owner-decided, not a defect):** the plan expected four `passed` readings. Three phases read `human_needed`, and the owner chose to defer the open items to Phase 8 instead of accepting overrides or adding tests in this plan. Documented here and in the ledger; no frontmatter was edited to change a status.
- Task 2 was performed by the orchestrator as planned (checkpoint contract), not by the executor.
- The plan's second automated check (`git show --name-only HEAD` has exactly 5 files, tree clean) held for commit `a590aa0`: exactly the four reports and the ledger.

## Known Stubs

None.

## Threat Flags

None. The plan changed only planning artifacts; no new endpoints, auth paths or file access.

## Later edits

An edit of a file covered by a Phase 1 to 4 report (`tests/conftest.py`, `tests/test_repo_structure.py`, `tests/test_manager_breaker.py`, `tests/test_hub_removal.py`, the three workflows, `manifest.json`) turns that phase stale; refresh the digest from `verification.fingerprint` with a dated note and re-check. The real 1.0.1 manifest bump at milestone close will stale Phase 1.

## Self-Check: PASSED

- Four reports and the ledger exist and are committed in `a590aa0`.
- `ad98080` and `a590aa0` found in `git log`.
- `verification status` after the commit: human_needed, human_needed, human_needed, passed.
