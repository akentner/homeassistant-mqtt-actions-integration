# Phase 4: Operations, Recovery and Release - Research

**Researched:** 2026-10-02
**Domain:** Home Assistant custom integration (Python 3.14, HA 2026.9.x): services with responses, MQTT presence/ack protocol, native entities, device registry, Repairs, diagnostics, GitHub Actions release
**Confidence:** HIGH for the HA API and in-repo facts (read this session from the venv at HA 2026.9.4 and from the repo), MEDIUM for the frontend behavior (read from the frontend `dev` branch), LOW only where tagged `[ASSUMED]`

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Re-trigger and acknowledgements (OPS-01, OPS-02)**
- **D-01:** The re-trigger service runs the actions of the trigger that matches the device's last acted state (for a Select, the current option). An optional parameter selects a different trigger. It never changes the entity state or the baseline, and it does not count toward the circuit breaker (same as the test button, Phase 2 D-13).
- **D-02:** One call targets exactly one device (required parameter) and reaches every instance that approved it. There is no "all devices" call and no instance filter in v1.
- **D-03:** The service returns a service response (`SupportsResponse`): per instance a status of executed, not approved, paused, disabled/observing, error, or no answer, collected within a timeout window (start value 5 s). It does not wait longer than the window. No event-bus variant in v1.
- **D-04:** Every call carries a `request_id` (UUID). Receivers remember the last N ids and ignore duplicates. The message is not retained. Per device, at most one re-trigger per 5 s is accepted; further calls are rejected with an error to the caller. The values are constants in `const.py`, not user-configurable. — **Reversibility:** costly — topic name, payload fields and acknowledgement shape become a cross-instance wire contract.

**Roster, heartbeat and duplicate instance ID (OPS-03, SYN-10)**
- **D-05:** Every instance publishes a heartbeat every 30 s on a new non-retained topic under `<base>/v1/instances/<instance_id>/`, carrying instance id, name, integration version, device count and a random per-start session id. A peer counts as offline after 90 s without a heartbeat, which also covers crashes. The retained availability topic and the Phase 3 prune logic stay as they are. A retained heartbeat is rejected because a crashed peer would look current forever. A Last Will is not possible (HA owns the MQTT connection, Phase 3 D-19). — **Reversibility:** costly — heartbeat topic and payload are a wire contract and the ACL in `docs/broker-acl.md` must grant it.
- **D-06:** The roster is a diagnostic sensor on the hub: state is the number of online instances, attributes list name, id, version, last seen and online or offline. There is no separate roster service.
- **D-07:** Duplicate id detection uses the session id: an instance that hears a heartbeat with its own instance id but a different session id raises a Repairs issue. The issue has a fix flow that gives this instance a new instance id. Nothing happens automatically.
- **D-08:** The fix flow discards the copy's own devices locally only: no tombstone, no discovery deletion, no state clearing. The original keeps ownership and topics, and the copy then sees the same devices as mirrors of the original. A copy that wants independent devices re-creates them (or imports an export).

**Ownership, export, import, resync (SYN-07, SYN-08, DSC-04)**
- **D-09:** SYN-07 is implemented as adoption of orphaned devices only. A device can be adopted when its owner is offline according to the roster, or on explicit confirmation (`force`). Adoption publishes a new document with the new owner and a transfer marker, and followers release the owner pin only for a document that carries that marker. This is the single exception to Phase 3 D-17 (first owner wins, no takeover); everything else in D-17 stays. Active hand-off from the current owner (offer and accept) is out of scope. — **Reversibility:** one-way — the transfer marker becomes part of the document schema (needs a `schema_version` decision) and changes the pin rule followers apply.
- **D-10:** Adoption is a service (`adopt_device`, device selector). It fails with a clear error when the owner is online, naming `force: true`. A mirror has no UI (Phase 3 D-08), so no new editing surface is added.
- **D-11:** Export is a service that returns JSON as the service response (all owned devices or a selection) and can also write a file under `/config`. Import is a service that takes JSON or a file path. Import always assigns new device UUIDs, so nothing collides with existing devices, and imported devices are owned by this instance. No option to keep UUIDs in v1. — **Reversibility:** costly — the export format is a user-facing file contract once people keep backups.
- **D-12:** Manual resync is a service and a button on the hub device. Both run the existing Phase 3 order (documents, then discovery, then `online`).

**Visibility on the integration page**
- **D-13:** The user wants the owned and mirrored devices and their entities to be visible on the MQTT Actions integration page, like other integrations show devices and entities. Hub entities (roster sensor, resync button, and the mode selects below) belong there. Mirrored and owned discovery devices should additionally be linked to the MQTT Actions config entry in the device registry. Whether the page then also lists entities that belong to the core MQTT entry is open; the researcher must verify what Home Assistant actually shows. Entities created by MQTT Discovery stay the contract for the device entities (project constraint).

**Per-instance and per-device mode (SYN-09)**
- **D-14:** Three modes, local to the instance and never part of the document: `run` (as today), `observe` (state and baseline are tracked, no actions run, each suppressed run is logged), `disabled` (the entity remains, no processing, no baseline). The modes apply to owned and mirrored devices.
- **D-15:** The mode is set through a configuration-category select entity per device on this instance, stored locally. This is a native, instance-local entity and not a Discovery entity, because Discovery messages are shared across instances. The researcher must settle how a native select coexists with the Discovery device of the same device id. Because the select is a hub-owned entity it also shows on the integration page (D-13).
- **D-16:** Resolve WR-04 from Phase 3 by binding `run_mode`, `breaker_max_runs` and `breaker_window` into `actions_hash`. A changed value then needs re-approval like changed actions, and the README sentence about the hash becomes true. Existing approvals lapse once; the planner must include a migration or an explicit one-time re-approval notice. — **Reversibility:** costly — the hash format changes and every existing approval is invalidated.

**Diagnostics (OPS-04)**
- **D-17:** The diagnostics download shows structure and redacts content. Included: hub options (base topic, instance name), roster, device list (uuid, kind, owner, mode, approval state, breaker state, rev, hash). Redacted: action content (YAML, templates, entity ids, service data), full instance ids shortened, broker credentials and hostnames.

**Documentation, release and CI (OPS-05, OPS-06)**
- **D-18:** Docs stay Markdown in the repo: the README is the entry point; `docs/` gets pages for operations (re-trigger, roster, resync, adoption, export and import, modes), diagnostics and troubleshooting. `docs/broker-acl.md` stays and is extended for the heartbeat topic. No docs generator.
- **D-19:** A tag `v*.*.*` triggers a release workflow that fails when `manifest.json` `version` differs from the tag, runs the test jobs, then creates a GitHub release with generated notes. No zip is needed for HACS. — **Reversibility:** costly — the tag and version scheme is what HACS users see.
- **D-20:** CI runs one job per test tier: unit (no broker), real Mosquitto (`tests/broker`) and multi-instance (fake broker). Mosquitto is installed only in the broker job. The release workflow requires all three.

### Claude's Discretion
- Service names and exact schemas, heartbeat and re-trigger topic names, payload field names, the number N of remembered request ids, the response timeout value, translation keys, Repairs wording, the format of the export file and its version field.
- How the transfer marker is encoded in the document and whether it needs a `schema_version` bump.
- How the mode select is implemented (platform, restore of state) and how the Discovery device and the native entity share one device in the registry.
- The structure of the CI jobs and the pytest markers or paths that separate the tiers.

### Deferred Ideas (OUT OF SCOPE)
- Active hand-off of a device from its current owner to another instance (offer and accept handshake). Phase 4 covers adoption of orphans only.
- Follower-local actions on mirrored devices, with per-instance entity mapping (backlog 999.1, MAP-01).
- Keep-UUID import for restoring after data loss (`keep_ids`), with collision handling.
- A time limit on `observe` and `disabled`.
- Residual Phase 3 review items A2 to A7 (see `03-SECURITY.md`) are not part of this phase unless the planner folds them in.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPS-01 | A service re-triggers the actions on all approved instances (non-retained, `request_id` dedupe, rate-limited) | Re-trigger protocol (Pattern 1), admin service with `SupportsResponse` (Pattern 6), pitfalls on self-echo, stale QoS 1 delivery and rate-limit double counting |
| OPS-02 | Instances acknowledge a re-trigger, and the caller can see which instances executed it | Ack topic per requester, response collection with early exit, roster-derived "no answer" (Pattern 1) |
| OPS-03 | User can see the connected instances (roster with presence heartbeat) | Heartbeat and roster design (Pattern 2), roster sensor with unrecorded attributes (Pattern 5) |
| OPS-04 | Diagnostics export with sensitive data redacted | Allow-list diagnostics platform (Pattern 9); never dump-then-redact |
| OPS-05 | README and docs cover setup, trust model, limitations; releases automated with manifest version in step with the tag | Docs plan, release workflow (Pattern 10), repo-structure test changes |
| OPS-06 | Test suite covers unit level, a real-Mosquitto tier, and multi-instance scenarios via an in-memory fake broker | Marker-based tier split, CI job layout, fake-broker seams that the new code needs (Validation Architecture) |
| SYN-07 | User can transfer ownership of a device or adopt an orphaned device | Adoption design incl. transfer marker without schema bump (Pattern 4), returning-owner trap |
| SYN-08 | User can export devices to JSON and import them | Export/import design (Pattern 8), file handling findings |
| SYN-09 | User can set per instance and device whether actions run, are only observed, or are disabled | Mode gate and native select on a companion device (Patterns 3 and 5) |
| SYN-10 | A duplicate instance ID (cloned or restored instance) is detected and reported | Session-id detection, fix flow with local-only discard order (Patterns 2 and 7) |
| DSC-04 | User can trigger a manual resync that republishes config and discovery of all owned devices | Existing `Manager._async_republish` reused by service and hub button |
</phase_requirements>

## Summary

The phase is mostly additive on a mature code base (823 passing tests in 46 s, run this session). Four findings change the plan compared to the CONTEXT assumptions and the planner must act on them.

1. **D-13 cannot be done as written.** In Home Assistant 2026.9 a device belongs to exactly one config entry, so a discovery device (MQTT entry) cannot also be linked to the MQTT Actions entry, and the integration page lists devices and entities by their own config entry. The way to make owned and mirrored devices and their entities visible on the MQTT Actions page is a **companion device** per owned or mirrored device, registered by this integration under its own entry (under the matching subentry for owned devices), carrying the native mode select. The core MQTT entry's entities do not appear on the page.
2. **D-08 and D-09 carry destructive traps.** Phase 3 teardown (`_async_remove_device`, `_async_orphan_cleanup`) tombstones broker topics. A "discard locally" fix flow that reuses it would delete the original's devices for everyone. Local discard needs its own primitive with a fixed order (pop, forget published ids, save, remove subentry). Adoption needs a marker that persists in the document and a decision on the returning old owner.
3. **The test harness bypasses `async_setup_entry`.** `tests/fake_broker.py` builds `Manager` directly, so services and platforms that live in `__init__.py` are invisible to the multi-instance tier. Put behavior in `Manager` (and small collaborators), keep service handlers and entities thin, and extend `InstanceFactory` only for what must be wired.
4. **Several repo tests pin things this phase changes** (`WORKFLOW_FILES`, the SHA-pin rule for job-level `uses`, the CI command test, `test_actions_hash_binds_mapping_and_startup_flag`, README phrase tests, the "no device_id in fenced examples" test). They must be updated in the same plans.

No new third-party packages are needed. Everything uses HA core APIs, the existing dev group, and the preinstalled `gh` and `jq` on GitHub runners.

**Primary recommendation:** Build the protocol pieces (heartbeat/roster, re-trigger/ack, transfer marker) as small testable classes owned by `Manager`, expose them through thin admin services and native entities, register services in `async_setup`, create companion devices for D-13, and split CI by pytest markers with a local reusable workflow that the tag-triggered release requires.

## Project Constraints (from CLAUDE.md)

From `.claude/CLAUDE.md` (project) and the parent `CLAUDE.md` files:
- Python 3.14 (>=3.14.2), HA 2026.9.x floor `2026.9.0`; `import probatio`, never `import voluptuous` (core provides probatio; do not add it to requirements).
- Use `entry.runtime_data`, not `hass.data[DOMAIN]`. Services registered in `async_setup`, not `async_setup_entry` (hassfest enforces).
- Config Flow only; no YAML configuration, no `async_setup_platform`. `translations/en.json` and `translations/de.json`, never `strings.json`.
- Do not use `device_id` targets in shipped examples or defaults (device ids differ per instance).
- Never execute a received action sequence without the local opt-in (approval) and schema validation.
- Ruff `select = ["ALL"]`, line length 120, `target-version = "py314"`; `uv` for everything; pytest via PHACC; do not add `pytest`, `pytest-asyncio`, `homeassistant` or `voluptuous` to dev deps.
- Pin GitHub Actions by commit SHA; `permissions: {}` at workflow level; `persist-credentials: false` on checkout.
- Code, commits and comments in English; user-facing chat in German. Work goes through GSD commands; no direct edits outside the workflow.
- Only edit via GSD workflow (`/gsd-execute-phase` etc.); research output itself is the only file written here.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Re-trigger request and acks | MQTT broker (non-retained messages) | HA instance (`Manager` logic) | The only shared medium is the broker; each instance executes locally and acks |
| Heartbeat and roster | MQTT broker (non-retained) | HA instance (in-memory roster, sensor entity) | HA owns the connection, no Last Will possible (Phase 3 D-19); presence is derived from timeouts |
| Duplicate instance id detection | HA instance | MQTT broker | Each instance compares its own session id with what it hears on its own id |
| Mode (run/observe/disabled) | HA instance (Store) | Entity registry (select entity) | Local by decision; never in the shared document |
| Companion devices and mode/roster/resync entities | HA device and entity registry | HA instance (entry-owned platforms) | The integration page reads the registries by config entry; discovery devices belong to the MQTT entry |
| Adoption and transfer marker | MQTT broker (retained document) | HA instance (follower pin rule, owner publish) | Ownership is expressed only in the retained config document |
| Export and import | HA instance (service response, file in config dir) | Config entry subentries | Import creates subentries, the reconcile then publishes as for any new device |
| Diagnostics | HA instance (diagnostics platform) | — | Built from an allow-list of manager state |
| Docs | Repo (Markdown) | — | Decision D-18 |
| Release and CI | GitHub Actions | Repo tests | Tag triggers a workflow that reuses the CI jobs |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Home Assistant core | 2026.9.4 in the venv [VERIFIED: `uv run python -c "import homeassistant.const as c; print(c.__version__)"` printed `2026.9.4`] | Platforms (`sensor`, `select`, `button`), services, device and entity registry, issue registry and Repairs fix flows, diagnostics platform | The whole phase is HA core API; floor stays `2026.9.0` |
| HA `mqtt` integration (built in) | bundled | Publish and subscribe through the existing `MqttGateway` | Project constraint; no second connection |
| `homeassistant.helpers.service.async_register_admin_service` | core | Admin-only services with `supports_response` | Signature read this session: `(hass, domain, service, service_func, schema=..., supports_response=SupportsResponse.NONE, *, description_placeholders=None)` [VERIFIED: helpers/service.py:988-1003] |
| `homeassistant.components.diagnostics.async_redact_data` | core | Defense-in-depth redaction of keys in the diagnostics dict | The MQTT integration itself uses it the same way [VERIFIED: components/mqtt/diagnostics.py:1-60] |
| `gh` CLI and `jq` on `ubuntu-latest` | gh 2.101.0, jq 1.7 [CITED: github.com/actions/runner-images Ubuntu2404-Readme.md] | Create the release, read `manifest.json` | Preinstalled, so the release workflow needs no third-party action |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-homeassistant-custom-component | 0.13.367 [VERIFIED: pyproject.toml dev group] | `hass`, `mqtt_mock`, `MockConfigEntry.mock_state`, `async_fire_time_changed` | All three tiers |
| ruff | 0.16.9 [VERIFIED: pyproject.toml dev group] | Lint and format | Lint job |
| Mosquitto | 2.1.2 locally [VERIFIED: `mosquitto -h` output], not preinstalled on runners [CITED: runner-images readme has no mosquitto entry] | Real-broker tier | Broker job only (`apt-get install -y mosquitto`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Companion devices for D-13 | Link the MQTT discovery device to our entry | Impossible in 2026.9: a device has one `config_entry_id` (see Pattern 3) |
| `gh release create` | `softprops/action-gh-release` | Adds a third-party action to pin and audit; `gh` is already on the runner |
| Local reusable workflow for the release gate | Duplicate the three jobs in `release.yml` | Duplication drifts; the reusable workflow needs one test change (local `./` refs have no SHA) |
| Allow-list diagnostics | Dump manager state then `async_redact_data` | Redaction by key name leaks anything not named; actions are nested arbitrary YAML |

**Installation:** none. `uv sync --locked` stays as is.

**Version verification:** no package is added. HA, PHACC and ruff versions are the ones pinned in `pyproject.toml` and `uv.lock`.

## Package Legitimacy Audit

No external packages are installed or added by this phase, so the legitimacy gate has nothing to check.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none added) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

The release workflow deliberately avoids a new third-party action. If the planner adds one anyway it must be pinned by 40-character SHA (enforced by `tests/test_repo_structure.py`).

## Architecture Patterns

### System Architecture Diagram

```
                       user / automation
                              |
              admin services (retrigger, adopt_device, export_devices,
                 import_devices, resync)        hub entities (resync button,
                              |                  roster sensor, mode selects)
                              v                              |
                      +---------------+   reads/writes      |
                      |   Manager     |<--------------------+
                      | (lock, Store) |
                      +-------+-------+
      +-----------+-----------+-----------+------------+----------------+
      |           |           |           |            |                |
  Retrigger   Presence     Modes     Transfer      Companion       Diagnostics
  coordinator  (heartbeat,  (Store,   (marker in    devices         (allow-list)
  (request/    roster,      gate in   document,     (device reg.,
   ack, dedupe, duplicate-  _on_msg)  pin rule)     per subentry)
   rate limit)  id detect)
      |           |                       |
      v           v                       v
   MqttGateway (publish / subscribe; the fake broker replaces it in tests)
      |
      v
   MQTT broker
      topics (new in Phase 4, all non-retained):
        <base>/v1/devices/<device uuid>/retrigger     request   (any instance writes, all read)
        <base>/v1/instances/<requester id>/acks       replies   (any writes, requester reads)
        <base>/v1/instances/<instance id>/heartbeat   presence  (that instance writes, all read)
      retained, existing: availability, config (+ optional transferred_from list), state, discovery

Retrigger flow:  service -> caller-side rate limit -> record request id + expected peers (roster)
                 -> publish request (QoS 1, retain False) -> every instance (incl. caller via echo):
                 reject retained / stale / duplicate / over-limit -> resolve device + mode + approval
                 -> enqueue like a test button -> publish ack -> caller collects until all expected
                 answered or 5 s -> service response
```

### Recommended Project Structure
```
custom_components/mqtt_actions/
├── __init__.py          # CONFIG_SCHEMA, async_setup (services), platforms forward/unload
├── services.py          # thin admin service handlers + schemas; resolves the loaded Manager
├── services.yaml        # hassfest requires it as soon as services are registered
├── presence.py          # heartbeat publisher/tracker, roster, duplicate-id detection (pure logic + timers)
├── retrigger.py         # request/ack coordinator, dedupe cache, per-device rate limits
├── transfer.py          # adoption + local discard helpers (or inside manager.py if small)
├── portability.py       # export/import (pure: build, validate, re-id)
├── modes.py             # mode constants and effective-mode resolution (pure)
├── entities.py          # shared base entity + companion device_info helper
├── sensor.py select.py button.py   # hub roster, mode selects, resync button
├── diagnostics.py       # async_get_config_entry_diagnostics
├── repairs.py           # dispatch by issue id: approval flow + duplicate-id flow (+ transferred flow)
docs/ operations.md diagnostics.md troubleshooting.md broker-acl.md
.github/workflows/ ci.yml (workflow_call + tier jobs) release.yml validate.yml
```
Existing module split (pure modules without HA imports: `topics.py`, `state.py`, `model.py`, `document.py`) stays the pattern: put protocol logic in pure modules or small classes that take `Manager`/`hass`, so the fake-broker tier tests them without `async_setup_entry`.

### Pattern 1: Re-trigger request and acknowledgement (OPS-01, OPS-02, D-01 to D-04)
**What:** A request on a non-retained device topic, replies on a per-requester topic.
**Proposed wire contract** (names are discretionary and new; every existing name used below is quoted from the repo):
- Request: `<base>/v1/devices/<device uuid>/retrigger`, QoS 1, `retain=False`. Payload JSON: `request_id` (uuid4 string), `requester` (instance id), `state` (the exact StateValue to run), `sent_at` (UTC epoch seconds).
- Ack: `<base>/v1/instances/<requester id>/acks`, `retain=False`. Payload JSON: `request_id`, `device_id`, `instance_id`, `instance_name`, `status`, optional short `reason` code. Statuses: `executed`, `not_approved`, `paused`, `observing`, `disabled`, `error`; `no_answer` is synthesized by the caller, never sent.
- Topic helpers go next to the existing ones (quoted): `topics.py:51-53` `def test_topic(base: str, device_id: str) -> str:` returning `f"{base}/{TOPIC_VERSION}/devices/{device_id}/test"`, and `topics.py:56-58` `availability_topic` returning `f"{base}/{TOPIC_VERSION}/instances/{instance_id}/availability"`. `const.py:18` `TOPIC_VERSION: Final = "v1"` stays; Phase 4 adds topics under `v1`, it does not bump it (new topics are additive).
**Receiver rules (in this order):** ignore `msg.retain`; cap payload size (1 KiB) and parse strictly (UUID via `uuid.UUID`, instance id and device id via `is_valid_device_id`); drop a stale `sent_at` (see Pitfall 4); drop a `request_id` already in the bounded dedupe cache; apply the per-device 5 s limit unless the request id was sent by this instance; resolve the device with the existing `Manager._device`; check mode (`disabled` -> `disabled`, `observing` -> `observing`, log the suppression); check breaker (`paused`); check the runner gate (`runner.can_run`) and map "mirror without approved Script" to `not_approved`; validate `state` against `device.spec.accepted`; then call `runner.enqueue(..., test=True)` exactly like `Manager._on_test_message` (manager.py:1177-1184), which never touches the tracker, baseline or breaker.
**Caller:** reject a second call for the same device within 5 s with `ServiceValidationError` (translated). Record `expected = roster-online peers + self`, subscribe state is already standing (a single standing subscription on `instances/<own id>/acks` started in `Manager.async_start`), publish, `asyncio.timeout(5)` around an event that fires early when every expected instance answered, fill `no_answer` for the rest, return a plain dict (service responses must be JSON-serializable dicts).
**Executed semantics:** `executed` should mean "accepted and started", not "finished" (a script can run for minutes; failures still surface as Repairs per DEV-08). `[ASSUMED]` A2.

### Pattern 2: Heartbeat, roster and duplicate instance id (OPS-03, SYN-10, D-05 to D-07)
**Topic:** `<base>/v1/instances/<instance id>/heartbeat`, QoS 0, `retain=False`. Payload: `instance_id`, `name`, `version`, `devices` (count of owned devices), `session` (uuid4 generated once per `Manager.async_start`). Subscribe to `instances/+/heartbeat` once, next to the existing availability wildcard (sync.py:179-183 subscribes `availability_wildcard(manager.base_topic)`); add `heartbeat_wildcard` and `parse_heartbeat_topic` to `topics.py` using the existing `_parse_segment` (topics.py:86-93).
**Validation:** topic segment must equal the payload `instance_id` (reject otherwise); name through the existing printable and 64-character rule (`model._invalid_text`, model.py:181-183); cap tracked peers with the existing `MAX_TRACKED_INSTANCES` (`const.py:133` `MAX_TRACKED_INSTANCES: Final = 256`); ignore `retain=True` messages entirely (D-05).
**Roster:** `instance_id -> (name, version, devices, session, last_seen_monotonic)`; online when `now - last_seen <= 90` and the retained availability is not `offline` (a clean unload publishes `offline`, `sync.py` already tracks it in `_instances`). Use `Manager.clock` (manager.py:335 `self.clock: Callable[[], float] = time.monotonic`, replaceable in tests). Expiry has no message to trigger it, so re-evaluate on a timer: reuse the 30 s heartbeat tick (`async_track_time_interval`) and push a dispatcher signal to the sensor.
**Timers:** heartbeat tick registered with `entry.async_on_unload`; cancelled in `Manager.async_stop` (a failed setup also calls `async_stop`, `__init__.py:33`). Publish the first heartbeat at the end of `async_start`, after availability `online`.
**Duplicate id:** own id on the wire with a different `session` than the one this start generated. Own echoes arrive with the same session and are ignored. Debounce: require two such observations (see Pitfall 5). Hub-level issue id (new constant, must also be removed by `async_remove_local_state`, manager.py:256-258, which deletes only ids with a device prefix or `ISSUE_DISCOVERY_DISABLED`).
**Offline owner for adoption (D-09):** `owner_offline = roster says offline, or never heard and this instance has listened for at least 90 s`; otherwise require `force`. Right after a start the roster is empty, so "unknown" must not count as offline. `[ASSUMED]` A10.

### Pattern 3: Companion devices make D-13 true (D-13, D-15)
**Finding (HIGH, read this session):** `core` 2026.9.4 device registry entries hold one config entry. Quote, helpers/device_registry.py:379-384: `config_entry_id: str = attr.ib()` and `config_subentry_id: str | None = attr.ib(default=None)`; `config_entries` is documented as "Deprecated compatibility shim: a device now belongs to a single config entry". Identifiers are unique per config entry: "Identifiers are unique per config entry, so only collisions with other devices of the same config entry are considered." (helpers/device_registry.py, `_validate_identifiers` docstring). `add_config_entry_id` only records a pending move, it does not link a second entry (`_async_update_device` comment block starting "A device belongs to exactly one config entry and subentry"). So the CONTEXT sentence "linked to the MQTT Actions config entry ... additionally" is not possible; the discovery device stays a core MQTT device.
**What the page shows [CITED: frontend `dev` branch, src/panels/config/integrations/ha-config-integration-page.ts]:** devices are collected with `device.config_entries.includes(entry.entry_id)` (line 1008) and grouped per subentry via `config_entries_subentries[entry.entry_id]`; entities with `entity.config_entry_id && entryIds.includes(entity.config_entry_id)` (line 1295). Therefore the core MQTT entry's devices and entities are **not** listed on the MQTT Actions page. This answers the open question in D-13.
**Recommended design:**
- For every owned device and every mirror, register a **companion device** with `device_registry.async_get_or_create(config_entry_id=entry.entry_id, config_subentry_id=<subentry id for owned, None for mirrors>, identifiers={(DOMAIN, device_id)}, name=<device name>, manufacturer="MQTT Actions", model=<"Switch"|"Select"> , sw_version=<owner version if known>)`. Owned ones sit under their subentry on the page; mirrors appear as plain devices, which answers the Phase 3 UAT question "where do I see the device of HA One on HA Two?".
- The per-device mode select (D-15) attaches to the companion device via `DeviceInfo(identifiers={(DOMAIN, device_id)})` and `has_entity_name`. It does not share a registry device with the discovery device and does not need to: entity uniqueness is per (domain, platform, unique_id) [VERIFIED: helpers/entity_registry.py:1243-1251 `async_get_entity_id(self, domain: str, platform: str, unique_id: str)`], so `select` + `mqtt_actions` + `<device uuid>_mode` cannot collide with the discovery `select` of platform `mqtt`.
- Hub device (service type) holds the roster sensor, the resync button and the instance-wide mode select.
- Removing a subentry already deletes devices linked to it [VERIFIED: helpers/device_registry.py:4444-4453 `async_clear_config_subentry` calls `self.async_remove_device(device.id)` for devices with that subentry]; a mirror removal must delete its companion device explicitly (add to `Manager.async_remove_mirror`). Do not define `async_remove_config_entry_device`: without it the UI cannot delete these devices [VERIFIED: components/config/device_registry.py:251 `if not config_entry.supports_remove_device:`].
- Entities are added dynamically: platform setup iterates existing devices, later devices arrive through a dispatcher signal; pass `config_subentry_id` for owned devices [VERIFIED: helpers/entity_platform.py:139-152 `AddConfigEntryEntitiesCallback.__call__(self, new_entities, update_before_add=False, *, config_subentry_id=None)`].
- `device_id` selectors: the services' `device` selector can be filtered with `integration: mqtt_actions` once companion devices exist; the handler maps the registry device to our uuid through the `(DOMAIN, device_id)` identifier.
- Two devices with the same display name now exist (core MQTT device and companion). Differentiate with `manufacturer`/`model`; do not use `via_device_id` (it resolves across entries, helpers/device_registry.py:2159-2193, but the MQTT device may not exist yet when the companion is created).
**User confirmation needed:** this changes the D-13 wording. `[ASSUMED]` A1; see Open Question 1.

### Pattern 4: Adoption and the transfer marker (SYN-07, D-09, D-10)
**Marker encoding (recommended, no `schema_version` bump):** add an optional top-level list `transferred_from` (previous owner instance ids, newest last, at most 8) as bookkeeping like `owner` and `rev`, **not** content. Content hash is unchanged, so approvals and mirror updates are unaffected. Existing readers ignore unknown keys: `document.py` docstring "unknown extra keys are ignored and never hashed" [VERIFIED: document.py:322-323]. A bump would be worse: `parse_document` raises `SchemaTooNewError` for a higher version before reading anything (document.py:336-337 `if version > SCHEMA_VERSION: raise SchemaTooNewError(version)`, `const.py:20` `SCHEMA_VERSION: Final = 1`), so every older instance would stop applying all updates, not just adopted ones. An older follower that ignores the marker degrades safely: it keeps the first pin and raises the existing `owner_conflict` issue (sync.py:398-400).
**Follower pin rule (sync.py `_async_ingest_locked`):** today `info.owner != parsed.owner` always conflicts. New: re-pin only when `parsed.owner != info.owner` and `info.owner in parsed.transferred_from`. A chain A to B to C is handled by the list. Recommended extra condition: honor it only when the pinned owner is not online per the roster; otherwise raise `owner_conflict` (a forger could otherwise re-pin every follower to itself; approval still gates execution, but the real owner's later edits would be ignored). `[ASSUMED]` A6, Open Question 3.
**Adopter steps (under `Manager.lock`, keep the order):**
1. Preconditions: mirror exists, not in `devices`, owner offline per roster or `force`.
2. Build subentry data from the mirror content: the content keys equal the subentry data keys (document.py docstring: "The keys of the content are the keys of the subentry data"), minus `kind` and `name`, plus `device_id`; title is `name`, `unique_id` is the device id (matches `conftest.make_switch_subentry`).
3. Keep the baseline (`_stored_last_acted`) so nothing runs; drop the approval and the mirror without `async_remove_mirror`'s registry cleanup semantics (promote, do not delete: the discovery entities stay live).
4. Seed `_revs[device_id]` with the mirror's rev and a hash that cannot match, so `async_publish_config` increments the rev; record the old owner in a persisted transfer map so **every** later republish (start, reconnect, heal) keeps carrying the marker (an offline follower must still see it later). Persist the map in the Store (new additive key, also add it to `_data_to_save` and `_async_load_store`, see Pitfall 6).
5. Release the lock, then `hass.config_entries.async_add_subentry(entry, ConfigSubentry(...))` [VERIFIED: config_entries.py:2690 `def async_add_subentry(self, entry: ConfigEntry, subentry: ConfigSubentry) -> bool:`; `ConfigSubentry` fields `data`, `subentry_id`, `subentry_type`, `title`, `unique_id` at config_entries.py:372-379]. The update listener reconciles and `_async_add_device(startup=False)` publishes the document and a discovery whose availability points at the adopter's availability topic, which makes the entities available again.
**Returning old owner (trap):** the old owner starts, subscribes, then publishes its own documents; the replayed retained document is delivered asynchronously, so its start-up publish can overwrite the adopter's document, and its heal logic treats the adopter's document as a foreign claim. Do not step down automatically on a marker (a forged marker would then make any owner delete its device, breaking D-17). Recommended: owner side recognizes a valid claimant document whose `transferred_from` contains its own id, stops healing it, and raises a fixable Repairs issue `transferred_<device id>` whose flow releases the device locally (same primitive as Pattern 7). Document the limitation in README and `docs/operations.md`. `[ASSUMED]` A15.

### Pattern 5: Modes (SYN-09, D-14, D-15, D-16)
- **Naming collision:** the codebase already has `CONF_RUN_MODE = "run_mode"` with `RUN_MODE_SERIAL = "serial"` and `RUN_MODE_RESTART = "restart"` (const.py:35-37). The new run/observe/disabled concept is a different thing. Use distinct names (for example `device_mode`, `MODE_RUN`, `MODE_OBSERVE`, `MODE_DISABLED`) so D-16 ("bind `run_mode`") is not confused with D-14.
- **Gate** goes into `Manager._on_message` between the tracker and the breaker. The current path (manager.py:1049-1076) is: `decision = device.tracker.handle(...)`, `if not decision.act: return`, trigger lookup and `can_run`, breaker `tripped`/`record`, then `self.runner.enqueue(...)`. Insert after the `can_run` check and before the breaker: `observe` logs the suppressed run (quote device and trigger names with the existing capped-and-quoted helper style, sync.py:91-93 `_shown`, because mirror names come from the broker) and returns without `breaker.record()`; `disabled` returns **before** `tracker.handle` so no baseline moves.
- **Leaving `disabled`:** the baseline is stale. Clear it and re-subscribe the state topic so the retained value replays as baseline-only. Core MQTT re-subscribes on every new subscription "to ensure retained messages are replayed" [CITED: components/mqtt/client.py:1074-1075 comment], and each new `Subscription` gets its own retained replay (client.py:1349-1354 `_retained_topics`). The fake broker replays on every subscribe too (fake_broker.py:112-115). Verify with a real Mosquitto test. `[ASSUMED]` that clearing plus re-subscribe is the wanted semantics; alternative is keeping the baseline while disabled, which contradicts D-14 "no baseline".
- **Effective mode** = the most restrictive of instance mode and device mode (`disabled` > `observe` > `run`). `[ASSUMED]` A9. Test button and re-trigger follow the same gate; the existing test-topic path should be gated too (disabled and observe must not run test presses either, otherwise the mode is bypassable).
- **Storage:** a new additive Store key (for example `modes`), written through `_data_to_save`; the select entity reads from and writes through the manager, so there is no `RestoreEntity`. Selecting persists with the delayed save; a mode change must not republish anything.
- **Entity:** `SelectEntity` with `EntityCategory.CONFIG`, `options = ["run", "observe", "disabled"]`, translation keys for the option labels in both languages (`test_translations.py` enforces en/de parity).
- **D-16:** `actions_hash` today is (document.py:111-117):
```python
def actions_hash(spec: DeviceSpec) -> str:
    """Return the hash an approval is bound to: the StateValue-to-actions mapping plus the startup flag (A5)."""
    pairs = sorted(
        ([trigger.value.lower(), trigger.actions] for trigger in spec.triggers.values()),
        key=lambda pair: pair[0],
    )
    return _sha256(canonical_json({"kind": spec.kind, CONF_RUN_ON_STARTUP: spec.run_on_startup, "triggers": pairs}))
```
  Add `CONF_RUN_MODE`, `CONF_BREAKER_MAX_RUNS` and `CONF_BREAKER_WINDOW` to the dict. The hash is computed locally from received content (never trusted from the wire, document.py:322-323), so there is **no cross-version wire problem**. Consequences to plan: (1) `tests/test_document.py:199-210` `test_actions_hash_binds_mapping_and_startup_flag` currently asserts the three values do **not** change the hash (`== base_hash` at lines 204-205) and must flip; (2) the module docstring (document.py:18-20) and README sentence must change; (3) the approval dialog must show the three values (it already shows `startup`, repairs.py:73) and both translation files and `test_translations.py` expectations follow; (4) migration: stored approvals are hash strings, so after the upgrade none matches, `_refresh_mirror_script` unloads every approved mirror and `_sync_approval_issues` re-raises an approval request for each at start. No migration code is needed; the Repairs requests are the notice. Add a release-note line and a README sentence. No release exists yet (`git tag` is empty this session), so the practical blast radius is the developer's own test instances.

### Pattern 6: Services (OPS-01, SYN-07, SYN-08, DSC-04)
- Register in `async_setup`, which does not exist yet: `__init__.py:1-65` has only `async_setup_entry`, `async_unload_entry`, `async_remove_entry`. hassfest then requires `CONFIG_SCHEMA` in `__init__.py` as soon as `async_setup` exists [VERIFIED: hassfest `script/hassfest/config_schema.py` fetched at tag 2026.9.4 returns early only when it finds an assignment of `CONFIG_SCHEMA`, `PLATFORM_SCHEMA` or `PLATFORM_SCHEMA_BASE`]; use `cv.config_entry_only_config_schema(DOMAIN)`.
- hassfest requires `services.yaml` once services are registered [VERIFIED: hassfest services.py, error "Registers services but has no services.yaml"], matching regex includes `async_register_admin_service`. For custom integrations name and description may live in `services.yaml` or `translations/en.json`; icons are required for core only [VERIFIED: services.py `if integration.core and service_name not in service_icons`]. Put names, descriptions and field names in both translation files (parity test).
- Use `async_register_admin_service` (admin only) for `export_devices`, `import_devices`, `adopt_device`, `retrigger`, `resync`. Export returns actions, import and adopt change ownership and execution, retrigger runs actions on other machines; a non-admin user must not call them. `[ASSUMED]` A8.
- `SupportsResponse.OPTIONAL` for `retrigger`, `export_devices`, `import_devices` (import returns per-item results), `adopt_device`, `resync` may return nothing. [VERIFIED: core.py:2539-2548 `class SupportsResponse`: `NONE`, `OPTIONAL`, `ONLY`].
- Validation errors the caller should see use `ServiceValidationError` with a translation key [VERIFIED: exceptions.py:110 `class ServiceValidationError(HomeAssistantError)`].
- Device parameter: a `device` selector (single, filtered to `integration: mqtt_actions`), mapped through the `(DOMAIN, device_id)` identifier. Field name: `device_id` is the HA convention, but `tests/test_repo_structure.py:test_docs_examples_use_no_device_id_targets` forbids the string `device_id` in fenced examples of README.md and docs/broker-acl.md; new docs pages are not covered. Either choose another field name (for example `device`) or extend/keep the test deliberately. Decide once.
- Handlers resolve the loaded manager like `repairs.py:24-30` `_loaded_manager` does (`entry.state is ConfigEntryState.LOADED`); move that helper to a shared place.

### Pattern 7: Local discard and the duplicate-id fix flow (SYN-10, D-07, D-08)
Teardown paths that publish destructively today: `_async_remove_device` clears discovery, config and state (manager.py:930-963) and `_async_orphan_cleanup` clears `published - current` (manager.py:965-977). A fix flow that just removes subentries would tombstone the **original's** topics (same device ids) for everyone. Required order, all under `Manager.lock`:
1. For each owned device: pop from `self.devices` first (the existing pop-first idea), unsubscribe state and test, `runner.async_unload`, `sync.forget`.
2. Remove the id from `_published`, `_revs`, `_tripped`, the transfer map, and drop the approval-free baseline decision (keep `last_acted`, it is harmless).
3. `await self._store.async_save(self._data_to_save())` immediately (not `_schedule_save`), so a crash cannot leave a published id behind.
4. Remove the subentries (`async_remove_subentry`, config_entries.py:2700). The update listener reconciles, finds nothing in `devices` to remove, publishes nothing. Companion devices of these subentries are removed by core (device_registry.py:4444-4453).
5. Update entry data with a new `str(uuid.uuid4())` instance id (config_flow.py:111 generates it this way) and schedule a reload: `hass.config_entries.async_schedule_reload(entry_id)` [VERIFIED: config_entries.py:2464]. `Manager` caches `self._instance_id` at construction (manager.py:312), so a new id is only effective after the reload.
6. After the reload the retained documents of the original replay; `parsed.owner != manager.instance_id` now holds, so the existing ingest creates mirrors. Before the new id the copy would have ignored them: sync.py:384-386 `if parsed.owner == manager.instance_id: ... return`.
`repairs.py:90-96` `async_create_fix_flow` ignores `issue_id` and always returns `ApprovalRepairFlow()`; it must dispatch on the issue id prefix once there are three flows. Fold in A7 here: `repairs.py:11` is the last `import voluptuous as vol` in the integration (all other modules use `probatio`), contrary to project rules.

### Pattern 8: Export and import (SYN-08, D-11)
- Export format: `{"format": "mqtt_actions_export", "export_version": 1, "devices": [ {content...} ]}` where each item is the existing shared content (`build_content`, document.py:81-103: `kind`, `name`, `run_on_startup`, `run_mode`, `breaker_max_runs`, `breaker_window` plus actions or options). No device id, no owner, no rev in the file (import always re-ids, D-11).
- Import: for each item build a throw-away document (`build_document` semantics: new `uuid4` device id, `owner` = this instance, `rev` 1) and run it through `parse_document` (document.py:316-360): that reuses the size cap, depth cap, field validation and hash computation; then `validate_spec_structure` and the deep `async_validate_actions`; then create subentries. Caps: items per import (use `MAX_MIRRORS`-like constant, 100) and total bytes (the per-document cap `MAX_DOCUMENT_BYTES: Final = 256 * 1024` is per item).
- Imported actions are **owned**, therefore unrestricted and published to peers. Reject items with statically denied services (`analyze_spec(...).denied`) so a hostile file cannot smuggle what mirrors would block. `[ASSUMED]` A11.
- **Files:** the default allowlist is only `www` and the media dirs: core_config.py:439 `hac.allowlist_external_dirs = {hass.config.path("www"), *hac.media_dirs.values()}`; `is_allowed_path` does blocking I/O (core_config.py:652-656). Writing "under /config" via the allowlist would therefore be `/config/www`, which is served unauthenticated at `/local/`. Recommended: a dedicated directory `<config>/mqtt_actions/` chosen by the integration, user passes only a file name matching `[A-Za-z0-9._-]+\.json`, reject separators and dot-dot, create the file with mode 0600 in the executor (exports contain actions and possibly secrets). Import reads from the same directory by file name only. `[ASSUMED]` A7.

### Pattern 9: Diagnostics (OPS-04, D-17)
`diagnostics.py` with `async_get_config_entry_diagnostics(hass, entry)` (same shape as the MQTT integration's, components/mqtt/diagnostics.py:24-28). Build the dict from an allow-list: `base_topic`, `instance_name`, shortened instance ids (first 8 characters), roster rows, per device `uuid`, `kind`, `owner` (shortened), `mode`, `approval` (`owned|approved|pending|blocked`), `breaker` (`ok|tripped`), `rev`, `hash`. Never read action content, MQTT entry data, hostnames or credentials. Still pass the result through `async_redact_data` for a short key list as a safety net. hassfest dependency check accepts the import because `diagnostics.py` exists in the integration [VERIFIED: hassfest `dependencies.py` exempts `(integration.path / f"{ref}.py").is_file()`]. Test with sentinel strings placed in actions, entity ids, template text and instance names and assert none appears in the serialized output.

### Pattern 10: Release and CI (OPS-05, OPS-06, D-19, D-20)
**Tier selection:** keep the existing marker `markers = ["broker: needs a real mosquitto broker on PATH (skipped when it is not installed)"]` (pyproject.toml) and add `multi_instance` (register it, and consider `--strict-markers`). `tests/broker/*` already use `pytestmark = pytest.mark.broker`. `make_instance` is used by `tests/test_multi_instance.py` and `tests/test_fake_broker.py` (grep this session) plus the fixture in `tests/conftest.py`; give those two modules `pytestmark = pytest.mark.multi_instance`. Commands: unit `uv run pytest -q -m "not broker and not multi_instance"`, broker `uv run pytest -q -m broker`, multi-instance `uv run pytest -q -m multi_instance`. Add an env switch (for example `MQTT_ACTIONS_REQUIRE_BROKER=1`) in `tests/broker/conftest.py` that turns the two `pytest.skip("... not installed")` calls (conftest.py lines 45 and 86) into failures; otherwise a broken `apt-get` leaves the broker job green with 11 skipped tests.
**ci.yml:** jobs `lint` (ruff check and format --check), `unit`, `broker` (installs mosquitto, only here), `multi-instance`; add `workflow_call` to the triggers so the release can reuse it. Keep `permissions: {}` at workflow level and `contents: read` per job, SHA-pinned `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1` and `astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0` (quoted from ci.yml). `tests/test_repo_structure.py:test_ci_runs_locked_sync_lint_format_and_pytest` checks that some step starts with each of `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest` and that some command mentions `mosquitto`; split jobs still satisfy it because `_steps` flattens all jobs.
**release.yml:** `on: push: tags: ["v*.*.*"]` (the repo test requires a `push` trigger without branch filters, a `tags` filter is fine), workflow `permissions: {}`. Jobs: `check-version` (checkout with `persist-credentials: false`, compare `${GITHUB_REF_NAME#v}` with `jq -r .version custom_components/mqtt_actions/manifest.json`, fail on mismatch), `ci` (`uses: ./.github/workflows/ci.yml` with `permissions: contents: read`), `release` (`needs: [check-version, ci]`, `permissions: contents: write`, `gh release create "$GITHUB_REF_NAME" --verify-tag --generate-notes` with `GH_TOKEN: ${{ github.token }}`). HACS only needs a release or the default branch and the manifest `version`; it shows the five latest releases and the tag format is unspecified in the docs [CITED: hacs.xyz/docs/publish/integration/]. Tag `v0.1.0` with manifest `0.1.0` is the natural first pair.
**Test changes:** add `release.yml` to `WORKFLOW_FILES` (tests/test_repo_structure.py line 30 `WORKFLOW_FILES = ("validate.yml", "ci.yml")`); the SHA rule (`SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")`, line 28) also checks job-level `uses` through `_uses_refs`, so a local `./.github/workflows/ci.yml` reference fails it; exempt refs that start with `./`. Add tests for the version check and for "release needs ci".
**validate.yml** (hassfest and HACS) runs on tag pushes as a separate workflow and does not gate the release; either call it from `release.yml` too or accept that. Optional: add `tags-ignore: ["v*.*.*"]` to the `push` trigger of `ci.yml` to avoid a duplicate run (allowed by the test, which only forbids `branches` and `branches-ignore`).

### Pattern 11: Hub entities (D-06, D-12)
- `sensor` roster: state = number of online instances **including this one** `[ASSUMED]` A10 (CONTEXT says "online instances" without saying). `EntityCategory.DIAGNOSTIC`. Attribute `instances` as a list of dicts: `name`, `id` (shortened or full? D-17 shortens only in diagnostics), `version`, `last_seen` (ISO timestamp), `online`. State attributes above 16384 bytes are dropped by the recorder [VERIFIED: components/recorder/db_schema.py:90 `MAX_STATE_ATTRS_BYTES = 16384`]; mark the attribute unrecorded with `_unrecorded_attributes = frozenset({"instances"})` [VERIFIED: helpers/entity.py:554 `_unrecorded_attributes: frozenset[str] = frozenset()`] and cap the list at the tracked-peer cap.
- `button` resync on the hub device, `EntityCategory.CONFIG`, calls the same manager method as the service. Both run the existing `_async_republish` (manager.py:479-492): "documents, then discovery, then `online`". Guard with a short cooldown or rely on the manager lock; a held button must not queue unbounded work.
- Platforms must be forwarded at the end of `async_setup_entry` and unloaded in `async_unload_entry` (today `__init__.py:46-50` does not forward any platform).

### Anti-Patterns to Avoid
- **Reusing `_async_remove_device`, subentry removal or `_async_orphan_cleanup` for the "discard locally" flows.** They clear broker topics (see Pattern 7).
- **A retained heartbeat or retained re-trigger.** Explicitly rejected (D-05, REQUIREMENTS out-of-scope table).
- **A schema bump for the transfer marker.** It would silence every older follower (Pattern 4).
- **Putting service or entity logic only in `__init__.py` or entity classes.** The fake-broker tier never runs them.
- **Dump-then-redact diagnostics.** Allow-list instead.
- **Trusting any new broker payload.** Heartbeat, request, ack and import all need the same strict-parse, bounded-size, typed-reject treatment as `parse_document`.
- **Using `device_id` as a documented service example key without deciding on the existing docs test.**

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Admin-only services | A manual `call.context.user_id` check | `async_register_admin_service` | Core does the admin check [VERIFIED: helpers/service.py:988-1016] |
| Service response plumbing | Events or custom websocket for acks to the caller | `SupportsResponse.OPTIONAL` and a returned dict | D-03 says no event-bus variant |
| Periodic heartbeat and expiry | A thread or a bare `asyncio` loop | `async_track_time_interval` tied to `entry.async_on_unload` | Lifecycle and test control with `async_fire_time_changed` |
| Document validation of imports | A second validator | `parse_document` + `validate_spec_structure` + `async_validate_actions` | One strict path from untrusted bytes to a spec (existing rule) |
| JSON canonicalization and hashing | Anything new | `canonical_json`, `content_hash`, `actions_hash` | Wire-contract algorithm already defined |
| Device registry linking | Manual registry writes for each entity | Entity `device_info` plus `async_get_or_create` for the companion | Entity platform creates and links the device |
| Release creation | A custom API script or a new action | `gh release create --generate-notes` | Preinstalled; no new supply-chain surface |
| Test broker | A new mock | Existing `FakeBroker`/`InstanceFactory` and `start_acl_broker` | Retain semantics already pinned against Mosquitto |
| Local fix flows | A custom config-flow step | `RepairsFlow` as in `repairs.py` | Existing machinery (D-07) |

**Key insight:** every new protocol element here is a tiny state machine over a broker that offers no ordering, no delivery guarantee beyond QoS and no authenticated sender. The existing code's discipline (strict parsing, typed rejects, bounded caches, lock-serialized state changes, never trusting the wire) is the thing to extend, not to replace.

## Common Pitfalls

### Pitfall 1: Teardown helpers destroy the original's topics
**What goes wrong:** Discarding a copy's devices through the normal delete path tombstones config, discovery and state of devices the original still owns.
**Why it happens:** Cloned instances share device ids and topics; `_async_remove_device` and `_async_orphan_cleanup` both publish empty retained payloads.
**How to avoid:** Pattern 7 order; assert in a multi-instance test that after the fix flow the original's retained config, discovery and state are still on the fake broker byte for byte.
**Warning signs:** Any publish with an empty payload during the fix flow.

### Pitfall 2: The harness never runs `async_setup_entry`
**What goes wrong:** Services registered in `async_setup` and platforms forwarded in `async_setup_entry` are untested in the fake-broker tier, and tests of them pass vacuously.
**Why it happens:** `InstanceFactory.__call__` constructs `Manager(hass, entry, gateway=gateway, store_key=store_key)` directly (fake_broker.py:237-239) and `Instance.start` does the same (fake_broker.py:182-185).
**How to avoid:** Behavior in `Manager` and collaborators; one unit-tier test per service/platform using the real entry setup with `mqtt_mock` (as `tests/test_hub_removal.py:52` does with `hass.config_entries.async_setup`). Where a service must be called across instances, let the factory call the same `async_setup_services(hass)` and `entry.mock_state(hass, ConfigEntryState.LOADED)` (PHACC `MockConfigEntry.mock_state` exists, common.py:1163) so `_loaded_manager`-style lookup works.

### Pitfall 3: Self-echo and rate limits
**What goes wrong:** The caller receives its own non-retained request through its standing subscription, so a caller-side limiter and a receiver-side limiter both count it and the caller's own device is rejected.
**How to avoid:** Mark own request ids as sent before publishing and let the receiver skip the rate limit (but not the dedupe) for them. Receiver-side limiting still protects against a flooding peer.

### Pitfall 4: Queued QoS 1 delivers old requests after a short outage
**What goes wrong:** A re-trigger sent while an instance's connection was down is delivered on reconnect and runs actions late.
**Why it happens:** Core's client does not always use a clean session (`clean_session` is chosen at client construction, client.py:357-391), and a persistent session queues QoS 1 messages.
**How to avoid:** `sent_at` in the request, reject requests older than a freshness window (60 s). `[ASSUMED]` A4 (value and clock-skew tolerance).

### Pitfall 5: False duplicate-id positives
**What goes wrong:** A restart or a delayed delivery produces a heartbeat of the same instance with an older session id and raises the issue.
**How to avoid:** Require two observations of a foreign session for the own id before raising; delete the issue when none was seen for 90 s. Publish the heartbeat QoS 0 so nothing queues. `[ASSUMED]` A12.

### Pitfall 6: New Store keys are silently dropped
**What goes wrong:** `Manager._data_to_save` (manager.py:540-556) returns a fixed dict, so any new persisted key (modes, transfers) that is not added there disappears at the next save, and `_async_load_store` (manager.py:524-538) must parse it defensively like the others.
**How to avoid:** Add constants next to `STORE_*` (const.py:109-121), parse with the same drop-malformed style, no `STORE_VERSION` bump (the established additive pattern, STATE.md Phase 02 decision), and cover the round trip in a test. Also include new keys' cleanup in `async_remove_local_state`/`async_remove_all_devices` paths where relevant, and new issue ids (hub-level duplicate-id issue, per-device `transferred_`) in `const.ISSUE_DEVICE_PREFIXES` (const.py:174-185) or the hub removal cleanup (manager.py:256-258).

### Pitfall 7: Roster expiry has no message to trigger it
**What goes wrong:** A crashed peer stays "online" in the sensor because nothing re-evaluates after the last heartbeat.
**How to avoid:** Evaluate on every heartbeat tick and on a dedicated timer at the next expiry; push state through the dispatcher. Test with `Manager.clock` replaced and `async_fire_time_changed`.

### Pitfall 8: Mirror names reach logs and registries unescaped
**What goes wrong:** Observe-mode log lines, companion device names, roster attributes and ack texts carry broker-supplied strings.
**How to avoid:** Keep the existing rules: logs use the capped, quoted form (sync.py:91-93 `_shown`), Repairs placeholders use `escape_markdown`, names are bounded by the `_invalid_label`/`_invalid_text` checks that `parse_document` and the heartbeat parser apply.

### Pitfall 9: Frontend facts come from the `dev` branch
**What goes wrong:** The integration-page filter logic could differ in the frontend version bundled with 2026.9.x.
**How to avoid:** Treat Pattern 3 as designed on the registry facts (verified in core) and confirm in the real frontend during UAT with the existing two-container setup under `~/ha-test/` (directories `a`, `b`, `mosquitto` exist on this machine).

### Pitfall 10: `ci.yml` and the release both run CI on a tag
**What goes wrong:** A tag push triggers `ci.yml` through `push` and again through the release's reusable call.
**How to avoid:** Optional `tags-ignore` on `ci.yml`'s push trigger; the test only forbids `branches` and `branches-ignore`.

## Code Examples

Existing names below are quoted from the files read this session; names marked "proposed" are new design.

### Services in `async_setup` (proposed shape)
```python
# Source: HA core helpers/service.py:988-1003 (signature), script/hassfest/config_schema.py (CONFIG_SCHEMA rule)
from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration services once; handlers look up the loaded manager at call time."""
    async_register_admin_service(
        hass, DOMAIN, "retrigger", _async_retrigger, SERVICE_RETRIGGER_SCHEMA, SupportsResponse.OPTIONAL
    )
    return True
```

### Heartbeat topic helpers (proposed, beside `availability_topic`)
```python
# Source: topics.py:56-58 and 76-78, 101-103 (existing patterns, quoted in Pattern 2)
def heartbeat_topic(base: str, instance_id: str) -> str:
    """Return the non-retained heartbeat topic of an instance."""
    return f"{base}/{TOPIC_VERSION}/instances/{instance_id}/heartbeat"

def heartbeat_wildcard(base: str) -> str:
    """Return the subscription that matches the heartbeat topic of every instance."""
    return f"{base}/{TOPIC_VERSION}/instances/+/heartbeat"

def parse_heartbeat_topic(base: str, topic: str) -> str | None:
    """Return the instance id of a heartbeat topic, or None for any other topic."""
    return _parse_segment(topic, f"{base}/{TOPIC_VERSION}/instances/", "/heartbeat")
```

### Local discard order (proposed)
```python
async def async_discard_owned_locally(self) -> list[str]:
    """Forget every owned device without touching the broker (D-08)."""
    async with self._lock:
        ids = list(self.devices)
        for device_id in ids:
            device = self.devices.pop(device_id)          # pop first, as in _async_remove_device
            if device.unsubscribe is not None:
                device.unsubscribe()
            if device.unsubscribe_test is not None:
                device.unsubscribe_test()
            await self.runner.async_unload(device_id, remove_issue=True)
            self._delete_device_issues(device_id)
            self.sync.forget(device_id)
            self._published.discard(device_id)             # otherwise _async_orphan_cleanup tombstones the original
            self._revs.pop(device_id, None)
            self._tripped.pop(device_id, None)
        await self._store.async_save(self._data_to_save())  # not _schedule_save
    return ids
```

### Release workflow skeleton (proposed)
```yaml
name: Release
on:
  push:
    tags: ["v*.*.*"]
permissions: {}
jobs:
  check-version:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - run: |
          manifest="$(jq -r .version custom_components/mqtt_actions/manifest.json)"
          test "${GITHUB_REF_NAME#v}" = "$manifest"
  ci:
    permissions:
      contents: read
    uses: ./.github/workflows/ci.yml
  release:
    needs: [check-version, ci]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - run: gh release create "$GITHUB_REF_NAME" --repo "$GITHUB_REPOSITORY" --verify-tag --generate-notes
        env:
          GH_TOKEN: ${{ github.token }}
```
`gh release create --repo` is used because the job does no checkout. The first `uses:` line is quoted from `.github/workflows/ci.yml`.

### Mode gate (proposed placement in `Manager._on_message`)
```python
# after: trigger = device.spec.triggers.get(trigger_key(decision.value)); the can_run check
mode = self.effective_mode(device_id)
if mode == MODE_OBSERVE:
    LOGGER.info("Observe mode: actions of %s for device %s were not run", _shown(trigger.label), _shown(device.name))
    return
# before the tracker for MODE_DISABLED:  if self.effective_mode(device_id) == MODE_DISABLED: return
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| A device linked to several config entries | One config entry and optional subentry per device; `config_entries` is a deprecated shim | HA 2026.9 registry (verified in 2026.9.4) | D-13 "additionally linked" is impossible; use companion devices |
| `hass.data[DOMAIN]` for state | `entry.runtime_data` | already used here | Services must resolve the manager through the entry |
| Services in `async_setup_entry` | Services in `async_setup`, `CONFIG_SCHEMA` required | hassfest rule | New `async_setup` forces `CONFIG_SCHEMA` |
| `voluptuous` | `probatio` | HA 2026.9 | `repairs.py:11` is the last remaining voluptuous import here |

**Deprecated/outdated:** `DeviceEntry.config_entries`, `add_config_entry_id`, `remove_config_entry_id`, `via_device` (parameter removal announced for 2027.8 in the registry source, `_DEPRECATED_DEVICE_INFO_PARAMETERS`). Do not use them.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Companion devices (a second device per logical device, under our entry) are an acceptable way to meet D-13; D-13's literal "linked to the MQTT Actions entry" is dropped | Pattern 3 | If the user insists on the discovery device on the page, the only alternative is moving the whole design to native entities, which conflicts with the Discovery contract |
| A2 | Ack `executed` means accepted and started, not finished | Pattern 1 | Users expecting completion status would see "executed" for runs that later fail (still shown in Repairs) |
| A3 | The caller resolves the trigger from its own last acted state and always sends the concrete StateValue | Pattern 1 | If receivers' baselines differ, running the caller's state might surprise; the alternative is each receiver using its own |
| A4 | Requests older than 60 s (by `sent_at`) are dropped | Pitfall 4 | Too tight breaks setups with clock skew, too loose runs stale re-triggers |
| A5 | No `SCHEMA_VERSION` bump; `transferred_from` is an additive bookkeeping list | Pattern 4 | A later reader that must distinguish could want a bump; wire contract is one-way |
| A6 | Followers honor a transfer marker only when the pinned owner is not online per roster | Pattern 4 | Stricter than D-09; without it a forged marker re-pins followers |
| A7 | Exports go to `<config>/mqtt_actions/` by file name only, mode 0600; imports read from there | Pattern 8 | D-11 says "under /config"; a broader path rule would need `is_allowed_path` and exposes `/config/www` |
| A8 | All new services are admin-only | Pattern 6 | Non-admin users cannot use them from the UI; relaxing risks remote action execution by any user |
| A9 | Effective mode is the most restrictive of instance mode and device mode | Pattern 5 | D-14 does not define the combination |
| A10 | Roster sensor counts this instance; "unknown owner" within 90 s of start is not "offline" for adoption | Patterns 2 and 11 | Off-by-one in the displayed count; too-easy adoption right after a start |
| A11 | Import rejects items with statically denied services | Pattern 8 | A user importing a legitimate item that uses a denied service on their own instance is blocked |
| A12 | Heartbeat QoS 0 and a two-observation debounce for duplicate-id detection | Pitfall 5 | Slower detection (one extra interval) or occasional false positive without it |
| A13 | N = 128 remembered request ids, per-device receiver limit identical to the caller's | Pattern 1 | Values are discretionary per CONTEXT |
| A14 | The `dev`-branch frontend filter logic matches the frontend shipped with 2026.9.x | Pattern 3 | Page contents differ from the design; UAT catches it |
| A15 | A returning old owner is handled by a fixable Repairs release flow, not by automatic step-down | Pattern 4 | Without it the old owner and the adopter fight over the topic |
| A16 | `--verify-tag --generate-notes` and a plain (non-prerelease) release fit HACS expectations | Pattern 10 | HACS may hide prereleases; version-suffixed tags may need `--prerelease` |
| A17 | Clearing the baseline and re-subscribing on leaving `disabled` is the wanted semantics | Pattern 5 | Re-enable could otherwise run actions on a repeated value |

## Open Questions

1. **D-13 wording**
   - What we know: the discovery device cannot be linked to our entry; companion devices work and give the user the page content they asked for.
   - What's unclear: whether duplicate-looking devices (core MQTT device plus companion) are acceptable.
   - Recommendation: take the companion design, differentiate by model and manufacturer, and confirm in UAT.

2. **`executed` semantics and per-instance detail in the response**
   - Recommendation: "started", plus a short `reason` code for non-executed statuses; document it in `docs/operations.md`.

3. **Marker honoring rule for followers (roster condition) and returning old owner**
   - What we know: D-09 only says "followers release the pin only for a document that carries that marker".
   - Recommendation: add the roster condition and the fixable Repairs release flow on the old owner; if the user prefers the literal D-09 rule, keep the marker check only and document the forged-marker limit.

4. **Field name of the device parameter** (`device` versus `device_id`) because of the docs test; decide once and write it into the plans.

5. **Instance-wide mode entity**: D-14 says "per instance and per device" but D-15 only describes the per-device select. Recommend one hub-level select with the same three options.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all | yes | 3.14.7 | — |
| uv | all | yes | 0.12.7 locally | — |
| HA 2026.9.4 in `.venv` | all | yes | 2026.9.4 | — |
| mosquitto | broker tier | yes | 2.1.2 | tests skip without it; CI installs it (add the require-broker switch) |
| mosquitto_passwd, mosquitto_pub | ACL tests | yes | — | tests skip |
| gh, jq | release workflow (runner) and local checks | yes locally; preinstalled on runners | gh 2.101.0, jq 1.7 | — |
| docker or podman | real-frontend UAT with two HA instances | yes (both installed) | — | `~/ha-test/{a,b,mosquitto}` already exists |
| Network access to GitHub | pushing tags, runner behavior | repo is public, default branch `main` [VERIFIED: `gh api` output `public`, `main`] | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9 via pytest-homeassistant-custom-component 0.13.367, `asyncio_mode = "auto"` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths `tests`, marker `broker`) |
| Quick run command | `uv run pytest -q -m "not broker and not multi_instance"` (after the marker split; the whole suite today is 823 tests in about 46 s) |
| Full suite command | `uv run pytest -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPS-01 | Service validates, rate limits per device, publishes non-retained request; approved instances run, unapproved do not; duplicate request id ignored; stale and retained ignored | unit + multi_instance | `uv run pytest tests/test_retrigger.py tests/test_multi_instance_ops.py -x` | no, Wave 0 |
| OPS-02 | Ack per instance, statuses, `no_answer` after window, early exit | multi_instance | `uv run pytest tests/test_multi_instance_ops.py -k ack -x` | no, Wave 0 |
| OPS-03 | Heartbeat publish, roster online/offline by timeout and by `offline` availability, sensor state and attributes, cap | unit + multi_instance | `uv run pytest tests/test_presence.py -x` | no, Wave 0 |
| OPS-04 | Diagnostics contain structure only; sentinel strings from actions, entity ids, instance names never appear | unit | `uv run pytest tests/test_diagnostics.py -x` | no, Wave 0 |
| OPS-05 | README and docs phrases, service names in `services.yaml` equal documented ones, release workflow checks version and requires CI | unit | `uv run pytest tests/test_repo_structure.py -x` | yes, extend |
| OPS-06 | CI has lint, unit, broker, multi-instance jobs; mosquitto only in broker job; tiers partition the suite | unit | `uv run pytest tests/test_repo_structure.py -x` | yes, extend |
| SYN-07 | Adopt: offline owner or `force`; document owner and marker; followers re-pin only with marker (and roster rule); online owner without force fails with message naming `force`; returning owner raises the release issue | multi_instance | `uv run pytest tests/test_multi_instance_ops.py -k adopt -x` | no, Wave 0 |
| SYN-08 | Export all and selection, file write rules, import re-ids, validation, caps, denied-service rejection, round trip | unit | `uv run pytest tests/test_portability.py -x` | no, Wave 0 |
| SYN-09 | Gate: observe logs and tracks baseline without running or counting the breaker; disabled ignores; leaving disabled re-baselines; select entity persists; test and retrigger honor mode | unit + multi_instance | `uv run pytest tests/test_modes.py -x` | no, Wave 0 |
| SYN-10 | Two instances with the same id raise the issue after two observations; fix flow leaves the original's retained topics byte-identical, new id, reload, mirrors appear | multi_instance | `uv run pytest tests/test_multi_instance_ops.py -k duplicate -x` | no, Wave 0 |
| DSC-04 | Resync service and button republish documents, discovery, `online` in order | unit | `uv run pytest tests/test_resync.py -x` | no, Wave 0 |
| D-16 | `actions_hash` changes with run mode and breaker settings; existing approvals lapse and raise requests | unit | `uv run pytest tests/test_document.py tests/test_trust.py -x` | yes, update |
| Broker | ACL block extended for heartbeat, retrigger and acks is enforced on Mosquitto; non-retained messages are not replayed | broker | `uv run pytest -m broker -x` | yes, extend `tests/broker/test_acl.py` |

### Sampling Rate
- **Per task commit:** the affected module's tests plus `uv run pytest -q -m "not broker and not multi_instance"`.
- **Per wave merge:** `uv run pytest -q` and `uv run ruff check . && uv run ruff format --check .`.
- **Phase gate:** full suite green, hassfest and HACS workflows green on the PR, real-frontend UAT on the two-instance setup (page contents, services in Developer Tools, Repairs flows).

### Wave 0 Gaps
- [ ] `pyproject.toml` pytest markers: register `multi_instance` and apply it to `tests/test_multi_instance.py` and `tests/test_fake_broker.py`; add the require-broker switch in `tests/broker/conftest.py`.
- [ ] `tests/fake_broker.py`: extend `InstanceFactory` so instances can answer services and platforms where tests need them (`MockConfigEntry.mock_state`, shared `async_setup_services`), and so two instances can be created with the **same** instance id (data override already exists via `data=`).
- [ ] Extend `tests/documents.py` helpers for the `transferred_from` field.
- [ ] New test files listed above (`test_retrigger.py`, `test_presence.py`, `test_modes.py`, `test_portability.py`, `test_diagnostics.py`, `test_resync.py`, `test_multi_instance_ops.py`).
- [ ] Update `tests/test_repo_structure.py` (WORKFLOW_FILES, `./` refs, CI commands, README phrases), `tests/test_document.py` (hash test), `tests/test_translations.py` (new issue and service keys), `tests/broker/test_acl.py` (new topics).

## Security Domain

`security_enforcement` is enabled in `.planning/config.json` (`security_asvs_level: 1`, `security_block_on: high`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (MQTT auth is the broker's) | document ACL extension |
| V3 Session Management | no | — |
| V4 Access Control | yes | admin-only services (`async_register_admin_service`), per-instance MQTT users and ACL lines for the new topics, mode and approval gates stay in force |
| V5 Input Validation | yes | strict parse with size caps and typed rejects for heartbeat, request, ack and import; UUID parsing; `is_valid_device_id`; reuse `parse_document` for imports |
| V6 Cryptography | no new use | no new crypto; hashes via existing `hashlib` helpers |
| V7 Logging | yes | capped and quoted broker strings in logs; no action content in logs or diagnostics |
| V8 Data protection | yes | allow-list diagnostics, export files mode 0600 in a private directory, never under `www` |
| V12 Files | yes | file name only, fixed directory, no path separators, no `..`, blocking I/O in the executor |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Re-trigger as a second remote execution path | Elevation of privilege | Receivers only run what the approval gate already allows; mode and breaker gates; ACL grants the topic only to Home Assistant users; documented next to the test topic |
| Re-trigger replay or flood | DoS | request-id dedupe, freshness window, per-device limit, ignore retained |
| Forged ack or forged heartbeat | Spoofing | Acks are advisory (display only); heartbeat topic segment must equal payload id; cap on tracked peers; ACL binds each instance to its own heartbeat topic |
| Forged transfer marker re-pinning followers | Tampering | Roster condition, approval stays bound to `actions_hash`, owner_conflict issue otherwise |
| Forged duplicate-id heartbeat | DoS (Repairs noise) | Two-observation debounce, issue created once, nothing automatic |
| Hostile import file | Tampering | Strict path through `parse_document`, caps, denied-service rejection, deep action validation |
| Path traversal through export or import file name | Tampering | Name-only parameter, fixed directory |
| Diagnostics leaking action content or credentials | Information disclosure | Allow-list structure, shortened ids, no MQTT entry data |
| Log forging through mirror names in observe logs | Tampering | Existing `_shown` capped and quoted helper |
| Stale queued request executing late | Tampering | `sent_at` freshness check |

## Sources

### Primary (HIGH confidence)
- Repository files read this session: `custom_components/mqtt_actions/{__init__,const,topics,manager,sync,document,runner,discovery,repairs,mqtt_gateway,model,trust,state,config_flow}.py`, `tests/{fake_broker,conftest,test_repo_structure,test_document,test_multi_instance}.py`, `tests/broker/{conftest,test_acl}.py`, `.github/workflows/{ci,validate}.yml`, `pyproject.toml`, `.ruff.toml`, `docs/broker-acl.md`, `README.md`, `.planning/{REQUIREMENTS,STATE}.md`, `04-CONTEXT.md`, `03-SECURITY.md`.
- HA core 2026.9.4 source in the project venv: `helpers/device_registry.py`, `helpers/entity_registry.py`, `helpers/entity_platform.py`, `helpers/service.py`, `helpers/entity.py`, `config_entries.py`, `core.py`, `core_config.py`, `exceptions.py`, `components/mqtt/{client,diagnostics}.py`, `components/config/device_registry.py`, `components/recorder/db_schema.py`; PHACC `common.py`.
- hassfest at tag 2026.9.4 (fetched): `script/hassfest/{services,config_schema,dependencies}.py`.
- Test baseline run this session: `uv run pytest -q` gave 823 passed in 46.02s.

### Secondary (MEDIUM confidence)
- Frontend `dev` branch: `src/panels/config/integrations/ha-config-integration-page.ts` (device and entity filtering by config entry, lines 1008 and 1295).
- https://www.hacs.xyz/docs/publish/integration/ (releases preferred, five latest shown, manifest `version`).
- https://github.com/actions/runner-images `images/ubuntu/Ubuntu2404-Readme.md` (gh 2.101.0, jq 1.7, no mosquitto).

### Tertiary (LOW confidence)
- None beyond the items tagged `[ASSUMED]` in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, all HA core APIs read from the pinned venv and no packages are added.
- Architecture: HIGH for registry, hassfest and test-harness facts; MEDIUM for protocol designs (they are proposals, listed as assumptions where a choice was made).
- Pitfalls: HIGH for the repo-derived ones (teardown helpers, harness seam, Store keys, pinned tests); MEDIUM for broker-session behavior (Pitfall 4) and frontend behavior (Pitfall 9).

**Research date:** 2026-10-02
**Valid until:** 2026-10-16 (HA ships patch releases roughly weekly and PHACC tracks them; re-check the registry and frontend facts if the HA floor or the pinned version moves)
