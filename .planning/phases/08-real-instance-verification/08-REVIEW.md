---
phase: 08-real-instance-verification
reviewed: 2026-10-11T14:29:58Z
depth: deep
iteration: 2
supersedes: "first 08-REVIEW.md as of commit 4a894b2 (git show 4a894b2:.planning/phases/08-real-instance-verification/08-REVIEW.md)"
diff_base: d72c46b
files_reviewed: 3
files_reviewed_list:
  - custom_components/mqtt_actions/takeover.py
  - tests/test_takeover.py
  - custom_components/mqtt_actions/manager.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 8: Code Review Report (second review, fix verification)

**Reviewed:** 2026-10-11T14:29:58Z
**Depth:** deep
**Files Reviewed:** 3
**Status:** issues_found

This report supersedes the first phase-08 review. That review is preserved in git at commit `4a894b2`
(`git show 4a894b2:.planning/phases/08-real-instance-verification/08-REVIEW.md`). Scope: the fix commits `d72c46b..HEAD`
(`f66caca`, `3f1b61e`, `e8acb50`, `4097b15`, `1ae6ad0`) for WR-01 and WR-02, traced into `manager.py` and the Home
Assistant core MQTT and registry code they depend on (`.venv/.../homeassistant/components/mqtt/entity.py`,
`helpers/entity.py`, `helpers/entity_registry.py`).

## Summary

- `uv run pytest tests/test_takeover.py`: 35 passed at HEAD.
- The three new tests were run against the pre-fix source (`git archive d72c46b` in a scratch directory with the HEAD
  test file). `..._disables_a_loaded_row_first_...` and `..._leaves_a_customized_entry_enabled_...` fail before the
  fix, so they discriminate. The positive control `..._disables_a_legacy_entry_when_the_native_twin_carries_the_identity`
  passes both before and after, which is expected for a control.
- Claims were checked with scratch probe tests that were never added to the repo (`scratchpad/head/tests/test_zz_probe*.py`).

**Verdicts on the user's questions**

| # | Question | Verdict |
|---|----------|---------|
| 1 | WR-01 completeness | **Partially closed** |
| 1a | Pre-guard call `manager.py:1074-1078` | **Partially closed.** Closed for loaded, enabled rows. Not closed for rows that core discovered while already disabled (CR-01). |
| 1b | Replay catch `manager.py:878-885` → `takeover.py:207-219` | **Ordering: closed. Clear: not closed.** Disable and remove run synchronously per row (`takeover.py:214-218`, no await between them). An exception at either step leaves the row disabled or untouched, which is safe. But the typical input of the catch, an export row born disabled, still produces a retained clear (CR-01). |
| 1c | Other callers | **Not closed.** `async_take_over` removes rows itself at `takeover.py:156` and `158` without disabling them first, which leaves enabled tombstones (WR-01). `remove_replay_twins` has no other caller than `Manager._remove_replay_twins` (`manager.py:850`), which is reached from `manager.py:1074` and `883`. |
| 2 | WR-02 user-data safety | **Partially closed.** The `name`/`icon`/`area`/`labels`/`categories` case is fixed. Other customization is still missed (WR-02). The both-customized and user-disabled-twin tie-breaks pick the wrong row, and the replay catch can then delete the customized row (WR-03). |
| 3 | Do the new tests exercise the fixed paths? | **Partially.** Both failing tests fail before the fix. They cover only the narrowest sub-case, and the paths in CR-01, WR-01, WR-02 and WR-03 have no test (WR-04). |

## Critical Issues

### CR-01: Removing an MQTT row that core discovered while it was disabled still clears the retained topic; the replay catch wipes a foreign core-prefix export at the next restart (WR-01 not closed for its main scenario)

**File:** `custom_components/mqtt_actions/takeover.py:214-218` (also `158`), called from `custom_components/mqtt_actions/manager.py:883` and `1074-1078`

**Issue:** The fix disables a row only when `legacy.disabled_by is None` (line 214). It assumes core MQTT clears the topic
only for a *loaded* entity that leaves the registry. Core has a second clear path:
- When core discovers an entity whose registry row is already disabled, the platform aborts the add. In
  `MqttEntity.add_to_platform_abort` (`homeassistant/components/mqtt/entity.py:1232-1252`) core then installs a
  registry hook, `async_clear_discovery_topic_if_entity_removed` (`entity.py:770-778`).
- That hook publishes `None` retained to the discovery topic as soon as the row is removed.
- The hook stays in place until the same hash is discovered again or MQTT unloads (`entity.py:1016-1020`,
  `mqtt/__init__.py:719-721`).

This is the usual state of the rows the guard exists for:
- The export payload is `enabled_by_default: false` (`discovery.py:153`), so a foreign export creates its row
  disabled and takes the abort path immediately.
- A row that the guard disabled at runtime takes the abort path at the next restart, when the retained replay
  rediscovers it.

The replay catch then removes that row. The retained export of the other instance on `homeassistant/device/<id>/config`
is wiped, which is the exact consequence WR-01 point 1 described. The docstrings at `takeover.py:200-201` ("nothing is
published here") and `245-247`, and `manager.py:906-908`, describe this removal as safe.

Reproduced with scratch probes:
- **Receiver flow, `test_zz_probe2.py`:** set up a native mirror, then a foreign core-prefix export arrives, and the row
  is born disabled with no tombstone (this is G5 of `test_export_guard_receiver.py`). After `_restart` and
  `_quiet_period_passes` the row is removed, and core publishes
  `('homeassistant/device/<id>/config', None, 0, True)`. The probe fails identically on pre-fix and HEAD, so the fix did
  not change this path.
- **Helper level, `test_zz_probe.py::test_probe_a_...`:** on the replayed rows, disable, then rediscover, then call
  `remove_replay_twins`. Result: 3 `None` clears on the topic. The control without rediscovery gives 0 clears (`probe_a2`).

On the pre-guard call `manager.py:1074`:
- For an owned device the topic is the instance's own legacy topic, which `_async_finish_takeover` clears at `1093`
  anyway. The clear still goes out before the registry flush at `1082`, out of the fixed order.
- For a native mirror (`manager.py:1066`) the topic belongs to the foreign owner. It is the same topic as that owner's
  core-prefix export.

**Fix:** Removing a disabled MQTT row is not safe while core holds an abort hook for it. Choose one:
- Do not remove disabled MQTT rows at all, in either the replay catch or `async_take_over`. Leave them disabled; they
  already restore as disabled.
  ```python
  # remove_replay_twins
  if legacy.disabled_by is not None:
      continue  # core holds a registry hook for an aborted add: removing would clear the retained topic
  entity_registry.async_update_entity(legacy.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
  entity_registry.async_remove(legacy.entity_id)
  ```
  The skip must also cover the row that this loop has just disabled, if core can rediscover it before removal. Here
  removal is synchronous, so only rows that were disabled before the call matter.
- Or remove a disabled row only when no retained discovery is known for its topic. This needs broker knowledge that
  `takeover.py` does not have by design.

Add a manager-level regression test: a foreign export born disabled, then restart, then the quiet period. Assert no
publish with a falsy payload on the core-prefix topic.

## Warnings

### WR-01: `async_take_over` still removes enabled legacy rows without disabling them, so enabled tombstones remain (the WR-01 tombstone half is closed only in `remove_replay_twins`)

**File:** `custom_components/mqtt_actions/takeover.py:150-159`

**Issue:** The fix report says the change "sits in `takeover.py`, so every caller is covered". The duplicate branch of
`async_take_over` still calls `entity_registry.async_remove(legacy.entity_id)` (line 158), and `async_remove(twin_id)`
(line 156), directly. There is no disable step.
- The legacy row is unloaded (`_async_wait_unloaded`), so no loaded-entity clear happens.
- Its deleted record keeps `disabled_by=None`. That is the UAT-04 tombstone class.

Probe `test_probe_b_...`: a customized native twin wins over an untouched legacy entry (the
`test_a_customized_native_twin_is_kept_over_an_untouched_legacy_entry` setup). Result: three `mqtt` deleted records
`('switch.lamp', None)`, `('button.lamp_test_on', None)`, `('button.lamp_test_off', None)`. The next core-prefix export
or replay of that unique id restores the row enabled. Only the guard, armed at `manager.py:808`, repairs that afterwards.

**Fix:** Apply the same step before both removals in `async_take_over`, and pin it with a test on `deleted_entities`:
```python
if legacy.disabled_by is None:
    entity_registry.async_update_entity(legacy.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
entity_registry.async_remove(legacy.entity_id)
```
CR-01 still applies to a legacy row that was disabled when core discovered it.

### WR-02: `_is_customized` misses common user customizations, so the guard still disables, and the replay catch can delete, a row the user customized

**File:** `custom_components/mqtt_actions/takeover.py:305-315` (used at `260`, and via `_carries_the_identity` at `212` and `155`)

**Issue:** The fix relies on `_is_customized`, which checks only `name`, `icon`, `area_id`, `labels`, `categories`,
`disabled_by is USER` and `hidden_by is USER`. These `RegistryEntry` fields are not checked:
- an entity-id rename (`entity_id`; there is no `name` change, but every automation and dashboard references it);
- `aliases` (voice);
- `device_class` (a user override, for example outlet versus switch);
- `options` (assistant exposure such as `conversation.should_expose`, `cloud.*`, and per-domain options);
- `hidden_by is INTEGRATION`, which is set when a wrapper helper such as Switch-as-X takes over the switch, and whose
  wrapper then points at this entity id.

Probes:
- `test_probe_c_...`: a legacy switch renamed to `switch.kitchen_lamp_renamed_by_user` next to an untouched twin.
  `disable_duplicates` returns 1 and the renamed row is disabled.
- `test_probe_e_...`: `hidden_by=INTEGRATION` plus a `conversation` exposure option. `disable_duplicates` returns 1.

If such a row is newer than its twin, the replay catch removes it at the next start. The reason is that
`_carries_the_identity` (line 325) uses the same predicate and then falls back to age.

**Fix:** Extend the predicate, and compare the entity id against the generated one:
```python
def _is_customized(entry: er.RegistryEntry) -> bool:
    generated = f"{entry.domain}.{entry.suggested_object_id or entry.object_id_base or ''}"
    return bool(
        entry.name or entry.icon or entry.area_id or entry.labels or entry.categories or entry.aliases
        or entry.device_class or _user_options(entry.options)
        or entry.hidden_by is not None
        or entry.disabled_by is er.RegistryEntryDisabler.USER
        or not entry.entity_id.startswith(generated)
    )
```
Here `_user_options` ignores keys the integration or core set by themselves. Verify the exact generated-id rule against
core before relying on it. Add one parametrized test per field.

### WR-03: Tie-breaks in `disable_duplicates` pick the wrong row: a user-disabled twin leaves no enabled entity, and with both rows customized the legacy row is disabled and then deleted

**File:** `custom_components/mqtt_actions/takeover.py:260`, `takeover.py:212` with `325-327`, `manager.py:883`

**Issue:** `_is_customized(entry) and not _is_customized(twin)` counts the twin's `disabled_by is USER` and
`hidden_by is USER` as "the twin carries the identity". For the guard those are the opposite signal: the user rejected
the twin. The fix report left the both-customized case as an open question.
- **User-disabled twin.** Probe `test_probe_h_...`: a legacy row named "Kitchen" and a twin with
  `disabled_by=USER`. `disable_duplicates` returns 1 and no enabled row is left for the unique id. The same happens
  with an untouched legacy row. The first review's IN-01 notes that the docs tell users to disable a duplicate by hand,
  so a user who disables the native one loses the device's switch. The guard then re-disables the legacy row at every
  start (`manager.py:916`). The mirror case: a legacy row `hidden_by=USER` is the row the user rejected, but it now
  counts as customized and is protected.
- **Both rows customized, legacy newer.** Probe `test_probe_d2_...`: a replayed row with `name` and `labels`, next to a
  moved twin with `name`. `disable_duplicates` disables the replayed row (1). Then `remove_replay_twins` removes it,
  because both are customized and the twin is older (line 327). The row's name and labels survive only in
  `deleted_entities`. That record is restored only if core re-creates the same unique id, and then disabled. No UI path
  lets the user get it back. This is the only path in scope that takes user customization out of reach. It is not
  strictly irreversible, because the record is kept while the MQTT entry exists.

**Fix:**
- Exclude the disabled/hidden state from the twin side of the comparison in `disable_duplicates`. Never disable the
  last enabled row of a unique id:
  ```python
  if twin.disabled_by is not None:
      continue  # the user turned the native entity off: the legacy row is the one they kept
  ```
- For both-customized rows, do not disable or remove anything automatically. Raise a Repairs issue that names the two
  entity ids (they are local registry data, not broker content).
- In `remove_replay_twins`, skip a legacy row whenever `_is_customized(legacy)` is true, whatever its age.

### WR-04: The new tests cover only the narrowest sub-case of each fix; the paths above have no test

**File:** `tests/test_takeover.py:915-946`, `992-1027`

**Issue:**
- **WR-01 test.** It builds only loaded, enabled replay rows (`_moved_and_replayed`) and calls the helper directly. It
  never covers:
  - a row that core discovered disabled (CR-01);
  - the foreign core-prefix export;
  - the manager paths, which are the pre-guard call at `manager.py:1074` and `_async_replay_catch`;
  - `async_take_over`'s own removals (WR-01).
- **WR-02 tests.**
  - Only `name` is exercised. There is no case for area, labels, icon, categories, hidden_by, entity-id rename, aliases
    or options.
  - The both-customized behavior is not pinned.
  - There is no user-disabled-twin case.
  - The event-listener path (`manager.py:918-941`) is not covered with a customized row.
  - The assertion that the twin stays enabled (`:1010`, `:1027`) is true with or without the fix, because the twin is
    never a candidate.

This is how CR-01 survived a fix that "passes 1516 tests".

**Fix:** Add the regression tests listed under CR-01 to WR-03, at least one of them through `Manager`
(`_restart` + `_quiet_period_passes`) and asserting on falsy-payload publishes to the core-prefix topic.

## Info

- **IN-01:** `takeover.py:220-221` / `manager.py:849-857,883`: if a row raises partway through the loop, the emptied MQTT device stays, because later calls return early at `if not removed`, and the partial count is lost, so the flush at `883` is skipped.
- **IN-02:** `takeover.py:217-218`: the no-clear guarantee for loaded rows depends on HA internals: the eager task in `Entity._async_registry_updated` (`helpers/entity.py:1590-1593`) unsubscribes before the remove event. Only one test pins this.
- **IN-03:** `takeover.py:260-262`: a customized legacy row kept enabled by the WR-02 fix stays a permanent enabled duplicate. No log line and no Repairs hint tell the user.

---

_Reviewed: 2026-10-11T14:29:58Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
