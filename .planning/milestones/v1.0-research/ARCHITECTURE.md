# Architecture Research

**Domain:** Home Assistant custom integration: MQTT state changes -> locally executed HA action sequences, with a central retained config in the broker replicated to all HA instances
**Researched:** 2026-09-28
**Confidence:** MEDIUM-HIGH (HA/MQTT platform facts verified against HA source and docs = HIGH; cross-instance protocol design is our own synthesis of standard MQTT patterns = MEDIUM, flagged inline)

There is no established off-the-shelf pattern for "replicated action config over MQTT". The closest analogues are (a) Zigbee2MQTT/Tasmota-style retained-config-plus-discovery publishers, and (b) HA's own MQTT discovery. The architecture below combines those with HA's `Script` helper and config subentries. Where a statement is a design recommendation rather than a verified platform fact, it is marked **[design]**.

## Standard Architecture

### System Overview

Key insight: **this integration owns no entities.** Entities come from core MQTT discovery, which every HA instance on the broker already runs. The integration is a *controller* (config store + publisher + subscriber + action runner) sitting next to core MQTT, not a platform provider.

```
   HA instance A (OWNER of dev-1)                     HA instance B (FOLLOWER of dev-1)
┌───────────────────────────────────────┐        ┌───────────────────────────────────────┐
│ UI layer                              │        │ UI layer                              │
│  ConfigFlow(hub) + SubentryFlow(dev)  │        │  ConfigFlow(hub) + read-only view     │
│  Services: retrigger  Repairs         │        │  Services: retrigger  Repairs(approve)│
├───────────────────────────────────────┤        ├───────────────────────────────────────┤
│ Domain core (pure, no I/O)            │        │ Domain core (pure, no I/O)            │
│  DeviceSpec models, wire schema,      │        │  same package                         │
│  topic map, hashing                   │        │                                       │
├───────────────────────────────────────┤        ├───────────────────────────────────────┤
│ Managers                              │        │ Managers                              │
│  DeviceRegistry (owned + mirrored)    │        │  DeviceRegistry (mirrored only)       │
│  SyncManager   (publish / mirror)     │        │  SyncManager   (mirror + trust gate)  │
│  DiscoveryPublisher (owner only)      │        │  (no discovery publishing)            │
│  StateTracker  (dedupe, baseline)     │        │  StateTracker                         │
│  ActionRunner  (Script per trigger)   │        │  ActionRunner                         │
├───────────────────────────────────────┤        ├───────────────────────────────────────┤
│ MqttGateway (thin wrapper)            │        │ MqttGateway                           │
│  homeassistant.components.mqtt        │        │  homeassistant.components.mqtt        │
│  async_subscribe / async_publish      │        │  async_subscribe / async_publish      │
├───────────────────────────────────────┤        ├───────────────────────────────────────┤
│ Core MQTT discovery -> mqtt switch /  │        │ Core MQTT discovery -> mqtt switch /  │
│ select entities (NOT ours)            │        │ select entities (NOT ours)            │
└──────────────────┬────────────────────┘        └──────────────────┬────────────────────┘
                   │                                                │
                   └──────────────────┬─────────────────────────────┘
                                      ▼
                     ┌───────────────────────────────────┐
                     │ MQTT broker (only shared thing)   │
                     │  retained: config, state, discov. │
                     │  transient: retrigger             │
                     └───────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `config_flow.py` (hub) | One config entry per HA instance: generates `instance_id`, sets base topic, trust policy | `ConfigFlow` with `single_config_entry: true` in manifest; `async_get_supported_subentry_types` returns `{"device": DeviceSubentryFlow}` |
| `DeviceSubentryFlow` | Create/reconfigure **owned** devices: domain choice -> Switch (name + on/off actions) or Select (name + options list, each StateValue/FriendlyName/actions) | `ConfigSubentryFlow` (HA >= 2025.3); `ActionSelector` for sequences; multi-step / menu loop for select options |
| Domain core (`models.py`, `schema.py`, `topics.py`) | Immutable `DeviceSpec` dataclasses, wire-format (voluptuous) schema with `schema_version`, canonical JSON + content hash, pure topic builder/parser | No HA imports except `cv`; fully unit-testable |
| `MqttGateway` | Only place that imports `homeassistant.components.mqtt`; tracks unsubscribe callables; waits for client; exposes connection-status hook; the seam for a fake in-memory broker in tests | `mqtt.async_wait_for_mqtt_client`, `mqtt.async_subscribe`, `mqtt.async_publish`, `mqtt.async_subscribe_connection_status` |
| `DeviceRegistry` | In-memory index `device_id -> Device(spec, owner, rev, hash, origin: owned/mirrored, trust_state)`. Owned devices are derived from subentries; mirrored from `Store` | `homeassistant.helpers.storage.Store` for mirrored devices + last-acted state |
| `SyncManager` | Owner: publish/unpublish retained config on change and on every MQTT (re)connect. Follower: apply incoming config, pin owner, enforce trust gate, prune tombstones | Wildcard subscription `<base>/v1/devices/+/config`; reconcile pattern (desired vs published) |
| `DiscoveryPublisher` | Owner only. Builds MQTT discovery payload per device (unique_id, device block, origin, topics, select templates); publishes retained; empty payload on delete | Diff against last-published hash |
| `StateTracker` | Parses state-topic messages, dedupes, decides "is this a change worth acting on" (retain-flag aware), persists last-acted state | Wildcard subscription `<base>/v1/devices/+/state`; per-device state cache incl. unknown devices |
| `ActionRunner` | Turns a state transition (or re-trigger) into a `Script` run; serial per device; loop circuit breaker | `homeassistant.helpers.script.Script`, validated by `cv.SCRIPT_SCHEMA` + `script.async_validate_actions_config` |
| `services.py` | `mqtt_actions.retrigger` (optionally per device) publishing a transient request; handler on all instances | `hass.services.async_register` (register in `async_setup`, not per entry) |
| `repairs.py` | Approval of remote-provided/changed actions; ownership-conflict and loop-breaker issues | HA Repairs (`RepairsFlow`) / issue registry |
| `diagnostics.py` | Redacted dump of registry + topic state | `async_get_config_entry_diagnostics` |

## Recommended Project Structure

```
custom_components/mqtt_actions/
├── __init__.py            # async_setup (services), async_setup_entry (wire managers), unload
├── manifest.json          # dependencies: ["mqtt"], config_flow, integration_type: hub, iot_class: local_push, version
├── const.py
├── config_flow.py         # hub flow + subentry flow registration
├── subentry_flows.py      # DeviceSubentryFlow (switch/select steps, ActionSelector)
├── models.py              # DeviceSpec, SwitchSpec, SelectSpec, Option (frozen dataclasses)
├── schema.py              # wire-format schemas, schema_version, canonical hash
├── topics.py              # pure topic build/parse
├── mqtt_gateway.py        # sole importer of components.mqtt
├── registry.py            # DeviceRegistry + Store persistence
├── sync.py                # SyncManager (owner publish / follower mirror / prune)
├── discovery.py           # DiscoveryPublisher
├── state.py               # StateTracker
├── runner.py              # ActionRunner (+ circuit breaker)
├── services.py / services.yaml
├── repairs.py
├── diagnostics.py
├── strings.json + translations/{en,de}.json
tests/                     # pytest-homeassistant-custom-component; FakeBroker implementing MqttGateway
hacs.json  .github/workflows/{hassfest,hacs,ci}.yml
```

### Structure Rationale

- **Domain core has no I/O:** wire schema, topics and hashing are where cross-instance compatibility bugs live; keeping them pure makes them cheap to test and version.
- **`mqtt_gateway.py` is the only MQTT seam:** allows an in-memory `FakeBroker` that connects two or three `Manager` stacks, which is the only realistic way to test ownership, echo and tombstone behavior without three real HA instances. **[design]**
- **Owned = subentries, mirrored = `Store`:** subentries give native HA UX (add/reconfigure/delete) but represent *user-authored* config. Broker-supplied config must not appear as user-editable config, and must survive restart before the broker replays it. **[design]**

## Topic Layout

`<base>` defaults to `mqtt_actions`; `v1` is the wire-schema major. `device_id` is an immutable generated id (short uuid4 hex; alnum only, valid as a discovery `object_id`), never derived from the name, so rename does not move topics. **[design]**

| Topic | Retained | QoS | Writer | Purpose |
|-------|----------|-----|--------|---------|
| `<base>/v1/devices/<device_id>/config` | yes | 1 | owner only | Central config document: `schema_version`, `device_id`, `owner` (instance_id), `owner_name`, `rev`, `domain`, `name`, `options`/actions (raw ActionSelector output). Empty payload = delete. |
| `<base>/v1/devices/<device_id>/state` | yes | 1 | anyone (UI via discovery command, or external systems) | Authoritative state; plain payload (`ON`/`OFF` or select StateValue) so external systems can drive it |
| `<base>/v1/retrigger` | **no** | 1 | any instance | Transient `{request_id, origin, device_id or null}` request |
| `homeassistant/<component>/mqtt_actions/<device_id>/config` | yes | 1 | owner only | Standard MQTT discovery (prefix must follow the owner's MQTT `discovery_prefix`; default `homeassistant`) |
| `<base>/v1/instances/<instance_id>` (optional, later) | yes | 1 | that instance | Name/version/session nonce for diagnostics and duplicate-instance-id detection |

Design choices and why:

- **One retained document per device, not one monolithic config.** A single shared document forces read-modify-write and re-creates exactly the multi-writer race the ownership model exists to avoid. Per-device topics have a single writer each; delete is a plain empty retained publish; followers subscribe to one wildcard. **[design] MEDIUM-HIGH**
- **Config is a separate topic from discovery.** MQTT discovery payloads are validated against the entity schema (extra keys such as action sequences are not accepted) and are readable by anything on the broker. Actions live only in the `config` topic, which can get its own ACL. **[design]**
- **Do not put `retain` on a topic where a replay would cause side effects.** Only `state` is both retained and action-relevant; replay handling is defined below. `retrigger` is never retained so late joiners do not re-execute.

### Command vs. state topic (decision needed in requirements)

The project says state changes originate from the UI (command topic) and external MQTT (state topic). Core MQTT `switch`/`select` with `state_topic` set are non-optimistic: the entity changes only when a state-topic message arrives (verified in HA docs). Someone must therefore turn a command into a state message.

| Option | How | Verdict |
|--------|-----|---------|
| **A (recommended): `command_topic == state_topic`, `retain: true` on the entity** | UI publishes the value to `.../state`; every subscriber (incl. the publisher) sees it and the entity confirms only after the broker round trip. No bridge, no dependency on the owner being online. | Simplest, no SPOF, fewer echo paths. External systems write the same topic. **[design] MEDIUM** |
| B: distinct `.../set` and `.../state`, owner bridges set -> state | Owner validates and republishes. Cleaner semantic separation. | Owner offline = follower UI dead (contradicts Core Value "reliably on every instance"). |
| C: every instance bridges set -> state | Idempotent-looking, but N publishes per command; rapid ON/OFF from two bridges interleave into spurious transitions. | Reject. |

If the roadmap insists on a visible `/set` topic, choose B and add owner-offline handling; do not choose C.

## Architectural Patterns

### Pattern 1: Controller beside core MQTT (no own entities)

**What:** Integration publishes MQTT Discovery; core MQTT on each instance creates the entities. The integration only reacts to the state topic.
**When:** Always (matches requirement "MQTT Discovery published for every entity").
**Trade-offs:** (+) "other instances create the same devices" is largely delivered by core MQTT discovery for free; no `switch.py`/`select.py` platform code. (-) Entities belong to the MQTT integration, so a follower that uninstalls this integration keeps inert entities; a follower with MQTT discovery disabled gets no entities (document as prerequisite). Entity/device naming is fixed by the discovery payload.

### Pattern 2: Single-writer-per-key retained state (ownership as conflict avoidance)

**What:** Each `devices/<id>/config` and its discovery topic has exactly one legitimate writer (`owner`). Everyone else is read-only and never republishes on receive.
**When:** All config and discovery traffic.
**Trade-offs:** (+) No conflict resolution, no merge, no republish loops. (-) Ownership is cooperative, not enforced by the broker; owner loss orphans devices (see Pitfalls/decisions).

```python
# Follower/owner decision on an incoming retained config message  [design]
def on_config(topic_device_id, payload):
    if not payload:                                   # tombstone
        return handle_delete(topic_device_id)
    doc = schema.parse(payload)                       # rejects unknown schema_version
    local = registry.get(doc.device_id)
    if doc.owner == instance_id:                      # echo of own publish, or conflict
        if local and local.hash == doc.hash:
            return                                    # own echo: ignore
        return republish_local_truth_and_raise_issue(local, doc)
    if local and local.owner != doc.owner:            # owner pinning: first owner wins
        return raise_conflict_issue(local, doc)
    if local and local.hash == doc.hash:
        return                                        # idempotent
    apply_mirror(doc)                                 # subject to trust gate
```

### Pattern 3: Reconcile instead of react (desired vs published)

**What:** `SyncManager.reconcile()` computes desired = all owned subentries; compares with what was last published (tracked set + hashes); publishes diffs and empty payloads for removed ids. Triggered on entry setup, subentry add/update/remove (config entry update listener), and on every MQTT reconnect (forced republish).
**When:** Owner side.
**Trade-offs:** (+) Handles subentry deletion without needing a "before delete" hook, handles broker restart that lost retained messages, handles crashes mid-publish. (-) Forced republish on reconnect causes followers to see identical documents; they no-op via hash compare.

### Pattern 4: Retained replay is baseline, live message is a change

**What:** `ReceiveMessage.retain` (verified field) is `True` for messages delivered as a result of subscribing. StateTracker rules:

1. Unknown device state + `retain=True` -> record as baseline, do not act (cold start).
2. Known `last_acted` (persisted in `Store`) and value differs -> act (instance missed a change while down; converge). Applies to retained or live.
3. Value equals `last_acted` -> ignore (duplicate, reconnect replay, echo).
4. Invalid value (not in select options / not ON/OFF) -> log and ignore.
5. State arrives before its config (different topics, no ordering guarantee) -> cache raw value per `device_id` (bounded) and evaluate when config arrives.

**Trade-offs:** rule 1 vs "run on startup" is a user-visible decision; make it a per-hub option (default: baseline only). **[design] MEDIUM**

### Pattern 5: Validated raw sequences -> Script per trigger

**What:** Store/transport the raw list from `ActionSelector` (plain JSON). On load: `cv.SCRIPT_SCHEMA(raw)` -> `await script.async_validate_actions_config(hass, seq)` -> `Script(hass, seq, name, DOMAIN, script_mode=..., logger=...)` (signature verified: `Script(hass, sequence, name, domain, *, change_listener, log_exceptions, logger, max_exceeded, max_runs, running_description, script_mode, top_level, variables, enabled)`; `async_run(run_variables, context, started_action)`).
**When:** Every device/trigger (Switch: on/off; Select: one per option).
**Trade-offs:** Rebuild the `Script` objects on every config change (they hold compiled templates and running state; call `async_stop` on the old one). Never persist template objects; only the raw form. Pass `run_variables={"trigger": {"platform": "mqtt_actions", "device_id", "state", "previous_state", "origin", "retrigger": bool}}` so actions can template on it.

**Concurrency:** HA `single` mode silently drops an overlapping run and `restart` aborts in-flight actions. For state-driven ordering use one serial worker (queue) per device that awaits each run (`Script` in `single` mode is then never overlapped). **[design]**

### Pattern 6: Transient fan-out for re-trigger

**What:** Service publishes non-retained `{request_id, origin, device_id|null}` to `<base>/v1/retrigger`. Every instance, **including the sender**, handles it through the same subscription path, so there is exactly one code path. Handler re-runs actions for the instance's own current `last_acted` state with `trigger.retrigger = true`. Dedupe on `request_id` (small LRU) because QoS 1 is at-least-once.
**Trade-offs:** Best-effort; instances disconnected at that moment miss it (intentional: non-retained so a restart does not re-fire). If the broker is down the sender executes nothing; acceptable and consistent ("all connected instances").

## Data Flow

### State change -> actions (every instance, symmetric)

```
HA UI toggle (any instance)        External system / automation
        │ core MQTT entity publishes          │ publishes plain payload
        └──────────────┬──────────────────────┘
                       ▼
         <base>/v1/devices/<id>/state   (retained)
                       │ broker fan-out to all subscribers
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
   Instance A     Instance B      Instance C
   StateTracker   StateTracker    StateTracker
   dedupe/baseline (Pattern 4)
        │
        ▼
   ActionRunner -> per-device queue -> Script.async_run -> local services
   (core MQTT entities on each instance also update their own state from the same message)
```

### Config publish / mirror

```
Owner: subentry created/edited/deleted
   -> DeviceRegistry (owned) -> SyncManager.reconcile()
   -> publish <base>/v1/devices/<id>/config (retained, hash+rev)
   -> DiscoveryPublisher publishes homeassistant/<comp>/mqtt_actions/<id>/config (retained)
                    │
                    ▼ broker (retained)
Follower: subscribe devices/+/config (retained replay on connect)
   -> SyncManager.on_config -> owner pin / hash check
   -> trust gate (auto | ask | deny)
   -> DeviceRegistry (mirrored) + Store -> ActionRunner rebuilds Scripts
   (entities appear separately via core MQTT discovery of the owner's retained payload)
```

### Delete

```
Owner confirms delete (custom warning step in reconfigure flow: "removed on ALL connected instances")
   -> subentry removed -> reconcile detects missing id
   -> publish empty retained: discovery topic, config topic, state topic
   -> followers: empty config => drop mirror, async_stop Scripts, clear Store, remove registry leftovers
   -> offline followers: see NOTHING (no retained message exists any more) => tombstone problem, see below
```

### Key Data Flows

1. **Config replication:** owner -> broker (retained per device) -> followers. One direction only; followers never publish config.
2. **State/trigger:** anyone -> retained state topic -> all instances; each acts locally after dedupe.
3. **Re-trigger:** any -> transient topic -> all instances (including sender).
4. **Persistence:** owned = subentries (HA config storage); mirrored + last_acted = `Store`. Broker is the shared truth for mirrored; the owner's local config is the truth for owned devices and self-heals the broker.

## Ownership and Conflict Handling

- **Instance identity:** generate a UUID at hub setup, store in config entry data. Do not use the HA core UUID (same clone problem). Backup-restore/cloned VM duplicates the ID: two "owners" of the same devices. Mitigate with the optional `instances/<id>` presence doc carrying a per-session nonce and raise a repair issue when two live nonces claim one id. **[design]**
- **Owner pinning:** a follower records `owner` per device on first sight and rejects configs from a different owner for that `device_id`. No takeover in v1; an explicit "adopt orphan / transfer ownership" flow is a later feature (needs a handshake, otherwise it reintroduces multi-writer).
- **Owner authority self-heal:** if a retained config for an owned device is missing or different (broker wiped, someone wrote to the topic), the owner republishes local truth and raises a repair issue when content differs.
- **Enforcement is cooperative.** Nothing in MQTT stops a client from writing another owner's topic. Real enforcement is broker ACLs (only the owner's MQTT user may write `devices/<id>/config`), which the docs should recommend. Optional hardening: HMAC signature of the config document with a broker-wide shared secret. **[design]**
- **Trust gate (security-critical):** remote-provided sequences run with full local service access. Follower policy per hub: `deny` (default until opted in), `ask` (new/changed actions become a Repairs approval bound to the content hash of the actions; any change re-prompts), `auto`. Unapproved mirrors are stored but not executed. **[design]**
- **Owner absent:** followers continue to execute mirrored actions from cached config (Store) and the retained state; only edits/deletes need the owner.

## Echo and Loop Prevention

MQTT has no reliable "do not deliver to sender" for this stack: MQTT v5 `no_local` is a subscribe option and `mqtt.async_subscribe(hass, topic, msg_callback, qos, encoding)` exposes no such parameter (verified), and HA defaults to MQTT 3.1.1. Prevention is therefore semantic, not transport-level.

| Loop / echo | Cause | Prevention |
|-------------|-------|------------|
| Config echo | Owner receives its own retained publish | `owner == me` and hash equal -> ignore. Publisher also diffs against last-published hash before publishing |
| Config ping-pong | Follower republishes what it received | Followers never publish config; only the owner is a writer |
| Reconnect storms | Forced republish after reconnect | Idempotent hash compare on receivers; publish is cheap and needed to heal a wiped broker |
| Discovery churn | Identical retained discovery republished | Core MQTT treats a repeated payload for a known entity as an update dispatch, not a no-op (verified in discovery.py), so avoid needless republish via hash diff; still safe to force on reconnect |
| State echo | Instance sees the state its own UI produced | Uniform path: always act on the state topic, never directly on the command; dedupe on `last_acted` |
| Retained replay | Restart/resubscribe redelivers current state | `msg.retain` + persisted `last_acted` (Pattern 4) |
| Re-trigger duplicates | QoS 1 redelivery, sender receives own message | `request_id` LRU; single path for sender and receivers |
| Action feedback loop | Action toggles the same MQTT device -> state -> action ... | Per-device circuit breaker in `ActionRunner` (e.g. > N runs in T seconds trips, stops running, raises a repair issue). Set `Context` on runs for traceability; context does not cross MQTT so it cannot be the guard |
| Multi-instance amplification | Same action on N instances calls a shared external service N times | Not a technical loop; document that actions run once per instance by design |

## Scaling Considerations

| Scale | Adjustments |
|-------|-------------|
| 2-3 instances, <50 devices (target) | Wildcard subscriptions (3 total), all in-memory. No tuning |
| ~10 instances, hundreds of devices | Startup burst of retained config replay: batch Script rebuilds; cap concurrent `async_validate_actions_config`. Consider the owner manifest topic to prune deterministically |
| Broker with multiple tenants | Base topic must be configurable per hub; document collisions between two unrelated deployments on one broker |

The first bottleneck is not throughput but **startup ordering and retained-replay handling**, not message volume.

## Anti-Patterns

### Anti-Pattern 1: One monolithic retained config document
**What:** All devices in one JSON at one topic. **Why bad:** any writer must read-modify-write; two instances editing concurrently lose data, and it silently defeats the ownership model. **Instead:** one retained topic per device, single writer.

### Anti-Pattern 2: Putting actions into the discovery payload
**What:** Extra keys in the discovery JSON. **Why bad:** rejected by entity schema validation, leaks executable config to every discovery consumer. **Instead:** separate `config` topic with its own ACL.

### Anti-Pattern 3: Acting directly on the command
**What:** Running actions in the command handler and again on the state. **Why bad:** double execution on the originating instance; divergence with external writers. **Instead:** one trigger source, the state topic.

### Anti-Pattern 4: Retained command / retained retrigger
**What:** Retaining transient requests. **Why bad:** every restart or reconnect re-executes. **Instead:** retain only state, config, discovery.

### Anti-Pattern 5: Name-derived topics or unique_ids
**What:** Slugging the device name into topics. **Why bad:** rename moves topics, orphans retained data, breaks entity registry history. **Instead:** immutable generated `device_id`.

### Anti-Pattern 6: Persisting Template/Script objects or runtime-only forms
**What:** Storing `cv.SCRIPT_SCHEMA` output. **Why bad:** not JSON-serializable, not portable between HA versions. **Instead:** store raw ActionSelector output, revalidate on load; include `ha_version_min` / `schema_version` in the document so a follower on an older HA rejects gracefully.

### Anti-Pattern 7: Importing `homeassistant.components.mqtt` throughout
**What:** Direct calls in every manager. **Why bad:** untestable across instances, brittle against MQTT internals. **Instead:** single `MqttGateway`. Only use the names in MQTT's `__all__` (`async_publish`, `async_subscribe`, `async_wait_for_mqtt_client`, `async_subscribe_connection_status`, `is_connected`, `ReceiveMessage`, `valid_subscribe_topic`).

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Core MQTT (`dependencies: ["mqtt"]`) | Public helpers above; `await mqtt.async_wait_for_mqtt_client(hass)`, raise `ConfigEntryNotReady` if it returns False | Subscriptions made through `mqtt.async_subscribe` are automatically resubscribed on reconnect (verified `_async_queue_resubscribe`), so no manual resubscribe logic |
| Broker | Retained messages, QoS 1 | Recommend persistence enabled and ACLs; a non-persistent broker loses config, healed by owner republish on reconnect |
| Entity/device registries | Cleanup of mirrored entities on tombstone | Needed when an offline follower missed the empty-payload delete; identify by `unique_id = mqtt_actions_<device_id>` |
| HA Repairs | Approval, conflict, breaker issues | Keeps security-relevant prompts out of config flows |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Flows <-> Registry | Subentry data is the source; registry derived via update listener | Flows never publish |
| Registry <-> SyncManager | Direct calls; SyncManager is the only writer of mirrored devices | |
| SyncManager -> DiscoveryPublisher | Called on reconcile (owner only) | |
| SyncManager -> ActionRunner | "rebuild scripts for device" | Stops old `Script` first |
| StateTracker -> ActionRunner | `enqueue(device_id, transition)` | Only trigger source besides retrigger |
| Services -> Gateway | Publish only; handling arrives via subscription | Single path for sender |
| All managers -> MQTT | Only through `MqttGateway` | Test seam |

## Known Structural Hazards (details also feed PITFALLS)

1. **Tombstone problem:** an empty retained message deletes the retained record, so an instance that was offline during a delete never receives it. Followers must prune: after subscribing, mirrored devices not re-seen within a grace window (e.g. 10 s after first config message or subscribe-ack) are stale -> drop, and remove the leftover core-MQTT entity/device registry entries. Robust alternative: owner publishes a retained per-owner manifest of device ids; followers prune against it (deterministic, at the cost of a second retained doc). Recommend grace window in v1. **[design] MEDIUM**
2. **No "end of retained replay" marker** in MQTT: never assume "all configs received"; hence grace window.
3. **Select StateFriendlyName:** the core MQTT `select` `options` are plain strings displayed as-is. To show friendly names while the state topic carries StateValue, the discovery payload must set `options` = friendly names and generate `value_template`/`command_template` mapping (Jinja dict). Requires unique friendly names and escaping of quotes; `command_template` and `value_template` exist for select (verified in docs), the generated templates themselves are unverified. **MEDIUM**
4. **Discovery prefix and node_id:** owner publishes under its own MQTT `discovery_prefix`; instances with a different prefix or discovery disabled will not create entities. Treat as documented prerequisite plus a warning in the follower hub flow.
5. **No LWT control:** the integration cannot set its own Last Will through the core MQTT client, so owner "online" availability cannot be made reliable. Do not build owner-availability into entity availability in v1.
6. **Deleting warning UX:** HA's standard subentry delete dialog cannot be customized; the required "happens on all connected instances" warning must be delivered by a dedicated confirm step (e.g. a "Delete device" step in the reconfigure flow with `description_placeholders`) plus detection via reconcile, since the generic delete button still exists. **MEDIUM**
7. **Startup ordering:** state and config arrive on different topics in undefined order; subscribe before publishing; register subscriptions once (wildcards) and look up by parsed `device_id`.

## Suggested Build Order (roadmap implications)

Dependencies: domain core -> gateway -> (owner path: flows -> discovery -> state -> runner) -> sync/mirror -> trust gate -> retrigger/hardening -> HACS release.

1. **Foundation and vertical slice (single instance, Switch):** repo/HACS skeleton (manifest, hacs.json, hassfest + HACS CI), domain core (models, wire schema, topics, hashing), `MqttGateway`, hub config flow, `DeviceSubentryFlow` for Switch with ActionSelector, DiscoveryPublisher, StateTracker, ActionRunner with serial queue. Proves Core Value locally (state change -> actions) and validates the command==state topic decision. Avoids: acting on command, retained replay misfires, template/Script persistence.
2. **Select device + state semantics:** options with StateValue/FriendlyName/actions, generated templates, per-option Scripts, retained baseline rules and persisted `last_acted`.
3. **Central config sync and ownership:** retained per-device config publish, reconcile (incl. reconnect republish), follower mirror + `Store`, owner pinning, delete/unpublish with confirm step, tombstone pruning, registry cleanup. **Ship the trust gate in this same phase**, default `deny`; never let mirrored actions execute before it exists. Needs the FakeBroker multi-instance tests.
4. **Re-trigger, loop guard, hardening:** `retrigger` service + request_id dedupe, circuit breaker, Repairs issues (conflict, breaker), diagnostics, instance-id duplicate detection, docs (ACL recommendation, prerequisites), release automation.

Phase research flags: Phase 3 needs deeper research/spike (tombstone pruning window, multi-instance FakeBroker, Repairs approval flow, registry cleanup of MQTT-discovered entities). Phase 2 needs a small spike on select friendly-name templates. Phases 1 and 4 use standard patterns.

## Sources

- HA MQTT integration public API (`__all__`, `async_publish`, `async_subscribe`, `async_subscribe_connection_status`, resubscribe, protocol support): https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/mqtt/__init__.py and .../client.py (HIGH, read 2026-09-28)
- `ReceiveMessage` fields incl. `retain`: https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/mqtt/models.py (HIGH)
- MQTT discovery topic format, removal by empty retained payload, repeated payload handling: https://www.home-assistant.io/integrations/mqtt/ and https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/mqtt/discovery.py (HIGH)
- Switch/Select MQTT behavior (optimistic, state_topic, templates): https://www.home-assistant.io/integrations/switch.mqtt/ , https://www.home-assistant.io/integrations/select.mqtt/ (HIGH)
- `Script` class signature and modes: https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/helpers/script.py (HIGH)
- Config subentries (introduced 2025.3): https://developers.home-assistant.io/docs/config_entries_config_flow_handler/ , https://developers.home-assistant.io/blog/2025/02/16/config-subentries/ (HIGH)
- Manifest keys (dependencies, integration_type, iot_class, version): https://developers.home-assistant.io/docs/creating_integration_manifest/ (HIGH)
- Cross-instance protocol design (per-device retained docs, owner pinning, trust gate, tombstone pruning, baseline rules): own synthesis from standard MQTT retained-message semantics (MEDIUM, not externally verified)
