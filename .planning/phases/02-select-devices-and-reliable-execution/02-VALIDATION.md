---
phase: "02"
slug: select-devices-and-reliable-execution
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-29"
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `02-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio (auto) via pytest-homeassistant-custom-component 0.13.367 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]`, `tests/conftest.py` |
| **Quick run command** | `uv run pytest tests/<file>.py -q` |
| **Full suite command** | `uv run pytest tests -q && uv run ruff check . && uv run ruff format --check .` |
| **Estimated runtime** | ~10 seconds (baseline 188 passed in 9.24s) |

---

## Sampling Rate

- **After every task commit:** Run the single test file the task touched
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| DEV-03 | Select flow validation; discovery payload; option runs its own actions | integration | `uv run pytest tests/test_config_flow_select.py tests/test_discovery_select.py tests/test_manager_select.py -q` | ❌ W0 | ⬜ pending |
| DEV-04 | StateValue locked; rename/action edits; add/remove option with button tombstone | integration | `uv run pytest tests/test_config_flow_select.py tests/test_manager_select.py -q` | ❌ W0 | ⬜ pending |
| DEV-06 | serial FIFO (bound 10), restart cancels, missing run_mode = serial | integration | `uv run pytest tests/test_runner_modes.py -q` | ❌ W0 | ⬜ pending |
| DEV-07 | Test buttons run actions without touching state/baseline/breaker | integration | `uv run pytest tests/test_test_buttons.py -q` | ❌ W0 | ⬜ pending |
| STA-06 | Breaker window, trip, persistence, release, Repairs issue | unit + integration | `uv run pytest tests/test_breaker.py tests/test_manager_breaker.py -q` | ❌ W0 | ⬜ pending |
| STA-07 | Unknown payload ignored and logged, entity keeps state | unit + integration | `uv run pytest tests/test_state.py tests/test_manager_select.py tests/test_discovery_select.py -q` | extend + W0 | ⬜ pending |
| FND-04 | en/de translation parity for new keys | unit | `uv run pytest tests/test_translations.py -q` | extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. The planner refines this into per-task rows.*

---

## Wave 0 Requirements

- [ ] `tests/test_breaker.py` — pure sliding-window table (injected clock)
- [ ] `tests/test_model.py` — `spec_from_subentry`, `trigger_key`, template builders with hostile strings
- [ ] `tests/test_discovery_select.py` — port the research spikes (real HA discovery via `mqtt_mock`)
- [ ] `tests/test_runner_modes.py` — queued FIFO + drop warning, restart cancel, dropped run keeps issue
- [ ] `tests/test_config_flow_select.py`, `tests/test_manager_select.py`, `tests/test_test_buttons.py`, `tests/test_manager_breaker.py`
- [ ] `tests/conftest.py` — `make_select_subentry`, `make_switch_subentry` run_mode/breaker kwargs
- [ ] `tests/test_translations.py` — extend `REQUIRED_KEYS` and placeholder assertions

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Menu loop and `ActionSelector` rendering, DE/EN labels | DEV-03, DEV-04 | Not testable in PHACC | Create and edit a Select device in the real HA dialog in both languages |
| End-to-end run on a real broker | DEV-03, DEV-07, STA-06 | Needs `haos-op3050-1` | Select an option in the UI, publish with `mosquitto_pub`, trip the breaker with a self-toggling action, release by reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
