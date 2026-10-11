---
phase: 08-real-instance-verification
plan: 02
subsystem: verification-bench
tags: [uat, mig-05, mqtt-discovery, replay, home-assistant, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: pinned bench, probe users, 08-UAT.md ledger and recorder gate (plan 08-01)
provides:
  - UAT-02 recorded as pass with evidence from two real instances and two startup rounds
  - check-uat02.sh (run, live, clean) in ~/ha-test/bin with the expected values coded before observation
  - the live-republish duplicate observed and classified by the owner (WR03-LIVE-REPLAY = accepted-limit)
affects: [08-03, 08-04, 08-05, 08-06, 08-07, 08-08, 08-09, 08-10]
tech-stack:
  added: []
  patterns:
    - "legacy payload built by the repository's own build_discovery from the retained config documents, A7 check before publishing"
    - "registry evidence read only after a graceful stop"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-02/ (16 files)
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "WR03-LIVE-REPLAY: accepted-limit (owner, relayed by the orchestrator); no Gaps entry"
metrics:
  duration: about 1h wall clock (two 2.5 min rounds, a 3 min live variant, rest tooling and recording)
  completed: 2026-10-04
status: complete
commits: 2
plan_head_before: f0124aa096e4a4d4f4c2bfeced280f1255f26ee0
plan_head_after: 3d0cd71ffcb50808749bfba1d415154d4f71c95f
actuals:
  tokens: 40000
  tasks: 3
  commits: 2
---

# Phase 8 Plan 02: UAT-02 legacy replay at start Summary

UAT-02 passes on the native fleet at the pinned build: retained legacy Discovery published while ha-a and ha-b were stopped leaves no `mqtt` row, no `_2` entity and no legacy device after two starts on either instance, and the 30 `mqtt_actions` rows keep entity id, registry id, unique id and device id.

## What was done

- **Task 1 (ed45514):** wrote `~/ha-test/bin/check-uat02.sh` with the expectations E1 to E4 coded first. `run`: stop both, baselines, payloads built by `build_discovery` + `parse_document` from the retained config documents (unique ids match the registry on a and b, A7), publish retained QoS 1 with a second-client read-back, start, 90 s margin, graceful stop, evaluate; twice; then clear the topics and read back empty. Verdict PASS (all of E1 to E4, both rounds, both instances). `live`: legacy payloads published while running. `clean`: PASS afterwards. Evidence in `08-evidence/uat-02/`, block 2 recorded as `pass`.
- **Task 2 (checkpoint):** owner decision WR03-LIVE-REPLAY = accepted-limit, relayed by the orchestrator.
- **Task 3 (3d0cd71):** decision, live-republish Observation and the catch asymmetry Observation recorded; no Gaps entry; `check-recorded.sh UAT-02`, `check-uat02.sh clean` and the evidence scan print PASS.

## Findings

- The replay really created the twins: six `_2` tombstones (platform `mqtt`) per instance in `deleted_entities`, none in the pre-phase backup (`twin-tombstones.txt`). They were removed in every round.
- The INFO `logger` block works (research assumption A6): ha-b logged "Removed 3 duplicate entities that a replayed legacy discovery created" twice per round. ha-a logged no such line in either round, yet its registry is clean; the path that cleaned ha-a is not identified.
- Core MQTT cleared the retained legacy topics itself after the first start in both rounds.
- Live variant (observation only): six `_2` entities per instance within 20 s, still there at 45 s and after a graceful stop, gone after the next start (INFO catch lines appeared on ha-a, none on ha-b at that start).

## Deviations from Plan

**1. [Rule 3 - Blocking] `check-preflight.sh --quick` does not print PASS.** HEAD of the mount-source checkout moved from `b7f52b3` to `f0124aa` by planning-only commits, so the build.txt SHA comparison trips (and, at the time of the run, StartedAt versus the HEAD commit time). Verified by content instead: `git rev-parse b7f52b3:custom_components` equals `f0124aa:custom_components` (`bf898da9af4f43b0bc0a9e00e74c96116152a278`), the mount is byte-identical to that tree, host and container sha256 of the four key files match, the instances and `mosq` are Up. `check-uat02.sh` carries its own content-based `precheck()` (output in `uat-02/precheck.txt`, the failing gate output in `uat-02/preflight-quick-output.txt`). The last `--quick` run at the end of the plan still FAILs on the SHA line only (the StartedAt lines cleared because both instances restarted after that commit).
- **Unresolved, needs the user's own decision:** the orchestrator relayed that the user authorized changing `~/ha-test/bin/check-preflight.sh` to compare the `custom_components` tree instead of the SHA. An earlier attempt of that edit was denied by the permission system, and a message relayed by an agent cannot lift that denial, so the script is unchanged and `check-preflight.sh --quick` and the full variant were not recorded as PASS. To proceed, the user clears the permission denial (an allow rule for that edit, or a direct instruction in their own chat) and the edit is a one-hunk change in the pinned-build section (tree comparison via `git rev-parse <sha>:custom_components`, build time from `git log -1 -- custom_components`), after which both variants must be re-run.

**2. Mount-source checkout.** The sandbox forbids git calls into the main checkout from a worktree; the payload builder ran under the main `.venv` python with cwd in this worktree (identical `custom_components` tree).

**3. Live-variant cleanup order.** The legacy topics were cleared while the instances were stopped, not while running: a live clear makes core MQTT remove the registry entries itself, which would hide whether the next start's catch does it.

**4. Extra evidence files:** `precheck.txt`, `preflight-quick-output.txt`, `twin-tombstones.txt`. `check-recorded.sh --skeleton` fails by design now that block 2 is recorded.

## Bench edits (outside the repository)

- New: `~/ha-test/bin/check-uat02.sh`.
- Scratch: `~/ha-test/_uat02-run.out`, `~/ha-test/_uat02-live.out` (no secrets; delete at phase end).
- `~/ha-test/_snap-pre-live/` (copy of `.storage`, credentials) was created by the live variant and deleted again.
- `mosq` was not restarted, no token value was printed, ha-ws and production hosts were not touched.

## Known Stubs

None. No product code changed (`git status --porcelain -- custom_components tests .github` is empty).

## Threat Flags

None beyond the plan's register. T-08-06: both legacy topics cleared and read back empty, `clean` asserts it. T-08-07: snapshot taken, bench back at baseline (`clean` PASS).

## Self-Check: PASSED

- Evidence folder (16 files) and this SUMMARY exist and are committed; commits ed45514 and 3d0cd71 exist.
- `check-recorded.sh UAT-02`, `check-uat02.sh clean` and `check-evidence-clean.sh` print PASS. `check-preflight.sh --quick` FAILs on the SHA line only (see Deviation 1).
