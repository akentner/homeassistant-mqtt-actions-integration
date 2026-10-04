# Phase 8: Real-Instance Verification - Research

**Researched:** 2026-10-04
**Domain:** Manual and semi-automated verification of a Home Assistant custom integration on real HA containers, a real Mosquitto broker and real hosts. There is no product code in this phase.
**Confidence:** MEDIUM-HIGH (environment facts and code behavior were read or probed this session; frontend behavior and the API surface used for automation are partly `[ASSUMED]`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** All checks run in `~/ha-test`: `ha-a` ("Test HA One", 8123), `ha-b` ("Test HA Two", 8124), Mosquitto `mosq`,
  and the v0.1.0 component from `~/ha-test/v010` as the straggler for UAT-01. The live production broker and hosts are not touched.
- **D-02:** Exception: the two items that need a real host run there. Phase 1 #1 (HACS client install, add and remove only,
  no device created) runs on a production host; Phase 1 #6 (core version of hassio-n2plus) the owner reads in Settings > About.
- **D-03:** The build under test is the current HEAD of the phase branch, mounted live. The SHA is recorded in the evidence.
  A later code change makes affected checks stale and they are re-run.
- **D-04:** Claude automates everything that does not need eyes or hands: broker publishes (`mosquitto_pub`/`mosquitto_sub`),
  container restarts, log and topic evaluation, and frontend steps via the browser MCP where it works. The owner performs only
  steps that need a human (real frontend rendering and DE/EN review, HACS client, anything the browser tooling cannot do).
- **D-05:** One `08-UAT.md` with one row per check (UAT-01 to UAT-04 plus the ten items): pass/fail, date, build SHA, evidence
  reference. Logs, topic dumps and screenshots go in `.planning/phases/08-real-instance-verification/08-evidence/`.
- **D-06:** After the run, `/gsd-verify-work` and the verifier refresh the Phase 1 to 3 reports (archived under
  `.planning/milestones/v1.0-phases/`) to `passed` where all their items passed.
- **D-07:** All ten Phase 1 to 3 items are in scope (ROADMAP success criterion 6), grouped by setup so each instance state is
  built once. No item is waived by default; an owner override is only possible under the owner's own name.
- **D-08:** A failed check is recorded as a gap and the remaining checks continue. Fixes go into a follow-up gap plan or phase,
  not into Phase 8 (consistent with "no code changes planned").

### Claude's Discretion

Grouping and order of checks per instance setup, helper scripts for the automated steps, and the evidence file naming.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UAT-01 | A v0.1.0 instance next to a native instance keeps running its actions, shows no entities for migrated devices and raises no error | Needs a third container `ha-c` with the byte-identical v0.1.0 component, its own MQTT user and an ACL block (see "Setting up ha-c"). v0.1.0 ignores unknown document keys; v0.1.0 still creates a companion mode select for every mirror, so the pass criterion must be worded precisely (Pitfall 6, Open Question 3). |
| UAT-02 | Re-published retained legacy Discovery plus two restarts yield no `_2` duplicates (proves MIG-05) | Publish the legacy payload while the container is stopped, then start; the catch is a one-shot 5 s timer armed only at start (Pitfall 3). Run before UAT-04 so the registry baseline is clean. Restart is mandatory because the containers still run pre-Phase-6 code (Pitfall 1). |
| UAT-03 | A command on one of two real instances runs the actions exactly once on every approved instance; an unknown payload is ignored and the state stays unchanged | Existing fixture: switch "Lampe Test" owned by ha-a, approved on ha-b. Count action runs by log markers per instance; publish the unknown payload live (not retained). The unknown-payload WARNING text is known (Code Examples). |
| UAT-04 | The Discovery export has `enabled_by_default` false and no buttons, the core prefix yields only disabled duplicates, and switching it off clears the topics | The test ACL has no row for the export prefix, so the owner's export publish is silently denied (Pitfall 2). The restart catch removes export duplicates on the core prefix (Pitfall 4): observe before any restart. |
</phase_requirements>

## Summary

Phase 8 is a manual verification phase for a build that already exists. The work is environment preparation, scripted observation and evidence recording, plus the frontend checks only a human (or the browser MCP) can make. The test bench in `~/ha-test` is mostly in place: `mosq` (Mosquitto 2.1.2, `allow_anonymous false`, `acl_file`, `persistence false`), `ha-a` and `ha-b` (HA 2026.9.4, host network, component bind-mounted read-only from the repo working tree). Four preparation gaps decide whether the phase works at all: (1) both HA containers were started 2026-10-03 20:54, before the Phase 6 fixes, so they run old code until restarted; (2) the Mosquitto ACL has no row for the export prefix `mqtt_actions_export`, so UAT-04 would fail silently; (3) there is no third instance for UAT-01 (needs a container, an MQTT user, an ACL block with its instance id, a free port 8125); (4) nothing gives Claude API access to the test instances (no token), so the API-driven steps need an owner-provided long-lived token or a scripted onboarding of a fresh instance.

The four UAT checks have clear, mostly scriptable pass criteria: registry files are host-readable (`~/ha-test/{a,b}/.storage/core.entity_registry`), retained broker topics are readable with `mosquitto_sub`, and action runs can be counted from log markers. The ten Phase 1 to 3 items are frontend or real-host checks; they are grouped into one frontend session on ha-a/ha-b plus two production-host items. Two behaviors will confuse an unprepared tester: the replay catch runs only once, 5 s after a start (live re-publishes leave `_2` entries until the next restart), and the same catch also removes the disabled duplicates that a core-prefix export creates, but only at the next start.

**Primary recommendation:** Plan five waves: preflight (SHA pin, backup, ACL, restart at HEAD, tokens, ha-c), scripted group on ha-a/ha-b in the order UAT-02, UAT-03, retained-vs-live chain, UAT-04; UAT-01 on ha-c before any destructive frontend work; one frontend session (owner plus browser MCP) with `ha-c` stopped; production items last; then consolidate `08-UAT.md` and re-run the verifier for Phases 1 to 3.

## Project Constraints (from CLAUDE.md)

Extracted from `/home/akentner/CLAUDE.md`, `/home/akentner/Projects/CLAUDE.md` and `./.claude/CLAUDE.md`:

- Work through GSD commands; no direct repo edits outside a GSD workflow. This phase writes only `.planning/` files; no `custom_components/` or `tests/` edits (CONTEXT D-08).
- Chat with the user in German; code, comments, commits and planning files in English.
- Fish is the primary shell, but helper scripts run through the Bash tool: write them as bash scripts (`#!/usr/bin/env bash`). Fish rejects `==` in `echo` arguments and bash-isms.
- Prefer `uv run` over `pip install`; no global pip pollution. `aiohttp` is already in the repo `.venv`, so a WebSocket helper needs no new package.
- Prefer `ha-ws` over curling the HA API. `ha-ws` reads `HA_URL` and `HA_TOKEN` from the environment [VERIFIED: `~/.local/bin/ha-ws` lines 112-113, `self.ha_url = os.environ.get('HA_URL', '')...`, `self.ha_token = os.environ.get('HA_TOKEN', '')`]. Without an inline override it targets PRODUCTION. Every call against `~/ha-test` must set both variables inline (Pitfall 9).
- Secrets live in Bitwarden; no plaintext credentials in files. Evidence files in `.planning/` are committed to a public repo: no tokens, no `.storage/auth`, no `core.config_entries` dumps (they contain broker passwords).
- The live broker has no auth or ACL on purpose (memory `live-broker-no-auth-acl`): do not raise it as a todo or finding. Phase 8 does not touch it (D-01).
- HA 2026.10 is imminent; the HA image tag is `2026.9`. Do not pull `latest`/`stable` (memory `phase-04-release-state`: a bump to HA 2026.10.0b0 already broke the unit tests once).

## Architectural Responsibility Map

There is no application tier split in this phase. The map assigns each verification capability to the component that can observe it.

| Capability | Primary observer | Secondary | Rationale |
|------------|-----------------|-----------|-----------|
| Retained topics, export payloads, clears | Mosquitto (`mosquitto_sub -F '%t %r %p'`) | — | The broker is the only source of truth for what is retained. |
| Entity and device identity (no `_2`, ids kept) | HA registry files `.storage/core.entity_registry`, `core.device_registry` | WS `config/entity_registry/list` | Host-readable, token-free; flushed on stop and by the integration's own flush. |
| Action execution count | Per-instance log file or `/api/error_log` | Persistent notifications via WS | A log marker per run is countable without a token. |
| Rendering, EN/DE strings, dialogs | Real frontend (owner, browser MCP) | — | No automated tier can see it; this is why the ten items are human. |
| Version/code identity of the build | `git rev-parse HEAD` plus `sha256sum` inside the container | HA log after restart | The container only sees the mounted working tree. |
| HACS install, core version of a real host | Owner on a production host | — | D-02. |

## Standard Stack

No product libraries. The "stack" is the existing test bench and tools.

### Core

| Item | Version | Purpose | Provenance |
|------|---------|---------|------------|
| Mosquitto container `mosq` | 2.1.2, image `docker.io/library/eclipse-mosquitto:2` | Test broker with ACL | [VERIFIED: `podman exec mosq mosquitto -h` printed `mosquitto version 2.1.2`] |
| HA containers `ha-a`, `ha-b` | HA 2026.9.4, image `ghcr.io/home-assistant/home-assistant:2026.9` | Instances under test | [VERIFIED: `.HA_VERSION` printed `2026.9.4`; `podman inspect` image name] |
| podman | 6.1.3 (invoked as `docker` emulation) | Container control | [VERIFIED: `podman --version`] |
| `mosquitto_pub`, `mosquitto_sub`, `mosquitto_passwd` | 2.1.2 client tools on host | Scripted broker steps | [VERIFIED: `which` found `/usr/bin/mosquitto_pub`, `/usr/bin/mosquitto_sub`, `/usr/bin/mosquitto_passwd`] |
| `jq` 1.8.2, `curl` 8.22, `sqlite3`, `python3` 3.14.7, `uv` 0.12.7, `gh` 2.102.0 | host | Evaluation and helper scripts | [VERIFIED: `--version` output] |
| `~/ha-test/v010/custom_components/mqtt_actions` | v0.1.0 | Straggler build | [VERIFIED: manifest `"version": "0.1.0"`; `git show v0.1.0:custom_components/mqtt_actions/<file> | diff` printed no difference for any of its `.py` files] |
| `/home/akentner/.local/bin/ha-ws` | script | WS client (`raw <type>`), usable against test instances with inline `HA_URL`/`HA_TOKEN` | [VERIFIED: usage text lists `raw <type> [key=value...]`] |
| Browser MCP (chrome-devtools) | n/a | Frontend steps | [ASSUMED] availability in the executing session was not verifiable from the researcher session; Phase 3 UAT used it against a real HA frontend (`03-UAT.md` test 1: "automated (chrome-devtools against a real HA 2026.9 frontend), confirmed by user") |

### Supporting

| Item | Purpose | When |
|------|---------|------|
| `.venv/bin/python` of the repo (has `aiohttp 3.14.3`, `homeassistant 2026.9.4`) | WS helper, and `custom_components.mqtt_actions.discovery.build_discovery` to build the legacy payload | UAT-02, token-based steps. [VERIFIED: `.venv/lib/python3.14/site-packages` listing] |
| `gsd_run verification status <dir> --pick status` | Reads the status of archived reports | Final wave (D-06) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New container `ha-c` with fresh config | Clone of `~/ha-test/_backup-pre-phase5-uat-20261003-181937/b` (a pre-Phase-5 v0.1.0 state) | The clone brings a ready, logged-in v0.1.0 instance, but its stored instance id, MQTT credentials (`ha_two`) and mirrors of old device ids must be rewritten by hand in `.storage`. Fresh is cleaner; the clone is the fallback if first-start dependency installation (internet) is a problem. |
| Per-instance ACL for ha-c | Wildcard availability write for the `ha_three` user | Wildcard is simpler but hides ACL mistakes; the documented block is per instance id. Use the per-instance block (the instance id is readable from the new config entry). |

**Installation:** none. No package is installed in this phase.

## Package Legitimacy Audit

No external package is installed by this phase. The helper scripts use `bash`, `jq`, `mosquitto_*` and the repo `.venv` (`aiohttp` is already a locked dependency of HA).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                       host ~/ha-test  (podman, --network host)
 owner / Claude
   |  scripts: mosquitto_pub/sub, jq on .storage, log grep, podman stop/start
   |  frontend: owner + browser MCP            token calls: ha-ws (inline HA_URL/HA_TOKEN)
   v
 +--------+   :8123    +--------+   :8124    +--------+   :8125 (new)
 | ha-a   |            | ha-b   |            | ha-c   |  v0.1.0 component (UAT-01 only)
 | native |            | native |            | legacy |
 | owner of 1111...,   | owner of 2222...,   | follower; mode select on companion
 | b6bd...             | e289..,51f2..,53ee..| device, no switch/select/button
 +---+----+            +---+----+            +---+----+
     | MQTT (user ha_one)  | (ha_two)            | (ha_three, new ACL block)
     v                     v                     v
 +-----------------------------------------------------------+
 | mosq 1883: acl_file, password_file, persistence false     |
 | retained: mqtt_actions/v1/devices/<id>/{config,state}     |
 |           mqtt_actions/v1/instances/<id>/availability     |
 |           homeassistant/device/<id>/config   (UAT-02)     |
 |           mqtt_actions_export/device/<id>/config (UAT-04) |
 +-----------------------------------------------------------+
   ^
   | external publisher: user bridge (state topics only) -> UAT-03 unknown payload
 real hosts (production, owner only): HACS install + remove (P1-1), core version (P1-6)
```

### Recommended Evidence Structure

```
.planning/phases/08-real-instance-verification/
├── 08-UAT.md                 # one block per check, format of 03/04/05-UAT.md, plus a summary table
└── 08-evidence/
    ├── 00-preflight/         # sha, backup list, acl diff, mount-integrity hashes, retained snapshot (no secrets)
    ├── uat-01/ ... uat-04/   # topic dumps, registry diffs (jq output), log excerpts, screenshots
    └── p1-1/ ... p3-2/       # one folder per deferred item
~/ha-test/bin/                # helper scripts (outside the repo; paths and local ports)
```

`08-UAT.md` must stay parseable by the GSD UAT tooling: one `### N. name` block per check with `expected:` and a `result:` token from `pending | pass | issue | skipped | blocked`, and a `## Gaps` section. [VERIFIED: `~/.claude/gsd-core/templates/UAT.md` and the parser notes in `bin/lib/uat.cjs` ("A block with no `result:` line at all is not a test row")]. D-05's table (pass/fail, date, SHA, evidence path) is an additional summary table, not a replacement. Use `result: issue` plus a `## Gaps` entry for a failure (D-08).

### Pattern 1: Pin the build, then prove the container runs it

The component is bind-mounted read-only from the repo working tree: `/home/akentner/Projects/homeassistant-mqtt-actions-integration/custom_components/mqtt_actions:/config/custom_components/mqtt_actions:ro` [VERIFIED: `podman inspect ha-a` binds]. Python modules load at start, so "mounted live" does not mean "hot". Before each group: record `git rev-parse HEAD`, assert `git diff --quiet HEAD -- custom_components` and `git status --porcelain custom_components` empty, restart the container, and compare `sha256sum` of one or two files (`manager.py`, `takeover.py`) on the host and via `podman exec`. Do not switch branches while the phase runs: the mount follows the working tree.

### Pattern 2: Group by instance state, destructive last

Recommended order (Claude's discretion area, D-07):

0. **Preflight** (see Wave plan).
1. **Scripted group on ha-a + ha-b (native fleet):** UAT-02, then UAT-03, then P1-5 (retained-versus-live), then UAT-04 with a final restart to clean up.
2. **ha-c group:** UAT-01 (before any frontend step that creates hostile-named devices or re-adds a hub).
3. **Frontend session** (owner plus browser MCP, `ha-c` stopped): P1-2, P1-3, P1-4, P2-1, P2-2, P3-1, P3-2; the hub re-add of P1-2 last.
4. **Production:** P1-1 and P1-6 (owner).
5. **Consolidation:** `08-UAT.md`, gaps, verifier re-run for Phases 1 to 3.

Why this order: UAT-02 needs a clean registry baseline (UAT-04 leaves disabled `mqtt` entries behind until a restart); UAT-04 core-prefix duplicates must be observed before a restart (Pitfall 4); an online legacy `ha-c` would make a freshly re-added, not-yet-native hub wait for a cutover (`native_cutover_waiting`), so `ha-c` is stopped before any hub re-add.

### Anti-Patterns to Avoid

- **Judging a check on the old process.** Running a check without a restart after the SHA was recorded tests pre-Phase-6 code.
- **`podman restart mosq` mid-run.** `persistence false` [VERIFIED: `~/ha-test/mosquitto/mosquitto.conf`] drops every retained message, including the state topics the checks depend on. Use a retained snapshot before, and use an MQTT entry reload for a "broker reconnect" (Pitfall 7).
- **Reading the registry while HA runs and calling it final.** HA writes the registry with a delay. Stop the container (or wait for the integration's own flush after the catch) before reading the file for evidence.
- **Calling `ha-ws` without inline environment.** It would act on production.
- **Fixing a failure in Phase 8.** D-08: record the gap, continue.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Legacy Discovery payload for UAT-02 | A hand-written JSON | `custom_components.mqtt_actions.discovery.build_discovery(...)` from the repo `.venv` | `build_discovery` is unchanged since v0.1.0 [VERIFIED: `git diff v0.1.0 HEAD -- custom_components/mqtt_actions/discovery.py` only adds `build_export`, `async_publish_export`, `async_clear_export`, `async_publish_migrate`, `discovery_prefix`], so the payload is byte-faithful to what v0.1.0 published, including unique ids `<id>_test_<key>`. |
| Export payload for UAT-04 | A hand-written JSON | Read the retained payload the owner actually publishes (`mosquitto_sub -F`) | The check is about what the integration publishes. |
| Counting action runs | Reading the UI | A log marker per run (`system_log.write`, level `warning`) and `grep -c` | Countable and token-free; default log level is WARNING (Pitfall 8). |
| API access to test instances | Parsing `.storage/auth` | An owner-created long-lived token, or a scripted onboarding of a fresh `ha-c` | Reading credential stores is off limits (a read of `.storage/auth` was blocked during this research). |
| Registry evaluation | Screenshots of entity lists | `jq` over `core.entity_registry` and `core.device_registry` | Exact, diffable, host-readable. |
| UAT bookkeeping | A new format | `~/.claude/gsd-core/templates/UAT.md` shape | `gsd-audit-uat` and the verifier parse it. |

**Key insight:** Every check here is cheap to run and expensive to interpret. Pre-written, pass/fail-assertive scripts (with the expected value in the script) prevent after-the-fact rationalizing, and they make D-03 "re-run when stale" a one-command repeat.

## Environment Findings (what exists now)

All `[VERIFIED]` entries come from commands or file reads of this session.

### Containers and mounts

- `mosq`: Up, binds `~/ha-test/mosquitto:/mosquitto/config:ro` plus two anonymous volumes; host network [VERIFIED: `podman inspect mosq`].
- `ha-a`: Up, started `2026-10-03 20:54:31 +0200`; binds `/home/akentner/ha-test/a:/config` and the repo component read-only; host network; entrypoint `/init`; env `TZ=Europe/Berlin`; not privileged; restart policy `no` [VERIFIED: `podman inspect`]. `ha-b` is identical with `~/ha-test/b` and `http: server_port: 8124` in its `configuration.yaml`.
- Phase 6 landed after that start: the diff `v1.0.0..HEAD` for the component touches `const.py`, `document.py`, `manager.py`, `takeover.py` [VERIFIED: `git diff --stat v1.0.0 HEAD -- custom_components hacs.json README.md` listed those four plus README]. Both containers must be restarted.
- Ports 8123, 8124, 1883 are listening; 8125 is free [VERIFIED: `ss -ltnp`]. Memory: 15 GiB total, about 4 GiB available; disk 42 GB free.
- Image `ghcr.io/home-assistant/home-assistant:2026.9` is present locally (id `cd74b0e02cee`, created 2026-09-27) [VERIFIED: `podman images`].
- No `chromium`/`google-chrome` binary on PATH (`which` found none); the browser MCP brings its own browser or does not exist in the executing session [ASSUMED].

### Instances and fixtures

- ha-a hub: `instance_id` `3851f34f-fa67-4f3c-bba0-122465013c3d`, name `Test HA One`; hub options `{'delete_devices_on_remove': False, 'discovery_export': False, 'export_prefix': 'mqtt_actions_export'}` [VERIFIED: `core.config_entries`].
- ha-b hub: `instance_id` `a09499e4-5674-48d5-b3d6-4860d5226fcb`, name `Test HA Two` [VERIFIED: `core.config_entries`].
- Owned by ha-a: switch `11111111-aaaa-4aaa-8aaa-000000000001` "Lampe Test" with `on_change_to_on` `persistent_notification.create` message `lampe on` and `on_change_to_off` message `lampe off`; select `b6bd2c0e-6d81-49ea-8025-4bd087bd718a` "Bar Select" [VERIFIED: ha-b stored mirror documents]. Approved on ha-b: `11111111-...0001` only [VERIFIED: ha-b `mqtt_actions.state` `approvals`].
- Owned by ha-b: select `22222222-bbbb-4bbb-8bbb-000000000002` "Modus Test" (options `one`, `two`, no actions), switch `e2890912-ec2c-4588-a590-0f2555297fc9` "Baz", switch `51f224e0-fa1d-4cf0-b92e-b02e5b637c40` "dfsfasdf", select `53ee0f1e-5f4d-4e9e-9893-1e698270a960` "dfgfdgd" (no actions) [VERIFIED: ha-a stored mirrors].
- All config documents carry `"entities":"native"` [VERIFIED: retained config dump]. ha-a's entity registry holds 0 entries with platform `mqtt`, 4 `deleted_entities`, and all device entities under platform `mqtt_actions` [VERIFIED: `jq` over `core.entity_registry`]. This is the clean baseline UAT-02 needs.
- Log noise on both instances is Bluetooth (`habluetooth.scanner`, 236 lines) and Chromecast; no `mqtt_actions` ERROR lines. Default log level is WARNING: the logs contain 0 `INFO` lines [VERIFIED: grep counts]. An error filter for "raises no error" must therefore be `custom_components.mqtt_actions` plus `homeassistant.components.mqtt`, not the whole log.
- HA keeps one rotated log (`home-assistant.log.1`) and rotates at every start: capture the log into the evidence folder before the next restart.

### Broker ACL (current test file)

Verbatim from `~/ha-test/mosquitto/acl` [VERIFIED: file read this session]:

```
user ha_one
topic readwrite mqtt_actions/v1/devices/+/retrigger
topic readwrite mqtt_actions/v1/instances/+/acks
topic readwrite mqtt_actions/v1/instances/+/heartbeat
topic readwrite mqtt_actions/v1/devices/+/config
topic readwrite mqtt_actions/v1/devices/+/state
topic readwrite mqtt_actions/v1/devices/+/test
topic readwrite homeassistant/#
topic read mqtt_actions/v1/instances/+/availability
topic write mqtt_actions/v1/instances/3851f34f-fa67-4f3c-bba0-122465013c3d/availability

user ha_two
... (same lines; availability write for a09499e4-5674-48d5-b3d6-4860d5226fcb)

user bridge
topic readwrite mqtt_actions/v1/devices/+/state
```

Consequences: (a) there is no line for `mqtt_actions_export/#`, so the export publish of UAT-04 is denied and Mosquitto gives no visible error; (b) there is no user for `ha-c`; (c) `bridge` can read and write state topics only (it was used successfully this session to read retained state; its password is the test one, see the HA MQTT config of the test instances, do not copy it into evidence); (d) the ACL is broader than `docs/broker-acl.md` (readwrite instead of read/write per instance id), which is fine for a test bench but means it is not evidence for the documented ACL block.
`docs/broker-acl.md` documents that a denied publish is not reported: "A broker may acknowledge a denied QoS 1 publish like an accepted one, and Home Assistant shows nothing in its log. When you verify your ACL, read the retained state back with a second client." [VERIFIED: `docs/broker-acl.md`]. Mosquitto reloads `acl_file` and `password_file` on SIGHUP ("Reloaded on reload signal. The currently loaded ACLs will be freed and reloaded." [CITED: `man mosquitto.conf`, local man page lines 171-172]): `podman kill --signal HUP mosq`. The config directory is mounted read-only inside the container but the host files are editable; use `mosquitto_passwd -b ~/ha-test/mosquitto/passwd ha_three <pw>` on the host [VERIFIED: tool present].

### Retained topics at research time

`mqtt_actions/v1/devices/<id>/config` for the six devices, `.../state` for four of them (`1111...` = `ON`, `2222...` = `one`, `e289...` = `ON`, `53ee...` = `tzzuu`), and the availability topics of both instances (`online`) [VERIFIED: read-only `mosquitto_sub` probe]. No retained `homeassistant/device/...` topic exists now.

## Setting up ha-c (UAT-01)

1. Directory `~/ha-test/c` with `configuration.yaml`: `default_config:` and `http:` `server_port: 8125`. First start installs dependencies for `default_config` and needs internet; ha-a and ha-b have a `deps` folder from that step [VERIFIED: directory listing]. If that is unwanted, copy only `deps` from `~/ha-test/b`.
2. Run (host network, as the others): image `ghcr.io/home-assistant/home-assistant:2026.9`, `-v ~/ha-test/c:/config`, `-v ~/ha-test/v010/custom_components/mqtt_actions:/config/custom_components/mqtt_actions:ro`, `-e TZ=Europe/Berlin`, `--name ha-c`. [ASSUMED: mirrors the flags read from `podman inspect ha-b`; the original run command is not stored anywhere in the repo.]
3. Onboard and obtain a token. Either scripted onboarding (`POST /api/onboarding/users`, then the auth login flow) which also gives Claude a token for this instance only, or the owner does it in the browser [ASSUMED: standard HA onboarding API, not verified this session].
4. Create the MQTT config entry (broker `localhost:1883`, user `ha_three`) after adding the user to `passwd` and an ACL block (copy the `ha_two` block, replace the availability write line). Keep `protocol` 5 like the others.
5. Add MQTT Actions through the config flow. Read the generated `instance_id` from `~/ha-test/c/.storage/core.config_entries` (non-secret field `instance_id` in the `mqtt_actions` entry data), put it into the ACL block, SIGHUP the broker, then reload the entry or restart `ha-c`. Skipping this step makes the straggler's availability publish silently denied.
6. The mirrors of ha-a and ha-b appear on ha-c; approve "Lampe Test" in Repairs (frontend or token call). Then run the UAT-01 steps.
7. Stop `ha-c` when UAT-01 is done (Pattern 2).

The v0.1.0 follower handles native documents: "unknown extra keys are ignored and never hashed" [VERIFIED: `~/ha-test/v010/custom_components/mqtt_actions/document.py:387`, docstring of the parser]. v0.1.0 creates "one per owned or mirrored device on its companion device" mode select [VERIFIED: `v010/select.py:1`, module docstring `"""The mode selects: one per owned or mirrored device on its companion device, one for the instance (D-13, D-14)."""`].

## Check Procedures

Pass criteria are written so they can be asserted by a script. Expected values come from the code read this session; `[ASSUMED]` marks behavior not observed.

### UAT-02 (do first; proves MIG-05)

1. Preconditions: ha-a restarted at the pinned SHA; registry baseline saved (`jq` filter for `platform=="mqtt"` returns nothing; list of `mqtt_actions` entity ids, registry `id`s and device ids saved).
2. `podman stop ha-a`. Build the legacy payload for the device with `build_discovery(spec=..., base_topic="mqtt_actions", instance_id=<ha-a id>, sw_version="0.1.0")` and publish it retained, QoS 1, on `homeassistant/device/<device id>/config` as user `ha_one`. Do it for `11111111-...0001` (switch with buttons) and `b6bd2c0e-...` (select). Read the topics back with a second client (ACL silence).
3. `podman start ha-a`. Wait until HA answers, then at least 10 s (quiet period `REPLAY_QUIET_SECONDS = 5.0` [VERIFIED: `takeover.py:41`]) plus margin. Stop the container again (flushes the registry) and evaluate: no entry with platform `mqtt` for these unique ids, no entity id ending `_2`, the saved native entity ids, registry ids and device ids unchanged, no `mqtt` device with identifier `mqtt_actions_<id>`.
4. Record whether the retained legacy topic still exists. The catch removes loaded twins and "core MQTT itself publishes an empty retained discovery for a loaded entity that goes" [VERIFIED: `takeover.py` docstring of `remove_replay_twins`, lines 195-197], so the topic may be gone after the first start. Re-publish while stopped, then start for restart 2 and evaluate again.
5. Repeat on ha-b (its mirrors are native) for at least one device. Optional variant: publish live while running and show the duplicates stay until the next start (documents the WR-03 limit, not a fail).
6. Enable INFO for `custom_components.mqtt_actions` (a `logger:` block in the test instance `configuration.yaml`; [ASSUMED] that `logger` is active with `default_config`) to capture `Removed %d duplicate entities that a replayed legacy discovery created` [VERIFIED: `takeover.py:219`]; the registry evidence is the proof either way.

### UAT-03

1. Preconditions: both instances restarted at SHA; ha-b approval for `11111111-...0001` present; `Lampe Test` actions use `persistent_notification.create` (existing) or a new marker device whose actions are `system_log.write` with `level: warning` and a unique message. `system_log.write` is not denied for broker-received actions (only `system_log.clear` is in `DENIED_SERVICES` [VERIFIED: `const.py` denylist: `"system_log.clear"`]).
2. Command from ha-a (REST `POST /api/services/switch/turn_on` with token, or UI) and, separately, from ha-b on the mirror switch (needs the owner online, no approval, per README). Count per instance: exactly 1 marker after the change; wait 60 s and count again (no late echo or replay run). Expected: both ha-a and ha-b run once.
3. Unknown payload: publish `banana` as user `bridge`, **not retained**, on `mqtt_actions/v1/devices/<id>/state`. Expect on both instances the WARNING `Ignoring unknown payload ... for device ...` [VERIFIED: `manager.py:2531`, `LOGGER.warning("Ignoring unknown payload %s for device %s", shown(payload), device.name)`], entity state unchanged, marker count unchanged, `last_acted` unchanged. A retained unknown payload overwrites the broker's retained state with garbage; if used at all, restore the previous valid value afterwards (a repeat of the baseline value acts on nothing since `value != last_acted` is false [VERIFIED: `state.py` `decide`]).
4. Evidence: log excerpts per instance with timestamps, the `mosquitto_sub -F '%t %r %p'` capture of the state topic across the sequence, entity states before and after.

### UAT-04 (do last of the scripted group)

1. Add the ACL row first: `topic readwrite mqtt_actions_export/#` for `ha_one` (and `ha_two` if used there), SIGHUP the broker.
2. Turn the export on in the hub options of ha-a (options flow; keys `discovery_export` and `export_prefix`, default prefix `mqtt_actions_export` [VERIFIED: `const.py:18-20`: `CONF_DISCOVERY_EXPORT: Final = "discovery_export"`, `CONF_EXPORT_PREFIX: Final = "export_prefix"`, `DEFAULT_EXPORT_PREFIX: Final = "mqtt_actions_export"`]). Read retained `mqtt_actions_export/device/<id>/config` for every owned native device (`11111111-...0001`, `b6bd2c0e-...`). Assert with `jq`: every component has `enabled_by_default == false`; component keys are only `switch` or `select`; no key starting `test_`; no `button` anywhere; no `/test` topic in the payload [VERIFIED against the builder: `build_export` sets `component["enabled_by_default"] = False` and one component only, `discovery.py:140-159`; test `test_build_export_has_one_component_no_buttons_and_is_disabled_by_default`]. Nothing may appear on `homeassistant/device/<id>/config`.
3. Set the export prefix to `homeassistant`. Right after the publish (and before any restart) the registry must show for each exported device an entry with platform `mqtt`, unique id equal to the device id, `disabled_by == "integration"`, next to the enabled native entity; no enabled `mqtt` entity. [VERIFIED by test: `test_the_export_on_the_core_prefix_creates_a_disabled_duplicate`.] Do it on ha-b too (core MQTT listens there as well).
4. Switch the export off: every export topic (old prefix and the `homeassistant` one) reads back empty (clear = empty retained payload [VERIFIED: `async_clear_export` publishes `""` retained]); registry leftovers of the disabled duplicates may remain; `mosquitto_sub` with a short `-W` returns no retained message for them.
5. Restart ha-a and ha-b once afterwards: the catch removes leftover `mqtt` twins (Pitfall 4). Record it as an observation, not a failure.

### UAT-01 (ha-c)

Pre: native fleet running at the pinned SHA, `ha-c` set up and approved (Setting up ha-c). Pass criteria, all asserted:

1. **Keeps running its actions:** a state change of `11111111-...0001` (from ha-a or the bridge user) produces exactly one action run on ha-c (marker or notification), as on ha-a and ha-b.
2. **No entities for migrated devices:** ha-c's entity registry has no entry with platform `mqtt` and none with a unique id equal to or starting with `<device id>_test_`, and no switch/select/button entity for the mirrored devices. The mode selects (platform `mqtt_actions`, unique id `<device id>_mode`) that v0.1.0 creates on companion devices are expected (Pitfall 6) and are recorded, not counted as failures (see Open Question 3).
3. **Raises no error:** no `custom_components.mqtt_actions` or `homeassistant.components.mqtt` line at ERROR or CRITICAL in ha-c's log; no Repairs issue other than the approval request `approval_required` (check `repairs/list_issues` or the Repairs page); no change in ha-a/ha-b logs caused by ha-c's arrival; ha-a and ha-b still run their own actions.
4. Evidence: `ha-c` registry excerpt, log, issue list, broker availability and heartbeat of ha-c's instance id, retained topics unchanged (no new `homeassistant/device/...` topic).

### Ten deferred items (frontend and production)

| Item | Setup | Mechanism | Notes |
|------|-------|-----------|-------|
| P1-1 HACS install | production host (owner) | custom repo, Download, restart, add MQTT Actions, second add aborts, icon, then remove integration and repository | HACS downloads the newest release by default [CITED: hacs.xyz/docs/use/repositories/dashboard], i.e. v1.0.0, not HEAD. Differences `v1.0.0..HEAD` are code only (Phase 6); `hacs.json`, manifest and brand files are unchanged [VERIFIED: diff stat lists only `const.py`, `document.py`, `manager.py`, `takeover.py`, README]. Record the HACS-reported version and the tag SHA `d0f660cb2422c7688d22a674cf54f955a8c26c7f` [VERIFIED: `git rev-parse v1.0.0`] as the build identity. Ask first whether the host already runs the integration (Open Question 2). |
| P1-2 EN/DE strings | ha-a/ha-b, user language switched in the profile | hub flow, Add switch device dialog, Repairs text, in both languages | The hub flow appears once: abort it in one language, finish in the other. Do it at the end of the frontend session by removing and re-adding the hub on ha-b (ha-c stopped). |
| P1-3 action editor, banners | ha-a | invalid YAML action; literal `device_id` submitted twice (warns, saves on resubmit) | Browser MCP can drive it; the owner judges rendering. |
| P1-4 Repairs dialog of failing action | ha-a | owned switch whose action fails, toggle, open Settings > Repairs | Unknown service names are accepted by the flows [VERIFIED: STATE decision "Deep validation does not check that a service exists"], so an unknown service makes a failing action. |
| P1-5 retained-versus-live chain | ha-a + ha-b, scripted | toggle in UI, full HA restart, MQTT entry reload (reconnect with replay), no action run for replayed state | Use the marker device. Do not restart `mosq` (Pitfall 7). |
| P1-6 core version of hassio-n2plus | owner | Settings > About, expect 2026.9.0 or newer | D-02 assigns it to the owner. SSH access exists per `/home/akentner/CLAUDE.md`, but D-02 says the owner reads it. |
| P2-1 select subentry flow | ha-a | add select device, three options, Done after two, reconfigure edit/add/remove, EN and DE | Frontend. |
| P2-2 breaker loop | ha-a (+ rendered Repairs card) | owned device whose actions publish the opposite value to its own state topic; 5 runs in 10 s trips the breaker; Repairs card EN/DE; release by reconfigure or reload; restart while paused stays paused | Owned actions are unrestricted, so `mqtt.publish` works (it is denied only for broker-received actions [VERIFIED: `DENIED_SERVICES` contains `"mqtt.publish"`]). Do not approve the device on ha-b. Delete the device afterwards. Defaults: `DEFAULT_BREAKER_MAX_RUNS = 5`, `DEFAULT_BREAKER_WINDOW = 10` [VERIFIED: `const.py:45-46`]. |
| P3-1 approval request rendering | ha-a owner, ha-b follower | device name, instance name and action YAML with backticks, underscores, pipes, templated service name; open the approval in Settings > Repairs on ha-b | Instance name is set at hub setup; check whether it can be changed on ha-a without losing state (Open Question). Phase 3 UAT did this with chrome-devtools. |
| P3-2 delete dialogs | ha-a | delete a device named with backticks and `<b>` through the integration's own step and the generic core dialog | The core dialog text cannot be changed by the integration (documented limitation). |

## Common Pitfalls

### Pitfall 1: The containers run the pre-Phase-6 build
**What goes wrong:** Checks pass or fail against code that predates MIG-05.
**Why it happens:** Python modules load at container start; ha-a/ha-b started 2026-10-03 20:54, before Phase 6 [VERIFIED above].
**How to avoid:** Record the SHA, restart, compare `sha256sum` host vs `podman exec`, and put the SHA and the container `StartedAt` in each evidence folder. A branch switch changes the mounted code: do not switch.
**Warning signs:** `.StartedAt` older than the recorded SHA's commit time.

### Pitfall 2: The export publish is silently denied
**What goes wrong:** UAT-04 finds no retained export topic and looks like an integration defect.
**Why it happens:** No ACL row for `mqtt_actions_export/#`; Mosquitto does not report denied publishes ([VERIFIED: `docs/broker-acl.md`]).
**How to avoid:** Add the row and SIGHUP before the group; read topics back with a second client; check the ACL before each group (CONTEXT specifics).

### Pitfall 3: The replay catch is one-shot at start
**What goes wrong:** A live re-publish of legacy Discovery leaves `_2` entities, and the tester calls UAT-02 a failure.
**Why it happens:** `_arm_replay_catch()` is called once at the end of `async_start` [VERIFIED: `manager.py:811-813`] with a 5.0 s timer; the Phase 6 verification recorded the limit: "A replay that core MQTT delivers later than the 5 s one-shot catch (for example after a broker reconnect while running) is cleaned only at the next start (review WR-03)" [VERIFIED: `06-VERIFICATION.md` `deferred` entry, now assigned to Phase 8].
**How to avoid:** Publish while the container is stopped (this is the startup replay MIG-05 is about) and judge after the quiet period. Treat live duplicates as the documented limit; record it as an observation; if the owner considers it a defect, raise it as a gap for a follow-up (D-08).

### Pitfall 4: A core-prefix export is cleaned by the catch at the next start
**What goes wrong:** After a restart the "only disabled duplicates" are gone and UAT-04 step 3 cannot be repeated.
**Why it happens:** The export device identifier is `mqtt_actions_<device id>` [VERIFIED: `discovery.py:155`, `"device": {"identifiers": [f"{DOMAIN}_{spec.device_id}"], ...}`], the same as the legacy one, and `remove_replay_twins` selects by MQTT device, platform, domain and unique id, including disabled entries (`include_disabled_entities=True`), without looking at the topic prefix [VERIFIED: `takeover.py:65-91, 188-220`]; a newer, uncustomized `mqtt` twin does not "carry the identity" and is removed. [ASSUMED: inferred from reading; not observed on a real instance.]
**How to avoid:** Observe the duplicates immediately after turning the prefix, before any restart. Record the post-restart cleanup as an observation. Run UAT-04 after UAT-02 so its leftovers cannot contaminate UAT-02's baseline.

### Pitfall 5: Reading the registry too early
**What goes wrong:** `core.entity_registry` on disk lags the in-memory state (writes are delayed by about 10 s; the integration flushes after the catch [VERIFIED: `takeover.py` `async_flush_registries` docstring]).
**How to avoid:** `podman stop` (graceful, flushes) before reading for evidence, or read through WS `config/entity_registry/list` [ASSUMED] while running.

### Pitfall 6: "Shows no entities" meets the v0.1.0 companion mode select
**What goes wrong:** A tester sees `select.<name>_mode` entities on ha-c and fails UAT-01 literally.
**Why it happens:** v0.1.0 creates a mode select per mirror on a companion device [VERIFIED: `v010/select.py:1`]; those are platform `mqtt_actions`, not Discovery entities of the migrated device.
**How to avoid:** Fix the pass wording before running (see UAT-01 step 2) and get owner agreement (Open Question 3).

### Pitfall 7: Restarting `mosq` wipes retained state
**What goes wrong:** All retained configs, states and availability vanish; follower mirrors may be pruned later.
**Why it happens:** `persistence false` [VERIFIED: `mosquitto.conf`]. Owners republish configs, discovery and availability on reconnect, but not state topics.
**How to avoid:** For P1-5 "broker reconnect" reload the core MQTT config entry (`POST /api/config/config_entries/entry/<mqtt entry id>/reload` [ASSUMED] or the UI) which resubscribes and replays retained state with `retain=True`. Take a retained snapshot first.

### Pitfall 8: Default log level hides the evidence
**What goes wrong:** INFO lines never appear; counting by INFO fails.
**Why it happens:** Both logs show 0 INFO lines [VERIFIED].
**How to avoid:** Use `level: warning` in marker actions; add a `logger:` block for `custom_components.mqtt_actions: info` if the INFO catch line is wanted [ASSUMED that `logger` is loaded with `default_config`]. Save logs before every restart.

### Pitfall 9: `ha-ws` and the `ha` wrapper target production
**What goes wrong:** A call without override acts on the real HA fleet.
**How to avoid:** Always `HA_URL=http://localhost:8123 HA_TOKEN=<test token> ha-ws ...` inline, and make a wrapper script that refuses to run when the URL is not `localhost`/`127.0.0.1` with a test port. Never use the `ha` SSH wrapper (it targets `haos-op3050-1`). Evidence files must not contain tokens.

### Pitfall 10: Legacy peer online while a hub is re-added
**What goes wrong:** A re-added hub (P1-2) starts non-native and, with `ha-c` online, shows `native_cutover_waiting`, derailing the frontend session.
**How to avoid:** Stop `ha-c` after UAT-01; the README describes the waiting behavior ("An instance switches once no online instance runs an older version" [VERIFIED: README "Upgrading from 0.1.x"]).

### Pitfall 11: Stale checks after any change
**What goes wrong:** D-03 says a later code change makes affected checks stale; the verifier digest also re-stales Phases 1 to 4 when covered files change.
**How to avoid:** Phase 8 changes `.planning/` only. A check of the final consolidation task: `git diff --stat <recorded SHA> HEAD -- custom_components tests .github` is empty.

## Code Examples

All commands are bash. Replace `<id>` and creds. `-W` in `mosquitto_sub` is a wait in seconds.

### Retained snapshot (no secrets in output)

```bash
# Source: mosquitto_sub(1); topics and ACL read this session
mosquitto_sub -h localhost -u ha_one -P "$PW" -t 'mqtt_actions/#' -t 'homeassistant/#' -t 'mqtt_actions_export/#' \
  -v -F '%t %r %p' -W 3 | sort > 08-evidence/00-preflight/retained-snapshot.txt
```

### Registry assertions (UAT-02 / UAT-04)

```bash
# Source: structure of ~/ha-test/a/.storage/core.entity_registry read this session (.data.entities[])
REG=~/ha-test/a/.storage/core.entity_registry
jq -r '.data.entities[] | select(.platform=="mqtt") | [.entity_id,.unique_id,.disabled_by] | @tsv' "$REG"   # UAT-02: expect empty
jq -r '.data.entities[] | select(.entity_id|test("_2$")) | .entity_id' "$REG"                               # expect empty
jq -c '.data.entities[] | select(.platform=="mqtt_actions") | {entity_id,id,unique_id,device_id}' "$REG" | sort  # diff against baseline
```

### Legacy payload for UAT-02

```bash
# Source: custom_components/mqtt_actions/discovery.py build_discovery (unchanged since v0.1.0); spec_from_data used as in tests/test_discovery_export.py
cd /home/akentner/Projects/homeassistant-mqtt-actions-integration
.venv/bin/python - <<'PY'
import json
from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.model import spec_from_data
spec = spec_from_data("switch", "Lampe Test", {"device_id": "11111111-aaaa-4aaa-8aaa-000000000001"})
print(json.dumps(build_discovery(spec=spec, base_topic="mqtt_actions", instance_id="3851f34f-fa67-4f3c-bba0-122465013c3d", sw_version="0.1.0")))
PY
```

(Whether `spec_from_data` needs further keys for a switch with actions is [ASSUMED]; the test uses `spec_from_data("switch", "Lamp", {CONF_DEVICE_ID: "dev-1"})` [VERIFIED: `tests/test_discovery_export.py`]. Compare the generated button unique ids with the registry: `..._test_b8d31e852725` and `..._test_b4dc66dde806` [VERIFIED: registry].)

### Publish and read back (ACL-silent denial)

```bash
mosquitto_pub -h localhost -u ha_one -P "$PW" -r -q 1 -t "homeassistant/device/$ID/config" -f payload.json
mosquitto_sub -h localhost -u ha_one -P "$PW" -t "homeassistant/device/$ID/config" -W 2 -v   # must print the payload
podman kill --signal HUP mosq                                                                   # after an ACL or passwd edit
```

### Unknown payload and the exactly-once count

```bash
mosquitto_pub -h localhost -u bridge -P "$BPW" -q 1 -t "mqtt_actions/v1/devices/$ID/state" -m banana     # not retained
grep -c 'Ignoring unknown payload' ~/ha-test/a/home-assistant.log ~/ha-test/b/home-assistant.log
grep -c 'UAT03-MARKER on' ~/ha-test/a/home-assistant.log ~/ha-test/b/home-assistant.log                   # expect 1 and 1 after one command
```

### Test-instance API call without touching production

```bash
HA_URL=http://localhost:8123 HA_TOKEN="$(cat ~/ha-test/.token-a)" ha-ws raw config/entity_registry/list --json
```

(`raw <type>` is in the tool's usage text [VERIFIED]; the token file lives outside the repo.)

### Mount integrity

```bash
git rev-parse HEAD; git diff --quiet HEAD -- custom_components && echo clean
for f in manager.py takeover.py; do
  sha256sum custom_components/mqtt_actions/$f | cut -c1-16
  podman exec ha-a sha256sum /config/custom_components/mqtt_actions/$f | cut -c1-16
done
```

## State of the Art

| Old approach | Current approach | Impact |
|--------------|------------------|--------|
| Phase 5 UAT skipped four checks (`05-UAT.md` tests 4 to 7: "result: skipped") | Phase 8 runs them on the build with the IN-02 and IN-03 fixes | Closes the debt; UAT-02 proves MIG-05 outside the harness |
| Phase 7 left ten human items open (`human_needed` for Phases 1 to 3) | Phase 8 records each with evidence; the verifier then closes items | `human_verification` entries close with a `resolution:` field and no contradicting `status:` [VERIFIED: `~/.claude/gsd-core/bin/lib/uat.cjs`, `isHumanVerificationEntryResolved`] |

**Closing the Phase 1 to 3 reports (D-06):** do not hand-edit report frontmatter (Phase 7 precedent in `07-PROOF.md`). Re-run the verifier or `/gsd-verify-work` per archived phase with `08-UAT.md` as the evidence source, then read `gsd_run verification status <archived dir> --pick status`. Items with `result: issue` stay open and the phase stays `human_needed` or becomes `gaps_found`; owner overrides need the owner's own name (D-07). The Phase 1 report will re-stale when the manifest version is bumped at milestone close (`07-VERIFICATION.md` warning 3); not a Phase 8 concern.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The browser MCP (chrome-devtools) is available in the executing session and can log into the test frontends | Standard Stack | Frontend steps fall entirely on the owner (more owner effort, no result change) |
| A2 | `ha-c` can be started with the flags read from `podman inspect ha-b` and a fresh config dir needs internet for `default_config` dependencies | Setting up ha-c | First start slower or fails offline; fall back to copying `deps` from ha-b or cloning the pre-Phase-5 backup |
| A3 | Standard HA onboarding API (`/api/onboarding/users`) gives a scripted token for a fresh instance | Setting up ha-c | Owner must onboard and create the token in the browser |
| A4 | The catch removes core-prefix export duplicates at the next start (read from `takeover.py`, not observed) | Pitfall 4, UAT-04 | UAT-04 step 5 shows the duplicates persist instead; then record as observation, no fail |
| A5 | WS `config/entity_registry/list` and the REST config-entry reload endpoint work as in `ha-ws raw` usage | Pitfalls 5, 7 | Use the host-readable registry file and the UI instead |
| A6 | `logger` is loaded with `default_config` so a `logger:` block works | Pitfall 8 | The INFO line cannot be captured; registry is the proof anyway |
| A7 | `spec_from_data("switch", name, {"device_id": id})` yields the same button keys as the real device | Code Examples | Payload differs from the real v0.1.0 payload: compare unique ids with the registry before publishing |
| A8 | Instance name of ha-a can be changed to hostile text for P3-1 without losing state | P3-1 | Use a hostile device name and hostile action YAML only; owner name part checked with the existing "Test HA One" |
| A9 | HACS keeps showing the newest release (v1.0.0) as default for this custom repository | Ten items P1-1 | The version HACS offers may differ; record what it reports |

## Open Questions

1. **API access to the test instances**
   - What we know: `.storage/auth` is off limits (a credential read was blocked this session); `ha-ws` and REST need a token.
   - What's unclear: whether the owner wants to create long-lived tokens for ha-a and ha-b (profile page) and store them outside the repo, or have Claude work through the browser only.
   - Recommendation: the owner creates one token per instance in `~/ha-test/.token-{a,b}` (mode 0600, not in git), and ha-c is onboarded by script so it comes with its own token. Ask at plan time.

2. **Which production host for Phase 1 #1 and is the integration already there?**
   - What we know: D-02 allows one production host; the UAT of Phase 5 says test 6 "is covered by the production rollout", which suggests the integration may already run there.
   - What's unclear: the host and whether install and remove would collide with an existing config entry (`single_config_entry`).
   - Recommendation: the owner names the host; if the integration is already installed, use a host without it, or treat "download and update" as the HACS path and say so in the evidence. HACS installs v1.0.0, not HEAD (see table).

3. **Wording of the UAT-01 pass criterion for the companion mode select**
   - What we know: v0.1.0 shows a mode select per mirror but no switch/select/button of the migrated device.
   - What's unclear: whether the owner reads "shows no entities for migrated devices" as including the mode select.
   - Recommendation: fix the wording as in UAT-01 step 2 in the plan and record the mode selects as an observation.

4. **Is the live-republish duplicate (Pitfall 3) a defect?**
   - What we know: documented as deferred WR-03 in `06-VERIFICATION.md`; README does not mention it.
   - Recommendation: run the live variant once for the record, classify it as an observation, and let the owner decide whether to raise a follow-up gap (not a Phase 8 fix).

5. **Where do helper scripts live?**
   - Recommendation: `~/ha-test/bin/` for bench scripts, evidence copies of their output in `08-evidence/`. Owner may prefer them in the repo; scripts contain local ports and paths.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| podman | containers | yes | 6.1.3 | — |
| Mosquitto broker `mosq` | all broker steps | yes (Up 22 h) | 2.1.2 | — |
| `ha-a` (8123), `ha-b` (8124) | UAT-02/03/04, frontend items | yes (Up, old code) | HA 2026.9.4 | restart at HEAD |
| `~/ha-test/v010` | UAT-01 | yes | v0.1.0, identical to tag | — |
| Port 8125, memory, disk | ha-c | yes | 42 GB free, about 4 GiB available | — |
| `mosquitto_pub/sub/passwd` | scripted steps, ACL users | yes | 2.1.2 | — |
| `jq`, `curl`, `python3`, `uv`, `gh`, `sqlite3` | evaluation | yes | see Standard Stack | — |
| `.venv` with `homeassistant` and `aiohttp` | payload build, WS helper | yes | HA 2026.9.4 | `uv sync` |
| `websocat` | WS from shell | no | — | `ha-ws` or aiohttp from the `.venv` |
| Browser MCP | frontend steps | unknown | — | owner performs the steps |
| API tokens for test instances | token-based steps | no | — | owner-created tokens, scripted onboarding for ha-c, or UI only |
| Production host and HACS | P1-1, P1-6 | owner only | — | — |
| Internet for first start of ha-c | dependencies | probably | — | copy `deps` from ha-b |

**Missing dependencies with no fallback:** none (all gaps have an owner action or a workaround).
**Missing items that need an owner decision:** tokens, production host choice.

## Validation Architecture

Validation here means: every check ends with a script-asserted or owner-signed result in `08-UAT.md`, and the final state of the planning artifacts is machine-checkable.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None for code (no code changes). Bench scripts in bash with explicit `PASS`/`FAIL` lines; the existing pytest suite is only a stale-check anchor |
| Config file | none; helper scripts in `~/ha-test/bin/` (Wave 0) |
| Quick run command | `~/ha-test/bin/check-<id>.sh` per check (to be written; each prints `PASS`/`FAIL` plus the evidence path) |
| Full suite command | `~/ha-test/bin/run-all-scripted.sh` over the scripted group (UAT-02, UAT-03, P1-5, UAT-04) |
| Stale anchor | `git diff --stat <recorded SHA> HEAD -- custom_components tests .github` must be empty at the end |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UAT-01 | v0.1.0 straggler runs actions, no Discovery entities, no error | semi-automated (scripts + owner approval of the mirror) | `check-uat01.sh` (registry jq, log grep, issue list) | Wave 0 |
| UAT-02 | no `mqtt` or `_2` entries after two starts with retained legacy Discovery | automated | `check-uat02.sh` (stop, jq diff against baseline, retained read-back) | Wave 0 |
| UAT-03 | exactly one run per approved instance; unknown payload ignored | automated (token for the command, or UI) | `check-uat03.sh` (marker counts, WARNING count, state compare) | Wave 0 |
| UAT-04 | export payload shape, core-prefix duplicates disabled, off clears | automated | `check-uat04.sh` (`mosquitto_sub` + `jq` assertions, registry) | Wave 0 |
| P1-1, P1-6 | HACS install, host core version | manual (owner) | none | n/a |
| P1-2, P1-3, P1-4, P2-1, P3-1, P3-2 | frontend rendering, strings, dialogs | manual or browser MCP + owner sign-off | screenshot plus owner statement | n/a |
| P1-5, P2-2 | retained-vs-live chain, breaker loop | scripted plus frontend for the Repairs card | `check-p15.sh`, `check-p22.sh` | Wave 0 |
| (all) | each row has a `result:` token and an evidence path | automated | grep over `08-UAT.md`: no `result: pending` left; every evidence path exists | Wave 0 |

### Sampling Rate

- **Per task:** the matching `check-*.sh` and a look at the evidence folder.
- **Per wave:** mount-integrity check (SHA, hashes) and ACL read-back.
- **Phase gate:** no `result: pending`, every `issue` has a `## Gaps` entry, `gsd_run verification status` printed for Phases 1 to 3, stale anchor empty.

### Wave 0 Gaps

- [ ] `~/ha-test/bin/` helper scripts (checks above, a `ha-test-guard` wrapper refusing production URLs)
- [ ] Backup of `~/ha-test/{a,b,mosquitto}` (stop containers first; pattern of `_backup-pre-phase5-uat-20261003-181937`)
- [ ] ACL: export prefix row for `ha_one`/`ha_two`; user `ha_three` and block with the real instance id of `ha-c`
- [ ] `ha-c` container, config dir, onboarding and MQTT entry
- [ ] Tokens for ha-a, ha-b (owner) and ha-c
- [ ] Marker device(s) for counting (actions `system_log.write`, level `warning`) created on ha-a
- [ ] `08-UAT.md` skeleton with all 14 blocks at `result: pending`

## Security Domain

`security_enforcement` is enabled in `.planning/config.json` (ASVS level 1, block on high). The phase changes no product code, so the relevant concerns are about the bench and the evidence.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (bench) | Test instances use their own accounts and tokens; tokens kept outside the repo, mode 0600; production credentials never used here |
| V3 Session Management | no | — |
| V4 Access Control | yes (bench) | Per-instance MQTT users and ACL blocks; verify ACL by read-back; the live broker is untouched (D-01) |
| V5 Input Validation | partly | The UAT exercises it: unknown payload ignored, hostile names rendered as text (P3-1, P3-2) |
| V6 Cryptography | no | — |
| V8 Data Protection | yes | Evidence files are committed to a public repo: no tokens, passwords, `.storage/auth`, `core.config_entries`, `.cloud` content or screenshots with tokens |

### Known Threat Patterns for this bench

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `ha-ws`/`ha` run against production by mistake | Tampering | Inline env override and a guard wrapper; never the `ha` SSH wrapper (Pitfall 9) |
| Secrets in committed evidence | Information disclosure | Redact; copy only filtered registry output; review `08-evidence/` with `grep -ri -E 'token|password|bearer'` before commit |
| Silent ACL denial taken as a pass or a fail | Repudiation | Read back every publish with a second client |
| Hostile device and instance names (P3-1, P3-2) | Tampering | These are the test inputs; use inert content only (no real service calls beyond logging) |
| Production host change (P1-1) | Tampering | Add and remove only, no device created; check afterwards that no retained availability topic of the new instance id remains on the production broker (read-only subscribe, owner's consent) |
| A forged `offline` heartbeat or availability on the test broker | Spoofing | Known limit WR-03 (README); not a Phase 8 target |

## Sources

### Primary (HIGH confidence)

- Repo files read this session: `.planning/phases/08-real-instance-verification/08-CONTEXT.md`, `08-DISCUSSION-LOG.md`, `.planning/REQUIREMENTS.md`, `STATE.md`, `ROADMAP.md` (Phase 8 section), `07-PROOF.md`, `07-VERIFICATION.md`, `06-VERIFICATION.md`, `06-RESEARCH.md`, `.planning/milestones/v1.0-phases/{03,04,05}-*/…-UAT.md`, `docs/adr/0001-native-entities-instead-of-mqtt-discovery.md`, `docs/broker-acl.md`, `README.md`, `custom_components/mqtt_actions/{takeover,discovery,topics,state,const}.py`, `manager.py` (lines 800-885, 2520-2532), `tests/test_discovery_export.py`, `tests/test_native_replay.py` (head).
- Environment probes this session: `podman inspect`, `podman images`, `ss`, `jq` over `~/ha-test/{a,b}/.storage/{core.entity_registry,core.device_registry,core.config_entries (non-secret fields),mqtt_actions.state}`, `~/ha-test/mosquitto/{acl,mosquitto.conf}` (and the passwd user names), a read-only retained-topic probe, `git diff`/`git show` against tags `v0.1.0` and `v1.0.0`, `~/ha-test/v010` file diffs.
- `man mosquitto.conf` (local, 2.1.2): reload on SIGHUP.
- `~/.claude/gsd-core/templates/UAT.md`, `bin/lib/uat.cjs` (UAT parsing, `human_verification` resolution rule), `agents/gsd-verifier.md`.

### Secondary (MEDIUM confidence)

- https://hacs.xyz/docs/use/repositories/dashboard/ : "By default, the newest version is downloaded."; version selection under "Need a different version?"; removal "removes the repository that was stored in your Home Assistant configuration directory". The page did not mention a pre-release toggle (a search summary mentioned one; unconfirmed).
- https://developers.home-assistant.io/docs/api/rest/ : Bearer token auth with a long-lived access token; `/api/states`, `/api/services/<domain>/<service>`, `/api/error_log`.

### Tertiary (LOW confidence)

- Onboarding API, config-entry reload endpoint, `config/entity_registry/list`, `logger` with `default_config`, and the first-start behavior of a fresh container: training knowledge, tagged `[ASSUMED]` above.

## Metadata

**Confidence breakdown:**
- Standard stack (bench): HIGH, read and probed this session.
- Architecture and grouping: MEDIUM-HIGH, sequencing derived from verified code behavior (catch timing, ACL, retained semantics).
- Pitfalls: MEDIUM-HIGH, Pitfalls 1, 2, 3, 7, 8 verified; 4, 5, 6 inferred from code with a read; 9 and 10 from tool and README reading.
- Frontend items: LOW-MEDIUM, no browser session available to the researcher.

**Research date:** 2026-10-04
**Valid until:** 2026-10-11 (HA 2026.10.0 is about to release; the bench image tag `2026.9` is pinned, but anyone pulling a newer image invalidates the findings)
