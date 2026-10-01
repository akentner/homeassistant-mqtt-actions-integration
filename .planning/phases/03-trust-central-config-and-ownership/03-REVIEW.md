---
phase: 03-trust-central-config-and-ownership
reviewed: 2026-10-01T00:00:00Z
depth: standard
files_reviewed: 39
files_reviewed_list:
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/trust.py
  - docs/broker-acl.md
  - tests/broker/conftest.py
  - tests/broker/test_acl.py
  - tests/conftest.py
  - tests/documents.py
  - tests/fake_broker.py
  - tests/test_config_flow.py
  - tests/test_config_flow_delete.py
  - tests/test_config_flow_select.py
  - tests/test_document.py
  - tests/test_fake_broker.py
  - tests/test_hub_removal.py
  - tests/test_manager.py
  - tests/test_manager_breaker.py
  - tests/test_manager_select.py
  - tests/test_multi_instance.py
  - tests/test_repairs_flow.py
  - tests/test_repo_structure.py
  - tests/test_sync_follower.py
  - tests/test_sync_owner.py
  - tests/test_topics.py
  - tests/test_translations.py
  - tests/test_trust.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-10-01
**Depth:** standard
**Files Reviewed:** 39
**Status:** issues_found

## Summary

Reviewed the Phase 3 trust boundary (strict document parser, hash-bound approval, static denylist plus run-time guard,
owner and follower sync, tombstones and prune) in full, plus the supporting model, state and flow code. The baseline is
good: the 780 tests pass, ruff is clean, and the run-time `GuardedTemplate` covers every service-name template position I
tried (action, service, service_template, if/then/else, repeat count/while/for_each, parallel, sequence, choose and
default, data and data_template).

The findings below were each reproduced against the real code (scratch tests outside the repo, no source touched).
The most serious one defeats the central "what you see is what you approve" guarantee of the approval dialog.

No structural findings (fallow) were provided for this review.

## Critical Issues

### CR-01: Select options with colliding labels hide actions from the approval dialog

**File:** `custom_components/mqtt_actions/trust.py:152` (root cause `custom_components/mqtt_actions/document.py:485-490`)
**Issue:** `_actions_yaml` does `sections = dict(approval_sections(spec))`. For a Select, the label is
`f"{friendly_name} ({state_value})"`. The broker controls both parts and only the state value must be unique
(case-insensitive), so two options can produce the identical label: option 1 with friendly name `a (b` and value `c`,
option 2 with friendly name `a` and value `b (c`; both yield `a (b (c)`. `dict()` then keeps a single entry, the later
one, and silently drops the other action list. `actions_hash` is computed over every option, so the approval covers
actions the user never saw. Reproduced: option 1 `lock.unlock`, option 2 `light.turn_on`; the rendered YAML contains only
`light.turn_on`, and `truncated` is False. The denylist does not help here, because `lock.unlock` and any other
non-denied service are allowed. This is a bypass of the hash-bound informed approval (TRU-02, T-03-28/29) by a hostile
broker writer, and a user cannot tell it happened.
**Fix:** Never collapse sections into a dict. Dump a list of single-key mappings (or add an index to the label) so every
trigger with actions is shown, and refuse the approval if two labels would be equal:
```python
def _actions_yaml(spec: DeviceSpec) -> tuple[str, bool]:
    sections = [{f"{index}. {label}": actions} for index, (label, actions) in enumerate(approval_sections(spec), 1)]
    try:
        text = yaml_dump(sections)
    ...
```
Add a regression test with the colliding option pair that asserts both action lists appear in `actions_yaml`.

### CR-02: A foreign claim for an owned device becomes a mirror during startup (no-takeover rule broken)

**File:** `custom_components/mqtt_actions/manager.py:379-405`, `custom_components/mqtt_actions/sync.py:343-399`
**Issue:** `async_start` subscribes the config wildcard (`self.sync.async_start()`, line 400) and only afterwards
populates `devices` (`async_reconcile`, line 402). `async_start` holds no lock in between. Retained documents delivered
while the later subscribes and `_async_orphan_cleanup` are awaited start `_async_ingest` tasks that take the (free) lock
and see `device_id not in manager.devices`. A retained document of a foreign owner for an id this instance owns then
passes `parsed.owner == manager.instance_id` (false) and creates a mirror via `async_apply_mirror`. Reproduced with the
fake broker once the subscribe call yields to the loop (as the real network subscribe does): `devices` and `mirrors`
both contain the id, no `ownership_claim` issue is raised, and an approval request for the owner's own device appears.
Consequences:
- `runner._scripts` is keyed by device id only. Approving the bogus mirror runs `runner.async_build_device(..., restricted=True)`
  and replaces the owner's own Script with the foreign actions.
- A later prune or tombstone path calls `async_remove_mirror(device_id)`, whose `runner.async_unload(device_id)` kills the
  owner's real Script (the `device_id not in manager.devices` guard exists in `_async_remove` but not in `_async_prune`
  or `async_remove_mirror`).
- Two state subscriptions and a stale Store entry exist for one device.
The existing tests pass only because the fake broker never yields between subscribe and reconcile.
**Fix:** Make the ingest wait until the owned devices are registered. Either hold `self._lock` from before
`sync.async_start()` until after the reconcile and first publish (split `async_reconcile` into a locked inner method),
or set a `manager.ready` flag that `_async_ingest` and `_check_owned` check under the lock, replaying nothing until it is
set. Also add `device_id not in manager.devices` to the `stale` filter in `_async_prune` and an early return in
`async_remove_mirror`/`async_apply_mirror`-created state for owned ids. Add a test whose fake gateway yields after each
subscribe.

### CR-03: A device or instance name over 64 characters makes the owner's own document unparseable (republish loop, no sync)

**File:** `custom_components/mqtt_actions/config_flow.py:93-94,293-295`, `custom_components/mqtt_actions/document.py:285-296`,
`custom_components/mqtt_actions/sync.py:455-481`
**Issue:** The flows only check that the Switch name and the hub instance name are non-empty after `strip()`.
`parse_document` rejects `name` and `owner_name` with `_invalid_label` (not printable, or longer than
`MAX_TEXT_LENGTH` = 64). The owner publishes such a document without checking it, every follower drops it
(`bad_name` or `bad_owner_name`, only a warning), and the owner's own echo fails `_parse` in `_check_owned`, which is
classified as "foreign overwrite": a false `doc_overwritten` Repairs error is raised and `_heal` republishes. The echo of
each republish triggers the next one, so the config topic is rewritten every `REPUBLISH_THROTTLE_SECONDS`. Reproduced:
a Switch named 70 characters gives `doc_overwritten_<id>` immediately and one config publish per 61 s window
(publishes 3, 4, 5, 6 in four windows). A long instance name does this for every device of the instance. The Select
flow does validate (`validate_option`), the Switch and hub flows do not. The same loop occurs when an owned document
exceeds `MAX_DOCUMENT_BYTES` or `MAX_ACTION_DEPTH`.
**Fix:** Validate name and instance name with the same rule the parser applies (`_invalid_text`) in `_async_handle_form`,
`_async_settings_form` and the hub `async_step_user` (new `name_invalid` error keys in both translations). Defensively,
in `Manager.async_publish_config` run the built payload through `parse_document` and refuse to publish (log once, no
heal) when it is rejected; and in `_check_owned` treat "my own owner id, unparseable, content equals nothing" differently
from a foreign write only when the payload really is foreign (for example compare against the last published payload text).

## Warnings

### WR-01: `parse_document` raises `TypeError` instead of a typed rejection for unhashable `kind` or `run_mode`

**File:** `custom_components/mqtt_actions/document.py:293,297`
**Issue:** `kind not in {SUBENTRY_SWITCH, SUBENTRY_SELECT}` and `document.get(CONF_RUN_MODE) not in {...}` hash the value.
A document with `"kind": []`, `{}` or `"run_mode": {}` raises `TypeError: cannot use 'list' as a set element`
(reproduced). The module contract says the only way to fail is `DocumentRejectedError` with a reason code. Callers
happen to catch `Exception` (sync ingest, `_parse_mirrors`, `_parse`), so nothing crashes, but the fixed-reason log,
reason codes and any caller that catches only `DocumentRejectedError` are bypassed.
**Fix:** Check types first: `if not isinstance(kind, str) or kind not in (...)`, same for `run_mode`. Add the cases to
`tests/test_document.py`.

### WR-02: The approval dialog does not show what the hash binds (startup flag), and its text is inaccurate

**File:** `custom_components/mqtt_actions/trust.py:150-158`, `custom_components/mqtt_actions/translations/en.json` (`approval_required.fix_flow.step.confirm.description`), `de.json`
**Issue:** `actions_hash` covers `run_on_startup`, and an approved mirror with `run_on_startup` runs its actions on the
first retained state after every Home Assistant start, integration reload and reconnect. The dialog shows only the
action lists and says they run "whenever the state of the device changes". The user cannot see that a device also
fires at startup, and a change of only that flag produces a new request that looks identical to the old one.
**Fix:** Add `run_on_startup` (and the run mode) to the view, for example as a first line of the YAML or a separate
placeholder, and adjust the dialog text in both languages.

### WR-03: Denylist leaves other host-level and code-execution services callable by approved mirrors

**File:** `custom_components/mqtt_actions/const.py:64-81`
**Issue:** Not on the list: `update.install` (installs core, add-on or HACS updates and thereby arbitrary code),
`button.press` and `homeassistant.turn_on`/`toggle` against restart or install entities, `downloader.download_file`,
`pyscript` services (domain), `recorder.disable`, `system_log` and `logger.set_level`. The README presents the denylist
as the hard layer and lists only scripts, automations, scenes, device actions, events and `notify` as residual risk.
The approval gate still applies, but the documented residual-risk list is incomplete and the dialog does not flag these.
**Fix:** Add `update.install` and the `pyscript` and `downloader` domains to the denylist, mention `button.press` and
`homeassistant.turn_on/toggle` on script, scene and button entities in the residual list (and report them from
`_note_service`), and state in the README that the list is best effort.

### WR-04: Run mode and breaker settings are not covered by the approval and can be changed remotely

**File:** `custom_components/mqtt_actions/document.py:110-116`
**Issue:** By design (A5) `actions_hash` ignores `run_mode`, `breaker_max_runs` and `breaker_window`. An owner (or forger)
can therefore set the breaker to 100 runs per 1 s or switch a device to `restart` after approval, and the local
loop-protection of the follower is weakened without a new request. This is documented as intended, but the README claims
the approval is "bound to the hash of the actions" without saying that the local safety limits are remote-controlled.
**Fix:** Either clamp mirrored breaker values to a local floor (for example never above the defaults) or include them in
the approval hash and view; at minimum document it in the trust model section.

### WR-05: Mirror device ids are accepted unbounded and unvalidated

**File:** `custom_components/mqtt_actions/topics.py:77-84`, `custom_components/mqtt_actions/sync.py:343-399`
**Issue:** `parse_config_topic` accepts any single topic level, so a hostile id of tens of kilobytes is accepted. It is
then used verbatim in the Store key, in `approval_`, `blocked_`, `schema_too_new_` and the other issue ids, in state and
test subscriptions and in registry lookups. `_shown` caps log output, but nothing caps persistence. Owned ids are always
uuid4 strings.
**Fix:** Reject ids that are not a canonical uuid (or at least longer than 64 characters or outside `[A-Za-z0-9_-]`) in
`parse_config_topic` for the follower path, with the fixed reason logged by `_shown`.

## Info

### IN-01: `repairs.py` imports `voluptuous` while the rest of the integration uses `probatio`

**File:** `custom_components/mqtt_actions/repairs.py:11`
**Issue:** Project rule (CLAUDE.md stack section) is `import probatio`; `actions.py` and `config_flow.py` follow it. The
alias keeps it working on core 2026.9 but it is the legacy spelling and fails the "single validation library" convention.
**Fix:** `import probatio` and `probatio.Schema({})`.

### IN-02: Service-name detection logic is duplicated and can drift

**File:** `custom_components/mqtt_actions/actions.py:59-61`, `custom_components/mqtt_actions/document.py:362-368`, `custom_components/mqtt_actions/trust.py:43`
**Issue:** `_is_template` exists twice (and only knows `{{` and `{%`, not core's `{#`), and the service key tuple exists
as `_SERVICE_KEYS` (document) and `GUARDED_KEYS` (trust). A change in one place silently leaves the static analysis and
the run-time guard disagreeing. (I confirmed that core rejects a `{# c #}name` action at schema level today, so there is no
live bypass.)
**Fix:** Keep one definition in `document.py` (or a tiny shared module) and import it in `actions.py` and `trust.py`.

### IN-03: Runner logs broker-derived validation error text for mirrors

**File:** `custom_components/mqtt_actions/runner.py:137-141`
**Issue:** `_report_setup_error` logs `LOGGER.error("Invalid actions for %s of device %s: %s", label, spec.name, error)` with
the schema/deep-validation message for restricted builds too. The sync module promises that no payload data reaches a log
line; deep validation errors can quote values from the document. The Repairs placeholder is escaped, the log line is not.
**Fix:** For `restricted` builds log only the label, the device name and a fixed reason; keep the full text for owned devices.

---

_Reviewed: 2026-10-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
