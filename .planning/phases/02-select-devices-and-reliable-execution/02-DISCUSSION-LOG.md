# Phase 2: Select Devices and Reliable Execution - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-29
**Phase:** 2-Select Devices and Reliable Execution
**Areas discussed:** Option editor, Payload mapping and discovery, Run mode and test button, Circuit breaker

---

## Option editor

| Question | Options | Selected |
|----------|---------|----------|
| Editing UX | Menu with loop / One form per option / All options in one form | Menu with loop |
| Add/remove after creation | Add and remove / Add only / Neither | Add and remove |
| Minimum requirements | At least 2 options, unique values / At least 1 / None | At least 2, unique |
| Ordering | Creation order / Reorder in menu | Creation order |

## Payload mapping and discovery

| Question | Options | Selected |
|----------|---------|----------|
| Matching | Trimmed, case-insensitive / Exact case-sensitive | Trimmed, case-insensitive |
| Discovery options | Friendly names with templates / StateValues | Friendly names with templates |
| Run on startup for Select | Same as Switch / Baseline only | Same as Switch |
| Unknown payload | Keep state, log / Also Repairs issue | Keep state, log |

## Run mode and test button

| Question | Options | Selected |
|----------|---------|----------|
| Restart semantics | Cancel running, discard queued / Cancel, keep queued in order | Cancel running, discard queued |
| Queue bound | Fixed limit / Unbounded | Fixed limit (10) |
| Run mode scope | Per device, Switch and Select / Select only | Per device, both |
| Test button | Button per option/trigger / One button plus helper / Service only | Button per option/trigger |

## Circuit breaker

| Question | Options | Selected |
|----------|---------|----------|
| Threshold | Fixed 5 in 10 s / Configurable per device / Loop detection by context | Configurable per device |
| After trip | Paused until reconfigure or reload / Auto release after cooldown | Paused until reconfigure or reload |
| Notification | Repairs issue plus log / Log plus persistent notification | Repairs issue plus log |
| Persistence | Tripped state persistent, window volatile / All volatile | Tripped state persistent |

---

## Claude's Discretion

Exact defaults beyond those named, translation keys and wording, runner implementation of restart vs. serial, test button entity naming.

## Deferred Ideas

- Reordering options
- Configurable queue limit
- Automatic breaker release after cooldown
