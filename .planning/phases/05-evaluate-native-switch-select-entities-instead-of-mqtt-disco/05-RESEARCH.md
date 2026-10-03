# Phase 5: Evaluate native switch/select entities instead of MQTT Discovery - Research

**Researched:** 2026-10-03
**Domain:** Home Assistant 2026.9 entity/device registry mechanics, MQTT Discovery lifecycle, one-way migration of live entities between integrations
**Confidence:** HIGH for the takeover mechanics (executed in a throwaway spike this session against HA 2026.9.4 and real core-MQTT discovery), MEDIUM for the mixed-version cutover design (design proposal, not yet exercised on two real instances), MEDIUM-LOW for frontend counting of devices/entities (not verifiable offline)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Phase 5 = evaluation first (spike plus decision record/ADR), then implementation plans in the same phase if the result is Go. On No-Go the phase ends with the ADR.
- **D-02:** Go/No-Go criteria, all four weighed: (a) all devices and entities, including mirrored ones, visible on our integration page; (b) removal of Discovery complexity (healing DSC-03, ghost entities, DSC-04 resync, retained topics); (c) non-HA consumers preserved where cheap; (d) migration cost and risk of rewriting Phases 1-3 after the v0.1.0 release.
- **D-03:** Native entities become the default. MQTT Discovery stays only as an optional mode for external consumers, with a documented warning about duplicate entities in HA. The PROJECT.md Discovery constraint is amended if the evaluation is Go. — **Reversibility:** costly — removing Discovery from the default path changes a published contract of v0.1.0.
- **D-04:** Non-HA consumers of the Discovery topics are nice-to-have, kept only if cheap (the optional mode covers this).
- **D-05:** Existing installations migrate automatically on update: the owner removes the retained Discovery topics, and the native entity takes over the same unique_id/entity_id. History is kept where technically possible. No manual step. — **Reversibility:** one-way — entity registry ownership moves from core MQTT to this integration; rolling back needs another migration.
- **D-06:** Mixed versions: the central config gets a schema version. Older instances show a Repairs hint, newer ones write backward-compatibly until all instances are updated.
- **D-07:** Owned devices sit under their subentry. Mirror devices (owner = another instance) are devices directly under the config entry, marked with the owner and not editable. Everything shows on our integration page.
- **D-08:** The Phase 4 companion devices and mode selects merge into the native device: one device carries switch/select plus the mode select; the companion concept ends (its reason was D-13).

### Claude's Discretion

- Technical form of the spike, how exactly the same entity_id/unique_id is taken over, and where the schema version lives in the central config.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. (Backlog 999.1, per-instance local actions on mirrored devices, remains separate.)
</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs are mapped to Phase 5 (ROADMAP: "Requirements: TBD"). The existing IDs below are the ones the change touches; the planner should add the new IDs proposed in the last table and amend the old ones in `.planning/REQUIREMENTS.md`.

| ID | Description (from REQUIREMENTS.md) | Research Support |
|----|------------------------------------|------------------|
| DSC-01 | The owner publishes MQTT Discovery for every entity (UUID `unique_id`, availability, device info) | Becomes "optional export mode"; native entities keep the same `unique_id` (Pattern 1, Takeover) |
| DSC-02 | Discovery is removed only on explicit user deletion, never on unload or shutdown | Still true for the optional mode; the one-time migration clear is the only other removal (Pitfalls 1, 2) |
| DSC-03 | The owner republishes discovery if it was removed by a follower deleting the entity | Obsolete in native mode (nothing to delete remotely); stays only in optional mode, or is dropped there too (Don't Hand-Roll, Open Question 4) |
| DSC-04 | Manual resync republishes config and discovery | Resync keeps republishing config documents; discovery part conditional on optional mode |
| STA-01..STA-07 | Shared retained state topic; external messages trigger actions; baseline-only at startup; breaker; unknown Select payload ignored | Native entities must publish to the same state topic and read the same tracker; STA-01 and STA-07 need native test coverage (Architecture, Validation) |
| MAP-01 | Per-instance entity mapping (v2) | Untouched; native entities are per instance already, so MAP-01 stays a separate v2 item |
| ENT-01 (proposed) | Switch/Select/test-button entities are native entities of the hub entry; owned under their subentry, mirrors directly under the entry; unique_id unchanged | Architecture Patterns 1-2 |
| ENT-02 (proposed) | Native entity state comes from the shared state topic; commands publish retained qos 1 to it; availability follows the owner | Pattern 2 |
| ENT-03 (proposed) | Discovery is an optional export mode, off by default, with `enabled_by_default: false` and a documented duplicate warning | Pattern 5 |
| MIG-01 (proposed) | Existing entities are taken over with entity_id, registry id, device id, area, name and history intact | Pattern 3 (verified spike) |
| MIG-02 (proposed) | Mixed versions: owner keeps the legacy path while an online peer is not native-capable; documents carry an additive unhashed marker | Pattern 4 |
| MIG-03 (proposed) | Healing, ghost cleanup, discovery-disabled and discovery-removed issues, test topic are removed or conditional | Don't Hand-Roll |
| DEC-01 (proposed) | ADR with the four D-02 criteria and the Go/No-Go result | Go/No-Go evidence table |
</phase_requirements>

## Summary

**Recommendation: Go.** All four D-02 criteria point the same way, and the single hardest technical risk (D-05, "same unique_id/entity_id, history kept, no manual step") was proven feasible in this session. I ran a throwaway spike (tests copied into `tests/`, executed, deleted; `git status` clean afterwards) against the installed HA 2026.9.4 with the real core MQTT discovery code. Result: using the documented MQTT `migrate_discovery` payload, core MQTT unloads the discovered entities **without** deleting their registry entries; `entity_registry.async_update_entity_platform` then moves them to platform `mqtt_actions`; `device_registry.async_update_device(new_config_entry_id=…, new_config_subentry_id=…)` moves the MQTT device itself under our entry/subentry. After a native entity with the same `unique_id` is added, the final state was: same `entity_id` (`switch.lamp`), same entity registry `id`, same device `id`, device `area_id` and `name_by_user` intact, mode select entity id/registry id intact, exactly one device for the logical device, and no empty discovery payload published by core. Recorder history is keyed by `entity_id` [VERIFIED: `.venv/.../recorder/db_schema.py:607-615`], so it survives automatically.

Three sharp edges decide the plan structure and were each reproduced: (1) `async_update_entity_platform` refuses an entity that is currently loaded ("Only entities that haven't been loaded can be migrated"), so the migrate payload must come first; (2) publishing a plain empty retained discovery payload while core MQTT entities are loaded **deletes their registry entries** (customizations, registry id, device-based automations lost), so the empty clear may only follow the takeover; (3) moving the MQTT device to our entry **removes the entities still registered to the old entry**, so entities move first and the device second. Wrong order in any of these silently destroys user data; the ordering belongs in the plan as a fixed sequence with a test per edge.

The cost side (D-02 d) is real but bounded: about 25 test files mention discovery, about 12 of them substantially; the discovery code is concentrated in `discovery.py`, `sync.py` (about 60 lines of heal logic), and `manager.py` (publish callers, `_clean_registry`, companion helpers, `retired_components`); README/docs have 35 discovery mentions that `tests/test_docs.py` pins. The mixed-version requirement (D-06) cannot be met literally for v0.1.0 instances: v0.1.0 has no code path that shows a specific "please update" hint except `schema_too_new`, which a schema bump would trigger but which also freezes mirror updates on those instances. The recommended design (additive unhashed marker in the document plus a roster gate on the owner) is described in Pattern 4 and listed as Open Question 1 because it deviates from the literal wording of D-06.

**Primary recommendation:** Go. Build native switch/select/button entities on the existing hub entry, take over existing registry entries with the fixed sequence migrate → wait for unload → move entities → move device → clear, gate the owner's cutover on the roster plus an additive marker in the config document, keep Discovery as an optional export that creates disabled-by-default entities, and ship as v0.2.0 with a UAT run on the real ha-one/ha-two + Mosquitto setup.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Switch/Select/test-button entities | HA entity platforms of this integration (`switch.py`, `select.py`, `button.py`) | Manager (state holder) | Entities are views on `Manager`/`Device`; they own no logic, publish through the gateway |
| Shared state and command | MQTT broker (retained state topic) via `MqttGateway` | Manager `_on_message` | Command topic equals state topic (STA-01); the broker echo is the only state source |
| Device and entity identity | HA device and entity registries | Manager takeover module | Registry ownership (platform, config entry, subentry, device) decides what the integration page shows |
| Takeover of legacy entities | New `takeover.py` called from `__init__.async_setup_entry` before platform forward | SyncManager signal for live cutover | Must run while none of our entities are loaded; needs registry plus core MQTT cooperation |
| Cutover gate (mixed versions) | Manager/Presence roster (heartbeat capability) | Config document marker | Owner decides, retained document carries the result for restarting followers |
| Optional Discovery export | `discovery.py` (reduced) via `DiscoveryPublisher` | HA core MQTT (consumer) | Only for external consumers; HA instances get disabled-by-default duplicates |
| Config documents, ownership, trust | Unchanged (`sync.py`, `document.py`, `trust.py`) | — | Phase 5 does not touch the central config content or hash |

## Standard Stack

No new packages. Everything is provided by Home Assistant core or already pinned in `pyproject.toml`.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Home Assistant core | 2026.9.4 installed in `.venv` (floor 2026.9.0 in `hacs.json`) | `SwitchEntity`, `SelectEntity`, `ButtonEntity`, entity and device registry APIs | Required platform [VERIFIED: `.venv/lib/python3.14/site-packages/homeassistant-2026.9.4.dist-info`; `hacs.json`: `"homeassistant": "2026.9.0"`] |
| `entity_registry.async_update_entity_platform` | core | Move a registry entry to another integration, keeping entity_id and registry id | Exact helper for "an entity needs to be migrated between integrations" [VERIFIED: `helpers/entity_registry.py:2076-2113`] |
| `device_registry.async_update_device(new_config_entry_id, new_config_subentry_id, new_identifiers)` | core, landed in Core 2026.8 | Move the MQTT device under our entry/subentry in one call | [VERIFIED: `helpers/device_registry.py:3099-3107` comment block "new_config_entry_id / new_config_subentry_id move the device immediately"; CITED: developers.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry/ "The changes land in Home Assistant Core 2026.8"] |
| MQTT `migrate_discovery` payload | core mqtt | Unload discovered entities, keep registry entries | [VERIFIED: `components/mqtt/discovery.py:81-84,100-119` `CONF_MIGRATE_DISCOVERY = "migrate_discovery"`; CITED: home-assistant.io/integrations/mqtt/ "unload the discovered item, but its settings will be retained"] |
| `AddConfigEntryEntitiesCallback(..., config_subentry_id=…)` | core | Attach entities and devices to a subentry or directly to the entry | Already used by `select.py` [VERIFIED: `custom_components/mqtt_actions/select.py:113-115`] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-homeassistant-custom-component | 0.13.367 (pinned) | `hass`, `mqtt_mock`, `async_fire_mqtt_message`, `mock_platform`, `MockPlatform` | Spike-as-test and all new tests [VERIFIED: `pyproject.toml` dev group] |
| Ruff | 0.16.10 (pinned) | Lint/format, 120 columns | All new code [VERIFIED: `pyproject.toml`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Registry takeover (platform change + device move) | Delete the MQTT entities and let native entities re-register | Loses entity registry id, device id, device area/name, labels, and all UI automations that reference them; spike scenario A showed the plain clear leaves only a `deleted_entities` tombstone keyed `("switch", "mqtt", device_id)`, which a `mqtt_actions` entity never restores |
| Owner-driven migrate broadcast | Each instance unloads its own MQTT entity locally | No public API to unload one discovered entity locally; the broadcast is the documented mechanism, and a ghost entry (not loaded) can be taken over without any broadcast |
| Keep companion devices (No-Go) | — | Entities of mirrored devices stay on core MQTT's device, not on our integration page; heal/ghost code stays; the visible complaint of Phase 3 UAT stays |

**Installation:** none. `manifest.json` keeps `"dependencies": ["mqtt"]` and `"requirements": []` [VERIFIED: `custom_components/mqtt_actions/manifest.json`].

**Version verification:** HA 2026.9.4 and PHACC 0.13.367 confirmed from the installed dist-info; unit tier ran green in this session (`1080 passed, 177 deselected in 57.36s`).

## Package Legitimacy Audit

No external packages are installed or added in this phase. The `package-legitimacy` gate does not apply.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                       broker (retained)
        ┌────────────────────────────────────────────────────────────┐
        │ <base>/v1/devices/<id>/config   (document, + native marker) │
        │ <base>/v1/devices/<id>/state    (command == state)          │
        │ <base>/v1/instances/<id>/availability|heartbeat (+ caps)    │
        │ <prefix>/device/<id>/config     (legacy; migrate -> clear)  │
        └──────▲──────────────┬───────────────────────▲──────────────┘
               │ publish      │ subscribe              │ subscribe (discovery wildcard)
   ┌───────────┴────────────┐ │                        │
   │ OWNER instance (new)   │ │             ┌──────────┴───────────────────────────────┐
   │ Manager                │ │             │ core MQTT discovery (every instance)      │
   │  ├ cutover gate        │◄┘             │  migrate_discovery -> entity unloaded,   │
   │  │  roster: all online │               │  registry entry kept; plain "" -> entry   │
   │  │  peers native-capable?              │  DELETED (never before takeover)          │
   │  ├ 1 publish migrate   │               └──────────┬───────────────────────────────┘
   │  ├ 2 wait unloaded     │                          │ entity unloaded
   │  ├ 3 takeover module ──┼──► entity registry:  platform mqtt -> mqtt_actions, entry+subentry
   │  │                     │──► device registry:  MQTT device -> our entry/subentry, new identifiers
   │  ├ 4 publish "" (clear)│
   │  └ 5 doc marker native │
   │ platforms: switch/select/button forward AFTER takeover
   └───────────┬────────────┘
               │ config document with marker (retained)
               ▼
   ┌────────────────────────┐      ┌──────────────────────────────────┐
   │ FOLLOWER (new)         │      │ FOLLOWER (v0.1.0, unchanged)     │
   │ marker seen -> same    │      │ ignores marker (unknown key),    │
   │ takeover for mirror    │      │ keeps mirror, loses entity after │
   │ entities, then native  │      │ clear (ghost until updated)      │
   └────────────────────────┘      └──────────────────────────────────┘
```

Primary use case, traced: user turns on a native switch on any instance -> entity calls `gateway.async_publish(state_topic, "ON", retain=True, qos=1)` -> broker echoes to every instance -> `Manager._on_message` updates `Device.value`, the tracker decides the edge, the runner executes locally -> dispatcher signal makes the native entity write its state.

### Recommended Project Structure
```
custom_components/mqtt_actions/
├── entities.py        # MqttActionsEntity + one device_info builder (companion_device_info merged, D-08)
├── switch.py          # NEW  native switch of an owned device or mirror
├── select.py          # + native device select; existing InstanceModeSelect/DeviceModeSelect stay
├── button.py          # + native test buttons (one per trigger key); ResyncButton stays
├── takeover.py        # NEW  registry takeover of legacy core-MQTT entities (pure registry logic, testable)
├── discovery.py       # reduced to the optional export builder/publisher
├── sync.py            # discovery heal block removed or conditional
└── manager.py         # cutover state machine, Device.value + signals, no _clean_registry / _remove_companion split
tests/
├── test_takeover.py            # NEW  spike scenarios as regression tests (real core MQTT discovery)
├── test_native_entities.py     # NEW
├── test_cutover.py             # NEW  roster gate, marker, mixed version
└── (test_discovery*.py, test_test_buttons.py, parts of test_manager*/test_sync_owner/test_multi_instance* rewritten)
```

### Pattern 1: Native device entity with the old identity
**What:** One `SwitchEntity` or `SelectEntity` per owned device or mirror, `_attr_has_entity_name = True`, `_attr_name = None`, `unique_id` equal to the device uuid, `DeviceInfo(identifiers={(DOMAIN, device_id)})`. Added with `config_subentry_id=manager.subentry_id_of(device_id)` (None for a mirror), exactly like `DeviceModeSelect`. Test buttons keep the unique id `f"{device_id}_test_{trigger.key}"`; the mode select keeps `f"{device_id}_mode"`.
**When to use:** every owned device and every mirror.
**Verified identity values** (the registry key is `(domain, platform, unique_id)`, so keeping the strings keeps the entry):
- `discovery.py:56-58`: `"platform": "switch", "unique_id": device_id, "name": None,`
- `discovery.py:101-102`: `"platform": "button", "unique_id": f"{device_id}_test_{trigger.key}",`
- `select.py:56`: `self._attr_unique_id = f"{device_id}_mode"`
- `discovery.py:133`: `"device": {"identifiers": [f"{DOMAIN}_{spec.device_id}"], "name": spec.name},` (so the MQTT device identifier is `("mqtt", "mqtt_actions_<device_id>")`; this is the identity check of Pattern 3)

**State source:** add `Device.value: str | None`, updated at the top of `_on_message` **before** the disabled-mode early return (`manager.py:1597`), so a disabled device still shows its real state. Dispatch a per-entry signal (same style as `SIGNAL_DEVICES_CHANGED = f"{DOMAIN}_devices_changed_{{}}"`, `const.py:173`) so the entity calls `async_write_ha_state`. A Select's `current_option` is computed live from `Device.value` and the current spec; `SelectEntity.state` already returns None for an option that is not in `options` [VERIFIED: `components/select/__init__.py:148-151` `if current_option is None or current_option not in self.options:`], so a renamed or removed option no longer leaves a stale state (this replaces the Phase 2 "stays unknown" decision and is a visible improvement to document).

### Pattern 2: Commands and availability
**Command:** `async_turn_on/off` and `async_select_option` publish the exact StateValue (`PAYLOAD_ON`/`PAYLOAD_OFF`, or the option's StateValue) to `state_topic(base, device_id)` with `retain=True, qos=1` through `manager.gateway.async_publish`. Do not set the entity state optimistically: the echo through `_on_message` is the single state source, as with `state_topic` + `command_topic` today. A `HomeAssistantError` from the gateway propagates to the caller.
**Availability parity:** the discovery payload uses `"availability": [{"topic": availability_topic(base_topic, instance_id)}]` (`discovery.py:136`), i.e. unavailable until the owner announced `online`. Native: available when owned (manager running) or when `sync.instance_status(owner) == "online"` for a mirror; re-evaluate on `SIGNAL_ROSTER_UPDATED` (already fired by presence). Keep this parity; heartbeat-based availability stays AVL-01 (v2).
**Test buttons:** `async_press` calls a new `Manager` method that enqueues the same `test=True` run as `_on_test_message` (`manager.py:1745-1752`), after the same mode gate. This removes the test-topic round trip, its subscription (`unsubscribe_test`) and the `test` topic ACL line for HA instances.

### Pattern 3: Takeover sequence (the verified core of D-05)
Fixed order, per device id (owned and mirrors). Each step is a test.
1. **Identify only our own legacy entities.** `mqtt_entry_id = gateway.mqtt_entry_id()`; `mqtt_device = device_registry.async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry_id)` (the form `Manager._clean_registry` already uses, `manager.py:1268`). Take over only entries of that device with `platform == "mqtt"`, `config_entry_id == mqtt_entry_id`, domain in {switch, select, button} and `unique_id == device_id` or `unique_id.startswith(f"{device_id}_test_")`. Never match on `unique_id` alone (Security Domain, T-5-01).
2. **Unload without deleting:** the owner publishes `{"migrate_discovery": true}` (qos 1) on `discovery_topic(prefix, device_id)`. A device that is already a ghost (not loaded, discovery topic cleared) needs no broadcast. Spike: the payload unloads the switch and both buttons in one go, registry entries stay (`registry kept: True`, `state: None`).
3. **Wait until unloaded.** Poll with a short bounded retry until `async_update_entity_platform` stops raising `ValueError("Only entities that haven't been loaded can be migrated")` (`entity_registry.py:2094-2095`, quoted); treat that exact condition as "try again", not as failure. Cap the wait (e.g. 10 s) and leave the device in legacy mode for this run when it expires.
4. **Move entities first:** `er.async_update_entity_platform(entity_id, DOMAIN, new_config_entry_id=entry.entry_id, new_config_subentry_id=<subentry id or leave UNDEFINED for a mirror>)`. Leave `new_device_id` UNDEFINED so the entity stays on the MQTT device. Guard first: if `er.async_get_entity_id(domain, DOMAIN, unique_id)` already exists, do not call it (see Pitfall 4).
5. **Move the device second:** `dr.async_update_device(mqtt_device.id, new_config_entry_id=entry.entry_id, new_config_subentry_id=<subentry id or None>)`. This keeps device id, `area_id`, `name_by_user`, labels.
6. **Merge the old companion:** `er.async_update_entity(mode_entity_id, device_id=mqtt_device.id)` (same platform, allowed while loaded), `dr.async_remove_device(companion.id)` once it has no entities, then `dr.async_update_device(mqtt_device.id, new_identifiers={(DOMAIN, device_id)})`. If no companion exists (fresh mirror), skip. (D-08.)
7. **Clear last:** publish the empty retained payload on the discovery topic. After step 4 core has nothing discovered for that hash, so the clear is harmless (spike scenario B: back-to-back migrate + empty left the registry intact).
8. **Forward the native platforms only after steps 1-7** (in `async_setup_entry`, before `async_forward_entry_setups`), so none of our entities is loaded while registry entries move. For a live cutover on a running follower, run the same steps and then `hass.config_entries.async_schedule_reload(entry.entry_id)` (the duplicate-id fix already does this, `manager.py:1099`).

Spike evidence (final state of the full sequence, real core MQTT discovery, `mqtt_mock`):
```
RES final: switch.lamp id kept True device kept True area True name_by_user Stehlampe entry True subentry True [('mqtt_actions', '<uuid>')]
RES mode select kept id: True True
RES state: <state switch.lamp=off; friendly_name=Stehlampe ...>
RES devices of entry: [('Test instance', None), ('Lamp', 'Stehlampe')]
```

### Pattern 4: Cutover gate and mixed versions (proposal for D-06)
v0.1.0 facts that constrain the design: `parse_document` ignores unknown keys ("unknown extra keys are ignored and never hashed", `document.py:385-388`), `SCHEMA_VERSION: Final = 1` and a higher version raises `SchemaTooNewError` (`document.py:401-402`) which a v0.1.0 follower turns into the `schema_too_new` Repairs issue and keeps its last mirror (`sync.py:497-526`); `parse_heartbeat` reads exactly `("name", "version", "devices", "session")` and ignores everything else (`presence.py:124`).
- **Recommended:** keep `schema_version: 1` (a bump freezes mirror updates on old followers, which breaks the core value there). Add an additive, unhashed marker to the document, following the existing `transferred_from` pattern (written only when set, never part of the content hash, `document.py:150-175`), e.g. `"entities": "native"`. Add an additive heartbeat key (e.g. `"entities": "native"`) so the roster knows who is capable; v0.1.0 ignores it and counts as legacy.
- **Owner rule:** publish the legacy discovery and no marker while any online peer in the roster is not native-capable; once all online peers are capable (or none exist), run the Pattern 3 sequence for its devices and start publishing the marker. A retained document with the marker tells restarting followers (even with the owner offline) that the device is native and its discovery is gone.
- **Follower rule:** a mirror is native iff its document carries the marker; otherwise it stays on today's path (companion device, discovery entity). Owned devices are native iff the owner's gate passed.
- **Consequences to document:** an old instance that is offline during the cutover, or comes online later, loses the UI entities of migrated devices (its actions keep running because the document stays v1); it can only be told through README/release notes. A real "Repairs hint on the old instance" is only possible through a schema bump in a later release (v0.3, when legacy mode is dropped). This is Open Question 1.

### Pattern 5: Optional Discovery export (D-03/D-04)
Keep `build_discovery` reduced to the switch/select components (drop the test buttons and the test topic from the export, they are an HA-only convenience). Add `"enabled_by_default": false` to each exported component so an HA instance that still listens to the prefix creates the duplicate entity disabled [VERIFIED: `components/mqtt/schemas.py:180` `vol.Optional(CONF_ENABLED_BY_DEFAULT, default=True): cv.boolean,`]. Offer a hub option for the export prefix (HA core only listens to its own configured prefix), so external consumers can be served without any HA duplicate at all. Off by default. The reduced publisher keeps `DSC-02` semantics (remove only on explicit delete). Whether DSC-03 healing survives in this mode is Open Question 4; the recommendation is to drop it (no HA user can delete a native entity remotely).

### Anti-Patterns to Avoid
- **Plain empty retained discovery while core MQTT entities are loaded:** deletes their registry entries (spike A).
- **Moving the device before the entities:** `entity_registry.async_device_modified` removes entities of the old config entry when the device moves (`entity_registry.py:1723-1728`, quoted in Pitfall 3).
- **Matching legacy entities by `unique_id` only:** a hostile document could pick the id of an unrelated MQTT entity.
- **Forwarding our platforms before the takeover:** a native entity registers `(switch, mqtt_actions, device_id)` first, so the later takeover creates a duplicate key (Pitfall 4).
- **A retained-replay assumption in tests:** a live message is `retain=False`; core ignores a second retained message on a subscribed topic (Pitfall 7).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unloading discovered MQTT entities without deleting them | Custom unload via core internals (`hass.data["mqtt"]`, dispatcher signals) | `{"migrate_discovery": true}` payload | Documented, version-stable, handles device-based topics (`discovery.py:_generate_device_config(... migrate_discovery=True)`) |
| Moving an entity between integrations | Delete + recreate + copy fields | `er.async_update_entity_platform` | Keeps registry id, entity_id, name, icon, area, labels, options, hidden/disabled |
| Moving a device between entries | Copy area/name/labels to a new device | `dr.async_update_device(new_config_entry_id=…, new_config_subentry_id=…, new_identifiers=…)` | Keeps device id (device-based automations), area, `name_by_user` |
| Removing owned devices/entities on delete | Manual registry cleanup as in `_clean_registry` for native entities | Core: `async_remove_subentry` removes the subentry's devices and entities (Phase 4 research: `async_clear_config_subentry`); for mirrors remove the device/entities via our own registry entries | No MQTT-side side effects, so Pitfall 10 of Phase 3 disappears for native entities |
| Waiting for "discovery has settled" | Sleeps tuned by feel | Mirror core's own rule: 5 s without a discovery message (`DISCOVERY_COOLDOWN = 5`, `components/mqtt/client.py:100`) observed on our own discovery wildcard subscription | Same notion of "settled" as core; our `SyncManager` already receives those messages (`sync.py:670-687`) |
| Version compare for peers | Parsing `version` strings (`0.2.0-rc1` vs `0.2.0`) | Explicit additive heartbeat capability key | Prerelease tags exist (Phase 4: hyphenated tags are prereleases) |

**Key insight:** every piece of the migration has a core-provided primitive; custom code is only the ordering, the identity check and the gate. Hand-rolled registry surgery is where the data-loss pitfalls live.

## Runtime State Inventory

This phase migrates live state, so all five categories are answered.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | (1) Entity registry entries `(switch\|select, "mqtt", <device_id>)` and `(button, "mqtt", <device_id>_test_<key>)` on every instance, with user customizations (name, icon, area, labels, aliases, hidden/disabled, options) [VERIFIED: spike]. (2) MQTT device registry entries with identifier `("mqtt", "mqtt_actions_<device_id>")`, user `area_id`/`name_by_user`/labels. (3) Recorder history keyed by `entity_id` [VERIFIED: `db_schema.py:607-615`]. (4) Our Store keys (`published`, `revs`, `mirrors`, `approvals`, `device_modes`, ...) [VERIFIED: `const.py:113-132`] keep their meaning; no key refers to discovery state. (5) UI automations/dashboards may reference the entity registry id or the device id. | Data migration (registry takeover, Pattern 3) plus code edits. Entity registry id and device id are preserved by design; entity_id preserved, so history and entity-id references stay valid. Optionally a new additive Store key for the cutover state (no `STORE_VERSION` bump needed, per the Phase 2/4 pattern). |
| Live service config | Retained discovery topics `<prefix>/device/<id>/config` on the broker, one per owned device; core MQTT in-memory discovery bookkeeping (`discovery_already_discovered`) on every instance; the retained config documents stay (gain the marker). | Broker: migrate then clear per owned device (owner only). Core MQTT bookkeeping is handled by the `migrate_discovery` payload. Documents: additive marker, no rev/hash change. |
| OS-registered state | None — the integration runs in-process in Home Assistant; no scheduled tasks, services or process names carry the string (checked: the only external processes are the test containers in `~/ha-test`, which are test infrastructure, not product state). | None |
| Secrets/env vars | None — no secret or env var is named after discovery. The live broker deliberately has no auth/ACL (user memory); do not add an auth todo. | None |
| Build artifacts / installed packages | HACS-installed copy of `custom_components/mqtt_actions` in each HA config directory still runs v0.1.0 until updated and HA restarted; `manifest.json` version must be bumped (planned v0.2.0) and equal the release tag (CI `check-version`). No compiled artifacts. | HACS update + HA restart per instance; version bump in manifest; translations en/de updated together. |

**The canonical question answered:** after every file is updated, what still has the old model? (a) registry entries of platform `mqtt` on every instance (taken over at first start of v0.2.0 or on cutover), (b) retained discovery topics (migrated and cleared by the owner), (c) instances still on v0.1.0 (they lose the UI entity until updated; documented), (d) user automations that reference the MQTT device by id (survive because the device id is kept).

## Common Pitfalls

### Pitfall 1: Loaded entity cannot be taken over
**What goes wrong:** `async_update_entity_platform` raises `ValueError`.
**Why:** `if entity_id in entity_sources(self.hass): raise ValueError("Only entities that haven't been loaded can be migrated")` [VERIFIED: `entity_registry.py:2094-2095`]. Reproduced in the spike: `LOADED TAKEOVER refused: Only entities that haven't been loaded can be migrated`.
**How to avoid:** publish `migrate_discovery` first and retry until the call stops raising; bounded wait; fall back to legacy for this run.
**Warning signs:** takeover works in unit tests with ghost entries but fails on a real start (race with the discovery replay).

### Pitfall 2: A plain empty discovery payload deletes registry entries
**What goes wrong:** user customizations, registry id, device-based automations are lost; the native entity gets a new entity_id (`switch.lamp_2` if the old id is taken).
**Why:** with no migrate flag core runs `_async_remove_state_and_registry_entry` -> `entity_registry.async_remove(...)` [VERIFIED: `components/mqtt/entity.py:1042-1058`]. Spike A: after a live `""` the registry entry for `switch.lamp` and both buttons was gone and `("switch", "mqtt", device_id)` sat in `deleted_entities`. Spike C/E: with migrate first the registry entry survived, also for a user-disabled entity.
**How to avoid:** the empty clear is the last step, after takeover. The same rule protects v0.1.0 followers: they receive migrate, then clear, in order.
**Warning signs:** any code path that calls `async_clear_device` (`discovery.py:164-166`) while legacy MQTT entities of that device may still be loaded.

### Pitfall 3: Moving the device first removes the entities
**What goes wrong:** after `async_update_device(new_config_entry_id=…)` the switch and buttons vanished from the registry (spike: `stepA` listed only the select).
**Why:** `async_device_modified` removes entities whose `config_entry_id` equals the old entry when the device's entry changed [VERIFIED: `entity_registry.py:1723-1728`: `if entity.config_entry_id == old_config_entry_id and entity.config_entry_id != device.config_entry_id: self.async_remove(entity.entity_id)`].
**How to avoid:** entities first (platform + entry + subentry), device second; verified order in Pattern 3.

### Pitfall 4: Silent duplicate registry key
**What goes wrong:** if `(switch, mqtt_actions, device_id)` already exists, `async_update_entity_platform` with an unchanged `unique_id` does not raise and leaves two entries with the same key (spike: `entities with key: ['switch.lamp', 'switch.lamp_2']`, lookup returns only one). The conflict check exists only for `new_unique_id` (`entity_registry.py:1959-1966`).
**How to avoid:** guard with `async_get_entity_id(domain, DOMAIN, unique_id)` before every call; run the takeover before our platforms are forwarded; if a native entry already exists, delete the legacy ghost instead (it is not loaded, so no discovery side effect).

### Pitfall 5: Races at startup
**What goes wrong:** our setup runs when the MQTT client is ready, but core MQTT may not have replayed the retained discovery yet; a late replay after the takeover recreates a legacy entity (`switch.lamp_2`).
**How to avoid:** use our own discovery wildcard subscription (already present in `SyncManager`) to detect the retained legacy discovery, wait for 5 s of quiet (core's `DISCOVERY_COOLDOWN`), then migrate; after the clear, delete any `platform == "mqtt"` registry entry for our device ids that reappeared (not loaded after the migrate marker, so no publish happens). Add a spike test with a delayed replay.

### Pitfall 6: Hostile device id (identity)
**What goes wrong:** mirror device ids come from the broker (`is_valid_device_id`: 1-64 of letters, digits, `_`, `-`, `topics.py:11`). A document whose `device_id` equals the `unique_id` of an unrelated MQTT switch would make a unique-id-only takeover steal that entity.
**How to avoid:** the identity check of Pattern 3 step 1 (MQTT device identifier `("mqtt", "mqtt_actions_<id>")` must match, domain and unique-id shape must match).

### Pitfall 7: Test harness semantics
**What goes wrong:** a second `retain=True` message on the same topic is skipped by core MQTT's client ("Skip if the subscription already received a retained message", `components/mqtt/client.py:1347-1354`), so a test that fires the clear with `retain=True` silently tests nothing (this fooled the first spike run). A live broker message has `retain=False`.
**How to avoid:** in tests, the first discovery payload is `retain=True`, everything after is `retain=False`. `mqtt_mock` does not loop publishes back; feed payloads with `async_fire_mqtt_message`. `device_registry.devices` used as a mapping raises `RuntimeError` in 2026.9 tests (deprecated, error behavior); use `dr.async_entries_for_config_entry` and `async_get_device_by_identifier`. `merge_identifiers` is deprecated; use `new_identifiers` [CITED: developers.home-assistant.io/blog/2026/08/24/device-registry-follow-up-changes/].

### Pitfall 8: Multi-instance harness does not run platforms
**What goes wrong:** `tests/fake_broker.py` `InstanceFactory` starts a bare `Manager` on a `FakeGateway` (`mqtt_entry_id()` returns None) and never forwards platforms, so native entities are not exercised there.
**How to avoid:** Wave 0 task: let `Instance` run the real `async_setup_entry` with the fake gateway patched in (`custom_components.mqtt_actions.MqttGateway` and `manager.MqttGateway`), or forward platforms after the manager start while the entry is loaded.

### Pitfall 9: Documentation and test pinning
`tests/test_docs.py` reads README, docs, `services.yaml`, `const.py` and translations; `tests/test_translations.py` reads `ISSUES` from `en.json`; `tests/test_repo_structure.py` lists docs files. Removing the `discovery_removed` and `mqtt_discovery_disabled` issues, changing README lines about discovery (README lines 111, 117, 126, 275) and the ACL page (`docs/broker-acl.md` lines 38, 58, 72, 95, 116) fails those tests until they are updated together with hassfest-valid en/de translations.

### Pitfall 10: Rollback is not supported
A user who downgrades to v0.1.0 after the takeover gets v0.1.0 discovery again; core MQTT creates new `(switch, mqtt, id)` entries that cannot take the entity_id of the migrated entry (`switch.lamp_2`), and the migrated entries become orphans. D-05 accepts one-way; state it in the release notes and the README.

### Pitfall 11: v0.1.0 owner healing
A v0.1.0 owner re-publishes discovery whenever its own discovery topic is cleared (`sync.py:670-687`, empty payload for an id in `manager.devices`). The new code never clears topics of devices it does not own, so no ping-pong arises, but a migrated device must never be handed back to a v0.1.0 owner (adoption between a new and an old instance): refuse or warn on adoption while the other side is not capable (planner decision).

## Code Examples

### Spike skeleton to keep as `tests/test_takeover.py` (verbatim from the spike that passed)
```python
# Source: executed this session against HA 2026.9.4 with pytest-homeassistant-custom-component 0.13.367
async def test_takeover_keeps_identity(hass, mqtt_mock, make_hub_entry, make_switch_subentry):
    sub = make_switch_subentry("Lamp")
    device_id = sub["data"][CONF_DEVICE_ID]
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)          # v0.1.0 behaviour: companion + mode select
    await hass.async_block_till_done(wait_background_tasks=True)
    topic = discovery_topic("homeassistant", device_id)
    payload = [c.args[1] for c in mqtt_mock.async_publish.call_args_list if c.args[0] == topic][-1]
    async_fire_mqtt_message(hass, topic, payload, retain=True)             # first (replay) message: retained
    await hass.async_block_till_done(wait_background_tasks=True)
    # ... customize area/name_by_user on the MQTT device ...
    async_fire_mqtt_message(hass, topic, json.dumps({"migrate_discovery": True}), retain=False)   # live: retain=False
    async_fire_mqtt_message(hass, topic, "", retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    sub_id = next(iter(entry.subentries))
    for ent in list(ereg.entities.values()):                               # B first: entities
        if ent.platform == "mqtt" and ent.unique_id.startswith(device_id):
            ereg.async_update_entity_platform(
                ent.entity_id, DOMAIN, new_config_entry_id=entry.entry_id, new_config_subentry_id=sub_id
            )
    dreg.async_update_device(old_device_id, new_config_entry_id=entry.entry_id, new_config_subentry_id=sub_id)  # A second
    ereg.async_update_entity(mode_eid, device_id=old_device_id)
    dreg.async_remove_device(companion.id)
    dreg.async_update_device(old_device_id, new_identifiers={(DOMAIN, device_id)})
    # then mock_platform(hass, f"{DOMAIN}.switch", MockPlatform(async_setup_entry=...)) and forward Platform.SWITCH
```

### Observed results of the spike scenarios (quote for the ADR)
```
A plain "" on a loaded entity:  registry after plain clear: None, state: None, deleted keeps ("switch","mqtt",id): True, buttons gone
B migrate then "" back-to-back: registry kept: True, state: None, buttons still platform mqtt
C user-disabled entity:         after migrate registry kept: True; after migrate+clear registry kept: True
E disabled at discovery + plain "": registry kept: False   (migrate first: kept True)
D full takeover:                entities after: [('button.lamp_test_on','mqtt_actions'), ('button.lamp_test_off','mqtt_actions'),
                                 ('switch.lamp','mqtt_actions'), ('select.lamp_mode','mqtt_actions')]; empty publishes by core: []
Conflict guard:                 existing native entry present -> takeover raises nothing, two entries share the key
```

### Registry-only identity check (new code, values from the quotes above)
```python
# Source: values from discovery.py:102,133 and select.py:56 (quoted in Pattern 1)
def _is_legacy_entity(entry: er.RegistryEntry, device_id: str, mqtt_entry_id: str, mqtt_device_id: str) -> bool:
    return (
        entry.platform == "mqtt"
        and entry.config_entry_id == mqtt_entry_id
        and entry.device_id == mqtt_device_id          # device found via identifier ("mqtt", f"{DOMAIN}_{device_id}")
        and entry.domain in {"switch", "select", "button"}
        and (entry.unique_id == device_id or entry.unique_id.startswith(f"{device_id}_test_"))
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Device linked to several config entries (`config_entries` set) | One config entry plus at most one subentry; move with `new_config_entry_id`/`new_config_subentry_id` | Core 2026.8 [CITED: developers blog 2026/07/21] | Makes the device move of Pattern 3 a single call; `add/remove_config_entry_id` deprecated, `async_get_device` and `merge_identifiers` deprecated |
| Delete MQTT entities to re-create elsewhere | `migrate_discovery` keeps registry entries | MQTT migration feature (documented for single-component to device discovery) [CITED: home-assistant.io/integrations/mqtt/] | Foundation of D-05; we use it for platform hand-over, which is not its documented purpose |
| Single-component discovery topics | Device-based discovery (`homeassistant/device/<id>/config`) | already used in v0.1.0 | The migrate payload on a device topic unloads every discovered component of that device (`discovery.py:_generate_device_config`) |

**Deprecated/outdated:** companion devices of Phase 4 (end with D-08); `Manager._clean_registry`, `_remove_companion` as separate concept, the `discovery_removed` and `mqtt_discovery_disabled` issues in native mode.

## Go/No-Go Evidence (input for the ADR, D-01/D-02)

| Criterion | Finding | Verdict |
|-----------|---------|---------|
| (a) All devices and entities on our integration page | Native entities carry `config_entry_id` of the hub entry; devices sit under the subentry (owned) or the entry (mirror). Devices already show via Phase 4 companions (UAT test 4 passed); entities of discovery devices belong to the MQTT entry. Frontend counting itself is [ASSUMED: counts by config entry, as stated in 04-RESEARCH] and must be checked in UAT | Go (confirm in UAT) |
| (b) Remove Discovery complexity | Removed or conditional: discovery heal (`sync.py` about 60 lines + `ISSUE_DISCOVERY_REMOVED_PREFIX`), `_clean_registry`, companion/mirror device split, `retired_components` tombstones, `_check_discovery_enabled` issue, test topic and its subscriptions, ACL need for HA instances to write the discovery prefix (`docs/broker-acl.md:116`), README limitation "Healing a removed discovery recreates the mirrored entities and loses the customizations" (`README.md:275`). New code: takeover and cutover (bounded) | Go |
| (c) Non-HA consumers | Optional export mode with `enabled_by_default: false` and a prefix option keeps them at low cost | Go (cheap) |
| (d) Migration cost and risk | Mechanics proven; risk is ordering and mixed versions, each reproducible and testable. Test rewrite: about 25 files mention discovery; heavy: `test_discovery.py` (294 lines), `test_test_buttons.py` (524), `test_manager.py` (1328), `test_sync_owner.py` (985), `test_multi_instance.py` (875), `test_discovery_select.py` (258). Docs: 35 mentions. Unit tier today: 1080 tests, 57 s | Go with a UAT gate |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The HA frontend counts devices and entities on the integration page by config entry (and subentry), so native entities and mirror devices appear there | Go/No-Go (a) | If counting differs, criterion (a) is partly unmet; check in UAT on ha-one/ha-two before declaring done |
| A2 | An old (v0.1.0) instance online during a cutover only loses its UI entity, not its actions, because the document stays `schema_version: 1` and v0.1.0 ignores the marker | Pattern 4 | If an unknown key were rejected somewhere I did not read (only `parse_document` and `parse_heartbeat` were read), old instances could drop mirrors; add a test that feeds the new document to the v0.1.0 parser (the current parser) |
| A3 | `async_update_entity_platform` for a mirror entry with `config_subentry_id` None and `new_config_subentry_id` left UNDEFINED behaves like the owned case | Pattern 3 | Not run for the mirror variant; add a spike test |
| A4 | A late replay of retained discovery after the takeover is detectable and cleanable as described (Pitfall 5) | Pitfall 5 | Not reproduced; if core MQTT behaves differently on a real broker the startup sequence needs another settle strategy; verify in UAT |
| A5 | A takeover performed on a *live* running follower followed by `async_schedule_reload` is clean | Pattern 3 step 8 | The spike moved the mode select while it was loaded and that worked, but the full live path was not run |
| A6 | The README/docs statement about HA Core 2026.10 (upcoming `DeviceEntry.config_entries` deprecation, user memory) does not break the used APIs | State of the Art | `new_config_entry_id`, `new_identifiers`, `async_get_device_by_identifier` are the non-deprecated forms; recheck when 2026.10 stable ships |
| A7 | Heartbeat capability key is the better gate than version comparison | Pattern 4 | Purely a design preference; either works |

## Open Questions

1. **D-06 cannot be met literally for v0.1.0.**
   - What we know: v0.1.0 has one hint mechanism, `schema_too_new`, triggered by `schema_version > 1`; that also freezes mirror updates on those instances. Additive changes (marker, heartbeat key) are silent for v0.1.0.
   - What's unclear: whether the user prefers (a) additive marker plus roster gate, silent loss of UI entities on stragglers, no hint (recommended), or (b) a schema bump to 2, hint via `schema_too_new`, but old followers stop applying updates.
   - Recommendation: (a) now; schema bump later when legacy mode is dropped. Put the choice in the ADR; confirm with the user before planning.
2. **Gate strictness.**
   - Unclear: block the cutover while any online peer is not capable (recommended, no timeout) versus cut over after a grace period.
   - Recommendation: block while online peers are legacy, show a Repairs hint on the new instance naming them, never block on offline peers.
3. **Adoption between new and old instances** (Pitfall 11): refuse, warn, or ignore?
4. **Discovery export details:** drop DSC-03 healing in the optional mode (recommended), default prefix (recommend a prefix HA does not listen to, configurable), and whether the export includes test buttons (recommend no).
5. **Entity categories and names of the native test buttons:** keep `entity_category config` and name `f"Test {trigger.friendly_name}"` (`discovery.py:103,109`) so migrated entries keep their original names.
6. **Live follower cutover UX:** reload automatically or ask? Recommend automatic scheduled reload (precedent: duplicate-id fix).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python / `.venv` | all tests | yes | 3.14.7 | — |
| Home Assistant core | spike, tests | yes | 2026.9.4 | — |
| pytest-homeassistant-custom-component | spike, tests | yes | 0.13.367 | — |
| uv | CI parity | yes | 0.12.7 (pin in project says 0.12.x) | — |
| mosquitto | `-m broker` tier | yes | `/usr/bin/mosquitto` | skipped marker |
| podman (as `docker`) | real two-instance UAT | yes | podman 6.1.3 | — |
| `~/ha-test` (ha-a, ha-b, mosquitto) | UAT of the upgrade path | yes (directories `a`, `b`, `mosquitto` exist; container state not probed) | — | start containers before UAT |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (pinned transitively) + pytest-homeassistant-custom-component 0.13.367, `asyncio_mode = "auto"` [VERIFIED: `pyproject.toml`] |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `--strict-markers`, markers `broker`, `multi_instance`) |
| Quick run command | `uv run pytest -q -m "not broker and not multi_instance" -x` (about 57 s today) |
| Full suite command | the three CI tiers: unit above, `uv run pytest -q -m multi_instance`, `uv run pytest -q -m broker` [VERIFIED: `.github/workflows/ci.yml` lines 46, 69, 85] |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MIG-01 | takeover keeps entity_id, registry id, device id, area, name_by_user, mode select; one device; no empty discovery published by core | unit (real core discovery via `mqtt_mock`) | `uv run pytest tests/test_takeover.py -x` | no, Wave 0 (spike code above) |
| MIG-01 | loaded-entity refusal handled; ghost takeover; disabled entity; duplicate-key guard; identity check rejects foreign MQTT entity with same unique_id; delayed replay | unit | `uv run pytest tests/test_takeover.py -x` | no, Wave 0 |
| ENT-01/02 | switch/select state from topic, retained qos-1 command to the state topic, availability parity, Select mapping and unknown-option state, disabled-mode state still shown | unit | `uv run pytest tests/test_native_entities.py -x` | no, Wave 0 |
| ENT-01 | owned entity under subentry, mirror entity directly under the entry, adoption moves it | unit | `uv run pytest tests/test_native_entities.py tests/test_companions.py -x` | partly (test_companions to rewrite) |
| ENT-03 | export mode off by default, payload has `enabled_by_default: false`, prefix option | unit | `uv run pytest tests/test_discovery.py -x` | yes, to rewrite |
| MIG-02 | roster gate holds while a legacy peer is online; marker written after cutover; v0.1.0-shaped heartbeat/document (no new keys) counts as legacy; current parser accepts the marker document | unit + multi_instance | `uv run pytest tests/test_cutover.py -x` and `-m multi_instance` | no, Wave 0 |
| STA-01, STA-07, STA-03 | unchanged behavior through native entities across two instances | multi_instance | `uv run pytest -q -m multi_instance` | yes, harness extension needed (Pitfall 8) |
| MIG-03 | removed issues absent from translations and docs; ACL doc matches broker test | unit + broker | `uv run pytest tests/test_docs.py tests/test_translations.py tests/test_repo_structure.py -x`, `-m broker` | yes, to update |
| DEC-01 | ADR exists with the four criteria and result | manual-only (file review) | — | no |
| A1/A4/A5 | integration page counts, real-broker replay race, live follower cutover | manual UAT on ha-one/ha-two | (UAT checklist) | no |

### Sampling Rate
- **Per task commit:** the single new test file of the task, `-x`
- **Per wave merge:** unit tier (`-m "not broker and not multi_instance"`)
- **Phase gate:** all three tiers green plus Ruff (`uv run ruff check . && uv run ruff format --check .`) before `/gsd-verify-work`, plus the UAT items above

### Wave 0 Gaps
- [ ] `tests/test_takeover.py`: spike scenarios A to E as regression tests (fixtures: legacy discovery entity loaded through `async_fire_mqtt_message`; a helper that builds the legacy payload with `build_discovery`)
- [ ] `tests/test_native_entities.py` and `tests/test_cutover.py`
- [ ] `tests/fake_broker.py`: `Instance` that runs real `async_setup_entry` with the `FakeGateway` patched in, so platforms are forwarded
- [ ] A helper that produces a v0.1.0-shaped peer (heartbeat and document without the new keys) for mixed-version tests
- [ ] Framework install: none

## Security Domain

`security_enforcement` is on (ASVS level 1, block on high).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | HA handles it; broker auth is deliberately out of scope (user memory: live broker without auth/ACL, EMQX migration planned; do not add it as a todo) |
| V3 Session Management | no | — |
| V4 Access Control | yes | Registry takeover touches only entries of our own MQTT device (identifier check); switch/select services on mirrors behave as before (the trust gate for actions is unchanged: no Script without approval); only the owner publishes `migrate_discovery`/clear for its own devices |
| V5 Input Validation | yes | Device ids from the broker are validated by `is_valid_device_id` before any registry lookup (`topics.py:11,14-16`); document content already passes `parse_document`; the new marker is parsed strictly (only the expected string value) and never hashed |
| V6 Cryptography | no | — |
| V8 Data Protection | yes | Names and option labels of mirrors come from the broker; entity and device names are plain strings; markdown contexts keep using `escape_markdown` (existing rule from 03-08) |
| V14 Configuration | yes | No secrets; ACL doc must be updated (HA instances no longer need discovery-prefix write access in native mode) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| T-5-01 Hostile document with a `device_id` equal to an unrelated MQTT entity's `unique_id` makes the takeover steal it | Tampering / Elevation | Match via MQTT device identifier `("mqtt", f"{DOMAIN}_{device_id}")` plus domain and unique-id shape; test with a foreign entity |
| T-5-02 Forged `migrate_discovery` or empty discovery on a device topic unloads or deletes entities of another instance | Tampering / DoS | Existing cooperative ownership (docs/broker-acl.md); per-instance ACL on the discovery prefix; the new code never publishes for devices it does not own; native entities are not affected by discovery messages at all |
| T-5-03 Forged marker in a document claims "native" and makes followers migrate | Tampering | The marker is only honored from the pinned owner's document (same pin rule as content, `sync.py` D-17); worst case is a loss of the legacy discovery entity, never action execution |
| T-5-04 Forged heartbeat capability keeps the owner from cutting over | DoS | Roster cap and heartbeat validation already exist (`presence.py`); the gate only delays a UI change |
| T-5-05 Broker-supplied names/options reach entity names and select options | Tampering | Bounded by `parse_document` limits (`MAX_TEXT_LENGTH`, `MAX_OPTIONS` in `const.py:46-48`); entity names are not markdown |

## Project Constraints (from CLAUDE.md)

- Python 3.14, HA 2026.9.x, hassfest and HACS validation must stay green; Ruff 120 columns, `target-version = "py314"`.
- Use `entry.runtime_data` (Manager), no `hass.data[DOMAIN]`; services are registered in `async_setup`; Config Flow only.
- `translations/en.json` and `de.json` must both be updated; no `strings.json`.
- `import probatio` (not voluptuous) for schemas if any new validation is added.
- Do not use `device_id` targets in shipped examples; documentation tests enforce this.
- Do not execute a received action sequence without the opt-in and validation (unchanged by this phase).
- Dev deps: do not add `homeassistant`, `pytest`, `voluptuous` directly; PHACC pins them.
- Pin action SHAs; Dependabot/Renovate bumps (a PHACC bump to 0.13.368 pulled HA 2026.10.0b0 before: do not bump during the phase).
- GSD enforcement: file changes go through a GSD workflow; TDD is on (`workflow.tdd_mode: true`), Nyquist validation on, code review on.
- Language: German in chat, English in code, comments, commits and planning files.
- Memory: the live broker has no auth/ACL on purpose; Phase 4 release state: release v0.1.0 is published, test setup `~/ha-test` with ha-a, ha-b and a Mosquitto container.

## Sources

### Primary (HIGH confidence)
- HA core 2026.9.4 source in `.venv`: `helpers/entity_registry.py` (1113-1180, 1417-1660, 1660-1790, 1842-2113), `helpers/device_registry.py` (360-420, 3060-3200), `components/mqtt/{discovery,entity,client,schemas,util}.py`, `components/select/__init__.py:140-170`, `components/recorder/db_schema.py:607-621`
- Spike runs this session (HA 2026.9.4, PHACC 0.13.367, real core MQTT discovery through `mqtt_mock`): scenarios A to F, M2, conflict check; temporary files deleted, `git status` clean
- Repo source read this session: `discovery.py`, `entities.py`, `select.py`, `button.py`, `sensor.py`, `__init__.py`, `topics.py`, `mqtt_gateway.py`, `state.py`, `sync.py`, `manager.py` (all), `const.py` (1-180), `document.py` (150-175, 245-275, 380-430), `presence.py` (100-135), `tests/conftest.py`, `tests/fake_broker.py`, `tests/test_discovery.py` (1-60), `tests/test_companions.py` (1-80)
- `.planning/phases/05-.../05-CONTEXT.md`, `REQUIREMENTS.md`, `STATE.md`, `ROADMAP.md`, `PROJECT.md`, `04-RESEARCH.md` (D-13 reasoning), `04-UAT.md`

### Secondary (MEDIUM confidence)
- https://www.home-assistant.io/integrations/mqtt/ (migrate_discovery: "unload the discovered item, but its settings will be retained"; empty payload cleanup afterwards)
- https://developers.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry/ (single config entry device model, Core 2026.8, `new_config_entry_id`)
- https://developers.home-assistant.io/blog/2026/08/24/device-registry-follow-up-changes/ (`async_get_device`, `merge_identifiers`, `config_entries` deprecations)

### Tertiary (LOW confidence)
- Frontend counting of devices/entities on the integration page (not verifiable offline; see A1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, core APIs read in source and exercised
- Architecture: MEDIUM-HIGH, takeover verified; cutover gate and live follower path designed, not yet run on two real instances
- Pitfalls: HIGH for 1-4, 6-7, 9 (reproduced or read); MEDIUM for 5, 8, 11

**Research date:** 2026-10-03
**Valid until:** 2026-10-17 (HA 2026.10 stable is imminent and touches device registry deprecations; PHACC moves almost daily)
