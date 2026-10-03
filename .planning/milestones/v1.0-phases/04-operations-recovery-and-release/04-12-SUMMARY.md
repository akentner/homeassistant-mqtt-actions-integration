---
phase: 04-operations-recovery-and-release
plan: 12
subsystem: recovery
tags: [home-assistant, mqtt, duplicate-instance-id, repairs, fix-flow, adoption, probatio]

requires:
  - phase: 04-operations-recovery-and-release
    provides: heartbeat, session id and PresenceManager (04-03), approval repairs flow and Repairs dispatch point (03-06), adopt_device with the transferred_from marker and the narrow re-pin rule (04-11)
provides:
  - Duplicate instance id detection in presence.py (two foreign-session heartbeats with the own id within 90 s, bounded, clears after 90 s of silence)
  - Manager.async_release_locally, a broker-silent local forget in a fixed order behind a reconcile guard, and Manager.async_resolve_duplicate_id (release all, new uuid4 id, one-shot offline suppression, scheduled reload)
  - Fixable Repairs issue duplicate_instance_id and DuplicateIdRepairFlow
  - Recognition of a transfer on an owned topic in sync.py, the transferred-away set, saved adopter document, TransferredRepairFlow and Manager.async_release_device_locally
  - A repairs dispatcher by issue id and the last legacy validation import replaced by probatio
affects: [04-13 docs (troubleshooting page, ACL note for the new instance id, returning owner and duplicate id pages)]

actuals:
  tokens: 17232
  tasks: 3
  commits: 8
plan_head_before: b32047ef277c895b7be945e98f4f6fd263fc6ca4
plan_head_after: 0d33aa8d61bef04b8745cc30fbc1481b4ad431d9

tech-stack:
  added: []
  patterns:
    - "A local release never publishes: the device leaves devices first, then subscriptions and Script, issues and the published/revs/tripped/transfers records go, the Store is saved at once, and only then are the subentries removed behind a _releasing guard that the reconcile honors"
    - "A fixable issue carries only identifiers in its data (instance id, device id plus claimant); the fix flow re-reads the manager on the form and again on the submit and aborts with changed when the identifier is not the current one"
    - "Publishing is guarded at the lowest level (async_publish_config, async_publish_discovery) for devices recognized as transferred away, so start, reconnect, resync, heal and edit all stay silent"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/presence.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/sync.py
    - custom_components/mqtt_actions/repairs.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_presence.py
    - tests/test_multi_instance_ops.py
    - tests/test_repairs_flow.py
    - tests/test_translations.py

key-decisions:
  - "The release primitive removes the subentries one at a time and yields once after each removal, so the update listener of every removal runs while the _releasing guard is still up (the guard is then exercised, not just present)"
  - "The no-publish rule for a transferred-away device sits inside async_publish_config and async_publish_discovery instead of only in _async_publish_owned, so a heal, an edit or a resync cannot reach the adopter's topics either"
  - "Deleting a device that was adopted away only forgets it locally: no discovery, config or state clear, because the topics are the adopter's (found while reviewing the guards, not in the plan)"
  - "A newer valid document of the same adopter only refreshes the saved payload; a different adopter replaces the issue, so the flow always binds the claimant that is current"
  - "Detection state lives in presence.py (deque with maxlen MAX_DUPLICATE_OBSERVATIONS on Manager.clock); the manager hook only raises or deletes the issue, never acts"

patterns-established:
  - "Pattern: a recovery flow asks for one confirmation and is idempotent against staleness; any identifier mismatch aborts changed and changes nothing"
  - "Pattern: a one-shot manager flag (_skip_offline_once) scopes a suppression to exactly the stop that the fix schedules"

requirements-completed: [SYN-10, SYN-07]

coverage:
  - id: D1
    description: "An instance that hears heartbeats with its own instance id and another session, twice within 90 seconds, confirms a duplicate; its own echo, one heartbeat and two heartbeats more than 90 seconds apart never do; the record is bounded and the detection clears after 90 seconds of silence"
    requirement: SYN-10
    verification:
      - kind: integration
        ref: "tests/test_presence.py#test_duplicate_detection_needs_two_foreign_session_heartbeats"
        status: pass
      - kind: integration
        ref: "tests/test_presence.py#test_two_foreign_heartbeats_more_than_90_seconds_apart_are_no_duplicate"
        status: pass
      - kind: integration
        ref: "tests/test_presence.py#test_duplicate_clears_after_90_seconds_of_silence"
        status: pass
      - kind: integration
        ref: "tests/test_presence.py#test_duplicate_observations_are_bounded"
        status: pass
    human_judgment: false
  - id: D2
    description: "Detection changes nothing by itself: both instances keep their devices, subentries and entry data and publish nothing but heartbeats"
    requirement: SYN-10
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_duplicate_detection_changes_nothing_by_itself"
        status: pass
    human_judgment: false
  - id: D3
    description: "The duplicate id fix forgets the copy's devices locally and gives it a new id; the retained config, discovery, state and availability topics of the original are byte identical, the copy publishes no empty payload and no offline for the shared id, and after the restart it mirrors the original's devices"
    requirement: SYN-10
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_duplicate_id_fix_leaves_the_originals_topics_byte_identical"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_stop_after_release_publishes_no_offline"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_duplicate_flow_form_and_confirmation"
        status: pass
    human_judgment: false
  - id: D4
    description: "The local release has a fixed order: released devices are not re-added by the reconcile of each subentry removal, the record loses published, revs, tripped and transfers but keeps baseline and mode, and the Store is saved at once while the subentries still exist"
    requirement: SYN-10
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_released_devices_are_not_readded_by_the_reconcile"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_release_keeps_baseline_and_mode_and_drops_the_rest"
        status: pass
    human_judgment: false
  - id: D5
    description: "The duplicate id Repairs issue is created once as fixable error with the escaped instance name and the instance id in its data, stays dismissed, is deleted when the duplicate clears or the hub is removed; the flow aborts not_loaded and changed; the dispatcher returns the right flow for each issue id"
    requirement: SYN-10
    verification:
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_duplicate_issue_is_created_once_and_cleared"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_duplicate_issue_is_removed_with_the_hub"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_duplicate_flow_aborts"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_dispatcher_returns_the_right_flow"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_required_duplicate_keys_exist_in_both_languages"
        status: pass
    human_judgment: false
  - id: D6
    description: "An old owner that comes back after its device was adopted recognizes the adopter's valid document that names it, stops healing and republishing that device, raises a fixable issue with escaped device and claimant, and never steps down or clears anything on its own; a marker naming someone else is the ordinary claim and a document the parser rejects never creates the issue"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_old_owner_recognizes_the_transfer_after_a_restart"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_recognizing_the_transfer_does_not_step_down"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_transferred_away_device_is_not_republished"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_marker_that_does_not_name_this_instance_is_a_claim"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_invalid_foreign_document_never_creates_the_transfer_issue"
        status: pass
    human_judgment: false
  - id: D7
    description: "The release flow shows device and claimant escaped, and on a submit releases the device locally without any clearing publish, removes its subentry, creates a mirror pinned to the claimant with the baseline kept and deletes the issue; it aborts for an unloaded entry, a different claimant or a device that is no longer owned"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_release_flow_follows_the_adopter"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_transferred_flow_aborts"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_required_transferred_keys_exist_in_both_languages"
        status: pass
    human_judgment: false
  - id: D8
    description: "Deleting a device on the old owner after the adopter took it clears nothing on the broker"
    requirement: SYN-07
    verification:
      - kind: integration
        ref: "tests/test_multi_instance_ops.py#test_deleting_a_transferred_away_device_clears_nothing_on_the_broker"
        status: pass
    human_judgment: false
  - id: D9
    description: "With two real Home Assistant instances that share an instance id (the same backup restored on both), the Repairs issue appears on one, the fix text reads correctly and after the confirmation that instance runs under a new id with the original's devices as mirrors while the original's entities stay available"
    verification: []
    human_judgment: true
    rationale: "Real core MQTT discovery, the real Repairs dialog and two real instances are not reproduced by the fake broker tier; the plan names this as a human check"
  - id: D10
    description: "With two real Home Assistant instances: adopt a device on the second, start the first again; the first shows the Repairs issue about the transferred device and, after the confirmation, the device as a mirror of the second with working entities"
    verification: []
    human_judgment: true
    rationale: "Real discovery overwrite and the registry behaviour of core MQTT during the start overlap cannot be reproduced by the fake broker; the plan names this as a human check"

duration: 21min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 12: Duplicate Instance ID and Returning Old Owner Summary

**A clone that shares an instance id is detected by two foreign-session heartbeats and repaired through a Repairs flow that forgets its devices locally and rotates the id without changing one byte of the original's broker state, and an old owner that returns after an adoption recognizes the adopter's marker, stops fighting and follows it through a second release flow**

## Performance

- **Duration:** 21 min
- **Started:** 2026-10-02T17:09:22Z
- **Completed:** 2026-10-02T17:30:34Z
- **Tasks:** 3
- **Files modified:** 11 (7 source and translation files, 4 test files)

## Accomplishments

- Duplicate detection in `PresenceManager`: a heartbeat with the own id and the own session is an echo and ignored, another session is an observation on `Manager.clock` (older than 90 s dropped, at most 8 kept); the second observation confirms, silence for 90 s clears through the tick and the expiry timer, which now also arms for this deadline. The manager hook only raises or deletes the issue and logs one fixed line
- `Manager.async_release_locally`: pops each owned device first, ends its subscriptions and Script, deletes its issues, drops its published, revs, tripped and transfers records, saves the Store at once, notifies, and only then removes the subentries (yielding after each removal) behind a `_releasing` guard in `_async_reconcile_locked`. It never publishes and never calls the delete or orphan paths
- `Manager.async_resolve_duplicate_id`: releases every owned device, sets a one-shot flag that makes the next `async_stop` skip the retained `offline` of the shared id, writes a new `uuid4` instance id into the entry data and schedules the reload. `test_duplicate_id_fix_leaves_the_originals_topics_byte_identical` compares every retained topic of the original before and after, and no empty payload is published by the copy
- Repairs: `duplicate_instance_id` (fixable, error, instance name escaped, instance id in data) with `DuplicateIdRepairFlow` (confirm form with `instance` and `devices`, aborts `not_loaded` and `changed`), `transferred_<device id>` with `TransferredRepairFlow`, a dispatcher by issue id (approval flow stays the default), and `probatio` instead of the last legacy validation import
- Returning old owner: `_check_owned` recognizes a valid foreign document whose marker lists this instance, keeps the adopter's payload and claimant, raises one fixable warning issue and goes quiet (no heal, no republish, no discovery, also not on start, reconnect, resync or edit). The flow releases the device locally and feeds the saved payload through the normal ingest path, so the mirror starts with the baseline and the mode
- English and German texts for both issues and both flows; the duplicate text states that only local devices go, the broker topics stay and a per-instance ACL needs the new id

## Task Commits

1. **Task 1: Tracer, detect a duplicate instance id, release locally and rotate the id** - `ab5b4fe` (test), `2cb8c96` (feat)
2. **Task 2: The duplicate id Repairs issue, its fix flow, the dispatcher and probatio** - `5d6fd12` (test), `830e402` (feat)
3. **Task 3: A returning old owner follows the adopter through a release flow** - `9a77335` (test), `1c45816` (feat)
4. **Unplanned hole found in Task 3 (Rule 2)** - `05467be` (test), `0d33aa8` (fix)

**Plan metadata:** the docs commits that follow this summary (summary, then state and roadmap)

## Files Created/Modified

- `custom_components/mqtt_actions/presence.py` - duplicate observations, `duplicate_detected`, the expiry deadline for the clearing
- `custom_components/mqtt_actions/manager.py` - `async_release_locally`, `_release_device`, `async_resolve_duplicate_id`, `async_release_device_locally`, `on_duplicate_id_changed`, the `_releasing` guard, the one-shot offline suppression, the publish guards, the adopted-away branch of `_async_remove_device`, issue cleanup in `async_remove_local_state`
- `custom_components/mqtt_actions/sync.py` - `TransferInfo`, the transferred-away map, recognition in `_check_owned`, `async_follow`, `clear_transferred`, the heal skip, `data` for fixable issues in `_raise_once`
- `custom_components/mqtt_actions/repairs.py` - `DuplicateIdRepairFlow`, `TransferredRepairFlow`, the dispatcher, `probatio`
- `custom_components/mqtt_actions/const.py` - `DUPLICATE_ID_CONFIRMATIONS`, `MAX_DUPLICATE_OBSERVATIONS`, `ISSUE_DUPLICATE_INSTANCE_ID`, `ISSUE_TRANSFERRED_PREFIX` (also in `ISSUE_DEVICE_PREFIXES`)
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - both issues and both fix flows
- `tests/test_presence.py`, `tests/test_multi_instance_ops.py`, `tests/test_repairs_flow.py`, `tests/test_translations.py` - detection, release, returning owner and flow scenarios

## Decisions Made

- The subentry removals yield once after each removal (see key-decisions), so a guard that is never reached by a test cannot rot silently. Mutation check: removing the guard fails `test_released_devices_are_not_readded_by_the_reconcile`.
- The recognized adopter document is kept in memory only (assumption A15): after a restart the old owner's first publish can briefly overwrite the adopter's document, the adopter heals within one throttle window and the old owner recognizes the marker again.
- The saved baseline of a released device survives in the Store written at release time and in memory for the mirror that follows in the same session. A restart prunes it like any baseline of an unknown id; a mirror created after the restart takes its baseline from the retained state replay.
- `async_follow` takes the saved payload as an argument instead of looking it up, because `SyncManager.forget` (called by the release primitive) already clears the recognition for the released id.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Deleting a transferred-away device cleared the adopter's topics**
- **Found during:** Task 3 (reviewing every path that publishes for an owned device after the recognition)
- **Issue:** The plan guards start, reconnect, resync and heal. The device delete path (`_async_remove_device`) still tombstones the config, discovery and state, which after an adoption belong to the adopter and would delete the device for every instance. The test failed with three clearing publishes
- **Fix:** A device recognized as transferred away is only forgotten locally; the three clears are skipped (the published id is still discarded)
- **Files modified:** custom_components/mqtt_actions/manager.py, tests/test_multi_instance_ops.py
- **Verification:** `test_deleting_a_transferred_away_device_clears_nothing_on_the_broker` (RED `05467be`, GREEN `0d33aa8`)
- **Committed in:** 0d33aa8

**2. [Rule 1 - Bug] One planned test variant could not fail the way it claimed**
- **Found during:** Task 3 GREEN
- **Issue:** The RED variant `tampered_hash` assumed that a wrong `hash` field makes the parser reject the document. The parser never trusts the wire hash and recomputes it, so the document was valid and rightly recognized
- **Fix:** The variant is `invalid_content` (a document with an unknown `kind`), which the parser really rejects
- **Files modified:** tests/test_multi_instance_ops.py
- **Verification:** the three variants of `test_invalid_foreign_document_never_creates_the_transfer_issue`
- **Committed in:** 1c45816

### Plan wording adapted

- The no-publish skip for transferred-away devices is placed in `async_publish_config` and `async_publish_discovery` (a superset of the plan's `_async_publish_owned` and `_async_heal` skips, which are both covered; `_async_heal` also checks the set explicitly)
- `SyncManager.async_follow(device_id, payload)` has the payload parameter (see Decisions)
- `_raise_once` gained a keyword `data`; an issue with data is fixable, so no second issue helper exists

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug in a planned test)
**Impact on plan:** Both necessary for correctness; no new files, no change of a locked decision.

## TDD Gate Compliance

All three tasks have a `test(04-12)` commit before their `feat(04-12)` commit, and the unplanned fix has `test(04-12)` before `fix(04-12)`. Each RED run failed on the missing feature: missing `duplicate_detected`, `async_release_locally`, `async_resolve_duplicate_id`, `DuplicateIdRepairFlow`, `TransferredRepairFlow`, `sync.transferred_away` and the translation keys. The RED for the delete hole failed on an assertion (three empty publishes). `test_recognizing_the_transfer_does_not_step_down` passed already in RED because the pre-plan code never steps down; it pins that property for the new code. Mutation checks after GREEN: removing the reconcile guard, the `_published` discard, the offline suppression, the immediate save, the publish guard, the marker condition or the follow call each fails at least one test. `check tdd-red-evidence` is not used because the plan type is `execute`.

## Issues Encountered

- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` failed once in one full run under load (the known flake from plan 04-05) and passed in three isolated runs, in the whole file and in two further full runs (1213 passed).
- Real-world overlap of the two owners: the old owner's start publishes its document and discovery before it hears the adopter's retained document, so the adopter's discovery briefly carries the old owner's availability topic until the adopter republishes (its Resync button). The issue text names this; no code path closes it.

## Known Stubs

None.

## Threat Flags

None - the surfaces (heartbeat observations, local release, adopter document) are covered by T-04-55 to T-04-60 of the plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 04-13 (documentation): troubleshooting page for the duplicate id (fix text, the new id is not in a per-instance ACL, devices to keep owning have to be created or imported again), the returning owner page (what the issue means, that the old owner keeps running its own actions for the device until released, that the mirror then needs an approval here), the A15 limitation (recognition is in memory, repeats after a restart)
- Known limitations worth a docs line: delete-everywhere hub removal on a former owner would still clear a device that was adopted away (the recognition does not outlive the manager); the baseline of a released device is not kept across a restart
- Human checks D9 and D10 (two real instances) stay open for the end-of-phase verification

## Self-Check: PASSED

- Source and test files from the key-files list exist on disk
- Commits ab5b4fe, 2cb8c96, 5d6fd12, 830e402, 9a77335, 1c45816, 05467be, 0d33aa8 exist on `gsd/phase-04-operations-recovery-and-release` and `git rev-list --count` from the ledger base measures 8
- Acceptance criteria: `grep -c "_releasing" manager.py` prints 4 (needs 3), `grep -c "class DuplicateIdRepairFlow" repairs.py` prints 1, `grep -c ISSUE_TRANSFERRED_PREFIX const.py` prints 2, the legacy validation library is not imported by `repairs.py`, each `test(04-12)` precedes its `feat(04-12)`
- Plan verification: `uv run pytest tests -q` 1213 passed, `uv run pytest -m multi_instance -q` 160 passed, `uv run ruff check .` and `uv run ruff format --check .` exit 0

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
