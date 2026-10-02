---
gsd_state_version: "1.0"
current_phase: 04
current_phase_name: Operations, Recovery and Release
status: verifying
stopped_at: Completed 04-13-PLAN.md
last_updated: "2026-10-02T17:46:39.635Z"
last_activity: 2026-10-02
last_activity_desc: Phase 04 execution started
state_head: e70b5f395c98fb34546cfb67959c7c977de23a99
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 32
  completed_plans: 32
  percent: 75
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-28)

**Core value:** A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.
**Current focus:** Phase 04 — Operations, Recovery and Release

## Current Position

Phase: 04 (Operations, Recovery and Release) — EXECUTING
Plan: 13 of 13
Status: Phase complete — ready for verification
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
| Phase 04 P06 | 7 min | 2 tasks | 3 files |
| Phase 04 P07 | 5 min | 2 tasks | 5 files |
| Phase 04 P08 | 7 min | 2 tasks | 10 files |
| Phase 04 P09 | 8 min | 2 tasks | 9 files |
| Phase 04 P10 | 30 min | 3 tasks | 15 files |
| Phase 04 P11 | 17 min | 3 tasks | 14 files |
| Phase 04 P12 | 21 min | 3 tasks | 11 files |
| Phase 04 P13 | 11 min | 3 tasks | 6 files |

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
- [Phase 04]: 04-06: mirrors share the owned devices' select add loop (config_subentry_id None for a mirror); _remove_companion removes only the (mqtt_actions, id) device and never the core MQTT device
- [Phase 04]: 04-07: diagnostics are an allow-list (hub, roster, device rows with 8-char instance ids); async_redact_data only as a safety net — Naming what is included is safer than removing what is not; sentinel tests prove no action content, device name or full id leaves
- [Phase 04]: 04-07: ApprovalState words (owned, approved, pending, blocked, no_actions, unknown) are the single public answer via Manager.approval_state — Diagnostics and later re-trigger acknowledgements use the same words
- [Phase 04]: 04-08: Services are registered once in async_setup (admin only, optional response); a service field naming a device is device_id (device selector) resolved to the uuid via the (mqtt_actions, uuid) identifier — Hassfest rule; hub, foreign and unknown devices refused; mirrors refused for export
- [Phase 04]: 04-08: Export files live only in <config>/mqtt_actions/ (0700 dir, 0600 file, bare name pattern, symlink refused); other write failures raise export_write_failed — Never www; user input never forms a path; log carries only a reason code
- [Phase 04]: Import items run through parse_document, the structure check, the static denylist and deep validation; a forged owner, id, rev or hash of an item is overwritten by this instance's values
- [Phase 04]: Import is all or nothing: every item is validated before the first subentry is created; rejections carry only a reason code and a 1-based position
- [Phase 04]: Import files are read by bare name from a real private directory with a no-follow open, a regular-file check and the size checked on the descriptor; every unreadable case is file_unreadable
- [Phase 04]: Deep validation does not check that a service exists (core resolves device actions, conditions and triggers only); an unknown service name is accepted by import, as in the UI flows
- [Phase 04]: 04-10: re-trigger runs through the test-press path (enqueue test=True after mode and breaker checks, never breaker.record), so no state, baseline, revision or breaker count moves — A second remote execution path must reuse the existing gates; D-01, D-02, T-04-42
- [Phase 04]: 04-10: receiver gate order retained, size and strict parse, freshness 60 s, duplicate id (128), per-device rate limit 5 s (foreign only), device, state, mode, breaker, runnability; not_approved is decided before no_actions — Replay, flood and stale requests must run nothing; every accepted request gets one answer; D-03, D-04, T-04-43 to T-04-46
- [Phase 04]: 04-10: caller claims its per-device send slot before publishing and releases it only when the publish failed; response keys the device as uuid; no_answer and offline are synthesized by the caller and never on the wire — Concurrent calls must not both pass; documentation examples never need the registry field name; D-03
- [Phase 04]: 04-10: tests/test_retrigger.py is a multi_instance module (receiver tests use the fake broker; a retained request is simulated by a reconnect replay) — test_tiers_partition_the_suite requires the marker for every module that uses make_instance
- [Phase 04]: 04-11: adoption runs entirely under the manager lock (drop the mirror, save, add the subentry, reconcile); force overrides only the owner-online check, never the approval; a mirror with an owner id that cannot be named in a marker is not adoptable — A late document of the old owner must not re-create a mirror for an id about to be owned; unreviewed remote actions must never become owned ones (TRU-01, T-04-50); D-09, D-10
- [Phase 04]: 04-11: the transferred_from marker is bookkeeping (never hashed, SCHEMA_VERSION stays 1, newest 8 kept); a follower re-pins only when the marker names its pinned owner and the roster says offline; a same-content re-pin keeps the breaker, Script and approval — A forged marker must not move followers of an online owner or release a tripped device; D-09 refined, T-04-49, T-04-52
- [Phase 04]: 04-11: the select platform needs one devices-changed signal while an id is in neither devices nor mirrors before an owned device with the same id gets its mode select under the new subentry — Mirror to owned switch keeps the same uuid; D-13 revised
- [Phase 04]: Plan 04-12: the local release never publishes; the device leaves devices first, then its subscriptions, Script, issues and published/revs/tripped/transfers records go, the Store is saved at once and only then are the subentries removed behind a _releasing guard; the duplicate id fix rotates the id and the next stop skips the offline for the shared id (D-08) — A tombstone or clear on the shared topics of a clone or an adopter would delete the original's devices for every instance, so byte-identical broker state is the proof
- [Phase 04]: Plan 04-12: an old owner that recognizes a valid adopter document naming it goes silent for that device (no heal, no publish, no clear on delete) and raises a fixable issue; the flow releases locally and follows the adopter from the saved document, nothing steps down automatically (D-09 refined, A15) — Recognition is memory-only and bounded by the owned devices; the guard sits in async_publish_config and async_publish_discovery so every publish path is covered
- [Phase 04]: Documentation is pinned to the code by tests: services.yaml, const.py, translations and the tested diagnostics key sets are read by tests/test_docs.py
- [Phase 04]: A fenced documentation example may carry device_id only as the data field of an mqtt_actions service call, next to the instance-specific warning; responses use the key uuid
- [Phase 04]: The pages state the known limits as they are: imports and adoption are owned content without approval, returning-owner recognition is in memory only, the new instance id is not in a per-instance ACL

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

Last session: 2026-10-02T17:46:39.538Z
Stopped at: Completed 04-13-PLAN.md
Resume file: None
