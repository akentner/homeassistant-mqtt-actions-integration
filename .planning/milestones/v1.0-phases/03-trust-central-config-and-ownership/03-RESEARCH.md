# Phase 3: Trust, Central Config and Ownership - Research

**Researched:** 2026-10-01
**Domain:** Home Assistant custom integration (Python 3.14, HA 2026.9.4): retained-MQTT config replication, owner/follower ownership, hash-bound approval via Repairs, execution-time service denylist, multi-instance test harness
**Confidence:** HIGH for HA/MQTT platform facts and the two spikes (verified against the installed HA 2026.9.4 source and by running code); MEDIUM for protocol-design recommendations (own synthesis, flagged `[ASSUMED]` where they are tunables or policy)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Trust gate and approval (TRU-01..04)
- **D-01:** There is no hub-wide trust policy. Remote actions are denied until the user approves a device on that instance. No `ask`/`auto` modes in v1 (keeps "auto-accepting remote config" out of scope).
- **D-02:** The approval is a Repairs flow showing device name, owner name and the full action sequence as YAML. The approval is bound to the canonical action hash. If the owner changes the actions, the old approval lapses, the mirror's actions pause and a new Repairs issue shows the new sequence. Owned devices never need approval.
- **D-03:** The service denylist is a fixed constant in `const.py` and applies only to actions received from the broker (mirrors). Owned actions stay unrestricted. The user cannot change the list.
- **D-04:** The denylist check walks the action tree recursively (choose, repeat, sequence, parallel, if, ...). Templated service names are allowed but flagged in the approval view.
- **D-05:** Because templates stay allowed, the denylist is also enforced at execution time on the resolved service name of mirror scripts. A hit aborts the run and is surfaced (log + Repairs). If the researcher finds no feasible hook, fallback: reject templated service names in mirrors.
- **D-06:** Every document from the broker is schema-validated (`cv.SCRIPT_SCHEMA` / `async_validate_actions_config`) before it is stored or offered for approval; invalid documents are dropped and logged.
- **D-07:** Docs (TRU-04) include a broker ACL example binding each instance to its own topics.

### Mirror storage and removal (SYN-02, SYN-05)
- **D-08:** Mirrors live in the HA `Store` (cached config, approval state, `last_acted`), not as subentries. Subentries stay exclusively owned devices. Mirrors are surfaced through their entities and Repairs, not an editable UI.
- **D-09:** A live tombstone (empty retained config payload) removes the mirror at once, including leftover entity/device registry entries.
- **D-10:** Deletions missed while offline are detected by a grace window after subscribe: a mirror whose config was not seen again within the window is removed, but only if its owner was seen online (owner availability topic). Owner offline or unknown: the mirror stays. A missing message alone never deletes a mirror.
- **D-11:** Removing the hub lets the user choose: keep devices (they become orphaned, config/discovery/state stay retained) or delete all owned devices everywhere. Local mirrors and Store are always removed. Replaces D-15 of Phase 1. Without an explicit choice the default is keep. — **Reversibility:** costly — changes what persists on the broker after uninstall.

### Central config document (SYN-01, SYN-04)
- **D-12:** One retained (QoS 1) document per device at `<base>/v1/devices/<device_id>/config`, written only by the owner. It carries `schema_version`, `device_id`, `owner` (instance ID), `owner_name`, `rev`, canonical content hash, name, kind, options/actions as raw ActionSelector output. — **Reversibility:** one-way — the document layout and topic become the cross-instance wire contract.
- **D-13:** Shared by the document: name, kind, options (StateValue, friendly name, actions), `run_mode`, `run_on_startup`, breaker limits. Local per instance: breaker tripped state, `last_acted`, approval. A device behaves the same everywhere.
- **D-14:** A follower rejects a document with a higher `schema_version` than it knows: nothing is applied, the existing mirror stays at its last known state, a Repairs issue asks to update the integration. Older versions are read through migration.
- **D-15:** Followers apply only a higher `rev` or a different hash; an identical hash is a no-op. The owner republishes all owned documents on every MQTT reconnect. If a retained document for an owned device differs from local truth (foreign write, wiped broker), the owner republishes and raises a Repairs issue when content differed.

### Ownership, delete and discovery healing (SYN-03, SYN-06, DSC-03)
- **D-16:** Delete confirmation is a step in the subentry flow stating that the device is removed on all connected instances, listing the instances that mirror it as far as known. Order as in D-16 of Phase 1: discovery first, unsubscribe, then config tombstone and state topic. No typed-name confirmation.
- **D-17:** Owner conflicts: first owner wins. A follower pins the owner on first sight and ignores documents from other owners for that `device_id`, with a Repairs issue naming both claims. An owner that sees its own `device_id` claimed by another republishes and raises Repairs. No takeover in v1.
- **D-18:** If a follower deletes the mirrored entity (core MQTT clears the retained discovery topic), the owner watches its discovery topics and republishes, throttled per device (start value one republish per 60 s). Repeated removals raise a Repairs hint.
- **D-19:** Discovery keeps the owner's availability topic. Owner offline means mirror entities are `unavailable`; followers still run actions for external state changes. No change to the Phase 1 discovery contract.

### Claude's Discretion
- Exact grace window length, throttle value, canonical-JSON/hash algorithm, Store layout and key names, step ids and Repairs wording, translation keys, YAML rendering in the approval view.
- How the delete step learns which instances mirror a device in Phase 3 (best effort from instance availability topics seen; a full roster is Phase 4).
- How the hub-removal choice (D-11) is offered, since HA has no hook in entry removal (likely a reconfigure/options step before removal).

### Deferred Ideas (OUT OF SCOPE)
- Hub-wide `ask`/`auto` trust policy.
- User-extendable denylist.
- Diff view between old and new actions on re-approval.
- Owner manifest topic for deterministic pruning (revisit if grace-window pruning proves fragile).
- Typed-name delete confirmation.
- Ownership transfer and adopting orphans (Phase 4, SYN-07).
- Full instance roster (Phase 4, OPS-03).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYN-01 | Owner publishes one retained, versioned config document per device | Wire document (Pattern 1), owner publish order and echo rules (Pattern 2), `IncomingMessage.topic` gap (Pitfall 1) |
| SYN-02 | Another instance creates the same devices as read-only mirrors | Follower apply state machine (Pattern 3), separate `mirrors` dict (Pitfall 2), Store layout |
| SYN-03 | One owner per device; only owner edits/deletes; followers pin owner, Repairs on conflict | Structural (mirrors are not subentries), pinning rules, ping-pong throttle (Pitfall 6) |
| SYN-04 | Owner reconciles and republishes on every MQTT reconnect | Reconnect hook exists in `manager.py:259-277`; add config docs first, availability last (Pattern 2) |
| SYN-05 | Followers never delete because a message is absent | Tombstone + grace-window prune bound to owner availability (Pattern 7) |
| SYN-06 | Delete needs explicit confirmation stating all-instances removal, then unpublish | Delete flow step + tombstone order (Pattern 8); generic HA delete cannot be vetoed (Open Question 1) |
| TRU-01 | Remote-provided actions are not executed by default | Mirror gets no Script until approved; `runner.can_run` already gates (Pattern 4) |
| TRU-02 | Per-instance approval via Repairs, bound to action hash | Repairs fix flow facts and lifecycle (Pattern 5), dismissed-issue pitfall (Pitfall 8) |
| TRU-03 | Schema validation of every received sequence + execution-time denylist | Two-level validation (Pattern 6), `GuardedTemplate` hook verified by spike (Pattern 6, Code Examples) |
| TRU-04 | Docs include broker ACL example | Mosquitto ACL syntax and its limits (Pattern 12, Security Domain), broker-tier ACL test |
| STA-03 | Actions run locally on every participating instance | Mirror subscribes to the state topic from creation (baseline), approved mirrors run like owned devices; multi-instance harness (Pattern 11) |
| DSC-03 | Owner republishes discovery removed by a follower deleting the entity | Verified core behavior (clears the whole device topic); watcher with trailing throttle (Pattern 9) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

From `/home/akentner/Projects/homeassistant-mqtt-actions-integration/.claude/CLAUDE.md` (plus the parent CLAUDE.md files), treated with the same authority as locked decisions:

- Python 3.14, HA 2026.9.x, `import probatio` (never add `voluptuous`); Ruff with `select = ["ALL"]`, 120-char lines, `target-version = "py314"` (`.ruff.toml`); code, comments and commits in English; chat in German.
- Use `entry.runtime_data`, never `hass.data[DOMAIN]` for per-entry state; translations in `translations/en.json` and `translations/de.json` (never `strings.json`); no YAML config; no `setup.py`/Poetry; pin nothing that PHACC pins.
- **Do not execute a received action sequence without (a) the local opt-in flag and (b) schema validation.** Phase 3 satisfies (a) with the per-device, per-instance approval of D-01/D-02 (no hub flag by decision); flag this wording difference to the user if the planner wants it reconciled (see Open Question 6).
- Do not use `device_id` targets in shipped examples or defaults; services are registered in `async_setup` (no new services in Phase 3; the re-trigger service is Phase 4).
- Repairs, flows and docs must have en/de parity (enforced by `tests/test_translations.py`); hassfest validates `en.json` only.
- GSD workflow enforcement: edits go through GSD commands; TDD is on (`workflow.tdd_mode: true`), tests come with each task.
- No project skills directory exists (`.claude/skills`, `.agents/skills` absent).

## Summary

The phase adds a second, symmetric role to the existing `Manager`: every instance is owner of its subentry devices and follower of everyone else's. The owner publishes one retained JSON document per device; followers validate it, cache it in the `Store`, subscribe to the device's state topic immediately (so the baseline is tracked), and build a `Script` only after the user approved the exact action hash in Repairs. Entities already appear on followers through core MQTT discovery published by the owner; this phase is therefore mostly about config, trust, ownership and lifecycle, not about creating entities.

Three findings change the plan shape and are not visible in CONTEXT.md. First, `IncomingMessage` has no `topic` field (`mqtt_gateway.py:17-21`), yet tombstones (empty payload), owner-availability and discovery-watch messages arrive on wildcard subscriptions where only the topic identifies the device or instance. Second, `Manager.async_reconcile` removes every device in `self.devices` that is not a subentry and clears its broker topics (`manager.py:217-219`), so mirrors must live in a separate dict or the first reconcile would wipe them from the broker. Third, the D-05 execution-time denylist is feasible without monkeypatching: core renders a templated service name by calling `Template.async_render` on the validated config (`service.py:281-283`), so wrapping those `Template` objects in a subclass that raises a plain `Exception` aborts the run even when the author sets `continue_on_error: true` (verified by a spike on 2026.9.4). The fallback of D-05 is not needed.

The remaining work is careful state-machine design: owner publish order (config documents, then discovery, then availability `online`), own-echo versus foreign-write detection, stale-mirror pruning tied to owner availability events, hash-bound approval with a Repairs lifecycle that survives the "dismissed issue stays dismissed" behavior of the issue registry, a delete flow that cannot veto HA's generic subentry delete, and a multi-instance test harness (`FakeBroker`) that was spiked and works with two real `hass` instances and unchanged production code.

**Primary recommendation:** Build a pure `document.py` (wire contract, canonical hash, denylist walker, caps) first, add `topic` to `IncomingMessage` and a `FakeBroker`/`FakeGateway` test tier in Wave 0, keep mirrors in their own dict and Store keys, gate execution on "no Script until approved", and enforce the denylist with a `GuardedTemplate` wrapper applied in the one place `ActionRunner._async_build_script` assembles the Script.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Central config document (publish, schema, hash) | Owner HA instance | MQTT broker (retained store) | Only the owner writes; the broker is transport and cache only |
| Mirror cache, pinning, approval state | Follower HA instance (`Store`) | — | D-08: local per instance, survives restart before the broker replays |
| Entity creation on followers | Core MQTT discovery (per instance) | Owner HA (publishes discovery) | Entities are not ours; the owner's retained discovery drives them |
| Action execution | Each HA instance (`Script`) | — | Core value: every instance executes locally |
| Approval UI | HA frontend (Repairs fix flow) | Follower `repairs.py` | Keeps security prompts out of config flows |
| Denylist enforcement | Follower `ActionRunner` (build + execution time) | `document.py` walker (static) | Never trust owner-side validation |
| Ownership enforcement | Broker ACL (real) | Follower pinning (cooperative) | MQTT has no per-message auth; owner is only text in the payload |
| Delete confirmation | HA config subentry flow (owner) | Broker tombstones | Confirmation in flow; propagation via retained empties |
| Discovery healing | Owner HA (watches its discovery topic) | Core MQTT (does the clearing) | Core clears the topic when any instance deletes the entity |
| Stale-mirror pruning | Follower HA (timer) | Broker (owner availability topic) | No end-of-replay marker exists; availability gates pruning |

## Standard Stack

No new runtime dependency is needed (`manifest.json` has `"requirements": []` and stays that way). Everything below is HA core API already on the path, verified against the installed 2026.9.4 source in `/home/akentner/Projects/homeassistant-mqtt-actions-integration/.venv/lib/python3.14/site-packages/homeassistant/`.

### Core
| Library / API | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| `homeassistant.components.repairs` (`RepairsFlow`, `async_create_fix_flow` in our `repairs.py`) | core 2026.9.4 | Approval flow | The only supported Repairs fix-flow mechanism `[CITED: developers.home-assistant.io/docs/core/platform/repairs/]` |
| `homeassistant.helpers.issue_registry` | core | Approval, conflict, blocked, schema issues | Already used by `manager.py`/`runner.py` |
| `homeassistant.helpers.storage.Store` | core | Mirrors, approvals, revs (additive keys, no version bump) | Phase 2 precedent (`STORE_TRIPPED`) |
| `homeassistant.helpers.script.Script` + `template.Template` subclass | core | Run mirror actions with guarded service names | Spike-verified hook (see Pattern 6) |
| `homeassistant.helpers.device_registry` / `entity_registry` | core | Leftover cleanup of mirrored entities | Device identifiers are config-entry scoped in 2026.9 |
| `homeassistant.util.yaml.dump` | core | YAML text of actions in the approval view | Exported in `util/yaml/__init__.py` `__all__` |
| `homeassistant.util.json.json_loads_object` (orjson) | core | Parse incoming documents | Same parser core discovery uses; nesting limited by orjson |
| stdlib `hashlib`, `json` | 3.14 | Canonical content hash | Own code both ends, so no JCS library needed |
| `paho.mqtt.client.topic_matches_sub` | paho 2.x (in HA) | Wildcard matching inside the `FakeBroker` | Do not hand-roll; present at `paho/mqtt/client.py:423` |

### Supporting (test tier)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-homeassistant-custom-component | 0.13.367 (pinned in `pyproject.toml`) | `hass`, `mqtt_mock`, `async_test_home_assistant`, `async_fire_mqtt_message` | All tests |
| mosquitto | 2.1.2 (installed at `/usr/bin/mosquitto`) | Broker-tier ACL test | `tests/broker/` (skips when missing) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Wrapping validated `Template` objects (`GuardedTemplate`) | Reject templated service names in mirrors (D-05 fallback) | Fallback is simpler and immune to core refactors but contradicts the user's choice (D-04 allows templates). Keep it as the documented escape hatch if a future HA version breaks the regression test |
| Separate `mirrors` dict in `Manager` | `Device.origin` flag inside `self.devices` | A flag requires touching six loops in `manager.py` (reconcile, stop, save, orphan cleanup, republish, load); a separate dict leaves owned behavior untouched |
| One wildcard subscription per concern | One subscription per device | Wildcards are stable across device churn and need no resubscribe; filter by parsed id |

**Installation:** none.

**Version verification:** `homeassistant` 2026.9.4 is what `.venv` resolves (`const.py:24-26` `MAJOR_VERSION: Final = 2026`, `MINOR_VERSION: Final = 9`, `PATCH_VERSION: Final = "4"`); `pytest-homeassistant-custom-component==0.13.367` and `ruff==0.16.9` are pinned in `pyproject.toml`; baseline suite run this session: 426 passed in 21.8 s.

## Package Legitimacy Audit

Not applicable: this phase installs no external packages. `manifest.json` `requirements` stays `[]`; the test tier uses only packages already pinned via PHACC and the system mosquitto binary.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Verified In-Repo Values (source-of-truth quotes, read this session)

| Value | Source | Verbatim |
|-------|--------|----------|
| Topic version | `const.py:16` | `TOPIC_VERSION: Final = "v1"` |
| Subentry data keys | `const.py:21-28` | `CONF_DEVICE_ID: Final = "device_id"`, `CONF_ON_CHANGE_TO_ON: Final = "on_change_to_on"`, `CONF_ON_CHANGE_TO_OFF: Final = "on_change_to_off"`, `CONF_RUN_ON_STARTUP: Final = "run_on_startup"`, `CONF_OPTIONS: Final = "options"`, `CONF_STATE_VALUE: Final = "state_value"`, `CONF_FRIENDLY_NAME: Final = "friendly_name"`, `CONF_ACTIONS: Final = "actions"` |
| Run mode / breaker keys | `const.py:31-36` | `CONF_RUN_MODE: Final = "run_mode"`, `CONF_BREAKER_MAX_RUNS: Final = "breaker_max_runs"`, `CONF_BREAKER_WINDOW: Final = "breaker_window"` |
| Limits | `const.py:39-44` | `SERIAL_QUEUE_LIMIT: Final = 10`, `MIN_OPTIONS: Final = 2`, `MAX_OPTIONS: Final = 50`, `MAX_TEXT_LENGTH: Final = 64` |
| Store constants | `const.py:57-62` | `STORE_KEY: Final = f"{DOMAIN}.state"`, `STORE_VERSION: Final = 1`, `STORE_LAST_ACTED: Final = "last_acted"`, `STORE_PUBLISHED: Final = "published"`, `STORE_TRIPPED: Final = "tripped"`, `STORE_SAVE_DELAY: Final = 5.0` |
| Issue prefixes | `const.py:73-75` | `ISSUE_ACTION_FAILED_PREFIX: Final = "action_failed_"`, `ISSUE_CIRCUIT_BREAKER_PREFIX: Final = "circuit_breaker_"`, `ISSUE_DISCOVERY_DISABLED: Final = "mqtt_discovery_disabled"` |
| State topic | `topics.py:35-37` | `return f"{base}/{TOPIC_VERSION}/devices/{device_id}/state"` |
| Instance availability topic | `topics.py:45-47` | `return f"{base}/{TOPIC_VERSION}/instances/{instance_id}/availability"` |
| Discovery topic | `topics.py:50-52` | `return f"{prefix}/device/{device_id}/config"` |
| Discovery device identifier | `discovery.py:133` | `"device": {"identifiers": [f"{DOMAIN}_{spec.device_id}"], "name": spec.name},` |
| Discovery availability | `discovery.py:136` | `"availability": [{"topic": availability_topic(base_topic, instance_id)}],` |
| Discovery unique ids | `discovery.py:57,76,101` | switch/select `"unique_id": device_id` / `spec.device_id`; button `"unique_id": f"{device_id}_test_{trigger.key}"` |
| Gateway message type | `mqtt_gateway.py:17-21` | `class IncomingMessage:` with only `payload: str` and `retain: bool` (no topic) |
| Reconcile removes non-subentry devices | `manager.py:217-219` | `subentries = {subentry.data[CONF_DEVICE_ID]: subentry for subentry in _device_subentries(self._entry)}` then `for device_id in [device_id for device_id in self.devices if device_id not in subentries]: await self._async_remove_device(device_id)` |
| Start prunes baselines/tripped to owned ids | `manager.py:197-201` | `current = {subentry.data[CONF_DEVICE_ID] for subentry in _device_subentries(self._entry)}` then `self._stored_last_acted = {... if device_id in current}` and `self._tripped = {... if device_id in current}` |
| Runner gate | `manager.py:469-470` | `if trigger is None or not self.runner.can_run(device_id, trigger.key): return` |
| Hub removal today | `__init__.py:52-58` | `async_remove_entry` docstring: "Phase 3 must redesign this as a confirmed, multi-instance-aware delete"; body `await async_remove_all_devices(hass, entry)` |
| Existing hub-flow guard test | `tests/test_config_flow.py:136-138` | `def test_hub_flow_has_no_reconfigure_step()` asserts `not hasattr(MqttActionsConfigFlow, "async_step_reconfigure")` (an `OptionsFlow` does not violate it) |

## Architecture Patterns

### System Architecture Diagram

```
  OWNER instance A                               BROKER                          FOLLOWER instance B
 ┌──────────────────────────┐                ┌────────────────────┐          ┌──────────────────────────────┐
 │ subentry add/edit/delete │                │ retained:          │          │ core MQTT discovery (per HA) │
 │        │                 │                │  v1/devices/X/config│          │   creates entities from A's  │
 │        ▼                 │  1 config doc  │  v1/devices/X/state │          │   retained discovery         │
 │ Manager.reconcile ───────┼───────────────▶│  v1/instances/A/avail│         │                              │
 │  (owned dict)            │  2 discovery   │  <prefix>/device/X/ │ replay   │ SyncManager (new)            │
 │ SyncManager.owner        ├───────────────▶│   config            │─────────▶│  config wildcard sub         │
 │  publish order:          │  3 avail=online│                    │ retain=T │  parse(topic,payload)        │
 │  config → discovery →    ├───────────────▶│                    │          │   ├ size/depth/schema gate   │
 │  availability            │                │                    │          │   ├ recompute hash (never    │
 │        ▲                 │  discovery     │                    │          │   │  trust doc.hash)         │
 │ discovery watcher ◀──────┼── empty live ──┤◀── follower deletes entity ────│   ├ pin owner / conflict     │
 │  (trailing throttle 60s) │  msg (retain=F)│    (core publishes None,       │   ├ schema_version gate      │
 │        │ republish       │                │     retain=True)    │          │   └ apply / pause / tombstone│
 │                          │                │                    │          │        │                     │
 │ delete flow step:        │ tombstones     │                    │ live     │  mirrors dict (Device)       │
 │  discovery clear →       ├───────────────▶│  (empty retained)  │─────────▶│   subscribe state+test from  │
 │  unsubscribe →           │                │                    │ empty    │   creation (baseline only)   │
 │  config+state tombstone  │                │                    │ retain=F │        │                     │
 └──────────────────────────┘                └────────────────────┘          │  approved hash == actions hash?
                                                                              │   no  → no Script, Repairs issue
        state change (UI on any instance, or external MQTT publish)           │   yes → ActionRunner builds    │
        ─────────────────────────▶ v1/devices/X/state ──────────────────────▶│         Script with guarded    │
                                   fan-out to every subscriber                │         service names → runs   │
                                                                              └──────────────────────────────┘
```

### Recommended Project Structure

```
custom_components/mqtt_actions/
├── document.py     # NEW, pure: wire schema, parse/caps, canonical JSON, content hash, actions hash,
│                   #   doc <-> DeviceSpec, static denylist walker, approval view model
├── sync.py         # NEW: SyncManager (owner publish/echo/republish/watch, follower apply/pin/prune/tombstone)
├── trust.py        # NEW: approval state, denylist constants usage, GuardedTemplate + guard_actions()
├── repairs.py      # NEW: async_create_fix_flow + ApprovalRepairFlow (HA discovers this platform file by name)
├── topics.py       # add config_topic, config wildcard, availability wildcard, parsers
├── const.py        # add DENIED_*, caps, STORE_MIRRORS/APPROVALS/REVS, ISSUE_* prefixes, SCHEMA_VERSION
├── mqtt_gateway.py # IncomingMessage gains topic
├── manager.py      # owned path unchanged in behavior; hosts self.mirrors; delegates to SyncManager
├── runner.py       # async_build_device(spec, *, restricted=False, on_denied=...)
├── config_flow.py  # delete steps (both flows), hub OptionsFlow (D-11)
└── __init__.py     # async_remove_entry reads the D-11 option; async_get_options_flow registered in config_flow
tests/
├── fake_broker.py  # NEW: FakeBroker, FakeGateway, instance factory (two real hass instances)
└── ...             # see Validation Architecture
docs: README section + docs/broker-acl.md (example ACL + limits)
```

### Pattern 1: Pure document module and the wire contract (SYN-01, D-12, D-13)

**What:** `document.py` owns everything about the document so compatibility bugs live in one pure, cheaply testable module. Reuse the subentry data keys verbatim so `spec_from_data(kind, name, data)` (`model.py:155-173`) can consume a document directly.

**Proposed document (D-12 fields, D-13 shared settings):**
```json
{
  "schema_version": 1,
  "device_id": "<uuid, must equal the topic segment>",
  "owner": "<instance uuid>",
  "owner_name": "<hub instance_name>",
  "rev": 7,
  "hash": "<sha256 hex of the canonical content>",
  "kind": "switch",
  "name": "Lamp",
  "run_on_startup": false,
  "run_mode": "serial",
  "breaker_max_runs": 5,
  "breaker_window": 10,
  "on_change_to_on": [{"action": "light.turn_on", "target": {"entity_id": "light.lamp"}}],
  "on_change_to_off": [],
  "options": [{"state_value": "eco", "friendly_name": "Eco", "actions": []}]
}
```
`kind` is `"switch"` or `"select"` (the `SUBENTRY_*` values); a switch carries `on_change_to_on`/`on_change_to_off`, a select carries `options`. `[ASSUMED]` exact key set beyond D-12/D-13 is discretion; the rules below are what matter.

**Rules the planner must encode:**
1. **Build the document from `DeviceSpec`, not from raw subentry data.** `spec_from_data` normalizes missing keys to defaults (`model.py:155-173`); a Phase 1 switch without `run_mode` must emit `"serial"` so the hash means "same behavior". Raw data would make the hash depend on storage history.
2. **Canonical form:** `json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` UTF-8 encoded, sha256 hex. Do not reuse `manager._fingerprint` (`manager.py:82-84`, default separators, includes title/data shape). The algorithm becomes part of the wire contract (document it in the module docstring). `content` excludes `hash`, `rev`, `owner`, `owner_name` (identity and bookkeeping, not behavior).
3. **Two hashes:** `content_hash` (whole shared content: drives "apply or no-op", D-15) and `actions_hash` (approval binding, D-02): sha256 over canonical `{"kind", "run_on_startup", "triggers": [[state_value.lower(), actions], ...]}` sorted by lowercased StateValue. Including the StateValue-to-actions mapping matters: swapping which actions run on ON versus OFF is a semantic change with identical action lists. Renaming the device or a friendly name, or changing run mode/breaker limits, changes `content_hash` but not `actions_hash`, so it needs no re-approval. `run_on_startup` is in `actions_hash` because it decides whether approved actions run at HA start `[ASSUMED]` policy choice.
4. **The follower never trusts `doc["hash"]`.** It recomputes both hashes from the received content. The field is informative (owner-side dedupe, diagnostics).
5. **Reject strictly (D-06):** payload over `MAX_DOCUMENT_BYTES`; not a JSON object; `schema_version` missing or not an int; `device_id` differs from the topic segment (the only "owner bound to topic" check possible with the locked layout, see Pattern 12); kind not `switch`/`select`; text fields not printable or over `MAX_TEXT_LENGTH` (reuse `model._invalid_text` semantics); select with fewer than `MIN_OPTIONS` or more than `MAX_OPTIONS`; duplicate StateValues ignoring case; breaker/run-mode values out of range (`validate_breaker` bounds); action nesting deeper than `MAX_ACTION_DEPTH`. A strict reject leaves an existing mirror untouched (same rule as D-14).
6. **`rev`:** an integer per owned device persisted in the `Store` (`revs`), incremented whenever the owner's content hash changes versus the last published one. Loss of the Store restarts at 1; followers still apply because the hash differs (D-15 says "higher rev or different hash"). Treat `rev` as ordering/diagnostics, never as the apply gate on its own.
7. `owner_name` and `name` end up in Repairs text and logs: apply the same printable/length rules and never log action data (existing T-01-10 rule).

### Pattern 2: Owner side (SYN-01, SYN-04, D-15)

- **Publish order on start and on every reconnect: config documents, then discovery, then availability `online`.** The order is load-bearing: pruning of stale mirrors (Pattern 7) interprets "owner online and my mirror not re-seen" as "deleted". `Manager._async_republish` (`manager.py:265-277`) currently does discovery then availability; insert the documents first.
- **Triggers:** subentry add/change (`_async_add_device`, `_async_change_device`), start (`async_start`), and every `_on_connection_status(True)` (`manager.py:259-263`). Publish with `retain=True`, QoS 1 through the gateway.
- **Subscribe to `<base>/v1/devices/+/config` before publishing** (architecture hazard 7) and start it in `async_start`; store the returned unsubscribe via `entry.async_on_unload`/manager teardown like the existing subscriptions.
- **Own-echo versus foreign write (D-15).** The owner sees its own documents come back live (`retain=False`). Naive "hash differs from local truth means foreign write" raises false alarms: publish rev1, edit quickly, publish rev2, then the rev1 echo arrives while local truth is already rev2. Use: keep the last N (for example 8) published content hashes per device in memory; an incoming `owner == me` document whose hash is in that set is an echo, ignore it. Otherwise compare with local truth: equal means no-op; different means republish, and raise the Repairs issue only when `doc.rev >= local rev` (a document with a lower rev is my own older document, for example published before an offline edit, so republish silently). After a crash, `rev` saved with `STORE_SAVE_DELAY` may lag; accept that a spurious Repairs issue can appear once and document it.
- **An `owner == me` document for a device with no local device** (tombstone failed earlier, cloned instance id, restore): if the id is in the persisted `published` set and no subentry exists, re-run the tombstone (retry); otherwise ignore with a debug log. Do not adopt it as a mirror (adoption is Phase 4, SYN-07/SYN-10).
- **A document for an owned `device_id` from another owner:** republish local truth and raise `ownership_claim_<device_id>` Repairs (D-17). Two claimants each "healing" would ping-pong forever: rate-limit per device (reuse the 60 s throttle) and raise the issue on the first occurrence only.
- **Do not wait for the retained replay before publishing.** Detection of a foreign write that predates the start is best-effort (works when the replay arrives before our publish); live foreign writes are always caught. State this limitation in docs `[ASSUMED]` trade-off; the alternative (settle window before publishing) delays SYN-04 and the spec says "republishes on every reconnect".

### Pattern 3: Follower apply state machine (SYN-02, SYN-03, D-14, D-15, D-17)

Input: `(topic_device_id, payload, retain)` from the config wildcard. Output actions, in this order:

| # | Condition | Action |
|---|-----------|--------|
| 1 | payload empty | **Tombstone** (live or retained): remove mirror now (D-09), see Pattern 7; if the device is owned locally this is the owner-foreign-write case of Pattern 2 |
| 2 | over size / not JSON object / `device_id` != topic | drop, log once (no payload content), keep existing mirror |
| 3 | `schema_version` > known | keep existing mirror unchanged, raise `schema_too_new_<device_id>` Repairs (non-fixable, "update the integration"), apply nothing (D-14) |
| 4 | strict document validation fails | drop and log, keep existing mirror |
| 5 | `owner == my instance id` | Pattern 2 branches (echo, stale self, unknown) |
| 6 | device owned locally (my subentry) and owner is someone else | Pattern 2 ownership claim |
| 7 | mirror exists, pinned owner != doc.owner | ignore; raise `owner_conflict_<device_id>` naming both claims; never apply (D-17) |
| 8 | mirror exists and `content_hash` equal | no-op (clear any conflict issue if the pinned owner wrote it) |
| 9 | mirror exists, hash differs | apply (update cache, `Device.spec`); Pattern 5 decides pause/re-approval |
| 10 | no mirror | cap check (`MAX_MIRRORS`), pin owner, store, create `Device` (tracker, breaker, state and test subscriptions), Pattern 5 |

`schema_version` migration: `SCHEMA_VERSION = 1` today; an older-version reader is a function `migrate(doc) -> doc` that does nothing at v1 but must exist and be tested with a synthetic "v0" fixture once v2 exists. `[ASSUMED]` planner may defer the function body and only reserve the seam.

### Pattern 4: Mirror runtime (STA-03, TRU-01)

- Keep mirrors in **`Manager.mirrors: dict[str, Device]`**, separate from `self.devices`. `async_reconcile` (`manager.py:206-224`), `async_stop`, `_data_to_save` (`manager.py:316-326`), `_async_orphan_cleanup`, `_async_republish` and the `current`-set pruning in `async_start` (`manager.py:197-201`) all assume `self.devices` equals the subentries. Looking mirrors up in both dicts is a small helper used by `_on_message`/`_on_test_message`.
- `_data_to_save` must include mirror baselines in `STORE_LAST_ACTED` and mirror trip hashes in `STORE_TRIPPED`; `async_start` must prune those maps against `owned | mirrors` ids, not only owned ids.
- Give a mirror its `StateTracker`, `CircuitBreaker` and both subscriptions **at creation, before approval**: the retained state replay then sets the baseline, so approving later never retroactively runs anything (STA-04 semantics hold). `startup_pending` is true only for mirrors restored from the `Store` at start (same as owned devices).
- **Gate = no Script until approved.** `ActionRunner.can_run` is false for a device without a built Script, and both `_on_message` and `_on_test_message` already return on that (`manager.py:469-470`, `577-578`). So unapproved (or paused-by-change) mirrors track state and run nothing with no new branch in the hot path. A mirror whose triggers all have empty actions needs no approval (nothing can execute).
- Test-button topic: decide explicitly (Open Question 4). Recommended: mirrors subscribe to the test topic as well and run only when approved, so pressing "Test" on any instance runs on every approved instance; the alternative is owner-only, which makes the follower button inert.
- Mirror `Device.signature` should be the canonical content JSON so `_hash_fingerprint(device.signature)` (used for breaker persistence, `manager.py:511,527`) keeps working unchanged.

### Pattern 5: Hash-bound approval through Repairs (TRU-01, TRU-02, D-01, D-02)

Facts verified in `components/repairs/issue_handler.py` and `helpers/issue_registry.py`:
- A fix flow needs `is_fixable=True`; our `repairs.py` must expose `async_create_fix_flow(hass, issue_id, data)`; the flow manager sets `flow.issue_id` and `flow.data = issue.data` (`issue_handler.py:55-78`). `data` values must be `str | int | float | None` (`issue_registry.py` `data: dict[str, str | int | float | None]`), so issue data carries only `device_id` and the `actions_hash`; the YAML and names are rendered in the flow from the `Manager`'s cached mirror and passed as `description_placeholders`.
- `async_finish_flow` deletes the issue for any result except ABORT (`issue_handler.py:97-98`: `if result.get("type") is not data_entry_flow.FlowResultType.ABORT: ir.async_delete_issue(...)`). So: approve = `async_create_entry(data={})` (issue removed automatically); "not now/changed underneath" = `async_abort`.
- `is_persistent` defaults to `False`, so issues vanish on restart; the manager recreates pending-approval issues at start from the `Store` (same as the breaker issue, `manager.py:517-537`).

Lifecycle rules:
1. `approvals` Store key (separate from `mirrors`): `{device_id: actions_hash}`. Keeping approvals apart from device records lets a false removal be reversed without a new approval `[CITED: .planning/research/PITFALLS.md "Recovery Strategies"]`.
2. On apply: `needs_approval = any trigger has actions` and `approvals.get(id) != actions_hash`. If approved: (re)build the Script (restricted, Pattern 6). If not: unload the Script (`runner.async_unload`, stops running and queued runs), delete then create `approval_<device_id>` issue.
3. **Delete before create when the hash changes.** `async_get_or_create` keeps `dismissed_version` when an issue exists (`dataclasses.replace(issue, ...)` does not reset it), so replacing an issue a user dismissed would keep the new approval request hidden. `ir.async_delete_issue` then `ir.async_create_issue` resets it.
4. The flow's confirm step must re-read the **current** mirror and compare `actions_hash` with the hash the issue was created for (issue `data`) and with what it displays: if the owner changed the document while the dialog was open, abort with a translated reason and let the freshly created issue take over. Approval stores the hash that was displayed, never "whatever is current".
5. Approval view (D-02): device name, owner name, the actions as YAML (`homeassistant.util.yaml.dump` over `{label: actions}` with labels `onChangeToOn`/`onChangeToOff` or the option friendly name + StateValue), a short hash prefix, and a bullet list of **templated service names** found by the walker (D-04). Cap the rendered text (`APPROVAL_YAML_MAX_CHARS`) with an explicit "truncated" notice; refuse approval of a document whose YAML would be truncated `[ASSUMED]` so nobody approves what they could not read.
6. Sanitize for markdown: strip or neutralize triple backticks and control characters from the YAML and names before putting them into a fenced block; `owner_name` and `name` are attacker-controlled (`[ASSUMED]` the HA frontend renders fix-flow descriptions as markdown; verify in UAT).
7. Statically denied services make the mirror **blocked**: stored for visibility, never approvable, a non-fixable `blocked_<device_id>` issue lists the denied service names. `[ASSUMED]` policy; the alternative (silent drop) hides the reason from the user.
8. Translations: `issues.<key>.title/description` and, for the fixable one, `issues.<key>.fix_flow.step.init...`/`confirm` plus `abort` reasons, in en and de; extend `tests/test_translations.py` `REQUIRED_KEYS`. Placeholder text must not sit inside single quotes (hassfest rule already encoded in `VARIABLE_IN_SINGLE_QUOTES`, `tests/test_translations.py`).

Issue ids (proposal, pattern follows `ISSUE_*_PREFIX` constants): `approval_<id>`, `blocked_<id>`, `owner_conflict_<id>`, `ownership_claim_<id>`, `schema_too_new_<id>`, `doc_overwritten_<id>` (owner sees foreign content), `discovery_removed_<id>` (repeated follower deletions). All deleted on mirror removal, hub removal and device delete; add the prefixes to the cleanup list in `async_remove_all_devices` (`manager.py:158-163` only knows three).

### Pattern 6: Two-level validation and the execution-time denylist (TRU-03, D-03 to D-06)

**Validation levels.** `cv.SCRIPT_SCHEMA` is structural and instance-independent; `script.async_validate_actions_config` (`actions.async_validate_actions`) is instance-dependent. Spike result on 2026.9.4: a device action with an unknown local `device_id` makes the deep validation raise `InvalidDeviceAutomationConfig` (a `HomeAssistantError`), message `Unknown device 'abc123'`. If the deep check dropped the document (literal reading of D-06), a follower lacking that device would never see the mirror and the user would never learn why. Recommended: **the structural gate (`SCRIPT_SCHEMA`, size, depth, static denylist) decides drop/blocked; the deep validation runs at ingest for information and again in `ActionRunner.async_build_device`, where a failure is already surfaced as the existing per-trigger setup error** (`runner.py:52-61`, Repairs `action_failed_`). Show "does not validate on this instance" in the approval view. This is a small reading of D-06; confirm in Open Question 5.

**Static walker (D-04)** over the raw actions, in pure code: recursive over dict/list, depth-capped, collecting values of keys `action`, `service` and `service_template`. Static strings are normalized `strip().lower()` (core lowercases both: `cv.service` does `string(value).lower()` at `config_validation.py:639`; `ServiceRegistry.async_call` lowers domain and service at `core.py:2889-2890`) and checked against `DENIED_SERVICES` (exact `domain.service`) and `DENIED_DOMAINS` (whole domain). Strings containing `{{` or `{%` are collected as "templated", not denied. Also flag (do not deny) `scene:`, `device` actions and `event:` steps in the approval view as residual-risk step types `[ASSUMED]`.

**Execution-time hook (D-05): feasible, no core patching.** `ServiceParams` preparation does:
```python
# homeassistant/helpers/service.py:281-283 (2026.9.4, read this session)
if isinstance(domain_service, template.Template):
    try:
        domain_service = domain_service.async_render(variables)
```
and `Script` passes the validated dict straight in (`script.py:1053-1055`). So after `async_validate_actions_config` returns, walk the validated tree and replace every `Template` found under keys `action`/`service_template` with `GuardedTemplate(original.template, original.hass)` whose `async_render` checks the rendered name. `Template.__slots__ = ()`-style subclassing works (spike below). The guard must raise a plain `Exception` subclass, **not** `TemplateError` and not `HomeAssistantError`: `async_prepare_call_from_config` converts `TemplateError` into a plain `HomeAssistantError` (`service.py:285-288`), and `_handle_exception` lets `continue_on_error: true` swallow plain `HomeAssistantError` (`script.py:611-638`), whereas anything that is not a `HomeAssistantError` is re-raised (`script.py:633-635`). Spike result: with a `continue_on_error: True` denied step followed by another step, the run aborted and the second step did not run (`ok calls 1`, `shell calls 0`); the unguarded control executed both (`CONTROL ok calls 3 shell calls 1`).

`ActionRunner._async_run` already catches `Exception`, logs, and calls `report_failure` (`runner.py:181-184`), which satisfies "aborts the run and is surfaced (log + Repairs)"; add a denylist-specific issue text (translation key) by catching the dedicated exception type first. Only the device and trigger names go into the log and issue, never action data.

Insertion point: `ActionRunner._async_build_script` (`runner.py:72-102`) after `validated = await async_validate_actions(self._hass, sequence)`; pass `restricted=True` for mirrors only (D-03: owned actions stay unrestricted). Nested `choose/if/repeat/parallel/sequence` bodies are part of the same validated tree, so one recursive walk covers them; add a unit test that nests a templated service name three levels deep.

Residual risk (document, do not claim to solve): service calls made by an approved local `script.turn_on`/`automation.trigger` are outside the denylist by design; `device` actions and `scene` steps do not go through the templated-name path. Approval is the primary control, the denylist is defense in depth.

**Proposed denylist (D-03 fixed constant).** Service names below were verified to exist in the installed core `services.yaml` this session; the selection is policy and `[ASSUMED]` (Open Question 2):
- Whole domains: `shell_command`, `python_script`, `rest_command`, `command_line`, `hassio`, `backup`.
- Exact: `homeassistant.restart`, `homeassistant.stop`, `homeassistant.reload_all`, `homeassistant.reload_core_config`, `homeassistant.reload_config_entry`, `homeassistant.set_location`, `homeassistant.save_persistent_states`, `mqtt.publish`, `mqtt.dump`, `recorder.purge`, `recorder.purge_entities`.
- `mqtt.publish` is in the list because a mirror that can publish arbitrary MQTT could forge or clear config documents, discovery and state of other devices. `hassio` has `host_reboot`, `host_shutdown`, `backup_*`, `restore_*` and the renamed `app_*`/`addon_*` services (verified in `components/hassio/services.yaml`). `notify.*`, `script.*`, `automation.trigger` are deliberately not listed: banning `notify` would cripple the most common action, and calling local scripts is a legitimate use; both are visible in the approval YAML.

### Pattern 7: Tombstone, grace-window prune and registry cleanup (SYN-05, D-09, D-10)

- **Tombstone (live or retained empty config):** stop and unload the mirror's Script, unsubscribe state and test topics, remove `mirrors`/`approvals`/`last_acted`/`tripped` entries and all its issues, then clean registries. Persist with `async_delay_save`.
- **Registry cleanup.** Core clears entity and registry entries itself when the empty discovery arrives while the entity is loaded: `_async_process_discovery_update_and_remove` calls `_async_remove_state_and_registry_entry` (`mqtt/entity.py:1072-1083`). Leftovers exist only when this instance was offline or disabled during the delete. Clean up by device: `dr.async_get_device_by_identifier(("mqtt", f"mqtt_actions_{device_id}"), mqtt_entry_id)` then `dr.async_remove_device(device.id)`, which removes the device's entities (`entity_registry.py:1683-1694`). The identifier tuple domain is `mqtt` because core builds `identifiers={(DOMAIN, id_) ...}` with the MQTT domain (`mqtt/entity.py` `device_info_from_specifications`), and the value is our `f"{DOMAIN}_{spec.device_id}"` (`discovery.py:133`). **Do not call the deprecated `async_get_device`** (`report_usage ... breaks_in_ha_version="2027.8.0"`, `device_registry.py:1961-1992`); identifiers are scoped per config entry in 2026.9, so `async_get_device_by_identifier(identifier, config_entry_id)` is the unambiguous call. Only remove registry entries after the tombstone/prune decision is final: removing a device whose discovery still exists makes core clear the discovery topic (`async_removed_from_registry` publishes an empty retained payload, `mqtt/entity.py:1211-1220`), which would trigger the owner's healing republish. Guard `async_remove_device` against a missing device and a missing MQTT entry.
- **Prune (no end-of-replay marker exists; never delete on absence alone):**
  - Track `seen_this_session: set[str]` of device ids whose config document (live or retained) arrived since the last (re)connect, and `owner_status: dict[instance_id, "online"|"offline"|None]` from a wildcard subscription on `<base>/v1/instances/+/availability` (empty payload means unknown/cleared).
  - Start a prune timer (`async_call_later`, cancelled on stop) `PRUNE_GRACE_SECONDS` after setup and after each reconnect, **and when an owner's availability turns `online` later** (an owner that was offline when the follower started and deleted the device while the follower was away would otherwise leave the mirror forever).
  - At expiry, remove a mirror only if it was not seen this session **and** its pinned owner's status is `online`. Owner offline/unknown keeps the mirror (covers a wiped broker: availability is wiped too, and the owner republishes documents before `online`).
  - Stale retained `online` after an owner crash (the integration has no Last Will; see the `manager.py` module docstring) only affects this combination in the harmless direction: document absent and owner believed online means the owner removed it.
- **Accepted risk (D-09):** a forged empty payload on a config topic removes followers' mirrors and their approvals; the owner republishes (Pattern 2), but approval must be granted again. The cheap mitigation is the `approvals` key kept after a tombstone for a short retention `[ASSUMED]`; if not built, say so in the docs and rely on broker ACLs.

### Pattern 8: Delete flow and tombstone order (SYN-06, D-16)

- Owner order (D-16): discovery clear (after removing the device from the watcher's watch set), unsubscribe state/test, **config tombstone** (empty retained), state clear (empty retained). Extend `Manager._async_remove_device` (`manager.py:398-424`) and `_async_clear_topics`/`async_remove_all_devices` (`manager.py:125-163`) so the config topic joins the cleared set; a failed clear keeps the id in `_published` for retry exactly as today.
- **HA cannot veto the generic subentry delete.** `ConfigEntries.async_remove_subentry` has no hook and the websocket command `config_entries/subentries/delete` calls it directly (`config_entries.py:2700-2714`, `components/config/config_entries.py:831-855`). A delete step in our flow therefore cannot be the only door. Recommended: both paths funnel into the same reconcile-driven removal (`async_reconcile` already handles a missing subentry), and the flow step is the one that carries the all-instances wording. `[ASSUMED]` the frontend's own delete dialog text is not customizable and does not mention other instances; verify in UAT and document in the README that the generic delete performs the same broker-wide removal. See Open Question 1 for the alternative (unconfirmed generic delete orphans the device instead).
- **Flow shape.** Only `user` and `reconfigure` are entry points, so delete must be reachable from the reconfigure step: add a menu (edit / delete device) at the start of the Switch reconfigure, and a `delete_device` item in the existing Select menu. The confirm step shows `description_placeholders` with the device name and the instances that mirror it "as far as known": derive from instance availability topics plus which instances' mirrors cannot be observed (Phase 4 has the roster), so in Phase 3 the placeholder lists instance names seen `online` via a new `instances` cache of `{instance_id: name}`; the name is not in the availability payload today, so either list ids/count or add a retained `instances/<id>/info` document now `[ASSUMED]`; recommended minimum: state "all connected instances" plus the count of other online instances seen. Confirm step runs `hass.config_entries.async_remove_subentry(entry, subentry_id)` then `async_abort(reason="device_deleted")`.
- Impact on existing tests: the Switch reconfigure form tests (`tests/test_config_flow.py:256-410`, five tests assert `step_id == "reconfigure"` and the form) and Select menu tests must be updated for the extra menu level. A lower-impact alternative is an optional boolean "delete this device" field on the Switch reconfigure form; the menu is recommended for consistent UX.
- Followers' view of the delete: discovery empty first (core removes entities), then the config tombstone (Pattern 7), then state empty (logged at debug by the tracker since the subscription is gone).

### Pattern 9: Discovery healing (DSC-03, D-18)

Verified core behavior: for device-based discovery every component's `discovery_data[ATTR_DISCOVERY_TOPIC]` is the **device** topic (`mqtt/discovery.py:505-512`), and deleting any one entity from the registry calls `async_remove_discovery_payload`, publishing `None` retained to that topic (`mqtt/entity.py:758-768`, `1211-1220`). So one follower deleting one entity (for example a test button) clears the whole device discovery for **every** instance, including the owner's own entities, and core drops their registry entries (`mqtt/entity.py:1072-1083`). User customizations of those entities (area, entity id, labels) are then lost on all instances when the owner republishes `[ASSUMED]` consequence (the registry removal is verified, the exact customization loss is inferred).

Implementation:
- One wildcard subscription `f"{prefix}/device/+/config"` using `gateway.discovery_prefix()` at subscribe time; act only on **empty** payloads for ids in the owner's watch set; ignore non-empty echoes (own republishes) and other owners' ids. The prefix is read when subscribing; a runtime change of the MQTT discovery prefix needs a reload (document).
- **Remove the device from the watch set before the owner's own delete clears discovery**, otherwise the owner heals its own deletion (Pattern 8 ordering).
- **Trailing throttle, not drop.** Per device: at most one republish per `REPUBLISH_THROTTLE_SECONDS` (60 s start value); a removal inside the window schedules one republish at window end. A dropped second removal would leave the device gone until the next reconnect. Count removals in a rolling window; `discovery_removed_<id>` Repairs after a small threshold (for example 3 in 10 minutes) `[ASSUMED]` values.
- The republish is the normal `_async_publish_discovery(device)` for the owned device (including retired-component tombstones).

### Pattern 10: Hub removal choice (D-11)

HA invokes `async_remove_entry(hass, entry)` after the entry is unloaded and offers no dialog (`config_entries.py:1102-1105`). The choice must therefore be stored beforehand: add an `OptionsFlow` to the hub flow (`async_get_options_flow`) with a boolean, for example `delete_devices_on_remove`, default `False`, with a translated description that states the consequence; use plain `OptionsFlow` (not a reload-on-change variant). The existing hub guard test only forbids a reconfigure step. `async_remove_entry` then:
- **keep (default):** publish nothing destructive; leave config, discovery and state retained; the `offline` availability the manager published on unload stays, so orphans show `unavailable` and are never pruned (D-10 needs the owner seen online).
- **delete:** for every id in `published | subentries` clear discovery, config, state (existing `_async_clear_topics` extended) and clear the instance availability (`AvailabilityState.CLEARED`).
- **always:** remove the `Store` (mirrors, approvals, revs, baselines) and delete all issues of this integration (extend the prefix list). Mirror entities remain as core MQTT discovered entities of the owner's retained discovery; they simply stop running actions.
- Update the Phase 1/2 tests that assert clear-everything on removal (`tests/test_manager_breaker.py:613` and the removal tests in `tests/test_manager.py`).

### Pattern 11: FakeBroker multi-instance harness (spiked)

The mocked paho client of PHACC loops every publish straight back into the same `hass` with **the publish's own retain flag** (`pytest_homeassistant_custom_component/plugins.py:1105-1157`, `mock_client.publish.side_effect = _async_fire_mqtt_message`), and has no retained store. A real broker delivers replays with `retain=True` and live forwards with `retain=False`, including empty retained clears (pinned against Mosquitto by `tests/broker/test_retain_semantics.py`). Phase 3 depends on those semantics (tombstone arrives live and empty; echoes arrive live), so the multi-instance tier needs its own broker model.

**Spike (run this session, `ok`):** a `FakeBroker` (retained dict, subscriptions with wildcard matching, replay with `retain=True`, live delivery with `retain=False`, empty retained deletes) plus a `FakeGateway(broker, hass)` implementing the five `MqttGateway` methods, two real `hass` instances from `async_test_home_assistant()`, and two unmodified `Manager` objects. Only two patch points were needed: `custom_components.mqtt_actions.manager.MqttGateway` (factory returning the fake) and `custom_components.mqtt_actions.manager.STORE_KEY` (per-instance key). Result: one retained `ON` published on the state topic ran each instance's own `test.on` service exactly once (`CALLS 1 1`), with the expected retained keys on the broker. Confirmed details:
- `hass_storage` (PHACC `mock_storage`) is one dict keyed by `store.key`, so **two Managers must use distinct store keys** even with two `hass` objects (`common.py:1517-1547`); add optional `gateway` and `store_key` constructor parameters to `Manager` instead of patching (production default unchanged).
- The spike teardown printed a lingering-timer warning only; `tests/conftest.py` already sets `expected_lingering_timers` to `True`.
- Each extra `hass` needs `hass2.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)` so the custom integration loads (same thing the `enable_custom_integrations` fixture does for the main one).
- Two `hass` objects give true isolation of service registry, issue registry and entity/device registries, which matters for per-instance approval assertions; one `hass` with two Managers would share one issue registry (two followers would both write `approval_<id>`).

The fake must also provide `topic` on `IncomingMessage` (Pitfall 1), a `disconnect()`/`reconnect()` that fires `async_subscribe_connection_status` callbacks and re-delivers retained messages with `retain=True`, and an optional "drop retained" (broker wipe). Core MQTT discovery is not simulated; assert on published discovery topics and on Store/registry effects. Keep the existing `mqtt_mock` tier for single-instance follower tests: inject a retained document from "owner B" with `async_fire_mqtt_message(..., retain=True)` and assert `mqtt_mock.async_publish` calls.

### Pattern 12: Broker ACL example and its limits (TRU-04, D-07)

Mosquitto syntax `[CITED: mosquitto.org/man/mosquitto-conf-5.html]`: `user <username>`, `topic [read|write|readwrite|deny] <topic>`, `pattern ... <topic>` with `%c` (client id) and `%u` (username), `+` and `#` allowed, and "Any 'deny' topics are handled before topics that grant read/write access." The doc does not say what a denied publish returns at QoS 1; do not assume, test it (Pitfall 13).

What the locked layout allows (D-12 puts the device id, not the owner, in the path): per-instance binding works for `<base>/v1/instances/<instance_id>/availability` (instance id known at setup, use one MQTT user per instance whose name is the instance id, or explicit per-user lines). It does **not** work for `<base>/v1/devices/<device_id>/config`, because device ids are random and unknown when the ACL is written. So the example should: give every HA instance user `write` on `<base>/v1/devices/+/config`, `<base>/v1/devices/+/state`, `<base>/v1/devices/+/test`, the discovery prefix, and its own `instances/<its id>/availability`; give read-only and external publishers only `write <base>/v1/devices/+/state`; `deny write <base>/v1/devices/+/config` for everyone else. State plainly in the docs: within the HA user group any instance can overwrite any config topic (cooperative ownership), which is why approval is the real gate; HA instances also need write access to the discovery prefix because core clears discovery when an entity is deleted. `[ASSUMED]` exact file wording; a broker-tier test (Validation Architecture) should start mosquitto with the documented file and assert an allowed and a denied publish.

### Anti-Patterns to Avoid
- **Mirrors inside `self.devices`:** the first reconcile removes them and clears their state/discovery topics on the broker (Pitfall 2).
- **Trusting `doc["hash"]` or `doc["owner"]` from the wire:** recompute the hash; owner is text only.
- **Raising `TemplateError`/`HomeAssistantError` from the guard:** `continue_on_error` would swallow the denial (Pattern 6).
- **Replacing an issue to re-request approval:** `dismissed_version` survives replacement; delete, then create.
- **Publishing config after discovery or availability:** breaks the prune invariant.
- **Acting on an empty payload without the topic:** there is no device id in an empty payload.
- **Clearing registry entries while the discovery topic is still live:** core republishes a clear and triggers owner healing.
- **Dropping (instead of coalescing) throttled republishes.**

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Approval UI | A config-flow or service-based approval | Repairs fix flow (`repairs.py`) | Native, per-issue lifecycle, auto-delete on finish |
| Wildcard topic matching in `FakeBroker` | Own `+`/`#` matcher | `paho.mqtt.client.topic_matches_sub` | Edge cases (`#` at end, `$` topics); already installed |
| Service-call interception | Monkeypatching `service.async_prepare_call_from_config` or wrapping `hass.services` | `Template` subclass on the validated config | Scoped to our Scripts only, no global state; spike-verified |
| Mirror registry cleanup | Direct `.storage` edits, entity-by-entity loops over guessed ids | `dr.async_get_device_by_identifier` + `dr.async_remove_device` | Removes the device's entities atomically |
| YAML for the approval view | Hand-rendered text | `homeassistant.util.yaml.dump` | Correct quoting of hostile strings |
| JSON parse of untrusted documents | `json.loads` with deep recursion risk | `json_loads_object` (orjson) plus our own depth cap on walkers | orjson bounds parser nesting; walkers still need a cap |
| Schema/action validation | Own action schema | `cv.SCRIPT_SCHEMA` / `async_validate_actions` (existing `actions.py`) | Same engine as automations |
| Hash comparison | `==` on attacker-controlled strings where timing matters | `hmac.compare_digest` is unnecessary (no secret); plain equality is fine | Approval binds integrity of public content, not a secret |

**Key insight:** the hard parts here are protocol and lifecycle rules, not libraries. Everything that needs a library already exists in HA core; the risk is misusing core behaviors (dismissed issues, `continue_on_error`, registry removal side effects, wildcard subscriptions without topics).

## Common Pitfalls

### Pitfall 1: `IncomingMessage` has no topic
**What goes wrong:** the config wildcard cannot tell which device an empty payload (tombstone) belongs to; availability and discovery watchers cannot identify the instance or device.
**Why:** `IncomingMessage(payload, retain)` was designed for per-device subscriptions (`mqtt_gateway.py:17-21`).
**How to avoid:** add `topic: str` (default `""` keeps existing constructors valid; none exist in tests today, only `manager.py` type hints), fill it from `msg.topic` in the `_forward` callback, and have `FakeGateway` fill it. Parse ids with pure functions in `topics.py` and reject topics with unexpected segment counts.
**Warning signs:** handlers that accept a `device_id` from payload content for deletion decisions.

### Pitfall 2: Reconcile wipes mirrors
**What goes wrong:** `async_reconcile` removes any device in `self.devices` that is not a subentry and publishes empty discovery and state for it (`manager.py:217-219`, `398-424`); `async_start` also prunes baselines to owned ids (`manager.py:197-201`). Mirrors in `self.devices` would be deleted from the broker for everyone on the next subentry change or restart.
**How to avoid:** separate `mirrors` dict and explicit unions where persistence needs both; add a regression test that adds a mirror, changes an owned subentry and asserts no publishes on the mirror's topics.

### Pitfall 3: Own echo mistaken for a foreign write
Covered in Pattern 2. Symptoms: spurious `doc_overwritten_<id>` issue after quick edits. Keep a short history of published hashes and compare `rev`.

### Pitfall 4: Denial swallowed by `continue_on_error`
Covered in Pattern 6: raise a plain `Exception` subclass from the guard; test a denied step that has `continue_on_error: true` and assert the next step does not run.

### Pitfall 5: Deep validation drops documents that merely reference a local-only object
Covered in Pattern 6 (unknown `device_id` spike). Structural gate drops, deep validation informs.

### Pitfall 6: Owner republish ping-pong between two claimants
Two instances that both own one `device_id` each "heal" on seeing the other's document, forever. Per-device throttle and raise the issue once. Also the legit owner's first republish restores the retained document that a conflicting claimant overwrote; followers ignore the foreign document meanwhile (pinning).

### Pitfall 7: Stale mirror never pruned after owner returns
If the owner was offline when the follower subscribed, no grace window prune happens. Re-arm pruning on the owner's live `online` event, and keep the owner-side publish order config, discovery, availability.

### Pitfall 8: Dismissed approval issue stays dismissed
`async_get_or_create` replacement keeps `dismissed_version`; a changed action set would never re-prompt. Delete then create on hash change.

### Pitfall 9: Approval race with owner edit
The dialog shows hash H1, the owner publishes H2 before the user submits. The flow must compare the issue's `actions_hash` (and the current mirror hash) at submit and abort if they differ; never approve "current".

### Pitfall 10: Registry cleanup triggers discovery clear
`dr.async_remove_device` on a device with live MQTT entities makes core publish an empty retained discovery (`mqtt/entity.py:1211-1220`). Only clean up after the decision is final, and guard for missing device/MQTT entry. Use `async_get_device_by_identifier` (the old `async_get_device` logs a deprecation error path scheduled for 2027.8).

### Pitfall 11: Documents as a flood/DoS vector
Anyone with broker write access can create unlimited `devices/<random>/config` topics: unbounded Store growth, validation CPU, Repairs issues. Cap `MAX_MIRRORS`, `MAX_DOCUMENT_BYTES`, `MAX_ACTION_DEPTH`; do not raise an approval issue for documents without actions; wrap ingest in a broad `except Exception` with a logged, content-free message (deep validation of hostile structures can raise non-`Invalid` exceptions; the existing `ActionsInvalid` wrapper only catches `probatio.Invalid` and `HomeAssistantError`, `actions.py`). `[ASSUMED]` cap values.

### Pitfall 12: Markdown/log injection through names and YAML
`owner_name`, `name`, friendly names and action strings come from the broker. Enforce printable/length limits (log injection via newlines), neutralize code-fence sequences, and never put action data into logs or issue `translation_placeholders` other than the capped YAML of the approval flow.

### Pitfall 13: Assuming ACL-denied publishes fail visibly
The Mosquitto docs do not say what a denied QoS 1 publish returns. Do not rely on an error in HA logs; the broker-tier test should assert on the retained state after a denied publish.

### Pitfall 14: Mirror entities lose customizations on healing
A follower deleting an entity causes an empty discovery, core removes registry entries everywhere, and the owner's republish recreates them fresh. Document it; it is the price of D-18.

### Pitfall 15: Tombstone ordering on delete
If the state topic were cleared before followers unsubscribe, every tracker logs an empty payload. Follow D-16 order; the tracker already treats empty payloads as debug noise (`manager.py:588-595`).

## Code Examples

### GuardedTemplate (verified by spike on HA 2026.9.4, trimmed)
```python
# Source: spike run this session; hook location homeassistant/helpers/service.py:281-283
from homeassistant.helpers import template as template_helper


class DeniedServiceCallError(Exception):
    """Plain Exception on purpose: continue_on_error cannot swallow a non-HomeAssistantError."""


class GuardedTemplate(template_helper.Template):
    __slots__ = ()

    def async_render(self, variables=None, parse_result=True, limited=False, strict=False, log_fn=None, **kwargs):
        result = super().async_render(variables, parse_result, limited, strict, log_fn, **kwargs)
        if isinstance(result, str) and is_denied(result.strip().lower()):
            raise DeniedServiceCallError(result)
        return result


def guard_actions(node):
    """Return a copy of a validated action tree with service-name templates replaced by guarded ones."""
    if isinstance(node, dict):
        return {
            key: GuardedTemplate(value.template, value.hass)
            if key in ("action", "service_template") and isinstance(value, template_helper.Template)
            else guard_actions(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [guard_actions(item) for item in node]
    return node
```
Spike output: `types: <class 'homeassistant.helpers.template.Template'>` before wrapping; with the guard `ERR <class 'test_spike.DeniedServiceCall'> shell_command.x`, `ok calls 1 shell calls 0`; control without the guard `ok calls 3 shell calls 1`. Add a regression test that fails loudly if a future core stops calling `async_render` on the validated `Template` for the service name (this is the version-coupling risk; fall back to "reject templated service names in mirrors" if it ever breaks).

### Fix flow skeleton
```python
# Source: developers.home-assistant.io/docs/core/platform/repairs/ ; components/repairs/issue_handler.py
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult


class ApprovalRepairFlow(RepairsFlow):
    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        view = manager.approval_view(self.data["device_id"])        # current mirror; None if gone
        if view is None or view.actions_hash != self.data["actions_hash"]:
            return self.async_abort(reason="changed")               # ABORT keeps the issue; the new one takes over
        if user_input is not None:
            manager.approve(view.device_id, view.actions_hash)      # stores the DISPLAYED hash
            return self.async_create_entry(data={})                 # issue is deleted by finish_flow
        return self.async_show_form(step_id="confirm", data_schema=probatio.Schema({}),
                                    description_placeholders=view.placeholders)


async def async_create_fix_flow(hass, issue_id, data) -> RepairsFlow:
    return ApprovalRepairFlow()
```
Approve/dismiss semantics: closing the dialog leaves the mirror paused; there is no "reject" write (deny is the default state).

### FakeBroker core (retain semantics verified against Mosquitto tests)
```python
# Source: spike this session; real-broker semantics pinned by tests/broker/test_retain_semantics.py
from paho.mqtt.client import topic_matches_sub

class FakeBroker:
    def publish(self, topic: str, payload: str, retain: bool) -> None:
        if retain:
            self.retained.pop(topic, None) if payload == "" else self.retained.__setitem__(topic, payload)
        for gateway, pattern, callback in list(self.subscriptions):
            if topic_matches_sub(pattern, topic):
                gateway.hass.loop.call_soon(callback, IncomingMessage(payload=payload, retain=False, topic=topic))

    def replay(self, gateway, pattern, callback) -> None:          # on subscribe and after reconnect
        for topic, payload in list(self.retained.items()):
            if topic_matches_sub(pattern, topic):
                gateway.hass.loop.call_soon(callback, IncomingMessage(payload=payload, retain=True, topic=topic))
```

### Canonical hash
```python
# Source: stdlib; own wire contract (document this exact call in document.py)
def canonical_hash(content: dict[str, Any]) -> str:
    text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()
```

### Device removal helper (registry lookup that is valid in 2026.9)
```python
# Source: helpers/device_registry.py:2013-2024 (async_get_device_by_identifier), 4083 (async_remove_device)
registry = dr.async_get(hass)
device = registry.async_get_device_by_identifier(("mqtt", f"mqtt_actions_{device_id}"), mqtt_entry.entry_id)
if device is not None:
    registry.async_remove_device(device.id)   # also removes its entities (entity_registry.py:1683-1694)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `dr.async_get_device(identifiers=...)` | `async_get_device_by_identifier(identifier, config_entry_id)` | 2026.9 (old call reports usage, breaks 2027.8) | Use the new call for registry cleanup |
| `voluptuous` | `probatio` (alias in core) | 2026.9 | Already the project rule |
| Per-component discovery | Device-based discovery (one topic per device) | Phase 1 choice | One entity deletion clears the whole device topic (Pattern 9) |
| `hassio` add-on service names | `app_*` services alongside `addon_*` | present in 2026.9.4 `hassio/services.yaml` | Domain-wide `hassio` denial avoids tracking renames |

**Deprecated/outdated:** `async_get_device` (above). HA 2026.10 is imminent (STACK.md watch-list); re-run the suite and the `GuardedTemplate` regression test on bump.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The proposed denylist content (domains/exact names, leaving `notify`, `script`, `automation.trigger` allowed) is the right policy | Pattern 6 | Too strict breaks legitimate actions; too loose weakens defense in depth. Service names themselves are verified; the choice needs user confirmation |
| A2 | Tunables: `PRUNE_GRACE_SECONDS` around 30 s, 60 s republish throttle (D-18 start value), `MAX_MIRRORS` around 100, `MAX_DOCUMENT_BYTES` around 256 KiB, `MAX_ACTION_DEPTH` around 16, removal-hint threshold 3 in 10 min | Patterns 1, 7, 9; Pitfall 11 | Mis-tuned windows cause late pruning or false prune; caps too low reject real documents |
| A3 | HA frontend renders Repairs fix-flow descriptions as markdown, so a fenced YAML placeholder displays correctly and fence-neutralizing is sufficient | Pattern 5 | Unreadable approval view or markdown injection; needs manual UAT |
| A4 | The frontend's generic subentry Delete dialog is not customizable and always available | Pattern 8 | If customizable or blockable, the delete design gets simpler |
| A5 | `actions_hash` should include `run_on_startup` and exclude run mode/breaker limits | Pattern 1 | Changes to these would wrongly skip or force re-approval |
| A6 | Static denylist hit makes a mirror blocked (visible, non-approvable) rather than silently dropped | Pattern 5 | Users may expect approval with a warning instead |
| A7 | Deep-validation failure (unknown local device, missing integration) keeps the mirror stored and only informs, instead of dropping (reading of D-06) | Pattern 6 | If the user meant strict drop, followers lacking a device never see the mirror |
| A8 | Follower customizations of mirrored entities are lost when healing republishes | Pattern 9, Pitfall 14 | Only a documentation consequence |
| A9 | Devices with no actions need no approval | Pattern 4 | If the user wants an explicit approval even for empty devices, one extra rule |
| A10 | Approvals kept briefly after a tombstone (optional mitigation) are worth building | Pattern 7 | Forged tombstones force re-approval; acceptable if documented |
| A11 | The delete confirm step can list only count/names of instances seen online (no roster until Phase 4) | Pattern 8 | Weaker wording than D-16 "listing the instances" |
| A12 | Denied QoS 1 publishes under a Mosquitto ACL are silently dropped | Pitfall 13 | The ACL test must assert on retained state, not on publish errors |
| A13 | Test-button topic behavior on mirrors (subscribe and run when approved) | Pattern 4 | Decision needed (Open Question 4) |
| A14 | `residual-risk` step types (`scene`, `device`, `event`) flagged but not denied | Pattern 6 | A hostile approved document could still use them; approval is the control |

## Open Questions

1. **Generic HA subentry delete cannot be vetoed (affects SYN-06 wording).**
   - Known: `async_remove_subentry` has no hook and the websocket command calls it directly; our flow step can carry the warning but cannot be the only door.
   - Unclear: whether the user wants an unconfirmed generic delete to tombstone everywhere (recommended; one code path, matches Phases 1 and 2) or to orphan the device (safer, but leaves an unowned device and breaks "removed everywhere").
   - Recommendation: unify both paths on reconcile, put the all-instances warning in the flow step and the README, verify the frontend dialog in UAT.
2. **Denylist contents** (A1). Recommendation: the list in Pattern 6, confirmed by the user before execution because it is a fixed, non-extendable constant (D-03).
3. **Foreign tombstone forces re-approval** (A10). Recommendation: accept per D-09 and document; optionally keep approvals briefly.
4. **Test buttons on mirrors.** Recommendation: mirrors subscribe to the test topic and run only when approved, so the button works on every approved instance; confirm that pressing Test on one instance running actions on others is intended.
5. **D-06 reading.** Structural gate drops/blocks; deep validation informs (A7). Confirm.
6. **CLAUDE.md "local opt-in flag" wording vs D-01.** Per-device approval is the opt-in; no hub flag exists. Confirm no additional hub switch is wanted.
7. **Instance names in the delete confirmation.** The availability payload carries no name; decide between count-only (A11) and adding a small retained instance info document now (scope creep toward Phase 4 OPS-03).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (uv-managed `.venv`) | everything | yes | 3.14.7 | — |
| uv | test/lint runs | yes | 0.12.7 | — |
| Home Assistant core (in `.venv`) | API verification, tests | yes | 2026.9.4 | — |
| pytest-homeassistant-custom-component | tests | yes | 0.13.367 | — |
| Ruff | lint | yes | 0.16.9 | — |
| mosquitto | broker tier, ACL test | yes | 2.1.2 (`/usr/bin/mosquitto`) | tests skip when missing (existing fixture) |
| mosquitto_pub | manual checks | yes | — | paho-based test client |
| Graph (`.planning/graphs`) | optional context | no | — | none needed |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 via PHACC 0.13.367, `asyncio_mode = "auto"` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, markers include `broker` |
| Quick run command | `uv run pytest tests/test_document.py -x -q` (substitute the file under change) |
| Full suite command | `uv run pytest -q` (426 tests pass in about 22 s today) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYN-01 | Owner publishes one retained, versioned document per device (keys, hash, rev, order config to discovery to availability) | unit + manager (`mqtt_mock`) | `uv run pytest tests/test_sync_owner.py -x` | no, Wave 0 |
| SYN-01 | Canonical hash stable across key order, missing-default keys, unicode; wire fixture | unit | `uv run pytest tests/test_document.py -x` | no, Wave 0 |
| SYN-02 | Retained document creates a mirror with state/test subscriptions, cached in Store, survives restart | manager | `uv run pytest tests/test_sync_follower.py -x` | no, Wave 0 |
| SYN-03 | Owner pinning, conflict Repairs, owner-claim republish with throttle, no edit path for mirrors | manager + multi-instance | `uv run pytest tests/test_sync_follower.py tests/test_multi_instance.py -x` | no, Wave 0 |
| SYN-04 | Republish on every reconnect; wiped broker healed | multi-instance | `uv run pytest tests/test_multi_instance.py -k reconnect -x` | no, Wave 0 |
| SYN-05 | No delete on absence; tombstone removes at once; prune only with owner online; re-armed by owner `online` | multi-instance | `uv run pytest tests/test_multi_instance.py -k prune -x` | no, Wave 0 |
| SYN-06 | Delete flow confirmation wording, order, config+discovery+state tombstones, retry on broker failure | flow + manager | `uv run pytest tests/test_config_flow_delete.py tests/test_sync_owner.py -k delete -x` | no, Wave 0 |
| TRU-01 | Unapproved mirror runs nothing for live state, test button, run-on-startup | manager | `uv run pytest tests/test_trust.py -k unapproved -x` | no, Wave 0 |
| TRU-02 | Approval flow binds hash; changed actions pause and re-prompt; dismissed issue does not hide re-prompt; race abort | repairs flow (`hass_client`/flow manager) | `uv run pytest tests/test_repairs_flow.py -x` | no, Wave 0 |
| TRU-03 | Schema validation gate, static walker nesting, `GuardedTemplate` incl. `continue_on_error`, blocked state, caps | unit + runner | `uv run pytest tests/test_trust.py tests/test_document.py -x` | no, Wave 0 |
| TRU-04 | ACL example enforced by a real mosquitto | broker | `uv run pytest tests/broker/test_acl.py -x` | no, Wave 0 |
| STA-03 | UI change on any instance and external publish run actions on every approved instance | multi-instance | `uv run pytest tests/test_multi_instance.py -k fanout -x` | no, Wave 0 |
| DSC-03 | Entity deletion clears discovery; owner republishes once per window (trailing), no self-heal on own delete, repeated-removal hint | manager + multi-instance | `uv run pytest tests/test_sync_owner.py -k discovery -x` | no, Wave 0 |
| (D-11) | Hub removal keep vs delete; Store and issues always removed | manager | `uv run pytest tests/test_manager_breaker.py tests/test_hub_removal.py -x` | partly (existing removal tests must change) |
| (FND-04) | en/de parity for all new issue, flow and options strings | unit | `uv run pytest tests/test_translations.py -x` | yes, extend `REQUIRED_KEYS` |

### Sampling Rate
- **Per task commit:** the quick command for the touched module plus `uv run ruff check custom_components tests`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** full suite green (including `-m broker` tests with mosquitto present) before `/gsd-verify-work`; manual UAT of the approval dialog rendering and the generic delete dialog (A3, A4)

### Wave 0 Gaps
- [ ] `custom_components/mqtt_actions/mqtt_gateway.py`: `IncomingMessage.topic` (Pitfall 1)
- [ ] `Manager.__init__` optional `gateway` and `store_key` parameters (replaces the spike's patch points)
- [ ] `tests/fake_broker.py`: `FakeBroker`, `FakeGateway`, reconnect/wipe controls, two-`hass` instance factory with teardown, per-instance store key
- [ ] `tests/test_document.py`, `tests/test_sync_owner.py`, `tests/test_sync_follower.py`, `tests/test_trust.py`, `tests/test_repairs_flow.py`, `tests/test_config_flow_delete.py`, `tests/test_multi_instance.py`, `tests/test_hub_removal.py`, `tests/broker/test_acl.py`
- [ ] Update existing tests that encode removed behavior: Phase 1 hub-removal clear-everything (`tests/test_manager_breaker.py:613` and related), Switch reconfigure tests if the reconfigure step becomes a menu (`tests/test_config_flow.py:256-410`), Select menu option lists (`tests/test_config_flow_select.py`)
- [ ] Extend `tests/test_translations.py` `REQUIRED_KEYS` for new issues, fix-flow steps, options flow and delete steps

## Security Domain

`security_enforcement` is enabled (`config.json`: `"security_enforcement": true`, `"security_asvs_level": 1`, `"security_block_on": "high"`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (broker auth is the user's; we store no credentials) | Reuse HA's MQTT connection; never add credentials |
| V3 Session Management | no | — |
| V4 Access Control | yes | Per-device, per-instance approval bound to `actions_hash`; owner-only edit/delete (mirrors are not subentries); owner pinning; broker ACLs as the real enforcement (Pattern 12) |
| V5 Input Validation | yes | Size cap, strict document schema, `cv.SCRIPT_SCHEMA`, depth cap, printable/length rules on names, topic-segment match, broad exception guard at the ingest boundary |
| V6 Cryptography | limited | sha256 from `hashlib` for integrity of public content; no secrets, no hand-rolled crypto; signed config is v2 (SEC-01) |
| V7 Logging | yes | Names only in logs and issues; never action data (existing T-01-10 rule); truncated payload repr for unknown payloads (`MAX_LOGGED_PAYLOAD_LENGTH`) |
| V12 Files/Resources | yes | Caps on mirror count and document size; no unbounded Repairs issues |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Forged owner document (anyone with broker write) | Spoofing / Tampering | Approval gate by default; pinning; `doc.device_id == topic`; ACL docs; owner republish and conflict issue |
| Approved document later changed to malicious actions | Elevation | `actions_hash` binding; change unloads the Script and re-prompts (delete-then-create the issue) |
| Templated service name resolving to a denied service | Elevation | `GuardedTemplate` at execution time; static walker at ingest; plain-`Exception` abort beats `continue_on_error` |
| `mqtt.publish` used by a mirror to forge other devices' config/state/discovery | Tampering / Elevation | `mqtt.publish`/`mqtt.dump` in the denylist |
| Document flood, huge or deeply nested payloads | DoS | `MAX_DOCUMENT_BYTES`, `MAX_MIRRORS`, `MAX_ACTION_DEPTH`, orjson parse, broad exception guard |
| Markdown/log injection via names, owner name, YAML | Tampering / Info | Printable and length rules, fence neutralization, capped YAML placeholder |
| Forged tombstone removes mirrors and approvals | DoS | Owner republishes; optional short approval retention; ACLs |
| State exfiltration through approved templates | Info disclosure | Approval view shows full YAML and flags templates; `notify` visibility (not denied, A1) |
| Replay of retained documents causing unintended execution | Tampering | Mirror actions only run on live or baseline-rule state edges (existing tracker); approval does not retroactively run anything |
| Follower entity deletion clearing discovery for everyone | DoS | Owner watcher republish with trailing throttle and repeated-removal hint |

## Sources

### Primary (HIGH confidence)
- Installed HA 2026.9.4 source under `/home/akentner/Projects/homeassistant-mqtt-actions-integration/.venv/lib/python3.14/site-packages/homeassistant/`: `const.py:24-26`; `helpers/service.py:261-295`; `helpers/script.py:575-640,1049-1100`; `helpers/issue_registry.py` (`async_create_issue`, `async_get_or_create`); `components/repairs/issue_handler.py:28-100`; `components/mqtt/discovery.py:380-525`; `components/mqtt/entity.py:758-778,960-985,1072-1083,1150-1260,1275-1330`; `helpers/device_registry.py:1961-2060,4083-4108`; `helpers/entity_registry.py:1243-1251,1672-1700`; `config_entries.py:1102-1105,2700-2714,3671-3746,3748-3800,3987-4017`; `components/config/config_entries.py:831-855`; `helpers/config_validation.py:636-643`; `core.py:2888-2890`; `util/yaml/__init__.py`; `util/json.py:31-58`; services.yaml of `homeassistant`, `hassio`, `mqtt`, `shell_command`, `python_script`, `rest_command`, `recorder`, `backup`, `command_line`, `script`, `automation`, `notify`, `system_log`
- PHACC 0.13.367 `plugins.py:1087-1160`, `common.py:222-260,460-485,1517-1547`
- Spike runs this session (scratchpad `test_spike*.py`, removed from the repo): unknown `device_id` validation, `GuardedTemplate` vs `continue_on_error`, two-`hass` isolation, FakeBroker with two Managers
- Repo files read in full: `manager.py`, `runner.py`, `discovery.py`, `mqtt_gateway.py`, `model.py`, `state.py`, `config_flow.py`, `__init__.py`, `actions.py`, `const.py`, `topics.py`, `tests/conftest.py`, `tests/broker/*`, `.planning/research/ARCHITECTURE.md`, PITFALLS.md (pitfalls 4-9, security/UX tables, recovery), `01-CONTEXT.md`, `02-CONTEXT.md`, `03-CONTEXT.md`, `REQUIREMENTS.md`, `STATE.md`
- https://developers.home-assistant.io/docs/core/platform/repairs/ (fix flows, persistence, dismissal)
- https://mosquitto.org/man/mosquitto-conf-5.html (ACL syntax)

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` and `SUMMARY.md` (own synthesis of MQTT patterns, flagged MEDIUM there)

### Tertiary (LOW confidence)
- None used as authority; frontend rendering and dialog behavior are explicitly `[ASSUMED]` (A3, A4)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new packages; every API read in the installed 2026.9.4 source
- Architecture: MEDIUM-HIGH - platform behaviors verified and two spikes passed; protocol rules (echo/rev/prune) are own design with explicit edge-case analysis
- Pitfalls: HIGH - most derive from code read this session (reconcile, gateway, issue registry, core discovery removal, continue_on_error)

**Research date:** 2026-10-01
**Valid until:** 2026-10-31 (HA 2026.10 lands in early October; re-run the `GuardedTemplate` regression test and the suite on the bump)
