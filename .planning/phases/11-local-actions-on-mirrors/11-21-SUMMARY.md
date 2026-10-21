---
phase: 11-local-actions-on-mirrors
plan: 21
subsystem: local-actions
tags: [storage, forward-compatibility, local-actions, docs, tdd, gap-closure]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-20 LocalActionsStoreUnreadableError (shape-invalid and corrupt-copy halves of WR-03), suite baseline 2084"
provides:
  - "ParsedLocalActions.preserved (copies of rows that fail parse, stored order) and .extra (copies of top-level keys other than records)"
  - "local_actions_payload(records, *, preserved=(), extra=None): extra keys first, then records = record rows followed by preserved rows"
  - "LocalActionsStore keeps _preserved/_extra from the last successful load, writes them back on every save, forgets them on removal"
  - "LocalActionsStore.preserved_device_ids -> frozenset[str] for the removal warning of Plan 11-22"
  - "README Lifecycle bullet 'Newer versions.'; disposition row WR-03 fixed"
affects: [11-22, phase-12-release]

plan_head_before: 05cb9dc259d81c552eb41eb0329234de36a955fa
plan_head_after: bae66d1aca80d295fe16276b48d46f88090846b2
actuals:
  tokens: 5709
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Forward compatibility of the local Store: whatever this release cannot parse is carried verbatim and inert, after the parsed records"
    - "Pure payload functions own the copy discipline (deep copy in and out); the Store adapter only holds and passes the kept parts"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-21-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-21-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-21-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-21-task2-red.xml
  modified:
    - custom_components/mqtt_actions/local_actions.py
    - custom_components/mqtt_actions/local_actions_store.py
    - tests/test_local_actions_store.py
    - tests/test_local_actions_manager.py
    - tests/test_docs.py
    - README.md
    - .planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md

key-decisions:
  - "Rows of the local Store that fail parse_local_record are kept verbatim and written back after the parsed records on every save; unknown top-level keys are kept too (WR-03 second half, D-07 extended by the owner 2026-10-21)"
  - "A later duplicate of a parsed identity is dropped and not preserved, so removing a customization can never bring an older row back (D-10)"
  - "async_remove_records forgets preserved rows and extra keys: removal is the user's explicit choice (D-08)"
  - "preserved_device_ids returns the raw non-blank string device_id of kept mapping rows, unstripped"

patterns-established:
  - "Kept rows are never records: they never reach _local_records, plans, the editor or the counts"

requirements-completed: [MIR-06, MIR-15]

coverage:
  - id: D1
    description: "An edit through the Manager keeps a row of an unknown mode, a non-mapping row and an unknown top-level key, after the parsed records; the kept row is not counted, not shown and never runs"
    requirement: MIR-06
    verification:
      - kind: integration
        ref: "tests/test_local_actions_manager.py#test_rows_this_release_cannot_parse_survive_a_local_edit"
        status: pass
    human_judgment: false
  - id: D2
    description: "Store and pure functions: repeated saves write kept rows and keys byte-identically after the records; duplicates are not kept; removal forgets kept rows; preserved_device_ids; copies in and out; an extra key named records never overrides"
    requirement: MIR-06
    verification:
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_preserved_rows_and_unknown_keys_are_written_back_after_the_records"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_duplicate_identity_rows_are_not_preserved"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_remove_records_forgets_preserved_rows_and_keys"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_preserved_device_ids_name_only_mapping_rows_with_a_device_id"
        status: pass
      - kind: unit
        ref: "tests/test_local_actions_store.py#test_payload_functions_keep_preserved_rows_and_extra_keys_as_copies"
        status: pass
    human_judgment: false
  - id: D3
    description: "README documents that local actions of newer versions stay unchanged, are neither applied nor shown, and are kept by saves here"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_every_local_actions_topic"
        status: pass
    human_judgment: true
    rationale: "Whether the bullet reads clearly to a user is a language judgment that the phrase check cannot make"
  - id: D4
    description: "Disposition row WR-03 fixed with the GREEN commits of 11-20 and 11-21; open count 8"
    verification:
      - kind: other
        ref: "Task 2 verify 4: disposition frontmatter/table agreement and commit ancestry"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 21: Local action rows of newer versions survive every save Summary

**Rows of the local actions Store that this release cannot parse, and top-level keys other than `records`, are now kept from the last load and written back verbatim after the parsed records on every save. They are never applied, counted or shown. `preserved_device_ids` exposes their device ids for Plan 11-22. WR-03 is fixed.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-10-21T08:11:20Z
- **Completed:** 2026-10-21T08:17:41Z
- **Tasks:** 2
- **Files modified:** 11 (7 source/test/doc/planning files, 4 RED evidence files)

## Accomplishments

- `parse_local_actions_payload` puts every row that fails `parse_local_record` into `ParsedLocalActions.preserved` (deep copies, stored order) and every top-level key other than `records` into `.extra`. `dropped` keeps its meaning: malformed rows plus later duplicates.
- `local_actions_payload(records, *, preserved=(), extra=None)` writes the extra keys first, then `records` = the record rows followed by copies of the preserved rows. An extra key named `records` is ignored. With nothing preserved, the payload is exactly the v1 shape.
- `LocalActionsStore` resets `_preserved`/`_extra` at the start of every load and in `async_remove_records`, sets them only in the success branch, and passes them to every save. Edits, removals, label refreshes and adoption discards all save through `async_save_records`, so none of them can erase what a newer release wrote. `manager.py` is unchanged.
- The load warning now reads "Kept %d local action records of %s that this version cannot read; they are not applied". Duplicates are logged by count separately. No row content is logged.
- README `### Lifecycle` has a new `**Newer versions.**` bullet.

## Final Payload Layout

```
{
  <extra key 1>: <verbatim copy>,      # keys other than "records", in stored order
  ...,
  "records": [
    <parsed record rows, in the order the caller saved them>,
    <preserved rows, verbatim, in stored order>
  ]
}
```

## Task Commits

1. **Task 1 (tracer): rows and keys this release cannot parse survive a local edit end to end**
   - RED `2e6b7ee` test(11-21): add failing tests for local action rows this release cannot parse
   - GREEN `936e0d9` feat(11-21): keep local action rows and keys this release cannot parse on every save
   - Tracer gate: interactive, `end-of-phase`, automated-only verify. All three verify commands were re-run and passed (6 passed; 249 passed in the seven modules; verify 3 OK). Then expansion continued.
2. **Task 2: README note, all tiers, disposition WR-03 fixed**
   - RED `2861a8a` test(11-21): add failing README topic for local actions of newer versions
   - GREEN `161d434` docs(11-21): README says local actions of newer versions are kept and not applied
   - Disposition `bae66d1` docs(11-21): WR-03 fixed by plans 11-20 and 11-21

## RED Evidence and Semantic Assessments

- **Task 1** (`tdd/11-21-task1-red.json`, RED_EVIDENCE_OK): the target `test_rows_this_release_cannot_parse_survive_a_local_edit` ran (1 test, 0 errors, 0 skipped). Hub setup, the owner document, the retained state and the edit all passed. It failed on the planned first assertion: "an edit must not erase a row this release cannot parse". The stored records held only the new ON row. Valid semantic RED, not an import, collection or fixture fault. The other new Store tests failed on `AttributeError` (`preserved_device_ids`, `ParsedLocalActions.preserved`) or on the data assertion. `test_duplicate_identity_rows_are_not_preserved` already passed before GREEN, as expected: it guards against preserving too much.
- **Task 2** (`tdd/11-21-task2-red.json`, RED_EVIDENCE_OK): the target `test_readme_documents_every_local_actions_topic` ran (1 test). All earlier topics passed, and it failed on `'cannot read' (newer versions)`. Valid semantic RED.

## Flagged Assumptions

- **Minor marker loss:** Core's minor-version migration re-saves the raw payload with this release's minor version, so the "newer minor" marker is lost. Preservation does not depend on that marker. It applies to every row that fails parse, whatever its origin. The Manager test seeds `minor_version: 2`, which exercises that path.
- **Same identity later:** a preserved row whose identity equals a record saved later here stays after that record. The newer release's first-row-wins rule then prefers the record saved here, which is the user's latest explicit choice.

## Disposition Change

- `11-REVIEW-DISPOSITION.md`: WR-03 `open` -> `fixed`. Row: `| WR-03 | warning | fixed | plans 11-20 6c09f99, 11-21 936e0d9 |`. Frontmatter `open: 9` -> `open: 8`. WR-01 and WR-02 stay fixed, and WR-04 and IN-01..IN-07 stay open.

## Verification

- Task 1 verify 1: 6 passed. Verify 2 (Store, Store instances, plans, Manager, lifecycle, invariants, hub removal): 249 passed. Verify 3 passed: RED_EVIDENCE_OK, `preserved=self._preserved` and `def preserved_device_ids` are present, no skip/xfail, the RED commit touches no `custom_components/`, and `manager.py` and `config_flow.py` are unchanged.
- Task 2: `tests/test_docs.py` had 36 passed. RED_EVIDENCE_OK, and `ruff check .` and `ruff format --check .` are clean (111 files).
- Full required-broker suite (`MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`, all tiers, nothing deselected), against the 11-20 baseline of 2084:

Full suite: 2090 passed, 2 xfailed

- Accounting: 2084 + 5 new Store tests + 1 new Manager test = 2090. The docs test gained a topic, not a test.
- The disposition verify (frontmatter/table agreement, both hashes are ancestors and are one feat(11-20) and one feat(11-21) commit) passed.

## Must-Haves Prohibition

- "MUST NOT erase, reorder ahead of parsed records, or execute stored local action rows that this release cannot parse" stays flagged `unverified` (judgment). Three tests pin it: the Manager test (kept after an edit, ordered after the record, not counted, not shown, no local run on OFF), the twice-saved byte-equality Store test, and the pure ordering assertion `list(payload) == [*EXTRA, "records"]`.

## Files Created/Modified

- `custom_components/mqtt_actions/local_actions.py`: adds `ParsedLocalActions.preserved` and `.extra`, preservation in `parse_local_actions_payload`, and the keyword-only `preserved`/`extra` of `local_actions_payload`, with updated docstrings.
- `custom_components/mqtt_actions/local_actions_store.py`: adds `_preserved`/`_extra`, the `preserved_device_ids` property, the save pass-through, the reset on load and removal, the kept-count and duplicate warnings, and updated docstrings.
- `tests/test_local_actions_manager.py`: adds `test_rows_this_release_cannot_parse_survive_a_local_edit`.
- `tests/test_local_actions_store.py`: adds the `UNPARSEABLE`/`EXTRA` fixtures, the `_seed_with_extras` helper and five tests.
- `tests/test_docs.py`: adds the `newer versions` topic.
- `README.md`: adds the `**Newer versions.**` Lifecycle bullet.
- `.planning/phases/11-local-actions-on-mirrors/11-REVIEW-DISPOSITION.md`: WR-03 fixed.
- `.planning/phases/11-local-actions-on-mirrors/tdd/11-21-task{1,2}-red.{json,xml}`: RED evidence.

## Decisions Made

- `preserved_device_ids` returns the device id as stored, without stripping, if it is a non-blank string. A padded id matches no device either way, and stripping would make up an id the file does not hold.
- The RED evidence files went into the RED `test(11-21)` commits along with the test files, as in 11-20. The plan says "test files only", but the verify only checks that `custom_components/` is untouched. The evidence files are planning artifacts, not code.

## Deviations from Plan

None. The plan was executed as written. The RED evidence was committed with the RED tests, following the 11-20 convention (see Decisions).

## TDD Gate Compliance

- Each RED `test(11-21)` commit comes before its GREEN: 2e6b7ee before 936e0d9 (feat), and 2861a8a before 161d434 (docs, text only, as the plan specified). No REFACTOR commit was needed.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plan 11-22 (WR-04, the hub-removal warning) can read `LocalActionsStore.preserved_device_ids`.
- Plan 11-22 reads its full-suite baseline from the single result line in the Verification section above (2090).

## Self-Check: PASSED

- All 7 modified files and all 4 RED evidence files exist.
- Commits 2e6b7ee, 936e0d9, 2861a8a, 161d434 and bae66d1 are ancestors of HEAD (5 commits since 05cb9dc).

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*
