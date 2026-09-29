# Phase 2: Select Devices and Reliable Execution - Research

**Researched:** 2026-09-29
**Domain:** Home Assistant custom integration (Python 3.14, HA 2026.9.4): MQTT device-based discovery (select + button), ConfigSubentryFlow with an option-editor menu loop, `helpers.script.Script` run modes, per-device circuit breaker with Repairs
**Confidence:** HIGH (every load-bearing behavior was read in the HA 2026.9.4 source in `.venv` or reproduced in a real-HA spike this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Option editor (DEV-03, DEV-04)**
- **D-01:** The Select subentry flow uses a menu with a loop: after the device settings, a menu offers add option / edit option / remove option / done. Each option has its own step with StateValue, StateFriendlyName and an actions field (ActionSelector).
- **D-02:** Options can be added and removed after creation. Removal asks for confirmation. A removed StateValue is treated as unknown afterwards (ignored and logged, STA-07). If the current selection is removed, the entity state stays until the next valid payload arrives.
- **D-03:** StateValue is locked after creation; only StateFriendlyName and actions are editable (DEV-04).
- **D-04:** Validation: at least 2 options; StateValue non-empty, without leading/trailing whitespace and unique case-insensitively; StateFriendlyName required; actions per option optional (as for the Switch).
- **D-05:** Option order is creation order (also the order of the discovery `options` list). No reordering in Phase 2.

**Payload mapping and discovery**
- **D-06:** An inbound payload is trimmed and matched case-insensitively against the StateValues. The published payload is the StateValue exactly as created. — **Reversibility:** costly — StateValue casing becomes part of the topic payload contract that external publishers and Phase 3 config documents depend on.
- **D-07:** Discovery `options` are the StateFriendlyNames; `value_template` and `command_template` map between StateValue (broker) and friendly name (HA UI). Renaming a friendly name only changes the retained discovery message, never the topic or payload. — **Reversibility:** costly — the Select wire mapping is a published contract from the first release containing Select.
- **D-08:** The "run on startup" flag applies to Select with the same semantics as the Switch (D-05/D-06/D-14 of Phase 1): retained state sets only the baseline; with the flag on, the retained value counts as a change once after start or reload and runs that option's actions.
- **D-09:** An unknown payload keeps the entity state, is ignored and logged (device name plus truncated payload, as for the Switch, `MAX_LOGGED_PAYLOAD_LENGTH`). No Repairs issue. An unknown retained payload does not set a baseline.

**Run mode and test button (DEV-06, DEV-07)**
- **D-10:** Run mode is configured per device for both Switch and Select, default `serial`. Existing Phase 1 Switch devices get `serial` without a migration step (missing key = default).
- **D-11:** `restart` cancels the running script, starts the new run and discards queued runs (HA script mode `restart` semantics). A cancelled run is not an error and creates no Repairs issue.
- **D-12:** The `serial` queue is bounded by a fixed limit (start value 10, constant in `const.py`, not user-configurable). Runs beyond the limit are dropped and logged.
- **D-13:** The test button is a Discovery `button` entity per trigger: the Switch gets "Test ON" and "Test OFF", the Select gets one button per option. It runs the actions locally without publishing, without changing the entity state and without touching the baseline. Failures use the normal Repairs path; test runs do not count toward the circuit breaker. Buttons follow the same add/remove/rename lifecycle as options.

**Circuit breaker (STA-06)**
- **D-14:** The breaker is configurable per device: maximum runs and window in seconds. Defaults 5 runs in 10 seconds, both fields in the Switch and Select flows, defaults as constants in `const.py`. Only runs triggered by real state changes count (not the test button). Sliding window per device.
- **D-15:** After a trip the device is paused: incoming changes only update the entity state and baseline, no actions run. Release is a deliberate user action: reconfigure the device or reload the entry.
- **D-16:** The user is informed by a dedicated Repairs issue per device (own key, separate from `action_failed_`) that explains the cause and the way to release, plus a log warning. The issue disappears on release.
- **D-17:** The tripped state is persistent in the store and survives an HA restart; the counting window is volatile and is not stored. — **Reversibility:** costly — adds a store key that later migrations must carry.

### Claude's Discretion
- Exact default and limit values beyond those named, translation keys and Repairs wording, step ids and menu labels of the flow.
- How the per-device runner implements restart vs. serial (Script mode versus lock plus cancellation) and how the breaker window is counted, as long as D-10 to D-16 hold.
- Entity naming and `unique_id` scheme for the test buttons (must be UUID-based and stable across renames, like D-03 of Phase 1).

### Deferred Ideas (OUT OF SCOPE)
- Reordering options in the flow (moves to a later phase if requested).
- User-configurable serial queue limit.
- Automatic circuit breaker release after a cooldown.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEV-03 | User can create a Select device with multiple options, each with StateValue, StateFriendlyName and actions | Subentry data shape, menu-loop flow with in-memory draft (Pattern 3), Select discovery + templates verified end to end (Pattern 2), Manager generalization via a pure `DeviceSpec` (Pattern 1) |
| DEV-04 | User can edit StateFriendlyName and actions of an option; StateValue is immutable after creation | `edit_option` step schema without `state_value`; friendly-name rename only changes retained discovery; HA select state goes `unknown` after renaming the current option (Pitfall 3, Open Question 1) |
| DEV-06 | User can choose per device how actions run on rapid state changes (serial queue by default, or restart) | One `Script` per device with `choose` dispatch; `queued`+`max_runs=10` and `restart` semantics reproduced in a spike (Pattern 4) |
| DEV-07 | User can run a device's actions locally via a test button without changing its state | Discovery `button` components + one non-retained test topic per device (Pattern 5); tombstones for removal (Pitfall 4) |
| STA-06 | A per-device circuit breaker stops action loops caused by actions that toggle their own device | Pure sliding-window `CircuitBreaker`, trip/pause/stop flow, persisted tripped map keyed by config hash, Repairs issue, release paths (Pattern 6) |
| STA-07 | A Select payload that matches no configured StateValue is ignored and logged | `decide()` generalized with an accepted-values map; value_template returns `''` for unknown payloads so HA keeps state without an error log (verified, Pattern 2) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Treated with the authority of locked decisions. Source: `.claude/CLAUDE.md` (read this session), plus `/home/akentner/CLAUDE.md` and `/home/akentner/Projects/CLAUDE.md`.

- Python 3.14 (`>=3.14.2`), HA floor 2026.9.0, schema validation via `import probatio` (never `voluptuous`), no new runtime dependencies (`manifest.json` has no `requirements`).
- Use `entry.runtime_data` (typed `ConfigEntry[Manager]`), never `hass.data[DOMAIN]`; register MQTT unsubscribes so they are released on unload.
- Use the built-in `mqtt` integration only (no `paho-mqtt`/`aiomqtt` in the integration); publish and subscribe only through `mqtt_gateway.py` (the single import seam).
- Actions execute through `homeassistant.helpers.script.Script`; validate action sequences with `cv.SCRIPT_SCHEMA` + `script.async_validate_actions_config` on user input (and on broker input in Phase 3). Never execute unvalidated sequences.
- Entities come from MQTT Discovery, device-based (`<prefix>/device/<id>/config`), discovery prefix read from the MQTT integration, never hard-coded.
- Translations in `translations/en.json` + `translations/de.json` only (no `strings.json`); both must stay in parity (existing `tests/test_translations.py`).
- Config Flow only, no YAML, no `async_setup_platform`; services (none in this phase) go in `async_setup`.
- Do not use `device_id` targets in shipped examples/defaults; prefer `entity_id`, areas, labels.
- Ruff (line length 120, `select = ["ALL"]` with short ignore list), `uv` for everything, no `setup.py`/Poetry, do not add `homeassistant`/`pytest*`/`voluptuous` to dev deps (PHACC pins them).
- Code, comments and commits in English; UI strings in EN and DE.
- GSD workflow enforcement: file changes go through a GSD command; TDD mode is on (`workflow.tdd_mode: true`), so tests come with each task.

## Summary

Phase 1 already provides almost everything Phase 2 needs to extend: subentry-per-device with UUID `device_id`, a pure `decide()`/`StateTracker`, `ActionRunner` with Repairs, a `DiscoveryPublisher` with device-based payloads, a `Manager` reconcile loop and a 188-test suite that runs in 9 s (`uv run pytest tests -x -q`, verified). The work is a **generalization** (Switch becomes one of two device kinds described by a pure `DeviceSpec`), three new runtime concerns (run mode, test buttons, circuit breaker) and one new UI surface (the Select option editor).

The riskiest items were spiked against the real HA MQTT discovery code in this session (spike files live in the session scratchpad, they must be ported into permanent tests): the generated `value_template`/`command_template` round-trips hostile strings (quotes, backslashes, `{{ 1+1 }}`, `{% if x %}`, `{# c #}`, `}} {{`, emoji, umlauts, tab) when the strings are emitted with `json_dumps` (JSON string escapes are valid Jinja string literals); an unknown payload mapped to `''` is silently ignored by HA's select (no state change, no warning/error log); **omitting** a component from a device payload does NOT remove its entity, only an explicit tombstone `{"platform": "button"}` does; native `Script` `queued` (max 10 runs, FIFO, overflow dropped with a warning) and `restart` behave as needed when ONE Script per device dispatches with `choose`. Three findings contradict or refine CONTEXT wording and are surfaced below: (1) HA's select entity shows `unknown` after the currently selected option is renamed or removed, so D-02's "the entity state stays" cannot literally hold; (2) "reconfigure the device" only releases the breaker reliably if it is detected from a config change, not from a flow hook; (3) a Discovery button always publishes to the broker, so "runs locally" is only true on a single instance until Phase 3 decides how test presses fan out.

**Primary recommendation:** Add a pure `model.py` (`DeviceSpec`/`TriggerSpec` from a subentry), generalize `state.decide()` with an accepted-values map, replace the per-trigger Scripts with ONE `Script` per device (mode `queued`/`max_runs=10` for serial, `restart` otherwise) that dispatches on a hashed `trigger_key` via `choose`, add a pure `CircuitBreaker` with a persisted tripped map keyed by config hash, and build the Select flow as a menu loop over an in-memory deep-copied draft committed once on "done".

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Select/option editing UI (menu loop, forms, ActionSelector) | HA config-flow layer (`config_flow.py`, subentry flow) | Frontend (renders steps) | Flow state lives in the flow instance; nothing is persisted until "done" |
| Option validation (unique StateValue, min 2, friendly-name rules) | Pure module (`model.py`) called by flow | Manager (defensive re-check at load) | Shared by the flow now and by Phase 3 importers; no HA imports |
| StateValue <-> friendly-name mapping (wire contract) | Pure module (template builders) + HA MQTT discovery consumer (renders templates) | Broker (carries StateValue payloads) | HA core renders the templates; we only generate strings |
| Payload normalization and edge detection | Pure `state.py` (`decide`, `StateTracker`) | Manager (calls it) | Already pure and table-tested; generalize, do not fork |
| Run mode (serial queue / restart) and queue bound | HA `Script` engine (modes) | `ActionRunner` (builds Script, enqueues) | Native semantics are tested by core; avoids custom cancellation races |
| Test button execution | Manager (test-topic subscription) -> `ActionRunner` | HA MQTT (button entity publishes the press) | Button entity only publishes; the integration owns execution |
| Circuit breaker counting and pause | Pure `breaker.py` + Manager | Store (tripped map), Repairs (user notice) | Counting is time logic (pure, clock-injected); pause lives where edges are dispatched |
| Tripped-state persistence | `homeassistant.helpers.storage.Store` (existing store, additive key) | — | D-17; survives restart, window stays in memory |
| Failure and trip surfacing | Repairs (`issue_registry`) + log | Translations (en/de) | Existing pattern (D-08/D-09); breaker gets its own issue key |
| Discovery of select + buttons, tombstones, cleanup | `DiscoveryPublisher` (device-based payload) | HA MQTT discovery (creates/removes entities) | One retained device topic per device; empty payload cleans all components |

## Standard Stack

### Core
No new libraries. Everything below is already in use in Phase 1 or ships with HA 2026.9.4.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Home Assistant core | 2026.9.4 (`.venv`, verified in `homeassistant/const.py`: `MAJOR_VERSION: Final = 2026`, `MINOR_VERSION: Final = 9`, `PATCH_VERSION: Final = "4"`) | Host, MQTT, Script, Store, Repairs, subentry flows | Project constraint |
| `helpers.script.Script` | core | Run modes `queued`/`restart`, `choose` dispatch, native queue bound | Same engine as automations; reproduced in spike |
| `helpers.selector` (`ActionSelector`, `SelectSelector`, `NumberSelector`, `TextSelector`, `BooleanSelector`) | core | Option and settings forms | `ActionSelector` already proven in Phase 1 UAT |
| `helpers.storage.Store` | core | Persist tripped map next to `last_acted`/`published` | Existing `STORE_KEY`; additive key needs no version bump |
| `helpers.issue_registry` | core | Breaker Repairs issue | Existing pattern |
| `probatio` | provided by core (0.11.4 in 2026.9.4 per CLAUDE.md) | Schemas | Project constraint |
| pytest-homeassistant-custom-component | 0.13.367 (pinned in `pyproject.toml`, read this session) | Test harness | Existing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `hashlib` (sha256), `collections.deque`, `time.monotonic` | stdlib | Stable component keys, sliding window, config hash for tripped map | Pure modules; inject the clock in tests |
| stdlib `copy.deepcopy` | stdlib | Flow draft isolation from `subentry.data` | Every flow that edits existing data |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| One combined `Script` per device with `choose` | Per-trigger Scripts + own lock/cancel (Phase 1 shape) | Cross-trigger `restart` (option A running, option B arrives) needs cancelling sibling Scripts by hand and re-implementing HA's "add new run, then stop others" race handling. Combined Script gets it natively |
| Flow-hook release of the breaker | Release detected from config-hash change + unload | The hook fails when the entry is not loaded and when a reconfigure is submitted unchanged |
| Per-option random UUID stored in data | Key derived from lowercased StateValue (sha256) | StateValue is immutable and unique case-insensitively, so a derived key is stable and adds nothing to the future central-config contract |

**Installation:** none (no new packages).

**Version verification:** No package is added. Versions above were read from `homeassistant/const.py` and `pyproject.toml` in this session. Test suite baseline: `188 passed in 9.24s` (`uv run pytest tests -x -q`).

## Package Legitimacy Audit

No external packages are installed in this phase; the audit is not applicable.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                       HA UI (select entity, test buttons)             HA UI (Devices > subentry dialog)
                              |  select_option / press                        |
                              v                                               v
                    [HA MQTT select/button entities]                [SelectSubentryFlow: menu loop over draft]
                       |  publish StateValue (retained, qos1)                 | done -> create/update subentry
                       |  publish test payload (NOT retained)                 v
                       v                                              [Config entry subentries]
   external publisher -> [Broker] <---- retained device discovery ---------+   | update listener
        (mosquitto_pub)     |   ^                                           |   v
                            |   +---- discovery (select + buttons + tombstones) <-- [DiscoveryPublisher] <-- [Manager.reconcile]
                            |                                                                 |   builds DeviceSpec per subentry
        state topic  <base>/v1/devices/<id>/state       test topic <base>/v1/devices/<id>/test        |
                            |                                   |                                     |
                            v                                   v                                     |
                 [Manager._on_message]                [Manager._on_test_message]                      |
                   normalize via accepted map            ignore retained; map payload -> trigger      |
                   StateTracker.handle (baseline)                |                                    |
                     unknown -> log, stop (D-09)                 |                                    |
                     retained -> baseline only (STA-04)          |                                    |
                     live edge:                                  |                                    |
                       breaker tripped? -> stop (baseline only)  |                                    |
                       breaker.record() over max? -> TRIP        |                                    |
                         (pause, Repairs issue, warning,         |                                    |
                          stop runs, persist tripped hash)       |                                    |
                       else enqueue ------------------------------+---> [ActionRunner.enqueue]        |
                                                                        one Script per device <-------+
                                                                        mode queued(max 10) | restart
                                                                        choose on trigger_key
                                                                        -> run actions locally
                                                                        failure -> log + Repairs action_failed_<id>
                                                                        (result None = dropped, CancelledError = superseded)
```

### Recommended Project Structure
```
custom_components/mqtt_actions/
├── const.py          # + SUBENTRY_SELECT, option/run-mode/breaker keys, defaults, queue limit, STORE_TRIPPED, issue prefix
├── model.py          # NEW pure: TriggerSpec/DeviceSpec, spec_from_subentry, option validation, trigger_key, template builders
├── breaker.py        # NEW pure: CircuitBreaker (sliding window, injected clock)
├── state.py          # decide()/StateTracker generalized with an accepted-values map (Switch passes ON/OFF)
├── topics.py         # + test_topic(base, device_id)
├── discovery.py      # build_discovery(spec, ...) with select|switch + button components + tombstones
├── runner.py         # one Script per device; run mode; stop_runs; None/CancelledError handling
├── manager.py        # Device generalized; test subscription; breaker; tripped persistence; issue create/delete
├── config_flow.py    # SwitchSubentryFlow (+ run mode/breaker fields) + SelectSubentryFlow; shared helpers
└── translations/     # en.json + de.json: select flow, menu_options, selector.run_mode, issues.circuit_breaker_tripped
```

### Pattern 1: One pure `DeviceSpec` per subentry (extend, don't fork)
**What:** `spec_from_subentry(subentry)` returns `DeviceSpec(kind, device_id, name, run_on_startup, run_mode, breaker_max_runs, breaker_window, accepted: dict[str, str], triggers: dict[str, TriggerSpec])`. For a Switch: `accepted = {"on": "ON", "off": "OFF"}` and two triggers labelled `onChangeToOn`/`onChangeToOff` (existing `TRIGGER_ON`/`TRIGGER_OFF`); for a Select: one trigger per option in stored order. `TriggerSpec(value, key, label, friendly_name, actions)`. Manager, discovery, runner and tests consume the spec; only `spec_from_subentry` knows the storage layout. Missing keys use defaults (`.get`), which satisfies D-10 with no migration (`Manager` currently reads `subentry.data[CONF_RUN_ON_STARTUP]` with `[]`, new keys must use `.get`).
**When to use:** Always; it removes the `on_script`/`off_script` special case from `Device` and `_on_message`.
**Example:**
```python
# Source: derived from custom_components/mqtt_actions/manager.py (Device, _on_message) and const.py
SWITCH_ACCEPTED = {"on": PAYLOAD_ON, "off": PAYLOAD_OFF}

def trigger_key(value: str) -> str:
    """Stable, space-free component/trigger key derived from the immutable StateValue (case-insensitive)."""
    return hashlib.sha256(value.lower().encode()).hexdigest()[:12]
```
Component keys in the discovery payload must not contain spaces because core splits `discover_id` on `" "` when it regenerates cleanup payloads (`homeassistant/components/mqtt/discovery.py` `_generate_device_config`: `ids = discover_id.split(" ")`) [VERIFIED: discovery.py:261-263 read this session].

### Pattern 2: Select discovery with generated mapping templates
**What:** The `select` component publishes friendly names as `options`; `value_template` maps broker StateValue (trimmed, lowercased) to friendly name and returns `''` for anything unknown; `command_template` maps the chosen friendly name back to the exact StateValue. Strings are emitted with `homeassistant.helpers.json.json_dumps` (already imported in `discovery.py`), whose output is a valid Jinja string literal, including non-ASCII (orjson does not `\u`-escape; Jinja turns non-ASCII into `\U…` escapes and decodes them back).
**When to use:** Every Select discovery publish.
**Example:**
```python
# Source: reproduced against real HA MQTT discovery in the phase-2 spike (session scratchpad test_spike.py)
def _lit(value: str) -> str:
    return json_dumps(value)  # JSON escapes are a subset of Jinja string escapes

def build_value_template(options: Sequence[tuple[str, str]]) -> str:
    body = ", ".join(f"{_lit(value.lower())}: {_lit(friendly)}" for value, friendly in options)
    return "{{ {" + body + "}.get(value | trim | lower, '') }}"

def build_command_template(options: Sequence[tuple[str, str]]) -> str:
    body = ", ".join(f"{_lit(friendly)}: {_lit(value)}" for value, friendly in options)
    return "{{ {" + body + "}.get(value, value) }}"
```
Verified in the spike with real HA MQTT discovery (`mqtt_mock`): for every hostile option, a live payload `"  <STATEVALUE UPPERCASE>\n"` sets the entity to the friendly name, `select.select_option` publishes exactly the StateValue with `retain=True`, and button presses publish the raw StateValue. Empty, `nope`, `none` and `None` payloads left the state unchanged and produced no WARNING/ERROR log [VERIFIED: spike run this session]. Why `''` works: `MqttSelect._message_received` starts with `if not payload.strip():  # No output from template, ignore` and only logs at debug [VERIFIED: components/mqtt/select.py:117]. Python and Jinja must normalize identically: Jinja `trim` = `str.strip()`, `lower` = `str.lower()`; use `.strip().lower()` in Python (not `casefold()`).
Select component keys: `"platform": "select"`, `"unique_id": device_id`, `"name": None`, `state_topic == command_topic`, `retain: True`, `qos: 1` (same as the Switch component in `build_switch_discovery`).

### Pattern 3: Select subentry flow = menu loop over an in-memory draft
**What:** Flow instance holds `self._draft` (deep copy) with settings and `options`. Steps: `user`/`reconfigure` -> settings form (name, run_on_startup, run_mode, breaker_max_runs, breaker_window) -> `menu` (`async_show_menu`) offering `add_option`, `edit_option`, `remove_option`, `settings` and `done`. `edit_option`/`remove_option` first show a `SelectSelector` of the existing options (value = StateValue, label = friendly name), then the form or a confirm menu (`confirm_remove` / `keep`). `done` is only offered when the draft has at least 2 options (a menu cannot show errors). Commit exactly once: create flow -> `async_create_entry(title=name, unique_id=device_id, data=...)`; reconfigure -> `async_update_and_abort(entry, subentry, title=name, data=...)` (replace, not merge, and re-inject the immutable `device_id`, exactly like the Switch flow).
**When to use:** DEV-03/DEV-04.
**Notes (verified in core source):**
- `ConfigSubentryFlow.async_create_entry` raises `ValueError` unless `self.source == SOURCE_USER` (config_entries.py:3770-3771), so create and reconfigure need separate commit calls; both are reached from the same `done` step.
- `async_show_menu(*, step_id, menu_options, sort, description_placeholders)` has no `errors` parameter (data_entry_flow.py:878-902); validation errors live on form steps only.
- Core reference for a subentry flow that starts with a menu: `components/bayesian/config_flow.py` `ObservationSubentryFlowHandler` (`async_step_user` returns `async_show_menu`, lines 537-546) with `menu_options` translations under `config_subentries.<type>.step.<step>.menu_options` (`bayesian/strings.json`).
- `async_step_reconfigure` presence is what makes HA offer reconfigure (`hasattr(... "async_step_reconfigure")`, config_entries.py:635).
- Reuse `_async_check_actions` for each option step, generalized to take `(label, raw_actions)` pairs so `invalid_actions` names the option (`{field}` placeholder) and the `device_id` warn-then-confirm fingerprint is per step.
- `NumberSelector` returns `float` (`value: float = vol.Coerce(float)(data)`, helpers/selector.py:1469). Coerce with `int()` before storing `breaker_max_runs` and `breaker_window`, otherwise `5.0` lands in the config entry and in the store hash.
- Run mode selector: `SelectSelector(SelectSelectorConfig(options=["serial", "restart"], translation_key="run_mode", mode=SelectSelectorMode.DROPDOWN))` with `selector.run_mode.options.*` in both translation files.

**Validation the flow/model must add on top of D-04** (derived from HA behavior, see Pitfall 3):
- `StateFriendlyName` unique (compare `.strip().lower()`), stripped on save (HA strips the rendered template result: `render_with_context(...).strip()`, helpers/template/__init__.py:596-599, so a name with edge whitespace could never match `options`), and must not equal `none` case-insensitively (`if payload.lower() == "none": self._attr_current_option = None`, mqtt/select.py:124-126 makes the entity unknown).
- Reject non-printable characters in StateValue and friendly name (`str.isprintable()`); this also rejects lone surrogates that would make `json_dumps` raise. [ASSUMED: discretionary limit]

### Pattern 4: One `Script` per device, native modes, `choose` dispatch
**What:** For each device build ONE `Script(hass, sequence, device_name, DOMAIN, script_mode=..., max_runs=SERIAL_QUEUE_LIMIT, max_exceeded="WARNING", logger=LOGGER)` where `serial` -> `script_mode="queued"` and `restart` -> `script_mode="restart"`. The sequence is a single `choose` with one branch per trigger that has actions; conditions compare a run variable against a hashed key so no user text enters a template: `{"conditions": [{"condition": "template", "value_template": "{{ trigger_key == '<hex>' }}"}], "sequence": raw_actions}`. Run variables: `{"device_id": ..., "state": <StateValue>, "trigger_key": <hex>, "test": bool}` (Phase 1 exposed `device_id` and `state`; `test` and `trigger_key` are additive).
Build order: validate each option's raw actions on its own (a bad option is reported through the existing `TRIGGER_SETUP` Repairs path and left out, other options keep working, as Phase 1 does per trigger), then validate the assembled `choose` once with `async_validate_actions`.
**Verified semantics (spike + source):**
- `queued`: FIFO order, at most `max_runs` runs including waiting ones; the 11th and 12th of 12 simultaneous runs were dropped with the warning `Dev: Maximum number of runs exceeded` [VERIFIED: spike output `Q order: ['a', 'b', ...] count 10`, `Q warnings: ['Dev: Maximum number of runs exceeded', ...]`; source `if self.script_mode != SCRIPT_MODE_RESTART and self.runs == self.max_runs:` script.py:1922]. This is D-12 for free (limit 10 = `DEFAULT_MAX`, but set it explicitly from a `const.py` constant).
- `restart`: the new run starts, the running one is stopped (`await self.async_stop(update_state=False, spare=run)`, script.py:1982-1990). The OLD caller receives `asyncio.CancelledError` when it was inside a step (spike: `R results: ['CancelledError', 'ScriptRunResult'] log ['b'] runs 0`), or returns normally with a result when the stop is observed between steps.
- A dropped run returns `None` without raising (`return None` in the `failed_single`/`failed_max_runs` branches, script.py:1917-1930); a finished run returns `ScriptRunResult`.
- `Script.async_unload()` stops running and waiting runs; their callers get `CancelledError` (spike `U results: ['CancelledError' x3]`).
**Runner rules that follow:**
- `_async_run` must NOT catch `CancelledError` (it is a `BaseException`, the existing `except Exception` is correct) and must clear the `action_failed_` issue only when `result is not None`; a dropped run must not clear a failure issue (Phase 1 cleared it in the `else:` branch, which was safe only while the lock guaranteed no drops).
- Guard the "clear issue on success" against superseded runs in `restart` mode with a per-device enqueue generation counter (a cancelled run can also return normally between steps). [ASSUMED: small hardening, not covered by a spike]
- Keep the `script not in self._scripts` skip check and `async_retire_scripts` semantics (retire after the new Script exists) with a single Script per device.
- Add `async_stop_runs(device_id)` (calls `script.async_stop()`) for the breaker trip.

### Pattern 5: Test buttons on a dedicated non-retained test topic
**What:** Discovery `button` components in the same device payload, one per trigger. Topic `test_topic(base, device_id) = f"{base}/{TOPIC_VERSION}/devices/{device_id}/test"`; `payload_press` = the trigger's StateValue exactly (`ON`, `OFF`, or the option StateValue), so the handler reuses the accepted-values map. Component key `test_<trigger_key>`, `unique_id` = `f"{device_id}_test_{trigger_key}"` (UUID-based, stable across renames because StateValue is immutable), `name` = `f"Test {label}"` (`Test ON`, `Test OFF`, `Test <friendly name>`), `retain: False`, `qos: 1`, `entity_category: "config"` [ASSUMED: keeps buttons off auto dashboards]. Manager subscribes to the test topic per device (unsubscribe on remove/stop next to the state subscription), ignores `msg.retain`, resolves the payload, logs unknown payloads like D-09, and calls `runner.enqueue(..., test=True)`. The test path never touches `StateTracker`, the baseline, the breaker, or publishes anything.
**Verified:** real HA created one button entity per component, pressing publishes `('t/test', '<payload_press>', 1, False)` (qos 1, retain False), entity names render as `<device> Test <name>` [VERIFIED: spike `PRESS button.dev_test_aan ('t/test', 'on', 1, False)`].
**Removal:** the empty device payload on delete already cleans all components because core regenerates a cleanup payload for every already discovered component of that device (`_generate_device_config`, discovery.py:249-271), so D-16 of Phase 1 covers buttons unchanged. Removing a single button (option removed) needs a tombstone, see Pitfall 4.

### Pattern 6: Circuit breaker
**What:** Pure `CircuitBreaker(max_runs, window, clock=time.monotonic)` with `record() -> bool`: prune stamps older than `window`; if `len(stamps) >= max_runs` set `tripped = True` and return `False` (the tripping change does not run); else append and return `True`. Exactly `max_runs` runs per window are allowed, the `max_runs + 1`-th trips (defaults: the 6th change within 10 s). Only real edges with an enqueued run count (not the test button, not changes to a trigger without actions, not paused devices).
**Manager on trip:** set paused, log a warning (device name and limits only), create `circuit_breaker_<device_id>` Repairs issue, schedule a background task calling `runner.async_stop_runs(device_id)` (breaks the loop; queued self-triggered runs must not keep publishing) [ASSUMED: stopping in-flight runs is a design choice, D-15 only says "no actions run" for incoming changes], persist `tripped[device_id] = sha256(signature)` through the existing delayed save (HA flushes delayed Store saves at final write).
**Paused device:** `StateTracker` still updates the baseline (already happens before the run decision), no run, debug log.
**Release paths (D-15):**
1. Config change of that device: in `_async_change_device`, if the device is tripped, clear tripped/issue/window (any changed title or data counts). At start, drop a persisted tripped entry whose stored hash differs from the current subentry signature hash.
2. Entry unload/reload: `async_unload_entry` clears all tripped entries before `async_stop()` saves the store. HA shutdown does NOT go through unload (`ConfigEntries._async_shutdown` only calls `entry.async_shutdown()`, config_entries.py:2307-2311), so a plain restart keeps the tripped state (D-17) while a user reload releases it (D-15). Do not release in `Manager.async_stop` itself: `__init__.py` also calls it when setup fails.
**Why not a flow hook:** reconfigure submitted with unchanged data makes `async_update_subentry` a no-op (no update listener), and a flow cannot reach `runtime_data` when the entry is not loaded. State this limitation in the Repairs text ("change the device or reload the integration").
**Persistence shape:** additive `STORE_TRIPPED = "tripped"` (`dict[str, str]` device_id -> config hash), tolerant loader like `_parse_published`, no `STORE_VERSION` bump. Prune ids no longer in the subentries. `_data_to_save`, `_async_remove_device`, `_async_orphan_cleanup` and `async_remove_all_devices` must all handle it (and delete issues with the new prefix; the hub-removal loop currently only deletes `action_failed_` and `mqtt_discovery_disabled`).
**Repairs at start:** issues are not persistent by default, so recreate the breaker issue for every persisted tripped device during `_async_add_device`.

### Anti-Patterns to Avoid
- **Per-trigger Scripts with per-trigger modes:** `restart` would not cancel a sibling trigger's run and `queued` would not serialize across triggers (each Script has its own `_runs`/`_queue_lck`).
- **Omitting a component to remove its entity:** core ignores omissions (Pitfall 4).
- **Embedding user text in templates without JSON escaping, or hashing/normalizing differently in Python and Jinja.**
- **Mutating `subentry.data` in a flow:** copy first; in-place mutation changes live config without an update listener and breaks signature comparison.
- **Publishing from the test path or from the breaker:** neither may write to the state topic.
- **Deleting the tripped state in `Manager.async_stop`:** it runs on failed setups too.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Serial queue with bound, FIFO, drop+log | asyncio.Lock + counter + custom cancel | `Script(script_mode="queued", max_runs=10, max_exceeded="WARNING")` | Native, tested, logs `Maximum number of runs exceeded` |
| Restart with race-free cancel | Task cancel bookkeeping across triggers | `Script(script_mode="restart")` over one combined `choose` Script | HA adds the new run before stopping others so simultaneous runs cannot cancel each other |
| Mapping StateValue <-> friendly name | Hand-escaped Jinja strings | `json_dumps(...)` as string literal + spike-derived tests | JSON escapes are valid Jinja; hostile-string round trip verified |
| Confirming removal | Custom modal state machine | `async_show_menu` with `confirm_remove`/`keep` | Native navigation, translatable labels |
| Wall-clock windows | `datetime` bookkeeping | `collections.deque` of `time.monotonic()` stamps with injected clock | Immune to clock changes, trivially testable |
| Repairs surfacing | Custom notifications | `issue_registry.async_create_issue` with `translation_key` | Existing D-08/D-09 pattern |
| Removing a single discovered component | Republishing without it | Tombstone `{"platform": "button"}` in the device payload | Only explicit empty component config removes an entity |

**Key insight:** every hard part of this phase (queueing, restarting, template rendering, component removal) already exists in HA core with tested semantics; the code to write is glue, validation, and a small pure breaker.

## Common Pitfalls

### Pitfall 1: A dropped or superseded run clears the failure issue
**What goes wrong:** `Script.async_run` returns `None` for a dropped run (queue full) and returns a result for a run stopped between steps; Phase 1's `else:` branch deletes the `action_failed_` issue in both cases.
**Why it happens:** Phase 1 relied on the lock, so drops could not occur.
**How to avoid:** clear only when `result is not None` and the run was not superseded (generation guard); never catch `CancelledError`.
**Warning signs:** a failing device whose Repairs issue disappears while runs are being dropped or restarted.

### Pitfall 2: Restart raises `CancelledError` into the old caller
**What goes wrong:** the old background task ends as cancelled; naive `except BaseException` or `gather` without `return_exceptions` turns it into a failure or a test error.
**How to avoid:** let it propagate, no Repairs, no error log (D-11). Tests use `gather(..., return_exceptions=True)` or `async_block_till_done(wait_background_tasks=True)`.
**Warning signs:** `action_failed_` issues in restart mode.

### Pitfall 3: HA select shows `unknown` after renaming or removing the current option
**What goes wrong:** the MQTT select stores the last rendered friendly name in `_attr_current_option`; `SelectEntity.state` returns `None` when `current_option not in self.options` (select/__init__.py:146-151). A discovery update with unchanged topic/qos does not resubscribe (`EntitySubscription._should_resubscribe`, mqtt/subscription.py:68-82), so no retained replay refreshes it.
**Reproduced:** state `Beta` -> rename to `Bravo` -> `unknown`; remove the option -> `unknown`; unknown payload keeps `unknown`; next valid payload sets the state [VERIFIED: spike `R1 Beta, R2 unknown, R3 unknown, R4 unknown, R5 Charlie`].
**Impact:** D-02's "the entity state stays until the next valid payload arrives" is only true for our tracker/baseline, not for the HA entity. See Open Question 1.

### Pitfall 4: Omitted components are not removed
**What goes wrong:** removing an option and dropping its button from the device payload leaves the button entity alive.
**Reproduced:** after republishing without a button, 7 buttons remained; after republishing with `{"platform": "button"}` for its key, 6 [VERIFIED: spike `after OMIT buttons: 7`, `after TOMBSTONE buttons: 6`; source comment "If the dict is empty after removing the platform, the payload is assumed to remove the existing config", discovery.py:444-446]. Core removes the entity and its registry entry without clearing the device topic (`_cleanup_discovery_on_remove()` runs first, entity.py:1076).
**How to avoid:** keep `Device.retired_components: set[str]` in memory, add `{"platform": "button"}` for those keys to every publish while the process lives (including reconnect republish), drop them at the next start. A removal while HA MQTT was down leaves an orphaned registry entry the user can delete (accepted edge).

### Pitfall 5: Reconfigure with unchanged data releases nothing
**What goes wrong:** `async_update_subentry` returns without calling listeners when nothing changed, so no reconcile runs.
**How to avoid:** detect release from a config change or unload (Pattern 6), state the rule in the issue text.

### Pitfall 6: `NumberSelector` yields floats
**How to avoid:** `int(value)` and range checks in the flow before storing; treat `5.0` in stored data defensively in `spec_from_subentry`.

### Pitfall 7: Baseline handling still assumes ON/OFF
**What goes wrong:** `_async_load_store` keeps only values in `{PAYLOAD_ON, PAYLOAD_OFF}` (manager.py:264) and `decide()` compares against ON/OFF (state.py:33), which would drop every Select baseline or mark every payload unknown.
**How to avoid:** load any string, then sanitize per device against the spec's accepted values at add/change time (a baseline that is no longer a StateValue becomes `None`) [ASSUMED: sanitizing choice]. Keep `handle()` behavior that any first message closes the startup window (state.py:50-51).

### Pitfall 8: Enumerations still use `SUBENTRY_SWITCH`
`async_reconcile`, `_async_orphan_cleanup` and `async_remove_all_devices` call `get_subentries_of_type(SUBENTRY_SWITCH)`; a Select subentry would never start, be cleaned up, or be cleared on hub removal. Iterate over both types via one helper.

### Pitfall 9: PHACC mock loops publishes back
`select.select_option` in the test harness changes the entity state immediately and the published message is delivered back to subscribers [VERIFIED: spike `C2 Alpha ('t/state', 'a', 1, True)`]. Phase 1's rule stands: drive edges with `async_fire_mqtt_message(..., retain=...)`, assert publishes via `mqtt_mock.async_publish`. Real Mosquitto forwards live messages with `retain=False`.

### Pitfall 10: Test presses fan out across instances (Phase 3)
A discovery button always publishes to the broker; any instance subscribed to the test topic runs the actions, not only the instance whose user pressed it. Harmless with one instance (Phase 2). See Open Question 2. The broker ACL documentation (TRU-04) and the Phase 3 trust gate must cover the `/test` topic as a second action trigger source.

### Pitfall 11: Jinja normalization drift
`casefold()` vs `lower()`, or forgetting `trim`, makes the entity disagree with the tracker (a payload accepted by one and not the other). Use `.strip().lower()` everywhere and unit-test both sides against the same table.

## Code Examples

### Sliding-window breaker (pure)
```python
# Source: design for D-14/D-15, pure module modelled on custom_components/mqtt_actions/state.py
@dataclass(slots=True)
class CircuitBreaker:
    max_runs: int
    window: float
    clock: Callable[[], float] = time.monotonic
    tripped: bool = False
    _stamps: deque[float] = field(default_factory=deque)

    def record(self) -> bool:
        """Count one real-change run; False (and tripped) when it would exceed max_runs within the window."""
        if self.tripped:
            return False
        now = self.clock()
        while self._stamps and now - self._stamps[0] >= self.window:
            self._stamps.popleft()
        if len(self._stamps) >= self.max_runs:
            self.tripped = True
            return False
        self._stamps.append(now)
        return True
```

### Generalized `decide()` (Switch behavior unchanged)
```python
# Source: generalization of custom_components/mqtt_actions/state.py decide()
def decide(retain, payload, last_acted, startup_pending, run_on_startup, accepted=SWITCH_ACCEPTED) -> Decision:
    value = accepted.get(payload.strip().lower())   # canonical StateValue or None
    if value is None:
        return Decision(act=False, baseline=last_acted, ignored=True)
    if retain:
        return Decision(act=startup_pending and run_on_startup, value=value, baseline=value)
    return Decision(act=value != last_acted, value=value, baseline=value)
```
Keeping `accepted` a trailing keyword with the Switch default keeps the existing positional `tests/test_state.py` cases valid.

### Combined per-device Script
```python
# Source: verified in spike (Script + choose + template condition on run variable), HA helpers/script.py
raw = [{"choose": [
    {"conditions": [{"condition": "template", "value_template": f"{{{{ trigger_key == '{t.key}' }}}}"}],
     "sequence": t.actions}
    for t in triggers if t.actions
]}]
sequence = await async_validate_actions(hass, raw)          # existing helper, ActionsInvalid on error
mode = "queued" if spec.run_mode == RUN_MODE_SERIAL else "restart"
script = Script(hass, sequence, spec.name, DOMAIN, script_mode=mode,
                max_runs=SERIAL_QUEUE_LIMIT, max_exceeded="WARNING", logger=LOGGER)
result = await script.async_run({"device_id": device_id, "state": value, "trigger_key": key, "test": False}, Context())
```

### Tombstoned device payload (Switch or Select)
```python
components["test_" + key] = {"platform": "button"}   # retired option: removes the entity, keep while the process lives
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-trigger Scripts + own lock (Phase 1) | One Script per device with native `queued`/`restart` | Phase 2 | Native queue bound and race-free restart |
| Switch-only ON/OFF tracker | Accepted-values map shared by Switch and Select | Phase 2 | One decision function, Phase 3 config documents reuse it |
| `object_id` for entity ids | `default_entity_id` in MQTT common schema (`CONF_DEFAULT_ENTITY_ID`, mqtt/schemas.py:185) | HA 2025/2026 | Not needed here; do not add `object_id` |
| `voluptuous` | `probatio` | HA 2026.9 | Already followed |

**Deprecated/outdated:** none relevant beyond the above.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Length/count caps (e.g. max options, max name length) are needed and reasonable; concrete values are discretionary (suggest 50 options, 64 characters) | Pattern 3, Security | Very large payloads or UI clutter; low impact, adjust constants |
| A2 | Test button stays usable while a device is paused by the breaker | Pattern 5/6 | User cannot debug a tripped loop; trivial to flip |
| A3 | On trip, running and queued runs of the device are stopped | Pattern 6 | If unwanted, in-flight sequences finish; loop may emit a few more state messages (bounded by the queue of 10) |
| A4 | `entity_category: "config"` for test buttons | Pattern 5 | Buttons appear under Controls instead of Configuration |
| A5 | A change to a trigger without actions does not cancel a running `restart` run (nothing is enqueued) | Pattern 4 | Users may expect "latest state wins" to cancel anyway |
| A6 | Reject non-printable characters in StateValue and friendly name (`isprintable()`) | Pattern 3 | Legitimate exotic names rejected; simplification to a smaller check is easy |
| A7 | Breaker inputs limited to 1..100 runs and 1..3600 seconds | Pattern 3 | Users with chatty devices need larger values |
| A8 | Additive `tripped` Store key needs no `STORE_VERSION` bump | Pattern 6 | If a later migration expects a version, add it then |
| A9 | Test press fan-out across instances is accepted for Phase 2 and revisited in Phase 3 | Pitfall 10, Open Question 2 | DEV-07 "locally" would be violated in multi-instance setups |
| A10 | Small generation guard against superseded runs clearing the issue | Pattern 4 | Rare false issue clear in restart mode |
| A11 | Sanitize a stored baseline that is no longer a StateValue to `None` | Pitfall 7 | Different edge behavior after an option is removed and re-added |
| A12 | Breaker release via config change + unload rather than a flow hook | Pattern 6 | Unchanged reconfigure does not release (documented) |

## Open Questions

1. **D-02 wording vs HA behavior: the select entity turns `unknown` after the current option is removed or renamed.**
   - What we know: reproduced in a real-HA spike; the tracker/baseline behave as D-02 says, the HA entity does not (Pitfall 3).
   - What's unclear: whether a rename of the currently selected option should heal the display.
   - Recommendation: accept `unknown` for removal (the option no longer exists). For a rename of the current option, ship the minimal behavior (unknown until the next valid payload, documented in the README/flow description) and treat "republish the retained `last_acted` once after a friendly-name change" as an optional follow-up: it is idempotent for our tracker (equals the baseline, no edge) but adds a state-topic write path for the owner and overwrites whatever retained value an external publisher left. Needs user confirmation.

2. **DEV-07 "locally" versus a broker round trip.**
   - What we know: Discovery buttons must publish; every instance subscribed to the test topic will run (single instance today).
   - What's unclear: whether Phase 3 should gate test execution to the instance that pressed (impossible from the wire) or drop the test topic subscription on follower/observe-only instances.
   - Recommendation: implement as designed for Phase 2 and record the constraint for Phase 3 planning and the broker ACL docs.

3. **Should a Switch test button and existing Phase 1 users see new entities after upgrade?**
   - What we know: the Switch device payload gains two button components on the next publish; D-10/D-13 imply yes.
   - Recommendation: yes, no opt-out; mention in release notes.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | test/lint runs | yes | 0.12.7 | — |
| Python (via uv) | runtime | yes | 3.14.7 | — |
| Home Assistant + PHACC in `.venv` | tests, source verification | yes | HA 2026.9.4, PHACC 0.13.367 | — |
| mosquitto | `tests/broker` tier | yes (`/usr/bin/mosquitto`) | not queried; `tests/broker` ran `4 passed` | tier skips when missing |
| Real HA host `haos-op3050-1` | manual UI checks (menu rendering, ActionSelector inside loop, DE/EN labels) | assumed reachable via SSH/Tailscale (per CLAUDE.md), not probed | — | Manual-only verification at phase end |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio (auto) via pytest-homeassistant-custom-component 0.13.367 (`pyproject.toml`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`, marker `broker`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, `tests/conftest.py` (factories `make_hub_entry`, `make_switch_subentry`) |
| Quick run command | `uv run pytest tests/<file>.py -q` |
| Full suite command | `uv run pytest tests -q && uv run ruff check . && uv run ruff format --check .` |

Baseline measured this session: `188 passed in 9.24s`.

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEV-03 | Flow creates a Select subentry with >= 2 options; validation errors (min 2, empty/whitespace/duplicate StateValue, duplicate/`none` friendly name) | integration (flow) | `uv run pytest tests/test_config_flow_select.py -q` | no, Wave 0 |
| DEV-03 | Discovery payload has select component, options in creation order, mapping templates; e2e entity creation with hostile strings | unit + integration (real HA MQTT discovery) | `uv run pytest tests/test_discovery_select.py -q` | no, Wave 0 |
| DEV-03 | Live payload of an option runs only that option's actions; UI selection publishes exact StateValue | integration (manager) | `uv run pytest tests/test_manager_select.py -q` | no, Wave 0 |
| DEV-04 | Edit step has no `state_value` field; friendly-name/actions edits reach the retained discovery only (topic and payload unchanged); add/remove option incl. confirmation; option removal tombstones the button | integration (flow + manager + discovery) | `uv run pytest tests/test_config_flow_select.py tests/test_manager_select.py -q` | no, Wave 0 |
| DEV-06 | `serial` FIFO, bound 10 with dropped-run warning, `restart` cancels running and starts the new run without Repairs, missing `run_mode` behaves as serial | integration (runner/manager) | `uv run pytest tests/test_runner_modes.py -q` | no, Wave 0 |
| DEV-07 | Buttons per trigger (Switch 2, Select N), press runs actions, publishes nothing to the state topic, baseline and entity state untouched, not counted by breaker, failure creates the normal issue, retained test message ignored | integration | `uv run pytest tests/test_test_buttons.py -q` | no, Wave 0 |
| STA-06 | Breaker window boundaries, (max+1)-th change trips, paused device updates baseline only, Repairs issue + warning, runs stopped, persisted across a manager restart, window not persisted, released by config change and by reload, issue removed on release/delete/hub removal | unit (pure) + integration | `uv run pytest tests/test_breaker.py tests/test_manager_breaker.py -q` | no, Wave 0 |
| STA-07 | Unknown/empty payload: no action, warning with truncated repr, baseline unchanged, unknown retained payload sets no baseline; HA entity keeps state and logs no error | unit (`decide` table) + integration | `uv run pytest tests/test_state.py tests/test_manager_select.py tests/test_discovery_select.py -q` | extend existing + Wave 0 |
| FND-04 (regression) | en/de parity for all new keys and placeholders | unit | `uv run pytest tests/test_translations.py -q` | extend existing |

### Sampling Rate
- **Per task commit:** the single test file the task touched (`uv run pytest tests/<file>.py -q`, under 10 s).
- **Per wave merge:** `uv run pytest tests -q` plus `uv run ruff check . && uv run ruff format --check .` (baseline 9 s).
- **Phase gate:** full suite green plus the manual checks below before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_breaker.py`: pure sliding-window table (boundary at exactly `window`, trip at max+1, no count after trip, injected clock)
- [ ] `tests/test_model.py` (or inside `test_state.py`): `spec_from_subentry` for Switch (missing new keys -> defaults) and Select, option validation, `trigger_key`, template builders against `homeassistant.helpers.template.Template` with hostile strings and shared normalization table
- [ ] `tests/test_discovery_select.py`: port the session spike (real HA discovery via `mqtt_mock` + `async_fire_mqtt_message` on `homeassistant/device/<id>/config`): hostile-string round trip both directions, unknown payload keeps state with no WARNING/ERROR, button press payloads, omit-vs-tombstone, rename-current-option yields `unknown`
- [ ] `tests/test_runner_modes.py`: queued FIFO + drop warning, restart cancel (old task cancelled, no issue), unload cancels queued runs, dropped run does not clear the issue
- [ ] `tests/test_config_flow_select.py`, `tests/test_manager_select.py`, `tests/test_test_buttons.py`, `tests/test_manager_breaker.py`
- [ ] Extend `tests/conftest.py` with `make_select_subentry` and extend `make_switch_subentry` with `run_mode`/breaker kwargs (defaults omitted so the old-data path is exercised)
- [ ] Extend `tests/test_translations.py` `REQUIRED_KEYS` and placeholder assertions (`issues.circuit_breaker_tripped.description` variables, select flow keys, `selector.run_mode.options.*`)
- [ ] Framework install: none

**Manual-only (cannot be tested in PHACC):** menu loop rendering, `ActionSelector` inside repeated option steps, DE/EN labels in the real dialog, and one end-to-end run against a real broker on `haos-op3050-1` (select an option in the UI, publish with `ha-ws`/`mosquitto_pub`, trip the breaker with a self-toggling action, release by reload). Test rule carried over from Phase 1: never drive edges through the publish loopback.

## Security Domain

`security_enforcement` is enabled (ASVS level 1, block on high, `.planning/config.json` read this session).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Broker credentials belong to the HA MQTT integration |
| V3 Session Management | no | — |
| V4 Access Control | yes (limited) | The new test topic is a second broker-reachable action trigger; same trust model as the state topic until the Phase 3 trust gate; document in the ACL example (TRU-04) |
| V5 Input Validation | yes | Flow validation in a pure module (StateValue/friendly name rules, length/count caps, integer ranges); `cv.SCRIPT_SCHEMA` + `async_validate_actions_config` per option; broker payloads normalized through the accepted-values map, unknown payloads dropped |
| V6 Cryptography | no | `sha256` only as a non-secret identifier/hash, never for security |
| V7 Error Handling and Logging | yes | Log only device name, trigger label and truncated `repr` of payloads (`MAX_LOGGED_PAYLOAD_LENGTH`); never action data or template text (Phase 1 T-01-10) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Template injection through option names/StateValues embedded in discovery templates | Tampering / Elevation | Emit strings only as `json_dumps` literals; hashed keys in `choose` conditions; hostile-string tests; the same builder will process broker-provided config in Phase 3 |
| Payload flood or self-triggering loop exhausts the event loop | Denial of service | Bounded queue (10) + per-device breaker + paused state persisted across restart |
| Broker user publishes to `/test` to run actions | Elevation | Ignore retained messages, accept only known payloads, rely on broker ACL and the Phase 3 trust gate |
| Log forging via unknown payloads or names | Repudiation | Truncated `repr` logging, reject non-printable characters in names |
| Oversized names/option lists bloat retained discovery and Repairs text | Denial of service | Count and length caps as `const.py` constants (A1) |

## Sources

### Primary (HIGH confidence)
- `custom_components/mqtt_actions/{runner,discovery,config_flow,manager,const,state,topics,mqtt_gateway,actions,__init__}.py` (read this session), `tests/{conftest,test_translations,test_config_flow,test_manager,test_state}.py` (read/sampled)
- HA 2026.9.4 source in `.venv/lib/python3.14/site-packages/homeassistant/`: `helpers/script.py` (modes, `Script.async_run`, `_QueuedScriptRun`), `components/mqtt/{select,button,discovery,entity,models,subscription,schemas}.py`, `components/select/__init__.py`, `helpers/selector.py` (`NumberSelector`), `helpers/template/__init__.py` (`async_render_with_possible_json_value`), `config_entries.py` (`ConfigSubentryFlow`, `_async_shutdown`, `supports_reconfigure`), `data_entry_flow.py` (`async_show_menu`), `components/bayesian/{config_flow.py,strings.json}` (core subentry menu reference)
- Real-HA spikes run this session (files in the session scratchpad, to be ported to permanent tests): select/button discovery round trip with hostile strings, unknown payloads, omit vs tombstone, rename/remove current option, PHACC publish loopback, `queued`/`restart`/unload Script semantics
- `.planning/phases/02-*/02-CONTEXT.md`, `REQUIREMENTS.md`, `STATE.md`, Phase 1 CONTEXT/VALIDATION, `.planning/research/PITFALLS.md` (Pitfalls 3, 13, 14)

### Secondary (MEDIUM confidence)
- `.claude/CLAUDE.md` stack notes (versions of probatio, uv, Ruff, PHACC)

### Tertiary (LOW confidence)
- None; no web search was needed (no external providers configured, and the authoritative source is the pinned HA release in `.venv`).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, no new packages; versions read from the environment
- Architecture: HIGH for Script modes, discovery, templates, tombstones (spiked); MEDIUM for the flow menu loop (core reference exists, rendering is manual-only) and for breaker release semantics (design choice, see A12)
- Pitfalls: HIGH, most reproduced or read in source

**Research date:** 2026-09-29
**Valid until:** 2026-10-29 for structure; re-check discovery/select behavior when the HA floor moves past 2026.9 (HA releases monthly, PHACC daily).
