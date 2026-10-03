---
phase: 03-trust-central-config-and-ownership
plan: 04
subsystem: sync
tags: [mqtt, follower, mirror, owner-pinning, schema-gate, store, repairs, hostile-input, tdd]

requires:
  - phase: 03-trust-central-config-and-ownership
    provides: "parse_document, analyze_spec, escape_markdown, FakeBroker tier, config wildcard and parse_config_topic (plan 03-01); SyncManager owner branch, ISSUE_DEVICE_PREFIXES, _raise_once, public Manager surface (plan 03-02); instance presence (plan 03-03)"
provides:
  - "Follower branch of SyncManager: strict parse, structure gate, owner check, mirror cap, ingest in FIFO background tasks under Manager.lock"
  - "Manager.mirrors, MirrorInfo and Device.mirror: read-only mirrors that follow the state and test topics, build no Script and publish nothing"
  - "Mirror persistence: payload text per mirror in the additive Store key mirrors, parsed and structure-checked again at load, restored at start with the startup window"
  - "Update by content hash (rev informational), owner pinning with owner_conflict_<id>, schema gate with bounded schema_too_new_<id>"
  - "validate_spec_structure(spec) in actions.py and tests/documents.py helpers for foreign documents"
  - "English and German texts for owner_conflict and schema_too_new"
affects: [03-05, 03-06, 03-07, 04-operations]

requirements-completed: [SYN-02]

plan_head_before: ca7c67ff23a1f248d71f0f9e51a672c2d073493b
plan_head_after: d14118edb2b87fcbdbcec363f5a3b95974d5bc7d

actuals:
  tokens: 14700
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "A mirror is a Device without a Script: the existing runner gate (can_run) keeps it inert by construction, so approval in plan 03-06 is the only thing that can ever make it run"
    - "Ingest under the manager lock with a broad except that logs one fixed line with a length-capped, repr-quoted device id; reason codes only, never payload, action data or structure error text"
    - "Cached payloads are untrusted: the Store holds the received text, every load runs parse_document and the structure gate again and the stored hash is never used"
    - "Extra hass instances of the test harness are stopped by the factory, because async_test_home_assistant only restores the time zone"

key-files:
  created:
    - tests/documents.py
    - tests/test_sync_follower.py
    - tests/test_multi_instance.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/actions.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/fake_broker.py
    - tests/test_manager_breaker.py
    - tests/test_translations.py

key-decisions:
  - "A mirror lives in Manager.mirrors, never in devices or a subentry; reconcile, orphan cleanup and the published set never see it, and the follower publishes nothing on its discovery, config or state topic (D-08, D-19)"
  - "Only the structural gate drops a document (strict parse, script schema, size, depth); a statically denied service does not, it is recorded on MirrorInfo.denied, templated and residual (Open Question 3 default, A6)"
  - "The content hash decides, never the rev: an equal hash is a no-op, a lower rev with new content still applies (D-15)"
  - "First owner wins: a valid document of another owner is ignored and raises one owner_conflict issue (ERROR, non-fixable) naming both claims, cleared when the pinned owner's current document arrives (D-17)"
  - "A too-new schema applies nothing; an existing mirror keeps its last state. The issue is WARNING and non-fixable, and is bounded by MAX_SCHEMA_TOO_NEW_ISSUES for ids without a mirror. Nothing of a too-new document is read, so the issue is raised whatever its owner (D-14)"
  - "Cached mirrors are capped at MAX_MIRRORS at load, and a cached mirror whose id is an owned subentry id is dropped"
  - "Mirror names from the broker are escaped wherever they reach a Repairs placeholder, including the breaker issue of a mirror"

patterns-established:
  - "Follower ingest reuses SyncManager._raise_once, now keyed by device id so ids without a Device can raise issues"
  - "New per-device issue families append their prefix to ISSUE_DEVICE_PREFIXES so device delete and hub removal clean them"

coverage:
  - id: D1
    description: "A foreign document creates a read-only mirror with owner, rev and both hashes; it is not in devices or subentries, and the follower publishes nothing on the device's topics"
    requirement: SYN-02
    verification:
      - kind: unit
        ref: "tests/test_sync_follower.py#test_retained_document_creates_a_read_only_mirror"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_mirror_never_publishes_anything_for_the_device"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_follower_mirrors_the_owners_device"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unapproved mirror tracks its baseline and runs nothing: live state, test topic and run-on-startup leave every service untouched and no Script exists"
    requirement: TRU-01
    verification:
      - kind: unit
        ref: "tests/test_sync_follower.py#test_mirror_tracks_the_baseline_and_runs_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_mirror_is_stored_and_restored_at_start"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mirrors persist in the Store, are validated again at load, survive a restart and a reconcile, and a cached mirror of an owned id is dropped"
    requirement: SYN-02
    verification:
      - kind: unit
        ref: "tests/test_sync_follower.py#test_malformed_mirrors_store_is_dropped"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_stored_mirror_of_an_owned_id_is_dropped"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_reconcile_keeps_mirrors_and_publishes_nothing_for_them"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_unload_releases_mirror_subscriptions"
        status: pass
    human_judgment: false
  - id: D4
    description: "Hostile and unexpected documents are dropped with one fixed-reason warning and no payload, action data or exception text in any log line; the mirror count and the too-new issues are bounded"
    requirement: TRU-03
    verification:
      - kind: unit
        ref: "tests/test_sync_follower.py#test_invalid_documents_are_dropped_and_logged_without_content"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_unexpected_exception_does_not_break_ingest"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_mirror_count_is_capped"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_schema_too_new_without_a_mirror_creates_no_mirror"
        status: pass
    human_judgment: false
  - id: D5
    description: "Updates follow the content hash; the first owner is pinned, competing owners are ignored and reported once, too-new documents keep the last mirror, and breaker and baseline are released on an applied change"
    requirement: SYN-03
    verification:
      - kind: unit
        ref: "tests/test_sync_follower.py#test_changed_document_updates_the_mirror"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_identical_hash_is_a_noop"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_lower_rev_with_different_content_is_applied"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_pinned_owner_ignores_another_owner"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_schema_too_new_keeps_the_mirror_and_raises_an_issue"
        status: pass
      - kind: unit
        ref: "tests/test_sync_follower.py#test_update_releases_a_tripped_breaker_and_sanitizes_the_baseline"
        status: pass
    human_judgment: false
  - id: D6
    description: "English and German texts for owner_conflict and schema_too_new with the placeholders the sync code supplies"
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_required_keys_present"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_issue_strings_use_expected_variables"
        status: pass
    human_judgment: false
  - id: D7
    description: "The tunables MAX_MIRRORS = 100 and MAX_SCHEMA_TOO_NEW_ISSUES = 10, the ERROR versus WARNING severity of the two issues, and the English and German wording of the two issue texts are planner assumptions"
    verification: []
    human_judgment: true
    rationale: "Tunables, severities and phrasing are policy and language judgments that no test can assert are the right ones"

duration: 12 min
completed: 2026-10-01
status: complete
---

# Phase 3 Plan 04: Follower Mirrors Summary

**Foreign config documents become validated, owner-pinned, Store-cached read-only mirrors that track state from creation and run nothing, because a mirror is a Device without a Script; hostile documents are dropped with fixed reason codes and no content in any log line**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-30T23:37:19Z
- **Completed:** 2026-09-30T23:50:01Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto, all TDD)
- **Files modified:** 12 (3 created, 9 modified)

## Accomplishments

- `SyncManager` routes a config message for an id that is not in `devices` to the follower branch. An empty payload returns (removal is plan 03-05); everything else runs `_async_ingest` in an entry background task that takes `Manager.lock` (arrival order), re-checks that the manager still runs and the id is still not owned, and is wrapped in a broad except that logs one line with a length-capped, repr-quoted device id.
- `_async_ingest_locked` parses strictly (`DocumentRejectedError` logs its reason code only), runs `validate_spec_structure` (logs the fixed reason `invalid_actions`, never the schema text that can quote data), ignores a document whose owner is this instance, applies the `MAX_MIRRORS` cap with a single overflow warning, and then decides by content hash.
- `Manager.mirrors` holds `Device` objects with a `MirrorInfo` (owner, owner name, rev, both hashes, payload, denied, templated, residual). A mirror has a `StateTracker` and a breaker, subscribes the state and test topics from creation, builds no Script and publishes nothing, so `ActionRunner.can_run` keeps it inert; `_on_message` and `_on_test_message` resolve devices through `_device()`.
- The Store key `mirrors` keeps the received payload text per mirror. At load every entry is parsed, structure-checked and analyzed again; non-dict containers, non-string entries, unparseable payloads, id mismatches and invalid actions are dropped and the list is capped at `MAX_MIRRORS`. At start, cached mirrors whose id is an owned subentry are dropped and the rest is restored with `startup_pending` before the config wildcard is subscribed. Baselines of mirrors share `last_acted`.
- Update branch: same content hash is a no-op (no replace, no save, no publish), a different hash replaces spec, info, signature and tracker settings, gives a fresh breaker, deletes the breaker issue and the `_tripped` entry and sets a no-longer-valid baseline to unknown while keeping the `Device` and its subscriptions. A lower rev with new content applies.
- Owner pinning: a valid document of another owner leaves the mirror untouched and raises one non-fixable `owner_conflict_<id>` (ERROR) with escaped device, owner and claimant names; the issue is deleted when the pinned owner's current document arrives. A too-new schema applies nothing and raises `schema_too_new_<id>` (WARNING); without a mirror at most ten such issues exist; a valid document resolves it. Both prefixes are in `ISSUE_DEVICE_PREFIXES`.
- English and German texts for both issue families, with exactly the placeholders the sync code supplies.

## Task Commits

1. **Task 1: Tracer, foreign document creates a read-only mirror** - `bd494c2` (test, RED), `b571f96` (fix, harness), `75fa5bb` (feat, GREEN)
2. **Task 2: Updates, owner pinning, schema gate, hostile documents** - `9f4810e` (test, RED), `9026a1f` (feat, GREEN)
3. **Task 3: Conflict and schema issue texts** - `9b902ee` (test, RED), `d14118e` (feat, GREEN)

**Plan metadata:** added by the docs commit that follows this file.

## TDD Gate Compliance

Every task has a `test(03-04)` commit before its `feat(03-04)` commit; no refactor commits. Tracer gate: Task 1's verify is automated only, so it was re-run end to end after the GREEN commit (both test modules, full suite, Ruff check and format) and passed before expansion. RED evidence (`check tdd-red-evidence` was not run):

- Task 1: 21 tests failed on the missing follower behavior, most of them as `AttributeError: 'Manager' object has no attribute 'mirrors'`, one as `KeyError: 'mirrors'` in the Store data and one as the missing `sync.MAX_MIRRORS` patch target. An attribute error on the planned new surface is the nearest thing to the planned assertion available for a not-yet-existing dict; the two name constants `MAX_MIRRORS` and `STORE_MIRRORS` were added to `const.py` in the RED commit so the tests fail on behavior and not at collection.
- Task 2: nine tests failed on the planned behavior (no update, no conflict issue, no too-new issue, no arrival-order result, prefixes missing from `ISSUE_DEVICE_PREFIXES`). Three new tests already passed at RED because they pin Task 1 behavior that the update branch must not break: `test_identical_hash_is_a_noop`, `test_invalid_documents_are_dropped_and_logged_without_content` and `test_unexpected_exception_does_not_break_ingest`. The issue constants and the cap were added in the RED commit, the prefix tuple was extended only in GREEN.
- Task 3: six translation tests failed on the missing keys (`KeyError` on `issues.owner_conflict.*` and the required-key list).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The fake broker harness never stopped its extra hass instances**
- **Found during:** Task 1 (the second test that creates an extra `hass` errored at teardown with `Event loop is closed`)
- **Issue:** `InstanceFactory` entered `async_test_home_assistant()`, which only restores the time zone on exit; nothing stopped the extra `hass`, so it stayed in the plugin's `INSTANCES` list and `verify_cleanup` aborted the run at the next test that created one. Plan 03-01 had only one multi-instance test, so it never showed; this plan's acceptance needs two.
- **Fix:** the factory pushes `hass.async_stop(force=True)` onto its exit stack right after entering the context, so it runs after the managers stop.
- **Files modified:** `tests/fake_broker.py`
- **Commit:** `b571f96`

**2. [Rule 3 - Blocking] Constants moved into the RED commits**
- **Found during:** Task 1 and Task 2 RED
- **Issue:** the new tests import `MAX_MIRRORS`, `STORE_MIRRORS`, the two issue prefixes and `MAX_SCHEMA_TOO_NEW_ISSUES`; a missing name is an import error at collection, which is INVALID_RED, not a failing assertion for the behavior.
- **Fix:** the names (no behavior) are added in the RED commits. The two prefixes are appended to `ISSUE_DEVICE_PREFIXES` only in the GREEN commit, so the containment test fails on its assertion.
- **Files modified:** `custom_components/mqtt_actions/const.py`
- **Commits:** `bd494c2`, `9f4810e`

**3. [Rule 1 - Bug] An existing test pinned the exact Store key set**
- **Found during:** Task 1 (full suite)
- **Issue:** `tests/test_manager_breaker.py::test_trip_is_persisted_as_config_hash` asserts the exact set of Store keys, which gained `mirrors` (additive key, no version bump, like `revs` in plan 03-01).
- **Fix:** the expected set includes `STORE_MIRRORS`.
- **Files modified:** `tests/test_manager_breaker.py`
- **Commit:** `75fa5bb`

**4. [Rule 2 - Missing critical] Mirror names are escaped in the breaker issue and the issue helper takes a device id**
- **Found during:** Task 1 and Task 2 design
- **Issue:** the name of a mirror comes from the broker, and `_create_breaker_issue` put `device.name` into a Repairs placeholder unescaped (T-03-05). `_raise_once` needed a `Device`, which a too-new document without a mirror does not have.
- **Fix:** `_create_breaker_issue` applies `escape_markdown` when the device is a mirror, and `_raise_once` now takes the device id (its three owner-side callers pass `device.device_id`).
- **Files modified:** `custom_components/mqtt_actions/manager.py`, `custom_components/mqtt_actions/sync.py`
- **Commits:** `75fa5bb`, `9026a1f`

**5. [Rule 1 - Bug] Plan acceptance wording not literally satisfiable**
- **Issue:** Task 3 requires `grep -c "schema_too_new"` on `en.json` and `de.json` to be equal and at least 2; the string occurs once per file (the issue key), because title and description do not repeat it. Counts are equal (1 and 1) and both texts are covered by `test_required_keys_present` and `test_issue_strings_use_expected_variables`; no artificial text was added to reach 2 (same situation as plan 03-02 deviation 4).
- **Files modified:** none

---

**Total deviations:** 5 (2 Rule 3, 2 Rule 1, 1 Rule 2). **Impact on plan:** no scope change, no existing assertion weakened; one existing test changed (deviation 3).

## Issues Encountered

- A test module that imports `test_topic` from `topics` gets it collected as a test and errors on the missing fixture; the tests import it as `device_test_topic`.
- After `async_unload` the entry has no `runtime_data`, so a test that inspects the manager after the unload takes the manager reference before it.
- Core MQTT drops a second retained message per topic and subscription in the mocked tier, so the update tests deliver their documents live (`retain=False`); the restore test delivers retained only once per subscription.

## Known Stubs

None. Open items by design:

- Mirrors are inert by construction: nothing builds a Script for them before plan 03-06, which adds approval and the execution-time denylist. `MirrorInfo.denied`, `templated` and `residual` are recorded and not yet shown anywhere.
- An empty payload (tombstone) for a mirrored device is ignored here; removal of mirrors, the grace window and entity registry cleanup are plan 03-05.
- A retained replay for an id that the owner branch has not yet seen as owned (the config wildcard is subscribed before the owned devices exist) reaches the follower branch and is discarded under the lock once the device is in `devices`, so a foreign claim that predates the start is still only caught when it arrives after the device exists (the limit plan 03-02 already records for the README).
- A too-new document raises its issue whatever its owner, because nothing of a too-new document is read; someone with broker write access can therefore raise up to one such issue per existing mirror (bounded, non-fixable, warning).

## Threat Flags

None. The surfaces are the ones of the plan's threat model: broker to follower ingest (T-03-14, T-03-15, T-03-16, T-03-17, T-03-18) and Store to follower runtime (T-03-19), all mitigated and covered by the tests above. T-03-SC: no package was installed.

## Next Phase Readiness

- Plan 03-05 can handle tombstones and pruning on `Manager.mirrors`: the follower branch returns early for an empty payload at the marked place in `SyncManager._on_config_message`, `SyncManager.instance_status()` is ready for the owner-liveness rule, and a mirror removal must unsubscribe both topics, drop its Store entry and baseline, delete the prefix issues with `_delete_device_issues`, and clean the entity and device registry.
- Plan 03-06 builds on `MirrorInfo.actions_hash`, `denied`, `templated` and `residual`; approval state needs its own Store key; a Script for a mirror must be built only for an approved hash, and `_update_mirror` is the place where an approval lapses when `actions_hash` changes.
- Needs user confirmation at review: `MAX_MIRRORS = 100`, `MAX_SCHEMA_TOO_NEW_ISSUES = 10`, ERROR for `owner_conflict` and WARNING for `schema_too_new`, and the English and German wording of both issue texts.
- Requirement bookkeeping: SYN-02 is declared by this plan only and is now complete. SYN-03 was already ticked by plan 03-02 (shared with 03-01 and 03-07 in the planning files). TRU-01, TRU-03 and STA-03 are shared with plan 03-06 and are left for the phase verification.

## Self-Check: PASSED

- Created files exist: `tests/documents.py`, `tests/test_sync_follower.py`, `tests/test_multi_instance.py` (FOUND)
- Commits exist: `bd494c2`, `b571f96`, `75fa5bb`, `9f4810e`, `9026a1f`, `9b902ee`, `d14118e` (FOUND); every `test(03-04)` commit precedes its `feat(03-04)` commit (three of each)
- Acceptance: `test_only_gateway_imports_mqtt_component` passes; `test_follower_mirrors_the_owners_device` runs with two distinct hass objects in both start orders; `grep -c` of the two issue prefixes in `const.py` prints 4 (at least 3); `test_invalid_documents_are_dropped_and_logged_without_content` asserts the canary is absent from the integration's log records
- `uv run pytest -q` 688 passed; `uv run ruff check .` and `uv run ruff format --check .` clean
