---
phase: "08"
slug: "real-instance-verification"
status: planned
nyquist_compliant: true
wave_0_complete: true
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
| 08-01-T1 | 01 | 1 | UAT-01..04 (bench) | T-08-01, T-08-03, T-08-05 | guard cannot reach production; pinned build runs; broker round trip with a second client | tracer, end to end | `~/ha-test/bin/check-preflight.sh` | ✅ | ✅ green |
| 08-01-T2 | 01 | 1 | UAT-01..04 (ledger) | T-08-02 | ledger skeleton, no secret in evidence | scripted | `~/ha-test/bin/check-recorded.sh --skeleton` | ✅ | ✅ green |
| 08-01-T3 | 01 | 1 | — | T-08-02 | tokens decided by the owner, never in the repo | decision checkpoint | none (owner) | n/a | ✅ green |
| 08-02-T1 | 02 | 2 | UAT-02 | T-08-06, T-08-07 | no `mqtt` platform entry and no `_2` after two startup rounds on ha-a and ha-b | automated | `~/ha-test/bin/check-recorded.sh UAT-02` and `~/ha-test/bin/check-uat02.sh clean` | ✅ | ✅ green |
| 08-02-T2 | 02 | 2 | UAT-02 | — | WR-03 live-republish classified by the owner | decision checkpoint | none (owner) | n/a | ✅ green |
| 08-02-T3 | 02 | 2 | UAT-02 | T-08-06 | bench back at baseline | automated | `~/ha-test/bin/check-recorded.sh UAT-02 && ~/ha-test/bin/check-uat02.sh clean && ~/ha-test/bin/check-preflight.sh --quick` | ✅ | ✅ green |
| 08-03-T1 | 03 | 3 | UAT-03 | T-08-08 | inert marker fixture, mirror unapproved | automated | `~/ha-test/bin/check-marker.sh pending` | ✅ | ✅ green |
| 08-03-T2 | 03 | 3 | UAT-03 | T-08-09 | one run per approved instance, unknown payload ignored (non-retained) | automated | `~/ha-test/bin/check-recorded.sh UAT-03` | ✅ | ✅ green |
| 08-03-T3 | 03 | 3 | UAT-03 (P1-5, criterion 6) | T-08-10 | replayed state runs nothing; positive control runs once | automated | `~/ha-test/bin/check-recorded.sh P1-5 && ~/ha-test/bin/check-preflight.sh --quick` | ✅ | ✅ green |
| 08-04-T1 | 04 | 4 | UAT-04 | T-08-11, T-08-12 | export shape, core-prefix disabled duplicates, off clears | automated | `~/ha-test/bin/check-recorded.sh UAT-04` and `~/ha-test/bin/check-uat04.sh clean` | ✅ | ✅ green (recorded; UAT-04 result is issue, Gaps entry test: 4) |
| 08-04-T2 | 04 | 4 | UAT-04 | T-08-11 | restart cleanup observed, re-run entry, stale anchor | automated | `~/ha-test/bin/run-all-scripted.sh --list && ~/ha-test/bin/run-all-scripted.sh --dry-run && ~/ha-test/bin/check-stale-anchor.sh` | ✅ | ✅ green |
| 08-05-T1 | 05 | 5 | UAT-01 | — | wording of the mode-select question fixed before the run | decision checkpoint | none (owner) | n/a | ✅ green |
| 08-05-T2 | 05 | 5 | UAT-01 | T-08-13, T-08-14, T-08-SC | v0.1.0 byte-identical, per-instance ACL line read back, secrets outside repo | automated | `~/ha-test/bin/check-hac.sh ready` | ✅ | ✅ green |
| 08-05-T3 | 05 | 5 | UAT-01 | T-08-15 | straggler runs actions once, no entities, no error; stopped and offline | automated | `~/ha-test/bin/check-recorded.sh UAT-01` and `~/ha-test/bin/check-hac.sh stopped` | ✅ | ✅ green |
| 08-06-T1 | 06 | 6 | criterion 6 (P1-3, P1-4, P3-2) | T-08-16, T-08-17, T-08-18 | inert hostile inputs, browser limited to localhost | browser MCP plus script | `~/ha-test/bin/check-frontend.sh prep p1-3 p1-4 p3-2` | ✅ | ✅ green |
| 08-06-T2 | 06 | 6 | criterion 6 | — | rendering and wording judged by the owner | human-verify checkpoint | none (owner) | n/a | ✅ green |
| 08-06-T3 | 06 | 6 | criterion 6 | T-08-16 | results recorded, throwaway devices removed | automated | `~/ha-test/bin/check-recorded.sh P1-3 && ~/ha-test/bin/check-recorded.sh P1-4 && ~/ha-test/bin/check-recorded.sh P3-2` | ✅ | ✅ green |
| 08-07-T1 | 07 | 7 | criterion 6 (P2-1, P2-2) | T-08-19, T-08-21 | breaker bounded, paused across restart, released by reload | browser MCP plus script | `~/ha-test/bin/check-frontend.sh prep p2-1 p2-2` | ✅ | ✅ green |
| 08-07-T2 | 07 | 7 | criterion 6 | — | select flow and breaker card rendering (EN, DE) judged by the owner | human-verify checkpoint | none (owner) | n/a | ✅ green |
| 08-07-T3 | 07 | 7 | criterion 6 | T-08-21 | results recorded, loop device deleted, no approval on ha-b | automated | `~/ha-test/bin/check-recorded.sh P2-1 && ~/ha-test/bin/check-recorded.sh P2-2` | ✅ | ✅ green |
| 08-08-T1 | 08 | 8 | criterion 6 (P1-2, P3-1) | T-08-22, T-08-23, T-08-24 | ha-b backed up first, new instance id gets its ACL line, hostile device never approved | browser MCP plus script | `~/ha-test/bin/check-frontend.sh prep p1-2 p3-1 && ~/ha-test/bin/check-preflight.sh --quick` | ✅ | ✅ green |
| 08-08-T2 | 08 | 8 | criterion 6 | — | strings and approval rendering (EN, DE) judged by the owner | human-verify checkpoint | none (owner) | n/a | ✅ green |
| 08-08-T3 | 08 | 8 | criterion 6 | T-08-24 | results recorded, hostile device deleted | automated | `~/ha-test/bin/check-recorded.sh P1-2 && ~/ha-test/bin/check-recorded.sh P3-1` | ✅ | ✅ green |
| 08-09-T1 | 09 | 9 | criterion 6 (P1-1) | T-08-25 | production host and install path chosen by the owner | decision checkpoint | none (owner) | n/a | ✅ green |
| 08-09-T2 | 09 | 9 | criterion 6 (P1-1, P1-6) | T-08-25, T-08-26, T-08-27 | add and remove only, own base topic, hosts by role | human-verify checkpoint | none (owner, production) | n/a | ✅ green |
| 08-09-T3 | 09 | 9 | criterion 6 | T-08-27, T-08-SC | installed release identity proven, results recorded | automated | `~/ha-test/bin/check-recorded.sh P1-1 && ~/ha-test/bin/check-recorded.sh P1-6` | ✅ | ✅ green |
| 08-10-T1 | 10 | 10 | UAT-01..04, criterion 5 | T-08-29, T-08-30 | ledger complete, nothing stale, scripts archived without secrets | automated | `~/ha-test/bin/check-final.sh --pre` | ✅ | ✅ green (check-final.sh --pre PASS, 2026-10-07) |
| 08-10-T2 | 10 | 10 | criterion 6 (D-06) | T-08-28 | verifier regenerates Phase 1 to 3 reports; overrides only in the owner's name | orchestrator-run checkpoint | none (verifier) | n/a | ⬜ pending (Task 2: owner question and verifier runs by the orchestrator) |
| 08-10-T3 | 10 | 10 | criterion 6 (D-06) | T-08-28 | report status equals what the ledger allows; Phase 4 passed | automated | `~/ha-test/bin/check-final.sh` and `~/ha-test/bin/check-final.sh --commit-shape` | ✅ | ⬜ pending (Task 3: after the verifier) |
| 08-11-T1 | 11 | 11 | UAT-04 (gap) | T-08-31, T-08-32, T-08-33 | fresh device exported on the core prefix, both live registries read before any restart, bench back at baseline | tracer, end to end | `~/ha-test/bin/check-uat04-iso.sh verify --tracer` and `~/ha-test/bin/check-uat02.sh clean && ~/ha-test/bin/check-uat04.sh clean && ~/ha-test/bin/check-preflight.sh --quick` | ✅ | ✅ green (tracer PASS, plan 08-11) |
| 08-11-T2 | 11 | 11 | UAT-04 (gap) | T-08-31, T-08-33, T-08-34 | both arms in one window, tombstone proven from flushed registry files, classification from observed values | automated | `~/ha-test/bin/check-uat04-iso.sh verify` and `~/ha-test/bin/check-stale-anchor.sh` | ✅ | ✅ green (classification TOMBSTONE-ONLY, plan 08-11) |
| 08-11-T3 | 11 | 11 | UAT-04 (gap) | T-08-34 | owner decision (incl. re-run scope and not-affected confirmation) recorded under its own id, never assumed | decision checkpoint | `~/ha-test/bin/check-uat04-iso.sh disposition` and `~/ha-test/bin/check-recorded.sh --all` | ✅ | ✅ green (UAT04-GAP-DISPOSITION recorded, plan 08-11) |
| 08-12-T1 | 12 | 12 | UAT-04 (gap) | T-08-44 | owner's D-08 waiver recorded before any product edit; original D-08 text intact | automated | `grep -q D08-WAIVER` over 08-UAT.md, 08-CONTEXT.md and the ROADMAP, and `~/ha-test/bin/check-recorded.sh --all` | ✅ | ✅ green (D08-WAIVER recorded, plan 08-12) |
| 08-12-T2 | 12 | 12 | UAT-04 (gap) | T-08-35, T-08-36 | guard test-first, registry-only, public API only, foreign rows untouched; a missing disposition fails (conditional on the decision) | tdd, unit and broker tiers | `~/ha-test/bin/check-uat04-iso.sh disposition`, then `uv run --locked pytest -q -p no:cacheprovider tests/test_discovery_export.py tests/test_native_replay.py tests/test_takeover.py` (plus the full not-broker and broker suites and ruff, see the plan) | ✅ | ✅ green (guard test-first, selected: guard-and-document) |
| 08-12-T3 | 12 | 12 | UAT-04 (gap) | T-08-37 | documentation states only what the evidence shows, pinned sentences intact (conditional on the decision) | automated | `~/ha-test/bin/check-uat04-iso.sh disposition`, then `uv run --locked pytest -q -p no:cacheprovider tests/test_docs.py tests/test_translations.py` | ✅ | ✅ green (README and troubleshooting, selected) |
| 08-13-T1 | 13 | 13 | UAT-04 (gap) | T-08-38, T-08-40, T-08-41 | prune with copies and checks, or re-pin; expectation blocks of the scripts unchanged | automated | `~/ha-test/bin/check-uat04-iso.sh disposition`, `~/ha-test/bin/check-preflight.sh --quick` and `~/ha-test/bin/check-uat02.sh clean` | ✅ | ✅ green (re-pin and script patches, plan 08-13) |
| 08-13-T2 | 13 | 13 | UAT-04 | T-08-40 | re-run beside the first run, evidence only, a FAIL is kept as evidence | automated | `~/ha-test/bin/check-uat04-iso.sh disposition` and `grep -q -x -E "(PASS|FAIL)"` over `uat-04-rerun/verdict.txt` | ✅ | ✅ green (re-run evidence in uat-04-rerun; its FAIL kept as history, superseded by 08-18) |
| 08-16-T1 | 16 | 14 | UAT-04 (gap) | T-08-46 | owner decides the extension of the D-08 waiver to the receiver-side guard and re-confirms the not-affected list, no default assumed (blocking-human) | decision checkpoint | `sed -n 1p .planning/phases/08-real-instance-verification/08-evidence/uat-04-receiver-guard/decision.txt` names one of the three option ids | ✅ | ✅ green (UAT04-RECEIVER-GUARD recorded, plan 08-16) |
| 08-16-T2 | 16 | 14 | UAT-04 (gap) | T-08-46, T-08-47 | decision, extended waiver and the failed 08-13 re-run recorded before any product edit; original D-08 text and first amendment intact | automated | `grep -q UAT04-RECEIVER-GUARD` over 08-UAT.md, 08-CONTEXT.md and the ROADMAP, and `~/ha-test/bin/check-recorded.sh --all` | ✅ | ✅ green (decision and 08-13 history recorded, plan 08-16) |
| 08-17-T1 | 17 | 15 | UAT-04 (gap) | T-08-48, T-08-49, T-08-50 | tracer: a receiver that does not export disables the duplicate restored from a null tombstone; the guard no longer depends on the export option; RED first | tdd tracer, unit tier | `uv run --locked pytest -q -p no:cacheprovider tests/test_export_guard_receiver.py tests/test_discovery_export.py tests/test_native_replay.py tests/test_takeover.py tests/test_native_start.py` | ✅ | ✅ green (tracer, plan 08-17) |
| 08-17-T2 | 17 | 15 | UAT-04 (gap) | T-08-48, T-08-49, T-08-50, T-08-52 | twin interlock, both orders, content-free log line, trust matrix, idempotence, fresh install, export-off cycle; full regression gate | tdd, unit and broker tiers | `uv run --locked pytest -q -p no:cacheprovider -n 6 -m "not broker"`, `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider -m broker`, `uv run ruff check .` | ✅ | ✅ green (receiver-side guard, plan 08-17) |
| 08-17-T3 | 17 | 15 | UAT-04 (gap) | T-08-51 | README and troubleshooting state only the tested behavior, pinned sentences intact | automated | `uv run --locked pytest -q -p no:cacheprovider tests/test_docs.py tests/test_translations.py` | ✅ | ✅ green (README and troubleshooting, plan 08-17) |
| 08-18-T1 | 18 | 16 | UAT-04 (gap) | T-08-53, T-08-55, T-08-56 | re-pin to the receiver-guard build, leftovers cleared by the product's own restart cleanup, check scripts byte-identical, restoration script proven read-only | automated | `~/ha-test/bin/check-preflight.sh --quick`, `~/ha-test/bin/check-uat02.sh clean` and `~/ha-test/bin/check-stale-anchor.sh` | ✅ | ✅ green (re-pin to b8232252, plan 08-18) |
| 08-18-T2 | 18 | 16 | UAT-02, UAT-03, UAT-04 (P1-5, criterion 6) | T-08-53, T-08-54, T-08-55, T-08-56 | the whole scripted group on the new build, failing tombstone state restored before UAT-04, earlier evidence untouched, a FAIL stands | automated | `grep -q -x -E "(PASS|FAIL)"` over the first line of the four `-rerun2` verdict files and the exact regression-state line in `uat-04-rerun2/prepare.txt` | ✅ | ✅ green (-rerun2 group PASS, plan 08-18) |
| 08-14-T1 | 14 | 17 | UAT-04 | T-08-39, T-08-45 | re-run recorded as observed, pruned-state qualifier carried, not-affected list tied to the owner's confirmation | automated | `~/ha-test/bin/check-recorded.sh UAT-04` and `~/ha-test/bin/check-recorded.sh --all` | ✅ | ✅ green (block 4 and re-run blocks recorded, plan 08-14) |
| 08-14-T2 | 14 | 17 | UAT-01..04 (traceability) | T-08-39 | REQUIREMENTS.md agrees with the ledger verdicts and carries the qualifier | automated | `~/ha-test/bin/check-recorded.sh --all` and the traceability check of the plan | ✅ | ✅ green (traceability updated, plan 08-14) |
| 08-15-T1 | 15 | 18 | UAT-04 | T-08-42, T-08-43 | final gate understands a resolved gap and a qualified verdict, anchor file and script copy current and clean | automated | `~/ha-test/bin/check-final.sh --pre` and `~/ha-test/bin/check-stale-anchor.sh` | ✅ | ✅ green (gate, anchor, bench state and script copy finalized, commit f65a174) |
| 08-15-T2 | 15 | 18 | UAT-04, criterion 6 (D-06) | T-08-42 | verifier re-run or dated digest refresh, never by hand; the report states the qualifier | orchestrator-run checkpoint | none (verifier) | n/a | ✅ green (Phases 1 to 4 re-run by gsd-verifier, Phase 8 re-verified, 0 hand digest refreshes) |
| 08-15-T3 | 15 | 18 | UAT-04, criterion 6 (D-06) | T-08-42 | archived Phase 1 to 4 reports read passed, Phase 8 report reads what the ledger allows | automated | `~/ha-test/bin/check-final.sh` and `~/ha-test/bin/check-final.sh --commit-shape` | ✅ | ✅ green (check-final.sh and --commit-shape PASS; Phases 1 to 4 and 8 read passed) |

*Planner filled Task IDs. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. "criterion 6" is ROADMAP success criterion 6 (the ten human items), which has no requirement id.*

---

## Wave 0 Requirements

Wave 0 is plan 08-01; the scripts and the ledger it creates are what every later verify command calls.

- [x] `~/ha-test/bin/` helper scripts: `lib.sh`, `ha-test-guard` (never ha-ws, never production), `ha-test-ws.py`, `bench-users.sh`, `preflight.sh`, `check-preflight.sh`, `check-evidence-clean.sh`, `check-recorded.sh` (plan 08-01); the per-check scripts are written inside the plan that runs them, with the expected values coded before anything is observed (08-02 to 08-08), `run-all-scripted.sh` and `check-stale-anchor.sh` (08-04), `check-final.sh` (08-10)
- [x] Backup of `~/ha-test/{a,b,mosquitto}` before the first restart (plan 08-01); ha-b again before its hub is removed (plan 08-08)
- [x] ACL: bench users `uat_probe` and `uat_bridge` (08-01); export prefix rows for `ha_one` and `ha_two` (08-04); user `ha_three` with its per-instance block (08-05); availability line for ha-b's new instance id (08-08)
- [x] `ha-c` container, config dir, onboarding, MQTT entry (plan 08-05)
- [x] Tokens for ha-a and ha-b (owner decision in 08-01 Task 3), ha-c by script (08-05)
- [x] Marker device `UAT Marker` on ha-a (`system_log.write`, level `warning`) (plan 08-03)
- [x] `08-UAT.md` skeleton, all 14 blocks at `result: pending` (plan 08-01 Task 2)

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

**Approval:** Wave 0 executed by plan 08-01 on 2026-10-04 (ha-c and the later check scripts by plans 08-02 to 08-10); Status column filled by plan 08-10 Task 1 on 2026-10-07 from the recorded results in 08-UAT.md (13 pass, 1 issue: UAT-04, Gaps entry test 4); nyquist_compliant: true re-confirmed (every row has an automated command or is an owner checkpoint, and an evidence path under 08-evidence); Tasks 2 and 3 of plan 08-10 stay pending until the verifier has run
