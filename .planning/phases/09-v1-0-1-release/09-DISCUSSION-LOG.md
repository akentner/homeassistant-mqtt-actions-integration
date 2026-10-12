# Phase 9: v1.0.1 Release - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-12
**Phase:** 09-v1-0-1-release
**Areas discussed:** Branch strategy, Bench scope and start state, Release notes, Evidence and gap closure

---

## Branch strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Freeze main | Bump, bench and tag on main; Phase 10 starts after the tag | ✓ |
| release/1.0.1 branch | Branch off HEAD, tag there, merge back to main | |

| Option | Description | Selected |
|--------|-------------|----------|
| Tag the bump commit | Tag SHA == bench SHA; evidence commits come after | ✓ |
| Tag the last docs commit | Same product code, different SHA, needs justification | |

| Option | Description | Selected |
|--------|-------------|----------|
| Push main first, CI green, then the tag | Avoids a red release run with a dangling tag | ✓ |
| Push the tag directly | release.yml runs CI anyway; a failure needs a tag delete | |

**User's choice:** All recommended options.

---

## Bench scope and start state

| Option | Description | Selected |
|--------|-------------|----------|
| UAT-02 + UAT-04 | Exactly what REL-01 requires | ✓ |
| + UAT-03 + P1-5 | Same group as run-all-scripted in 08-18 | |
| All scripted checks | Anticipates Phase 12 | |

| Option | Description | Selected |
|--------|-------------|----------|
| Restore null tombstones (like 08-18) | Hardest case, the original failure | ✓ |
| As-is after UAT-02 | Simpler, no longer tests the original failure | |
| Both | Twice the UAT-04 effort | |

| Option | Description | Selected |
|--------|-------------|----------|
| ha-c stays off | UAT-02/04 need only ha-a and ha-b | ✓ |
| ha-c as observer | Logged, adds nothing to the checks | |

| Option | Description | Selected |
|--------|-------------|----------|
| Preflight like Phase 8 | preflight.sh, registry backups, mount SHA == bump SHA | ✓ |
| SHA check only | No backup | |

**User's choice:** All recommended options.

---

## Release notes

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-written, applied after the release | Notes file in 09-evidence, `gh release edit`; release.yml unchanged | ✓ |
| Workflow reads the notes file | Workflow change on the bump SHA | |
| Generated notes only | Nearly empty | |

Content (multi-select): v1.0.1 fixes ✓, guard behavior change ✓, known limits ✓, upgrade note ✓

| Option | Description | Selected |
|--------|-------------|----------|
| English | Like README, commits and code | ✓ |
| English + German | Bilingual | |

---

## Evidence and gap closure

| Option | Description | Selected |
|--------|-------------|----------|
| 09-UAT.md + 09-evidence/ | Phase 8 ledger pattern | ✓ |
| VERIFICATION.md only | Leaner, departs from the pattern | |

Gap-close record (multi-select): PROJECT.md Key Decision ✓, MILESTONES.md v1.0.1 entry ✓, STATE.md (remove the Phase 9 blocker, keep the 07 deferred item) ✓

| Option | Description | Selected |
|--------|-------------|----------|
| Done after a green release + HACS check | Claude verifies the gh run and the release; criterion 3 fully covered | ✓ |
| Done after the bench passes | Tag and release outside the phase | |

---

## Claude's Discretion

- Plan split and wave order; helper and evidence file naming; how the bench scripts are parametrized for the Phase 9 evidence path (check logic unchanged).

## Deferred Ideas

- README text for the re-disabled duplicate: Phase 10 (FIX-05)
- Full re-verification and the UAT-03/P1-5 re-runs: Phase 12
- release.yml notes file instead of generated notes: revisit for v1.1.0
