---
phase: 04-operations-recovery-and-release
plan: 02
subsystem: trust
tags: [approval-hash, repairs, sha256, circuit-breaker, run-mode, readme]

requires:
  - phase: 03-multi-instance-sync
    provides: actions_hash approval gate, ApprovalView and the Repairs approval flow
provides:
  - actions_hash that binds run mode, both circuit breaker limits, the startup flag and the trigger mapping
  - approval dialog that shows run mode and both breaker limits (en and de)
  - README sentence about what the approval binds, including the one-time lapse of old approvals
  - tests/test_docs.py as the home of documentation checks of this phase
affects: [04-operations-recovery-and-release, trust, release]

actuals:
  tokens: 6297
  tasks: 2
  commits: 4
plan_head_before: 1cd686111190c20e89043d19e3a40dfa4e02ac84
plan_head_after: 83a71b9b46acb5520b52708871462abaccc95e86

tech-stack:
  added: []
  patterns:
    - "Approval hash derived locally from received content: widening what it binds needs no wire or SCHEMA_VERSION change"
    - "Documentation checks as tests: tests/test_docs.py reads README bullets and asserts the phrases a claim needs"

key-files:
  created:
    - tests/test_docs.py
  modified:
    - custom_components/mqtt_actions/document.py
    - custom_components/mqtt_actions/trust.py
    - custom_components/mqtt_actions/repairs.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - README.md
    - tests/test_document.py
    - tests/test_trust.py
    - tests/test_translations.py
    - tests/test_repairs_flow.py

key-decisions:
  - "run_mode, breaker_max_runs and breaker_window are bound into actions_hash (D-16); a rename is still not"
  - "No migration code: old approvals stop matching, the mirror loses its Script and Repairs asks once more"
  - "Wire format, content_hash and SCHEMA_VERSION untouched: the approval hash is never read from the wire"

patterns-established:
  - "A claim in the README about the trust model gets a test that fails when the sentence stops naming the facts"

requirements-completed: [SYN-09]

coverage:
  - id: D1
    description: "Changing the run mode or a breaker limit of an approved mirror stops it and raises a new approval request with the new hash; a rename keeps the approval"
    requirement: SYN-09
    verification:
      - kind: unit
        ref: "tests/test_document.py#test_actions_hash_binds_mapping_startup_run_mode_and_breaker"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_run_mode_or_breaker_change_lapses_the_approval"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_rename_keeps_the_approval"
        status: pass
    human_judgment: false
  - id: D2
    description: "Approvals stored under the old hash format lapse once: no Script, no action run, a new approval request; approving the new hash runs again"
    requirement: SYN-09
    verification:
      - kind: integration
        ref: "tests/test_trust.py#test_approval_of_the_old_hash_format_lapses_once"
        status: pass
    human_judgment: false
  - id: D3
    description: "The approval dialog shows run mode and both breaker limits in English and German"
    requirement: SYN-09
    verification:
      - kind: unit
        ref: "tests/test_trust.py#test_view_shows_run_mode_and_breaker_limits"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_confirm_form_placeholders_include_settings"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_issue_strings_use_expected_variables"
        status: pass
    human_judgment: false
  - id: D4
    description: "The README bullet about the approval names the actions, the startup flag, the run mode and the circuit breaker limits and states the one-time lapse"
    requirement: SYN-09
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_states_what_the_approval_hash_binds"
        status: pass
    human_judgment: false
  - id: D5
    description: "The wording of the German and English dialog paragraph reads naturally to a user"
    requirement: SYN-09
    verification: []
    human_judgment: true
    rationale: "Tests pin the placeholders and key parity, not the quality of the prose"

duration: 5min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 02: Approval hash binds run mode and breaker limits Summary

**`actions_hash` now covers run mode and both circuit breaker limits next to the startup flag and the trigger mapping, so a forger of the config topic can no longer switch an approved mirror to restart mode or raise its breaker limit without a new approval; the dialog shows the three values and the README says exactly what the hash binds**

## Performance

- **Duration:** 5 min
- **Started:** 2026-10-02T07:29:00Z
- **Completed:** 2026-10-02T07:35:00Z
- **Tasks:** 2
- **Files modified:** 11 (1 created)

## Accomplishments
- `document.py`: `actions_hash` includes `run_mode`, `breaker_max_runs` and `breaker_window`; docstrings updated (A5 revised by D-16). `content_hash`, `build_document`, `parse_document`, `SCHEMA_VERSION` and every wire field are untouched.
- Lapse needs no new code: `parse_document` recomputes the hash, the mirror Script gate compares it with the stored approval and `_sync_approval_issues` raises the new request. Verified end to end for all three settings and for an approval stored under the old formula.
- `ApprovalView` carries `run_mode`, `breaker_max_runs`, `breaker_window`; the confirm step of the Repairs flow supplies them as placeholders; the confirm description in `en.json` and `de.json` states them and that a change of any asks again.
- README: the trust-model bullet names the actions, the startup flag, the run mode and the circuit breaker limits, says a rename does not change the hash and that earlier approvals lapse once after the upgrade.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Tracer, a changed run mode or breaker limit lapses the approval end to end** - `557a271` (test), `0a41bff` (feat)
2. **Task 2: The dialog shows what the hash binds, old approvals lapse once, README states it** - `0c611fe` (test), `83a71b9` (feat)

**Plan metadata:** committed with this summary (docs: complete plan)

## TDD Gate Compliance

RED precedes GREEN for both tasks. Task 1 RED failed on the planned assertion (`actions_hash(...) != base_hash` for a run mode change, and the changed hash for each of the three parametrized cases). Task 2 RED failed on the planned assertions for the view attribute, the placeholder set in the flow and translation tests, and the README bullet (`the approval bullet never names startup flag`). One test, `test_approval_of_the_old_hash_format_lapses_once`, already passed at Task 2 RED because Task 1's GREEN had changed the hash; it is a regression guard for the prohibition "a mirror whose stored approval carries the old hash runs nothing", not a driver of new behavior. No refactor commits were needed. Tracer gate: the Task 1 verify chain (targeted tests, full suite, ruff check, ruff format check) was run green after the GREEN commit before expansion.

## Files Created/Modified
- `custom_components/mqtt_actions/document.py` - `actions_hash` over kind, startup flag, run mode, breaker limits and sorted trigger pairs
- `custom_components/mqtt_actions/trust.py` - `ApprovalView` fields for the three settings, filled from the spec
- `custom_components/mqtt_actions/repairs.py` - three new description placeholders on the confirm form
- `custom_components/mqtt_actions/translations/en.json`, `de.json` - confirm description paragraph with the three variables
- `README.md` - trust-model bullet about what the approval binds and the one-time lapse
- `tests/test_docs.py` - new; README bullet check
- `tests/test_document.py`, `tests/test_trust.py`, `tests/test_translations.py`, `tests/test_repairs_flow.py` - flipped and new tests

## Decisions Made
- Followed the plan's assumptions: no migration code, `run_mode` rendered as the stored word and the limits as plain numbers, `MODE_*` naming reserved for the later D-14 per-device mode.
- Dialog wording uses "pauses" for the breaker (matches the existing config-flow text and the breaker behavior: the next run beyond the limit trips and does not run), with "more than N runs within M seconds".

## Deviations from Plan

None - plan executed exactly as written. (Small adjustments inside the planned work: the two docstrings of the new tests were shortened for the 120-character limit, and `tests/test_docs.py` checks the README bullet by splitting list items rather than a regex over the whole text, so the "bound to the hash" bullet is found as one unit.)

## Issues Encountered
None. The pre-existing uncommitted change to `.planning/config.json` was left untouched and is not part of any commit of this plan.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path or trust boundary; T-04-06 and T-04-07 of the plan are mitigated and pinned by tests, T-04-08 is accepted as planned (one request per approved mirror after the upgrade, bounded by MAX_MIRRORS).

## User Setup Required

None - no external service configuration required. After upgrading, every previously approved mirror stops running once and Repairs shows a new approval request (explained in the README).

## Next Phase Readiness
- The approval now binds everything that governs execution frequency and mode, so the operations tools of the next plans (re-trigger, recovery) can rely on an honest approval.
- `tests/test_docs.py` exists for the documentation checks of later plans in this phase.

## Self-Check: PASSED

- Files exist: `custom_components/mqtt_actions/document.py`, `trust.py`, `repairs.py`, both translation files, `README.md`, `tests/test_docs.py` found on disk.
- Commits found in `git log`: `557a271`, `0a41bff`, `0c611fe`, `83a71b9`; `test(04-02)` precedes `feat(04-02)` for both tasks.
- Acceptance: `grep -c CONF_BREAKER_MAX_RUNS document.py` prints 4 (at least 3); `grep -c breaker_max_runs` prints 11 for both `en.json` and `de.json`.
- Plan verification re-run: `uv run pytest tests -q` 846 passed; `ruff check` and `ruff format --check` clean.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
