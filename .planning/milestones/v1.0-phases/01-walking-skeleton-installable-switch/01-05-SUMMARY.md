---
phase: 01-walking-skeleton-installable-switch
plan: 05
subsystem: discovery-lifecycle
tags: [home-assistant, mqtt, discovery, lifecycle, reconcile, store, repairs, availability]

requires:
  - phase: 01-04
    provides: StateTracker, Store-backed baseline and published-id set, ActionRunner with async_unload(remove_issue) and report_failure
provides:
  - Final device-based discovery contract proven against real core MQTT discovery (identity, availability, retained toggle, prefix)
  - AvailabilityState (online, offline, cleared), async_clear_device and async_clear_state on the publisher
  - Gateway discovery_enabled(), options-over-data MQTT configuration merge, connection-status subscription, KeyError-safe publish
  - Manager reconcile for add, change and remove; D-16 delete order; orphan cleanup from the persisted published set
  - Hub removal cleanup (D-15) through async_remove_entry and async_remove_all_devices
  - Reconnect republish, offline-on-unload without deletes, MQTT-discovery-disabled Repairs issue
affects: [01-06]

actuals:
  tokens: 13500
  tasks: 3
  commits: 6
plan_head_before: 2520cf877afdb6b14c43dd172f912cf8d1fbd7df
plan_head_after: 35512bb7261ebb97db2b705c017a9cfcdd04b616

tech-stack:
  added: []
  patterns:
    - "Every MQTT cleanup or republish step goes through _async_attempt: HomeAssistantError is logged as a warning and never raised (T-01-14)"
    - "Reconcile compares a JSON fingerprint of title and data per device, so unrelated entry updates rebuild nothing"
    - "Remove order: clear discovery, end the subscription, clear the retained state; a failed clear keeps the id in the published set for the next start"
    - "Unload publishes offline availability and deletes nothing; deletion exists only on explicit device delete and hub removal"
    - "Tests replay retained messages themselves (mocked client keeps none and skips a second retained message per topic and subscription)"

key-files:
  created:
    - tests/test_discovery.py
  modified:
    - custom_components/mqtt_actions/discovery.py
    - custom_components/mqtt_actions/mqtt_gateway.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/runner.py
    - custom_components/mqtt_actions/__init__.py
    - tests/test_manager.py
    - .ruff.toml

key-decisions:
  - "AvailabilityState StrEnum (online, offline, empty) replaces the online boolean so one publisher method covers online, offline and cleared"
  - "async_stop saves the Store first and publishes the offline availability last, so a slow or failing publish cannot cost the baseline"
  - "A reconfigure clears the device's action_failed issue before rebuilding the Scripts; invalid new actions raise the setup issue again (finding from 01-04)"
  - "MqttGateway.async_publish converts KeyError (MQTT entry exists but is not loaded) into HomeAssistantError so hub removal never blocks"
  - "The MQTT readiness check is the first statement of async_setup_entry, before the Manager is constructed"
  - "PLR0913 and PLR0917 are ignored under tests/ because pytest fixtures are arguments"

requirements-completed:
  - FND-05
  - STA-01
  - DSC-01
  - DSC-02

coverage:
  - id: D1
    description: "The discovered switch has UUID identity, state unknown until a state arrives, follows the instance availability topic, and a UI toggle publishes retained qos-1 ON or OFF to the shared state topic"
    requirement: DSC-01
    verification:
      - kind: integration
        ref: "tests/test_discovery.py#test_discovery_creates_switch_entity"
        status: pass
      - kind: integration
        ref: "tests/test_discovery.py#test_discovery_availability_toggles_entity"
        status: pass
      - kind: integration
        ref: "tests/test_discovery.py#test_discovery_toggle_publishes_retained_on_and_off"
        status: pass
    human_judgment: false
  - id: D2
    description: "The discovery prefix comes from the MQTT entry data merged with options, and disabled MQTT discovery is warned about and shown as a non-fixable Repairs issue"
    requirement: DSC-01
    verification:
      - kind: integration
        ref: "tests/test_discovery.py#test_discovery_prefix_options_win_over_data"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_discovery_disabled_creates_issue"
        status: pass
    human_judgment: false
  - id: D3
    description: "Unload and shutdown never publish an empty payload; discovery is removed only on explicit delete or hub removal"
    requirement: DSC-02
    verification:
      - kind: integration
        ref: "tests/test_manager.py#test_unload_publishes_offline_and_never_clears_discovery"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_unload_then_setup_republishes_without_clearing"
        status: pass
    human_judgment: false
  - id: D4
    description: "Explicit delete clears discovery, then unsubscribes, then clears the retained state; a device deleted while the entry was not loaded is cleaned at the next start; hub removal clears every owned topic and survives an unavailable MQTT"
    requirement: DSC-02
    verification:
      - kind: integration
        ref: "tests/test_manager.py#test_delete_device_clears_discovery_then_state"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_orphan_discovery_is_cleared_at_start"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_remove_entry_clears_all_owned_topics"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_remove_entry_survives_mqtt_not_loaded"
        status: pass
    human_judgment: false
  - id: D5
    description: "Setup without MQTT retries, a reconnect republishes availability and discovery, a reload keeps exactly one subscription per device"
    requirement: FND-05
    verification:
      - kind: integration
        ref: "tests/test_manager.py#test_setup_retry_without_mqtt"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_reconnect_republishes_availability_and_discovery"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_reload_keeps_single_subscription"
        status: pass
    human_judgment: false
  - id: D6
    description: "Changing a device rebuilds its Scripts, keeps its subscription and baseline, republishes discovery and clears or re-raises the stale setup issue"
    requirement: STA-01
    verification:
      - kind: integration
        ref: "tests/test_manager.py#test_reconcile_change_rebuilds_scripts_keeps_baseline"
        status: pass
      - kind: integration
        ref: "tests/test_manager.py#test_reconcile_change_clears_or_reraises_setup_issue"
        status: pass
    human_judgment: false
  - id: D7
    description: "Deleting a device in the real frontend against a real retaining broker removes the entity and its registry entry without a ghost, and a reconnect after a real broker outage restores availability"
    requirement: DSC-02
    verification: []
    human_judgment: true
    rationale: "The PHACC mocked client keeps no retained messages and skips a second retained message per topic, so the broker-side half of delete and reconnect is only simulated; it needs a look on a real host during UAT"

duration: about 60min
completed: 2026-09-29
status: complete
---

# Phase 1 Plan 05: Discovery Contract and Lifecycle Summary

**The discovered switch is pinned against real core MQTT discovery (UUID identity, availability, retained toggle, options-over-data prefix), and the whole lifecycle is covered: change rebuilds in place, delete clears discovery then subscription then state, deletions made while offline are cleaned at the next start, hub removal clears every owned topic, reconnects republish, and unload only ever publishes offline.**

## Performance

- **Duration:** about 60 min (start 2026-09-29T07:35Z, code done 08:27Z)
- **Tasks:** 3 (all TDD, RED commit before each GREEN commit)
- **Files created:** 1, modified: 7
- **Commits:** 6 (measured from `plan_head_before`)
- **Suite:** 167 passed (126 before, 41 new: 19 in `tests/test_discovery.py`, 22 in `tests/test_manager.py`)

## Accomplishments

- **Task 1, discovery contract:** `discovery.py` gained `AvailabilityState`, `async_clear_device` and `async_clear_state` (empty retained qos-1 payloads), and `async_publish_availability(instance_id, state)` now covers online, offline and cleared. `mqtt_gateway.py` merges the MQTT entry `data | options` in one place for `discovery_prefix()` and the new `discovery_enabled()`. `tests/test_discovery.py` runs the published payload through real core MQTT discovery: unique_id equals the device UUID, state is unknown, the device registry entry carries the name, offline availability makes the entity unavailable, a lower-case inbound `on` turns it on, `switch.turn_on` and `turn_off` publish `("ON", 1, True)` and `("OFF", 1, True)` to the shared topic, and the payload sw_version equals the manifest version. The builder stays pure and JSON is built only from a dict.
- **Task 2, reconcile, delete, orphans, hub removal:** `async_reconcile` diffs subentries against running devices under one lock: remove, change (only when a JSON fingerprint of title and data differs), add. A change clears the device's Repairs issue, rebuilds both Scripts through the runner, retires the old Scripts afterwards (`ActionRunner.async_retire_scripts`), keeps the subscription and baseline, updates name and `run_on_startup`, and republishes discovery. Delete follows D-16 and a failed clear keeps the id in the published set. `_async_orphan_cleanup` runs before the first subscription. `async_remove_entry` calls module-level `async_remove_all_devices`, which builds a fresh gateway and Store, clears discovery and state for the union of published ids and current subentries, clears the availability topic, removes the Store file and deletes the action-failed and discovery-disabled issues; its docstring and the `__init__` docstring name the Phase 3 redesign.
- **Task 3, readiness, reconnect, unload:** the readiness check is now the first statement of setup. `Manager.async_start` registers the connection-status handler with `entry.async_on_unload`, checks discovery, runs orphan cleanup, reconciles, and publishes availability online at the end. On a connection True the handler starts a background task that republishes every device's discovery and the online availability under the manager lock. `async_stop` saves the Store, unsubscribes, unloads the Scripts and publishes a retained offline availability, and never publishes an empty payload. With MQTT discovery disabled the setup logs a warning and raises the non-fixable warning issue `mqtt_discovery_disabled`; otherwise it deletes it. The module docstring records the missing Last Will limitation (AVL-01).

## Task Commits

1. **Task 1 RED:** `21bfcba` test(01-05): add discovery contract tests
2. **Task 1 GREEN:** `982b6f0` feat(01-05): finish the discovery contract
3. **Task 2 RED:** `e79298a` test(01-05): add failing lifecycle tests
4. **Task 2 GREEN:** `7c8835f` feat(01-05): reconcile changes and removals, orphan and hub cleanup
5. **Task 3 RED:** `19a0581` test(01-05): add failing startup and unload tests
6. **Task 3 GREEN:** `35512bb` feat(01-05): startup readiness, reconnect republish and safe unload

## Verification Results

- `uv run pytest -q`: 167 passed
- `uv run pytest tests/test_discovery.py -k toggle -q`: 2 passed
- `uv run pytest tests/test_manager.py -k "unload or delete or orphan or remove" -q`: 13 passed
- `uv run pytest tests/test_manager.py -q`: 48 passed
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 24 files already formatted
- hassfest (podman, same image as `docker run ghcr.io/home-assistant/hassfest`): `Integrations: 1`, `Invalid integrations: 0`
- The `test(01-05)` commit precedes its `feat(01-05)` commit for all three tasks
- The unload test inspects every recorded publish and finds no empty payload on any topic; the delete-order test asserts the relative order of discovery clear, unsubscribe and state clear
- The `KeyError` wrapper in the gateway was proven necessary: with the wrapper disabled, `test_remove_entry_survives_mqtt_not_loaded` fails with `KeyError: 'mqtt'`

## TDD Gate Compliance

All three tasks have a `test(01-05)` commit before their `feat(01-05)` commit. No refactor commits. RED state: Task 1, 6 of 19 tests failed on behavior (missing `async_clear_device`, `async_clear_state`, `discovery_enabled`, `AvailabilityState`); the 13 characterisation tests passed at once as the plan expects. Task 2, 10 of 14 new tests failed on behavior (no change, remove, orphan or hub cleanup); adding a device at runtime, leaving an unchanged device alone, and the own-subscription guard already passed. Task 3, 6 of 12 new tests failed on behavior (no reconnect handler, no offline on unload, no discovery-disabled issue); setup retry, online availability, reload and single subscription already passed because the tracer and 01-04 had them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff PLR0913 and PLR0917 on fixture-heavy tests**
- **Found during:** Task 2 RED
- **Issue:** Tests that request six pytest fixtures exceed the five-argument limit.
- **Fix:** Ignore both rules under `tests/**` in `.ruff.toml`, next to the existing per-file ignores (fixtures are arguments by design).
- **Files modified:** `.ruff.toml`
- **Commit:** `e79298a`

**2. [Rule 1 - Bug] Gateway publish raised KeyError instead of HomeAssistantError**
- **Found during:** Task 2 GREEN (test `test_remove_entry_survives_mqtt_not_loaded`)
- **Issue:** With an MQTT config entry that exists but is not loaded (broker down at start), core `mqtt.async_publish` passes its enabled check and then raises `KeyError` on `hass.data["mqtt"]`. Hub removal would have failed exactly in the scenario T-01-14 names.
- **Fix:** `MqttGateway.async_publish` converts the `KeyError` into `HomeAssistantError`.
- **Files modified:** `custom_components/mqtt_actions/mqtt_gateway.py`
- **Commit:** `7c8835f`

### Notes

**3. [Note] Test harness limits shape a few assertions.** The mocked MQTT client keeps no retained messages and delivers only the first retained message per topic and subscription (`_retained_topics`). Tests therefore replay the retained `online` availability themselves after setup (test_discovery), and deliver the cleared discovery topic once with `retain=False`, as a real broker forwards it live, before asserting that the entity is gone. The publish assertions themselves are on the recorded calls.

**4. [Note] sw_version was already taken from the manifest.** Plan 01-02 wired `async_get_integration` into the publisher, so the "sw_version from the manifest" behavior passed at RED; it stays as a characterisation test.

**5. [Note] `async_publish_availability` signature changed** to `(instance_id, state: AvailabilityState)` for the online, offline and cleared cases; the only call sites were in the manager.

**6. [Note] Stop order differs from the listed order.** The plan lists offline, unsubscribe, unload, save. The implementation saves first and publishes offline last, so a publish that waits for a broker acknowledgement cannot cost the persisted baseline. The observable contract (retained offline, no deletes, Scripts unloaded, Store saved) is unchanged.

**7. [Note] Readiness check moved ahead of the Manager.** `async_setup_entry` builds a bare `MqttGateway` for the readiness check and only then constructs the Manager, so nothing else runs before it.

**8. [Note] Extra tests beyond the plan list:** `test_reconcile_unchanged_device_is_left_alone`, `test_reconcile_change_clears_or_reraises_setup_issue`, `test_delete_device_keeps_id_for_orphan_cleanup_when_mqtt_fails`, `test_remove_entry_survives_mqtt_not_loaded`, `test_unload_survives_unavailable_mqtt`, `test_discovery_enabled_deletes_stale_issue`, prefix fallback and clear-state tests.

**9. [Note] hassfest invocation.** Run through podman with the literal worktree path mounted at `/ws`, as in plans 01-02 to 01-04 (the sandbox guard refuses the `docker run -v "$PWD"` form).

**10. [Note] REQUIREMENTS.md not touched.** FND-05, STA-01, DSC-01 and DSC-02 are copied into `requirements-completed`, but the orchestrator owns shared tracking for the wave (STA-01 and DSC-01 are also declared by earlier plans).

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 3), 8 notes. **Impact:** none on scope.

## Findings for Later Plans (observations, not fixes here)

- **Offline publish can wait on a dead broker:** `async_stop` awaits the offline publish, and core waits for the publish acknowledgement. With the MQTT client disconnected an unload can take up to core's acknowledgement timeout before it proceeds; the failure is caught and logged, and everything else (save, unsubscribe, unload) has already happened.
- **A reconfigure stops an in-flight run of the old Script** (`Script.async_unload` on retire). Queued runs of a retired Script are skipped. Acceptable for Phase 1; Phase 2's run-mode work (DEV-06) may want to let a running Script finish.
- **Hub removal is destructive on a shared broker (D-15):** it clears every id this instance published. With several instances on one broker, Phase 3 must replace it with a confirmed, multi-instance-aware delete (already stated in the docstrings).
- **`mqtt_discovery_disabled` stays after an unload** and is recomputed at the next start; only hub removal deletes it.
- **Issue text and German wording** for `mqtt_discovery_disabled` and the reconfigure-clears-issue behavior read in the real frontend are not asserted by any test (see coverage D7 for the broker-side half).
- **Broker tests in CI (from 01-04):** still need `mosquitto` on PATH in the plan 01-06 CI job.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-13 (retained topics tamperable, accepted; reload and reconnect republish idempotently) and T-01-15 (stale retained online after a crash, accepted; documented in the manager docstring) hold as planned. T-01-14 is mitigated as planned: cleanup runs only on explicit hub removal, is scoped to the persisted published set plus current subentries, and every MQTT failure, including the not-loaded `KeyError` case, is logged and never blocks removal.

## Next Phase Readiness

Plan 01-06 (repo, CI, README) can rely on the complete lifecycle. README material to carry over: the stale-online limitation after a crash, that hub removal clears the instance's broker topics, and that device_id targets do not sync across instances. No blockers.

## Self-Check: PASSED

- Files exist: `tests/test_discovery.py`, `custom_components/mqtt_actions/discovery.py`, `mqtt_gateway.py`, `manager.py`, `runner.py`, `__init__.py`, `tests/test_manager.py`, `.ruff.toml` (verified before the SUMMARY commit)
- Commits `21bfcba`, `982b6f0`, `e79298a`, `7c8835f`, `19a0581`, `35512bb` exist on branch `worktree-agent-a7b6591639ea208d1`
- Acceptance criteria re-run: full pytest (167 passed), the `-k toggle` and `-k "unload or delete or orphan or remove"` selections, ruff check and format, hassfest all pass
