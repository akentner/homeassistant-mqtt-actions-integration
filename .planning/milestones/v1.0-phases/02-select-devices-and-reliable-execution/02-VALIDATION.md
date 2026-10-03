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

Refined by the planner from the requirement-level rows of 02-RESEARCH.md. Every task is TDD (RED test commit before the feature commit) and creates the test files it needs; the Wave 0 files below are therefore created inside the tasks, not by a separate wave.

| Task | Req | Behavior | Test Type | Automated Command | File Exists | Status |
|------|-----|----------|-----------|-------------------|-------------|--------|
| 02-01-T1 | DEV-03 | Select payload runs only its option's actions; Switch path unchanged (tracer) | integration + unit | `uv run pytest tests -q && uv run pytest tests/test_manager_select.py -k tracer -q` | ❌ W0 (created in task) | ⬜ pending |
| 02-01-T2 | DEV-03, STA-07 | Select discovery, mapping templates with hostile strings, unknown payload silent in core | integration | `uv run pytest tests/test_discovery.py tests/test_discovery_select.py tests/test_manager_select.py -q` | ❌ W0 (created in task) | ⬜ pending |
| 02-01-T3 | DEV-03, STA-07 | Loader hardening, unknown/retained/startup/removed-value semantics, orphan and hub removal | unit + integration | `uv run pytest tests/test_model.py tests/test_manager_select.py tests/test_manager.py -q && uv run pytest tests -q` | ❌ W0 (created in task) | ⬜ pending |
| 02-02-T1 | DEV-06 | One Script per device: restart cancels and serial orders across triggers | integration | `uv run pytest tests/test_runner_modes.py tests/test_manager.py -q && uv run pytest tests -q` | ❌ W0 (created in task) | ⬜ pending |
| 02-02-T2 | DEV-06 | Queue bound 10, dropped and superseded runs keep the issue, unload cancels | integration | `uv run pytest tests/test_runner_modes.py tests/test_manager.py -q && uv run pytest tests -q` | extends T1 | ⬜ pending |
| 02-03-T1 | DEV-07 | Test buttons per trigger; press runs actions locally without state, baseline or publish | integration | `uv run pytest tests/test_topics.py tests/test_test_buttons.py -q && uv run pytest tests -q` | ❌ W0 (created in task) | ⬜ pending |
| 02-03-T2 | DEV-07, DEV-04 | Button lifecycle: add, rename, remove with tombstones, delete, unsubscribe | integration | `uv run pytest tests/test_test_buttons.py tests/test_manager.py -q && uv run pytest tests -q` | extends T1 | ⬜ pending |
| 02-04-T1 | STA-06 | Pure breaker table; trip, pause, stop runs, Repairs issue, self-toggling loop stopped | unit + integration | `uv run pytest tests/test_breaker.py tests/test_manager_breaker.py -q && uv run pytest tests -q` | ❌ W0 (created in task) | ⬜ pending |
| 02-04-T2 | STA-06 | Tripped state persisted as config hash; release by change or reload; cleanup | integration | `uv run pytest tests/test_manager_breaker.py tests/test_manager.py -q && uv run pytest tests -q` | extends T1 | ⬜ pending |
| 02-04-T3 | STA-06, FND-04 | Breaker issue text in en and de, variables match, hassfest | unit | `uv run pytest tests/test_translations.py -q` plus hassfest via Docker | extends existing | ⬜ pending |
| 02-05-T1 | DEV-03 | Select flow create path, option validation, menu visibility, en/de strings | integration + unit | `uv run pytest tests/test_config_flow_select.py tests/test_model.py tests/test_translations.py tests/test_config_flow.py -q` plus hassfest via Docker | ❌ W0 (created in task) | ⬜ pending |
| 02-05-T2 | DEV-04 | Reconfigure: edit with locked StateValue, add, remove with confirmation | integration | `uv run pytest tests/test_config_flow_select.py tests/test_translations.py -q && uv run pytest tests -q` plus hassfest via Docker | extends T1 | ⬜ pending |
| 02-05-T3 | DEV-06, STA-06, FND-04 | Run mode and breaker fields in the Switch flow, translation parity, README | integration + unit | `command -v mosquitto >/dev/null && uv run pytest -m broker -q && uv run pytest -q` plus ruff and hassfest via Docker | extends existing | ⬜ pending |

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
