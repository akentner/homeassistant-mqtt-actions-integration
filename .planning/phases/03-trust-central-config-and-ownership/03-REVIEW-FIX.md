---
phase: 03-trust-central-config-and-ownership
fixed_at: 2026-10-01T00:00:00Z
review_path: .planning/phases/03-trust-central-config-and-ownership/03-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 7
skipped: 1
status: partial
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-10-01
**Source review:** .planning/phases/03-trust-central-config-and-ownership/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (CR-01..CR-03, WR-01..WR-05; Info findings were out of scope for this run)
- Fixed: 7
- Skipped: 1 (WR-04, needs a user decision because it touches the wire contract)

**Verification:** every fix was verified in the main checkout (`/home/akentner/Projects/homeassistant-mqtt-actions-integration`,
branch `gsd/phase-03-trust-central-config-and-ownership`), not in an isolated worktree, as instructed by the caller. After
each fix `uv run pytest -q && uv run ruff check . && uv run ruff format --check .` was green. The suite grew from 780 to
814 tests. Each regression test was run against the pre-fix source (via `git stash -- custom_components`) and failed there.

## Fixed Issues

### CR-01: Select options with colliding labels hide actions from the approval dialog

**Files modified:** `custom_components/mqtt_actions/trust.py`, `tests/test_trust.py`
**Commit:** 60a1f22
**Applied fix:** `_actions_yaml` no longer collapses the sections into a dict. It dumps a list of single-key mappings, so two
options with the same label both appear in the review. Regression test
`test_view_shows_every_action_list_when_select_labels_collide` uses the reviewer's colliding pair (`lock.unlock` and
`light.turn_on`). The label format was left unchanged, so the existing dialog assertions still hold.

### CR-02: A foreign claim for an owned device becomes a mirror during startup

**Files modified:** `custom_components/mqtt_actions/manager.py`, `custom_components/mqtt_actions/sync.py`, `tests/test_multi_instance.py`
**Commit:** 2115d45
**Applied fix:** `Manager.async_start` now holds the manager lock from `sync.async_start()` through orphan cleanup, the
reconcile and the first publish (reconcile body split into `_async_reconcile_locked`). Replayed retained documents queue
their ingest on that lock and see the owned ids in `devices` when they run. Defense in depth: `_async_prune` skips ids in
`manager.devices`, and `async_remove_mirror` returns early for an owned id so it can never unload the owner's Script.
Regression test `test_foreign_claim_replayed_during_startup_never_becomes_a_mirror` patches `FakeGateway.async_subscribe`
to yield to the loop (like a real network subscribe) with a retained foreign claim on the broker.
**Status note:** logic/concurrency fix, flagged for human verification (see below).

### CR-03: Device or instance name over 64 characters makes the owner's own document unparseable

**Files modified:** `custom_components/mqtt_actions/model.py`, `custom_components/mqtt_actions/config_flow.py`,
`custom_components/mqtt_actions/manager.py`, `custom_components/mqtt_actions/translations/en.json`,
`custom_components/mqtt_actions/translations/de.json`, `tests/test_config_flow.py`, `tests/test_config_flow_select.py`,
`tests/test_multi_instance.py`, `tests/test_translations.py`
**Commit:** 379243f
**Applied fix:** New `invalid_name()` in `model.py` (same rule as the parser). The hub flow (`instance_name_invalid`), the
switch flow and the select settings form (`name_invalid`) now reject such names, with en and de strings. Defensively,
`Manager.async_publish_config` runs the built payload through `parse_document` and, when it is rejected, logs once (device
name and reason code only) and publishes nothing, so no echo, no false `doc_overwritten` issue and no republish loop for
names stored before this fix. Regression tests: flow rejections for hub, switch and select, and a fake-broker test that a
70-character device name and a 70-character instance name publish nothing and raise no `doc_overwritten`.
**Known residual:** an already-retained invalid document of an older version still raises one `doc_overwritten` issue when
it is replayed; with the guard it no longer loops.
**Status note:** logic fix, flagged for human verification (see below).

### WR-01: `parse_document` raises `TypeError` for unhashable `kind` or `run_mode`

**Files modified:** `custom_components/mqtt_actions/document.py`, `tests/test_document.py`
**Commit:** 5cf3967
**Applied fix:** `kind` and `run_mode` are type-checked (`isinstance(..., str)`) before the set membership test, so a list or
dict now raises `DocumentRejectedError` with `bad_kind` / `bad_run_mode`. Four cases added to the parametrized rejection test.

### WR-02: Approval dialog does not show what the hash binds (startup flag)

**Files modified:** `custom_components/mqtt_actions/trust.py`, `custom_components/mqtt_actions/repairs.py`,
`custom_components/mqtt_actions/translations/en.json`, `custom_components/mqtt_actions/translations/de.json`,
`tests/test_trust.py`, `tests/test_repairs_flow.py`, `tests/test_translations.py`
**Commit:** fa4ec30
**Applied fix:** `ApprovalView` carries `run_on_startup`; the confirm step passes a new `startup` placeholder
(`true` / `false`) and the dialog text (en, de) now states that with startup active the actions also run on the first state
after every Home Assistant start, reload and reconnect. The run mode was deliberately not added: it is not part of the
hash (see WR-04).

### WR-03: Denylist leaves other host-level and code-execution services callable

**Files modified:** `custom_components/mqtt_actions/const.py`, `custom_components/mqtt_actions/document.py`,
`custom_components/mqtt_actions/translations/en.json`, `custom_components/mqtt_actions/translations/de.json`, `README.md`,
`tests/test_document.py`, `tests/test_repo_structure.py`
**Commit:** 0cd598d
**Applied fix:** Added to `DENIED_SERVICES` only services that exist in core `services.yaml` (checked in the installed HA):
`update.install`, `downloader.download_file`, `recorder.disable`, `logger.set_level`, `logger.set_default_level`,
`system_log.clear`. New `RESIDUAL_SERVICES` constant (`automation.trigger`, `button.press`, `scene.turn_on`,
`homeassistant.turn_on/turn_off/toggle`) is flagged as residual by the walker and in the dialog text. README denylist and
residual-risk text updated, including a "best effort" statement and the note that custom-integration services such as
`pyscript` are not covered. New test `test_readme_lists_every_denied_and_residual_service` keeps README and `const.py` in
sync. `pyscript` was NOT added as a domain because it is not a core integration (not in core `services.yaml`); this is
disclosed in the README instead. The run-time `GuardedTemplate` uses `is_denied`, so the new entries apply to templated
names automatically.

### WR-05: Mirror device ids are accepted unbounded and unvalidated

**Files modified:** `custom_components/mqtt_actions/topics.py`, `custom_components/mqtt_actions/sync.py`,
`tests/test_topics.py`, `tests/test_sync_follower.py`
**Commit:** 6b2ad50
**Applied fix:** New `is_valid_device_id` (1 to 64 of `[A-Za-z0-9_-]`, full match). The follower branch of
`SyncManager._on_config_message` ignores config messages (document or tombstone) for other ids, with a debug log through
`_shown`. The owned-id branch is unchanged (owned ids are uuid4). Regression test covers 65 and 5000 characters, space,
non-ASCII and newline ids: no mirror, no Store entry, no issue. I chose the permissive pattern over strict uuid so existing
fixtures and any non-uuid ids keep working.

## Skipped Issues

### WR-04: Run mode and breaker settings are not covered by the approval and can be changed remotely

**File:** `custom_components/mqtt_actions/document.py:110-116`
**Reason:** Needs a user decision. Both options in the review change a documented contract: putting `run_mode`,
`breaker_max_runs` and `breaker_window` into `actions_hash` changes the published wire contract (A5, the hash algorithm is
documented as part of the protocol, and it would invalidate every existing approval across instances). Clamping mirrored
breaker values to a local floor is a behavior change of the follower's loop protection that the review leaves open
("for example"). The third option (only document it) was not applied either, since the caller asked for a clear skip so the
decision stays with the user. The README trust model section still says the approval is bound to "the hash of the actions"
without stating that run mode and breaker limits are remote-controlled.
**Original issue:** By design `actions_hash` ignores `run_mode`, `breaker_max_runs` and `breaker_window`, so an owner or
forger can set the breaker to 100 runs per 1 s or switch a device to `restart` after approval, weakening the follower's local
loop protection without a new request.

## Items for human verification

- CR-02 and CR-03 are concurrency / logic fixes; tests pin the reviewer's reproductions but the lock scope in
  `Manager.async_start` (now held across the three subscribes and the first publish) deserves a human look.
- WR-03 widens what is flagged as residual (for example every `homeassistant.turn_on`); this is intentionally noisy in the
  dialog.

---

_Fixed: 2026-10-01_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
