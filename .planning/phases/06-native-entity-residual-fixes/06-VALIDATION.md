---
phase: "06"
slug: "native-entity-residual-fixes"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-04"
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 via pytest-homeassistant-custom-component, asyncio_mode=auto |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_takeover.py tests/test_native_start.py tests/test_native_replay.py tests/test_native_entities.py tests/test_native_cleanup.py tests/test_cutover.py -q` |
| **Full suite command** | `uv run pytest -q && uv run ruff check . && uv run ruff format --check .` |
| **Estimated runtime** | ~105 seconds (full), ~30 seconds (quick) |

---

## Sampling Rate

- **After every task commit:** Run `quick run command`
- **After every plan wave:** Run `full suite command`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 110 seconds

---

## Per-Task Verification Map

Task IDs follow the plans: `06-01-NN` are the tasks of plan 06-01 (IN-02, MIG-04, wave 1), `06-02-NN` the tasks of plan 06-02 (IN-03, MIG-05, README, wave 2). Commands use `uv run pytest`, which works in any checkout (the equivalent of `.venv/bin/python -m pytest` in the main tree). Behaviors come from 06-RESEARCH.md "Validation Architecture".

| Task ID | Plan | Wave | Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|----------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | MIG-04 | Tracer: mirror at exactly MAX_DOCUMENT_BYTES stays native after restart, no test-topic subscription, no reload; set parsing; 1.0.0 Store compatibility | unit | `uv run pytest tests/test_native_start.py -k "at_the_size_limit or native_mirror_set" -q` | ❌ W0 (RED commit creates the tests) | ⬜ pending |
| 06-01-02 | 01 | 1 | MIG-04 | Set lifecycle (tombstone, adoption, stale id, failed adoption), parser guard, marker writer removed | unit | `uv run pytest tests/test_native_start.py -k native_mirror_set -q` | ❌ W0 (RED commit creates the tests) | ⬜ pending |
| 06-01-02 | 01 | 1 | MIG-04 | Store shape unchanged when the set is empty; marker-only payload assertion moved to the set | unit | `uv run pytest tests/test_cutover.py tests/test_native_entities.py -q` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 2 | MIG-05 | Tracer: replay before and after the clear, native mirror, finished owner with two restarts: no duplicate after the quiet period, ids kept, no publish by the catch | unit | `uv run pytest tests/test_native_replay.py tests/test_takeover.py -k replay -q` | ❌ W0 (RED commit creates `tests/test_native_replay.py`) | ⬜ pending |
| 06-02-01 | 02 | 2 | MIG-05 | Registry-only helper: loaded duplicates removed, entry without twin, older legacy entry, foreign entity, no legacy device | unit | `uv run pytest tests/test_takeover.py -k remove_replay_twins -q` | ❌ W0 (added with the fix) | ⬜ pending |
| 06-02-02 | 02 | 2 | MIG-05 | Catch right after the registry move: nothing left when the retained clear goes out | unit | `uv run pytest tests/test_native_replay.py -q` | ❌ W0 (RED commit) | ⬜ pending |
| 06-02-03 | 02 | 2 | MIG-04, MIG-05 | README Limitations no longer lists the residuals; pinned phrases stay | doc | `uv run pytest tests/test_docs.py -k "limitations" -q` | ✅ (new test added by the task) | ⬜ pending |

*Status: ⬜ pending*

---

## Wave 0 Requirements

- [ ] New tests above (TDD `test(06-NN)` commits, red on the 1.0.0 production code; the fix commits are `fix(06-NN)`)
- [ ] No `tests/conftest.py` change: the quiet period is an `async_call_later` timer that the tests fire with `async_fire_time_changed` (a sleep would hang under the `freezer` fixture; verified)
- [ ] `tests/test_native_start.py`: `_loop_back_discovery` hands an empty payload on instead of None (core's removal of a loaded duplicate publishes None)

---

## Manual-Only Verifications

All phase behaviors have automated verification. The real boot-time race is deferred to Phase 8 UAT-02.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 110s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** {pending / approved YYYY-MM-DD}
