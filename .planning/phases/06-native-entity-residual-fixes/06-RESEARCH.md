# Phase 6: Native Entity Residual Fixes - Research

**Researched:** 2026-10-04
**Domain:** Home Assistant custom integration internals (Store persistence, entity/device registry takeover, core MQTT discovery behavior), pytest-homeassistant-custom-component test design
**Confidence:** HIGH for IN-02, HIGH for the IN-03 core-behavior facts (reproduced on the installed HA 2026.9.4), MEDIUM for the production race itself

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### IN-02: where the native flag lives
- **D-01:** The native flag of a mirror is persisted as a set of mirror device ids in `STORE_NATIVE` (new field in `NativeState`, next to `pending` and `devices`), not in the stored payload. Parsed with `_parse_native` and `is_valid_device_id`. Additive Store key, no version bump (as in 04-05 and D-09 of Phase 5). Reserving headroom in the size cap is rejected: it contradicts success criterion 1.
- **D-02:** Loading: a mirror is native if its id is in the set OR its stored payload carries the v1.0.0 marker, so v1.0.0 Stores stay native. Only the set is written from now on; `with_native_marker` (`document.py:188`) stops being the persistence path and is removed. The first save moves old marker-only mirrors into the set.

#### IN-02: lifecycle of the flag
- **D-03:** An id leaves the set only when the mirror ends: device deleted, adoption (it becomes owned, then `NativeState.devices` applies) or release. A document without the marker never resets it (T-5-11 stays). A re-pin to another owner keeps the flag only if that owner's document carries the marker.

#### IN-03: strategy against the replay
- **D-04:** Keep the order migrate payload, registry takeover, retained clear (D-12 of Phase 5; a clear before the move deletes the legacy registry entries, T-5-08). The fix is a duplicate catch after the move: new `mqtt`-platform entities of the device id are detected and removed or merged so the migrated entities keep their registry ids and entity ids. Reuse the twin logic and `_carries_the_identity` in `takeover.py`. Waiting for the MQTT discovery queue is rejected: core exposes no public settle signal.
- **D-05:** The catch runs twice: right after the move (before the clear is published) and again after the retained clear (after a short quiet period), because the replay can arrive in the window between them.

#### Tests
- **D-06:** The IN-03 test delivers the replay by replacing `async_clear_device` (or the gateway publish) with a variant that plays the retained legacy Discovery via `async_fire_mqtt_message` just before the clear. Deterministic, no production hook. The window is exactly the call before the clear.
- **D-07:** TDD, one failing-test commit per fix first (`test:`), then the fix (`fix:`). The IN-02 test is a Store round trip with a document exactly at `MAX_DOCUMENT_BYTES`: after a restart it is native, starts no test-topic subscription and causes no extra reload on the next document. Both tests must be red on v1.0.0 code; the existing takeover, native-entity and cutover suites stay green.

### Claude's Discretion
- Exact names and placement of the new `NativeState` field and the duplicate-catch helper.
- Length of the quiet period before the second catch, and whether a Multi-Instance test is added on top of the unit test (not required).
- Wording of the README change (criterion 4) and of any log line for a removed duplicate (no registry or broker content in logs).

### Deferred Ideas (OUT OF SCOPE)
None - discussion stayed within phase scope. (WR-03, authenticating the cutover gate, and backlog 999.1 remain later work.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MIG-04 | A native mirror stays native after a restart, even when its config document is close to `MAX_DOCUMENT_BYTES` (IN-02) | Root cause pinned to `with_native_marker` + `_mirror_info` + `_build_mirror`; set-in-`NativeState` design, lifecycle hooks, exact-limit test recipe, Store-compat constraint (existing exact-dict assertions in `tests/test_cutover.py`) |
| MIG-05 | The takeover creates no duplicate when core MQTT replays retained legacy Discovery during startup (IN-03); a test delivers the replay between the registry move and the retained clear | Reproduced on HA 2026.9.4: what core does with a replay and a clear, which test harness is red on v1.0.0, how to remove loaded twins, scope gap for UAT-02 |
</phase_requirements>

## Summary

Phase 6 is two small, local code fixes plus two regression tests and a README edit; no new dependency. **IN-02:** `with_native_marker` returns the unmarked payload when the marker (20 bytes) no longer fits under `MAX_DOCUMENT_BYTES`, so the stored copy of a native mirror loses its only persistent native flag and `_build_mirror` rebuilds it as legacy after a restart. The fix (D-01..D-03) moves the flag to a persisted id set in `NativeState`, read at `_build_mirror` and written in `_data_to_save`, with `with_native_marker` deleted.

**IN-03:** the fix design (D-04/D-05) is feasible, but the research found three things the planner must act on. (1) On HA 2026.9.4 a replay *immediately before* a **live** retained clear is already cleaned by core itself: the clear removes the replayed `_2` twins and their registry entries (reproduced). A test built exactly as D-06 says is therefore only red on v1.0.0 if the clear does **not** reach core as a live message, which is what the default `mqtt_mock` does (it loops the retained clear back as a retained message, and core drops a second retained message per topic). The genuine residual is a replay processed **after** the clear. Success criterion 3 ("red on v1.0.0") is met by the two harness variants in the Validation Architecture section, both reproduced as red. (2) Removing the registry entry of a **loaded** `mqtt` twin makes core publish an empty retained payload on the discovery topic (observed three times, once per entity). That is harmless for an owner (it is the same message as its own clear) but a follower must never publish a migrate payload (T-5-02), so the catch removes loaded twins directly instead of "migrate, wait, remove". (3) `_async_native_takeover` only passes over `pending` owned devices and native mirrors, so a **non-pending native owner** never gets a catch at all; UAT-02 ("re-published retained legacy Discovery plus two restarts") and criterion 4 (boot-time replay residual removed from the README) need the second catch to cover every native device on every start.

CONTEXT D-03 also contains a sentence that contradicts the chosen discussion option (see Open Question 1).

**Primary recommendation:** Add `NativeState.mirrors` (written only when non-empty, so the exact-dict assertions in `tests/test_cutover.py` stay green), feed it into `_mirror_info(keep_native=...)` at `_build_mirror`, delete `with_native_marker`; add `takeover.async_remove_replay_twins` (no waiting, removes loaded `mqtt` twins whose identity is already held by a moved entry, then the emptied legacy device) and call it right after the move and again from a background task after a quiet period under the manager lock; write the IN-02 test as a live-path restart round trip and the IN-03 tests as before-clear and after-clear variants with the default (non-loop-back) `mqtt_mock`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist native flag of mirrors | Integration Store (`Manager._data_to_save` / `_parse_native`) | - | Local per-instance state, never part of a document or hash (existing `STORE_NATIVE` contract) |
| Decide a mirror is native at start | `Manager._build_mirror` / `_mirror_info` | `Manager.is_native` | One choke point decides test-topic subscription and reload behavior |
| Detect and remove replay twins | `takeover.py` (registry logic only, never publishes) | `Manager._async_native_takeover` (orchestration, lock, scheduling) | `takeover.py` header: "registry logic only: it never publishes"; the manager owns broker order |
| Retained clear / migrate publish | `DiscoveryPublisher` via `Manager` (owners only) | - | T-5-02: publish only for owned ids |
| Replay of retained legacy Discovery | Core MQTT integration (HA core) | Broker | Outside this repo; only observable through the registries |
| Documentation of residuals | README Limitations | `tests/test_docs.py` | Pinned phrases test must stay green |

## Standard Stack

No new packages. Everything below is already installed and pinned.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Home Assistant core | 2026.9.4 (installed in `.venv`) | Entity/device registry, Store, core MQTT discovery | Project platform [VERIFIED: `.venv/bin/python -c "import homeassistant.const"` printed `2026.9.4`] |
| pytest-homeassistant-custom-component | 0.13.367 | `hass`, `mqtt_mock`, `async_fire_mqtt_message`, `hass_storage` | Project test harness [VERIFIED: `pip list` output and `pyproject.toml` `dev` group] |
| Ruff | 0.16.10 | Lint/format, 120 columns | `.venv/bin/ruff --version` printed `ruff 0.16.10`; `ruff check custom_components tests` passed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Persisted id set (D-01) | Derive the set from live mirrors at every save | Rejected by the user in the discussion ("Derive on every save" was an unchosen option) |
| Direct removal of loaded twins | Migrate payload, wait for unload, then `async_take_over` again | Needs a publish, forbidden for followers (T-5-02); also costs up to `TAKEOVER_UNLOAD_TIMEOUT` (10 s) of waiting |
| Time-based second catch (D-05) | Entity-registry event watcher (`entity_registry_updated`, action `create`, platform `mqtt`) | Event-driven would also catch a replay from a legacy peer minutes later; not locked, so only an optional hardening |

**Installation:** none. **Package Legitimacy Audit:** not applicable, this phase installs no external package (no `gsd-tools package-legitimacy` run needed).

## Architecture Patterns

### System Architecture Diagram

```
HA start / entry reload
  -> Manager.async_start (holds self._lock)
       -> _async_restore_mirrors -> _build_mirror(parsed)            [IN-02: native = marker OR id in NativeState.mirrors]
       -> _async_native_takeover
            owned = pending & devices ; mirrors = native mirrors with a legacy MQTT device
            1. publish migrate (owners only, live, not retained)
            2. takeover.async_take_over per target (registry move)    --> DONE | DEFERRED | NOTHING
            3. [CATCH 1] for DONE targets: remove replay twins        [IN-03, new]
            4. takeover.async_flush_registries
            5. _async_finish_takeover -> publish retained clear (owners only)
            6. save Store
            7. [CATCH 2] schedule background task: sleep(quiet) -> take lock -> remove replay twins  [IN-03, new]
       -> _async_publish_owned, availability, heartbeat

Core MQTT (outside repo): replay of retained legacy Discovery can land at any point
  after step 2: creates NEW registry entries platform "mqtt" (entity ids *_2), loaded, new MQTT device
  a LIVE empty retained payload for the topic: removes the loaded twins and their registry entries
```

### Recommended Project Structure
```
custom_components/mqtt_actions/
├── const.py        # update the STORE_NATIVE comment (lines 137-139) for the new key
├── document.py     # delete with_native_marker (188-204) and its unused imports if any
├── manager.py      # NativeState, _parse_native, _data_to_save, _build_mirror, _mirror_info, lifecycle hooks, catch calls
└── takeover.py     # async_remove_replay_twins (new), REPLAY_QUIET_SECONDS (new)
tests/
├── test_native_start.py or new tests/test_native_residuals.py   # the two regression tests (unit tier, no make_instance)
└── test_docs.py    # optional: assert the removed residual sentences stay removed
README.md           # Limitations bullet at lines 351-352 removed
```

### Pattern 1: Persisted native-mirror id set (IN-02)

**What:** Extend the existing additive Store dict, exactly like `pending` and `devices`.
**Current code to change** [VERIFIED: manager.py:310-343, read this session]:
```python
@dataclass(slots=True)
class NativeState:
    """The persisted native switch of this instance (D-03): the instance flag and two sets of owned device ids."""

    instance: bool = False
    pending: set[str] = field(default_factory=set)
    devices: set[str] = field(default_factory=set)
```
```python
def _parse_native(stored: dict[str, Any]) -> NativeState:
    ...
    native = stored.get(STORE_NATIVE)
    if not isinstance(native, dict):
        return NativeState()
    instance = native.get("instance")
    pending = native.get("pending")
    devices = native.get("devices")
```
**Why the persisted flag is lost today** [VERIFIED: document.py:188-204 and manager.py:1796-1818, read this session]:
```python
    marked = canonical_json(value)
    return marked if len(marked.encode(errors="replace")) <= MAX_DOCUMENT_BYTES else payload
```
```python
        carried = keep_native and not parsed.native
        ...
            payload=with_native_marker(parsed.payload) if carried else parsed.payload,
            ...
            native=parsed.native or keep_native,
```
and `_build_mirror` calls `mirror=self._mirror_info(parsed)` with no `keep_native` (manager.py:1836), so after a restart `native` is `parsed.native` only.
**Shape of the fix (names are the planner's discretion):**
```python
@dataclass(slots=True)
class NativeState:
    instance: bool = False
    pending: set[str] = field(default_factory=set)
    devices: set[str] = field(default_factory=set)
    mirrors: set[str] = field(default_factory=set)   # native mirror ids (D-01)

# _parse_native: same comprehension as devices, plus a cap: ids beyond MAX_MIRRORS are dropped (Store is untrusted)
# _data_to_save: write "mirrors" ONLY when non-empty (see Pitfall 1)
# _build_mirror: mirror=self._mirror_info(parsed, keep_native=parsed.device_id in self._native.mirrors)
# _mirror_info:  payload=parsed.payload (always as received); native=parsed.native or keep_native
```
**Single choke point for adding an id:** after every place a mirror record is created or replaced (`_build_mirror` result registered by `_async_subscribe_mirror` / `_async_restore_mirrors`, `async_apply_mirror` branches, `_update_mirror`), call one helper that does `if device.mirror.native: self._native.mirrors.add(id)`. All three live branches already call `_schedule_save()`. `_async_restore_mirrors` is the "first save moves old marker-only mirrors into the set" path (D-02): adding there is enough, the final save at stop persists it.
**Lifecycle (D-03):** remove the id in `async_remove_mirror` (tombstone, prune), in `_async_drop_mirror` (adoption; `_native_devices` already takes over for `info.native`, manager.py:1394-1395), and prune the set to `self.mirrors.keys()` right after `_async_restore_mirrors(current)` in `async_start` next to the other start-time prunes (manager.py:765-775), so an id whose cached payload no longer parses or whose device became owned cannot linger. A stale id is dangerous: `async_apply_mirror` builds a brand-new mirror through `_build_mirror`, and a stale id would turn a legacy mirror native without any marker (T-5-03 class risk).

### Pattern 2: Replay-twin catch (IN-03)

**What:** A registry-only helper in `takeover.py` that, for a device id that was just moved, finds the **new** legacy `mqtt` device core created from a replay and removes its duplicate entries and the emptied device. It reuses `legacy_device`, `_legacy_entries`, `_carries_the_identity` and the identity filter `is_legacy_entity` (T-5-01).

**Verified core behavior (reproduced with scratch tests on HA 2026.9.4, scratch file deleted afterwards, repo clean):**

| Scenario (owner pass, `pending=[id]`) | Final registry on v1.0.0 |
|---|---|
| Replay fired just before the clear, clear delivered **live** (`_loop_back_discovery`) | clean: core removed the `_2` twins itself. Transient `*_2` entities and states exist for a moment (`Registered new switch.mqtt entity: switch.lamp_2`, then `Removing component: switch.lamp_2`) |
| Replay fired just before the clear, default `mqtt_mock` (clear loops back **retained** and core drops it) | `switch.lamp_2`, `button.lamp_test_on_2`, `button.lamp_test_off_2` stay, platform `mqtt`, loaded; second MQTT device stays |
| Replay fired right **after** the clear (live clear) | same three twins stay |
| No replay | clean |

[VERIFIED: scratch test run this session, outputs `FINAL[before_loop]`, `FINAL[before_noloop]`, `FINAL[after_loop]`, `FINAL[none]`]

Removing the registry entry of a loaded twin: the entity disappears from the state machine and core publishes an empty retained payload on the discovery topic, once per removed entity, but it leaves the newly created `mqtt` device behind, so the helper must remove that device itself [VERIFIED: scratch test, `PUBLISHES after removing loaded twins` listed three `('homeassistant/device/<id>/config', None, True)` and the `('mqtt', ...)` device was still present afterwards; core source `async_removed_from_registry` -> `async_remove_discovery_payload` publishes `None` retained, `components/mqtt/entity.py:1211-1220,758-767`].

**Recommended helper behavior:**
1. `device = legacy_device(hass, mqtt_entry_id, device_id)`; return NOTHING when absent (so the common case does no work and publishes nothing; the existing exact-publish assertion `[migrate, clear]` in `tests/test_native_start.py:189-192` stays green).
2. For each `_legacy_entries(...)` entry with a twin under `DOMAIN` (`entity_registry.async_get_entity_id(legacy.domain, DOMAIN, legacy.unique_id)`): remove the legacy entry whenever `_carries_the_identity(legacy, twin)` is False; a replayed entry is newer and uncustomized, so it loses. Do **not** wait for it to unload (the existing `_async_wait_unloaded` would time out and return DEFERRED for a loaded replay).
3. An entry **without** a twin keeps today's behavior (it is moved), so a replay can never cost the user an identity.
4. Remove the emptied legacy device; keep the existing "leftovers keep the device" rule (`takeover.py:131-139`).
5. Never import or publish MQTT; never publish a migrate for a mirror.
6. Log at most a fixed line plus a count; no registry or broker content (CONTEXT discretion note).

The cleanest implementation is `async_take_over(..., allow_loaded=True)` (skip `_async_wait_unloaded`) or a small sibling function that shares the duplicate branch; either way keep the branch condition `twin_id not in loaded and _carries_the_identity(legacy, twin)` so a loaded **native** entity (cutover on a running instance) is never removed in favor of a replayed one. [VERIFIED: takeover.py:107-160, read this session]

**Where the catches go (manager.py `_async_native_takeover`, lines 873-933 read):**
- **Catch 1:** inside the `for target, status in zip(targets, results)` loop for `DONE` targets, and before `async_flush_registries` (which currently sits at line 918, before the loop). Move the flush after the catch, or flush again when the catch removed something, so the registry files hold both the move and the removal before the clear goes out (WR-01).
- **Catch 2:** after `await self._store.async_save(...)` at the end of the pass, create one background task `self._entry.async_create_background_task(self._hass, self._async_replay_catch(device_ids), name=f"{DOMAIN} replay catch")` (the same pattern as `_start_cutover_check`, manager.py:820). The coroutine sleeps `takeover.REPLAY_QUIET_SECONDS`, then `async with self._lock:` re-checks `self._running` and runs the helper for each id. Do not sleep inside `async_start`: it holds `self._lock` and would delay every publish.
- Core's own cooldown is `DISCOVERY_COOLDOWN = 5` seconds [VERIFIED: `homeassistant/components/mqtt/client.py:100`]; 5.0 s is a reasonable production default. Tests set the constant near zero.

**Scope gap to resolve (see Open Question 2):** `owned = sorted(self._native_pending & self.devices.keys())` (manager.py:884) means a native owner whose pass finished never reaches the catch on later starts; only native mirrors are re-scanned every start (manager.py:888-895). UAT-02 re-publishes retained legacy Discovery and restarts twice on a finished instance. Recommended: Catch 2 iterates over **all** `is_native` owned devices and native mirrors, guarded by the cheap `legacy_device(...) is not None` check.

### Pattern 3: Test harness for the two regression tests

See Validation Architecture for the exact recipes.

### Anti-Patterns to Avoid
- **Writing `mirrors: []` into the Store when empty.** `tests/test_cutover.py` compares the whole dict (see Pitfall 1).
- **Calling a migrate publish for a mirror in the catch.** A follower publishes nothing (T-5-02); a migrate would unload the entities of every core MQTT instance on the broker.
- **Sleeping under the manager lock** for the quiet period.
- **Replaying with `retain=True` in a test on a topic core already saw retained.** Core drops the second retained message per subscription and topic [VERIFIED: `components/mqtt/client.py:1348-1353`, and the repo's own note in `tests/test_native_start.py:66-72`]; the replay then creates nothing and the test goes green for the wrong reason. Use `retain=False`, as `tests/test_takeover.py::_deliver` does.
- **Using `_loop_back_discovery` in the IN-03 test** and expecting red on v1.0.0 (see table above).
- **Deriving the persisted set from live mirrors at save time.** Explicitly rejected by the user; do not "simplify" to it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Which of two registry entries keeps the identity | New heuristics | `_carries_the_identity`, `_is_customized` in `takeover.py` | WR-04 already pinned by `test_an_existing_native_twin_never_replaces_the_legacy_identity` and `test_a_customized_native_twin_is_kept_over_an_untouched_legacy_entry` |
| Recognising a legacy entry of this integration | Unique-id matching alone | `is_legacy_entity` | T-5-01: platform, entry, device, domain and unique-id shape must all match |
| Waiting for core MQTT to settle | Polling `hass.data[DATA_MQTT].last_discovery` | Nothing; D-04 rejects it | Internal core state, not public API |
| Flushing registries | New writer | `takeover.async_flush_registries` | Already isolated, best effort |
| Device id validation for the new Store set | New regex | `is_valid_device_id` (already used by `_parse_native`) | Same trust boundary |
| Delayed work with cleanup on unload | `asyncio.create_task` | `entry.async_create_background_task` | Cancelled with the entry; `async_block_till_done(wait_background_tasks=True)` waits for it in tests |

**Key insight:** every primitive needed already exists; the phase is wiring plus two harness decisions.

## Common Pitfalls

### Pitfall 1: The new Store key breaks exact-dict assertions
**What goes wrong:** `tests/test_cutover.py:157, 640, 653, 663` assert `_stored_native(hass_storage) == {"instance": True, "pending": [...], "devices": []}` [CITED: grep of tests/test_cutover.py]. An always-written `"mirrors": []` turns four existing tests red.
**How to avoid:** write `mirrors` only when the set is non-empty, and keep the existing `if self._native != NativeState()` gate semantics (the dataclass equality now includes `mirrors`).
**Warning signs:** `KeyError`/`AssertionError` on `_stored_native` in the cutover suite.

### Pitfall 2: The IN-03 test is green on v1.0.0
**What goes wrong:** with a live clear the replayed twins are removed by core, so a test that only asserts the final registry passes on the old code, violating success criterion 3.
**How to avoid:** use the default `mqtt_mock` (no `_loop_back_discovery`), where the migrate payload still reaches core live but the retained clear is dropped, or fire the replay after the clear. Run both new tests against the pre-fix code and record the red output in the `test:` commit message.
**Warning signs:** the "red" commit passes.

### Pitfall 3: A retained replay is silently ignored by core
See Anti-Patterns. Always `retain=False` for the replay in tests.

### Pitfall 4: The IN-02 "at the limit" test never reaches the bug
**What goes wrong:** the stored payload only loses the marker via the live path: a marked document makes the mirror native, then a later **changed-content** unmarked document of exactly `MAX_DOCUMENT_BYTES` arrives. Extra top-level keys are ignored and never hashed (`parse_document` docstring, document.py:411-418), so padding alone does not change the content hash and the document would not even be applied (`sync.py:484` compares `content_hash`).
**How to avoid:** change the content (for example the actions or the name) **and** pad with an ASCII `pad` key up to exactly `MAX_DOCUMENT_BYTES` bytes. The marker costs 20 bytes (`,"entities":"native"`), so any unmarked canonical payload larger than `MAX_DOCUMENT_BYTES - 20` bytes cannot be marked. Assert `len(payload.encode()) == MAX_DOCUMENT_BYTES` in the test so a future change to canonicalization fails loudly.

### Pitfall 5: A stale id in the native-mirror set
**What goes wrong:** an id left behind after a mirror ended makes a later, unmarked mirror of that id native (see Pattern 1 lifecycle).
**How to avoid:** the three removal points plus the start-time prune, and a unit test for each (tombstone, adoption, restore of an owned id).

### Pitfall 6: Catch 2 slows or hangs the suite
**What goes wrong:** `async_block_till_done(wait_background_tasks=True)` waits for the quiet-period sleep, so a 5 s production constant adds 5 s to every test that runs a takeover pass (many files: `test_native_start.py`, `test_cutover.py`, `test_takeover.py` users, `test_native_cleanup.py`).
**How to avoid:** put an autouse fixture in `tests/conftest.py` that monkeypatches `takeover.REPLAY_QUIET_SECONDS` to a few milliseconds (the existing per-file `fast_takeover` fixtures patch `TAKEOVER_RETRY_INTERVAL` the same way, test_native_start.py:126-129), read the constant at call time (not as a default argument).

### Pitfall 7: The catch removes something it must not
**What goes wrong:** removing a **loaded native** entity, or an entry of a foreign MQTT device with the same unique id.
**How to avoid:** the identity filter plus `twin_id not in loaded` branch (Pattern 2); keep `test_a_foreign_mqtt_entity_with_the_same_unique_id_is_left_alone` green.

## Code Examples

### IN-02 regression test recipe (live path, name-independent of the new Store key)
```python
# Sources: tests/documents.py (document_payload with tamper=), tests/test_cutover.py:692-698 (reload spy),
#          tests/test_native_start.py:114-120 (_restart), tests/test_native_entities.py:606-612 (_deliver)
spec = make_spec(name="Foreign lamp", on=ON_ACTIONS)
changed = make_spec(device_id=spec.device_id, name="Foreign lamp", on=NEW_ACTIONS)   # content must change
entry = await _setup(hass, make_hub_entry())
await _presence(hass, "online")
await _deliver(hass, spec.device_id, document_payload(spec, native=True))           # mirror becomes native
unpadded = document_payload(changed, rev=2)                                          # no marker
pad = MAX_DOCUMENT_BYTES - len(unpadded.encode())
at_limit = document_payload(changed, rev=2, tamper=lambda doc: doc.update(pad="x" * (pad - len(',"pad":""'))))
assert len(at_limit.encode()) == MAX_DOCUMENT_BYTES                                  # exact; adjust by the key overhead
await _deliver(hass, spec.device_id, at_limit, retain=False)
assert _manager(entry).is_native(spec.device_id)

await _restart(hass, entry)                                                          # Store round trip
manager = _manager(entry)
assert manager.is_native(spec.device_id)
assert manager.mirrors[spec.device_id].unsubscribe_test is None                      # no test-topic subscription
with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
    await _deliver(hass, spec.device_id, document_payload(changed, rev=3, native=True), retain=False)
schedule_reload.assert_not_called()                                                  # no extra reload
```
On v1.0.0 the restart rebuilds the mirror as legacy (`is_native` False, `unsubscribe_test` set, and the marked document triggers `_follow_native_status` with `was_native=False`, which schedules a reload). The `pad` arithmetic must be computed against the real canonical output; `serialize_document` is `canonical_json` so keys are sorted and the pad key's position does not change the size.

### IN-03 regression test recipe (D-06 hook on the publisher clear)
```python
# Sources: tests/test_native_start.py:135-195 (owner pass), tests/test_takeover.py:57-83 (setup_legacy_device)
legacy = await setup_legacy_device(hass, mqtt_mock, make_hub_entry, make_switch_subentry)
device_id = legacy.device_id
before = {e: er.async_get(hass).async_get(e) for e in legacy_entity_ids(hass, device_id)}   # 3 entries
assert await hass.config_entries.async_unload(legacy.entry.entry_id)
await hass.async_block_till_done(wait_background_tasks=True)
_seed_native(hass_storage, pending=[device_id])
mqtt_mock.async_publish.reset_mock()          # NOTE: no _loop_back_discovery(...)
original = DiscoveryPublisher.async_clear_device

async def clear_with_replay(self, did):
    async_fire_mqtt_message(hass, legacy.topic, legacy.payload, retain=False)   # retain=False, see Pitfall 3
    await hass.async_block_till_done(wait_background_tasks=True)
    await original(self, did)

monkeypatch.setattr(DiscoveryPublisher, "async_clear_device", clear_with_replay)
assert await hass.config_entries.async_setup(legacy.entry.entry_id)
await hass.async_block_till_done(wait_background_tasks=True)

assert legacy_entity_ids(hass, device_id) == []                    # no platform "mqtt" twin left (red on v1.0.0: 3 left)
for entity_id, old in before.items():                              # identities kept
    moved = er.async_get(hass).async_get(entity_id)
    assert moved is not None and (moved.id, moved.platform) == (old.id, DOMAIN)
assert hass.states.get("switch.lamp_2") is None
```
Add a second parametrization where the replay is fired **after** `await original(self, did)` (and with `_loop_back_discovery` so the clear is live): that is the residual that exists on a real broker and it is also red on v1.0.0. To exercise Catch 1 specifically, wrap `takeover.async_take_over` (the manager calls it as `takeover.async_take_over`, manager.py:943) to fire the replay right after the original returns.

### Store parse sketch
```python
mirrors = native.get("mirrors")
... mirrors={item for item in mirrors if isinstance(item, str) and is_valid_device_id(item)}
    if isinstance(mirrors, list) else set()   # then cap at MAX_MIRRORS
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Native flag carried inside the stored mirror payload (v1.0.0, T-5-11) | Native flag in the Store `native` dict, payload stored as received | This phase | The size cap can no longer drop the flag; stored payload is byte-identical to what the broker delivered |
| Duplicates cleaned only at the next takeover pass (`test_a_late_replay_duplicate_is_cleaned_at_the_next_call`) | Cleaned right after the move and after a quiet period | This phase | README "next start cleans it up" residual goes |

**Deprecated/outdated:** `with_native_marker` (delete; no test references it, grep over `tests/` found none).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | In production a replay that precedes the clear is always cleaned by core, so the real residual is "replay after the clear" (legacy peer healing, re-published retained Discovery). Core's per-hash pending queue keeps order, but the real race against `async_wait_for_mqtt_client` was not reproduced on a broker | Summary, Pattern 2 | Low: the fix covers both orders; only the explanation changes |
| A2 | Direct removal of loaded replay twins by a follower (empty retained publish by core) is acceptable because a native mirror's owner is native, so the topic holds only stale legacy Discovery | Pattern 2 | Medium: a v0.1.x peer that still shows entities for that device would lose them (it already loses them at the owner's clear). Confirm with the user |
| A3 | 5.0 s is a sensible production quiet period (core's `DISCOVERY_COOLDOWN` is 5) | Pattern 2 | Low |
| A4 | D-03's last sentence is a slip from the unchosen "Also reset on owner change" option; the safe reading is that a re-pin keeps the flag when the mirror was native (current v1.0.0 behavior, `keep_native=was_native`) | Open Question 1 | Medium: the literal reading would let a re-pin to an unmarked document demote a native mirror, which T-5-11 forbids |
| A5 | Catch 2 should cover all native devices on every start (not only pending ones and native mirrors) so UAT-02 passes | Pattern 2, Open Question 2 | Medium: without it UAT-02 on a finished owner would show `_2` duplicates in Phase 8 |

## Open Questions

1. **D-03 vs the discussion log**
   - What we know: the discussion log shows the chosen option "Only at mirror end (Delete, adoption, release remove the id; no marker never resets)" and the *unchosen* "Also reset on owner change (Re-derive from the new owner's marker)". D-03's final sentence ("A re-pin to another owner keeps the flag only if that owner's document carries the marker") reads like the unchosen option. Current code keeps native across a same-content re-pin (`manager.py:1289-1291`) and across changed content (`_update_mirror`, manager.py:1850).
   - What's unclear: whether the user wants re-pin demotion.
   - Recommendation: implement the chosen option (sticky, id leaves only at mirror end) and ask the user one question in plan review. Do not change the re-pin branches in this phase unless confirmed.

2. **Scope of Catch 2 (UAT-02)**
   - What we know: only pending owned devices and native mirrors are visited at start.
   - Recommendation: visit every native owned device and native mirror in Catch 2, guarded by `legacy_device(...)`; Catch 1 stays limited to the devices the pass moved. Cheap registry lookups, no publish unless a twin exists.

3. **Follower removal of loaded twins** (A2): confirm the empty retained publish by core is acceptable, or restrict followers to unloaded twins and leave loaded ones to the next start.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | tests | yes | 3.14.7 | - |
| uv | project workflow | yes | 0.12.7 | `.venv/bin/python -m pytest` works directly |
| Ruff | lint gate | yes | 0.16.10 | - |
| Mosquitto | `broker` tier (`tests/broker`) | yes | `/usr/bin/mosquitto` | tier is skipped when absent |
| Full suite baseline | regression gate | yes | 1460 passed in 104 s (this session, clean tree) | - |

No missing dependencies.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 via pytest-homeassistant-custom-component 0.13.367, `asyncio_mode = "auto"` [VERIFIED: pyproject.toml read this session] |
| Config file | `pyproject.toml` (`--strict-markers`; markers `broker`, `multi_instance`) |
| Quick run command | `.venv/bin/python -m pytest tests/test_takeover.py tests/test_native_start.py tests/test_native_entities.py tests/test_native_cleanup.py tests/test_cutover.py -q` (about 10 s for the first two files measured: 42 passed in 5.6 s) |
| Full suite command | `.venv/bin/python -m pytest -q` (1460 passed, 104 s) plus `.venv/bin/ruff check custom_components tests` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MIG-04 | Native mirror at exactly `MAX_DOCUMENT_BYTES` stays native after a restart, no test-topic subscription, no reload on the next document | unit (hass, mqtt_mock) | `pytest tests/test_native_start.py -k at_the_size_limit -x` | Wave 0 (new test) |
| MIG-04 | `_parse_native` drops malformed/invalid ids in `mirrors`, caps at `MAX_MIRRORS`; v1.0.0 Store (marker-only payload, no key) still loads native | unit | `pytest tests/test_native_start.py -k native_mirror_set -x` | Wave 0 |
| MIG-04 | Set lifecycle: id removed on tombstone/prune, adoption, restore of an owned id; marker-only mirror is moved into the set at the first save | unit | `pytest tests/test_native_start.py -k native_mirror_set -x` | Wave 0 |
| MIG-04 | Store shape: `mirrors` written only when non-empty; existing cutover dict assertions stay | unit | `pytest tests/test_cutover.py -x` | exists |
| MIG-05 | Replay just before the clear (clear not processed by core): no `mqtt` twin, ids kept, no `_2` state | unit | `pytest tests/test_native_start.py -k replay -x` | Wave 0 |
| MIG-05 | Replay after the clear: removed after the quiet period | unit | same | Wave 0 |
| MIG-05 | Replay between move and Catch 1 (wrap `takeover.async_take_over`) | unit | same | Wave 0 |
| MIG-05 | Native mirror (follower) variant: no migrate/clear published, loaded twins removed | unit | same | Wave 0 |
| MIG-05 | A finished native owner (not pending) with a replay at the next start is cleaned (only if Open Question 2 is accepted) | unit | same | Wave 0 |
| MIG-05 | Helper unit tests in `tests/test_takeover.py`: loaded replay twin removed with its device, customized twin kept, foreign MQTT entity untouched, no legacy device is a no-op that publishes nothing | unit | `pytest tests/test_takeover.py -x` | Wave 0 additions |
| Criterion 4 | README Limitations no longer mentions the size-limit and boot-time replay residuals | doc test | `pytest tests/test_docs.py -x` | exists; add a negative phrase check |
| Criterion 3 | Existing takeover, native-entity and cutover suites green | regression | quick run above | exists |

### Red-on-v1.0.0 verification (criterion 3)
Run each new test on a checkout of the v1.0.0 production code (`git stash` the fix or run the `test:` commit alone) and capture the failure in the commit message. Known red/green facts from this session on HA 2026.9.4:
- before-clear replay, default `mqtt_mock`: **red** on v1.0.0 (three `mqtt` twins remain)
- before-clear replay with `_loop_back_discovery`: **green** on v1.0.0, do not use as the regression test
- after-clear replay (live clear): **red** on v1.0.0

### Sampling Rate
- **Per task commit:** the new test file or `-k` selection plus `tests/test_takeover.py`
- **Per wave merge:** quick run command (five files) plus `ruff check`
- **Phase gate:** full suite green and ruff clean before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] New tests listed above (two regression tests are the `test:` commits of the TDD flow, D-07)
- [ ] `tests/conftest.py`: autouse fixture that shrinks `takeover.REPLAY_QUIET_SECONDS`
- [ ] No new framework or fixtures beyond that. Modules that use `make_instance` need `pytestmark = pytest.mark.multi_instance` (`tests/test_repo_structure.py` enforces it); the planned tests do not use it.

## Security Domain

`security_enforcement` is enabled in `.planning/config.json` (ASVS level 1, block on high).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | - |
| V3 Session Management | no | - |
| V4 Access Control | yes | Publish only for owned ids (T-5-02): the catch never publishes; follower never publishes migrate/clear |
| V5 Input Validation | yes | The new Store set goes through `isinstance(str)` + `is_valid_device_id` + `MAX_MIRRORS` cap; payload still goes through `parse_document` |
| V6 Cryptography | no | - |
| V7 Error handling and logging | yes | Fixed log text, no registry or broker content (CONTEXT discretion note, existing pattern manager.py:921-924) |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hostile or large-but-valid owner document forces the mirror back to legacy (IN-02, T-5-11) | Tampering | Flag in the Store set, independent of payload size |
| Forged native marker flips followers (T-5-03) | Tampering | Unchanged: only the pinned owner's document is applied; the set is only written for mirrors already native |
| Stale set entry marks an unrelated legacy mirror native | Tampering | Remove at mirror end, prune at start, validate ids |
| Catch removes a foreign or customized entity (T-5-01, WR-04) | Tampering / Information loss | `is_legacy_entity` identity filter and `_carries_the_identity` |
| Catch publishes on another instance's topics (T-5-02) | Tampering | Registry-only helper; removal side effect is core's own empty retained discovery on a native device's legacy topic (Assumption A2) |
| Tampered local Store | Tampering | Treated as untrusted on load (existing practice) |

## Sources

### Primary (HIGH confidence)
- Repository source read this session: `manager.py` (255-404, 500-680, 740-1020, 1125-1574, 1700-1960), `takeover.py` (full), `document.py` (150-260, 405-470), `discovery.py` (150-260), `mqtt_gateway.py`, `sync.py` (440-520), `const.py` (60-70, 130-145)
- Installed HA core 2026.9.4 source: `components/mqtt/discovery.py` (discovery handling, pending queue), `components/mqtt/entity.py:758-767,1211-1220` (removal publishes empty retained), `components/mqtt/client.py:100,1348-1353` (cooldown, retained dedupe)
- Scratch tests run against the installed core (deleted afterwards; `git status` clean): replay before/after clear, loop-back vs default mock, removal of loaded twins and its publishes
- `.planning/milestones/v1.0-phases/05-*/05-REVIEW.md`, `05-REVIEW-DISPOSITION.md`, `05-SECURITY.md`, `05-RESEARCH.md` (Pitfall 5), `05-UAT.md`, `docs/adr/0001-*.md`
- `06-DISCUSSION-LOG.md` (alternatives not chosen)

### Secondary (MEDIUM confidence)
- Grep of test files for exact Store assertions (`tests/test_cutover.py`) and absence of `with_native_marker` references

### Tertiary (LOW confidence)
- None. No web research was needed; no external library is involved. The research-plan seam was not used because every question was answerable from the repo and the installed core.

## Project Constraints (from CLAUDE.md)

- Python 3.14, HA 2026.9.x, Ruff with `select = ["ALL"]` and 120 columns, `target-version py314`; tests with PHACC; no new runtime dependency.
- Use `entry.runtime_data`, not `hass.data[DOMAIN]`; no YAML config.
- Do not execute received actions without opt-in and validation (untouched by this phase).
- Code, commits and comments in English; chat and user-facing summary in German.
- GSD workflow: changes go through GSD commands; TDD mode is on (`workflow.tdd_mode: true`), so `test:` commit then `fix:` commit per fix (D-07).
- README is pinned by `tests/test_docs.py`: keep the phrases listed in `test_readme_limitations_are_current` (test_docs.py:377-388) when removing the bullet at README lines 351-352.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (no change, versions read from the venv)
- Architecture (IN-02): HIGH (code read end to end, one choke point)
- Architecture (IN-03): MEDIUM-HIGH (core behavior reproduced; the real boot race not reproduced on a broker, covered by UAT-02 in Phase 8)
- Pitfalls: HIGH (each one observed or read in code)

**Research date:** 2026-10-04
**Valid until:** 2026-11-03, or until the HA/PHACC pin moves (core MQTT discovery internals are the fast-moving part)
