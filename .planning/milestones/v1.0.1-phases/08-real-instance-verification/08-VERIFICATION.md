---
phase: 08-real-instance-verification
verified: 2026-10-11T13:52:00Z
status: passed
score: 6/6 must-haves verified
covered_files:
  - .planning/phases/08-real-instance-verification/08-01-PLAN.md
  - .planning/phases/08-real-instance-verification/08-01-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-02-PLAN.md
  - .planning/phases/08-real-instance-verification/08-02-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-03-PLAN.md
  - .planning/phases/08-real-instance-verification/08-03-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-04-PLAN.md
  - .planning/phases/08-real-instance-verification/08-04-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-05-PLAN.md
  - .planning/phases/08-real-instance-verification/08-05-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-06-PLAN.md
  - .planning/phases/08-real-instance-verification/08-06-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-07-PLAN.md
  - .planning/phases/08-real-instance-verification/08-07-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-08-PLAN.md
  - .planning/phases/08-real-instance-verification/08-08-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-09-PLAN.md
  - .planning/phases/08-real-instance-verification/08-09-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-10-PLAN.md
  - .planning/phases/08-real-instance-verification/08-10-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-11-PLAN.md
  - .planning/phases/08-real-instance-verification/08-11-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-12-PLAN.md
  - .planning/phases/08-real-instance-verification/08-12-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-13-PLAN.md
  - .planning/phases/08-real-instance-verification/08-13-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-14-PLAN.md
  - .planning/phases/08-real-instance-verification/08-14-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-15-PLAN.md
  - .planning/phases/08-real-instance-verification/08-15-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-16-PLAN.md
  - .planning/phases/08-real-instance-verification/08-16-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-17-PLAN.md
  - .planning/phases/08-real-instance-verification/08-17-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-18-PLAN.md
  - .planning/phases/08-real-instance-verification/08-18-SUMMARY.md
  - .planning/phases/08-real-instance-verification/08-UAT.md
  - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/build.txt
  - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/stale-anchor-final.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-1/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-3/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-4/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-5-rerun2/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-01/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-01/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-02-rerun2/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-02/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-02/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-03-rerun2/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-03/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-03/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-isolation/classification.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-isolation/disposition.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-receiver-guard/decision.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun2/prepare.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun2/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04-rerun2/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04/tombstone-cause.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04/verdict.txt
covered_digest: "v3:sha256:7cc16feff1ab4b435d0f4170dbfce1c2be475a91b3b367cfea03bef1ec3eed06"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "ROADMAP criterion 4, second clause (UAT-04): the core MQTT prefix yields only disabled duplicates"
  gaps_remaining: []
  regressions: []
---

# Phase 8: Real-Instance Verification Verification Report

**Phase Goal:** The Phase 5 UAT debt is closed: the four checks the owner skipped in v1.0 are run by hand on real instances against the v1.0.1 build, and each result is recorded with its evidence. This is a manual verification phase (ha-one and ha-two, or the production instances); no code changes are planned, and a failed check becomes a gap, not an accepted skip. The exception is the gap closure of UAT-04 clause 2, which may include a product fix by owner decisions D08-WAIVER of 2026-10-08 and UAT04-RECEIVER-GUARD of 2026-10-11 (the receiver-side extension of the guard, plans 08-16 to 08-18); every other check stays manual verification without code changes.
**Verified:** 2026-10-11T13:52:00Z
**Status:** passed
**Re-verification:** Yes, after gap closure (previous report 2026-10-08: `gaps_found`, 5/6); refreshed 2026-10-11T13:52:00Z because `08-15-SUMMARY.md` joined the covered files, no verdict changed (HEAD 797a708 differs from 36d8f95 only in STATE.md and 08-15-SUMMARY.md)

## Goal Achievement

All four UAT checks have a recorded result with evidence, and all four are `pass` in the final ledger (`08-UAT.md`, 14 of 14 blocks pass, no block is `issue`). The one gap of the previous report (UAT-04 clause 2) is closed by evidence, not by an override: the first run (`uat-04`) failed, the re-run of plan 08-13 on the first guard build failed on ha-b (`uat-04-rerun`, kept as history), and the final re-run of plan 08-18 on the receiver-guard build passes on both instances (`uat-04-rerun2`). No FAIL was turned into a pass and no override was invented. The verifier re-read the verdicts, the registry projections, the guard code and ran the guard tests itself.

### Build under test

| Check | Result |
| ----- | ------ |
| Recorded build | `b8232252540a55969145ca0034d8fd86b4be3b7c` (`00-preflight/build.txt`; `previous_sha` `caf2fe5dc003ea834104f4016d1996be4132e0c8`, the guard of plan 08-12 on the exporting instance only; `first_sha` `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3`). Read-only bind mount of `custom_components/mqtt_actions`, HA 2026.9.4 on ha-a and ha-b, `repin_reason` receiver-side guard of plan 08-17 |
| Stale anchor | `git diff --stat b8232252 HEAD -- custom_components tests .github pyproject.toml uv.lock` is empty (re-run by the verifier). `stale-anchor-final.txt` records `stale: no` and the PASS line. No recorded check on the final build is stale |
| Product change in Phase 8 | Allowed and bounded by the owner waivers D08-WAIVER and UAT04-RECEIVER-GUARD. `git diff --stat b7f52b34 HEAD -- custom_components tests .github` names four files: `manager.py` (+82), `takeover.py` (+34), `tests/test_discovery_export.py` (+200), `tests/test_export_guard_receiver.py` (+474). `git log --grep='(08-' -- custom_components tests .github pyproject.toml uv.lock` lists exactly the seven TDD commits of plans 08-12 and 08-17 (tests first, then fixes). No other code, workflow or manifest file changed |
| "v1.0.1 build" | There is no `v1.0.1` tag; the build is the unreleased Phase 6 and 7 code plus the Phase 8 guard, as in the ROADMAP use of the term |

### Observable Truths (ROADMAP success criteria, the contract)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | SC1 / UAT-01: with a v0.1.0 instance next to a native instance, the v0.1.0 instance keeps running its actions for the migrated devices, shows no entities for them and raises no error | VERIFIED | Unchanged from the previous report: `uat-01/verdict.txt` PASS on the first pin `b7f52b34`. Marker commands gave delta exactly +1 on ha-a, ha-b and ha-c, ha-c registry holds no `mqtt` row and no switch or button of `mqtt_actions` for a migrated device, no ERROR or CRITICAL. "Shows no entities" holds under the owner wording UAT01-WORDING (the seven v0.1.0 companion mode selects are an observation, not counted). Not re-run on the receiver-guard build: the owner confirmed it as not affected (UAT04-GAP-DISPOSITION, UAT04-RECEIVER-GUARD) because the guard only acts on a core MQTT row of a native id, which UAT-01 never creates; the product diff against the first pin is limited to `manager.py` and `takeover.py`. See Evidence strength |
| 2 | SC2 / UAT-02: after re-publishing retained legacy Discovery and restarting twice, no `_2` duplicate entities exist, proving MIG-05 outside the test harness | VERIFIED | Re-run on the final build: `uat-02-rerun2/verdict.txt` PASS, build `b8232252`, E1 to E4 hold in round 1 and round 2 on ha-a and ha-b. First run (`uat-02`, b7f52b34) and the 08-13 re-run (`uat-02-rerun`) are superseded history. Limits carried: the live variant is an owner-accepted limit (WR03-LIVE-REPLAY, no gap); on the first run ha-a was cleaned without the catch log line that ha-b shows (mechanism unidentified, outcome identical) |
| 3 | SC3 / UAT-03: a command on one of two real instances runs the actions exactly once on every approved instance; an unknown payload is ignored and leaves the state unchanged | VERIFIED | Re-run on the final build with a fresh marker: `uat-03-rerun2/verdict.txt` PASS, steps A (unapproved control +1 / 0), B, C (+1 and +1 each) and D (`banana`: delta 0, "Ignoring unknown payload" +1 each, state and retained value unchanged) hold on both instances. First run and 08-13 re-run are history |
| 4 | SC4 / UAT-04: the Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics | VERIFIED | `uat-04-rerun2/verdict.txt` PASS and `result.txt`: clause 1 (X1 to X6) holds on the default prefix; clause 2 holds on BOTH instances with the core prefix and no restart (X7: exactly one `mqtt` row per exported device with `disabled_by` integration for Lampe Test, Bar Select and the marker; X8: no enabled `mqtt` row on ha-a or ha-b; X9: native rows present and enabled); clause 3 holds (X10: nothing retained under `mqtt_actions_export/` or `homeassistant/device/` after off). The verifier re-read `registry-core-prefix-a.json` and `-b.json`: all three `mqtt` rows per instance read `disabled_by` integration. **The pass was observed on the original tombstoned state with the receiver-guard build** (the failing state of the first run: `disabled_by` null tombstones for the Lampe Test switch and the Bar Select select on both instances, see below), not on a pruned registry state, so no pruned-state qualifier applies (disposition `guard-and-document`, no prune). The options flow was applied on ha-a only, so ha-b only received the export, which is the case that failed in the 08-13 re-run. Guard log: two INFO lines "Disabled 1 duplicate entities that core MQTT created for native devices" on each instance (`guard-log-a.txt`, `guard-log-b.txt`). After one graceful restart both instances hold 0 live `mqtt` rows (`post-restart.txt`). Behavior-dependent, so also checked by tests: `tests/test_export_guard_receiver.py` (14 passed) and `tests/test_discovery_export.py` (28 passed), run by the verifier |
| 5 | SC5: each of the four checks has a recorded pass or fail result with evidence, and any failure is raised as a gap for follow-up work | VERIFIED | `08-UAT.md` blocks 1 to 4 carry `result: pass`, a 40-hex sha, a date and an existing evidence folder; the earlier failure was raised as a Gaps entry (`test: 4`) and followed up (plans 08-11 to 08-18). The entry now has `status: resolved` plus a `resolution:` line naming the evidence (`uat-04-rerun2`), the build and the date; no `skipped` token is used. The failed runs stay in the record (`uat-04`, `uat-04-isolation`, `uat-04-rerun`) |
| 6 | SC6: the ten human items of Phases 1 to 3 each have a recorded pass or fail result on the final build, so the archived reports can be refreshed to `passed` (or accepted as owner overrides) | VERIFIED (with evidence-strength limits, see below) | Blocks 5 to 14 are all `result: pass` (block 5 with `override_by: Alexander Kentner` on the abbreviated PROD-HOST path). P1-5 (block 9) was re-run on the final build (`p1-5-rerun2/verdict.txt` PASS: toggle +1, restart 0, mqtt entry reload 0, positive control +1 on both instances). The other nine stay on their recorded evidence at the first pin or the release tag; the owner confirmed them as not affected by the guard in his own name (UAT04-GAP-DISPOSITION 2026-10-10, UAT04-RECEIVER-GUARD 2026-10-11, `uat-04-receiver-guard/decision.txt`: `not-affected-confirmed: yes`, `checks-to-widen: none`). The archived Phase 1 to 4 reports were regenerated by their own verifier runs in plan 08-15 Task 2; the verifier re-read `verification status` of all four on this re-run and each reads `passed`. They are not part of this report's digest |

**Score:** 6/6 truths verified. Behavior-unverified truths: 0 (the guard behavior has both real-instance runs and 42 passing unit tests; the owner-judged items are listed under Evidence strength because the phase's deliverable is the recorded owner judgement).

### UAT-04 gap closure (the one open item of the previous report)

| Step | Build | Result | Evidence |
| ---- | ----- | ------ | -------- |
| First run | `b7f52b34` | FAIL clause 2 (X7, X8) on ha-a and ha-b: Lampe Test and Bar Select got ENABLED `mqtt` rows | `uat-04/verdict.txt`, `tombstone-cause.txt` (history) |
| Isolation | `b7f52b34` | TOMBSTONE-ONLY: clean id disabled, tombstoned id enabled, on both instances; owner disposition `guard-and-document`, modifier `full-rerun` | `uat-04-isolation/classification.txt`, `disposition.txt` |
| Re-run of plan 08-13 | `caf2fe5d` (guard armed on the exporting instance only) | FAIL on ha-b (X7 for Lampe Test and Bar Select, X8 two enabled rows); ha-a passed | `uat-04-rerun/verdict.txt`, `result.txt` (history, not edited) |
| Owner decision | n/a | UAT04-RECEIVER-GUARD `extend-and-confirm` (2026-10-11), failure rule of D-08 stands | `uat-04-receiver-guard/decision.txt` |
| Guard on every native instance | `b8232252` | `Manager._arm_duplicate_guard()` is called in the start sequence (`manager.py:808`), disarmed on stop (`manager.py:1231`); listens to registry `create` events, and `takeover.disable_duplicates` disables only a switch or select `mqtt` row of the device whose unique id equals the device id, is enabled and has a native twin under this config entry; nothing is removed, published or enabled | `custom_components/mqtt_actions/manager.py`, `takeover.py` |
| Final re-run | `b8232252` | PASS X1 to X10 on both instances | `uat-04-rerun2/verdict.txt`, `result.txt`, `prepare.txt` |

State of the final re-run, stated exactly: the UAT-02 replay on the receiver-guard build turns the null tombstones of Lampe Test and Bar Select into `disabled_by` integration (the guard disables a replayed row before the catch removes it). Plan 08-18 therefore restored the original failing tombstone state before UAT-04 by flipping `disabled_by` back to null on four existing registry records (both instances stopped, backups taken, file validation passed, nothing fabricated; `uat-04-rerun2/prepare.txt`), and proved it with the line "regression state before UAT-04: ha-a null tombstones switch=1 select=1; ha-b null tombstones switch=1 select=1; live mqtt rows a=0 b=0". UAT-04 passed from that state. This is a bench-prepared state that equals the failing state of the first run; it is not a pruned state and not a clean state.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ------------ | ----------- | ------ | -------- |
| UAT-01 | 08-01, 08-05, 08-14, 08-15 and the ten-item plans | v0.1.0 instance keeps running actions, no entities for migrated devices, no error | SATISFIED (under owner wording UAT01-WORDING; first pin, owner-confirmed not affected) | block 1, `uat-01/` |
| UAT-02 | 08-02, 08-17, 08-18, 08-14, 08-15 | Retained legacy Discovery plus two restarts yields no `_2` duplicates (proves MIG-05) | SATISFIED | block 2, `uat-02-rerun2/` |
| UAT-03 | 08-03, 08-18, 08-14, 08-15 | Command runs actions exactly once on every approved instance; unknown payload ignored | SATISFIED | block 3, `uat-03-rerun2/` |
| UAT-04 | 08-04, 08-11 to 08-14, 08-16 to 08-18, 08-15 | Export has `enabled_by_default` false and no buttons, core prefix yields only disabled duplicates, off clears topics | SATISFIED (all three clauses; clause 2 observed on the original tombstoned state with the receiver-guard build, no pruned-state qualifier) | block 4, `uat-04-rerun2/`; Gaps entry test 4 `resolved` |

Cross-reference: UAT-01 to UAT-04 are the only requirement ids mapped to Phase 8 in REQUIREMENTS.md, all four read `Complete` there and agree with the ledger verdicts; no orphaned requirement and no plan claims an id that is not mapped.

### Evidence strength of the ten items (SC6) and of the scripted checks

Stated so the pass marks are not read stronger than the evidence (unchanged from the previous report except the two rows marked new):

| Item | Evidence | Limit |
| ---- | -------- | ----- |
| UAT-01 (new) | first pin only | Not re-run on the receiver-guard build; owner-confirmed not affected on the argument that the guard triggers only on a core MQTT row of a native id. That is an owner judgement, not a test of this build; the product diff against the first pin is `manager.py` and `takeover.py` |
| UAT-04 (new) | `uat-04-rerun2/` | The failing tombstone state was restored by editing four registry records between runs (see above); the guard behavior is additionally pinned by unit tests |
| P1-1 (HACS client install) | `p1-1/` | Abbreviated host-with-integration path on production host 1; first add and both removals not run; recorded as pass with an override in the owner's own name (Alexander Kentner, 2026-10-07); it verifies the released `v1.0.0`, not the bench build |
| P1-2 (EN/DE strings) | 8 screenshots plus `p3-1/01..06` | Strongest owner item; orchestrator drove the browser, owner judged |
| P1-3, P1-4, P3-2 | owner statement "approved P1-3 P1-4 P3-2" | Chat statements, no screenshots; clearing of the P1-4 issue rests on a unit test |
| P1-5 (retained vs live) | `p1-5-rerun2/` | Fully scripted, re-run on the final build; the toggle is the service call, the broker reconnect is a reload of the core `mqtt` entry, the Mosquitto container was not restarted |
| P1-6 (core version) | owner statement "2026.9.4" | Informational; Claude did not connect to the host |
| P2-1, P2-2 | owner statement "Vollständig, ok" per item | Two-step approval after "not checked" answers; no screenshots; P2-2 breaker loop scripted PASS plus owner-judged Repairs card |
| P3-1 | 6 screenshots | Orchestrator drove the browser, owner judged |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `08-UAT.md` | 14 blocks, 14 pass, Gaps resolved, Owner decisions, Bench state | VERIFIED | Counts re-read: blocks 1 to 14 all `pass`, summary `passed: 14, issues: 0`, requirement verdict table equals the blocks, Gaps entry `status: resolved` with `resolution:`, frontmatter `status: complete` |
| `08-evidence/00-preflight/build.txt`, `stale-anchor-final.txt` | re-pinned build, empty stale anchor | VERIFIED | build sha `b8232252`, `previous_sha`, `first_sha`; anchor re-run by the verifier is empty; `check-final.sh --pre` PASS |
| `08-evidence/uat-04-rerun2/`, `uat-02-rerun2/`, `uat-03-rerun2/`, `p1-5-rerun2/` | verdict and result of the final re-run | VERIFIED | each holds a PASS `verdict.txt` that agrees with the ledger |
| `08-evidence/uat-04/`, `uat-04-isolation/`, `uat-04-rerun/`, `uat-04-receiver-guard/` | first failing run, isolation, failed 08-13 re-run, owner decision | VERIFIED | present, tracked, kept as history |
| Guard implementation and tests | receiver-side guard, TDD | VERIFIED | `manager.py` and `takeover.py` as described; two test files, 14 and 28 tests passed when run by the verifier |
| Bench script copy and evidence tree | secret-free | VERIFIED | `check-final.sh --pre` runs `check-evidence-clean.sh` over the script copy and the whole tree: PASS |
| Archived Phase 1 to 4 reports | current | NOT PART OF THIS DIGEST | regenerated by the verifier runs of plan 08-15 Task 2; `verification status` of Phases 1 to 4 reads `passed` (re-read on this run) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| ledger block N | evidence folder | `evidence:` field | WIRED | every block's folder exists and is tracked |
| ledger Gaps entry `test: 4` | block 4 | gaps rule of `check-final.sh` | WIRED | `status: resolved`, block 4 is `pass`, `resolution:` line present; no issue block remains |
| `Manager` start | `takeover.disable_duplicates` | `_arm_duplicate_guard` (`manager.py:808`), registry `create` listener, `_disable_duplicates` | WIRED | armed on every native instance independent of its own export option; disarmed at `manager.py:1231` |
| final re-run | recorded build | `build.txt` mount hashes (`prepare.txt`: `manager.py`, `takeover.py` host equals container, both instances) | WIRED | the mount is byte-identical to the tree of the recorded sha |
| UAT-04 failure history | follow-up work | D-08, plans 08-11 to 08-18 | WIRED | the failure was followed up and closed on evidence; the 08-13 FAIL is kept |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Receiver-side guard | `uv run pytest tests/test_export_guard_receiver.py -q` | 14 passed | PASS |
| Export and guard on the exporting instance | `uv run pytest tests/test_discovery_export.py -q` | 28 passed | PASS |
| Stale anchor | `git diff --stat b8232252 HEAD -- custom_components tests .github pyproject.toml uv.lock` | empty | PASS |
| Ledger and anchor gate | `~/ha-test/bin/check-final.sh --pre` | PASS (re-run on this re-verification; Phase 1 to 4 reports read `passed`, Phase 8 `stale` until this report is regenerated) | PASS |
| UAT-04 pass is real | read `uat-04-rerun2/verdict.txt`, `result.txt`, `registry-core-prefix-{a,b}.json` | X7 and X8 PASS on both instances; three `mqtt` rows per instance all `disabled_by` integration | CONFIRMED PASS |
| Earlier failures remain history | read `uat-04/verdict.txt`, `uat-04-rerun/verdict.txt` | both FAIL, untouched | CONFIRMED |

The live bench (`~/ha-test`, containers) was not re-run by the verifier; the scripted results are read from the committed evidence. The full test suite was not re-run (only the two named files above).

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` is declared or exists for this phase; SKIPPED.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| none | - | TBD, FIXME or XXX in the guard code, its tests, `08-UAT.md`, the summaries of plans 08-11 to 08-18 or the final evidence | - | none found; no empty handler or static return in the guard path |

### Advisory (New Scope, Unevidenced)

None.

### Findings the owner should see

1. UAT-04 clause 2 is closed on evidence: the failing case of the 08-13 re-run (ha-b as a receiver, null tombstones) now passes with the original expectations X1 to X10, and the exporting instance also passes. The pass is on the failing tombstone state, which plan 08-18 had to restore by hand-editing four registry records after the UAT-02 replay changed them; this is documented in the ledger and `prepare.txt`.
2. On the final build the UAT-02 replay itself turns the tombstones of Lampe Test and Bar Select to `disabled_by` integration, so on this build a user who replays legacy Discovery and then exports on the core prefix is protected twice (the replay and the guard).
3. UAT-01 and nine of the ten human items were not re-run on the receiver-guard build; they rest on the owner's confirmation of "not affected". P1-1 is an abbreviated path with an owner override in the owner's own name and verifies the released `v1.0.0`.
4. Five items (P1-3, P1-4, P2-1, P2-2, P3-2) pass on chat statements without screenshots.
5. The catch asymmetry (ha-b logs "Removed 3 duplicate entities", ha-a does not, same clean outcome) is still unexplained; it is an observation, not a gap.
6. A bench defect found by plan 08-18: `check-uat03.sh` leaves a background `mosquitto_sub` that can write into an earlier evidence folder; one file was restored from git and the script was not changed.
7. Bench state is deliberately left in place (tokens, ACL rows, ha-c container, UAT Marker, orphan mirrors, backups); the removal list is in `08-UAT.md` and `bench-state-final.txt`. The ROADMAP plan list now ticks 08-15 (18 of 18); the Phase 8 checkbox stays with the orchestrator's tooling.

### Gaps Summary

No gaps. The UAT-04 gap of the previous report is closed: block 4 is `pass`, the Gaps entry is `resolved`, and the verifier agrees from the evidence (final re-run on build `b8232252540a55969145ca0034d8fd86b4be3b7c`, observed on the original tombstoned state with the receiver-guard build, ha-b receiving only). No override is applied and none was invented; the earlier FAIL records stay as history. Human verification items: none open (the owner-judged items are recorded as pass in the ledger with their limits stated above).

---

_Verified: 2026-10-11T13:52:00Z_
_Verifier: Claude (gsd-verifier)_
