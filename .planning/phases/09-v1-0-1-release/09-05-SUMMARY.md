---
phase: 09-v1-0-1-release
plan: 05
subsystem: release
tags: [release, v1.0.1, release-notes, evidence, ledger, accepted-gap]
status: complete

requires:
  - phase: 09-v1-0-1-release
    plan: 04
    provides: "tag v1.0.1 on FIX 3dc9093 pushed by the owner, decision push-tag-claude-notes, release run 38824818079 started"
provides:
  - "release.yml run 38824818079 on tag v1.0.1 (headSha FIX) success, all 8 jobs success (release-run.json, release-jobs.json)"
  - "GitHub release v1.0.1 Latest, not draft, not prerelease, published 2026-10-15T23:41:07Z (release-view.json, release-latest.json)"
  - "hand-written release notes applied by Claude (notes_route claude); body equals release-notes.md (release-body.md, notes-applied.txt)"
  - "09-UAT.md complete: block 5 REL pass on FIX, REL-01 pass, ACCEPTED-GAP-V101 closed for v1.0.1"
  - "PROJECT.md, MILESTONES.md, STATE.md and ROADMAP.md line 6 record v1.0.1 as released"
affects: [10, 12]

actuals:
  tokens: 8200
  tasks: 2
  commits: 2
plan_head_before: 3d404f7f528ca9232e2198d4a84fb854cdb2fa85
plan_head_after: f6ec105f2b01f8b336ee2b9aa419e671eba4f725

tech-stack:
  added: []
  patterns:
    - "Keep the replaced generated release body as evidence before overwriting it (release-body-generated.md)"

key-files:
  created:
    - .planning/phases/09-v1-0-1-release/09-evidence/release/release-run.json
    - .planning/phases/09-v1-0-1-release/09-evidence/release/release-jobs.json
    - .planning/phases/09-v1-0-1-release/09-evidence/release/release-view.json
    - .planning/phases/09-v1-0-1-release/09-evidence/release/release-latest.json
    - .planning/phases/09-v1-0-1-release/09-evidence/release/release-body.md
    - .planning/phases/09-v1-0-1-release/09-evidence/release/release-body-generated.md
    - .planning/phases/09-v1-0-1-release/09-evidence/release/notes-applied.txt
  modified:
    - .planning/phases/09-v1-0-1-release/09-UAT.md
    - .planning/PROJECT.md
    - .planning/MILESTONES.md
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "v1.0.1 released 2026-10-15 on tag v1.0.1 -> 3dc9093f3cc49900bf76576cb4432d84aa94cd74; release.yml run 38824818079 green in all eight jobs"
  - "ACCEPTED-GAP-V101 closed for the v1.0.1 release only (UAT-02 x2, UAT-04 and the CR-01 gate on FIX plus the green release run); the full re-verification stays Phase 12 (QLT-01)"
  - "Release notes applied by Claude per decision.txt (notes_route claude); release.yml unchanged (D-10)"

requirements-completed: [REL-01]

duration: 5min
completed: 2026-10-15
---

# Phase 9 Plan 05: v1.0.1 release verified, notes applied, ACCEPTED-GAP-V101 closed Summary

v1.0.1 is published. GitHub marks it Latest. It points at tag `v1.0.1` on FIX `3dc9093f3cc49900bf76576cb4432d84aa94cd74`. Release run 38824818079 passed all eight jobs. The release now carries the hand-written notes, and the ledger and project records say v1.0.1 is released.

## Performance

- **Started:** 2026-10-15T23:40:20Z
- **Completed:** 2026-10-15T23:43:00Z
- **Duration:** about 5 min. The release run finished about 20 s after dispatch, so there was almost no wait.
- **Tasks:** 2 of 2
- **Files:** 7 evidence files created, 5 records modified

## Accomplishments

- **Release run green.** release.yml run 38824818079 has event push, headBranch v1.0.1 and headSha FIX. It was created at 2026-10-15T23:38:48Z and finished with conclusion success. All eight jobs succeeded:
  - Tag matches manifest version
  - CI / Ruff
  - CI / Unit tests
  - CI / Broker tests (Mosquitto)
  - CI / Multi-instance tests
  - Validate / hassfest
  - Validate / HACS
  - Create GitHub release
- **Release object.** v1.0.1 was published at 2026-10-15T23:41:07Z. It is not a draft and not a prerelease. `gh release list` shows it as Latest, ahead of v1.0.0 and v0.1.0.
- **Notes applied (D-10).** Claude ran `gh release edit v1.0.1 --notes-file .planning/phases/09-v1-0-1-release/09-evidence/release-notes.md`, following decision.txt (`notes_route: claude`).
  - The body read back is identical to the notes file under `diff -B --strip-trailing-cr`.
  - The replaced generated body (`**Full Changelog**: ...v1.0.0...v1.0.1`) is kept in `release-body-generated.md`.
- **Ledger complete.** `09-UAT.md` changes:
  - `status: complete`
  - Current Test: `[testing complete]`
  - REL row and block 5: pass on FIX
  - REL-01: pass
  - Summary counts: 22 passed, 1 issue, 0 pending, 1 blocked
  - Gap closure: ACCEPTED-GAP-V101 closed for v1.0.1 on 2026-10-15, with the tag, the SHA, blocks 21 to 24 and the run id. It also states that this is not a full re-verification (Phase 12).
- **Records (D-13):**
  - PROJECT.md: the Current State paragraph, the Context parenthesis, the HACS row and the ACCEPTED-GAP-V101 Outcome cell are updated.
  - MILESTONES.md: the v1.0.1 `**Releases:**` line is replaced and a closing sentence is added to Closeout.
  - STATE.md: the `[Phase 9]` and `[Phase 9.2]` blocker bullets are removed. There was no `[Phase 9.1]` bullet. The deferred item `07/07-VERIFICATION.md` is kept.
  - ROADMAP.md: line 6 says "released as v1.0.1 on 2026-10-15".
  - Nothing under `.planning/milestones/` was changed.

## Task Commits

1. **Task 1: Release run, Latest, notes, ledger** - `29bbfcf` (docs)
2. **Task 2: Project records, ACCEPTED-GAP-V101 closed** - `f6ec105` (docs)

## Decisions Made

- RDATE is 2026-10-15, the UTC date of `publishedAt`.
- The generated release body was saved before it was overwritten, so the public change can be traced and reversed.

## Deviations from Plan

**1. [Rule 2 - Traceability] Extra evidence file `release-body-generated.md`**
- **Why:** `gh release edit` overwrites a public body. Saving the generated body first records what was replaced.
- **Files:** `09-evidence/release/release-body-generated.md`. It is referenced in `notes-applied.txt` and in block 5.
- **Commit:** `29bbfcf`

**2. Line numbers in PROJECT.md moved**
- The plan names line 93 for the ACCEPTED-GAP-V101 row. The row is now at line 95.
- It was edited by content match, and only the Outcome cell changed.

Otherwise the plan was executed as written.

## Authentication / Human Gates

None during execution. `gh auth status` was valid.

Open end-of-phase human check (Task 1 `<human-check>`): on a Home Assistant host with MQTT Actions installed through HACS, run "Update information" and confirm that HACS offers 1.0.1.

## Prohibitions honored

- No `git push`, no `gh run rerun` and no tag change.
- `git ls-remote origin refs/tags/v1.0.1` still prints FIX.
- release.yml is unchanged.
- The archived files under `.planning/milestones/` are unchanged.
- The closing records claim only UAT-02 (twice), UAT-04 and the CR-01 gate on FIX plus the green release run. They name Phase 12 for the full re-verification.

## Issues Encountered

None.

## Next Phase Readiness

- **Owner:** main may now be pushed together with its local `.planning` commits. The main freeze of D-01 ended with the tag, so Phase 10 can start.
- **Follow-up still open:** add a branches filter under `on.push` in ci.yml and validate.yml (`.planning/todos/pending/2026-10-12-ci-push-trigger-branches.md`).
- **Phase completion:** the Phase 9 progress row and checkbox in ROADMAP.md, and the PROJECT.md Active checklist, are left to the orchestrator's phase transition.

## Self-Check: PASSED

- FOUND: release-run.json, release-jobs.json, release-view.json, release-latest.json, release-body.md, release-body-generated.md, notes-applied.txt
- FOUND: commits 29bbfcf and f6ec105 are ancestors of HEAD
- All six automated verifies of Tasks 1 and 2 exit 0. `check-evidence-clean.sh` prints PASS.
- The remote tag v1.0.1 == FIX
