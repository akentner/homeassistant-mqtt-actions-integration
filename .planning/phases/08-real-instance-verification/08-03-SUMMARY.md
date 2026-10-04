---
phase: 08-real-instance-verification
plan: 03
subsystem: verification-bench
tags: [uat, uat-03, p1-5, exactly-once, retained-vs-live, home-assistant, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: pinned bench, uat_probe and uat_bridge users, owner tokens, 08-UAT.md ledger and recorder gate (plans 08-01, 08-02)
provides:
  - UAT-03 recorded as pass (command across two real instances, unapproved control, unknown payload)
  - P1-5 recorded as pass (replayed state runs no action after a full restart and a core MQTT entry reload)
  - the "UAT Marker" fixture (countable, inert, approved on ha-b) reusable by plans 08-04 and 08-05
  - check-marker.sh, check-uat03.sh, check-p15.sh, setup-marker.sh in ~/ha-test/bin with the expectations coded before observation
affects: [08-04, 08-05, 08-06, 08-07, 08-08, 08-09, 08-10]
tech-stack:
  added: []
  patterns:
    - "exactly-once measured as a per-instance log-line delta inside one process lifetime, with a wait after each trigger"
    - "negative control (unapproved mirror, delta 0) and positive control (live change, delta +1) in the same run"
    - "headless approval of a mirrored device through the Repairs fix flow API"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-03/ (11 files)
    - .planning/phases/08-real-instance-verification/08-evidence/p1-5/ (6 files)
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "Marker device created through import_devices (scriptable, new uuid, inert system_log.write actions)"
  - "P1-5 toggle is the switch service call; its direction follows the current state so it is a real edge"
metrics:
  duration: about 45 min wall clock (three 60 s waits plus a 90 s restart margin per P1-5 run, two P1-5 runs)
  completed: 2026-10-04
status: complete
commits: 3
plan_head_before: f116455c28da683604b1142033f74c9dec855f82
plan_head_after: 35b5f8eda9b9b399cdd8f499f42b5106a339a8f1
actuals:
  tokens: 45000
  tasks: 3
  commits: 3
---

# Phase 8 Plan 03: UAT-03 command across two instances and P1-5 retained-versus-live Summary

UAT-03 and P1-5 both pass at the pinned build: a command on either instance runs the marker actions exactly once on every approved instance (0 on the unapproved one), an unknown payload is ignored on both with the state and the retained broker value unchanged, and retained state replayed by a full restart or a core MQTT entry reload runs no action while a following live change runs once per instance.

## What was done

- **Task 1 (9100348):** read the content shape of "Lampe Test" from `export_devices` (`uat-03/export-shape.json`), imported a Switch "UAT Marker" on ha-a through `import_devices` (actions: `system_log.write` at warning, `UAT03-MARKER on` / `UAT03-MARKER off`; startup flag off). Marker uuid `81d53f84-469e-4937-a3bb-09b24f11e4e4`, entity `switch.uat_marker` on both instances; the mirror on ha-b raised the approval Repairs issue. `check-marker.sh pending` PASS.
- **Task 2 (a716e15):** `check-uat03.sh run`. A (unapproved control, command on ha-a): ha-a +1, ha-b 0. Approval of the mirror through the Repairs fix flow API. B (command on ha-a): +1 on both. C (command on the ha-b mirror): +1 on both. D (`banana`, QoS 1, not retained, as `uat_bridge`): marker deltas 0, `Ignoring unknown payload` +1 on each instance, entity state unchanged on both, retained value `ON` read back unchanged. 60 s after each command, 30 s after D. Block 3 recorded as pass.
- **Task 3 (35b5f8e):** `check-p15.sh run`. Precondition: `run_on_startup` false in the retained config document. 1 toggle +1/+1; 2 `podman restart ha-a ha-b`, new lifetime, 0/0; 3 reload of the core `mqtt` entry on both, 0/0; 4 positive control +1/+1. `mosq` StartedAt unchanged. Block 9 recorded as pass.

## Deviations from Plan

**1. [Rule 1 - Bug] Reload endpoint of research assumption A5.** `POST /api/config_entries/entry/{id}/reload` answers 404 on HA 2026.9.4; the working path is `POST /api/config/config_entries/entry/{id}/reload`. The first P1-5 run aborted there (ABORT, never a result) after toggle and restart; the script was corrected and the whole check re-run from the start. The recorded evidence is the second, complete run. Recorded as an Observation in 08-UAT.md.

**2. [Rule 1 - Bug] Two bench-script defects in `check-p15.sh`, found by the first runs (before any outcome was observed):** the jq fallback `// "missing"` treats the value `false` as absent (fixed with an explicit null test), and the toggle direction was hard coded although the second run started with the marker already off (a service call to the state it already has is no edge). The direction now follows the current state and step 4 flips it back. Expected values were not changed.

**3. Fallbacks not needed.** The Repairs fix flow API worked as assumed (start returns the form, a submit of `{}` returns `create_entry`), so no browser MCP or human-action checkpoint was used.

**4. Not-retained proof.** A subscriber receives every live message with retain flag 0, so `topic-capture.txt` showing `retain=0` for `banana` is weak on its own. The real proof is the retained read-back: `1 ON` before and after D (`states-before.json`, `states-after.json`).

**4b. Orphaned capture process.** The background `mosquitto_sub` of `check-uat03.sh` survived the script (the kill hit the wrapper function, not the child) and kept appending to `topic-capture.txt` during P1-5. I killed the orphan, removed its temporary options file and restored the committed capture, so `topic-capture.txt` shows only the UAT-03 run. Bench-script defect to fix in `lib.sh`/`check-uat03.sh` if the script is reused or published in plan 08-10.

**5. Plan-commit ledger.** The sandbox refuses writes to the shared git directory from this worktree, so the `gsd-plan-head-before-08-03` ledger file could not be written; `commits:` was measured as `git rev-list --count f116455..HEAD` = 3 (the base given by the orchestrator, verified by `git merge-base` at start). The SUMMARY commit follows as a fourth.

## Findings

- No product defect observed: no Gaps entry, both blocks are `pass`.
- Exactly-once holds including the owner echo: ha-a runs the actions once per command although it receives its own state message back.
- The unknown payload does not reach the recorded value of either instance (the entity stays `on`).

## Bench edits (outside the repository)

- New: `~/ha-test/bin/check-marker.sh`, `check-uat03.sh`, `check-p15.sh`, `setup-marker.sh`; `~/ha-test/.fixtures.env` (`MARKER_ID`, not a secret).
- Bench state left behind: the "UAT Marker" device on ha-a (owner) and its approved mirror on ha-b, left approved for plans 08-04 and 08-05; its entity is currently `off`. It is retained on the broker (`mqtt_actions/v1/devices/81d53f84-469e-4937-a3bb-09b24f11e4e4/*`) and should be removed at phase end (plan 08-10).
- Both instances restarted during P1-5 (two process lifetimes, the first run included); `mosq` was not restarted, no token value was printed, ha-ws and production hosts were not touched. `git status --porcelain -- custom_components tests .github` is empty.

## Known Stubs

None. No product code changed.

## Threat Flags

None beyond the plan's register. T-08-08: the marker actions are inert (`system_log.write` only). T-08-09: `banana` was not retained and the retained value was read back unchanged. T-08-10: `mosq` StartedAt unchanged (`p1-5/result.txt`).

## Self-Check: PASSED

- Evidence folders `uat-03` (11 files) and `p1-5` (6 files) and this SUMMARY exist and are committed; commits 9100348, a716e15, 35b5f8e exist on the branch.
- `check-recorded.sh UAT-03`, `check-recorded.sh P1-5`, `check-marker.sh approved`, `check-evidence-clean.sh` and `check-preflight.sh --quick` print PASS.
