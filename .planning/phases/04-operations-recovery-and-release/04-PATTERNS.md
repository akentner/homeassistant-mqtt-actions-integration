# Phase 4: Operations, Recovery and Release - Pattern Map

**Mapped:** 2026-10-02
**Files analyzed:** 27 new/modified
**Analogs found:** 25 / 27
**Tracked-source gate:** all analogs below are git-tracked (`git ls-files` listing checked; no mirror paths).

Post-Research Decisions in 04-CONTEXT.md apply: companion devices (D-13), additive `transferred_from` marker honored only when the pinned owner is offline (D-09), service field named `device_id`, hub-level mode select plus per-device select, most restrictive mode wins.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `custom_components/mqtt_actions/topics.py` (mod) | utility | transform | itself (`availability_topic`, `availability_wildcard`, `parse_availability_topic`) | exact |
| `custom_components/mqtt_actions/const.py` (mod) | config | n/a | itself (`STORE_*`, `ISSUE_DEVICE_PREFIXES`, `MAX_TRACKED_INSTANCES`) | exact |
| `custom_components/mqtt_actions/presence.py` (new) | service | pub-sub + timer | `sync.py` `SyncManager._on_availability_message` / prune timer | role-match |
| `custom_components/mqtt_actions/retrigger.py` (new) | service | request-response over pub-sub | `manager.py` `_on_test_message` | role-match |
| `custom_components/mqtt_actions/modes.py` (new) | utility | transform | `state.py` / `breaker.py` (pure modules) | role-match |
| `custom_components/mqtt_actions/manager.py` (mod: gate, stores, discard, adopt) | service | event-driven | itself (`_on_message`, `_data_to_save`, `_async_remove_device`) | exact |
| `custom_components/mqtt_actions/sync.py` (mod: pin rule, heartbeat subscribe) | service | event-driven | itself (`async_start`, `_async_ingest_locked`) | exact |
| `custom_components/mqtt_actions/document.py` (mod: `actions_hash`, `transferred_from`) | model | transform | itself | exact |
| `custom_components/mqtt_actions/transfer.py` (new, or in manager) | service | CRUD | `manager.py` `_async_remove_device` | role-match |
| `custom_components/mqtt_actions/portability.py` (new) | utility | file-I/O + transform | `document.py` `parse_document` / `build_content` | role-match |
| `custom_components/mqtt_actions/services.py` + `services.yaml` (new) | controller | request-response | `repairs.py` `_loaded_manager` (lookup) | partial |
| `custom_components/mqtt_actions/__init__.py` (mod) | config | request-response | itself | exact |
| `custom_components/mqtt_actions/entities.py`, `sensor.py`, `select.py`, `button.py` (new) | component | event-driven | none in repo | no analog |
| `custom_components/mqtt_actions/diagnostics.py` (new) | service | transform | none in repo | no analog |
| `custom_components/mqtt_actions/repairs.py` (mod: dispatch, duplicate-id and transferred flows) | component | request-response | itself (`ApprovalRepairFlow`) | exact |
| `custom_components/mqtt_actions/translations/{en,de}.json` (mod) | config | n/a | existing files + `tests/test_translations.py` parity | exact |
| `docs/operations.md`, `diagnostics.md`, `troubleshooting.md`, `broker-acl.md` (mod) | docs | n/a | `docs/broker-acl.md` | role-match |
| `.github/workflows/ci.yml` (mod: tier jobs, `workflow_call`) | config | batch | itself | exact |
| `.github/workflows/release.yml` (new) | config | batch | `ci.yml` / `validate.yml` | role-match |
| `pyproject.toml` (mod: markers) | config | n/a | itself | exact |
| `tests/test_repo_structure.py` (mod) | test | n/a | itself | exact |
| `tests/broker/conftest.py` (mod: require-broker switch) | test | n/a | itself | exact |
| `tests/test_retrigger.py`, `test_presence.py`, `test_modes.py`, `test_transfer.py`, `test_portability.py`, `test_services.py`, `test_diagnostics.py` (new) | test | request-response | `tests/test_test_buttons.py`, `tests/test_multi_instance.py`, `tests/test_hub_removal.py` | role-match |
| `tests/test_document.py` (mod: flip hash test) | test | n/a | itself (lines ~199-210) | exact |

## Pattern Assignments

### `topics.py` (utility, transform)

**Analog:** itself, lines 51-103. Add `retrigger_topic`, `acks_topic`, `heartbeat_topic`, `heartbeat_wildcard`, `parse_heartbeat_topic`, `parse_retrigger_topic` in the same shape. Reuse `_parse_segment` (one segment, no wildcard) and `is_valid_device_id` for ids.

```python
def test_topic(base: str, device_id: str) -> str:
    """Return the non-retained topic the test buttons of a device publish to; it never carries device state (D-13)."""
    return f"{base}/{TOPIC_VERSION}/devices/{device_id}/test"

def availability_wildcard(base: str) -> str:
    return f"{base}/{TOPIC_VERSION}/instances/+/availability"

def parse_availability_topic(base: str, topic: str) -> str | None:
    return _parse_segment(topic, f"{base}/{TOPIC_VERSION}/instances/", "/availability")
```
Note: new topics stay under `v1` (additive, no `TOPIC_VERSION` bump). Pure module: no HA imports. Extend `tests/test_topics.py` and `docs/broker-acl.md`.

### `presence.py` (service, pub-sub + timer)

**Analog:** `sync.py` `SyncManager` (subscribe at 165-185, bounded tracking at 270-297, timer at 209-226).

**Subscribe + unsubscribers pattern** (sync.py:179-185):
```python
self._unsubscribers.append(
    await manager.gateway.async_subscribe(
        availability_wildcard(manager.base_topic), self._on_availability_message
    )
)
```
**Bounded tracking + overflow-logged-once** (sync.py:278-297): parse topic segment, return on None, cap with `MAX_TRACKED_INSTANCES`, log once.
**Timer in background task** (sync.py:221-226): `async_call_later(...)` -> callback -> `manager.entry.async_create_background_task(manager.hass, coro, name=f"{DOMAIN} ...")`. For the 30 s tick use `async_track_time_interval` registered through `entry.async_on_unload` and cancelled in `Manager.async_stop`.
**Rules for new payload:** ignore `msg.retain`; topic segment must equal payload `instance_id`; validate name with `model._invalid_text`; use `Manager.clock` (manager.py `self.clock = time.monotonic`) so tests can replace it; own echo (same session) ignored; two foreign-session observations before the Repairs issue (Pitfall 5). `on_reconnect` (sync.py:198-207) must also clear the roster ("unknown is never online").

### `retrigger.py` (service, request-response over pub-sub)

**Analog:** `manager.py` `_on_test_message` (1159-1184) plus the test-topic subscription in `_async_add_device`/`_async_subscribe_mirror` (manager.py ~833-850, 889).

**Core pattern** (manager.py:1168-1184):
```python
if msg.retain or (device := self._device(device_id)) is None:
    return
value = device.spec.accepted.get(msg.payload.strip().lower())
if value is None:
    self._log_ignored(device, msg.payload)
    return
trigger = device.spec.triggers.get(trigger_key(value))
if trigger is None or not self.runner.can_run(device_id, trigger.key):
    return
self.runner.enqueue(device_id, device.name, trigger.label, trigger.key,
                    {"device_id": device_id, "state": value}, test=True)
```
Add before this, in order: payload size cap (1 KiB), strict JSON parse (`uuid.UUID`, `is_valid_device_id`), stale `sent_at`, bounded dedupe cache, per-device 5 s limit (skipped for own request ids, Pitfall 3), mode check, breaker `paused`; then publish ack. Constants (N, 5 s window, 60 s freshness) go in `const.py`. Never touches tracker, baseline, breaker (D-01).

### `manager.py` mode gate, stores, discard, adopt

**Mode gate:** insert in `_on_message` (manager.py:1045-1076). `disabled` returns before `device.tracker.handle` (line 1050); `observe` after the `can_run` check at line 1060 and before the breaker at 1063, without `breaker.record()`. Log names via `sync._shown` style (capped, quoted). Gate `_on_test_message` (1168) too.

**New Store keys** (Pitfall 6): add to both `_async_load_store` (524-538) and `_data_to_save` (541-556); copy the defensive `_parse_*` helpers (manager.py:154-215, e.g. `_parse_approvals`) and `STORE_*` constants; no `STORE_VERSION` bump.
```python
self._approvals = _parse_approvals(stored)
...
STORE_APPROVALS: dict(self._approvals),
STORE_PUBLISHED: sorted(self._published),
```
**Local discard (D-08):** follow `_async_remove_device` (manager.py:930-963) pop-first order but with no publish calls; research "Local discard order" snippet (04-RESEARCH.md lines 433-453) is the target, saving with `await self._store.async_save(...)`, not `_schedule_save`. Do NOT call `_async_remove_device` or `_async_orphan_cleanup` (they publish tombstones).
**Issue cleanup:** `_delete_device_issues` (1149-1152) iterates `ISSUE_DEVICE_PREFIXES`; add `transferred_` prefix there (const.py:174-185); hub-level duplicate-id issue id must also be deleted in `async_remove_local_state` (manager.py:247-258).
**Republish for resync:** call `_async_republish` (manager.py:479-492) unchanged.
**Issue creation pattern:** `_create_breaker_issue` (manager.py:1131-1146) with `escape_markdown` for broker-supplied names.

### `sync.py` pin rule

**Analog:** `_async_ingest_locked` (sync.py:366-405) and `_conflict` (413-428). Today `info.owner != parsed.owner` always conflicts (around 398-400); change to re-pin only when `info.owner in parsed.transferred_from` and the pinned owner is not online per `instance_status` (sync.py:266). Otherwise keep raising `owner_conflict`.

### `document.py` (model, transform)

**`actions_hash`** (document.py:111-117): add `CONF_RUN_MODE`, `CONF_BREAKER_MAX_RUNS`, `CONF_BREAKER_WINDOW` to the canonical dict:
```python
return _sha256(canonical_json({"kind": spec.kind, CONF_RUN_ON_STARTUP: spec.run_on_startup, "triggers": pairs}))
```
Update module docstring (lines 18-20), `README.md` approval sentence, approval dialog placeholders (repairs.py:68-77) and both translation files. Flip `tests/test_document.py:199-210` (`test_actions_hash_binds_mapping_and_startup_flag`).
**`transferred_from`:** optional top-level bookkeeping list (max 8, validated ids), like `owner`/`rev`, not hashed; unknown keys already ignored (document.py:322-323); `SCHEMA_VERSION` stays 1. Parse in `parse_document` (316-360) with the same typed-reject style.

### `portability.py` (utility, file-I/O + transform)

**Analog:** `document.py` `build_content` (81-103) and `parse_document` (316-360). Export items = shared content with no id, owner or rev; import builds a throw-away document (new `uuid4`, owner = this instance, rev 1) and runs it through `parse_document` -> `validate_spec_structure` -> `async_validate_actions`; reject `analyze_spec(...).denied`. File I/O in executor, dedicated `<config>/mqtt_actions/` directory, name regex `[A-Za-z0-9._-]+\.json`, mode 0600. Pure build/validate functions, no HA imports where possible.

### `services.py` / `services.yaml` / `__init__.py` (controller, request-response)

**Analog:** `repairs.py:24-30` `_loaded_manager` (move to shared module) and `__init__.py` (no `async_setup` yet). Add `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)` and `async_setup` registering with `async_register_admin_service(..., SupportsResponse.OPTIONAL)` (research Code Examples lines 399-415).
```python
def _loaded_manager(hass: HomeAssistant) -> Manager | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            manager: Manager = entry.runtime_data
            return manager
    return None
```
User-visible errors: `ServiceValidationError` with translation key. Field name `device_id` is chosen; map registry device to uuid via the `(DOMAIN, device_id)` identifier. Reconcile `tests/test_repo_structure.py::test_docs_examples_use_no_device_id_targets`: keep the rule (no `device_id` targets in README and `broker-acl.md` examples), document the field in docs with a different example form and amend the test to cover new docs pages only for target usage.
**`__init__.py` platforms:** forward `sensor`, `select`, `button` at the end of `async_setup_entry` (after line 38 start) and unload in `async_unload_entry` (46-50). Keep the try/except `async_stop` pattern (29-37).

### `repairs.py` (component, request-response)

**Analog:** itself. `ApprovalRepairFlow` (33-87): `async_step_init` -> `async_step_confirm`, abort with `not_loaded`/`changed` reasons, bind the shown hash. Copy the structure for `DuplicateIdRepairFlow` and `TransferredRepairFlow`. Dispatch in `async_create_fix_flow` (90-96) on the `issue_id` prefix. Replace `import voluptuous as vol` (line 11) with `import probatio as vol`-style import used by other modules (A7). Duplicate-id fix: discard order from Pattern 7 (research lines 293-301), then new `uuid4` instance id into entry data and `hass.config_entries.async_schedule_reload(entry.entry_id)`.

### Hub and companion entities: `entities.py`, `sensor.py`, `select.py`, `button.py`

**No analog in repo** (no entity platform exists). Use research Pattern 3 and 11: companion device via `device_registry.async_get_or_create(config_entry_id=..., config_subentry_id=..., identifiers={(DOMAIN, device_id)}, manufacturer="MQTT Actions", ...)`; roster sensor `EntityCategory.DIAGNOSTIC` with `_unrecorded_attributes = frozenset({"instances"})`; mode select `EntityCategory.CONFIG`, reads/writes through the manager (no `RestoreEntity`); resync button calls `_async_republish` path. Dynamic add via dispatcher; pass `config_subentry_id` for owned. Mirror removal must delete its companion device (extend `Manager.async_remove_mirror`, manager.py:707-735, and `_clean_registry` 736-760). Do not define `async_remove_config_entry_device`. Translation keys en and de.

### `diagnostics.py`

**No analog in repo.** Use research Pattern 9: allow-list build, `async_redact_data` safety net, sentinel-string tests.

### `.github/workflows/ci.yml` (mod) and `release.yml` (new)

**Analog:** `ci.yml` lines 1-32. Keep header, `permissions: {}`, per-job `contents: read`, SHA-pinned checkout and setup-uv:
```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  with:
    persist-credentials: false
- uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
  with:
    python-version: "3.14"
    enable-cache: true
```
Split into `lint`, `unit` (`-m "not broker and not multi_instance"`), `broker` (only job with `apt-get install -y mosquitto`; env `MQTT_ACTIONS_REQUIRE_BROKER=1`), `multi-instance`; add `workflow_call:` trigger. `release.yml` skeleton: research lines 455-487 (check-version via `jq`, `uses: ./.github/workflows/ci.yml`, `gh release create --verify-tag --generate-notes`). `validate.yml` is the analog for a schedule/tag-independent workflow shape.

### `tests/test_repo_structure.py`, `pyproject.toml`, `tests/broker/conftest.py`

- `test_repo_structure.py`: `WORKFLOW_FILES = ("validate.yml", "ci.yml")` (line 30) add `release.yml`; `SHA_PIN` (line 28) must exempt local `./` refs; add tests "release needs ci" and the version check. Existing CI test flattens all jobs, so splitting still passes.
- `pyproject.toml`: extend existing `markers` list (has `broker`) with `multi_instance`; consider `--strict-markers`. Add `pytestmark = pytest.mark.multi_instance` to `tests/test_multi_instance.py` and `tests/test_fake_broker.py`.
- `tests/broker/conftest.py`: the two `pytest.skip("... not installed")` calls (around lines 45 and 86) become failures when the env switch is set.

### New tests

**Analogs:** `tests/test_test_buttons.py` (imports and `async_fire_mqtt_message`, `async_mock_service` recorder pattern, lines 1-60) for re-trigger and modes; `tests/test_multi_instance.py` + `tests/fake_broker.py` (`make_instance`; constructs `Manager` directly, so services and platforms need `async_setup_services(hass)` and `entry.mock_state(hass, ConfigEntryState.LOADED)`, Pitfall 2) for presence, adoption, duplicate-id and discard (assert the original's retained config, discovery and state stay byte-identical); `tests/test_hub_removal.py:52` (`hass.config_entries.async_setup` with `mqtt_mock`) for services, platforms, diagnostics; `tests/test_repairs_flow.py` for the new flows; `tests/test_translations.py` enforces en/de parity.

## Shared Patterns

### Untrusted broker input
**Source:** `document.py` `parse_document` (316-360), `sync.py` `_on_availability_message` (270-297), `topics.is_valid_device_id`.
**Apply to:** heartbeat, request, ack, import. Ignore `retain` where non-retained is required, size cap, strict typed parse, bounded caches, never log raw payloads; mirror names go through `_shown` in logs and `escape_markdown` in Repairs placeholders and registries.

### Lock-serialized state changes
**Source:** `async with manager.lock:` (sync.py:238, research discard snippet).
**Apply to:** discard, adopt, import, mode change that touches devices.

### Services in `async_setup`, state in `Manager`
Put behavior in `Manager` or small collaborators so the fake-broker tier covers it; `__init__.py` and entities stay thin.

### Constants
All limits and windows (heartbeat 30 s, offline 90 s, ack window 5 s, rate limit 5 s, dedupe N, freshness 60 s, import item cap 100) in `const.py` next to `MAX_TRACKED_INSTANCES` (const.py:133).

### Lint and style
Ruff `select = ["ALL"]`, 120 columns, docstrings on public functions with decision tags, `probatio` not `voluptuous`, English comments.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `entities.py`, `sensor.py`, `select.py`, `button.py` | component | event-driven | No entity platforms exist; use research Patterns 3 and 11 and HA core docs |
| `diagnostics.py` | service | transform | No diagnostics module exists; use research Pattern 9 |

## Metadata

**Analog search scope:** `custom_components/mqtt_actions/`, `tests/`, `.github/workflows/`, `docs/`
**Files scanned:** about 60 tracked files listed, 6 read in full or in targeted ranges
**Pattern extraction date:** 2026-10-02
