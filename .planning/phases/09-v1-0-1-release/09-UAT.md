---
status: testing
phase: 09-v1-0-1-release
source:
  - .planning/phases/09-v1-0-1-release/09-CONTEXT.md
  - .planning/ROADMAP.md (Phase 9)
  - .planning/milestones/v1.0.1-REQUIREMENTS.md (wording of UAT-02 and UAT-04)
  - .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-CONTEXT.md
started: 2026-10-12T01:45:21Z
updated: 2026-10-15T22:30:00Z
---

## Current Test

number: 5
name: REL on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (tag, release workflow, Latest, release notes)
expected: |
  On the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74, CI and Validate are green (block 19), the heal start (block 20),
  UAT-02 from integration tombstones (block 21), UAT-02 from null tombstones (block 22) and UAT-04 (block 23) pass, and the
  CR-01 release gate holds (block 24). The owner decides the one-way tag v1.0.1 on that SHA in plan 09-04, and plan 09-05
  checks the release and records block 5.
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

This subsection describes the 681c587 run of blocks 6 to 11. It is superseded: the review fixes (CR-01, WR-01, WR-02) and the
troubleshooting correction moved FIX after this run (see the next subsection). The list above is history as well: it describes
the 7baec98 bench of blocks 1 to 5. The pinned identity of this run is in
`.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/00-preflight/build.txt`.

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

### Phase 9.1 build after the review fixes (fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6)

This subsection describes the dc6513c run of blocks 12 to 17. It is superseded: Phase 9.2 fixed the cross-instance CR-01
defect that the 09.1 bench observation found, which moved FIX after this run (see the next subsection). The pinned identity
is in
`.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/00-preflight/build.txt`.

- sha: dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (FIX, the last commit on main that changes a path outside `.planning/`; it
  equals `fix_sha:` of `fix2/release/push-readiness.txt`; manifest `version` 1.0.1, unchanged since 7baec98)
- commit time: 2026-10-15T10:36:29+02:00
- image: ghcr.io/home-assistant/home-assistant:2026.9 (HA 2026.9.4 on ha-a and ha-b)
- ha-a: instance id 3851f34f-fa67-4f3c-bba0-122465013c3d; ha-b: instance id b4cf285b-428f-426b-9500-8e269634356e; ha-c stopped
- Pin: HEAD was detached at FIX only for preflight stage1 and stage2 (2026-10-15T09:42:28Z to 09:43:31Z) and then restored to
  main with an empty index diff (`fix2/00-preflight/pin-window.txt`), so `build.txt` names FIX itself with `branch: (detached)`.
  The mount is byte-identical to the custom_components tree of FIX (blob by blob, no extra files).
- Pre-state restore before the pin (owner decision 2026-10-15, not a result): with ha-a and ha-b stopped, the four registry
  files were copied back from `~/ha-test/_backup-pre-phase9.1-20261014T222425Z`, the D-08 backup that plan 09.1-05 took before
  the 681c587 heal start. The 681c587 end state was backed up first (`fix2/heal-start/restore.txt`,
  `fix2/00-preflight/backup-phase9.1-fix2.txt`).

### Phase 9.2 build (fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74)

Blocks 18 to 24 ran on this build. The pinned identity is in
`.planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/00-preflight/build.txt`.

- sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (FIX, the last commit on main that changes a path outside `.planning/`; it
  equals `fix_sha:` of `09.2-evidence/release/push-readiness.txt`; manifest `version` 1.0.1, unchanged since 7baec98)
- commit time: 2026-10-15T21:58:11+02:00
- image: ghcr.io/home-assistant/home-assistant:2026.9 (HA 2026.9.4 on ha-a and ha-b)
- ha-a: instance id 3851f34f-fa67-4f3c-bba0-122465013c3d; ha-b: instance id b4cf285b-428f-426b-9500-8e269634356e; ha-c stopped
- Pin: HEAD was detached at FIX only for preflight stage1 and stage2 (2026-10-15T20:59:35Z to 21:00:38Z) and then restored to
  main with an empty index diff (`09.2-evidence/00-preflight/pin-window.txt`), so `build.txt` names FIX itself with
  `branch: (detached)`. The mount is byte-identical to the custom_components tree of FIX (blob by blob, no extra files).
- Fast-forward of main (`09.2-evidence/release/fast-forward.txt`): local main moved from 5f9799a to the phase branch head
  ae738fe with `git fetch . <phase branch>:main` (fast-forward only, no merge, no rebase, no force). FIX is the last
  review-fix commit on that branch (IN-01) and supersedes the 09.2-03 FIX candidate a4d0895.
- Owner decisions: review `reviewed-clean` (2026-10-15T20:08:19Z) after one fix-first round (WR-01, WR-02, WR-03, IN-01,
  IN-02, all fixed test first; WR-03 keeps the conservative shared retry budget), `release/review-decision.txt`; push `push`
  with the acknowledged wire field `kept_legacy` (2026-10-15T20:36:07Z), `release/push-decision.txt`; bench `confirm` with
  `heal_restore: yes` (2026-10-15T20:55:41Z), `00-preflight/bench-decision.txt`.
- Pre-state restore before the pin (owner decision `confirm`, not a result): with ha-a and ha-b stopped, the dc6513c end state
  was backed up to `~/ha-test/_backup-pre-phase9.2-20261015T205830Z` (mode 700, `00-preflight/backup-phase9.2.txt`), then the
  four registry files were copied back with `cp -p` from `~/ha-test/_backup-pre-phase9.1-20261014T222425Z`, the D-08 backup
  that plan 09.1-05 took before the 681c587 heal start and the same source plan 09.1-09 restored from
  (`09.2-evidence/heal-start/restore.txt`).

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
| PRE (9.1 fix2) | bench pin on the new fix SHA (Phase 9.1 D-12), REL-01 | pass | 2026-10-15 | dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/00-preflight |
| CI (9.1 fix2) | ci.yml and validate.yml on the new fix SHA (Phase 9 D-04 amendment), REL-01 | pass | 2026-10-15 | dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/release |
| HEAL (fix2) | first start of the fix build on the restored failing state (Phase 9.1 D-09, owner decision 2026-10-15), REL-01 | pass | 2026-10-15 | dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/heal-start |
| UAT-02 (integration, fix2) | UAT-02 from integration tombstones (Phase 9.1 D-10 a), REL-01 | pass | 2026-10-15 | dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/uat-02 |
| UAT-02 (null, fix2) | UAT-02 from null tombstones (Phase 9.1 D-10 b), REL-01 | pass | 2026-10-15 | dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/uat-02-null |
| UAT-04 (9.1 fix2) | UAT-04 from null tombstones (Phase 9.1 D-12), REL-01 | pass | 2026-10-15 | dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 | .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/uat-04 |
| PRE (9.2) | bench pin on the fix SHA (Phase 9.2 D-14), REL-01 | pass | 2026-10-15 | 3dc9093f3cc49900bf76576cb4432d84aa94cd74 | .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/00-preflight |
| CI (9.2) | ci.yml and validate.yml on the fix SHA (Phase 9 D-04 amendment), REL-01 | pass | 2026-10-15 | 3dc9093f3cc49900bf76576cb4432d84aa94cd74 | .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/release |
| HEAL (9.2) | first start of the fix build on the restored failing state (Phase 9.1 D-09, Phase 9.2 D-14, bench decision confirm), REL-01 | pass | 2026-10-15 | 3dc9093f3cc49900bf76576cb4432d84aa94cd74 | .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/heal-start |
| UAT-02 (integration, 9.2) | UAT-02 from integration tombstones (Phase 9.1 D-10 a), REL-01 | pass | 2026-10-15 | 3dc9093f3cc49900bf76576cb4432d84aa94cd74 | .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-02 |
| UAT-02 (null, 9.2) | UAT-02 from null tombstones (Phase 9.1 D-10 b), REL-01 | pass | 2026-10-15 | 3dc9093f3cc49900bf76576cb4432d84aa94cd74 | .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-02-null |
| UAT-04 (9.2) | UAT-04 from null tombstones (Phase 9.1 D-12), REL-01 | pass | 2026-10-15 | 3dc9093f3cc49900bf76576cb4432d84aa94cd74 | .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-04 |
| CR-01 gate (9.2) | cross-instance keep, release gate (Phase 9.2 D-15 and D-16), REL-01 | pass | 2026-10-15 | 3dc9093f3cc49900bf76576cb4432d84aa94cd74 | .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/cr01-gate |
| REL | tag, release workflow, Latest, notes (D-14), REL-01 | pending | - | - | .planning/phases/09-v1-0-1-release/09-evidence/release |

The allowed result tokens are the same as in 08-UAT.md: pending, pass, issue, blocked. A recorded block carries `sha:` (40 hex),
`date:` (ISO date), `evidence:` (a folder under 09-evidence) and `note:` after `result:`. An issue also carries `reported:` and
`severity:`. A FAIL is recorded as `issue`. It stands as the result and is never repeated to get a pass.

The rows PRE, CI, UAT-02 and UAT-04 (blocks 1 to 4) are the 7baec98 history and stay as recorded (Phase 9.1 D-16). The six
rows PRE (9.1) to UAT-04 (9.1) (blocks 6 to 11) ran on the fix SHA, and their `evidence:` is a folder under
`.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence`. The REL row (block 5) stays
`pending` until plan 09-05 records it on the fix SHA.

The rows PRE (9.1) to UAT-04 (9.1) (blocks 6 to 11) ran on 681c58793b656b51869906b62f2564829de7a10d and are superseded by the
six fix2 rows PRE (9.1 fix2) to UAT-04 (9.1 fix2) (blocks 12 to 17). Those ran on the fix SHA
dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 after the review fixes, and their evidence lies under
`.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2`. The CR-01 bench
observation of plan 09.1-11 is an observation, not a row (see Observations).

The fix2 rows PRE (9.1 fix2) to UAT-04 (9.1 fix2) (blocks 12 to 17) ran on dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 and are
superseded by the six rows PRE (9.2) to UAT-04 (9.2) (blocks 18 to 23). Those ran on the fix SHA
3dc9093f3cc49900bf76576cb4432d84aa94cd74 after Phase 9.2 fixed the cross-instance CR-01 defect, and their evidence lies under
`.planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence`. Block 24 (CR-01 gate (9.2))
is the CR-01 release gate on the same SHA, a result like any other block (Phase 9.2 D-15).

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
expected: The owner pushes tag v1.0.1 on the bump SHA (re-pointed by Phase 9.2: on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74; 681c58793b656b51869906b62f2564829de7a10d and dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 are superseded and never tagged). release.yml is fully green (check-version, CI tiers, hassfest, HACS, release job). GitHub shows v1.0.1 as Latest, and the hand-written notes are applied (D-14).
result: pending
note: Not reached. The tag may follow only after UAT-02 and UAT-04 pass on the tagged SHA (REL-01). With block 3 `issue` and block 4 `blocked`, no tag is pushed on 7baec98, no release notes are written, and plans 09-04 and 09-05 do not run. Phase 9.2 (plan 09.2-09): the tag candidate is now the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74, on which blocks 18 to 23 pass and the CR-01 release gate (block 24) holds in all three variants. 681c58793b656b51869906b62f2564829de7a10d (blocks 6 to 11) is superseded and never tagged, because it carries the CR-01 defect that the 9.1 review fixes addressed. dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (blocks 12 to 17) is superseded and never tagged, because it carries the cross-instance CR-01 defect that the 09.1 bench observation found and Phase 9.2 fixed. Plan 09.2-09 writes the final CR-01 behavior into the release notes and re-points plans 09-04 (tag, owner decision) and 09-05 (release) to this SHA; this block runs next, in those plans.

### 6. PRE (9.1): bench pinned to the fix SHA
expected: ha-a and ha-b run exactly the custom_components tree of the fix SHA (byte-identical mount, pin check in lib.sh). The Phase 9.1 D-08 registry backups were taken with both instances stopped. check-preflight.sh (full) and check-stale-anchor.sh print PASS against the Phase 9.1 evidence root.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/00-preflight
note: Plan 09.1-05 Task 1. The red gate before the pin failed as expected (four evidence files missing, rc=1), and the green gate after it passed: check-preflight.sh (full, with the guard routing proof) and check-stale-anchor.sh both printed PASS (`gate-pin.txt`). HEAD was detached at FIX only for stage1 and stage2 and then restored to main (`pin-window.txt`). Backup `~/ha-test/_backup-pre-phase9.1-20261014T222425Z` has mode 700, and the pointer is `~/ha-test/.current-backup-phase9.1` (`backup-phase9.1.txt`). The bench scripts that ran are copied, scrubbed, to `00-preflight/bench-scripts/` with `cmp-proof.txt`. Every UAT precheck of blocks 9 and 10 names FIX as the pinned sha.
superseded_by: block 12 on the fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (the review fixes for CR-01, WR-01 and WR-02 and the troubleshooting correction moved FIX after this run)

### 7. CI (9.1): ci.yml and validate.yml green on the fix SHA
expected: CI (Ruff, Unit tests, Broker tests, Multi-instance tests) and Validate (hassfest, HACS) completed with success on a run whose headSha is exactly the fix SHA (event push or workflow_dispatch per the owner-approved Phase 9 D-04 amendment).
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/release
note: Plan 09.1-04. The owner pushed exactly FIX to main with `git push origin 681c587:refs/heads/main`, a fast-forward from 7baec98 (`push-main.txt`). The owner then dispatched CI run 38646428109 and Validate run 38646494618. Both have event workflow_dispatch, headSha FIX and conclusion success, and all six jobs succeeded (`ci-fix-sha.json`, `ci-fix-sha-jobs.json`). Claude issued no push, dispatch or rerun.
superseded_by: block 13 on the fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (the review fixes for CR-01, WR-01 and WR-02 and the troubleshooting correction moved FIX after this run)

### 8. HEAL: first start of the fix build on the failing state
expected: The first start of the fix build on the real leftover state of the 7baec98 UAT-02 run leaves zero platform-mqtt rows and zero legacy mqtt devices of the two regression ids on ha-a and ha-b, by product behavior, with no hand edit of a registry and no backup restore (Phase 9.1 D-09).
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/heal-start
note: Plan 09.1-05 Task 1, the preflight stage2 start. Pre-state (`pre-state.txt`, from the D-08 backup copies taken with both instances stopped), on each of ha-a and ha-b: 2 platform-mqtt rows, `switch.lampe_test_2` and `select.bar_select_2`, both `disabled_by` integration, and 2 legacy mqtt devices, "Lampe Test" (mqtt_actions_11111111-aaaa-4aaa-8aaa-000000000001) and "Bar Select" (mqtt_actions_b6bd2c0e-6d81-49ea-8025-4bd087bd718a). Post-state after a graceful stop, on the flushed registries (`post-state-a.json`, `post-state-b.json`): 0 mqtt rows and 0 legacy devices on each instance, and both records are now `integration` tombstones. Log lines of the catch: ha-a logged "Removed 1 duplicate entities that a replayed legacy discovery created" twice; ha-b logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids, then "Removed 1 duplicate entities that a replayed legacy discovery created" twice (`log-a.txt`, `log-b.txt`). Nothing was retained on `homeassistant/device/#` before or after the start (`retained-before.txt`, `retained-after.txt`), so this start exercised the "nothing retained" branch of the refined rule. ha-a and ha-b had not started on any tree after 7baec98 before this start (`00-preflight/bench-recovery.txt`).
superseded_by: block 14 on the fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (the review fixes for CR-01, WR-01 and WR-02 and the troubleshooting correction moved FIX after this run)

### 9. UAT-02 (integration): late legacy Discovery replay, two starts, from integration tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-02
note: Plan 09.1-05 Task 2, run (a). `uat-02/` is the integration start (Phase 9.1 user decision 1): the start state is the one the heal start left, 0 live mqtt rows and the deleted-entity records of both regression ids with `disabled_by` integration on both instances. The read-only projection (`prepare.txt`) reads "would flip to disabled_by null: ha-a switch.lampe_test_2 (disabled_by integration);ha-a select.bar_select_2 (disabled_by integration);ha-b switch.lampe_test_2 (disabled_by integration);ha-b select.bar_select_2 (disabled_by integration);". The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha, and both baselines equal the 00-preflight registry baseline. All 16 assertions passed: E1 to E4 in round 1 and round 2 on ha-a and ha-b, with 34 mqtt_actions rows identical to the baseline (`result.txt`, `verdict.txt`). Per instance and round, the logs show the guard line "Disabled 1 duplicate entities that core MQTT created for native devices" twice and then the catch line "Removed 3 duplicate entities that a replayed legacy discovery created" twice (`log-a.txt`, `log-b.txt`). After each start, core MQTT had cleared the legacy topics (`retained-topics.txt`). No ABORT occurred, and no "Takeover of device ... postponed" or "keeps its MQTT device" line appeared.
superseded_by: block 15 on the fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (the review fixes for CR-01, WR-01 and WR-02 and the troubleshooting correction moved FIX after this run)

### 10. UAT-02 (null): late legacy Discovery replay, two starts, from null tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-02-null
note: Plan 09.1-05 Task 2, run (b), with `PHASE8_EV_SUFFIX=-null`. reseed-tombstones.sh stopped both instances, backed up both registries to `~/ha-test/_backup-pre-phase9.1-20261014T222425Z/reseed-20261014T223659Z`, flipped the four records from integration to null, validated both files and started both instances again. `prepare.txt` ends with the exact state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0" (the wording "before UAT-04" is the script's fixed text). The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha. All 16 assertions passed in both rounds on both instances (`result.txt`, `verdict.txt`). The logs show the same guard and catch lines as block 9 ("Disabled 1 ..." twice, then "Removed 3 ..." twice, per instance and round). After each start, core MQTT had cleared the legacy topics. No ABORT occurred.
superseded_by: block 16 on the fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (the review fixes for CR-01, WR-01 and WR-02 and the troubleshooting correction moved FIX after this run)

### 11. UAT-04 (9.1): Discovery export and core prefix, from null tombstones
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: pass
sha: 681c58793b656b51869906b62f2564829de7a10d
date: 2026-10-14
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/uat-04
note: Plan 09.1-05 Task 3 (Phase 9.1 D-12). `prepare.txt` records both UAT-02 verdicts as PASS, the read-only projection, and a new reseed with the backup `~/ha-test/_backup-pre-phase9.1-20261014T222425Z/reseed-20261014T224502Z`. It ends with the exact regression-state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0". check-uat04.sh ran with X1 to X10 unchanged: X1 to X4 for the three exported devices on the default prefix and on the core prefix, X5 and X6, X7 to X9 on ha-a and ha-b (one disabled mqtt row per exported device, the native row present and enabled, no enabled mqtt row) and X10 (nothing retained after the export was switched off) all printed PASS (`result.txt`, `verdict.txt`). The containers were not restarted during the run.
superseded_by: block 17 on the fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (the review fixes for CR-01, WR-01 and WR-02 and the troubleshooting correction moved FIX after this run)

### 12. PRE (9.1 fix2): bench pinned to the new fix SHA
expected: ha-a and ha-b run exactly the custom_components tree of the fix SHA (byte-identical mount, pin check in lib.sh). The Phase 9.1 D-08 registry backups were taken with both instances stopped. check-preflight.sh (full) and check-stale-anchor.sh print PASS against the Phase 9.1 evidence root.
result: pass
sha: dc6513c0b4ac54d68fbf5207161508c18cc2a5b6
date: 2026-10-15
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/00-preflight
note: Plan 09.1-09 Task 1, with the evidence root `09.1-evidence/fix2` (`~/ha-test/phase9.1-fix2.env`). Before the pin, both instances were stopped and their 681c587 end state was backed up to `~/ha-test/_backup-pre-phase9.1-fix2-20261015T094121Z` (mode 700, pointer `~/ha-test/.current-backup-phase9.1-fix2`, `backup-phase9.1-fix2.txt`); then the pre-state was restored (block 14). The red gate before the pin failed as expected (four evidence files missing, rc=1), and the green gate after it passed: check-preflight.sh (full, with the guard routing proof) and check-stale-anchor.sh both printed PASS (`gate-pin.txt`, 2026-10-15T09:45:13Z). HEAD was detached at FIX only for stage1 and stage2 (09:42:28Z to 09:43:31Z) and then restored to main with an empty index diff (`pin-window.txt`). The bench scripts that ran are copied, scrubbed, to `00-preflight/bench-scripts/` with `cmp-proof.txt`. `handoff.txt` records the pinned session for plan 09.1-10. Plan 09.1-10 re-asserted the pin before UAT-02 and never redid it (`uat-02/pin-reassert.txt`: build, handoff, fix and planning-excluded sha all equal FIX, HEAD main, check-preflight.sh --quick and check-stale-anchor.sh PASS, StartedAt of ha-a and ha-b unchanged since the handoff, ha-c not running). Every UAT precheck of blocks 15 and 16 names FIX as the pinned sha.
superseded_by: block 18 on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (Phase 9.2 fixed the cross-instance CR-01 defect of the 09.1 bench observation, which moved FIX after this run)

### 13. CI (9.1 fix2): ci.yml and validate.yml green on the new fix SHA
expected: CI (Ruff, Unit tests, Broker tests, Multi-instance tests) and Validate (hassfest, HACS) completed with success on a run whose headSha is exactly the fix SHA (event push or workflow_dispatch per the owner-approved Phase 9 D-04 amendment).
result: pass
sha: dc6513c0b4ac54d68fbf5207161508c18cc2a5b6
date: 2026-10-15
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/release
note: Plan 09.1-08. The owner decided to push (`push-decision.txt`, choice push) and pushed exactly FIX to main with `git push origin dc6513c0b4ac54d68fbf5207161508c18cc2a5b6:refs/heads/main`, a fast-forward from 681c587 (`push-main.txt`). The owner then dispatched CI run 38713873705 and Validate run 38713877413. Both have event workflow_dispatch, headSha FIX and conclusion success, and all six jobs succeeded: Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests, hassfest and HACS (`ci-fix-sha.json`, `ci-fix-sha-jobs.json`). Claude issued no push, dispatch or rerun. The 681c587 runs of block 7 do not count for this SHA.
superseded_by: block 19 on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (Phase 9.2 fixed the cross-instance CR-01 defect of the 09.1 bench observation, which moved FIX after this run)

### 14. HEAL (fix2): first start of the fix build on the restored failing state
expected: The first start of the fix build on the failing state, re-created from the pre-phase-9.1 registry backup with both instances stopped (owner decision 2026-10-15), leaves zero platform-mqtt rows and zero legacy mqtt devices of the two regression ids on ha-a and ha-b, by product behavior, with no hand edit of a registry (Phase 9.1 D-09).
result: pass
sha: dc6513c0b4ac54d68fbf5207161508c18cc2a5b6
date: 2026-10-15
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/heal-start
note: Plan 09.1-09 Task 1, the preflight stage2 start. Restore (owner decision 2026-10-15, `restore.txt`): with ha-a and ha-b stopped, the four registry files were copied with `cp -p` from `~/ha-test/_backup-pre-phase9.1-20261014T222425Z`, the D-08 backup of plan 09.1-05. Their sha256 values equal those recorded in `09.1-evidence/00-preflight/backup-phase9.1.txt`, they are cmp-identical to the stage1 backup `~/ha-test/_backup-pre-phase8-20261014T222456Z`, and the live config entries and `mqtt_actions.state` equal that backup, so only the registries needed restoring. No registry file was edited by hand, and no tree started on the restored registries before stage2. Pre-state (`pre-state.txt`), on each of ha-a and ha-b: 2 platform-mqtt rows, `switch.lampe_test_2` and `select.bar_select_2`, both `disabled_by` integration, 2 legacy mqtt devices, "Lampe Test" (mqtt_actions_11111111-aaaa-4aaa-8aaa-000000000001) and "Bar Select" (mqtt_actions_b6bd2c0e-6d81-49ea-8025-4bd087bd718a), and 0 deleted records of the regression ids. Post-state after a graceful stop at 2026-10-15T09:44:22Z, on the flushed registries (`post-state-a.json`, `post-state-b.json`): 0 mqtt rows and 0 legacy devices on each instance, and both records are now `integration` tombstones. Log lines: ha-a logged "Removed 1 duplicate entities that a replayed legacy discovery created" twice; ha-b logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids, then "Removed 1 duplicate entities that a replayed legacy discovery created" twice (`log-a.txt`, `log-b.txt`). Nothing was retained on `homeassistant/device/#` before or after the start (`retained-before.txt`, `retained-after.txt`).
superseded_by: block 20 on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (Phase 9.2 fixed the cross-instance CR-01 defect of the 09.1 bench observation, which moved FIX after this run)

### 15. UAT-02 (integration, fix2): late legacy Discovery replay, two starts, from integration tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: dc6513c0b4ac54d68fbf5207161508c18cc2a5b6
date: 2026-10-15
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/uat-02
note: Plan 09.1-10 Task 1, run (a), after the pin re-assert of block 12. `uat-02/` is the integration start (Phase 9.1 user decision 1): the start state is the one the heal start left, 0 live mqtt rows and the deleted-entity records of both regression ids with `disabled_by` integration on both instances. The read-only projection (`prepare.txt`) reads "would flip to disabled_by null: ha-a switch.lampe_test_2 (disabled_by integration);ha-a select.bar_select_2 (disabled_by integration);ha-b switch.lampe_test_2 (disabled_by integration);ha-b select.bar_select_2 (disabled_by integration);". The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha, and both baselines equal the 00-preflight registry baseline. All 16 assertions passed: E1 to E4 in round 1 and round 2 on ha-a and ha-b, with 34 mqtt_actions rows identical to the baseline (`result.txt`, `verdict.txt`). Per instance and round, the logs show the guard line "Disabled 1 duplicate entities that core MQTT created for native devices" twice and then the catch line "Removed 3 duplicate entities that a replayed legacy discovery created" twice (`log-a.txt`, `log-b.txt`). After each start, core MQTT had cleared the legacy topics (`retained-topics.txt`). No ABORT occurred, and no "postponed", "keeps its MQTT device" or "the next start checks again" line appeared (`observations.txt`).
superseded_by: block 21 on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (Phase 9.2 fixed the cross-instance CR-01 defect of the 09.1 bench observation, which moved FIX after this run)

### 16. UAT-02 (null, fix2): late legacy Discovery replay, two starts, from null tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: dc6513c0b4ac54d68fbf5207161508c18cc2a5b6
date: 2026-10-15
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/uat-02-null
note: Plan 09.1-10 Task 1, run (b), with `PHASE8_EV_SUFFIX=-null`. reseed-tombstones.sh stopped both instances, backed up both registries to `~/ha-test/_backup-pre-phase9.1-fix2-20261015T094121Z/reseed-20261015T095919Z`, flipped the four records from integration to null, validated both files and started both instances again; check-preflight.sh --quick and check-uat02.sh clean printed PASS. `prepare.txt` ends with the exact state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0" (the wording "before UAT-04" is the script's fixed text). The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha. All 16 assertions passed in both rounds on both instances (`result.txt`, `verdict.txt`). The logs show the same guard and catch lines as block 15 ("Disabled 1 ..." twice, then "Removed 3 ..." twice, per instance and round). After each start, core MQTT had cleared the legacy topics. No ABORT occurred, and no "postponed", "keeps its MQTT device" or "the next start checks again" line appeared (`observations.txt`).
superseded_by: block 22 on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (Phase 9.2 fixed the cross-instance CR-01 defect of the 09.1 bench observation, which moved FIX after this run)

### 17. UAT-04 (9.1 fix2): Discovery export and core prefix, from null tombstones
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: pass
sha: dc6513c0b4ac54d68fbf5207161508c18cc2a5b6
date: 2026-10-15
evidence: .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/uat-04
note: Plan 09.1-10 Task 2 (Phase 9.1 D-12). `prepare.txt` records both UAT-02 verdicts of blocks 15 and 16 as PASS, the read-only projection, and a new reseed with the backup `~/ha-test/_backup-pre-phase9.1-fix2-20261015T094121Z/reseed-20261015T100723Z`. It ends with the exact regression-state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0". check-marker.sh approved and check-preflight.sh --quick printed PASS. check-uat04.sh ran with X1 to X10 unchanged: X1 to X4 for the three exported devices on the default prefix and on the core prefix, X5 and X6, X7 to X9 on ha-a and ha-b (one disabled mqtt row per exported device, the native row present and enabled, no enabled mqtt row) and X10 (nothing retained after the export was switched off) all printed PASS (`result.txt`, `verdict.txt`). The containers were not restarted during the run (StartedAt unchanged, `result.txt`).
superseded_by: block 23 on the fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (Phase 9.2 fixed the cross-instance CR-01 defect of the 09.1 bench observation, which moved FIX after this run)

### 18. PRE (9.2): bench pinned to the fix SHA
expected: ha-a and ha-b run exactly the custom_components tree of the fix SHA (byte-identical mount, pin check in lib.sh). The Phase 9.2 registry backups were taken with both instances stopped. check-preflight.sh (full) and check-stale-anchor.sh print PASS against the Phase 9.2 evidence root.
result: pass
sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74
date: 2026-10-15
evidence: .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/00-preflight
note: Plan 09.2-06 Tasks 2 and 3, with the evidence root `09.2-evidence` (`~/ha-test/phase9.2.env`). Before the pin, both instances were stopped (`podman stop -t 60`) and their dc6513c end state was backed up to `~/ha-test/_backup-pre-phase9.2-20261015T205830Z` (mode 700, pointer `~/ha-test/.current-backup-phase9.2`, `backup-phase9.2.txt`); then the pre-state was restored (block 20). The red gate before the pin failed as expected (four evidence files missing, rc=1), and the green gate after it passed: check-preflight.sh (full, with the guard routing proof) and check-stale-anchor.sh both printed PASS (`gate-pin.txt`, 2026-10-15T21:02:10Z). HEAD was detached at FIX only for stage1 and stage2 (20:59:35Z to 21:00:38Z) and then restored to main with an empty index diff; nothing was committed inside the window (`pin-window.txt`). The stage1 backup is `~/ha-test/_backup-pre-phase8-20261015T205935Z`. The bench scripts are proven unchanged in `00-preflight/bench-scripts/cmp-proof.txt` (plan 09.2-04). `handoff.txt` (2026-10-15T21:03:33Z) records the pinned session for plans 09.2-07 and 09.2-08. Plan 09.2-07 re-asserted the pin before UAT-02 and never redid it (`uat-02/pin-reassert.txt`: build, handoff, fix and planning-excluded sha all equal FIX, HEAD main, no path outside `.planning/` differs from FIX, check-preflight.sh --quick and check-stale-anchor.sh PASS, StartedAt of mosq, ha-a and ha-b unchanged since the handoff, ha-c not running); plan 09.2-08 re-asserted it before the CR-01 gate (`cr01-gate/pin-reassert.txt`, PASS). Every UAT precheck of blocks 21 and 22 names FIX as the pinned sha.

### 19. CI (9.2): ci.yml and validate.yml green on the fix SHA
expected: CI (Ruff, Unit tests, Broker tests, Multi-instance tests) and Validate (hassfest, HACS) completed with success on a run whose headSha is exactly the fix SHA (event push or workflow_dispatch per the owner-approved Phase 9 D-04 amendment).
result: pass
sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74
date: 2026-10-15
evidence: .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/release
note: Plans 09.2-04 and 09.2-05. The owner reviewed the 09.2 product diff before the fast-forward (`review-decision.txt`, choice reviewed-clean after one fix-first round), local main was fast-forwarded to the phase branch (`fast-forward.txt`), and the local gate passed before the push (`push-readiness.txt`: Ruff check and format pass, 1727 passed and 2 xfailed, broker tier 18 passed). The owner decided to push (`push-decision.txt`, choice push, wire field `kept_legacy` acknowledged) and pushed exactly FIX to main with `git push origin 3dc9093f3cc49900bf76576cb4432d84aa94cd74:refs/heads/main`, a fast-forward from dc6513c (`push-main.txt`). The owner then dispatched CI run 38803359122 and Validate run 38803379292. Both have event workflow_dispatch, headSha FIX and conclusion success, and all six jobs succeeded: Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests, hassfest and HACS (`ci-fix-sha.json`, `ci-fix-sha-jobs.json`). Claude issued no push, dispatch or rerun. The dc6513c runs of block 13 do not count for this SHA.

### 20. HEAL (9.2): first start of the fix build on the restored failing state
expected: The first start of the fix build on the failing state, re-created from the pre-phase-9.1 registry backup with both instances stopped (bench decision confirm, heal_restore yes), leaves zero platform-mqtt rows and zero legacy mqtt devices of the two regression ids on ha-a and ha-b, by product behavior, with no hand edit of a registry (Phase 9.1 D-09, Phase 9.2 D-14).
result: pass
sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74
date: 2026-10-15
evidence: .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/heal-start
note: Plan 09.2-06 Task 2, the preflight stage2 start. Restore (`restore.txt`, bench decision `confirm` with `heal_restore: yes`): the StartedAt values of ha-a and ha-b matched `bench-before.txt`; with both instances stopped, the four registry files were copied with `cp -p` from `~/ha-test/_backup-pre-phase9.1-20261014T222425Z`. Their sha256 values equal those recorded in `09.1-evidence/00-preflight/backup-phase9.1.txt`, they are cmp-identical to the stage1 backup `~/ha-test/_backup-pre-phase8-20261014T222456Z`, and the live config entries and `mqtt_actions.state` equal that backup, so only the registries needed restoring. No registry file was edited by hand, and no tree started on the restored registries before stage2. Pre-state (`pre-state.txt`), on each of ha-a and ha-b: 2 platform-mqtt rows, `switch.lampe_test_2` and `select.bar_select_2`, both `disabled_by` integration, 2 legacy mqtt devices, "Lampe Test" (mqtt_actions_11111111-aaaa-4aaa-8aaa-000000000001) and "Bar Select" (mqtt_actions_b6bd2c0e-6d81-49ea-8025-4bd087bd718a), and 0 deleted records of the regression ids. Post-state after a graceful stop at 2026-10-15T21:01:26Z, on the flushed registries (`post-state-a.json`, `post-state-b.json`): 0 mqtt rows and 0 legacy devices on each instance, and both records are now `integration` tombstones. Log lines: ha-a logged "Removed 1 duplicate entities that a replayed legacy discovery created" twice; ha-b logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids, then "Removed 1 duplicate entities that a replayed legacy discovery created" twice (`log-a.txt`, `log-b.txt`). None of the 09.2 lines ("Kept the MQTT entities of N native devices", "cannot announce", "another instance keeps", "was not heard yet") appeared. Nothing was retained on `homeassistant/device/#` before or after the start (`retained-before.txt`, `retained-after.txt`). Both instances were started again after the verdict.

### 21. UAT-02 (integration, 9.2): late legacy Discovery replay, two starts, from integration tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74
date: 2026-10-15
evidence: .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-02
note: Plan 09.2-07 Task 1, run (a), 2026-10-15T21:09:17Z to 21:13:20Z, after the pin re-assert of block 18. `uat-02/` is the integration start (Phase 9.1 user decision 1): the start state is the one the heal start left, 0 live mqtt rows and the deleted-entity records of both regression ids with `disabled_by` integration on both instances. The read-only projection (`prepare.txt`) lists the four records that would flip to `disabled_by` null (switch and select on ha-a and ha-b, each `disabled_by` integration). The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha, and both baselines equal the 00-preflight registry baseline. All 16 assertions passed: E1 to E4 in round 1 and round 2 on ha-a and ha-b, with 34 mqtt_actions rows identical to the baseline (`result.txt`, `verdict.txt`). Per instance, the window shows the guard line "Disabled 1 duplicate entities that core MQTT created for native devices" 4 times and the catch line "Removed N duplicate entities that a replayed legacy discovery created" 8 times, 2, 2, 1 and 1 per start (`observations.txt`). After each start, core MQTT had cleared the legacy topics (`retained-topics.txt`). No ABORT occurred, and no "postponed", "keeps its MQTT device", "Kept the MQTT entities of N native devices", "cannot announce" or "the next start checks again" line appeared (`observations.txt`).

### 22. UAT-02 (null, 9.2): late legacy Discovery replay, two starts, from null tombstones (MIG-05)
expected: After retained legacy Discovery is re-published (while the instance is stopped) and the instance is started twice, no `_2` duplicate entities exist and the entity ids, registry ids and device ids are unchanged, which proves MIG-05 outside the test harness.
result: pass
sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74
date: 2026-10-15
evidence: .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-02-null
note: Plan 09.2-07 Task 1, run (b), 2026-10-15T21:17:14Z to 21:21:17Z, with `PHASE8_EV_SUFFIX=-null`. reseed-tombstones.sh stopped both instances, backed up both registries to `~/ha-test/_backup-pre-phase9.2-20261015T205830Z/reseed-20261015T211508Z`, flipped the four records from integration to null, validated both files and started both instances again; check-preflight.sh --quick and check-uat02.sh clean printed PASS. `prepare.txt` ends with the exact state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0" (the wording "before UAT-04" is the script's fixed text). The run used check-uat02.sh with E1 to E4 unchanged; `precheck.txt` names FIX as the pinned sha. All 16 assertions passed in both rounds on both instances (`result.txt`, `verdict.txt`). The logs show the same guard and catch counts as block 21 (4 and 8 per instance). After each start, core MQTT had cleared the legacy topics (`retained-topics.txt`). No ABORT occurred, and none of the lines listed in block 21 appeared (`observations.txt`).

### 23. UAT-04 (9.2): Discovery export and core prefix, from null tombstones
expected: The Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics.
result: pass
sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74
date: 2026-10-15
evidence: .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-04
note: Plan 09.2-07 Task 2 (Phase 9.1 D-12), 2026-10-15T21:25:16Z to 21:28:08Z. `prepare.txt` records both UAT-02 verdicts of blocks 21 and 22 as PASS, the read-only projection, and a new reseed with the backup `~/ha-test/_backup-pre-phase9.2-20261015T205830Z/reseed-20261015T212311Z`. It ends with the exact regression-state line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0". check-marker.sh approved and check-preflight.sh --quick printed PASS. check-uat04.sh ran with X1 to X10 unchanged: X1 to X4 for the three exported devices on the default prefix and on the core prefix, X5 and X6, X7 to X9 on ha-a and ha-b (one disabled mqtt row per exported device, the native row present and enabled, no enabled mqtt row) and X10 (nothing retained after the export was switched off) all printed PASS, 47 PASS lines and no FAIL line (`result.txt`, `verdict.txt`). The containers were not restarted during the run (StartedAt unchanged, `result.txt`).

### 24. CR-01 gate (9.2): cross-instance keep of a customized MQTT entity, release gate
expected: On exactly the fix SHA, three variants on real instances with expectations fixed before the run (plan 09.2-08, cr01-gate/expectations.txt): the positive control leaves no legacy row, legacy device or retained legacy topic on either instance after one start; in the reverse case the owner neither clears nor removes its disabled twin while the follower's customized row survives loaded; in the bench case the owner's customized row survives, the follower removes no integration-disabled row and the topic stays retained. The verdict is holds on ha-a and ha-b in all three.
result: pass
sha: 3dc9093f3cc49900bf76576cb4432d84aa94cd74
date: 2026-10-15
evidence: .planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/cr01-gate
note: Plan 09.2-08, 2026-10-15T21:36:12Z to 22:18:00Z. The pin re-assert printed PASS (`pin-reassert.txt`), and `expectations.txt`, `cr01-gate.sh` and `cleanup-cr01.sh` were committed before the first variant ran (order 3, 2, 1; ID is 11111111-aaaa-4aaa-8aaa-000000000001, "Lampe Test", owned by ha-a and mirrored natively on ha-b; NAME is "CR-01 kept button"). Line 1 of `verdict.txt` reads `holds`, with `build:` FIX; each variant's `outcome.txt` reads holds on ha-a and on ha-b. v3-positive-control holds: after one joint restart, no platform-mqtt row of ID, no legacy device and no retained topic on either instance; each instance logged "Removed 2" and then "Removed 1", ha-b also "keeps its MQTT device" once; the heartbeats after the start announce `kept_legacy: []` on both. v2-reverse holds: ha-b renamed its enabled replayed button to NAME and announced `kept_legacy: [ID]` (ha-a `[]`); ha-a restarted alone while ha-b kept running; ha-a kept its switch twin integration-disabled with the same registry id, left the topic retained (1203 bytes, JSON equal to the published payload) and logged "Removed 2" and "Kept the MQTT entities of 1 native devices: another instance keeps an MQTT entity of them or has not announced what it keeps"; on ha-b the renamed row stayed on platform mqtt, enabled, with state `unknown`, and its switch twin stayed integration-disabled. v1-bench-case holds: both instances renamed the button and announced `kept_legacy: [ID]` before a joint restart; on ha-a the renamed row stayed on platform mqtt and enabled, the switch twin stayed integration-disabled and the topic stayed retained and equal to the published payload (ha-a logged "Removed 1"); on ha-b the takeover moved the renamed row to platform mqtt_actions as `button.lampe_test_test_off_2` with its registry id (WR-04, allowed by the expectations), the integration-disabled switch twin stayed with the same registry id, and the catch removed the 2 enabled replay twins ("Removed 2", allowed, D-05); the heartbeats after the start read ha-a `[ID]`, ha-b `[]`. No ABORT, no re-run and no `contradicts` occurred. Bench hygiene (D-11, never a result): variant 3 needed no cleanup beyond product behavior and variant 2 a name reset, clear and restart; after variant 1, `check-uat02.sh clean` failed on ha-b because of the moved `_2` native row, so the pre-variant-1 copy `cr01-v1-pre-20261015T220218Z` was restored with both instances stopped at 22:11:41Z (`v1-bench-case/bench-notes.txt`); `cleanup-cr01.sh final` then printed PASS at 22:14:42Z. The verdicts were written before any cleanup step.

Not run in Phase 9 (D-05). They are not re-verified here, and nothing in this ledger claims they are:
- UAT-01: last recorded pass 2026-10-06 on b7f52b34, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-01`
- UAT-03: last recorded pass 2026-10-11 on b8232252, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-03-rerun2`
- P1-5: last recorded pass 2026-10-11 on b8232252, `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/p1-5-rerun2`

## Summary

total: 24
passed: 21
issues: 1
pending: 1
skipped: 0
blocked: 1

The issue (block 3) and the blocked block (block 4) are the 7baec98 history. Blocks 6 to 11 passed on
681c58793b656b51869906b62f2564829de7a10d and blocks 12 to 17 passed on dc6513c0b4ac54d68fbf5207161508c18cc2a5b6; both are
superseded history. On the current fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74, blocks 18 to 23 pass, the CR-01 release
gate (block 24) passes with the verdict `holds` in all three variants, and block 5 is pending. The CR-01 bench observation of
plan 09.1-11 (`contradicts` on dc6513c) stays an observation and is not counted here.

## Requirement verdicts

A requirement is complete only when all of its blocks are `pass`. The verdict stays `pending` until block 5 is recorded (plan
09-05). With block 3 `issue`, REL-01 cannot pass on 7baec98. On the fix SHA, blocks 3 and 4 are superseded by blocks 9 to 11.
On the fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6, blocks 9 to 11 are superseded by blocks 15 to 17. On the current fix
SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74, blocks 15 to 17 are superseded by blocks 21 to 23, and block 24 (the CR-01
release gate) is added.

| Requirement | Block | Verdict | Evidence |
|-------------|-------|---------|----------|
| REL-01 | 1 to 24 (blocks 3 and 4 superseded by blocks 9 to 11, then by blocks 15 to 17, then on the current fix SHA by blocks 21 to 23, plus the CR-01 release gate block 24) | pending | 7baec98 history: 09-evidence/00-preflight (pass), 09-evidence/release (CI pass), 09-evidence/uat-02 (issue), 09-evidence/uat-04 (blocked); 681c58793b656b51869906b62f2564829de7a10d history: 09.1-evidence/00-preflight (pass), 09.1-evidence/release (CI pass), 09.1-evidence/heal-start (pass), 09.1-evidence/uat-02 (pass), 09.1-evidence/uat-02-null (pass), 09.1-evidence/uat-04 (pass); dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 history: 09.1-evidence/fix2/00-preflight (pass), 09.1-evidence/fix2/release (CI pass), 09.1-evidence/fix2/heal-start (pass), 09.1-evidence/fix2/uat-02 (pass), 09.1-evidence/fix2/uat-02-null (pass), 09.1-evidence/fix2/uat-04 (pass); current fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74: 09.2-evidence/00-preflight (pass), 09.2-evidence/release (CI pass), 09.2-evidence/heal-start (pass), 09.2-evidence/uat-02 (pass), 09.2-evidence/uat-02-null (pass), 09.2-evidence/uat-04 (pass), 09.2-evidence/cr01-gate (holds, pass); REL pending (block 5, plans 09-04 and 09-05) |

## Gap closure

ACCEPTED-GAP-V101 closes for the v1.0.1 release only when blocks 3, 4 and 5 pass. Plan 09-05 records that. On 7baec98 the gap is
still open: block 3 is `issue` and block 4 is `blocked`. Phase 9.1 needs a fix SHA, a new bench run of UAT-02 and UAT-04 on that
SHA, and then the tag on that SHA.

Phase 9.1 (plan 09.1-06): on the fix SHA 681c58793b656b51869906b62f2564829de7a10d, blocks 9, 10 and 11 replace blocks 3 and 4 for
this rule. ACCEPTED-GAP-V101 closes for v1.0.1 only when blocks 9, 10, 11 and 5 pass. Blocks 9, 10 and 11 pass; block 5 is
pending. Plan 09-05 records the closure after the tag and release on the fix SHA.

Phase 9.1 (plan 09.1-12): on the current fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6, ACCEPTED-GAP-V101 closes for v1.0.1
only when blocks 15, 16, 17 and 5 pass. Blocks 15, 16 and 17 pass; block 5 is pending. 681c587 is superseded and never tagged.
The CR-01 bench observation (plan 09.1-11) read `contradicts`, so plans 09-04 and 09-05 are not re-pointed to this SHA yet; the
owner decides the route (a new decimal phase or a decision, see Gaps).

Phase 9.2 (plan 09.2-09): the owner's route was Phase 9.2. On the current fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74,
ACCEPTED-GAP-V101 closes for v1.0.1 only when blocks 21, 22, 23, 24 and 5 pass. Blocks 21, 22, 23 and 24 pass; block 5 is
pending. 681c587 and dc6513c are superseded and never tagged. Plan 09.2-09 re-points plans 09-04 and 09-05 to this SHA, and
plan 09-05 records the closure after the tag and release.

## Gaps

- truth: "After a retained legacy Discovery replay at start, two startup rounds leave no mqtt row, no `_2` id and no legacy mqtt device on ha-a and ha-b (UAT-02 E1 to E3, MIG-05)"
  status: resolved
  resolved_by: Phase 9.2, fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74, blocks 20 to 23 (first closed on 681c587, blocks 8 to 11, then on dc6513c, blocks 14 to 17, both superseded)
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
- truth: "While the legacy Discovery message of a device is still retained, a start keeps a renamed or otherwise customized MQTT entity of that device on every instance and never clears the shared topic under it (review fix CR-01, D-08 keep)"
  status: resolved
  resolved_by: Phase 9.2, fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74, block 24 (CR-01 release gate holds in all three variants)
  reason: "CR-01 bench observation of plan 09.1-11 on dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (2026-10-15), outcome `contradicts` on ha-a and ha-b: after one graceful start with the legacy message retained, ha-b's takeover moved its renamed legacy button to platform mqtt_actions, ha-b's catch then removed the integration-disabled switch twin on legacy content ('Removed 3 duplicate entities'), core MQTT on ha-b cleared the shared topic, and core MQTT on ha-a deleted ha-a's kept, renamed button. The D-08 keep is decided per instance, the clear goes to a topic all instances share. This is an observation, not a ledger block; blocks 12 to 17 are unaffected"
  severity: major
  test: none (bench observation of plan 09.1-11, not a ledger block; it holds back block 5)
  artifacts:
    - path: ".planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/cr01-observation/outcome.txt"
      issue: "line 1 reads contradicts; per-instance facts for ha-a and ha-b"
    - path: ".planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/fix2/cr01-observation/findings.txt"
      issue: "the recorded facts of the start and their reading (cross-instance clear)"
  missing:
    - "owner route: a new decimal phase that fixes the cross-instance clear before the v1.0.1 tag, or a decision that accepts and documents it; until then plans 09-04 and 09-05 are not re-pointed to dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 and the release notes are unchanged"

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

Phase 9.1 after the review fixes (fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6), observations only:

- **Pre-state restore (owner decision 2026-10-15).** Before the heal start, the four registry files of ha-a and ha-b were
  copied back from `~/ha-test/_backup-pre-phase9.1-20261014T222425Z` with both instances stopped. The sha256 values match the
  recorded backup, the files are cmp-identical to the stage1 backup, and the config entries and `mqtt_actions.state` were equal,
  so nothing else was restored (`fix2/heal-start/restore.txt`).
- **Heal start log (block 14).** ha-a logged "Removed 1 duplicate entities that a replayed legacy discovery created" twice.
  ha-b logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids, then the same
  "Removed 1 ..." line twice, and its rows and legacy devices were gone afterwards. Nothing was retained on the core prefix
  (`fix2/heal-start/log-a.txt`, `log-b.txt`, `retained-before.txt`, `retained-after.txt`).
- **"postponed" and "keeps its MQTT device".** No "Takeover of device ... postponed" line appeared in the heal start or in either
  UAT-02 run. "keeps its MQTT device" appeared at the heal start on ha-b (twice) and never in a UAT-02 run; neither UAT-02 run
  logged the catch's final-pass "the next start checks again" line (`fix2/uat-02/observations.txt`,
  `fix2/uat-02-null/observations.txt`).
- **Guard log in UAT-04 (block 17).** "Disabled 1 duplicate entities that core MQTT created for native devices" appeared twice on
  ha-a and twice on ha-b during the run (`fix2/uat-04/guard-log-a.txt`, `guard-log-b.txt`).
- **Post-UAT-04 restart.** After "export off", each instance still held 3 disabled mqtt rows. After one graceful restart
  (2026-10-15T10:12:32Z, plus 90 s) both held 0 live mqtt rows, the guard logged nothing on that start, and
  `check-uat02.sh clean` printed PASS (`fix2/uat-04/post-restart.txt`, `post-run-*.json`, `post-restart-*.json`).
- **CR-01 bench observation (plan 09.1-11), an observation, never a result.** Line 1 of `fix2/cr01-observation/outcome.txt`
  reads `contradicts`. A renamed, enabled legacy test button ("CR-01 kept button") next to an integration-disabled switch twin,
  with the legacy Discovery message still retained, across one graceful start of both instances. Per instance
  (`outcome.txt`, `findings.txt`):
  - ha-a: contradicts. The renamed button is no longer on platform mqtt; its deleted record keeps the name and disabled_by
    null. The switch twin is gone, the topic holds no retained payload, and the integration logged no line in this start.
  - ha-b: contradicts. The takeover moved its renamed button to platform mqtt_actions (entity id `_2`, name kept, enabled),
    the log reads "keeps its MQTT device" and "Removed 3 duplicate entities that a replayed legacy discovery created", and
    the switch twin is gone.
  - Reading in `findings.txt` (interpretation, not separately proven): ha-b's catch found no kept, enabled legacy row after
    the move and removed the disabled twin on legacy content; core MQTT on ha-b cleared the shared topic, and core MQTT on ha-a
    deleted its kept, renamed button 4 to 22 ms later. The D-08 keep is decided per instance, but the clear goes to a topic
    that all instances share.
  - The bench was returned to the clean state with the fallback restore of the pre-observation registry copy, with both
    instances stopped (`cleanup.txt`, `bench-notes.txt`). No verdict of blocks 12 to 17 changed.
- **Accepted residual risks (Phase 9.1 user decisions 2 and 5), unchanged and not exercised as results.** The broker-restart
  race and the follower deletion when the owner clears a stale legacy Discovery message stay as described above.

Phase 9.2 (fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74), observations only:

- **Owner decisions.** Review: `reviewed-clean` after one fix-first round (WR-01, WR-02, WR-03, IN-01, IN-02 fixed test first;
  WR-03 keeps the conservative shared retry budget; IN-01 is mirrored into the release notes), `release/review-decision.txt`.
  Push: `push`, with the new heartbeat key `kept_legacy` acknowledged, `release/push-decision.txt`. Bench: `confirm` with
  `heal_restore: yes` and the CR-01 gate procedure of plan 09.2-08, `00-preflight/bench-decision.txt`.
- **Heal start log (block 20).** ha-a logged "Removed 1 duplicate entities that a replayed legacy discovery created" twice.
  ha-b logged "Device '<id>' keeps its MQTT device: it has entries this integration did not create" for both ids, then the same
  "Removed 1 ..." line twice. The 09.2 lines ("Kept the MQTT entities of N native devices", "cannot announce", "another
  instance keeps", "was not heard yet") did not appear. Nothing was retained on the core prefix
  (`heal-start/log-a.txt`, `log-b.txt`, `retained-before.txt`, `retained-after.txt`). The same pattern as the dc6513c heal start.
- **"postponed", "keeps its MQTT device" and the 09.2 count-only lines in UAT-02.** Neither UAT-02 run logged "Takeover of
  device ... postponed", "keeps its MQTT device", any "Kept the MQTT entities of N native devices" line ("another instance
  keeps", "was not heard yet", "is not known"), "cannot announce" or the catch's final-pass "the next start checks again"
  line, in the script logs or in podman logs (`uat-02/observations.txt`, `uat-02-null/observations.txt`). In each start the
  owner ha-a logged its second catch pass about 1 s before the follower ha-b, with core MQTT's "No device components to
  cleanup" for both ids in between.
- **Guard log in UAT-04 (block 23).** "Disabled 1 duplicate entities that core MQTT created for native devices" appeared twice on
  ha-a and twice on ha-b during the run, with no 09.2 catch line in that window (`uat-04/guard-log-a.txt`, `guard-log-b.txt`).
- **Post-UAT-04 restart.** After "export off", each instance still held 3 disabled mqtt rows. After one graceful restart
  (2026-10-15T21:28:31Z, plus 90 s) both held 0 live mqtt rows, the guard logged nothing on that start, and
  `check-uat02.sh clean` printed PASS. Unlike the dc6513c run, that start logged three "Removed 1 duplicate entities" catch
  lines on each instance, and ha-b logged "keeps its MQTT device" for the switch, the select and the marker id; afterwards ha-b
  held no legacy mqtt_actions device and ha-a only the pre-existing "UAT Iso Clean" device without entities
  (`uat-04/post-restart.txt`, `post-run-*.json`, `post-restart-*.json`).
- **CR-01 gate heartbeats (block 24).** With ID = 11111111-aaaa-4aaa-8aaa-000000000001, the `kept_legacy` projections of the
  heartbeats matched each variant: `[]` on both after
  variant 3; ha-b `[ID]` and ha-a `[]` before and after variant 2; `[ID]` on both before variant 1, and ha-a `[ID]`, ha-b `[]`
  after it (ha-b's row had moved to the native platform). In variant 2, ha-a logged "Kept the MQTT entities of 1 native
  devices: another instance keeps an MQTT entity of them or has not announced what it keeps" about 38 s after its start.
- **CR-01 gate hygiene restore (D-11), never a result.** After variant 1, the pre-variant-1 registry copy was restored with both
  instances stopped, because ha-b's moved `_2` native row made `check-uat02.sh clean` fail; the verdicts had been written before
  any cleanup step (`cr01-gate/v1-bench-case/bench-notes.txt`, `cleanup.txt`). Variants 3 and 2 needed no restore.
- **Residual limits, not exercised as results.** The broker-restart race of Phase 9.1 user decision 2 stays. The follower deletion
  of Phase 9.1 user decision 5 is replaced by the Phase 9.2 behavior: only the owner lets the shared legacy topic go empty, and
  only when no online instance announces a kept row. The limits that stay are an online instance older than 1.0.1, an offline
  owner, the live-customization moment, the one-time cutover clear (review finding IN-01) and the live-replay limit.

## Bench state left behind

After plan 09.2-08 (fix SHA 3dc9093f3cc49900bf76576cb4432d84aa94cd74, current):

- mosq, ha-a and ha-b are Up on the fix tree 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (`check-preflight.sh --quick` PASS,
  2026-10-15T22:14:42Z). ha-c is stopped.
- The registries of ha-a and ha-b are the pre-variant-1 copy `cr01-v1-pre-20261015T220218Z`, restored with both instances
  stopped after the CR-01 gate (D-11 hygiene). `check-uat02.sh clean` and `check-uat04.sh clean` print PASS, nothing is
  retained on `homeassistant/device/#`, and no entity or deleted record is named "CR-01 kept button"
  (`cr01-gate/v1-bench-case/cleanup.txt`, `cleanup-cr01.sh final` PASS).
- Backups: the 9.2 backup `~/ha-test/_backup-pre-phase9.2-20261015T205830Z` (mode 700, pointer
  `~/ha-test/.current-backup-phase9.2`, the dc6513c end state) with the reseed copies `reseed-20261015T211508Z` and
  `reseed-20261015T212311Z` and the pre-variant copies `cr01-v3-pre-20261015T214513Z`, `cr01-v2-pre-20261015T215228Z` and
  `cr01-v1-pre-20261015T220218Z`, and the stage1 backup `~/ha-test/_backup-pre-phase8-20261015T205935Z`. The earlier backups
  listed below are kept.
- No stray `mosquitto_sub` is running. The bench and its tokens are kept until Phase 12 (owner follow-up from Phase 8).

After plan 09.1-11 (fix SHA dc6513c0b4ac54d68fbf5207161508c18cc2a5b6, history):

- mosq, ha-a and ha-b are Up on the fix tree dc6513c0b4ac54d68fbf5207161508c18cc2a5b6 (`check-preflight.sh --quick` PASS,
  2026-10-15T10:40:49Z). ha-c is stopped.
- The registries of ha-a and ha-b are the pre-observation copy `cr01-pre-20261015T102353Z`, restored with both instances
  stopped after the CR-01 observation. `check-uat02.sh clean` and `check-uat04.sh clean` print PASS, nothing is retained on
  `homeassistant/device/#`, and no entry or deleted record is named "CR-01 kept button" (`fix2/cr01-observation/cleanup.txt`).
- Backups: the fix2 backup `~/ha-test/_backup-pre-phase9.1-fix2-20261015T094121Z` (mode 700, pointer
  `~/ha-test/.current-backup-phase9.1-fix2`, the 681c587 end state) with the reseed copies `reseed-20261015T095919Z` and
  `reseed-20261015T100723Z` and the pre-observation copy `cr01-pre-20261015T102353Z`, and the stage1 backup
  `~/ha-test/_backup-pre-phase8-20261015T094228Z`. The earlier backups listed below are kept.
- No stray `mosquitto_sub` is running. The bench and its tokens are kept until Phase 12 (owner follow-up from Phase 8).

After plan 09.1-05 (681c587, history):

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
