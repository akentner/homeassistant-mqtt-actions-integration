# MQTT Actions Integration

## What This Is

A Home Assistant custom integration (HACS-ready) that turns MQTT state changes into locally executed HA action sequences. Devices (Switch, Select) are configured via UI, published through MQTT Discovery, and described in a central config stored in the MQTT broker — so any other HA instance on the same broker picks it up and creates the same devices. It is for people running several HA instances who want synchronized, state-driven behavior without YAML boilerplate.

## Core Value

A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Integration subscribes to MQTT topics and runs configured actions on state changes
- [ ] Device creation via Config Flow / UI with selectable domain (initially Switch and Select)
- [ ] Switch device: configurable actions `onChangeToOn` and `onChangeToOff`
- [ ] Select device: multiple options, each with StateValue, StateFriendlyName and Actions
- [ ] Actions are native HA action sequences (service, target, data) configured with the UI action selector and executed locally on each instance
- [ ] State changes can originate from the HA UI (command topic) and from external MQTT messages (state topic); both drive the same behavior
- [ ] MQTT Discovery published for every entity
- [ ] Central integration config stored (retained) in MQTT; other HA instances reading it create the same devices
- [ ] Each device has an owner instance (the creator); only the owner may edit or delete it, other instances follow
- [ ] Deleting a device unpublishes it from the central config and removes its MQTT Discovery, with an explicit warning that this happens on all connected instances
- [ ] Service that re-triggers the actions on all connected instances
- [ ] HACS-compatible structure (hacs.json, releases, CI with hassfest and HACS validation)

### Out of Scope

- Domains beyond Switch and Select — initial release only; further domains (e.g. Number, Button) can follow
- Peer-to-peer multi-writer editing of devices — ownership model chosen to avoid conflict resolution
- Referencing local scripts by name as the action mechanism — inline action sequences chosen instead

## Context

- Part of a Home Assistant ecosystem of custom components maintained by the user (phone-logger, notify_actions, kroki integration); conventions: Config Flow for setup, Python with uv and Ruff (120 chars).
- Multiple HA instances reachable over Tailscale (haos-op3050-1, lxc-haos-104, hassio-n2plus) can serve as test bed against a shared MQTT broker.
- Actions and configuration travel through the broker, so trust in the broker and its ACLs is a security concern (remote-provided action sequences execute locally).

## Constraints

- **Platform**: Home Assistant custom component (Python) using the built-in MQTT integration — must work with the standard MQTT Discovery mechanism
- **Distribution**: HACS-compatible public repo — dictates repo layout, versioning and CI
- **Security**: Actions from the broker run with full local service access — needs explicit design (trust model, opt-in)
- **Language**: UI and chat in German for the user; code, commits and comments in English

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Actions are HA action sequences | Maximum flexibility, familiar UI selector | — Pending |
| Per-device owner instance | Avoids conflict resolution in multi-writer setup | — Pending |
| Central config retained in MQTT | Broker is the only shared component between instances | — Pending |
| State changes from UI and external MQTT | Supports both manual and system-driven use | — Pending |
| HACS-ready from start | Intended for public distribution | — Pending |

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
*Last updated: 2026-09-28 after initialization*
