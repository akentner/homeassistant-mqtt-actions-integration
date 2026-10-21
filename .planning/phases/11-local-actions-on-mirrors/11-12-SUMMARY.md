---
phase: 11-local-actions-on-mirrors
plan: 12
subsystem: docs
tags: [local-actions, documentation, downgrade, release-notes, tdd]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-06: adopt_device response key local_actions_discarded, prune/tombstone/adoption lifecycle"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-07: local_action_failed issue, run_manual gate, error/no_actions for muted triggers"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-08: hub options menu and local actions editor texts"
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-09: removal warning placeholder and count-only diagnostics keys"
provides:
  - "README section 'Local actions on mirrored devices' covering every MIR-15 topic, with a 'Downgrading to 1.0.1' warning alert"
  - "docs/operations.md adopt_device row and Adoption text with local_actions_discarded; re-trigger answers for local actions"
  - "docs/troubleshooting.md local_action_failed entry with the continue_on_error rule and exact clear conditions"
  - "5 static docs tests in tests/test_docs.py, including an AST check that the adopt_device row equals the handler's response keys"
  - ".planning/phases/11-local-actions-on-mirrors/11-release-notes.md (unpublished draft for Phase 12)"
affects: [11-13, 12]

# Actuals (#2632)
actuals:
  tokens: 9600
  tasks: 2
  commits: 3
plan_head_before: cf4a3ba391350a599cb80863faec1b21e5cae18a
plan_head_after: 895de85b0a49ef4a17a741f98bebbc0acfc93c85

tech-stack:
  added: []
  patterns:
    - "Docs contract read from source: the adopt_device response keys come from the handler's return dict through ast, so the docs row cannot drift"
    - "GitHub alert boxes (> [!WARNING]) for prominent warnings; docs tests strip blockquote markers before phrase checks"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/11-release-notes.md
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-12-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-12-task1-red.xml
  modified:
    - README.md
    - docs/operations.md
    - docs/troubleshooting.md
    - tests/test_docs.py

key-decisions:
  - "The downgrade warning is a GitHub [!WARNING] alert in its own README subsection, linked from a second alert at the top of the local actions section and from Limitations"
  - "The downgrade text says 'by design' the separate Store returns after an upgrade and that the round trip has not been verified (MIR-F4); a regex test rejects any 'round trip was/has been verified' claim in the README"
  - "docs/diagnostics.md was left unchanged: Plan 11-09 already documents all six local-actions keys and the existing docs test enforces them"
  - "The adopt_device docs row is checked against the handler's return dict via ast, not against a hand-written key list"

patterns-established:
  - "Phrase checks for a README section use _plain(): normalized, blockquote markers, backticks and emphasis removed"

requirements-completed: [MIR-08, MIR-15]

coverage:
  - id: D1
    description: "README 'Local actions on mirrored devices' covers navigation, additive/replacement/mute, local trust and owner-only approval, safe defaults, gates, parallel completion/error-stop/response-variable sharing, orphan/kind identity, prune/tombstone/adoption/integration removal, local Repairs with continue_on_error, count-only diagnostics and the {{ state }} caveat"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_every_local_actions_topic"
        status: pass
    human_judgment: false
  - id: D2
    description: "Prominent downgrade warning: v1.0.1 ignores replacement and mute, approved owner actions may run again, separate local data returns by design, round trip unverified and deferred (MIR-F4); no verified-round-trip claim"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_warns_prominently_about_a_downgrade_to_1_0_1"
        status: pass
    human_judgment: false
  - id: D3
    description: "docs/operations.md adopt_device row lists exactly the handler's response keys, local_actions_discarded included; Adoption and Re-trigger sections explain local actions"
    requirement: MIR-08
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_operations_adopt_row_names_every_response_key"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_operations_re_trigger_section_explains_local_actions"
        status: pass
    human_judgment: false
  - id: D4
    description: "Troubleshooting local_action_failed entry: continue_on_error still raises the issue; only a later successful run of the same trigger or removing the customization clears it"
    requirement: MIR-08
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_troubleshooting_explains_when_the_local_failure_issue_clears"
        status: pass
    human_judgment: false
  - id: D5
    description: "Unpublished v1.1 release-note draft with the downgrade warning and the MIR-F4 deferral; no version, tag or release change"
    verification:
      - kind: command
        ref: "Task 2 <automated> gate (first line, v1.0.1, MIR-F4, no verified claim)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Readability and tone of the new README section and the release draft for end users (en)"
    human_judgment: true
    rationale: "No test can judge whether the wording is clear enough; reviewed in UAT / Phase 12 before publication"

# Metrics
duration: 12 min
completed: 2026-10-21
---

# Phase 11 Plan 12: Local Actions Documentation and Downgrade Boundary Summary

**The README now has a "Local actions on mirrored devices" section. It covers every MIR-15 topic and ends with a `[!WARNING]` alert for downgrading to 1.0.1: replacement and mute are ignored, approved owner actions may run again, and the round trip is unverified and deferred as MIR-F4. operations.md lists `local_actions_discarded` as an `adopt_device` response key, checked against the handler's source through AST. Troubleshooting states the `continue_on_error` rule and the exact clear conditions. An unpublished release-note draft is ready for Phase 12.**

## Performance

- **Duration:** about 12 min (2026-10-21T03:02:37Z to 03:14:30Z)
- **Tasks:** 2 (1 tracer TDD, 1 auto). Commits: 1 RED, 1 GREEN and 1 docs. No refactor was needed.
- **Files:** 3 docs and 1 test module modified, 1 release draft and 2 evidence files created.

## Documentation sections

README.md:
- Intro: a link to the new section.
- **Local actions on mirrored devices.** It has a top alert that links the downgrade subsection, plus these subsections:
  - Editing local actions: navigation, the three modes, removing a customization, and picker markers in the server language.
  - Trust, approval and the gates: no approval for local actions, approval for owner actions only, the replaced count in the request, safe defaults (startup off, `serial`, 5 runs in 10 seconds), observe/disabled/breaker, release on save or remove, and the test press and re-trigger rules.
  - Parallel runs: the sibling still finishes, `stop`/error-stop end the run after the sibling, and response variables share one namespace.
  - The `{{ state }}` variable: the canonical StateValue versus a live `states()` lookup, with a YAML example.
  - Lifecycle: owner changes, removed options (orphan, edit, reattach), device kind, start and prune, tombstone, adoption, and integration removal with the device count.
  - Local failures and diagnostics: `local_action_failed`, the `continue_on_error` rule, the clear conditions, and count-only diagnostics.
  - **Downgrading to 1.0.1:** a `[!WARNING]` alert.
- Operations (Adoption bullet), Deleting devices and removing the integration, and Limitations (two new bullets).

docs/operations.md:
- The `adopt_device` row now lists `uuid`, `adopted`, `previous_owner` and `local_actions_discarded`.
- The Adoption section explains the discard: the count, the log line, that a local customization is no approval, and that a failed adoption restores the records.
- The Re-trigger section has a new "Local actions" bullet: `executed` for local-only, `error`/`no_actions` for muted, `paused` for a tripped breaker, and no new words.

docs/troubleshooting.md: the existing `local_action_failed` entry is extended, not duplicated. It now covers:
- invalid saved actions;
- the `continue_on_error` rule;
- independence from `action_failed` in additive mode;
- a single clear rule: only a later successful run of the same trigger, or removing the customization;
- what does not clear it: `stop`, cancelled or superseded runs;
- removal of the mirror or of the integration.

docs/diagnostics.md is unchanged. It was already consistent with Plan 11-09, and `test_diagnostics_page_lists_the_included_keys_and_the_exclusions` enforces it.

## New docs checks (tests/test_docs.py)

| Test | Pins |
|------|------|
| `test_readme_documents_every_local_actions_topic` | 19 topic groups of phrases in the README local section |
| `test_readme_warns_prominently_about_a_downgrade_to_1_0_1` | the `> [!WARNING]` alert, 1.0.1 ignores replacement and mute, owner actions may run again, separate data available again, "not been verified", "deferred", MIR-F4, a Limitations bullet, no `VERIFIED_ROUND_TRIP` match and no "phase 12" in the README |
| `test_operations_adopt_row_names_every_response_key` | every key of the `_async_handle_adopt` return dict (read via `ast`) is in the `adopt_device` row; the Adoption section explains the discard |
| `test_operations_re_trigger_section_explains_local_actions` | local actions, muted, `no_actions`, no new status words |
| `test_troubleshooting_explains_when_the_local_failure_issue_clears` | `local_action_failed` is a translated issue, so the existing per-key test covers it; the entry states the `continue_on_error` and clear rules |

No existing assertion changed. The only edits to existing code are a new `import ast` and the `SERVICES_PY` path constant.

## Release draft

`.planning/phases/11-local-actions-on-mirrors/11-release-notes.md`:
- The first line is `Status: Unpublished draft (version, tag and publication belong to Phase 12)`.
- It repeats the downgrade warning: v1.0.1 ignores replacement and mute, so approved owner actions may run again. It says the bench round trip is deferred as MIR-F4 and has not been run.
- It summarizes local actions, the trust boundary, count-only diagnostics and the adoption response key.
- It hands version, tag, publication and QLT-05 to Phase 12.

No version, tag or release changed. `manifest.json` stays at 1.0.1.

## TDD Gate Compliance

| Task | RED commit | Target node | Classifier | GREEN | REFACTOR |
|------|-----------|-------------|-----------|-------|----------|
| 1 (tracer) | `dadf654` | `tests/test_docs.py::test_readme_documents_every_local_actions_topic` | RED_EVIDENCE_OK (junit, 1 test, 1 failure) | `b692e2d` | none needed |
| 2 (auto, not tdd) | - | - | n/a | `895de85` | - |

- **RED semantic assessment:** valid. The target ran and failed on its first planned assertion, because the README had no local actions section. There was no import, fixture or collection fault. In the same suite run, 5 failed and 28 passed. The other four new tests failed for their planned reasons:
  - the downgrade section was missing;
  - `local_actions_discarded` was missing from the row;
  - the Re-trigger section did not mention local actions;
  - the troubleshooting entry did not mention `continue_on_error`.

  Record: `tdd/11-12-task1-red.{xml,json}`.
- **GREEN adjustments to the new tests only** (made in the GREEN commit):
  - `_plain` now strips `> ` blockquote markers. The alert's line wrap had split "not been verified".
  - The troubleshooting phrase "removing the device" became "the issue goes with it", to match the final, more precise wording (the mirror goes by tombstone, prune or adoption).
- **Non-vacuity probe:** the README was copied to the scratchpad and mutated twice, then restored byte for byte (`cmp`). Neither mutation was committed.
  - "round trip was verified" made the downgrade test fail.
  - `[!NOTE]` in place of `[!WARNING]` made it fail too.
- **Tracer gate:** `uv run pytest -q tests/test_docs.py tests/test_diagnostics.py` re-ran with 45 passed before Task 2.

## Verification

- Task 1: `uv run pytest -q tests/test_docs.py tests/test_diagnostics.py` gave 45 passed.
- Task 2: the release-draft gate printed `VERIFY_PASS`. It checks the first line, `v1.0.1`, `MIR-F4` and that there is no verified/passed/confirmed claim.
- Full tiers, with no `--deselect`:
  - Unit (`-m "not broker and not multi_instance"`): 1858 passed, 2 xfailed.
  - Multi-instance: 180 passed.
  - Broker: 18 passed.
  - Total: 2056 passed, 2 xfailed. That is the previous 2051 plus 5 new docs tests.
- `uv run ruff check .` and `ruff format --check .` are clean.
- No release action ran: no manifest bump, no tag, nothing published.

## Task Commits

1. **Task 1 (tracer): docs contract and docs.** `dadf654` (test), `b692e2d` (feat).
2. **Task 2: unpublished release-note draft.** `895de85` (docs).

## Deviations from Plan

### Notes (no auto-fixes to product code)

**1. [Scope] docs/diagnostics.md unchanged**
- It is in `files_modified`, but Plan 11-09 already documented every key and the exclusion sentence.
- Keeping it consistent needed no edit.

**2. [Test] Blockquote-aware phrase matching**
- **Found during:** Task 1 GREEN.
- **Issue:** the line break inside the `[!WARNING]` alert put `> ` between "not been" and "verified".
- **Fix:** `_plain()` strips leading blockquote markers. The fix lives in the new helper only, and no existing helper changed.
- **Commit:** `b692e2d`

**3. [Commit type] GREEN of a documentation task**
- The GREEN commit uses `feat(11-12)` to follow the TDD commit-scope contract, although the change is user documentation.

**4. [Verification note] Wrong pytest flag in the first unit-tier run**
- The first unit-tier run used `-p no:logging`, which disables the `caplog` fixture and produced 60 setup errors that the plan did not cause.
- The re-run without the flag passed completely: 1858 passed, 2 xfailed.

**Total deviations:** 0 auto-fixed product issues, plus 1 scope note, 1 test-helper fix, 1 commit-type note and 1 verification note. **Impact:** none on product behavior.

## Prohibition check (D-09, T-11-29)

The README and the release draft never claim that the real v1.1 to v1.0.1 to v1.1 round trip, or any Phase 12 final-build verification, was performed:
- the README says "has not been verified on real instances; that check is deferred (MIR-F4)";
- the draft says "deferred as MIR-F4 and has not been run".

A test rejects any verified-round-trip claim and any "phase 12" mention in the README.

## Known Stubs

None.

## Threat Flags

None. The only surface is T-11-29 (documentation to user expectations), which this plan mitigates as described above.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- Plan 11-13 (UAT / cross-file review) can read the user-facing wording of the README section and the release draft (coverage D6, human judgment).
- Phase 12 finalizes the version, tag and publication from `11-release-notes.md`. The MIR-F4 round trip stays deferred.

## Self-Check: PASSED
