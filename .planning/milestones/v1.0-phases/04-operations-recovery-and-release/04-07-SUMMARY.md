---
phase: 04-operations-recovery-and-release
plan: 07
subsystem: infra
tags: [home-assistant, diagnostics, redaction, allow-list, approval-state, mqtt]

requires:
  - phase: 04-operations-recovery-and-release
    provides: PresenceManager.rows(), device_mode and effective_mode (plans 04-03, 04-05), mirror companions (plan 04-06)
  - phase: 03-multi-instance-sync
    provides: MirrorInfo, the approval store and spec_has_actions
provides:
  - diagnostics platform for the hub entry (async_get_config_entry_diagnostics) built from an allow-list
  - ApprovalState string enum (owned, approved, pending, blocked, no_actions, unknown) and Manager.approval_state
  - tests that pin the key sets and prove that no sentinel and no full instance id leaves the instance
affects: [04-08 re-trigger acknowledgements (reuse the approval words), 04-13 docs]

actuals:
  tokens: 5200
  tasks: 2
  commits: 4
plan_head_before: 595d70907b9952ed41243f08afa72a54e0e725e5
plan_head_after: b9f00507333e777c7426109cd4359b2959ceee90

tech-stack:
  added: []
  patterns:
    - "Diagnostics are an allow-list: every key is written by name, nothing is dumped and then redacted; async_redact_data runs over the result only as a safety net"
    - "One public word for the approval state of a device, shared by diagnostics and later acknowledgements"

key-files:
  created:
    - custom_components/mqtt_actions/diagnostics.py
    - tests/test_diagnostics.py
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/trust.py
    - tests/test_trust.py

key-decisions:
  - "The roster rows of the diagnostics are a projection of PresenceManager.rows() to id (shortened), name, version, last_seen and online; the device count of a peer is left out because the plan documents five roster keys"
  - "An entry without a manager answers {'loaded': False} and nothing else; found with getattr(entry, 'runtime_data', None) because an entry that was never set up has no runtime_data attribute"
  - "The redaction safety net replaces a leaked key's value with the core marker instead of dropping the key, which is how async_redact_data works; the test asserts the marker and the absence of every leaked value"
  - "The owned device hash is computed from the spec (content_hash(build_content(spec))), the mirror's from its recorded MirrorInfo.content_hash; neither is the approval hash"

patterns-established:
  - "Sentinel tests for shareable output: sentinel strings in entity ids, service data, templates, trigger labels and device names, asserted absent from json.dumps of the result, plus full-id absence and short-id presence"

requirements-completed: [OPS-04]

coverage:
  - id: D1
    description: "The diagnostics download lists hub options, roster and per device uuid, kind, origin, owner, mode, effective mode, approval, breaker, rev and hash, and its keys equal the documented sets"
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_diagnostics.py#test_diagnostics_structure"
        status: pass
      - kind: integration
        ref: "tests/test_diagnostics.py#test_output_has_exactly_the_documented_keys"
        status: pass
      - kind: integration
        ref: "tests/test_diagnostics.py#test_device_rows_cover_modes_breaker_rev_and_hash"
        status: pass
      - kind: integration
        ref: "tests/test_diagnostics.py#test_origin_and_owner"
        status: pass
    human_judgment: false
  - id: D2
    description: "No action content (entity ids, service data, templates, trigger labels), no device name and no full instance id of this instance, a mirror owner or a roster peer is in the serialized result"
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_diagnostics.py#test_sentinel_strings_never_appear_in_the_output"
        status: pass
      - kind: integration
        ref: "tests/test_diagnostics.py#test_redaction_safety_net_removes_leaked_keys"
        status: pass
    human_judgment: false
  - id: D3
    description: "Roster rows list peers with a shortened id and keep an expired peer as offline; an entry without a manager answers a minimal not-loaded dict"
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_diagnostics.py#test_roster_rows_are_shortened_and_include_offline_peers"
        status: pass
      - kind: integration
        ref: "tests/test_diagnostics.py#test_unloaded_entry_returns_a_small_answer"
        status: pass
    human_judgment: false
  - id: D4
    description: "Manager.approval_state answers owned, approved, pending, blocked, no_actions or unknown"
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_trust.py#test_approval_state_words"
        status: pass
    human_judgment: false
  - id: D5
    description: "In a real Home Assistant, Settings, Devices and services, MQTT Actions, Download diagnostics yields a file with hub, roster and devices and none of the user's actions, entity ids or broker settings"
    verification: []
    human_judgment: true
    rationale: "The download button and the real file in the frontend are the plan's human-check; no automated test sees the real UI"

duration: 5min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 07: Diagnostics Summary

**A shareable diagnostics download for the hub entry, built from an allow-list (hub, roster, per-device structure with 8-character instance ids) with a redaction safety net and sentinel tests proving that no action content, device name or full id leaves, plus one public `ApprovalState` word per device**

## Performance

- **Duration:** about 5 min
- **Started:** 2026-10-02T08:26:16Z
- **Completed:** 2026-10-02T08:32Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `trust.py`: `ApprovalState(StrEnum)` with `owned`, `approved`, `pending`, `blocked`, `no_actions` and `unknown`. `manager.py`: `Manager.approval_state(device_id)` (owned, unknown, then for a mirror blocked, no_actions, approved or pending, in that order).
- `diagnostics.py` (new): `async_get_config_entry_diagnostics` reads only the manager's public properties, `presence.rows()` and the device rows, never actions, options, state values, entity ids, service data, device names or the MQTT entry. Instance ids (own, owner, roster) are cut to `INSTANCE_ID_SHORT_LENGTH` = 8. The result goes through `async_redact_data` with `TO_REDACT` (all 15 keys of the plan) as a safety net. An unloaded entry answers `{"loaded": False}`.
- Device rows carry `uuid`, `kind`, `origin`, `owner`, `mode`, `effective_mode`, `approval`, `breaker` (ok or tripped), `rev` and `hash` (content hash, never the approval hash).
- Pinned by 9 new tests (8 in `tests/test_diagnostics.py`, 1 in `tests/test_trust.py`), among them the two prohibitions `test_sentinel_strings_never_appear_in_the_output` (8 sentinels, three full ids absent, three short ids present, with an approved mirror) and `test_output_has_exactly_the_documented_keys`.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Tracer, diagnostics of a hub with an owned device and a mirror, free of every sentinel** - `c8b6794` (test), `2ebd06a` (feat)
2. **Task 2: Device row for every state and the redaction safety net** - `273d9e4` (test), `b9f0050` (feat)

**Plan metadata:** committed with this summary (docs: complete plan)

## TDD Gate Compliance

RED precedes GREEN for both tasks (`test(04-07)` `c8b6794`, `273d9e4` before `feat(04-07)` `2ebd06a`, `b9f0050`). No refactor commits were needed.

- **Task 1 RED:** all three tests failed for the planned reasons (`ModuleNotFoundError` for `custom_components.mqtt_actions.diagnostics`, `AttributeError: 'Manager' object has no attribute 'approval_state'`). The diagnostics module is imported inside the helper, not at module top, so each test fails on its own target instead of a collection error. A first run failed on a KeyError because the test's Select mirror had one option (documents need at least two, `MIN_OPTIONS`); that was a test-data mistake, fixed before the RED commit.
- **Task 2 RED:** `test_device_rows_cover_modes_breaker_rev_and_hash` (`KeyError: 'mode'`) and `test_output_has_exactly_the_documented_keys` (device rows lacked the documented keys) failed. The other four new tests (origin and owner, roster with offline peer, redaction safety net, unloaded entry) already passed at RED because Task 1 had built the roster, the safety net, the origin and owner fields and the not-loaded answer; they pin that behavior against later regressions. The plan's "five new tests" became six.
- `gsd_run check tdd-red-evidence` parses TAP and Surefire output, not pytest, so the RED evidence is recorded here by hand (as in plans 04-05 and 04-06).
- **Tracer gate:** the Task 1 verify chain (`tests/test_diagnostics.py tests/test_trust.py` 40 passed, full suite 959 passed, `ruff check`, `ruff format --check`) was re-run on the GREEN state and passed before expansion; `Tracer verified end-to-end - expanding`. The tracer's `<verify>` also carries a `<human-check>`; the run is dispatched in `mode: yolo` with `human_verify_mode: end-of-phase` (as plans 04-03 to 04-06), so the real-frontend download check is deferred to the phase verification (coverage D5).

## Files Created/Modified
- `custom_components/mqtt_actions/diagnostics.py` - allow-list diagnostics, shortening and the redaction safety net
- `custom_components/mqtt_actions/manager.py` - `Manager.approval_state`
- `custom_components/mqtt_actions/trust.py` - `ApprovalState` enum
- `tests/test_diagnostics.py` - structure, sentinel, device rows, roster, safety net, not-loaded and key-set tests
- `tests/test_trust.py` - `test_approval_state_words`

## Decisions Made
- Roster rows project `PresenceManager.rows()` to the five documented keys; the per-peer device count is not part of the documented set, so it stays out.
- The not-loaded check uses `getattr(entry, "runtime_data", None)`: a config entry that was never set up has no `runtime_data` attribute at all.
- The safety net redacts (core marker) rather than drops, because that is what `async_redact_data` does; the test asserts the marker on the leaked keys and the absence of every leaked value in the serialized result.
- Owned `hash` is computed from the spec, mirror `hash` is the recorded content hash; both are the shared-content hash, never the approval hash.

## Deviations from Plan

None - plan executed exactly as written. Two small notes: Task 2 added six tests instead of the five the acceptance criterion names (the not-loaded test is listed in the behaviors but not counted), and the `diagnostics` import in the tests is done inside the helper so RED fails on the target assertion.

## Issues Encountered
- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` (flaky once in plan 04-05) did not fail in any of my full-suite runs (959 and 965 passed).
- A one-line docstring in `Manager.approval_state` and the module docstring of the test file were shortened for the 120-character Ruff limit.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None. The builder reads no actions, options or MQTT entry data (T-04-27, T-04-28), instance ids are cut to 8 characters (T-04-29), and device names are left out of the device rows (T-04-30). Peer instance names appear in the roster as documented; they were validated as printable text when the heartbeat was parsed.

## Next Phase Readiness
- The re-trigger acknowledgements of a later plan can reuse `ApprovalState` and `Manager.approval_state`.
- The human-check (D5: Download diagnostics in a real Home Assistant) is left to the phase verification.

## Self-Check: PASSED

- Created and modified files exist: `diagnostics.py`, `tests/test_diagnostics.py`, `manager.py`, `trust.py`, `tests/test_trust.py` and this summary (checked with `[ -f ]`).
- Commits found in `git log`: `c8b6794`, `2ebd06a`, `273d9e4`, `b9f0050`; `git rev-list --count` from the plan's recorded base gives 4.
- Plan-level verification: `uv run pytest tests -q` 965 passed, `uv run ruff check .` and `uv run ruff format --check .` clean.
- Acceptance greps: `async_get_config_entry_diagnostics` in `diagnostics.py` 1, `async_redact_data` 3.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
