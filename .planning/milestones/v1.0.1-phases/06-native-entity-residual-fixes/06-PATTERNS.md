# Phase 6: Native Entity Residual Fixes - Pattern Map

**Mapped:** 2026-10-04
**Files analyzed:** 9
**Analogs found:** 9 / 9 (all modify existing code or extend existing tests; all tracked in git)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `custom_components/mqtt_actions/manager.py` (`NativeState`, `_parse_native`, `_data_to_save`, `_mirror_info`, `_build_mirror`, lifecycle hooks) | store/model | CRUD (Store round trip) | itself: `NativeState.pending/devices` | exact |
| `custom_components/mqtt_actions/manager.py` (`_async_native_takeover` catches, `_async_replay_catch`) | service | event-driven / batch | itself + `_start_cutover_check` (~820) | exact |
| `custom_components/mqtt_actions/takeover.py` (`async_remove_replay_twins`, `REPLAY_QUIET_SECONDS`) | utility (registry logic) | transform | `async_take_over` (107-160) | exact |
| `custom_components/mqtt_actions/document.py` (delete `with_native_marker`, 188-204) | utility | transform | removal only | n/a |
| `custom_components/mqtt_actions/const.py` (`STORE_NATIVE` comment, ~137-139) | config | n/a | itself | exact |
| `tests/test_native_start.py` or new `tests/test_native_residuals.py` | test | request-response | `tests/test_native_start.py` (owner pass, 135-195) | exact |
| `tests/test_takeover.py` (helper unit tests) | test | request-response | `tests/test_takeover.py` (`setup_legacy_device`, `_deliver`) | exact |
| `tests/conftest.py` (autouse `REPLAY_QUIET_SECONDS` shrink) | test config | n/a | `fast_takeover` fixture, `test_native_start.py` | role-match |
| `README.md` (Limitations ~336-352) + `tests/test_docs.py` | docs / doc test | n/a | `test_readme_limitations_are_current` (test_docs.py:377-388) | exact |

## Pattern Assignments

### `manager.py`: persisted native-mirror id set (IN-02, D-01..D-03)

**Analog:** `NativeState` / `_parse_native` / `_data_to_save` (manager.py:311-343, ~1218-1232)

**Dataclass and parse** (copy the `devices` shape for a new `mirrors` field):
```python
@dataclass(slots=True)
class NativeState:
    instance: bool = False
    pending: set[str] = field(default_factory=set)
    devices: set[str] = field(default_factory=set)

devices = native.get("devices")
...
devices={item for item in devices if isinstance(item, str) and is_valid_device_id(item)}
if isinstance(devices, list)
else set(),
```
Add the same comprehension for `mirrors`, then cap at `MAX_MIRRORS` (Store is untrusted).

**Save** (write `mirrors` only when non-empty; `tests/test_cutover.py:157,640,653,663` assert the exact dict `{"instance","pending","devices"}`):
```python
if self._native != NativeState():
    data[STORE_NATIVE] = {
        "instance": self._native.instance,
        "pending": sorted(self._native.pending),
        "devices": sorted(self._native.devices),
    }
    # add: if self._native.mirrors: data[STORE_NATIVE]["mirrors"] = sorted(self._native.mirrors)
```

**Read side** (replace `with_native_marker` use in `_mirror_info`, ~1795-1818, and pass the flag from `_build_mirror`, ~1836):
```python
carried = keep_native and not parsed.native
payload=with_native_marker(parsed.payload) if carried else parsed.payload,   # -> payload=parsed.payload
native=parsed.native or keep_native,
...
mirror=self._mirror_info(parsed)   # -> keep_native=parsed.device_id in self._native.mirrors
```
Lifecycle: add the id after every mirror create/replace (one helper, `if device.mirror.native: self._native.mirrors.add(id)`); remove in `async_remove_mirror` and `_async_drop_mirror`; prune to `self.mirrors.keys()` after `_async_restore_mirrors(current)` in `async_start` next to the other start-time prunes (~765-775). Keep sticky semantics (RESEARCH Open Question 1): do not change re-pin branches (~1289-1291, `_update_mirror` ~1850).

### `manager.py`: catches in `_async_native_takeover` (IN-03, D-04/D-05)

**Analog:** `_async_native_takeover` (873-933) and `_start_cutover_check` (~820) for the background task.

Catch 1 goes inside the `for target, status in zip(targets, results, strict=True)` loop for `DONE` targets; move/repeat `await takeover.async_flush_registries(self._hass)` after it so the registry holds move and removal before the clear:
```python
if any(status is takeover.TakeoverStatus.DONE or isinstance(status, BaseException) for status in results):
    await takeover.async_flush_registries(self._hass)
```
Catch 2: after the final `await self._store.async_save(self._data_to_save())`, schedule `self._entry.async_create_background_task(self._hass, self._async_replay_catch(ids), name=f"{DOMAIN} replay catch")`; the coroutine sleeps `takeover.REPLAY_QUIET_SECONDS` (read at call time), takes `self._lock`, re-checks `self._running`, runs the helper for every native owned device and native mirror (guarded by `legacy_device(...) is not None`). Never sleep inside `async_start` (holds the lock). Log fixed text only:
```python
LOGGER.warning("The native takeover of a device raised an unexpected error")
```
Followers publish nothing (T-5-02); owned ids only for any publish.

### `takeover.py`: `async_remove_replay_twins` (new)

**Analog:** `async_take_over` (107-160). Reuse `legacy_device`, `_legacy_entries`, `entity_sources`, `_carries_the_identity`, `is_legacy_entity`. Skip `_async_wait_unloaded` (a loaded replay would time out):
```python
if (device := legacy_device(hass, mqtt_entry_id, target.device_id)) is None:
    return TakeoverStatus.NOTHING
...
loaded = entity_sources(hass)
for legacy in entries:
    if (twin_id := entity_registry.async_get_entity_id(legacy.domain, DOMAIN, legacy.unique_id)) is not None:
        twin = entity_registry.entities[twin_id]
        if twin_id not in loaded and _carries_the_identity(legacy, twin):
            entity_registry.async_remove(twin_id)
        else:
            entity_registry.async_remove(legacy.entity_id)
            continue
    entity_registry.async_update_entity_platform(legacy.entity_id, DOMAIN, new_config_entry_id=entry.entry_id,
        new_config_subentry_id=UNDEFINED if target.subentry_id is None else target.subentry_id)
```
New rule: a replayed (newer, uncustomized) legacy entry loses when `_carries_the_identity(legacy, twin)` is False, even if loaded; entries without a twin are moved as before. Then remove the emptied legacy device, keeping the leftovers rule:
```python
leftovers = [r for r in er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True)
             if r.config_entry_id == mqtt_entry_id]
if leftovers: LOGGER.warning("Device %r keeps its MQTT device: ...", _short(target)); return TakeoverStatus.DONE
```
Registry-only; never import or publish MQTT. Never remove a loaded native entity (cutover) or a foreign MQTT entity.

### Tests (IN-02, IN-03)

**Analog:** `tests/test_native_start.py` (helpers `_setup`, `_restart`, `_manager`, `_seed_native`, `_loop_back_discovery`, `fast_takeover`) and `tests/test_takeover.py` (`setup_legacy_device`, `legacy_entity_ids`, `_deliver`). Unit tier, no `make_instance` (so no `multi_instance` marker needed).

`fast_takeover` pattern for the new constant (put as autouse in `tests/conftest.py`):
```python
@pytest.fixture(autouse=True)
def fast_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(takeover, "TAKEOVER_RETRY_INTERVAL", 0.01)
```
Replay delivery: always `retain=False`:
```python
async def _deliver(hass, topic, payload):
    async_fire_mqtt_message(hass, topic, payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
```
Owner-pass setup (test_native_start.py:135-195): `setup_legacy_device`, unload entry, `_seed_native(hass_storage, pending=[device_id])`, `mqtt_mock.async_publish.reset_mock()`, setup again. For IN-03 do NOT call `_loop_back_discovery` (green on v1.0.0); monkeypatch `DiscoveryPublisher.async_clear_device` to fire the replay before (and in a second case after) calling the original. IN-02: use the recipe in RESEARCH "Code Examples" (changed content plus ASCII pad key so `len(payload.encode()) == MAX_DOCUMENT_BYTES`; restart; assert `is_native`, `unsubscribe_test is None`, `schedule_reload` not called). TDD: `test:` commit red on v1.0.0, then `fix:`. Existing exact publish assertion `[migrate, clear]` (test_native_start.py:189-192) must stay green, so the helper publishes nothing when no legacy device exists.

### `README.md` and `tests/test_docs.py`

Remove the size-limit and replay bullets at ~351-352; keep the phrases pinned in `test_readme_limitations_are_current` (test_docs.py:377-388). Optionally add a negative phrase check.

## Shared Patterns

- **Store additive key, no version bump; malformed values fall back to defaults** (manager.py `_parse_native`): apply to the new `mirrors` set.
- **Id trust boundary:** `isinstance(str)` plus `is_valid_device_id` plus `MAX_MIRRORS` cap.
- **Publish only for owned ids (T-5-02):** the catch and all follower paths never publish.
- **Identity filter (T-5-01, WR-04):** `is_legacy_entity` and `_carries_the_identity` for any registry removal.
- **Log hygiene:** fixed strings, no registry or broker content.
- **Background work:** `entry.async_create_background_task`, never `asyncio.create_task`.

## No Analog Found

None. The event-driven registry watcher (optional hardening) has no analog and is not locked.

## Metadata

**Analog search scope:** `custom_components/mqtt_actions/`, `tests/`
**Files scanned:** manager.py, takeover.py, document.py, test_takeover.py, test_native_start.py (plus CONTEXT and RESEARCH)
**Pattern extraction date:** 2026-10-04
