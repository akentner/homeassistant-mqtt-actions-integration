# MQTT Actions Integration

## What This Is

A Home Assistant custom integration (HACS-ready) that turns MQTT state changes into locally executed HA action sequences. Devices (Switch, Select) are configured via UI, appear as native entities of the integration (MQTT Discovery is an optional export, ADR 0001), and are described in a central config stored in the MQTT broker — so any other HA instance on the same broker picks it up and creates the same devices. It is for people running several HA instances who want synchronized, state-driven behavior without YAML boilerplate.

## Core Value

A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.

## Current State

v1.0.1 Hardening closed 2026-10-11 with an accepted verification gap (owner decision ACCEPTED-GAP-V101). The code fixes and the real-instance UAT are done; v1.0.1 is not released or tagged. The last public release stays v1.0.0. A v1.0.1 release needs a bench re-run of UAT-02 and UAT-04 on the final build first.

## Next Milestone Goals (v1.1, to be defined with `/gsd-new-milestone`)

- Per-instance local actions on mirrored devices (backlog 999.1, MIR-01, relates to MAP-01)
- Info findings of the two Phase 8 reviews (IN-01 to IN-04 and IN-01 to IN-03, incl. a Repairs hint for two customized rows)
- Full re-verification at the end of v1.1: Phases 1 to 8 reports current, UAT-02 and UAT-04 re-run on the final build, then a release

## Requirements

### Validated

- ✓ Integration subscribes to MQTT topics and runs configured actions on state changes — v1.0
- ✓ Device creation via Config Flow / UI with selectable domain (Switch and Select) — v1.0
- ✓ Switch device with `onChangeToOn` / `onChangeToOff` actions, Select device with per-option StateValue, StateFriendlyName and Actions — v1.0
- ✓ Actions are native HA action sequences, configured with the UI action selector and executed locally on each instance — v1.0
- ✓ State changes from the HA UI (command topic) and from external MQTT messages (state topic) drive the same behavior — v1.0
- ✓ Every device appears as native Switch or Select entities of the integration on every instance; MQTT Discovery is an optional export (ADR 0001) — v1.0
- ✓ Central integration config retained in MQTT; other instances create the same devices as validated, read-only mirrors — v1.0
- ✓ Per-device owner instance; only the owner edits or deletes, followers mirror, and an offline owner's devices can be adopted — v1.0
- ✓ Remote actions run only after the user approves the exact action hash on that instance — v1.0
- ✓ Deleting a device removes it from the central config and its entities everywhere, after an explicit all-instances warning — v1.0
- ✓ Re-trigger service runs the actions on all approving instances — v1.0
- ✓ HACS-compatible structure with releases and CI (hassfest, HACS validation, three test tiers) — v1.0 (v0.1.0, v1.0.0)
- ✓ A native mirror stays native after a restart, even near `MAX_DOCUMENT_BYTES` (IN-02, MIG-04) — v1.0.1
- ✓ The takeover survives a boot-time retained Discovery replay without a duplicate entity (IN-03, MIG-05) — v1.0.1
- ✓ CI and release on a pinned runner, flaky test fixed at its cause (QLT-02, QLT-03) — v1.0.1 (per Phase 7 verification; not ticked, see accepted gap)
- ✓ Phase 5 UAT debt closed on real instances (UAT-01 to UAT-04) — v1.0.1
- ✓ Core-prefix duplicates are disabled, never removed, on every native instance; user-customized rows are kept — v1.0.1 (unit tests only for the final review fixes)

### Active

- [ ] Current verification of Phases 1 to 8 on the final build (QLT-01 carried over, accepted gap of v1.0.1) — v1.1
- [ ] Per-instance local actions on mirrored devices (backlog 999.1, relates to MAP-01) — v1.1
- [ ] Info findings of the Phase 8 reviews — v1.1
- [ ] Authenticate or ACL-protect the cutover gate (WR-03) — with the EMQX migration

### Out of Scope

- Domains beyond Switch and Select — initial release only; further domains (e.g. Number, Button) can follow
- Peer-to-peer multi-writer editing of devices — ownership model chosen to avoid conflict resolution
- Referencing local scripts by name as the action mechanism — inline action sequences chosen instead

## Context

- Part of a Home Assistant ecosystem of custom components maintained by the user (phone-logger, notify_actions, kroki integration); conventions: Config Flow for setup, Python with uv and Ruff (120 chars).
- Multiple HA instances reachable over Tailscale (haos-op3050-1, lxc-haos-104, hassio-n2plus) can serve as test bed against a shared MQTT broker.
- Actions and configuration travel through the broker, so trust in the broker and its ACLs is a security concern (remote-provided action sequences execute locally).

Shipped v1.0 (2026-10-03) with about 9,200 lines of Python and three test tiers (unit, real Mosquitto, multi-instance). Released as v0.1.0 and v1.0.0 on GitHub. Known limits are listed in the README (Limitations).

Closed v1.0.1 (2026-10-11, not released): about 9,500 lines of Python, 1535 tests passing (2 strict xfail), CI pinned to `ubuntu-24.04`. Real-instance bench ha-a, ha-b, ha-c with its own broker users; tokens and bench state are owner follow-ups. Tech debt: verification reports of Phases 1 to 8 read stale or human_needed after the late review fixes; disabled MQTT duplicates stay in the registry (CR-01); entity-id rename and assistant exposure are not detected as customization.

## Constraints

- **Platform**: Home Assistant custom component (Python) using the built-in MQTT integration; it creates native entities and offers MQTT Discovery only as an optional export (amended in Phase 5, ADR 0001, D-03)
- **Distribution**: HACS-compatible public repo — dictates repo layout, versioning and CI
- **Security**: Actions from the broker run with full local service access — needs explicit design (trust model, opt-in)
- **Language**: UI and chat in German for the user; code, commits and comments in English

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Actions are HA action sequences | Maximum flexibility, familiar UI selector | ✓ Good (v1.0) |
| Per-device owner instance | Avoids conflict resolution in multi-writer setup | ✓ Good (v1.0), adoption added for offline owners |
| Central config retained in MQTT | Broker is the only shared component between instances | ✓ Good (v1.0) |
| State changes from UI and external MQTT | Supports both manual and system-driven use | ✓ Good (v1.0) |
| HACS-ready from start | Intended for public distribution | ✓ Good (v0.1.0 and v1.0.0 released) |
| Remote actions need per-instance approval of the exact hash | Broker content must never execute without a local opt-in | ✓ Good (v1.0), Phase 5 audit 19/19 threats closed |
| Native entities instead of MQTT Discovery | Every device and entity of every instance appears on the integration page, and the native path needs no healing | ✓ Good (ADR 0001, v1.0), one-way upgrade documented |
| Broker is cooperative and unauthenticated | Owner decision, EMQX migration planned; per-instance ACL is the real control | ⚠️ Revisit with the EMQX migration |
| Native flag of a mirror is a sticky set of ids in the Store (v1.0.1, D-01 to D-03) | The payload marker did not fit near the size limit | ✓ Good |
| Replay catch and duplicate guard are registry-only and disable rather than remove (v1.0.1, 06-02, 08-12, 08-17) | Removing a row lets core clear a retained topic; disabling keeps identities and user data | ✓ Good, CR-01 leaves disabled rows behind (accepted) |
| D-08 waiver: product fixes allowed inside the verification phase for UAT-04 clause 2 (v1.0.1) | The gap was a real product defect found on the bench | — Pending: one-off, keep fixes out of verification phases |
| Close v1.0.1 with an accepted verification gap (ACCEPTED-GAP-V101) | Late review fixes made the reports stale; a full re-run costs a bench cycle | ⚠️ Revisit: re-verify and re-run UAT-02/UAT-04 before any release |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-11 after v1.0.1 milestone*
