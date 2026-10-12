---
phase: 09-v1-0-1-release
plan: 02
subsystem: release
tags: [release, ci, github-actions, evidence, v1.0.1, blocked]

requires:
  - phase: 09-v1-0-1-release
    plan: 01
    provides: "bump commit 7baec9878badc8fb49ea0d80243277d5ff3fb443 and the owner's refspec push command"
provides:
  - "origin main == bump SHA 7baec9878badc8fb49ea0d80243277d5ff3fb443, pushed by the owner (push-main.txt)"
  - "evidence that GitHub Actions created no CI and no Validate run for that push within 45 minutes (ci-bump-sha.json, ci-bump-sha-wait.txt)"
affects: [09-03, 09-04, 09-05]

actuals:
  tokens: 2400
  tasks: 1
  commits: 2
plan_head_before: e23b1a64bdc598048175bd9287eb215fb2051eba
plan_head_after: daa1669c107cb529ac59c0d17f171d5e1b3b0519

tech-stack:
  added: []
  patterns:
    - "CI on the bump SHA counts only for runs with event push and headSha == bump (T-09-07)"

key-files:
  created:
    - .planning/phases/09-v1-0-1-release/09-evidence/release/push-main.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/release/ci-bump-sha.json
    - .planning/phases/09-v1-0-1-release/09-evidence/release/ci-bump-sha-wait.txt
  modified: []

key-decisions:
  - "Phase 9 stops before the bench: no CI or Validate run exists on the bump SHA after the 45-minute window, so D-04 is not met; the owner decides how a push-event run on 7baec98 gets created"

requirements-completed: []

coverage:
  - id: D1
    description: "Owner pushed exactly the bump SHA to main (D-04, D-01)"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 1 verify: git ls-remote origin refs/heads/main == bump_sha of push-readiness.txt"
        status: pass
    human_judgment: false
  - id: D2
    description: "ci.yml and validate.yml green on exactly the bump SHA (event push)"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 2 verify: gh run list --commit 7baec98 | jq (push, headSha == bump, completed, success, CI and Validate)"
        status: fail
    human_judgment: true

duration: 46min
completed: 2026-10-12
status: blocked
---

# Phase 9 Plan 02: Bump SHA push and CI gate Summary

**BLOCKED: the owner's push moved origin main to the bump SHA `7baec98`, but GitHub Actions started no CI or Validate run for that push. `gh run list --commit 7baec98` stayed `[]` for the full 45-minute window. D-04 is not met, and the bench run (09-03) must not start.**

## Blocker (read first)

- **No CI run and no Validate run on the bump SHA.** This is not a red result, because no run exists at all. The poll ran every 30 s from 07:16:13 to 08:00:41 UTC, and every result was `[]`. `actions/runs?head_sha=7baec98` returns `total_count: 0`.
- The commit has two check suites, `claude` and `renovate`, both created at 07:15:13Z. It has no `github-actions` check suite. GitHub received the push, but Actions never queued a workflow for it.
- Things ruled out by API reads: Actions is enabled, and the CI, Validate and Release workflows are `active`. Both workflow files at the bump SHA trigger on `push` with only `tags-ignore: v*.*.*`. None of the pushed commit messages contains a skip marker. githubstatus showed All Systems Operational. Earlier pushes to main did trigger CI and Validate, for example 97c178d on 2026-10-02.
- The repo events feed shows no `PushEvent` for `refs/heads/main` from this push. The cause is unknown from here.
- Claude did not re-run, dispatch or push anything.

### Owner decision needed

Option A is recommended, because it keeps the D-04 contract: CI runs with event `push` on exactly 7baec98.

| Option | What | Trade-off |
|--------|------|-----------|
| A | The owner re-delivers a push event for 7baec98 on a ref that is not main, for example `git push origin 7baec98…:refs/heads/ci/v1.0.1-bump`. ci.yml and validate.yml run on every branch push. Afterwards the owner deletes the branch. | A push event on the exact bump SHA. It needs one temporary branch, and it does not move main. |
| B | The owner starts `workflow_dispatch` of CI and Validate on main, which is currently 7baec98. | The SHA is right, but the event is `workflow_dispatch`, not `push`. The plan's jq filter (`event == "push"`) would have to be relaxed, and that is a written D-04 amendment. |
| C | The owner first investigates why the push event was dropped (repo Settings > Webhooks/Actions, GitHub support). | Slowest option, and the bench waits. |

After A or B, re-run this plan's Task 2 (poll, jobs JSON, judgment) on 7baec98. Do not use any later SHA.

### Side observation (another SHA, does not count)

Renovate rebased PR #16 (`renovate/ubuntu-26.x`, head 7334f6d, parent = bump) right after the push. Its PR CI failed in **Broker tests (Mosquitto)** at `uv run pytest -q -m broker`. Ruff, Unit tests, Multi-instance tests, hassfest and HACS were green. The PR moves `runs-on` to Ubuntu 26, while the bump tree pins `ubuntu-24.04`. So the failure says nothing about 7baec98, but it is a warning for that PR. Per D-01, do not merge it before the tag.

## Performance

- **Duration:** about 46 min, most of it the 45-minute CI wait
- **Started:** 2026-10-12T07:15:47Z (continuation after the Task 1 checkpoint)
- **Completed:** 2026-10-12T08:01:25Z
- **Tasks:** 1 of 2 complete (Task 1 verified; Task 2 stopped at step 4)
- **Files:** 3 evidence files created

## Accomplishments

- Task 1 verify passed. `git ls-remote origin refs/heads/main` prints `7baec9878badc8fb49ea0d80243277d5ff3fb443`. `push-main.txt` records origin_main_before `d0f660c…`, origin_main_after = bump, the owner's refspec command and output, and `pushed_by: owner`.
- Task 2: the poll ran for the full 45-minute window. The final run list is in `ci-bump-sha.json` (`[]`). The poll window and the API diagnostics are in `ci-bump-sha-wait.txt`. `check-evidence-clean.sh` printed PASS over `09-evidence/release` before each commit.

## Task Commits

1. **Task 1: owner push verified.** `34c61bd` (docs, push-main.txt)
2. **Task 2: CI gate, stopped.** `daa1669` (docs, ci-bump-sha.json and ci-bump-sha-wait.txt)

## Deviations from Plan

### Process deviations (no product change)

**1. push-main.txt committed on its own (orchestrator instruction)**
- The plan commits push-main.txt together with the two CI files in Task 2. The continuation prompt asked for push-main.txt to be committed right after Task 1's verify. Same content, two commits instead of one.

**2. Task 2 stopped without ci-bump-sha-jobs.json; ci-bump-sha-wait.txt added**
- No run exists, so there are no jobs to list. Step 4 says to stop and report when the window passes. The file `ci-bump-sha-wait.txt` replaces the jobs file as evidence of the wait and of the diagnostics. The commit message says "no CI or Validate run" instead of the plan's "CI and Validate on the bump commit", because the planned message would claim something that did not happen.

**Total deviations:** 2 process deviations. **Impact:** the plan's truths 1 and 4 hold: only the bump SHA reached main, and Claude made no push and no re-run. Truth 2 (green CI on the bump) is **not met**. Truth 3 (stop before the bench) is honored.

## Known Stubs

None.

## Threat Flags

None. The evidence holds only public run metadata, check-suite app slugs and SHAs.

## Next

STOP. Phase 9 waits for the owner's decision (option A, B or C above). Do not start 09-03 (bench) until Task 2's verify passes on 7baec98.

## Self-Check: PASSED

- FOUND: 09-evidence/release/push-main.txt (origin_main_after: 7baec98…, pushed_by: owner)
- FOUND: 09-evidence/release/ci-bump-sha.json (`[]`)
- FOUND: 09-evidence/release/ci-bump-sha-wait.txt
- FOUND commits on HEAD: 34c61bd, daa1669
- ABSENT, as expected because of the blocker: 09-evidence/release/ci-bump-sha-jobs.json
