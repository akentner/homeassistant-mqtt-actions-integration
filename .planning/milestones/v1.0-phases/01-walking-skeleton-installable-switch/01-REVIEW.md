---
phase: 01-walking-skeleton-installable-switch
reviewed: 2026-09-29T00:00:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - .github/dependabot.yml
  - .github/workflows/ci.yml
  - .github/workflows/validate.yml
  - .gitignore
  - hacs.json
  - pyproject.toml
  - README.md
  - .ruff.toml
  - tests/broker/conftest.py
  - tests/broker/test_retain_semantics.py
  - tests/conftest.py
  - tests/test_config_flow.py
  - tests/test_device_ids.py
  - tests/test_discovery.py
  - tests/test_manager.py
  - tests/test_repo_structure.py
  - tests/test_state.py
  - tests/test_toolchain.py
  - tests/test_topics.py
  - tests/test_tracer.py
  - tests/test_translations.py
findings:
  critical: 0
  warning: 7
  info: 6
  total: 13
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-09-29
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

The core design holds up. State payloads are normalised to ON/OFF and never reach templates. Actions are schema-validated before a Script is built, and the raw list is what gets persisted. Unload never clears discovery. Retained replays only move the baseline. I checked the last point against core MQTT's client code: `_retained_topics` de-duplicates retained deliveries per subscription and is cleared on reconnect. That behaviour agrees with the tracker's assumptions. CI actions are SHA-pinned, workflows use `permissions: {}`, and en/de translations have parity.

I found no BLOCKER. There are seven WARNINGs, all about lifecycle robustness and one Repairs semantics bug:

- A reconcile can run on a stopped manager and leak a live subscription.
- A partial `async_start` failure leaks subscriptions and scripts.
- One shared Repairs issue id lets an unrelated success erase a permanent setup failure.
- A malformed Store payload crashes setup for good.
- Hub removal forgets its retry state even when the broker clears failed.
- The broker-writable state topic can queue unbounded runs and log lines.
- The entity value template does not trim while the manager does.

No structural (fallow) findings were supplied.

## Warnings

### WR-01: Reconcile has no `_running` guard, so a late update-listener call revives a stopped manager

**File:** `custom_components/mqtt_actions/manager.py:168-186` (listener in `custom_components/mqtt_actions/__init__.py:30-32`)
**Issue:** `async_stop` sets `_running = False` and clears `self.devices`. `async_reconcile` never checks `_running`. HA runs update listeners as separate tasks. A subentry change followed closely by a reload or unload can run the old manager's `_async_entry_updated` after `async_stop` has finished. The manager then sees every subentry as "missing", calls `_async_add_device`, subscribes to the state topic and publishes discovery. Nothing ever unsubscribes that manager, because `async_unload_entry` has already run. After the new manager starts, every state message runs the actions twice (two Scripts, two subscriptions).
**Fix:**
```python
async def async_reconcile(self, *, startup: bool = False) -> None:
    async with self._lock:
        if not self._running:
            return
        ...
```
`async_start` already sets `_running = True` before it calls `async_reconcile(startup=True)`, so the guard does not break startup.

### WR-02: A failing `async_start` leaks subscriptions and scripts, and a retry doubles them

**File:** `custom_components/mqtt_actions/__init__.py:23-27`, `custom_components/mqtt_actions/manager.py:277-301`, `custom_components/mqtt_actions/mqtt_gateway.py:49`
**Issue:** `gateway.async_subscribe` is the one MQTT call in the start path that is not wrapped in `_async_attempt`. `mqtt.async_subscribe` raises `HomeAssistantError` when the MQTT entry becomes disabled or unavailable after `async_wait_ready` returned. `_async_build` and `async_get_integration` can also raise unexpected errors. When any of these raise from `async_reconcile` or `async_start`:
- `entry.runtime_data` is already set, but HA does not call `async_unload_entry` for a failed setup.
- Device subscriptions and Scripts already created for earlier devices are never released.
- The failing device itself is already in `self.devices` with `unsubscribe = None`.
- A `ConfigEntryNotReady` retry builds a second Manager and doubles the subscriptions, so actions run twice.

`entry.add_update_listener` is also registered only after `async_start` returns, so a subentry change during start is lost.
**Fix:** Wrap the start in a guard that tears down on failure and converts MQTT failures into a retry:
```python
try:
    await manager.async_start()
except HomeAssistantError as err:
    await manager.async_stop()
    raise ConfigEntryNotReady(str(err)) from err
except BaseException:
    await manager.async_stop()
    raise
```
Register the update listener before `async_start`. Alternatively, register `manager.async_stop` through `entry.async_on_unload` at the start of setup.

### WR-03: The single per-device Repairs issue lets a success on one trigger erase a permanent failure on the other

**File:** `custom_components/mqtt_actions/runner.py:77-78` (creation at `custom_components/mqtt_actions/manager.py:385`)
**Issue:** Failures for ON, OFF and the TRIGGER_SETUP (invalid stored actions) all use the issue id `action_failed_<device_id>`, and any successful run deletes it. Trace: the ON actions are invalid, so no script exists and the setup issue is raised. The next OFF message runs its script successfully, and `_async_run` deletes the issue. The ON transition stays permanently broken and silent: no script, no log, no Repairs entry. The same happens when ON fails at runtime and OFF later succeeds. The tests (`test_issue_cleared_after_next_success`) lock this behaviour in, and README line 63 documents it, but it defeats the "failures are surfaced" goal.
**Fix:** Key the run-failure issue by trigger (`action_failed_<device_id>_<trigger>`) and delete only the issue for the trigger that succeeded. Keep the setup issue separate, and delete it only when the scripts are rebuilt (`_async_change_device` already does this). Alternatively, remember which trigger is failing and delete the issue only when that same trigger succeeds.

### WR-04: A malformed Store payload raises `TypeError` and the entry can never start

**File:** `custom_components/mqtt_actions/manager.py:251-258`
**Issue:** `_async_load_store` claims "anything malformed is dropped", but the filter is `value in {PAYLOAD_ON, PAYLOAD_OFF}`. If a stored `last_acted` value is a list or a dict (hand edit, partial write, future format), membership in a set raises `TypeError: unhashable type`. The exception propagates out of `async_setup_entry`. Since the file is re-read on every attempt, the integration is stuck failing. Non-string keys are also kept.
**Fix:**
```python
self._stored_last_acted = (
    {
        key: value
        for key, value in last_acted.items()
        if isinstance(key, str) and isinstance(value, str) and value in {PAYLOAD_ON, PAYLOAD_OFF}
    }
    if isinstance(last_acted, dict)
    else {}
)
```
Also add a test with a malformed payload (`{"last_acted": {"x": []}}`) next to the existing `_parse_published` handling.

### WR-05: Hub removal deletes the Store even when clearing the broker failed, so ghost entities are never retried

**File:** `custom_components/mqtt_actions/manager.py:122-128`
**Issue:** `async_remove_all_devices` ignores the boolean result of `_async_clear_topics` and of the availability clear, then calls `store.async_remove()`. If MQTT is down or not loaded when the hub is removed (the case `test_remove_entry_survives_unavailable_mqtt` covers), the retained discovery configs stay on the broker. Every HA restart re-creates the switch entities from them, and nothing manages, clears or retries them. The persisted `published` set was the only retry mechanism, and it is destroyed in the same step. The README limitations section does not mention this.
**Fix:** Keep failure from being silent and unrecoverable. Options:
- Remember the failed ids somewhere that outlives the entry, such as a separate Store key that is not removed. A later hub setup or a Repairs issue can then clear them.
- At minimum, raise a persistent Repairs issue or `persistent_notification` that lists the topics left on the broker.
- Document the leftover-ghost behaviour in the README limitations.

### WR-06: The broker-writable state topic can queue unbounded runs and flood the log

**File:** `custom_components/mqtt_actions/runner.py:38-51`, `custom_components/mqtt_actions/manager.py:389-422`
**Issue:** Anyone with publish access to a state topic can alternate `ON`/`OFF`. Each edge creates a background task that waits on the per-device lock. There is no queue bound, coalescing or rate limit, so tasks pile up and execute real actions long after the flood ends. Every unknown payload also emits a `LOGGER.warning` with no throttle, which can drown the HA log. The README documents the trust boundary ("can trigger the actions"), but not that the effect is amplified and outlasts the attacker's access.
**Fix:**
- Cap the pending runs per device, for example a counter that is incremented in `enqueue` and decremented in `_async_run`, dropping and logging once (rate-limited) beyond N.
- Rate-limit the unknown-payload warning: log the first occurrence per device at WARNING and later ones at DEBUG until a valid message arrives.

### WR-07: The entity `value_template` does not trim, so the entity and the manager disagree on whitespace payloads

**File:** `custom_components/mqtt_actions/discovery.py:48-49`
**Issue:** The comment says the template exists because the tracker is case-insensitive. The tracker also strips whitespace (`payload.strip().upper()`, `custom_components/mqtt_actions/state.py:32`, and README line 45), but the template is `{{ value | upper }}`. For `" on "` or `"ON\n"` the manager runs the ON actions, while core MQTT sees `" ON "`, rejects it as an invalid state payload, and leaves the switch entity in a stale or unknown state. The tests cover lower-case only (`test_discovery_accepts_lowercase_inbound`).
**Fix:** Use `"{{ value | trim | upper }}"`. Update `test_discovery_payload_full_keys` and add a whitespace case to the entity test.

## Info

### IN-01: A changed MQTT discovery prefix is never noticed, so old discovery topics are orphaned

**File:** `custom_components/mqtt_actions/manager.py:159-166`, `custom_components/mqtt_actions/mqtt_gateway.py:77-79`
**Issue:** The prefix is read live on each publish and clear, but the manager never tracks it. After the user changes the prefix in the MQTT options, new discovery goes to the new prefix. The retained config under the old prefix is never cleared, because `_published` stores ids only and clearing uses the current prefix. `_check_discovery_enabled` also runs only once at start, so a later toggle of discovery does not update the Repairs issue.
**Fix:** Store the prefix used at publish time (for example `{"prefix": ..., "ids": [...]}`) and clear under the old prefix when it differs. Document the limitation until then.

### IN-02: The "never log action data" claim (T-01-10) is weaker than the comments state

**File:** `custom_components/mqtt_actions/runner.py:73-76`, `custom_components/mqtt_actions/manager.py:383-385`
**Issue:** `LOGGER.exception` writes the full traceback and exception message. `str(err)` from schema errors, service-call validation errors (`"... got 'value'"`) or template errors can contain the offending action data or template text. It is also copied into the Repairs issue placeholder. The canary test passes only because its failing service raises a fixed `"boom"`. The Repairs description also renders the raw error as markdown, and the internal trigger tokens `onChangeToOn` and `setup` are shown untranslated.
**Fix:** Soften the comment and the threat claim. Alternatively, log the exception type and a redacted message only. Escape or backtick the error in the issue description.

### IN-03: `expected_lingering_timers` returns True for the whole suite

**File:** `tests/conftest.py:32-35`
**Issue:** The comment justifies it with the mocked MQTT client's misc-loop timer, but the override applies to every test and also hides lingering timers created by this integration, such as a `Store.async_delay_save` timer left behind after a path that skips `async_save`. It weakens the leak detection the PHACC harness would otherwise give the lifecycle tests.
**Fix:** Apply it only to tests that need it, or narrow it to the mqtt-mock fixtures. Run the lifecycle tests without the override to confirm nothing of this integration lingers.

### IN-04: The gateway catches a bare `KeyError`, and one decode branch is effectively dead

**File:** `custom_components/mqtt_actions/mqtt_gateway.py:46,65-68`
**Issue:**
- Any `KeyError` raised inside `mqtt.async_publish` is reported as "MQTT integration is not loaded", which can mask an unrelated bug.
- `mqtt.async_subscribe` is called with the default encoding (utf-8), so `msg.payload` is always `str`, and the `bytes` decode branch never runs.

**Fix:** Narrow the `try` to the lookup that can actually miss, or check `mqtt.mqtt_config_entry_enabled`/entry state explicitly. Drop the bytes branch or pass `encoding=None` deliberately.

### IN-05: Queued runs of retired scripts are dropped silently on reconfigure

**File:** `custom_components/mqtt_actions/runner.py:69-70,101-109`
**Issue:** When a device is reconfigured, `async_retire_scripts` unloads the old Scripts, which also stops an in-flight run. A run that was queued but not started is discarded without a log line, although its edge already moved the baseline, so the change is never acted on. This is defensible but undocumented.
**Fix:** Log at debug or info when a queued run is discarded, and note the behaviour in the README.

### IN-06: Hygiene nits

**File:** `.gitignore`, `custom_components/mqtt_actions/config_flow.py:37`
**Issue:**
- `.gitignore` covers only `.planning/research/.cache/`. The untracked `.gsd/`, `.planning/state.json` and `.planning/milestone.lock` are one `git add -A` away from being committed to a public HACS repository.
- `CONF_NAME = "name"` duplicates `homeassistant.const.CONF_NAME`.
- Both CI workflows trigger on `push` and `pull_request` without a branch filter, so PR branches run everything twice. This is intentional per `test_push_trigger_has_no_branch_filter`, so it is only a note.

**Fix:** Add `.gsd/`, `.planning/state.json` and `.planning/milestone.lock` to `.gitignore`, and import `CONF_NAME` from `homeassistant.const`.

---

_Reviewed: 2026-09-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
