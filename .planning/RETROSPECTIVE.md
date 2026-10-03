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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | n/a | 5 | TDD with per-plan threat models, human gate before one-way migration |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 1458 passed (1 known flake) | not measured | 0 runtime dependencies |

### Top Lessons (Verified Across Milestones)

1. (Single milestone so far, lessons to be cross-checked after v1.1.)
