---
phase: 09-v1-0-1-release
verified: 2026-10-15T23:50:14Z
status: passed
score: 3/3 must-haves verified (roadmap success criteria; 27/27 plan truths verified or superseded by the re-pointed 09-04/09-05 truths)
covered_files:
  - ".github/workflows/release.yml"
  - ".planning/MILESTONES.md"
  - ".planning/PROJECT.md"
  - ".planning/REQUIREMENTS.md"
  - ".planning/phases/09-v1-0-1-release/09-01-PLAN.md"
  - ".planning/phases/09-v1-0-1-release/09-01-SUMMARY.md"
  - ".planning/phases/09-v1-0-1-release/09-02-PLAN.md"
  - ".planning/phases/09-v1-0-1-release/09-02-SUMMARY.md"
  - ".planning/phases/09-v1-0-1-release/09-03-PLAN.md"
  - ".planning/phases/09-v1-0-1-release/09-03-SUMMARY.md"
  - ".planning/phases/09-v1-0-1-release/09-04-PLAN.md"
  - ".planning/phases/09-v1-0-1-release/09-04-SUMMARY.md"
  - ".planning/phases/09-v1-0-1-release/09-05-PLAN.md"
  - ".planning/phases/09-v1-0-1-release/09-05-SUMMARY.md"
  - ".planning/phases/09-v1-0-1-release/09-CONTEXT.md"
  - ".planning/phases/09-v1-0-1-release/09-UAT.md"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release-notes.md"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/decision.txt"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/notes-applied.txt"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/pre-tag-gate.txt"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/release-body.md"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/release-jobs.json"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/release-latest.json"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/release-run.json"
  - ".planning/phases/09-v1-0-1-release/09-evidence/release/tag-push.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/00-preflight/build.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/00-preflight/mount-hashes.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/cr01-gate/verdict.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/heal-start/verdict.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-02-null/verdict.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-02/verdict.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-04/prepare.txt"
  - ".planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence/uat-04/verdict.txt"
  - "custom_components/mqtt_actions/manifest.json"
covered_digest: "v3:sha256:fd949f9198b119baf6b4a4f86964b4c45ee09ab7d9170101d6fb7e6481d6302b"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Owner confirms that every push and workflow action of Phase 9 was the owner's: the refspec push of 7baec98 to main (09-02), the push of tag v1.0.1 on 3dc9093 (09-04), and that Claude issued no git push, no gh workflow run and no gh run rerun (judgment-tier prohibitions 09-01 P2, 09-02 P1, 09-04 P2, 09-05 P1)"
    expected: "Owner states yes. Supporting evidence (non-authoritative): push-main.txt and tag-push.txt read pushed_by: owner, claude_push: none; release run 38824818079 is attempt 1; gh run list --commit 3dc9093 shows exactly one Release, one CI and one Validate run"
    why_human: "Who typed a push or dispatch cannot be proven from git or GitHub state; ADR-550 D4 requires human resolution of judgment-tier prohibitions"
    result: "confirmed by owner 2026-10-16 (/gsd-verify-work 9)"
  - test: "Owner acknowledges the remaining judgment-tier prohibitions of Phase 9 (09-01 P1 and P3, 09-02 P2, 09-03 P1 to P3, 09-04 P1, 09-05 P2 and P3) as held, per the Prohibitions table in this report"
    expected: "Owner agrees with the verifier's read: only 7baec98 touched a non-planning file among the 09-0x commits; no commit touches the archived Phase 8 tree after f3c375d (2026-10-11); the 7baec98 UAT-02 FAIL and UAT-04 BLOCKED stand unchanged (one commit each); every 9.2 verdict file has exactly one commit; tag v1.0.1 == FIX on origin and was never moved; the ledger and release notes claim no UAT-01, UAT-03, P1-5 or full re-verification"
    why_human: "Judgment-tier prohibitions; the verifier's read is non-authoritative (ADR-550 D4, never a silent pass)"
    result: "confirmed by owner 2026-10-16 (/gsd-verify-work 9)"
---

# Phase 9: v1.0.1 Release Verification Report

**Phase Goal:** v1.0.1 becomes a real release: the commit whose manifest says 1.0.1 passes UAT-02 and UAT-04 on the bench on exactly that SHA and is tagged, which closes ACCEPTED-GAP-V101 for that release.
**Verified:** 2026-10-15T23:50:14Z
**Status:** passed (all truths verified; both owner confirmations given on 2026-10-16)
**Re-verification:** No, initial verification

Context: plans 09-04 and 09-05 were re-pointed by Phase 9.2 from the bump commit 7baec98 to FIX
`3dc9093f3cc49900bf76576cb4432d84aa94cd74` (`09.2-evidence/00-preflight/build.txt`). The 7baec98 bench run (UAT-02 FAIL,
UAT-04 BLOCKED) and the 9.1 builds 681c587 and dc6513c are superseded history and were never tagged.

## Goal Achievement

### Observable Truths (roadmap success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The manifest bump to 1.0.1 is committed before the bench run, and the tagged commit contains no IN-04 or MIR-01 change (main frozen until the tag) | ✓ VERIFIED | `git show 3dc9093:custom_components/mqtt_actions/manifest.json` → `"version": "1.0.1"`. Bump 7baec98 (only manifest.json, 1 line, no CI-skip marker) is an ancestor of FIX. `git diff v1.0.0 3dc9093` outside `.planning`: no module extraction out of `manager.py` (manager.py grew +562, `takeover.py` already existed at v1.0.0), no `local_actions`/MIR-01 code; commits since v1.0.0 are Phase 6 to 8 and the 9.1/9.2 gap fixes. No `release/1.0.1` branch; remote `main` == FIX == tag; `git diff 3dc9093 HEAD -- . ':!.planning'` is empty. Phase 10 directory does not exist. |
| 2 | UAT-02 and UAT-04 pass on the bench on exactly that SHA; the evidence records the SHA and records ACCEPTED-GAP-V101 as closed for v1.0.1 | ✓ VERIFIED | 9.2 evidence on FIX: `uat-02/verdict.txt` PASS + `build: 3dc9093…`, `uat-02-null/verdict.txt` PASS + build line, `uat-04/verdict.txt` PASS (X1 to X10, `prepare.txt` names build 3dc9093 and holds the exact null-tombstone regression line), `heal-start/verdict.txt` PASS, `cr01-gate/verdict.txt` holds. Independent pin check: sha256 prefixes in `mount-hashes.txt` (manager.py afe57468…, takeover.py f6b446a4…, const.py ff5ec83c…, document.py 3fa07dec…) recomputed from `git show 3dc9093:<file>` and they match. `pin-reassert.txt` PASS with `tree_diff_fix_to_head_excluding_planning: 0 files`. All verdict files committed once (a1014e4, a5474e3, f0afc34, 4a588e7) before the tag push. `09-UAT.md` blocks 21 to 24 pass on FIX; "Gap closure" section: ACCEPTED-GAP-V101 closed for v1.0.1 on 2026-10-15, scoped to this release only. ha-c stopped per D-07 (the roadmap's "ha-a, ha-b, ha-c" means the bench as a whole, CONTEXT D-07). |
| 3 | After the owner pushes tag v1.0.1, release.yml (check-version, three test tiers, hassfest, HACS, release job) is green and GitHub shows v1.0.1 as latest, so HACS offers 1.0.1 | ✓ VERIFIED | Live: `git ls-remote origin refs/tags/v1.0.1` → 3dc9093; `git rev-parse v1.0.1^{commit}` → 3dc9093 (lightweight). `gh run view 38824818079`: Release, event push, headBranch v1.0.1, headSha 3dc9093, conclusion success, attempt 1; jobs Tag matches manifest version, CI / Ruff, Unit tests, Broker tests (Mosquitto), Multi-instance tests, Validate / hassfest, Validate / HACS, Create GitHub release all success. `gh api …/releases/latest` → v1.0.1; `gh release list` → v1.0.1 Latest, not draft, not prerelease. Live body equals `09-evidence/release-notes.md` (differs only by the trailing newline `gh --jq` adds). Pre-tag CI 38803359122 and Validate 38803379292 on headSha 3dc9093 (workflow_dispatch per D-04 amendment) both success, created before the tag. |

**Score:** 3/3 truths verified (0 present, behavior-unverified)

### Plan truths (summary)

| Plan | Result | Note |
|------|--------|------|
| 09-01 (7) | ✓ | Bump 7baec98 manifest-only; 7baec98 pin, backup and bench-script parametrization evidence present (`00-preflight/`). |
| 09-02 (4) | ✓ | `push-main.txt` origin_main_after 7baec98, pushed_by owner; CI/Validate on 7baec98 per D-04 amendment. |
| 09-03 (7) | ✓ (superseded) | On 7baec98 UAT-02 FAIL stands (one commit), UAT-04 BLOCKED, routed to 9.1; release notes written later on FIX. The 7baec98 artifacts `uat-04/verdict.txt` (missing) and the regression line in `09-evidence/uat-04/prepare.txt` are replaced by the 9.2 evidence, which has both. |
| 09-04 (5) | ✓ | Tag on FIX, owner pushed (`tag-push.txt`), pre-tag gate PASS, decision recorded before release, origin/main == FIX. |
| 09-05 (6) | ✓ | Release run green, Latest, notes applied, ledger `status: complete`, PROJECT/MILESTONES/STATE updated, tag still on FIX. |

### Prohibitions (ADR-550, all judgment-tier, non-authoritative verifier read)

| Plan | Prohibition | Verifier read | Basis |
|------|-------------|---------------|-------|
| 09-01 P1 | No product, test, workflow or hacs.json change in this phase except the manifest version | holds | Of all `(09-0x)` commits only 7baec98 touches a non-planning file (manifest.json). `.github`/`hacs.json` unchanged since a5d54d9 (Phase 7). The 9.1/9.2 product fixes are in the inserted phases, as the failure rule requires. |
| 09-01 P2, 09-02 P1, 09-04 P2, 09-05 P1 | No push, tag push or workflow re-run by Claude | consistent, needs owner | `pushed_by: owner`, `claude_push: none` in evidence; release run attempt 1 → human item 1 |
| 09-01 P3, 09-05 P3 | Archived Phase 8 files not edited | holds | Last commit under `.planning/milestones/v1.0.1-phases/08-*` is f3c375d (2026-10-11, archive) |
| 09-02 P2 | No CI run on another SHA counted | holds | Counted runs 38803359122, 38803379292, 38824818079 all have headSha 3dc9093 |
| 09-03 P1 | No FAIL/ABORT turned into a pass | holds | 7baec98 `uat-02/verdict.txt` FAIL and `uat-04/blocked.txt` stand, one commit each; 9.2 verdict files one commit each |
| 09-03 P2, 09-05 P2 | No over-claiming | holds | `09-UAT.md` lists UAT-01, UAT-03, P1-5 as not run; closure text says "not a full re-verification … Phase 12"; release notes claim no extra verification |
| 09-03 P3 | No product change in Phase 9 to make a check pass | holds | Same as 09-01 P1 |
| 09-04 P1 | Tag only the bench-verified SHA; never move it | holds | Tag == FIX on origin and locally; single release run |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/manifest.json` | version 1.0.1 at the tagged SHA | ✓ VERIFIED | at 3dc9093 |
| `09-evidence/00-preflight/build.txt`, `backup-phase9.txt`, `bench-scripts/reseed-tombstones.diff` | 7baec98 pin and backup | ✓ VERIFIED | exist (history) |
| `09-evidence/release/push-readiness.txt`, `push-main.txt`, `ci-bump-sha*.json` | 7baec98 push and CI | ✓ VERIFIED | exist |
| `09-evidence/uat-02/verdict.txt`, `uat-04/*` (09-03) | 7baec98 verdicts | ✓ superseded | FAIL/BLOCKED history; gsd-tools reports `uat-04/verdict.txt` missing and the regression line absent in `uat-04/prepare.txt` on the 7baec98 tree, both present in the 9.2 tree on FIX |
| `09.2-evidence/{uat-02,uat-02-null,uat-04,heal-start,cr01-gate}/verdict.txt` | bench verdicts on FIX | ✓ VERIFIED | PASS/holds with build line 3dc9093 |
| `09-evidence/release/{pre-tag-gate,decision,tag-push}.txt` | tag gate and owner push | ✓ VERIFIED | `tag_local: v1.0.1`, `pushed_by: owner` |
| `09-evidence/release/{release-run,release-jobs,release-latest}.json`, `release-body.md` | release evidence | ✓ VERIFIED | match live `gh` output |
| `09-evidence/release-notes.md` | hand-written notes (D-11) | ✓ VERIFIED | fixes, re-disable behavior change, live-replay `_2` limit, "No breaking change", HACS update from 1.0.0, minimum HA 2026.9.0 |
| `09-UAT.md` | completed ledger | ✓ VERIFIED | `status: complete`, REL-01 pass, ACCEPTED-GAP-V101 closed |
| `.planning/PROJECT.md` | ACCEPTED-GAP-V101 row closed | ✓ VERIFIED | line 95 closed with SHA, tag, date; status paragraph line 13; HACS row line 86 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| 9.2 `build.txt` sha | `refs/tags/v1.0.1` | lightweight tag pushed by owner | ✓ WIRED | both 3dc9093 (live ls-remote) |
| `refs/tags/v1.0.1` | `release.yml` | `on.push.tags: "v*.*.*"` | ✓ WIRED | run 38824818079 triggered by the tag push |
| `refs/tags/v1.0.1` | `release-run.json` | headSha filter | ✓ WIRED | headSha 3dc9093 |
| `release-notes.md` | GitHub release body | `gh release edit --notes-file` | ✓ WIRED | `notes-applied.txt`; live body equal (gsd-tools pattern miss only because the target is not a file) |
| `~/ha-test/phase9.2.env` | 9.2 evidence root | `PHASE8_EVIDENCE_ROOT` | ✓ WIRED | env file points at `09.2-evidence` (re-pointed equivalent of `phase9.env`) |
| `09-UAT.md` | `PROJECT.md` | Key Decision row cites the ledger | ✓ WIRED | row 95 names `09-UAT.md` |

gsd-tools `verify.key-links` reports the links whose `from` is not a repo file (`~/ha-test/...`, `refs/...`, `origin refs/heads/main`) as unverifiable; each one was checked by hand above.

### Data-Flow Trace (Level 4)

Not applicable (release phase, no rendered dynamic data).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Tag on FIX on origin | `git ls-remote origin refs/tags/v1.0.1` | `3dc9093… refs/tags/v1.0.1` | ✓ PASS |
| Manifest at tag | `git show 3dc9093:custom_components/mqtt_actions/manifest.json` | `"version": "1.0.1"` | ✓ PASS |
| Release run green | `gh run view 38824818079` | success, 8/8 jobs success, headSha FIX | ✓ PASS |
| Latest release | `gh api repos/:owner/:repo/releases/latest` | v1.0.1 | ✓ PASS |
| Mounted bench tree == FIX | sha256 of `git show 3dc9093:<file>` vs `mount-hashes.txt` | 4/4 match on ha-a and ha-b | ✓ PASS |
| Nothing but `.planning` after FIX | `git diff --stat 3dc9093 HEAD -- . ':!.planning'` | empty | ✓ PASS |

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` in the repo; the bench check scripts live in `~/ha-test/bin/` and were not re-run (read-only verification, bench state must not change). Their committed verdicts on FIX are the evidence.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REL-01 | 09-01 to 09-05 | v1.0.1 tagged on the commit whose manifest says 1.0.1, after UAT-02 and UAT-04 pass on exactly that SHA; release workflow, hassfest and HACS green; closes ACCEPTED-GAP-V101 | ✓ SATISFIED | Truths 1 to 3; REQUIREMENTS.md marks it `[x]` and Complete |

No orphaned requirements: REQUIREMENTS.md maps only REL-01 to Phase 9.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `custom_components/` at 3dc9093 | – | TBD/FIXME/XXX | – | none found |
| `.planning/phases/09-v1-0-1-release/09-UAT.md` | 19-33 | "Build under test" header still names 7baec98; FIX is in the sub-section at line 74 | ℹ️ Info | readability only |
| `.planning/PROJECT.md` | 49 | Active item "Release v1.0.1 …" still `[ ]` | ℹ️ Info | left to the orchestrator's phase transition (09-05-SUMMARY) |
| `.planning/STATE.md` | 340 | "Operator Next Steps" still says start Phase 9 | ℹ️ Info | stale hint |
| `.planning/ROADMAP.md` | 42, 242 | Phase 9.1 still `[ ]` / In Progress | ℹ️ Info | outside Phase 9 scope |
| `.github/workflows/ci.yml`, `validate.yml` | – | branch pushes do not trigger CI (todo `2026-10-12-ci-push-trigger-branches.md`) | ℹ️ Info | known follow-up after the tag |

### Human Verification Required

### 1. Owner-only pushes and workflow actions

**Test:** Confirm that you pushed 7baec98 to main and the tag v1.0.1 on 3dc9093 yourself, and that Claude ran no `git push`, `gh workflow run` or `gh run rerun` in Phase 9.
**Expected:** Yes. Evidence consistent: `push-main.txt`, `tag-push.txt` (`pushed_by: owner`, `claude_push: none`), release run attempt 1.
**Why human:** Who issued a push cannot be proven from repository or GitHub state (judgment-tier prohibitions 09-01 P2, 09-02 P1, 09-04 P2, 09-05 P1).
**Result:** Confirmed by the owner on 2026-10-16.

### 2. Remaining judgment-tier prohibitions

**Test:** Review the Prohibitions table above.
**Expected:** You agree that each one held.
**Why human:** ADR-550 D4: judgment-tier prohibitions are never a silent pass.
**Result:** Confirmed by the owner on 2026-10-16.

### Gaps Summary

No gaps. The phase goal is achieved in live state: tag v1.0.1 on origin points at 3dc9093, whose manifest says 1.0.1; UAT-02 (integration and null tombstones), UAT-04 and the CR-01 gate passed on exactly that SHA with an independently re-checked mount pin; release run 38824818079 is green in all eight jobs; v1.0.1 is Latest with the hand-written notes; ACCEPTED-GAP-V101 is closed for v1.0.1 in the ledger, PROJECT.md and MILESTONES.md. The status is `human_needed` only for the owner confirmations of the judgment-tier prohibitions.

## Acknowledged Gaps

Acknowledged by the owner on 2026-10-16 during `/gsd-verify-work 9`. `09-UAT.md` is left unchanged on purpose (09-03 P1: the
7baec98 FAIL and BLOCKED stand), so `phase uat-passed 09` keeps reporting these two rows:

- Test 3 (UAT-02 on 7baec98, `result: issue`): superseded by blocks 21 and 22 (UAT-02 from integration and null tombstones)
  on the tagged FIX 3dc9093. Its gap reads `status: resolved`, but the fix plans live in Phases 9.1 and 9.2, so the
  `resolved_by` cross-check of the predicate (a plan in this phase directory) cannot match.
- Test 4 (UAT-04 on 7baec98, `result: blocked`): superseded by block 23 (UAT-04) on 3dc9093.

The phase is closed by owner decision despite these two historical rows.

---

_Verified: 2026-10-15T23:50:14Z_
_Verifier: Claude (gsd-verifier)_
