# Phase 5: Evaluate native switch/select entities instead of MQTT Discovery - Context

**Gathered:** 2026-10-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Decide whether switch and select entities owned by the MQTT Actions config entry replace MQTT Discovery as the way device entities are created. If the evaluation says go, the same phase implements it (native entities, migration, mixed-version handling). If no-go, the phase ends with the decision record. Origin: backlog 999.2 and Phase 4 D-13 (a device belongs to exactly one config entry, so Discovery devices cannot show on our integration page).

</domain>

<decisions>
## Implementation Decisions

### Phase outcome
- **D-01:** Phase 5 = evaluation first (spike plus decision record/ADR), then implementation plans in the same phase if the result is Go. On No-Go the phase ends with the ADR.
- **D-02:** Go/No-Go criteria, all four weighed: (a) all devices and entities, including mirrored ones, visible on our integration page; (b) removal of Discovery complexity (healing DSC-03, ghost entities, DSC-04 resync, retained topics); (c) non-HA consumers preserved where cheap; (d) migration cost and risk of rewriting Phases 1-3 after the v0.1.0 release.

### Discovery and non-HA consumers
- **D-03:** Native entities become the default. MQTT Discovery stays only as an optional mode for external consumers, with a documented warning about duplicate entities in HA. The PROJECT.md Discovery constraint is amended if the evaluation is Go. — **Reversibility:** costly — removing Discovery from the default path changes a published contract of v0.1.0.
- **D-04:** Non-HA consumers of the Discovery topics are nice-to-have, kept only if cheap (the optional mode covers this).

### Migration
- **D-05:** Existing installations migrate automatically on update: the owner removes the retained Discovery topics, and the native entity takes over the same unique_id/entity_id. History is kept where technically possible. No manual step. — **Reversibility:** one-way — entity registry ownership moves from core MQTT to this integration; rolling back needs another migration.
- **D-06:** Mixed versions: the central config gets a schema version. Older instances show a Repairs hint, newer ones write backward-compatibly until all instances are updated.

### Mirror devices and entity model
- **D-07:** Owned devices sit under their subentry. Mirror devices (owner = another instance) are devices directly under the config entry, marked with the owner and not editable. Everything shows on our integration page.
- **D-08:** The Phase 4 companion devices and mode selects merge into the native device: one device carries switch/select plus the mode select; the companion concept ends (its reason was D-13).

### Cutover refinements (from plan-phase research, 2026-10-03)
- **D-09:** D-06 is realized without a schema bump: `schema_version` stays 1; an additive, unhashed marker in the document plus an additive heartbeat capability key signal native mode. v0.1.0 instances get no Repairs hint; their actions keep running, only their UI entities are lost.
- **D-10:** The owner only switches to native mode once all online peers are capable; an online legacy peer blocks the switch (offline peers do not block).
- **D-11:** The optional Discovery export drops DSC-03 healing: best-effort, `enabled_by_default: false`, configurable prefix, no test buttons or test topic.
- **D-12:** Live cutover on running followers reloads the config entry automatically; takeover runs before the platform forward (entities first, then device, then retained clear).

### Claude's Discretion
- Behaviour when a new and an old instance adopt the same device.
- Technical form of the spike, how exactly the same entity_id/unique_id is taken over, and where the schema version lives in the central config.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and phase scope
- `.planning/ROADMAP.md` — Phase 5 goal and backlog 999.1/999.2 notes
- `.planning/PROJECT.md` — Discovery constraint to amend on Go
- `.planning/REQUIREMENTS.md` — DSC-01..04, STA-01..07, MAP-01

### Prior decisions
- `.planning/phases/04-operations-recovery-and-release/04-CONTEXT.md` — D-13 (revised: companion device), D-15 (native mode select)

### Code
- `custom_components/mqtt_actions/discovery.py` — Discovery payload builders
- `custom_components/mqtt_actions/entities.py` — hub and companion device info
- `custom_components/mqtt_actions/select.py`, `sensor.py`, `button.py` — existing native platforms
- `custom_components/mqtt_actions/manager.py`, `sync.py` — publishing and central config handling

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MqttActionsEntity` base class and `hub_device_info`/`companion_device_info` in `entities.py`: starting point for native device entities.
- Existing native platforms (sensor, button, select) already forward through `PLATFORMS` in `__init__.py`; a switch platform would be added there.

### Established Patterns
- State and command share one retained topic (STA-01); native entities must keep publishing to it so cross-instance sync stays unchanged.
- Entry state lives in `entry.runtime_data` (Manager).

### Integration Points
- Discovery publisher in `discovery.py` and the callers in `manager.py`/`sync.py`.
- Device registry: companion devices keyed by device uuid under our domain.

</code_context>

<specifics>
## Specific Ideas

- Trigger: user could not find devices of another instance during Phase 3 UAT; the integration page must show the full device and entity count.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Backlog 999.1, per-instance local actions on mirrored devices, remains separate.)

</deferred>

---

*Phase: 5-Evaluate native switch/select entities instead of MQTT Discovery*
*Context gathered: 2026-10-03*
