# Roadmap: MQTT Actions Integration

## Overview

The journey starts with a single-instance walking skeleton: an installable HACS integration in which a user creates a Switch whose MQTT state changes run Home Assistant actions locally, with startup and reconnect semantics correct from day one. Phase 2 adds Select devices and makes action execution predictable (run modes, test button, loop protection). Phase 3 delivers the core value: central retained config, owner/follower ownership and the trust gate ship together, so other instances mirror devices and run remote actions only after explicit approval. Phase 4 adds the operating tools (re-trigger, roster, recovery, import/export, diagnostics), documentation, the full test tiers and automated releases.

Ordering rationale: startup semantics, the single trigger source and the Select mapping change wire and behavior contracts, so they are fixed before any sync exists. No release contains follower apply before the trust gate. Tests are written with every phase (TDD mode is on); OPS-06 is assigned to Phase 4 because that is where all three test tiers (unit, real Mosquitto, multi-instance fake broker) exist together.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Walking Skeleton - Installable Switch** - HACS-installable integration where a Switch created in the UI runs its actions on MQTT state changes, safely across restarts (completed 2026-09-29)
- [x] **Phase 2: Select Devices and Reliable Execution** - Select devices with per-option actions, plus run modes, test button and loop protection (completed 2026-09-30)
- [x] **Phase 3: Trust, Central Config and Ownership** - Retained central config, owner/follower mirrors and the approval gate so every instance runs actions locally and safely (completed 2026-10-02)
- [ ] **Phase 4: Operations, Recovery and Release** - Re-trigger service, roster, resync/import/export/transfer, diagnostics, docs, test tiers and release automation

## Phase Details

### Phase 1: Walking Skeleton - Installable Switch

**Goal:** As a Home Assistant user, I want to create a Switch device whose MQTT state changes run my configured actions, so that I need no YAML automation.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, FND-05, DEV-01, DEV-02, DEV-05, DEV-08, STA-01, STA-02, STA-04, STA-05, DSC-01, DSC-02
**Success Criteria** (what must be TRUE):
  1. User can install the integration through HACS, add it once via the Config Flow (it requires MQTT and generates a persistent instance ID), and see every UI string in English or German.
  2. Every push to the repository runs hassfest, HACS validation, Ruff and pytest in CI, and the pipeline passes.
  3. User can create a Switch device with a name and set its `onChangeToOn` and `onChangeToOff` actions with the HA action selector; invalid actions are rejected on input and actions targeting instance-local `device_id`s show a warning.
  4. The Switch appears in HA through MQTT Discovery (UUID `unique_id`, availability, device info); toggling it in the HA UI or publishing to its retained state topic runs the matching actions locally on each real change, and a failing action is visible in the log and as a Repairs issue instead of being swallowed.
  5. After an HA restart, integration reload or broker reconnect, the integration starts cleanly even if MQTT is not ready yet, retained state only sets the baseline (no actions run unless the device's "run on startup" flag is on), only real state changes trigger actions, and the entity stays until the user explicitly deletes the device.

**Plans:** 6/6 plans complete

Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Package-legitimacy gate and uv/Ruff/PHACC tooling scaffold (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-02-PLAN.md — Tracer: one Switch end to end, one-way identifier freeze, D-13 spike gate (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 01-03-PLAN.md — Hub and Switch subentry flows with validation, device_id warning, en/de translations (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 01-04-PLAN.md — Trigger path: decision function, persisted baseline, failure surfacing, real-broker retain test (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 01-05-PLAN.md — Discovery contract and lifecycle: change, delete, orphan, hub removal, reconnect, unload (wave 5)

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 01-06-PLAN.md — HACS metadata, SHA-pinned CI, public repo gate, CI green and manual UAT list (wave 6)

**UI hint**: yes

### Phase 2: Select Devices and Reliable Execution

**Goal:** As a Home Assistant user, I want to create Select devices whose options each run their own actions, so that multi-state MQTT devices drive my setup predictably.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: DEV-03, DEV-04, DEV-06, DEV-07, STA-06, STA-07
**Success Criteria** (what must be TRUE):
  1. User can create a Select device with several options, each with StateValue, StateFriendlyName and actions; choosing an option in the HA UI or publishing its StateValue to the state topic runs that option's actions.
  2. User can later edit an option's StateFriendlyName and actions, while its StateValue is locked after creation.
  3. A Select payload that matches no configured StateValue is ignored and logged: no actions run and the entity keeps its state.
  4. User can choose per device whether rapid state changes run their actions as a serial queue (default) or as restart, and can press a test button that runs a device's actions locally without changing its state.
  5. An action that toggles its own device is stopped by a per-device circuit breaker instead of looping forever, and the user is told why.

**Plans:** 5/5 plans complete

Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Tracer: Select device runtime (DeviceSpec, accepted-values decision, select discovery with mapping templates, unknown-payload semantics) (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md — One Script per device: serial and restart run modes, queue bound, dropped and superseded run handling (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-03-PLAN.md — Test buttons per trigger on a non-retained test topic, button lifecycle with tombstones (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 02-04-PLAN.md — Per-device circuit breaker: trip, pause, Repairs issue, persisted tripped state, release paths (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 02-05-PLAN.md — Select option editor flow, run mode and breaker fields in the Switch and Select flows, en/de strings, README (wave 5)

**UI hint**: yes

### Phase 3: Trust, Central Config and Ownership

**Goal:** As a user with several HA instances, I want devices created on one instance to appear on the others once I approve them, so that every instance runs the actions locally.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SYN-01, SYN-02, SYN-03, SYN-04, SYN-05, SYN-06, TRU-01, TRU-02, TRU-03, TRU-04, STA-03, DSC-03
**Success Criteria** (what must be TRUE):
  1. A device created on one instance is published as one retained, versioned (`schema_version`) config document; a second instance on the same broker creates the same device as a read-only mirror, the owner republishes on every MQTT reconnect, and a missing message never deletes a mirror (removal only follows a tombstone or grace window).
  2. A mirrored device's actions do not run on an instance until the user approves them there via Repairs; approval is bound to the action hash so changed actions need re-approval; every action sequence received from the broker is schema-validated, denylisted services are refused at execution time, and the docs include a broker ACL example binding each instance to its own topics.
  3. After approval, a real state change (from the HA UI on any instance or from an external MQTT message) runs the device's actions locally on every participating instance.
  4. Only a device's owner can edit or delete it; followers pin the owner and raise a Repairs issue on conflicting ownership claims, and if a follower removes the discovered entity the owner republishes its discovery.
  5. Deleting a device requires an explicit confirmation stating that it is removed on all connected instances, after which its central config and discovery are unpublished and the device disappears everywhere.

**Plans:** 8/8 plans complete

Plans:
- [x] 03-08-PLAN.md

**Wave 1**
- [x] 03-01-PLAN.md — Wire contract: config document, strict parsing, denylist walker, owner publish, FakeBroker and gateway seams (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-02-PLAN.md — Owner lifecycle: delete order with config tombstone, echo and foreign-write healing, ownership claims, discovery healing (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-03-PLAN.md — Owner flows: all-instances delete confirmation with instance presence, hub removal keep or delete option (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 03-04-PLAN.md — Follower: read-only mirrors, owner pinning, schema gate, Store persistence (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 03-05-PLAN.md — Follower removal: tombstone, grace-window prune gated by owner availability, registry cleanup (wave 5)

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 03-06-PLAN.md — Trust gate: hash-bound approval via Repairs, guarded Script, blocked state, execution-time denylist (wave 6)

**Wave 7** *(blocked on Wave 6 completion)*
- [x] 03-07-PLAN.md — Tested broker ACL document, multi-instance acceptance scenarios, README (wave 7)

**UI hint**: yes

### Phase 4: Operations, Recovery and Release

**Goal:** As a user running several HA instances, I want to re-trigger actions, see who is connected and recover devices, so that I can operate the setup with confidence.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OPS-06, SYN-07, SYN-08, SYN-09, SYN-10, DSC-04
**Success Criteria** (what must be TRUE):
  1. User can call a service that re-triggers the actions on all approved instances (non-retained, `request_id` dedupe, rate-limited) and sees which instances acknowledged and executed it.
  2. User can see the connected instances in a roster with presence heartbeat, and a duplicate instance ID (cloned or restored instance) is detected and reported.
  3. User can run a manual resync that republishes config and discovery of all owned devices, export devices to JSON and import them, and transfer ownership of a device or adopt an orphaned one.
  4. User can set per instance and device whether actions run, are only observed, or are disabled, and can download diagnostics with sensitive data redacted.
  5. README and docs cover setup, trust model and limitations; a tagged release is built automatically with the manifest version matching the tag; CI runs the unit, real-Mosquitto and multi-instance fake-broker test tiers.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Walking Skeleton - Installable Switch | 6/6 | Complete    | 2026-09-29 |
| 2. Select Devices and Reliable Execution | 5/5 | Complete    | 2026-09-30 |
| 3. Trust, Central Config and Ownership | 8/8 | Complete    | 2026-10-02 |
| 4. Operations, Recovery and Release | 0/0 | Not started | - |

## Backlog

### Phase 999.1: Per-instance local actions on mirrored devices (followers add own actions, relates to MAP-01) (BACKLOG)

**Goal:** [Captured for future planning] A follower instance can add its own local actions to a mirrored device, on top of the owner's document (for example different entities per instance). Found during Phase 3 UAT: mirrors are read-only today.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.2: Evaluate native switch/select entities instead of MQTT Discovery (BACKLOG)

**Goal:** [Captured for future planning] Entities owned by the MQTT Actions config entry would show the full device and entity count on our integration page (incl. mirrored devices on other instances), remove discovery healing/ghost-entity handling and DSC-04. Costs: breaks the PROJECT.md Discovery constraint, rewrite of phase 1-3 publishing, loses non-HA consumers. Origin: Phase 4 research on D-13 (a device belongs to exactly one config entry); Phase 4 uses companion devices meanwhile.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
