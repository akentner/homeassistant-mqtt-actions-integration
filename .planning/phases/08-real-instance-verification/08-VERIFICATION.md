---
phase: 08-real-instance-verification
verified: 2026-10-08T21:00:00Z
status: gaps_found
score: 5/6 must-haves verified
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
  - .planning/phases/08-real-instance-verification/08-UAT.md
  - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/build.txt
  - .planning/phases/08-real-instance-verification/08-evidence/00-preflight/stale-anchor-final.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-1/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-3/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/p1-4/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-01/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-01/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-02/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-02/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-03/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-03/verdict.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04/result.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04/tombstone-cause.txt
  - .planning/phases/08-real-instance-verification/08-evidence/uat-04/verdict.txt
covered_digest: "v3:sha256:adaee73906de7e388651848794457ba472084b205dfebc77cc6f120ef56ae5ac"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "ROADMAP criterion 4, second clause (UAT-04): the core MQTT prefix yields only disabled duplicates"
    status: failed
    reason: "Scripted check 08-04 (expectations coded before the run) FAILED X7 and X8 on both ha-a and ha-b: with export_prefix set to `homeassistant` (no restart) Lampe Test and Bar Select each got an ENABLED `mqtt` row (`switch.lampe_test_2`, `select.bar_select_2`, disabled_by null); only the UAT Marker duplicate was disabled_by integration. The published payload is correct (enabled_by_default false on every component, X3 passes). Likely cause (inference, not reproduced in isolation): core `entity_registry.async_get_or_create` restores `disabled_by` from a deleted-entity tombstone with the same (domain, platform, unique_id); the UAT-02 legacy replay had left such tombstones (disabled_by null) for exactly those two devices, and the marker, which never had one, behaves as expected. Whether this is a product gap (a real user with earlier legacy twins and the core prefix would see the same) or a bench artifact of running UAT-02 before UAT-04 on the same instances is undecided. The owner left it open (UAT04-DISPOSITION, 2026-10-08), with no override."
    artifacts:
      - path: ".planning/phases/08-real-instance-verification/08-evidence/uat-04/verdict.txt"
        issue: "FAIL X7 (2 devices x 2 instances) and FAIL X8 (2 enabled mqtt rows per instance)"
      - path: ".planning/phases/08-real-instance-verification/08-evidence/uat-04/tombstone-cause.txt"
        issue: "core source lines and the tombstones that explain the enabled rows"
    missing:
      - "Reproduce clause 2 in isolation: a fresh bench state with NO earlier legacy twin tombstones for the exported unique ids, export on the core prefix, no restart; read both registries"
      - "If it reproduces only with tombstones: decide product gap (documented warning or a guard, for example clear matching deleted-entity tombstones or force disabled_by on the export-created row) versus accepted bench artifact; then fix in a follow-up gap plan or phase (D-08) and re-run UAT-04 (`~/ha-test/bin/check-uat04.sh run`, scrubbed copy in 08-evidence/00-preflight/bench-scripts/)"
      - "If it does not reproduce without tombstones: record the tombstone interaction as a documented limitation or a guard, and re-run UAT-04 on a clean state"
---

# Phase 8: Real-Instance Verification Verification Report

**Phase Goal:** The Phase 5 UAT debt is closed: the four checks the owner skipped in v1.0 are run by hand on real instances against the v1.0.1 build, and each result is recorded with its evidence. This is a manual verification phase (ha-one and ha-two, or the production instances); no code changes are planned, and a failed check becomes a gap, not an accepted skip.
**Verified:** 2026-10-08T21:00:00Z
**Status:** gaps_found
**Re-verification:** No, initial verification

## Goal Achievement

All four UAT checks were run and each has a recorded result with evidence; the phase did what it was set up to do, including raising the failure as a gap instead of skipping it. But the Phase 5 UAT debt is not fully closed: UAT-04 holds for clauses 1 and 3 and fails for clause 2, and that failure is an open gap by owner decision. Three of the four requirements are met; UAT-04 is not. The report does not turn UAT-04 into a pass.

### Build under test

| Check | Result |
| ----- | ------ |
| Recorded build | `b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3` (`00-preflight/build.txt`), read-only bind mount of `custom_components/mqtt_actions`, HA 2026.9.4 on ha-a and ha-b |
| "v1.0.1 build" | There is no `v1.0.1` tag (tags are `v0.1.0`, `v1.0.0`; the prerelease `v1.0.1-rc1` was deleted in Phase 7) and the manifest still reads `1.0.0`. The v1.0.1 build is the unreleased Phase 6 and 7 code: `git diff --stat v1.0.0 b7f52b34 -- custom_components` shows the Phase 6 fixes in `manager.py`, `takeover.py`, `document.py`, `const.py`. This matches the ROADMAP use of the term |
| No product change in Phase 8 | `git log --grep='(08-' -- custom_components tests .github pyproject.toml uv.lock` is empty; `git diff --stat b7f52b34 HEAD -- custom_components tests .github pyproject.toml uv.lock` is empty (re-run by the verifier). No recorded check is stale |
| Regression gate | Full test suite run by the orchestrator: 1490 passed (not re-run here) |

### Observable Truths (ROADMAP success criteria, the contract)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | SC1 / UAT-01: with a v0.1.0 instance next to a native instance, the v0.1.0 instance keeps running its actions for the migrated devices, shows no entities for them and raises no error | VERIFIED | `uat-01/verdict.txt` PASS, `result.txt`: ha-c ran the byte-identical v0.1.0 component (`v010-identity.txt`) with its own MQTT user and ACL block; marker commands gave delta exactly +1 on ha-a, ha-b and ha-c for both on and off, 0 for the other text on ha-c; ha-c registry holds no `mqtt` row, no row with unique id equal to a device id, no switch or button of `mqtt_actions` for a migrated device, no switch state; no ERROR or CRITICAL of `mqtt_actions` or core `mqtt` on ha-c (all lifetimes) or on ha-a/ha-b since ha-c arrived. Pass wording fixed before the run (UAT01-WORDING, `observation`): the 7 v0.1.0 companion mode selects `select.{name}_mode` exist on ha-c and are recorded as an observation, not counted. Read this literally, "shows no entities for them" holds only under that owner wording, because the companion selects are entities of `mqtt_actions` for the migrated devices; the wording was decided by the owner before the run (decision recorded in 08-UAT.md, Owner decisions) |
| 2 | SC2 / UAT-02: after re-publishing retained legacy Discovery and restarting twice, no `_2` duplicate entities exist, proving MIG-05 outside the test harness | VERIFIED | `uat-02/verdict.txt` PASS: E1 to E4 hold in round 1 and round 2 on ha-a and ha-b (no `mqtt` row, no `_2` id, no legacy `mqtt` device, 30 `mqtt_actions` rows identical to baseline in entity id, registry id, unique id, device id). The replay really created twins (six `_2` tombstones per instance in `twin-tombstones.txt`) and they were removed. Limit, recorded by the ledger: ha-b logged the "Removed 3 duplicate entities" catch line and ha-a logged none although both ended clean; the path that cleaned ha-a is not identified, so the proof is on the outcome, not on one named code path. Live variant (legacy Discovery published while running: six `_2` entities appear and vanish only at the next start) is an owner-accepted limit (WR03-LIVE-REPLAY), no Gaps entry |
| 3 | SC3 / UAT-03: a command on one of two real instances runs the actions exactly once on every approved instance; an unknown payload is ignored and leaves the state unchanged | VERIFIED | `uat-03/verdict.txt` PASS, `counts.txt` re-read by the verifier: unapproved control +1 on ha-a, 0 on ha-b; after approval of the mirror (Repairs fix flow API) command on ha-a gives +1 on ha-a and +1 on ha-b (step B), command on the ha-b mirror gives +1 and +1 (step C), each after a 60 s wait; `banana` (QoS 1, not retained) gives marker delta 0 on both, "Ignoring unknown payload" +1 on each, states unchanged, retained value read back unchanged. Limit: "not retained" is proved by the unchanged retained read-back (a subscriber capture shows retain=0), not by a broker-side flag |
| 4 | SC4 / UAT-04: the Discovery export has `enabled_by_default` false and no buttons, the core MQTT prefix yields only disabled duplicates, and switching the export off clears its topics | FAILED | `uat-04/verdict.txt` FAIL. Clause 1 holds (X1 to X5: three retained payloads, only `switch`/`select`, `enabled_by_default` false, no button, no `test_` key, nothing on `homeassistant/device`). Clause 3 holds (X10: `mqtt_actions_export/#` and `homeassistant/device/#` read back empty after off). Clause 2 FAILS (X7, X8) on both instances for Lampe Test and Bar Select (enabled `mqtt` rows `switch.lampe_test_2`, `select.bar_select_2`); the UAT Marker control behaved as expected. See Gaps. Not turned into a pass; no override (UAT04-DISPOSITION, leave-as-gap, 2026-10-08) |
| 5 | SC5: each of the four checks has a recorded pass or fail result with evidence, and any failure is raised as a gap for follow-up work | VERIFIED | `08-UAT.md` blocks 1 to 4 carry `result`, 40-hex sha, date and an existing evidence folder; the single `issue` block (4) has a Gaps entry with `test: 4`, `severity: minor`, `status: failed`; the rule "failed check is a gap, not a skip" was applied (no `skipped` token used). Caveat: the gap lives in the ledger and, now, in this report's frontmatter; there is no ROADMAP follow-up phase yet, which is the next step (`/gsd-plan-phase --gaps`) |
| 6 | SC6: the ten human items of Phases 1 to 3 each have a recorded pass or fail on the final build, so the archived reports can be refreshed to `passed` (or accepted as owner overrides) | VERIFIED (with evidence-strength limits, see below) | Blocks 5 to 14 are all `result: pass`; block 5 carries `override_by: Alexander Kentner`. Archived reports re-read by the verifier: `verification.status` returns `passed` for Phases 1, 2, 3 and 4; scores 8/8, 10/10, 5/5, 5/5; each Phase 1 to 3 human item has a `resolution:` that names block, folder, sha and date; no other override than the recorded Phase 5 supersession ones and the P1-1 override |

**Score:** 5/6 truths verified (SC4 failed). Behavior-unverified truths: 0 (the checks are manual by design; owner-judged items are listed under Evidence strength rather than as human-verification items, because the phase's deliverable is exactly the recorded owner judgement).

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ------------ | ----------- | ------ | -------- |
| UAT-01 | 08-01, 08-05 (declared by every plan) | v0.1.0 instance keeps running actions, no entities for migrated devices, no error | SATISFIED (under owner wording UAT01-WORDING: companion mode selects are an observation) | block 1, `uat-01/` |
| UAT-02 | 08-01, 08-02 | Retained legacy Discovery plus two restarts yields no `_2` duplicates (proves MIG-05) | SATISFIED | block 2, `uat-02/` |
| UAT-03 | 08-01, 08-03 | Command runs actions exactly once on every approved instance; unknown payload ignored | SATISFIED | block 3, `uat-03/` |
| UAT-04 | 08-01, 08-04 | Export has `enabled_by_default` false and no buttons, core prefix yields only disabled duplicates, off clears topics | BLOCKED (clause 2 fails; clauses 1 and 3 hold) | block 4, `uat-04/`, Gaps entry test 4 |

Cross-reference: the IDs UAT-01 to UAT-04 appear in the frontmatter of plans 08-01, 08-06 to 08-10 (all four) and in 08-02 (UAT-02), 08-03 (UAT-03), 08-04 (UAT-04), 08-05 (UAT-01); REQUIREMENTS.md lists exactly UAT-01 to UAT-04 for Phase 8, all `Pending` (traceability still to be updated by the orchestrator: UAT-01 to UAT-03 complete, UAT-04 stays open). No orphaned requirement, no requirement in a plan that REQUIREMENTS.md does not map. Plans 08-06 to 08-09 carry the UAT ids only because the ten-item checks share the ledger (they have no requirement id).

### Evidence strength of the ten items (SC6) and of the scripted checks

Stated so the pass marks are not read stronger than the evidence:

| Item | Evidence | Limit |
| ---- | -------- | ----- |
| P1-1 (HACS client install) | `p1-1/result.txt`, `release-identity.txt` | Abbreviated path host-with-integration on production host 1 (PROD-HOST): repository card with installed version, Redownload/Update, restart, icon, second add aborts. NOT run: first add, removal of integration, removal of repository. Recorded as pass with an override in the owner's own name (Alexander Kentner, 2026-10-07; chat replies "P1-1, Pfad host-with-integration:" and "Wie vorgeschlagen"). It verifies the released `v1.0.0` (tag SHA `d0f660cb...`), not the bench build; the verifier did not and cannot see the host. Owner-only, no screenshot |
| P1-2 (EN/DE strings) | 8 screenshots in `p1-2/` plus `p3-1/01..06`, `screens.txt` | Strongest of the owner items. The orchestrator drove the browser, the owner judged ("approved P1-2 P3-1", chat) |
| P1-3 (action editor and banners) | owner statement "approved P1-3 P1-4 P3-2" | Chat statement, no screenshots. Claude's REST pre-check aborted its flows and saved nothing, so the real-frontend save on the identical resubmit rests on the owner plus `tests/test_config_flow.py::test_switch_flow_device_id_warns_then_saves_on_resubmit` |
| P1-4 (failing-action Repairs dialog) | same statement; `result.txt` shows the Repairs issue listed through the API before the owner looked | Chat statement, no screenshots; clearing after the next success rests on a unit test, not on the real instance |
| P1-5 (retained vs live) | scripted, `p1-5/verdict.txt`, `counts.txt` | Fully scripted, no owner judgement. Toggle was the service call, not a UI click; "broker reconnect" was a reload of the core `mqtt` entry (`require_restart: false`), the Mosquitto container was not restarted (StartedAt unchanged), so a real broker disconnect was not exercised |
| P1-6 (core version of hassio-n2plus) | owner statement "2026.9.4" | Informational; read by the owner, Claude did not connect to the host |
| P2-1 (select subentry flow) | owner statement "Vollständig, ok" per item | The owner first answered "Noch nicht geprüft" and "Nur teilweise gesehen" and confirmed this item completely when asked per item (two-step approval). No screenshots; data path scripted over REST (`flow-precheck.txt`) |
| P2-2 (breaker loop) | `p2-2/verdict.txt` (scripted PASS: 6 live messages after the trip, one breaker warning, pause survives restart, hub reload releases) plus owner statement "Vollständig, ok" for the Repairs card EN/DE | Two-step approval as for P2-1; Repairs card rendering has no screenshot |
| P3-1 (approval request rendering) | 6 screenshots in `p3-1/`, owner "approved P1-2 P3-1" | The orchestrator drove the browser, the owner judged; never approved on ha-a; cleaned up (`topics-after-delete.txt`) |
| P3-2 (delete dialogs) | owner statement "approved P1-3 P1-4 P3-2"; `deletes.txt`, `topics-after-delete.txt` | Chat statement, no screenshots. The owner judged the two dialogs but did not confirm the deletes; Claude performed them through the same paths over the guard |

Items P1-3, P1-4, P3-2, P2-1 and P2-2 rest on the owner's word without screenshots; this was decided by plan (browser MCP unavailable in the executing session) and the statements are recorded verbatim, but none of it can be re-checked from the repository. The owner approvals were sometimes given in two steps (first "not checked", then confirmed per item), and whether the owner performed every click path is not independently evidenced (08-10-SUMMARY deviation 4). The 08-UAT.md ledger states these limits itself and does not overstate them.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `08-UAT.md` | 14 blocks, summary 13 pass / 1 issue, Gaps, Owner decisions | VERIFIED | Counts re-read: blocks 1 to 14, one `issue` (block 4), summary block consistent; requirement verdict table matches the blocks; frontmatter `status: partial` (one open issue) |
| `08-evidence/00-preflight/build.txt` and `stale-anchor-final.txt` | pinned build, empty stale anchor | VERIFIED | verifier re-ran `git diff --stat` on `custom_components tests .github pyproject.toml uv.lock`: empty |
| `08-evidence/uat-01..04/` | verdict and result per scripted check | VERIFIED | all four folders hold `verdict.txt` and `result.txt` that agree with the ledger (PASS, PASS, PASS, FAIL) |
| `08-evidence/p1-*..p3-*/` | one folder per item | VERIFIED | 10 folders exist, each with `result.txt` |
| Bench script copy | secret-free copy of the bench helpers | VERIFIED | 23 scripts plus README in `00-preflight/bench-scripts/`; the verifier's grep for JWT-shaped tokens over the evidence tree and ledger finds none |
| `08-VALIDATION.md` | validation contract, all tasks green | VERIFIED | task map reads green; 08-04-T1 is noted as "recorded; UAT-04 result is issue" |
| Archived Phase 1 to 3 reports | regenerated to `passed` with resolutions | VERIFIED | see SC6; digests were refreshed through `verification.fingerprint` per 08-10-SUMMARY |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| ledger block N | evidence folder | `evidence:` field | WIRED | every block's folder exists in the tree |
| ledger `issue` block 4 | Gaps entry `test: 4` | gaps rule of `check-final.sh` | WIRED | one issue, one Gaps entry |
| ledger blocks 5 to 14 | archived Phase 1 to 3 reports | `resolution:` per human item | WIRED | resolutions name block, folder, sha, date, and carry the P1-1 override |
| UAT-04 failure | follow-up plan or phase | D-08 | NOT YET WIRED | no follow-up phase in ROADMAP; the gap is recorded in the ledger and in this report's frontmatter and needs `/gsd-plan-phase --gaps` or a new phase |

### Behavioral Spot-Checks

Run by the verifier (read-only):

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| No product code changed in Phase 8 | `git log --grep='(08-' -- custom_components tests .github pyproject.toml uv.lock` | empty | PASS |
| Pinned build equals tree | `git diff --stat b7f52b34 HEAD -- custom_components tests .github pyproject.toml uv.lock` | empty | PASS |
| Archived report status | `gsd-tools query verification.status` over Phase 1 to 4 | `passed` x4 | PASS |
| UAT-03 counts | read `uat-03/counts.txt` | steps A to D match the claimed deltas | PASS |
| UAT-04 failure is real | read `uat-04/verdict.txt`, `export-shape-check.txt` | six FAIL lines (X7 x4, X8 x2); X1 to X5, X10 pass | CONFIRMED FAIL |

The bench scripts and the live bench (`~/ha-test`) were not re-run: they act on running containers and the full test suite was already run by the orchestrator (1490 passed). The scripted results are therefore read from the recorded evidence, not reproduced.

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` is declared or exists for this phase; SKIPPED.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| none | - | TBD, FIXME or XXX in `08-UAT.md` or `08-evidence` | - | none found; no code file was modified by the phase |

### Findings the owner should see

1. UAT-04 clause 2 is a real, reproducible-on-the-bench failure on two instances, not a flake: the evidence is six assertions failing in a script whose expectations were coded before the run. The cause analysis (tombstone restore of `disabled_by` in core `async_get_or_create`) is an inference from the marker control and the core source, not an isolated reproduction. The first thing the follow-up needs is that isolated reproduction. A user who ever ran legacy Discovery for the same devices and then enables the export on the core prefix could hit the same result, so "bench artifact" is not established.
2. The ROADMAP wording of criterion 4 ("yields only disabled duplicates") and of UAT-01 ("shows no entities for them") are met only under the owner wording for UAT-01 (companion mode selects as an observation) and not for UAT-04 clause 2. The v0.1.0 companion selects are a decision of the owner, documented, but it is a loosening of the literal text.
3. P1-1 is an abbreviated path with an owner override in the owner's name; it validates the released v1.0.0, not the bench build, and three of its steps were not run.
4. Five items (P1-3, P1-4, P2-1, P2-2, P3-2) pass on chat statements without screenshots; P2-1 and P2-2 were confirmed in a second step after "not checked" answers.
5. UAT-02 catch asymmetry: ha-a's duplicates were cleaned without the catch log line that ha-b shows; the outcome is identical (clean registry), the mechanism on ha-a is unexplained. Not raised as a gap by the ledger; worth one line in the follow-up.
6. Bench state is deliberately left in place (tokens, ACL rows, ha-c container, UAT Marker, orphan mirrors, three backups); the removal list is in `08-UAT.md` ("Bench state left behind", "Owner follow-ups") and a follow-up gap plan re-uses it.
7. `REQUIREMENTS.md` still shows UAT-01 to UAT-04 as Pending; update UAT-01 to UAT-03 to complete, keep UAT-04 open.

### Gaps Summary

One gap, minor severity (as classified in the ledger): UAT-04 clause 2. Everything else the phase set out to do is done and evidenced: UAT-01, UAT-02 and UAT-03 pass against the pinned build with scripted, counted evidence; the ten human items are recorded as pass with their evidence limits stated; the archived Phase 1 to 3 reports read `passed`; no product code was changed. The status is `gaps_found` because a must-have truth (roadmap criterion 4) is failed, and the owner explicitly chose to keep it that way instead of accepting an override. The honest next step is a follow-up gap plan (`/gsd-plan-phase --gaps`) that reproduces the failure in isolation, decides product gap versus bench artifact, and re-runs UAT-04.

---

_Verified: 2026-10-08T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
