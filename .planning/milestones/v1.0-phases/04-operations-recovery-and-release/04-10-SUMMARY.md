---
phase: 04-operations-recovery-and-release
plan: 10
subsystem: operations
tags: [home-assistant, mqtt, retrigger, acknowledgements, services, broker-acl, security, mosquitto]

requires:
  - phase: 04-operations-recovery-and-release
    provides: presence roster and heartbeat (04-03), modes and breaker gate (04-05), ApprovalState and Manager.approval_state (04-07), services layer with resolve_device (04-08)
provides:
  - Re-trigger protocol (non-retained request per device, non-retained acknowledgement per requester) with strict parsing
  - RetriggerCoordinator (caller collector with a 5 s window, receiver with replay, rate and gate rules) wired into Manager as Manager.retrigger
  - Public Manager.device(device_id) accessor
  - mqtt_actions.retrigger service (admin only, optional response) with translated refusals in en and de
  - Re-trigger and acknowledgement topics in the documented ACL, enforced by a real Mosquitto
affects: [04-11 adoption, 04-12 release checks, 04-13 docs (operations page, ACL page, response shape)]

actuals:
  tokens: 23769
  tasks: 3
  commits: 6
plan_head_before: 764c01c77dc1ab8237418d139c1f3a2cf458a0b1
plan_head_after: f7d180b0d66ee39fbc57864a10b9e26d838b930c

tech-stack:
  added: []
  patterns:
    - "A remote execution path reuses the existing gates (can_run, effective mode, breaker, approval state) and enqueues with test=True, so it never touches tracker, baseline, state topic or breaker count"
    - "Receiver gate order: retained, size and strict parse, freshness, duplicate id, per-device rate limit (foreign requests only), device known, state valid, mode, breaker, runnability"
    - "Per-call pending record with an asyncio.Event, removed in a finally; first answer per instance, capped at MAX_TRACKED_INSTANCES; unexpected and offline roster instances are listed too"

key-files:
  created:
    - custom_components/mqtt_actions/retrigger.py
    - tests/test_retrigger.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/topics.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/presence.py
    - custom_components/mqtt_actions/services.py
    - custom_components/mqtt_actions/services.yaml
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - docs/broker-acl.md
    - tests/test_multi_instance_ops.py
    - tests/test_services.py
    - tests/test_translations.py
    - tests/broker/test_acl.py

key-decisions:
  - "Receiver runs the re-trigger exactly like a test press (enqueue with test=True after the mode and breaker checks) and never calls breaker.record(), so a re-trigger cannot trip or advance a breaker (D-01, D-02)"
  - "not_approved is decided before no_actions: when the trigger cannot run and the mirror is pending or blocked the answer is not_approved; otherwise error with no_actions (trigger has no actions) or not_runnable"
  - "The caller claims its per-device send slot before publishing and gives it back when the publish itself failed, so two concurrent calls cannot both pass and a failed publish does not block a retry"
  - "The receiver's per-device last-accepted times are bounded to MAX_TRACKED_INSTANCES (expired entries pruned first, then oldest), because request device ids are untrusted; an own echo skips the limit but still records the time and still goes through the duplicate check"
  - "A receiver that does not know the device answers error/unknown_device after the rate limit, so every request gets an answer from every instance and the limit also bounds that traffic"
  - "The service response keys the device as uuid, and every entry carries instance_id, instance_name, status and an optional reason; no_answer and its offline reason are produced by the caller only"

patterns-established:
  - "Strict-parse helpers (valid_text, valid_uuid, within_size_cap) live in presence.py and are shared by every protocol message of the operations phase"
  - "Hostile-message tests pin each rejection individually (parametrized, one id per field and flaw) and assert a None result, never an exception"

requirements-completed: [OPS-01, OPS-02]

coverage:
  - id: D1
    description: "One service call re-runs a device's actions once on every instance that approved it, the caller included, through the test-press path, and returns the acknowledgements"
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_retrigger_runs_approved_instances_and_touches_no_state"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_retrigger_service_returns_the_acknowledgements"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_retrigger_returns_before_the_window_when_everyone_answered"
        status: pass
    human_judgment: false
  - id: D2
    description: "A re-trigger never changes entity state, baseline, state topic, revision or circuit breaker of any instance"
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_retrigger_runs_approved_instances_and_touches_no_state"
        status: pass
    human_judgment: false
  - id: D3
    description: "The receiver answers executed, not_approved, paused, observing, disabled or error with a reason code and runs nothing for any non-executed case"
    requirement: OPS-02
    verification:
      - kind: integration
        ref: "tests/test_retrigger.py#test_statuses"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_unapproved_mirror_answers_not_approved_and_runs_nothing"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_retrigger_honors_modes_and_breaker_in_the_multi_instance_tier"
        status: pass
    human_judgment: false
  - id: D4
    description: "Retained, stale, future, duplicate, oversized, malformed and flooding requests run nothing; the caller refuses a repeat inside 5 seconds with a translated error"
    requirement: OPS-01
    verification:
      - kind: unit
        ref: "tests/test_retrigger.py#test_parse_request_rejects_invalid_payloads"
        status: pass
      - kind: integration
        ref: "tests/test_retrigger.py#test_retained_requests_are_ignored"
        status: pass
      - kind: integration
        ref: "tests/test_retrigger.py#test_stale_and_future_requests_are_dropped"
        status: pass
      - kind: integration
        ref: "tests/test_retrigger.py#test_duplicate_request_ids_run_once"
        status: pass
      - kind: integration
        ref: "tests/test_retrigger.py#test_receiver_rate_limit_per_device"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_retrigger_service_errors_are_translated"
        status: pass
    human_judgment: false
  - id: D5
    description: "The caller reports offline roster instances and silent online instances as no_answer, ignores acknowledgements of another request or device, and caps the answers kept per request"
    requirement: OPS-02
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_roster_offline_and_silent_instances_are_no_answer"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_acknowledgements_per_request_are_capped"
        status: pass
      - kind: unit
        ref: "tests/test_retrigger.py#test_parse_ack_rejects_invalid_payloads"
        status: pass
    human_judgment: false
  - id: D6
    description: "The documented broker ACL grants the request topic to Home Assistant users only and each instance read access to its own acknowledgement topic; a real Mosquitto enforces it"
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/broker/test_acl.py#test_retrigger_topic_is_a_live_trigger_for_home_assistant_users_only"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_ack_topic_is_readable_only_by_its_instance"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_any_instance_may_answer_a_requester"
        status: pass
    human_judgment: false
  - id: D7
    description: "The service is admin only, accepts the companion device of an owned device or a mirror, and has its texts and refusals in English and German"
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_retrigger_service_is_admin_only"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_retrigger_service_accepts_a_mirror"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_required_retrigger_keys_exist_in_both_languages"
        status: pass
    human_judgment: false
  - id: D8
    description: "With two real Home Assistant instances on one broker, mqtt_actions.retrigger from Developer Tools lists both instances (executed, or not_approved where not approved) and the device state does not change"
    requirement: OPS-02
    verification: []
    human_judgment: true
    rationale: "Real core MQTT, a real second instance and the Developer Tools response view are not reproduced by the fake broker tier; the plan names this as a human check"

duration: 30min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 10: Re-trigger Summary

**Re-trigger protocol and `mqtt_actions.retrigger` service: one non-retained request per device runs the actions of a StateValue through the test-press path on every approving instance, each answers on a per-requester acknowledgement topic, and the caller returns who executed it; replay, flood, stale and malformed requests run nothing, and the ACL for both topics is enforced by a real Mosquitto.**

## Performance

- **Duration:** about 30 min of active work (the machine clock jumped during the final task, so the commit timestamps are not a reliable span)
- **Started:** 2026-10-02T10:55:22+02:00
- **Completed:** 2026-10-02
- **Tasks:** 3
- **Files modified:** 15 (2 created, 13 modified)

## Accomplishments

- **Protocol (D-01, D-02):** request topic `<base>/v1/devices/<uuid>/retrigger` (QoS 1, retain False) with `request_id`, `requester`, `state` (the exact StateValue, never actions) and `sent_at`; acknowledgement topic `<base>/v1/instances/<requester id>/acks` with `request_id`, `device_id`, `instance_id`, `instance_name`, `status`, optional `reason`. Every instance, the caller included, runs the trigger with `enqueue(..., test=True)` after the same gates as a test press; no tracker, baseline, state topic, revision or breaker count moves.
- **Receiver rules (D-04, T-04-42 to T-04-46):** gate order retained, size and strict parse, freshness (60 s either way), duplicate id (last 128), per-device rate limit (one per 5 s, foreign requests only), device known, state valid, mode (`disabled`, `observing`), breaker (`paused`), runnability (`not_approved`, `no_actions`, `not_runnable`), then `executed`.
- **Caller (D-03, T-04-47, T-04-48):** expected acknowledgers are this instance plus the online roster peers; offline roster instances are `no_answer` with reason `offline` without waiting, silent online ones are `no_answer` after the window, the call leaves early when everyone answered, answers for another request or device are ignored, one answer per instance, capped per request, pending record removed in a `finally`.
- **Service (D-02):** `mqtt_actions.retrigger` (admin only, optional response) with `device_id` (device selector, owned or mirror) and an optional `state`; refusals `retrigger_rate_limited`, `retrigger_bad_state`, `retrigger_no_state` are translated in English and German.
- **ACL (D-04):** the request and acknowledgement topics are in the topic table, the single tested `acl` block, "Why an ACL matters", "What it enforces" and "Limits" (acknowledgements are advisory and forgeable inside the Home Assistant group); three broker tests pin it against Mosquitto.

## Task Commits

1. **Task 1 (tracer, TDD):** RED `26f6bd1` (test), GREEN `15c4925` (feat) - protocol, topics, constants, coordinator, manager wiring
2. **Task 2 (TDD):** RED `5688847` (test), GREEN `af0d766` (feat) - strict parsing, receiver gates, all statuses, caller limits and collector edge cases
3. **Task 3 (TDD):** RED `f4fee1f` (test), GREEN `f7d180b` (feat) - service, translations, ACL document and broker tests

**Plan metadata:** the docs commit that carries this summary, STATE.md, ROADMAP.md and REQUIREMENTS.md.

## Files Created/Modified

- `custom_components/mqtt_actions/retrigger.py` - request and acknowledgement parsing, `RetriggerError`, `RetriggerCoordinator` (caller and receiver)
- `custom_components/mqtt_actions/const.py` - window, interval, seen limit and age constants, `ACK_*` status words, reason words, `SERVICE_RETRIGGER`
- `custom_components/mqtt_actions/topics.py` - `retrigger_topic`, `retrigger_wildcard`, `parse_retrigger_topic`, `acks_topic`
- `custom_components/mqtt_actions/manager.py` - `Manager.retrigger`, public `Manager.device`, start and stop wiring
- `custom_components/mqtt_actions/presence.py` - `valid_text`, `valid_uuid`, `within_size_cap` made public for reuse (renames only)
- `custom_components/mqtt_actions/services.py`, `services.yaml` - the `retrigger` service
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - service texts and three refusals
- `docs/broker-acl.md` - rows, ACL lines and bullets for both topics
- `tests/test_retrigger.py` (new), `tests/test_multi_instance_ops.py`, `tests/test_services.py`, `tests/test_translations.py`, `tests/broker/test_acl.py`

## Decisions Made

See `key-decisions` above. The one with the widest effect: the receiver answers every accepted request (including `error/unknown_device`), so the per-device rate limit sits before the device lookup and its bookkeeping is bounded because device ids in requests are untrusted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/test_retrigger.py` is a multi-instance module**
- **Found during:** Task 2 (full-suite run after GREEN)
- **Issue:** `tests/test_repo_structure.py::test_tiers_partition_the_suite` requires every module that uses `make_instance` to carry `pytest.mark.multi_instance`. The plan sketched the receiver tests on the `mqtt_mock` tier, but the module must hold both the pure parser tests and the named receiver tests (`test_duplicate_request_ids_run_once` is an artifact of that file).
- **Fix:** The receiver tests run real instances on the FakeBroker; a retained request is simulated by storing it on the broker and replaying it through a reconnect, which delivers it with `retain=True`. The whole module is marked `multi_instance` (the pure tests run in that tier too).
- **Files modified:** `tests/test_retrigger.py`
- **Verification:** `uv run pytest tests -q` green including the tier partition test
- **Committed in:** `af0d766`

**2. [Rule 3 - Blocking] Strict-parse helpers shared instead of duplicated**
- **Found during:** Task 2
- **Issue:** The acknowledgement and request parsers need the same size cap, name and uuid checks as the heartbeat parser, which had them private.
- **Fix:** `_valid_text`, `_valid_session` and `_within_size_cap` in `presence.py` are renamed `valid_text`, `valid_uuid` and `within_size_cap` (no behavior change, docstrings generalized) and imported by `retrigger.py`.
- **Files modified:** `custom_components/mqtt_actions/presence.py`
- **Verification:** `tests/test_presence.py` and the full suite unchanged green
- **Committed in:** `af0d766`

**3. [Rule 2 - Missing critical] Bounded receiver bookkeeping and an answer cap, beyond the listed constants**
- **Found during:** Task 2
- **Issue:** Device ids in requests are untrusted, so a per-device last-accepted map keyed by them could grow without bound (T-04-47 scope).
- **Fix:** The map is pruned of expired entries and then of its oldest entries beyond `MAX_TRACKED_INSTANCES`. Also added the constants `REASON_RATE_LIMITED` and `REASON_NO_STATE` for the caller refusals, which the plan's list did not name.
- **Files modified:** `custom_components/mqtt_actions/retrigger.py`, `custom_components/mqtt_actions/const.py`
- **Verification:** `test_receiver_rate_limit_per_device`, `test_acknowledgements_per_request_are_capped`
- **Committed in:** `15c4925`, `af0d766`

**4. [Test addition] Extra tests beyond the plan's list**
- `test_acknowledgements_per_request_are_capped` (T-04-47), `test_services_yaml_describes_retrigger`, and the status cases `instance_disabled`, `mirror_no_actions` and `not_runnable` in `test_statuses`.

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 missing critical) plus extra tests
**Impact on plan:** No scope creep; all changes are required by the tier rule, by reuse of existing strict helpers, or by the threat register.

## TDD Gate Compliance

Each task has its `test(04-10)` commit before its `feat(04-10)` commit (`26f6bd1` before `15c4925`, `5688847` before `af0d766`, `f4fee1f` before `f7d180b`); no REFACTOR commits. RED evidence is recorded by hand because `gsd_run check tdd-red-evidence` parses TAP and Surefire output, not pytest (as in plans 04-05 to 04-07).

- **Task 1 RED:** 4 target tests failed: `AttributeError: module ... topics has no attribute 'retrigger_topic'`, `ModuleNotFoundError: ...retrigger` (the import sits inside that one test so a missing module fails the test and not the collection), and `AttributeError: 'Manager' object has no attribute 'device'` / `'retrigger'` for the two instance tests.
- **Task 2 RED:** 47 failures on planned assertions: parser cases returned a value instead of None, duplicate and stale requests ran twice (`assert 2 == 1`), the mode, breaker and approval cases answered `executed`, offline peers were missing from the response (`KeyError`), rate-limit case `DID NOT RAISE RetriggerError`, the flood case kept 10 answers (`assert 10 <= 2`). Two tests already passed in RED by design of the tracer (retained requests ignored, the `executed` status) and the parser rejects that need only a type check also passed; all other cases failed. A first draft used the topic base `b` for instance tests (no mirror, `assert 0 == 1`); fixed before the RED commit by separating `BROKER_BASE`.
- **Task 3 RED:** `ServiceNotFound: Action mqtt_actions.retrigger not found` for the service tests, missing translation keys, `KeyError: 'retrigger'` in the descriptions, and the three broker tests received `set()` instead of the granted messages.

## Issues Encountered

- A mirror created from a foreign document needs a few `async_block_till_done` rounds on the fake broker; the receiver helper settles four times.
- `selector: device` is normalized with `multiple: False`, so the services.yaml test pins that shape.
- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` (flaked once in 04-05) did not fail in any of the full-suite runs here.
- The human check of Task 3 (two real Home Assistant instances, Developer Tools) was not run; it is recorded as deliverable D8 with `human_judgment: true` for the end-of-phase verification.

## User Setup Required

None - no external service configuration required. Operators who use the documented ACL must add the three new lines per Home Assistant user (see `docs/broker-acl.md`).

## Next Phase Readiness

- The response shape (`request_id`, `uuid`, `state`, `instances[]` with `instance_id`, `instance_name`, `status`, optional `reason`) and the status and reason words are final for the operations docs of plan 04-13.
- Plan 04-11 (adoption) can reuse `Manager.device`, the roster `owner_offline` and `ApprovalState` unchanged.

## Self-Check: PASSED

- Created files exist: `custom_components/mqtt_actions/retrigger.py`, `tests/test_retrigger.py`
- Commits exist: `26f6bd1`, `15c4925`, `5688847`, `af0d766`, `f4fee1f`, `f7d180b`
- Final runs: `uv run pytest tests -q` 1147 passed (broker tier 17 passed, multi-instance tier 129 passed), `uv run ruff check .` and `uv run ruff format --check .` clean, `grep -c test=True` in `retrigger.py` is at least 1, `grep -c RETRIGGER_SEEN_LIMIT` is 3, `grep -c retrigger docs/broker-acl.md` is 4

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
