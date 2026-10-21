---
phase: 11-local-actions-on-mirrors
plan: 23
subsystem: docs
tags: [contract, requirements, roadmap, release-notes, wr-01, wr-02, wr-03, wr-04]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-13: lifecycle contract texts (MIR-08, success criterion 5, release-notes Lifecycle bullet); Plan 11-18: WR-01 fix (tombstone keeps local actions inactive)"
provides:
  - "11-CONTEXT.md: Amendments block (owner decision 2026-10-21, WR-01 to WR-04) with D-05 amended, D-19 amended, D-07 extended, D-08 extended; D-05 bullet points to it"
  - "REQUIREMENTS MIR-08 amended: adoption is the only discard; a tombstone keeps local actions inactive"
  - "ROADMAP Phase 11 success criterion 5 amended: start-up, transient prunes and tombstones discard nothing"
  - "Release-notes Lifecycle bullet amended; draft stays unpublished"
affects: [11-19, 11-20, 11-21, 11-22, phase-11-verification, milestone-v1.1-audit]

actuals:
  tokens: 2674
  tasks: 2
  commits: 2
plan_head_before: 99ec5af92c606da59ddd5dc5e4f11652a65c8b08
plan_head_after: 1e426b5a296713276fd091688a49f21f5692cad4

tech-stack:
  added: []
  patterns:
    - "Owner decisions that change an earlier D-NN go into a dated Amendments block; the original bullet only gains a pointer"

key-files:
  created: []
  modified:
    - .planning/phases/11-local-actions-on-mirrors/11-CONTEXT.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/phases/11-local-actions-on-mirrors/11-release-notes.md

key-decisions:
  - "Amendments are recorded as decisions, not implementation status: no bullet says fixed, done or implemented"
  - "D-05 text stays as it was and only gains the pointer '(Tombstones amended 2026-10-21, see Amendments.)'"

patterns-established:
  - "Dated Amendments block before Implementation discretion in a phase CONTEXT"

requirements-completed: [MIR-08]

coverage:
  - id: D1
    description: "11-CONTEXT.md has the Amendments heading with four bullets (D-05, D-19, D-07, D-08) before Implementation discretion, the D-05 pointer, and still 23 D-NN bullets"
    requirement: MIR-08
    verification:
      - kind: other
        ref: "Task 1 <automated> grep gate in 11-23-PLAN.md (exit 0; 23 D-NN bullets)"
        status: pass
    human_judgment: false
  - id: D2
    description: "MIR-08, ROADMAP Phase 11 success criterion 5 and the release-notes Lifecycle bullet state the amended tombstone rule; 15 checked MIR lines remain; draft still unpublished"
    requirement: MIR-08
    verification:
      - kind: other
        ref: "Task 2 <automated> grep + uv run python gate in 11-23-PLAN.md (exit 0; 15 checked MIR lines)"
        status: pass
    human_judgment: false
  - id: D3
    description: "No requirement, success criterion or decision text other than MIR-08, criterion 5, the D-05 pointer and the Amendments block changed (flagged prohibition)"
    verification:
      - kind: other
        ref: "git diff 99ec5af..1e426b5 (4 files, 1 line each in REQUIREMENTS/ROADMAP, 1 line + new block in CONTEXT, Lifecycle bullet in release notes)"
        status: pass
    human_judgment: true
    rationale: "The prohibition is flagged unverified/judgment in the plan; the line-count gates only check it in part, so a verifier should read the diff"

duration: 1min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 23: Contract documents carry the owner decisions of 2026-10-21 Summary

**Amendments block in 11-CONTEXT.md (D-05 tombstone keeps local actions inactive with grace timer rejected, D-19, D-07, D-08) and the amended tombstone rule in MIR-08, ROADMAP success criterion 5 and the release-notes draft**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-10-21T07:42:27Z
- **Completed:** 2026-10-21T07:43:08Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- 11-CONTEXT.md records the four owner decisions of 2026-10-21 (WR-01 to WR-04) as amendments; the D-05 bullet points to them.
- MIR-08 (still `[x]`) now names adoption as the only discard and says a tombstone keeps local actions inactive.
- ROADMAP Phase 11 success criterion 5 and the release-notes Lifecycle bullet state the same rule as the README and code of Plan 11-18.

## Task Commits

1. **Task 1: Record the owner decisions of 2026-10-21 as amendments in 11-CONTEXT.md** - `b3ecda2` (docs)
2. **Task 2: Carry the amended tombstone rule into MIR-08, ROADMAP success criterion 5 and the release-notes draft** - `1e426b5` (docs)

## Final texts

### 11-CONTEXT.md, D-05 pointer

The D-05 bullet now ends with: `Startup and transient prune never discard them. (Tombstones amended 2026-10-21, see Amendments.)`

### 11-CONTEXT.md, Amendments block

```markdown
### Amendments (owner decision 2026-10-21, code review WR-01 to WR-04)
- **D-05 amended (WR-01):** A tombstone removes the mirror at once but keeps its local actions inactive, like after a prune. They are shown as not mirrored and stay until the user removes them or the device returns. Adoption still discards them with a log entry and the `adopt_device` count. Explicit removal and hub removal still delete them. The grace-timer alternative was rejected.
- **D-19 amended (WR-02):** Saving the customization of the named trigger without local actions (a mute or an empty additive list) also clears its local failure issue.
- **D-07 extended (WR-03):** A payload without a record list, or a missing file next to a Home Assistant `.corrupt` copy, counts as unreadable: issue raised, no overlay, saves refused. Stored rows this release cannot parse are kept unchanged on every save.
- **D-08 extended (WR-04):** When the saved local actions cannot be read, the removal settings show a dedicated warning, in English and German, that they cannot be read and will be deleted, instead of a device count.
```

### REQUIREMENTS.md, MIR-08

```markdown
- [x] **MIR-08**: On an adoption, local actions are discarded and logged; `adopt_device` reports it in its response. A tombstone removes the mirror but keeps its local actions inactive until the user removes them or the device returns; nothing is discarded at start-up, on a transient prune or on a tombstone (amended 2026-10-21, review WR-01)
```

The traceability row `| MIR-08 | Phase 11 | Complete |` is unchanged.

### ROADMAP.md, Phase 11 success criterion 5

```markdown
  5. Local actions survive owner content changes, renames, rev bumps, restarts and an owner re-pin. Local actions of a Select option the owner removed stay inactive, are listed as orphaned in the options where the user can remove them, and re-attach when the same StateValue returns. An adoption discards them with a log entry and `adopt_device` reports it; start-up, transient prunes and tombstones discard nothing, and the local actions of a deleted device stay inactive until the user removes them (amended 2026-10-21, WR-01). The README documents modes, mute, parallel semantics, this lifecycle, downgrade behavior and the `{{ state }}` template caveat. (MIR-06, MIR-07, MIR-08, MIR-15)
```

### 11-release-notes.md, Lifecycle bullet

```markdown
- Lifecycle: local actions survive owner edits, renames, new revisions, restarts and a new pinned owner. Local actions
  of a removed Select option stay inactive and reattach when the same state value returns. A start, a prune or a
  tombstone discards nothing: the local actions of a deleted device stay inactive until you remove them, and apply
  again if the device returns. An adoption discards them and logs the count. Removing the integration deletes them,
  and the removal settings name how many devices are affected.
```

The status line `Status: Unpublished draft (version, tag and publication belong to Phase 12)` is unchanged.

## Wave note

This plan ran in wave 16 next to Plan 11-18 (which had already committed before this executor started) and touched none of its files (no code, test, README, troubleshooting or disposition file). Plan 11-19 depends on it, because both edit the release-notes draft.

## Files Created/Modified

- `.planning/phases/11-local-actions-on-mirrors/11-CONTEXT.md` - D-05 pointer and the Amendments block
- `.planning/REQUIREMENTS.md` - MIR-08 text
- `.planning/ROADMAP.md` - one sentence of Phase 11 success criterion 5
- `.planning/phases/11-local-actions-on-mirrors/11-release-notes.md` - Lifecycle bullet sentences on discards

## Decisions Made

- Amendment bullets are phrased as owner decisions and never as implementation status, so they stay true before Plans 11-19 to 11-22 run.
- The D-19, D-07 and D-08 bullets restate the decisions as Plans 11-19 to 11-22 quote them. If a later plan finds a contradiction, that plan's objective wins and its SUMMARY records it (flagged assumption of the plan).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 11-19 to 11-22 can cite the Amendments block. Plan 11-19 can now edit the release-notes draft.
- The flagged prohibition (no other contract text changed) is checked only in part by the gates; the verifier should read the diff `99ec5af..1e426b5`.

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*
