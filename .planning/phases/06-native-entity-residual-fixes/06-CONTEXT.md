# Phase 6: Native Entity Residual Fixes - Context

**Gathered:** 2026-10-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the two accepted v1.0 review residuals of Phase 5. IN-02 (MIG-04): a native mirror stays native after a restart even
when its config document is at `MAX_DOCUMENT_BYTES`. IN-03 (MIG-05): a retained legacy Discovery replay between the
takeover's registry move and the retained clear leaves no `_2` duplicate, and the migrated entities keep registry ids
and entity ids. The README Limitations section drops both residuals. No new capabilities.

</domain>

<decisions>
## Implementation Decisions

### IN-02: where the native flag lives
- **D-01:** The native flag of a mirror is persisted as a set of mirror device ids in `STORE_NATIVE` (new field in `NativeState`, next to `pending` and `devices`), not in the stored payload. Parsed with `_parse_native` and `is_valid_device_id`. Additive Store key, no version bump (as in 04-05 and D-09 of Phase 5). Reserving headroom in the size cap is rejected: it contradicts success criterion 1.
- **D-02:** Loading: a mirror is native if its id is in the set OR its stored payload carries the v1.0.0 marker, so v1.0.0 Stores stay native. Only the set is written from now on; `with_native_marker` (`document.py:188`) stops being the persistence path and is removed. The first save moves old marker-only mirrors into the set.

### IN-02: lifecycle of the flag
- **D-03:** An id leaves the set only when the mirror ends: device deleted, adoption (it becomes owned, then `NativeState.devices` applies) or release. A document without the marker never resets it (T-5-11 stays). A re-pin to another owner keeps the flag only if that owner's document carries the marker.

### IN-03: strategy against the replay
- **D-04:** Keep the order migrate payload, registry takeover, retained clear (D-12 of Phase 5; a clear before the move deletes the legacy registry entries, T-5-08). The fix is a duplicate catch after the move: new `mqtt`-platform entities of the device id are detected and removed or merged so the migrated entities keep their registry ids and entity ids. Reuse the twin logic and `_carries_the_identity` in `takeover.py`. Waiting for the MQTT discovery queue is rejected: core exposes no public settle signal.
- **D-05:** The catch runs twice: right after the move (before the clear is published) and again after the retained clear (after a short quiet period), because the replay can arrive in the window between them.

### Tests
- **D-06:** The IN-03 test delivers the replay by replacing `async_clear_device` (or the gateway publish) with a variant that plays the retained legacy Discovery via `async_fire_mqtt_message` just before the clear. Deterministic, no production hook. The window is exactly the call before the clear.
- **D-07:** TDD, one failing-test commit per fix first (`test:`), then the fix (`fix:`). The IN-02 test is a Store round trip with a document exactly at `MAX_DOCUMENT_BYTES`: after a restart it is native, starts no test-topic subscription and causes no extra reload on the next document. Both tests must be red on v1.0.0 code; the existing takeover, native-entity and cutover suites stay green.

### Claude's Discretion
- Exact names and placement of the new `NativeState` field and the duplicate-catch helper.
- Length of the quiet period before the second catch, and whether a Multi-Instance test is added on top of the unit test (not required).
- Wording of the README change (criterion 4) and of any log line for a removed duplicate (no registry or broker content in logs).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` — Phase 6 goal and success criteria 1 to 4
- `.planning/REQUIREMENTS.md` — MIG-04, MIG-05

### Origin of the residuals
- `.planning/milestones/v1.0-phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-REVIEW.md` — IN-02 and IN-03 findings and suggested fixes
- `.planning/milestones/v1.0-phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-REVIEW-DISPOSITION.md` — why they were accepted
- `.planning/milestones/v1.0-phases/05-evaluate-native-switch-select-entities-instead-of-mqtt-disco/05-CONTEXT.md` — D-05, D-09, D-12 (migration order, additive markers, takeover before platform forward)

### Code
- `custom_components/mqtt_actions/document.py` — `with_native_marker` (188-204), `NATIVE_KEY`
- `custom_components/mqtt_actions/manager.py` — `NativeState` (311), `_parse_native` (327), `_parse_mirrors` (283), `_mirror_info` (~1795), `_async_native_takeover` (873), `_async_finish_takeover`, `_data_to_save` (1218)
- `custom_components/mqtt_actions/takeover.py` — `async_take_over` (107), `_async_wait_unloaded`, `_carries_the_identity`
- `README.md` — Limitations section (~336), size-limit and replay bullets to remove

### Tests
- `tests/` — `test_a_late_replay_duplicate_is_cleaned_at_the_next_call` (existing late-replay coverage), takeover, native-entity and cutover suites

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NativeState` + `_parse_native` + `_data_to_save`: the existing persisted native state, extended by one set.
- Twin handling and `_carries_the_identity` in `takeover.py`: the base for the duplicate catch.
- `takeover.async_flush_registries`: registry files hold the move before the clear goes out.

### Established Patterns
- Additive Store keys without a version bump; malformed Store values fall back to defaults.
- Order migrate, takeover, clear; the clear is retried via `_clear_unconfirmed` and `_native_pending` (WR-02).
- Tests use the three tiers (unit, real Mosquitto, multi_instance); modules using `make_instance` need the `multi_instance` marker.

### Integration Points
- `_mirror_info(keep_native=...)` and `_parse_mirrors` read and write the native status of a mirror.
- `_async_native_takeover` is where the duplicate catch is called before and after `_async_finish_takeover`.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (WR-03, authenticating the cutover gate, and backlog 999.1 remain later work.)

</deferred>

---

*Phase: 6-Native Entity Residual Fixes*
*Context gathered: 2026-10-04*
