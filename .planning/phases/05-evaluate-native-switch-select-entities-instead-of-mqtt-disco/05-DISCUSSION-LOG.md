# Phase 5: Evaluate native switch/select entities instead of MQTT Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-03
**Phase:** 5-evaluate-native-switch-select-entities-instead-of-mqtt-disco
**Areas discussed:** Phase outcome, Discovery constraint and non-HA consumers, Migration, Mirror devices and entity model

---

## Phase outcome

Options: evaluation then implement on Go (selected) / evaluation + ADR only / implement directly.
Criteria selected (all four): integration page visibility, removal of Discovery complexity, non-HA consumers, migration cost/risk.

---

## Discovery constraint and non-HA consumers

Options: replace completely / native default with optional Discovery (selected) / keep both in parallel.
Non-HA consumers: nice-to-have (selected) / unimportant / hard requirement.

---

## Migration

Options: automatic with entity_id kept (selected) / hard cut with notice / opt-in migration.
Mixed versions: schema version + hint (selected) / all update at once / you decide.

---

## Mirror devices and entity model

Mirror: hub-level mirror devices marked with owner (selected) / one entity per device on hub device / you decide.
Companion: merge into native device (selected) / keep companion for now.

---

## Claude's Discretion

Spike form, entity_id takeover mechanics, schema version placement.

## Deferred Ideas

None.
