---
phase: 11-local-actions-on-mirrors
reviewed: 2026-10-21T05:42:46Z
depth: standard
files_reviewed: 39
files_reviewed_list:
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/diagnostics.py
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/local_actions.py
  - custom_components/mqtt_actions/local_actions_store.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/retrigger.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/services.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/trust.py
  - docs/diagnostics.md
  - docs/operations.md
  - docs/troubleshooting.md
  - README.md
  - tests/fake_broker.py
  - tests/helpers.py
  - tests/test_diagnostics.py
  - tests/test_discovery_export.py
  - tests/test_docs.py
  - tests/test_hub_removal.py
  - tests/test_local_action_plans.py
  - tests/test_local_actions_flow.py
  - tests/test_local_actions_lifecycle.py
  - tests/test_local_actions_manager.py
  - tests/test_local_actions_store_instances.py
  - tests/test_local_actions_store.py
  - tests/test_local_invariants.py
  - tests/test_local_multi_instance.py
  - tests/test_local_parallel.py
  - tests/test_native_cleanup.py
  - tests/test_repairs_flow.py
  - tests/test_services.py
  - tests/test_sync_follower.py
  - tests/test_translations.py
findings:
  critical: 0
  warning: 4
  info: 7
  total: 11
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-10-21T05:42:46Z
**Depth:** standard
**Files Reviewed:** 39
**Status:** issues_found

## Summary

I reviewed the Phase 11 diff (`01a9edf..HEAD`). It adds local actions on mirrors: a pure model (`local_actions.py`), a separate Store, effective-plan Script building with one native `parallel` per trigger, per-branch outcome reduction from Core traces, the options-flow editor, lifecycle hooks (prune, tombstone, adoption, hub removal), and diagnostics and docs.

The full test suite passes: `uv run pytest -n 8` gave 2072 passed and 2 xfailed. I checked the trace-path assumptions against the installed Core `helpers/script.py`. The `parallel/<idx>/sequence` paths, step-level trace elements for disabled steps, and `gather(return_exceptions=True)` semantics all match what `at_dispatch`, `reduce_local_outcome` and `_owner_error` expect. I also checked the owner-subtree guard path in `_replace_at` against the validated tree shape, and found no defect there.

I found no blockers. The remaining findings are about data durability and issue lifecycle:
- An unauthenticated tombstone permanently destroys local-only data.
- The local failure issue can become impossible to clear without undoing the user's choice.
- A corrupt or shape-invalid local Store is silently treated as empty, which contradicts the code's own docstring and the troubleshooting doc.
- The hub-removal warning under-reports what gets deleted.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Any tombstone on a config topic permanently discards local actions, while the mirror itself self-heals

**File:** `custom_components/mqtt_actions/sync.py:489-505`, `custom_components/mqtt_actions/manager.py:2167-2200`
**Issue:** `_async_remove` now forwards every empty config payload for a non-owned, valid id to `async_remove_mirror(..., cause=TOMBSTONE)`. This happens even when no mirror exists. `_async_discard_tombstoned_records` then saves the record set without that device.

An empty payload carries no owner, so its provenance is never checked. A stray "delete retained topic" from any broker client is enough, for example MQTT Explorer, a script, or a misconfigured bridge. The owner treats its cleared config topic as a foreign write (`_check_owned` → `_overwritten`) and republishes, so the mirror comes back on every instance. The local records do not come back: they exist only in this instance's Store and nothing on the broker can restore them.

Before Phase 11 the same event was fully self-healing. Now it is permanent, silent data loss on every connected instance; the only trace is an INFO log line. This is a data-loss risk created by D-05 trusting an unauthenticated signal. I am not asking for broker auth here.
**Fix:** Corroborate the tombstone before destroying local data. Options:
- Remove the mirror at once but defer the record discard. Discard only when the document stays absent for `PRUNE_GRACE_SECONDS` while the owner is online, using the same evidence the prune already uses. If a document of the pinned owner arrives in the meantime, cancel the discard.
- Or keep the records, mark them inactive as after a prune, and let the user remove them. The editor already lists "no mirror" devices.

```python
# sync._async_remove: remove the mirror now, schedule the record discard
await manager.async_remove_mirror(device_id, cause=MirrorRemovalCause.TRANSIENT_PRUNE)
self._pending_tombstones[device_id] = manager.clock()  # discard after grace if no document of the owner returns
```

### WR-02: The local failure issue cannot clear after the user mutes the trigger or empties its additive actions

**File:** `custom_components/mqtt_actions/manager.py:1788-1842`, `custom_components/mqtt_actions/manager.py:1845-1878`
**Issue:** Only two events clear the local failure issue:
- a proven `SUCCESS` outcome of the named trigger (`_clear_local_failure_naming`);
- removal of its record (`async_remove_local_action`).

`async_set_local_action` never looks at the issue. Suppose the user reacts to a failure by changing the trigger to a mute (`REPLACEMENT` with `[]`) or to `ADDITIVE` with `[]`. Both are valid saves through the flow. The trigger then has no local branch (`build_effective_trigger_plan` sets `local_actions=None`), so no local outcome is ever produced again, and the record still exists. The issue stays forever and shows a stale error for actions that no longer exist.

To get rid of it, the user must remove the customization. For a mute, that brings back the owner actions they deliberately suppressed. `docs/troubleshooting.md:206` tells the user to "correct its local actions", which in this case does not work.
**Fix:** When a saved record has no local actions, clear the issue if it names that identity. A record without local actions cannot fail locally any more.

```python
# in async_set_local_action, after _async_commit_local_records(...)
if not record.actions:
    self._clear_local_failure_naming(identity)
```

### WR-03: A corrupt or shape-invalid local Store is treated as empty: no `local_actions_unreadable` issue, mutes revert, and the next save overwrites it

**File:** `custom_components/mqtt_actions/local_actions_store.py:87-99`, `custom_components/mqtt_actions/manager.py:1222-1252`, `docs/troubleshooting.md:216-221`
**Issue:** The `local_actions_unreadable` issue and its docs promise this for a damaged file: local actions are not applied, the issue is shown, editing is refused, and "the file is not changed". The code only does that when `async_load` raises, which in practice means a newer major version. Two other cases bypass it.

1. **JSON-corrupt file.** Core's `Store._async_load_data` renames the file to `*.corrupt.<time>`, raises a generic `storage_corruption` issue and returns `None`. `async_load_records` treats `None` as "no records" and sets `_loaded = True`. The integration issue is never raised. Replaced and muted triggers silently run approved owner actions again, which is exactly the safety regression the issue text warns about.
2. **Valid JSON with the wrong shape**, for example `{"records": {...}}`, or a newer minor format. The code only logs a warning and still sets `_loaded = True`. The next save then overwrites the file with the reduced set, which can be any edit, a label refresh in `_async_refresh_local_labels`, or a tombstone discard. This contradicts the class docstring ("never overwritten", T-11-09).

There is a related forward-compatibility problem. Rows that fail `parse_local_record` are dropped in memory, for example a `mode` value a newer minor release adds. Core's minor-version path also re-saves the payload at load. The next save of this release then erases those rows permanently.
**Fix:** Treat "shape invalid" and "load returned None while a corrupt sibling file exists" as unreadable. That means raising the instance issue and keeping `_loaded = False`, so no save can overwrite. At minimum, do this for `not parsed.shape_valid`:

```python
if not parsed.shape_valid:
    raise LocalActionsStoreVersionError("local actions Store holds no record list")  # Manager raises the issue, refuses saves
```

Then align `docs/troubleshooting.md` and the issue text with what actually happens for a JSON-corrupt file: Core moves it aside, and the user restores it from the `.corrupt` copy.

### WR-04: The hub-removal warning reports 0 devices when the local Store is unreadable, but removal deletes the file anyway

**File:** `custom_components/mqtt_actions/manager.py:605-622`, `custom_components/mqtt_actions/config_flow.py` (`async_step_settings`, `local_action_device_count` placeholder)
**Issue:** `async_local_action_device_count` returns `manager.local_action_counts().devices` for a loaded hub. That is `0` when the load was refused, because `_local_records = ()`. For an unloaded hub, a read error is also mapped to `0`. Either way, `async_remove_local_state` then deletes the file unconditionally.

This is the downgrade scenario the README warns about: a file written by a newer release is unreadable here. The settings text tells the user that removing the hub "deletes the local actions of 0 devices" while it actually deletes all of them.
**Fix:** Return `None` (unknown) when the Store could not be read, and show a dedicated warning text such as "the saved local actions cannot be read and will be deleted". For a loaded hub, expose a `local_actions_readable` flag from the Manager instead of the count of an empty fallback.

## Info

### IN-01: The `replaced` placeholder of the approval issue is never rendered, so `_refresh_approval_count` does no visible work

**File:** `custom_components/mqtt_actions/manager.py:2120`, `custom_components/mqtt_actions/manager.py:2125-2132`
**Issue:** `approval_required` is a fixable issue. Its only description lives in `fix_flow.step.confirm`, and that text is filled from `ApprovalRepairFlow`'s own placeholders (`repairs.py`). The issue-level `translation_placeholders["replaced"]` is not referenced by any translation. `_refresh_approval_count` therefore re-creates the issue on every local edit only to update an unused value.
**Fix:** Drop the issue-level `replaced` placeholder and `_refresh_approval_count`, or reference `{replaced}` in a rendered string.

### IN-02: Production-dead state and API kept only for tests

**File:** `custom_components/mqtt_actions/manager.py:298`, `custom_components/mqtt_actions/manager.py:2162`, `custom_components/mqtt_actions/runner.py:305-307`, `custom_components/mqtt_actions/manager.py:1420-1422`
**Issue:** Production code never reads these:
- `Device.policy` and `ActionRunner.policy_for`/`_policies`: only `tests/test_local_actions_manager.py` reads them.
- `Manager.async_adopt`: production uses `async_adopt_device`.
- `LocalActionChange`: returned by `async_set_local_action`/`async_remove_local_action`, but the flow discards it.
**Fix:** Remove them, or mark them clearly as test seams so they do not drift from the real policy holders (tracker and breaker).

### IN-03: The test topic applies the mode gate twice

**File:** `custom_components/mqtt_actions/manager.py:2923-2930`
**Issue:** `_on_test_message` first returns on `_test_blocked(device)`, then calls `run_manual`, which checks the same mode again. Two gates for one rule can drift apart.
**Fix:** Drop the `_test_blocked` check in `_on_test_message`, so `run_manual` is the only gate as MIR-10 intends.

### IN-04: `local_action_devices` docstring says "sorted by id", but mirrors are listed in dict order

**File:** `custom_components/mqtt_actions/manager.py:1715-1736`
**Issue:** Only the record-only devices are sorted; the mirrors follow `self.mirrors` insertion order.
**Fix:** Sort the mirrors as well, or fix the docstring.

### IN-05: A build-time local validation failure is logged twice at ERROR and refreshes the issue time on every rebuild

**File:** `custom_components/mqtt_actions/runner.py:249-261`, `custom_components/mqtt_actions/manager.py:1860-1866`
**Issue:** `_async_check_branches` logs "Invalid local actions ..." and then emits a FAILURE outcome, which `async_report_local_outcome` logs again at ERROR. This repeats on every rebuild: owner document update, approval, or an edit of another trigger. Each time the issue's `time` placeholder moves forward, although no run happened.
**Fix:** Log once, in the Manager. Optionally, skip re-emitting a generation-0 failure when the issue already names the same identity with the same error.

### IN-06: Shared response variables let an approved owner branch feed values into unguarded local templates

**File:** `custom_components/mqtt_actions/runner.py:53-60`, `README.md` (Parallel runs)
**Issue:** Owner and local branches share one response-variable namespace inside one `parallel`. Only the owner subtree is guarded. A local template that reads a variable name the owner branch also sets, for example a templated `action:`, renders owner-controlled data with full local trust. Through that path the owner could reach a denied service. The README presents this only as a race. It is also a trust-boundary crossing.
**Fix:** In the README, state that local actions must not read variables the owner branch could set. Optionally, namespace or deny owner `response_variable` names in the restricted analysis.

### IN-07: `adopt_device` surfaces an untranslated internal error when the local discard cannot be saved

**File:** `custom_components/mqtt_actions/services.py:309-312`
**Issue:** `async_adopt_device` can raise `LocalActionsStoreError` before anything changed. The handler catches only `AdoptionError`, so the caller sees the raw message "The local actions of mqtt_actions.local_actions could not be saved" instead of a translated `ServiceValidationError`, as the other refusals get.
**Fix:** Catch `LocalActionsStoreError` and raise a `HomeAssistantError` with a `translation_key` (for example `local_actions_save_failed`).

---

_Reviewed: 2026-10-21T05:42:46Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
