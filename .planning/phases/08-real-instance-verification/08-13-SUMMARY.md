---
phase: 08-real-instance-verification
plan: 13
subsystem: verification-gap-closure
tags: [uat-04, rerun, repin, guard, entity-registry, bench-scripts, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: owner decision guard-and-document with modifier full-rerun (plan 08-11), export-duplicate guard in manager.py and takeover.py (plan 08-12)
provides:
  - re-pinned build under test (caf2fe5, tree of the guard commit 2b3b9c3) with previous_sha b7f52b34 and the first record kept as build-b7f52b34.txt
  - proof from the flushed registry files that the original failing tombstone state was intact before the guard build started
  - re-run evidence beside the first runs: uat-02-rerun PASS, uat-03-rerun PASS, p1-5-rerun PASS, uat-04-rerun FAIL
  - re-run support in the bench scripts (PHASE8_EV_SUFFIX) with every expectation block unchanged, shown by a diff
affects: [08-14, 08-15]
coverage:
  - id: D1
    description: "Bench re-pinned to the guard build, original failing state proven intact, scripts patched for re-runs beside the recorded evidence"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-preflight.sh --quick; ~/ha-test/bin/check-stale-anchor.sh; uat-04-rerun/prepare.txt"
        status: pass
    human_judgment: false
  - id: D2
    description: "UAT-02, UAT-03 and P1-5 re-run on the guard build with the original expectations"
    verification:
      - kind: other
        ref: "uat-02-rerun/verdict.txt, uat-03-rerun/verdict.txt, p1-5-rerun/verdict.txt (line 1 PASS)"
        status: pass
    human_judgment: false
  - id: D3
    description: "UAT-04 re-run with the original expectations X1 to X10; the outcome is a FAIL on ha-b (X7 twice, X8), recorded as it is"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "uat-04-rerun/verdict.txt (line 1 FAIL), uat-04-rerun/result.txt"
        status: fail
    human_judgment: true
    rationale: "The outcome is a failed expectation; plan 08-14 records it in the ledger and the owner decides the next step"
actuals:
  tokens: 50700
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "re-run evidence goes beside the recorded run through one environment variable (PHASE8_EV_SUFFIX), expectations untouched"
    - "re-pin records previous_sha and keeps the old build file; the stale anchor is read against the new pin"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun/
    - .planning/phases/08-real-instance-verification/08-evidence/uat-02-rerun/
    - .planning/phases/08-real-instance-verification/08-evidence/uat-03-rerun/
    - .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun/
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/build-b7f52b34.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/repin.sh
  modified:
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/build.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/mount-hashes.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/ (check-uat02.sh, check-uat03.sh, check-uat04.sh, check-p15.sh, setup-marker.sh, run-all-scripted.sh, README.txt)
key-decisions:
  - "The UAT-04 re-run on the guard build FAILS on ha-b; the result stands, nothing was repeated or edited (D-08 failure rule)"
  - "mosq was found stopped by a host reboot and was started again; the preflight anchor for its StartedAt was re-anchored and the old value kept"
requirements-completed: []
duration: 31 min
completed: 2026-10-11
status: complete
commits: 2
plan_head_before: caf2fe5dc003ea834104f4016d1996be4132e0c8
plan_head_after: 287dd50248b08326c00c6403b59bbf0c789fe5f7
---

# Phase 8 Plan 13: re-pin and scripted re-run of the UAT-04 gap closure Summary

**The guard build was re-pinned and the whole scripted group re-run with the original expectations: UAT-02, UAT-03 and P1-5 PASS, but UAT-04 FAILS on ha-b, where the two core-prefix duplicates restored from the tombstones are still enabled; the evidence stands beside the first failing run.**

## Performance

- Start 2026-10-11T10:29Z, end about 11:00Z, 31 min (the scripted group itself ran 10:34Z to about 10:55Z)
- 2 tasks, 2 task commits (`db021d1`, `287dd50`), 55 files, no ledger file edited
- Disposition read: `guard-and-document`, modifier `full-rerun` (`applies repin` yes, `guard` yes, `full-rerun` yes, `prune` no, `scoped` no)

## What was done

- **Task 1 (db021d1), prepare:**
  - Script patches: the evidence folder name of `check-uat02.sh`, `check-uat03.sh`, `check-p15.sh`, `check-uat04.sh` and `setup-marker.sh` carries `PHASE8_EV_SUFFIX` (default empty); `check-uat04.sh` runs its nested `check-uat02.sh clean` with the variable unset and copies the ACL backup only when `acl.bak-phase8-04` does not exist yet; `run-all-scripted.sh` prints and reads the suffixed path. Nine diff hunks in `uat-04-rerun/script-patches.diff`; a comparison of every comment line (the coded expectation blocks) of the four check scripts against the committed copies is identical.
  - `repin.sh` (new): asserted the mount is byte-identical to the new tree, the product diff against `b7f52b34` names only `manager.py` and `takeover.py`, stopped both instances, read the flushed registry files (original tombstones with `disabled_by` null for the Lampe Test switch and the Bar Select select on ha-a and ha-b, no live mqtt row, nothing pruned), kept the old `build.txt` as `build-b7f52b34.txt`, started both on the new code, rewrote `build.txt` (`sha: caf2fe5d...`, `previous_sha: b7f52b34...`, `repin_reason: product guard of plan 08-12 (D-03)`) and `mount-hashes.txt` (all eight hashes match), and `check-preflight.sh --quick` printed PASS. `check-stale-anchor.sh` PASS, `check-uat02.sh clean` PASS before the runs.
- **Task 2 (287dd50), run:**
  - Marker reset: subentry of the old marker deleted on ha-a (mirror and retained topics gone), `MARKER_ID` removed, the same inert marker imported again (new uuid `33239fb1-67a9-481f-9f69-afdab7b31417`), `check-marker.sh pending` PASS.
  - `PHASE8_EV_SUFFIX=-rerun run-all-scripted.sh`, each check after `check-preflight.sh --quick`: UAT-02 PASS, UAT-03 PASS, P1-5 PASS, UAT-04 FAIL. Evidence in `uat-02-rerun/`, `uat-03-rerun/`, `p1-5-rerun/`, `uat-04-rerun/`. The first-run folders are untouched (`git diff --stat` empty). `check-uat04.sh clean` and `check-preflight.sh --quick` PASS afterwards; `check-evidence-clean.sh` PASS over the whole evidence tree.

## UAT-04 re-run: observed result (FAIL, stands)

Verdict line 1 `FAIL`, three failed expectations (the same three expectations the first run failed on ha-b; on ha-a they now pass):

| Expectation | ha-a | ha-b |
|-------------|------|------|
| X7 Lampe Test (one mqtt row, `disabled_by` integration) | PASS | FAIL: 1 row, `disabled_by` null |
| X7 Bar Select | PASS | FAIL: 1 row, `disabled_by` null |
| X7 UAT Marker (new, never had a tombstone) | PASS | PASS |
| X8 no enabled mqtt row | PASS | FAIL: `select.bar_select_2`, `switch.lampe_test_2` enabled |
| X1 to X6, X9, X10 | PASS | PASS |

First run for comparison: FAIL on X7 and X8 on both instances (`uat-04/verdict.txt`).

Reading of the cause, from the evidence and `manager.py` (not a new run): the options flow was applied on ha-a only (`options-flow.txt`), so only ha-a exports. The guard (`_sync_export_guard`) arms per instance only when that instance's own export is on with the core prefix, and acts on `_export_guard_ids()` (devices of that instance). ha-b's core MQTT still receives ha-a's retained export on `homeassistant/device/...` from the shared broker, restores the enabled state of its own null tombstones (Lampe Test, Bar Select) and creates enabled duplicates; ha-b's guard is not armed, so nothing disables them. The guard therefore works on the exporting instance (ha-a, X7 and X8 PASS) and not on the instances that receive the export. The product claim of the README (every instance holds one disabled mqtt row per exported id) is not met on ha-b. This is a finding for 08-14 and the owner; it is not fixed here (plan scope is run and evidence).

## Deviations from Plan

**1. [Rule 3 - Blocking] The host had rebooted before the plan started; the broker and both instances were down.**
- **Found during:** Task 1 start (`podman ps -a`: ha-a, ha-b, ha-c, mosq Exited; host uptime 1 day 1 h).
- **Issue:** the plan assumes a running bench. `mosq` runs with persistence off, so all retained messages were gone, and `check-preflight.sh` asserts that mosq `StartedAt` equals `~/ha-test/.mosq-started-before-phase8`.
- **Fix:** `podman start mosq` (StartedAt 2026-10-11 12:31:00 +0200), then rewrote the anchor file to that value; the old value stays in `~/ha-test/.mosq-started-before-phase8.pre-reboot`. The instances republished their retained documents on connect (preflight round trip PASS, UAT-02 baseline step found the config documents). The gate keeps asserting what it is for: no mosq restart during the re-run (the `mosq not restarted` line of `p1-5-rerun/result.txt` is PASS). Recorded in the first block of `uat-04-rerun/prepare.txt`.
- **Files modified:** `~/ha-test/.mosq-started-before-phase8` (outside the repo).
- **Commit:** db021d1 (the record).
- **Consequence to weigh:** the re-run ran in a new broker lifetime; the first runs were taken in the old one. The registries (the state the UAT-04 clause depends on) were the intact original files, proven in `prepare.txt`.

**2. [Rule 3 - Blocking] `setup-marker.sh` also writes into `uat-03/` (it would have overwritten the first run's `fixture.txt`).** The plan names only four check scripts for the suffix patch. The same one-line suffix change was applied to `setup-marker.sh`, so the re-created marker's `fixture.txt` is in `uat-03-rerun/` and `uat-03/` is untouched. Files: `~/ha-test/bin/setup-marker.sh`, its copy in `bench-scripts/`. Commit db021d1.

**3. [Rule 3 - Blocking] The marker was re-created with a new uuid** (the plan's reset step imports it again, which always gives a new uuid). `check-uat02.sh clean` already excludes marker rows by `MARKER_ID`, so no script change was needed. The old marker's mqtt tombstone (`switch.uat_marker_2`, `disabled_by` integration) stays in both registries.

**4. Pin value.** `build.txt` records HEAD of the mount-source checkout at re-pin time (`caf2fe5`, a docs commit) as `sha`, exactly as the first record recorded the then-HEAD; its `custom_components` tree equals the guard commit `2b3b9c3` (the check compares trees). No guard-specific key was added beyond `previous_sha` and `repin_reason`.

**Total deviations:** 4 (3 Rule 3 bench/script items, 1 note). **Impact:** none on the expectations or their outcome; the reboot is the only item that changes the context of the re-run and is disclosed in `prepare.txt`.

## Bench state left behind

- ha-a and ha-b running on the guard build (re-pinned), mosq running (new lifetime, re-anchored), export off, nothing retained under `mqtt_actions_export/` or `homeassistant/device/` (`check-uat04.sh clean` PASS, `check-preflight.sh --quick` PASS).
- The UAT-04 run left live mqtt rows (ha-a 3, ha-b 1; the observation line of the script, as after the first run). `check-uat02.sh clean` therefore FAILs now (mqtt rows, `_2` ids, a legacy device); it was not part of this plan's verification and nothing was cleaned to alter the recorded outcome.
- `~/ha-test/.fixtures.env` holds the new `MARKER_ID` (copy of the old file: `.fixtures.env.pre-08-13`); the marker is approved on ha-b.

## Next

Plan 08-14 records the outcome (UAT-04 re-run FAIL on ha-b, the other three PASS) in the ledger and the traceability as it is. UAT-04 stays Pending; I did not mark it complete in REQUIREMENTS.md. The finding that the guard does not reach instances that only receive the export needs the owner's decision (extend the guard to receivers, document the limit, or another disposition) before a further re-run; none was started.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register: T-08-38 did not apply (no prune; the registry files were only read), T-08-40 `check-evidence-clean.sh` PASS over the evidence tree and `bench-scripts/`, T-08-41 the patch diff shows only the suffix lines and the ACL backup guard.

## Self-Check: PASSED

- Commits `db021d1` and `287dd50` are in the branch (`git merge-base --is-ancestor`).
- `uat-04-rerun/verdict.txt` line 1 FAIL, `uat-02-rerun`, `uat-03-rerun`, `p1-5-rerun` verdicts PASS; `build.txt` has `previous_sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`, `build-b7f52b34.txt` exists; `git diff --stat HEAD -- .../uat-04 uat-02 uat-03 p1-5` empty.
- The plan's verify commands: `check-uat04-iso.sh disposition` guard-and-document, `check-uat04.sh clean` and `check-preflight.sh --quick` PASS, `check-evidence-clean.sh` PASS.
