---
phase: 08-real-instance-verification
plan: 12
subsystem: verification-gap-closure
tags: [uat-04, guard, entity-registry, tombstone, discovery-export, docs, tdd]
requires:
  - phase: 08-real-instance-verification
    provides: owner decision UAT04-GAP-DISPOSITION guard-and-document, classification TOMBSTONE-ONLY (plan 08-11)
provides:
  - waiver D08-WAIVER of the D-08 clause "fixes not in Phase 8", recorded in the ledger, CONTEXT.md and the ROADMAP goal
  - registry-only guard that disables an enabled core MQTT duplicate of an exported device id while the export is on the core prefix
  - README and troubleshooting text for the restored enabled state and what to do
affects: [08-13, 08-14, 08-15]
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-04-guard/ (four RED records with their JUnit XML)
  modified:
    - custom_components/mqtt_actions/takeover.py
    - custom_components/mqtt_actions/manager.py
    - tests/test_discovery_export.py
    - README.md
    - docs/troubleshooting.md
    - .planning/phases/08-real-instance-verification/08-UAT.md
    - .planning/phases/08-real-instance-verification/08-CONTEXT.md
    - .planning/ROADMAP.md
decisions:
  - "D08-WAIVER: product fix allowed in Phase 8 for the UAT-04 clause 2 gap closure only; the failure rule of D-08 stands; relayed 2026-10-08, confirmed directly by the owner in chat 2026-10-11"
  - "The guard disables, it does not remove; it uses public registry API only (async_update_entity, entity registry updated event) and adds no string, service, option or issue"
metrics:
  completed: 2026-10-11
status: complete
commits: 4
plan_head_before: a9094bac387c1882734f337dbedc7845652033de
plan_head_after: 72684c9
---

# Phase 8 Plan 12: guard and documentation for the enabled core-prefix export duplicate Summary

The enabled duplicate that an export on the core prefix creates from a restored tombstone is now disabled by the integration itself, test-first, and the README and the troubleshooting page say when it happens and what to do. The disposition read was `guard-and-document` (`applies guard` yes, `applies document` yes).

## What was done

- **Task 1, waiver (272d4fa), applied:** row `D08-WAIVER` in `08-UAT.md` Owner decisions, a dated amendment line under D-08 in `08-CONTEXT.md` (original D-08 text untouched, scope limited to plans 08-11 to 08-15), and an exception sentence in the ROADMAP Phase 8 goal. The provenance says: relayed by the orchestrator on 2026-10-08 and confirmed directly by the owner in chat on 2026-10-11 with "ja". An earlier executor run stopped at the commit because the permission classifier refused it; the owner's own confirmation and the inline run (`--interactive` style, each step under the normal permission prompts) resolved it.
- **Task 2, guard (RED d4c7daa, GREEN 2b3b9c3), applied:**
  - `takeover.disable_export_duplicates` finds the core MQTT device of the id, keeps the switch or select entries whose unique id equals the id and whose `disabled_by` is None, and sets them to `integration`. It publishes nothing and never touches another unique id.
  - `manager._sync_export_guard` arms a listener on the entity registry updated event while the export is on and its prefix equals `gateway.discovery_prefix()`, runs one sweep for rows that exist, and disarms in `_apply_export_options` when the signature changes and in `async_stop`. The listener returns at once unless the action is `create`, the platform is `mqtt` and the unique id is an exported device id; the change runs on the next loop iteration (`call_soon`), not nested in core's entity creation.
  - Exported ids: owned, native, not in `sync.transferred_away`, read when the event arrives.
- **Task 3, documentation (72684c9), applied:** README export section keeps both pinned sentences and adds the restored-state exception and the guard; `docs/troubleshooting.md` has one new entry (symptom, why, what to do). No claim about a restart while the export stays on the core prefix.

## TDD Gate Compliance

RED commit `d4c7daa` precedes GREEN `2b3b9c3`. Four target tests were red on the unchanged production code, each on its own assertion that the mqtt row is `disabled_by` integration while it was enabled (None). Verdicts come from `gsd_run check tdd-red-evidence`, fed with the pytest JUnit XML of the RED run (classname and name swapped, the parser quirk of plans 06-01 and 06-02); records in `08-evidence/uat-04-guard/red-1..4.json`.

| Target test | Failed on | Verdict |
|-------------|-----------|---------|
| `test_a_restored_enabled_state_is_disabled_by_the_guard[switch]` | duplicate row `disabled_by` is None, not integration | RED_EVIDENCE_OK |
| `test_a_restored_enabled_state_is_disabled_by_the_guard[select]` | same | RED_EVIDENCE_OK |
| `test_an_enabled_row_that_exists_when_the_export_is_switched_on_is_disabled` | existing enabled row stays enabled after the export is switched on | RED_EVIDENCE_OK |
| `test_the_guard_publishes_nothing_and_stops_with_the_manager` | restored enabled row is not disabled | RED_EVIDENCE_OK |

Semantic assessment: the target tests ran and failed on the planned assertion, not on an import, fixture or collection fault. The tombstone tests reproduce the bench sequence on the real core MQTT code: an enabled mqtt row of the device id is removed (tombstone with `disabled_by` None), then the export on the core prefix is switched on, core creates the entity and the registry restores the enabled state. The tests that pass on the unchanged code by design are the inert ones (export off, other prefix, export switched off, foreign unique id), which pin what the guard must not do.

GREEN: all pass after `2b3b9c3`. REFACTOR: none.

## Verification

- Guard tests plus `tests/test_native_replay.py` and `tests/test_takeover.py`: 65 passed.
- Full unit suite 1481 passed, broker tier 17 passed (1498 tests, the 1490 of the phase plus 8 new), `ruff check` and `ruff format --check` clean.
- `tests/test_docs.py` and `tests/test_translations.py`: 86 passed.
- `git diff --name-only b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3 HEAD -- custom_components` names only `manager.py` and `takeover.py`; no translation file, `services.yaml` or `const.py` changed.
- `check-recorded.sh --all` PASS (14 checks) after Task 1. No bench script ran in this plan.

## Deviations from Plan

**1. [Rule 3 - Blocking] Test construction differs from the plan text.** The plan says the export payload is "delivered to core MQTT the way the existing core-prefix test delivers it". In this harness the mocked client already hands every publish to core, and core ignores an identical payload and keeps a pending discovery after an entity was removed, so a second manual delivery created no row. The tombstone tests therefore switch the export on through the hub options after the tombstone exists (core receives the real published export). The sequence is the same: an enabled row removed, then the export on the core prefix. A helper enables an existing disabled duplicate before removing it, so the tombstone carries `disabled_by` None.

**2. Commit mix-up recovered.** A scripted edit duplicated a block in `tests/test_discovery_export.py` once; the file was restored from git (`git checkout`) before any commit and the tests were rewritten, so no broken state was committed.

## Findings for the follow-up plans

- Plan 08-13 must restart the containers (they bind-mount the main checkout) and re-pin the build; the guard reaches them only then.
- Pre-existing bench rows (Lampe Test and Bar Select, enabled null-tombstone duplicates) are the regression state for the re-run; the guard should disable them through its sweep at the next start with the export on the core prefix; plan 08-13 has to confirm that on the bench, it is not shown here.
- A `refactor` pass was not needed. Open question, not decided here: whether a guard that runs before the first replay catch should also remove the disabled row; the plan decided disable-only.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register: T-08-35 (only exported owned native ids, switch or select, exact unique id, registry only), T-08-36 (listener returns at once, armed only on the core prefix, cancelled on stop), T-08-37 (text limited to evidence and tested behavior), T-08-44 (waiver scope, provenance and original D-08 sentence checked).

## Requirements

UAT-04 stays Pending: clause 2 closes only when the re-run on the new build is recorded (plans 08-13 and 08-14).

## Self-Check: PASSED

- Commits 272d4fa, d4c7daa, 2b3b9c3 and 72684c9 are in the branch; the RED records exist and classify RED_EVIDENCE_OK.
- Full suites and lint green; the diff constraint on `custom_components` holds.
