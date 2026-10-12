---
phase: 09-v1-0-1-release
plan: 01
subsystem: release
tags: [release, bench, preflight, evidence, manifest, v1.0.1]

requires:
  - phase: 08-real-instance-verification
    provides: bench scripts (preflight.sh, check-preflight.sh, check-uat02.sh, check-uat04.sh, reseed-tombstones.sh) and their scrubbed copies
provides:
  - "bump commit 7baec9878badc8fb49ea0d80243277d5ff3fb443 on main (manifest version 1.0.1, one line)"
  - "bench ha-a and ha-b pinned to the bump SHA, check-preflight.sh (full) and check-stale-anchor.sh PASS against the Phase 9 evidence root"
  - "~/ha-test/phase9.env pointing the unchanged bench scripts at 09-evidence"
  - "reseed-tombstones.sh parametrized by path (RESEED_EV_DIR, RESEED_BACKUP_POINTER)"
  - "push readiness of the bump SHA with the owner's exact refspec push command"
affects: [09-02, 09-03, 09-04, 09-05]

actuals:
  tokens: 29920
  tasks: 3
  commits: 4
plan_head_before: 3983710bde4659eca1cbb9750d7185d831163ee0
plan_head_after: 4ab3bfca9e86bad38f43c26e1fbc84d87d507333

tech-stack:
  added: []
  patterns:
    - "Phase evidence root via PHASE8_EVIDENCE_ROOT in ~/ha-test/phase9.env, lib.sh unchanged"
    - "Owner pushes the exact bump SHA with a refspec so CI runs on it, not on a later docs commit"

key-files:
  created:
    - .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/build.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/backup-phase9.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/bench-recovery.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/gate-pin.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/bench-scripts/cmp-proof.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/bench-scripts/reseed-tombstones.diff
    - .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/bench-scripts/README.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/uat-04/prepare.txt
    - .planning/phases/09-v1-0-1-release/09-evidence/release/push-readiness.txt
  modified:
    - custom_components/mqtt_actions/manifest.json

key-decisions:
  - "Bump SHA 7baec9878badc8fb49ea0d80243277d5ff3fb443 is the single anchor for bench, CI, tag and release (D-01, D-02, D-03)"
  - "Owner push command for 09-02: git push origin 7baec9878badc8fb49ea0d80243277d5ff3fb443:refs/heads/main (refspec, because main already carries evidence commits after the bump)"
  - "At pin time the regression tombstones on ha-a and ha-b are disabled_by integration; the flip to null (D-06) happens after UAT-02 in a later plan"

patterns-established:
  - "Every bench call: bash -c '. ~/ha-test/phase9.env && ~/ha-test/bin/<script> <args>' from the repo root"

requirements-completed: [REL-01]

coverage:
  - id: D1
    description: "Bump commit on main changes exactly the manifest version line 1.0.0 -> 1.0.1, no CI-skip marker"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 1 verify blocks 2 and 3 (build.txt sha == last manifest commit on main, numstat 1 1, version 1.0.1, no skip marker)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Bench ha-a and ha-b run exactly the bump tree, proven against the Phase 9 evidence root"
    requirement: REL-01
    verification:
      - kind: integration
        ref: "bash -c '. ~/ha-test/phase9.env && ~/ha-test/bin/check-preflight.sh' (full) and check-stale-anchor.sh"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-08 registry backup with both instances stopped, mode 700, pointer ~/ha-test/.current-backup-phase9"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 1 verify block 4 (pointer, mode 700, four non-empty registry copies)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Bench check scripts byte-identical to Phase 8; reseed-tombstones.sh path-only edit with recorded diff"
    requirement: REL-01
    verification:
      - kind: other
        ref: "Task 2 verify blocks 1 and 2 (cmp of ten scripts and ws.py; awk allowlist over the reseed diff, bash -n)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Push readiness: ruff, format and pytest green on the bump tree, origin/main ancestor of the bump, refspec push command recorded"
    requirement: REL-01
    verification:
      - kind: unit
        ref: "uv run ruff check . && uv run ruff format --check . && uv run pytest -q (1535 passed, 2 xfailed)"
        status: pass
      - kind: other
        ref: "Task 3 verify block 3 (merge-base --is-ancestor, push_command line)"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-10-12
status: complete
---

# Phase 9 Plan 01: Bump SHA anchor and bench pin Summary

**Bump SHA `7baec9878badc8fb49ea0d80243277d5ff3fb443`: manifest 1.0.1 on main, ha-a and ha-b pinned to exactly that tree with check-preflight.sh PASS against the Phase 9 evidence root, bench scripts proven unchanged, and the owner's refspec push command recorded.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-10-12T01:45:21Z
- **Completed:** 2026-10-12T01:56:40Z
- **Tasks:** 3 / 3
- **Files:** 1 product file modified (manifest.json), 30 evidence files created

## Accomplishments

- main was fast-forwarded to the phase branch (`3e0f565..3983710`, .planning commits only) and is the checked-out branch. The bump commit `7baec98` changes one line of `manifest.json`.
- Red gate before the pin: `check-preflight.sh --quick` under `phase9.env` failed with exit 1 and named the Phase 9 path. Green gate after the pin: `check-preflight.sh` (full, with the guard routing proof) and `check-stale-anchor.sh` both PASS. `build.txt` records `sha: 7baec987…` and `branch: main`. Both instances report `"version": "1.0.1"` in their heartbeats.
- D-08 backup: `~/ha-test/_backup-pre-phase9-20261012T014617Z` (mode 700, pointer `~/ha-test/.current-backup-phase9`). It holds both registries of a and b, taken while both instances were stopped. `preflight.sh stage1` also took its own full backup, `~/ha-test/_backup-pre-phase8-20261012T014640Z`.
- Bench recovery: mosq, ha-a and ha-b had Exited (135) after a host restart. mosq was started again; its StartedAt changed from 2026-10-11 12:31:00 to 2026-10-12 03:46:21, and stage1 re-anchored it. Pointer copies `*.pre-phase9` were kept.
- D-09: ten scripts are cmp-identical to the Phase 8 copies. `reseed-tombstones.sh` changed in three path lines plus one header comment (`reseed-tombstones.diff`). Its `--check` writes to `09-evidence/uat-04/prepare.txt`, and no `uat-04-rerun2` folder appears.
- Push readiness: origin/main `d0f660cb` is an ancestor of the bump, with 191 commits to push. Ruff and format are clean, and pytest shows 1535 passed, 2 xfailed. The broker tier ran because mosquitto is on PATH.

## Task Commits

1. **Task 1 (tracer): bump + pin.** `7baec98` (chore, the bump) and `c10719d` (docs, 00-preflight evidence)
2. **Task 2: bench scripts unchanged.** `555f815` (docs)
3. **Task 3: push readiness.** `4ab3bfc` (docs)

## Owner action for plan 09-02

```
git push origin 7baec9878badc8fb49ea0d80243277d5ff3fb443:refs/heads/main
```

Then wait until ci.yml and validate.yml are green on that SHA (D-04). No tag yet (plan 09-04).

## Bench state left behind

- mosq, ha-a and ha-b are Up on the bump tree. ha-c is stopped (D-07). No stray `mosquitto_sub` is running.
- `~/ha-test/phase9.env` (0644, paths only). Every later Phase 9 bench call sources it.
- Regression tombstones at pin time: on both instances, `switch.lampe_test_2` and `select.bar_select_2` are `disabled_by: integration`, with 0 live mqtt rows. `reseed-tombstones.sh` flips them back to null after UAT-02 (D-06).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] zsh modifier mangled the push_command line before commit**
- **Found during:** Task 3
- **Issue:** The Bash tool's shell is zsh, and zsh read `$B:r` as the `:r` history modifier. The first draft of push-readiness.txt therefore had `...3fb443efs/heads/main`.
- **Fix:** Corrected the line to `push_command: git push origin 7baec98…:refs/heads/main` with an exact edit before the commit. The Task 3 verify (`grep -qx "push_command: git push origin $B:refs/heads/main"`) passes.
- **Files modified:** .planning/phases/09-v1-0-1-release/09-evidence/release/push-readiness.txt
- **Commit:** 4ab3bfc

### Process notes (no plan change)

- **Commits on main:** the executor's default guard refuses commits on the default branch. This plan (D-01) and the orchestrator require every Phase 9 commit on main, so the commits went to main as specified. Nothing was pushed.
- **phase9.env written with the Write tool:** a shell safety check blocked the `printf > file` command. The file's content is exactly the four lines the plan specifies.
- **shellcheck:** the only finding on the edited `reseed-tombstones.sh` is the existing SC2016 info note at the `istarget=` line. The Phase 8 copy has the same note, so the edit did not introduce it.

**Total deviations:** 1 auto-fixed (Rule 1). **Impact:** none on the plan's truths. The bump stays one line, and the evidence names the bump SHA.

## Known Stubs

None.

## Threat Flags

None. Evidence holds only fixed-field projections, sizes and sha256 values, and topic ACL rules. `check-evidence-clean.sh` printed PASS over all of `09-evidence`.

## Next

Ready for 09-02 (owner pushes the bump SHA; Claude checks CI with `gh run list --commit 7baec98…`).

## Self-Check: PASSED

- FOUND: custom_components/mqtt_actions/manifest.json at version 1.0.1 in commit 7baec98
- FOUND: 00-preflight/{build,mount-hashes,heartbeats,retained-snapshot,acl-after,backup-manifest,backup-phase9,bench-recovery,gate-pin}.txt, registry-baseline-{a,b}.json; no verdict.txt
- FOUND: bench-scripts/{cmp-proof.txt,reseed-tombstones.diff,README.txt,phase9.env} and the twelve script copies
- FOUND: uat-04/prepare.txt (headed `== projection (--check, read-only)`), release/push-readiness.txt
- FOUND commits on HEAD: 7baec98, c10719d, 555f815, 4ab3bfc
- Plan-level verification rerun: check-preflight.sh PASS, build.txt sha == bump, cmp and reseed allowlist pass, push-readiness names the bump and refspec, ha-c not running, evidence scan PASS
