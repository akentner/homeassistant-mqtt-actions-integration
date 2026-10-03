---
phase: 03-trust-central-config-and-ownership
plan: 01
subsystem: sync
tags: [mqtt, retained-config, sha256, canonical-json, denylist, fake-broker, tdd]

requires:
  - phase: 02-select-devices-and-reliable-execution
    provides: DeviceSpec and TriggerSpec model, run mode and breaker settings, additive Store keys, Select devices
provides:
  - "Pure wire contract (document.py): canonical JSON, content hash, approval actions hash, strict parse_document, schema gate and migrate seam"
  - "Owner publish of one retained QoS-1 config document per device before discovery and availability, with persisted rev"
  - "Fixed service denylist (const.py) and a recursive static walker with approval sections and markdown escaping"
  - "Wave 0 seams: IncomingMessage.topic, Manager(gateway=, store_key=), MqttGateway.mqtt_entry_id, tests/fake_broker.py two-hass harness"
affects: [03-02, 03-03, 03-04, 03-05, 03-06, 03-07, 04-operations]

requirements-completed: [SYN-01, SYN-04, TRU-03]

plan_head_before: 65cc4e72be105b0da282192e21a718a656f96bd9
plan_head_after: ff6932b8c74bfd8bb4a86e6c5b9802164ed9fa43

actuals:
  tokens: 27300
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Build the wire document from DeviceSpec (defaults applied), never from raw subentry data"
    - "Typed, content-free rejection reasons (RejectReason StrEnum) for every hostile document"
    - "Injectable gateway and store key so real Managers run against a FakeBroker"

key-files:
  created:
    - custom_components/mqtt_actions/document.py
    - tests/fake_broker.py
    - tests/test_document.py
    - tests/test_sync_owner.py
    - tests/test_fake_broker.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/topics.py
    - custom_components/mqtt_actions/discovery.py
    - custom_components/mqtt_actions/actions.py
    - custom_components/mqtt_actions/mqtt_gateway.py
    - custom_components/mqtt_actions/manager.py
    - tests/conftest.py
    - tests/test_topics.py
    - tests/test_manager.py
    - tests/test_manager_breaker.py

key-decisions:
  - "Wire hash is sha256 over compact, sorted, unescaped UTF-8 canonical JSON of the shared content (kind, name, run_on_startup, run_mode, breaker limits, actions); owner, owner_name, rev, hash, device_id and schema_version are not content. Pinned by a golden fixture."
  - "actions_hash (approval binding) covers kind, run_on_startup and the StateValue-to-actions mapping sorted by lower-cased StateValue; renames, run mode and breaker changes never invalidate an approval (A5)."
  - "On start the owner publishes all config documents, then all discovery, then online; _async_add_device only publishes per device for a device added after start."
  - "A reconcile that leaves the content hash unchanged publishes no config document (changed_only); start and every reconnect publish unconditionally."
  - "Rejection reasons are a RejectReason StrEnum; messages never carry payload or action content."
  - "Residual-risk entries of the walker are the literals scene, event and device, and the normalized service name of a static call into the script domain or automation.trigger."

patterns-established:
  - "Owner publish order: config documents, then discovery, then availability online (load-bearing for the prune rule of plan 03-05)"
  - "Multi-instance tests: make_instance('name', hass=..., subentries=[...]) gives a started instance with its own hass, Manager and FakeGateway"

coverage:
  - id: D1
    description: "Each owned device is published as one retained QoS-1 versioned, hash-stamped document before discovery and availability, on start, change and every reconnect"
    requirement: SYN-01
    verification:
      - kind: unit
        ref: "tests/test_sync_owner.py#test_owner_publishes_one_retained_versioned_document_per_device"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_publish_order_config_then_discovery_then_availability"
        status: pass
      - kind: unit
        ref: "tests/test_document.py#test_wire_fixture_switch"
        status: pass
    human_judgment: false
  - id: D2
    description: "rev grows only when the content hash changes and is persisted with that hash, so a restart republishes the same rev and a reconnect republishes the identical document"
    requirement: SYN-04
    verification:
      - kind: unit
        ref: "tests/test_sync_owner.py#test_rev_and_hash_persist_across_restart"
        status: pass
      - kind: unit
        ref: "tests/test_sync_owner.py#test_reconnect_republishes_identical_documents"
        status: pass
    human_judgment: false
  - id: D3
    description: "parse_document is the only way a payload becomes a spec: strict, size-capped, typed rejections, hashes recomputed, schema_version gate; denylist walker finds denied and templated services recursively"
    requirement: TRU-03
    verification:
      - kind: unit
        ref: "tests/test_document.py#test_parse_rejects_invalid_documents"
        status: pass
      - kind: unit
        ref: "tests/test_document.py#test_parse_never_trusts_the_wire_hash"
        status: pass
      - kind: unit
        ref: "tests/test_document.py#test_walker_finds_services_recursively"
        status: pass
    human_judgment: false
  - id: D4
    description: "FakeBroker with real retain semantics and two real hass instances running two unmodified Managers; IncomingMessage carries the topic"
    verification:
      - kind: integration
        ref: "tests/test_fake_broker.py#test_two_instances_share_one_broker"
        status: pass
    human_judgment: false
  - id: D5
    description: "The denylist policy (A1) and the 256 KiB / depth 32 tunables (A2) are assumptions that need the user's confirmation"
    verification: []
    human_judgment: true
    rationale: "The denylist is a fixed, non-extendable constant (D-03); which services it names is policy and no test can assert it is the right one"

duration: 12min
completed: 2026-10-01
status: complete
---

# Phase 3 Plan 01: Central Config Document Summary

**Retained, versioned, sha256-stamped config document per owned device with a strict pure parser, a fixed recursive service denylist and a two-hass FakeBroker test tier**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-30T22:54:10Z
- **Completed:** 2026-09-30T23:07:00Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto, all TDD)
- **Files modified:** 15 (5 created, 10 modified)

## Accomplishments

- The wire contract is fixed in one pure module (`document.py`) and pinned by a golden fixture (`test_wire_fixture_switch`: one literal JSON text, one literal sha256 digest computed independently of the implementation).
- The owner publishes `<base>/v1/devices/<id>/config` retained at QoS 1 on start, on add, on change and on every reconnect, always before discovery and the `online` availability; `rev` is persisted with its hash in the additive `revs` Store key and survives a restart.
- `parse_document` rejects 19 typed reasons (size in bytes, JSON shape, schema, identity, text hygiene, ranges, option rules, nesting depth) without ever putting payload content into a message, never trusts the wire `hash`, and raises `SchemaTooNewError` before reading anything else.
- Denylist walker, approval sections and `escape_markdown` are ready for plans 03-04 and 03-06 to enforce; `validate_actions_structure` gives the instance-independent schema gate.
- Wave 0 seams for the rest of the phase: `IncomingMessage.topic`, `Manager(gateway=, store_key=)`, `MqttGateway.mqtt_entry_id()` and `tests/fake_broker.py` (`FakeBroker`, `FakeGateway`, `make_instance`).

## Task Commits

1. **Task 1: Tracer, owned device published as one retained config document** - `234df93` (test, RED), `9656f5c` (feat, GREEN)
2. **Task 2: Strict parsing, schema gate, denylist walker, approval sections** - `f36f63b` (test, RED), `6cb78ae` (feat, GREEN)
3. **Task 3: Wave 0 seams and FakeBroker tier** - `d72c538` (test, RED), `ff6932b` (feat, GREEN)

**Plan metadata:** added by the docs commit that follows this file.

## TDD Gate Compliance

All three tasks have a `test(03-01)` commit before its `feat(03-01)` commit; no refactor commits were needed. RED evidence: the topic tests failed on `AttributeError` (the helpers did not exist), the seam test on its first assertion; the other new test modules failed at collection with `ImportError`/`ModuleNotFoundError` because the modules and constants they test did not exist yet. Collection errors are an unavoidable RED for a not-yet-existing module, so the RED evidence verifier (`check tdd-red-evidence`) would class those runs as `INVALID_RED`; it was not run. GREEN was confirmed by the full suite after each feat commit.

## Files Created/Modified

- `custom_components/mqtt_actions/document.py` - wire contract: canonical JSON, content and actions hash, build/serialize, strict parse, migrate seam, denylist walker, approval sections, markdown escape
- `custom_components/mqtt_actions/const.py` - `SCHEMA_VERSION`, `STORE_REVS`, `MAX_DOCUMENT_BYTES`, `MAX_ACTION_DEPTH`, `DENIED_DOMAINS`, `DENIED_SERVICES`
- `custom_components/mqtt_actions/topics.py` - config topic, three wildcards and three strict id parsers
- `custom_components/mqtt_actions/discovery.py` - `async_publish_config`, `async_clear_config`
- `custom_components/mqtt_actions/actions.py` - `validate_actions_structure`
- `custom_components/mqtt_actions/mqtt_gateway.py` - `IncomingMessage.topic`, `mqtt_entry_id()`
- `custom_components/mqtt_actions/manager.py` - public `async_publish_config` / `async_publish_discovery`, `_revs` persistence, config-first publish order, `gateway` and `store_key` injection
- `tests/fake_broker.py`, `tests/conftest.py` (`fake_broker`, `make_instance`) - multi-instance harness
- `tests/test_topics.py`, `test_document.py`, `test_sync_owner.py`, `test_fake_broker.py` - new behavior tests (133 + 41 + 26 cases in the three new modules)

## Decisions Made

See `key-decisions` above. Additionally: `parse_document` accepts breaker limits as plain ints only (a float like `5.0` is rejected as `bad_breaker`), and `run_on_startup`, `run_mode` and the breaker keys are required on the wire (no defaults on receive), since the owner always publishes them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Start published per device instead of all config documents first**
- **Found during:** Task 1 (`test_publish_order_config_then_discovery_then_availability` failed after the first implementation)
- **Issue:** `_async_add_device` published config and discovery per device, so with two devices the start order was config, discovery, config, discovery, violating "every config precedes every discovery" (D-15).
- **Fix:** `_async_add_device` publishes only when it is not part of the start; `async_start` runs the new `_async_publish_owned` (all documents, then all discovery) under the lock, then availability. `_async_republish` uses the same helper.
- **Files modified:** `custom_components/mqtt_actions/manager.py`
- **Verification:** the order test passes for start and reconnect; full suite green.
- **Committed in:** `9656f5c`

**2. [Rule 1 - Bug] Two existing tests encoded behavior the document changes**
- **Found during:** Task 1 (full suite run)
- **Issue:** `tests/test_manager.py::test_issue_and_log_do_not_leak_action_data` asserted the canary is absent from all captured logs, but core MQTT's own DEBUG line for the (by design action-carrying) config publish now contains it. `tests/test_manager_breaker.py::test_trip_is_persisted_as_config_hash` asserted the exact Store key set, which gained `revs`.
- **Fix:** the leak test now asserts on records of the `custom_components.mqtt_actions` loggers only (and that some exist); the Store test expects `STORE_REVS`.
- **Files modified:** `tests/test_manager.py`, `tests/test_manager_breaker.py`
- **Verification:** both pass; intent of T-01-10 (this integration never logs action data) is unchanged.
- **Committed in:** `9656f5c`

**3. [Rule 2 - Missing critical] `changed_only` on the change path**
- **Found during:** Task 1
- **Issue:** the plan calls `async_publish_config(device)` in `_async_change_device` but also requires that a reconcile that changes nothing in the spec publishes nothing new; an unconditional publish would republish the same document.
- **Fix:** `async_publish_config(device, *, changed_only=False)`; the change path passes `changed_only=True`, start and reconnect publish unconditionally.
- **Files modified:** `custom_components/mqtt_actions/manager.py`
- **Committed in:** `9656f5c`

**4. [Rule 3 - Blocking] Reason codes as a StrEnum**
- **Found during:** Task 2 (Ruff EM101 on `raise DocumentRejectedError("literal")`)
- **Fix:** `RejectReason(StrEnum)`; `DocumentRejectedError.reason` compares equal to the plain strings the tests and plan use.
- **Files modified:** `custom_components/mqtt_actions/document.py`
- **Committed in:** `6cb78ae`

**5. [Rule 1 - Bug] Walker depth off by one versus `actions_depth`**
- **Found during:** Task 2
- **Issue:** `analyze_actions` allowed one more container level than `parse_document` (`> MAX` on a zero-based depth).
- **Fix:** the walker counts container levels above the node and raises at `>= MAX_ACTION_DEPTH` for a container; boundary assertions added to `test_walker_depth_guard` in the GREEN commit.
- **Files modified:** `custom_components/mqtt_actions/document.py`, `tests/test_document.py`
- **Committed in:** `6cb78ae`

---

**Total deviations:** 5 auto-fixed (3 Rule 1, 1 Rule 2, 1 Rule 3)
**Impact on plan:** all necessary for correctness of the specified behavior; no scope change. Existing tests changed: `tests/test_manager.py::test_issue_and_log_do_not_leak_action_data` and `tests/test_manager_breaker.py::test_trip_is_persisted_as_config_hash`; no existing test asserted an exact publish sequence that broke.

## Issues Encountered

- A lone surrogate in an option value cannot reach `_encodable` through `parse_document` because the orjson parser already rejects it as `not_json`; the plan's `bad_option_value (not encodable)` case is therefore covered by a dedicated test that accepts any `DocumentRejectedError`, and the `_encodable` check stays as defense in depth.
- The plan's `test_publish_order_*` hint to wrap the gateway publish was replaced by reading the ordered `mqtt_mock.async_publish` call list, which records the same sequence.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Open items handed to later plans (not stubs in this plan's scope):

- Deleting a device or removing the hub does not yet clear the retained config topic (`DiscoveryPublisher.async_clear_config` exists but no caller); the tombstone order of D-16 and the D-11 hub-removal redesign belong to the delete and ownership plans. Until then a deleted device leaves its retained config document on the broker.
- `parse_document` and the walker are not yet wired to a subscriber; plan 03-02 onward consumes them.

## Next Phase Readiness

- Plans 03-02 to 03-07 can build follower apply, approval, enforcement and delete on `parse_document`, `ParsedDocument`, `analyze_spec`, `approval_sections`, `escape_markdown`, `IncomingMessage.topic`, `DiscoveryPublisher.async_clear_config`, `MqttGateway.mqtt_entry_id` and `make_instance`.
- Needs user confirmation at review: the denylist contents (A1), `MAX_DOCUMENT_BYTES = 256 KiB` and `MAX_ACTION_DEPTH = 32` (A2), and that `run_on_startup` belongs to `actions_hash` (A5).
- Residual-risk format for plan 03-04/03-06 consumers: `ActionAnalysis.residual` holds `scene`, `event`, `device`, and normalized names such as `script.turn_on` or `automation.trigger`; `templated` holds the template strings as written; `denied` holds normalized names. A templated name such as `shell_command.{{ x }}` is reported as templated only and relies on the execution-time guard (D-05) of plan 03-06.

## Self-Check: PASSED

- Created files exist: `document.py`, `tests/fake_broker.py`, `tests/test_document.py`, `tests/test_sync_owner.py`, `tests/test_fake_broker.py` (FOUND)
- Commits exist: `234df93`, `9656f5c`, `f36f63b`, `6cb78ae`, `d72c538`, `ff6932b` (FOUND); every `test(03-01)` commit precedes its `feat(03-01)` commit
- `uv run pytest -q` 589 passed; `uv run ruff check .` and `uv run ruff format --check .` clean
- Acceptance criteria: seven topic functions (grep 7), `test_only_gateway_imports_mqtt_component` passes, `test_wire_fixture_switch` pins one JSON literal and one 64-character digest, `grep -c topic_matches_sub tests/fake_broker.py` is 3, `test_two_instances_share_one_broker` uses two distinct hass objects
