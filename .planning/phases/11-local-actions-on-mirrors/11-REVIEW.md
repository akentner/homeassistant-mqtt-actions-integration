---
phase: 11-local-actions-on-mirrors
reviewed: 2026-10-21T08:40:15Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/local_actions.py
  - custom_components/mqtt_actions/local_actions_store.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - docs/troubleshooting.md
  - README.md
  - tests/test_docs.py
  - tests/test_hub_removal.py
  - tests/test_local_actions_lifecycle.py
  - tests/test_local_actions_manager.py
  - tests/test_local_actions_store.py
  - tests/test_local_invariants.py
  - tests/test_translations.py
findings:
  critical: 0
  warning: 2
  info: 10
  total: 12
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-10-21T08:40:15Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

This is an incremental re-review of `git diff 4426cf3..HEAD`, the gap-closure plans 11-18 to 11-23. It checks the fixes for WR-01 to WR-04 against the owner amendments in 11-CONTEXT.md ("Amendments, owner decision 2026-10-21") and looks for regressions the fixes introduced.

Verification of the earlier warnings:
- **WR-01 (tombstone): fixed.** `MirrorRemovalCause` is gone. `sync._async_remove` only acts on an existing mirror, and `Manager.async_remove_mirror` never writes the local Store. Records and their failure issue stay and are listed as "not mirrored". Adoption is now the only path that calls `_async_discard_local_records`. README, troubleshooting and tests match.
- **WR-02 (issue cannot clear after mute or empty additive): fixed for the synchronous path.** A durable save without actions clears the issue only when the issue names that identity, and a failed save clears nothing. An in-flight run can still re-create the issue after the clear. I confirmed this with a probe (see WR-06).
- **WR-03 (corrupt or shape-invalid Store): fixed for the two named cases.** A payload without a record list now raises `LocalActionsStoreUnreadableError`, and so does a missing file next to a `<key>.corrupt.*` copy. The Store stays unloaded and refuses saves. The copy match is anchored on `"<file>.corrupt."`, so other keys do not match. Rows that fail parsing are now kept, and unknown top-level keys too. The forward-compatibility part is only half fixed: unknown keys inside a parseable row are still stripped on save (see WR-05).
- **WR-04 (removal warning shows 0): fixed.** The count is `int | None`. A loaded hub reports `None` via `_local_actions_readable`, and an unloaded hub maps any read error to `None`. The dedicated `settings_unreadable` step uses the same schema and submits through `async_step_settings`. The en/de texts exist and are covered by `OPTION_STEPS`. Devices named only by preserved rows are counted.

Probe used for WR-06, run outside the repository: `/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-mqtt-actions-integration/667d23fa-9fde-4c75-b77c-e0d2d74cb17b/scratchpad/test_probe_mute_race.py`. It runs an additive local branch `[test.flaky (continue_on_error), delay 30 s]`, fires ON, saves a mute while the run is in flight, then waits for it to settle. Result: no issue right after the save, then `local_action_failed` exists naming `switch/on` while the record's actions are `[]`.

I found no blockers. IN-01 to IN-07 are unchanged by this diff and carried forward.

**Resolved since previous review:** WR-01, WR-02, WR-03 and WR-04, as recorded in 11-REVIEW-DISPOSITION.md. WR-05 and WR-06 below are gaps or regressions left by the WR-03 and WR-02 fixes. They are new findings, not reopened IDs. None of IN-01 to IN-07 was resolved.

## Narrative Findings (AI reviewer)

## Warnings

### WR-05: Unknown keys inside a parseable row are dropped on save, contradicting the new "saving here keeps them" promise

**File:** `custom_components/mqtt_actions/local_actions.py:143-167`, `custom_components/mqtt_actions/local_actions.py:245-255`, `README.md:367-369`, `custom_components/mqtt_actions/manager.py:615`
**Issue:** The WR-03 fix keeps only rows that *fail* `parse_local_record`. `parse_local_record` checks that the six `RECORD_KEYS` are present and ignores every other key. `local_record_data` then writes back only those six keys. A newer minor release will most likely add an optional row field (for example `enabled`, `conditions` or `variables`). Such a row:
1. parses here as a full record and is **applied without the new field's semantics**. For example, a row a newer release marked `"enabled": false` runs here.
2. loses the field permanently on the next save of this release. That save can be any edit, a label refresh in `_async_refresh_local_labels`, or an adoption discard.

Verified:

```text
parse_local_actions_payload({'records': [{...six keys..., 'enabled': False, 'conditions': [...]}]})
-> 1 record, preserved=()
local_actions_payload(...) -> {'records': [{...six keys only...}]}
```

The README bullet added in this diff says local actions a newer version saved "stay in the file unchanged ... saving here keeps them". That is only true for rows that fail to parse.

There is a related problem. For a newer minor envelope, Core's `Store._async_load_data` calls `_async_migrate_func` and then `async_save(stored)` stamped with this release's `minor_version = 1`. Merely loading therefore rewrites the file and downgrades its minor marker. The newer release will then run its own 1→2 migration over rows that are already in 2-shape. This also happens in the unloaded-hub count path, so the new docstring claim "Reading never writes the Store" (`manager.py:615`) is false for a newer-minor file.
**Fix:** Keep each row's unknown keys and write them back. Also refuse to apply rows that carry keys this release does not know, or at least document why that is safe. For example:

```python
# LocalActionRecord gains: extra: dict[str, Any] = field(default_factory=dict)
def parse_local_record(raw):
    ...
    record = make_local_record(...)
    extra = {k: copy.deepcopy(v) for k, v in raw.items() if k not in RECORD_KEYS}
    return dataclasses.replace(record, extra=extra)

def local_record_data(record):
    return {**copy.deepcopy(record.extra), "device_id": ..., ...}
```

If unknown row keys should instead mean "not applicable here", send such rows to `preserved` and do not parse them. In `migrate_local_actions_payload`, record that every future minor migration must be idempotent, because an older release re-stamps the file as minor 1 at load. Fix the `manager.py:615` docstring.

### WR-06: An in-flight failing run re-creates the local failure issue after a mute or empty-additive save cleared it (WR-02 fix is racy)

**File:** `custom_components/mqtt_actions/manager.py:1856-1857`, `custom_components/mqtt_actions/manager.py:1886-1896`, `custom_components/mqtt_actions/runner.py:483-493`
**Issue:** `async_set_local_action` clears the issue right after the commit. The run that was in flight when the user saved keeps going. The rebuild cancels it, and the runner's `finally` ("Also on cancellation: a local error recorded before a restart or unload is still a local failure") later delivers a `FAILURE` outcome. `reduce_local_outcome` returns `FAILURE` without needing `proven`. `async_report_local_outcome` only drops a failure when the record is *gone* (`_local_record(identity) is None`). After a mute the record still exists with `actions == []`, so the issue is re-created and names a trigger that has no local actions.

The probe described in the Summary reproduces this: issue absent right after the save, present after settle with `data={'kind': 'switch', 'state_value': 'on'}`, while the record's actions are `[]`. This is the stuck state WR-02 was about. The only ways out are saving the mute again or removing the customization, which brings back the owner actions the user deliberately suppressed. Removal is not affected, because the record is gone and the outcome is dropped. The two "end the customization" paths are therefore asymmetric.
**Fix:** Drop a failure outcome whose current record has no local actions, the same way a removed record is dropped:

```python
if outcome.status is OutcomeStatus.FAILURE:
    record = self._local_record(identity)
    if record is None or not record.actions:
        return  # nothing local can fail any more; a stale in-flight outcome must not re-open the issue
```

Add a regression test modelled on the probe: an in-flight local branch with a recorded error, then a mute save, then settle. The issue must stay absent.

## Info

### IN-08: Preserved rows are invisible to every device-scoped operation, so they outlive adoption and "Remove local customization" and can resurface after an upgrade

**File:** `custom_components/mqtt_actions/local_actions_store.py:126-136`, `custom_components/mqtt_actions/manager.py:2228-2238`, `custom_components/mqtt_actions/local_actions.py:176-184`
**Issue:**
- `_async_discard_local_records` (adoption) filters only `_local_records`. Preserved rows of the adopted device stay in the file. After an upgrade that parses them, they become local records of a device this instance now owns. `local_actions_discarded` and the troubleshooting text ("its local actions are discarded") under-report this.
- A user can create a record for an identity that already has a preserved row, because the editor does not show it. Removing that record later leaves the preserved row, and it comes back after an upgrade. The `ParsedLocalActions` docstring says "removing a record never brings an older row back (D-10)", which only holds for parsed duplicates.
- Genuinely malformed rows, not from a newer version, are now kept forever. They log a WARNING on every start and can only be cleared by removing the hub.
- `preserved_device_ids` ignores preserved rows without a string `device_id`. A file holding only such rows shows "0 devices" in the removal settings, although removal deletes them.

**Fix:** In `_async_discard_local_records`, also drop preserved rows whose `device_id` matches, and have the Store expose a `discard_preserved(device_id)` helper for this. Make the `ParsedLocalActions` docstring precise. Optionally surface a preserved-row count in diagnostics.

### IN-09: Hub removal deletes Core's `.corrupt` copy but leaves Core's persistent `storage_corruption_*` repair pointing at it

**File:** `custom_components/mqtt_actions/local_actions_store.py:180-195`, `custom_components/mqtt_actions/manager.py:535-560`
**Issue:** Core creates a persistent CRITICAL issue `homeassistant/storage_corruption_mqtt_actions.local_actions_<time>` with `corrupt_path` as a placeholder. `async_remove_records` now deletes that file, both at hub removal and when a new hub is created in `async_step_user`. `async_remove_local_state` only deletes issues in `DOMAIN`, so the Core issue survives and points at a file that no longer exists. Deleting the copy also destroys the user's only repairable copy. The `settings_unreadable` text says the local actions are deleted, but it does not mention that the `.corrupt` copy goes too.
**Fix:** Also delete Core issues whose id starts with `storage_corruption_{LOCAL_ACTIONS_STORE_KEY}_`, using `ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, ...)`. Name the `.corrupt` copy in the `settings_unreadable` text.

### IN-10: Text drift after the WR-01 and WR-03 fixes

**File:** `docs/troubleshooting.md:219-222`, `custom_components/mqtt_actions/manager.py:1726-1727`
**Issue:**
- Troubleshooting still says "the file is not changed" and "the newer or damaged file and your local actions in it stay as they are". Two sentences later it says that Home Assistant moves a non-JSON file aside. The en/de issue text was reworded to "MQTT Actions does not change the file", but the troubleshooting page was not.
- The `local_action_devices` docstring lists only "a transient prune, a start before the owner's document" as reasons a record-only device is listed. A tombstone now does the same.

**Fix:** Change the troubleshooting text to "MQTT Actions does not change the file" and drop "stay as they are" for the damaged-JSON case. Add "a tombstone" to the docstring.

### IN-01: The `replaced` placeholder of the approval issue is never rendered, so `_refresh_approval_count` does no visible work (carried forward)

**File:** `custom_components/mqtt_actions/manager.py:2152`, `custom_components/mqtt_actions/manager.py:2157-2163`
**Issue:** `approval_required` is a fixable issue. Its only description lives in `fix_flow.step.confirm`, and that text is filled from `ApprovalRepairFlow`'s own placeholders (`repairs.py`). The issue-level `translation_placeholders["replaced"]` is not referenced by any translation. `_refresh_approval_count` therefore re-creates the issue on every local edit only to update an unused value.
**Fix:** Drop the issue-level `replaced` placeholder and `_refresh_approval_count`, or reference `{replaced}` in a rendered string.

### IN-02: Production-dead state and API kept only for tests (carried forward)

**File:** `custom_components/mqtt_actions/manager.py:299`, `custom_components/mqtt_actions/manager.py:2194`, `custom_components/mqtt_actions/runner.py:305-307`, `custom_components/mqtt_actions/manager.py:1427`
**Issue:** Production code never reads these:
- `Device.policy` and `ActionRunner.policy_for`/`_policies`: only `tests/test_local_actions_manager.py` reads them.
- `Manager.async_adopt`: production uses `async_adopt_device`.
- `LocalActionChange`: returned by `async_set_local_action`/`async_remove_local_action`, but the flow discards it.

**Fix:** Remove them, or mark them clearly as test seams so they do not drift from the real policy holders (tracker and breaker).

### IN-03: The test topic applies the mode gate twice (carried forward)

**File:** `custom_components/mqtt_actions/manager.py:2952-2960`, `custom_components/mqtt_actions/manager.py:2980`
**Issue:** `_on_test_message` first returns on `_test_blocked(device)`, then calls `run_manual`, which checks the same mode again. Two gates for one rule can drift apart.
**Fix:** Drop the `_test_blocked` check in `_on_test_message`, so `run_manual` is the only gate as MIR-10 intends.

### IN-04: `local_action_devices` docstring says "sorted by id", but mirrors are listed in dict order (carried forward)

**File:** `custom_components/mqtt_actions/manager.py:1722-1743`
**Issue:** Only the record-only devices are sorted; the mirrors follow `self.mirrors` insertion order.
**Fix:** Sort the mirrors as well, or fix the docstring.

### IN-05: A build-time local validation failure is logged twice at ERROR and refreshes the issue time on every rebuild (carried forward)

**File:** `custom_components/mqtt_actions/runner.py:249-261`, `custom_components/mqtt_actions/manager.py:1886-1896`
**Issue:** `_async_check_branches` logs "Invalid local actions ..." and then emits a FAILURE outcome, which `async_report_local_outcome` logs again at ERROR. This repeats on every rebuild: owner document update, approval, or an edit of another trigger. Each time the issue's `time` placeholder moves forward, although no run happened.
**Fix:** Log once, in the Manager. Optionally, skip re-emitting a generation-0 failure when the issue already names the same identity with the same error.

### IN-06: Shared response variables let an approved owner branch feed values into unguarded local templates (carried forward)

**File:** `custom_components/mqtt_actions/runner.py:53-60`, `README.md:337-339` (Parallel runs)
**Issue:** Owner and local branches share one response-variable namespace inside one `parallel`. Only the owner subtree is guarded. A local template that reads a variable name the owner branch also sets, for example a templated `action:`, renders owner-controlled data with full local trust. Through that path the owner could reach a denied service. The README presents this only as a race. It is also a trust-boundary crossing.
**Fix:** In the README, state that local actions must not read variables the owner branch could set. Optionally, namespace or deny owner `response_variable` names in the restricted analysis.

### IN-07: `adopt_device` surfaces an untranslated internal error when the local discard cannot be saved (carried forward)

**File:** `custom_components/mqtt_actions/services.py:309-312`
**Issue:** `async_adopt_device` can raise `LocalActionsStoreError` before anything changed. The handler catches only `AdoptionError`, so the caller sees the raw message "The local actions of mqtt_actions.local_actions could not be saved" instead of a translated `ServiceValidationError`, as the other refusals get.
**Fix:** Catch `LocalActionsStoreError` and raise a `HomeAssistantError` with a `translation_key` (for example `local_actions_save_failed`).

---

_Reviewed: 2026-10-21T08:40:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
