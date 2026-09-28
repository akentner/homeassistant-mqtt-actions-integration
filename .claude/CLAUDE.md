<!-- GSD:project-start source:PROJECT.md -->

## Project

**MQTT Actions Integration**

A Home Assistant custom integration (HACS-ready) that turns MQTT state changes into locally executed HA action sequences. Devices (Switch, Select) are configured via UI, published through MQTT Discovery, and described in a central config stored in the MQTT broker — so any other HA instance on the same broker picks it up and creates the same devices. It is for people running several HA instances who want synchronized, state-driven behavior without YAML boilerplate.

**Core Value:** A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.

### Constraints

- **Platform**: Home Assistant custom component (Python) using the built-in MQTT integration — must work with the standard MQTT Discovery mechanism
- **Distribution**: HACS-compatible public repo — dictates repo layout, versioning and CI
- **Security**: Actions from the broker run with full local service access — needs explicit design (trust model, opt-in)
- **Language**: UI and chat in German for the user; code, commits and comments in English

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Headline Decisions

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.14 (>=3.14.2) | Runtime | HA 2026.9.x hard requirement (`requires-python >=3.14.2`). PHACC requires `>=3.14`. | HIGH |
| Home Assistant Core | 2026.9.x (floor `2026.9.0`; dev/CI resolves 2026.9.4) | Host platform | Current stable. Ships probatio, config subentries, local brand images (since 2026.3), and the MQTT API used here. | HIGH |
| HA `mqtt` integration (built-in) | bundled (paho-mqtt 2.1.0 inside HA) | Broker connection, discovery consumption, pub/sub | Required by project constraints. Reuses the user's broker credentials, TLS and reconnect handling. Declare in `manifest.json` `dependencies`. | HIGH |
| Config Flow (+ Options/Reconfigure flow, + Config Subentries) | HA core API | UI setup and device management | `ConfigSubentryFlow` and `async_get_supported_subentry_types` are current core API. Subentries fit "one instance, many devices" (see Device Model below). | HIGH (API), MEDIUM (fit as device store) |
| `homeassistant.helpers.script.Script` | HA core | Execute inline action sequences locally | Same engine as automations and scripts (templates, `choose`, `delay`, targets, `continue_on_error`). Signature verified: `Script(hass, sequence, name, domain, *, script_mode=..., max_runs=..., variables=..., ...)`, `await script.async_run(run_variables, context)`. | HIGH |
| `homeassistant.helpers.selector.ActionSelector` (`selector: action`) | HA core | UI editor for action sequences in config/options/subentry flows | Native action editor as in the automation UI. Stores plain list-of-dict data. | HIGH |
| `probatio` (via `import probatio`) | provided by HA (`probatio==0.11.4` in core 2026.9.4) | Schema validation | Core moved to it in 2026.9. It has the same API as voluptuous. Do not add it to `requirements`, because core provides it. | HIGH |
| `manifest.json` keys | n/a | Metadata | `domain`, `name`, `version` (SemVer, required for custom integrations), `documentation`, `issue_tracker`, `codeowners`, `config_flow: true`, `integration_type: "service"` (MEDIUM: could be `"hub"`; either passes hassfest), `iot_class: "local_push"`, `dependencies: ["mqtt"]`, `single_config_entry: true`. | HIGH (keys), MEDIUM (`single_config_entry`, `integration_type`) |

### Data / Persistence

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| MQTT retained message on a single "central config" topic | n/a | Cross-instance source of truth | Required by design. The broker is the only shared component. Publish with `retain=True`, `qos=1`. | HIGH |
| MQTT Discovery, **device-based** (`<prefix>/device/<object_id>/config` with `device`, `origin`, `components`) | HA MQTT discovery spec | Creates the `switch` and `select` entities | The docs recommend device discovery for multi-component payloads. It requires `origin.name`. Removal is an empty retained payload, which also removes the device entry. Use the configured `discovery_prefix` (default `homeassistant`), not a hard-coded one. | HIGH |
| `homeassistant.helpers.storage.Store` | HA core | Local cache of the last-seen central config and instance identity (instance UUID) | Lets the instance start and reconcile before the broker delivers the retained message. It is the standard mechanism and needs no DB. | MEDIUM (not re-verified this session, long-standing API) |
| Config entry `data` / `options` / subentries | HA core | Local instance settings (instance ID, opt-in "accept remote actions" flag) and, optionally, locally owned device definitions | Survives restarts and is backed up by HA. | HIGH |
| JSON via `homeassistant.util.json` (`json_loads_object`) and `homeassistant.helpers.json` (`json_dumps`) | HA core (orjson-backed) | Payload (de)serialization | No extra dependency. `json_loads_object` is what the MQTT discovery code itself uses. | MEDIUM-HIGH |

### Infrastructure (repo, CI, release)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| uv | 0.12.19 (latest on PyPI) | Env, lockfile, Python 3.14 provisioning, runs tests and lint | Matches the user's ecosystem convention (uv and Ruff). `uv python install 3.14` sidesteps distro Python lag. | HIGH |
| Ruff | 0.16.x (0.16.9 latest; HA core pins 0.16.8) | Lint and format | Ecosystem standard. Line length 120 per user convention. `target-version = "py314"`. Start from the ludeeus `integration_blueprint` `.ruff.toml` (`select = ["ALL"]` with a short ignore list). | HIGH |
| pytest-homeassistant-custom-component | 0.13.367 (released 2026-09-27; new release almost daily, tracks HA patch releases 1:1) | Test harness: `hass` fixture, `MockConfigEntry`, `mqtt_mock`, `mqtt_mock_entry`, `async_fire_mqtt_message`, `enable_custom_integrations`, `hass_ws_client` | The only maintained way to extract HA core's test plugins for custom components. Verified in the wheel's `plugins.py` and `common.py`. Its version is coupled to HA, so bump it together with HA. | HIGH |
| pytest / pytest-asyncio / pytest-cov / pytest-xdist / syrupy / freezegun | pinned transitively by PHACC (`pytest==9.0.3`, `pytest-asyncio==1.4.0`, `pytest-cov==7.1.0`, ...) | Test tooling | Do not pin these yourself. Set `asyncio_mode = "auto"`. | HIGH |
| `home-assistant/actions/hassfest@master` (pin to commit SHA) | rolling (`master`) | Manifest, services, translations, dependency validation | Official validator. Runs on push, PR and a daily cron. The blueprint pins by SHA with a `# master` comment. | HIGH |
| `hacs/action` | `22.5.0` (pin to SHA `d556e736723344f83838d08488c983a15381059a`, as in the blueprint) | HACS repository validation, `category: integration` | Official. HACS docs suggest `@main` but recommend pinning and using Dependabot. | HIGH |
| actions/checkout | v7.0.1 | CI checkout | Latest release (2026-07-20). Set `persist-credentials: false` and `permissions: {}` at workflow level, as in the blueprint. | HIGH |
| astral-sh/setup-uv | v10.2.0 | Install uv in CI, cache, provision Python 3.14 | Latest release (2026-09-21). Replaces `actions/setup-python` plus pip. | HIGH |
| Dependabot (or Renovate) | n/a | Bump PHACC, Ruff and action SHAs | PHACC and HA move weekly. Manual tracking will drift. | MEDIUM |
| GitHub Releases + SemVer git tags | n/a | HACS versioning | `manifest.json` `version` must match the tag. HACS shows the 5 latest releases. No `zip_release` needed, since the layout is standard `custom_components/<domain>/`. | HIGH |
| Local brand images at `custom_components/<domain>/brand/icon.png` (+ optional `logo.png`, `dark_*`, `@2x`) | HA 2026.3+ | Integration icon | HACS's `brands` validator (verified in `hacs/integration` main) checks this path first. Drop the blueprint's `ignore: brands` and ship the icon. | HIGH |

### Repo Layout (HACS)

- `hacs.json` keys supported per HACS docs: `name` (required), `homeassistant`, `hacs`, `content_in_root`, `zip_release`, `filename`.
- Repo requirements: public, description set, GitHub topics set, README present.
- Custom integrations use `translations/en.json` directly. `strings.json` is core-only.
- Register services in `async_setup`, not in `async_setup_entry`. Hassfest enforces this for the re-trigger service.
- Suggested domain: `mqtt_actions`. This is a naming decision for the user, and it must be settled before the first release because it is baked into entity and unique-ID history.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `homeassistant.helpers.config_validation` (`cv.SCRIPT_SCHEMA`, `cv.slug`, ...) | core | Validate action sequences and payloads | Always, on user input AND on every payload received from the broker. |
| `script.async_validate_actions_config(hass, actions)` | core | Deep-validate action sequences (resolves services and blueprint-style config) | When persisting from the flow and again when ingesting the central config. |
| `homeassistant.helpers.dispatcher` | core | Fan out "central config changed" to the sync manager | Internal signalling. Avoids global state. |
| `entry.runtime_data` with typed `ConfigEntry[RuntimeData]` | core | Hold manager, unsubscribe callbacks and Script objects | Instead of `hass.data[DOMAIN]`. This is the current pattern. |
| `entry.async_on_unload(...)` | core | Register MQTT unsubscribe callbacks | Every `mqtt.async_subscribe` return value goes here. |
| `mqtt.async_wait_for_mqtt_client(hass)` | core | Wait for the MQTT client before subscribing | First call in `async_setup_entry`. If `False`, raise `ConfigEntryNotReady`. |
| `mypy` / `pyright` | mypy 2.3.1 | Static typing | Optional. Add after the first phase if wanted; not needed to pass hassfest or HACS. |
| codecov/codecov-action | v7.1.1 | Coverage upload | Optional. |

### MQTT API Shapes (verified in core 2026.9.4)

# Setup

# Subscribe; the return value is the unsubscribe callback. Retained messages arrive right after subscribing.

# Publish (raises HomeAssistantError if the MQTT entry is disabled or unavailable)

# Remove a retained discovery or config topic

### Action Execution Shape

# On unload or reconfigure: await runner.async_stop()

### Device Model Note (for roadmap)

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| MQTT client | HA `mqtt` integration API | Own `paho-mqtt` / `aiomqtt` connection | Second connection, duplicate credentials and TLS config, and no `mqtt_mock` for tests. It also bypasses the user's broker settings and birth/will handling. |
| Entity creation | MQTT Discovery (device-based) | Native `switch` / `select` platforms in the integration | Native platforms would be simpler locally, but the project requirement is Discovery. Discovery also makes entities visible to non-HA consumers. Revisit only if Discovery latency or ghost-entity problems dominate. |
| Discovery format | Device-based (`homeassistant/device/<id>/config`) | Per-component topics | Per-component topics create more retained messages and a harder cleanup story. Device discovery removes the whole device with one empty payload. |
| Action mechanism | `helpers.script.Script` on inline sequences | Call `script.turn_on` on named scripts | Named scripts are out of scope and non-portable between instances. |
| Action mechanism | `Script` helper | Calling `hass.services.async_call` per step by hand | Loses templating, `choose`, `delay`, `parallel`, `continue_on_error`, and traces. Reimplements a fragile subset. |
| Validation import | `import probatio` | `import voluptuous as vol` | It still works through the alias, but it is legacy for 2026.9+. On an older floor (< 2026.9), `import probatio` would fail. |
| Env and deps | uv + `pyproject.toml` `[dependency-groups]` | pip + `requirements*.txt` (blueprint style), Poetry | uv is the user's convention and gives a lockfile and Python provisioning. Blueprint uses pip only because it is a template. |
| Lint and format | Ruff only | black + isort + flake8 + pylint | Ruff replaces them. HA core itself only uses Ruff for format and lint. |
| Test harness | PHACC | Hand-rolled `hass` fixtures, or `pytest-homeassistant` forks | Unmaintained or unsupported. PHACC is auto-extracted from core each release. |
| CI Python setup | `astral-sh/setup-uv` | `actions/setup-python` (v7.0.0 exists) + pip | Both work. uv unifies local and CI, and `setup-python` needs a separate pip cache config. |
| HACS action ref | Pin SHA of `22.5.0` | `hacs/action@main` | `@main` (last commit 2026-06-08) is what the docs show, but pinning is what HACS itself recommends. |
| Peer state | Retained topic per data type | Publishing a full config on every change without retain | Retain is the requirement. New instances must receive the config on subscribe. |

## Explicit "Do Not Use" List

- **Do not** add `homeassistant`, `pytest`, `pytest-asyncio` or `voluptuous` to dev deps beyond PHACC. PHACC pins them, and duplicates cause resolver failures every week.
- **Do not** add `paho-mqtt` or `aiomqtt` to `manifest.json` `requirements`. Also do not rely on `after_dependencies` for mqtt: use `dependencies` so MQTT is loaded first.
- **Do not** use `hass.data[DOMAIN]` for per-entry state. Use `entry.runtime_data`.
- **Do not** use `strings.json` (core only). Use `translations/en.json` and `translations/de.json`.
- **Do not** use YAML configuration (`configuration.yaml` schema). Config Flow only. Do not use `async_setup_platform`.
- **Do not** add `setup.py`, `setup.cfg` or Poetry.
- **Do not** use `device_id` targets in shipped examples or defaults. Device IDs differ per instance, which breaks cross-instance sync. Prefer `entity_id` and areas/labels, and warn users in docs.
- **Do not** pin `hacs/action@main` or `hassfest@master` unpinned in a security-sensitive repo. Pin SHAs and let Dependabot bump them.
- **Do not** execute a received action sequence without (a) the local opt-in flag and (b) schema validation. This is a stack rule, not just a design rule. The security constraint in PROJECT.md applies to `Script` execution specifically.

## Installation

# One-time setup (uv provisions Python 3.14)

# pyproject.toml gets the dev group below, then:

# Dev workflow

# pyproject.toml (minimal; there are no runtime deps)

# tests/conftest.py

# .github/workflows/validate.yml (essentials; SHAs to be pinned when the repo is created)

## Version Watch-list (things that will move during development)

| Item | Current | Why it matters |
|------|---------|----------------|
| PHACC / HA | 0.13.367 / 2026.9.4 | Updates roughly daily and coupled to each HA patch. Use Dependabot with a weekly grouped update for PHACC. |
| Ruff | 0.16.9 (core on 0.16.8) | Ruff 0.16 was a recent major-ish bump for core. Core's config notes rule follow-ups "after ruff 0.16 bump". Expect new rule triggers on bumps. |
| Probatio | 0.11.4 in core (0.12.3 on PyPI) | Core owns the version. Do not pin it yourself. |
| hassfest rules | rolling `master` | Check the daily run. New rules can fail the badge without any code change. |
| HA 2026.10 (upcoming) | not released | Bump `hacs.json` `homeassistant` only when a needed API appears. |

## Confidence Summary

| Recommendation | Confidence | Basis |
|----------------|------------|-------|
| Python 3.14, HA 2026.9.x, PHACC 0.13.367 | HIGH | PyPI JSON (`requires_python`, `requires_dist`); HA `pyproject.toml` at dev/2026.9.4 |
| MQTT API (`async_publish`, `async_subscribe`, `async_wait_for_mqtt_client`) and `dependencies: ["mqtt"]` | HIGH | HA source at tag 2026.9.4; developers.home-assistant.io manifest docs |
| Device-based MQTT discovery | HIGH | Official MQTT integration docs; `discovery.py` handles device payloads |
| `Script` + `cv.SCRIPT_SCHEMA` + `ActionSelector` unvalidated output | HIGH | HA source (`helpers/script.py`, `helpers/selector.py`, `config_validation.py`) at 2026.9.4 |
| probatio migration | HIGH | HA source (`homeassistant/__init__.py` at 2026.9.4) plus the developers-docs PR #3361 |
| HACS action, hassfest action, hacs.json keys, brand path | HIGH | hacs.xyz docs; `hacs/integration` `validate/brands.py`; ludeeus `integration_blueprint` (updated 2026-07-19) |
| Ruff 0.16.x, uv 0.12.x, action versions | HIGH | PyPI and GitHub releases API |
| Subentries as the device store; `single_config_entry`; `integration_type` | MEDIUM | Design judgment; needs phase-level research |
| `Store` for the local cache | MEDIUM | Standard HA helper, not re-verified this session |

## Sources

- PyPI JSON: pytest-homeassistant-custom-component 0.13.367 (2026-09-27, wheel METADATA and `plugins.py`); homeassistant 2026.9.4 (2026-09-27); ruff 0.16.9; uv 0.12.19; pytest 9.1.1 (PHACC pins 9.0.3)
- HA core at tag 2026.9.4: `pyproject.toml`, `requirements.txt`, `homeassistant/__init__.py`, `helpers/script.py`, `helpers/selector.py`, `helpers/config_validation.py`, `config_entries.py`, `components/mqtt/{__init__,client,util,discovery}.py`, `components/mqtt/manifest.json`; `requirements_test.txt` and `requirements_test_pre_commit.txt` on dev
- https://developers.home-assistant.io/docs/creating_integration_manifest (dependencies, version, integration_type, single_config_entry)
- https://developers.home-assistant.io/docs/config_entries_config_flow_handler/ (subentries, reconfigure)
- https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/ (local brand images, HA 2026.3)
- https://github.com/home-assistant/developers.home-assistant/pull/3361 (probatio docs migration)
- https://www.home-assistant.io/integrations/mqtt/ (device discovery, removal, birth message, retention)
- https://www.hacs.xyz/docs/publish/action/ and https://www.hacs.xyz/docs/publish/integration/ and https://www.hacs.xyz/docs/publish/start/ (HACS action, requirements, hacs.json)
- https://github.com/hacs/integration/blob/main/custom_components/hacs/validate/brands.py (brand validator)
- https://github.com/ludeeus/integration_blueprint (validate.yml, lint.yml, `.ruff.toml`, hacs.json; last commit 2026-07-19)
- GitHub releases API: actions/checkout v7.0.1, astral-sh/setup-uv v10.2.0, hacs/action 22.5.0, codecov/codecov-action v7.1.1

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
