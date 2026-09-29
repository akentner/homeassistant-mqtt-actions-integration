# Phase 2: Select Devices and Reliable Execution - Context

**Gathered:** 2026-09-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Select devices whose options each run their own actions, plus predictable execution for all devices (Switch and Select): a per-device run mode (serial queue or restart), a test button, and a per-device circuit breaker against self-triggering loops. Unknown Select payloads are ignored and logged. Central config, owner/follower sync and the trust gate belong to Phase 3; re-trigger service, roster and recovery tooling belong to Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Option editor (DEV-03, DEV-04)
- **D-01:** The Select subentry flow uses a menu with a loop: after the device settings, a menu offers add option / edit option / remove option / done. Each option has its own step with StateValue, StateFriendlyName and an actions field (ActionSelector).
- **D-02:** Options can be added and removed after creation. Removal asks for confirmation. A removed StateValue is treated as unknown afterwards (ignored and logged, STA-07). If the current selection is removed, the entity state stays until the next valid payload arrives.
- **D-03:** StateValue is locked after creation; only StateFriendlyName and actions are editable (DEV-04).
- **D-04:** Validation: at least 2 options; StateValue non-empty, without leading/trailing whitespace and unique case-insensitively; StateFriendlyName required; actions per option optional (as for the Switch).
- **D-05:** Option order is creation order (also the order of the discovery `options` list). No reordering in Phase 2.

### Payload mapping and discovery
- **D-06:** An inbound payload is trimmed and matched case-insensitively against the StateValues. The published payload is the StateValue exactly as created. — **Reversibility:** costly — StateValue casing becomes part of the topic payload contract that external publishers and Phase 3 config documents depend on.
- **D-07:** Discovery `options` are the StateFriendlyNames; `value_template` and `command_template` map between StateValue (broker) and friendly name (HA UI). Renaming a friendly name only changes the retained discovery message, never the topic or payload. — **Reversibility:** costly — the Select wire mapping is a published contract from the first release containing Select.
- **D-08:** The "run on startup" flag applies to Select with the same semantics as the Switch (D-05/D-06/D-14 of Phase 1): retained state sets only the baseline; with the flag on, the retained value counts as a change once after start or reload and runs that option's actions.
- **D-09:** An unknown payload keeps the entity state, is ignored and logged (device name plus truncated payload, as for the Switch, `MAX_LOGGED_PAYLOAD_LENGTH`). No Repairs issue. An unknown retained payload does not set a baseline.

### Run mode and test button (DEV-06, DEV-07)
- **D-10:** Run mode is configured per device for both Switch and Select, default `serial`. Existing Phase 1 Switch devices get `serial` without a migration step (missing key = default).
- **D-11:** `restart` cancels the running script, starts the new run and discards queued runs (HA script mode `restart` semantics). A cancelled run is not an error and creates no Repairs issue.
- **D-12:** The `serial` queue is bounded by a fixed limit (start value 10, constant in `const.py`, not user-configurable). Runs beyond the limit are dropped and logged.
- **D-13:** The test button is a Discovery `button` entity per trigger: the Switch gets "Test ON" and "Test OFF", the Select gets one button per option. It runs the actions locally without publishing, without changing the entity state and without touching the baseline. Failures use the normal Repairs path; test runs do not count toward the circuit breaker. Buttons follow the same add/remove/rename lifecycle as options.

### Circuit breaker (STA-06)
- **D-14:** The breaker is configurable per device: maximum runs and window in seconds. Defaults 5 runs in 10 seconds, both fields in the Switch and Select flows, defaults as constants in `const.py`. Only runs triggered by real state changes count (not the test button). Sliding window per device.
- **D-15:** After a trip the device is paused: incoming changes only update the entity state and baseline, no actions run. Release is a deliberate user action: reconfigure the device or reload the entry.
- **D-16:** The user is informed by a dedicated Repairs issue per device (own key, separate from `action_failed_`) that explains the cause and the way to release, plus a log warning. The issue disappears on release.
- **D-17:** The tripped state is persistent in the store and survives an HA restart; the counting window is volatile and is not stored. — **Reversibility:** costly — adds a store key that later migrations must carry.

### Claude's Discretion
- Exact default and limit values beyond those named, translation keys and Repairs wording, step ids and menu labels of the flow.
- How the per-device runner implements restart vs. serial (Script mode versus lock plus cancellation) and how the breaker window is counted, as long as D-10 to D-16 hold.
- Entity naming and `unique_id` scheme for the test buttons (must be UUID-based and stable across renames, like D-03 of Phase 1).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` - core value, constraints, key decisions
- `.planning/REQUIREMENTS.md` - DEV-03, DEV-04, DEV-06, DEV-07, STA-06, STA-07
- `.planning/ROADMAP.md` - Phase 2 goal and success criteria
- `.planning/phases/01-walking-skeleton-installable-switch/01-CONTEXT.md` - Phase 1 decisions carried forward (topics, payloads, baseline, failure surfacing)

### Research
- `.planning/research/SUMMARY.md` - roadmap-level conclusions
- `.planning/research/ARCHITECTURE.md` - components, topics, subentry device model
- `.planning/research/PITFALLS.md` - retained-message semantics, loop risks
- `.planning/research/FEATURES.md` - feature expectations and anti-features

### Project instructions
- `.claude/CLAUDE.md` - stack rules and "Do not use" list

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `custom_components/mqtt_actions/runner.py` (`ActionRunner`): per-device `asyncio.Lock` FIFO, `Script` built with `script_mode="single"`, Repairs issue per device. Needs a run-mode dimension, a queue bound and cancellation for restart.
- `custom_components/mqtt_actions/discovery.py` (`build_switch_discovery`, `DiscoveryPublisher`): device-based discovery with `components`; extend with `select` and `button` components.
- `custom_components/mqtt_actions/config_flow.py` (`SwitchSubentryFlow`, `_async_check_actions`, `_prefill`): action validation and device_id warning reused per option.
- `custom_components/mqtt_actions/state.py`, `manager.py`: decision function and baseline/store handling for the Switch, to be generalized for option payloads.
- `custom_components/mqtt_actions/const.py`: subentry keys and trigger names; add `SUBENTRY_SELECT`, option/run-mode/breaker keys.

### Established Patterns
- Subentry per device with UUID `device_id` doubling as `unique_id` and topic segment.
- Only the state subscription triggers actions; the command topic equals the state topic.
- Failures: log plus one Repairs issue per device; translations in `translations/en.json` and `de.json` with a parity test.
- TDD mode is on: tests come with each task.

### Integration Points
- `SwitchSubentryFlow` registration in `async_get_supported_subentry_types`: add the Select flow.
- Discovery topic cleanup on device delete (D-16 of Phase 1) must also cover the button components.

</code_context>

<specifics>
## Specific Ideas

The user chose the recommended option everywhere except the circuit breaker threshold, which is configurable per device (max runs and window) instead of fixed.

</specifics>

<deferred>
## Deferred Ideas

- Reordering options in the flow (moves to a later phase if requested).
- User-configurable serial queue limit.
- Automatic circuit breaker release after a cooldown.

</deferred>

---

*Phase: 2-Select Devices and Reliable Execution*
*Context gathered: 2026-09-29*
