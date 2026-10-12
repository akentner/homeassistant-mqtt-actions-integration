---
status: testing
phase: 09-v1-0-1-release
source:
  - .planning/phases/09-v1-0-1-release/09-CONTEXT.md
  - .planning/ROADMAP.md (Phase 9)
  - .planning/milestones/v1.0.1-REQUIREMENTS.md (wording of UAT-02 and UAT-04)
started: 2026-10-12T01:45:21Z
updated: 2026-10-12T20:05:00Z
---

## Current Test

number: 3
name: UAT-02 is an issue on the bump SHA (E1 to E3 fail in both rounds on ha-a and ha-b), and UAT-04 is blocked by it
expected: |
  The release stops before the tag. REL-01 stays open. The gap goes to an inserted Phase 9.1 on the release line (ROADMAP
  Phase 9 note). Phase 9.1 fixes it and runs the bench again on a new SHA. Plans 09-04 (tag) and 09-05 (release check) do not run.
awaiting: a planned Phase 9.1 (gap closure for block 3, then UAT-02 and UAT-04 again on the fix SHA)

## Build under test

The containers bind-mount `custom_components/mqtt_actions` of the main checkout read-only. The pinned identity is in
`09-evidence/00-preflight/build.txt`. `check-preflight.sh --quick` and `check-stale-anchor.sh` re-assert it before every run.

- sha: 7baec9878badc8fb49ea0d80243277d5ff3fb443 (the bump commit, manifest `version` 1.0.1)
- branch: main
- commit time: 2026-10-12T03:45:43+02:00
- image: ghcr.io/home-assistant/home-assistant:2026.9 (HA 2026.9.4 on ha-a and ha-b)
- ha-a (Test HA One, port 8123): instance id 3851f34f-fa67-4f3c-bba0-122465013c3d
- ha-b (Test HA Two, port 8124): instance id b4cf285b-428f-426b-9500-8e269634356e
- ha-c: stopped for the whole phase (D-07)
- Bench recovery before the pin (not a result): after a host restart, mosq, ha-a and ha-b had exited with code 135. mosq was
  started again, and because its persistence is off, every retained message was dropped. The instances republish their own
  documents at start. Record: `09-evidence/00-preflight/bench-recovery.txt`.

## Results (D-12)

| Check | Requirement or source | Result | Date | Build SHA | Evidence |
|-------|-----------------------|--------|------|-----------|----------|
| PRE | bench pin (D-08), REL-01 | pass | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/00-preflight |
| CI | ci.yml and validate.yml on the bump SHA (D-04 and its amendment), REL-01 | pass | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/release |
| UAT-02 | UAT-02, ROADMAP Phase 9 criterion 2, REL-01 | issue | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/uat-02 |
| UAT-04 | UAT-04, ROADMAP Phase 9 criterion 2, REL-01 | blocked | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/uat-04 |
| REL | tag, release workflow, Latest, notes (D-14), REL-01 | pending | - | - | .planning/phases/09-v1-0-1-release/09-evidence/release |

The allowed result tokens are the same as in 08-UAT.md: pending, pass, issue, blocked. A recorded block carries `sha:` (40 hex),
`date:` (ISO date), `evidence:` (a folder under 09-evidence) and `note:` after `result:`. An issue also carries `reported:` and
`severity:`. A FAIL is recorded as `issue`. It stands as the result and is never repeated to get a pass.

## Tests

### 1. PRE: bench pinned to the bump SHA
expected: ha-a and ha-b run exactly the custom_components tree of the bump SHA (byte-identical mount, pin check in lib.sh). The D-08 registry backups were taken with both instances stopped. check-preflight.sh (full) and check-stale-anchor.sh print PASS against the Phase 9 evidence root.
result: pass
sha: 7baec9878badc8fb49ea0d80243277d5ff3fb443
date: 2026-10-12
evidence: .planning/phases/09-v1-0-1-release/09-evidence/00-preflight
note: Plan 09-01. The red gate before the pin failed as expected, and the green gate after it passed (`gate-pin.txt`). Backup `~/ha-test/_backup-pre-phase9-20261012T014617Z` has mode 700, and the pointer is `~/ha-test/.current-backup-phase9`. Ten bench scripts are cmp-identical to the scrubbed Phase 8 copies. `reseed-tombstones.sh` has a path-only edit (`bench-scripts/cmp-proof.txt`, `reseed-tombstones.diff`). Plan 09-03 re-ran `check-preflight.sh --quick` and `check-stale-anchor.sh` before UAT-02, and both printed PASS.

### 2. CI: ci.yml and validate.yml green on the bump SHA
expected: CI (Ruff, Unit tests, Broker tests, Multi-instance tests) and Validate (hassfest, HACS) completed with success on a run whose headSha is exactly the bump SHA (D-04; event push or workflow_dispatch per the owner-approved D-04 amendment).
result: pass
sha: 7baec9878badc8fb49ea0d80243277d5ff3fb443
date: 2026-10-12
evidence: .planning/phases/09-v1-0-1-release/09-evidence/release
note: Plan 09-02. The owner pushed exactly the bump SHA to main (`push-main.txt`). That push triggered no run, because `on.push` in both workflows has only `tags-ignore` (`ci-bump-sha-wait.txt`, kept as history). The owner then dispatched CI run 38299461144 and Validate run 38299494978 on main == 7baec98. Both completed with success, and all six jobs succeeded (`ci-bump-sha.json`, `ci-bump-sha-jobs.json`). The amendment is recorded in `d04-amendment.txt`.

### 3. UAT-02: late legacy Discovery replay, two starts (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: issue
sha: 7baec9878badc8fb49ea0d80243277d5ff3fb443
date: 2026-10-12
evidence: .planning/phases/09-v1-0-1-release/09-evidence/uat-02
reported: "check-uat02.sh run on the bump SHA, exit 1 (FAIL). In round 1 and round 2, on ha-a and on ha-b: E1 fails (platform mqtt rows switch.lampe_test_2 and select.bar_select_2), E2 fails (the same two `_2` ids), E3 fails (legacy devices mqtt_actions_11111111-aaaa-4aaa-8aaa-000000000001 and mqtt_actions_b6bd2c0e-6d81-49ea-8025-4bd087bd718a). E4 holds (34 mqtt_actions rows identical to the baseline)."
severity: major
note: One run, 2026-10-12T19:49:15Z to 19:53:24Z, with the script that is byte-identical to the scrubbed Phase 8 copy (expectations E1 to E4 unchanged, D-09). It ran right after `check-preflight.sh --quick` and `check-stale-anchor.sh` printed PASS. `precheck.txt` names the bump SHA as the pinned sha. Both baselines were clean (no mqtt row, no `_2` row, no legacy device) and equal the 00-preflight registry baseline. The A7 payload check passed (`legacy-payload-check.txt`). Two rounds ran. In each, retained legacy Discovery for Lampe Test and Bar Select was published while both instances were stopped, then both started and settled for 90 s, then both stopped gracefully. After each stop, both registries held the two mqtt rows, both with `disabled_by` integration and `config_entry_id` null, and the two legacy mqtt devices (`round1-*.json`, `round2-*.json`). The logs show the guard line "Disabled 1 duplicate entities that core MQTT created for native devices" twice per instance in round 1, and the catch line "Removed 2 duplicate entities that a replayed legacy discovery created" twice per instance in both rounds. The rows were still in the flushed registry afterwards. In round 2, ha-b also logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids (`log-a.txt`, `log-b.txt`). Unlike the Phase 8 reference run, the legacy topics were still retained after each start (`retained-topics.txt`). The script cleared them at the end. No ABORT occurred, so no `bench-notes.txt` exists. The FAIL stands and was not repeated. The reference PASS on build b8232252 is in `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-02-rerun2`.

### 4. UAT-04: Discovery export and core prefix
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: blocked
sha: 7baec9878badc8fb49ea0d80243277d5ff3fb443
date: 2026-10-12
evidence: .planning/phases/09-v1-0-1-release/09-evidence/uat-04
note: Not run. UAT-04 must start from the D-06 state, which is proven by the exact line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0". That line was never produced. After the UAT-02 FAIL, both instances hold 2 live mqtt rows, and the deleted-entity records of both regression ids are gone (`reseed-tombstones.sh --check`: "nothing to flip"). `reseed-tombstones.sh` stopped both instances and backed up both registries to `~/ha-test/_backup-pre-phase9-20261012T014617Z/reseed-20261012T195511Z` (mode 700). It then ended in ABORT "ha-a holds live mqtt rows (2); the restoration needs none" before writing any file, and started both instances again (`prepare.txt`). Reaching D-06 would need a hand edit of live rows and fabricated records, which the plan forbids. The block is therefore `blocked` with the reason in `blocked.txt`. The blocker is the UAT-02 gap, not a bench defect. `check-marker.sh approved` and `check-uat04.sh run` were not called. The scripted expectations X1 to X10 are unchanged and wait for the Phase 9.1 run.

### 5. REL: tag, release workflow, Latest, release notes
expected: The owner pushes tag v1.0.1 on the bump SHA. release.yml is fully green (check-version, CI tiers, hassfest, HACS, release job). GitHub shows v1.0.1 as Latest, and the hand-written notes are applied (D-14).
result: pending
note: Not reached. The tag may follow only after UAT-02 and UAT-04 pass on the tagged SHA (REL-01). With block 3 `issue` and block 4 `blocked`, no tag is pushed on 7baec98, no release notes are written, and plans 09-04 and 09-05 do not run.

Not run in Phase 9 (D-05). They are not re-verified here, and nothing in this ledger claims they are:
- UAT-01: last recorded pass 2026-10-06 on b7f52b34, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-01`
- UAT-03: last recorded pass 2026-10-11 on b8232252, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-03-rerun2`
- P1-5: last recorded pass 2026-10-11 on b8232252, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/p1-5-rerun2`

## Summary

total: 5
passed: 2
issues: 1
pending: 1
skipped: 0
blocked: 1

## Requirement verdicts

A requirement is complete only when all of its blocks are `pass`. The verdict stays `pending` until block 5 is recorded (plan
09-05). With block 3 `issue`, REL-01 cannot pass on this SHA.

| Requirement | Block | Verdict | Evidence |
|-------------|-------|---------|----------|
| REL-01 | 1 to 5 | pending | 09-evidence/00-preflight (pass), 09-evidence/release (CI pass), 09-evidence/uat-02 (issue), 09-evidence/uat-04 (blocked), REL not reached |

## Gap closure

ACCEPTED-GAP-V101 closes for the v1.0.1 release only when blocks 3, 4 and 5 pass. Plan 09-05 records that. On 7baec98 the gap is
still open: block 3 is `issue` and block 4 is `blocked`. Phase 9.1 needs a fix SHA, a new bench run of UAT-02 and UAT-04 on that
SHA, and then the tag on that SHA.

## Gaps

- truth: "After a retained legacy Discovery replay at start, two startup rounds leave no mqtt row, no `_2` id and no legacy mqtt device on ha-a and ha-b (UAT-02 E1 to E3, MIG-05)"
  status: failed
  reason: "check-uat02.sh run on 7baec9878badc8fb49ea0d80243277d5ff3fb443 (2026-10-12): after both rounds, both instances keep switch.lampe_test_2 and select.bar_select_2 as platform mqtt rows (disabled_by integration, config_entry_id null) and the legacy devices mqtt_actions_<id> of both ids, although the catch logs 'Removed 2 duplicate entities that a replayed legacy discovery created'; E4 holds"
  severity: major
  test: 3
  artifacts:
    - path: ".planning/phases/09-v1-0-1-release/09-evidence/uat-02/result.txt"
      issue: "E1, E2 and E3 FAIL in round 1 and round 2 on ha-a and ha-b; E4 PASS"
    - path: ".planning/phases/09-v1-0-1-release/09-evidence/uat-02/round2-a.json"
      issue: "the remaining mqtt rows and legacy devices after the second round"
    - path: ".planning/phases/09-v1-0-1-release/09-evidence/uat-02/log-a.txt"
      issue: "guard and catch log lines per round"
    - path: ".planning/phases/09-v1-0-1-release/09-evidence/uat-04/blocked.txt"
      issue: "UAT-04 blocked by the remaining rows"
  missing:
    - "root cause of the remaining disabled replay rows (see the start-state observation below); fix in Phase 9.1, then UAT-02 and UAT-04 on the fix SHA"

## Observations

These are observations only, never results.

- **Start state of UAT-02 differs from the Phase 8 reference run.** Before this run, the deleted-entity records of the two
  regression ids had `disabled_by` integration on both instances (`uat-04/prepare.txt`, first projection, 2026-10-12T01:51Z,
  plan 09-01). They were left that way by the Phase 8 receiver-guard run. The Phase 8 UAT-02 reference run (uat-02-rerun2) started
  from null tombstones, which turned into `integration` during that run (08-UAT block 2). On 7baec98 the replay brought both
  records back as live rows with `disabled_by` integration, and they stayed. This is a lead for the Phase 9.1 root cause, not a
  finding about the check.
- **Projection after UAT-02:** both instances hold 2 live mqtt rows and no deleted-entity record of the regression ids
  (`uat-04/prepare.txt`, 2026-10-12T19:54:04Z and 19:55:11Z).
- **Guard log:** "Disabled 1 duplicate entities that core MQTT created for native devices" appears 2 times on ha-a and 2 times
  on ha-b since the start of UAT-02, all in round 1 (`uat-04/guard-log-a.txt`, `guard-log-b.txt`; UAT-04 did not run, so there is no UAT-04 window).
- **Post-restart:** after one graceful restart (2026-10-12T19:56:26Z, plus 90 s), both instances still hold 2 live mqtt rows
  (`disabled_by` integration). The guard logged nothing on that start. `check-uat02.sh clean` prints FAIL (`uat-04/post-restart.txt`,
  `post-run-*.json`, `post-restart-*.json`).
- **Bench-tooling defect (for Phase 9.1, not a result):** `check-uat02.sh clean` removes the UAT Marker rows from the live side of
  its comparison but not from the baseline. The Phase 8 baseline in `uat-02/` was taken before the marker existed. The Phase 9
  baseline holds the 4 marker rows, so `clean` reports "mqtt_actions rows (without hub rows) differ from the baseline" on a
  correct bench too. `reseed-tombstones.sh` requires `check-uat02.sh clean` after the restoration, so it would ABORT even on a
  clean bench. Phase 9.1 must fix this bench path (comparison only, no expectation) before its re-run.
- **ABORTs:** one, from `reseed-tombstones.sh`, caused by the UAT-02 gap and recorded in block 4. It is not a bench fix.

## Bench state left behind

- mosq, ha-a and ha-b are Up on the bump tree (`check-preflight.sh --quick` PASS, 2026-10-12T19:58Z). ha-c is stopped (D-07).
- The export is off. Nothing is retained under `mqtt_actions_export/#` or `homeassistant/device/#` (`check-uat04.sh clean` PASS).
- Live mqtt rows: 2 on ha-a and 2 on ha-b (`switch.lampe_test_2`, `select.bar_select_2`, `disabled_by` integration). The legacy
  mqtt devices of both ids remain. Nothing was removed by hand. The next bench run must deal with this state through product
  behavior or a documented, backed-up restoration.
- Backups: the D-08 backup `~/ha-test/_backup-pre-phase9-20261012T014617Z` (pointer `~/ha-test/.current-backup-phase9`), and the
  reseed copy `~/ha-test/_backup-pre-phase9-20261012T014617Z/reseed-20261012T195511Z` (mode 700). The reseed copy holds the
  registries after UAT-02, before any write.
- No stray `mosquitto_sub` is running. The bench and its tokens are kept until Phase 12 (owner follow-up from Phase 8).
