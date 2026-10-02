---
phase: "03"
slug: "trust-central-config-and-ownership"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: "2026-10-02"
---

# Phase 3 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Broker to instance (config topic) | Any client with access can publish a config document an instance ingests | JSON document with the full action sequence (untrusted until validated and approved) |
| Broker to instance (state and test topics) | Anyone allowed to publish there triggers actions on every instance that approved the device | State payloads, test presses |
| Broker to core MQTT (discovery prefix) | Anyone who can write the prefix creates, changes or removes entities | Retained discovery payloads |
| Owner to follower (ownership) | Ownership is cooperative within the group of HA users; the topic carries a device uuid, not the owner | Config documents, tombstones, availability |
| Follower to local execution (approval gate) | A mirrored document runs nothing before the user approved its exact actions on this instance | Action sequences, `actions_hash` |
| Broker text to UI (Repairs and config flow) | Names and YAML from another instance are rendered in HA dialogs | Device and owner names, action YAML |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Tampering | Document hashes | high | mitigate | `document.py:343-348` recomputes `content_hash` and `actions_hash`; the wire hash is never read | closed |
| T-03-02 | DoS | Document ingest | high | mitigate | Byte size checked before parsing, iterative depth walk, option caps (`document.py:325-340`) | closed |
| T-03-03 | Elevation of privilege | Denylist | high | mitigate | `is_denied` and the fixed frozensets in `const.py:64-87`, not user-editable | closed |
| T-03-04 | Information disclosure | Config topic | medium | accept | Documented: no secrets in actions, ACL read restriction, TLS (`README.md:233`, `docs/broker-acl.md:104-112`) | closed (accepted) |
| T-03-05 | Tampering | Broker text in UI | medium | mitigate | Printable and 64-char rule plus `escape_markdown` at every broker-text placeholder | closed |
| T-03-06 | Tampering | Owner documents | high | mitigate | `_check_owned` / `_overwritten` republish; spec never mutated (`sync.py:461-511`) | closed |
| T-03-07 | DoS | Republish loop | high | mitigate | `_TrailingThrottle`, `REPUBLISH_THROTTLE_SECONDS`, issue raised once (`sync.py:96-151`) | closed |
| T-03-08 | Tampering | Delete order | high | mitigate | Device popped before any clear; handlers act only for known ids (`manager.py:941`) | closed |
| T-03-09 | Spoofing | Ownership claims | medium | mitigate | `_claimed`: republish plus issue naming the claimant; no takeover path | closed |
| T-03-10 | DoS | Discovery removal | low | mitigate | `_note_removal` with `DISCOVERY_REMOVAL_HINT_COUNT`, throttled heal | closed |
| T-03-11 | Tampering | Hub removal | high | mitigate | Default keeps devices, delete only on explicit option (`__init__.py:62-65`) | closed |
| T-03-12 | DoS | Instance tracking | medium | mitigate | `MAX_TRACKED_INSTANCES` cap (`sync.py:285-292`) | closed |
| T-03-13 | Repudiation | Generic delete dialog | medium | accept | Documented: generic dialog cannot be vetoed, deletes everywhere (`README.md:172-173`); UAT test 2 passed | closed (accepted) |
| T-03-14 | Spoofing | Mirror creation | high | mitigate | Mirror built without a Script; Script only when approved (`manager.py:563-705`) | closed |
| T-03-15 | Spoofing | Owner pinning | high | mitigate | First owner pinned, later claims go to `_conflict`; pin survives restarts | closed |
| T-03-16 | DoS | Mirror flooding | high | mitigate | `MAX_MIRRORS`, schema-too-new issue cap, id validation (`sync.py:322-446`) | closed |
| T-03-17 | Tampering | Schema version | medium | mitigate | Too-new schema never applied, last mirror kept | closed |
| T-03-18 | Information disclosure | Ingest errors | medium | mitigate | Fixed reason codes, capped and quoted ids; see advisory A5 | closed |
| T-03-19 | Tampering | Local mirror cache | medium | mitigate | `_parse_mirrors` re-parses and re-analyzes every cached payload | closed |
| T-03-20 | DoS | Forged tombstone | medium | accept | Documented: owner republishes, mirror returns unapproved, worst case a forced re-approval (`README.md:143-144,231`) | closed (accepted) |
| T-03-21 | Tampering | Pruning on reconnect | high | mitigate | Reconnect clears seen state; prune only when unseen and owner online | closed |
| T-03-22 | DoS | Registry cleanup | high | mitigate | `_clean_registry` needs an MQTT entry and stops when any entity is live | closed |
| T-03-23 | Tampering | Stale `online` | low | accept | Documented: no Last Will, known limitation (`README.md:223-226`) | closed (accepted) |
| T-03-24 | Elevation of privilege | Approval gate | critical | mitigate | No Script without a stored approval equal to `actions_hash`; every trigger path gates on `runner.can_run` | closed |
| T-03-25 | Elevation of privilege | Approval binding | critical | mitigate | Changed hash unloads the Script and re-asks; see advisory A1 | closed |
| T-03-26 | Elevation of privilege | Template guard | high | mitigate | `GuardedTemplate` and `guard_actions` on restricted builds (`trust.py:46-94`) | closed |
| T-03-27 | Tampering | Denied services | high | mitigate | `mqtt.publish` and `mqtt.dump` in the fixed denylist | closed |
| T-03-28 | Tampering | Approval dialog | high | mitigate | Control chars dropped, fences neutralized, YAML capped (`trust.py:123-185`); UAT test 1 passed | closed |
| T-03-29 | Tampering | Approval race | high | mitigate | `async_approve` requires `info.actions_hash == actions_hash` under the lock | closed |
| T-03-30 | Repudiation | Stale approval issue | medium | mitigate | Old issue deleted before the new one is created | closed |
| T-03-31 | Elevation of privilege | Residual service kinds | medium | accept | Documented: residual steps flagged in the approval view (`README.md:158-164`) | closed (accepted) |
| T-03-32 | Information disclosure | Allowed exfiltration services | medium | accept | Documented: `notify` named as an allowed path (`README.md:158-160`) | closed (accepted) |
| T-03-33 | Tampering | Stored approvals | high | mitigate | Script only when the stored approval equals the recomputed hash; restricted build refuses denied static services | closed |
| T-03-34 | Spoofing | Cooperative ownership | high | accept | Documented: ownership is cooperative, the approval gate is the real control (`docs/broker-acl.md:83-91`, `README.md:253-255`) | closed (accepted) |
| T-03-35 | Tampering | Documented ACL | medium | mitigate | `tests/broker/test_acl.py` runs the documented block against a real Mosquitto; CI installs Mosquitto | closed |
| T-03-36 | Information disclosure | Config read access | medium | mitigate | Docs say no secrets and restrict config reads; example ACL gives `bridge` no config read | closed |
| T-03-37 | Elevation of privilege | Test topic | medium | mitigate | Test topic named as a trigger source and granted only to HA users | closed |
| T-03-38 | Tampering | Config-flow descriptions | low | mitigate | `escape_markdown` at the four config-flow sites (plan 03-08); UAT test 2 retested in a real frontend | closed |
| T-03-39 | Tampering | Translations | low | mitigate | Placeholders stay plain in both languages; guard tests pass | closed |
| T-03-SC | Tampering | Supply chain | low | accept | No packages installed; `manifest.json` has `"requirements": []` | closed (accepted) |

*Status: open · closed · open — below block_on threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-04 | Action data is readable by every config-topic subscriber. Control: no secrets in actions, ACL read restriction, TLS. | Plan-time disposition (03 threat models, plan-checked) | 2026-10-02 |
| AR-03-02 | T-03-13 | The generic HA subentry delete dialog cannot be vetoed and deletes everywhere. The integration's own dialog names all instances. | Plan-time disposition; UAT test 2 passed | 2026-10-02 |
| AR-03-03 | T-03-20 | A forged tombstone removes mirrors and approvals. The owner republishes and the mirror returns unapproved, so the worst case is a forced re-approval. | Plan-time disposition | 2026-10-02 |
| AR-03-04 | T-03-23 | No Last Will, so a retained `online` survives an owner crash. | Plan-time disposition | 2026-10-02 |
| AR-03-05 | T-03-31 | Residual step kinds outside the denylist (scripts, automations, scenes, device actions, events, generic turn_on/off/toggle). The approval is the primary control. | Plan-time disposition | 2026-10-02 |
| AR-03-06 | T-03-32 | Approved templates can send state out through allowed services such as `notify`. | Plan-time disposition | 2026-10-02 |
| AR-03-07 | T-03-34 | Ownership is cooperative within the HA user group, because device uuids are random and unknown when the ACL is written. The approval gate is the real control. | Plan-time disposition | 2026-10-02 |
| AR-03-08 | T-03-SC | No third-party packages in this phase. | Plan-time disposition | 2026-10-02 |

*Accepted risks do not resurface in future audit runs.*

---

## Open Review Items (not threats, not counted in `threats_open`)

These items map to no register threat. They are recorded here so they stay visible. None is accepted by this audit.

| ID | Finding | Assessment |
|----|---------|------------|
| A1 (WR-04) | `run_mode`, `breaker_max_runs` and `breaker_window` are outside `actions_hash` (`document.py:111-117`). After approval, the owner or a forger can change them: restart mode, or up to 100 runs per second, which weakens the follower's loop protection. It cannot add or change actions, so T-03-25 holds. README line 142 says "hash of the actions" without noting that these settings follow the owner. | Low to medium. Needs a decision: bind the settings into the hash, clamp mirrored limits locally, or document it. |
| A2 (iteration-2 WR-01) | `manager.py:1007-1017` drops an unpublishable document with one log line and no Repairs issue. | Consistency, not privilege. |
| A3 (IN-05) | A foreign claim replayed during start is healed without an `ownership_claim` or `doc_overwritten` issue. | Healing is present, only the report is missing. |
| A4 (IN-02) | `_parse_mirrors` does not call `is_valid_device_id`. | Needs a poisoned local Store; no foreign execution path. |
| A5 (IN-03) | `runner.py:140` logs deep-validation text (up to 500 chars) for approved mirrors, which may quote action data. | Only reachable after user approval. |
| A6 | `field`, `error` and `device_ids` placeholders in `config_flow.py` are passed unescaped. They feed form error alerts, not Markdown. Not checked in a frontend. | Low. |
| A7 | `repairs.py:11` imports `voluptuous` instead of `probatio`. | Not a security issue. |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-02 | 40 | 40 | 0 | gsd-security-auditor (ASVS 1, block_on high) |

Method: register built from the `<threat_model>` blocks of plans 03-01..03-08. Each mitigate threat checked by reading the cited code at HEAD `6dbfa63`. The 19 named evidence tests (28 parametrized cases) ran with 28 passed and 0 skipped, so a real Mosquitto was exercised.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-02
