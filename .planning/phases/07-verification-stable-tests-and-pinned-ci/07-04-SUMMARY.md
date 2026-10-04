---
phase: 07-verification-stable-tests-and-pinned-ci
plan: 04
subsystem: release
tags: [github-actions, release-workflow, prerelease, ubuntu-24.04, proof-ledger]

requires:
  - phase: 07-01
    provides: "pinned ubuntu-24.04 runner in release.yml"
  - phase: 07-03
    provides: "remote branch gsd/phase-06-native-entity-residual-fixes and the CI proof ledger"
provides:
  - "Release proof: release.yml run for v1.0.1-rc1 passed all 8 jobs on ubuntu-24.04 and created a prerelease"
  - "Clean end state: release and tag deleted, manifest byte-identical to 1.0.0 locally and on the remote branch"
affects: [07-05]

actuals:
  tokens: 3500
  tasks: 3
  commits: 3

plan_head_before: 3a37790d6774f4f0826da07f44e515f82a558735
plan_head_after: 001e12240be099ff743c09300fd096160a44adeb

tech-stack:
  added: []
  patterns:
    - "Prerelease tag run as the only way to exercise check-version, the reusable workflows and the release job, followed by a mandatory cleanup"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/manifest.json
    - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md

key-decisions:
  - "Checkpoint decision (Task 1, blocking-human): the owner answered approve for the prerelease tag push in this session, before any bump, tag or push"

requirements-completed: [QLT-03]

status: complete
---

# Phase 7 Plan 04: Prerelease Release Proof Summary

**The release workflow passes end to end on the pinned `ubuntu-24.04` image: the `v1.0.1-rc1` run succeeded in all 8 jobs (check-version, four CI jobs, hassfest, HACS, Create GitHub release), created a prerelease, and the release, tag and manifest bump were then removed completely.**

## Decision taken at the checkpoint (Task 1)

The owner answered **approve** (blocking-human, never auto-approved) for pushing the prerelease tag `v1.0.1-rc1`. The answer was given in the session before the executor started; the push happened only after it. Only the pushes authorised in that decision were made: the branch to `refs/heads/gsd/phase-06-native-entity-residual-fixes` (fast-forward, no force) and the single tag `v1.0.1-rc1`. Nothing went to `main`, no second tag.

## Accomplishments

- **Task 2 (commit 4d24fb4):** `PRE` (commit before the bump) is `3a37790d6774f4f0826da07f44e515f82a558735`. The manifest line `"version": "1.0.0"` became `"version": "1.0.1-rc1"` and nothing else; the manifest-reading tests (`test_repo_structure`, `test_discovery`, `test_presence`, `test_docs`) gave 147 passed. Tag `v1.0.1-rc1` was created on `4d24fb4` and pushed with the branch at 2026-10-04T13:37:59Z.
- **Run:** https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37206309249, headSha `4d24fb4` (equal to the tag commit), conclusion `success`, 8 jobs, all `success`: Tag matches manifest version, CI / Ruff, CI / Unit tests, CI / Broker tests (Mosquitto), CI / Multi-instance tests, Validate / hassfest, Validate / HACS, Create GitHub release.
- **Image:** `Image: ubuntu-24.04` in all 8 job logs, the only distinct value (runner image version 20260927.320.1).
- **Prerelease:** `gh release view v1.0.1-rc1` returned `isPrerelease: true`.
- **A1 confirmed:** while the prerelease existed, `gh release list` kept `v1.0.0` as Latest.
- **Task 3 (commits 8a93a2f, 001e122):** `gh release delete v1.0.1-rc1 --cleanup-tag --yes` removed the release and the remote tag. The manifest was restored from `PRE` (`git diff --exit-code PRE -- manifest.json` exit 0, version `1.0.0`), committed as `chore(07-04): reset the manifest version after the release proof`, and pushed (`4d24fb4..8a93a2f`). The remote branch manifest reads `1.0.0`.
- **End state:** `git ls-remote --tags origin v1.0.1-rc1` empty, `git tag -l v1.0.1-rc1` empty, `gh release list` shows only `v1.0.0` (Latest) and `v0.1.0`, `git status --porcelain` empty.
- **A2 confirmed:** after the cleanup no `release.yml` run newer than the rc run exists (the tag deletion started no workflow). The branch pushes started no push-event runs of CI or Validate (informational, same as in plan 07-03).
- Plan verification: the plan's first verify command (run via `bash -c`) printed `VERIFY-OK`; the ledger check `release run conclusion: success` passed.

Full evidence is in `07-PROOF.md`, section "Release proof (plan 07-04)".

## Deviations from Plan

None in substance. Two small observations:

- **Ledger order:** the plan has Task 2 write the ledger section before the cleanup and Task 3 append the cleanup checks. I wrote the whole section once, after the cleanup, and committed it as `docs(07-04): record the release proof and its cleanup`. The recorded content is the same; the run was already green and nothing depended on the earlier write.
- **Local tag:** `git tag -d v1.0.1-rc1` reported that the tag did not exist, i.e. it was already gone after `gh release delete --cleanup-tag`. The end-state check (`git tag -l` empty) holds either way.

Also, the first verify attempt in my interactive shell failed on `"origin/$b:custom_components..."` because the shell parsed `$b:c` as a modifier; the plan's `bash -c` command passed unchanged.

## Net manifest change

Bump commit `4d24fb4` and reset commit `8a93a2f` stay on the phase branch; the net change of `manifest.json` against `PRE` is zero, so the covered-file digest of plan 07-05 sees identical bytes.

## Known Stubs

None.

## Threat Flags

None. T-07-09 and T-07-12 (mitigate) were applied: approval before the push, release and tag deleted and verified, manifest reset and checked on the remote branch.

## Self-Check: PASSED

- 07-PROOF.md section present with `release run conclusion: success`
- commits 4d24fb4, 8a93a2f, 001e122 exist on the branch; tag and prerelease absent; manifest 1.0.0 locally and on origin
