---
phase: 08-real-instance-verification
plan: 16
subsystem: verification-gap-closure
tags: [uat-04, owner-decision, waiver, receiver-guard, ledger]
requires:
  - phase: 08-real-instance-verification
    provides: failed UAT-04 re-run of plan 08-13 on build caf2fe5d (ha-b X7 and X8), waiver D08-WAIVER (plan 08-12)
provides:
  - owner decision UAT04-RECEIVER-GUARD = extend-and-confirm, recorded verbatim in evidence/uat-04-receiver-guard/decision.txt
  - D-08 second amendment (2026-10-11) and the ROADMAP Phase 8 goal exception sentence naming both decision ids
  - the failed 08-13 re-run recorded as history in the Gaps entry for test 4 and in Observations
affects: [08-17, 08-18, 08-14, 08-15]
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-04-receiver-guard/decision.txt
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
    - .planning/phases/08-real-instance-verification/08-CONTEXT.md
    - .planning/ROADMAP.md
decisions:
  - "UAT04-RECEIVER-GUARD: extend-and-confirm (2026-10-11): D08-WAIVER extends to plans 08-16 to 08-18 for UAT-04 clause 2; the guard is armed on every native instance; UAT-01, P2-2 and the owner-judged frontend items confirmed as not affected; the failure rule of D-08 stands"
metrics:
  completed: 2026-10-11
status: complete
commits: 2
plan_head_before: 22ff366
plan_head_after: fab6fed
actuals:
  tokens: 3000
  tasks: 2
  commits: 2
---

# Phase 8 Plan 16: owner decision on the receiver-side guard and the failed 08-13 re-run Summary

The owner chose `extend-and-confirm`: the D-08 waiver now covers plans 08-16 to 08-18 for UAT-04 clause 2, the guard is to be armed on every native instance, and UAT-01, P2-2 and the owner-judged frontend items stand as not affected. The closure continues: plans 08-17, 08-18, 08-14 and 08-15 may run (the precondition, line 1 of `decision.txt`, reads `extend-and-confirm`). No product, test or workflow file was touched and no bench action ran.

## What was done

- **Task 1 (checkpoint:decision, gate blocking-human), commit 2b13f10:** the orchestrator put the question to the owner in German with the facts of the plan context (the 08-13 FAIL on ha-b X7/X8, the receiver-side guard design of plan 08-17, the replacement of the "inert while export is off" argument, the tombstone side effect and the costs). The owner answered with the option id `extend-and-confirm`, no further free text. `decision.txt` has the five fixed lines (option id, `2026-10-11`, waiver-scope line, `not-affected-confirmed: yes`, `checks-to-widen: none`) and the owner's words as relayed, with nothing added (D-07). `check-evidence-clean.sh` over the folder: PASS.
- **Task 2 (auto), commit fab6fed:**
  - `08-UAT.md` Owner decisions: row `UAT04-RECEIVER-GUARD` with option, scope, replacement argument, provenance and date; the earlier rows are unchanged.
  - `08-UAT.md` Gaps entry for test 4: `reason` extended by the 08-13 re-run sentence, new `artifacts` item for `uat-04-rerun/verdict.txt`; `status: failed`, `severity`, `test`, `root_cause`, block 4 (`result: issue`), the results table and the Summary counts untouched.
  - `08-UAT.md` Observations: entry "UAT-04 re-run on the guard build (plan 08-13)" (UAT-02, UAT-03, P1-5 PASS, UAT-04 FAIL, host reboot at plan start, evidence folders untouched, final result to be the re-run of plan 08-18, recorded by plan 08-14).
  - `08-CONTEXT.md`: one dated amendment line (2026-10-11, UAT04-RECEIVER-GUARD) under the amendment of 2026-10-08; the original D-08 text and the first amendment are word for word as before; the failure rule is stated as standing.
  - `ROADMAP.md`: the Phase 8 goal exception sentence now names D08-WAIVER and UAT04-RECEIVER-GUARD; the failure-rule wording is unchanged.

## Verification

- Task 1 verify (decision.txt shape, evidence-clean): PASS.
- Task 2 verify: ledger greps (decision id, `uat-04-rerun/verdict.txt`, the original D-08 sentence, the first amendment) PASS; CONTEXT.md and ROADMAP name UAT04-RECEIVER-GUARD PASS; `check-recorded.sh --all` PASS (all 14 checks recorded); `check-evidence-clean.sh` PASS.
- `git diff --stat HEAD` over the evidence folders `uat-04`, `uat-04-rerun`, `uat-02-rerun`, `uat-03-rerun`, `p1-5-rerun`: empty.
- `git log --format=%H --grep='(08-16)' -- custom_components tests .github`: prints nothing.

## Deviations from Plan

None - plan executed exactly as written. The `.planning/config.json` modification present at the start was not part of this plan and was left unstaged.

## Known Stubs

None.

## Threat Flags

None. T-08-46 mitigated (owner words verbatim, dated added amendment limited to UAT-04 clause 2, original sentences intact); T-08-47 mitigated (evidence scans PASS).

## Self-Check: PASSED

- `decision.txt` FOUND; commits 2b13f10 and fab6fed present on gsd/phase-08-real-instance-verification.
