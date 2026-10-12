---
phase: 09-v1-0-1-release
plan: 02
subsystem: release
tags: [release, ci, github-actions, evidence, v1.0.1, d04-amendment]

requires:
  - phase: 09-v1-0-1-release
    plan: 01
    provides: "bump commit 7baec9878badc8fb49ea0d80243277d5ff3fb443 and the owner's refspec push command"
provides:
  - "origin main == bump SHA 7baec9878badc8fb49ea0d80243277d5ff3fb443, pushed by the owner (push-main.txt)"
  - "CI run 38299461144 and Validate run 38299494978 green on exactly 7baec98, all six jobs success (ci-bump-sha.json, ci-bump-sha-jobs.json)"
  - "written D-04 amendment: workflow_dispatch accepted instead of push for v1.0.1, headSha still exact (d04-amendment.txt, 09-CONTEXT.md)"
  - "pending todo: branches filter for on.push in ci.yml and validate.yml after the tag"
affects: [09-03, 09-04, 09-05]

actuals:
  tokens: 6500
  tasks: 2
  commits: 5
plan_head_before: e23b1a64bdc598048175bd9287eb215fb2051eba
plan_head_after: 3863764ff628b4e68e6037c72bf3ca4b7c71c494

tech-stack:
  added: []
  patterns:
    - "CI on the bump SHA counts only for runs with headSha == bump; for v1.0.1 event push or workflow_dispatch (D-04 amendment, T-09-07)"

key-files:
  created:
    - .planning/phases/09-v1-0-1-release/09-evidence/release/push-main.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/release/ci-bump-sha.json
    - .planning/phases/09-v1-0-1-release/09-evidence/release/ci-bump-sha-jobs.json
    - .planning/phases/09-v1-0-1-release/09-evidence/release/ci-bump-sha-wait.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/release/d04-amendment.txt
    - .planning/todos/pending/2026-10-12-ci-push-trigger-branches.md
  modified:
    - .planning/phases/09-v1-0-1-release/09-CONTEXT.md

key-decisions:
  - "D-04 amendment (owner-approved, v1.0.1 only): CI and Validate on the bump SHA count with event workflow_dispatch as well as push; headSha must still equal 7baec98 exactly"
  - "Root cause of the missing push run: ci.yml and validate.yml define on.push with only tags-ignore, so branch pushes never trigger them (since 2f786d8, plan 04-01)"
  - "The trigger fix (branches: [\"**\"]) waits until after the v1.0.1 tag, because a workflow change now would move the anchor SHA"

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
    description: "ci.yml and validate.yml green on exactly the bump SHA (event push or workflow_dispatch per D-04 amendment)"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 2 verify (amended filter): ci-bump-sha.json | jq (headSha == bump, push or workflow_dispatch, completed, success, CI and Validate) -> true"
        status: pass
      - kind: other
        ref: "Task 2 verify: ci-bump-sha-jobs.json six jobs all success; check-evidence-clean.sh PASS"
        status: pass
    human_judgment: true

duration: 47min
completed: 2026-10-12
status: complete
---

# Phase 9 Plan 02: Bump SHA push and CI gate Summary

**CI (Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests) and Validate (hassfest, HACS) are green on exactly the bump SHA `7baec98`. The runs were dispatched by the owner, under a written D-04 amendment, because the workflows never run on branch pushes. The bench run (09-03) may start.**

## Result

| Workflow | Run | Event | headSha | Conclusion | Jobs |
|----------|-----|-------|---------|------------|------|
| CI | 38299461144 | workflow_dispatch (main) | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | success | Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests: all success |
| Validate | 38299494978 | workflow_dispatch (main) | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | success | hassfest, HACS: all success |

- origin main was still `7baec98` when the evidence was taken (`git ls-remote`).
- The only annotation is a setup-uv cache-save warning, "another job may be creating this cache". It comes from two parallel jobs that share a cache key, and it does not affect the result.

## Performance

- **Duration:** about 47 min of executor time. The first attempt waited 45 min for a run that never came. The continuation took about 3 min.
- **First attempt:** 2026-10-12T07:15:47Z to 08:01:25Z (blocked)
- **Continuation:** 2026-10-12T19:42Z to 19:48Z
- **Tasks:** 2 of 2
- **Files:** 5 evidence files, 1 todo, and 1 CONTEXT note

## Accomplishments

- Task 1 verify passed. `push-main.txt` records origin_main_before `d0f660c…`, origin_main_after = bump, the owner's refspec command and `pushed_by: owner`.
- Task 2, first attempt: the poll ran for 45 min and found no run (`ci-bump-sha-wait.txt`, kept as history).
- Task 2, second attempt: both owner-dispatched runs completed green. `ci-bump-sha.json` now holds the real run list, and `ci-bump-sha-jobs.json` holds the six job conclusions. The amended jq filter prints `true`, the jobs check prints `true`, and `check-evidence-clean.sh` prints PASS.

## Task Commits

1. **Task 1: owner push verified.** `34c61bd` (push-main.txt)
2. **Task 2, first attempt: no run.** `daa1669` (ci-bump-sha.json `[]`, ci-bump-sha-wait.txt)
3. Blocked SUMMARY and STATE blocker: `40a0f48`, `c2b426c`
4. **Task 2, second attempt: green under the D-04 amendment.** `3863764` (ci-bump-sha.json, ci-bump-sha-jobs.json, d04-amendment.txt, 09-CONTEXT.md amendment note, pending todo)

## Deviations from Plan

### Blocker and root cause

**1. [Rule 3 - Blocking] The owner's push of the bump SHA triggered no CI or Validate run**
- **Found during:** Task 2, first attempt
- **Issue:** `gh run list --commit 7baec98` returned `[]` for 45 min.
- **Root cause (verified by the orchestrator):** `ci.yml` and `validate.yml` at the bump SHA define `on.push` with only `tags-ignore: ["v*.*.*"]` and no `branches` filter. When only tags or tags-ignore is set, GitHub Actions skips the workflow for branch pushes. 2f786d8 introduced this on 2026-10-02 (plan 04-01, already part of v1.0.0). The last push-triggered branch run was 97c178d, made before that commit. A test push of the bump SHA to the temporary branch `ci/v1.0.1-bump` also produced no run. Tag releases are not affected, because release.yml calls CI through `workflow_call`.
- **Correction:** `ci-bump-sha-wait.txt` says "branch main is not excluded". That reading was wrong. The line stays unchanged as history, and `d04-amendment.txt` corrects it.

### Owner decisions (D-04 amendment)

**2. Event `workflow_dispatch` accepted instead of `push` (owner-approved, v1.0.1 only)**
- The owner chose option B and dispatched CI and Validate on main (== 7baec98) themselves.
- Amended filter: `select(.headSha == $b and (.event == "push" or .event == "workflow_dispatch") and .status == "completed" and .conclusion == "success")`. The exact-SHA rule (T-09-07) is unchanged.
- Recorded in `09-evidence/release/d04-amendment.txt` and as an amendment note under D-04 in `09-CONTEXT.md`.

**3. Trigger fix deferred, captured as a todo**
- The fix is to add `branches: ["**"]` under `on.push` in both workflows. Making that change before the tag would move the anchor SHA (D-01, D-02), so it waits. It is tracked in `.planning/todos/pending/2026-10-12-ci-push-trigger-branches.md`.
- The temporary branch `ci/v1.0.1-bump` on origin is no longer needed. Deleting it is left to the owner.

### Process deviations (no product change)

**4. push-main.txt committed on its own.** The orchestrator asked for this after Task 1's verify. The content is the same, but it is in two commits instead of one.

**5. Extra evidence files.** `ci-bump-sha-wait.txt` documents the failed first attempt, and `d04-amendment.txt` records the amendment. The plan lists neither file.

**Total deviations:** 1 blocker (resolved by an owner decision) and 4 process or decision deviations. **Impact:** all four of the plan's truths hold. Only the bump SHA reached main. CI and Validate are green on the bump SHA under the amended event rule. Nothing was red. Claude ran no push, no dispatch and no re-run.

## Known Stubs

None.

## Threat Flags

None. The evidence holds only public run metadata: ids, names, conclusions, URLs and SHAs.

## Next

09-03: the bench run (UAT-02, UAT-04) on exactly 7baec98. A separate plan handles the owner's tag push, after the bench.

## Self-Check: PASSED

- FOUND: 09-evidence/release/push-main.txt (origin_main_after: 7baec98…, pushed_by: owner)
- FOUND: 09-evidence/release/ci-bump-sha.json (CI and Validate, headSha 7baec98, success)
- FOUND: 09-evidence/release/ci-bump-sha-jobs.json (6 jobs, all success)
- FOUND: 09-evidence/release/d04-amendment.txt
- FOUND: .planning/todos/pending/2026-10-12-ci-push-trigger-branches.md
- FOUND commits on HEAD: 34c61bd, daa1669, 40a0f48, c2b426c, 3863764
