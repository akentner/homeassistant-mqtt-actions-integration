# Phase 1: Walking Skeleton - Installable Switch - Context

**Gathered:** 2026-09-29
**Status:** Ready for planning

<domain>
## Phase Boundary

A HACS-installable integration (`mqtt_actions`) where a Switch created in the UI runs its configured HA actions on MQTT state changes, on a single instance. Includes CI, hub Config Flow with instance ID, en/de translations, MQTT Discovery for the Switch, startup/reconnect-safe state handling, and failure surfacing. Select devices, central config sync, ownership, trust gate and operations tooling belong to Phases 2-4.

</domain>

<decisions>
## Implementation Decisions

### Topic layout and payloads
- **D-01:** Base topic is configurable in the hub Config Flow, default `mqtt_actions`. State topic: `<base>/v1/devices/<device_uuid>/state` (retained). Command topic equals state topic (STA-01). All instances must use the same base topic. — **Reversibility:** one-way — base topic and the `v1` path are baked into retained broker messages and, from Phase 3, into other instances' config.
- **D-02:** Switch payloads are `ON` / `OFF`. Published values are upper case; inbound values are read case-insensitively. Unknown payloads are ignored and logged. Payloads are not configurable per device. — **Reversibility:** costly — external systems and later Phase 3 config documents depend on the payload contract.
- **D-03:** The device ID in topics is a random UUID, also used as the entity `unique_id`. It is stable across renames. — **Reversibility:** one-way — `unique_id` and topic paths persist in the entity registry and broker.
- **D-04:** The discovery prefix is read from the MQTT integration, not asked in the flow.

### Startup and baseline behavior
- **D-05:** On the first start of a new Switch, an existing retained state only sets the baseline (`last_acted`); no actions run.
- **D-06:** Per-device flag "run on startup" (default off). When on, the retained state is treated as a change once after HA start or reload, even if it equals `last_acted`, so actions run. When off, retained state at start or reconnect is baseline only (STA-04).
- **D-07:** Before any state has arrived (empty topic), the entity state is `unknown`, with no assumed state. The first state that arrives sets the baseline without running actions; later real changes are edges (STA-05).

### Failure surfacing (DEV-08)
- **D-08:** One Repairs issue per device, updated with the last error (time, trigger, error text). Repeated failures update the issue rather than creating new ones.
- **D-09:** The issue is cleared automatically after the next successful run and can also be dismissed manually. It is informational (not fixable). Failures are always logged too.

### Action validation (DEV-05)
- **D-10:** Schema-invalid actions are rejected in the flow. Actions targeting instance-local `device_id`s show a warning in the flow step but can still be saved (user confirms by submitting again).

### Setup flow and repo
- **D-11:** Hub Config Flow fields: base topic (default `mqtt_actions`) and instance name (default: HA location name). The instance UUID is generated automatically. One hub per instance (`single_config_entry`), requires MQTT.
- **D-12:** Repo: GitHub `akentner/homeassistant-mqtt-actions-integration`, MIT license, codeowner `@akentner`.
- **D-13:** Plan 1 of the phase is a spike plus host check: verify `ActionSelector` rendering and validation inside a subentry flow, and confirm that `haos-op3050-1`, `lxc-haos-104` and `hassio-n2plus` can run HA 2026.9.0 before fixing the `hacs.json` floor. Fallback if the subentry flow does not work: an options-flow-based device editor.

### Claude's Discretion
- Distinguishing replayed retained messages from live ones (MQTT `retain` flag on the received message) for baseline handling: implementation detail.
- Availability topic design and MQTT QoS/retain settings for discovery and state, following the research defaults (QoS 1, retained).
- CI workflow layout (hassfest, HACS action pinned by SHA, Ruff, pytest via uv), test structure, and brand icon design.
- Logger names, translation key structure, and exact Repairs issue wording.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` - core value, constraints, key decisions
- `.planning/REQUIREMENTS.md` - v1 requirements FND-01..05, DEV-01/02/05/08, STA-01/02/04/05, DSC-01/02
- `.planning/ROADMAP.md` - Phase 1 goal and success criteria
- `.planning/STATE.md` - blockers/concerns for Phase 1 (host HA version check, ActionSelector spike)

### Research
- `.planning/research/SUMMARY.md` - roadmap-level conclusions and open decisions
- `.planning/research/STACK.md` - stack decisions (HA 2026.9.x, Python 3.14, probatio, PHACC, hassfest/HACS pins)
- `.planning/research/ARCHITECTURE.md` - components (`MqttGateway`, `StateTracker`, `ActionRunner`, `DiscoveryPublisher`), topics, subentry device model
- `.planning/research/PITFALLS.md` - retained-message semantics, discovery removal, startup ordering, loop risks
- `.planning/research/FEATURES.md` - feature expectations and anti-features

### Project instructions
- `.claude/CLAUDE.md` - technology stack rules and the "Do not use" list (e.g. no `hass.data[DOMAIN]`, no `device_id` defaults, translations in `translations/`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None. The repository contains only planning artifacts (greenfield).

### Established Patterns
- Ecosystem conventions from the user's other projects: uv, Ruff (120 chars), Config Flow for setup, English code and comments.
- Blueprint reference: ludeeus `integration_blueprint` for CI and Ruff config (see STACK.md).

### Integration Points
- HA built-in `mqtt` integration (`async_wait_for_mqtt_client`, `async_subscribe`, `async_publish`) behind a single gateway seam.
- HA `helpers.script.Script` for local action execution; Repairs (`issue_registry`) for failure surfacing.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the research recommendations: the user accepted the recommended option for every question.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Walking Skeleton - Installable Switch*
*Context gathered: 2026-09-29*
