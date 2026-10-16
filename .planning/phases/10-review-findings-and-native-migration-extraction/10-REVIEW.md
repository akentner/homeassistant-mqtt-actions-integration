---
phase: 10-review-findings-and-native-migration-extraction
reviewed: 2026-10-16T14:52:49Z
depth: standard
files_reviewed: 31
files_reviewed_list:
  - custom_components/mqtt_actions/native_migration.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/takeover.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/translations/de.json
  - .github/workflows/ci.yml
  - .github/workflows/validate.yml
  - README.md
  - docs/troubleshooting.md
  - tests/helpers.py
  - tests/conftest.py
  - tests/test_core_contracts.py
  - tests/test_startup_order.py
  - tests/test_kept_duplicates.py
  - tests/test_takeover.py
  - tests/test_native_replay.py
  - tests/test_native_start.py
  - tests/test_native_entities.py
  - tests/test_export_guard_receiver.py
  - tests/test_hub_removal.py
  - tests/test_docs.py
  - tests/test_repo_structure.py
  - tests/test_translations.py
  - tests/test_cutover.py
  - tests/test_diagnostics.py
  - tests/test_discovery_content.py
  - tests/test_discovery_export.py
  - tests/test_native_cleanup.py
  - tests/test_presence.py
findings:
  critical: 0
  warning: 2
  info: 8
  total: 10
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-10-16T14:52:49Z
**Depth:** standard
**Files Reviewed:** 31
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

Scope: the changed hunks since `7163c7d`, which are:
- `takeover.py`: `ReplayTwinsError`, `_remove_planned`, `_guard_candidates`, `KeptReason`, `kept_duplicates`
- `native_migration.py`: the extraction, `TwinRemoval`, the flush condition, `_refresh_kept_duplicates`, `kept_duplicates_placeholders`
- the hub-removal issue cleanup in `manager.py`
- `mqtt_gateway.async_attempt`
- the translations, the docs, the CI triggers and the new or reworked tests

Verification run on this branch: `uv run pytest tests/` gives 1767 passed and 2 xfailed. `ruff check .` is clean.

Security constraints. I found no violation in the new code:
- **No retained clear on removal (FIX-06).** `_remove_planned` stops at the first row that raises. An enabled row is never removed unless it was disabled first. The device is removed only when no entry at all is left on it.
- **Read-only refresh (FIX-08).** `_refresh_kept_duplicates` and `kept_duplicates` only read the registry. They never publish or write.
- **Broker actions.** No new path runs broker actions.

`_guard_candidates` is a faithful refactor of the old filter in `disable_duplicates`. The parametrized split test proves that every candidate is either disabled or listed as kept.

The main weaknesses are in the Repairs semantics:
- A dismissal can never survive a Home Assistant restart, and the docs give a reason for this that is not true. HA does keep the text when the issue is created with `is_persistent=True`.
- The restart branch is untested, and so are the failure and no-MQTT branches of the refresh.

## Warnings

### WR-01: The kept-duplicates dismissal never survives a restart, and the documented reason is wrong

**Files:**
- `custom_components/mqtt_actions/native_migration.py:724-736`
- `README.md:111-114`
- `docs/troubleshooting.md:119-122`

**Issue:** `_refresh_kept_duplicates` creates the issue with the default `is_persistent=False`. Home Assistant reloads a non-persistent issue in `IssueRegistry._async_load` (`homeassistant/helpers/issue_registry.py`, `else` branch) with `active=False` and `translation_placeholders=None`. So at every HA restart the check `current.active and current.translation_placeholders == placeholders` fails. The issue is then deleted and created again, and that drops `dismissed_version`.

The result: a user who keeps a customized duplicate on purpose, which is a supported state, gets the warning back after every restart, for as long as the duplicate exists. Dismissing it does nothing useful in that steady state.

Both doc pages justify this with "because Home Assistant does not keep the text of this warning across a restart". That is only true for non-persistent issues. For `is_persistent=True`, the same loader restores the issue with `active=True` and the stored `translation_placeholders`. The equality check would then hold, and the dismissal would survive.

**Fix:** Create the issue as persistent. The refresh already deletes it at every start once the list is empty, so a persistent issue cannot go stale. The hub removal deletes it by id (`manager.py:417-426`).
```python
ir.async_create_issue(
    self._manager.hass,
    DOMAIN,
    ISSUE_KEPT_DUPLICATES,
    is_fixable=False,
    is_persistent=True,  # placeholders survive a restart, so an unchanged list keeps the dismissal
    severity=ir.IssueSeverity.WARNING,
    translation_key=ISSUE_KEPT_DUPLICATES,
    translation_placeholders=placeholders,
)
```
Then reword the README and troubleshooting sentences, and change `test_the_docs_describe_the_kept_duplicates_warning`, which asserts the phrase "after a home assistant restart". If you keep the current design on purpose, at least remove the false rationale from both doc pages.

### WR-02: The restart, failure and no-MQTT branches of `_refresh_kept_duplicates` are untested

**Files:**
- `custom_components/mqtt_actions/native_migration.py:706-727`
- `tests/test_kept_duplicates.py:153-197`

**Issue:** Every test in `test_kept_duplicates.py` uses `restart_entry`, which is an entry reload. A reload keeps the issue active with its placeholders. Three branches are never run:
- **Inactive issue.** The `current.active is False` branch, which is the one behind the documented "comes back after a Home Assistant restart". No test seeds `hass_storage["repairs.issue_registry"]` with a dismissed, non-persistent issue. `grep '\.active' tests/` finds only one assertion, at `test_kept_duplicates.py:195`.
- **Failure path.** The `except Exception` path at lines 715-719: the warning is left as it is and the log carries no entity data (T-04-14).
- **No MQTT entry.** The `mqtt_entry_id is None` path, which deletes the issue.

A regression in any of these, for example dropping the `current.active` condition, would pass the suite.

**Fix:** Add three tests:
1. Seed the issue registry storage with `{"domain": "mqtt_actions", "issue_id": "kept_duplicates", "is_persistent": false, "dismissed_version": "2026.9.4", ...}` before setup. Then assert the outcome you intend: the issue comes back un-dismissed today, or stays dismissed after WR-01.
2. Patch `takeover.kept_duplicates` to raise. Assert that an existing issue is unchanged, that one WARNING is logged, and that no entity id appears in the log.
3. Remove the MQTT entry, or patch `gateway.mqtt_entry_id` to return `None`, and assert the issue is deleted.

## Info

### IN-01: TWIN_REJECTED blames the user for any `disabled_by` on the native twin

**Files:**
- `custom_components/mqtt_actions/takeover.py:500-504` and `takeover.py:568-570`
- `translations/en.json` / `de.json`, key `kept_duplicates`

**Issue:** `_is_turned_off` is true for every `disabled_by` value: `INTEGRATION`, `DEVICE`, `CONFIG_ENTRY` and `USER`. The issue text says "Kept because you disabled or hid the native entity". A native row that was moved by the takeover while it carried `disabled_by=INTEGRATION` (from a deleted record restored by a replay) would be reported as a user decision.

**Fix:** Either word the label neutrally ("Kept because the native entity is disabled or hidden"), or count only `disabled_by in (USER, DEVICE)` as a rejection and treat `INTEGRATION` separately.

### IN-02: The catch's refresh is not in a `finally`, so the docstring contract can break

**File:** `custom_components/mqtt_actions/native_migration.py:350,352-438`

**Issue:** The docstring says "Every run that got past its running check ends with the refresh". But an unexpected exception after line 355 skips the refresh at line 438. Possible sources:
- the `unknown` sum at 430-435
- `_rearm_or_log_replay_catch`
- `publisher.async_publish_migrate`, when it raises anything that is not a `HomeAssistantError`, since `async_attempt` catches only that

**Fix:** Wrap the body after the running check in `try: ... finally: self._refresh_kept_duplicates()`. The refresh is synchronous and catches its own errors.

### IN-03: The kept-duplicates issue goes stale when the hub is disabled or a device is deleted

**File:** `custom_components/mqtt_actions/native_migration.py:127-138`

**Issue:** `stop()` does not delete or refresh `ISSUE_KEPT_DUPLICATES`, and neither does `forget()`. A disabled hub entry, or a subentry deleted while the hub runs, leaves the warning with entity ids that no running code will look at again. It stays until the next start, or until a guard create event happens. The cutover hint behaves the same way.

**Fix:** Call `self._refresh_kept_duplicates()` from `forget()`. Optionally delete the issue in `stop()` when the stop is an unload and not an HA shutdown.

### IN-04: "lists every duplicate" is not accurate when more than 10 are kept per reason

**Files:**
- `README.md:108`
- `docs/troubleshooting.md:116`
- `native_migration.py:80-81`

**Issue:** The placeholders show at most `KEPT_DUPLICATES_MAX_SHOWN` (10) ids per reason, followed by "…". The docs say the warning lists every duplicate.

**Fix:** Say "lists the duplicates it keeps enabled, up to ten per reason, with their total".

### IN-05: The English issue text is ungrammatical for a count of 1

**File:** `custom_components/mqtt_actions/translations/en.json`, key `kept_duplicates.description`

**Issue:** "{count} MQTT entities stay enabled" renders as "1 MQTT entities stay enabled", which is the most common case.

**Fix:** Use ICU plural syntax, which the HA frontend's message formatting supports, for example `{count, plural, one {# MQTT entity stays} other {# MQTT entities stay}} enabled ...`. Alternatively, phrase it without the number agreement ("MQTT entities kept enabled: {count}").

### IN-06: Each commit to a PR branch now runs CI and Validate twice

**Files:**
- `.github/workflows/ci.yml:4-9`
- `.github/workflows/validate.yml:4-9`

**Issue:** The filter `push: branches: ["**"]` plus `pull_request` starts two runs for every commit pushed to a same-repo PR branch: hassfest, HACS, ruff and pytest each run twice. The fix for "a branch push never runs" itself is correct.

**Fix:** This is acceptable if wanted. Otherwise, restrict `push.branches` to `["main"]` and rely on `pull_request` for feature branches, or add a `concurrency` group keyed on `github.head_ref || github.ref`.

### IN-07: Duplicate constants in the shared test helpers

**File:** `tests/helpers.py:49,53`

**Issue:** `PREFIX` and `CORE_PREFIX` are both `"homeassistant"`. Two names for one value invite drift now that every test module shares the helpers.

**Fix:** Keep one name, `CORE_PREFIX`, and alias or replace the other.

### IN-08: The contract-pin spy depends on a positional argument index

**File:** `tests/test_core_contracts.py:183-184`

**Issue:** `_recording` reads `device_id = args[2]`. If a future caller passes `device_id=` by keyword, the spy raises `IndexError`. The pin would then turn red with a misleading error instead of `EAGER_TASK_HINT`.

**Fix:** Bind the arguments to the real signature: `inspect.signature(original).bind(*args, **kwargs).arguments["device_id"]`.

---

_Reviewed: 2026-10-16T14:52:49Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
