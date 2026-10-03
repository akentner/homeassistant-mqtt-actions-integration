# Phase 1: Walking Skeleton - Installable Switch - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-29
**Phase:** 1-Walking Skeleton - Installable Switch
**Areas discussed:** Topic layout & payloads, Startup & baseline behavior, Failure display (DEV-08), Setup flow & repo/CI

---

## Topic layout & payloads

| Question | Options | Selected |
|----------|---------|----------|
| Base topic | Configurable, default `mqtt_actions` / Fixed / Configurable but hidden in options flow | Configurable, default `mqtt_actions` ✓ |
| Switch payloads | ON/OFF case-insensitive on read / Strict ON/OFF / Configurable per device | ON/OFF case-insensitive ✓ |
| Device ID in topic | Random UUID / Slug + short suffix / User-chosen slug | Random UUID ✓ |

**User's choice:** Recommended option for each question.

---

## Startup & baseline behavior

| Question | Options | Selected |
|----------|---------|----------|
| First start with retained state | Baseline only / Run actions once / Ask in flow | Baseline only ✓ |
| "Run on startup" flag semantics | Run retained-state actions after HA start / Only if state != last_acted / Omit in Phase 1 | Run retained-state actions after HA start ✓ |
| Initial entity state | Unknown / Assumed OFF / Publish OFF on creation | Unknown ✓ |

**User's choice:** Recommended option for each question.

---

## Failure display (DEV-08)

| Question | Options | Selected |
|----------|---------|----------|
| Repairs granularity | One issue per device / Per device and trigger / Log only until N errors | One issue per device with last error ✓ |
| Issue lifetime | Auto-clear on next success + dismissable / Manual only / Fixable with edit flow | Auto-clear + dismissable ✓ |
| device_id warning | Warning in flow, save allowed / Log/Repairs only / Hard reject | Warning in flow, save allowed ✓ |

**User's choice:** Recommended option for each question.

---

## Setup flow & repo/CI

| Question | Options | Selected |
|----------|---------|----------|
| Hub flow fields | Base topic + instance name / Confirmation only / Also discovery prefix | Base topic + instance name ✓ |
| Repo | `akentner/homeassistant-mqtt-actions-integration`, MIT / Other name or owner / Apache-2.0 | `akentner/...`, MIT ✓ |
| ActionSelector spike and HA floor | First plan of the phase / Separate `/gsd-spike` / Build directly | First plan of the phase ✓ |

**User's choice:** Recommended option for each question.

---

## Claude's Discretion

- Retained-vs-live message handling, availability topic, QoS/retain settings, CI layout, translation keys, Repairs wording.

## Deferred Ideas

None.
