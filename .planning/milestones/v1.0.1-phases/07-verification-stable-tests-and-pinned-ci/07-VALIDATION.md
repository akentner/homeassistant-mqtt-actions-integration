---
phase: "7"
slug: "verification-stable-tests-and-pinned-ci"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: true
created: "2026-10-04"
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + PHACC 0.13.367 |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run --locked pytest -q -p no:cacheprovider tests/test_repo_structure.py tests/test_log_helpers.py tests/test_manager_breaker.py tests/test_modes.py` |
| **Full suite command** | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider && uv run ruff check . && uv run ruff format --check .` |
| **Estimated runtime** | ~7 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 7 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | QLT-03 | T-07-01, T-07-02, T-07-03 | Every job pinned to `ubuntu-24.04`; guard reads the whole workflow directory; red before the pin | unit (TDD) | `uv run pytest tests/test_repo_structure.py -q` | ✅ test created by the RED commit | ⬜ pending |
| 7-01-02 | 01 | 1 | QLT-03 | T-07-02 | Guard rejects a floating label, two versions, a non-string runner, an empty directory; skips caller jobs | unit (tmp_path, mutation check) | `uv run --locked pytest -q -p no:cacheprovider tests/test_repo_structure.py -k "pinned_runner or workflow_runners"` | ✅ | ⬜ pending |
| 7-02-01 | 02 | 1 | QLT-02 | T-07-04, T-07-06 | Always-slow probe red on exactly two tests, green after own-logger scoping; no production change | probe + unit (TDD) | `uv run --locked pytest -q -p no:cacheprovider -n 6 -m "not broker"` | ✅ fixture created by the RED commit | ⬜ pending |
| 7-02-02 | 02 | 1 | QLT-02 | T-07-04 | The last negative log check is scoped to the integration's loggers | unit | `uv run --locked pytest -q -p no:cacheprovider tests/test_hub_removal.py tests/test_log_helpers.py` | ✅ | ⬜ pending |
| 7-02-03 | 02 | 1 | QLT-02 | T-07-05 | 50 consecutive repetitions of the named test under CPU load, probe on, no busy loop left | stress loop | bash loop in the plan (taskset plus four busy loops, 50 runs) | ✅ | ⬜ pending |
| 7-03-01 | 03 | 2 | QLT-02 | — | Three consecutive full-suite runs, broker tier mandatory, no skip | full suite x3 | bash loop in the plan (`MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider` three times, then Ruff) | ✅ | ⬜ pending |
| 7-03-02 | 03 | 2 | QLT-03 | T-07-07 | Owner decides merge order and push (checkpoint:decision) | manual | n/a (decision recorded in the SUMMARY) | n/a | ⬜ pending |
| 7-03-03 | 03 | 2 | QLT-03 | T-07-08 | CI x3 and Validate x1 green on the pushed sha on `ubuntu-24.04` | CI | `gh run list --workflow ci.yml --event workflow_dispatch --branch BRANCH --limit 3` (script in the plan) | n/a (recorded in 07-PROOF.md) | ⬜ pending |
| 7-04-01 | 04 | 3 | QLT-03 | T-07-09 | Explicit blocking-human approval before the tag push | manual | n/a (answer recorded in the SUMMARY) | n/a | ⬜ pending |
| 7-04-02 | 04 | 3 | QLT-03 | T-07-09, T-07-10, T-07-11 | `release.yml` run for `v1.0.1-rc1` passes all eight jobs on the pinned runner; release is a prerelease | CI | `gh run list --workflow release.yml --branch v1.0.1-rc1 --limit 1` (script in the plan) | n/a (recorded in 07-PROOF.md) | ⬜ pending |
| 7-04-03 | 04 | 3 | QLT-03 | T-07-09, T-07-12 | Release and tags deleted, manifest byte-identical to 1.0.0 locally and on the remote branch | script | `git ls-remote --tags origin v1.0.1-rc1` and `git diff --quiet PRE -- custom_components/mqtt_actions/manifest.json` (script in the plan) | n/a | ⬜ pending |
| 7-05-01 | 05 | 4 | QLT-01 | T-07-14 | Clean frozen tree, before state of the four reports recorded | tooling | `node ~/.claude/gsd-core/bin/gsd-tools.cjs verification status ARCHIVED_DIR --pick status` | n/a | ⬜ pending |
| 7-05-02 | 05 | 4 | QLT-01 | T-07-13 | Orchestrator spawns gsd-verifier four times with the archived PHASE_DIR (checkpoint:human-action) | manual (orchestrator) | n/a (reports are written by the verifier) | n/a | ⬜ pending |
| 7-05-03 | 05 | 4 | QLT-01 | T-07-13, T-07-14 | `verification status` prints `passed` for Phases 1 to 4; nothing else changed | tooling | `node ~/.claude/gsd-core/bin/gsd-tools.cjs verification status ARCHIVED_DIR --pick status` for each of 01 to 04 | overwritten by the verifier | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The red tests are created by the TDD tasks themselves (the guard test in plan 07-01, the always-slow fixture in plan 07-02); there is no stub-only Wave 0 step and no framework to install.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Merge order and push of the Phase 6 and 7 branch (plan 07-03, Task 2) | QLT-03 | A push publishes commits; the owner decides, nothing is assumed | Answer the checkpoint:decision with push-branch-as-is, separate-remote-branch, merge-phase-6-first or no-push |
| Push of the prerelease tag `v1.0.1-rc1` (plan 07-04, Task 1) | QLT-03 | A public GitHub release is created in the HACS repository; `gate="blocking-human"`, never auto-approved (D-13) | Type approve or reject at the checkpoint |
| Spawn of the `gsd-verifier` agent for Phases 1 to 4 (plan 07-05, Task 2) | QLT-01 | An executor subagent may be unable to spawn agents, so the orchestrator performs the four spawns (D-01) | Spawn per the contract in the plan, then resume with done or blocked |

Every other behavior of the phase has an automated command or a recorded CI run.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 7s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** {pending / approved YYYY-MM-DD}
