---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
reviewed: 2026-10-03T00:00:00Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/presence.py
  - custom_components/mqtt_actions/select.py
  - custom_components/mqtt_actions/switch.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/takeover.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - tests/documents.py
  - tests/fake_broker.py
  - tests/test_cutover_instances.py
  - tests/test_cutover.py
  - tests/test_discovery_export.py
  - tests/test_native_cleanup.py
  - tests/test_native_entities.py
  - tests/test_native_start.py
  - tests/test_takeover.py
  - docs/adr/0001-native-entities-instead-of-mqtt-discovery.md
  - docs/broker-acl.md
  - docs/operations.md
  - docs/troubleshooting.md
  - README.md
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-10-03
**Depth:** standard
**Files Reviewed:** 30
**Status:** issues_found

## Summary

Focus areas were the one-way registry takeover (`takeover.py`, `Manager._async_native_takeover`), the cutover gate
(`presence.py`, `Manager._async_cutover_check`), mirror handling of untrusted documents and heartbeats, the reload versus
takeover interaction, and the legacy/native conditionals. Ruff is clean. The takeover core itself is careful: the step
order, the identity check (`is_legacy_entity`) and the idempotence after a crash are sound.

The most serious defect is outside the takeover proper. Adopting a native mirror deletes the companion device of that
mirror and, through the registry cascade, every native entity on it. This is exactly the entity-id and customization
loss the phase set out to prevent, and the test for the scenario does not detect it. The remaining findings are
ordering and fail-open weaknesses around the takeover and the cutover gate.

## Critical Issues

### CR-01: Adopting a native mirror deletes its native entities (entity ids, area and names are lost)

**File:** `custom_components/mqtt_actions/manager.py:1357-1375` (`_async_drop_mirror`), `:1334-1336`, `:1645-1656`
(`_remove_companion`); `custom_components/mqtt_actions/button.py:96-102` (`_sync_test_buttons`)
**Issue:** `async_adopt` promises that "the device keeps its uuid ... so its entities stay". For a native mirror this is
false, in two independent ways:

1. `_async_drop_mirror` calls `_remove_companion(device_id)`, which removes the registry device
   `(mqtt_actions, device_id)` under this entry. For a native mirror that device is the one that carries the native
   switch/select and the test buttons (`device_info_for`). HA's entity registry removes every entity of a removed device
   whose config entry and subentry match (`async_device_modified`, action `remove`), and the native mirror entities have
   `config_entry_id == entry` and `config_subentry_id is None`, which is exactly the removed device's pair. The registry
   entries, with their entity ids, area, user name and customizations, are deleted. The new owned device then creates
   fresh entities (new ids, possibly `_2`).
2. `_notify_devices_changed()` at line 1336 fires while the device is in neither `mirrors` nor `devices` (the subentry
   is only added after an awaited `Store.async_save`). `_sync_test_buttons` sees every `(device_id, key)` of the mirror
   vanish from `expected` and calls `registry.async_remove` on the test-button entries. This destroys the buttons even
   if point 1 were fixed.

`test_adopting_a_native_mirror_keeps_the_device_native_on_a_legacy_instance` only asserts that *a* switch entry exists
afterwards (`native_switch is not None`), never that its registry id / entity id equals the one before the adoption, so
the loss passes unnoticed.

**Fix:**
- Do not remove the companion when a native mirror is adopted. The owned device uses the same identifier
  `(DOMAIN, device_id)`, so HA reuses the device and the entities keep their registry entries. Add a parameter, for
  example `_async_drop_mirror(mirror, *, keep_companion=info.native)`, and skip `_remove_companion` for it (the legacy
  mirror case keeps removing it, only the mode select lives there).
- Move `self._notify_devices_changed()` in `_async_adopt_locked` after `async_add_subentry` and the reconcile, so no
  platform callback observes the device-less intermediate state. Alternatively make `_sync_test_buttons` remove
  registry entries only for ids that are no longer in `devices` or `mirrors` *and* whose device was deleted, never as a
  side effect of a transient absence.
- With the companion kept, `select.py`/`switch.py` drop the id from `added` while the old entity object is still in
  the platform, and a re-add logs "unique ID already exists". Keep the id in `added` while the device exists as owned or
  mirror (qualify on `manager.device(id) is not None`), and verify that the entity registry entry takes over the new
  `config_subentry_id`.
- Strengthen the test: capture `entity_registry.async_get(entity_id)` ids and entity ids before the adoption and assert
  they are unchanged after it, for the switch and for the test buttons.

## Warnings

### WR-01: The takeover result is persisted before the registries are; a crash loses the entity ids

**File:** `custom_components/mqtt_actions/manager.py:927`, `:894` (`_async_finish_takeover`, `_async_native_takeover`);
`custom_components/mqtt_actions/takeover.py:152-170`
**Issue:** After the registry moves, the pending marker is discarded and `self._store.async_save(...)` writes the Store
immediately. The entity and device registries only schedule a delayed save (about 10 s). A power loss or kill inside that
window leaves the Store saying "takeover done, native" while the registries on disk still hold the `mqtt` entries and the
legacy device. The next start treats the device as native (no pending id, `NOTHING` is never evaluated), the platforms
create new entities, the entity ids become `_2`, and the old entries are orphaned. That is the loss the one-way takeover
is supposed to rule out, and the crash-idempotence argument (pending stays set until done) only holds if the registry
write is durable first.
**Fix:** Flush both registries before clearing the pending marker in the Store, or keep the marker in the Store until
the registry store has been written. For example, call `await er.async_get(hass).async_save?`-equivalent flush (the
registry `_store.async_flush`/`async_delay_save` hook) before `_native_pending.discard(...)`, or only discard the id in
the next start after the takeover confirms the MQTT device is gone (`NOTHING`).

### WR-02: A failed clear or an exception after the registry move demotes a device to the legacy path with discovery republished

**File:** `custom_components/mqtt_actions/manager.py:885-893`, `:913-931`, `:933-941`
**Issue:** `async_take_over` can return `DONE` (entities already moved to platform `mqtt_actions`) and then
`_async_finish_takeover` returns `False` because the retained clear failed (MQTT unavailable for a moment). The caller
then calls `_async_defer_takeover`, which puts the id in `_legacy_this_run`. For this run `is_native` is `False`, so no
native entity is created for the moved entries (they sit as unavailable restored entities), and `_async_publish_owned`
publishes the legacy discovery again. Core MQTT, finding no `mqtt` registry entry for the unique id, creates new
entities with `_2` ids. The same happens when `async_take_over` raises after some entities were already moved (the
`BaseException` branch treats it as "deferred, nothing changed"). It heals at the next start only because the duplicate
branch deletes the `_2` twins, but until then the user sees duplicates and dead entities, and any automation that
touched the new ids is bound to entities that are then deleted.
**Fix:** Treat the registry state, not the return path, as the truth. After `DONE` (or after any exception, re-check
`takeover.legacy_device(...)`/the registry), keep the device native for this run and retry only the clear (for example
retry in the republish on reconnect). Only put a device in `_legacy_this_run` when nothing was moved (`DEFERRED` or a
failed migrate). Record "registry moved" separately from "clear published".

### WR-03: The one-way cutover is gated only on unauthenticated heartbeat data and fails open

**File:** `custom_components/mqtt_actions/presence.py:112-125`, `:146-152` (`observe`), `:468-483` (`blocking_peers`);
`custom_components/mqtt_actions/manager.py:791-810`
**Issue:** The decision to switch irreversibly rests on the roster:
- A peer's `native` capability is whatever its latest non-retained heartbeat says. Anyone who can publish to
  `<base>/v1/instances/<legacy id>/heartbeat` (the id is visible in the retained availability topic) can send one
  heartbeat with `"entities": "native"` under a legacy peer's id and replace its row. That peer then stops blocking
  and the cutover proceeds, clearing the legacy peer's entities with no way back.
- `Roster.observe` drops a new peer when the roster is full of fresh rows (256). A flood of valid random-id heartbeats
  keeps a real legacy peer out of the roster; it is then only covered by the "silent" rule, which stops applying after
  `HEARTBEAT_OFFLINE_SECONDS` of listening. After that a legacy peer that is online no longer blocks.
- `_async_cutover_check` runs 5 s after start. A legacy peer that is cleanly offline at that moment never blocks, and
  the switch cannot be undone when it comes back. This is accepted in the docs, but it is the easiest way to lose a
  peer's entities during a rolling restart.
The broker has no authentication by decision (see the project notes), so the first two cases are reachable by any
client on the broker. The ACL document only partly mitigates this.
**Fix:** Make the gate fail closed where it is cheap: never replace a row that currently blocks (a legacy row) with a
row that claims native within the offline window unless the session id changed; on roster overflow keep a flag so that
`blocking_peers` returns a sentinel and the cutover waits; document the offline-peer case in the cutover repair text.
At minimum add the heartbeat spoofing case to `docs/broker-acl.md` as a reason to restrict the heartbeat topic per
instance.

### WR-04: The duplicate branch deletes the user's customized legacy entry in favour of an auto-created native twin

**File:** `custom_components/mqtt_actions/takeover.py:134-141`
**Issue:** When a native entry with the same `(domain, platform, unique_id)` already exists, the legacy entry is
removed and the native one is kept. The legacy entry is the one that carries the user's entity id, area, name and
icon; the native twin is a fresh auto-generated entry (typically `..._2`). Any path that lets a native entity be created
before the pass (a mirror that is created native while its old core MQTT device still exists in `async_apply_mirror`
-> `_build_mirror`, which runs no takeover; or a retained-discovery replay recreating twins) therefore trades the
customized identity for a generated one. The test `test_an_existing_native_entry_is_never_duplicated` pins this as
intended, with natives that carry neither customizations nor the original ids.
**Fix:** Prefer the legacy entry: remove the native twin (it is not loaded at takeover time) and then move the legacy
entry, copying nothing from the twin. If the native twin has user customizations and the legacy one has none, keep the
twin; compare `name`, `area_id`, `icon`, `disabled_by` and `entity_id` against the default before deleting either.

## Info

### IN-01: Unreachable code in `_follow_native_status`

**File:** `custom_components/mqtt_actions/manager.py:1783-1793`
**Issue:** After `if not was_native: ... return`, `was_native` is always `True`, so `if was_native: return` always
returns and the block that unsubscribes the test topic and calls `_notify_devices_changed()` is dead. The docstring
also describes behaviour (native status handled "after its record was replaced") that the code no longer has.
**Fix:** Delete the unreachable tail (and the `if was_native: return`), or fix the intent: a mirror that was native
and whose takeover was deferred is the case that would need the test topic, and `_async_defer_takeover` already does
that.

### IN-02: `with_native_marker` silently drops the sticky native flag for a payload near the size limit

**File:** `custom_components/mqtt_actions/document.py:188-204`
**Issue:** When the marked payload would exceed `MAX_DOCUMENT_BYTES`, the unmarked payload is returned. The
mirror is native in memory but its stored copy has no marker; after the next restart `_parse_mirrors` rebuilds it as a
legacy mirror (T-5-11 broken), starts a test-topic subscription and may trigger another reload when the next document
arrives. A hostile or large-but-valid owner document can force this.
**Fix:** Persist the native flag separately (for example a set of native mirror ids in `STORE_NATIVE`) instead of
rewriting the stored document, or reject the unmarked case by reserving headroom for the marker in the size cap.

### IN-03: The takeover only waits for entities that are loaded, so a boot-time retained replay can race it

**File:** `custom_components/mqtt_actions/takeover.py:93-109`
**Issue:** `_async_wait_unloaded` checks `entity_sources`. A deferred device is retried at the next setup, usually a
Home Assistant restart. At that point the core MQTT integration may not have processed the retained legacy discovery
yet, so no legacy entity is loaded, the takeover moves the registry entries, and the replay then creates new entities
under platform `mqtt` before the retained clear is published. The duplicates are cleaned at the following pass
(`test_a_late_replay_duplicate_is_cleaned_at_the_next_call`) but the window exists on every restart-driven retry.
Confidence is moderate: it depends on when core MQTT processes retained discovery relative to `async_wait_ready`.
**Fix:** Publish the retained clear (or the migrate payload) before the registry move for retried devices, and wait
briefly for the MQTT discovery queue to settle before reading `entity_sources`. Add a test that delivers the replay
between the move and the clear.

### IN-04: Tests do not pin entity identity across adoption and the cutover reload

**File:** `tests/test_native_start.py:462-484`
**Issue:** See CR-01. The adoption tests assert existence and subentry binding only. There is also no test where the
cutover reload runs the takeover with a user-customized entity (name, area) and asserts that the customization
survives the whole cycle through a real `async_schedule_reload`; `test_cutover*.py` patch `async_schedule_reload`.
**Fix:** Add identity assertions (registry id, entity id, area, name) to the adoption tests and one end-to-end reload
test.

---

_Reviewed: 2026-10-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
