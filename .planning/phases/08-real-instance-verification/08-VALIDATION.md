---
phase: "08"
slug: "real-instance-verification"
status: planned
nyquist_compliant: true
wave_0_complete: false
created: "2026-10-04"
---

# Phase 08 — Validation Strategy

> Per-phase validation contract. No code changes: checks are bench scripts plus owner-signed results in `08-UAT.md`.
> Source: `08-RESEARCH.md` § Validation Architecture. Task IDs filled by the planner (10 plans, strictly sequential waves 1 to 10).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash bench scripts printing `PASS`/`FAIL`/`ABORT` plus evidence path; existing pytest suite only as stale anchor |
| **Config file** | none — Wave 0 (plan 08-01) creates `~/ha-test/bin/` helpers outside the repo |
| **Quick run command** | `~/ha-test/bin/check-<id>.sh` (per check); `~/ha-test/bin/check-preflight.sh --quick` (build and bench gate before every plan) |
| **Full suite command** | `~/ha-test/bin/run-all-scripted.sh` (UAT-02, UAT-03, P1-5, UAT-04; created in plan 08-04) |
| **Final gate** | `~/ha-test/bin/check-final.sh` (ledger complete, Phase 1 to 4 report status as allowed, stale anchor empty, evidence clean; created in plan 08-10) |
| **Estimated runtime** | ~120 seconds of scripted checks per group plus restarts and 60 s settle waits; frontend and production items are owner-paced |

---

## Sampling Rate

- **After every task commit:** the task's `check-*.sh` and `check-evidence-clean.sh` over its evidence folder
- **After every plan wave:** `check-preflight.sh --quick` (SHA, sha256 host vs container, containers Up, probe round trip) and, for broker groups, the ACL read-back
- **Before `/gsd-verify-work`:** no `result: pending` in `08-UAT.md` (`check-recorded.sh --all`); stale anchor empty (`check-stale-anchor.sh`); `check-final.sh` PASS
- **Max feedback latency:** 120 seconds per scripted check (settle waits of 60 to 90 s are part of the check, not feedback latency)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-T1 | 01 | 1 | UAT-01..04 (bench) | T-08-01, T-08-03, T-08-05 | guard cannot reach production; pinned build runs; broker round trip with a second client | tracer, end to end | `~/ha-test/bin/check-preflight.sh` | ❌ W0 (created by this task) | ⬜ pending |
| 08-01-T2 | 01 | 1 | UAT-01..04 (ledger) | T-08-02 | ledger skeleton, no secret in evidence | scripted | `~/ha-test/bin/check-recorded.sh --skeleton` | ❌ W0 | ⬜ pending |
| 08-01-T3 | 01 | 1 | — | T-08-02 | tokens decided by the owner, never in the repo | decision checkpoint | none (owner) | n/a | ⬜ pending |
| 08-02-T1 | 02 | 2 | UAT-02 | T-08-06, T-08-07 | no `mqtt` platform entry and no `_2` after two startup rounds on ha-a and ha-b | automated | `~/ha-test/bin/check-recorded.sh UAT-02` and `~/ha-test/bin/check-uat02.sh clean` | ❌ W0 | ⬜ pending |
| 08-02-T2 | 02 | 2 | UAT-02 | — | WR-03 live-republish classified by the owner | decision checkpoint | none (owner) | n/a | ⬜ pending |
| 08-02-T3 | 02 | 2 | UAT-02 | T-08-06 | bench back at baseline | automated | `~/ha-test/bin/check-recorded.sh UAT-02 && ~/ha-test/bin/check-uat02.sh clean && ~/ha-test/bin/check-preflight.sh --quick` | ❌ W0 | ⬜ pending |
| 08-03-T1 | 03 | 3 | UAT-03 | T-08-08 | inert marker fixture, mirror unapproved | automated | `~/ha-test/bin/check-marker.sh pending` | ❌ W0 | ⬜ pending |
| 08-03-T2 | 03 | 3 | UAT-03 | T-08-09 | one run per approved instance, unknown payload ignored (non-retained) | automated | `~/ha-test/bin/check-recorded.sh UAT-03` | ❌ W0 | ⬜ pending |
| 08-03-T3 | 03 | 3 | UAT-03 (P1-5, criterion 6) | T-08-10 | replayed state runs nothing; positive control runs once | automated | `~/ha-test/bin/check-recorded.sh P1-5 && ~/ha-test/bin/check-preflight.sh --quick` | ❌ W0 | ⬜ pending |
| 08-04-T1 | 04 | 4 | UAT-04 | T-08-11, T-08-12 | export shape, core-prefix disabled duplicates, off clears | automated | `~/ha-test/bin/check-recorded.sh UAT-04` and `~/ha-test/bin/check-uat04.sh clean` | ❌ W0 | ⬜ pending |
| 08-04-T2 | 04 | 4 | UAT-04 | T-08-11 | restart cleanup observed, re-run entry, stale anchor | automated | `~/ha-test/bin/run-all-scripted.sh --list && ~/ha-test/bin/run-all-scripted.sh --dry-run && ~/ha-test/bin/check-stale-anchor.sh` | ❌ W0 | ⬜ pending |
| 08-05-T1 | 05 | 5 | UAT-01 | — | wording of the mode-select question fixed before the run | decision checkpoint | none (owner) | n/a | ⬜ pending |
| 08-05-T2 | 05 | 5 | UAT-01 | T-08-13, T-08-14, T-08-SC | v0.1.0 byte-identical, per-instance ACL line read back, secrets outside repo | automated | `~/ha-test/bin/check-hac.sh ready` | ❌ W0 | ⬜ pending |
| 08-05-T3 | 05 | 5 | UAT-01 | T-08-15 | straggler runs actions once, no entities, no error; stopped and offline | automated | `~/ha-test/bin/check-recorded.sh UAT-01` and `~/ha-test/bin/check-hac.sh stopped` | ❌ W0 | ⬜ pending |
| 08-06-T1 | 06 | 6 | criterion 6 (P1-3, P1-4, P3-2) | T-08-16, T-08-17, T-08-18 | inert hostile inputs, browser limited to localhost | browser MCP plus script | `~/ha-test/bin/check-frontend.sh prep p1-3 p1-4 p3-2` | ❌ W0 | ⬜ pending |
| 08-06-T2 | 06 | 6 | criterion 6 | — | rendering and wording judged by the owner | human-verify checkpoint | none (owner) | n/a | ⬜ pending |
| 08-06-T3 | 06 | 6 | criterion 6 | T-08-16 | results recorded, throwaway devices removed | automated | `~/ha-test/bin/check-recorded.sh P1-3 && ~/ha-test/bin/check-recorded.sh P1-4 && ~/ha-test/bin/check-recorded.sh P3-2` | ❌ W0 | ⬜ pending |
| 08-07-T1 | 07 | 7 | criterion 6 (P2-1, P2-2) | T-08-19, T-08-21 | breaker bounded, paused across restart, released by reload | browser MCP plus script | `~/ha-test/bin/check-frontend.sh prep p2-1 p2-2` | ❌ W0 | ⬜ pending |
| 08-07-T2 | 07 | 7 | criterion 6 | — | select flow and breaker card rendering (EN, DE) judged by the owner | human-verify checkpoint | none (owner) | n/a | ⬜ pending |
| 08-07-T3 | 07 | 7 | criterion 6 | T-08-21 | results recorded, loop device deleted, no approval on ha-b | automated | `~/ha-test/bin/check-recorded.sh P2-1 && ~/ha-test/bin/check-recorded.sh P2-2` | ❌ W0 | ⬜ pending |
| 08-08-T1 | 08 | 8 | criterion 6 (P1-2, P3-1) | T-08-22, T-08-23, T-08-24 | ha-b backed up first, new instance id gets its ACL line, hostile device never approved | browser MCP plus script | `~/ha-test/bin/check-frontend.sh prep p1-2 p3-1 && ~/ha-test/bin/check-preflight.sh --quick` | ❌ W0 | ⬜ pending |
| 08-08-T2 | 08 | 8 | criterion 6 | — | strings and approval rendering (EN, DE) judged by the owner | human-verify checkpoint | none (owner) | n/a | ⬜ pending |
| 08-08-T3 | 08 | 8 | criterion 6 | T-08-24 | results recorded, hostile device deleted | automated | `~/ha-test/bin/check-recorded.sh P1-2 && ~/ha-test/bin/check-recorded.sh P3-1` | ❌ W0 | ⬜ pending |
| 08-09-T1 | 09 | 9 | criterion 6 (P1-1) | T-08-25 | production host and install path chosen by the owner | decision checkpoint | none (owner) | n/a | ⬜ pending |
| 08-09-T2 | 09 | 9 | criterion 6 (P1-1, P1-6) | T-08-25, T-08-26, T-08-27 | add and remove only, own base topic, hosts by role | human-verify checkpoint | none (owner, production) | n/a | ⬜ pending |
| 08-09-T3 | 09 | 9 | criterion 6 | T-08-27, T-08-SC | installed release identity proven, results recorded | automated | `~/ha-test/bin/check-recorded.sh P1-1 && ~/ha-test/bin/check-recorded.sh P1-6` | ❌ W0 | ⬜ pending |
| 08-10-T1 | 10 | 10 | UAT-01..04, criterion 5 | T-08-29, T-08-30 | ledger complete, nothing stale, scripts archived without secrets | automated | `~/ha-test/bin/check-final.sh --pre` | ❌ W0 | ⬜ pending |
| 08-10-T2 | 10 | 10 | criterion 6 (D-06) | T-08-28 | verifier regenerates Phase 1 to 3 reports; overrides only in the owner's name | orchestrator-run checkpoint | none (verifier) | n/a | ⬜ pending |
| 08-10-T3 | 10 | 10 | criterion 6 (D-06) | T-08-28 | report status equals what the ledger allows; Phase 4 passed | automated | `~/ha-test/bin/check-final.sh` and `~/ha-test/bin/check-final.sh --commit-shape` | ❌ W0 | ⬜ pending |

*Planner filled Task IDs. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. "criterion 6" is ROADMAP success criterion 6 (the ten human items), which has no requirement id.*

---

## Wave 0 Requirements

Wave 0 is plan 08-01; the scripts and the ledger it creates are what every later verify command calls.

- [ ] `~/ha-test/bin/` helper scripts: `lib.sh`, `ha-test-guard` (never ha-ws, never production), `ha-test-ws.py`, `bench-users.sh`, `preflight.sh`, `check-preflight.sh`, `check-evidence-clean.sh`, `check-recorded.sh` (plan 08-01); the per-check scripts are written inside the plan that runs them, with the expected values coded before anything is observed (08-02 to 08-08), `run-all-scripted.sh` and `check-stale-anchor.sh` (08-04), `check-final.sh` (08-10)
- [ ] Backup of `~/ha-test/{a,b,mosquitto}` before the first restart (plan 08-01); ha-b again before its hub is removed (plan 08-08)
- [ ] ACL: bench users `uat_probe` and `uat_bridge` (08-01); export prefix rows for `ha_one` and `ha_two` (08-04); user `ha_three` with its per-instance block (08-05); availability line for ha-b's new instance id (08-08)
- [ ] `ha-c` container, config dir, onboarding, MQTT entry (plan 08-05)
- [ ] Tokens for ha-a and ha-b (owner decision in 08-01 Task 3), ha-c by script (08-05)
- [ ] Marker device `UAT Marker` on ha-a (`system_log.write`, level `warning`) (plan 08-03)
- [ ] `08-UAT.md` skeleton, all 14 blocks at `result: pending` (plan 08-01 Task 2)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HACS install, host core version (P1-1, P1-6) | Phase 1 deferred | production host, owner only (D-02) | plan 08-09 Task 2; owner performs and reports; Claude records and proves the release identity |
| Frontend rendering, strings, dialogs (P1-2, P1-3, P1-4, P2-1, P2-2 card, P3-1, P3-2) | Phase 1-3 deferred | needs UI judgment | browser MCP screenshots plus owner sign-off in plans 08-06, 08-07, 08-08 |
| Owner decisions: API access, UAT-01 wording, WR-03 classification, production host | Phase 8 open questions | only the owner can decide | checkpoint:decision tasks in 08-01 T3, 08-05 T1, 08-02 T2, 08-09 T1 |

---

## Validation Sign-Off

- [x] All tasks have automated verify or are owner checkpoints (decision, human-verify, orchestrator-run)
- [x] No 3 consecutive tasks without automated verify (longest run: two checkpoints in plan 08-09)
- [x] Wave 0 covers all MISSING references (plan 08-01 creates the shared scripts; each check script is written by the task that first runs it)
- [x] No watch-mode flags
- [x] Feedback latency < 120s per scripted check (settle waits excluded)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (Wave 0 not yet executed; `wave_0_complete` flips in plan 08-10)
