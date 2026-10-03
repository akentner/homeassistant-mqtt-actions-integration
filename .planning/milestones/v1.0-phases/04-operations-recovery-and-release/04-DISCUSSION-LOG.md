# Phase 4: Operations, Recovery and Release - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-02
**Phase:** 4-Operations, Recovery and Release
**Areas discussed:** Re-trigger and acknowledgements; Roster, heartbeat and duplicate id; Ownership, import/export, resync; Per-instance mode and diagnostics; Release, docs and CI

---

## Re-trigger and acknowledgements

| Question | Options | Selected |
|----------|---------|----------|
| What does the re-trigger run? | Current state / Explicit trigger only / Like the test button | Current state |
| Scope of a call | One device, all instances / Device or all own devices / With instance filter | One device, all instances |
| How the caller sees who executed | Service response with timeout / Event on the bus / Both | Service response with timeout |
| Limits | 1 per device per 5 s, constants / Configurable per hub / Value left to the planner | 1 per device per 5 s, constants |

**User's choice:** All recommended options.
**Notes:** Builds on the non-retained test topic of Phase 2.

---

## Roster, heartbeat and duplicate id

| Question | Options | Selected |
|----------|---------|----------|
| Presence heartbeat | Periodic, not retained / Retained / Last Will | Periodic, not retained (30 s, offline after 90 s) |
| Where the roster is shown | Sensor on the hub / Service with response / Both | Sensor on the hub |
| Duplicate id detection | Session id plus Repairs fix / Report only / Automatic new id | Session id plus Repairs fix |
| Devices of the copy on fix | Discard locally, broker untouched / Keep as new devices / User chooses | Discard locally, broker untouched |

**User's choice:** All recommended options.
**Notes:** Last Will rejected because HA owns the MQTT connection.

---

## Ownership, import/export, resync

| Question | Options | Selected |
|----------|---------|----------|
| Ownership change vs. pinning | Adopt orphans only / Hand off and adopt / Export and import only | Adopt orphans only |
| Where adoption is triggered | Service with device selector / Repairs hint with fix / Button on the mirror | Service with device selector |
| Export and import | Services with JSON, new UUIDs / Keep UUIDs on import / Both by parameter | Services with JSON, new UUIDs |
| Manual resync | Service plus hub button / Service only / Button only | Service plus hub button |

**User's choice:** All recommended options.
**Notes:** SYN-07 reads "transfer or adopt"; only adoption is implemented, active hand-off is deferred. During this area the user added a free-text wish: "In der Konfiguration von Instanzen möchte ich ebenfalls die Entitäten sehen, so wie bei anderen Integrationen auch." Clarified with a follow-up question; chosen: own and mirrored devices including their entities visible on the integration page (recorded as D-13, technical feasibility left to research).

---

## Per-instance mode and diagnostics

| Question | Options | Selected |
|----------|---------|----------|
| Meaning of the modes | run / observe / disabled / run and disabled only / Modes plus time limit | run / observe / disabled |
| Where the mode is set | Select entity per device / Service set_mode / Flow for own devices, service for mirrors | Select entity per device |
| WR-04 (settings outside the hash) | Bind into the hash / Clamp locally / Document only | Bind into the hash |
| Diagnostics content | Structure visible, contents redacted / Everything except credentials / Minimal | Structure visible, contents redacted |

**User's choice:** All recommended options.

---

## Release, docs and CI

| Question | Options | Selected |
|----------|---------|----------|
| Release | Tag triggers GitHub release / Release-Please / Manual script | Tag triggers GitHub release |
| Documentation | README plus docs/ / Everything in README / MkDocs site | README plus docs/ |
| Test tiers in CI | One job per tier / One job as today / Matrix with markers | One job per tier |

**User's choice:** All recommended options.

---

## Claude's Discretion

Service names and schemas, topic and payload field names, request-id cache size, timeouts, translation keys, Repairs wording, export file format, transfer marker encoding, mode select implementation, CI job layout.

## Deferred Ideas

- Active hand-off of a device between instances
- Follower-local actions on mirrors (backlog 999.1, MAP-01)
- Keep-UUID import
- Time limit on observe and disabled
- Residual Phase 3 review items A2 to A7
