---
phase: 08-real-instance-verification
plan: 01
subsystem: verification-bench
tags: [uat, bench, mosquitto, home-assistant, evidence]
requires:
  - phase: 07-verification-stable-tests-and-pinned-ci
    provides: the verified build and the ten deferred human-verification items
provides:
  - pinned build identity for ha-a and ha-b (b7f52b3) with host-versus-container mount proof
  - bench helpers in ~/ha-test/bin (guard, preflight, gates) and throw-away broker users uat_probe and uat_bridge
  - 08-UAT.md ledger with 14 pending blocks and the recorder gate check-recorded.sh
  - owner decision API-ACCESS = owner-tokens, both tokens verified
affects: [08-02, 08-03, 08-04, 08-05, 08-06, 08-07, 08-08, 08-09, 08-10]
tech-stack:
  added: []
  patterns:
    - "all API calls via ha-test-guard (fixed letter map, env ignored, ha-ws never used)"
    - "evidence scan (check-evidence-clean.sh) before every evidence commit"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-UAT.md
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/ (8 files)
  modified: []
decisions:
  - "API-ACCESS: owner-tokens (tokens in ~/ha-test/.token-a and .token-b, mode 0600, outside the repo)"
  - "Helper scripts live in ~/ha-test/bin outside the repo; a scrubbed copy is added by plan 08-10"
metrics:
  duration: about 2h wall clock including a 60 s heartbeat listen and two container restarts
  completed: 2026-10-04
status: complete
commits: 3
plan_head_before: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
plan_head_after: 4ad5edb (task commits; the SUMMARY commit follows)
actuals:
  tokens: 45000
  tasks: 3
  commits: 3
---

# Phase 8 Plan 01: Bench preflight and ledger Summary

Pinned the build mounted by ha-a and ha-b (b7f52b3, HA 2026.9.4), restarted both at it, proved the broker round trip with a second client, created the 14-block `08-UAT.md` ledger with its recorder gate, and recorded the owner decision for API access (owner-tokens, both tokens verified).

## What was done

- **Task 1 (38ac724):** `~/ha-test/bin/{lib.sh, ha-test-guard, ha-test-ws.py, bench-users.sh, preflight.sh, check-preflight.sh, check-evidence-clean.sh}`. Backup `~/ha-test/_backup-pre-phase8-20261004T184824Z/{a,b,mosquitto}` taken with both instances stopped. Broker users `uat_probe` and `uat_bridge` added and the broker reloaded by SIGHUP; `mosq` was never restarted (StartedAt unchanged, asserted by the check). INFO `logger` block added to both test configurations. ha-a and ha-b restarted 2026-10-04 20:48:48 +0200, later than the commit time. Host and container sha256 of manager.py, takeover.py, const.py and document.py match on both. Both instance heartbeats heard, both retained availability topics `online`, `uat_bridge` cannot read availability. `check-preflight.sh` (full, with the guard routing proof) and `--quick` print PASS.
- **Task 2 (5feaaaa):** `08-UAT.md` with exactly 14 blocks at `result: pending`, the D-05 table, Gaps, Observations, Owner decisions and a "Bench state left behind" section. `~/ha-test/bin/check-recorded.sh` (`--skeleton`, `{id}`, `--all`) accepts it; negative cases (verdict mismatch, pending block) were exercised in scratch space.
- **Task 3 (4ad5edb):** decision API-ACCESS = owner-tokens recorded. Mode 0600 confirmed on both token files; `ha-test-guard a|b ws raw auth/current_user` succeeded for both (token a ok, token b ok). `check-evidence-clean.sh` still prints PASS. No token value appears anywhere in the repository.

## Deviations from Plan

**1. [Rule 3 - Blocking] Mount-source checkout cannot be queried with git from this worktree.**
- **Found during:** Task 1 start
- **Issue:** the containers mount the main checkout; the sandbox refuses `git -C` and `cd` into it for a worktree-isolated agent, so the plan's `git rev-parse` and `git status --porcelain` in the mount-source checkout could not run.
- **Fix:** `lib.sh pin` reads HEAD from the mount-source checkout's `.git/HEAD` and ref files (plain file reads), takes the commit time from the shared object database, and `mount_clean` proves cleanliness by content: every blob of `git ls-tree -r <sha> custom_components` is hashed against the file on disk and the file lists must be identical (ignoring `__pycache__`). This is stricter than `git status`. Result: main checkout HEAD b7f52b3 equals this worktree's base and the mount is byte-identical to it.
- **Files modified:** `~/ha-test/bin/lib.sh` (outside the repo)

**2. [Rule 1 - Bug] StartedAt parsing.** `date -d` rejected podman's "CEST" suffix, so the first full check run failed on a false negative. The suffix is stripped in `check-preflight.sh`.

**3. [Rule 2 - Missing critical] Evidence privacy and extra assertion.** `reg_rows` lists ids only for platforms `mqtt` and `mqtt_actions`; other entities appear only when their id ends in `_2` (and without ids), so unrelated device identifiers (wled, cast) stay out of the public evidence. `check-preflight.sh` additionally asserts that `mosq` StartedAt equals the value saved before the phase.

**4. Evidence location.** Evidence is written into this worktree's tree (the evidence root follows the git toplevel). The branch must be merged before later plans run `check-preflight.sh` from the phase branch.

**5. Executor-protocol note.** The final SUMMARY commit is a fourth commit on top of the three task commits recorded in `commits:`.

## Observations

- The guard routing proofs left 3 "invalid authentication" warnings in `~/ha-test/a/home-assistant.log` (expected).
- The INFO `logger` block is not yet proven to work: no INFO line has been emitted since the restart. Plan 08-02 shows it (research assumption A6); the registry stays the proof if `logger` rejects it.
- Bench state left behind (to clean up at phase end): users `uat_probe` and `uat_bridge` (`bench-users.sh remove`), `~/ha-test/.mqtt-uat.env`, the `logger` blocks, the two token files (owner revokes them), the backup directory.

## Known Stubs

None. No product code was changed (`git status --porcelain -- custom_components tests .github` is empty).

## Threat Flags

None beyond the plan's threat register. T-08-01 to T-08-05 are mitigated as planned (guard, evidence scan, second-client read-back, 0600 password file, pinned SHA with hash comparison).

## Self-Check: PASSED

- 08-UAT.md and the eight `00-preflight` evidence files exist and are committed.
- Commits 38ac724, 5feaaaa, 4ad5edb exist on the branch.
- `check-preflight.sh`, `check-recorded.sh --skeleton`, `check-evidence-clean.sh` print PASS.
