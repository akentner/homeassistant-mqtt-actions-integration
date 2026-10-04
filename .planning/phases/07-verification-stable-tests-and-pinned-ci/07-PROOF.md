# Phase 7 Proof Ledger

Evidence ledger of Phase 7 (Verification, Stable Tests and Pinned CI). It is the source for the proof section of the
phase VERIFICATION (D-13). Plans 07-03, 07-04 and 07-05 append their sections below.

## QLT-02 stress proof (plan 07-02)

- **Date:** 2026-10-04 (run started 2026-10-04T12:57:58Z)
- **Head:** `f8e271e927061fc413d79f8afc793f566bc7e7b5` (all three 07-02 code commits included)
- **Test:** `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear`
- **Result line:** `repetitions passed: 50 of 50`
- **Wall-clock time:** 354 seconds
- **Load:** four busy loops (`while :; do :; done`, each bounded by `timeout 900`) and every repetition pinned with
  `taskset -c 0,1`, so spinners and test share two cores
- **Probe:** the permanent autouse fixture `always_slow_event_loop` (`tests/conftest.py`) was on during every
  repetition, so asyncio's slow-callback WARNING was present in every run
- **Cleanup:** no busy loop left running afterwards (`ps -eo args | grep -c '[w]hile :; do :; done'` printed 0)
- **Retries:** none; the loop stops at the first failure and none occurred

## Local three-run proof (plan 07-03)

- **Date:** 2026-10-04 (loop ran 2026-10-04T13:07:32Z to 2026-10-04T13:13:11Z)
- **Head:** `0f9ad70a9fe54d28c73d31ca3d7f8acc577789aa` (contains the 07-01 and 07-02 commits; working tree clean before and during the runs)
- **Local broker:** `mosquitto version 2.1.2` (CI installs 2.0.18 from the Ubuntu 24.04 archive, so this does not prove the CI broker tier)
- **Command (each run):** `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider`, one invocation over the
  unit, broker and multi-instance tiers, no xdist, no marker filter, always-slow probe on
- **Retries:** none; three sequential runs, each accepted only on `N passed` with no skipped, failed, error or deselected

| Run | Summary line | Duration |
|-----|--------------|----------|
| 1 | `1490 passed in 111.42s (0:01:51)` | 111.42 s |
| 2 | `1490 passed in 111.42s (0:01:51)` | 111.42 s |
| 3 | `1490 passed in 110.26s (0:01:50)` | 110.26 s |

Runs 1 and 2 report the same duration to the hundredth of a second. They are separate runs (separate log files written
about 113 seconds apart); the equal figure is a coincidence of the rounded pytest timer.

- **Ruff:** `uv run ruff check .` printed `All checks passed!`; `uv run ruff format --check .` printed `91 files already formatted`

## CI proof on ubuntu-24.04 (plan 07-03)

- **Date:** 2026-10-04 (runs 13:26Z to 13:33Z)
- **Remote branch:** `gsd/phase-06-native-entity-residual-fixes` (owner decision `push-branch-as-is`; created on origin by
  `git push origin HEAD:refs/heads/gsd/phase-06-native-entity-residual-fixes`; no tag, no release)
- **Proven sha:** `d92b87f3ebf427c6f63d3ccf0d95dd14c93af961` (the local-proof docs commit; code identical to the head of the
  local three-run proof `0f9ad70`, which differs only by planning documents)
- **Runner image (read from each job log):** `Image: ubuntu-24.04`, `Version: 20260927.320.1`, Ubuntu 24.04.5 LTS
- **Broker in CI (read from the broker job log):** Ubuntu archive package `mosquitto 2.0.18-1build3` (local broker is 2.1.2)
- **Retries:** none; each run was dispatched once, after the previous one had finished, and the next run id was taken only
  after it was newer than the previous one

| Run | Workflow | URL | Conclusion | Jobs (all success) | Image | Test counts |
|-----|----------|-----|------------|--------------------|-------|-------------|
| 1 | ci.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205596675 | success | Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests | ubuntu-24.04 / 20260927.320.1 | 1308 unit, 17 broker, 165 multi-instance |
| 2 | ci.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205721595 | success | Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests | ubuntu-24.04 / 20260927.320.1 | 1308 unit, 17 broker, 165 multi-instance |
| 3 | ci.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205851615 | success | Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests | ubuntu-24.04 / 20260927.320.1 | 1308 unit, 17 broker, 165 multi-instance |
| V | validate.yml | https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37205956233 | success | hassfest, HACS | ubuntu-24.04 / 20260927.320.1 | HACS: `All (9) checks passed` |

All four runs report `headSha` `d92b87f3ebf427c6f63d3ccf0d95dd14c93af961`. The three CI runs are consecutive dispatch runs
(no failure in between). 1308 + 17 + 165 = 1490, the same total as the local runs.

- **Push-event runs (informational, not counted):** none. `gh run list --branch gsd/phase-06-native-entity-residual-fixes
  --event push` returned an empty list at the dispatch time and again after the last run; GitHub did not start push-event
  runs for the branch creation.

## Release proof (plan 07-04)

- **Approval (D-13):** owner answered `approve` at the blocking-human checkpoint (Task 1) in the session of 2026-10-04,
  before any bump, tag or push; the executor was dispatched with that answer.
- **PRE (commit before the bump):** `3a37790d6774f4f0826da07f44e515f82a558735`
- **Bump commit:** `4d24fb429514c627fab2f3298ca66f9dfabaaecf` (`chore(07-04): manifest 1.0.1-rc1 for the release proof`)
- **Local pre-push check:** `tests/test_repo_structure.py tests/test_discovery.py tests/test_presence.py tests/test_docs.py`:
  147 passed with the manifest at 1.0.1-rc1
- **Tag:** `v1.0.1-rc1` on `4d24fb4`, pushed 2026-10-04T13:37:59Z together with
  `HEAD:refs/heads/gsd/phase-06-native-entity-residual-fixes` (fast-forward `d92b87f..4d24fb4`)
- **Run URL:** https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/37206309249
  (event push, head branch `v1.0.1-rc1`, headSha `4d24fb429514c627fab2f3298ca66f9dfabaaecf` = the tag commit)
- release run conclusion: success

| Job | Conclusion |
|-----|------------|
| Tag matches manifest version | success |
| CI / Ruff | success |
| CI / Unit tests | success |
| CI / Broker tests (Mosquitto) | success |
| CI / Multi-instance tests | success |
| Validate / hassfest | success |
| Validate / HACS | success |
| Create GitHub release | success |

- **Job count:** `gh run view ... --json jobs` returned 8 jobs.
- **Runner image (from `gh run view --log`):** `Image: ubuntu-24.04` appears 8 times and is the only distinct image value
  (one per job); `Version: 20260927.320.1` (runner image version) appears 8 times
- **Prerelease flag:** `gh release view v1.0.1-rc1 --json isPrerelease` returned `isPrerelease: true`
- **A1 (Latest marker):** while the prerelease existed `gh release list` showed `v1.0.1-rc1 Pre-release`, `v1.0.0 Latest`,
  `v0.1.0`; v1.0.0 kept the Latest marker (assumption A1 confirmed)

### Cleanup (Task 3, ran after the green run)

- `gh release delete v1.0.1-rc1 --cleanup-tag --yes` removed the release and the remote tag; the follow-up
  `git tag -d v1.0.1-rc1` reported the local tag as already absent (the `gh` call or the earlier state had removed it)
- Manifest reset: `git restore --source=3a37790... --staged --worktree -- custom_components/mqtt_actions/manifest.json`;
  `git diff --exit-code 3a37790... -- custom_components/mqtt_actions/manifest.json` exited 0 (byte-identical);
  `jq -r .version` printed `1.0.0`
- Reset commit: `8a93a2f5d6252471038a993a67c0d9b3b534232b` (`chore(07-04): reset the manifest version after the release proof`),
  pushed `4d24fb4..8a93a2f` to `gsd/phase-06-native-entity-residual-fixes`
- `git ls-remote --tags origin v1.0.1-rc1`: empty; `git tag -l v1.0.1-rc1`: empty
- `gh release list --limit 5`: `v1.0.0 Latest`, `v0.1.0` only
- Remote branch manifest (`git show origin/gsd/phase-06-native-entity-residual-fixes:custom_components/mqtt_actions/manifest.json`): version `1.0.0`
- **A2 (tag deletion starts no workflow):** `gh run list --workflow release.yml --limit 3` after the cleanup showed the rc run
  `37206309249` as the newest release run; no run started from the deletion (assumption A2 confirmed)
- **Push-event runs (informational):** none for the branch pushes `d92b87f..4d24fb4` and `4d24fb4..8a93a2f`;
  `gh run list --branch gsd/phase-06-native-entity-residual-fixes` still lists only the four dispatch runs of plan 07-03

## QLT-01 re-verification (plan 07-05)

### Freeze (Task 1)

- **Frozen sha the verifiers judge:** `81db888c5e49389ea7dc27626100f6e090535e61` (branch `gsd/phase-07-verification-stable-tests-and-pinned-ci`,
  `git status --porcelain` empty before this section was written; this ledger section is the only change after the freeze and
  touches no covered file)
- Preconditions: manifest version `1.0.0`; no local or remote tag `v1.0.1-rc1`; ledger holds `release run conclusion: success`

### Before state (`verification status ARCHIVED_DIR --pick status`)

| Phase | Archived directory | Status before | PLAN + SUMMARY files |
|-------|--------------------|---------------|----------------------|
| 1 | `.planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch` | stale | 12 |
| 2 | `.planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution` | stale | 10 |
| 3 | `.planning/milestones/v1.0-phases/03-trust-central-config-and-ownership` | stale | 16 |
| 4 | `.planning/milestones/v1.0-phases/04-operations-recovery-and-release` | stale | 28 |
| 5 (surfaced, out of scope) | `.planning/milestones/v1.0-phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco` | stale | 18 |

- `init.manager` lists only phases 6, 7, 8 and 999.1 (milestone v1.0.1); it never listed Phases 1 to 5, so it was vacuously
  clean (`verification_stale_check_indeterminate: false` for all four) and cannot be the gate.
- Phase 5 reads stale for the same cause (stored `covered_files` name pre-archive paths). QLT-01 names Phases 1 to 4 only, so it is
  not re-verified in this plan; surfaced for the owner.
