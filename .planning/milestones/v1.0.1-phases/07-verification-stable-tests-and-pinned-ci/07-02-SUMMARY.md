---
phase: 07-verification-stable-tests-and-pinned-ci
plan: 02
subsystem: testing
tags: [pytest, caplog, asyncio, flaky-test, log-scoping, stress-proof]

requires:
  - phase: 07-01
    provides: "pinned runner and structure guard (no code dependency)"
provides:
  - "Permanent autouse fixture always_slow_event_loop: asyncio's slow-callback WARNING is present in every test"
  - "Log assertions of test_manager_breaker.py, test_modes.py and test_hub_removal.py scoped to the integration's own loggers"
  - "07-PROOF.md started with the 50 of 50 stress proof"
affects: [07-03, 07-04, 07-05]

actuals:
  tokens: 2200
  tasks: 3
  commits: 4

plan_head_before: eed2c4f921d6f9289db57444edf5b421e2072485
plan_head_after: 14d72ee15640e7832be1a1a55f0aa192d8eeb32a

tech-stack:
  added: []
  patterns:
    - "Deterministic reproducer for a load-dependent defect class: make the foreign noise constant instead of retrying"

key-files:
  created:
    - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md
  modified:
    - tests/conftest.py
    - tests/test_manager_breaker.py
    - tests/test_modes.py
    - tests/test_hub_removal.py

key-decisions:
  - "The always-slow probe is permanent (autouse in tests/conftest.py), not environment-gated"
  - "The flake is a test-scope defect; no file under custom_components changed (D-06)"
  - "Two ERROR-level negative checks in test_runner_modes.py stay unscoped on purpose"

requirements-completed: [QLT-02]

status: complete
---

# Phase 7 Plan 02: Stable Tests Summary

**The load-dependent flake class is a test-scope defect (asyncio's slow-callback WARNING leaking into unscoped `caplog` counts); a permanent always-slow loop fixture makes it a deterministic red, three assertions are scoped to the integration's loggers, and the named test passed 50 of 50 repetitions under load.**

## Accomplishments

- Added autouse `always_slow_event_loop` to `tests/conftest.py`. It requests PHACC's `enable_event_loop_debug` by name and sets `slow_callback_duration = 0.0`, so asyncio logs `Executing <...> took N seconds` at WARNING for every callback in every test.
- Scoped `_warnings` in `tests/test_manager_breaker.py` (now `own_warnings(caplog, exact=True)`), the observe `lines` filter in `tests/test_modes.py` (`record.name.startswith(OWN_LOGGER)`), and the negative MQTT warning check in `tests/test_hub_removal.py`.
- Proved the named test `test_delete_device_own_subscription_never_sees_state_clear` stable: 50 of 50 repetitions on two cores shared with four busy loops, probe on (see `07-PROOF.md`).
- No `custom_components/`, `pyproject.toml` or `uv.lock` change; no retry, skip, expected-failure marker or rerun plugin added (acceptance greps return 0 matches).

## Task Commits

1. Task 1 RED: `ec2711d` test(07-02): make the foreign asyncio slow-callback warning part of every test
2. Task 1 GREEN: `7173b28` fix(07-02): count only the integration's own warnings in two log assertions
3. Task 2: `f8e271e` refactor(07-02): scope the hub removal warning check to the integration's own loggers
4. Task 3: `14d72ee` docs(07-02): record the stress proof of the named test

## Diagnosis evidence (D-05)

- RED run: `uv run --locked pytest -q -p no:cacheprovider -n 6 -m "not broker"` -> `2 failed, 1471 passed in 31.79s`. Failing set was exactly:
  - `tests/test_manager_breaker.py::test_change_after_max_runs_trips_pauses_and_informs`: `tests/test_manager_breaker.py:150: assert 7 == 1` (7 records, all `asyncio` level 30 `Executing %s took %.3f seconds`)
  - `tests/test_modes.py::test_observe_logs_and_runs_nothing_but_tracks_the_baseline`: `tests/test_modes.py:135: assert 5 == 1` (5 messages, the `"observe"` substring matched asyncio task reprs, which contain the test function name)
- Asyncio record text: `WARNING:asyncio:Executing <Handle _run_until_complete_cb(<Task finishe...unners.py:110>) at /usr/lib/python3.14/asyncio/base_events.py:181 created at /usr/lib/python3.14/asyncio/events.py:94> took 0.000 seconds`
- The named test passed under the probe (`1 passed`): its Phase 5 scoping (`own_warnings(caplog) == []`) holds, so the flake cause is the same defect class (a foreign asyncio record decides an assertion once a callback exceeds the real 0.1 s threshold on a loaded machine), already fixed for that test and now removed from its two siblings.
- The race candidate in `_async_remove_device` (`manager.py:2126`) is not involved: the named test passes under the probe and the two failing tests never touch it. No production change.

## TDD Gate Compliance

RED commit `ec2711d` (`test(07-02)`) precedes GREEN `7173b28` (`fix(07-02)`); the Task 2 refactor `f8e271e` has no new test (assertion refactor, guarded by the permanent probe).

- RED command: `uv run --locked pytest -q -p no:cacheprovider -n 6 -m "not broker" --junitxml=...`, exit 1, failures on the record-count assertions (not import, collection or fixture errors).
- `gsd_run check tdd-red-evidence`: **RED_EVIDENCE_OK** (reason `target_test_failed`) for both `test_change_after_max_runs_trips_pauses_and_informs` and `test_observe_logs_and_runs_nothing_but_tracks_the_baseline`, with the tooling caveat under Deviations.
- GREEN: `1473 passed` (not broker), `17 passed` (broker, `MQTT_ACTIONS_REQUIRE_BROKER=1`, no skip), ruff check and format clean.

## Sweep of the log assertions (Task 2)

Classes: (a) scoped to the integration's loggers, (b) positive or specific-text assertion a foreign record cannot break, (c) negative assertion whose filter a foreign record could satisfy.

| Site | Class | Note |
|------|-------|------|
| tests/log_helpers.py:23 | (a) | the helper itself |
| tests/test_config_flow_select.py:642 | (b) | positive `any(...)` |
| tests/test_hub_removal.py:254 | (b) | positive, unchanged |
| tests/test_hub_removal.py:277 | (c) -> (a) | scoped in this plan via `own_warnings(caplog, exact=True)` |
| tests/test_runner_modes.py:69 | (a) | `OWN_LOGGERS` prefix filter |
| tests/test_runner_modes.py:292 | (b) | exact count of a specific `MAX_EXCEEDED` text |
| tests/test_runner_modes.py:393, 448 | kept on purpose | ERROR-level negatives: asyncio logs real defects (e.g. unretrieved task exception) at ERROR and these must fail a test |
| tests/test_modes.py:137 | (c) -> (a) | scoped in Task 1 |
| tests/test_modes.py:289 | (a) | prefix filter |
| tests/test_sync_follower.py:103 | (a) | prefix filter |
| tests/test_manager.py:449 | (b) | ERROR with `exc_info`, count 1; a foreign ERROR with traceback is a real defect signal |
| tests/test_manager.py:548 | (a) | prefix filter |
| tests/test_manager.py:952 | (b) | `"Ignoring empty payload" not in caplog.text`: specific text no asyncio record contains; preceded by `own_warnings(caplog) == []` |
| tests/test_manager.py:975, 1190 | (b) | positive `"down" in caplog.text` |
| tests/test_manager.py:1062, 1082, 1245 | (b) | positive |
| tests/test_presence.py:223 | (a) | prefix filter |
| tests/test_presence.py:271 | (b) | exact count of a specific phrase |
| tests/test_sync_owner.py:640 | (a) | prefix filter |
| tests/test_config_flow_delete.py:155 | (a) | prefix filter (multi-line comprehension) |
| tests/test_trust.py:236 | (a) | prefix filter |
| tests/test_services.py:558 | (b) | `SENTINEL not in caplog.text`: a secret must not appear in any log, foreign included, so it stays global on purpose |

Other `own_warnings` users (`test_discovery_select.py`, `test_manager_select.py`, `test_manager.py` named test) are class (a). No class (c) site is left unscoped; the full suite is green with the probe on, which would fail any remaining one.

## Verification

- `uv run --locked pytest -q -p no:cacheprovider -n 6 -m "not broker"`: 1473 passed (probe on)
- `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider -m broker`: 17 passed
- `uv run --locked pytest -q -p no:cacheprovider tests/test_hub_removal.py tests/test_log_helpers.py`: 11 passed
- `uv run ruff check . && uv run ruff format --check .`: clean
- Stress: `repetitions passed: 50 of 50`, 354 s, head `f8e271e`, no spinner left (`ps ... | grep -c` prints 0)
- Added test lines contain none of xfail, flaky, reruns, mark.skip; `git log --grep='(07-02)' -- custom_components pyproject.toml uv.lock` prints nothing
- Tracer gate: `<verify>` is automated-only (end-of-phase), re-run after the fix commit and passed; expansion proceeded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RED evidence checker cannot parse pytest console output (same as 07-01)**
- **Found during:** Task 1 RED
- **Issue:** `gsd_run check tdd-red-evidence` takes `targetTest`, `exitCode`, `output` fields and parses TAP or Surefire XML. With pytest `--junitxml` as `output`, both targets gave `INVALID_RED (no_target_test_failure)`: the checker's `name="..."` regex matches inside the leading `classname="..."` attribute of pytest's `<testcase>` tags.
- **Fix:** In scratchpad copies of the record only (not committed), swapped the attribute order (`name` before `classname`) of the `<testcase>` tags, content otherwise unchanged; both targets then returned `RED_EVIDENCE_OK`. The raw pytest output above independently shows the assertion failures. Both the raw (INVALID_RED) and swapped (RED_EVIDENCE_OK) records were run, so the verdict depends on this tooling quirk and is disclosed here. No repo evidence file was altered.
- **Files modified:** none in the repo
- **Commit:** n/a

**2. [Rule 3 - Blocking] `gsd_run` not on PATH**
- Invoked `node ~/.claude/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence <record.json>` directly. Plan-level SDK state commands were not used, per the dispatch instruction (STATE.md and ROADMAP.md untouched).

### Notes

- The plan text says the named test uses `own_warnings` "since Phase 5"; the import in `tests/test_manager.py` is present and the test at line 951 uses `own_warnings(caplog) == []`, confirmed.
- `commits: 4` is measured before the SUMMARY commit itself (`git rev-list --count` from the ledger base to `plan_head_after`).

## Known Stubs

None.

## Threat Flags

None. T-07-04 (foreign records deciding assertions), T-07-05 (busy loops, bounded by `timeout 900`, killed by trap, none left) and T-07-06 (no retry, skip, xfail or silenced asyncio logger, no production change) mitigated as planned.

## Self-Check: PASSED

- FOUND: tests/conftest.py (`def always_slow_event_loop`), tests/test_manager_breaker.py, tests/test_modes.py, tests/test_hub_removal.py, 07-PROOF.md (tracked, contains "50 of 50")
- FOUND commits: ec2711d, 7173b28, f8e271e, 14d72ee
