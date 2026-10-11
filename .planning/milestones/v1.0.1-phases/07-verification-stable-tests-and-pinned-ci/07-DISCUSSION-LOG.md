# Phase 7: Verification, Stable Tests and Pinned CI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-04
**Phase:** 7-Verification, Stable Tests and Pinned CI
**Areas discussed:** Re-verification of Phases 1-4, Flake cause and fix strategy, Pinned runner, Proof (3 runs and prerelease tag)

---

## Re-verification of Phases 1-4

| Option | Description | Selected |
|--------|-------------|----------|
| gsd-verifier per phase | Agent re-runs against current code, regenerates report and digest | ✓ |
| Only stale reports | Re-verify only phases reported stale | |
| Edit frontmatter by hand | No real check | |

**User's choice:** gsd-verifier per phase
**Notes:** Location: overwrite in the archive (`milestones/v1.0-phases/`), not side-by-side files, not reviving phase dirs. Gaps: mark superseded, fix real regressions. Human items: automated coverage suffices, real instances stay in Phase 8.

---

## Flake cause and fix strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Reproduce under load, then cause | Find the cause first | ✓ |
| Read code and fix hypothesis | Unproven fix | |

**User's choice:** Reproduce under load, then cause; fix where the cause lives; deterministic repro test first if possible; 50 stress repetitions.
**Notes:** Test alone passed 25/25 during discussion.

---

## Pinned runner

| Option | Description | Selected |
|--------|-------------|----------|
| ubuntu-24.04 | Same as presumed ubuntu-latest | ✓ |
| ubuntu-22.04 | Older, changes Mosquitto version | |
| ubuntu-26.04 or newer | Newer image risk | |

**User's choice:** ubuntu-24.04, guarded by a test in the suite.
**Notes:** That `ubuntu-latest` resolves to 24.04 was an assumption, to be verified in research.

---

## Proof (3 runs and prerelease tag)

**User's choice:** 3 runs both locally and in CI; prerelease `v1.0.1-rc1` with manifest `1.0.1-rc1`; push only after explicit approval, delete prerelease and tag afterwards.

---

## Claude's Discretion

Load generation for the flake reproduction, plan split and order, guard test format, how CI results are recorded.

## Deferred Ideas

None
