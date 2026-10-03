---
phase: "05"
slug: evaluate-native-switch-select-entities-instead-of-mqtt-disco
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-03"
---

# Phase 5 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Overall model: the broker is cooperative and unauthenticated by owner decision (EMQX migration planned). The only real control is the per-instance ACL in `docs/broker-acl.md`. Approval and the Script gate are untouched by this phase, so no threat in this phase can execute actions.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Installed HA core to takeover design (05-01) | Migration relies on core registry behaviour that can change in a core release | Registry and discovery semantics |
| Autonomous execution to one-way door (05-01) | An unattended run could pass D-05 without human confirmation | Go/No-Go decision |
| Broker device id to registry lookup (05-02) | Mirror device ids come from foreign documents | Device ids |
| Takeover steps to user registry (05-02) | Wrong step order destroys customizations, registry ids, automations | Registry entries |
| Broker payload to entity state (05-03) | Mirror names and select options reach entity names and option lists | Names, option labels |
| HA user command to broker (05-03) | A native entity publishes to a state topic on behalf of the user | State payloads |
| Foreign document to mirror native status (05-04) | A document's "native" claim decides legacy vs native entities | Native marker |
| Owner announcement to availability (05-04) | Availability topic decides whether a mirror can be commanded | Availability |
| Instance to shared discovery topics (05-05) | Migrate and empty retained payloads could unload or delete another instance's entities | Discovery topics |
| Persisted Store to takeover pass (05-05) | Pending list decides which topics are published for | Pending device ids |
| Heartbeat/availability to cutover gate (05-06) | Anyone on the broker can publish under an instance id | Heartbeats, capabilities |
| Peer names to Repairs text (05-06) | Names reach a Repairs issue that renders markdown | Peer names |
| Foreign document to reload (05-07) | A document can make this instance reload its config entry | Native marker |
| Export prefix to external subscribers (05-08) | Subscribers see device names and kinds | Export payloads |
| User export prefix to broker topic space (05-08) | Prefix could collide with core discovery or own topics | Topic prefix |
| Documentation to user expectation (05-09) | Users decide on a one-way migration and ACLs from these pages | Documentation |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-5-01 | Tampering | Device id equal to unrelated MQTT entity unique id | high | mitigate | Device lookup by `(mqtt, mqtt_actions_<id>)`; `is_legacy_entity` requires platform, entry, device, domain and unique-id shape (`takeover.py:58-84`); ids shape-checked (`sync.py:400`, `topics.py:14`) | closed |
| T-5-02 | Tampering | Forged migrate/empty payload hits another instance | medium | mitigate | Publish only for `owned` ids (`manager.py:884-909`, `:959-965`); pending ids validated on load (`:337`) | closed |
| T-5-03 | Tampering | Forged "native" marker flips followers | medium | mitigate | Non-pinned owner documents go to `_conflict` (`sync.py:476-487`); takeover only for pinned owner (`manager.py:888-895`) | closed |
| T-5-04 | Tampering | Forged heartbeat capability skews cutover gate | low | accept | See Accepted Risks; hardened by WR-03 (`presence.py:182-204`, `:523`) | closed (accepted) |
| T-5-05 | Tampering | Broker names/labels reach entity names | low | mitigate | `_invalid_label`/`_invalid_text`, option count and length limits (`document.py:334-395`, `model.py:192-194`) | closed |
| T-5-06 | Repudiation | One-way migration without human confirmation | high | mitigate | Blocking human gate; ADR 0001 accepted by the user before takeover code (`402f624`, `docs/adr/0001-…`) | closed |
| T-5-07 | Tampering | Core bump changes registry behaviour | high | mitigate | Core behaviour pinned incl. negative controls in `tests/test_takeover.py` | closed |
| T-5-08 | Tampering | Wrong step order / loaded entity loses registry entries | high | mitigate | Wait on entity sources, DEFERRED path, entities before device (`takeover.py:87-177`); WR-01, WR-02 fixed. Residual IN-03 owner-accepted | closed |
| T-5-09 | Tampering | Silent duplicate registry key | medium | mitigate | Existing-entity check before every move, identity-aware rule (WR-04) (`takeover.py:140-149`, `:218-240`) | closed |
| T-5-10 | Tampering | Native command publishes arbitrary text | medium | mitigate | `async_send_state` accepts only spec values (`manager.py:2241-2252`); all state publishes route through it | closed |
| T-5-11 | Tampering | Document without marker pushes mirror back to legacy | medium | mitigate | `keep_native` rule and persisted marker (`manager.py:1289-1298`, `:1805-1850`, `document.py:188-204`). Residual IN-02 owner-accepted | closed |
| T-5-12 | Tampering | Adoption between native/legacy creates duplicates | medium | mitigate | Native adoption and companion keep, `_rebind_native_registry` (`manager.py:1391-1447`, `:1735-1752`); CR-01 fixed | closed |
| T-5-13 | Denial of service | Cutover flips or reloads repeatedly | medium | mitigate | Flag persisted before reload, runs once (`manager.py:798-841`, `:1221-1226`) | closed |
| T-5-14 | Tampering | Peer name injects markup via hint | low | mitigate | Name length/printable limits, `escape_markdown`, cap of 5 (`presence.py:74-130`, `manager.py:854-855`) | closed |
| T-5-15 | Denial of service | Flood of marked documents reloads follower | medium | mitigate | One reload per manager lifetime, pinned owner only (`manager.py:1873-1898`, `sync.py:476-487`) | closed |
| T-5-16 | Information disclosure | Export reveals names and kinds | low | accept | See Accepted Risks; off by default, minimal payload (`discovery.py:140-159`) | closed (accepted) |
| T-5-17 | Tampering | Export prefix collides with core prefix/base topic | low | mitigate | `validate_base_topic`, `invalid_export_prefix`, `enabled_by_default` False (`config_flow.py:159-166`, `discovery.py:153`) | closed |
| T-5-18 | Repudiation | Docs promise more than code / hide one-way limit | medium | mitigate | README, operations docs and `tests/test_docs.py` pin the limits | closed |
| T-5-SC | Tampering | Package installs (all nine plans) | low | accept | See Accepted Risks; no dependency changes | closed (accepted) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-5-01 | T-5-04 | Gate only decides when a UI change happens. A forged capability can make a legacy instance lose UI entities (never actions); a forged legacy blocker only delays the switch. Heartbeats are validated, size-capped, roster-capped. Includes residual WR-03: a forged retained `offline` still lifts a block. Documented in README Limitations and `docs/broker-acl.md`. | Plan disposition; WR-03 residual per 05-REVIEW-DISPOSITION | 2026-10-03 |
| AR-5-02 | T-5-16 | Export holds only device names, kinds, option labels and the availability topic. No actions, owner, config or approval data. Off by default. | Plan disposition | 2026-10-03 |
| AR-5-03 | T-5-SC | Phase installs no packages; `pyproject.toml`, `uv.lock` unchanged, manifest `requirements` is `[]`. | Plan disposition | 2026-10-03 |
| AR-5-04 | T-5-11 (IN-02) | Marker dropped when payload exceeds `MAX_DOCUMENT_BYTES`; mirror reads as legacy after restart. Reload count stays bounded (T-5-15). | Owner, 05-REVIEW-DISPOSITION | 2026-10-03 |
| AR-5-05 | T-5-08 (IN-03) | Takeover can race a boot-time retained discovery replay. Impact is a temporary duplicate that the next pass removes. UAT test 5 skipped by owner. | Owner, 05-REVIEW-DISPOSITION | 2026-10-03 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-03 | 19 | 19 | 0 | gsd-security-auditor (ASVS 1, block_on high) |

Auditor ran 355 security-relevant tests (all passed) and found no unregistered threat flags. Non-blocking follow-ups: no direct negative test for the `ValueError` branch of `Manager.async_send_state`; T-5-14 "never logged" rests on code reading only.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-03
