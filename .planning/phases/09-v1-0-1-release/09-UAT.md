---
status: testing
phase: 09-v1-0-1-release
source:
  - .planning/phases/09-v1-0-1-release/09-CONTEXT.md
  - .planning/ROADMAP.md (Phase 9)
  - .planning/milestones/v1.0.1-REQUIREMENTS.md (wording of UAT-02 and UAT-04)
  - .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-CONTEXT.md
started: 2026-10-12T01:45:21Z
updated: 2026-10-14T22:56:08Z
---

## Current Test

number: 5
name: REL on the fix SHA 681c58793b656b51869906b62f2564829de7a10d (tag, release workflow, Latest, release notes)
expected: |
  Phase 9.1 closed the UAT-02 gap on the fix SHA: the heal start (block 8), UAT-02 from integration tombstones (block 9), UAT-02
  from null tombstones (block 10) and UAT-04 (block 11) pass on 681c58793b656b51869906b62f2564829de7a10d, and CI and Validate are
  green on exactly that SHA (block 7). The owner decides the one-way tag v1.0.1 on that SHA in plan 09-04, and plan 09-05 checks
  the release and records block 5.
awaiting: the re-pointed plans 09-04 (tag) and 09-05 (release)

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

### Phase 9.1 build (fix SHA)

The list above is history: it describes the 7baec98 bench of blocks 1 to 5. Blocks 6 to 11 ran on the fix SHA. The pinned
identity is in `.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/00-preflight/build.txt`.

- sha: 681c58793b656b51869906b62f2564829de7a10d (FIX, the last commit on main that changes a path outside `.planning/`; manifest
  `version` 1.0.1, unchanged since 7baec98)
- commit time: 2026-10-14T16:14:54+02:00
- image: ghcr.io/home-assistant/home-assistant:2026.9 (HA 2026.9.4 on ha-a and ha-b)
- ha-a: instance id 3851f34f-fa67-4f3c-bba0-122465013c3d; ha-b: instance id b4cf285b-428f-426b-9500-8e269634356e; ha-c stopped
- Pin: HEAD was detached at FIX only for preflight stage1 and stage2 (2026-10-14T22:24:55Z to 22:25:59Z) and then restored to
  main with an empty index diff (`pin-window.txt`), so `build.txt` names FIX itself with `branch: (detached)`. The mount is
  byte-identical to the custom_components tree of FIX (blob by blob, no extra files).
- Bench recovery before the pin (not a result): after a host crash, mosq, ha-a and ha-b had exited with code 135. Only mosq was
  started again (persistence off, nothing retained). ha-a and ha-b kept their StartedAt from before the fix, so stage2 was the
  first start of the fix build (`00-preflight/bench-recovery.txt`).

## Results (D-12)

| Check | Requirement or source | Result | Date | Build SHA | Evidence |
|-------|-----------------------|--------|------|-----------|----------|
| PRE | bench pin (D-08), REL-01 | pass | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/00-preflight |
| CI | ci.yml and validate.yml on the bump SHA (D-04 and its amendment), REL-01 | pass | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/release |
| UAT-02 | UAT-02, ROADMAP Phase 9 criterion 2, REL-01 | issue | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/uat-02 |
| UAT-04 | UAT-04, ROADMAP Phase 9 criterion 2, REL-01 | blocked | 2026-10-12 | 7baec9878badc8fb49ea0d80243277d5ff3fb443 | .planning/phases/09-v1-0-1-release/09-evidence/uat-04 |
| PRE (9.1) | bench pin on the fix SHA (Phase 9.1 D-12), REL-01 | pass | 2026-10-14 | 681c58793b656b51869906b62f2564829de7a10d | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/00-preflight |
| CI (9.1) | ci.yml and validate.yml on the fix SHA (Phase 9 D-04 amendment), REL-01 | pass | 2026-10-14 | 681c58793b656b51869906b62f2564829de7a10d | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/release |
| HEAL | first start of the fix build on the failing state (Phase 9.1 D-09), REL-01 | pass | 2026-10-14 | 681c58793b656b51869906b62f2564829de7a10d | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/heal-start |
| UAT-02 (integration) | UAT-02 from integration tombstones (Phase 9.1 D-10 a), REL-01 | pass | 2026-10-14 | 681c58793b656b51869906b62f2564829de7a10d | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-02 |
| UAT-02 (null) | UAT-02 from null tombstones (Phase 9.1 D-10 b), REL-01 | pass | 2026-10-14 | 681c58793b656b51869906b62f2564829de7a10d | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-02-null |
| UAT-04 (9.1) | UAT-04 from null tombstones (Phase 9.1 D-12), REL-01 | pass | 2026-10-14 | 681c58793b656b51869906b62f2564829de7a10d | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-04 |
| REL | tag, release workflow, Latest, notes (D-14), REL-01 | pending | - | - | .planning/phases/09-v1-0-1-release/09-evidence/release |

The allowed result tokens are the same as in 08-UAT.md: pending, pass, issue, blocked. A recorded block carries `sha:` (40 hex),
`date:` (ISO date), `evidence:` (a folder under 09-evidence) and `note:` after `result:`. An issue also carries `reported:` and
`severity:`. A FAIL is recorded as `issue`. It stands as the result and is never repeated to get a pass.

The rows PRE, CI, UAT-02 and UAT-04 (blocks 1 to 4) are the 7baec98 history and stay as recorded (Phase 9.1 D-16). The six
rows PRE (9.1) to UAT-04 (9.1) (blocks 6 to 11) ran on the fix SHA, and their `evidence:` is a folder under
`.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence`. The REL row (block 5) stays
`pending` until plan 09-05 records it on the fix SHA.

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
expected: The owner pushes tag v1.0.1 on the bump SHA (re-pointed by Phase 9.1: on the fix SHA 681c58793b656b51869906b62f2564829de7a10d). release.yml is fully green (check-version, CI tiers, hassfest, HACS, release job). GitHub shows v1.0.1 as Latest, and the hand-written notes are applied (D-14).
result: pending
note: Not reached. The tag may follow only after UAT-02 and UAT-04 pass on the tagged SHA (REL-01). With block 3 `issue` and block 4 `blocked`, no tag is pushed on 7baec98, no release notes are written, and plans 09-04 and 09-05 do not run. Phase 9.1 (plan 09.1-06): the tagged SHA is now the fix SHA 681c58793b656b51869906b62f2564829de7a10d, on which blocks 6 to 11 pass. The re-pointed plan 09-05 records this block on that SHA.

### 6. PRE (9.1): bench pinned to the fix SHA
expected: ha-a and ha-b run exactly the custom_components tree of the fix SHA (byte-identical mount, pin check in lib.sh). The Phase 9.1 D-08 registry backups were taken with both instances stopped. check-preflight.sh (full) and check-stale-anchor.sh print PASS against the Phase 9.1 evidence root.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/00-preflight
note: Plan 09.1-05 Task 1. The red gate before the pin failed as expected (four evidence files missing, rc=1), and the green gate after it passed: check-preflight.sh (full, with the guard routing proof) and check-stale-anchor.sh both printed PASS (`gate-pin.txt`). HEAD was detached at FIX only for stage1 and stage2 and then restored to main (`pin-window.txt`). Backup `~/ha-test/_backup-pre-phase9.1-20261014T222425Z` has mode 700, and the pointer is `~/ha-test/.current-backup-phase9.1` (`backup-phase9.1.txt`). The bench scripts that ran are copied, scrubbed, to `00-preflight/bench-scripts/` with `cmp-proof.txt`. Every UAT precheck of blocks 9 and 10 names FIX as the pinned sha.

### 7. CI (9.1): ci.yml and validate.yml green on the fix SHA
expected: CI (Ruff, Unit tests, Broker tests, Multi-instance tests) and Validate (hassfest, HACS) completed with success on a run whose headSha is exactly the fix SHA (event push or workflow_dispatch per the owner-approved Phase 9 D-04 amendment).
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/release
note: Plan 09.1-04. The owner pushed exactly FIX to main with `git push origin 681c587:refs/heads/main`, a fast-forward from 7baec98 (`push-main.txt`). The owner then dispatched CI run 38646428109 and Validate run 38646494618. Both have event workflow_dispatch, headSha FIX and conclusion success, and all six jobs succeeded (`ci-fix-sha.json`, `ci-fix-sha-jobs.json`). Claude issued no push, dispatch or rerun.

### 8. HEAL: first start of the fix build on the failing state
expected: The first start of the fix build on the real leftover state of the 7baec98 UAT-02 run leaves zero platform-mqtt rows and zero legacy mqtt devices of the two regression ids on ha-a and ha-b, by product behavior, with no hand edit of a registry and no backup restore (Phase 9.1 D-09).
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/heal-start
note: Plan 09.1-05 Task 1, the preflight stage2 start. Pre-state (`pre-state.txt`, from the D-08 backup copies taken with both instances stopped), on each of ha-a and ha-b: 2 platform-mqtt rows, `switch.lampe_test_2` and `select.bar_select_2`, both `disabled_by` integration, and 2 legacy mqtt devices, "Lampe Test" (mqtt_actions_11111111-aaaa-4aaa-8aaa-000000000001) and "Bar Select" (mqtt_actions_b6bd2c0e-6d81-49ea-8025-4bd087bd718a). Post-state after a graceful stop, on the flushed registries (`post-state-a.json`, `post-state-b.json`): 0 mqtt rows and 0 legacy devices on each instance, and both records are now `integration` tombstones. Log lines of the catch: ha-a logged "Removed 1 duplicate entities that a replayed legacy discovery created" twice; ha-b logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids, then "Removed 1 duplicate entities that a replayed legacy discovery created" twice (`log-a.txt`, `log-b.txt`). Nothing was retained on `homeassistant/device/#` before or after the start (`retained-before.txt`, `retained-after.txt`), so this start exercised the "nothing retained" branch of the refined rule. ha-a and ha-b had not started on any tree after 7baec98 before this start (`00-preflight/bench-recovery.txt`).

### 9. UAT-02 (integration): late legacy Discovery replay, two starts, from integration tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-02
note: Plan 09.1-05 Task 2, run (a). `uat-02/` is the integration start (Phase 9.1 user decision 1): the start state is the one the heal start left, 0 live mqtt rows and the deleted-entity records of both regression ids with `disabled_by` integration on both instances. The read-only projection (`prepare.txt`) reads "would flip to disabled_by null: ha-a switch.lampe_test_2 (disabled_by integration);ha-a select.bar_select_2 (disabled_by integration);ha-b switch.lampe_test_2 (disabled_by integration);ha-b select.bar_select_2 (disabled_by integration);". The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha, and both baselines equal the 00-preflight registry baseline. All 16 assertions passed: E1 to E4 in round 1 and round 2 on ha-a and ha-b, with 34 mqtt_actions rows identical to the baseline (`result.txt`, `verdict.txt`). Per instance and round, the logs show the guard line "Disabled 1 duplicate entities that core MQTT created for native devices" twice and then the catch line "Removed 3 duplicate entities that a replayed legacy discovery created" twice (`log-a.txt`, `log-b.txt`). After each start, core MQTT had cleared the legacy topics (`retained-topics.txt`). No ABORT occurred, and no "Takeover of device ... postponed" or "keeps its MQTT device" line appeared.

### 10. UAT-02 (null): late legacy Discovery replay, two starts, from null tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-02-null
note: Plan 09.1-05 Task 2, run (b), with `PHASE8_EV_SUFFIX=-null`. reseed-tombstones.sh stopped both instances, backed up both registries to `~/ha-test/_backup-pre-phase9.1-20261014T222425Z/reseed-20261014T223659Z`, flipped the four records from integration to null, validated both files and started both instances again. `prepare.txt` ends with the exact state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0" (the wording "before UAT-04" is the script's fixed text). The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha. All 16 assertions passed in both rounds on both instances (`result.txt`, `verdict.txt`). The logs show the same guard and catch lines as block 9 ("Disabled 1 ..." twice, then "Removed 3 ..." twice, per instance and round). After each start, core MQTT had cleared the legacy topics. No ABORT occurred.

### 11. UAT-04 (9.1): Discovery export and core prefix, from null tombstones
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-04
note: Plan 09.1-05 Task 3 (Phase 9.1 D-12). `prepare.txt` records both UAT-02 verdicts as PASS, the read-only projection, and a new reseed with the backup `~/ha-test/_backup-pre-phase9.1-20261014T222425Z/reseed-20261014T224502Z`. It ends with the exact regression-state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0". check-uat04.sh ran with X1 to X10 unchanged: X1 to X4 for the three exported devices on the default prefix and on the core prefix, X5 and X6, X7 to X9 on ha-a and ha-b (one disabled mqtt row per exported device, the native row present and enabled, no enabled mqtt row) and X10 (nothing retained after the export was switched off) all printed PASS (`result.txt`, `verdict.txt`). The containers were not restarted during the run.

Not run in Phase 9 (D-05). They are not re-verified here, and nothing in this ledger claims they are:
- UAT-01: last recorded pass 2026-10-06 on b7f52b34, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-01`
- UAT-03: last recorded pass 2026-10-11 on b8232252, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-03-rerun2`
- P1-5: last recorded pass 2026-10-11 on b8232252, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/p1-5-rerun2`

## Summary

total: 11
passed: 8
issues: 1
pending: 1
skipped: 0
blocked: 1

The issue (block 3) and the blocked block (block 4) are the 7baec98 history. On the fix SHA, blocks 6 to 11 pass and block 5 is
pending.

## Requirement verdicts

A requirement is complete only when all of its blocks are `pass`. The verdict stays `pending` until block 5 is recorded (plan
09-05). With block 3 `issue`, REL-01 cannot pass on 7baec98. On the fix SHA, blocks 3 and 4 are superseded by blocks 9 to 11.

| Requirement | Block | Verdict | Evidence |
|-------------|-------|---------|----------|
| REL-01 | 1 to 11 (blocks 3 and 4 superseded on the fix SHA by blocks 9 to 11) | pending | 7baec98 history: 09-evidence/00-preflight (pass), 09-evidence/release (CI pass), 09-evidence/uat-02 (issue), 09-evidence/uat-04 (blocked); fix SHA 681c58793b656b51869906b62f2564829de7a10d: 09.1-evidence/00-preflight (pass), 09.1-evidence/release (CI pass), 09.1-evidence/heal-start (pass), 09.1-evidence/uat-02 (pass), 09.1-evidence/uat-02-null (pass), 09.1-evidence/uat-04 (pass); REL not reached |

## Gap closure

ACCEPTED-GAP-V101 closes for the v1.0.1 release only when blocks 3, 4 and 5 pass. Plan 09-05 records that. On 7baec98 the gap is
still open: block 3 is `issue` and block 4 is `blocked`. Phase 9.1 needs a fix SHA, a new bench run of UAT-02 and UAT-04 on that
SHA, and then the tag on that SHA.

Phase 9.1 (plan 09.1-06): on the fix SHA 681c58793b656b51869906b62f2564829de7a10d, blocks 9, 10 and 11 replace blocks 3 and 4 for
this rule. ACCEPTED-GAP-V101 closes for v1.0.1 only when blocks 9, 10, 11 and 5 pass. Blocks 9, 10 and 11 pass; block 5 is
pending. Plan 09-05 records the closure after the tag and release on the fix SHA.

## Gaps

- truth: "After a retained legacy Discovery replay at start, two startup rounds leave no mqtt row, no `_2` id and no legacy mqtt device on ha-a and ha-b (UAT-02 E1 to E3, MIG-05)"
  status: resolved
  resolved_by: Phase 9.1, fix SHA 681c58793b656b51869906b62f2564829de7a10d, blocks 8 to 11
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

Phase 9.1 (fix SHA 681c58793b656b51869906b62f2564829de7a10d), observations only:

- **Corrected mechanism of the 7baec98 failure (Phase 9.1 research).** The first bullet above is superseded. The replayed rows
  come back **enabled** from both tombstone states: core MQTT re-enables a restored row from an `integration` tombstone because
  the legacy payload is enabled by default, and creates it enabled from a `null` tombstone. The duplicate guard then disabled
  them, and the start-up catch on 7baec98 skipped disabled rows (CR-01), so they stayed. The Phase 8 reference run passed only
  because it ran before the CR-01 change. The fix lets the catch remove an integration-disabled duplicate when the core-prefix
  topic holds the legacy payload or nothing, and keep it for an export or unknown content.
- **Heal start log (block 8).** ha-a logged "Removed 1 duplicate entities that a replayed legacy discovery created" twice. ha-b
  logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids, then the same
  "Removed 1 ..." line twice, and its rows and legacy devices were gone afterwards. Nothing was retained on the core prefix.
- **"postponed" and "keeps its MQTT device".** No "Takeover of device ... postponed" line appeared in the heal start or in either
  UAT-02 run. "keeps its MQTT device" appeared only at the heal start on ha-b (twice), never in a UAT-02 run, so no
  `observations.txt` was written (`09.1-evidence/README.txt`).
- **Guard log in UAT-04 (block 11).** "Disabled 1 duplicate entities that core MQTT created for native devices" appeared twice on
  ha-a and twice on ha-b during the run (`uat-04/guard-log-a.txt`, `guard-log-b.txt`).
- **Post-UAT-04 restart.** After "export off", each instance still held 3 disabled mqtt rows (the export rows). After one graceful
  restart (2026-10-14T22:50:05Z, plus 90 s) both held 0 live mqtt rows, the guard logged nothing on that start, and
  `check-uat02.sh clean` printed PASS (`uat-04/post-restart.txt`, `post-run-*.json`, `post-restart-*.json`). The export rows were
  removed by that restart, as observed.
- **Accepted residual risks (Phase 9.1 user decisions 2 and 5), not exercised as results.** (1) If a broker restart without
  persistence and a Home Assistant start fall into the same few seconds, another instance's Discovery export on the core prefix
  can be cleared until that instance publishes it again. (2) When the owner of a device clears a stale legacy Discovery message,
  the instances that follow the device delete their remaining MQTT entities of it, customized ones included.

## Bench state left behind

After plan 09.1-05 (fix SHA, current):

- mosq, ha-a and ha-b are Up on the fix tree 681c58793b656b51869906b62f2564829de7a10d (`check-preflight.sh --quick` PASS). ha-c is
  stopped.
- The export is off. Nothing is retained under `mqtt_actions_export/#` or `homeassistant/device/#` (`check-uat04.sh clean` PASS).
- Live mqtt rows after the last restart: 0 on ha-a and 0 on ha-b. The legacy mqtt devices of both ids are gone. The switch and
  select records of both regression ids are `integration` tombstones on both instances, so a later UAT-04 re-run needs the
  reseed again.
- Backups: the Phase 9.1 D-08 backup `~/ha-test/_backup-pre-phase9.1-20261014T222425Z` (mode 700, pointer
  `~/ha-test/.current-backup-phase9.1`) with the reseed copies `reseed-20261014T223659Z` and `reseed-20261014T224502Z`, and the
  stage1 backup `~/ha-test/_backup-pre-phase8-20261014T222456Z`. The Phase 9 backups listed below are kept.
- No stray `mosquitto_sub` is running. The bench and its tokens are kept until Phase 12 (owner follow-up from Phase 8).

After plan 09-03 (7baec98, history):

- mosq, ha-a and ha-b are Up on the bump tree (`check-preflight.sh --quick` PASS, 2026-10-12T19:58Z). ha-c is stopped (D-07).
- The export is off. Nothing is retained under `mqtt_actions_export/#` or `homeassistant/device/#` (`check-uat04.sh clean` PASS).
- Live mqtt rows: 2 on ha-a and 2 on ha-b (`switch.lampe_test_2`, `select.bar_select_2`, `disabled_by` integration). The legacy
  mqtt devices of both ids remain. Nothing was removed by hand. The next bench run must deal with this state through product
  behavior or a documented, backed-up restoration.
- Backups: the D-08 backup `~/ha-test/_backup-pre-phase9-20261012T014617Z` (pointer `~/ha-test/.current-backup-phase9`), and the
  reseed copy `~/ha-test/_backup-pre-phase9-20261012T014617Z/reseed-20261012T195511Z` (mode 700). The reseed copy holds the
  registries after UAT-02, before any write.
- No stray `mosquitto_sub` is running. The bench and its tokens are kept until Phase 12 (owner follow-up from Phase 8).
