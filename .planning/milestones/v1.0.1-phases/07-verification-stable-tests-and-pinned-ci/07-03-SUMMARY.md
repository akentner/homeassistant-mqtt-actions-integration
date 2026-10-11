---
phase: 07-verification-stable-tests-and-pinned-ci
plan: 03
subsystem: testing
tags: [pytest, mosquitto, github-actions, workflow-dispatch, ubuntu-24.04, proof-ledger]

requires:
  - phase: 07-01
    provides: "pinned ubuntu-24.04 runner and structure guard"
  - phase: 07-02
    provides: "stable tests (always-slow probe, scoped log assertions) and the ledger 07-PROOF.md"
provides:
  - "Local three-run proof: 1490 passed three times in a row, broker tier mandatory, Ruff clean"
  - "Branch gsd/phase-06-native-entity-residual-fixes on origin (owner decision push-branch-as-is)"
  - "CI proof: three consecutive green ci.yml dispatch runs and one green validate.yml run on d92b87f, image ubuntu-24.04 20260927.320.1"
affects: [07-04, 07-05]

actuals:
  tokens: 2600
  tasks: 3
  commits: 2

plan_head_before: 0f9ad70a9fe54d28c73d31ca3d7f8acc577789aa
plan_head_after: 6afcea658d02d6e07e253c20b8526802ee0f4338

tech-stack:
  added: []
  patterns:
    - "Proof by consecutive runs on a named sha, with image and broker versions read from the job log, never assumed"

key-files:
  created: []
  modified:
    - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md

key-decisions:
  - "Checkpoint decision (Task 2): push-branch-as-is. REMOTE_BRANCH is gsd/phase-06-native-entity-residual-fixes; the branch was pushed under that name from the local branch gsd/phase-07-verification-stable-tests-and-pinned-ci via HEAD:refs/heads/..."
  - "The proven sha is d92b87f (the docs commit of the local proof); its code is identical to 0f9ad70, the head of the local runs"

requirements-completed: [QLT-02, QLT-03]

status: complete
---

# Phase 7 Plan 03: Local and CI Proof Summary

**The v1.0.1 head is proven sound twice: three consecutive local full-suite runs (1490 passed, real Mosquitto 2.1.2, no skip) and three consecutive green CI dispatch runs plus one green Validate run on the pinned `ubuntu-24.04` image (version 20260927.320.1, Mosquitto 2.0.18 in CI), all on sha `d92b87f`.**

## Decision taken at the checkpoint (Task 2)

The owner chose **push-branch-as-is**. The remote branch is `gsd/phase-06-native-entity-residual-fixes`; it did not exist on origin before. The only push was `git push origin HEAD:refs/heads/gsd/phase-06-native-entity-residual-fixes` (new branch, no force, no tag, no release, nothing to `main`). Merging into `main` is not part of this plan.

## Accomplishments

- **Task 1 (commit d92b87f):** three sequential local runs of `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider` on head `0f9ad70`: `1490 passed` each (111.42 s, 111.42 s, 110.26 s), no skipped/failed/deselected. Ruff check and format check clean. Local broker `mosquitto version 2.1.2`.
- **Task 3 (commit 6afcea6):** pushed the branch, then dispatched `ci.yml` three times sequentially and `validate.yml` once, each on `--ref gsd/phase-06-native-entity-residual-fixes`, each run id taken only after it was newer than the previous one. No retry, no extra dispatch.

| Run | URL | Result |
|-----|-----|--------|
| CI 1 | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205596675 | success (Ruff, Unit, Broker, Multi-instance) |
| CI 2 | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205721595 | success (same four jobs) |
| CI 3 | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205851615 | success (same four jobs) |
| Validate | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205956233 | success (hassfest, HACS: `All (9) checks passed`) |

- Every run reports `headSha` `d92b87f3ebf427c6f63d3ccf0d95dd14c93af961` and, in the job log, `Image: ubuntu-24.04`, `Version: 20260927.320.1` (Ubuntu 24.04.5 LTS). The broker job installed `mosquitto 2.0.18-1build3`. CI test counts per run: 1308 unit + 17 broker + 165 multi-instance = 1490, equal to the local total.
- The plan's verify command exited 0: `green ci.yml dispatch runs on d92b87f...: 3` and `validate.yml: success`.

## Deviations from Plan

None - plan executed exactly as written, with one observation:

- **Push-event runs:** the plan expected the push to start push-event runs of CI and Validate (informational). `gh run list --branch gsd/phase-06-native-entity-residual-fixes --event push` returned an empty list at dispatch time and after the last run; GitHub started none for the branch creation. Recorded in the ledger as "none". This does not affect the three dispatch runs and is not a finding against the code.

## Issues Encountered

None. No run failed; no auth gate occurred.

## Known Stubs

None. No code was changed in this plan (`git log --grep='(07-03)' -- custom_components tests .github pyproject.toml uv.lock` is empty).

## Threat Flags

None. The push published the branch (T-07-07, accepted, explicit decision preceded it); dispatched workflows keep their `contents: read` permissions (T-07-08, unchanged).

## Notes for plan 07-04

- The branch is on origin at `d92b87f`; the local branch is now 1 commit ahead (`6afcea6`, the CI proof ledger) plus this SUMMARY commit. Neither is pushed, as the plan prescribes: 07-04 pushes again together with the rc commit.
- `commits: 2` in the frontmatter was measured with `git rev-list --count 0f9ad70..HEAD` before this SUMMARY commit.

## Self-Check: PASSED

- 07-PROOF.md contains the sections "Local three-run proof" and "CI proof on ubuntu-24.04" (greps 1 and 6 matches)
- Commits d92b87f and 6afcea6 exist on the local branch
- `origin/gsd/phase-06-native-entity-residual-fixes` resolves to d92b87f
