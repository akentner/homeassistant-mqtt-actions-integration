# Phase 1: Walking Skeleton - Installable Switch - Research

**Researched:** 2026-09-29
**Domain:** Home Assistant custom integration (HACS) on the built-in MQTT integration: config flow + config subentries, MQTT Discovery, retained-state edge detection, local `Script` execution, Repairs, CI
**Confidence:** HIGH for platform mechanics (read in HA 2026.9.4 source and exercised by a working spike), MEDIUM for frontend rendering of `ActionSelector` in a subentry dialog (not visually verified), LOW for two of the three target hosts (not reachable)

> Evidence base of this document: HA `2026.9.4` wheel (pulled in by `pytest-homeassistant-custom-component==0.13.367`, Python 3.14.7) was read directly, and a throw-away prototype of the whole Switch slice (hub flow, Switch subentry flow, discovery, state tracker, action runner, Repairs, Store) was built in the session scratchpad. It ran green: 14 pytest tests on PHACC, the real `ghcr.io/home-assistant/hassfest` image reported `Invalid integrations: 0`, and Ruff 0.16.9 ran with the blueprint config. The prototype is NOT in the repo (scratchpad is session-local); every finding needed by the planner is reproduced below. Claims tagged `[VERIFIED: spike]` were observed in that run.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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

### Deferred Ideas (OUT OF SCOPE)
None - discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-01 | Install via HACS (`hacs.json`, `manifest.json`, local brand icon, domain `mqtt_actions`, min HA 2026.9.0) | HACS validator sources read (brand path `<content path>/brand/icon.png`, `hacs.json` schema keys, manifest required keys); repo prerequisites list; hassfest-clean manifest from spike |
| FND-02 | Every push runs hassfest, HACS validation, Ruff, pytest in CI | Pinned action SHAs verified; workflow skeletons; GitHub repo must exist with description/topics/issues/LICENSE first; Ruff per-file-ignores needed |
| FND-03 | Config Flow, one hub per instance, requires MQTT, persistent random instance ID | Hub flow verified (abort `mqtt_required`, `single_instance_allowed` from manifest, uuid4 in `entry.data`) |
| FND-04 | All UI strings in English and German | `translations/{en,de}.json`; hassfest validates `en.json` only, so a parity test is required; hassfest placeholder-in-quotes rule |
| FND-05 | Wait for MQTT at startup, resume cleanly after reconnect | `async_wait_for_mqtt_client` semantics, `ConfigEntryNotReady`, HA client auto-resubscribe, `async_subscribe_connection_status` republish |
| DEV-01 | Create a Switch device via UI with a name | Subentry type `switch`; `ConfigSubentryFlow` verified end to end in PHACC |
| DEV-02 | Configure `onChangeToOn`/`onChangeToOff` with the action selector | `ActionSelector` in flow schema serializes to `{"action": {}}`; store RAW selector output |
| DEV-05 | Actions validated on input; instance-local `device_id` produces warning | `cv.SCRIPT_SCHEMA` + `script.async_validate_actions_config`; warn-then-confirm pattern; recursive `device_id` detector |
| DEV-08 | Action failures surfaced (log + Repairs), not swallowed | `Script.async_run` re-raises; catch, log, `ir.async_create_issue`; clear on next success |
| STA-01 | UI change publishes to the shared retained state topic (command == state) | Discovery payload with `command_topic == state_topic`, `retain: true`, `qos: 1`; verified by publish-call assertion |
| STA-02 | External MQTT message on the state topic triggers the same actions | Single trigger source = state subscription; edge test |
| STA-04 | Retained state at start/reconnect only sets baseline (opt-in flag) | `ReceiveMessage.retain` semantics verified in source and against real Mosquitto 2.1.2; decision function |
| STA-05 | Last processed state persisted; only real edges trigger | `Store` with `async_delay_save`; decision table |
| DSC-01 | Owner publishes discovery (UUID `unique_id`, availability, device info) | Device-based discovery payload verified to create a real `switch` entity; prefix must come from `entry.data | entry.options` |
| DSC-02 | Discovery removed only on explicit user deletion | Unload never publishes empty payload; subentry removal fires update listener; `Store`-tracked published set covers deletion while entry is not loaded |
</phase_requirements>

## Summary

The phase is fully feasible on the stack fixed in `.claude/CLAUDE.md`. Every hard question in the phase was answered by reading HA 2026.9.4 source and running a working prototype of the whole Switch slice. The architecture is a "controller beside core MQTT": the integration owns no entities. It publishes device-based MQTT Discovery so HA's built-in `mqtt` integration creates the `switch` entity, and it subscribes to the same retained state topic to detect edges and run the configured actions through `helpers.script.Script`. Devices are config subentries of a single hub entry; the device UUID (D-03) lives in subentry data and is never changed.

Six findings change or sharpen the plan and are not visible in the prior project research: (1) `mqtt.async_subscribe` is a coroutine (must be awaited) and its callback MUST be a `@callback`/coroutine, a plain `lambda` is run in an executor thread and crashes on the first message; (2) the MQTT discovery prefix lives in `entry.data | entry.options` of the MQTT entry, not in `data` alone; (3) `D-07` as written ("the first state that arrives sets the baseline") would swallow the very first live UI toggle on a brand-new device, so it needs a one-line interpretation decision (Assumption A1); (4) PHACC's mocked paho client loops every publish back with the publish's OWN `retain` flag (`True` for our retained publishes) while a real broker forwards it with `retain=False`, so edge semantics must never be tested through the loopback; (5) hassfest rejects translation placeholders inside single quotes, and validates only `en.json`; (6) the frontend `ha-selector-action` exposes no error property, so validation errors on the action fields may not render inline and should be reported as `base` errors.

D-13 is mostly discharged by this research: the subentry flow with `ActionSelector` works on the backend (create, reconfigure, invalid-action error, device-id warn-then-confirm, schema serializes for the frontend). What remains for Plan 1 is (a) one visual check in a running HA frontend, (b) HA version checks on `lxc-haos-104` and `hassio-n2plus` (`haos-op3050-1` already runs `2026.9.4`), and (c) creating the GitHub repository, which does not exist yet and is a hard prerequisite for the HACS check in CI.

**Primary recommendation:** Build the slice exactly as in the Architecture Patterns below (hub entry + `switch` subentries + discovery publisher + retain-aware `StateTracker` + lock-serialized `ActionRunner`), write the pure decision function and topic helpers test-first, run hassfest through the container locally before the first push, and resolve Assumption A1 (D-07 wording) with the user before Plan 3.

## Project Constraints (from CLAUDE.md)

Directives extracted from `/home/akentner/Projects/homeassistant-mqtt-actions-integration/.claude/CLAUDE.md` (and the two parent CLAUDE.md files). Treated with the authority of locked decisions.

- Python 3.14 (`>=3.14.2`), HA Core `2026.9.x` (floor `2026.9.0`). Zero third-party runtime dependencies; declare `dependencies: ["mqtt"]` in `manifest.json`, NOT `requirements` for paho/aiomqtt, and not `after_dependencies`.
- Validation import is `probatio` (`import probatio`), provided by HA; do not add it to `requirements`. `[VERIFIED: spike]` `import probatio as vol` works in hub flow, subentry flow and reconfigure (4 flow tests green); `import voluptuous as vol` also works because HA aliases it (see Verified Platform Facts F-19). Follow CLAUDE.md: use `probatio`.
- uv for env/lock/Python provisioning; Ruff for lint and format (line length 120, `target-version = "py314"`, start from the ludeeus blueprint `.ruff.toml`); pytest through `pytest-homeassistant-custom-component` only. Do NOT add `homeassistant`, `pytest`, `pytest-asyncio` or `voluptuous` as dev dependencies (PHACC pins them). Set `asyncio_mode = "auto"`.
- Use `entry.runtime_data` (typed `ConfigEntry[...]`), never `hass.data[DOMAIN]`; register every unsubscribe with `entry.async_on_unload`.
- Translations in `translations/en.json` + `translations/de.json`; NOT `strings.json`. No YAML configuration, no `async_setup_platform`, no `setup.py`/`setup.cfg`/Poetry.
- Register services in `async_setup` (no services exist in Phase 1).
- Do NOT use `device_id` targets in shipped examples or defaults; prefer `entity_id`/areas/labels and warn users.
- Pin `home-assistant/actions/hassfest` and `hacs/action` by commit SHA; workflow `permissions: {}`; `actions/checkout` with `persist-credentials: false`; Dependabot for PHACC, Ruff and action SHAs.
- Local brand image at `custom_components/mqtt_actions/brand/icon.png`; do not use `ignore: brands` in the HACS action.
- Never execute a received action sequence without local opt-in and schema validation. (Phase 1 has no remote-provided actions; actions are authored locally. Still validate on authoring AND again when building Scripts at setup.)
- Code, comments and commits in English; chat/UI text for the user in German. Work goes through GSD commands (this phase: `/gsd-execute-phase`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Switch entity (state, toggle UI) | HA core `mqtt` integration (via Discovery) | — | Project does not own entities; discovery makes core MQTT create `switch.<name>` |
| Device authoring UI (name, actions) | HA frontend (config subentry dialog) | Integration backend flow (validation) | Frontend renders `ha-selector-action`; backend validates and stores |
| Action validation | Integration backend (flow) | Setup-time re-validation | `ActionSelector.__call__` returns data unchanged (F-13), so all validation is ours |
| Trigger detection (edge vs baseline) | Integration (`StateTracker`) | MQTT broker (retain flag semantics) | Only the integration knows `last_acted`; the broker only marks replays via `retain=True` |
| Action execution | Integration (`ActionRunner` + `helpers.script.Script`) | HA service registry | Runs locally on each instance through HA's own engine |
| Persistence of `last_acted` and published-id set | HA `Store` | — | Survives restart; broker is transport only |
| Device definitions | Config subentries (HA config storage) | — | Native add/reconfigure/delete UX and backup |
| Discovery/availability/state retention | MQTT broker | Integration (publisher) | Retained messages are the only cross-restart shared state |
| Failure surfacing | HA issue registry (Repairs) | Python logging | Repairs is the user-visible surface, log is the audit trail |
| Build/validation gates | GitHub Actions CI | Local container run of hassfest | hassfest + HACS action are the store gate |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14.7 available locally (`requires-python >=3.14.2`) | Runtime | HA 2026.9.x hard requirement `[VERIFIED: local python3 --version 3.14.7]` |
| Home Assistant Core | 2026.9.4 (floor 2026.9.0) | Host platform | `haos-op3050-1` runs `version: 2026.9.4`, `version_latest: 2026.9.4` `[VERIFIED: ssh haos-op3050-1 "ha core info"]` |
| HA `mqtt` integration | bundled (`paho-mqtt==2.1.0`) | Broker connection, discovery consumer, pub/sub | `[VERIFIED: raw.githubusercontent.com core tag 2026.9.0 homeassistant/components/mqtt/manifest.json: "requirements": ["paho-mqtt==2.1.0"], "single_config_entry": true]` |
| `helpers.script.Script` | core | Local action execution | Same engine as automations; `async_unload` exists in the `2026.9.0` tag as well as `2026.9.4` `[VERIFIED: raw.githubusercontent.com core tags 2026.9.0 and 2026.9.4, grep count 1 each]` |
| `helpers.selector.ActionSelector` | core | Action editor in flows | Used by core's own `template` config flow `[VERIFIED: template/config_flow.py:267-268]` |
| `helpers.storage.Store` | core | `last_acted` + published id set | Standard; exercised in spike (`async_load`, `async_delay_save`, `async_save`) |
| `helpers.issue_registry` | core | Repairs issue per device | Signature read (F-11) |
| `probatio` (`import probatio as vol`) | provided by HA (`0.11.4` in 2026.9.4) | Flow schemas | `[VERIFIED: pip metadata Requires-Dist: probatio==0.11.4 in homeassistant-2026.9.4.dist-info]` |

### Supporting (dev / CI only)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-homeassistant-custom-component | 0.13.367 (2026-09-27) | Test harness (`hass`, `mqtt_mock`, `MockConfigEntry`, `async_fire_mqtt_message`, `async_mock_service`) | All tests. Installed HA = 2026.9.4 `[VERIFIED: uv sync + import homeassistant.const.__version__]` |
| ruff | 0.16.9 (2026-09-24) | Lint + format | `[VERIFIED: PyPI JSON latest 0.16.9; ruff --version in spike]` |
| uv | 0.12.19 latest on PyPI (0.12.7 installed locally) | Env, lock, Python | `[VERIFIED: PyPI JSON]` |
| Mosquitto | 2.1.2 available locally at `/usr/bin/mosquitto` | Optional real-broker retain-semantics test | `[VERIFIED: mosquitto --version]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Subentry type per domain (`switch`, later `select`) | One `device` subentry type with a domain menu (ARCHITECTURE.md) | Separate types give one "Add" button per domain and independent reconfigure flows (core's `satel_integra` does this). Recommended; one type needs an extra menu step. `[ASSUMED]` A7 — planner may choose either, subentry type name is persisted in storage |
| Options-flow device editor | Subentry flow | Only fallback per D-13; not needed, subentry flow works on the backend |
| Mock MQTT (PHACC) only | Real Mosquitto tier | Mock cannot prove replay-vs-live retain flags. A minimal broker test protects the key invariant (see Validation Architecture) |

**Installation (dev):**
```bash
uv init --bare --python 3.14        # then hand-write pyproject.toml, see Code Examples
uv add --dev pytest-homeassistant-custom-component==0.13.367 ruff==0.16.9
uv sync --locked
```

**Version verification:** performed 2026-09-29 against PyPI JSON: PHACC `0.13.367` (first upload 2020-08-16, 574 releases), ruff `0.16.9` (first upload 2022-08-27, 425 releases), uv `0.12.19` (first upload 2024-02-15).

## Package Legitimacy Audit

Only dev/CI tooling is installed; the integration itself has **zero runtime dependencies**.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pytest-homeassistant-custom-component | PyPI | 6 yrs (first upload 2020-08-16, 574 releases) | seam: unknown | github.com/MatthewFlamm/pytest-homeassistant-custom-component (111 stars, pushed 2026-09-27) | SUS (seam reasons: `too-new` = latest release 2026-09-27, `unknown-downloads`) | Flagged - planner adds one consolidated `checkpoint:human-verify` before first `uv add`/`uv sync` |
| ruff | PyPI | 4 yrs (first upload 2022-08-27, 425 releases) | seam: unknown | github.com/astral-sh/ruff (49,829 stars) | SUS (seam reasons: `too-new` = latest release 2026-09-24, `unknown-downloads`) | Flagged - same checkpoint |
| uv | PyPI | 2.6 yrs (first upload 2024-02-15, 318 releases) | seam: unknown | github.com/astral-sh/uv | SUS (seam reasons: `too-new`, `unknown-downloads`) | Flagged - same checkpoint (tool, not a project dependency; already installed locally) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** pytest-homeassistant-custom-component, ruff, uv. The SUS verdicts come only from "latest release is days old" and "no download data"; the age, release history and source repos above were checked independently. The planner should still insert a single `checkpoint:human-verify` ("confirm the three dev tool names and versions in `pyproject.toml`") before the first install, as the protocol requires. No postinstall hooks apply (PyPI, wheels).

*GitHub Actions used in CI are pinned by commit SHA (see Standard CI pins); they are actions, not packages.*

## Architecture Patterns

### System Architecture Diagram

```
                          HA frontend (dialog)                          HA instance (this integration)
                       ┌───────────────────────────┐        ┌─────────────────────────────────────────────────────┐
  user ───────────────▶│ Add "Switch device"       │  WS    │ ConfigSubentryFlow (type "switch")                  │
                       │ name + ha-selector-action │───────▶│  validate: cv.SCRIPT_SCHEMA +                       │
                       │ x2 + run_on_startup       │◀───────│  script.async_validate_actions_config               │
                       └───────────────────────────┘ errors │  device_id? -> warn, submit again to confirm        │
                                                            │  store RAW actions + device UUID in subentry.data   │
                                                            └───────────────┬─────────────────────────────────────┘
                                                                            │ subentry added/changed/removed
                                                                            ▼  (entry update listener)
   ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
   │ Manager (entry.runtime_data)                                                                                 │
   │  reconcile(): diff subentries vs devices                                                                     │
   │   add     -> build Scripts, subscribe state topic, publish discovery (+ record id in Store "published")      │
   │   change  -> rebuild Scripts (keep subscription + baseline), republish discovery                            │
   │   remove  -> unsubscribe, unload Scripts, publish EMPTY retained discovery (+ empty retained state)         │
   │  start(): orphan cleanup = Store.published − subentry ids -> empty retained discovery                        │
   │  reconnect (mqtt connection status True): republish availability + discovery of all devices                  │
   │  unload: stop tasks, unload Scripts, save Store, availability "offline" — NEVER clear discovery              │
   └───────┬────────────────────────────────────────────────┬──────────────────────────────────────┬─────────────┘
           │ publish (retain, QoS1)                          │ subscribe <base>/v1/devices/<uuid>/state
           ▼                                                 ▼ (one subscription per device, @callback)
   ┌─────────────────────────────┐              ┌──────────────────────────────────────────────┐
   │ MQTT broker                 │◀────────────▶│ HA core mqtt client (shared connection)      │
   │ retained: discovery, state, │  replay on   │  new subscription => re-SUBSCRIBE => retained │
   │ availability                │  subscribe   │  replay with retain=True; live msgs retain=False│
   └───────────┬─────────────────┘              └───────────────┬──────────────────────────────┘
               │ homeassistant/device/<uuid>/config              │ ReceiveMessage(retain, payload)
               ▼                                                 ▼
   ┌─────────────────────────────┐              ┌──────────────────────────────────────────────┐
   │ core MQTT discovery ->      │              │ StateTracker.decide(retain, value, last_acted,│
   │ switch.<name> entity        │              │   startup_pending, run_on_startup)            │
   │ command_topic == state_topic│              │   retain=True  -> baseline only (or once run) │
   │ UI toggle publishes ON/OFF  │              │   retain=False -> act iff value != last_acted │
   └─────────────────────────────┘              └───────────────┬──────────────────────────────┘
                                                                 ▼ act
                                        ActionRunner: background task, per-device asyncio.Lock (FIFO),
                                        Script(single).async_run(run_variables, Context())
                                          ok    -> ir.async_delete_issue(action_failed_<uuid>)
                                          error -> log + ir.async_create_issue (updates in place)
```

### Recommended Project Structure
```
custom_components/mqtt_actions/
├── __init__.py          # async_setup_entry / async_unload_entry / update listener; wires Manager
├── manifest.json        # see Code Examples
├── const.py             # DOMAIN, conf keys, SUBENTRY_SWITCH
├── config_flow.py       # hub flow + SwitchSubentryFlow (+ device-id detector)
├── topics.py            # PURE: build/parse state, availability, discovery topics; base-topic validator
├── state.py             # PURE: StateTracker.decide() decision function + value normalisation
├── mqtt_gateway.py      # ONLY importer of homeassistant.components.mqtt (test seam for a FakeBroker in Phase 3/4)
├── discovery.py         # PURE builder of the device-based discovery payload + publisher
├── runner.py            # ActionRunner: Script build/unload, lock, failure -> Repairs
├── manager.py           # Manager: reconcile, Store, reconnect handling
├── brand/icon.png       # 256x256 PNG (A4)
└── translations/{en,de}.json
tests/                   # conftest.py, test_state.py (pure), test_topics.py, test_config_flow.py, test_manager.py,
                         # test_discovery.py, test_translations.py, test_repo_structure.py, broker/ (optional)
hacs.json  pyproject.toml  uv.lock  .ruff.toml  README.md  LICENSE
.github/workflows/{validate.yml,ci.yml}  .github/dependabot.yml
```
Rule: `topics.py`, `state.py`, and the payload builders import nothing from HA except `cv`, so the core semantics are unit-testable without a `hass` fixture (fast TDD loop).

### Pattern 1: Controller beside core MQTT (no own entities)
**What:** The integration publishes device-based MQTT Discovery; HA core MQTT creates and owns the `switch`. `[VERIFIED: spike]` the published payload, fed back as a retained message, produced `switch.lamp` with state `unknown`, `unique_id == device uuid`, availability honoured, and `switch.turn_on` published `("<base>/v1/devices/dev-1/state", "ON", 1, True)`.
**When to use:** Always (DSC-01).
**Example:** see Code Examples "Discovery payload".

### Pattern 2: Subentry-per-device with an immutable UUID and reconcile-by-diff
**What:** `SwitchSubentryFlow.async_step_user` generates `uuid.uuid4()` once, stores it in `subentry.data["device_id"]` and as the subentry `unique_id`. Reconfigure must carry the same `device_id` forward. One entry update listener diffs `entry.get_subentries_of_type("switch")` against the running devices.
**Why a diff:** `async_remove_subentry` does not unload anything and does not call us directly; it calls `_async_update_entry`, which fires the entry's update listeners. `[VERIFIED: homeassistant/config_entries.py:2700-2714]`
```
    def async_remove_subentry(self, entry: ConfigEntry, subentry_id: str) -> bool:
        ...
        result = self._async_update_entry(entry, subentries=subentries)
```
and `[VERIFIED: homeassistant/config_entries.py:2676-2679]`
```
    def _async_save_and_notify(self, entry: ConfigEntry) -> None:
        for listener in entry.update_listeners:
            self.hass.async_create_task(
```
The UI deletion path is the websocket handler `[VERIFIED: homeassistant/components/config/config_entries.py:848]` `hass.config_entries.async_remove_subentry(entry, msg["subentry_id"])`. No entry reload happens.
**Deletion while the entry is not loaded** (e.g. MQTT down, entry in SETUP_RETRY): the listener is not registered, so the removal is invisible. Persist the set of published device ids in `Store` and, in `Manager.start()`, publish an empty retained discovery payload for `published − current`. `[VERIFIED: spike test test_unload_keeps_discovery_delete_clears_it; orphan branch written but exercised by design review]` -> planner: add an explicit test for the orphan branch.

### Pattern 3: Retain-aware decision function (pure, table-driven)
**What:** `ReceiveMessage.retain` is `True` only for a replay caused by a (re)subscribe and `False` for live forwards. `[VERIFIED: real Mosquitto 2.1.2 via paho]` observed sequence: replay on subscribe `('sub','t/state','ON',True)`, live publish `('sub','t/state','OFF',False)`, re-SUBSCRIBE replay `('sub','t/state','OFF',True)`, clearing the retained topic delivers `('sub','t/state','',False)` live and a new subscriber receives nothing.
Decision table (recommended; `value` is normalised `strip().upper()`, must be `ON`/`OFF` else ignored):

| retain | condition | act? | baseline update |
|--------|-----------|------|-----------------|
| True | `run_on_startup` and `startup_pending` | yes (D-06) | `last_acted = value` |
| True | otherwise (start, reconnect, later replay, new device D-05) | no (STA-04) | `last_acted = value` |
| False | `value != last_acted` (incl. `last_acted is None`, see A1) | yes (STA-02) | `last_acted = value` |
| False | `value == last_acted` | no | unchanged |
| any | value not ON/OFF (also empty string from a retained clear) | no, log (D-02) | unchanged |

`startup_pending` is set `True` when the device is (re)built after HA start/reload and cleared by the first message of any kind. A later reconnect replay therefore never re-runs actions (STA-04). `last_acted` is persisted via `Store.async_delay_save` (STA-05).
**Why persisted `last_acted` still matters** although replays never act: it defines "real edge" for the first live message after a restart and for D-06's "even if it equals last_acted".

### Pattern 4: ActionRunner - validated raw sequence -> Script, serialized per device
**What:** Store the raw `ActionSelector` output; at build time run `cv.SCRIPT_SCHEMA` then `await script.async_validate_actions_config(hass, seq)` then `Script(hass, seq, name, DOMAIN, script_mode="single", logger=_LOGGER)`. Serialize runs per device with an `asyncio.Lock` (FIFO) inside a background task; `single` mode would otherwise silently drop an overlapping run. `[VERIFIED: homeassistant/helpers/script.py:1917-1921]`
```
            if self.script_mode == SCRIPT_MODE_SINGLE:
                if self._max_exceeded != "SILENT":
                    self._log("Already running", level=LOGSEVERITY[self._max_exceeded])
                script_execution_set("failed_single")
                return None
```
Unhandled action errors propagate out of `Script.async_run` `[VERIFIED: homeassistant/helpers/script.py:526-528]` `except Exception:` / `script_execution_set("error")` / `raise`, so the runner must catch them. Tear down with `await script.async_unload()`; a run after unload raises `[VERIFIED: script.py:1898-1901]` `raise RuntimeError(f"Cannot run script '{self.name}' after it has been unloaded")`.
**Run tasks** with `entry.async_create_background_task(hass, coro, name)` (cancelled on unload). NOTE: `hass.async_block_till_done()` does NOT wait for background tasks; tests need `await hass.async_block_till_done(wait_background_tasks=True)` for any path whose first `await` really suspends (e.g. republish-on-reconnect). `[VERIFIED: spike test_reconnect_republishes_discovery failed until this was added]`
**Phase 2 hook:** DEV-06 (queue vs restart) replaces the lock with a mode switch; keep `ActionRunner` behind one `enqueue(device, transition)` method.

### Pattern 5: Device-based discovery, republished idempotently
- Topic: `<discovery_prefix>/device/<uuid>/config`. UUID with hyphens is legal `[VERIFIED: discovery.py:64-67]`
```
TOPIC_MATCHER = re.compile(
    r"(?P<component>\w+)/(?:(?P<node_id>[a-zA-Z0-9_-]+)/)"
    r"?(?P<object_id>[a-zA-Z0-9_-]+)/config"
)
```
- `discovery_prefix` = `dict(mqtt_entry.data | mqtt_entry.options).get(mqtt.CONF_DISCOVERY_PREFIX, mqtt.DEFAULT_PREFIX)`. `[VERIFIED: components/mqtt/__init__.py:549]` `conf = dict(entry.data | entry.options)` and `[VERIFIED: __init__.py:605]` `hass, conf.get(CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX), entry`. Reading `.data` alone (as the first prototype did) silently uses the wrong prefix when the user changed it in MQTT options.
- Required top-level keys `[VERIFIED: components/mqtt/schemas.py:212-217]`
```
DEVICE_DISCOVERY_SCHEMA = _MQTT_AVAILABILITY_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Required(CONF_COMPONENTS): vol.Schema({str: _COMPONENT_CONFIG_SCHEMA}),
        vol.Required(CONF_ORIGIN): MQTT_ORIGIN_INFO_SCHEMA,
```
  and origin requires a name `[VERIFIED: schemas.py:157-160]` `vol.Required(CONF_NAME): cv.string`. Use the full key names (`device`, `origin`, `components`, `platform`); the abbreviated forms also work but add nothing.
- The switch component: `unique_id` = device UUID (D-03), `name: null` (entity takes the device name), `state_topic == command_topic`, `retain: true`, `qos: 1`, `payload_on/off`, and `value_template: "{{ value | upper }}"`. The template is needed because the core switch compares the payload exactly: `[VERIFIED: components/mqtt/switch.py:108-110]`
```
        self._is_on_map = {
            state_on or config[CONF_PAYLOAD_ON]: True,
            state_off or config[CONF_PAYLOAD_OFF]: False,
```
  and `[VERIFIED: switch.py:127]` `if (payload := self._value_template(msg.payload)) in self._is_on_map:` — so a lower-case external `on` would be ignored by the entity while our tracker (case-insensitive, D-02) acts. `[VERIFIED: spike]` with the template, publishing `on` turned the entity `on`. Non-optimistic because `state_topic` is set `[VERIFIED: switch.py:113-115]` `config[CONF_OPTIMISTIC] or config.get(CONF_STATE_TOPIC) is None`, giving `unknown` until the first message (D-07 entity side) `[VERIFIED: spike]`.
- Discovery silently drops unknown keys (`DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)`, switch.py) — "entity exists" does NOT prove `retain`/`qos` were honoured. Assert on the publish call of `switch.turn_on` instead. `[VERIFIED: spike]`
- Availability: `availability: [{"topic": "<base>/v1/instances/<instance_uuid>/availability"}]`, `online` retained after start and on every reconnect, `offline` retained on unload/stop. `[VERIFIED: spike]` payload `offline` made the entity `unavailable`. The integration cannot set an MQTT Last Will on HA's shared client, so a hard crash leaves a stale retained `online` (document; heartbeat/AVL-01 is v2). Design choice A5.
- Idempotent republish: an unchanged retained payload is ignored by core `[VERIFIED: entity.py:1206]` `# Non-empty, unchanged payload: Ignore to avoid changing states`, so republishing on every reconnect is safe.
- Removal = empty retained payload on the same topic. Core then removes state AND entity-registry entry `[VERIFIED: entity.py:1051-1056]`
```
        entity_registry = er.async_get(self.hass)
        if entity_entry := entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)
            await async_cleanup_device_registry(
```
  so no extra registry cleanup is needed for the single-instance case.
- Reverse direction (DSC-03 is Phase 3, note only): when a user deletes the MQTT entity in the HA UI, core publishes the empty retained payload itself `[VERIFIED: entity.py:1211-1220]` `async_removed_from_registry` ... `await async_remove_discovery_payload(self.hass, self._discovery_data)`. In Phase 1 the next reconnect/reload republishes the discovery and the entity returns; no dedicated handling is required.

### Pattern 6: Flow validation, warn-then-confirm, errors as `base`
- Validate each action field: `cv.SCRIPT_SCHEMA(raw)` then `await script.async_validate_actions_config(hass, validated)`; on any exception report an error. `[VERIFIED: spike]` `[{"bogus": 1}]` is rejected; a valid `[{"action": "light.turn_on", ...}]` passes. Store the RAW list, not the validated form (validated form contains Template objects, not JSON-serializable, not portable). `ActionSelector` does no validation itself `[VERIFIED: helpers/selector.py:284-286]`
```
    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data
```
- Device-id detection: recursive walk over the raw structure collecting the value of any `device_id` key (covers `target:`, device actions, `data:`). Static detection only; a template that computes a device id is not caught.
- Warn-then-confirm (D-10): first submit with `device_id`s returns the form with `errors={"base": "device_id_warning"}` and `description_placeholders={"device_ids": ...}`; remember a fingerprint of the submitted input on the flow instance; an identical second submit saves. `[VERIFIED: spike test_subentry_flow_validation_and_warning]`
- Report action errors as `base` (with a `{field}` placeholder), not as field errors. `[CITED: raw.githubusercontent.com/home-assistant/frontend/dev/src/components/ha-selector/ha-selector-action.ts]` the selector "does not expose explicit error or required validation properties", and `[CITED: .../config-flow/step-flow-form.ts]` errors are passed to `ha-form` as `.error=${this._errors}`; whether a field-level error renders under the action editor is unverified (A2). `base` errors always render as a form alert. Keep the field-level error as well only if the visual spike shows it renders.
- Reconfigure: `async_update_and_abort(entry, subentry, title=..., data={**cleaned, "device_id": subentry.data["device_id"]})` — replace, do not merge, so a cleared action list really clears, but re-inject the immutable `device_id`. `[VERIFIED: spike]` the first version passed `data=cleaned`, dropped `device_id`, and the update listener raised `KeyError: 'device_id'`.
- `ConfigSubentryFlow.async_create_entry` only works for `source == user` `[VERIFIED: config_entries.py:3770-3771]` `if self.source != SOURCE_USER: raise ValueError(f"Source is {self.source}, expected {SOURCE_USER}")` — the reconfigure path must use `async_update_and_abort`.

### Pattern 7: Gateway seam
`mqtt_gateway.py` is the only module importing `homeassistant.components.mqtt`. Surface: `async wait_ready() -> bool`, `async subscribe(topic, cb) -> unsub`, `async publish(topic, payload, *, retain, qos=1)`, `on_connection_change(cb) -> unsub`, `discovery_prefix() -> str`. Phase 3/4's `FakeBroker` implements the same surface. It also makes the "callback must be `@callback`" rule impossible to violate elsewhere.

### Anti-Patterns to Avoid
- **`lambda` / plain function as MQTT callback:** HA classifies anything that is neither a coroutine function nor `@callback` as an executor job `[VERIFIED: homeassistant/core.py:353-362]`
```
    while isinstance(check_target, functools.partial):
        check_target = check_target.func
    if inspect.iscoroutinefunction(check_target):
        return HassJobType.Coroutinefunction
    if is_callback(check_target):
        return HassJobType.Callback
    ...
    return HassJobType.Executor
```
  The spike hit `RuntimeError: Non-thread-safe operation invoked on an event loop other than the current one`. Use `functools.partial(self._on_message, device_id)` where `_on_message` is `@callback` (partials are unwrapped).
- **Forgetting `await` on `mqtt.async_subscribe`:** it is `async def` `[VERIFIED: components/mqtt/client.py:251]` `async def async_subscribe(` ... `) -> CALLBACK_TYPE:`; without `await` you hold a coroutine, never subscribe, and `unsub()` later raises `'coroutine' object is not callable`. (`STACK.md`'s snippet omits the `await`.)
- **Binding the Device object into the callback:** after a reconfigure the rebuilt device replaces it and the old object's Scripts are unloaded (`RuntimeError: Cannot run script ... after it has been unloaded`). Bind the device id and resolve `self.devices.get(id)` at message time.
- **Publishing empty discovery in unload/stop** (violates DSC-02).
- **Acting on the command:** the state topic is the only trigger (command == state, so there is no separate command path).
- **Storing the validated (Template-bearing) action list** or deriving anything from the device name for topics/unique_id.
- **Per-message `Store.async_save`:** use `async_delay_save`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Running action sequences | Own service-call loop | `helpers.script.Script` | Templates, `choose`, `delay`, targets, `continue_on_error`, traces |
| Action validation | Own schema | `cv.SCRIPT_SCHEMA` + `script.async_validate_actions_config` | Device actions/conditions need the second stage |
| Action editor UI | Custom form fields | `selector.ActionSelector()` | Native editor, same as automations |
| Entity creation | `switch.py` platform | MQTT Discovery -> core `mqtt.switch` | Requirement DSC-01, and it gives cross-instance entities in Phase 3 for free |
| Topic validation | Regex | `mqtt.valid_publish_topic` (+ explicit checks below) | Public, in `mqtt.__all__` |
| Persistence | JSON files | `helpers.storage.Store` | Atomic, executor-based, flushed at HA final-write |
| User-visible failures | Persistent notifications | `helpers.issue_registry` | Repairs UI, dismiss, translation |
| MQTT connection | paho/aiomqtt | HA `mqtt` API | Reuses credentials/TLS/reconnect; `mqtt_mock` in tests |
| Instance/device ids | Derived hashes | `uuid.uuid4()` | Random, stable, clone-safe enough for Phase 1 |

**Key insight:** every piece that feels custom (execution, validation, entity, persistence, alerts) already exists in HA; the only genuinely new logic is the retain-aware decision function and the reconcile diff, and both are small and pure.

## Common Pitfalls

### Pitfall 1: MQTT callback runs in an executor thread
**What goes wrong:** first message raises `Non-thread-safe operation invoked on an event loop other than the current one` inside your handler; no action ever runs. **Why:** lambda/plain function classified as `Executor` job (F-9). **Avoid:** `@callback` method + `functools.partial`; or `async def`. **Warning sign:** tests where actions never fire and an exception appears only in captured logs.

### Pitfall 2: `mqtt.async_subscribe` not awaited
See Anti-Patterns. Also `mqtt.async_publish` is a coroutine.

### Pitfall 3: Reconfigure loses `device_id` / stale callbacks after rebuild
See Pattern 6 and Anti-Patterns. Add a test: reconfigure -> new actions run, old do not, baseline kept, discovery republished with the new name.

### Pitfall 4: PHACC's MQTT mock loops publishes back with the publish's own `retain` flag
**What goes wrong:** in a test, `switch.turn_on` on the discovered entity publishes with `retain=True`; the mocked paho client immediately feeds that back to subscribers as a message with `retain=True` `[VERIFIED: pytest_homeassistant_custom_component/plugins.py:1110-1114]`
```
        @ha.callback
        def _async_fire_mqtt_message(topic, payload, qos, retain, properties=None):
            async_fire_mqtt_message(
                hass, topic, payload or b"", qos, retain, properties=properties
            )
```
so the tracker would classify a UI toggle as a retained replay (baseline, no action). A real broker forwards to an established subscription with `retain=False` (MQTT-3.3.1-9, quoted in `client.py:1069-1072`: "It MUST set the RETAIN flag to 0 when a PUBLISH Packet is sent to a Client because it matches an established subscription"; observed with Mosquitto 2.1.2). **Avoid:** in unit tests drive state with explicit `async_fire_mqtt_message(hass, topic, payload, retain=False|True)`; do not assert edge semantics through publish loopback; cover the real-broker invariant in the optional broker test.

### Pitfall 5: `async_block_till_done()` does not wait for background tasks
Use `wait_background_tasks=True` where the code path uses `entry.async_create_background_task` and truly suspends. `[VERIFIED: spike]`

### Pitfall 6: `Lingering timer after test ... MQTT._async_start_misc_periodic`
Every test using `mqtt_mock` fails at teardown in a custom-component repo unless `expected_lingering_timers` is overridden to `True` in `tests/conftest.py` (PHACC autouse fixture, `plugins.py:333-342`). The mocked client never emits the socket-close callback that cancels the timer. `[VERIFIED: spike]` bare `mqtt_mock` test fails without it, all pass with it.

### Pitfall 7: hassfest translation rules
- Placeholders inside single quotes are rejected. Verbatim hassfest output: `* [ERROR] [TRANSLATIONS] Invalid translations/en.json: the string should not contain placeholders inside single quotes at 'issues.action_failed.description'. Got "The actions for '{trigger}' of {device} failed at {time}: {error}"` `[VERIFIED: spike, ghcr.io/home-assistant/hassfest]`.
- Only `en.json` is validated; `de.json` drift is invisible to CI -> add a parity test (keys and `{placeholders}` identical).
- Selector/option/abort/error/issue keys all need entries; `config_subentries.<type>.{initiate_flow.user, entry_type, step, error, abort}` passed hassfest `[VERIFIED: spike]`.

### Pitfall 8: Discovery prefix and discovery-disabled MQTT
Prefix comes from `entry.data | entry.options`; discovery can also be disabled in MQTT (`components/mqtt/__init__.py:603-604`: `if conf.get(CONF_DISCOVERY, DEFAULT_DISCOVERY):` / `await discovery.async_start(`). If disabled, no entity ever appears. Log a warning and (recommended) raise a non-fixable Repairs issue `mqtt_discovery_disabled` at setup. `[ASSUMED]` A8 (issue vs warning only).

### Pitfall 9: D-07 vs the first live toggle
See Open Question 1 / Assumption A1. Literal reading makes the first UI toggle on a fresh device do nothing (the entity turns on, no actions) because `last_acted` is `None` and "the first state that arrives" is the toggle echo.

### Pitfall 10: ActionSelector field errors may be invisible
See Pattern 6. Always show a `base` error.

### Pitfall 11: Retained clear arrives as an empty live message
When a topic is cleared, subscribers get `''` with `retain=False` (Mosquitto observation). Ignore it at DEBUG, not WARNING (otherwise every delete/clear logs a warning; D-02's "ignored and logged" -> log level is discretion).

### Pitfall 12: Dismissed Repairs issue stays dismissed
`async_get_or_create` on an existing issue uses `dataclasses.replace(issue, active=True, ..., translation_placeholders=...)` and never touches `dismissed_version` `[VERIFIED: helpers/issue_registry.py:181-193; field at :62]`, so repeated failures update the text but keep a user-dismissed issue dismissed (matches D-09). `async_delete_issue` on success removes it entirely, resetting the dismissal (`issue_registry.py:415-421`). Cap `str(err)` (e.g. 500 chars) before putting it in a placeholder, and log the full exception separately; error text can echo rendered templates.

### Pitfall 13: GitHub repo does not exist yet
`gh repo view akentner/homeassistant-mqtt-actions-integration` -> `Could not resolve to a Repository`; the local repo has no remote (`git remote -v` empty). hacs/action needs a public repo with a description, topics, issues enabled, `README`, a recognised `LICENSE` (MIT is in the accepted list), `hacs.json`, `brand/icon.png`. Creating a public repo is an external, user-visible action -> `checkpoint:human-action` (or explicit user approval) for the planner. `[VERIFIED: gh repo view, git remote -v; validators read from hacs/integration main]`

### Pitfall 14: Ruff `select = ["ALL"]` noise
On the prototype the blueprint config produced 113 findings, dominated by test-only rules (`S101`, `ANN001`, `D103`, `ARG001`, `PT018`, `PLC0415`, `PLR2004`, `FBT001`) plus `CPY001`. Ship with: `ignore += ["CPY001"]` and `[lint.per-file-ignores] "tests/**" = ["S101", "ANN", "D", "ARG", "PLR2004", "PLC0415", "SLF001", "PT018", "FBT"]`, `line-length = 120`. `[VERIFIED: spike ruff 0.16.9 --statistics]`

### Pitfall 15: Hub `base_topic` is one-way
Do not offer a base-topic reconfigure in Phase 1 (D-01 "one-way"). Validate strictly at input: `mqtt.valid_publish_topic` (rejects wildcards), no leading/trailing `/`, no empty level (`//`), not starting with `$`, no NUL. Wildcards in the base would turn per-device subscriptions into broad ones (security, see Security Domain).

## Code Examples

Verified in the spike unless tagged otherwise.

### manifest.json (hassfest-clean) and hacs.json
```json
{
  "domain": "mqtt_actions",
  "name": "MQTT Actions",
  "codeowners": ["@akentner"],
  "config_flow": true,
  "dependencies": ["mqtt"],
  "documentation": "https://github.com/akentner/homeassistant-mqtt-actions-integration",
  "integration_type": "service",
  "iot_class": "local_push",
  "issue_tracker": "https://github.com/akentner/homeassistant-mqtt-actions-integration/issues",
  "requirements": [],
  "single_config_entry": true,
  "version": "0.1.0"
}
```
```json
{ "name": "MQTT Actions", "homeassistant": "2026.9.0" }
```
`hacs.json` keys allowed by HACS `[VERIFIED: hacs/integration utils/validate.py HACS_MANIFEST_JSON_SCHEMA]`: `content_in_root, country, filename, hacs, hide_default_branch, homeassistant, persistent_directory, render_readme, zip_release`, required `name`, extras rejected. HACS manifest required keys: `codeowners, documentation, domain, issue_tracker, name, version`. Second instance of the flow aborts with `single_instance_allowed` `[VERIFIED: spike test_hub_flow_creates_entry]`.

### Gateway subscribe with the correct callback shape
```python
from functools import partial
from homeassistant.core import callback

class Manager:
    async def _async_add(self, sub) -> None:
        device = await self._async_build(sub)
        self.devices[device.device_id] = device
        device.unsub = await mqtt.async_subscribe(          # coroutine: await it
            self.hass, topics.state_topic(self.base, device.device_id),
            partial(self._on_message, device.device_id), qos=1,   # partial of a @callback
        )

    @callback
    def _on_message(self, device_id: str, msg: ReceiveMessage) -> None:
        if (device := self.devices.get(device_id)) is None:      # resolve at message time
            return
        decision = state.decide(msg.retain, msg.payload, device.last_acted,
                                device.startup_pending, device.run_on_startup)
        ...
```

### Pure decision function (test-first target)
```python
def decide(retain: bool, payload: str, last_acted: str | None,
           startup_pending: bool, run_on_startup: bool) -> Decision:
    value = payload.strip().upper()
    if value not in ("ON", "OFF"):
        return Decision(act=False, baseline=last_acted, ignored=True)
    if retain:
        return Decision(act=startup_pending and run_on_startup, baseline=value)
    return Decision(act=value != last_acted, baseline=value)   # live message; A1: last_acted None acts
```

### Discovery payload (full keys)
```python
{
  "device": {"identifiers": [f"mqtt_actions_{uuid}"], "name": name},
  "origin": {"name": "MQTT Actions", "sw_version": VERSION},
  "components": {"switch": {
      "platform": "switch", "unique_id": uuid, "name": None,
      "state_topic": t, "command_topic": t, "retain": True, "qos": 1,
      "payload_on": "ON", "payload_off": "OFF", "value_template": "{{ value | upper }}"}},
  "availability": [{"topic": f"{base}/v1/instances/{instance_id}/availability"}],
}
# publish: await mqtt.async_publish(hass, f"{prefix}/device/{uuid}/config", json_dumps(payload), qos=1, retain=True)
# remove:  await mqtt.async_publish(hass, same_topic, "", qos=1, retain=True)
```
`[VERIFIED: spike]` the full-key form above ran green (all 14 tests, including entity creation, availability and rename republish). Key definitions: `components/mqtt/schemas.py:135` `vol.Optional(CONF_IDENTIFIERS, default=list): vol.All(` (device) and `schemas.py:161` `vol.Optional(CONF_SW_VERSION): cv.string,` (origin). The abbreviated forms (`dev/o/cmps/p`) also worked in an earlier run but add nothing.

### Failure surfacing
```python
try:
    await script.async_run({"trigger": {...}}, Context())
except Exception as err:                    # noqa: BLE001
    _LOGGER.exception("Actions of %s for %s failed", device.name, value)
    ir.async_create_issue(hass, DOMAIN, f"action_failed_{device.device_id}", is_fixable=False,
        severity=ir.IssueSeverity.ERROR, translation_key="action_failed",
        translation_placeholders={"device": device.name, "trigger": value, "error": str(err)[:500], "time": now_iso})
else:
    ir.async_delete_issue(hass, DOMAIN, f"action_failed_{device.device_id}")
```
Signature `[VERIFIED: helpers/issue_registry.py:339-353]` `async_create_issue(hass, domain, issue_id, *, breaks_in_ha_version=None, data=None, is_fixable: bool, is_persistent: bool = False, ..., severity: IssueSeverity, translation_key: str, translation_placeholders=None)`.

### tests/conftest.py
```python
import pytest

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations): return

@pytest.fixture
def expected_lingering_timers() -> bool:      # mocked paho client never cancels its misc-loop timer
    return True
```
`pyproject.toml`: `requires-python = ">=3.14.2"`, `dependencies = []`, `[dependency-groups] dev = ["pytest-homeassistant-custom-component==0.13.367", "ruff==0.16.9"]`, `[tool.pytest.ini_options] asyncio_mode = "auto"`, `testpaths = ["tests"]`. (`uv sync` produced `uv.lock`; `uv sync --locked` re-checks.)

### CI (pins verified 2026-09-29 with `git ls-remote`, all lightweight tags = commit SHAs)
```yaml
# .github/workflows/validate.yml
name: Validate
on: { workflow_dispatch: {}, schedule: [{cron: "0 0 * * *"}], push: {branches: [main]}, pull_request: {branches: [main]} }
permissions: {}
jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with: { persist-credentials: false }
      - uses: home-assistant/actions/hassfest@06749dd8c0b54f350bc69c8752456cee498808a3 # master
  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: hacs/action@d556e736723344f83838d08488c983a15381059a # 22.5.0
        with: { category: integration }          # no ignore: brands
# .github/workflows/ci.yml  (lint + test)
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with: { python-version: "3.14", enable-cache: true }
      - run: uv sync --locked
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -q
```
`setup-uv` inputs `python-version`, `enable-cache` exist `[VERIFIED: astral-sh/setup-uv v10.2.0 action.yml]`. hassfest action body is `docker run --rm -v ${{ github.workspace }}://github/workspace ghcr.io/home-assistant/hassfest` `[VERIFIED: home-assistant/actions hassfest/action.yml]`; locally (podman-docker emulation present): `docker run --rm -v "$PWD":/github/workspace:Z ghcr.io/home-assistant/hassfest`. Add `.github/dependabot.yml` for `github-actions` and `uv` ecosystems (weekly; group PHACC).

### Optional real-broker invariant test (no HA involved)
```python
@pytest.mark.broker   # skipped unless `mosquitto` is on PATH
def test_live_forward_has_retain_false_and_replay_has_retain_true(mosquitto_port): ...
```
Start `mosquitto -c <conf with listener <port> 127.0.0.1, allow_anonymous true, persistence false>`; assert the four observations listed in Pattern 3. CI: `sudo apt-get install -y mosquitto` or a service container.

## Verified Platform Facts (in-repo / installed-source values)

Read this session from HA `2026.9.4` (`homeassistant/...`) and PHACC `0.13.367`.

| # | Fact | Source (path:lines) and verbatim quote |
|---|------|----------------------------------------|
| F-1 | `ReceiveMessage` carries `retain` | `components/mqtt/models.py:149-157`: `class ReceiveMessage:` ... `retain: bool` |
| F-2 | Public subscribe is a coroutine returning the unsubscribe callable | `components/mqtt/client.py:251-257`: `async def async_subscribe(hass: HomeAssistant, topic: str, msg_callback: Callable[[ReceiveMessage], Coroutine[Any, Any, None] \| None], qos: int = DEFAULT_QOS, encoding: str \| None = DEFAULT_ENCODING,) -> CALLBACK_TYPE:` |
| F-3 | Publish signature | `client.py:149-158`: `qos: int = 0, retain: bool = False, encoding: str \| None = DEFAULT_ENCODING, *, message_expiry_interval: int \| None = None,` |
| F-4 | Retained replay is de-duplicated per subscription | `client.py:1348-1354`: `if msg.retain:` / `if topic in retained_topics:` / `continue` |
| F-5 | Every new subscription re-SUBSCRIBEs (broker replays retained) | `client.py:1027-1029`: `# Only subscribe if currently connected.` `if self.connected:` `self._async_queue_subscriptions(((topic, qos),))` |
| F-6 | Reconnect resubscribes everything and resets replay tracking | `client.py:1267-1268`: `self._max_qos.clear()` / `self._retained_topics.clear()` |
| F-7 | `async_wait_for_mqtt_client` waits for setup, not connection | `components/mqtt/util.py:210-216`: `Waits when mqtt set up is in progress,` `It is not needed that the client is connected.` `Returns False when the client is not available.` |
| F-8 | Connection status hook | `components/mqtt/__init__.py:672,676-677`: `type ConnectionStatusCallback = Callable[[bool], None]` / `def async_subscribe_connection_status(hass: HomeAssistant, connection_status_callback: ConnectionStatusCallback) -> Callable[[], None]:` |
| F-9 | Job type classification | `core.py:353-362` (quoted in Anti-Patterns) |
| F-10 | Script signature | `helpers/script.py:1505-1523`: `def __init__(self, hass: HomeAssistant, sequence: Sequence[dict[str, Any]], name: str, domain: str, *, change_listener..., log_exceptions: bool = True, logger: logging.Logger \| None = None, max_exceeded: str = DEFAULT_MAX_EXCEEDED, max_runs: int = DEFAULT_MAX, running_description..., script_mode: str = DEFAULT_SCRIPT_MODE, top_level: bool = True, variables..., enabled: bool = True,` ; `async_run(self, run_variables=None, context=None, started_action=None)` at `:1891-1896`; `async def async_unload(self) -> None:` at `:2025` |
| F-11 | Issue API | `helpers/issue_registry.py:339-353` (signature above); `async_delete_issue(hass, domain, issue_id)` at `:415`; `async_ignore_issue(hass, domain, issue_id, ignore: bool)` at `:435-436` |
| F-12 | Entry unload callbacks may be coroutine functions | `config_entries.py:1241-1244`: `def async_on_unload(self, func: Callable[[], Coroutine[Any, Any, None] \| None],) -> None:` |
| F-13 | ActionSelector returns data unvalidated | `helpers/selector.py:284-286` (quoted in Pattern 6) |
| F-14 | Schema serialization for the frontend uses probatio | `helpers/data_entry_flow.py:7` `from probatio import to_field_list`; spike: serialized field `{"name": "on_change_to_on", "selector": {"action": {}}}` |
| F-15 | Core's own flows already use ActionSelector | `components/template/config_flow.py:267-268`: `vol.Required(CONF_ON_ACTION): selector.ActionSelector(),` `vol.Required(CONF_OFF_ACTION): selector.ActionSelector(),` |
| F-16 | Core MQTT has its own subentry flow | `components/mqtt/config_flow.py:4604`: `class MQTTSubentryFlowHandler(ConfigSubentryFlow):` |
| F-17 | Retain option on MQTT read/write entities | `components/mqtt/config.py:43`: `vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,` |
| F-18 | `default_entity_id` exists (not used in Phase 1) | `components/mqtt/schemas.py:185`: `vol.Optional(CONF_DEFAULT_ENTITY_ID): cv.string,` |
| F-19 | voluptuous is aliased to probatio in HA | `homeassistant/__init__.py:3-8`: `from probatio import BuildPolicy, set_build_policy` / `from probatio.compat import install_as_voluptuous` ... `install_as_voluptuous()` |
| F-20 | PHACC fixtures and echo behaviour | `pytest_homeassistant_custom_component/common.py:460-467`: `def async_fire_mqtt_message(hass, topic, payload, qos: int = 0, retain: bool = False, properties=None)`; `plugins.py:1110-1114` (loopback quoted in Pitfall 4); `plugins.py:334`: `def expected_lingering_timers() -> bool:` |
| F-21 | Subentry delete goes through the websocket API | `components/config/config_entries.py:831,848` (`"type": "config_entries/subentries/delete"`, `hass.config_entries.async_remove_subentry(entry, msg["subentry_id"])`) |
| F-22 | Brand images for custom integrations | `[CITED: developers.home-assistant.io/docs/core/integration/brand_images]` "Custom integrations should place brand images in `custom_components/my_integration/brand/`" and "Starting with Home Assistant 2026.3"; HACS check `[VERIFIED: hacs/integration validate/brands.py]` `ASSET_FILENAME = "icon.png"`, `asset_path = f"{self.repository.content.path.remote}/brand/{ASSET_FILENAME}"` |

## Runtime State Inventory

Not applicable: greenfield phase, no rename/refactor/migration.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `import voluptuous as vol` | `import probatio as vol` (voluptuous kept as alias) | HA 2026.9 | Both work in flows; CLAUDE.md mandates probatio |
| `Script.async_stop` only | `Script.async_unload` (also removes from the global script registry, blocks new runs) | present in tag 2026.9.0 | Use on teardown/rebuild |
| Brand icons in `home-assistant/brands` | `custom_components/<domain>/brand/icon.png` | HA 2026.3 | No `ignore: brands` in HACS action |
| Options-flow device lists | Config subentries | HA 2025.3+ | Native add/reconfigure/delete |
| `voluptuous_serialize` for flow schemas | `probatio.to_field_list` | HA 2026.9 | `voluptuous_serialize` not installed; tests must use `to_field_list` |
| `hass.data[DOMAIN]` | `entry.runtime_data` | 2024+ | Per CLAUDE.md |

**Deprecated/outdated:** passing `None` for `qos`/`retain` to `mqtt.async_publish` is deprecated (`client.py:195-208`: `if qos is None or retain is None:` ... `breaks_in_ha_version="2027.6.0"`): always pass ints/bools.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | D-07 should be read as: a *retained* first message sets the baseline; a *live* first message on a device with no baseline is a real edge and runs actions. The literal wording ("the first state that arrives sets the baseline without running actions") would make the first UI toggle on a brand-new device a no-op | Pattern 3, Pitfall 9, Open Question 1 | If user wants the literal reading, the first toggle after creation runs no actions and the decision function's `last_acted is None` row flips to "no". Needs user confirmation before Plan 3 |
| A2 | `ha-selector-action` renders inside the subentry dialog and a `base` error banner is visible; a field-level error under the action editor may not render | Pattern 6, Pitfall 10 | If the editor does not render, fall back to the options-flow editor (D-13). Backend behaviour is verified; only the visual is not |
| A3 | `lxc-haos-104` and `hassio-n2plus` can run HA 2026.9.0 (Python 3.14) | Environment Availability | `hacs.json` floor might need to stay lower, or a host is excluded from the test bed. `haos-op3050-1` (2026.9.4) is verified; `lxc-haos-104` SSH lands in a container without Supervisor token (`Error: unauthorized: missing or invalid API token`), `hassio-n2plus` timed out on port 22 |
| A4 | A 256x256 RGBA `icon.png` is accepted (HACS only checks the file's existence; sizes are not enforced by the validators read) | Standard Stack | Cosmetic only (icon rendering) |
| A5 | Availability = per-instance retained topic `<base>/v1/instances/<instance_uuid>/availability` (`online` on start/reconnect, `offline` on unload). Consistent with Phase 3 only if followers should also go unavailable when the owner instance is offline (open decision in STATE.md) | Pattern 5 | Discovery payload is re-publishable, so the topic can change in Phase 3 without breaking stored data; low cost |
| A6 | Removing the hub config entry (`async_remove_entry`) should publish empty discovery for all devices of that instance (explicit user action; avoids ghost entities). In Phase 3 this must become a confirmed, multi-instance-aware delete | Open Question 2 | If not done, removal leaves inert entities on the broker; if done and unconfirmed in Phase 3 it deletes devices for everyone |
| A7 | One subentry type per domain (`switch`) instead of a single `device` type with a menu | Standard Stack | Subentry type names are persisted; changing later needs a migration |
| A8 | MQTT discovery disabled/prefix-mismatch is surfaced as a Repairs issue rather than only a log line | Pitfall 8 | Users with discovery disabled see nothing happen |
| A10 | Clearing the retained state topic on explicit device delete (in addition to discovery) is desirable | Pattern 5 / Open Question 3 | Otherwise a stale retained `ON`/`OFF` stays on the broker per deleted UUID (harmless, garbage) |

## Open Questions

1. **D-07 vs first live toggle (A1).**
   - What we know: retained replay -> baseline is unambiguous (D-05/STA-04). `switch.turn_on` on a new device publishes retained `ON`; the echo arrives live (`retain=False`) with `last_acted is None`.
   - What's unclear: whether "the first state that arrives" includes a live message.
   - Recommendation: retained-first = baseline, live-first = edge (run actions). Ask the user in discuss/plan handoff with the concrete example ("create a switch, toggle it once: should the on-actions run?").

2. **Hub removal semantics (A6).** Recommend clearing owned discovery on `async_remove_entry` in Phase 1 and flagging for Phase 3 redesign. Alternative: leave devices on the broker (ghosts). Needs a one-line user decision.

3. **State topic on delete (A10).** Recommend publishing empty retained to the state topic after unsubscribing (so the own subscription never sees the `''`). Discovery-clear first, then state-clear.

4. **Availability semantics (A5).** Keep the per-instance topic in Phase 1; revisit with the Phase 3 owner-availability decision.

5. **Hosts.** Check `lxc-haos-104` (needs a shell with Supervisor access or the HA UI/API) and `hassio-n2plus` (reachable via Tailscale?). Suggested: `ha core info` from the HA OS host shell or `curl` the Supervisor/Core API with a token. Not automatable from here.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | tests, uv | yes | 3.14.7 | `uv python install 3.14` |
| uv | env/lock | yes | 0.12.7 (PyPI 0.12.19) | `uv self update` |
| podman (docker CLI emulation) + hassfest image | local hassfest | yes (image pulled) | `ghcr.io/home-assistant/hassfest:latest` | rely on CI only |
| Mosquitto | optional broker test | yes | 2.1.2 | skip marker |
| gh CLI | repo creation, topics | yes, authed as `akentner` | - | manual GitHub UI |
| GitHub repo `akentner/homeassistant-mqtt-actions-integration` | CI, HACS check | **no** (does not exist, no remote) | - | none: `checkpoint:human-action` |
| haos-op3050-1 (HA) | manual UAT of the dialog | yes | Core 2026.9.4, OS 18.3, amd64 | - |
| lxc-haos-104 | host check (D-13) | reachable via ssh, HA version not obtainable (`ha` CLI unauthorized in SSH container) | unknown | check via HA UI (Settings -> About) |
| hassio-n2plus | host check (D-13) | **no** (ssh port 22 timed out over Tailscale) | unknown | check when reachable |
| Node / browser automation | frontend visual check | node yes; browser automation not attempted | - | manual `checkpoint:human-verify` on haos-op3050-1 |

**Missing dependencies with no fallback:** the GitHub repository (needs the user to approve/perform creation).
**Missing dependencies with fallback:** the two secondary hosts (verify manually; `hacs.json` floor stays `2026.9.0` per the project decision unless a host proves it cannot run it).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.4.0 (pinned transitively) via pytest-homeassistant-custom-component 0.13.367 `[VERIFIED: import metadata in spike venv]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) - Wave 0 |
| Quick run command | `uv run pytest -x -q` (spike suite: 14 tests in ~1.6 s) |
| Full suite command | `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && docker run --rm -v "$PWD":/github/workspace:Z ghcr.io/home-assistant/hassfest` |

TDD is enabled in `.planning/config.json` (`workflow.tdd_mode: true`): write the pure tests (`test_state.py`, `test_topics.py`, translations parity) first, then the flow/manager tests, then implementation.

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FND-01 | manifest keys, `hacs.json` keys, `brand/icon.png` present, domain == folder | unit | `uv run pytest tests/test_repo_structure.py -q` + hassfest container | Wave 0 |
| FND-02 | workflows pin actions by SHA, `permissions: {}`, no `ignore:` | unit (parse YAML) + CI | `uv run pytest tests/test_repo_structure.py -q` | Wave 0 |
| FND-03 | abort `mqtt_required` without MQTT; entry has uuid4 `instance_id`; second setup aborts `single_instance_allowed`; invalid base topic rejected | flow | `uv run pytest tests/test_config_flow.py -q` | Wave 0 |
| FND-04 | en/de key + placeholder parity; hassfest green | unit + container | `uv run pytest tests/test_translations.py -q` | Wave 0 |
| FND-05 | no MQTT -> `setup_retry`; connection-status True republishes discovery+availability; reload keeps a single subscription (1 message = 1 run) | integration (mqtt_mock) | `uv run pytest tests/test_manager.py -q` | Wave 0 |
| DEV-01 | create Switch via subentry flow, UUID stored, unique_id == UUID | flow | `uv run pytest tests/test_config_flow.py -k switch -q` | Wave 0 |
| DEV-02 | raw actions persisted; schema serializes to `{"action": {}}` via `probatio.to_field_list` | flow | same | Wave 0 |
| DEV-05 | invalid action -> error; `device_id` (target/device action/nested) -> warning; resubmit saves | flow + unit (detector) | `uv run pytest tests/test_config_flow.py tests/test_device_ids.py -q` | Wave 0 |
| DEV-08 | failing service -> log + Repairs issue (non-fixable, placeholders); next success deletes; repeated failure updates same issue id | integration | `uv run pytest tests/test_manager.py -k issue -q` | Wave 0 |
| STA-01 | `switch.turn_on` on discovered entity publishes `(state_topic, "ON", 1, True)` | integration | `uv run pytest tests/test_discovery.py -k toggle -q` | Wave 0 |
| STA-02 | live external `on`/`off` (any case) runs matching actions once | integration | `uv run pytest tests/test_manager.py -k edge -q` | Wave 0 |
| STA-04 | retained -> no action; `run_on_startup` runs once, later replay does not; reconnect replay baseline only | unit (decision table) + integration | `uv run pytest tests/test_state.py tests/test_manager.py -k "retain or startup" -q` | Wave 0 |
| STA-05 | `last_acted` persisted across reload (`hass_storage`); duplicate live value ignored; unknown payload / empty string ignored | unit + integration | `uv run pytest tests/test_state.py tests/test_manager.py -k baseline -q` | Wave 0 |
| DSC-01 | payload creates `switch.<name>`, `unique_id == uuid`, initial state `unknown`, availability `offline` -> `unavailable`, lower-case inbound accepted | integration | `uv run pytest tests/test_discovery.py -q` | Wave 0 |
| DSC-02 | unload publishes no empty `/config`; subentry removal publishes exactly one; orphan (published − current) cleaned at start | integration | `uv run pytest tests/test_manager.py -k "unload or delete or orphan" -q` | Wave 0 |
| (invariant) | real broker: replay `retain=True`, live `retain=False`, clear delivers `''` live | broker (optional marker) | `uv run pytest -m broker -q` | Wave 0 (optional) |

Test-writing rules learned in the spike: drive state with explicit `async_fire_mqtt_message(..., retain=...)` (never rely on publish loopback, Pitfall 4); use `await hass.async_block_till_done(wait_background_tasks=True)` where background tasks suspend; supply `expected_lingering_timers`; use `async_mock_service` for action targets; assert discovery behaviour through a publish call, not merely entity existence; for the `ha-selector-action` visual check use a manual UAT step.

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q && uv run ruff check .` (seconds)
- **Per wave merge:** full suite command (adds `ruff format --check` and the hassfest container)
- **Phase gate:** CI green on the pushed phase branch (hassfest, HACS, Ruff, pytest) plus the manual UAT below before `/gsd-verify-work`

### Manual UAT (cannot be automated here)
1. On `haos-op3050-1`: install the branch build, add the hub, add a Switch, confirm the action editor renders in the "Add switch device" dialog, the `base` error banner shows for an invalid action and for a `device_id`, DE/EN strings show.
2. Toggle the switch in the UI and publish `on`/`off` with `ha-ws`/mosquitto_pub to the state topic; restart HA and reload the integration; confirm no actions on restart and one action per real change.

### Wave 0 Gaps
- [ ] `pyproject.toml`, `uv.lock`, `.ruff.toml` (blueprint base + CPY001 and test per-file ignores) - greenfield
- [ ] `tests/conftest.py` (`enable_custom_integrations`, `expected_lingering_timers`)
- [ ] `tests/test_state.py`, `test_topics.py`, `test_device_ids.py`, `test_translations.py`, `test_repo_structure.py` (pure/fast)
- [ ] `tests/test_config_flow.py`, `test_manager.py`, `test_discovery.py` (PHACC)
- [ ] optional `tests/broker/` with `mosquitto` fixture and `broker` marker registered in `pyproject.toml`
- [ ] Framework install: `uv add --dev pytest-homeassistant-custom-component==0.13.367 ruff==0.16.9` (after the package checkpoint)

## Security Domain

`security_enforcement` is enabled (absent = enabled), ASVS level 1, block on `high`.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no own auth; broker credentials belong to HA's MQTT entry, never stored here) | - |
| V3 Session Management | no | - |
| V4 Access Control | yes (limited) | Admin-only access is enforced by HA (e.g. `config_entries/subentries/delete` is decorated `@websocket_api.require_admin`, `components/config/config_entries.py:828`); the state topic is writable by anyone with broker write access (Option A) -> document, broker ACLs come in Phase 3 (TRU-04); README warns in Phase 1 |
| V5 Input Validation | yes | `mqtt.valid_publish_topic` + strict base-topic checks; payload allow-list `ON`/`OFF` after `strip().upper()`; `cv.SCRIPT_SCHEMA` + `async_validate_actions_config` on authoring AND on every Script build; UUID from `uuid4` only, never from user or payload |
| V6 Cryptography | no (no crypto; UUIDs are identifiers, not secrets) | - |
| V7 Error handling/logging | yes | Do not log action `data` (may hold tokens); log service names/device names; truncate `str(err)` in Repairs placeholders |
| V10/V14 Config & supply chain | yes | Actions pinned by SHA, `permissions: {}`, `persist-credentials: false`, Dependabot, lockfile `uv.lock`, no runtime deps |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Base topic with wildcard (`#`, `+`) or `$SYS` prefix widens the per-device subscription and lets unrelated broker traffic hit the parser | Tampering / Info disclosure | Validate base topic at input (Pitfall 15); parser ignores anything not ON/OFF |
| Anyone with broker write access publishes `ON`/`OFF` to a state topic and triggers local actions | Tampering / Elevation | Inherent to Option A; actions are locally authored and schema-validated; broker ACLs + docs (Phase 3, TRU-04); no remote-provided actions exist in Phase 1 |
| Payload flood on a state topic (rapid alternation) | DoS | Per-device FIFO lock keeps runs serial; circuit breaker is Phase 2 (STA-06) - note the unbounded lock queue as a known Phase 1 limitation |
| Action error text leaks secrets into Repairs UI | Info disclosure | Truncate, and keep detailed exception in log only |
| Device name in discovery JSON / Repairs markdown | Tampering | Build JSON with `json_dumps` (no string concatenation); names are user-supplied by an admin |
| Malicious dependency via dev tooling | Supply chain | Package legitimacy checkpoint; lockfile; Dependabot |
| Stale retained `online` after crash hides a dead instance | Repudiation / availability | Documented limitation (no LWT on shared client); AVL-01 in v2 |

## Suggested Work Breakdown (for the planner; adjust freely)

TDD order inside each plan: tests first for the pure modules, then flow/manager tests, then implementation.

1. **Plan 1 - Spike closure + host check + repo bootstrap (D-13).** Package checkpoint; visual check of the action editor on `haos-op3050-1` (throw-away branch build), version checks for the two other hosts, decision on A1/A6/A10; `checkpoint:human-action` to create the public GitHub repo (`gh repo create`, description, topics such as `home-assistant`, `hacs`, `mqtt`, `custom-component`, issues on, MIT `LICENSE`, remote, first push). Output: go/no-go for subentry flow and the `hacs.json` floor.
2. **Plan 2 - Scaffold, CI, HACS (FND-01, FND-02).** `pyproject.toml`/`uv.lock`/`.ruff.toml`, `manifest.json`, `hacs.json`, `brand/icon.png`, README, LICENSE, workflows with pinned SHAs, Dependabot, `test_repo_structure.py`; hassfest container run must be green before the first push.
3. **Plan 3 - Pure core (STA-04, STA-05, D-02, D-05..D-07).** `topics.py`, `state.py` decision function + table tests, device-id detector, base-topic validator. (A1 must be settled.)
4. **Plan 4 - Hub flow + i18n (FND-03, FND-04).** Hub flow, `single_config_entry`, en/de strings, parity test.
5. **Plan 5 - Switch subentry flow (DEV-01, DEV-02, DEV-05).** Create + reconfigure, validation, warn-then-confirm, immutable UUID.
6. **Plan 6 - Runtime: gateway, discovery, tracker, runner, lifecycle (FND-05, STA-01, STA-02, DEV-08, DSC-01, DSC-02).** Manager reconcile, Store, orphan cleanup, reconnect republish, availability, Repairs, unload semantics.
7. **Plan 7 - Verification.** Manual UAT, optional broker test, full gate.

## Sources

### Primary (HIGH confidence)
- HA core 2026.9.4 source (installed wheel): `config_entries.py`, `core.py`, `helpers/{script,selector,issue_registry,data_entry_flow,config_validation}.py`, `components/mqtt/{__init__,client,util,models,discovery,schemas,switch,entity,config,config_flow}.py`, `components/template/config_flow.py`, `components/config/config_entries.py` - read line-level this session
- PHACC 0.13.367 `plugins.py`, `common.py` - read this session
- Spike prototype (14 tests green), real hassfest container run, Ruff 0.16.9 run, Mosquitto 2.1.2 + paho retain-flag experiment - executed this session
- `hacs/integration` main: `validate/{brands,hacsjson,integration_manifest,images,information,description,topics,issues,license}.py`, `utils/validate.py` - read this session
- `git ls-remote` for actions/checkout, astral-sh/setup-uv, hacs/action, home-assistant/actions; `astral-sh/setup-uv` v10.2.0 `action.yml`; `home-assistant/actions` `hassfest/action.yml`; ludeeus `integration_blueprint` `validate.yml`, `lint.yml`, `.ruff.toml`, `hacs.json`
- PyPI JSON for pytest-homeassistant-custom-component, ruff, uv
- `ssh haos-op3050-1 "ha core info"`: Core 2026.9.4, OS 18.3

### Secondary (MEDIUM confidence)
- developers.home-assistant.io `creating_integration_file_structure` and `core/integration/brand_images` (brand directory, HA 2026.3) `[CITED]`
- hacs.xyz `publish/action` and `publish/integration` `[CITED]`
- home-assistant/frontend `step-flow-form.ts`, `ha-selector-action.ts` (web fetch summaries) `[CITED]`

### Tertiary (LOW confidence)
- Visual behaviour of the action editor and error display in the dialog - not observed (A2)
- HA versions of `lxc-haos-104` and `hassio-n2plus` - not obtainable (A3)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions from PyPI/GitHub/registry and an executed spike on the exact pinned versions
- Architecture: HIGH for backend mechanics (source + tests); MEDIUM for frontend rendering
- Pitfalls: HIGH - most were hit and fixed during the spike; two are source-derived (empty-payload delete, dismissed issue)

**Research date:** 2026-09-29
**Valid until:** 2026-10-06 for pins (PHACC/HA move daily: re-resolve `pytest-homeassistant-custom-component` and hassfest SHA before the first commit), ~30 days for the architectural findings
