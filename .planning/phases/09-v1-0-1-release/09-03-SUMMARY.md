---
phase: 09-v1-0-1-release
plan: 03
subsystem: release
tags: [release, bench, uat-02, uat-04, evidence, v1.0.1, gap]

requires:
  - phase: 09-v1-0-1-release
    plan: 02
    provides: "CI and Validate green on the bump SHA 7baec98 (D-04 amendment)"
  - phase: 09-v1-0-1-release
    plan: 01
    provides: "bench pinned to the bump SHA, phase9.env, reseed-tombstones.sh parametrized"
provides:
  - "UAT-02 verdict FAIL on 7baec9878badc8fb49ea0d80243277d5ff3fb443 (E1 to E3 fail in both rounds on ha-a and ha-b, E4 holds)"
  - "UAT-04 BLOCKED: the D-06 state cannot be reached without a hand edit after the UAT-02 FAIL"
  - "09-UAT.md ledger: PRE pass, CI pass, UAT-02 issue, UAT-04 blocked, REL pending, REL-01 pending, Gaps entry test: 3"
  - "no release notes (D-10, D-11: notes only on a double pass)"
affects: [09-04, 09-05, 9.1]

actuals:
  tokens: 38500
  tasks: 3
  commits: 3
plan_head_before: 8c607b14142cbdfe6620a855df469ae046f5bb72
plan_head_after: 14ccd19a533c9fa0349a8720a0efa2f49b516b1e

tech-stack:
  added: []
  patterns:
    - "A bench FAIL stands as evidence. A blocked follow-up check gets a blocked.txt with the reason and is never forced by a hand edit."

key-files:
  created:
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-02/ (13 files: precheck, baselines, round1/round2 projections, logs, retained topics, payload check, result, verdict)
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/blocked.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/guard-log-a.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/guard-log-b.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/post-run-a.json
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/post-run-b.json
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/post-restart.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/post-restart-a.json
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/post-restart-b.json
    - .planning/phases/09-v1-0-1-release/09-UAT.md
  modified:
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/prepare.txt

key-decisions:
  - "UAT-02 FAIL on the bump SHA 7baec98 stands (E1 to E3); v1.0.1 is not tagged on 7baec98, and the gap routes to an inserted Phase 9.1"
  - "UAT-04 recorded as blocked, not run: live mqtt rows remain and the regression tombstones are gone, so D-06 would need a forbidden hand edit"
  - "Planner decision 1 applied: UAT-04 was attempted after the UAT-02 FAIL. Its precondition (reseed) failed without any hand edit, so block 4 is blocked with the reason."

requirements-completed: []

coverage:
  - id: D1
    description: "UAT-02 ran once on exactly the bump SHA with unchanged E1 to E4 and has a recorded verdict"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 1 verify: verdict.txt line 1 FAIL; precheck.txt names pinned sha 7baec98; check-evidence-clean.sh uat-02 PASS"
        status: pass
    human_judgment: false
  - id: D2
    description: "UAT-04 has a stated BLOCKED reason; observations recorded; bench left clean (export off, preflight PASS, ha-c stopped)"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 2 verify blocks 1 to 3: blocked.txt line 1 BLOCKED; check-uat04.sh clean PASS; check-preflight.sh --quick PASS; ha-c Running=false; check-evidence-clean.sh 09-evidence PASS"
        status: pass
    human_judgment: false
  - id: D3
    description: "09-UAT.md ledger with five rows, REL-01 pending, and no release notes on a non-pass"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 3 verify blocks 1 and 2 (ledger greps; release-notes.md absent because the checks did not both pass)"
        status: pass
    human_judgment: true
    rationale: "Whether the gap description and the observations are accurate and complete enough for Phase 9.1 planning is a judgment"

duration: 18min
completed: 2026-10-12
status: complete
---

# Phase 9 Plan 03: Bench run on the v1.0.1 bump SHA Summary

**UAT-02 FAILED on the bump SHA 7baec98, and UAT-04 is BLOCKED by it. UAT-02 failed expectations E1, E2 and E3 in round 1 and round 2 on both ha-a and ha-b: `switch.lampe_test_2` and `select.bar_select_2` stay as platform-mqtt rows (`disabled_by` integration), and the legacy devices `mqtt_actions_<id>` stay too. E4 holds. v1.0.1 is not tagged on 7baec98. The gap goes to an inserted Phase 9.1, and plans 09-04 and 09-05 do not run.**

## Result

| Check | Result | Evidence |
|-------|--------|----------|
| UAT-02 (E1 to E4) | FAIL (exit 1). E1, E2 and E3 fail in round 1 and round 2 on ha-a and ha-b. E4 passes (34 mqtt_actions rows identical to the baseline). | `09-evidence/uat-02/` |
| UAT-04 (X1 to X10) | BLOCKED, not run | `09-evidence/uat-04/blocked.txt`, `prepare.txt` |
| Release notes | not written (D-10, D-11) | - |
| Ledger | `09-UAT.md`: PRE pass, CI pass, UAT-02 issue, UAT-04 blocked, REL pending. REL-01 pending. | `09-UAT.md` |

### Failing expectations (UAT-02, `uat-02/result.txt`)

- **E1** (zero platform-mqtt rows): `select.bar_select_2` (b6bd2c0e-…) and `switch.lampe_test_2` (11111111-…) are present on ha-a and ha-b after both rounds. Both have `disabled_by` integration and `config_entry_id` null.
- **E2** (zero `_2` ids): the same two ids.
- **E3** (zero legacy devices): the devices `mqtt_actions_11111111-aaaa-4aaa-8aaa-000000000001` and `mqtt_actions_b6bd2c0e-6d81-49ea-8025-4bd087bd718a` are present on both instances.

What the logs show (`log-a.txt`, `log-b.txt`): in round 1 the guard logged "Disabled 1 duplicate entities…" twice per instance. In both rounds the catch logged "Removed 2 duplicate entities that a replayed legacy discovery created" twice per instance. Even so, the rows were still in the flushed registry. Also, unlike in Phase 8, the legacy topics were still retained after each start.

### Lead for Phase 9.1 (observation, not a reinterpretation)

The start state was different from the Phase 8 reference run. Before this run, the regression tombstones on both instances were `disabled_by: integration`, left that way by the Phase 8 receiver-guard run (`uat-04/prepare.txt`, first projection from plan 09-01). The Phase 8 UAT-02 PASS (uat-02-rerun2) started from null tombstones. This time the replay brought the tombstones back as disabled live rows, and the catch did not remove them.

## Performance

- **Duration:** about 18 min (2026-10-12T19:48:13Z to about 20:06Z)
- **Tasks:** 3 of 3, run under the plan's FAIL and BLOCKED rules
- **Files:** 22 evidence files and the ledger (23 files, 3385 lines)

## Accomplishments

- Task 1: the gate passed (`check-preflight.sh --quick`, `check-stale-anchor.sh`, ha-c not running). One `check-uat02.sh run` (19:49:15Z to 19:53:24Z) ended in exit 1, FAIL. Both baselines were clean and equal the 00-preflight baseline, and the A7 payload check passed. No ABORT occurred, so no bench-notes.txt was needed. The FAIL was not repeated.
- Task 2: `prepare.txt` now includes the build under test, the UAT-02 FAIL and the `--check` projection (2 live mqtt rows per instance, no tombstones, "nothing to flip"). `reseed-tombstones.sh` stopped both instances and backed up both registries to `~/ha-test/_backup-pre-phase9-20261012T014617Z/reseed-20261012T195511Z` (mode 700). It then ABORTed on "ha-a holds live mqtt rows (2)" before writing anything. `blocked.txt` records the reason. Observations recorded: guard log lines (2 per instance, all in UAT-02 round 1) and live mqtt rows before and after one graceful restart (2 per instance, both times). `check-uat02.sh clean` prints FAIL. At the end the bench is clean: `check-uat04.sh clean` PASS, `check-preflight.sh --quick` PASS, ha-c stopped, no stray `mosquitto_sub`.
- Task 3: `09-UAT.md` is written in the 08-UAT.md format, with five rows, blocks 1 to 5, Summary, Requirement verdicts (REL-01 pending), Gap closure, Gaps (test: 3), Observations and Bench state. It also lists the checks that did not run in Phase 9 (UAT-01, UAT-03, P1-5), each with its last Phase 8 evidence. No release notes were written.

## Task Commits

1. **Task 1: UAT-02 evidence (FAIL).** `0911f94`
2. **Task 2: UAT-04 blocked, prepare, observations.** `9740301`
3. **Task 3: ledger.** `14ccd19`

## Deviations from Plan

### Plan-path adaptations (no rule change)

**1. Task 2 commit message names the blocked outcome**
- The plan's message ("run UAT-04 … from the restored tombstone state") would claim a run that did not happen (T-09-15). The commit is titled "UAT-04 blocked on the v1.0.1 bump commit after the UAT-02 FAIL (evidence)".

**2. Task 2 step 5 observations without a UAT-04 window**
- Step 5 is defined relative to the UAT-04 run, which did not happen. The guard log lines were taken from the start of the UAT-02 run (19:49:15Z) instead, and the file header says so. The restart observation was made after the reseed ABORT start. Timestamps in the guard logs are container local time (UTC+2), and the header states this too.

### Bench-tooling finding (not fixed here, for Phase 9.1)

**3. `check-uat02.sh clean` cannot pass with a Phase 9 baseline**
- `do_clean` removes the UAT Marker rows only from the live side of the comparison. The Phase 9 `uat-02/baseline-*.json` holds the 4 marker rows, because the marker fixture predates this baseline. So `clean` always reports "mqtt_actions rows (without hub rows) differ from the baseline". `reseed-tombstones.sh` needs `clean` to PASS after the restoration, so it would ABORT even on a clean bench. This plan forbids changing the scripts. Phase 9.1 must fix this comparison path before its re-run (D-09 allows it, because it is not an expectation).

**Total deviations:** 0 auto-fixes. 2 plan-path adaptations and 1 bench finding. **Impact:** none on the recorded results. The FAIL is recorded exactly as the script produced it.

## Issues Encountered

- **UAT-02 FAIL (E1 to E3)** on the bump SHA. This is a product gap, not bench noise, because the baselines were clean and the payload check passed. It blocks REL-01 on 7baec98.
- **UAT-04 blocked** as a consequence of the UAT-02 FAIL.

## Known Stubs

None.

## Threat Flags

None. The evidence holds fixed-field projections, log lines reduced to the timestamp and the content-free guard text, and topic payloads that carry only the instance ids already recorded in build.txt. `check-evidence-clean.sh` printed PASS over all of `09-evidence`. No registry row was edited or removed by hand. The reseed made a backup and then aborted before writing anything.

## Bench state left behind

- mosq, ha-a and ha-b are Up on the bump tree. ha-c is stopped. The export is off, and nothing is retained on the export prefix or the core prefix.
- ha-a and ha-b each hold 2 disabled live mqtt rows (`switch.lampe_test_2`, `select.bar_select_2`) and the two legacy mqtt devices. Nothing was removed by hand.

## Next

Plans 09-04 and 09-05 must not run. Next step: insert Phase 9.1 (gap closure for 09-UAT.md block 3: root cause, fix, new bump SHA, then UAT-02 and UAT-04 again), for example `/gsd-phase` (insert 9.1) followed by `/gsd-plan-phase 9.1 --gaps`. The owner pushes nothing on 7baec98.

## Self-Check: PASSED

- FOUND: uat-02/{verdict,result,precheck}.txt, baseline-{a,b}.json, round{1,2}-{a,b}.json
- FOUND: uat-04/{prepare,blocked,guard-log-a,guard-log-b,post-restart}.txt, post-run-{a,b}.json, post-restart-{a,b}.json
- FOUND: 09-UAT.md. release-notes.md is absent (correct for a non-pass).
- FOUND commits on HEAD: 0911f94, 9740301, 14ccd19
- Plan-level verification rerun: verdict FAIL / blocked BLOCKED; check-uat04.sh clean PASS; check-preflight.sh --quick PASS; ha-c not running; check-evidence-clean.sh 09-evidence PASS
