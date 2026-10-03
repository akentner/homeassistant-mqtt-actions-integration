---
phase: 04-operations-recovery-and-release
plan: 14
subsystem: infra
tags: [hassfest, translations, repairs, release-gate, gap-closure, tdd]

requires:
  - phase: 04-operations-recovery-and-release
    provides: the three fixable Repairs issues (approval_required from phase 3, duplicate_instance_id and transferred from 04-12), the release workflow that needs validate (04-01)
provides:
  - en.json and de.json where approval_required, duplicate_instance_id and transferred carry title and fix_flow only
  - the cause, shared-topics and adoption explanation merged into the confirm step of duplicate_instance_id and transferred
  - a local guard (test_issue_has_one_text_source) that models the hassfest text-source rule for all 13 issues in both languages, with a self-test
  - a hassfest container run that exits 0 with no invalid integration
affects: [release v0.1.0, 04-VERIFICATION success criterion 5, Validate workflow]

actuals:
  tokens: 5500
  tasks: 2
  commits: 4
plan_head_before: 0e32d0160bbfd842cb3b3b6832c1bbb3c3a27149
plan_head_after: e6d69cdd90bf607350fa3322ae220e0cdaa52319

tech-stack:
  added: []
  patterns:
    - "A fixable Repairs issue shows its text only in fix_flow.step.<step>.description; an issue-level description next to fix_flow is rejected by hassfest (exclusion group 'fixable')"
    - "A CI-only validator rule is modeled by a local structural test with a synthetic-violation self-test, so the guard cannot pass vacuously"

key-files:
  created: []
  modified:
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_translations.py

key-decisions:
  - "The issue-level description of the three fixable issues is removed and the explanation moves into the confirm step; the workflows, docs, repairs.py, manager.py and sync.py stay untouched"
  - "approval_required merges nothing: its confirm description already holds every fact of the removed text"
  - "The sentences 'Open this repair ...' and 'Nothing changes until you confirm' are dropped on purpose, each confirm step ends with its own 'nothing happens until you submit'"
  - "ISSUES is read from en.json at import time, so a new issue is guarded without touching the test"

patterns-established:
  - "Pattern: FIXABLE_ISSUES (issue to confirm-step variables) and FIXABLE_WORDING (issue to language to pinned phrases) keep fixable issue text complete in both languages"

requirements-completed: [OPS-05]

coverage:
  - id: D1
    description: "hassfest accepts the translations: no issue carries both description and fix_flow, the container run exits 0 with Invalid integrations: 0"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_issue_has_one_text_source"
        status: pass
      - kind: other
        ref: "docker run --rm -v \"$PWD\":/github/workspace:Z ghcr.io/home-assistant/hassfest (exit 0)"
        status: pass
    human_judgment: false
  - id: D2
    description: "No explanation is lost: the confirm steps of duplicate_instance_id and transferred gain the removed text, en and de keep the same keys and placeholders"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_fixable_issue_text_keeps_its_explanation"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_en_and_de_have_identical_keys"
        status: pass
    human_judgment: false
  - id: D3
    description: "The guard detects a synthetic violation and covers all 13 issues in both languages"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_issue_guard_detects_the_hassfest_violations"
        status: pass
    human_judgment: false
  - id: D4
    description: "Validate (hassfest and HACS) is green on the pushed phase branch, so the release job can pass its validate requirement"
    requirement: OPS-05
    verification: []
    human_judgment: true
    rationale: "The branch is not on origin and this plan does not push; the green GitHub run is an end-of-phase human check"

duration: 15min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 14: hassfest translation gap closure Summary

**The three fixable Repairs issues keep title and fix_flow only, the removed issue-level text now lives in their confirm steps, and a local guard checks the hassfest text-source rule for all 13 issues in en and de; the hassfest container exits 0.**

## Performance

- **Duration:** about 15 min
- **Completed:** 2026-10-02
- **Tasks:** 2 (a tracer and an expansion)
- **Files modified:** 3

## Accomplishments

- Closed the one verified gap of 04-VERIFICATION.md: the hassfest container went from exit 1 with three `fixable` errors to exit 0 and `Invalid integrations: 0`, so the Validate gate in front of `release.yml` is no longer red for this reason.
- `duplicate_instance_id` and `transferred` open their confirm step with the explanation that used to be the issue-level description (cause, shared topics, adoption, stopped publishing, local ownership). `approval_required` lost only the obsolete call to action.
- `test_issue_has_one_text_source` runs over every issue of en.json (13 issues, 26 tests) and `test_issue_guard_detects_the_hassfest_violations` pins the guard to the rule on synthetic data. `test_fixable_issue_text_keeps_its_explanation` pins key phrases per issue and language.

## Task Commits

1. **Task 1 (tracer): duplicate instance id** - RED `4cc1d8f` (test), GREEN `6058ee4` (feat)
2. **Task 2: approval and transferred, guard widened** - RED `48b17b5` (test), GREEN `e6d69cd` (feat)

The tracer feedback gate was the automated verify (full suite, Ruff, hassfest container naming only the other two issues); it passed and the expansion ran.

**Plan metadata:** committed with this summary (docs: complete plan)

## Files Created/Modified

- `custom_components/mqtt_actions/translations/en.json` - issue-level description removed from three issues; confirm steps of duplicate_instance_id and transferred extended
- `custom_components/mqtt_actions/translations/de.json` - same structure, German sentences reused from the removed descriptions
- `tests/test_translations.py` - `_raw`, `_issue_problems`, `ISSUES`, `FIXABLE_ISSUES`, `FIXABLE_WORDING`, three new tests; `NEW_ISSUES` reduced to the seven issues that keep an issue-level description

## Decisions Made

See key-decisions. All followed the plan; edits were exact string replacements, the JSON was never re-serialized.

## Deviations from Plan

None - plan executed exactly as written. The hassfest container reported no further translation error after Task 2.

Verification evidence: `uv run pytest tests -q` 1257 passed, Ruff check and format clean, hassfest container exit 0, `git diff --name-only 19ae5d6 -- .github docs README.md repairs.py manager.py sync.py` prints nothing, `jq` shows no issue with both keys and 13 issues with text in both languages.

## Issues Encountered

None.

## Known Stubs

None.

## Human Check (end of phase)

The phase branch is not on origin. After pushing, confirm Validate is green: `gh run list --workflow Validate --branch gsd/phase-04-operations-recovery-and-release --limit 1 --json status,conclusion,headSha`, and both hassfest and HACS jobs show success. The first tag v0.1.0 stays a separate end-of-phase check from 04-VERIFICATION.md.

## Next Phase Readiness

Gap closed locally. Remaining: push, green Validate run, first tag (human checks).

## Self-Check: PASSED

- `custom_components/mqtt_actions/translations/en.json`, `de.json`, `tests/test_translations.py` exist and are committed
- Commits 4cc1d8f, 6058ee4, 48b17b5, e6d69cd exist; `git rev-list --count` from the ledger base gives 4
