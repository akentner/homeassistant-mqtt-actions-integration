# Phase 2: Select Devices and Reliable Execution - Pattern Map

**Mapped:** 2026-09-29
**Files analyzed:** 21 (5 new source, 8 modified source, 2 translation files, 6+ test files)
**Analogs found:** 21 / 21 (all in-repo, all git-tracked; brand-new logic is confined to `breaker.py` and the menu loop, which still have role analogs)

All analogs are tracked under `custom_components/mqtt_actions/` and `tests/` (verified via `git ls-files`). Line numbers refer to the current files.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `custom_components/mqtt_actions/model.py` (NEW) | utility (pure) | transform | `state.py` (pure, no HA imports) | role-match |
| `custom_components/mqtt_actions/breaker.py` (NEW) | utility (pure) | transform | `state.py` (`StateTracker`, slots dataclass) | role-match |
| `custom_components/mqtt_actions/const.py` (mod) | config | n/a | itself, lines 17-46 | exact |
| `custom_components/mqtt_actions/topics.py` (mod: `test_topic`) | utility (pure) | transform | `state_topic` (topics.py:211-213) | exact |
| `custom_components/mqtt_actions/state.py` (mod: `accepted` map) | utility (pure) | transform | itself, `decide` lines 140-159 | exact |
| `custom_components/mqtt_actions/discovery.py` (mod: select/button/tombstones) | service | request-response (publish) | `build_switch_discovery` + `DiscoveryPublisher` | exact |
| `custom_components/mqtt_actions/runner.py` (mod: one Script per device, modes) | service | event-driven | itself | exact |
| `custom_components/mqtt_actions/manager.py` (mod: DeviceSpec, test sub, breaker, tripped store) | service | pub-sub + event-driven | itself | exact |
| `custom_components/mqtt_actions/config_flow.py` (mod: run mode/breaker fields; new `SelectSubentryFlow`) | controller (flow) | request-response | `SwitchSubentryFlow` (config_flow.py:100-199) | exact for settings/actions; menu loop has no in-repo analog |
| `custom_components/mqtt_actions/translations/en.json`, `de.json` (mod) | config | n/a | existing `issues` block, en.json:76-85 | exact |
| `tests/test_breaker.py`, `tests/test_model.py` (NEW) | test (pure) | transform | `tests/test_state.py` | exact |
| `tests/test_discovery_select.py` (NEW) | test | request-response | `tests/test_discovery.py`, `tests/test_manager.py` | role-match |
| `tests/test_runner_modes.py`, `tests/test_manager_select.py`, `tests/test_test_buttons.py`, `tests/test_manager_breaker.py` (NEW) | test (integration) | event-driven | `tests/test_manager.py` | exact |
| `tests/test_config_flow_select.py` (NEW) | test (flow) | request-response | `tests/test_config_flow.py` | exact |
| `tests/conftest.py` (mod: `make_select_subentry`, kwargs) | test config | n/a | `make_switch_subentry` (conftest.py:44-67) | exact |
| `tests/test_translations.py` (mod: `REQUIRED_KEYS`) | test | transform | itself (line 20) | exact |
| `custom_components/mqtt_actions/__init__.py` (mod: unload clears tripped) | config | event-driven | itself, `async_unload_entry` | exact |

## Pattern Assignments

### `model.py` (utility, transform) and `state.py` generalization

**Analog:** `custom_components/mqtt_actions/state.py`. Style: module docstring "Pure functions without Home Assistant imports", frozen slots dataclasses, constants imported from `.const`.

**Imports and dataclass style** (state.py:1-15):
```python
"""Edge detection for state messages. Pure functions without Home Assistant imports."""

from dataclasses import dataclass

from .const import PAYLOAD_OFF, PAYLOAD_ON

@dataclass(frozen=True, slots=True)
class Decision:
    act: bool
    value: str | None = None
    baseline: str | None = None
    ignored: bool = False
```

**Function to generalize** (state.py:140-159). Change the normalization from `.strip().upper()` plus set membership to `accepted.get(payload.strip().lower())`. Add `accepted` as a trailing keyword with the Switch default so positional calls in `tests/test_state.py` stay valid. `StateTracker.handle` (state.py:170-176) needs an `accepted` field passed through:
```python
value = payload.strip().upper()
if value not in {PAYLOAD_ON, PAYLOAD_OFF}:
    return Decision(act=False, baseline=last_acted, ignored=True)
if retain:
    return Decision(act=startup_pending and run_on_startup, value=value, baseline=value)
return Decision(act=value != last_acted, value=value, baseline=value)
```
Keep `handle()` behavior "any first message closes the startup window, only non-ignored updates the baseline" (state.py:170-176).

`DeviceSpec`/`TriggerSpec`/`spec_from_subentry`: use `subentry.data.get(...)` with defaults for new keys (D-10, no migration). Current code reads `subentry.data[CONF_RUN_ON_STARTUP]` with `[]` (manager.py:297, 328); do not copy that for new keys. `trigger_key`, template builders, `_lit = json_dumps` come from RESEARCH.md Patterns 1 and 2, copied verbatim. `model.py` may import `json_dumps` from `homeassistant.helpers.json` (as discovery.py:229 does), or keep the template builders in `discovery.py` to keep `model.py` HA-free.

---

### `breaker.py` (utility, transform)

**Analog:** `state.py:162-176` (slots dataclass with mutable per-device state and a single method). Copy the shape, implement the "Sliding-window breaker (pure)" from RESEARCH.md "Code Examples" (no closer in-repo analog for the deque logic). Time is injected (`clock` field) so tests stay pure, like `tests/test_state.py`.

---

### `const.py` (config)

**Analog:** itself. Conventions: `Final` typed module constants, grouped by comment header (const.py:17-46).
```python
# Subentry types and subentry data keys (D-03)
SUBENTRY_SWITCH: Final = "switch"
CONF_RUN_ON_STARTUP: Final = "run_on_startup"
# Persistent store
STORE_LAST_ACTED: Final = "last_acted"
STORE_PUBLISHED: Final = "published"
# Repairs issues
ISSUE_ACTION_FAILED_PREFIX: Final = "action_failed_"
```
Add: `SUBENTRY_SELECT`, `CONF_OPTIONS`/`CONF_STATE_VALUE`/`CONF_FRIENDLY_NAME`/`CONF_ACTIONS`, `CONF_RUN_MODE`, `RUN_MODE_SERIAL`/`RUN_MODE_RESTART`, `CONF_BREAKER_MAX_RUNS`/`CONF_BREAKER_WINDOW` plus defaults 5 and 10, `SERIAL_QUEUE_LIMIT = 10`, `STORE_TRIPPED = "tripped"`, `ISSUE_CIRCUIT_BREAKER_PREFIX = "circuit_breaker_"`, length/count caps (A1, A7). Keep `TRIGGER_ON`/`TRIGGER_OFF` labels (const.py:239-241).

---

### `topics.py` (utility, transform)

**Analog:** `state_topic` (topics.py:211-213). Add `test_topic` directly beneath:
```python
def state_topic(base: str, device_id: str) -> str:
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/state"
```
New: `f"{base}/{TOPIC_VERSION}/devices/{device_id}/test"`. Test lives in `tests/test_topics.py`.

---

### `discovery.py` (service, publish)

**Analog:** itself. Rename or generalize `build_switch_discovery` to `build_discovery(spec, ...)`.

**Payload shape to reuse** (discovery.py:255-276): `device` / `origin` / `components` / `availability`. The `switch` component keys (`platform`, `unique_id: device_id`, `name: None`, `state_topic == command_topic`, `retain: True`, `qos: 1`) are copied for the `select` component:
```python
"switch": {
    "platform": "switch", "unique_id": device_id, "name": None,
    "state_topic": topic, "command_topic": topic,
    "retain": True, "qos": 1,
    "payload_on": PAYLOAD_ON, "payload_off": PAYLOAD_OFF,
    "value_template": "{{ value | upper }}",
}
```
Select replaces the payload/template keys with `options` (friendly names) and the generated `value_template`/`command_template` (RESEARCH Pattern 2). Add button components per trigger (RESEARCH Pattern 5: `retain: False`, `unique_id = f"{device_id}_test_{key}"`, component key `test_<key>`), plus tombstones `{"platform": "button"}` for retired keys.

**Publisher pattern** (discovery.py:288-301): all publishes go through `self._gateway.async_publish(discovery_topic(self._gateway.discovery_prefix(), device_id), json_dumps(payload), retain=True)`. Extend `async_publish_device` to take a spec and `retired_components`. `async_clear_device` (discovery.py:303-305) already clears all components on delete, so no change is needed for button cleanup.

---

### `runner.py` (service, event-driven)

**Analog:** itself. Keep the constructor, `report_failure` (runner.py:80-95, the `ir.async_create_issue` block with `translation_placeholders`), `clear_issue`, and background-task enqueue via `self._entry.async_create_background_task` (runner.py:46-51).

**Replace** (runner.py:29-36): the per-trigger `Script(..., script_mode="single")` becomes one Script per device (RESEARCH "Combined per-device Script"). Store a single `Script` per `device_id`, adopt `async_retire_scripts`'s "retire only after the new one exists" order (runner.py:101-109).

**Replace** (runner.py:53-78): the `asyncio.Lock` FIFO goes away. Keep this error-handling block but change the `else`:
```python
try:
    await script.async_run(run_variables, Context())
except Exception as err:  # noqa: BLE001
    LOGGER.exception("Actions for %s of device %s failed", trigger, device_name)
    self.report_failure(device_id, device_name, trigger, str(err))
else:
    ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}")
```
Do not catch `CancelledError`. Clear the issue only if `result is not None` and the run was not superseded (generation counter). Log only the device and trigger names, never action data (T-01-10 comment at runner.py:74). Add `async_stop_runs(device_id)` and a `test: bool` run variable. Follow the `async_unload` pattern (runner.py:116-121) for `remove_issue`, and delete the breaker issue too where appropriate.

---

### `manager.py` (service, pub-sub / event-driven)

**Analog:** itself. Key sections to generalize:

- `Device` dataclass (manager.py:61-71): replace `on_script`/`off_script` with `spec: DeviceSpec`, `script`, `breaker`, `unsubscribe`, `unsubscribe_test`, `retired_components: set[str]`.
- `_signature` (manager.py:74-76) is reused for change detection and for the tripped hash: `json.dumps({"title": subentry.title, "data": dict(subentry.data)}, sort_keys=True)`; hash it with sha256 for `STORE_TRIPPED`.
- `_parse_published` (manager.py:79-82): copy this tolerant-loader style (`isinstance` guards) for the tripped map.
- `async_reconcile` (manager.py:175-189), `_async_orphan_cleanup` (manager.py:363), `async_remove_all_devices` (manager.py:117-119): iterate both `SUBENTRY_SWITCH` and `SUBENTRY_SELECT` through one helper (Pitfall 8). The hub-removal issue loop (manager.py:130-134) must also delete the `circuit_breaker_` prefix.
- `_async_load_store` (manager.py:257-269): the value filter `value in {PAYLOAD_ON, PAYLOAD_OFF}` at line 264 must accept any string, then sanitize against the spec (Pitfall 7).
- `_data_to_save` (manager.py:271-281): add the `STORE_TRIPPED` key next to `STORE_LAST_ACTED`/`STORE_PUBLISHED`. Keep `_schedule_save` (manager.py:283-286).
- `_async_add_device` (manager.py:288-312): subscription pattern to copy for the test topic. Resolve the device by id at message time:
```python
device.unsubscribe = await self.gateway.async_subscribe(
    state_topic(self._base_topic, device_id),
    partial(self._on_message, device_id),
)
```
- `_async_build` (manager.py:383-397): the per-trigger `ActionsInvalid` -> log + `report_failure(..., TRIGGER_SETUP, error)` pattern, applied per option before assembling the combined Script.
- `_async_change_device` (manager.py:314-330): `clear_issue` first, rebuild, retire old, republish; add the breaker release here (clear tripped, issue, window).
- `_async_remove_device` (manager.py:332-354): order is discovery clear, unsubscribe, state clear, runner unload. Add unsubscribing the test topic and dropping the tripped entry.
- `_on_message` (manager.py:399-424): `@callback`, resolves device, `decision = device.tracker.handle(...)`, `_log_ignored`, `_schedule_save` on baseline change, then enqueue. Insert the breaker check between `decision.act` and `enqueue`. The comment "Only the device id and the normalised value reach templates" stays true (add `trigger_key`).
- `_log_ignored` (manager.py:426-433): reuse verbatim for Select unknown payloads and the test topic (D-09).
- `async_stop` (manager.py:191-210): must not release the tripped state (RESEARCH Pattern 6; `__init__.py` calls it on failed setup).
- `_check_discovery_enabled` (manager.py:232-245): the `ir.async_create_issue(... translation_key=...)` block is the template for the breaker Repairs issue.

`__init__.py:47-50` `async_unload_entry` calls `entry.runtime_data.async_stop()`; clear the tripped map there (before `async_stop` saves), not inside `async_stop`.

---

### `config_flow.py` (flow, request-response)

**Analog:** `SwitchSubentryFlow` (config_flow.py:100-199).

**Registration** (config_flow.py:93-97):
```python
@classmethod
@callback
def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:  # noqa: ARG003
    return {SUBENTRY_SWITCH: SwitchSubentryFlow}
```
Add `SUBENTRY_SELECT: SelectSubentryFlow`.

**Form/commit pattern** (config_flow.py:116-170): shared `_async_handle_form(step_id, user_input, subentry)`, RAW selector output stored (never validated Template objects), `async_create_entry(title, unique_id=device_id, data={CONF_DEVICE_ID: device_id, **data})` for create, `async_update_and_abort(self._get_entry(), subentry, title=name, data={**data, CONF_DEVICE_ID: subentry.data[CONF_DEVICE_ID]})` for reconfigure (replace, not merge). Schema via `probatio.Schema` with `probatio.Required/Optional` and `selector.*`; `self.add_suggested_values_to_schema(schema, suggested)`.

**Action validation** (config_flow.py:172-187): `_async_check_actions` loops fields with `async_validate_actions`, returns `{"base": "invalid_actions"}` with `{"field", "error"}` placeholders capped at `MAX_FLOW_ERROR_LENGTH`, then the `device_id` warn-then-confirm via a JSON fingerprint. Generalize to `(label, raw_actions)` pairs so it serves the Switch fields and each Select option (D-01).

**Add to the Switch flow:** `run_mode` (`SelectSelector`, `translation_key="run_mode"`), `breaker_max_runs`, `breaker_window` (`NumberSelector`; coerce to `int` before storing, Pitfall 6). `_prefill` (config_flow.py:189-199) uses `subentry.data.get(...)` with defaults; keep that for the new keys.

**Menu loop (no in-repo analog):** use RESEARCH Pattern 3 and the HA core reference `components/bayesian/config_flow.py` `ObservationSubentryFlowHandler` (lines 537-546, in `.venv`). Key facts: `async_show_menu` has no `errors`; `async_create_entry` is only valid for `SOURCE_USER`; deep-copy the draft; commit once on `done`.

---

### Translations `en.json` / `de.json`

**Analog:** en.json:76-85 `issues` block:
```json
"action_failed": {
  "title": "An action failed",
  "description": "The actions for {trigger} of {device} failed at {time}: {error}"
},
```
Add `issues.circuit_breaker_tripped` (placeholders `{device}`, `{max_runs}`, `{window}`), `config_subentries.select.*` steps and `menu_options`, `selector.run_mode.options.*`, error keys. Keep parity between files; `tests/test_translations.py` enforces identical keys and placeholders, no variables inside single quotes, and `REQUIRED_KEYS` (line 20) which must be extended.

---

### Tests

- **Pure tests** (`test_breaker.py`, `test_model.py`, extend `test_state.py`): copy the parametrized-table style of `tests/test_state.py:1-55` (tuple case, one assertion block, `@pytest.mark.parametrize`). Existing positional `decide(...)` calls must keep working.
- **Integration tests** (`test_manager_select.py`, `test_runner_modes.py`, `test_test_buttons.py`, `test_manager_breaker.py`): copy helpers from `tests/test_manager.py:41-62`:
```python
async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry

async def _fire(hass, entry, device_id, payload, *, retain):
    topic = state_topic(entry.data["base_topic"], device_id)
    async_fire_mqtt_message(hass, topic, payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)
```
Drive edges with `async_fire_mqtt_message`, never via publish loopback (Pitfall 9); use `async_mock_service` for action targets. Use `gather(..., return_exceptions=True)` around cancelled restart runs (Pitfall 2).
- **Flow tests** (`test_config_flow_select.py`): follow `tests/test_config_flow.py` around lines 141-156 (`hass`, `hub` fixture, assertions on `hub.subentries`, `uuid.UUID(...).version == 4`, `unique_id == device_id`).
- **conftest** (`tests/conftest.py:44-67`): `make_switch_subentry` returns `ConfigSubentryData(data={...}, subentry_type=..., title=name, unique_id=device_id)`. Add `make_select_subentry` in the same style. Extend the Switch factory with `run_mode`/breaker kwargs that are OMITTED from data when not given, so the missing-key default path is exercised.
- **Discovery e2e test**: `mqtt_mock` plus `async_fire_mqtt_message` on `homeassistant/device/<id>/config`, ported from the RESEARCH spike.

## Shared Patterns

### Failure and setup-problem surfacing
**Source:** `runner.py:80-95` (`report_failure`), `manager.py:383-397` (`_async_build`).
**Apply to:** runner, manager, breaker Repairs issue (own key prefix and `translation_key`), test-button failures (normal path, D-13).
Log only device and trigger labels and capped errors (`MAX_ISSUE_ERROR_LENGTH`), never action data.

### MQTT access only through the gateway, cleanup never raises
**Source:** `manager.py:85-92` (`_async_attempt`), `mqtt_gateway.py` (`async_subscribe`, `async_publish`).
```python
async def _async_attempt(action, description) -> bool:
    try:
        await action()
    except HomeAssistantError as err:
        LOGGER.warning("MQTT could not %s: %s", description, err)
        return False
    return True
```
**Apply to:** all discovery publishes, tombstones, test-topic subscribe/unsubscribe.

### Unknown payload handling
**Source:** `manager.py:426-433` (`_log_ignored`), `const.py:236` (`MAX_LOGGED_PAYLOAD_LENGTH`).
**Apply to:** Select state topic and the test topic (D-09). Empty payload is debug only.

### Tolerant store loading, additive keys
**Source:** `manager.py:79-82`, `manager.py:255-269`.
**Apply to:** `STORE_TRIPPED`. No `STORE_VERSION` bump; drop malformed entries silently.

### Immutable device id and RAW action storage
**Source:** `config_flow.py:133-152`.
**Apply to:** the Select flow commit and option edits (StateValue immutable, D-03).

### Translation parity
**Source:** `tests/test_translations.py:69-100`.
**Apply to:** every new user-visible string in en and de.

### Ruff and style
Line length 120, `select = ["ALL"]`; existing code uses `# noqa: FBT001` on boolean positional args (state.py:141-145), `# noqa: BLE001` on the broad except, `# noqa: S101` on `assert self._publisher is not None`. Docstrings on every function, English comments, `TYPE_CHECKING` import blocks for typing-only imports.

## No Analog Found

| File / Piece | Role | Data Flow | Reason |
|---|---|---|---|
| Menu-loop flow steps in `SelectSubentryFlow` (`async_show_menu`, in-memory draft) | flow | request-response | Repo has only form-based flows. Use RESEARCH Pattern 3 and core `components/bayesian/config_flow.py` (in `.venv`, not tracked in this repo). |
| Sliding-window deque logic in `breaker.py` | utility | transform | No time-window logic exists. Use RESEARCH "Sliding-window breaker (pure)". |
| Tombstone handling for retired button components | service | pub-sub | No component-level removal exists yet. Use RESEARCH Pitfall 4 and the "Tombstoned device payload" example. |
| Jinja value/command template builders | utility | transform | Switch uses one static template (discovery.py:272). Use RESEARCH Pattern 2 code. |

## Metadata

**Analog search scope:** `custom_components/mqtt_actions/`, `tests/`
**Files scanned:** 12 source files, 5 test/config files read in full or in relevant ranges
**Pattern extraction date:** 2026-09-29
