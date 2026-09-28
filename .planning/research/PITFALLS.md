# Pitfalls Research

**Domain:** Home Assistant custom integration (HACS) that turns MQTT state changes into locally executed HA action sequences, with device definitions synced across multiple HA instances via retained config on a shared broker
**Researched:** 2026-09-28
**Confidence:** MEDIUM-HIGH (MQTT/HA mechanics verified against HA core source and official docs; multi-instance sync and trust-model recommendations are architectural judgment, flagged per item)

Phase labels used below are *suggested* roadmap phases (the roadmap does not exist yet):

- **P1** Scaffold, CI, HACS/hassfest compliance
- **P2** MQTT lifecycle + single-instance Switch (subscribe, action execution)
- **P3** Select device, config/options flow, action selector
- **P4** Central config + ownership + multi-instance sync
- **P5** Trust model / remote-action security (must be *designed* before P4 ships anything remote)
- **P6** Delete/cleanup semantics, re-trigger service
- **P7** Hardening, multi-instance test bed, release

---

## Critical Pitfalls

### Pitfall 1: The integration duplicates what HA's MQTT integration already syncs (double entity creation / discovery echo)

**What goes wrong:**
The requirement "other HA instances read the central config and create the same devices" plus "publish MQTT Discovery for every entity" is easy to implement as: every instance publishes discovery for every device. Two problems follow. (a) Every instance's built-in MQTT integration *already* consumes retained discovery from the shared broker, so the follower gets the entities for free from the owner's discovery; a second discovery publish from the follower overwrites the same/similar topic, creating flapping updates or duplicate entities with a different `unique_id`. (b) The entities are owned by the *MQTT* config entry, not this integration, so this integration's lifecycle (unload, remove entry) does not clean them up.

**Why it happens:**
The mental model "central config -> each instance builds devices" ignores that the discovery messages themselves are the cross-instance entity sync mechanism.

**How to avoid:**
Decide the split explicitly in P4 design and write it into ARCHITECTURE.md: **only the owner publishes discovery** (retained, one topic per entity, `unique_id` = `<owner_uuid>_<device_uuid>[_<suffix>]`). Followers use the central config *only* to (1) know which state topics to watch and (2) obtain the action sequences to run. Followers never publish discovery for devices they do not own. Document that followers need MQTT discovery enabled and the same discovery prefix (see Pitfall 14).

**Warning signs:**
Duplicate entities (`switch.foo_2`), discovery topic flapping in `mosquitto_sub -v -t 'homeassistant/#'`, entities present on follower with no corresponding integration device.

**Phase to address:** P4 (architecture decision), verified in P7 multi-instance test.

**Confidence:** HIGH (MQTT discovery is retained and consumed by every client per official docs).

---

### Pitfall 2: Retained state replayed on every startup/reconnect re-triggers all actions

**What goes wrong:**
The broker replays the retained value of every subscribed state topic on each (re)subscription: HA start, MQTT integration reload, broker reconnect, integration reload. A naive "on message -> run actions" handler fires every `onChangeToOn` on every restart of any instance, e.g. all lights toggle, notifications spam, garage door actions re-run. Retained state on a state topic is normal and recommended, so this is not avoidable at the broker.

**Why it happens:**
Developers treat "message received" as "state changed". The MQTT client passes `msg.retain`; on replay it is `True`, whereas live-forwarded messages normally have retain cleared (unless a bridge/`retain_as_published` changes that). HA's own client tracks retained messages per subscription for this reason (verified in `mqtt/client.py`).

**How to avoid:**
- Triggers are **edge-based on a persisted last-known value**, not message-based: run actions only when the value differs from the stored previous value.
- Messages with `msg.retain == True` are used to *initialize/reconcile* the baseline and never trigger actions by default (make "run on initial retained value" an explicit, off-by-default option).
- Persist the last-processed state per device in `homeassistant.helpers.storage.Store` (or `RestoreEntity`) so a restart with an unchanged broker value is a no-op.
- Decide and document the missed-transition policy: an instance that was offline during a flip only sees the final retained value. The core value says "reliably triggers on every connected instance", but MQTT retained state cannot replay history. Offer optional "reconcile on start" (run actions for current state if it differs from last executed state) and make it visible in the UI.
- Never rely on QoS 0 for command/state topics that drive actions; use QoS 1 and accept at-least-once duplicates -> dedupe (Pitfall 3).

**Warning signs:**
Actions fire right after HA restart or after a broker restart; logs show actions triggered with no external publisher; `retain` flag `True` on handled messages.

**Phase to address:** P2 (baseline handling), P6 (re-trigger service must be the *only* deliberate way to force replay).

**Confidence:** HIGH.

---

### Pitfall 3: Action loops and echo across instances (command -> state -> actions -> state ...)

**What goes wrong:**
Several loop/echo shapes are specific to this design:
1. **Command/state double trigger.** UI toggle publishes to `command_topic`; something republishes to `state_topic`. If actions are bound to *both* topics (requirement: "both drive the same behavior"), each toggle runs actions twice.
2. **No state echo at all.** A non-optimistic MQTT switch/select never changes state in the UI unless someone publishes to `state_topic`. With N instances subscribing to the command topic and *each* echoing state, you get N duplicate state publishes (and N triggers); with none echoing, the UI toggle "snaps back".
3. **Action feedback loop.** An action (e.g. `switch.turn_on` on an entity that is itself a device of this integration, or a device on another instance) changes a state that is published to MQTT that triggers the same/other device's actions on all instances, possibly A -> B -> A across instances. The owner/follower split makes cycles invisible to any single instance.
4. **Config echo.** Applying a received central config calls `async_update_entry`/reloads, which republishes config, which is received again.

**Why it happens:**
The design has multiple writers of derived state (each instance) and a fan-out trigger (every instance executes). No single place sees a full cycle.

**How to avoid:**
- Exactly one trigger source per device: **the state topic is the sole trigger**. The command topic only requests a change; it never runs actions.
- Exactly one state-authority per device: **the owner instance** converts command -> state (retained) and is the only one echoing. Owner offline => commands are dropped; expose availability (Pitfall 9) so the UI shows unavailable instead of lying.
- Put an origin marker in every message this integration publishes (JSON state `{"v":"on","src":"<instance_uuid>","seq":n}` or MQTT5 user properties) and dedupe on `(src, seq)`. Keep raw scalar state topics supported for external publishers.
- Per-device re-entrancy guard + rate limit (e.g. max N executions per device in T seconds, then trip a Repairs issue and pause the device). This is the cheap defense against cross-instance cycles.
- For the config path: compare a content hash/`revision` before applying; only mutate storage if it differs; never reload the whole config entry to apply a remote device change (manage devices dynamically).

**Warning signs:**
Broker message rate climbing on integration topics; the same action logged 2xN times per toggle; CPU pegged after connecting a second instance; a device that toggles by itself.

**Phase to address:** P2 (single trigger source, guards), P4 (owner echo, origin markers, config hash), P7 (two-instance loop test).

**Confidence:** HIGH for mechanisms; MEDIUM on exact marker design (your call).

---

### Pitfall 4: Remotely provided action sequences execute with full local privileges (no trust model)

**What goes wrong:**
Anyone who can publish to the central-config topic can make every connected HA instance run `shell_command.*`, `rest_command.*`, `python_script.*`, `hassio.*`, `homeassistant.restart`, `lock.unlock`, `notify.*`, arbitrary `script.turn_on`, or Jinja templates that exfiltrate state. MQTT has **no per-message authentication**: the `owner` field in a payload is just text, so any client with write access can impersonate any owner. Broker credentials on IoT devices/ESPHome/Zigbee2MQTT bridges are commonly broad (`readwrite #`).

**Why it happens:**
Treating the broker as a trusted internal bus; PROJECT.md already flags this but "needs explicit design" often degrades into "documented in README".

**How to avoid (recommended design, opinionated):**
1. **Opt-in per instance, default off**: an instance only *publishes* its devices by default; *accepting* remote devices is a separate switch in the config entry.
2. **Approval gate**: remote devices/actions land as "pending" (Repairs issue or a UI list) and run only after the local admin approves. Store the **hash of the approved action sequence**; any change to remote actions invalidates approval and requires re-approval (or per-owner "trust and auto-approve" as an explicit advanced opt-in).
3. **Service allowlist/denylist enforced at execution time on the follower** (deny by default: `shell_command`, `rest_command`, `python_script`, `pyscript`, `hassio`, `homeassistant.restart/stop`, `script` calling unknown scripts, `automation.*` edits, `persistent_notification`/`notify` unless allowed). Never trust validation done by the owner.
4. **Broker ACLs as the real identity layer**: per-instance MQTT user, write only to `<prefix>/<own_instance_uuid>/#`, read all. Ship an example Mosquitto ACL in the docs. Bind `owner` to the topic path, and reject any payload whose `owner` field differs from the topic segment.
5. **Optional payload signing** (HMAC/Ed25519 with a shared/trusted key) as a later hardening step if ACLs are not enough; not needed for v1 if ACLs + approval exist.
6. Restrict templates in remote actions or run them via HA's normal template engine only after approval (templates can read all state).
7. Use TLS to the broker; document that plaintext MQTT over Tailscale is still LAN-trusted.

**Warning signs:**
Follower executes a sequence nobody approved; any topic under the config prefix is writable by non-HA clients; `owner` in payload not validated against the topic.

**Phase to address:** P5 -- design before P4 ships remote apply. Treat "remote apply without approval" as a release blocker.

**Confidence:** HIGH that the risk is real; MEDIUM on the specific mitigation set (design judgment).

---

### Pitfall 5: Broker used as the database -- lost retained messages cause mass deletion or silent drift

**What goes wrong:**
Followers interpret "retained config missing" as "device deleted". Then a broker without persistence (Mosquitto `persistence false`, container without a volume, add-on reinstall, broker migration) restarts empty and every follower deletes every remote device -- or an instance starting before the owner has republished sees an empty world. Related: MQTT has **no "end of retained messages" marker**, so during startup a follower cannot know whether it has received *all* retained config documents; acting on the partial set causes false deletions and flicker.

**Why it happens:**
Reconciling by set difference against an eventually-complete but unmarked stream.

**How to avoid:**
- **Owner instance holds the authoritative copy in its local `Store`** and republishes retained config + discovery on MQTT connect and when it sees HA birth (`homeassistant/status` = `online`). The broker is transport/cache only.
- Followers **never delete on absence**. Deletion requires an explicit signal: a tombstone message (`{"deleted": true, "rev": n}` retained for a TTL) or a signed/validated delete from the owner. Absence for a long grace period only marks a device "orphaned/unavailable" and raises a Repairs issue.
- Persist the follower's last-known remote config locally so behavior continues while the broker is empty or the owner offline.
- Prefer a **per-device retained document** under the owner's subtree over one monolithic config document (Pitfall 6), plus a small `index`/`manifest` retained message with `count` and `rev` so followers know when "complete" (or use a debounce/idle window).
- Include `schema_version` in every payload; ignore (do not crash on) unknown-newer versions.

**Warning signs:**
All remote devices vanish on all followers after a broker restart; devices flicker at HA start; `mosquitto.conf` has no `persistence true`.

**Phase to address:** P4.

**Confidence:** HIGH (MQTT spec has no end-of-retained signal; well-known operational failure); MEDIUM on chosen mitigation.

---

### Pitfall 6: One monolithic retained config document with multiple writers (last-writer-wins clobber)

**What goes wrong:**
A single `<prefix>/config` JSON containing all devices from all owners requires read-modify-write. Two owners saving at the same time (or one owner with stale local copy, e.g. after a restore from backup) silently overwrite each other's devices. Large documents also hit broker/client packet-size limits and make every small edit re-trigger a full re-parse on all instances.

**Why it happens:**
Simplicity of "one config topic"; the ownership model was chosen to avoid conflicts but a shared document reintroduces them physically.

**How to avoid:**
One retained topic per device (or per owner), each written by exactly one instance: `<prefix>/v1/<owner_uuid>/devices/<device_uuid>`. Never do read-modify-write across owners. Add monotonic `rev` per device; ignore messages with `rev <=` known. Keep payloads small (well under typical 256 KB defaults; some brokers/bridges are much lower).

**Warning signs:**
Devices from instance A disappear after instance B saves; config payload size grows with device count.

**Phase to address:** P4 (topic design), captured in ARCHITECTURE.md.

**Confidence:** HIGH.

---

### Pitfall 7: Deleting/unloading semantics -- discovery cleared at the wrong time, or not at all

**What goes wrong (three variants):**
1. **Cleared on unload.** Publishing empty discovery in `async_unload_entry` / shutdown wipes devices on all instances every time the user reloads the integration or restarts HA.
2. **Never cleared on remove.** `async_remove_entry` / device removal that forgets to publish the retained empty payload leaves "ghost entities" that reappear on every restart (the standard MQTT ghost-entity problem: retained discovery persists at the broker).
3. **Follower UI deletion deletes it for everyone.** Verified in HA core (`mqtt/entity.py`): when a user deletes an MQTT-discovered entity from the entity registry, `async_removed_from_registry` calls `async_remove_discovery_payload`, which publishes an empty **retained** payload to the discovery topic. A user deleting the entity on a *follower* therefore removes it for **all instances**, bypassing the "only the owner may delete" rule. Note also that `async_remove_config_entry_device` in the MQTT integration does *not* clear payloads (device removal and entity removal behave differently).
4. **Empty retained clears are also needed for state/config topics** (`retain=True`, empty string) -- a non-retained empty publish clears nothing.

**Why it happens:**
Not knowing that HA's MQTT integration itself issues the cleanup on entity-registry deletion, and conflating "temporary unload" with "permanent removal".

**How to avoid:**
- Clear discovery only in explicit user-initiated delete paths (subentry/device deletion confirmed in UI, plus `async_remove_entry` for the whole instance with a prompt), never on unload/shutdown.
- Delete flow: owner publishes empty retained to discovery topic(s) **and** publishes the config tombstone (Pitfall 5) **and** clears state/command topics it owns; then removes local storage. Make it idempotent and retryable if the broker is down (persist a "pending cleanup" list in Store; run on next connect).
- Mitigate follower-side deletion: use the follower's local device flow to reject/warn, and monitor for discovery topics of owned devices disappearing unexpectedly -> the owner **republishes** (self-healing), turning accidental follower deletions into a no-op. Also consider `enabled_by_default`/entity category choices so followers are less tempted to delete; document that follower deletion is not supported.
- The explicit multi-instance warning required by the project ("this happens on all connected instances") must appear in the delete confirmation dialog text (translation string), not just README.
- Publish discovery with `retain=True` -- and remember stale registry entries from the earlier retained discovery remain "unavailable" on an instance that was offline during deletion (empty retained leaves no tombstone at the broker): follower reconciliation must remove orphaned entity/device registry entries of ids it knows are gone.

**Warning signs:**
Entities reappear after HA restart; entity deletion on a follower makes the device vanish on the owner; unavailable orphan entities in follower registry after a delete.

**Phase to address:** P6 (delete semantics), with P4 supplying tombstones/republish.

**Confidence:** HIGH (source-verified for entity-registry removal behavior).

---

### Pitfall 8: Startup ordering -- MQTT not ready when `async_setup_entry` runs

**What goes wrong:**
`mqtt.async_subscribe` and `mqtt.async_publish` raise `HomeAssistantError` (`mqtt_not_setup_cannot_subscribe` / `mqtt_not_enabled_cannot_subscribe`) when the MQTT entry is not set up or is disabled. Setup order in HA is not guaranteed by alphabet or timing; a broker that is down at HA start puts the MQTT entry in retry. An unhandled exception in `async_setup_entry` leaves this integration in `SETUP_ERROR` (no automatic retry), while raising `ConfigEntryNotReady` gives automatic retry with backoff.

**How to avoid:**
- `manifest.json`: `"dependencies": ["mqtt"]` (hard requirement) -- verify with hassfest. Also handle the case where the user has no MQTT config entry (config flow abort `mqtt_required` with a clear message).
- In `async_setup_entry`: `if not await mqtt.async_wait_for_mqtt_client(hass): raise ConfigEntryNotReady("MQTT not available")` (helper waits up to 50 s and returns False if MQTT is not configured/disabled or times out -- verified in `mqtt/util.py`). Note it waits for *setup*, not for an established connection; publishes then depend on HA's client.
- **Do not publish before you have consumed retained config.** Required ordering: (1) wait for MQTT, (2) subscribe to central config and `await mqtt.async_on_subscribe_done(...)` (QoS must match the subscription), (3) allow a settle window/manifest completeness (Pitfall 5), (4) reconcile, (5) only then republish owned discovery/config, (6) subscribe to state topics. Publishing local (stale) state first overwrites newer central state.
- Everything registered must be cleaned in `async_unload_entry` (unsubscribe callbacks via `entry.async_on_unload`, cancel scripts/tasks) so reload works.
- MQTT entry reload: HA restores other integrations' subscriptions (`async_restore_tracked_subscriptions`, verified), but *do not assume* -- include a test that reloads the MQTT integration while the integration is loaded.

**Warning signs:**
"MQTT not set up" errors in the log at start; integration stuck in "Failed to set up"; works only after manual reload; stale local config overwriting central.

**Phase to address:** P2.

**Confidence:** HIGH (source-verified).

---

### Pitfall 9: Availability, LWT, and the shared `homeassistant/status` topic in a multi-instance setup

**What goes wrong:**
Entities created by discovery have no `availability` unless you provide it, so they look healthy when the owner (the only state echo) is dead: commands silently vanish. Reusing `homeassistant/status` for liveness is wrong: every HA instance on the broker publishes birth/will there with the default MQTT options, so one instance restarting says `online`/`offline` for "Home Assistant" as a whole. Also, two HA instances sharing the same MQTT `client_id` (copied configs, clones) kick each other off the broker in a reconnect loop.

**How to avoid:**
- Per-instance availability topic `<prefix>/<instance_uuid>/status` with a proper LWT (`offline`, retained) and an `online` retained publish after start; include it in the discovery `availability` list with `availability_mode: all` for the owned device. Because you cannot set a will on HA's shared client, publish `online`/`offline` on graceful shutdown (`EVENT_HOMEASSISTANT_STOP`) and provide a periodic heartbeat with timestamp; followers treat stale heartbeat as offline. State honestly that a hard crash cannot be detected without the LWT (limitation to document, or ship an optional own paho connection -- not recommended).
- Use `homeassistant/status` birth only as a *trigger* to republish discovery (per the official recommendation to avoid broker IO load), not as identity.
- Require unique MQTT `client_id` per instance in docs.

**Phase to address:** P4.

**Confidence:** MEDIUM-HIGH (birth-message behavior from official docs; the LWT limitation follows from using HA's shared client).

---

### Pitfall 10: Instance identity -- cloned/restored instances share a UUID, or the ID is derived from something mutable

**What goes wrong:**
"Owner instance" needs a stable identity. If it is derived from hostname, HA name, or `location_name`, a rename changes ownership and orphans devices. If it is a UUID stored only in the config entry, restoring a backup or cloning a VM/LXC to a second instance (very common in the stated test bed with LXC + haos) yields **two instances claiming the same owner**, both writing to the same subtree and both believing they are the sole authority -- ghost duplicates, fighting republishes.

**How to avoid:**
- Generate a random `instance_uuid` at config-entry creation and store in entry data; expose a friendly, editable *display name* separately.
- Detect collisions: include a per-boot `session_id` in the retained instance heartbeat; if an incoming heartbeat for *your own* `instance_uuid` carries a different `session_id`, raise a Repairs issue ("another instance uses the same identity -- reset identity") and stop publishing.
- Provide an explicit "regenerate identity / transfer ownership" action (owner move is out of scope for v1 but the uuid design must not preclude it).
- Do not use HA's `helpers.instance_id` as-is for the same reason (it is copied by clones) -- treat it as a hint only.

**Warning signs:**
Two instances alternately republish the same topics; devices show wrong owner after restore.

**Phase to address:** P4.

**Confidence:** MEDIUM (design reasoning; `instance_id` clone behavior is well known).

---

### Pitfall 11: Entity and device IDs are instance-local -- shared actions reference things that don't exist elsewhere

**What goes wrong:**
An action sequence authored on instance A with the UI action selector routinely contains `device_id` (device actions), area/floor/label targets, or `entity_id`s that exist only on A. On instance B the same YAML errors (`Unable to find referenced entities`), fails silently in the background, or -- worse -- a `device_id` accidentally resolves to something different. The requirement "each executing them locally" implicitly assumes identical entity naming across instances.

**How to avoid:**
- At authoring time, warn on/forbid `device_id`-based actions and non-entity targets in synced devices (accept only `action:` service calls with `entity_id` targets, `data`, and a limited set of flow controls).
- At follower apply time, validate: schema (`cv.SCRIPT_SCHEMA`), *then* the second-stage HA-aware validation (`homeassistant.helpers.script.async_validate_actions_config`), then check referenced entity IDs exist locally; if not, show status "needs attention" with a Repairs issue listing the missing entities rather than silently no-op.
- Consider (v2) a per-instance entity mapping table; for v1, document "entity IDs must match across instances".
- Execution errors must be surfaced (log + event + device status attribute), not swallowed; use `continue_on_error` only when the user chose it.

**Warning signs:**
Actions "work on the owner but not on follower"; `ServiceNotFound`/`Unable to find referenced entities` in follower logs; repairs empty despite failures.

**Phase to address:** P3 (authoring constraints), P4 (follower validation), P5 (allowlist shares the validator).

**Confidence:** HIGH.

---

### Pitfall 12: Blocking the MQTT callback / unmanaged script tasks / overlapping runs

**What goes wrong:**
Running the action sequence inside the subscription callback and awaiting it blocks message processing when a sequence contains `delay`, `wait_template`, or slow service calls (HA's MQTT client warns that messages are high volume and callbacks should be cheap). Rapid flips (`on -> off -> on`) start overlapping sequences that finish out of order, leaving the physical result opposite to the final state. Tasks not tracked by the config entry survive unload, causing "Task was destroyed but it is pending"-type noise and double execution after a reload.

**How to avoid:**
- Subscription callback is a `@callback` that only records the value and schedules work via `entry.async_create_background_task(...)`.
- One `homeassistant.helpers.script.Script` (or equivalent runner) per device/option with explicit `script_mode`: default `restart` for state-driven on/off pairs (the latest state wins) with `queued` as an advanced option; expose `max_exceeded` behavior. Cancel all running scripts in `async_unload_entry` (`script.async_stop()`).
- Debounce identical values; treat `on` and `off` sequences of the same device as one run-group so an `off` cancels a pending `on` sequence.
- Set a hard timeout/limit for remote sequences (Pitfall 4).

**Warning signs:**
MQTT message backlog; end state opposite to last message after rapid toggling; actions continue after integration reload.

**Phase to address:** P2.

**Confidence:** HIGH.

---

### Pitfall 13: Config-flow / lifecycle design that fights HA (entry-per-device, reload loops, storage in the wrong place)

**What goes wrong:**
- Modeling each device as its own config entry makes synced devices awkward: remote creation/removal needs programmatic entry creation, and each change triggers reloads.
- Update listener + `async_update_entry` on remote sync triggers `async_reload` -> republish -> receive -> update ... (Pitfall 3.4).
- Select devices with a variable number of options, each with an action list, do not fit a linear config flow: the `ActionSelector` returns a raw list of dicts, and multi-step "add another option" loops get brittle (lost state on abort, no validation of the action structure).
- Storing remote-derived state (approvals, last-executed values, rev counters) in `entry.data` forces reload on every change.

**How to avoid:**
- One config entry per HA instance (holds instance UUID, options like "accept remote devices", allowlist) with **config subentries** for locally owned devices (HA's supported mechanism for child items with own flows; confirm minimum HA version when pinning `hacs.json` `homeassistant`), or an options-flow menu. Remote (follower) devices live in `Store`, not in entries.
- No blanket reload in the update listener; apply diffs dynamically. Guard `async_update_entry` with an equality check.
- Validate every action list returned from the selector with `cv.SCRIPT_SCHEMA` + `async_validate_actions_config` inside the flow and show errors on the field.
- Use `entry.runtime_data` (typed) rather than `hass.data[DOMAIN]` dicts; version the entry (`VERSION`, `async_migrate_entry`) from the first release -- config schema *will* change and users of a HACS integration are not migrated by hand.
- Confirm the `ActionSelector` renders acceptably in a flow dialog early in a spike (visual editor vs YAML fallback, dialog size) before committing the UX (MEDIUM-confidence area).

**Warning signs:**
Repeated "Reloading configuration entry" logs; flow loses entered data when validation fails; no migration path when changing the payload shape.

**Phase to address:** P3 (flow design), P4 (no-reload sync).

**Confidence:** MEDIUM-HIGH (lifecycle docs verified; subentry fit and ActionSelector-in-flow rendering are judgment/need spike).

---

### Pitfall 14: MQTT Discovery payload details that bite (Select mapping, IDs, prefix)

**What goes wrong:**
- **StateValue vs StateFriendlyName.** MQTT `select` `options` is a flat list that serves as both display text and payload. The requirement stores a `StateValue` and a friendly name per option. Naively putting friendly names in `options` publishes friendly names on the wire; putting values shows raw values in the UI. Correct approach needs `value_template`/`command_template` mapping (Jinja dict lookup) or having the trigger side map friendly-name <-> value; special characters/quotes in names break hand-built templates.
- Unknown payload on `state_topic` (external publisher sends a value not in `options`) puts the select into an invalid/unknown state and logs errors; must be handled (ignore + log once, or an "unknown" behavior).
- `unique_id` derived from the *name* -> renaming a device/option creates a new entity and loses history, and breaks the registry link. Use UUIDs.
- `object_id` in discovery does not control the `entity_id` (official docs: it is derived from the name; use `default_entity_id`); relying on it yields unpredictable `entity_id`s, which then breaks actions/dashboards referencing them across instances. Verify the exact key supported by the minimum HA version pinned.
- Custom `discovery_prefix` on some instances: followers with a different prefix never see the entities. Read the local MQTT entry option and raise a Repairs issue on mismatch.
- Discovery JSON must be valid per component schema; a schema error is only logged by the MQTT integration -- the publishing integration gets no feedback. Validate payloads in unit tests against a real HA MQTT discovery run (test with `pytest-homeassistant-custom-component` + MQTT mock).
- Retained flag: discovery must be `retain=True`; command topics must never be retained (a retained command would re-execute on every reconnect); ignore any command message with `msg.retain == True`.

**Phase to address:** P2 (Switch), P3 (Select mapping).

**Confidence:** HIGH for docs-backed items; MEDIUM for exact `default_entity_id` availability by version.

---

### Pitfall 15: HACS/hassfest validation failures found only at release time

**What goes wrong:**
Repo passes locally but fails the two required checks (hassfest + `hacs/action` with `category: integration`), or fails default-store inclusion later:
- Layout: exactly **one** integration under `custom_components/<domain>/`; `hacs.json` in repo root with at least `name`, **no unknown keys**.
- `manifest.json` must contain for HACS: `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, `version` (custom integrations need `version` in SemVer/CalVer, verified in HA dev docs); hassfest also requires ordering of keys, `config_flow: true`, `integration_type`, `iot_class`, `dependencies` valid.
- `strings.json`/`translations/en.json` must cover every config-flow step, error, abort, option, selector and service; missing keys fail at runtime UI or hassfest. Repairs issue and delete-confirmation texts need translation keys too (project needs German UI: add `translations/de.json`).
- `services.yaml` must exist for any registered service (the re-trigger service) and match the schema.
- Brand: HACS requires a `brand` directory with at least `icon.png`; per current sources HACS accepts `custom_components/<domain>/brand/icon.png` (change reported for Feb 2026) so the brands check need not be ignored -- verify against current HACS docs at implementation time rather than adding `ignore: brands`.
- GitHub repo needs description, topics, issues enabled, README/info file; the HACS action checks these (`archived`, `brands`, `description`, `hacsjson`, `images`, `information`, `issues`, `topics` are the checkable items). Do not "green" CI with `ignore:` lists if default-store inclusion is a goal.
- Manifest `version` must be bumped in step with the release tag; HACS installs from the release; tag/version drift shows wrong versions or stale code. Automate: tag -> workflow writes manifest version -> release zip.
- `homeassistant` minimum version in `hacs.json` must match APIs used (subentries, `runtime_data`, `async_on_subscribe_done`).

**How to avoid:**
Wire `hassfest` + `hacs/action` (push, PR, schedule) in **P1**, before any feature code, with no `ignore:` entries; add Ruff (120), pytest, and a release workflow. Run the pipeline on an empty skeleton so failures are attributed to config, not code.

**Warning signs:**
CI red on first push; HACS "repository structure" error in HA UI on install; version shown in HACS != manifest.

**Phase to address:** P1 (setup), re-verify P7.

**Confidence:** HIGH (HACS docs fetched); MEDIUM on brand-directory change (search snippet, single source -- verify).

---

## Moderate Pitfalls

### Pitfall 16: Payload parsing -- `on`/`ON`/`true`/`1`, JSON state, whitespace, encoding

**What goes wrong:** External publishers (Zigbee2MQTT, Tasmota, scripts) use different truthy values; HA's subscription decodes UTF-8 and skips messages that fail decoding with only a warning.
**Prevention:** Configurable `payload_on/payload_off` (same as MQTT switch) plus optional `value_template`; case-insensitive strip; explicit unknown-payload policy. Unit tests with the tricky values.
**Phase:** P2.

### Pitfall 17: Test bed treats mocks as truth

**What goes wrong:** Unit tests with a mocked MQTT pass while real retained/reconnect/multi-instance behavior fails (Pitfalls 2, 3, 5, 7 are invisible to mocks).
**Prevention:** Include a Docker Mosquitto (persistence on and off) integration test tier and a documented two-HA-instance manual script (haos-op3050-1 + lxc-haos-104) covering: restart, broker restart with/without persistence, owner offline, follower entity deletion, clone with same UUID. Use `pytest-homeassistant-custom-component` for unit level.
**Phase:** P2 (harness), P7 (scenarios).

### Pitfall 18: Re-trigger service semantics

**What goes wrong:** "Re-trigger actions on all connected instances" implemented as publishing the state again is indistinguishable from a real change (deduped away by Pitfall 2/3 guards) or, if it bypasses them, is an unauthenticated remote-execution broadcast.
**Prevention:** Dedicated control message (`<prefix>/control/retrigger` with `device`, `nonce`, `src`), non-retained, QoS 1, dedupe on nonce, rate limited, honors the follower's approval/allowlist. Service returns immediately with a summary; never sets retain (a retained re-trigger would re-run on every reconnect).
**Phase:** P6.

### Pitfall 19: Non-idempotent, non-serialized publishing on connect

**What goes wrong:** Multiple triggers (MQTT reconnect, HA birth, setup, options change) each start a full republish of all devices concurrently; interleaved publishes leave an older revision as the last retained value.
**Prevention:** One serialized "sync" coroutine guarded by a lock with coalescing; always publish latest rev from Store; debounce triggers.
**Phase:** P4.

### Pitfall 20: Logging secrets and full action payloads

**What goes wrong:** Debug logs and Repairs/diagnostics dump action data (tokens in `rest_command`/`notify` data, webhook IDs) and broker credentials.
**Prevention:** Implement `diagnostics.py` with `async_redact_data`; log action *summaries* (service names) only.
**Phase:** P7.

### Pitfall 21: Sequential/dynamic entity churn from wildcard subscriptions

**What goes wrong:** Subscribing `<prefix>/#` or a broad wildcard for config plus rapid subscribe/unsubscribe on device edits hits known HA MQTT subscription-management bugs (see core issues on quick unsubscribe/resubscribe of wildcard topics) and floods the client.
**Prevention:** One stable wildcard subscription for config (`<prefix>/v1/+/devices/+`) created once per entry; per-device state topic subscriptions created/removed idempotently and not in tight loops; avoid re-subscribing the same topic rapidly.
**Phase:** P4.
**Confidence:** MEDIUM (community/core issues; version-dependent).

---

## Minor Pitfalls

### Pitfall 22: Blocking I/O in the event loop
File reads (translations, Store outside helper), `yaml.load` etc. must be executor-based; HA logs "Detected blocking call" and future versions may raise. **Prevention:** use `Store` helper, `hass.async_add_executor_job`. **Phase:** P2.

### Pitfall 23: Forgetting `hass.data`/runtime cleanup and duplicate setups
Not using `entry.async_on_unload` for every unsub leaks listeners; reload doubles triggers (= double action execution). **Prevention:** central cleanup list; test "load -> reload x3 -> 1 execution per message". **Phase:** P2.

### Pitfall 24: `single_config_entry` omission
Two entries on one HA instance would both publish as owner. **Prevention:** `"single_config_entry": true` in manifest (verified as a supported key) since one entry per instance is the model. **Phase:** P1/P3.

### Pitfall 25: Non-English-only UI text
Project expects German UI; delete warning and security prompts missing in `de.json` cause English fallback for the most safety-critical text. **Prevention:** ship `en.json` + `de.json`, both checked in CI. **Phase:** P3/P6.

### Pitfall 26: Topic naming without version segment
No `v1` in the topic prefix makes future breaking schema changes impossible without ghost documents. **Prevention:** `<prefix>/v1/...` from the start. **Phase:** P4.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single retained JSON config for all devices | Simple read/write | Multi-writer clobber, size limits, full re-parse per edit | Never (per-device docs cost almost nothing more) |
| Run remote actions without approval "for now" | Sync works immediately in demo | Remote code execution baked into first users' setups; retrofitting approval breaks their flows | Never in a public release; OK behind a dev-only flag |
| Trigger on every message (no edge detection) | 10 lines less | Startup action storms (Pitfall 2) | Never |
| Derive `unique_id` from device name | Human-readable | Rename = new entity, lost history, orphan registry entries | Never |
| Skip `async_migrate_entry`/`schema_version` in v1 | Faster | Every later change is a breaking change for HACS users | Never |
| Mock-only MQTT tests | Fast CI | Retained/reconnect/multi-instance bugs escape | Only for unit tier, with an integration tier alongside |
| Ignore `brands` etc. in HACS action | Green CI | Blocks default-store inclusion later | Only temporarily in P1 with a tracked TODO |
| Hard-code `homeassistant` discovery prefix | Works on defaults | Silent no-entities on customized instances | v1 acceptable if a Repairs check flags mismatch |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| HA MQTT (`mqtt.async_subscribe`) | Calling before MQTT entry is set up; unhandled `HomeAssistantError` | `dependencies: ["mqtt"]`, `async_wait_for_mqtt_client`, raise `ConfigEntryNotReady` |
| HA MQTT publish | Empty clear without `retain=True`; publishing discovery as non-retained | `await mqtt.async_publish(hass, topic, "", qos=1, retain=True)` for clears; discovery retained |
| HA MQTT discovery removal | Assuming device deletion clears payload | Entity-registry removal clears (source-verified); device removal (`async_remove_config_entry_device`) does not -- handle both |
| Retained subscription | Treating replay as a change | Check `msg.retain`, persist baseline |
| `mqtt.async_subscribe` completion | Assuming subscribed == broker confirmed (subscriptions are debounced/queued) | `mqtt.async_on_subscribe_done` (QoS must match) before publishing dependent state |
| Broker (Mosquitto) | No persistence, no ACLs, `allow_anonymous true` | Document required broker config; provide ACL example; warn in README/setup flow |
| Broker bridges/Zigbee2MQTT | Publishes retained on command topics; `retain_as_published` changes replay flag semantics | Ignore retained on command topics; document assumptions |
| Script helper | Passing only `cv.SCRIPT_SCHEMA`-validated data to `Script` | Also run `async_validate_actions_config`; device actions / conditions / `wait_for_trigger` need the second stage |
| HACS | Adding `hacs.json` keys not in schema; multiple integrations per repo | Only documented keys; one integration in `custom_components/` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Republish all discovery on every trigger | Broker/IO load, log noise | Coalesced sync, publish only on diff/HA birth | Roughly >50 devices or >3 instances |
| Per-message Store writes for last state | Disk wear on SD/eMMC hosts (Odroid N2+) | Debounced writes (`Store.async_delay_save`) | High-frequency state topics |
| Action loop between instances | Broker message storm, CPU at 100% | Rate limit + trip breaker per device | Instant once a cycle exists |
| Large retained payloads | Slow startup, bridge drops | Per-device docs, small payloads | Hundreds of KB total |
| Wildcard resubscribe churn | Subscription errors, missed messages | One stable wildcard, idempotent per-device subs | Frequent edits |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Auto-applying remote action sequences | Broker write access == RCE on every instance (Critical) | Opt-in, approval by hash, allowlist, ACLs (Pitfall 4) |
| Trusting `owner` field in payload | Impersonation of any owner | Bind owner to topic path + ACL; reject mismatch |
| Remote sequences may contain templates | State exfiltration via notify/rest_command | Deny outbound services by default; approval shows rendered summary |
| Re-trigger broadcast unauthenticated | Remote execution nudge | Nonce, rate limit, same approval gating (Pitfall 18) |
| Plaintext MQTT credentials in entry data shown in diagnostics/logs | Credential leak | Reuse HA's MQTT connection (don't store creds); redact diagnostics |
| Follower can delete owner's discovery | Denial of service / ownership bypass | Owner self-heals republish; warn in UI (Pitfall 7) |
| Retained command topics | Re-execution on every reconnect | Ignore retained commands |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Delete dialog does not say it removes the device on all instances | Surprise deletion of other people's/instances' setups | Explicit, translated warning listing known connected instances |
| Follower silently ignores failing actions | "It doesn't work" with no signal | Status attribute + Repairs issue with missing entity list |
| UI toggle snaps back when owner offline | Looks broken | Availability tied to owner heartbeat |
| Pending approval invisible | Remote devices appear to do nothing | Notification/Repairs entry with a review screen showing the action summary |
| Non-owner edit attempt gives generic error | Confusion | Read-only device page with "owned by <name>" and reason |
| Select option rename changes value | Broken external publishers | Immutable `StateValue`, editable `StateFriendlyName` |

## "Looks Done But Isn't" Checklist

- [ ] **Startup safety:** Often missing suppression of retained-replay triggers -- verify: restart HA and broker with unchanged state, expect zero action executions.
- [ ] **Delete:** Often missing empty *retained* clears and tombstone -- verify: delete on owner, restart every instance, no ghost entities and no orphan registry entries; delete entity on follower and confirm owner self-heals.
- [ ] **Unload vs remove:** Often clears discovery on unload -- verify: reload integration, devices persist on all instances.
- [ ] **Broker restart without persistence:** Verify followers keep devices and owner republishes; no mass deletion.
- [ ] **Two-instance loop test:** A device whose action sets another integration device that maps back; verify the breaker trips.
- [ ] **Same-UUID clone:** Verify collision detection raises a Repairs issue.
- [ ] **Remote apply:** Verify unapproved remote action does NOT execute; changed action re-requires approval; denied services blocked at execution.
- [ ] **Reload x3:** One message => exactly one execution.
- [ ] **MQTT not up at start:** Broker down at HA boot -> integration retries and recovers with no manual reload.
- [ ] **Translations:** Every step/error/abort/repair string exists in `en.json` and `de.json`; hassfest green.
- [ ] **HACS:** `hacs/action` green with no `ignore`; release zip installs from HACS UI on a clean instance; manifest version == tag.
- [ ] **Select mapping:** Friendly names with quotes/umlauts/`{}` round-trip through discovery; unknown payload handled.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Ghost discovery topics (retained, orphaned) | LOW | Provide a "clean up orphaned topics" service/diagnostic listing `<prefix>/#` retained topics not in the owner's Store; publish empty retained for each; document `mosquitto_sub -t '#' -v --retained-only` + `mosquitto_pub -r -n` |
| Broker lost retained data | MEDIUM | Owner republishes from Store (auto on connect); followers use cached remote config; "Resync now" button |
| Mass false-deletion on followers | HIGH | Requires owner republish + follower re-approval if approvals were dropped; prevented by never-delete-on-absence; keep approval hashes in Store separate from device data |
| Action loop storm | MEDIUM | Circuit breaker pauses the device; Repairs issue; user disables device; `retain` clear of offending topic |
| Duplicate instance UUID | MEDIUM | "Reset identity" action creates new UUID; owner devices re-registered under new owner (requires explicit ownership transfer design) |
| Malicious/unwanted remote action executed | HIGH | Rotate broker credentials, review ACLs, clear retained config topics, audit logs of executed action summaries (keep an execution log) |
| Bad config schema release | MEDIUM | `async_migrate_entry` + `schema_version` tolerance; fast patch release via HACS |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Discovery duplication/echo | P4 | Two-instance test: exactly one entity per device per instance; only owner publishes discovery topics |
| 2 Retained replay triggers | P2 | Restart HA/MQTT/broker: 0 executions; live change: 1 execution |
| 3 Loops/echo | P2 + P4 + P7 | Single trigger source; N-instance toggle = N executions total (one per instance); breaker test |
| 4 Remote-action security | P5 (before P4 ships apply) | Unapproved/denied actions never run; ACL example tested |
| 5 Broker as database | P4 | Mosquitto without persistence: no deletion, owner republishes |
| 6 Monolithic config doc | P4 | Topic layout is per-device, one writer each |
| 7 Delete/unload semantics | P6 | Delete/reload/follower-delete scenarios in checklist |
| 8 Startup ordering | P2 | Broker down at boot; MQTT reload while loaded |
| 9 Availability/LWT | P4 | Owner stopped -> follower entities unavailable within heartbeat timeout |
| 10 Instance identity | P4 | Cloned instance detected |
| 11 Instance-local IDs | P3/P4/P5 | Missing entity on follower -> Repairs issue, no silent failure |
| 12 Blocking/overlap | P2 | Rapid on/off/on final state correct; unload cancels runs |
| 13 Config-flow/lifecycle | P3/P4 | No reload loops; migration test |
| 14 Discovery payload details | P2/P3 | Select round-trip; prefix mismatch issue |
| 15 HACS/hassfest | P1, P7 | Green CI, clean HACS install |
| 16-26 | as listed | as listed |

## Sources

- Home Assistant MQTT integration docs (discovery topics, empty-payload removal, retained/ghost-entity warning, birth message, unique_id, discovery prefix, `default_entity_id`, `migrate_discovery`): https://www.home-assistant.io/integrations/mqtt/ -- HIGH
- HA core source `mqtt/entity.py` (`async_removed_from_registry` -> `async_remove_discovery_payload` publishes empty retained payload on entity registry removal): https://github.com/home-assistant/core/blob/dev/homeassistant/components/mqtt/entity.py -- HIGH
- HA core source `mqtt/__init__.py` (`async_remove_config_entry_device` does not clear payloads; subscriptions restored across MQTT client reinit): https://github.com/home-assistant/core/blob/dev/homeassistant/components/mqtt/__init__.py -- HIGH
- HA core source `mqtt/util.py` (`async_wait_for_mqtt_client`, 50 s timeout, waits for setup not connection) and `mqtt/client.py` (subscribe raises when MQTT not set up, reconnect resubscribe, retained tracking, UTF-8 decode-skip, callback exceptions) -- HIGH
- HA developer blog, MQTT subscription status callback (`async_on_subscribe_done`): https://developers.home-assistant.io/blog/2025/11/23/mqtt-subscribe-wait/ -- HIGH
- HA developer docs: config entries lifecycle (setup retry, unload/remove, migration) https://developers.home-assistant.io/docs/config_entries_index/ ; manifest (`dependencies`, `version`, `single_config_entry`, `integration_type`) https://developers.home-assistant.io/docs/creating_integration_manifest/ -- HIGH
- HA script syntax docs (`continue_on_error`, parallel caveats) https://www.home-assistant.io/docs/scripts/ -- HIGH; two-stage action validation (`SCRIPT_SCHEMA` then `async_validate_actions_config`) from community PR write-up (extended_openai_conversation #187) -- MEDIUM
- HACS integration publishing requirements https://hacs.xyz/docs/publish/integration/ ; HACS action checks https://www.hacs.xyz/docs/publish/action/ -- HIGH; local brand icon acceptance (Feb 2026) from third-party CI PR descriptions -- MEDIUM (verify)
- Core issues on MQTT wildcard resubscribe / concurrency (#183226, #67231), discovery removal registry cleanup (#32509, #32693, #77728) -- MEDIUM
- Community article on MQTT ghost entities: https://vdaluz.com/blog/ghost-entities-mqtt-discovery-leaves-behind -- LOW-MEDIUM
- Architectural recommendations (ownership topics, approval hashing, heartbeat, breaker, identity collision) -- project-specific judgment, MEDIUM; the MQTT spec's lack of an end-of-retained marker and of per-message authentication is standard protocol knowledge -- HIGH

---
*Pitfalls research for: HA MQTT-driven action-sequence integration with multi-instance sync*
*Researched: 2026-09-28*
