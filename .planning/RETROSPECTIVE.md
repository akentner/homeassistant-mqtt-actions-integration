# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-10-03
**Phases:** 5 | **Plans:** 42 | **Sessions:** not tracked

### What Was Built
- A HACS-installable integration where a Switch or Select created in the UI runs its actions locally on every instance sharing the MQTT broker.
- Retained, hash-stamped config documents with owner/follower ownership and an approval gate: remote actions run only after the user approves the exact hash.
- Operating tools: roster and heartbeat, resync, export/import, diagnostics, re-trigger service, adoption of an offline owner's devices.
- Native entities as the default, with a takeover migration that keeps every registry identity and an optional Discovery export (ADR 0001).
- Three test tiers (unit, real Mosquitto, multi-instance) and a tag-triggered release workflow. Last full run: 1458 passed, 1 known load-dependent flake.

### What Worked
- Pinning real core behavior with tests before building on it (takeover order against real core MQTT discovery) made the one-way migration safe to ship.
- A blocking human gate (ADR 0001, Go) before the irreversible migration code.
- Code review after Phase 5 found a critical issue (CR-01, adopting a native mirror deleted its entities) before release; the findings were fixed or consciously accepted with a recorded disposition.
- A threat register in every plan made the final security audit a verification pass (19 of 19 closed) instead of a discovery exercise.

### What Was Inefficient
- Phase 5 started as backlog item 999.2 and changed the Discovery contract of Phases 1 to 4. Their verification went `stale` as a result, and the milestone had to close with an override.
- UAT tests 4 to 7 of Phase 5 (real mixed fleet, late replay race, cross-instance commands, export on/off) were skipped, so the riskiest cutover paths rest on automated tests only.
- The `[ci skip]` ship note ended up in the squash-merge message and silently suppressed the tag-triggered release run, which cost an extra commit and a re-tag.
- Fish-specific quirks of the GSD shell snippets (`echo =====`) broke combined commands more than once.

### Patterns Established
- Native entities with `unique_id` unchanged and registry takeover in a fixed order: entities first, device second, companion last.
- Additive, unhashed markers in the config document for capability negotiation, so older readers ignore them by construction.
- Docs claims pinned by executable tests (`tests/test_docs.py`).
- Release by tag: `release.yml` checks the manifest version and requires every tier plus hassfest and HACS.

### Key Lessons
1. Never let `[ci skip]` reach the default branch's head commit when a tag-triggered workflow must run; a squash merge copies it from the PR commits.
2. A change to a shared contract (Discovery to native) should re-verify earlier phases at once, otherwise the milestone close inherits `stale` verification.
3. Skipped UAT on a one-way migration is debt with interest: schedule the mixed-fleet checks before the next release.
4. Record accepted review residuals (WR-03, IN-02, IN-03) in README Limitations and in the security accepted-risks log, so they stay visible after the milestone is archived.

### Cost Observations
- Model mix: not tracked
- Sessions: not tracked
- Notable: 327 commits in 6 days, strict TDD (test commit before implementation commit).

---

## Milestone: v1.0.1 — Hardening

**Closed:** 2026-10-11 (accepted gap ACCEPTED-GAP-V101, not released)
**Phases:** 3 | **Plans:** 25

### What Was Built
- Native flag of a mirror as a sticky id set in the Store (MIG-04) and a registry-only replay catch (MIG-05).
- All CI, Validate and Release jobs pinned to `ubuntu-24.04`; the flake class fixed at its cause (unscoped `caplog`).
- The four skipped Phase 5 UAT checks plus ten deferred Phase 1 to 3 human checks run on a real three-instance bench.
- A duplicate guard on every native instance that disables, never removes, core-prefix duplicates and keeps user-customized rows.

### What Worked
- The real bench found a product defect no automated tier could: UAT-04 failed twice on the receiver before the guard covered it.
- TDD held through the late fixes: every review finding got a failing-test commit first, and the fixer ran the new tests against the old code.
- A second, deep code review on the fix commits found a Critical (CR-01) that the first review had rated as a warning.

### What Was Inefficient
- Phase 8 grew from 10 to 18 plans through two gap-closure rounds; a "verification only" phase ended up carrying product fixes under a waiver (D-08).
- The late review fixes made every verification report stale again, so the milestone closed with an accepted gap instead of a clean re-run.
- Phase 7's QLT-01 depended on human checks that the Phase 8 success criteria did not name until later.

### Patterns Established
- Disable, do not remove, registry rows that core MQTT may own: a removal can make core clear a foreign retained topic.
- Verify HA-internal assumptions against the installed core source before fixing; report deviations instead of implementing them (D1 to D3).
- Owner decisions get an ID and a verbatim quote in the ledger (UAT04-GAP-DISPOSITION, D08-WAIVER, ACCEPTED-GAP-V101).

### Key Lessons
- Keep product fixes out of verification phases, or plan a re-verification step after them from the start.
- Run the deep cross-file review before the bench re-run, not after it, so the bench evidence covers the final code.

### Cost Observations
- Model mix: not tracked
- Sessions: not tracked
- Notable: 177 commits in 9 days; tests grew from 1458 to 1535.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | n/a | 5 | TDD with per-plan threat models, human gate before one-way migration |
| v1.0.1 | n/a | 3 | Real three-instance bench, owner decisions with IDs, second deep review on fix commits |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 1458 passed (1 known flake) | not measured | 0 runtime dependencies |
| v1.0.1 | 1535 passed, 2 strict xfail, flake fixed | not measured | 0 runtime dependencies |

### Top Lessons (Verified Across Milestones)

1. Real-instance checks find what the test tiers miss (v1.0 Phase 5 UAT debt, v1.0.1 UAT-04 receiver gap); plan bench time, do not defer it.
2. Verification goes stale when code changes after it; order fixes before the final verification (v1.0 stale Phases 1 to 4, v1.0.1 accepted gap).
