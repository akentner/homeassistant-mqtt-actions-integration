---
phase: 04-operations-recovery-and-release
reviewed: 2026-10-02T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/diagnostics.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/modes.py
  - custom_components/mqtt_actions/portability.py
  - custom_components/mqtt_actions/presence.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/retrigger.py
  - custom_components/mqtt_actions/select.py
  - custom_components/mqtt_actions/sensor.py
  - custom_components/mqtt_actions/services.py
  - custom_components/mqtt_actions/services.yaml
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/trust.py
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - .github/workflows/validate.yml
  - pyproject.toml
findings:
  critical: 0
  warning: 12
  info: 4
  total: 16
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-10-02
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

All 24 listed files were read in full. `actions.py`, `runner.py`, `discovery.py`, `state.py` and the translations were read as callees. `ruff check custom_components` passes.

The core trust gates hold up. Broker documents go through `parse_document` and the structure check. Mirrors get no Script until the approval hash matches. The static denylist and the runtime `GuardedTemplate` guard both apply to mirrors. Retained re-trigger requests are dropped. Heartbeat and re-trigger parsing never raises. The export and import file handling is sound: bare-name regex, 0700/0600 permissions, `O_NOFOLLOW`, a regular-file check and a bounded read. The release workflow reads the tag from an env var and validates it, so there is no injection.

I found no BLOCKER. The weaknesses are these:

- **Broker-input hardening.** The re-trigger rate limiter can be flushed with fake device ids, heartbeats are not throttled, and a forged adoption marker or a forged duplicate-id heartbeat raises Repairs flows whose confirm step is destructive.
- **Approval binding and trust-level changes.** The approval hash is weaker than the runtime inputs, and adoption silently lifts the mirror restrictions.
- **Import and export policy gaps.**
- **Teardown robustness.**
- **Release supply chain.**

No structural (fallow) findings were supplied.

## Warnings

### WR-01: Re-trigger rate limit is flushed by unknown device ids, and every unknown id produces an ack

**File:** `custom_components/mqtt_actions/retrigger.py:379-402` (and `404-420`)
**Issue:**
- `_admit` records `_last_accepted[device_id]` before `_decide` checks that the device exists. Any syntactically valid device id from the topic therefore creates an entry.
- At 257 entries (`MAX_TRACKED_INSTANCES` = 256) the `while len(...) > MAX` loop evicts the oldest entry. A broker client that sends 257 requests for random ids within 5 s evicts the legitimate device's entry. The per-device interval limit is gone, and the same client can then re-trigger a real device at flood rate.
- The re-trigger path deliberately bypasses the circuit breaker, so this limit is the only loop guard. `_seen` holds only 128 ids, so an id sent earlier can be replayed once 128 newer ones have pushed it out, within the 60 s freshness window.
- Each unknown-device request also makes this instance publish an `error/unknown_device` ack to an attacker-chosen requester topic. That is one outbound publish per inbound message, with no global limit.

**Fix:** Check that the device exists before any state is recorded, and drop silently or answer without touching `_last_accepted`. Add a global token bucket for requests and acks.
```python
def _decide(self, device_id, request):
    if (device := self._manager.device(device_id)) is None:
        return None  # unknown ids never touch limiter state; the caller reports no_answer
    if not self._admit(device_id, request):
        return None
    ...
```
Evict by age only. Never evict an entry that is still inside its interval to make room for a new id.

### WR-02: Forged adoption marker or forged duplicate-id heartbeats raise destructive Repairs flows

**Files:** `custom_components/mqtt_actions/sync.py:528-547`, `608-634`; `custom_components/mqtt_actions/manager.py:1532-1534`, `1581-1582`; `custom_components/mqtt_actions/repairs.py:126-158`; `custom_components/mqtt_actions/presence.py:359-372`; `custom_components/mqtt_actions/manager.py:1086-1099`
**Issue:**

*Adoption marker:*
- Any broker client can publish a structurally valid document on an owned device's config topic. It needs `owner` set to anything other than this instance and `transferred_from` containing this instance's id. The id is public in the availability and heartbeat topics.
- `_check_owned` then calls `_transferred_to`, which puts the device in `transferred_away`.
- From then on `async_publish_config` and `async_publish_discovery` return early, even on resync, start and reconnect. A healthy, online owner silently stops healing and publishing until a restart.
- Nothing checks that the claimant is a known peer from the roster or that this owner was ever offline or forced.
- The resulting Repairs flow (`TransferredRepairFlow`) calls `async_release_device_locally`. That removes the owner's subentry, so the user's configured actions are deleted.
- The confirm text says only "forgets the device locally". It does not say the configured actions are deleted.

*Duplicate-id heartbeats:*
- Two forged heartbeats with this instance's id and a different session within 90 s set `_duplicate_detected` and create a fixable issue.
- `DuplicateIdRepairFlow` then calls `async_resolve_duplicate_id`, which releases and deletes all local devices and rotates the instance id.

Both are user-confirmed. Still, one or two unauthenticated messages can steer an admin into an irreversible deletion of their device configuration.

**Fix:**
- Honour a transfer claim only when the claimant is in the heartbeat roster (`presence.peer_status(parsed.owner) is not None`).
- Require a different session for duplicate detection from an id that is also seen in the availability roster.
- State in both confirm texts that the local device configuration and actions are deleted.
- Offer an export before deleting. For example, `async_release_locally` could call `build_export` and write a backup file first.

### WR-03: `actions_hash` lower-cases StateValues, but the runtime passes the original-case value to templates

**Files:** `custom_components/mqtt_actions/document.py:123-145`; `custom_components/mqtt_actions/manager.py:1634-1640`, `1738-1752`; `custom_components/mqtt_actions/retrigger.py:416`, `444-451`
**Issue:**
- The approval binding hashes `trigger.value.lower()`. `accepted` maps the lower-cased input to the original-case `trigger.value`, and that value is passed as the template variable `state`.
- An approved mirror whose owner changes only the case of a Select StateValue (for example `Away` to `away`) keeps the same `actions_hash`. No new approval is requested.
- The approved Script then runs with a different `state` value, so `{{ state == 'Away' }}` or `{{ state }}` payloads behave differently.
- The approval gate is meant to bind everything that can influence execution.

**Fix:** Bind the exact value, or pass the lower-cased canonical value to templates. The hash is computed locally and never read from the wire, so changing it needs no protocol bump. It invalidates existing approvals once, which is acceptable.
```python
pairs = sorted(([trigger.value, trigger.actions] for trigger in spec.triggers.values()), key=lambda p: p[0].lower())
```

### WR-04: Adopting an approved mirror silently drops the restricted build and the templated-service guard

**Files:** `custom_components/mqtt_actions/manager.py:897-960` (`async_adopt`, `_async_adopt_locked`), `1399`; `custom_components/mqtt_actions/runner.py:48-135`
**Issue:**
- A mirror's Script is built `restricted=True`, so service-name templates are wrapped in `GuardedTemplate` and a name that resolves to a denied service aborts the run.
- `async_adopt` accepts any `APPROVED` mirror. Reconcile then builds the new owned device through `_async_add_device`, which calls `async_build_device(spec)` unrestricted.
- Actions that were approved only under the guard, such as `action: "{{ 'shell_' ~ 'command.x' }}"`, then run unguarded and may call denied services. Approval does not close this gap, because the approval dialog lists the templated names as "real service is only known when the action runs", with the guard as the safety net.
- Nothing tells the user that adoption changes the trust level. `force=True` does not matter here, because the approval check always applies.

**Fix:** Refuse adoption (`ADOPT_NOT_APPROVED` or a new reason) when `info.templated` is non-empty, or keep the guard for devices that came from a mirror. At minimum, state the trust-level change in the service description.

### WR-05: Import applies the broker denylist, so export-as-backup cannot restore a legitimate owned device

**Files:** `custom_components/mqtt_actions/portability.py:278-283`; `custom_components/mqtt_actions/const.py:66-67`
**Issue:**
- `const.py` says owned actions stay unrestricted. A user can therefore configure an owned device that calls `shell_command.*`, `rest_command.*` or `mqtt.publish`.
- The export module documents these files as backups. `_prepare_item` rejects any item that `analyze_spec(...).denied` flags with `denied_service`, so re-importing the user's own export fails.
- Either the policy (imports are untrusted files) or the backup claim is wrong. The user has no override: the admin-only service has no `allow_denied` flag, and a rejected import creates nothing.

**Fix:** Decide the intent and make it explicit. Either add an admin `allow_denied_services: true` field (default false) with a log line that names only counts, or remove the "backup" wording and document that devices with denied services cannot be imported.

### WR-06: Import skips the UI option rules, so it can create Select devices the UI would refuse

**Files:** `custom_components/mqtt_actions/portability.py:244-291`; `custom_components/mqtt_actions/model.py:202-234`; `custom_components/mqtt_actions/discovery.py:68-80`
**Issue:**
- `_prepare_item` goes through the document parser only. The UI rules in `validate_option` are not applied: duplicate friendly names (case-insensitive), the reserved friendly name `none`, and a non-stripped friendly name.
- An imported owned Select with two identical friendly names, or one named `None`, gets those names as `options` in the retained discovery. Core MQTT select maps names back through the command template, so the second option cannot be selected and `None` renders as unknown.
- The device is created and published to every instance, and the UI cannot edit it into a valid state.

**Fix:** In `_prepare_item`, run `validate_option(value, friendly, others)` for each option (`editing=False`) after parsing, and raise `PortabilityError(REASON_INVALID_DEVICE, index)` on any error. Run `validate_breaker` for the owned path as well. The parser already does this for received documents.

### WR-07: `_is_template` ignores `{#`, which Home Assistant treats as a template marker

**Files:** `custom_components/mqtt_actions/document.py:436-438`; `custom_components/mqtt_actions/actions.py:59-61`
**Issue:**
- `homeassistant.helpers.template.is_template_string` treats `{#` as a template marker (verified in the installed core, `template/__init__.py:176`). `cv.dynamic_template` therefore accepts `action: "{# x #}shell_command.foo"`, and core renders it to `shell_command.foo`.
- `document._is_template` checks only `{{` and `{%`. Such a name is neither `denied`, `templated` nor `residual`. It does not appear in the approval dialog's templated list.
- The runtime guard still blocks it for mirrors. The static layer is therefore inconsistent: the approval view omits it from the templated warning list, and the import denylist and the mirror pre-check (`_refuse_denied`) treat it as a harmless static name.

**Fix:** Mirror core's definition in both helpers.
```python
def _is_template(value: str) -> bool:
    return "{" in value and ("{{" in value or "{%" in value or "{#" in value)
```
`actions._is_template` has the same gap. Better, import `template.is_template_string` from core in both places.

### WR-08: A failing store save in `async_stop` skips the whole teardown and leaves a half-unloaded entry

**Files:** `custom_components/mqtt_actions/manager.py:663-693`; `custom_components/mqtt_actions/__init__.py:68-79`
**Issue:**
- `async_stop` awaits `self._store.async_save(...)` before it unsubscribes the devices, unloads the Scripts and publishes `offline`. If the save raises (disk full, permission), the remaining steps are skipped.
- `async_unload_entry` has already unloaded the platforms and released the breakers. It propagates the exception. The entry ends in a failed-unload state with live MQTT subscriptions, running Scripts and no offline availability.
- The same applies to the failed-setup cleanup in `async_setup_entry`, where a second exception replaces the original one.

**Fix:** Wrap the save so teardown always proceeds.
```python
try:
    await self._store.async_save(self._data_to_save())
except OSError:
    LOGGER.exception("The state could not be saved while stopping")
```
Use `try/finally` around the rest if other steps can raise.

### WR-09: Hub removal with "delete devices" clears topics of devices that another instance adopted

**File:** `custom_components/mqtt_actions/manager.py:338-366`
**Issue:**
- `async_remove_all_devices` runs without a manager and clears discovery, config and state for every id in the persisted `published` set plus the current subentries.
- `_async_remove_device` protects against exactly this case with `adopted_away`, because the topics belong to the adopter. `async_remove_all_devices` has no equivalent. `transferred` is kept in memory only, and the removal path has no manager.
- If instance A still holds a device that B adopted (A offline when B adopted, or the repair was never confirmed) and the user removes A's hub with deletion enabled, A erases B's retained config, discovery and state. The device disappears for B and for every mirror.

**Fix:** Persist transferred-away ids in the Store (a `STORE_TRANSFERRED` set). Skip them in `async_remove_all_devices` and in `_async_orphan_cleanup`. As a minimum, document the risk in the delete option text.

### WR-10: `_checked_size` lets `RecursionError` escape for deeply nested `data`

**File:** `custom_components/mqtt_actions/services.py:218-226`
**Issue:**
- `json.dumps(data)` on a deeply nested dict raises `RecursionError` at roughly 1000 levels. Only `TypeError` and `ValueError` are caught, so a nested `data` argument bypasses the service's translated-error design and returns a traceback.
- The file path is safe, because orjson caps the depth. The service-call path is not.
- It needs an admin to call the service, so the impact is low. It is still an uncaught error in the input-validation layer that is meant to turn every flaw into `import_rejected`.

**Fix:**
```python
except (TypeError, ValueError, RecursionError) as err:
    raise PortabilityError(REASON_BAD_FORMAT) from err
```

### WR-11: Heartbeat handling writes entity state per message with no per-peer throttle

**File:** `custom_components/mqtt_actions/presence.py:332-356` (with `sensor.py:33-49`)
**Issue:**
- Every accepted heartbeat calls `_arm_expiry()` and `_send_signal()`. That makes the roster sensor call `async_write_ha_state`, and `last_seen` changes with every message.
- Legitimate peers send every 30 s. A broker client that floods valid heartbeats, from 256 spoofed ids or from one id, drives state writes and event-bus traffic at message rate. The 1 KB cap does not limit the rate.
- Because `Roster.observe` refuses new peers once 256 rows are fresh, the same client can also keep a real instance out of the roster (T-04-12, accepted). That affects the expected set of a re-trigger and the adoption offline check.

**Fix:**
- Ignore a heartbeat from a known peer when the previous one is less than about 5 s old, and refresh `seen` without signalling.
- Only dispatch the signal when the online set changed.
- Optionally keep `last_seen` out of the state attributes.

### WR-12: Release workflow does not verify that the tag commit is on the default branch

**File:** `.github/workflows/release.yml:3-9`, `11-33`, `49-66`
**Issue:**
- Any `v*.*.*` tag push triggers the release job, including a tag on a commit that never passed review on `main`.
- The job checks only that the tag matches `manifest.json` at that commit. It then runs `gh release create` with `contents: write`.
- HACS consumes releases, so a stray or malicious tag publishes unreviewed code. A repo-level tag protection rule would help, but the workflow itself should not depend on it.
- Related: `validate.yml`'s `hacs` job sets no `permissions`, so it inherits the workflow-level `{}`. Confirm that `hacs/action` works with a token that has no scopes.

**Fix:** Add a step to `check-version`, with `fetch-depth: 0` on the checkout.
```yaml
- uses: actions/checkout@... 
  with: { persist-credentials: false, fetch-depth: 0 }
- run: |
    git fetch origin main
    git merge-base --is-ancestor "$GITHUB_SHA" origin/main || { echo "::error::tag is not on main"; exit 1; }
```

## Info

### IN-01: Diagnostics can raise, and the roster exposes broker-supplied names

**File:** `custom_components/mqtt_actions/diagnostics.py:62-91`
**Issue:**
- `_device_row` calls `content_hash(build_content(device.spec))`, which raises `ValueError` on NaN or inf in action data. `async_publish_config` guards exactly this case (`except ValueError, TypeError`). A diagnostics download fails at the moment it is most needed.
- `_roster` includes peer `name` values from broker heartbeats, and `_hub` includes the base topic and instance name. The module docstring says "never device names", and the redaction list does not cover them. Instance names of other installations end up in bug-report attachments.

**Fix:** Catch `(ValueError, TypeError)` and return `"hash": None` for that row. Drop `name` from `_roster`, or document it.

### IN-02: Runner logs broker-derived validation text for mirrors

**File:** `custom_components/mqtt_actions/runner.py:137-141`, `227-230`
**Issue:**
- `_report_setup_error` logs `error = str(err)[:500]` from the deep validation of a mirror's actions. That text can quote broker-supplied keys or values. `LOGGER.exception("Actions ... failed")` also logs the full traceback with service-call errors.
- Other modules state that nothing from a broker document reaches a log line except fixed reason codes and quoted, capped values. This path is inconsistent, though the names themselves are validated printable.

**Fix:** For `restricted` devices, log the reason class only (`type(err).__name__`) and keep the full text out of the log. The Repairs placeholder already escapes it.

### IN-03: A rename or other content change on a mirror resets a tripped breaker

**File:** `custom_components/mqtt_actions/manager.py:1333-1352` (`_update_mirror`)
**Issue:**
- Any content change, including a pure rename, creates a fresh `CircuitBreaker` and drops the tripped state. A remote owner whose approved actions loop can release the local breaker by renaming the device.
- The approval hash correctly excludes the name. The breaker reset follows `content_hash`, which includes it.

**Fix:** Reset the breaker only when `parsed.actions_hash` differs from the previous `info.actions_hash`.

### IN-04: Release job and CI have no `timeout-minutes`, and branch pushes run twice

**Files:** `.github/workflows/ci.yml:3-10`, `release.yml:49-66`, `validate.yml:3-12`
**Issue:**
- No job sets `timeout-minutes`, so a hung Mosquitto or hassfest step uses the runner default of 6 hours.
- Every PR branch push runs both the `push` and the `pull_request` trigger, so CI and validation run twice.

**Fix:** Add `timeout-minutes: 15` per job. Restrict `push` to `branches: [main]`.

---

_Reviewed: 2026-10-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
