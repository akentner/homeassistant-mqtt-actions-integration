---
phase: 03-trust-central-config-and-ownership
reviewed: 2026-10-01T12:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/trust.py
  - README.md
  - tests/test_trust.py
  - tests/test_multi_instance.py
  - tests/test_sync_follower.py
  - tests/test_document.py
findings:
  critical: 0
  warning: 1
  info: 5
  total: 6
status: issues_found
---

# Phase 03: Code Review Report (iteration 2, fix re-review)

**Reviewed:** 2026-10-01T12:00:00Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Scope: the fix commits 60a1f22..6b2ad50 (`git diff 2531c0c..HEAD`), reviewed for correctness and regressions. The full
suite passes (814 tests). No blocker was found. CR-01, CR-02, CR-03 and WR-01, WR-02, WR-03, WR-05 are fixed as
described. One new warning concerns the CR-03 guard: it turns a loop into a silent failure. The rest are minor.

Answers to the five review questions:

(a) Lock scope in `Manager.async_start` (`manager.py:405-410`): no deadlock. `asyncio.Lock` is not reentrant, so I
checked every callee that now runs under the lock: `sync.async_start`, `_async_orphan_cleanup`,
`_async_reconcile_locked`, `_async_add_device`, `_async_change_device`, `_async_remove_device`, `async_publish_config`,
`async_publish_discovery` and `_async_publish_owned`. None of them takes `self._lock`. Every path that does take it
(`async_reconcile`, `async_approve`, `async_stop`, `_async_republish`, `_async_prune`, `_async_ingest`, `_async_remove`,
`_async_heal`) runs in its own task or is awaited from outside the lock. The MQTT message callbacks are sync
`@callback`s that only create background tasks, so a retained message replayed during a subscribe cannot block on the
lock. The only cost is latency. Subscribe, orphan-clear publishes and discovery publishes now hold the lock for the whole
start, so a slow broker delays `async_stop`, a reconnect republish and a prune. Publishing under the lock already
existed. The failure path is also safe: an exception in `async_start` releases the lock via the context manager before
`__init__.py` calls `async_stop`.

(b) CR-02 by another route: no remaining route found. The ingest re-checks `device_id not in manager.devices` under the
lock (`sync.py:361`). `async_apply_mirror` (`manager.py:573`), `async_remove_mirror` (`manager.py:716`), `_async_remove`
(`sync.py:340`) and the prune (`sync.py:245`) check it too. `_async_restore_mirrors` drops owned ids. Two side effects
are listed as IN-02 and IN-03.

(c) CR-03 guard: it blocks exactly what the owner's own echo check (`SyncManager._parse`) would reject, so it cannot
create a loop. A reject returns before `_revs`/`note_published` and before any publish, and `_unpublishable` is
cleared on the next good build. It can block a legitimate document only for the sizes and depths the form does not
validate (see WR-01).

(d) Approval view: the list-of-single-key-dicts fix in `trust.py:156` removes the label-collision hiding. Escaping is
unchanged. `{startup}` is `str(bool).lower()`, so it is fixed text and not markdown-injectable. Remaining nits are in
IN-04.

(e) `is_valid_device_id` (`topics.py:11-16`): `fullmatch` with an ASCII-only class correctly rejects a trailing
newline, non-ASCII digits and letters, dots and empty strings. Owned ids (uuid4, 36 characters) always pass. The
owned-device branch runs before the check, so a legitimate owner is never affected. The only gap is old persisted
mirrors (IN-02).

## Warnings

### WR-01: A document the CR-03 guard refuses fails silently and leaves a stale retained document live on followers

**File:** `custom_components/mqtt_actions/manager.py:1005-1017`, `custom_components/mqtt_actions/config_flow.py:296-304`
**Issue:** The guard only logs one warning per device and returns. The device still gets its discovery, so it works
locally and looks healthy. No Repairs issue is raised, and the form does not validate the other things the parser
enforces: `MAX_DOCUMENT_BYTES` (256 KiB, `too_large`) and `MAX_ACTION_DEPTH` (32, `too_deep`). The name rules were added
to the form for CR-03, but not these two. Consequences:
1. An owner who edits an already shared device so that it crosses the size or depth cap sees no error. The previously
   retained document stays on the broker, and every follower keeps mirroring, and running, the old approved actions
   while the owner believes the new ones are synced. Nothing says so on the owner's side.
2. If the old retained document is itself rejected (for example one published by an earlier build with an over-long
   name), the owner's startup check `_check_owned` -> `_parse` returns None -> `_overwritten` raises the
   `doc_overwritten` issue ("something other than this instance changed it"). That text is false. The heal then hits
   the guard, publishes nothing, and the issue cannot be resolved.
3. A hub whose stored `instance_name` already exceeds 64 characters (created before the new check, and the hub has no
   reconfigure step) publishes no document for any device and gets only a log line per device.
**Fix:** Surface it to the user, and keep the form and the parser in step.
```python
# manager.py, in the except branch of async_publish_config
ir.async_create_issue(
    self._hass, DOMAIN, f"{ISSUE_UNPUBLISHABLE_PREFIX}{device_id}", is_fixable=False,
    severity=ir.IssueSeverity.WARNING, translation_key="document_unpublishable",
    translation_placeholders={"device": device.name, "reason": str(err.reason)},
)
# and delete the issue next to self._unpublishable.discard(device_id), and in _async_remove_device
```
In the device forms, reject actions whose canonical JSON exceeds a margin below `MAX_DOCUMENT_BYTES` and whose
`actions_depth` exceeds `MAX_ACTION_DEPTH`, by reusing `parse_document` on the would-be document. Consider publishing
a tombstone instead of leaving a stale document when a previously published device becomes unpublishable.

## Info

### IN-01: The pre-publish guard is narrower than the follower pipeline and than the owner's own parse wrapper

**File:** `custom_components/mqtt_actions/manager.py:1005-1008`
**Issue:** The comment says the document must pass "the parser every follower applies". Followers additionally run
`validate_spec_structure` (`sync.py:378`), which the guard skips. That cannot cause a loop, because the owner echo
check does not call it either, but a document can pass the guard and still be dropped everywhere with `invalid_actions`.
`SyncManager._parse` also catches any `Exception` ("hostile structures can raise anything"), but the guard only
catches `DocumentRejectedError`. Any other exception from `parse_document` now aborts `async_start` from inside
`_async_publish_owned`, whereas publish failures were swallowed before. I found no such path for normal owner data, so
this is defensive only.
**Fix:** Call `validate_spec_structure(parse_document(...).spec)` in the guard and catch
`(DocumentRejectedError, ActionsInvalid)`. Optionally log and return on any `Exception`, as `_parse` does.

### IN-02: Cached mirrors with an invalid id are restored and can never be updated or removed

**File:** `custom_components/mqtt_actions/manager.py:192-216`, `custom_components/mqtt_actions/sync.py:322-325`
**Issue:** WR-05 filters live messages, but `_parse_mirrors` still accepts any string key from the Store.
A mirror that was cached with a long or odd id before the fix is restored at start (`_async_restore_mirrors`) and is then
unreachable: its updates and its tombstone are dropped by the new `is_valid_device_id` check. The prune can still
remove it. It also keeps its state subscriptions and its Store entry.
**Fix:** In `_parse_mirrors` add `if not isinstance(device_id, str) or not is_valid_device_id(device_id): continue`.

### IN-03: `async_remove_mirror` returns without cleaning up when the id has meanwhile become an owned device

**File:** `custom_components/mqtt_actions/manager.py:716-718`
**Issue:** The new guard is correct for the Script, but it leaves the stale entry in `self.mirrors` (with both
subscriptions and a persisted payload) because it returns before the `pop`. This needs a subentry whose uuid4 equals an
existing mirror id (a restored or cloned config), so it is rare. `_async_add_device` has the same blind spot: it never
checks `self.mirrors` for the new owned id.
**Fix:** In `_async_add_device`, drop a mirror with the same id first (unsubscribe, `self.mirrors.pop`). In
`async_remove_mirror`, do the `mirrors.pop` and unsubscribe before the early return, and only skip
`runner.async_unload`.

### IN-04: Approval dialog nits

**File:** `custom_components/mqtt_actions/manager.py:629-635`, `custom_components/mqtt_actions/translations/de.json:294`
**Issue:**
- `async_approval_view` appends the label of every failing section to `invalid`. Two Select options can still produce
  the same label (`"a (b (c)"` from two different pairs, the case the CR-01 test builds), so the "invalid" list can name
  one label twice or leave it unclear which entry failed. The YAML itself now shows both.
- The German dialog shows the placeholder as the English words `true` / `false`.
- `run_mode` and the breaker settings are not bound by the approval hash. A changed `run_mode` therefore does not ask
  again. This is low impact, but the README states that the hash binds the approved behavior.
**Fix:** Dedupe or index the invalid labels (`invalid.append(f"{label} #{index}")`). Pass a localized "yes/no" via
the translation. Either bind `run_mode` in `actions_hash` or document that it is not.

### IN-05: A foreign claim for an owned id that is replayed during the start is healed without any report

**File:** `custom_components/mqtt_actions/sync.py:319-333`
**Issue:** CR-02 is fixed by queuing the ingest behind the start lock, but the callback chooses its branch at message time.
For an owned id that is not yet in `devices` it takes the follower branch, so the later ingest is a no-op. The retained
foreign document is overwritten by the unconditional start publish, but `_check_owned` never classified it, so no
`ownership_claim` or `doc_overwritten` issue is raised, whereas the same message at runtime raises one. Also,
`_unpublishable` (`manager.py:333`) is not cleared in `_async_remove_device` (trivial), and the two name error strings
hard-code "64" instead of `MAX_TEXT_LENGTH` (`en.json:19`, `de.json:19`).
**Fix:** In `_async_ingest`, when `device_id in manager.devices` after taking the lock, call
`self._check_owned(manager.devices[device_id], payload)` instead of skipping.

---

_Reviewed: 2026-10-01T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
