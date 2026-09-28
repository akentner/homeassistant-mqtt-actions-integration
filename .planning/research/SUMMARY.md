# Project Research Summary

**Project:** MQTT Actions Integration (HACS custom HA component)
**Researched:** 2026-09-28
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is a controller, not an entity provider. The integration publishes MQTT Discovery so HA's built-in `mqtt` integration creates the Switch and Select entities on every instance. It watches one retained state topic per device and runs the configured action sequence locally on every instance through HA's `Script` helper. No competitor does this. `remote_homeassistant` and the abandoned `mqtt-share-remote` sync existing entity states and forward service calls, and they suffer from ghost entities, loops and stale state. The real alternative is hand-written MQTT YAML plus an automation on each instance. The product's value is removing that duplication.

Recommended approach:
- Target Python 3.14 and HA 2026.9.x, with zero third-party runtime dependencies.
- Use uv, Ruff and pytest-homeassistant-custom-component (PHACC).
- Reach the broker only through HA's MQTT API, behind a single `MqttGateway` seam.
- Model owned devices as config subentries. Keep devices owned by other instances as read-only mirrors in `Store`.
- Publish one retained config document per device, with the owner as its single writer. Do not use a monolithic config document.
- The state topic is the only trigger source. Set `command_topic == state_topic` (Architecture Option A).
- Retained replay only sets a baseline. Actions run only on a real edge against a persisted `last_acted`.

Key risks:
1. **Remote code execution.** Remote action sequences run with full local privileges, and MQTT has no per-message authentication. The trust gate (default deny, hash-bound approval, service denylist, owner bound to topic path, documented ACLs) must ship in the same phase as follower apply.
2. **Retained-message semantics.** These cause startup action storms, undelivered deletes (an empty retained publish leaves no tombstone), mass false deletion if the broker loses data, and no end-of-replay marker.
3. **HA's own MQTT behavior.** Deleting an MQTT-discovered entity on a follower publishes an empty retained discovery payload, which removes it for everyone. The owner must self-heal by republishing.

## Key Findings

**Stack (HIGH).**
- Python 3.14 / HA 2026.9.x (`hacs.json` floor `2026.9.0`). The current PHACC 0.13.367 pins HA 2026.9.4.
- `manifest.json` has `dependencies: ["mqtt"]`, no `requirements`, and `single_config_entry: true`.
- Use `mqtt.async_wait_for_mqtt_client`, `async_subscribe` and `async_publish`. Register unsubscribes with `entry.async_on_unload`.
- Use `helpers.script.Script` with `cv.SCRIPT_SCHEMA` and `script.async_validate_actions_config`. `ActionSelector` returns unvalidated data, so validate on input and on every broker payload.
- Device-based MQTT Discovery under the owner's configured discovery prefix.
- `entry.runtime_data`, `Store`, `import probatio`, and `translations/{en,de}.json`.
- hassfest and `hacs/action` pinned by SHA. Local brand icon at `custom_components/<domain>/brand/icon.png`. Dependabot.
- Do not pin `homeassistant`, `pytest` or `pytest-asyncio` (PHACC pins them). Do not use `hass.data[DOMAIN]`, YAML config, `strings.json`, or `device_id` targets.

**Features (MEDIUM).**
- v1 table stakes:
  - Config Flow and instance identity.
  - Switch and Select with owner-only edit and delete.
  - Discovery with UUID `unique_id`s and clean removal.
  - One state path, loop protection, and startup semantics.
  - Central retained config with `schema_version`.
  - Trust opt-in.
  - Non-retained re-trigger service.
  - Error surfacing, README, en/de translations, diagnostics, tests, HACS CI.
- v1.x: instance roster, re-trigger ack, Repairs, per-instance participation, test-actions button, import/export and resync, ownership transfer, Button and Number domains.
- v2+: signed config, per-instance entity mapping, Light, Cover and Climate.
- Anti-features: multi-writer editing, referencing local scripts by name, retained commands or re-trigger, auto-accepting remote config, own broker connection, custom action editor, exactly-once guarantees.

**Architecture (MEDIUM-HIGH).**
- Components:
  - Domain core (no I/O).
  - `MqttGateway`, the only importer of `components.mqtt` and the seam for a `FakeBroker`.
  - `DeviceRegistry` (owned from subentries, mirrored from `Store`).
  - `SyncManager` (reconcile on setup, change and every reconnect; owner pinning; trust gate; prune).
  - `DiscoveryPublisher` (owner only).
  - `StateTracker` (retain-aware baseline, dedupe, state-before-config cache).
  - `ActionRunner` (serial queue per device, `Script`, circuit breaker).
  - services, repairs, diagnostics.
- Topics:
  - `<base>/v1/devices/<id>/config` (retained, owner-only writer, holds actions).
  - `<base>/v1/devices/<id>/state` (retained).
  - `<base>/v1/retrigger` (non-retained, `request_id` dedupe).
  - Standard discovery topic (retained, contains no actions).
- The instance ID is a random UUID in the config entry, not HA's `instance_id`.

**Pitfalls (MEDIUM-HIGH). Top five with prevention:**
1. Remote actions run with full privileges. Prevent with opt-in, hash-bound approval, an execution-time denylist, owner bound to the topic path, and ACL docs.
2. Retained replay re-triggers actions. Prevent with edge detection against persisted `last_acted`; ignore retained commands.
3. Loops and echoes. Prevent with a single trigger source, config hash compare, `request_id` dedupe, and a per-device circuit breaker.
4. The broker is not a database. Never delete on absence. The owner's `Store` is authoritative and it republishes on connect. Followers cache mirrors and use a grace window or manifest for pruning.
5. Delete and unload semantics. Clear discovery only on explicit, confirmed delete, never on unload. The owner self-heals against follower entity deletion. The all-instances warning needs a dedicated confirm step.

Also: startup ordering (`ConfigEntryNotReady`, subscribe before publish), Select StateValue/FriendlyName templates, instance-local `device_id`/entity IDs, and blocking or overlapping runs.

## Implications for Roadmap (suggested 5 phases)

The researchers proposed 4 phases (Architecture) and 7 (Pitfalls). This merges them into 5.

1. **Scaffold, CI and Foundation.**
   - Delivers repo skeleton, hassfest, `hacs/action`, Ruff and pytest workflows, domain core, `MqttGateway` plus fake, hub config flow with instance UUID and `single_config_entry`, the `v1` topic segment, and `schema_version`.
   - Avoids Pitfalls 15, 24, 26.
   - Research: standard, skip.
2. **Single-instance Switch vertical slice.**
   - Delivers subentry flow with `ActionSelector` and validation, `DiscoveryPublisher`, `StateTracker` (baseline, `last_acted`), `ActionRunner`, availability, error surfacing, and a Mosquitto integration test tier.
   - Avoids Pitfalls 2, 3 (single trigger), 8, 12, 14, 16, 22, 23.
   - Research: an early spike on `ActionSelector` in a subentry flow dialog (LOW confidence).
3. **Select device and state semantics.**
   - Delivers option list with immutable StateValue and editable FriendlyName, generated `value_template`/`command_template` with escaping, unknown-payload policy, per-option Scripts, and authoring constraints (warn on `device_id`).
   - Avoids Pitfalls 11, 13, 14.
   - Research: spike on the templates and on `default_entity_id` availability.
4. **Trust model, central config sync and ownership.**
   - Trust gate first: default deny, hash-bound approval, denylist, owner bound to topic path.
   - Owner reconcile and republish on reconnect, follower mirror in `Store`, owner pinning, rev handling, never delete on absence, tombstone or grace-window pruning, registry cleanup, and Repairs for missing entities.
   - Confirm-step delete with the all-instances warning, idempotent pending-cleanup, heartbeat/availability decision, clone detection, and serialized coalesced publishing.
   - Avoids Pitfalls 1, 4, 5, 6, 7, 9, 10, 11, 13, 19, 21.
   - Research: needs deeper research (`/gsd-plan-phase --research-phase 4`). Topics are the prune strategy, `FakeBroker` design, Repairs approval flow, discovered-entity registry cleanup, subentry deletion hooks, and the subentries-as-store fit.
5. **Re-trigger, hardening and release.**
   - Delivers the re-trigger service (non-retained, QoS 1, `request_id` dedupe, rate limit, approval-gated), circuit breaker and Repairs, diagnostics redaction, multi-instance scenario tests, README with ACL example, and release automation.
   - Avoids Pitfalls 3, 17, 18, 20, 25.
   - Research: standard, skip.

Ordering rationale:
- Dependencies run from domain core -> gateway -> owner path -> sync -> trust -> re-trigger -> release.
- Startup semantics, the single trigger source and the Select mapping change wire or behavior contracts, so fix them before sync.
- There is no release with follower apply before the trust gate.
- CI comes first so later failures are attributed to code, not configuration.

## Open Decisions for Requirements

- **Startup policy.** Recommended: baseline only, with an opt-in run-on-startup flag.
- **`script_mode`.** Architecture recommends a serial queue per device. Pitfalls recommends `restart` (latest state wins). Choose one, or make it configurable.
- **Owner availability.** The integration cannot set its own LWT on HA's shared MQTT client. Architecture says do not tie entity availability to owner liveness in v1. Pitfalls recommends a heartbeat plus a graceful-shutdown publish. Decide.
- **Option A trade-off.** State is writable by anyone, including followers, while config edits stay owner-only. Confirm this fits the ownership model.
- **Domain name.** `mqtt_actions` is suggested. It must be fixed before the first release.
- **Minimum HA version.** Research suggests 2026.9.0 (Python 3.14). Confirm that the user's three HA hosts can run it.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified against PyPI JSON and HA source at tag 2026.9.4. Subentries as the device store, `integration_type` and `Store` are MEDIUM. |
| Features | MEDIUM | HA MQTT semantics verified. No direct competitor, so comparisons are by analogy. `ActionSelector` rendering in flows is LOW. |
| Architecture | MEDIUM-HIGH | Platform facts verified. The cross-instance protocol is own synthesis, marked as design. |
| Pitfalls | MEDIUM-HIGH | Mechanics source-verified. Mitigations are design judgment. Brand-icon acceptance is single-sourced. |

**Overall:** MEDIUM-HIGH.

## Gaps to Address

- **`ActionSelector` in subentry flows.** Frontend rendering and field-level validation errors are unverified. Spike in Phase 2.
- **Subentries as the device store.** The fit is MEDIUM. Deletion from the HA UI must trigger unpublish plus the warning, and the standard dialog cannot be customized. Validate in Phase 4.
- **Prune strategy.** Grace window versus owner manifest is unresolved. The grace window is the recommended v1 default.
- **Select templates.** The generated templates are unverified. Test against a real HA MQTT discovery run.
- **`Store` and JSON helpers.** Not re-verified this session.
- **Brand path.** Verify against current HACS docs.
- **Instance-local IDs.** There is no cross-instance entity mapping in v1. Document that entity IDs must match.

## Sources

- Primary (HIGH): HA core source at tag 2026.9.4, PyPI JSON, developers.home-assistant.io and home-assistant.io docs, hacs.xyz docs, `hacs/integration` `validate/brands.py`, ludeeus `integration_blueprint`.
- Secondary (MEDIUM): `remote_homeassistant` and `mqtt-share-remote-hacs` READMEs, HA core issues on MQTT wildcard resubscribe and discovery removal.
- Tertiary (LOW): third-party CI PRs on the local brand icon, a community ghost-entity article, and training knowledge on `ActionSelector` frontend behavior.
