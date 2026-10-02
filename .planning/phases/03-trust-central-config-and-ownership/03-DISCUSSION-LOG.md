# Phase 3: Trust, Central Config and Ownership - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-01
**Phase:** 3-Trust, Central Config and Ownership
**Areas discussed:** Trust gate and approval, Mirror storage and removal, Central config document and sync, Ownership / delete / discovery healing

---

## Trust gate and approval

| Question | Options | Selected |
|----------|---------|----------|
| Trust policy | Per-device approval only / Hub deny-ask / Hub deny-ask-auto | Per-device approval only |
| Approval UX | Full view + re-approval / Summary + re-approval / Diff on change | Full view + re-approval |
| Denylist scope | Fixed constant, mirrors only / Constant + hub extension / All actions | Fixed constant, mirrors only |
| Templates and nesting | Recursive, reject templates / Recursive, warn on templates / Top-level only | Recursive, warn on templates |
| Runtime check | Enforce at runtime / Static only | Enforce at runtime |

## Mirror storage and removal

| Question | Options | Selected |
|----------|---------|----------|
| Mirror store | Store, no subentries / Read-only subentries | Store |
| Detecting missed deletes | Grace window / Owner manifest / Manual only | Grace window |
| Grace protection | Delete only if owner online / Mark stale, user confirms / Live tombstone only | Delete only if owner online |
| Hub removal | Keep all / Confirm and delete all / User chooses in dialog | User chooses in dialog |

## Central config document and sync

| Question | Options | Selected |
|----------|---------|----------|
| Document contents | All but breaker state / Core only, behavior local | All but breaker state |
| Newer schema_version | Reject + Repairs / Best effort | Reject + Repairs |
| Change detection | Hash + rev, owner heals / Hash only | Hash + rev, owner heals |

## Ownership, delete and discovery healing

| Question | Options | Selected |
|----------|---------|----------|
| Delete confirmation | Step with instance list / Typed name / Simple yes-no | Step with instance list |
| Owner conflict | First owner wins + Repairs / Pause device too | First owner wins + Repairs |
| Follower deletes entity | Republish, throttled / Only on reconnect | Republish, throttled |
| Availability | Owner offline = unavailable / Always available | Owner offline = unavailable |

## Claude's Discretion

- Window/throttle values, hash algorithm, Store layout, wording, how the hub-removal choice is offered, how the delete step learns mirroring instances.

## Deferred Ideas

- Hub-wide ask/auto policy, user-extendable denylist, action diff view, owner manifest topic, typed-name delete, transfer/adopt and roster (Phase 4).
