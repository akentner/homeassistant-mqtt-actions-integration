---
gsd_state_version: "1.0"
current_phase: 04
current_phase_name: Operations, Recovery and Release
status: executing
stopped_at: Completed 04-05-PLAN.md
last_updated: "2026-10-02T08:18:37.363Z"
last_activity: 2026-10-02
last_activity_desc: Phase 04 execution started
state_head: 20fe59c8b0876392722fd5dd883736fcc446a60f
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 32
  completed_plans: 24
  percent: 75
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-28)

**Core value:** A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.
**Current focus:** Phase 04 — Operations, Recovery and Release

## Current Position

Phase: 04 (Operations, Recovery and Release) — EXECUTING
Plan: 6 of 13
Status: Ready to execute
Last activity: 2026-10-02 — Phase 04 execution started

Progress: [████████░░] 75% of Phase 01 plans

## Performance Metrics

**Velocity:**
- Total plans completed: 19
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 6 | - | - |
| 02 | 5 | - | - |
| 03 | 8 | - | - |

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
| Phase 03 P03 | 10 min | 3 tasks | 15 files |
| Phase 03 P04 | 12 min | 3 tasks | 12 files |
| Phase 03 P05 | 25 min | 2 tasks | 6 files |
| Phase 03 P06 | 55 min | 3 tasks | 13 files |
| Phase 03 P07 | 10 min | 3 tasks | 6 files |
| Phase 03 P08 | 20min | 2 tasks | 3 files |
| Phase 04 P01 | 7 min | 3 tasks | 8 files |
| Phase 04 P02 | 5 min | 2 tasks | 11 files |
| Phase 04 P03 | 12min | 3 tasks | 11 files |
| Phase 04 P04 | 10 min | 3 tasks | 11 files |
| Phase 04 P05 | 15 min | 3 tasks | 14 files |

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
- [Phase 03]: Plan 03-03: the generic HA subentry delete cannot be vetoed, so both delete paths end in the same reconcile tombstone sequence; the confirmation wording lives in the flow and the README (Open Question 1)
- [Phase 03]: Plan 03-03: hub removal keeps every device retained by default; deletion everywhere only when delete_devices_on_remove was set in the hub OptionsFlow before removal; Store and issues are removed in both modes (D-11)
- [Phase 03]: Plan 03-03: instance presence is tracked from the availability wildcard (online and offline only, own id excluded, capped at 256); the delete confirmation gives the count of other online instances, an upper bound because a crashed instance stays online (A11)
- [Phase 03]: Plan 03-04: a mirror is a Device without a Script in Manager.mirrors (never in devices, never a subentry); the runner gate keeps it inert, the follower publishes nothing for it, and cached mirrors are parsed and structure-checked again at every load (D-08, D-19)
- [Phase 03]: Plan 03-04: the content hash decides updates, never the rev; the first owner is pinned and a competing owner raises one owner_conflict issue; a too-new schema keeps the last mirror and raises a bounded schema_too_new issue (D-14, D-15, D-17)
- [Phase 03]: 03-05: Seen set is bounded to mirror ids; marked by the config callback for ids with a mirror and by the ingest on creation (Rule 2 deviation from the literal plan)
- [Phase 03]: 03-05: Registry cleanup treats an entity as live when its state exists and is not restored; any live entity skips the whole cleanup (Pitfall 10)
- [Phase 03]: 03-05: PRUNE_GRACE_SECONDS = 30; reconnect clears seen set and presence cache; every owner-online transition re-arms the prune timer; no approval retention after a tombstone (A10)
- [Phase 03]: Mirror Scripts are built before the mirror subscribes and only when approvals[id] equals the actions hash; unapproved, changed, blocked and action-less mirrors run nothing
- [Phase 03]: Execution-time denylist through GuardedTemplate raising a plain Exception so continue_on_error cannot swallow a denial; statically denied mirrors are blocked and never approvable
- [Phase 03]: Approval issues are deleted then created on every applied document and at start so a dismissed request never hides a changed one; empty lists in the dialog are an em dash
- [Phase 03]: Action failure issues of mirrors escape device name, trigger label and error text because they come from the broker
- [Phase 03]: 03-07: ACL example uses one MQTT user per instance; ownership of config topics stays cooperative (device ids are random), approval is the real gate
- [Phase 03]: 03-07: The documented acl block is the block the broker test enforces (the test reads docs/broker-acl.md); the external publisher gets state-topic access only
- [Phase 03]: 03-07: owner_conflict issue is transient with an online owner (cleared when the owner's healing republish is re-seen); flagged for user review
- [Phase 03]: 03-08: escape_markdown only on Markdown-rendered flow description placeholders; chooser labels and suggested values stay raw
- [Phase 04]: 04-01: --strict-markers in pytest addopts; release requires hassfest/HACS validation via reusable validate.yml; ci and validate jobs in release.yml need check-version so a mismatching tag stops early; hyphenated tags are prereleases
- [Phase 04]: 04-02: run_mode, breaker_max_runs and breaker_window are bound into actions_hash (D-16); a rename is still not; no migration code, old approvals lapse once
- [Phase 04]: 04-03: peer online while heartbeat age <= 90 s and availability not offline; expiry timer fires 1 s after the deadline — Strict comparison gives 89 s online and 91 s offline without a busy re-arm loop
- [Phase 04]: 04-03: owner_offline treats an owner that announced online without any heartbeat as not offline; unknown owner is offline only after 90 s of listening — Unknown must never count as offline right after a start; adoption then needs force (D-09, A10)
- [Phase 04]: 04-03: at the peer cap a new peer evicts the stalest expired row, else is not tracked — Random heartbeat ids must not block real instances permanently (T-04-12)
- [Phase 04]: Plan 04-04: hub device identifier is (mqtt_actions, config entry id), so it survives an instance id change
- [Phase 04]: Plan 04-04: roster sensor counts this instance, lists it first, and caps the unrecorded instances attribute at MAX_TRACKED_INSTANCES + 1
- [Phase 04]: Plan 04-04: Manager.async_resync returns False when throttled (5 s on Manager.clock) or stopped; the time is remembered before the republish is awaited
- [Phase 04]: 04-05: mode gate sits between can_run and the circuit breaker; observe is logged through model.shown and never counted, disabled returns before the tracker
- [Phase 04]: 04-05: leaving disabled re-baselines (baseline and startup window cleared, state topic resubscribed); the test topic obeys the effective mode
- [Phase 04]: 04-05: companion devices are looked up with async_get_device_by_identifier (async_get_device is deprecated and raises in tests); mode keys are additive Store keys without a version bump

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

Last session: 2026-10-02T08:18:37.283Z
Stopped at: Completed 04-05-PLAN.md
Resume file: None
