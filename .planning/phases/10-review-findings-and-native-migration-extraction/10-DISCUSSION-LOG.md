# Phase 10: Review Findings and Native Migration Extraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-16
**Phase:** 10-review-findings-and-native-migration-extraction
**Areas discussed:** Repairs warning (FIX-08), Private registry API (FIX-01), Eager-task dependency (FIX-07), Module cut of the move (FIX-02); todo cross-reference

---

## Todo cross-reference

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, in Phase 10 | Small first plan, so Phase 10 commits get CI on push again | ✓ |
| No, separate via /gsd-quick | Handled outside the phase | |

**User's choice:** Yes, in Phase 10

## Repairs warning (FIX-08)

| Question | Options | Selected |
|----------|---------|----------|
| Content | Entity ids + reason / Device names + count / Count only | Entity ids + reason |
| Granularity | One per instance / One per device | One per instance |
| Include D-03 fail-safe leftovers (09.1 deferred) | No, enabled only / Yes, own section | No, enabled only |
| Re-evaluation timing | After takeover/guard/catch / Also live on registry events | After takeover/guard/catch |

## Private registry API (FIX-01)

| Question | Options | Selected |
|----------|---------|----------|
| Runtime reaction | As today: warning log + fallback / Additionally a Repairs hint | As today |
| What the loud test proves | Immediate write to disk via `hass_storage` / Attribute existence only | Immediate write to disk |

## Eager-task dependency (FIX-07)

| Question | Options | Selected |
|----------|---------|----------|
| Approach | Pin loudly with a test / Make independent (two-step, async) / Both | Pin loudly with a test |
| Loudness rule for FIX-01/04/07 | Red CI is wanted / Red CI plus own pytest marker | Red CI is wanted |

## Module cut of the move (FIX-02)

| Question | Options | Selected |
|----------|---------|----------|
| Cut | Research sketch + 09.2 gate / Research scope only / You decide | Research sketch + 09.2 gate |
| Tests in the move plan | Unchanged / Move to `test_native_migration.py` | Unchanged |
| Shared helpers module | `tests/helpers.py` / Several topic modules | `tests/helpers.py` |

## Claude's Discretion

- Issue id, translation wording, reason labels and list cap of the FIX-08 warning
- FIX-05 doc wording and an optional `tests/test_docs.py` claim
- Public surface of `NativeMigration`
- Plan split within the fixed roadmap order; placement of the CI todo plan

## Deferred Ideas

- Repairs notice for disabled fail-safe leftovers (not taken)
- Renaming orchestration tests to `test_native_migration.py` (not in this phase)
