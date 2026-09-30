---
phase: "03"
slug: trust-central-config-and-ownership
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-01"
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `03-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio (auto) via pytest-homeassistant-custom-component 0.13.367 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (marker `broker`), `tests/conftest.py` |
| **Quick run command** | `uv run pytest tests/<file>.py -x -q` |
| **Full suite command** | `uv run pytest -q && uv run ruff check . && uv run ruff format --check .` |
| **Estimated runtime** | ~25 seconds (baseline 426 passed in ~22s) |

---

## Sampling Rate

- **After every task commit:** Run the single test file the task touched plus `uv run ruff check custom_components tests`
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite green, including `-m broker` tests (mosquitto 2.1.2 installed)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Refined by the planner from the requirement-level rows of 03-RESEARCH.md (Phase Requirements to Test Map):

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| SYN-01 | Retained versioned document, canonical hash, publish order config → discovery → availability | unit + manager | `uv run pytest tests/test_document.py tests/test_sync_owner.py -x` |
| SYN-02 | Retained document creates a mirror, cached in Store, survives restart | manager | `uv run pytest tests/test_sync_follower.py -x` |
| SYN-03 | Owner pinning, conflict Repairs, owner-claim republish with throttle | manager + multi-instance | `uv run pytest tests/test_sync_follower.py tests/test_multi_instance.py -x` |
| SYN-04 | Republish on every reconnect, wiped broker healed | multi-instance | `uv run pytest tests/test_multi_instance.py -k reconnect -x` |
| SYN-05 | No delete on absence; tombstone removes at once; prune only with owner online | multi-instance | `uv run pytest tests/test_multi_instance.py -k prune -x` |
| SYN-06 | Delete confirmation wording, config + discovery + state tombstones, retry | flow + manager | `uv run pytest tests/test_config_flow_delete.py tests/test_sync_owner.py -k delete -x` |
| TRU-01 | Unapproved mirror runs nothing (live state, test button, run-on-startup) | manager | `uv run pytest tests/test_trust.py -k unapproved -x` |
| TRU-02 | Approval binds action hash; changed actions re-prompt; dismissed issue does not hide it | repairs flow | `uv run pytest tests/test_repairs_flow.py -x` |
| TRU-03 | Schema gate, nesting cap, `GuardedTemplate` incl. `continue_on_error`, blocked state | unit + runner | `uv run pytest tests/test_trust.py tests/test_document.py -x` |
| TRU-04 | ACL example enforced by a real mosquitto | broker | `uv run pytest tests/broker/test_acl.py -x` |
| STA-03 | UI change / external publish runs actions on every approved instance | multi-instance | `uv run pytest tests/test_multi_instance.py -k fanout -x` |
| DSC-03 | Entity deletion clears discovery; owner republishes once per window | manager + multi-instance | `uv run pytest tests/test_sync_owner.py -k discovery -x` |
| D-11 | Hub removal keep vs delete | manager | `uv run pytest tests/test_hub_removal.py -x` |
| FND-04 | en/de parity for new strings | unit | `uv run pytest tests/test_translations.py -x` |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `custom_components/mqtt_actions/mqtt_gateway.py` — `IncomingMessage.topic`
- [ ] `Manager.__init__` optional `gateway` and `store_key` parameters
- [ ] `tests/fake_broker.py` — `FakeBroker` (real retain semantics), `FakeGateway`, reconnect/wipe controls, two-`hass` factory with per-instance store key
- [ ] Test stubs: `tests/test_document.py`, `test_sync_owner.py`, `test_sync_follower.py`, `test_trust.py`, `test_repairs_flow.py`, `test_config_flow_delete.py`, `test_multi_instance.py`, `test_hub_removal.py`, `tests/broker/test_acl.py`
- [ ] Update existing tests encoding removed behavior (hub-removal clear-everything `tests/test_manager_breaker.py:613`, reconfigure tests `tests/test_config_flow.py:256-410`, Select menu lists)
- [ ] Extend `tests/test_translations.py` `REQUIRED_KEYS`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Approval dialog rendering in Repairs | TRU-02 | Frontend rendering of fix-flow form | Create a device on instance A, open Repairs on instance B, check YAML view and approve |
| Generic subentry delete dialog wording | SYN-06 | Core dialog cannot be vetoed or customised | Delete a device via the generic HA dialog; confirm it tombstones and README covers the wording |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
