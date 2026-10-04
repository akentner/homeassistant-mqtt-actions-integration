---
phase: "08"
slug: "real-instance-verification"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-04"
---

# Phase 08 — Validation Strategy

> Per-phase validation contract. No code changes: checks are bench scripts plus owner-signed results in `08-UAT.md`.
> Source: `08-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash bench scripts printing `PASS`/`FAIL` plus evidence path; existing pytest suite only as stale anchor |
| **Config file** | none — Wave 0 creates `~/ha-test/bin/` helpers |
| **Quick run command** | `~/ha-test/bin/check-<id>.sh` |
| **Full suite command** | `~/ha-test/bin/run-all-scripted.sh` (UAT-02, UAT-03, P1-5, UAT-04) |
| **Estimated runtime** | ~120 seconds per scripted group |

---

## Sampling Rate

- **After every task commit:** matching `check-*.sh` and evidence folder review
- **After every plan wave:** mount-integrity check (SHA, sha256 host vs container) and ACL read-back
- **Before `/gsd-verify-work`:** no `result: pending` in `08-UAT.md`; stale anchor empty
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-xx-xx | TBD | TBD | UAT-01 | — | v0.1.0 straggler runs actions, no Discovery entities | semi-automated | `check-uat01.sh` | ❌ W0 | ⬜ pending |
| 08-xx-xx | TBD | TBD | UAT-02 | — | no `mqtt` or `_2` entries after two starts | automated | `check-uat02.sh` | ❌ W0 | ⬜ pending |
| 08-xx-xx | TBD | TBD | UAT-03 | — | one run per approved instance; unknown payload ignored | automated | `check-uat03.sh` | ❌ W0 | ⬜ pending |
| 08-xx-xx | TBD | TBD | UAT-04 | — | export shape, core-prefix duplicates disabled, off clears | automated | `check-uat04.sh` | ❌ W0 | ⬜ pending |

*Planner fills Task IDs. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `~/ha-test/bin/` helper scripts (check-*.sh, `ha-test-guard` refusing production URLs)
- [ ] Backup of `~/ha-test/{a,b,mosquitto}`
- [ ] ACL: export prefix row for `ha_one`/`ha_two`; user `ha_three` block
- [ ] `ha-c` container, config dir, onboarding, MQTT entry
- [ ] Tokens for ha-a, ha-b, ha-c
- [ ] Marker device(s) on ha-a (`system_log.write`, level `warning`)
- [ ] `08-UAT.md` skeleton, all 14 blocks at `result: pending`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HACS install, host core version (P1-1, P1-6) | Phase 1 deferred | production host, owner only | owner installs and records result |
| Frontend rendering, strings, dialogs (P1-2..4, P2-1, P3-1, P3-2) | Phase 1-3 deferred | needs UI judgment | browser MCP screenshot plus owner sign-off |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
