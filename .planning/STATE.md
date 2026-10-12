---
gsd_state_version: "1.0"
milestone: v1.1
milestone_name: Local Actions on Mirrors
current_phase: 09
current_phase_name: v1.0.1 Release
status: executing
stopped_at: "09-02 blocked at Task 2: no CI/Validate run on bump SHA 7baec98"
last_updated: "2026-10-12T08:03:03.230Z"
last_activity: 2026-10-12
last_activity_desc: Phase 09 execution started
state_head: 40a0f48b13f9da37a987f86ccf8ecf46d1823078
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 5
  completed_plans: 1
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-11)

**Core value:** A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.
**Current focus:** Phase 09 — v1.0.1 Release

## Current Position

Phase: 09 (v1.0.1 Release) — EXECUTING
Plan: 2 of 5
Status: Ready to execute
Last activity: 2026-10-12 — Phase 09 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 62
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 6 | - | - |
| 02 | 5 | - | - |
| 03 | 8 | - | - |
| 04 | 14 | - | - |
| 5 | 9 | - | - |
| 6 | 2 | - | - |
| 8 | 18 | - | - |

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
| Phase 04 P14 | 15 min | 2 tasks | 3 files |
| Phase 05 P01 | 24min | 3 tasks | 4 files |
| Phase 05 P02 | 30min | 2 tasks | 2 files |
| Phase 05 P03 | 40min | 3 tasks | 9 files |
| Phase 05 P04 | 45min | 2 tasks | 9 files |
| Phase 05 P05 | 75min | 3 tasks | 4 files |
| Phase 5 P06 | 60min | 2 tasks | 11 files |
| Phase 05 P07 | 45min | 2 tasks | 6 files |
| Phase 05 P08 | 60min | 3 tasks | 10 files |
| Phase 5 P09 | 35min | 2 tasks | 8 files |
| Phase 06 P01 | 8 min | 2 tasks | 6 files |
| Phase 06 P02 | 13 min | 3 tasks | 7 files |
| Phase 08 P11 | 2 sessions | 3 tasks | 24 files |
| Phase 08 P12 | 1 session | 3 tasks | 8 files |
| Phase 08 P13 | 31 min | 2 tasks | 55 files |
| Phase 08 P16 | 10m | 2 tasks | 4 files |
| Phase 08 P17 | 15min | 3 tasks | 7 files |
| Phase 08 P18 | 37 min | 2 tasks | 57 files |
| Phase 08 P14 | 20 min | 2 tasks | 4 files |
| Phase 08 P15 | not measured | 3 tasks | 11 files |
| Phase 09 P01 | 11 min | 3 tasks | 31 files |

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
- [Phase 04]: 04-14: issue-level description removed from the three fixable Repairs issues; explanation lives in the confirm step (hassfest exclusion group fixable)
- [Phase 04]: 04-14: ISSUES in tests/test_translations.py is read from en.json so every new issue is guarded against description plus fix_flow
- [Phase 05]: Go: replace MQTT-Discovery entities with native switch/select platforms (ADR 0001 Accepted)
- [Phase 05]: Takeover removes the emptied legacy device only when nothing moved and the native device exists; otherwise the device is moved and the companion merged
- [Phase 05]: Native Store key written only when non-default, so legacy instances keep their persisted data unchanged
- [Phase 05]: device_info_for replaces companion_device_info as the single device info builder shared by mode select and native entities
- [Phase 05]: 05-04: Native marker is the top-level key entities=native, never hashed, read strictly; mirror native-ness is one-way and the stored payload carries the marker
- [Phase 05]: 05-04: Presence signal is sent only for owners of native mirrors and only when the roster did not already signal, keeping Phase 4 roster signal counts
- [Phase 05]: 05-05: a pending owned device always gets the migrate payload before the retained clear, even without a legacy device of its own
- [Phase 05]: 05-05: adoption keeps a native mirror native via the persisted devices set; a legacy mirror on a native instance is queued as pending and reloads the entry
- [Phase 5]: 05-06: hint rebuilt only when the set of blocking peers changes; a silent announced-online peer is released by the heartbeat tick; natively listed devices are not made pending at the flip
- [Phase 05]: A running legacy mirror that flips to native is parked in _legacy_this_run and the entry reloads once, so the takeover keeps every entity identity (05-07)
- [Phase 05]: 05-08: heals_discovery gates healing to owned legacy devices; a deferred device is legacy again (in _legacy_this_run), only the pass window is excluded
- [Phase 05]: 05-08: the discovery export is a best-effort second publish path (disabled by default, own prefix, no subscription, no healing); option changes apply from async_reconcile without reload
- [Phase 5]: 05-09: ACL block unchanged; the export prefix has its own row and the discovery prefix is a legacy-path and export concern
- [Roadmap v1.0.1]: Three phases continue the numbering at 6 (coarse granularity): 6 code fixes (MIG-04, MIG-05), 7 verification, stable tests and pinned CI (QLT-01 to QLT-03), 8 manual real-instance UAT (UAT-01 to UAT-04); Phase 7 follows the fixes so re-verification and the three-run proof cover the final code, Phase 8 follows both and is a manual verification phase, not code plans
- [Phase 06]: Native flag of a mirror is a set of device ids in the native Store dict; the stored payload is kept as received (D-01)
- [Phase 06]: A mirror is native when the set lists it or its payload carries the 1.0.0 marker; only the set is written from now on (D-02)
- [Phase 06]: The native flag is sticky: the id leaves the set only at tombstone, prune or adoption and is pruned at start to the restored mirrors (D-03, T-06-01)
- [Phase 06]: 06-02: the replay catch is registry-only and its quiet period is an async_call_later timer (5.0 s), not a sleep — A sleeping task hangs the freezer fixture; the timer follows the cutover pattern and publishes nothing (T-06-07, T-06-09)
- [Phase 06]: 06-02: the emptied replayed MQTT device is removed only when nothing at all remains on it — Removing a device removes the entries on it, so a check on MQTT entries alone could delete moved native entities
- [Phase 08]: UAT04-GAP-DISPOSITION: guard-and-document, full-rerun, not-affected confirmed by owner; classification TOMBSTONE-ONLY
- [Phase 08]: D08-WAIVER: a product fix may land in Phase 8 for the UAT-04 clause 2 gap closure only (relayed 2026-10-08, confirmed by the owner in chat 2026-10-11); the failure rule of D-08 stands
- [Phase 08]: 08-12: the export-duplicate guard disables, it does not remove, and uses public registry API only — armed while the export is on the core prefix, disarmed on export off, prefix change and stop
- [Phase 08]: 08-13: UAT-04 re-run on the guard build FAILS on ha-b (X7 Lampe Test and Bar Select, X8); UAT-02, UAT-03 and P1-5 PASS; the guard only arms on the exporting instance, receivers of the export are not covered — Recorded as observed (D-08 failure rule); evidence in uat-04-rerun/, 08-14 records it in the ledger
- [Phase 08]: 08-13: host reboot found at plan start; mosq started again and its preflight StartedAt anchor re-anchored (old value kept as .mosq-started-before-phase8.pre-reboot) — Bench recovery, not a result; disclosed in uat-04-rerun/prepare.txt
- [Phase 08]: UAT04-RECEIVER-GUARD extend-and-confirm (2026-10-11): D08-WAIVER extends to plans 08-16 to 08-18 for UAT-04 clause 2; guard armed on every native instance; UAT-01, P2-2 and owner-judged frontend items confirmed not affected; D-08 failure rule stands
- [Phase 08]: 08-17: duplicate guard armed on every native instance, independent of the export option; candidate needs a native twin, disable-only
- [Phase 08]: UAT-04 passes on the receiver-guard build from the restored failing tombstone state; UAT-02, UAT-03 and P1-5 pass as well; outcome recorded by plan 08-14
- [Phase 08]: 08-14: UAT-04 recorded pass on the receiver-guard build without a pruned-state qualifier (guard-and-document, pass on the restored null-tombstone state); ledger status complete
- [Roadmap v1.1]: Four phases continue the numbering at 9 (coarse granularity): 9 v1.0.1 release (REL-01), 10 Phase 8 info findings and IN-04 extraction (FIX-01 to FIX-08), 11 local actions on mirrors as one vertical slice (MIR-01 to MIR-15), 12 re-verification and v1.1.0 release (QLT-01, QLT-04, QLT-05, REL-02); research's split of MIR-01 into a runtime phase and a UI phase is folded into Phase 11 with a runtime-first plan order
- [Roadmap v1.1]: Release phases commit the manifest bump before the bench run and tag exactly the bench-verified SHA; the user pushes tags; no IN-04 or MIR-01 commit on `main` before the v1.0.1 tag (or release from `release/1.0.1`)
- [Roadmap v1.1]: The pure IN-04 move and each review fix are separate plans; the extraction lands before MIR-01
- [Roadmap v1.1]: Phases 9 and 12 change no product code; a failed check becomes an inserted decimal phase, then the affected verification and bench run repeat on the new SHA
- [Owner 2026-10-11, MIR-01]: one Script per mirror with a `parallel` branch for "in addition to"; local actions discarded (logged, reported) on tombstone and adoption; orphaned Select options kept inactive and re-attached; no GuardedTemplate on local actions; UI is a menu in the hub options flow
- [Phase 09]: Bump SHA 7baec9878badc8fb49ea0d80243277d5ff3fb443 is the single v1.0.1 anchor; owner pushes it with git push origin 7baec9878badc8fb49ea0d80243277d5ff3fb443:refs/heads/main (09-01)
- [Phase 09]: Phase 9 stops before the bench: no push-event CI/Validate run exists on bump SHA 7baec98 after 45 min; D-04 not met, owner decides how to create one

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 9]: No IN-04 or MIR-01 commit on `main` before the v1.0.1 tag (or cut the release from `release/1.0.1`); manifest 1.0.1 committed before the UAT-02/UAT-04 bench run (closes ACCEPTED-GAP-V101 for v1.0.1)
- [Phase 11]: Open for discuss-phase: storage location of local actions (separate Store file or main Store key, which a v1.0.x downgrade drops) and the stored trigger identity; `parallel` pin test against core 2026.9.4 before relying on the owner's topology decision
- [Phase 12]: Verification reports of Phases 1 to 8 read stale or human_needed; all refreshed in Phase 12 (QLT-01, extended to Phases 5, 6 and 8 by owner decision 2026-10-11)
- [Owner follow-up]: Keep the bench (ha-a, ha-b, ha-c) and its tokens until the Phase 12 bench run; revoke the three tokens and tear down the bench state after v1.1.0 (see v1.0.1-phases/08-real-instance-verification/08-UAT.md)
- [Open decision]: owner availability (AVL-01) stays deferred to v2
- 09-02: GitHub Actions created no CI/Validate run for the owner's push of bump SHA 7baec98 (45 min, gh run list empty, no github-actions check suite). Owner decides: push-event on a temp branch (A), workflow_dispatch with D-04 amendment (B), or investigate (C). Bench 09-03 waits.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 261003-rmy | Native Select restore-previous-state button and previous_state attribute; new native test buttons diagnostic and disabled by default | 2026-10-03 | c7a537c | [261003-rmy-native-entities-test-buttons-disabled-by](./quick/261003-rmy-native-entities-test-buttons-disabled-by/) |
| 261003-sfb | New native entities get short English entity id parts (_restore, _test_<StateValue>, _mode, _resync, _instances, _instance_mode) in every UI language; existing ids never renamed | 2026-10-03 | 89019df | [261003-sfb-native-entity-ids-shorter-and-english](./quick/261003-sfb-native-entity-ids-shorter-and-english/) |

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| verification_gaps | 07/07-VERIFICATION.md | human_needed | 2026-10-11 | v1.0.1 |

## Session Continuity

Last session: 2026-10-12T08:03:03.005Z
Stopped at: 09-02 blocked at Task 2: no CI/Validate run on bump SHA 7baec98
Resume file: .planning/phases/09-v1-0-1-release/09-02-SUMMARY.md

## Operator Next Steps

- Review the roadmap, then start Phase 9 with /gsd-discuss-phase 9 or /gsd-plan-phase 9
