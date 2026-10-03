# Walking Skeleton — MQTT Actions Integration

**Phase:** 1
**Generated:** 2026-09-29

## Capability Proven End-to-End

> A Home Assistant admin installs the integration through HACS, adds it once, creates a Switch device in the UI with an action sequence, and a state message on that device's retained MQTT topic (from the HA UI toggle or an external publisher) runs the configured action locally on that instance, without replaying old state after a restart.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | Home Assistant custom integration, domain `mqtt_actions`, Python 3.14, HA >= 2026.9.0, distributed through HACS | Fixed by PROJECT.md constraints and `.claude/CLAUDE.md`; one-way identifier, frozen at plan 01-02 Task 1 |
| Device model | One hub config entry per instance (`single_config_entry`) plus one config subentry of type `switch` per device; device definitions live in subentry data (`device_id`, `on_change_to_on`, `on_change_to_off`, `run_on_startup`) | Native add, reconfigure and delete UX; verdict on the real frontend is decided at the D-13 gate (plan 01-02 Task 3), fallback is an options-flow editor |
| Data layer | Subentry data (definitions), HA `Store` key `mqtt_actions.state` (`last_acted` map and `published` id set), MQTT retained topics for state, discovery and availability. No database | The broker is the only shared component; Store survives restarts and is flushed by HA (STA-05) |
| MQTT access | Built-in `mqtt` integration only, behind `MqttGateway` (`mqtt_gateway.py` is the only importer, enforced by an AST test) | Reuses the user's credentials, TLS and reconnect; gives Phase 3 and 4 a seam for a fake broker |
| Entity creation | Device-based MQTT Discovery consumed by core MQTT; the integration owns no entity platform | DSC-01; entities are then visible to any MQTT consumer and mirror on other instances in Phase 3 |
| Topic contract | State topic `{base}/v1/devices/{device_uuid}/state`, retained, command topic identical (D-01); availability `{base}/v1/instances/{instance_uuid}/availability`; payloads `ON` and `OFF`, published upper case, read case-insensitively (D-02) | One-way choices recorded in CONTEXT.md and re-confirmed at plan 01-02 Task 1 |
| Identity | Random UUID per device is the topic id and the entity `unique_id` (D-03); random UUID per hub is `instance_id` | Stable across renames; no derived ids |
| Trigger semantics | The state subscription is the only trigger source. `decide(retain, payload, last_acted, startup_pending, run_on_startup)`: retained means baseline only (unless the opt-in run-on-startup flag and a pending start), live means act when the value differs from `last_acted` (D-05, D-06, D-14) | STA-02, STA-04, STA-05; pure function, table-tested; proven against real Mosquitto in plan 01-04 |
| Action execution | `helpers.script.Script` per transition, serialised first-in first-out per device, raw action lists validated with `cv.SCRIPT_SCHEMA` and `async_validate_actions_config` at authoring and at every build | Same engine as automations; raw lists are portable, validated forms are not |
| Failure surfacing | Log plus one non-fixable Repairs issue per device, updated in place, cleared by the next success (D-08, D-09) | DEV-08 |
| Auth and security | No own authentication; broker credentials stay in HA's MQTT entry. Phase 1 has no remotely provided actions, but write access to a state topic can trigger that device's actions; documented in the README, broker ACLs follow in Phase 3 (TRU-04) | ASVS level 1, threat model per plan |
| Deployment target | HACS custom repository `akentner/homeassistant-mqtt-actions-integration` (MIT, D-12); manual UAT by copying `custom_components/mqtt_actions` to `/config/custom_components` on `haos-op3050-1` | The documented local full-stack run: hub, switch device, publish a state message, observe the action |
| CI | hassfest, HACS action, Ruff and pytest (uv, pytest-homeassistant-custom-component) on every push; all actions pinned by SHA, empty workflow permissions | FND-02 |
| Directory layout | `custom_components/mqtt_actions/` with `topics.py`, `state.py`, `actions.py` (pure), `mqtt_gateway.py`, `discovery.py`, `runner.py`, `manager.py`, `config_flow.py`, `translations/{en,de}.json`, `brand/icon.png`; tests under `tests/` | One module per responsibility; pure modules import nothing from Home Assistant except `cv` |

## Stack Touched in Phase 1

- [ ] Project scaffold (uv, Ruff, pytest harness, manifest, hacs.json) — plans 01-01, 01-02, 01-06
- [ ] Routing equivalent — hub Config Flow and the switch subentry flow — plans 01-02, 01-03
- [ ] Persistence — at least one real write and one real read: subentry data and the `Store` baseline (write on edge, read on reload), plus retained discovery on the broker — plans 01-02, 01-04, 01-05
- [ ] UI — the Add switch dialog with the HA action selector wired to the flow backend — plans 01-02 (D-13 gate), 01-03
- [ ] Deployment — HACS metadata, public repository, CI green, and the documented local run on `haos-op3050-1` — plan 01-06

## Out of Scope (Deferred to Later Slices)

- Select devices, option mapping (Phase 2)
- Run modes (queue versus restart), test button, per-device circuit breaker (Phase 2)
- Central retained config, owner and follower mirrors, tombstones, trust gate and approval via Repairs, denylist, broker ACL documentation (Phase 3)
- Confirmed multi-instance delete (Phase 3 redesigns the hub-removal cleanup of D-15)
- Re-trigger service, roster and heartbeat, resync, import and export, ownership transfer, per-instance run mode, diagnostics, release automation, full docs (Phase 4)
- Configurable payloads per device, reconfiguring the base topic, heartbeat-based availability (deferred requirement AVL-01)

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: Select devices with per-option actions, reliable execution (run modes, test button, loop protection)
- Phase 3: Central config, ownership and the trust gate so devices mirror to other instances and run only after approval
- Phase 4: Operations, recovery and release (re-trigger, roster, resync, import/export, diagnostics, docs, test tiers, releases)
