---
phase: 10-review-findings-and-native-migration-extraction
plan: 08
subsystem: docs
tags: [fix-05, review-1-in-01, duplicate-guard, discovery-export, docs, doc-tests, tdd]
status: complete

requires:
  - phase: 10-review-findings-and-native-migration-extraction
    provides: "plan 10-04 (NativeMigration.arm_duplicate_guard, whose start-up sweep is the stated behavior)"
provides:
  - "README.md, section MQTT Discovery export: the re-enable sentence with both guard exceptions"
  - "docs/troubleshooting.md, section An enabled duplicate after the export prefix was set to the core prefix: the same sentence"
  - "tests/test_docs.py: two FIX-05 doc tests pinning both statements"
affects: [10-10 (adds that the kept duplicates are listed in Repairs, next to this sentence)]

actuals:
  tokens: 1214
  tasks: 2
  commits: 4
plan_head_before: 101fc73fd15636eddec64c3dbf6a89ce8ace0541
plan_head_after: 4f616ae1752133591a0aa71237391c2332c38e81

tech-stack:
  added: []
  patterns:
    - "Doc claim pinned by a phrase test on the normalized markdown section (_normalize(_section(...)) with backticks removed)"

key-files:
  created:
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-08-task1-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-08-task1-red.json
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-08-task2-red.xml
    - .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-08-task2-red.json
  modified:
    - README.md
    - docs/troubleshooting.md
    - tests/test_docs.py

key-decisions:
  - "FIX-05 wording as in the plan's Decisions section, in both documents: a duplicate the user enables again is disabled again at the next start of MQTT Actions (restart or reload), unless it is customized (name, area) or the native entity is turned off; the docs keep advising to disable by hand, never to delete"
  - "The phrase 'disabled again at the next start' is kept on one physical line in both files, so the plan's line-based grep check and the normalized doc test both find it"

patterns-established: []

requirements-completed: [FIX-05]

coverage:
  - id: D1
    description: "README MQTT Discovery export section says a re-enabled duplicate is disabled again at the next start, with both exceptions; RED before the sentence existed"
    requirement: FIX-05
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_the_readme_says_a_re_enabled_duplicate_is_disabled_again_at_the_next_start"
        status: pass
      - kind: other
        ref: "node ~/.claude/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-08-task1-red.json --raw"
        status: pass
    human_judgment: false
  - id: D2
    description: "Troubleshooting enabled-duplicate section says the same, next to its advice to disable by hand; RED before the sentence existed"
    requirement: FIX-05
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_troubleshooting_says_a_re_enabled_duplicate_is_disabled_again_at_the_next_start"
        status: pass
      - kind: other
        ref: "node ~/.claude/gsd-core/bin/gsd-tools.cjs check tdd-red-evidence .planning/phases/10-review-findings-and-native-migration-extraction/tdd/10-08-task2-red.json --raw"
        status: pass
    human_judgment: false
  - id: D3
    description: "The sentence matches the guard's actual behavior and does not advise deleting an MQTT entity (CR-01)"
    requirement: FIX-05
    human_judgment: true
    rationale: "Wording accuracy against NativeMigration.arm_duplicate_guard and the WR-02/WR-03 exceptions is a reading judgment; the guard tests pin the behavior, no test pins that the prose matches it"

duration: 5min
completed: 2026-10-16
---

# Phase 10 Plan 08: FIX-05 re-enable sentence Summary

**README and troubleshooting now say that a duplicate the user enables again is disabled again at the next start or reload of MQTT Actions. They name the two exceptions: a customized row and a turned-off native entity. Two RED-first doc tests in `tests/test_docs.py` pin the statement. No product code changed.**

## Performance

- **Duration:** about 5 min
- **Started:** 2026-10-16T14:07:11Z
- **Completed:** 2026-10-16T14:12Z
- **Tasks:** 2
- **Files modified:** 3 (plus 4 RED records)

## Accomplishments

- README `MQTT Discovery export`: the re-enable sentence sits right before "If you still find an enabled duplicate, disable it".
- `docs/troubleshooting.md` `An enabled duplicate after the export prefix was set to the core prefix`: the same sentence sits right after "points to a row you enabled yourself or to a device that the instance does not hold natively".
- `test_the_readme_says_a_re_enabled_duplicate_is_disabled_again_at_the_next_start` and `test_troubleshooting_says_a_re_enabled_duplicate_is_disabled_again_at_the_next_start` each check the normalized section for `disabled again at the next start`, `unless you customized it` and `turned the native entity off`.

## Task Commits

1. **Task 1 (tracer): README sentence**
   - RED `0754c10`: `test(10-08): the README says a re-enabled duplicate is disabled again at the next start (FIX-05)`
   - GREEN `6ae075a`: `docs(10-08): say that a re-enabled duplicate is disabled again at the next start (FIX-05)`
   - Tracer gate (end-of-phase, automated-only verify): `<verify>` was re-run and passed, so the plan moved on to Task 2.
2. **Task 2: troubleshooting sentence**
   - RED `46d7732`: `test(10-08): troubleshooting says a re-enabled duplicate is disabled again at the next start (FIX-05)`
   - GREEN `4f616ae`: `docs(10-08): troubleshooting says a re-enabled duplicate is disabled again at the next start (FIX-05)`

## TDD Gate Compliance

- **RED:** both targets ran (1 test, 1 failure, 0 errors each). Each failed on its first phrase assertion with its own message, "never says: disabled again at the next start". The section lookups returned non-empty text, so neither failure was an empty section, an import, a collection or a fixture fault. Both records (`tdd/10-08-task1-red.json`, `tdd/10-08-task2-red.json`) return `RED_EVIDENCE_OK`.
- **GREEN:** the plan names `docs(10-08): ...` as the GREEN commit type because the change is documentation only. There is therefore no `feat(10-08)` commit, by design. Each `test(10-08)` commit comes before its `docs(10-08)` commit.
- **REFACTOR:** none needed.

## Files Created/Modified

- `README.md`: the re-enable sentence, paragraph tail rewrapped to 120 columns
- `docs/troubleshooting.md`: the re-enable sentence, the affected lines rewrapped to 120 columns
- `tests/test_docs.py`: the two FIX-05 doc tests
- `tdd/10-08-task{1,2}-red.{xml,json}`: RED records

## Decisions Made

- The wording follows the plan's Decisions section in both files. The docs still advise disabling an enabled duplicate by hand or switching the prefix back. They never advise deleting an MQTT entity (CR-01).
- The README line break was placed before `**Devices & services**`, so the bold label is not split across lines.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Kept the pinned phrase on one physical line in troubleshooting**
- **Found during:** Task 2, GREEN gate
- **Issue:** the first wrap of the troubleshooting paragraph split "disabled again at" and "the next start" across two lines. The plan's `<verify>` check `grep -q "disabled again at the next start" docs/troubleshooting.md` works line by line and failed, even though the normalized doc test passed.
- **Fix:** moved the line break so the phrase sits on one line. The wording did not change.
- **Files modified:** docs/troubleshooting.md (before its commit)
- **Commit:** 4f616ae

**Total deviations:** 1 auto-fixed (line wrap only). **Impact:** none on the content.

## Issues Encountered

None.

## Known Stubs

None.

## Verification

- `uv run pytest -q tests/test_docs.py`: 27 passed
- `grep -q "disabled again at the next start"` succeeds on README.md and docs/troubleshooting.md
- `git diff --quiet -- custom_components/`: clean, no product change
- `uv run ruff check .`: all checks passed. `uv run ruff format --check .`: 98 files already formatted
- `uv run pytest -q`: 1743 passed, 2 xfailed (baseline 1741 + 2 new doc tests)

## Next Phase Readiness

Ready for 10-09. Plan 10-10 adds, next to this sentence, that the kept duplicates are listed in Repairs.

## Self-Check: PASSED

- FOUND: README.md, docs/troubleshooting.md, tests/test_docs.py, tdd/10-08-task1-red.{xml,json}, tdd/10-08-task2-red.{xml,json}
- FOUND commits: 0754c10, 6ae075a, 46d7732, 4f616ae (all ancestors of HEAD)
