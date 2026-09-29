---
phase: 02-select-devices-and-reliable-execution
reviewed: 2026-09-29T00:00:00Z
depth: standard
files_reviewed: 29
files_reviewed_list:
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/breaker.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - tests/conftest.py
  - tests/test_breaker.py
  - tests/test_config_flow.py
  - tests/test_config_flow_select.py
  - tests/test_discovery.py
  - tests/test_discovery_select.py
  - tests/test_manager.py
  - tests/test_manager_breaker.py
  - tests/test_manager_select.py
  - tests/test_model.py
  - tests/test_repo_structure.py
  - tests/test_runner_modes.py
  - tests/test_state.py
  - tests/test_test_buttons.py
  - tests/test_topics.py
  - tests/test_translations.py
findings:
  critical: 0
  warning: 4
  info: 6
  total: 10
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-09-29
**Depth:** standard
**Files Reviewed:** 29 (`actions.py` and `mqtt_gateway.py` were also read as callees)

## Summary

Phase 2 adds Select devices, one Script per device with a run mode, test buttons with tombstones, and a persisted circuit breaker. The full suite passes (426 tests). `ruff check` and `ruff format --check` are clean. en.json and de.json have identical key sets.

I found no blocker. Template construction is safe: user text goes through `json_dumps` literals, and only the hashed hex key enters a template. The baseline, breaker and tripped-state logic is consistent, and the persisted hash matches the in-memory signature.

The main weaknesses are in failure handling and in inconsistencies between what the tracker accepts and what the entity does:

- A live reconcile that fails halfway leaves a device stuck.
- The Switch entity does not trim payloads although the tracker does.
- The test topic path is outside the breaker.
- The Repairs issue is cleared by an unrelated successful run.

## Warnings

### WR-01: Failed `_async_add_device` during a live reconcile leaves a permanently dead device

**File:** `custom_components/mqtt_actions/manager.py:333-366`
**Issue:** `self.devices[device_id] = device` is set (line 354) before the two `gateway.async_subscribe` calls and before discovery is published. If `async_subscribe` raises `HomeAssistantError`, the exception propagates out of `async_reconcile`. That is only logged when it comes from the update listener. At startup, `__init__.py` turns it into `ConfigEntryNotReady` and the entry is retried. In a live reconcile the device stays in `self.devices`. It has `unsubscribe`/`unsubscribe_test` set to `None`, no discovery, and it is not in `_published`. Every later reconcile finds `device.signature == _signature(subentry)` and skips it. `_on_connection_status` republishes discovery only, never subscriptions. The device therefore never receives messages until the entry is reloaded. The remaining subentries in the same reconcile pass are also skipped, because the exception aborts the loop.
**Fix:** Register the device only after every step succeeded, and undo on failure. For example, subscribe first, then assign `self.devices[device_id] = device`, wrapped in try/except that unsubscribes and unloads the runner on error. Alternatively catch `HomeAssistantError` per device in `async_reconcile` and leave the subentry out of `self.devices` so the next reconcile retries it.

### WR-02: Switch `value_template` does not trim, but the tracker does

**File:** `custom_components/mqtt_actions/discovery.py:66-67`
**Issue:** The comment says the entity must be as tolerant as the tracker. The Select template uses `value | trim | lower`, and `state.decide` uses `payload.strip().lower()`. The Switch template is only `{{ value | upper }}`. A payload such as `" on"` or `"ON\n"` runs the ON actions, because the tracker trims. The entity renders `" ON"`, which core does not match against `payload_on`, so the entity ignores it and logs a warning. The README says "Inbound values are trimmed and read case-insensitively", which is only true for the actions.
**Fix:**
```python
"value_template": "{{ value | trim | upper }}",
```
Add a discovery test with a whitespace-padded payload.

### WR-03: Test topic is a second, breaker-free trigger path

**File:** `custom_components/mqtt_actions/manager.py:561-586`
**Issue:** `_on_test_message` calls `runner.enqueue` directly. It skips `device.breaker.record()`, the `breaker.tripped` check, and the edge detection that the state path uses. Any message on `<base>/v1/devices/<id>/test` runs actions without limit. Serial mode is bounded by the queue limit of 10, and restart mode cancels and restarts on every message. An action that publishes to the test topic, or a misconfigured broker client, therefore creates exactly the self-triggering loop the breaker is meant to stop, and the breaker neither sees nor stops it. The README documents the test topic as a trust boundary, but not that it is exempt from loop protection. It says "test buttons keep working" only for the paused state.
**Fix:** At minimum, count test runs against a separate small limit, or count them in the same breaker and only let the manual press through when the breaker is not tripped. If the exemption is intended (D-13), state it explicitly in the README security section and add a test that pins the behavior.

### WR-04: A successful run of one trigger clears the "invalid actions" Repairs issue of another trigger

**File:** `custom_components/mqtt_actions/runner.py:52-61, 104-108, 186-187`
**Issue:** An invalid trigger is reported through `report_failure`, so it uses the same issue id `action_failed_<device_id>` as runtime failures. `_async_run` calls `clear_issue(device_id)` after any successful latest run. In a Select with option A invalid and option B valid, the first successful run of B deletes the setup issue. Option A stays permanently broken and silent, apart from one error log at build time. If several triggers are invalid, the last one overwrites the earlier ones in the single issue.
**Fix:** Use a separate issue id for setup errors, for example `f"{ISSUE_ACTION_FAILED_PREFIX}setup_{device_id}"`. Clear it only on rebuild (`async_build_device` or `clear_issue` in `_async_change_device`) and on removal, not from `_async_run`. Then `async_remove_all_devices` and `async_unload(remove_issue=True)` must delete both ids.

## Info

### IN-01: The Repairs issue for invalid trigger actions drops the offending trigger name

**File:** `custom_components/mqtt_actions/runner.py:104-108`
**Issue:** `_report_setup_error(spec, label, err)` logs `label`, but calls `report_failure(..., TRIGGER_SETUP, error)`. The Repairs issue therefore says "The actions for setup of <device> failed" with no option name. The docstring says the label is shown in Repairs (trigger setup). For a Select with many options the user cannot tell which option is invalid, unless the validation error text names it.
**Fix:** Pass `label` as the trigger placeholder, or embed it in the error string: `f"{label}: {error}"`.

### IN-02: Test button of a trigger without runnable actions is a silent no-op

**File:** `custom_components/mqtt_actions/manager.py:576-578`
**Issue:** Every trigger gets a test button. If the trigger has no actions, or its actions failed validation, `runner.can_run` is False and the handler returns without any log line. A user pressing "Test X" gets no feedback.
**Fix:** Log at debug level or info level ("Test press for %s ignored: no runnable actions"), or skip creating the button for triggers without actions.

### IN-03: A Select with no valid options publishes an invalid discovery payload

**File:** `custom_components/mqtt_actions/model.py:125-143`, `custom_components/mqtt_actions/discovery.py:71-85`
**Issue:** `_select_triggers` drops malformed options and never enforces the two-option minimum. If stored data ends up with no valid options, `_select_component` emits `"options": []`. Core MQTT select requires at least one option and rejects the whole device payload with a log line in core. Only the flow enforces `MIN_OPTIONS`. This applies only to corrupted or hand-edited storage.
**Fix:** Skip publishing discovery, and log a warning, when `len(spec.triggers) < 1` for a Select.

### IN-04: The reconfigure flow indexes stored option keys that the loader treats as optional

**File:** `custom_components/mqtt_actions/config_flow.py:410-422, 482`
**Issue:** `model._select_triggers` tolerates malformed stored options and a missing `actions` key. `_others`, `_selected_option`, `_chooser_schema`, the menu placeholders and `edit_option_details` use `option[CONF_STATE_VALUE]`, `option[CONF_FRIENDLY_NAME]` and `option[CONF_ACTIONS]` directly. A single malformed or actions-less stored option turns the reconfigure flow into an unhandled `KeyError`. The user cannot repair the device through the UI.
**Fix:** Normalize the draft in `async_step_reconfigure`. Drop options that fail `_valid_option` (the model helper) and default `actions` to `[]`.

### IN-05: `signature_hash` is public API used only by tests

**File:** `custom_components/mqtt_actions/manager.py:92-98`
**Issue:** Production code computes the persisted hash with `_hash_fingerprint(device.signature)` in `_trip` and `_restore_tripped`. `signature_hash(title, data)` exists only so tests can compute the same value. The two paths can drift apart unnoticed, and the tests would then still pass against the helper rather than production.
**Fix:** Have production code call `signature_hash` through one shared function, or move the helper into the tests.

### IN-06: Button tombstones live only in memory

**File:** `custom_components/mqtt_actions/manager.py:69, 379-383`
**Issue:** `retired_components` is not persisted. After a restart the republished payload no longer contains the tombstone. Core MQTT does not remove components that are merely omitted. Another Home Assistant instance on the same broker that was offline during the option removal and starts after this instance restarted never sees the tombstone. It keeps an orphaned button entity in its registry. This is relevant to the planned multi-instance phase rather than to the current single-instance release.
**Fix:** Persist the retired keys in the Store, or derive them from the last published component set. Alternatively, note it in the Phase 3 plan.

---

_Reviewed: 2026-09-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
