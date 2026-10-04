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
| **Quick run command** | `.venv/bin/python -m pytest tests/test_takeover.py tests/test_native_start.py tests/test_native_entities.py tests/test_native_cleanup.py tests/test_cutover.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && .venv/bin/ruff check custom_components tests` |
| **Estimated runtime** | ~105 seconds (full), ~30 seconds (quick) |

---

## Sampling Rate

- **After every task commit:** Run `quick run command`
- **After every plan wave:** Run `full suite command`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 110 seconds

---

## Per-Task Verification Map

Task IDs are finalized by the planner; behaviors and commands come from 06-RESEARCH.md "Validation Architecture".

| Requirement | Behavior | Test Type | Automated Command | File Exists |
|-------------|----------|-----------|-------------------|-------------|
| MIG-04 | Mirror at exactly MAX_DOCUMENT_BYTES stays native after restart, no test-topic subscription, no reload | unit | `pytest tests/test_native_start.py -k at_the_size_limit -x` | ❌ W0 |
| MIG-04 | `mirrors` set parsing, lifecycle, v1.0.0 Store compatibility | unit | `pytest tests/test_native_start.py -k native_mirror_set -x` | ❌ W0 |
| MIG-04 | Store shape unchanged when set is empty | unit | `pytest tests/test_cutover.py -x` | ✅ |
| MIG-05 | Replay before/after clear and between move and catch: no twin, ids kept | unit | `pytest tests/test_native_start.py -k replay -x` | ❌ W0 |
| MIG-05 | Registry-only helper behavior | unit | `pytest tests/test_takeover.py -x` | ❌ W0 |
| MIG-05 | Catch 2 covers all native owners and mirrors | unit | `pytest tests/test_native_start.py -k replay -x` | ❌ W0 |
| Criterion 4 | README no longer lists the residuals | doc | `pytest tests/test_docs.py -x` | ✅ |

*Status: ⬜ pending*

---

## Wave 0 Requirements

- [ ] New tests above (TDD `test:` commits, red on v1.0.0)
- [ ] `tests/conftest.py` autouse fixture shrinking `takeover.REPLAY_QUIET_SECONDS`

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
