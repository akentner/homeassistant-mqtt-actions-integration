---
phase: "01"
slug: walking-skeleton-installable-switch
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-29"
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `01-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.4.0 via pytest-homeassistant-custom-component 0.13.367 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 creates it |
| **Quick run command** | `uv run pytest -x -q && uv run ruff check .` |
| **Full suite command** | `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && docker run --rm -v "$PWD":/github/workspace:Z ghcr.io/home-assistant/hassfest` |
| **Estimated runtime** | ~5 s (quick), ~60 s (full, incl. hassfest container) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green and CI green on the phase branch
- **Max feedback latency:** 10 seconds (quick)

---

## Per-Task Verification Map

| Requirement | Behavior | Test Type | Automated Command | File Exists |
|-------------|----------|-----------|-------------------|-------------|
| FND-01 | manifest / hacs.json / brand icon present | unit | `uv run pytest tests/test_repo_structure.py -q` | ❌ W0 |
| FND-02 | workflows pinned by SHA, `permissions: {}` | unit | `uv run pytest tests/test_repo_structure.py -q` | ❌ W0 |
| FND-03 | hub flow: mqtt_required, uuid4 instance_id, single instance | flow | `uv run pytest tests/test_config_flow.py -q` | ❌ W0 |
| FND-04 | en/de key + placeholder parity | unit | `uv run pytest tests/test_translations.py -q` | ❌ W0 |
| FND-05 | setup_retry without MQTT; reconnect republish; single subscription | integration | `uv run pytest tests/test_manager.py -q` | ❌ W0 |
| DEV-01 | Switch subentry create, UUID unique_id | flow | `uv run pytest tests/test_config_flow.py -k switch -q` | ❌ W0 |
| DEV-02 | raw actions persisted, selector schema serializes | flow | `uv run pytest tests/test_config_flow.py -k switch -q` | ❌ W0 |
| DEV-05 | invalid action rejected; device_id warning, resubmit saves | flow + unit | `uv run pytest tests/test_config_flow.py tests/test_device_ids.py -q` | ❌ W0 |
| DEV-08 | failing action → log + Repairs issue | integration | `uv run pytest tests/test_manager.py -k issue -q` | ❌ W0 |
| STA-01 | UI toggle publishes retained ON/OFF | integration | `uv run pytest tests/test_discovery.py -k toggle -q` | ❌ W0 |
| STA-02 | live on/off runs matching actions once | integration | `uv run pytest tests/test_manager.py -k edge -q` | ❌ W0 |
| STA-04 | retained = baseline only; run_on_startup; live w/o baseline acts (D-14) | unit + integration | `uv run pytest tests/test_state.py tests/test_manager.py -k "retain or startup" -q` | ❌ W0 |
| STA-05 | last_acted persisted; duplicates/unknown payloads ignored | unit + integration | `uv run pytest tests/test_state.py tests/test_manager.py -k baseline -q` | ❌ W0 |
| DSC-01 | discovery payload → entity with UUID unique_id, availability | integration | `uv run pytest tests/test_discovery.py -q` | ❌ W0 |
| DSC-02 | unload never clears; delete clears discovery then state (D-16); orphan cleanup; hub removal (D-15) | integration | `uv run pytest tests/test_manager.py -k "unload or delete or orphan or remove" -q` | ❌ W0 |

*Status tracking happens in the plans' SUMMARY files.*

---

## Wave 0 Requirements

- [ ] `pyproject.toml`, `uv.lock`, `.ruff.toml`
- [ ] `tests/conftest.py` (`enable_custom_integrations`, `expected_lingering_timers`)
- [ ] `tests/test_state.py`, `test_topics.py`, `test_device_ids.py`, `test_translations.py`, `test_repo_structure.py`
- [ ] `tests/test_config_flow.py`, `test_manager.py`, `test_discovery.py`
- [ ] Framework install after the package-legitimacy checkpoint: `uv add --dev pytest-homeassistant-custom-component==0.13.367 ruff==0.16.9`

Test rules: drive edges with explicit `async_fire_mqtt_message(..., retain=...)` (never the publish loopback); `async_block_till_done(wait_background_tasks=True)`; assert discovery via publish calls.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `ActionSelector` renders in the subentry dialog; `base` error banner; DE/EN strings | DEV-02, DEV-05, FND-04 | Frontend rendering is not testable in PHACC | Install branch build on `haos-op3050-1`, add hub + Switch, submit invalid action and a `device_id` action |
| No actions on restart; one action per real change | STA-02, STA-04 | Real broker + restart | Publish `on`/`off` via `ha-ws`/mosquitto_pub; restart HA; reload integration |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
