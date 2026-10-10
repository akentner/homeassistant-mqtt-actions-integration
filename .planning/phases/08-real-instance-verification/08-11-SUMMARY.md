---
phase: 08-real-instance-verification
plan: 11
subsystem: verification-gap-closure
tags: [uat-04, isolation, tombstone, entity-registry, owner-decision, bench-scripts]
requires:
  - phase: 08-real-instance-verification
    provides: UAT-04 clause 2 recorded as a gap (plan 08-04), bench scripts and evidence tree (plans 08-01 to 08-10)
provides:
  - observed classification TOMBSTONE-ONLY of the UAT-04 clause 2 failure, from a controlled pair of fresh devices on two real instances
  - owner decision UAT04-GAP-DISPOSITION guard-and-document, full-rerun, not-affected confirmed, in the ledger and in disposition.txt
  - check-uat04-iso.sh with modes disposition and applies (fail closed) for plans 08-12 to 08-15
  - Gaps entry for test 4 with the observed root cause instead of the inference
affects: [08-12, 08-13, 08-14, 08-15]
tech-stack:
  added: []
  patterns:
    - "expectations and classification rules coded in a script header before the first run, header sha256 written into the result (D-08)"
    - "fail-closed disposition file read by downstream plans (exit 2 on a missing or invalid file)"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-04-isolation/ (21 evidence files)
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/check-uat04-iso.sh
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
    - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/bench-scripts/check-uat02.sh
decisions:
  - "UAT04-GAP-DISPOSITION: guard-and-document with modifier full-rerun; UAT-01, P2-2 and the owner-judged frontend items (P1-1 to P1-4, P1-6, P2-1, P3-1, P3-2) confirmed not affected by the owner (2026-10-10)"
  - "Classification TOMBSTONE-ONLY: a fresh id is exported disabled, an id with a null-disabled_by mqtt tombstone is exported enabled, on both instances"
metrics:
  completed: 2026-10-10
status: complete
commits: 4
plan_head_before: 9ea21b53969d27395fb123f81dde10fcb532d9e8
plan_head_after: 6941377f5c4e1ff251cfcd7a40965dd318d797dd
actuals:
  tokens: 33000
  tasks: 3
  commits: 4
---

# Phase 8 Plan 11: isolated reproduction of UAT-04 clause 2 and owner decision Summary

UAT-04 clause 2 is classified TOMBSTONE-ONLY from observed values: on the core prefix a fresh device id got one disabled mqtt duplicate on both instances, a device id with a real null-`disabled_by` tombstone got one enabled duplicate on both instances, and the owner chose guard-and-document with the full scripted re-run.

## What was done

- **Task 1, tracer (842ba7d):** the clean arm end to end (one fresh inert switch `UAT Iso Clean`, export on the core prefix `homeassistant` without a restart, both live registries read through `config/entity_registry/list`, export off with the empty read-back, owner delete, one restart, three gates PASS). Result CLEAN-ARM-DISABLED. The expectations were coded in the script header before the run.
- **Task 2, expansion (895bac0):** two fresh devices exported in one window. ISO-TWIN was given a real tombstone through the UAT-02 field path (retained legacy Discovery built with the repository's `build_discovery`, replayed at start, the replay catch removes the enabled legacy twin). Tombstone proof T1 to T3 read from the flushed registry files of both instances before the export. Per instance and arm:
  - ISO-CLEAN, ha-a and ha-b: one mqtt row, `disabled_by` integration, no tombstone before the export
  - ISO-TWIN, ha-a and ha-b: one mqtt row, `disabled_by` null (enabled), tombstone present with null
  - Lampe Test and Bar Select read enabled and the UAT Marker disabled, as predicted
  - classification TOMBSTONE-ONLY; header sha256 `da30841ec8c1c9532ea50ee8824c0792e8d29877fc5ec6d962a36925723f8288` in `result.txt`; bench back at baseline (`check-uat02.sh clean`, `check-uat04.sh clean`, `check-preflight.sh --quick`, `check-stale-anchor.sh` PASS)
- **Task 3, owner decision (6941377):** the owner answered `guard-and-document, confirm-not-affected` (no `scoped`, so the re-run modifier is `full-rerun`). Recorded verbatim in `08-evidence/uat-04-isolation/disposition.txt` and as the Owner decisions row `UAT04-GAP-DISPOSITION` in `08-UAT.md`. The script gained the modes `disposition` and `applies TARGET` (exit 2 on a missing or invalid file; `check-uat04-iso.sh applies` prints guard yes, document yes, repin yes, full-rerun yes, prune no, scoped no). The Gaps entry for test 4 carries the observed root cause and `debug_session`, `status: failed` and block 4 are untouched. Observations, Bench state left behind and Owner follow-ups item 1 are updated.
- **Pre-task commit 47b2bf6 (Rule 3, below):** fix of the `check-uat02.sh clean` hub-row comparison.

## Deviations from Plan

**1. [Rule 3 - Blocking] `check-uat02.sh clean` compared ha-b's hub rows against a stale baseline.** Since plan 08-08 re-added the hub of ha-b under a new config entry id, `do_clean` compared the hub-owned rows (`{hub entry id}_resync`, `_instance_mode`, `_roster`) with `uat-02/baseline-b.json`, which still holds the old hub's rows, and failed although nothing else had moved. The precondition of Task 1 could not be met. Fix, bench script only: the comparison now ignores the three hub-owned unique id suffixes; E1 to E3 unchanged, baseline file not edited. Authorized by the owner in chat. Commit 47b2bf6; the same fix is used by plan 08-13.

**2. [Rule 3 - Blocking] Mirror detection through the registry, not a subentry.** The plan text says the mirror "exists on ha-b"; a mirror is an entity, not a config subentry, so `wait_mirror` and `mirror_present` look for a registry row of platform `mqtt_actions` on ha-b with the fixture's unique id. Planner clarification applied with it: the native row is judged on ha-a only (the mirror on ha-b is never approved); ha-b is judged on the mqtt rows.

**3. [Rule 3 - Blocking] Restart before the owner delete in the cleanup.** The plan lists delete, then restart. The disabled leftover export row is removed at the next start only while its device still has the native twin (research Pitfall 4), so deleting first would leave a leftover that the restart no longer removes and `check-uat04.sh clean` would fail. `cleanup_round` therefore restarts first, then deletes and asserts topics and mirrors. Both orderings end at the same baseline; recorded in the Observations.

**Aborted attempts.** Two earlier attempts of the bench construction were aborted before a result (bench problem, never recorded); they left tombstones for the unique ids `e8a6edf6-45ba-43c8-b171-88ca668c31f2` (mqtt, integration) and `51c0db03-84d3-434a-b2d5-1ec4f110ff41` (only `mqtt_actions` tombstones). Both are listed in Bench state left behind.

## Findings for the follow-up plans

- Plan 08-12 implements the guard. The evidence shows exactly the case it must cover: an mqtt-platform row of an exported device id with `disabled_by` null on the core prefix. Regression state on the live bench: Lampe Test and Bar Select (null tombstones, still present in both registries), plus the retired `020b9715-...` tombstones; a fresh id (ISO-CLEAN) must stay untouched.
- The replay catch produced the null tombstone itself in the field path (enabled legacy twin removed with `async_remove` stores `disabled_by` null). This is the MIG-05 scenario, so the affected users are real, not a bench artifact.
- Catch asymmetry again: the INFO line "Removed 3 duplicate entities…" appeared on ha-b only (ha-a 0, ha-b 1) although both registries held the same tombstones (verification finding 5, still unexplained).
- The scripted re-run uses `check-uat04-iso.sh applies full-rerun` (yes); `prune` reads no, so no tombstone pruning is planned.
- The 999.1 relabel remark in the owner's reply concerns the ROADMAP backlog and is not handled here (orchestrator).

## Known Stubs

None. No product, test or workflow file changed (stale anchor empty, build `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`).

## Threat Flags

None. All evidence went through `check-evidence-clean.sh`; registry projections are limited to the fixed fields of the plan.

## Requirements

UAT-04 stays Pending: clause 2 is open until the guard is built and UAT-04 is re-run and recorded (plans 08-12 to 08-14).

## Self-Check: PASSED

- `check-uat04-iso.sh verify` PASS (TOMBSTONE-ONLY); `check-uat04-iso.sh disposition` prints guard-and-document; `check-recorded.sh --all` PASS (14 checks); `check-evidence-clean.sh` over `08-evidence` PASS; `check-stale-anchor.sh` PASS.
- Commits 47b2bf6, 842ba7d, 895bac0 and 6941377 are in the branch; `disposition.txt`, `classification.txt` and the bench-script copy exist.
