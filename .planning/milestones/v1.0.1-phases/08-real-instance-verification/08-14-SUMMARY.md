---
phase: 08-real-instance-verification
plan: 14
subsystem: verification-gap-closure
tags: [uat-04, uat-02, uat-03, p1-5, ledger, traceability, receiver-guard, rerun2]
requires:
  - phase: 08-real-instance-verification
    provides: final re-run evidence on the receiver-guard build (plan 08-18, -rerun2 folders), owner decisions UAT04-GAP-DISPOSITION and UAT04-RECEIVER-GUARD, the 08-13 history entry (plan 08-16)
provides:
  - block 4 (UAT-04) recorded pass from uat-04-rerun2; blocks 2, 3 and 9 re-recorded from the -rerun2 folders with the new sha
  - Gaps entry for test 4 resolved (resolution line, new evidence artifact, history kept)
  - ledger status complete (14 of 14 pass), Requirement verdicts, Build under test with both earlier shas, Observations (final result, checks not re-run)
  - REQUIREMENTS.md UAT-01 to UAT-04 complete, ROADMAP.md plan ticked, 08-VALIDATION.md status for the 17 tasks of plans 08-11 to 08-14 and 08-16 to 08-18
affects: [08-15]
coverage:
  - id: D1
    description: "Block 4 and the re-run blocks 2, 3, 9 recorded from the -rerun2 evidence; check-recorded.sh UAT-04, UAT-02, UAT-03, P1-5 and --all PASS"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-recorded.sh UAT-04 / UAT-02 / UAT-03 / P1-5 / --all (PASS), check-uat04-iso.sh disposition (guard-and-document)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Traceability: REQUIREMENTS.md agrees with the ledger verdicts; validation map has a green status for 17 tasks"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "plan task 2 awk traceability check and the grep -c >= 17 check on 08-VALIDATION.md"
        status: pass
    human_judgment: false
actuals:
  tokens: 15000
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "re-run recorded beside the superseded runs: new evidence folder per block, earlier folders never edited, history named in the block notes"
key-files:
  created: []
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/phases/08-real-instance-verification/08-VALIDATION.md
key-decisions:
  - "UAT-04 recorded pass without the pruned-state qualifier: the disposition is guard-and-document, so the pass is on the regression state (null tombstones restored by plan 08-18, proven in prepare.txt) with the receiver-guard build"
  - "Ledger frontmatter status set to complete: no block is an issue any more"
  - "Build under test ha-b instance id corrected to the id of the hub re-added in plan 08-08 (b4cf285b), as in build.txt"
requirements-completed: [UAT-01, UAT-02, UAT-03, UAT-04]
duration: 20 min
completed: 2026-10-11
status: complete
commits: 2
plan_head_before: 18311ebf0d81b6b19b1a874ff5bc90f9de512687
plan_head_after: 418210238d81363104d5f4b5c02b4fca3ac61bfc
---

# Phase 8 Plan 14: record the final re-run in the ledger and close the traceability Summary

**UAT-04 is recorded pass on the receiver-guard build (`b8232252540a55969145ca0034d8fd86b4be3b7c`) from the restored null-tombstone state, with UAT-02, UAT-03 and P1-5 re-recorded from the -rerun2 folders, the Gaps entry resolved, and UAT-01 to UAT-04 complete in REQUIREMENTS.md.**

## Performance

- 2 tasks, 2 task commits (`24798d8`, `4182102`); only `.planning/` files edited, no bench action beyond read-only checks.
- Disposition read first: `check-uat04-iso.sh disposition` printed `guard-and-document` (modifier `full-rerun`, `applies guard` yes, `applies document` yes, `applies prune` no).

## What was done

- **Task 1 (24798d8), ledger:**
  - Block 4: `result: pass`, sha = pin of `00-preflight/build.txt`, date 2026-10-11, evidence `uat-04-rerun2`; `reported:` and `severity:` removed. The note names the regression state with the exact `prepare.txt` line, ha-a exporting and ha-b only receiving, X1 to X10 unchanged (check scripts byte-identical, `cmp` in plan 08-18), the guard log (two INFO lines on each instance), the restart observation, and the superseded history (`uat-04` and `uat-04-isolation` first run, `uat-04-rerun` 08-13 FAIL on ha-b). No qualifier, because for a guard option the pass is on the failing state.
  - Blocks 2, 3 and 9 re-recorded from `uat-02-rerun2`, `uat-03-rerun2`, `p1-5-rerun2`; their notes name the superseded first runs and the 08-13 re-runs.
  - Table rows (plain `pass`), Summary 14 passed / 0 issues, frontmatter `status: complete`, Current Test, Requirement verdicts for UAT-02 to UAT-04, Verification refresh sentence, `updated`.
  - Gaps entry for test 4: `status: resolved` with a `resolution:` line, reason extended, a `uat-04-rerun2/verdict.txt` artifact added, the 08-13 artifact marked history.
  - Build under test: new sha, two `previous sha` lines (`caf2fe5d`, `b7f52b34`), the sentence that the not re-run blocks keep their sha. Observations: the 08-13 entry extended with the final result (not rewritten), plus a new entry listing every check not re-run (UAT-01, P2-2, P1-1 to P1-4, P1-6, P2-1, P3-1, P3-2) with the reason and the owner confirmations. Owner follow-up 1 marked decided.
- **Task 2 (4182102), traceability:** REQUIREMENTS.md UAT-01 to UAT-04 ticked and Complete, last-updated line; ROADMAP.md 08-14 ticked; 08-VALIDATION.md status for 17 rows (08-13-T2 reads green with its FAIL kept as history, superseded by 08-18).

## Verification

- `check-recorded.sh UAT-04`, `UAT-02`, `UAT-03`, `P1-5` and `--all`: PASS.
- Traceability check (UAT-01 to UAT-03 Complete, UAT-04 follows the ledger pass): PASS; green-rows count 17.
- Earlier evidence folders untouched: `git diff --stat HEAD` over `08-evidence` was empty before each commit.
- The pruned-state qualifier checks do not apply (disposition is not document-only; `applies prune` is no).

## Deviations from Plan

**1. [Rule 1 - Bug] Build under test named a stale ha-b instance id.** The ledger said `a09499e4-...`, but plan 08-08 re-added the ha-b hub under `b4cf285b-428f-426b-9500-8e269634356e` (as `build.txt` records). Corrected in place with a note naming the old id. Commit 24798d8.

**2. [Scope note] Task 2 step 2 of the plan (ROADMAP counts).** The plan list tick was done by hand; the Plans count and progress row are advanced by `roadmap update-plan-progress` in the state updates.

Otherwise: plan executed as written. `.planning/STATE.md` carried the orchestrator's begin-phase edit and `.planning/config.json` an unrelated edit; config.json was never staged.

## Known Stubs

None.

## Threat Flags

None. T-08-39 and T-08-45 mitigations hold: first run and 08-13 re-run kept as named history, the not-re-run list is tied to the owner rows UAT04-GAP-DISPOSITION and UAT04-RECEIVER-GUARD.

## Next

Plan 08-15 (final gate, verifier refresh of the archived reports, Phase 8 re-verification) can run; `check-final.sh` is amended there to read the first token of the Requirement verdicts cell. Bench note for 08-15: `check-uat03.sh` leaves a background `mosquitto_sub` running (recorded in the Observations entry).

## Self-Check: PASSED

- Commits `24798d8` and `4182102` are in the branch.
- `08-UAT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `08-VALIDATION.md` edited; `check-recorded.sh --all` PASS.
