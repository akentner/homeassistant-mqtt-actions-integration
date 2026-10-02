---
phase: 04-operations-recovery-and-release
plan: 11
subsystem: ownership
tags: [home-assistant, mqtt, adoption, orphaned-devices, transfer-marker, services, security]

requires:
  - phase: 04-operations-recovery-and-release
    provides: presence roster and PresenceManager.owner_offline (04-03), companion devices and the mode select (04-05, 04-06), ApprovalState and Manager.approval_state (04-07), services layer with resolve_device (04-08), subentry_payload (04-09), retrigger services pattern (04-10)
provides:
  - Additive transferred_from marker in the config document (bookkeeping, never hashed, SCHEMA_VERSION stays 1) with the bad_transfer rejection
  - Manager.async_adopt and AdoptionError (not_a_mirror, not_approved, owner_not_offline) turning an approved mirror into an owned device with the same uuid, baseline and rev + 1
  - Persisted transfers (additive Store key) written into every later document of an adopted device
  - Narrow follower re-pin rule in sync.py (marker names the pinned owner and the roster says it is offline)
  - mqtt_actions.adopt_device service (admin only, optional response) with translated refusals in en and de
affects: [04-12 returning old owner (Repairs release flow), 04-13 docs (adoption page, ACL unchanged, service response shape)]

actuals:
  tokens: 16333
  tasks: 3
  commits: 6
plan_head_before: 342768be3eeae474712eb82ed1505a50f2375c5d
plan_head_after: 14808154a92274e0cdd5aeed1245e8ea4f9e2a5e

tech-stack:
  added: []
  patterns:
    - "A takeover runs entirely under the manager lock: drop the mirror without any broker or core-registry cleanup, persist, add the subentry, reconcile; a failed subentry add restores the mirror through the normal ingest path"
    - "A bookkeeping field of the document (owner, rev, transferred_from) is validated strictly on parse but never enters content_hash or actions_hash, so adding one needs no schema bump"
    - "A refused operation is tested for no trace: snapshot of publishes, mirrors, devices, transfers, revs, approvals and subentries, and no Store save"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/document.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/services.py
    - custom_components/mqtt_actions/services.yaml
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/documents.py
    - tests/test_document.py
    - tests/test_manager_breaker.py
    - tests/test_multi_instance_ops.py
    - tests/test_services.py
    - tests/test_translations.py

key-decisions:
  - "The whole adoption (drop mirror, save, add subentry, reconcile) runs under the manager lock instead of releasing it before the subentry add: a late document of the old owner can then never re-create a mirror for an id that is about to be owned"
  - "A mirror whose owner id does not have the shape of an id is refused as not_a_mirror: the marker could not name it, so followers could never re-pin"
  - "Following a new owner with unchanged content only replaces the mirror's owner bookkeeping (no fresh breaker, no rebuilt Script), so a re-pin cannot release a tripped breaker"
  - "force overrides only the owner-online check; an unapproved or blocked mirror is refused with and without force (TRU-01, T-04-50)"
  - "The adopter's first publish is old rev + 1 by seeding the revision record with a hash that cannot match a sha256 digest"

patterns-established:
  - "The select platform forgets a device only when the manager signals a change while the id is in neither devices nor mirrors; a mirror-to-owned switch sends that signal once before the owned device is added"

requirements-completed: [SYN-07]

coverage:
  - id: D1
    description: "An approved mirror of an offline owner becomes an owned device with the same uuid, state topic, baseline and entities; the adopter publishes a document with itself as owner, rev + 1 and the old owner in transferred_from, and its own discovery"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_adoption_end_to_end"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_adoption_clears_nothing_on_the_broker"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_adopt_service_promotes_a_mirror"
        status: pass
    human_judgment: false
  - id: D2
    description: "The transfer marker is bookkeeping: never part of content_hash or actions_hash, SCHEMA_VERSION stays 1, an absent marker leaves the document byte-identical, and a malformed marker rejects the document with bad_transfer"
    requirement: SYN-07
    verification:
      - kind: unit
        ref: "tests/test_document.py#test_transferred_from_is_bookkeeping_and_not_hashed"
        status: pass
      - kind: unit
        ref: "tests/test_document.py#test_transferred_from_rejects_malformed_markers"
        status: pass
      - kind: unit
        ref: "tests/test_document.py#test_transferred_from_roundtrip"
        status: pass
    human_judgment: false
  - id: D3
    description: "A follower re-pins only for a valid document whose marker names its pinned owner while the roster says that owner is offline; a marker naming someone else, or an online or unknown pinned owner, is an owner conflict"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_marker_with_an_online_pinned_owner_is_a_conflict"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_marker_that_does_not_name_the_pinned_owner_is_a_conflict"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_forged_marker_cannot_repin_when_the_owner_is_online"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_marker_naming_the_offline_pinned_owner_repins"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_repin_keeps_the_breaker_and_the_script_of_an_unchanged_mirror"
        status: pass
    human_judgment: false
  - id: D4
    description: "Adoption needs evidence that the owner is gone (clean offline, stale heartbeat, 90 s of silence) or force, needs an approved mirror (or none needed) even with force, and a refused adoption changes, publishes and saves nothing"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_adoption_needs_the_owner_offline_or_force"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_unknown_owner_needs_force_until_enough_was_heard"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_stale_heartbeat_allows_adoption"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_adoption_requires_an_approved_mirror"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_not_a_mirror_and_unknown_device"
        status: pass
    human_judgment: false
  - id: D5
    description: "The marker persists and accumulates: every republish after a restart or an edit carries it, a chain A to B to C names A and B, only the newest eight are kept, and a follower that started after the adoption follows the adopter directly"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_marker_survives_a_restart_of_the_adopter"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_adopter_edits_after_adoption_keep_the_history"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_chain_of_adoptions_keeps_the_history"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_history_keeps_only_the_newest_eight"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_follower_that_was_offline_during_the_adoption"
        status: pass
    human_judgment: false
  - id: D6
    description: "A failed subentry add restores the mirror with its approval and baseline"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_failed_subentry_add_restores_the_mirror"
        status: pass
    human_judgment: false
  - id: D7
    description: "The adopt_device service is admin only, returns uuid, adopted and previous_owner, refuses with translated errors in en and de (the online-owner error names force: true), and its fields are described in services.yaml"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_services.py#test_adopt_service_errors_are_translated"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_adopt_force_with_an_online_owner_works"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_adopt_service_is_admin_only"
        status: pass
      - kind: integration
        ref: "tests/test_services.py#test_services_yaml_describes_adopt_device"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_required_adopt_keys_exist_in_both_languages"
        status: pass
    human_judgment: false
  - id: D8
    description: "With two real Home Assistant instances: create a device on the first, stop it, approve the mirror on the second, call mqtt_actions.adopt_device on the second; the device appears as an owned device of the second on the integration page, edits work and the entities stay"
    requirement: SYN-07
    verification: []
    human_judgment: true
    rationale: "Real core MQTT discovery, the real frontend integration page and a second instance are not reproduced by the fake broker tier; the plan names this as a human check"

duration: 17min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 11: Adoption of Orphaned Devices Summary

**A follower adopts the approved mirror of an offline owner under the same uuid (transferred_from marker, rev + 1, baseline and entities kept), other followers re-pin only for a marker that names their offline pinned owner, and an admin-only adopt_device service exposes it with force: true errors**

## Performance

- **Duration:** 17 min
- **Started:** 2026-10-02T16:50:37Z
- **Completed:** 2026-10-02T17:08Z
- **Tasks:** 3
- **Files modified:** 14 (8 source and translation files, 6 test files)

## Accomplishments

- Additive `transferred_from` list in the config document: at most 8 ids of the shape of any id, newest last, written only when non-empty, never hashed, `SCHEMA_VERSION` still 1; a malformed marker rejects the document with the new reason `bad_transfer`
- `Manager.async_adopt(device_id, force=False)`: preconditions in order (`not_a_mirror`, `not_approved`, `owner_not_offline`), then under the manager lock the mirror is dropped without a single broker message or core-registry cleanup, the transfer record and a rev seed are saved, the subentry is built with `subentry_payload` from the mirror's content and added, and a reconcile publishes document and discovery; a failed subentry add restores the mirror, its approval and its baseline
- Follower pin rule: a document of another owner moves the pin only when its marker names the pinned owner and `owner_offline` says so; every other claim is still the Phase 3 conflict. A re-pin with unchanged content keeps the mirror's breaker, Script and approval
- `mqtt_actions.adopt_device` (admin only, optional response) with `device_id` and `force`, returning `uuid`, `adopted`, `previous_owner`; translated `adopt_owner_not_offline` (names the owner, the device and `force: true`), `adopt_not_approved`, `adopt_not_a_mirror` in English and German
- Tests in both tiers: 13 document and 18 multi-instance scenarios plus 5 service tests and the translation parity test; mutation checks confirmed the pin rule, the offline check, the approval check, the history trim and the restore each fail a test when removed

## Task Commits

1. **Task 1: Tracer, an offline owner's device is adopted by a follower and a third instance re-pins to it** - `cf5ee54` (test), `7b08a8e` (feat)
2. **Task 2: Preconditions, the narrow pin rule and the transfer history** - `2654e19` (test), `90b72db` (feat)
3. **Task 3: The adopt_device service, its translated errors and the companion device** - `8886ea2` (test), `1480815` (feat)

**Plan metadata:** the docs commits that follow this summary (summary, then state and roadmap)

## Files Created/Modified

- `custom_components/mqtt_actions/document.py` - `TRANSFER_KEY`, `RejectReason.BAD_TRANSFER`, `ParsedDocument.transferred_from`, the `transferred_from` argument of `build_document`, strict marker parsing
- `custom_components/mqtt_actions/manager.py` - `AdoptionError`, `Manager.async_adopt`, `_async_adopt_locked`, `_async_drop_mirror`, the `transfers` Store key (load, save, prune, removal), the marker on every publish, `MirrorInfo.transferred_from`, the same-content fast path in `async_apply_mirror`
- `custom_components/mqtt_actions/sync.py` - `_may_repin`, `forget_mirror`, `async_restore_mirror`, the re-pin branch of the ingest
- `custom_components/mqtt_actions/services.py`, `services.yaml` - the `adopt_device` service and its schema
- `custom_components/mqtt_actions/const.py` - `STORE_TRANSFERS`, `MAX_TRANSFER_HISTORY`, `SERVICE_ADOPT_DEVICE`, the three `ADOPT_*` reason codes
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - service texts and the three refusals
- `tests/documents.py`, `tests/test_document.py`, `tests/test_multi_instance_ops.py`, `tests/test_services.py`, `tests/test_translations.py` - marker helper and the new scenarios
- `tests/test_manager_breaker.py` - the pinned Store key set now includes `transfers`

## Decisions Made

- The adoption holds the manager lock from dropping the mirror to the reconcile (see deviation 1) instead of releasing it before the subentry add as the plan sketched.
- An owner id that is not id-shaped cannot be named in a marker, so such a mirror is refused as `not_a_mirror`.
- A same-content document of a new owner only replaces the mirror's owner bookkeeping.
- Refusal keys are `adopt_<reason>` with placeholders `device` and `owner` only where the message uses them; `adopt_not_approved` uses `device`, `adopt_not_a_mirror` uses none.
- `force` never relaxes the approval requirement (the planner-added precondition stands as written; nothing was relaxed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Adoption keeps the manager lock until the device is added**
- **Found during:** Task 1 (async_adopt)
- **Issue:** The plan releases the lock before adding the subentry. In that window the retained or a live document of the old owner is ingested under the lock first and re-creates a mirror for an id that is about to be owned, leaving the id in both `devices` and `mirrors`
- **Fix:** The subentry add and `_async_reconcile_locked` run inside the same lock hold. The update listener of the entry reconciles later and finds nothing to do, as the plan expected
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Verification:** all adoption scenarios, `test_failed_subentry_add_restores_the_mirror`
- **Committed in:** 7b08a8e

**2. [Rule 2 - Missing critical] A mirror whose owner id is not id-shaped is refused**
- **Found during:** Task 1 (async_adopt)
- **Issue:** The owner id of a document only passes a label check, but the marker accepts ids of the shape of `is_valid_device_id`. Adopting such a mirror would make the adopter's own document fail its own parse (`bad_transfer`) and never be published
- **Fix:** Refused as `not_a_mirror` before anything changes
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Verification:** `test_not_a_mirror_and_unknown_device`
- **Committed in:** 7b08a8e

**3. [Rule 3 - Blocking] Companion mode select of the adopted device did not move to the subentry**
- **Found during:** Task 3 (the gap the plan asks to check)
- **Issue:** The select platform keeps an `added` set and only forgets an id when a devices-changed signal arrives while the id is in neither `devices` nor `mirrors`; without that signal the owned device never got a select under its new subentry
- **Fix:** One `_notify_devices_changed()` right after the mirror is dropped; `_async_add_device` sends the second one. Found while writing the code for Task 1, pinned by Task 3's test (removing the call fails `test_adopt_service_promotes_a_mirror`)
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Verification:** `tests/test_services.py::test_adopt_service_promotes_a_mirror`
- **Committed in:** 7b08a8e

**4. [Rule 1 - Bug] A re-pin released a tripped breaker and rebuilt the Script**
- **Found during:** Task 2 (RED test `test_repin_keeps_the_breaker_and_the_script_of_an_unchanged_mirror` failed on the assertion)
- **Issue:** Following a new owner went through `_update_mirror`, which builds a fresh breaker, so a forged or real marker for an offline owner would also release a paused device on every follower
- **Fix:** A document with the content the mirror already has only replaces the mirror info and refreshes the approval issues
- **Files modified:** custom_components/mqtt_actions/manager.py
- **Verification:** the test above, full suite
- **Committed in:** 90b72db

**5. [Rule 1 - Bug] A pinned test listed the exact Store keys**
- **Found during:** Task 1 verification
- **Issue:** `test_trip_is_persisted_as_config_hash` asserts the exact key set of the Store; the additive `transfers` key is a deliberate new key
- **Fix:** Added `STORE_TRANSFERS` to the expected set
- **Files modified:** tests/test_manager_breaker.py
- **Verification:** full suite
- **Committed in:** 7b08a8e

---

**Total deviations:** 5 auto-fixed (3 missing critical or blocking, 2 bugs)
**Impact on plan:** All necessary for correctness; no scope creep, no new files, no change of any locked decision.

## TDD Gate Compliance

All three tasks have a `test(04-11)` commit before their `feat(04-11)` commit. Task 1 failed as planned (no marker, no `async_adopt`, missing keyword), and so did Task 3 (the service did not exist; the registered error was core's `ServiceNotFound`). The Task 2 RED could not fail for most of its scenarios: the plan's Task 1 action already prescribes the precondition order, the narrow pin rule, the history trim and the restore, so Task 1's GREEN implemented them. Those tests pin behavior that already worked (checked by mutation: breaking the pin rule, the offline check, the approval check, the trim or the restore fails the matching test). The Task 2 RED commit contains one genuinely failing test (a re-pin must keep a tripped breaker and the Script), and its `feat` commit fixes that real defect (deviation 4). `check tdd-red-evidence` is not used because the plan type is `execute`, not `tdd`.

## Issues Encountered

- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` did not flake in any of the five full runs (1147 to 1185 tests).
- Forced adoption while the old owner is online starts the Phase 3 claim and heal exchange between the two owners (throttled, 60 s windows) until the old owner steps down; handling the returning owner is plan 04-12.
- A follower whose roster still shows the old owner online when the adopter's document arrives raises an `owner_conflict` and re-pins on the next document of the adopter (resync, reconnect, an edit or a restart). In the normal cases the owner's offline availability or its stale heartbeat precedes the adoption by far, so this is a narrow window; the manual resync on the adopter closes it.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 04-12: the returning old owner. Its start-up publish can overwrite the adopter's document, the adopter heals, and the old owner can recognize the marker (`transferred_from` contains its own id) to offer the Repairs release flow
- For 04-13 docs: adoption page (service fields, `force: true`, the approval requirement, the 90 second rule, the clean-offline shortcut), no new broker topic, so the ACL page needs no change
- Human check D8 (two real instances) stays open for the end-of-phase verification

## Self-Check: PASSED

- Source and test files from the key-files list exist on disk; SUMMARY frontmatter lists them
- Commits cf5ee54, 7b08a8e, 2654e19, 90b72db, 8886ea2, 1480815 exist on `gsd/phase-04-operations-recovery-and-release`
- Acceptance criteria: `grep -c transferred_from document.py` prints 9 (needs 4), `grep -c "def async_adopt" manager.py` prints 1, `grep -c owner_offline sync.py` prints 1, `grep -c adopt_device services.yaml` prints 1
- Plan verification: `uv run pytest tests -q` 1185 passed, `uv run pytest -m multi_instance -q` passed, `uv run ruff check .` and `uv run ruff format --check .` exit 0

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
