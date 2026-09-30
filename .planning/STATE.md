---
gsd_state_version: "1.0"
current_phase: 03
current_phase_name: trust-central-config-and-ownership
status: executing
stopped_at: Completed 03-02-PLAN.md
last_updated: "2026-09-30T23:23:50.400Z"
last_activity: 2026-10-01
last_activity_desc: Phase 03 execution started
state_head: e2f04af72a8a79aa578660b2b07da0e4e9c87992
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 18
  completed_plans: 13
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-28)

**Core value:** A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.
**Current focus:** Phase 03 — trust-central-config-and-ownership

## Current Position

Phase: 03 (trust-central-config-and-ownership) — EXECUTING
Plan: 3 of 7
Status: Ready to execute
Last activity: 2026-10-01 — Phase 03 execution started

Progress: [█████░░░░░] 50% of Phase 01 plans

## Performance Metrics

**Velocity:**
- Total plans completed: 11
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 6 | - | - |
| 02 | 5 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P06 | multi-session | 3 tasks | 8 files |
| Phase 02 P01 | 10 min | 3 tasks | 13 files |
| Phase 02 P02 | 5 min | 2 tasks | 4 files |
| Phase 02 P03 | 6 min | 2 tasks | 9 files |
| Phase 02 P04 | 48 min | 3 tasks | 11 files |
| Phase 02 P05 | 12 min | 3 tasks | 12 files |
| Phase 03 P01 | 12 min | 3 tasks | 15 files |
| Phase 03 P02 | 13min | 3 tasks | 8 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Research's 5 phases compressed to 4 (coarse granularity); scaffold/CI/foundation merged into the Switch walking skeleton (vertical MVP slice)
- [Roadmap]: Trust gate ships in the same phase as follower apply (Phase 3); no release with follower apply before it
- [Roadmap]: Startup policy = baseline only (opt-in run-on-startup flag); command topic equals state topic; domain `mqtt_actions`; min HA 2026.9.0
- [Roadmap]: OPS-06 test tiers are built incrementally per phase (TDD on) and closed in Phase 4 when the multi-instance tier exists
- [Phase 01]: [01-06] hacs.json floor 2026.9.0; HACS license check reads the default branch, so LICENSE was added to main (c02d5fe, developer-approved)
- [Phase 02]: device_id stays the only device identity; triggers are keyed by trigger_key = sha256(lowercased StateValue)[:12], derived and never stored
- [Phase 02]: A stored baseline that is not a StateValue of its device is sanitized to no baseline at add and change time (A11)
- [Phase 02]: Renaming or removing the selected Select option leaves the HA entity at unknown until the next valid payload; no republish (open question 1)
- [Phase 02]: Select payload normalization is str.strip().lower() in tracker and Jinja (trim | lower), never casefold
- [Phase 02]: Run mode maps to Script mode one to one (serial=queued, restart=restart) with max_runs=SERIAL_QUEUE_LIMIT; one Script per device dispatches on the hashed trigger_key — Native FIFO, race-free restart and logged overflow drops across all triggers of a device (DEV-06, D-10 to D-12)
- [Phase 02]: A run clears the failure issue only when the Script returned a result and it is the device's latest enqueue — Dropped, cancelled or superseded runs must not fake success (T-02-06, A10)
- [Phase 02]: Test buttons run a trigger's actions through a per-device non-retained test topic and never touch tracker, baseline or state topic; retained test messages are ignored (DEV-07, D-13, T-02-08, T-02-09) — A Discovery button only publishes the exact StateValue, so the manager executes the press itself
- [Phase 02]: Removed options retire their button with a platform-button tombstone kept in memory for every republish while running; button unique_id is device_id + _test_ + trigger_key (D-13, pitfall 4, T-02-11) — Core MQTT discovery never removes an omitted component; identity derives from the immutable StateValue hash so renames keep entity ids
- [Phase 02]: Per-device sliding-window breaker: exactly max_runs runs per window, the next change trips and does not run; a trip pauses the device (baseline only), stops running and queued runs, warns once and raises Repairs issue circuit_breaker_<device id> (STA-06, D-14 to D-16) — A self-toggling action would otherwise loop forever and the queue bound only limits a burst; the tripping change must not run
- [Phase 02]: Tripped state persists as a per-device config hash in the additive store key tripped (no version bump, no window stored); async_unload_entry releases via release_all_breakers before the final save while Manager.async_stop never releases (D-15, D-17, A12) — A failed setup also calls async_stop and a Home Assistant restart never unloads, so a restart keeps the pause and a user reload or a real config change releases it; an unchanged save is a no-op and releases nothing
- [Phase 02]: Select flow is a menu loop over a deep-copied draft committed once on Done; a menu cannot show errors so Done, Remove and Add are hidden instead of failing (D-01, D-04, T-02-24)
- [Phase 02]: Breaker number selectors carry no min and max so out-of-range input returns a translated field error; validate_breaker owns 1..100 and 1..3600 and rejects non-integral values (A7, T-02-21)
- [Phase 02]: Edit step has no StateValue field, removal needs a confirmation menu and is hidden at two options; Done in reconfigure replaces stored data and re-injects the device id (D-02, D-03, D-05)
- [Phase 03]: Plan 03-01: wire hash is sha256 over canonical JSON of the shared content (sorted keys, compact, unescaped UTF-8); owner, owner_name, rev, hash, device_id and schema_version are not content; actions_hash binds approvals to the StateValue-to-actions mapping and run_on_startup
- [Phase 03]: Plan 03-01: owner publishes all config documents, then all discovery, then online availability on start and every reconnect; rev persisted with its hash in the Store key revs
- [Phase 03]: Plan 03-01: parse_document is the only path from broker payload to spec; typed content-free RejectReason codes, wire hash never trusted, SchemaTooNewError raised first
- [Phase 03]: Pop-first removal: a device leaves Manager.devices before its first clear message so the owner never heals its own delete (03-02)
- [Phase 03]: Owner republishes are throttled per device with a trailing throttle (60 s); issues for foreign writes and claims are created only when absent (03-02)
- [Phase 03]: Discovery removal hint fires after 3 removals within 600 s using the replaceable Manager.clock; doc_overwritten and ownership_claim are ERROR severity, discovery_removed WARNING (03-02)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Confirm haos-op3050-1, lxc-haos-104 and hassio-n2plus can all run HA 2026.9.0 (Python 3.14) before fixing the `hacs.json` floor
- [Phase 1]: Spike needed: `ActionSelector` rendering and field-level validation inside a subentry flow (LOW confidence); verify local brand icon path against current HACS docs
- [Phase 2]: Spike needed: generated Select `value_template`/`command_template` with escaping, tested against a real HA MQTT discovery run
- [Phase 3]: Needs deeper research before planning (`/gsd-plan-phase --research-phase 3`): prune strategy (grace window vs owner manifest), `FakeBroker` design, Repairs approval flow, discovered-entity registry cleanup, subentry deletion hooks, subentries as device store fit
- [Phase 3]: Open decision: owner availability (heartbeat + graceful-shutdown publish vs. no tie to owner liveness); AVL-01 is deferred to v2

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-30T23:23:50.338Z
Stopped at: Completed 03-02-PLAN.md
Resume file: None
