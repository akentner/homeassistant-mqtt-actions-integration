---
phase: 04-operations-recovery-and-release
plan: 03
subsystem: infra
tags: [mqtt, heartbeat, presence, roster, mosquitto-acl, home-assistant]

requires:
  - phase: 03-multi-instance-sync
    provides: availability wildcard tracking in SyncManager, fake-broker multi-instance tier, documented and broker-tested ACL
  - phase: 04-operations-recovery-and-release
    provides: marker-based test tiers (plan 04-01), so the new module carries the multi_instance marker
provides:
  - non-retained QoS 0 heartbeat every 30 seconds on <base>/v1/instances/<instance id>/heartbeat
  - strict heartbeat parser (size cap in characters and bytes, typed and capped fields, canonical session uuid)
  - Roster with a 90 second timeout, offline availability handling, peer cap and the conservative owner_offline answer
  - PresenceManager (session, rows, online_count, online_peers, peer_status, owner_offline) wired into the Manager
  - heartbeat lines in the documented ACL, enforced by a real Mosquitto
affects: [04-04 roster sensor, 04-07 diagnostics, 04-10 re-trigger acknowledgements, 04-11 adoption, 04-12 duplicate id detection]

actuals:
  tokens: 14000
  tasks: 3
  commits: 6
plan_head_before: 6e73855d5438fead13f9cb71f7dac4c38b266c8f
plan_head_after: 6bf3538d2af21c872ac895ea736e576b8335d838

tech-stack:
  added: []
  patterns:
    - "Liveness by timeout from a non-retained heartbeat, availability only as the fast path for a clean shutdown"
    - "Untrusted broker payload: size cap before parse, typed fields, None instead of raising, no field in any log line"
    - "Roster rows are kept across a reconnect; only the listening time restarts"

key-files:
  created:
    - custom_components/mqtt_actions/presence.py
    - tests/test_presence.py
    - tests/test_multi_instance_ops.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/topics.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/sync.py
    - docs/broker-acl.md
    - tests/test_topics.py
    - tests/test_multi_instance.py
    - tests/broker/test_acl.py

key-decisions:
  - "A peer is online while its heartbeat is at most 90 s old and its retained availability is not offline; the expiry timer fires 1 s after the deadline so the strict comparison holds"
  - "owner_offline treats an owner that announced online and never sent a heartbeat as not offline, and an unknown owner as offline only after 90 s of listening"
  - "At the peer cap a new peer replaces the stalest expired row; when every row is fresh it is not tracked (overflow logged once per start)"
  - "The roster signal fires on every accepted heartbeat and on every change of the online set"

patterns-established:
  - "Presence hook: SyncManager reports every availability change to PresenceManager.on_availability_changed, so a clean shutdown shows at once"
  - "Tick publishes under the manager lock, so no heartbeat can follow the offline availability of a stop"

requirements-completed: [OPS-03]

coverage:
  - id: D1
    description: "Every instance publishes a non-retained QoS 0 heartbeat with the five keys after the online availability and on a 30 second tick, and none after the manager stopped"
    requirement: OPS-03
    verification:
      - kind: unit
        ref: "tests/test_presence.py#test_heartbeat_is_published_non_retained_with_qos_0"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_heartbeat_tick_publishes_every_30_seconds"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_reconnect_republishes_config_before_availability"
        status: pass
    human_judgment: false
  - id: D2
    description: "A peer is in the roster of the others while its heartbeat is at most 90 s old, offline after that (also with a stale retained online), offline at once after a clean shutdown, and rows survive a reconnect"
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_instances_see_each_other_through_heartbeats"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_roster_marks_a_peer_offline_after_90_seconds"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_clean_shutdown_marks_the_peer_offline_at_once"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_rows_survive_a_reconnect"
        status: pass
    human_judgment: false
  - id: D3
    description: "Hostile heartbeats are dropped: retained, own echo, forged id, oversized, malformed fields, peer flood; nothing from a payload reaches a log line"
    requirement: OPS-03
    verification:
      - kind: unit
        ref: "tests/test_presence.py#test_parse_heartbeat_rejects_invalid_messages"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_retained_heartbeat_is_ignored"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_own_echo_is_not_a_peer"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_peer_cap"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_rejected_heartbeats_log_nothing_from_the_payload"
        status: pass
    human_judgment: false
  - id: D4
    description: "owner_offline answers conservatively: offline announcement, stale heartbeat, or nothing known after 90 s of listening; an owner that announced online without heartbeats is never offline"
    requirement: OPS-03
    verification:
      - kind: unit
        ref: "tests/test_presence.py#test_owner_offline_when_the_owner_announced_offline"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_owner_that_announced_online_without_a_heartbeat_is_never_offline"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_unknown_owner_is_offline_only_after_listening_long_enough"
        status: pass
      - kind: unit
        ref: "tests/test_presence.py#test_a_reconnect_restarts_the_listening_time"
        status: pass
    human_judgment: false
  - id: D5
    description: "The documented ACL grants write of the own heartbeat topic and read of all of them, and a real Mosquitto enforces exactly that text; the heartbeat is not replayed to late subscribers and the bridge user has no access"
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/broker/test_acl.py#test_instance_cannot_write_another_instances_heartbeat"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_heartbeat_is_not_replayed_to_late_subscribers"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_external_publisher_has_no_heartbeat_access"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_acl_document_states_the_limits"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 03: Heartbeat, roster and the heartbeat ACL Summary

**Non-retained 30 s heartbeat per instance, a strictly validated roster with a 90 s timeout that also reflects clean shutdowns at once, a conservative owner_offline answer for adoption, and heartbeat lines in the ACL that a real Mosquitto enforces**

## Performance

- **Duration:** 12 min
- **Started:** 2026-10-02T07:36:55Z
- **Completed:** 2026-10-02T07:48:32Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- `presence.py`: `Heartbeat`, `parse_heartbeat` (size cap in characters and UTF-8 bytes before parsing, topic id equals payload id, typed and capped fields, canonical lower-case session uuid, never raises, never logs), `Roster` and `PresenceManager`.
- Heartbeat published after the retained `online` availability at the end of the start and of every republish, on a 30 s tick (under the manager lock, only while running) and never retained, QoS 0.
- Roster: online while the heartbeat is at most 90 s old and the retained availability is not `offline`; one expiry timer fires 1 s after the earliest deadline (89 s online, 91 s offline); rows survive a reconnect while the listening time restarts; `SIGNAL_ROSTER_UPDATED` fires on every accepted heartbeat and on every change of the online set.
- `owner_offline`: availability offline gives True, a stale row gives True, a fresh row gives False, an owner that announced online without a heartbeat is never offline, and an unknown owner is offline only after 90 s of listening.
- `docs/broker-acl.md`: topic table row, `topic read .../instances/+/heartbeat` and `topic write .../<instance-id-N>/heartbeat` in both Home Assistant blocks, one enforcement bullet and one limits bullet; still exactly one `acl` block and both markers.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Tracer, one instance announces itself and another puts it in its roster** - `8852c2d` (test), `d9053a8` (feat)
2. **Task 2: Timeouts, strict validation, caps, reconnect and the conservative owner-offline answer** - `cc614fb` (test), `bf574b1` (feat)
3. **Task 3: The documented ACL grants the heartbeat topic** - `37bb5e5` (test), `6bf3538` (feat)

**Plan metadata:** committed with this summary (docs: complete plan)

## TDD Gate Compliance

RED precedes GREEN for all three tasks (`test(04-03)` `8852c2d`, `cc614fb`, `37bb5e5` before `feat(04-03)` `d9053a8`, `bf574b1`, `6bf3538`). No refactor commits were needed.

- **Task 1 RED** failed at collection with `ImportError` (`heartbeat_topic`, `presence` do not exist yet). That is what the plan asked for ("fail because none of it exists"), but by the strict #3770 rule an import error is not an assertion-level RED; for a brand-new module there is no assertion to reach. The behavior tests were all assertion-checked in GREEN.
- **Task 2 RED:** 26 tests failed on the planned assertions (parser accepts too much, nothing expires, no timer, no cap). Four tests already passed at RED and are guards for GREEN rather than drivers of new behavior: `test_rejected_heartbeats_log_nothing_from_the_payload`, `test_rows_survive_a_reconnect`, `test_heartbeat_tick_keeps_the_roster_fresh_for_running_peers`, `test_parse_heartbeat_accepts_the_limits`.
- **Task 3 RED:** the three broker tests failed on the positive control (a live heartbeat was not delivered because the block granted nothing), so the denial assertions could not pass vacuously.
- Tracer gate: the Task 1 verify chain (`pytest` of the three modules, full suite, `ruff check`, `ruff format --check`) was re-run after the GREEN commit and passed before expansion.

## Files Created/Modified
- `custom_components/mqtt_actions/presence.py` - heartbeat parser, roster, presence manager (publish, subscribe, tick, expiry timer, owner_offline)
- `custom_components/mqtt_actions/const.py` - `HEARTBEAT_INTERVAL_SECONDS`, `HEARTBEAT_OFFLINE_SECONDS`, `MAX_BROKER_MESSAGE_BYTES`, `MAX_HEARTBEAT_DEVICES`, `SIGNAL_ROSTER_UPDATED`
- `custom_components/mqtt_actions/topics.py` - `heartbeat_topic`, `heartbeat_wildcard`, `parse_heartbeat_topic`
- `custom_components/mqtt_actions/manager.py` - `Manager.presence`, `Manager.version`, start, stop, reconnect and republish wiring
- `custom_components/mqtt_actions/sync.py` - reports availability changes to presence (see deviations)
- `docs/broker-acl.md` - heartbeat row, ACL lines and bullets
- `tests/test_presence.py`, `tests/test_multi_instance_ops.py` (new, `multi_instance`), `tests/test_topics.py`, `tests/broker/test_acl.py`, `tests/test_multi_instance.py`

## Decisions Made
- The expiry timer is armed 1 s after the earliest deadline, because online is `age <= 90` (strict expiry); this gives the planned 89 s online and 91 s offline.
- Peer cap with eviction: a new peer at the cap replaces the stalest row that is already expired, otherwise it is not tracked. Without the eviction a flood of random ids would block every real instance until the next restart (T-04-12).
- The tick publishes under the manager lock so a heartbeat can never follow the `offline` availability of a stop.
- Roster rows carry a `devices` key besides `id`, `name`, `version`, `last_seen` and `online`, because the plan's multi-instance test asserts the device count; plan 04-04 maps rows to its five attribute keys explicitly.
- `online_peers()` returns the online peer rows (dicts), which gives plan 04-10 the id and the name for the "no answer" status.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Availability changes reach the roster**
- **Found during:** Task 2 (clean shutdown test)
- **Issue:** `files_modified` does not list `sync.py`, but a clean shutdown changes only the retained availability that `SyncManager` tracks. Without a notification the roster rows read correctly (status is computed on read) but `SIGNAL_ROSTER_UPDATED` would lag up to 30 s, so the sensor of plan 04-04 would show a stale count.
- **Fix:** `SyncManager._on_availability_message` calls `manager.presence.on_availability_changed()` (two lines); presence re-evaluates and signals only when the online set changed.
- **Files modified:** `custom_components/mqtt_actions/sync.py`
- **Verification:** `test_clean_shutdown_marks_the_peer_offline_at_once` asserts the row, the count, `owner_offline` and the signal.
- **Committed in:** `bf574b1`

**2. [Rule 1 - Bug in existing tests] Two SYN-04 order tests assumed the last publish is the availability**
- **Found during:** Task 1 (full suite)
- **Issue:** `test_first_start_publishes_documents_before_availability` and `test_reconnect_republishes_config_before_availability` asserted `published[-1]` is `online`. The plan puts the heartbeat after `online`, so the assertion measured the wrong thing; the load-bearing order (documents, discovery, online) is unchanged and still asserted through `_publish_order`.
- **Fix:** a `_last_before_heartbeat` helper in `tests/test_multi_instance.py`; the republish test additionally pins that the heartbeat is the last publish.
- **Files modified:** `tests/test_multi_instance.py`
- **Committed in:** `d9053a8`

**3. [Rule 2 - Missing critical functionality] Eviction of expired rows at the peer cap**
- **Found during:** Task 2 (peer cap design)
- **Issue:** "not tracked at the cap" alone lets random heartbeat ids permanently block real instances once they expire but are never freed.
- **Fix:** see Decisions Made; `test_peer_cap` still asserts that further ids are not tracked while all rows are fresh.
- **Files modified:** `custom_components/mqtt_actions/presence.py`
- **Committed in:** `bf574b1`

### Test-design adjustments (not plan deviations)
- The expiry test uses a synthetic peer (a heartbeat published straight on the fake broker) instead of a second running instance: `async_fire_time_changed` fires every timer of the shared event loop, which would also fire the real peer's own heartbeat tick and keep it alive. The shutdown, reconnect and tick scenarios use two real instances.
- `test_rejected_heartbeats_log_nothing_from_the_payload` inspects only records of the `custom_components.mqtt_actions` logger, because core MQTT logs every received payload at debug level.

---

**Total deviations:** 3 auto-fixed (2 missing critical, 1 existing-test bug)
**Impact on plan:** All three are small and keep the plan's behavior intact; the sync hook is the only change outside the listed files.

## Issues Encountered
None. The assumption from the plan stands: a newly started instance learns its peers at their next heartbeat (at most 30 s), because a non-retained message is not replayed.

## User Setup Required
None - no external service configuration required. Operators who use the documented ACL must add the two heartbeat lines to their own copy (documented in `docs/broker-acl.md`); without them heartbeats are denied and peers show offline.

## Threat Flags
None. The new surface (a subscription to the heartbeat wildcard and the heartbeat publish) is covered by T-04-09 to T-04-14 of the plan, each mitigated and pinned by a test.

## Known Stubs
None.

## Next Phase Readiness
- Plan 04-04 can build the roster sensor on `presence.rows()` and `SIGNAL_ROSTER_UPDATED`; the signal already fires on heartbeat, expiry, shutdown and reconnect.
- Plans 04-10, 04-11 and 04-12 can use `online_peers()`, `peer_status()`, `owner_offline()` and `PresenceManager.session`.
- Operators must extend an existing ACL by the heartbeat lines.

## Self-Check: PASSED

- Created/modified files exist: `presence.py`, `tests/test_presence.py`, `tests/test_multi_instance_ops.py`, `docs/broker-acl.md`, `const.py`, `topics.py`, `manager.py`, `sync.py` found on disk.
- Commits found in `git log`: `8852c2d`, `d9053a8`, `cc614fb`, `bf574b1`, `37bb5e5`, `6bf3538`; `test(04-03)` precedes `feat(04-03)` for every task.
- Plan verification re-run: `uv run pytest tests -q` 901 passed; `-m multi_instance` 45 passed; `-m broker` 14 passed against Mosquitto; `ruff check` and `ruff format --check` clean; `grep -c heartbeat docs/broker-acl.md` prints 9; `grep -c "def owner_offline"` prints 2.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
