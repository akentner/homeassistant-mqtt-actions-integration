# Phase 4: Operations, Recovery and Release - Context

**Gathered:** 2026-10-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 turns the working multi-instance setup into something a user can operate with confidence and ship: a re-trigger service with acknowledgements, a presence heartbeat and roster, duplicate instance ID detection, a manual resync, adoption of orphaned devices, JSON export and import, a per-instance and per-device mode (run, observe, disabled), redacted diagnostics, documentation, an automated tagged release and a CI split by test tier.

Requirements: OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OPS-06, SYN-07, SYN-08, SYN-09, SYN-10, DSC-04.

Not in this phase: active hand-off of a device to another instance, follower-local actions on mirrored devices (backlog 999.1, MAP-01), new device kinds, signed config (SEC-01), heartbeat-based entity availability (AVL-01).

</domain>

<decisions>
## Implementation Decisions

### Re-trigger and acknowledgements (OPS-01, OPS-02)
- **D-01:** The re-trigger service runs the actions of the trigger that matches the device's last acted state (for a Select, the current option). An optional parameter selects a different trigger. It never changes the entity state or the baseline, and it does not count toward the circuit breaker (same as the test button, Phase 2 D-13).
- **D-02:** One call targets exactly one device (required parameter) and reaches every instance that approved it. There is no "all devices" call and no instance filter in v1.
- **D-03:** The service returns a service response (`SupportsResponse`): per instance a status of executed, not approved, paused, disabled/observing, error, or no answer, collected within a timeout window (start value 5 s). It does not wait longer than the window. No event-bus variant in v1.
- **D-04:** Every call carries a `request_id` (UUID). Receivers remember the last N ids and ignore duplicates. The message is not retained. Per device, at most one re-trigger per 5 s is accepted; further calls are rejected with an error to the caller. The values are constants in `const.py`, not user-configurable. — **Reversibility:** costly — topic name, payload fields and acknowledgement shape become a cross-instance wire contract.

### Roster, heartbeat and duplicate instance ID (OPS-03, SYN-10)
- **D-05:** Every instance publishes a heartbeat every 30 s on a new non-retained topic under `<base>/v1/instances/<instance_id>/`, carrying instance id, name, integration version, device count and a random per-start session id. A peer counts as offline after 90 s without a heartbeat, which also covers crashes. The retained availability topic and the Phase 3 prune logic stay as they are. A retained heartbeat is rejected because a crashed peer would look current forever. A Last Will is not possible (HA owns the MQTT connection, Phase 3 D-19). — **Reversibility:** costly — heartbeat topic and payload are a wire contract and the ACL in `docs/broker-acl.md` must grant it.
- **D-06:** The roster is a diagnostic sensor on the hub: state is the number of online instances, attributes list name, id, version, last seen and online or offline. There is no separate roster service.
- **D-07:** Duplicate id detection uses the session id: an instance that hears a heartbeat with its own instance id but a different session id raises a Repairs issue. The issue has a fix flow that gives this instance a new instance id. Nothing happens automatically.
- **D-08:** The fix flow discards the copy's own devices locally only: no tombstone, no discovery deletion, no state clearing. The original keeps ownership and topics, and the copy then sees the same devices as mirrors of the original. A copy that wants independent devices re-creates them (or imports an export).

### Ownership, export, import, resync (SYN-07, SYN-08, DSC-04)
- **D-09:** SYN-07 is implemented as adoption of orphaned devices only. A device can be adopted when its owner is offline according to the roster, or on explicit confirmation (`force`). Adoption publishes a new document with the new owner and a transfer marker, and followers release the owner pin only for a document that carries that marker. This is the single exception to Phase 3 D-17 (first owner wins, no takeover); everything else in D-17 stays. Active hand-off from the current owner (offer and accept) is out of scope. — **Reversibility:** one-way — the transfer marker becomes part of the document schema (needs a `schema_version` decision) and changes the pin rule followers apply.
- **D-10:** Adoption is a service (`adopt_device`, device selector). It fails with a clear error when the owner is online, naming `force: true`. A mirror has no UI (Phase 3 D-08), so no new editing surface is added.
- **D-11:** Export is a service that returns JSON as the service response (all owned devices or a selection) and can also write a file under `/config`. Import is a service that takes JSON or a file path. Import always assigns new device UUIDs, so nothing collides with existing devices, and imported devices are owned by this instance. No option to keep UUIDs in v1. — **Reversibility:** costly — the export format is a user-facing file contract once people keep backups.
- **D-12:** Manual resync is a service and a button on the hub device. Both run the existing Phase 3 order (documents, then discovery, then `online`).

### Visibility on the integration page
- **D-13:** The user wants the owned and mirrored devices and their entities to be visible on the MQTT Actions integration page, like other integrations show devices and entities. Hub entities (roster sensor, resync button, and the mode selects below) belong there. Mirrored and owned discovery devices should additionally be linked to the MQTT Actions config entry in the device registry. Whether the page then also lists entities that belong to the core MQTT entry is open; the researcher must verify what Home Assistant actually shows. Entities created by MQTT Discovery stay the contract for the device entities (project constraint).

### Per-instance and per-device mode (SYN-09)
- **D-14:** Three modes, local to the instance and never part of the document: `run` (as today), `observe` (state and baseline are tracked, no actions run, each suppressed run is logged), `disabled` (the entity remains, no processing, no baseline). The modes apply to owned and mirrored devices.
- **D-15:** The mode is set through a configuration-category select entity per device on this instance, stored locally. This is a native, instance-local entity and not a Discovery entity, because Discovery messages are shared across instances. The researcher must settle how a native select coexists with the Discovery device of the same device id. Because the select is a hub-owned entity it also shows on the integration page (D-13).
- **D-16:** Resolve WR-04 from Phase 3 by binding `run_mode`, `breaker_max_runs` and `breaker_window` into `actions_hash`. A changed value then needs re-approval like changed actions, and the README sentence about the hash becomes true. Existing approvals lapse once; the planner must include a migration or an explicit one-time re-approval notice. — **Reversibility:** costly — the hash format changes and every existing approval is invalidated.

### Diagnostics (OPS-04)
- **D-17:** The diagnostics download shows structure and redacts content. Included: hub options (base topic, instance name), roster, device list (uuid, kind, owner, mode, approval state, breaker state, rev, hash). Redacted: action content (YAML, templates, entity ids, service data), full instance ids shortened, broker credentials and hostnames.

### Documentation, release and CI (OPS-05, OPS-06)
- **D-18:** Docs stay Markdown in the repo: the README is the entry point; `docs/` gets pages for operations (re-trigger, roster, resync, adoption, export and import, modes), diagnostics and troubleshooting. `docs/broker-acl.md` stays and is extended for the heartbeat topic. No docs generator.
- **D-19:** A tag `v*.*.*` triggers a release workflow that fails when `manifest.json` `version` differs from the tag, runs the test jobs, then creates a GitHub release with generated notes. No zip is needed for HACS. — **Reversibility:** costly — the tag and version scheme is what HACS users see.
- **D-20:** CI runs one job per test tier: unit (no broker), real Mosquitto (`tests/broker`) and multi-instance (fake broker). Mosquitto is installed only in the broker job. The release workflow requires all three.

### Claude's Discretion
- Service names and exact schemas, heartbeat and re-trigger topic names, payload field names, the number N of remembered request ids, the response timeout value, translation keys, Repairs wording, the format of the export file and its version field.
- How the transfer marker is encoded in the document and whether it needs a `schema_version` bump.
- How the mode select is implemented (platform, restore of state) and how the Discovery device and the native entity share one device in the registry.
- The structure of the CI jobs and the pytest markers or paths that separate the tiers.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions
- `.planning/phases/03-trust-central-config-and-ownership/03-CONTEXT.md` — D-01..D-19: approval gate, owner pinning (D-17, the rule D-09 here amends), mirrors in Store (D-08), hub removal (D-11), discovery healing (D-18, D-19).
- `.planning/phases/02-select-devices-and-reliable-execution/02-CONTEXT.md` — run modes, test button (the pattern D-01 follows), circuit breaker.
- `.planning/phases/01-walking-skeleton-installable-switch/01-CONTEXT.md` — topic layout, baseline and run-on-startup semantics.

### Phase 3 outputs
- `.planning/phases/03-trust-central-config-and-ownership/03-SECURITY.md` — threat register and open review items A1 (WR-04, resolved here by D-16) and A2 to A7.
- `.planning/phases/03-trust-central-config-and-ownership/03-VERIFICATION.md` and `03-UAT.md` — what was verified and how.
- `docs/broker-acl.md` — the ACL that must grant any new topic (heartbeat, re-trigger).
- `README.md` — trust model and limitations; the sentence on the approval hash must stay true.

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — OPS-01..06, SYN-07..10, DSC-04. SYN-07 says "transfer or adopt"; D-09 deliberately covers adoption only.
- `.planning/ROADMAP.md` — Phase 4 goal and success criteria; backlog item 999.1 (not in scope).

### Code touched by this phase
- `custom_components/mqtt_actions/topics.py` — topic helpers (`test_topic`, `availability_topic`) to extend.
- `custom_components/mqtt_actions/sync.py`, `manager.py`, `document.py` — presence tracking, owner pin, document schema and hash.
- `custom_components/mqtt_actions/runner.py`, `trust.py`, `repairs.py` — mode handling, approval, Repairs flows.
- `.github/workflows/ci.yml`, `.github/workflows/validate.yml` — existing CI to split and extend.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `topics.test_topic` and the test-button path in `manager.py` (Phase 2): a non-retained topic that every approving instance runs; the re-trigger reuses the pattern with a `request_id` and acknowledgements.
- `sync.online_instance_count()` and the availability wildcard cache (capped, Phase 3): the base for the roster and for "owner offline" in adoption; the heartbeat adds a timeout-based view.
- Phase 3 republish order (documents, discovery, `online`) in `manager.py`: reused unchanged by resync.
- `repairs.py` fix-flow machinery (approval flow): reused for the duplicate-id fix.
- `tests/fake_broker.py` (two or three hass instances on an in-memory broker) and `tests/broker/` (real Mosquitto): the second and third test tiers already exist.

### Established Patterns
- Services are registered in `async_setup`, not in `async_setup_entry` (hassfest rule).
- Instance-local state lives in the HA `Store`; shared state lives only in the document.
- Anything received from the broker is validated before use and shown escaped (`escape_markdown`).
- Constants such as limits and windows live in `const.py`.

### Integration Points
- `__init__.py`: service registration, new platforms (sensor, button, select) for the hub entities.
- `manager.py`: mode handling in the trigger path (`runner.can_run`), heartbeat task, request-id cache.
- `document.py`: `actions_hash` (D-16) and the transfer marker (D-09).
- Device registry: linking Discovery devices to the MQTT Actions entry (D-13).

</code_context>

<specifics>
## Specific Ideas

- The user hit the problem of not finding a device of another instance during the Phase 3 UAT ("where do I see the device of HA One on HA Two?"). D-13 comes straight from that: the integration page should list devices and entities the way other integrations do.
- The Phase 3 test setup (two HA containers on one Mosquitto with the documented ACL, under `~/ha-test/`) worked well for real-frontend checks and should be reusable for Phase 4 UAT.

</specifics>

<deferred>
## Deferred Ideas

- Active hand-off of a device from its current owner to another instance (offer and accept handshake). Phase 4 covers adoption of orphans only.
- Follower-local actions on mirrored devices, with per-instance entity mapping (backlog 999.1, MAP-01).
- Keep-UUID import for restoring after data loss (`keep_ids`), with collision handling.
- A time limit on `observe` and `disabled`.
- Residual Phase 3 review items A2 to A7 (see `03-SECURITY.md`) are not part of this phase unless the planner folds them in.

### Reviewed Todos (not folded)
None.

</deferred>

---

*Phase: 4-Operations, Recovery and Release*
*Context gathered: 2026-10-02*
