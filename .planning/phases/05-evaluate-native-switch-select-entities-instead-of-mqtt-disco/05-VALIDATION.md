---
phase: "05"
slug: evaluate-native-switch-select-entities-instead-of-mqtt-disco
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-03"
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `05-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-homeassistant-custom-component 0.13.367, `asyncio_mode = "auto"` |
| **Config file** | `pyproject.toml` (`--strict-markers`, markers `broker`, `multi_instance`) |
| **Quick run command** | `uv run pytest -q -m "not broker and not multi_instance" -x` |
| **Full suite command** | unit tier above + `uv run pytest -q -m multi_instance` + `uv run pytest -q -m broker` |
| **Estimated runtime** | ~57 seconds (unit tier) |

---

## Sampling Rate

- **After every task commit:** the single new test file of the task, `-x`
- **After every plan wave:** unit tier (`-m "not broker and not multi_instance"`)
- **Before `/gsd-verify-work`:** all three tiers green plus `uv run ruff check . && uv run ruff format --check .`
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| MIG-01 | Takeover keeps entity_id, registry id, device id, area, name_by_user, mode select; loaded-entity refusal; ghost/disabled entity; duplicate-key guard; foreign-entity identity check; delayed replay | unit | `uv run pytest tests/test_takeover.py -x` | ❌ W0 | ⬜ pending |
| ENT-01/02 | Switch/select state from topic, retained qos-1 command, availability parity, owned under subentry, mirror under entry | unit | `uv run pytest tests/test_native_entities.py tests/test_companions.py -x` | ❌ W0 | ⬜ pending |
| ENT-03 | Export off by default, `enabled_by_default: false`, prefix option | unit | `uv run pytest tests/test_discovery.py -x` | ✅ rewrite | ⬜ pending |
| MIG-02 | Roster gate holds while a legacy peer is online; marker after cutover; v0.1.0-shaped peer counts as legacy | unit + multi_instance | `uv run pytest tests/test_cutover.py -x` | ❌ W0 | ⬜ pending |
| STA-01/03/07 | Unchanged behavior through native entities across two instances | multi_instance | `uv run pytest -q -m multi_instance` | ✅ harness extension | ⬜ pending |
| MIG-03 | Removed issues absent from translations/docs; ACL doc matches broker test | unit + broker | `uv run pytest tests/test_docs.py tests/test_translations.py tests/test_repo_structure.py -x` | ✅ update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_takeover.py` — spike scenarios A to E as regression tests
- [ ] `tests/test_native_entities.py`, `tests/test_cutover.py`
- [ ] `tests/fake_broker.py` — `Instance` running real `async_setup_entry` so platforms are forwarded
- [ ] helper producing a v0.1.0-shaped peer (heartbeat/document without new keys)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ADR exists with the four D-02 criteria and result | DEC-01 | File review | Read the ADR |
| Integration page shows all devices/entities incl. mirrors | ENT-01 | Frontend counting | UAT on ha-one/ha-two |
| Real-broker discovery replay race, live follower cutover | MIG-01/02 | Needs real HA + broker | UAT on `~/ha-test` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
