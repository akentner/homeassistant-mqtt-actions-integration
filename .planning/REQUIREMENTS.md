# Requirements: MQTT Actions Integration

**Defined:** 2026-09-29
**Core Value:** A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.

## v1 Requirements

### Foundation

- [x] **FND-01**: User can install the integration via HACS (`hacs.json`, `manifest.json`, local brand icon, domain `mqtt_actions`, minimum HA 2026.9.0)
- [x] **FND-02**: Every push runs hassfest, HACS validation, Ruff and pytest in CI
- [x] **FND-03**: User can set up the integration via Config Flow (one hub per instance, requires MQTT); a persistent random instance ID is generated
- [x] **FND-04**: All UI strings are available in English and German
- [x] **FND-05**: Integration waits for the MQTT client at startup and resumes cleanly after broker reconnects

### Devices

- [x] **DEV-01**: User can create a Switch device via the UI with a name
- [x] **DEV-02**: User can configure `onChangeToOn` and `onChangeToOff` actions of a Switch with the HA action selector
- [x] **DEV-03**: User can create a Select device with multiple options, each with StateValue, StateFriendlyName and actions
- [x] **DEV-04**: User can edit StateFriendlyName and actions of an option; StateValue is immutable after creation
- [x] **DEV-05**: Configured actions are validated on input; actions targeting instance-local `device_id`s produce a warning
- [x] **DEV-06**: User can choose per device how actions run on rapid state changes (serial queue by default, or restart)
- [x] **DEV-07**: User can run a device's actions locally via a test button without changing its state
- [x] **DEV-08**: Action failures are surfaced to the user (log and Repairs issue), not silently swallowed

### State & Actions

- [x] **STA-01**: Switching a device in the HA UI on any instance publishes to the shared retained state topic (command topic equals state topic)
- [x] **STA-02**: An external MQTT message on the state topic triggers the same actions as a UI change
- [x] **STA-03**: On a real state change, the actions run locally on every participating instance
- [x] **STA-04**: Retained state received at startup or reconnect only sets the baseline and runs no actions (optional per-device "run on startup" flag)
- [x] **STA-05**: The last processed state per device is persisted; only real edges trigger actions
- [x] **STA-06**: A per-device circuit breaker stops action loops caused by actions that toggle their own device
- [x] **STA-07**: A Select payload that matches no configured StateValue is ignored and logged

### Discovery

- [x] **DSC-01**: The owner publishes MQTT Discovery for every entity (UUID `unique_id`, availability, device info)
- [x] **DSC-02**: Discovery is removed only on explicit user deletion, never on unload or shutdown
- [x] **DSC-03**: The owner republishes discovery if it was removed by a follower deleting the entity
- [x] **DSC-04**: User can trigger a manual resync that republishes config and discovery of all owned devices

### Central Config & Ownership

- [x] **SYN-01**: The owner publishes one retained, versioned (`schema_version`) config document per device
- [x] **SYN-02**: Another HA instance reading the central config creates the same devices as read-only mirrors
- [x] **SYN-03**: Every device has one owner (its creator); only the owner can edit or delete it; followers pin the owner and raise a Repairs issue on conflicting claims
- [x] **SYN-04**: The owner reconciles and republishes its config on every MQTT reconnect
- [x] **SYN-05**: Followers never delete devices because a message is absent; removal is driven by tombstone or grace window
- [x] **SYN-06**: Deleting a device requires an explicit confirmation stating it is removed on all connected instances, then unpublishes central config and discovery
- [x] **SYN-07**: User can transfer ownership of a device or adopt an orphaned device
- [x] **SYN-08**: User can export devices to JSON and import them
- [x] **SYN-09**: User can set per instance and device whether actions run, are only observed, or are disabled
- [x] **SYN-10**: A duplicate instance ID (cloned or restored instance) is detected and reported

### Trust & Security

- [x] **TRU-01**: Remote-provided actions are not executed by default (deny)
- [x] **TRU-02**: User can approve a remote device's actions per instance via Repairs; approval is bound to the action hash, so changed actions require re-approval
- [x] **TRU-03**: Every action sequence received from the broker is validated against the script schema, and a service denylist is enforced at execution time
- [x] **TRU-04**: Documentation includes a broker ACL example binding each instance to its own topics

### Operations

- [x] **OPS-01**: A service re-triggers the actions on all approved instances (non-retained, `request_id` dedupe, rate-limited)
- [x] **OPS-02**: Instances acknowledge a re-trigger, and the caller can see which instances executed it
- [x] **OPS-03**: User can see the connected instances (roster with presence heartbeat)
- [x] **OPS-04**: Diagnostics export with sensitive data redacted
- [x] **OPS-05**: README and docs cover setup, trust model, limitations; releases are automated with manifest version in step with the tag
- [x] **OPS-06**: Test suite covers unit level, a real-Mosquitto tier, and multi-instance scenarios via an in-memory fake broker

## v2 Requirements

Deferred to a future release. Tracked but not in the current roadmap.

### Domains

- **DOM-01**: Button and Number devices
- **DOM-02**: Light, Cover and Climate devices

### Security & Mapping

- **SEC-01**: Signed central config
- **MAP-01**: Per-instance entity mapping for actions with instance-local entity IDs

### Availability

- **AVL-01**: Heartbeat-based entity availability when the owner is offline

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Peer-to-peer multi-writer editing | Ownership model chosen to avoid conflict resolution |
| Referencing local scripts by name | Inline action sequences chosen for portability |
| Retained commands or retained re-trigger | Would replay on every reconnect |
| Auto-running actions on retained state at startup | Causes action storms; baseline-only chosen |
| Auto-accepting remote config | Remote actions run with full local privileges |
| Second MQTT connection | HA's built-in MQTT client is used |
| Custom action editor or DSL | Native HA action selector is enough |
| Cloning remote_homeassistant / entity state sync | Different product; only actions and devices are synced |
| Exactly-once delivery | Not achievable across independent HA processes; at-least-once documented |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| FND-03 | Phase 1 | Complete |
| FND-04 | Phase 1 | Complete |
| FND-05 | Phase 1 | Complete |
| DEV-01 | Phase 1 | Complete |
| DEV-02 | Phase 1 | Complete |
| DEV-03 | Phase 2 | Complete |
| DEV-04 | Phase 2 | Complete |
| DEV-05 | Phase 1 | Complete |
| DEV-06 | Phase 2 | Complete |
| DEV-07 | Phase 2 | Complete |
| DEV-08 | Phase 1 | Complete |
| STA-01 | Phase 1 | Complete |
| STA-02 | Phase 1 | Complete |
| STA-03 | Phase 3 | Complete |
| STA-04 | Phase 1 | Complete |
| STA-05 | Phase 1 | Complete |
| STA-06 | Phase 2 | Complete |
| STA-07 | Phase 2 | Complete |
| DSC-01 | Phase 1 | Complete |
| DSC-02 | Phase 1 | Complete |
| DSC-03 | Phase 3 | Complete |
| DSC-04 | Phase 4 | Complete |
| SYN-01 | Phase 3 | Complete |
| SYN-02 | Phase 3 | Complete |
| SYN-03 | Phase 3 | Complete |
| SYN-04 | Phase 3 | Complete |
| SYN-05 | Phase 3 | Complete |
| SYN-06 | Phase 3 | Complete |
| SYN-07 | Phase 4 | Complete |
| SYN-08 | Phase 4 | Complete |
| SYN-09 | Phase 4 | Complete |
| SYN-10 | Phase 4 | Complete |
| TRU-01 | Phase 3 | Complete |
| TRU-02 | Phase 3 | Complete |
| TRU-03 | Phase 3 | Complete |
| TRU-04 | Phase 3 | Complete |
| OPS-01 | Phase 4 | Complete |
| OPS-02 | Phase 4 | Complete |
| OPS-03 | Phase 4 | Complete |
| OPS-04 | Phase 4 | Complete |
| OPS-05 | Phase 4 | Complete |
| OPS-06 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 44 total
- Mapped to phases: 44
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-29*
*Last updated: 2026-09-29 after roadmap creation (traceability filled)*
