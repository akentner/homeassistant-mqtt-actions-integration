---
phase: "02"
slug: "select-devices-and-reliable-execution"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-30"
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Broker to state subscription | Payload text and retain flag come from any party with write access to the state topic | Untrusted payload text |
| Broker to test topic subscription | Anyone with write access to the test topic can ask a device to run an action | Untrusted payload text |
| Retained broker messages | A retained message on a subscribed topic is replayed on every (re)subscribe | Retained payloads |
| Subentry data to discovery templates | Option names and StateValues are user-authored text embedded in templates evaluated by core MQTT | User-authored text |
| User-authored actions to the combined Script | Action text runs with full local service access; only the dispatch condition is generated | Action sequences |
| Store on disk to Manager | Persisted baselines, tripped map and stored subentry data are read back at start | Persisted state |
| UI form input to stored subentry data | User-typed names, values, actions and numbers become persisted configuration and later template and payload text | User-authored text, numbers |
| Repairs and log output | Text shown to the user must not carry action data | Device name, limits |
| Discovery payload to core | Component keys and unique ids become entity registry entries | Identifiers |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Tampering / Elevation | value_template and command_template built from option names and StateValues | high | mitigate | `discovery._literal` emits every user string as a `json_dumps` literal (`discovery.py:26-33`); hostile-string tests through real core discovery (`test_discovery_select.py`) | closed |
| T-02-02 | Tampering | payload-to-option mapping | medium | mitigate | Accepted-values map decides the option (`state.py:45`); same trim and lower rule in tracker and Select template; only device id and canonical value enter run variables | closed |
| T-02-03 | Repudiation | log lines for unknown payloads | low | mitigate | `_log_ignored` logs a truncated repr (`manager.py:588-595`, cap `MAX_LOGGED_PAYLOAD_LENGTH`) | closed |
| T-02-04 | Denial of service | malformed or duplicate stored options crash reconcile | medium | mitigate | `model.py:99-143` drops malformed, duplicate and unencodable options; `test_spec_select_drops_malformed_options` | closed |
| T-02-05 | Denial of service | unbounded serial queue from rapid state changes | medium | mitigate | Script `queued` with `max_runs=SERIAL_QUEUE_LIMIT` (10) and `max_exceeded="WARNING"` (`runner.py:93-102`); breaker backstop | closed |
| T-02-06 | Repudiation | dropped, cancelled or superseded run clears or fakes the failure state | low | mitigate | Issue cleared only by a run that returned a result and is the latest enqueue (`runner.py:177-187`); `CancelledError` never caught | closed |
| T-02-07 | Tampering | user text inside the generated choose conditions | medium | mitigate | Conditions compare the run variable with the sha256-derived hex key only (`runner.py:75-87`, `model.py:42-49`); actions validated before and after assembly | closed |
| T-02-08 | Elevation of privilege | broker user publishes to the test topic to run actions | medium | mitigate | Only payloads equal to a StateValue run anything (`manager.py:572-579`); README names the test topic as a second trigger source and extends ACL guidance; TRU-04 (Phase 3) extends it | closed |
| T-02-09 | Tampering | retained message on the test topic replays actions at every restart | high | mitigate | `_on_test_message` returns for `msg.retain` (`manager.py:570`); button publishes with `retain` False; `test_retained_test_message_is_ignored` | closed |
| T-02-10 | Repudiation | log forging through unknown test payloads | low | mitigate | Reuses `_log_ignored` (truncated repr, one line) | closed |
| T-02-11 | Tampering | button entity survives after its option was removed while MQTT was unavailable | low | accept | Tombstones are in memory only; an orphaned registry entry can be deleted by the user; no action can run from it | closed |
| T-02-12 | Denial of service | a press fans out to every instance subscribed to the test topic | low | accept | Single instance in Phase 2 (A9); documented in README; revisited in Phase 3 | closed |
| T-02-13 | Denial of service | self-triggering loop from actions that toggle their own device | high | mitigate | Per-device sliding-window breaker (`breaker.py`, `manager.py:471-515`); `test_self_toggling_action_is_stopped`; verified end to end in UAT test 5 | closed |
| T-02-14 | Tampering | a restart would reset protection and let the loop resume | medium | mitigate | Tripped flag persisted as config hash (`manager.py:311-326`, `517-537`); verified across a real HA restart in UAT test 5 | closed |
| T-02-15 | Repudiation | the user does not know why a device stopped acting | low | mitigate | Repairs issue `circuit_breaker_<device id>` in EN and DE plus one log warning; rendered in the real UI in UAT test 5 | closed |
| T-02-16 | Tampering | malformed or stale tripped data breaks setup or pauses the wrong device | low | mitigate | Tolerant loader, pruning, hash-mismatch release (`manager.py:107-112`, `201`, `525-530`) | closed |
| T-02-17 | Denial of service | the counting window is volatile, so a loop that survives a restart gets a fresh window | low | accept | By design (D-17); a persistent loop re-trips within one window | closed |
| T-02-18 | Information disclosure | trip warning or issue text leaks action data | low | mitigate | Only device name and the two limits are logged and shown (`manager.py:504-509`, `549-553`) | closed |
| T-02-19 | Tampering | hostile or malformed StateValue and StateFriendlyName typed in the flow | medium | mitigate | `validate_option` rejects them before storing (`model.py:181-218`, `config_flow.py:380`, `456`) | closed |
| T-02-20 | Denial of service | oversized option lists or text bloat retained discovery and Repairs text | medium | mitigate | `MAX_OPTIONS` 50 and `MAX_TEXT_LENGTH` 64; menu hides Add at the cap | closed |
| T-02-21 | Tampering | float or out-of-range breaker numbers stored as data | low | mitigate | `validate_breaker` range checks and `int(...)` coercion; loader falls back to defaults | closed |
| T-02-22 | Information disclosure | validation error text echoes action data | low | mitigate | `_async_check_actions` returns only the label and an error capped at `MAX_FLOW_ERROR_LENGTH` | closed |
| T-02-23 | Tampering | device_id targets in option actions cannot resolve on other instances | low | mitigate | Warn-then-confirm per option via `find_device_ids` | closed |
| T-02-24 | Tampering | in-place mutation of stored subentry data by the flow | low | mitigate | `copy.deepcopy` draft, single commit; `test_flow_never_mutates_stored_data_before_done` | closed |
| T-02-SC | Tampering | package installs (repeated in each of the five plans, counted once) | low | accept | No plan of the phase installs anything; `manifest.json` `requirements` is empty | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02-11 | A button can survive in the entity registry if its option was removed while MQTT was unavailable; no action can run from it | Plan 02-03 threat register | 2026-09-30 |
| AR-02-02 | T-02-12 | Single instance in Phase 2; a test press fans out to instances subscribed to the test topic; revisited in Phase 3 | Plan 02-03 threat register | 2026-09-30 |
| AR-02-03 | T-02-17 | The breaker counting window is volatile by design (D-17); a loop that survives a restart re-trips within one window | Plan 02-04 threat register | 2026-09-30 |
| AR-02-04 | T-02-SC | No package installs in any plan of the phase | Plans 02-01 to 02-05 threat registers | 2026-09-30 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Observations (non-blocking, not counted in threats_open)

- **Test topic bypasses the circuit breaker** (review WR-03, disposition open). `_on_test_message` (`manager.py:561-586`) enqueues without `breaker.record()`. Intentional (D-13/A2), pinned by `test_manager_breaker.py:259`, documented in the README. An action that publishes to its own test topic is outside T-02-13, which covers the state topic. Serial mode still caps it at 10 queued runs; restart mode has no cap. Handle in the Phase 3 trust gate and ACL work (TRU-04) or with a small separate limit for test presses.
- **Device name has no length cap.** The `CONF_NAME` field flows into discovery and Repairs text; T-02-20 covers option text and option count only.
- Review items next to registered threats, none changing a verdict: WR-02 (Switch `value_template` lacks `trim`, next to T-02-02), WR-04 (shared Repairs issue id, next to T-02-06), IN-06 (memory-only tombstones, already accepted as T-02-11), IN-04 (reconfigure flow `KeyError` on a malformed stored option).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-30 | 25 | 25 | 0 | gsd-security-auditor (ASVS 1, block_on high; full suite 426 passed) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-30
