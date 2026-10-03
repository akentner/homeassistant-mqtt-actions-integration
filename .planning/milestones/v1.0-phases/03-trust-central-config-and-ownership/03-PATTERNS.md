# Phase 3: Trust, Central Config and Ownership - Pattern Map

**Mapped:** 2026-10-01
**Files analyzed:** 19 (8 new, 11 modified)
**Analogs found:** 17 / 19 (all analog paths verified git-tracked via `git ls-files`)

All paths are relative to `/home/akentner/Projects/homeassistant-mqtt-actions-integration/`. Protocol and lifecycle rules are in `03-RESEARCH.md` (Patterns 1-12); this file gives the in-repo code to copy from.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `custom_components/mqtt_actions/document.py` (new) | utility (pure) | transform | `model.py` + `topics.py` (pure, no-HA style) | role-match |
| `custom_components/mqtt_actions/sync.py` (new) | service | event-driven / pub-sub | `manager.py` (Manager) | role-match |
| `custom_components/mqtt_actions/trust.py` (new) | service/utility | transform + request-response | `runner.py` (Script build) | partial |
| `custom_components/mqtt_actions/repairs.py` (new) | provider (Repairs platform) | request-response | none in repo (issues: `runner.py:189-208`; flows: `config_flow.py`) | no analog |
| `custom_components/mqtt_actions/topics.py` (mod) | utility | transform | itself, lines 35-52 | exact |
| `custom_components/mqtt_actions/const.py` (mod) | config | n/a | itself, lines 56-76 | exact |
| `custom_components/mqtt_actions/mqtt_gateway.py` (mod) | gateway | pub-sub | itself, lines 16-49 | exact |
| `custom_components/mqtt_actions/manager.py` (mod) | service | event-driven | itself | exact |
| `custom_components/mqtt_actions/runner.py` (mod) | service | request-response | itself, lines 42-102 | exact |
| `custom_components/mqtt_actions/discovery.py` (mod) | service | pub-sub | itself, lines 140-174 | exact |
| `custom_components/mqtt_actions/config_flow.py` (mod: delete step, hub OptionsFlow) | controller (flow) | request-response | itself, `SelectSubentryFlow` lines 500-525 | exact |
| `custom_components/mqtt_actions/__init__.py` (mod) | config/lifecycle | request-response | itself, lines 45-58 | exact |
| `custom_components/mqtt_actions/translations/en.json`, `de.json` (mod) | config | n/a | themselves + `tests/test_translations.py` | exact |
| `tests/fake_broker.py` (new) | test utility | pub-sub | `tests/conftest.py` + `tests/broker/conftest.py` | partial |
| `tests/test_document.py`, `test_trust.py` (new) | test | transform | `tests/test_model.py`, `tests/test_topics.py` | role-match |
| `tests/test_sync_*.py`, `test_repairs.py` (new) | test | event-driven | `tests/test_manager.py`, `tests/test_manager_breaker.py` | exact |
| `tests/test_translations.py` (mod) | test | n/a | itself (`REQUIRED_KEYS`) | exact |
| `tests/test_config_flow*.py` (mod) | test | request-response | themselves (lines 136-138, 256-410) | exact |
| `tests/broker/test_acl.py` (new) | test | pub-sub | `tests/broker/test_retain_semantics.py` + `conftest.py` | exact |
| `README.md`, `docs/broker-acl.md` (new/mod) | docs | n/a | none | no analog |

## Pattern Assignments

### `topics.py` (mod: config topic, wildcards, parsers)

**Analog:** itself. Keep the pure, no-HA-import style and f-string builders (`topics.py:35-52`):
```python
def state_topic(base: str, device_id: str) -> str:
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/state"

def availability_topic(base: str, instance_id: str) -> str:
    return f"{base}/{TOPIC_VERSION}/instances/{instance_id}/availability"

def discovery_topic(prefix: str, device_id: str) -> str:
    return f"{prefix}/device/{device_id}/config"
```
Add `config_topic(base, device_id)`, wildcard builders (`.../devices/+/config`, `.../instances/+/availability`, `{prefix}/device/+/config`) and parse functions (topic -> device_id / instance_id, reject wrong segment count). Base topic is validated wildcard-free (`validate_base_topic`, lines 12-32), so wildcards are only appended after it.

### `const.py` (mod)

**Analog:** itself (`const.py:56-76`): `Final` constants, prefix style for issue ids, Store keys additive without version bump.
```python
STORE_TRIPPED: Final = "tripped"
STORE_SAVE_DELAY: Final = 5.0
ISSUE_ACTION_FAILED_PREFIX: Final = "action_failed_"
ISSUE_CIRCUIT_BREAKER_PREFIX: Final = "circuit_breaker_"
```
Add `SCHEMA_VERSION`, `DENIED_SERVICES`/`DENIED_DOMAINS` (frozenset), caps (`MAX_DOCUMENT_BYTES`, `MAX_MIRRORS`, `MAX_ACTION_DEPTH`), `PRUNE_GRACE_SECONDS`, `REPUBLISH_THROTTLE_SECONDS`, `STORE_MIRRORS/APPROVALS/REVS`, and the new `ISSUE_*_PREFIX` constants.

### `mqtt_gateway.py` (mod: `topic` on `IncomingMessage`)

**Analog:** itself (`mqtt_gateway.py:16-21, 44-47`):
```python
@dataclass(frozen=True, slots=True)
class IncomingMessage:
    payload: str
    retain: bool
# in _forward (must stay a @callback):
message_callback(IncomingMessage(payload=payload, retain=msg.retain))
```
Change: add `topic: str = ""` and pass `topic=msg.topic`. Keep the `@callback` comment-worthy constraint. The gateway stays the only module importing `homeassistant.components.mqtt`.

### `document.py` (new, pure: wire contract, hashes, walker)

**Analog:** `model.py` (pure dataclasses, `spec_from_data`, `_invalid_text`, `validate_breaker`, lines 56-233) and `manager.py:82-98` for hashing.
```python
# manager.py:82-98 - existing fingerprint/hash style; do NOT reuse _fingerprint for the wire hash (RESEARCH Pattern 1 rule 2)
def _fingerprint(title: str, data: Mapping[str, Any]) -> str:
    return json.dumps({"title": title, "data": dict(data)}, sort_keys=True)
def _hash_fingerprint(fingerprint: str) -> str:
    return hashlib.sha256(fingerprint.encode()).hexdigest()
```
Build the document from `DeviceSpec` (`model.py:68-79`), and turn a validated document back into a `DeviceSpec` via `spec_from_data(kind, title, data)` (`model.py:155`). Reuse `model._invalid_text` semantics and `validate_breaker` for strict rejection. Canonical JSON: `sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False`. Parse with `homeassistant.util.json.json_loads_object`.

### `sync.py` (new: SyncManager, owner and follower)

**Analog:** `manager.py` (lock discipline, `_async_attempt`, callbacks spawning background tasks, `entry.async_on_unload`).

**Callback-to-task pattern** (`manager.py:259-263`), copy for wildcard handlers that must publish:
```python
@callback
def _on_connection_status(self, connected: bool) -> None:
    if connected and self._running:
        self._entry.async_create_background_task(self._hass, self._async_republish(), name=f"{DOMAIN} republish")
```
**Republish body** (`manager.py:265-277`): insert config documents before discovery, availability last.
```python
async with self._lock:
    if not self._running:
        return
    for device in self.devices.values():
        await self._async_publish_discovery(device)
    await self._async_publish_availability(AvailabilityState.ONLINE)
```
**MQTT failure handling** (`manager.py:115-122`), wrap every broker write:
```python
async def _async_attempt(action, description) -> bool:
    try:
        await action()
    except HomeAssistantError as err:
        LOGGER.warning("MQTT could not %s: %s", description, err)
        return False
    return True
```
**Store load/parse defensiveness** (`manager.py:101-112, 302-313`): every Store key is type-checked and malformed data dropped; mirror/approval/rev parsers follow `_parse_tripped`. Subscriptions: `await self.gateway.async_subscribe(topic, partial(handler, ...))` with unsubscribe stored and called on stop (`manager.py:356-363`, `239-245`). Use `async_call_later` for the prune/throttle timers, cancelled on stop.

### `manager.py` (mod)

**Analog:** itself. Key edit sites (keep mirrors in a separate `self.mirrors` dict, never in `self.devices`):
- `async_start` lines 197-204: prune maps against `owned | mirrors` ids; start config/availability/discovery-watch subscriptions before publishing.
- `_async_remove_device` lines 398-424: extend order to discovery clear, unsubscribe, config tombstone, state clear.
```python
cleared = await _async_attempt(partial(self._publisher.async_clear_device, device_id), ...)
if device.unsubscribe is not None: device.unsubscribe()
if device.unsubscribe_test is not None: device.unsubscribe_test()
state_cleared = await _async_attempt(partial(self._publisher.async_clear_state, device_id), ...)
```
- `_data_to_save` lines 315-326 and `_async_load_store` 302-313: add mirrors/approvals/revs keys; include mirror baselines in `STORE_LAST_ACTED`/`STORE_TRIPPED`.
- `_on_message` lines 453-485 and `_on_test_message` 561-586: resolve the device from `devices` or `mirrors`; the gate `not self.runner.can_run(...)` already means "no Script until approved".
- `async_remove_all_devices` lines 136-163: extend cleared set with the config topic, add new issue prefixes to the cleanup tuple, honor the D-11 option.
- Constructor lines 169-187: add optional `gateway` and `store_key` params (production defaults unchanged) for `FakeBroker` tests.

### `runner.py` (mod: `restricted` mirror build, denylist error)

**Analog:** itself. Insertion point is `_async_build_script` after validation (`runner.py:88-102`):
```python
try:
    validated = await async_validate_actions(self._hass, sequence)
except ActionsInvalid as err:
    self._report_setup_error(spec, TRIGGER_SETUP, err)
    return None
return Script(self._hass, validated, spec.name, DOMAIN, script_mode=..., max_runs=SERIAL_QUEUE_LIMIT, max_exceeded="WARNING", logger=LOGGER)
```
Change: `async_build_device(spec, *, restricted=False)`; when restricted, `validated = guard_actions(validated)` (see `trust.py`). Failure surfacing: `_async_run` (`runner.py:179-184`) already catches `Exception`, logs names only and calls `report_failure`; catch the dedicated `DeniedServiceCallError` first to use a denylist translation key. Issue create/delete shape to copy: `runner.py:189-208`. Unload: `async_unload(device_id, remove_issue=True)` (220-227) is the "pause on missing approval" primitive.

### `trust.py` (new)

**Analog:** `actions.py` (validation wrapper; read it for the `ActionsInvalid` convention) plus the `GuardedTemplate`/`guard_actions` code in `03-RESEARCH.md` "Code Examples" (spike-verified; `DeniedServiceCallError` must be a plain `Exception`, not `TemplateError`/`HomeAssistantError`). Approval-state helpers follow the `_parse_*` Store pattern.

### `repairs.py` (new)

**No in-repo analog.** Use RESEARCH Pattern 5 (`async_create_fix_flow(hass, issue_id, data)`, `RepairsFlow`, `async_create_entry(data={})` to approve, `async_abort` otherwise, delete-then-create on hash change). Issue creation style to copy: `manager.py:539-554`:
```python
ir.async_create_issue(self._hass, DOMAIN, f"{ISSUE_CIRCUIT_BREAKER_PREFIX}{device.device_id}",
    is_fixable=False, severity=ir.IssueSeverity.ERROR, translation_key="circuit_breaker_tripped",
    translation_placeholders={"device": device.name, ...})
```
Set `is_fixable=True` for approval and pass only `device_id` and `actions_hash` in `data`.

### `discovery.py` (mod: config-topic clear, watcher support)

**Analog:** itself, `DiscoveryPublisher` (`discovery.py:140-174`). Add `async_publish_config(doc_json)` and `async_clear_config(device_id)` with the same one-line `gateway.async_publish(topic, payload, retain=True)` shape as `async_clear_state`. Discovery prefix comes from `self._gateway.discovery_prefix()` at call time.

### `config_flow.py` (mod: delete step, hub OptionsFlow)

**Analog:** `SelectSubentryFlow` remove-confirm steps (`config_flow.py:491-525`) for the confirm/confirmed step naming, and `SwitchSubentryFlow.async_step_reconfigure` (203-205) where a menu must be added. Menu precedent: `SelectSubentryFlow.async_step_menu` (348). Delete execution per RESEARCH Pattern 8: `hass.config_entries.async_remove_subentry(entry, subentry_id)` then `async_abort(reason="device_deleted")`. Hub `OptionsFlow` with one boolean `delete_devices_on_remove` (default False); `MqttActionsConfigFlow.async_get_supported_subentry_types` (line 118) stays unchanged and the hub must still have no `async_step_reconfigure` (`tests/test_config_flow.py:136-138`).

### `__init__.py` (mod)

**Analog:** itself. `async_remove_entry` (lines 52-58) currently calls `async_remove_all_devices`; change it to read the D-11 option (keep = no destructive publishes, still remove Store and issues). `async_unload_entry` (45-49) pattern stays.

### Tests

- **`tests/fake_broker.py`**: fixtures pattern from `tests/conftest.py:1-60` (`MockConfigEntry`, autouse `enable_custom_integrations`, `expected_lingering_timers`). Implement `FakeGateway` with the five `MqttGateway` methods (`async_wait_ready`, `async_subscribe`, `async_subscribe_connection_status`, `async_publish`, `discovery_prefix`, `discovery_enabled`). Spiked design in RESEARCH Pattern 11 (use `paho.mqtt.client.topic_matches_sub`; per-instance Store key).
- **Follower/owner single-instance tests**: copy `tests/test_manager.py` helpers (`_setup`, `async_fire_mqtt_message(..., retain=True)`, `async_mock_service`, `mqtt_mock.async_publish` assertions; imports at lines 1-46).
- **Broker tier**: `tests/broker/conftest.py` (`mosquitto_port` fixture, `_free_port`, `_wait_for_port`, skip when missing) and `tests/broker/test_retain_semantics.py` for the ACL test; add an ACL file in `tmp_path`.
- **Translations**: extend `REQUIRED_KEYS` in `tests/test_translations.py`; placeholders must not sit in single quotes (`VARIABLE_IN_SINGLE_QUOTES`).
- **Pure tests**: follow `tests/test_model.py` / `tests/test_topics.py` for `document.py` and the denylist walker (nest a templated service name three levels deep; `continue_on_error: true` regression).

## Shared Patterns

### MQTT writes never raise into lifecycle code
**Source:** `manager.py:115-122` (`_async_attempt`). **Apply to:** all sync/publish/clear code.

### Logging without payload content
**Source:** `manager.py:588-595` and `runner.py:182` (names and truncated repr only, `MAX_LOGGED_PAYLOAD_LENGTH`). **Apply to:** document ingest, denylist hits, approval. Never log action data.

### Repairs issue id = prefix constant + device id; delete on removal
**Source:** `const.py:73-75`, `manager.py:539-559`, cleanup list `manager.py:158-163`. **Apply to:** approval, blocked, owner_conflict, ownership_claim, schema_too_new, doc_overwritten, discovery_removed.

### Store is additive, defensively parsed, saved with delay
**Source:** `manager.py:101-112, 315-331`. **Apply to:** mirrors, approvals, revs.

### Gateway is the only MQTT seam; subscribe handlers are `@callback`
**Source:** `mqtt_gateway.py:35-49`. **Apply to:** every new subscription; heavy work goes through `entry.async_create_background_task`.

### Lifecycle via `entry.async_on_unload` and `runtime_data`
**Source:** `__init__.py:23-27`, `manager.py:196`. **Apply to:** SyncManager subscriptions and timers.

### Ruff/typing conventions
Module docstrings on each file, `from __future__`-free annotations with `TYPE_CHECKING` imports (see `runner.py:21-25`), `# noqa` with rule code where needed, `assert self._publisher is not None  # noqa: S101`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `custom_components/mqtt_actions/repairs.py` | Repairs fix flow | request-response | No fix flow exists; all current issues are `is_fixable=False`. Use RESEARCH Pattern 5. |
| `docs/broker-acl.md`, README section | docs | n/a | Use RESEARCH Pattern 12 wording. |
| `GuardedTemplate` (in `trust.py`) | Template subclass | transform | New mechanism; use the spike-verified code in RESEARCH "Code Examples". |

## Metadata

**Analog search scope:** `custom_components/mqtt_actions/`, `tests/`, `tests/broker/`
**Files scanned:** 12 source modules, 4 test files (read or sampled)
**Pattern extraction date:** 2026-10-01
