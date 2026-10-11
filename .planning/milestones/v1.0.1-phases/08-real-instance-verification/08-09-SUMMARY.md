---
phase: 08-real-instance-verification
plan: 09
subsystem: verification-bench
tags: [uat, human-verify, p1-1, p1-6, hacs, release-identity, production-host, owner-override, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: 08-UAT.md ledger and recorder gate, check-evidence-clean.sh, every bench check recorded (plans 08-01 to 08-08), the v1.0.0 release of Phase 4 and the hacs.json floor
provides:
  - P1-1 recorded as pass in 08-UAT.md (block 5) on the abbreviated path host-with-integration with `override_by: Alexander Kentner`, the steps not run listed, and the release tag SHA d0f660cb2422c7688d22a674cf54f955a8c26c7f as the build identity
  - P1-6 recorded as pass in 08-UAT.md (block 10): core 2026.9.4 of hassio-n2plus, read by the owner in Settings > About, at or above the 2026.9.0 floor
  - Owner decision PROD-HOST in 08-UAT.md; results table and Summary complete (14 recorded, passed 13, issues 1, pending 0)
  - Evidence p1-1/result.txt, p1-1/release-identity.txt (read-only git and gh proof of what HACS installs), p1-6/result.txt, hosts by role only
affects: [08-10]
tech-stack:
  added: []
  patterns:
    - "release identity of a HACS install is proven from the public repository (tag SHA, release data, empty diff of hacs.json, manifest and brand against HEAD), never from the bench SHA"
    - "an abbreviated owner-performed check is a pass only with override_by in the owner's own name plus the list of steps not run (D-07)"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/p1-1/result.txt
    - .planning/phases/08-real-instance-verification/08-evidence/p1-1/release-identity.txt
    - .planning/phases/08-real-instance-verification/08-evidence/p1-6/result.txt
    - .planning/phases/08-real-instance-verification/08-09-SUMMARY.md
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "PROD-HOST (owner): P1-1 on production host 1, which already runs MQTT Actions, on the abbreviated path host-with-integration; override in the owner's own name, Alexander Kentner"
  - "Block 5 carries the release tag SHA d0f660cb (what HACS installs), block 10 the pinned bench SHA b7f52b34 like every other non-P1-1 block, although the host's core version does not depend on the build"
  - "No cleanup step and no residue decision on the abbreviated path: no temporary hub, no base topic phase8_hacs_check, no retained topic on the production broker"
  - "REQUIREMENTS.md left unchanged: UAT-01..04 are shared by the whole phase and UAT-04 carries an open gap; the phase-end plan owns that file (as in 08-08)"
metrics:
  duration: 2026-10-07T21:46Z to 2026-10-07T21:50Z (executor dispatch for Task 3; the owner answered Tasks 1 and 2 to the orchestrator earlier the same day)
  completed: 2026-10-07
status: complete
commits: 1
plan_head_before: 78717e66447aac78e64725748a0ec31247af3e3f
plan_head_after: f06ae9a
actuals:
  tokens: 3950
  tasks: 3
  commits: 1
requirements-completed: [UAT-01, UAT-02, UAT-03, UAT-04]
coverage:
  - id: D1
    description: "P1-1: HACS client on production host 1 shows the repository card with installed version v1.0.0, Redownload/Update and restart work, the icon is shown on the integration page, a second Add integration > MQTT Actions aborts as already configured (abbreviated path; the first add and the removal of integration and repository were not run)"
    verification:
      - kind: manual_procedural
        ref: "08-evidence/p1-1/result.txt; owner statements \"P1-1, Pfad host-with-integration:\" and \"Wie vorgeschlagen\" (2026-10-07)"
        status: pass
      - kind: other
        ref: "08-evidence/p1-1/release-identity.txt: git rev-parse v1.0.0 = d0f660cb2422c7688d22a674cf54f955a8c26c7f, gh release view v1.0.0 (not a prerelease, published 2026-10-03), empty diff of hacs.json, manifest and brand against HEAD"
        status: pass
      - kind: other
        ref: "~/ha-test/bin/check-recorded.sh P1-1"
        status: pass
    human_judgment: true
    rationale: "owner-performed steps on a production host that Claude never touches (D-02); the pass is an owner override on the abbreviated path (D-07)"
  - id: D2
    description: "P1-6: the core version of hassio-n2plus, read by the owner in Settings > About, is 2026.9.4, at or above the 2026.9.0 floor of hacs.json"
    verification:
      - kind: manual_procedural
        ref: "08-evidence/p1-6/result.txt; owner statement \"P1-6: 2026.9.4\" (2026-10-07)"
        status: pass
      - kind: other
        ref: "~/ha-test/bin/check-recorded.sh P1-6; tests/test_toolchain.py test_home_assistant_floor states the (2026, 9, 0) floor"
        status: pass
    human_judgment: true
    rationale: "owner-read value on a production host (D-02); Claude cannot observe it"
  - id: D3
    description: "08-UAT.md ledger complete: PROD-HOST decision recorded, blocks 5 and 10 recorded, table and Summary consistent (14 recorded, 13 passed, 1 issue, 0 pending), evidence free of secrets and host addresses"
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-recorded.sh --all; ~/ha-test/bin/check-evidence-clean.sh .planning/phases/08-real-instance-verification/08-evidence; grep for IPs and production host names over p1-1 and p1-6 (no hits)"
        status: pass
    human_judgment: false
---

# Phase 8 Plan 09: P1-1 and P1-6 Summary

P1-1 (HACS client install) is recorded as `pass` on the abbreviated path host-with-integration on production host 1 with `override_by: Alexander Kentner`, the steps not run listed (first add, removal of integration and repository), and the release tag SHA `d0f660cb2422c7688d22a674cf54f955a8c26c7f` as the build identity, proven read-only from the public repository (`git rev-parse v1.0.0`, `gh release view v1.0.0` not a prerelease, `gh release list` marks v1.0.0 Latest, empty diff of hacs.json, manifest and brand files against HEAD); HACS reported v1.0.0. P1-6 is recorded as `pass`: the owner read core 2026.9.4 in Settings > About of hassio-n2plus, at or above the 2026.9.0 floor. With these two, all 14 checks of the phase are recorded (`check-recorded.sh --all` PASS: passed 13, issues 1, pending 0). Claude touched no production host and no production broker; the owner answered both checkpoints to the orchestrator in chat. `commits:` is 1 measured from this worktree's base (`git rev-list --count 78717e6..HEAD`).

## What was done

- **Task 1 (checkpoint:decision, PROD-HOST, no commit):** answered by the owner to the orchestrator in chat on 2026-10-07. Literal replies: `P1-1, Pfad host-with-integration:` and, to the orchestrator's proposed recording line `production host 1, override Alexander Kentner, HACS v1.0.0, P1-1 approved, nicht gelaufen: erstes Hinzufügen und Entfernen`, the reply `Wie vorgeschlagen` ("as proposed"). Option `host-with-integration`, host role "production host 1", override name given by the owner. Recorded in `08-UAT.md` section Owner decisions (row `PROD-HOST`, 2026-10-07) with both the proposed line and the confirmation verbatim.
- **Task 2 (checkpoint:human-verify, blocking-human, no commit):** answered by the owner in the same chat. P1-1: HACS-reported version v1.0.0; approved on the abbreviated path (repository card, Redownload/Update, restart, icon, second add aborts); not run: the first add and the removal of integration and repository; cleanup not applicable (nothing installed or removed, no temporary base topic, no residue on the production broker). P1-6: literal reply `P1-6: 2026.9.4` (Settings > About of hassio-n2plus).
- **Task 3 (f06ae9a, this dispatch):** wrote `p1-1/release-identity.txt` from read-only commands against the local tags and the public repository: `git rev-parse v1.0.0` = `d0f660cb2422c7688d22a674cf54f955a8c26c7f`, `gh release view v1.0.0 --json tagName,targetCommitish,publishedAt,isPrerelease,name` (tagName v1.0.0, target main, published 2026-10-03T20:22:01Z, isPrerelease false), `gh release list --limit 5` (v1.0.0 Latest, v0.1.0; the deleted prerelease v1.0.1-rc1 is absent), newest non-prerelease v1.0.0 (`--exclude-pre-releases`, isLatest), and an empty `git diff --stat v1.0.0 HEAD -- hacs.json custom_components/mqtt_actions/manifest.json custom_components/mqtt_actions/brand`; the HACS-reported version stands next to the tag. Wrote `p1-1/result.txt` and `p1-6/result.txt` with the owner's statements verbatim, the date, hosts by role only ("production host 1"; "hassio-n2plus" is the documented role name of the second real host used by the plan itself), the path taken, the steps not run, the cleanup choice (not applicable) and the build identity. Recorded block 5 (`result: pass`, `override_by: Alexander Kentner`, `sha:` = the release tag SHA, `date: 2026-10-07`, `evidence: 08-evidence/p1-1`, `note:` with the steps not run and the HACS version) and block 10 (`result: pass`, `sha:` = the pinned bench SHA like every other non-P1-1 block, `note:` with 2026.9.4 read in Settings > About and the floor comparison of `tests/test_toolchain.py` `test_home_assistant_floor`), updated the results table rows P1-1 and P1-6, the Summary counts (passed 13, issues 1, pending 0) and added an Observations entry "Release HACS reports" (research assumption A9). Gates from the worktree root, all PASS: `check-recorded.sh P1-1`, `check-recorded.sh P1-6`, `check-recorded.sh --all`, `check-evidence-clean.sh .planning/phases/08-real-instance-verification/08-evidence`, the tag test (`git rev-parse v1.0.0` equals the recorded SHA and the HACS-visible diff is empty), `git status --porcelain -- custom_components tests .github` empty, and a grep over `p1-1` and `p1-6` for IP addresses and production host names (no hits).

## Task Commits

1. **Task 1:** no commit (owner decision in chat; written into `08-UAT.md` in Task 3)
2. **Task 2:** no commit (owner answer in chat)
3. **Task 3:** `f06ae9a` (docs: record P1-1 and P1-6)

**Plan metadata:** the commit of this SUMMARY (`docs(08-09): complete P1-1 and P1-6 plan summary`); STATE.md and ROADMAP.md are updated by the orchestrator after the worktree merge.

## Deviations from Plan

**1. [Plan adaptation] Both checkpoints were answered to the orchestrator, not to an executor.** Tasks 1 and 2 are `checkpoint:decision` and `checkpoint:human-verify gate="blocking-human"`; the owner answered them in chat to the orchestrator session on 2026-10-07 and the answers were relayed to this executor in the dispatch. The executor ran Task 3 only. Both evidence files and the ledger say so ("answered to the orchestrator, relayed to the executor").

**2. [Plan adaptation] Abbreviated path, so no install, no removal, no residue.** The owner chose `host-with-integration` (production host 1 already runs the single-instance integration). The full path's first add, the temporary hub with the base topic `phase8_hacs_check`, the removal of integration and repository and the retained availability topic (T-08-26) therefore did not occur, and the plan's step 8 (read and clear command for the residue) was not given to the owner. Per the plan and D-07 this is recorded as `result: pass` with `override_by:` in the owner's own name and the list of steps not run, not as a full-path pass. The ledger's general sentence "an owner override of a failed item stays `result: issue`" describes failed items; P1-1 did not fail, it was abbreviated, which the plan defines as an override pass. `check-recorded.sh` accepts the block (P1-1 is not a scripted check, so no verdict.txt is required).

**3. [Observation] Two different `sha:` conventions in one plan.** Block 5 records the release tag SHA (the build HACS really installs, D-03 as worded in "Build under test"); block 10 records the pinned bench SHA like every other block, although the host's core version does not depend on any build. Both notes say which SHA they carry and why.

**4. [Observation] REQUIREMENTS.md not changed.** As in 08-08: the plan carries UAT-01..04 only because the ten-item checks share the ledger and the success-criterion-5 gap rule; UAT-04 holds an open gap, so the phase-end plan (08-10) owns the checkboxes.

**5. [Rule 3 - Blocking] Commit ledger kept outside `.git`.** The sandbox refuses commands that name the `.git` directory, so the per-plan ledger file of protocol 0c could not be written; the plan base 78717e66447aac78e64725748a0ec31247af3e3f (the asserted worktree base) was used as the ledger and `commits:` was measured against it with `git rev-list --count`.

## Production footprint (D-01, D-02)

- Claude did not connect to any production host or the production broker, did not use `ha-ws` or `ha`, and printed no token. Claude's only external actions were read-only `git` on the local tags and read-only `gh release view` / `gh release list` against the public repository.
- The owner's production steps: on production host 1 a Redownload/Update of the already installed integration and a restart (HACS reported v1.0.0); on hassio-n2plus a read of Settings > About. Nothing was installed fresh, nothing removed, no device created, no temporary hub, no retained topic left behind.
- Committed evidence names the hosts by role only and holds no address or credential (`check-evidence-clean.sh` PASS, grep for IPs and production host names empty).

## Self-Check: PASSED

Re-run at the end of Task 3 from the worktree root, before this SUMMARY was written:

- Task 3 acceptance: block 5 `sha:` equals `git rev-parse v1.0.0` (`d0f660cb2422c7688d22a674cf54f955a8c26c7f`); `p1-1/release-identity.txt` shows the tag, the release data (tagName, target, publishedAt, isPrerelease false, name), the newest non-prerelease v1.0.0 and the empty diff of the HACS-visible files; block 5 carries `override_by: Alexander Kentner` and the note lists the steps not run (first add, removal of integration and repository); `p1-1/result.txt` and `p1-6/result.txt` name hosts by role only; `check-recorded.sh P1-1` and `check-recorded.sh P1-6` print PASS.
- Plan verification: `check-recorded.sh P1-1` PASS, `check-recorded.sh P1-6` PASS, `check-recorded.sh --all` PASS (14 recorded, Summary counts equal the blocks), `check-evidence-clean.sh .planning/phases/08-real-instance-verification/08-evidence` PASS, `git status --porcelain -- custom_components tests .github` empty.
- Files exist: `08-evidence/p1-1/result.txt` (2514 bytes), `08-evidence/p1-1/release-identity.txt` (1852 bytes), `08-evidence/p1-6/result.txt` (995 bytes); commit `f06ae9a` is HEAD of this worktree branch on top of the base 78717e6 (`git log --oneline -3`); `git show --diff-filter=D` of that commit lists no deletions; working tree clean after the commit.
- No modification of STATE.md or ROADMAP.md in this worktree.
