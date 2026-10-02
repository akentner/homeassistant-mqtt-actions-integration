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

Refined by the planner: one row per task of plans 03-01 to 03-07 (requirement-level rows of 03-RESEARCH.md are covered by the combination of these rows). The `-k` filters of the research map (`reconnect`, `prune`, `fanout`, `unapproved`, `delete`, `discovery`) are kept in the test names so they still select the right tests.

| Task | Req ID | Behavior | Test Type | Automated Command |
|------|--------|----------|-----------|-------------------|
| 03-01-T1 | SYN-01, SYN-04 | Retained versioned document, canonical hash and golden fixture, publish order config, discovery, availability, rev persistence | unit + manager | `uv run pytest tests/test_topics.py tests/test_document.py tests/test_sync_owner.py -q` |
| 03-01-T2 | TRU-03 | Strict parse, schema gate, caps, denylist walker, markdown escape | unit | `uv run pytest tests/test_document.py -q` |
| 03-01-T3 | (Wave 0) | IncomingMessage.topic, Manager gateway and store_key, FakeBroker retain semantics, two real instances | unit + multi-instance | `uv run pytest tests/test_fake_broker.py -q` |
| 03-02-T1 | SYN-06 | Delete order discovery, unsubscribe, config tombstone, state; pop-first; retry | manager | `uv run pytest tests/test_sync_owner.py tests/test_manager.py -q` |
| 03-02-T2 | SYN-03 | Echo history, foreign write healing, ownership claim, trailing throttle | manager | `uv run pytest tests/test_sync_owner.py -q` |
| 03-02-T3 | DSC-03 | Discovery healing with trailing throttle, repeated-removal hint, issue texts | manager + unit | `uv run pytest tests/test_sync_owner.py tests/test_translations.py -q` |
| 03-03-T1 | SYN-06 | Delete confirmation menu with all-instances wording and presence count, generic path parity | flow + manager | `uv run pytest tests/test_config_flow_delete.py tests/test_config_flow.py tests/test_config_flow_select.py -q` |
| 03-03-T2 | D-11 | Hub options flow, removal keep versus delete | manager | `uv run pytest tests/test_hub_removal.py tests/test_manager.py tests/test_manager_select.py tests/test_manager_breaker.py -q` |
| 03-03-T3 | FND-04 | en and de parity for delete and options texts | unit | `uv run pytest tests/test_translations.py -q` |
| 03-04-T1 | SYN-02, TRU-01 | Retained document creates an inert persistent mirror, reconcile regression, cap | manager + multi-instance | `uv run pytest tests/test_sync_follower.py tests/test_multi_instance.py -q` |
| 03-04-T2 | SYN-03, TRU-03 | Hash-based update, owner pinning, too-new schema, hostile documents | manager | `uv run pytest tests/test_sync_follower.py -q` |
| 03-04-T3 | FND-04 | en and de parity for conflict and schema texts | unit | `uv run pytest tests/test_translations.py -q` |
| 03-05-T1 | SYN-05 | Live tombstone removal, guarded registry cleanup | manager + multi-instance | `uv run pytest tests/test_sync_follower.py tests/test_multi_instance.py -q` |
| 03-05-T2 | SYN-05 | Grace-window prune only with owner online and document unseen; wipe safe | multi-instance | `uv run pytest tests/test_sync_follower.py tests/test_multi_instance.py -q` |
| 03-06-T1 | TRU-01, TRU-03, STA-03 | Hash-bound approval, guarded Script, continue_on_error regression, blocked state, fanout | manager + runner + multi-instance | `uv run pytest tests/test_trust.py tests/test_multi_instance.py -q` |
| 03-06-T2 | TRU-02 | Repairs approval flow, race abort, dismissal, safe view | repairs flow | `uv run pytest tests/test_repairs_flow.py tests/test_trust.py -q` |
| 03-06-T3 | FND-04 | en and de parity for approval, blocked and denied-call texts | unit | `uv run pytest tests/test_translations.py -q` |
| 03-07-T1 | TRU-04 | Documented ACL enforced by a real mosquitto | broker | `uv run pytest tests/broker/test_acl.py tests/test_repo_structure.py -q -rs` |
| 03-07-T2 | STA-03, SYN-04, SYN-05, SYN-06 | Three-instance acceptance scenarios incl. wipe, conflict, forged tombstone | multi-instance | `uv run pytest tests/test_multi_instance.py -q` |
| 03-07-T3 | TRU-04 (docs) | README phase 3 content, no device_id in examples | unit | `uv run pytest tests/test_repo_structure.py -q` |

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
