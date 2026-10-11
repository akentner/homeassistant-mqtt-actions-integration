---
phase: 08-real-instance-verification
plan: 04
subsystem: verification-bench
tags: [uat, uat-04, discovery-export, core-prefix, mosquitto-acl, home-assistant, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: pinned bench, uat_probe user, owner tokens, 08-UAT.md ledger and recorder gate, UAT Marker fixture (plans 08-01 to 08-03)
provides:
  - UAT-04 recorded as issue (clause 1 and 3 hold, clause 2 fails for two of three devices) with a Gaps entry and a cause analysis
  - observation that one start removes the leftover core-prefix mqtt rows on both instances (research assumption A4 confirmed)
  - run-all-scripted.sh (re-run entry for UAT-02, UAT-03, P1-5, UAT-04) and check-stale-anchor.sh (D-03 gate)
  - gate-after-scripted.txt: quick preflight PASS, ACL read-back, bench clean, empty stale anchor
affects: [08-05, 08-06, 08-07, 08-08, 08-09, 08-10]
tech-stack:
  added: []
  patterns:
    - "export option driven headless through the hub options flow REST endpoints (/api/config/config_entries/options/flow)"
    - "control device with no tombstone (UAT Marker) next to devices with UAT-02 tombstones inside one run"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-04/ (16 files)
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/gate-after-scripted.txt
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "UAT-04 recorded as issue, not pass: the expectations were coded before the run and X7/X8 failed; the likely cause (core restores disabled_by from tombstones) is recorded as an inference and left for the owner to rate as product gap or bench artifact"
  - "Stored export prefix reset to the default after the run (export stays off) so the bench options do not keep homeassistant as prefix"
metrics:
  duration: about 25 min wall clock (one 20 s wait per options change, one 90 s restart margin)
  completed: 2026-10-04
status: complete
commits: 2
plan_head_before: 0cd08e124bd18a44cbae6b87a76e1fa9aee62851
plan_head_after: 935274b
actuals:
  tokens: 30000
  tasks: 2
  commits: 2
---

# Phase 8 Plan 04: UAT-04 Discovery export and core prefix, restart cleanup, scripted-group gate Summary

UAT-04 is recorded as `issue`: the export shape and its clear behave as specified, but with the export on the core prefix `homeassistant` the duplicates of Lampe Test and Bar Select were enabled `mqtt` entities on both ha-a and ha-b, not disabled ones; only the UAT Marker duplicate was disabled.

## What was done

- **Task 1 (ece75f7):** wrote `check-uat04.sh run|clean` with the expectations coded first. Added `topic readwrite mqtt_actions_export/#` to the `ha_one` and `ha_two` blocks of the bench ACL (diff in `uat-04/acl-diff.txt`, container read-back 2), SIGHUP to `mosq`. Drove the hub options flow of ha-a through the REST endpoints, each change followed by 20 s and a read-back with `uat_probe`.
  - Clause 1 (export on, default prefix): retained payload for all three owned devices; every component is `switch` or `select`, `enabled_by_default` false, no button, no `test_` key, no `/test` topic; nothing on `homeassistant/device`. PASS.
  - Clause 2 (prefix `homeassistant`, no restart, registries of ha-a and ha-b read through the WebSocket API): old prefix empty and the new topics have the same shape (PASS); UAT Marker: one `mqtt` row, `disabled_by` integration (PASS); Lampe Test and Bar Select: one `mqtt` row each but `disabled_by` null, `switch.lampe_test_2` and `select.bar_select_2`, on both instances (FAIL, X7 and X8, 6 failed expectations); native rows present and enabled everywhere (PASS).
  - Clause 3 (export off): `mqtt_actions_export/#` and `homeassistant/device/#` read back empty. PASS. Leftover after off: one disabled `mqtt` row per instance (the marker).
  - Block 4 recorded as `issue` (`severity: minor`, Gaps entry `test: 4`); `check-recorded.sh UAT-04`, `check-uat04.sh clean` and the evidence scan print PASS.
- **Task 2 (935274b):** one `podman restart ha-a ha-b`, 90 s, graceful stop, registry read, start. Both registries then held 0 `mqtt` rows, 0 `_2` ids and 34 `mqtt_actions` rows: the start removed the leftover (assumption A4 confirmed, recorded as an Observation, not a failure). Wrote `run-all-scripted.sh` (`--list`, `--dry-run`, run; never edits 08-UAT.md) and `check-stale-anchor.sh`; `gate-after-scripted.txt` records the quick preflight PASS, the ACL read-back (rows in both blocks, availability of both instance ids retained and `online`, nothing retained under the export or discovery prefix), `check-uat02.sh clean` PASS and an empty stale anchor.

## Deviations from Plan

**1. [Rule 3 - Blocking] `check-uat02.sh clean` failed the plan's own precondition.** It compared the `mqtt_actions` rows of both registries to the UAT-02 baseline, which predates the UAT Marker fixture of plan 08-03 (4 extra rows per instance: switch, mode select, two test buttons). I confirmed read-only that the diff held only marker rows, then changed `do_clean` in `~/ha-test/bin/check-uat02.sh` to exclude rows whose unique id starts with `MARKER_ID` from `.fixtures.env`. Only the `clean` mode changed; the `run` evaluation is untouched. The original is not kept in the repo (bench file).

**2. [Rule 1 - Bug] Options flow path.** The plan text names `/api/config_entries/options/flow`; like the reload endpoint of plan 08-03 the working path is `/api/config/config_entries/options/flow` (+ `/{flow_id}`). The first call used the working path, no failed attempt.

**3. Stored prefix reset.** After the off step the script submits `discovery_export` false with the default prefix, so ha-a's options no longer keep `homeassistant`. No retained message appeared because of it (checked).

**4. Plan-commit ledger.** The sandbox refuses writes to the shared git directory from the worktree, so no ledger file; `commits:` is measured as `git rev-list --count 0cd08e1..HEAD` = 2 at write time (the base is the orchestrator's, verified by `git merge-base` at start). The SUMMARY commit follows as a third.

**5. `check-stale-anchor.sh` runs `git diff` in the executing checkout, not inside the mount-source checkout.** The sandbox refuses git calls into the main checkout from a worktree and the object database is shared, so the script resolves the mount-source HEAD from its `.git` files (the `pin` function of `lib.sh`) and diffs `{recorded sha} {that HEAD}` plus `{recorded sha} {HEAD of the checkout it runs in}`. Both are empty. Exit status of git is captured first (a failing git is ABORT).

## Findings

- **UAT-04 clause 2 (issue, minor):** enabled `mqtt` duplicates for the two devices that went through the UAT-02 legacy replay. The export payload is correct (X3 passes on every device), so the enabled state does not come from the payload. HA 2026.9.4 `entity_registry.py` (lines 1498-1508) restores `disabled_by` from a deleted-entity tombstone with the same (domain, platform, unique_id); the UAT-02 twins left such tombstones with `disabled_by` null (`uat-02/twin-tombstones.txt`, entity ids `switch.lampe_test_2` and `select.bar_select_2` are reused), while the marker had none and got `integration`. This is an inference from the control and the core source, not an isolated reproduction. Open for the owner: product gap (a user who migrated from v0.1.0 and then exports on the core prefix gets enabled duplicates; a documented warning or guard would address it) or bench artifact of running UAT-02 before UAT-04 on the same instances. Phase 8 fixes nothing (D-08).
- The clear on off removed the enabled duplicates (they became tombstones again) and left the disabled one until the next start, which then removed it.
- No product code, tests or workflows changed: the stale anchor is empty.

## Bench edits (outside the repository)

- New: `~/ha-test/bin/check-uat04.sh`, `run-all-scripted.sh`, `check-stale-anchor.sh`; edited `~/ha-test/bin/check-uat02.sh` (clean mode, deviation 1); edited `~/ha-test/mosquitto/acl` (export rows for `ha_one` and `ha_two`), copy of the previous file `~/ha-test/mosquitto/acl.bak-phase8-04`.
- Bench state left behind: ha-a hub options `discovery_export` false, `export_prefix` `mqtt_actions_export` (before: no options set); export off, nothing retained under the export prefix or `homeassistant/device`; the UAT Marker fixture still in place and approved. ha-a and ha-b were restarted once (a new process lifetime), `mosq` was only sent SIGHUP (StartedAt unchanged, preflight PASS). No token value was printed, ha-ws and production hosts were not touched.

## Known Stubs

None. No product code changed.

## Threat Flags

None beyond the plan's register. T-08-11 (core-prefix duplicates in live registries) is the behavior under test and was observed, then cleaned by the restart; T-08-12 (ACL widened by one row per instance user) is on the test broker only and its diff is evidence.

## Self-Check: PASSED

- `uat-04` evidence (16 files), `00-preflight/gate-after-scripted.txt` and this SUMMARY exist; commits ece75f7 and 935274b exist on the branch.
- `check-recorded.sh UAT-04`, `check-uat04.sh clean`, `check-uat02.sh clean`, `check-preflight.sh --quick`, `check-stale-anchor.sh`, `run-all-scripted.sh --list` and `--dry-run`, and `check-evidence-clean.sh` over `08-evidence` all print PASS or exit 0.
