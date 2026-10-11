---
phase: 08-real-instance-verification
plan: 18
subsystem: verification-gap-closure
tags: [uat-04, uat-02, uat-03, p1-5, rerun, repin, receiver-guard, entity-registry, bench-scripts, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: receiver-side duplicate guard in manager.py and takeover.py (plan 08-17), owner decision UAT04-RECEIVER-GUARD = extend-and-confirm (plan 08-16), the failed 08-13 re-run on ha-b
provides:
  - bench re-pinned to the receiver-guard build (build.txt with previous_sha caf2fe5d and first_sha b7f52b34, earlier records kept)
  - cleanup of the 08-13 leftovers through the product's own restart, no hand edit of a live row
  - final scripted re-run with unchanged expectations: uat-02-rerun2 PASS, uat-03-rerun2 PASS, p1-5-rerun2 PASS, uat-04-rerun2 PASS
  - proof that UAT-04 started from the failing state (null tombstones on both instances, no live mqtt row)
  - observation of the guard on the receiver (INFO lines of both containers) and of the restart cleanup
affects: [08-14, 08-15]
coverage:
  - id: D1
    description: "Bench re-pinned to the receiver-guard build, 08-13 leftovers removed by the product's restart cleanup, check scripts provably unchanged"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-preflight.sh --quick; check-stale-anchor.sh; check-uat02.sh clean; cmp of the eight check scripts against bench-scripts/; uat-04-rerun2/prepare.txt"
        status: pass
    human_judgment: false
  - id: D2
    description: "UAT-02, UAT-03 (fresh marker) and P1-5 re-run on the receiver-guard build with the original expectations"
    requirement: UAT-02
    verification:
      - kind: other
        ref: "uat-02-rerun2/verdict.txt, uat-03-rerun2/verdict.txt, p1-5-rerun2/verdict.txt (line 1 PASS)"
        status: pass
    human_judgment: false
  - id: D3
    description: "UAT-04 re-run from the restored failing state with the original expectations X1 to X10"
    requirement: UAT-04
    verification:
      - kind: other
        ref: "uat-04-rerun2/verdict.txt (line 1 PASS), uat-04-rerun2/result.txt, uat-04-rerun2/prepare.txt (regression state line)"
        status: pass
    human_judgment: false
actuals:
  tokens: 60900
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "re-run evidence beside the earlier runs through PHASE8_EV_SUFFIX=-rerun2, expectations untouched"
    - "failing precondition restored by a backed-up, validated flip of one field on existing registry records, abort instead of fabricate"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun2/
    - .planning/phases/08-real-instance-verification/08-evidence/uat-02-rerun2/
    - .planning/phases/08-real-instance-verification/08-evidence/uat-03-rerun2/
    - .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun2/
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/build-caf2fe5d.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/repin-rerun2.sh
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/reseed-tombstones.sh
  modified:
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/build.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/mount-hashes.txt
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/README.txt
key-decisions:
  - "UAT-04 PASSES on the receiver-guard build from the restored failing state; nothing was repeated or edited to get it (D-08)"
  - "No ledger file and no requirement checkbox was touched: plan 08-14 records the outcome"
requirements-completed: []
duration: 37 min
completed: 2026-10-11
status: complete
commits: 2
plan_head_before: b8232252540a55969145ca0034d8fd86b4be3b7c
plan_head_after: 93af3450bc12a7c2a3e427521e8e7aed3fe99ea5
---

# Phase 8 Plan 18: re-pin to the receiver-guard build and final scripted re-run Summary

**The bench was re-pinned to the receiver-guard build and the whole scripted group re-run with the original expectations from the failing tombstone state: UAT-02, UAT-03, P1-5 and UAT-04 all PASS. On ha-b, which only receives the export, X7 and X8 now hold (one mqtt row per exported id, `disabled_by` integration, no enabled mqtt row), the cases that failed in 08-13.**

No FAIL occurred, so there is nothing to name first. The runs stand as they came out; no run was repeated and no expectation was edited.

## Performance

- Start 2026-10-11T12:51Z, end about 13:28Z, 37 min (re-pin 12:52Z to 12:57Z, scripted group 13:00Z to 13:23Z, observations to 13:27Z)
- 2 tasks, 2 task commits (`4e04ca7`, `93af345`), no ledger file edited, no product file edited
- Disposition read: `guard-and-document` (`check-uat04-iso.sh disposition`), owner decision `extend-and-confirm`

## What was done

- **Task 1 (4e04ca7), re-pin and cleanup:**
  - `repin-rerun2.sh` (new, outside the repo, scrubbed copy in `bench-scripts/`): required `build.txt` to name `caf2fe5d`, resolved the new pin (`b8232252540a55969145ca0034d8fd86b4be3b7c`, the HEAD of the mount source), asserted the mount is byte-identical to its tree, asserted that the product diff against both `caf2fe5d` and `b7f52b34` names only `manager.py` and `takeover.py` (stats recorded), stopped both instances gracefully, projected the state before from the flushed registry files, backed up both entity and device registries to `~/ha-test/_backup-pre-gap-rerun2-20261011T125246Z/{a,b}/` (0700, pointer `.current-backup-gap08-rerun2`), kept `build-caf2fe5d.txt`, started both on the new code, waited the 90 s settle time, rewrote `build.txt` (`previous_sha`, new `first_sha`, `repin_reason: receiver-side guard of plan 08-17 (D-03)`) and `mount-hashes.txt` (all eight hashes match), and ran `check-preflight.sh --quick` (PASS).
  - Cleanup: the restart that carries the new code removed the 08-13 leftovers by itself (research assumption A4): ha-a went from 3 live mqtt rows to 0, ha-b from 1 to 0, and `check-uat02.sh clean` printed PASS at the first attempt. No second restart and no WebSocket removal was needed; no live row was edited by hand. One legacy `UAT Iso Clean` mqtt device stays on ha-a; it is not one of the migrated ids and the check passes with it.
  - `reseed-tombstones.sh` (new, scrubbed copy in `bench-scripts/`): written, shellcheck clean apart from info notes, and its read-only `--check` shown in `prepare.txt` (ha-a: both records `disabled_by` integration, ha-b: both null, as expected).
  - `cmp` of `check-uat02.sh`, `check-uat03.sh`, `check-uat04.sh`, `check-p15.sh`, `run-all-scripted.sh`, `setup-marker.sh`, `check-marker.sh`, `lib.sh` against `bench-scripts/`: all byte-identical (expectations unchanged). `check-evidence-clean.sh` PASS, README gained the 08-18 lines.
- **Task 2 (93af345), the scripted group:**
  - `runner-order.txt` saved. Marker reset (copy `.fixtures.env.pre-08-18`, subentry deleted on ha-a, `MARKER_ID` removed, same inert marker imported again, new uuid `87c29b56-8abe-4531-b03c-c402a2f10cb8`), `check-marker.sh pending` PASS, `check-uat02.sh clean` PASS.
  - Each check ran with `PHASE8_EV_SUFFIX=-rerun2` right after `check-preflight.sh --quick`, in the runner's order: UAT-02 PASS, UAT-03 PASS (A to D on both instances, unapproved control 0, unknown payload ignored, banana not retained), P1-5 PASS (toggle +1, restart 0, reload 0, positive control +1, mosq not restarted).
  - The tombstone projection after those three checks (`prepare.txt`) shows what the plan predicted: on this build the replay of UAT-02 turned the null tombstones of the Lampe Test switch and the Bar Select select into `disabled_by` integration on both instances (the guard disables a replayed row before the catch removes it). `reseed-tombstones.sh` then flipped `disabled_by` back to null on exactly those four existing records (backup `.../reseed-20261011T131823Z/{a,b}/`), validation passed (valid JSON, entities identical, deleted-entity count unchanged, every other record identical, targets differ only in `disabled_by`), both instances started, `check-preflight.sh --quick` and `check-uat02.sh clean` PASS, and `prepare.txt` holds the exact line `regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0`. `check-marker.sh approved` PASS.
  - `check-uat04.sh run` right after the gate: PASS. The options flow was applied on ha-a only, so ha-b was the pure receiver.

## UAT-04 re-run: observed result (PASS)

| Expectation | ha-a | ha-b |
|-------------|------|------|
| X1 to X6, X10 (shape, core prefix, cleared on off) | PASS | (broker-level, same for both) |
| X7 Lampe Test (one mqtt row, `disabled_by` integration) | PASS | PASS (FAIL in 08-13: `disabled_by` null) |
| X7 Bar Select | PASS | PASS (FAIL in 08-13: `disabled_by` null) |
| X7 UAT Marker (never had a tombstone) | PASS | PASS |
| X8 no enabled mqtt row | PASS | PASS (FAIL in 08-13: two enabled `_2` rows) |
| X9 native row present and enabled | PASS | PASS |

## Observations (recorded, not expectations)

- **Guard on the receiver:** the guard INFO line (`Disabled 1 duplicate entities that core MQTT created for native devices`) appears twice on ha-a and twice on ha-b within the UAT-04 window, all four at 15:22:36 local time, i.e. when the core-prefix export arrived: one pass for the switch, one for the select, on the exporter and on the receiver (`guard-log-a.txt`, `guard-log-b.txt`). The marker needed no pass because it had no tombstone and core created its row disabled.
- **Rows after the run:** both instances hold three live mqtt rows, all `disabled_by` integration (`post-run-a.json`, `post-run-b.json`), as in the earlier runs, except that the Lampe Test and the Bar Select rows are now disabled on ha-b as well.
- **Restart cleanup:** after one graceful restart of both instances and 90 s settle time, both hold 0 live mqtt rows, ha-a keeps the one legacy `UAT Iso Clean` device (not a migrated id), ha-b none, and `check-uat02.sh clean` prints PASS (`post-restart.txt`, `post-restart-a.json`, `post-restart-b.json`). This is the observation behind the README sentence that the next start removes the disabled leftovers; it held on both instances.

## Deviations from Plan

**1. [Rule 3 - Blocking] A `mosquitto_sub` left running by the UAT-03 run of plan 08-13 wrote into a committed earlier evidence folder.**
- **Found during:** Task 2 step 1 (`git status` after deleting the old marker showed ` M .../uat-03-rerun/topic-capture.txt`).
- **Issue:** `check-uat03.sh` starts its topic capture in the background and does not stop it. The leftover process (PID started 12:41Z) was still writing to `uat-03-rerun/topic-capture.txt` and recorded the retained clear (empty payload) of the old marker's state topic as an extra line, which would have broken the "earlier folders untouched" rule.
- **Fix:** the process was stopped, that one file was restored with `git checkout --` (a single path, nothing else touched), and the event is recorded in `prepare.txt`. The same script left a new capture running after the new UAT-03 run (its own folder `uat-03-rerun2/`); it was stopped after the verdict was written and the capture already held steps A to D, so later checks (P1-5 toggles) could not add lines to it. The check script was not changed, which keeps the byte-identity claim.
- **Files modified:** `uat-03-rerun/topic-capture.txt` restored (byte-identical to the 08-13 commit), `uat-04-rerun2/prepare.txt` (the record).
- **Commit:** 93af345.
- **Consequence to weigh:** none on any expectation; the bench scripts have a latent defect (a capture process that outlives its check) that plan 08-14 may note.

**2. [Rule 3 - Blocking] The first marker import was answered 400 Bad Request.** The request file lacked the `data` wrapper that `setup-marker.sh` posts as the body. Nothing was created and no `MARKER_ID` was written; the file was corrected (`{"data": <export document>}`) and the script re-run. A bench problem, not recorded as a result; the sentence is in `prepare.txt`.

**3. Precondition tolerance.** The precondition of Task 1 tolerates only ` M .planning/config.json` as a dirty path. `.planning/STATE.md` was also modified at the start (orchestrator's begin-phase step: `current_phase_name`, `last_updated`, `state_head`), treated as the orchestrator's own change as in plan 08-17 and committed with the final metadata commit; `config.json` was never staged.

**4. Pin value.** `build.txt` records the HEAD of the mount-source checkout at re-pin time (`b8232252`, a docs commit) as `sha`, as in 08-13; its `custom_components` tree equals the 08-17 tree (the check compares trees, and the stale anchor against it is empty).

**Total deviations:** 4 (2 Rule 3 bench items, 2 notes). **Impact:** none on the expectations or their outcome.

## Bench state left behind

- ha-a and ha-b running on the receiver-guard build (restarted once more after UAT-04 for the observation), mosq running (StartedAt unchanged since the 08-13 re-anchor), export off, nothing retained under `mqtt_actions_export/` or `homeassistant/device/` (`check-uat04.sh clean` PASS, `check-preflight.sh --quick` PASS, `check-stale-anchor.sh` PASS, `check-uat02.sh clean` PASS).
- `~/ha-test/.fixtures.env` holds the new `MARKER_ID` (copy before this plan: `.fixtures.env.pre-08-18`); the marker is approved on ha-b. No stray `mosquitto_sub` is running.
- Backups (outside the repo, 0700): `~/ha-test/_backup-pre-gap-rerun2-20261011T125246Z/` with `{a,b}/` (entity and device registries before the re-pin) and `reseed-20261011T131823Z/{a,b}/` (entity registries before the flip).

## Next

Plan 08-14 records the outcome (UAT-02, UAT-03, P1-5 and UAT-04 re-run PASS on the receiver-guard build; the 08-13 FAIL and the first runs stay as history) in the ledger and the traceability. UAT-02, UAT-03 and UAT-04 stay Pending in REQUIREMENTS.md here; this plan edits no ledger file.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register: T-08-53 (backups taken, only `disabled_by` of four existing records changed, validation passed, nothing fabricated), T-08-54 (the restoration restores the failing precondition and is disclosed with before and after projections and the exact state line), T-08-55 (fixed-field projections, log lines reduced to timestamp and the guard text, `check-evidence-clean.sh` PASS over the whole evidence tree and `bench-scripts/`), T-08-56 (`git diff --stat HEAD` over the eight earlier folders is empty).

## Self-Check: PASSED

- Commits `4e04ca7` and `93af345` are in the branch (`git merge-base --is-ancestor`).
- The four `-rerun2` `verdict.txt` files start with PASS; `build.txt` has `previous_sha: caf2fe5dc003ea834104f4016d1996be4132e0c8` and `first_sha: b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`; `build-caf2fe5d.txt` and `build-b7f52b34.txt` exist; `prepare.txt` holds the exact regression-state line; `runner-order.txt`, `guard-log-a.txt`, `guard-log-b.txt` and `post-restart.txt` exist.
- Plan verify commands: `check-uat04-iso.sh disposition` guard-and-document, `check-uat04.sh clean`, `check-preflight.sh --quick`, `check-stale-anchor.sh` and `check-evidence-clean.sh` PASS, earlier evidence folders untouched.
