---
phase: 03-trust-central-config-and-ownership
plan: 02
subsystem: sync
tags: [mqtt, ownership, tombstone, trailing-throttle, echo-history, repairs, discovery-healing, tdd]

requires:
  - phase: 03-trust-central-config-and-ownership
    provides: "Config document, parse_document, escape_markdown, config/discovery wildcards and parsers, FakeBroker tier, gateway seams (plan 03-01)"
provides:
  - "Delete order discovery, unsubscribe, config tombstone, state, with the device popped from devices before the first clear"
  - "SyncManager owner side (sync.py): config and discovery watchers, echo history seeded with the persisted hash, trailing throttle"
  - "Repairs issues doc_overwritten_<id>, ownership_claim_<id>, discovery_removed_<id> in English and German"
  - "Public Manager surface for sync code: hass, entry, base_topic, instance_id, instance_name, lock, running, revision(), sync"
affects: [03-03, 03-04, 03-05, 03-06, 03-07, 04-operations]

requirements-completed: [SYN-03, SYN-06, DSC-03]

plan_head_before: 1bcd99f9c86bb853dae92eb4483ea62052139ed2
plan_head_after: 11dbfc3caa7b711bfa3b430078f4cd6b796f88fe

actuals:
  tokens: 14100
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Pop-first removal: a device leaves Manager.devices before any clear message, so handlers that act only for ids in devices never react to the owner's own delete"
    - "_TrailingThrottle: idle key runs at once and opens a window, a request inside the window sets one pending flag, window end runs a pending key and reopens"
    - "Issues for broker-influenced events are created only when absent, with every broker-supplied name passed through escape_markdown"

key-files:
  created:
    - custom_components/mqtt_actions/sync.py
  modified:
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_sync_owner.py
    - tests/test_manager.py
    - tests/test_translations.py

key-decisions:
  - "Severity: doc_overwritten and ownership_claim are ERROR (security relevant), discovery_removed is WARNING"
  - "The removal-hint deque keeps only the last DISCOVERY_REMOVAL_HINT_COUNT timestamps (maxlen), so a flood of empty discovery messages cannot grow memory; the hint fires when the deque is full and spans at most the window"
  - "The removal clock is Manager.clock (replaceable, as for the breaker), not wall time"
  - "note_published does not re-append a hash that is already in the history, so repeated reconnect republishes cannot evict older echo hashes"
  - "An unparseable or hostile payload is caught with a broad except in the owner branch and treated as an unreadable payload (content-free debug line), so a message callback never raises"

patterns-established:
  - "Owner watchers select the owned id with parse_config_topic / parse_discovery_topic and act only for ids in manager.devices; the follower branch of plan 03-04 plugs into the else path of SyncManager._on_config_message"
  - "Heal tasks run as entry background tasks under Manager.lock and re-check running and device existence"

coverage:
  - id: D1
    description: "Deleting an owned device clears discovery, unsubscribes, tombstones the config topic, then clears the state; a failed clear keeps the id published and the next start retries all three topics"
    requirement: SYN-06
    verification:
      - kind: unit
        ref: "tests/test_manager.py#test_delete_clears_discovery_then_unsubscribes_then_config_tombstone_then_state"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_failed_clear_keeps_id_published_and_retry_clears_all_three_topics"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_device_leaves_devices_before_the_first_clear"
        status: pass
    human_judgment: false
  - id: D2
    description: "The owner recognizes its own echoes and heals foreign content, tombstones, garbage and ownership claims with a trailing-throttled republish and one issue per conflict"
    requirement: SYN-03
    verification:
      - kind: unit
        ref: "tests/test_sync_owner.py#test_foreign_content_on_my_topic_is_healed_and_reported"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_heal_is_throttled_with_one_trailing_republish"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_persisted_hash_seeds_the_echo_history"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_other_owner_claim_raises_ownership_claim_once"
        status: pass
    human_judgment: false
  - id: D3
    description: "A follower deleting a mirrored entity makes the owner republish the device discovery at most once per window with a trailing republish; repeated removals are explained in Repairs; the owner's own delete never heals"
    requirement: DSC-03
    verification:
      - kind: unit
        ref: "tests/test_sync_owner.py#test_discovery_republish_is_throttled_with_one_trailing_republish"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_own_delete_does_not_heal_the_discovery"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_repeated_removals_raise_the_hint_once"
        status: pass
    human_judgment: false
  - id: D4
    description: "Issue texts in English and German with the expected placeholders; no broker-supplied text reaches an issue or a log line unescaped"
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_issue_texts_exist_in_both_languages"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_hostile_claimant_name_is_escaped_in_the_issue"
        status: pass
    human_judgment: false
  - id: D5
    description: "The A2 tunables (60 s throttle, 8-hash echo history, hint at 3 removals in 600 s) and the German wording of the three issue texts are planner assumptions"
    verification: []
    human_judgment: true
    rationale: "The tunables are policy values and the German phrasing is a language judgment; no test can assert they are the right ones"

duration: 13min
completed: 2026-10-01
status: complete
---

# Phase 3 Plan 02: Owner Side of Ownership Summary

**Owner tombstones the config topic on delete (pop-first, no self-heal) and defends its truth with an echo-aware config and discovery watcher, a per-device trailing throttle and Repairs issues for overwrites, claims and repeated entity removals**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-30T23:10:29Z
- **Completed:** 2026-09-30T23:23:00Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto, all TDD)
- **Files modified:** 8 (1 created, 7 modified)

## Accomplishments

- Delete order is now discovery clear, state and test unsubscribe, empty retained config tombstone, empty retained state. The device is popped from `Manager.devices` as the very first step, so the clear messages of the owner's own delete never look like a foreign event. Orphan cleanup and hub removal inherit the config clear through `_async_clear_topics`, and a failed clear keeps the id published so the next start retries all three topics.
- `sync.py` subscribes to the config wildcard before anything publishes. Own documents coming back are echoes by a per-device history of 8 content hashes seeded with the persisted hash, so quick edits and offline-edit restarts raise nothing. Foreign content (rev at least the local one), foreign tombstones and unreadable payloads republish the owner's document and raise `doc_overwritten_<id>`; a lower rev heals silently; another owner's document raises `ownership_claim_<id>` naming the escaped claimant, once.
- `_TrailingThrottle` (60 s, per device) gives one immediate and exactly one trailing republish for any burst; `stop` cancels windows and pending runs.
- The discovery watcher republishes an emptied device discovery through the normal publish path (retired button tombstones included) with its own throttle, and raises `discovery_removed_<id>` (warning) once after 3 removals within 600 s. Own deletes never heal because the device has already left `devices`.
- Issue prefixes live in `ISSUE_DEVICE_PREFIXES`; `_delete_device_issues` and `async_remove_all_devices` use it, so device delete and hub removal clear overwrite, claim and hint issues too. Texts exist in English and German.

## Task Commits

1. **Task 1: Tracer, delete order with config tombstone** - `018f2f4` (test, RED), `041435c` (feat, GREEN)
2. **Task 2: Owner echo, foreign write healing, ownership claims** - `44154ea` (test, RED), `4189e4b` (feat, GREEN)
3. **Task 3: Discovery healing, hint, issue texts** - `aa421cc` (test, RED), `11dbfc3` (feat, GREEN)

**Plan metadata:** added by the docs commit that follows this file.

## TDD Gate Compliance

All three tasks have a `test(03-02)` commit before its `feat(03-02)` commit; no refactor commits. RED evidence (`check tdd-red-evidence` was not run): Task 1 failed on six assertions (missing config tombstone, device still in `devices` during the clears, event order). Task 2 failed on eleven tests (no heal publish, no issue, `sync` attribute missing for the spy). Task 3 failed on six sync tests and four translation tests (no discovery republish, no hint, missing issue keys). Some behaviors are negative guards that already pass at RED because nothing reacts yet (own echo ignored, quick edits, seeded history, equal content, unowned ids, own delete never healed, stop releases); they fail under mutation, verified for the two that matter most: removing the persisted-hash seeding fails `test_persisted_hash_seeds_the_echo_history`, removing `note_published` before the publish fails `test_quick_edits_do_not_look_like_foreign_writes`. `test_delete_forgets_rev_baseline_and_tripped` likewise pins behavior that already existed and had to survive the reorder.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Broad exception guard around `parse_document` in the owner branch**
- **Found during:** Task 2
- **Issue:** the plan catches `DocumentRejectedError`; research pitfall 11 notes deep validation of hostile structures can raise other exceptions, and an exception in a message callback would be logged by core with the payload.
- **Fix:** `SyncManager._parse` also catches `Exception` (noqa BLE001), logs a content-free debug line and treats the payload as unreadable (heal plus issue).
- **Files modified:** `custom_components/mqtt_actions/sync.py`
- **Commit:** `4189e4b`

**2. [Rule 1 - Bug] `note_published` would evict older echo hashes on every reconnect**
- **Found during:** Task 2 design
- **Issue:** appending the same hash at every reconnect publish fills the 8-slot deque with duplicates and pushes older hashes out.
- **Fix:** a hash already in the history is not appended again.
- **Files modified:** `custom_components/mqtt_actions/sync.py`
- **Commit:** `4189e4b`

**3. [Rule 3 - Blocking] Test adjustments for the mocked MQTT client**
- **Found during:** Task 2
- **Issue:** core MQTT drops a second retained message per topic and subscription, so a retained replay cannot be simulated with the mocked client; and core MQTT's own debug line logs received payloads. A test that delivered the old document with `retain=True` could not fail without the seed, and a whole-`caplog` assertion saw core's line.
- **Fix:** the late replay in `test_persisted_hash_seeds_the_echo_history` is delivered live (mutation-verified), and the garbage test asserts on the records of `custom_components.mqtt_actions` only, requiring that some exist (same approach as plan 03-01 deviation 2).
- **Files modified:** `tests/test_sync_owner.py`
- **Commit:** `4189e4b`

**4. [Rule 1 - Bug] Plan acceptance wording not literally satisfiable**
- **Issue:** `grep -c "discovery_removed"` on `en.json` and `de.json` is required to print at least 2; the string occurs once per file (the issue key), because title and description do not repeat it. Counts are equal (1 and 1) and the texts are covered by `test_issue_texts_exist_in_both_languages`; no artificial text was added to reach 2.
- **Files modified:** none

---

**Total deviations:** 4 (1 Rule 2, 2 Rule 1, 1 Rule 3)
**Impact on plan:** no scope change. No existing test was weakened; `test_delete_device_clears_discovery_then_state` was updated in place to the four-event order, as the plan specifies.

## Issues Encountered

- `async_unload_entry` calls `release_all_breakers`, which empties `_tripped`; the first draft of the forget test that unloaded and reloaded to inspect the Store could not keep a tripped entry. It now flushes the delayed save with the frozen clock instead.
- Sorted issue ids list `doc_overwritten_` before `ownership_claim_`; the hub-removal test asserts in that order.

## Known Stubs

None. Open items by design:

- The follower branch of `SyncManager._on_config_message` (ids not in `devices`) is deliberately empty until plan 03-04.
- A foreign write that predates the start is only caught when the retained replay reaches the owner after the device exists; live foreign writes are always caught. The README (plan 03-07) states this limit, as does the discovery-prefix reload note and the loss of follower entity customizations on healing (A8, Pitfall 14).
- Issues are not deleted on a plain unload or reload of the entry, only with the device, with the hub and at HA restart (they are not persistent).

## Threat Flags

None. The two new wildcard subscriptions (config and discovery) and the republish paths are the surfaces T-03-06 to T-03-10 of the plan's threat model cover.

## Next Phase Readiness

- Plan 03-04 adds the follower branch at the marked else path of `SyncManager._on_config_message` and can reuse `_raise_once`, `escape_markdown` and the `ISSUE_DEVICE_PREFIXES` tuple (append its prefixes there so delete and hub removal clean them).
- Needs user confirmation at review: the A2 tunables (`REPUBLISH_THROTTLE_SECONDS = 60.0`, `PUBLISHED_HASH_HISTORY = 8`, hint at 3 removals in 600 s), ERROR versus WARNING severity of the issues, and the German issue wording.

## Self-Check: PASSED

- Created file exists: `custom_components/mqtt_actions/sync.py` (FOUND)
- Commits exist: `018f2f4`, `041435c`, `44154ea`, `4189e4b`, `aa421cc`, `11dbfc3` (FOUND); every `test(03-02)` commit precedes its `feat(03-02)` commit
- `uv run pytest -q` 626 passed; `uv run ruff check .` and `uv run ruff format --check .` clean
- Acceptance: `grep -c async_clear_config manager.py` is 2 (Task 1 needs at least 1, satisfied via `_async_clear_topics` and `_async_remove_device`), `grep -c ISSUE_DEVICE_PREFIXES manager.py` is 3, the throttle tests assert two heal publishes per burst and an immediate, a trailing and a post-window immediate discovery republish
