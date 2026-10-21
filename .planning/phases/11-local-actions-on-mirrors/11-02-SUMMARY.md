---
phase: 11-local-actions-on-mirrors
plan: 02
subsystem: ui
tags: [frontend-smoke, options-flow, section, action-selector, playwright, translations]
status: complete

# Dependency graph
requires:
  - phase: 11-local-actions-on-mirrors
    provides: "Plan 11-01: Core 2026.9.4 pins and the planned per-trigger section shape"
provides:
  - Versioned evidence that Core 2026.9.4 / frontend 20260826.7 renders a section with a mode SelectSelector and an ActionSelector, round-trips values and shows a base alert, in en and de
  - Human-approved PASS verdict for the D-22 frontend gate (blocking-human), which unblocks the full options editor in Plan 11-08
  - Four rendering findings that Plan 11-08 must adopt (collapsed state, hidden ActionSelector data_description, base-error channel, raw selector data)
affects: [11-08, 11-13]

# Actuals (#2632)
actuals:
  tokens: 1909
  tasks: 2
  commits: 2
plan_head_before: d1b35459cb143d9ba1d0d4c765393871058420b4
plan_head_after: 1c920ffd7e38207efa7a8658b7007d54bab05e9b

tech-stack:
  added: []
  patterns:
    - "Frontend assumptions are proven on the pinned Core/frontend pair with a disposable bench-only integration, never with a repository route"
    - "Rendering evidence = versioned interaction table + real screenshot + explicit Verdict line + recorded human approval"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/11-FRONTEND-SMOKE.md
    - .planning/phases/11-local-actions-on-mirrors/11-frontend-smoke.png
  modified: []

key-decisions:
  - "D-22 frontend gate is PASS on Core 2026.9.4 / home-assistant-frontend 20260826.7, approved by the human on 2026-10-21; Plan 11-08 may build the full options editor on section + ActionSelector"
  - "Plan 11-08 should use collapsed: False for the per-trigger editor section, because a collapsed section folds again after a refused submit"
  - "Guidance for the action list goes into the section or step description, because the ActionSelector field's data_description is not rendered"
  - "Validation failures of local actions surface as errors[base]; the form-level alert renders outside the section in en and de"
  - "Manager-side validation of local actions stays mandatory: ActionSelector passes frontend-shaped raw data (e.g. delay as hours/minutes/seconds/milliseconds) and YAML-authored invalid content unchanged"

patterns-established:
  - "Bench smoke cleanup is verified, not assumed: entry deleted, component removed, ha-a restarted, smoke domain absent from core registries, user language restored"

requirements-completed: [MIR-01, MIR-15]

coverage:
  - id: D1
    description: "Real Core 2026.9.4 frontend renders section + mode SelectSelector + ActionSelector and passes expand, add, edit, save, reopen, clear, invalid/base-alert and value-kept checks in en and de"
    requirement: MIR-01
    verification:
      - kind: automated_ui
        ref: "playwright:.planning/phases/11-local-actions-on-mirrors/11-frontend-smoke.png + 11-FRONTEND-SMOKE.md interaction table (8 rows x en/de)"
        status: pass
      - kind: manual_procedural
        ref: "Task 2 blocking-human review, approved 2026-10-21"
        status: pass
    human_judgment: true
    rationale: "The plan defines the gate as a human review of real rendering; the approval is recorded, but visual adequacy stays a human judgment"
  - id: D2
    description: "Custom en/de translations for section name, description, mode options and base error render in the real frontend"
    requirement: MIR-15
    verification:
      - kind: automated_ui
        ref: "11-FRONTEND-SMOKE.md 'Labels rendered from the custom translations'"
        status: pass
    human_judgment: true
    rationale: "Only proves the translation keys render in a disposable form; the shipped en/de texts arrive with Plan 11-08 and need their own review"

# Metrics
duration: 22min
completed: 2026-10-21
---

# Phase 11 Plan 02: Frontend Smoke for Section + ActionSelector Summary

**Home Assistant Core 2026.9.4 with frontend 20260826.7 renders a section that holds a mode radio list and an ActionSelector. The section round-trips values through reopen, supports clearing, and shows a form-level base alert in English and German. The human approved the result as PASS on 2026-10-21.**

## Performance

- **Duration:** 22 min (two sessions with the checkpoint in between)
- **Started:** 2026-10-21T00:11:51Z
- **Completed:** 2026-10-21T00:34Z
- **Tasks:** 2 of 2
- **Files modified:** 2 (evidence only, no production file)

## Accomplishments

- Ran the frontend smoke on bench `ha-a`, which has the pinned Core 2026.9.4 and frontend 20260826.7. The browser was headless Chromium via Playwright 1.64.0 at a 1280x1000 viewport. All 8 interactions passed in both `en` and `de`.
- Recorded the versions, the interaction table, the rendered labels and a 2x2 screenshot composite in `11-FRONTEND-SMOKE.md` and `11-frontend-smoke.png`.
- The blocking-human gate in Task 2 was approved by the user. The approval is recorded verbatim in the evidence file.
- Wrote down four rendering findings that change how Plan 11-08 builds the editor. They are listed under Decisions Made.

## Task Commits

1. **Task 1: Render the smallest real section plus ActionSelector and capture evidence** - `7691adb` (docs)
2. **Task 2: Confirm the frontend smoke evidence before UI expansion** - `1c920ff` (docs: human approval recorded)

## Files Created/Modified

- `.planning/phases/11-local-actions-on-mirrors/11-FRONTEND-SMOKE.md`: the versions, the disposable form shape, the 8x2 interaction table, the rendered labels, the findings for 11-08, the `Verdict: PASS` line and the human approval line.
- `.planning/phases/11-local-actions-on-mirrors/11-frontend-smoke.png`: a 2x2 composite of real captures: en edit, de edit, en reopen and de base alert.

## Human Verdict

- Gate: Task 2, `checkpoint:human-verify`, `gate="blocking-human"`.
- Response (verbatim): "approved — Beleg geprüft (Screenshot + 11-FRONTEND-SMOKE.md, en/de, alle 8 Interaktionen PASS)."
- Evidence file verdict: `Verdict: PASS`. The plan's `fails_when` condition is not met: the response is an approval and the PASS line is present.

## Decisions Made

- **Gate result.** The D-22 gate is PASS. Plan 11-08 may build the full options editor on section + ActionSelector.
- **Collapsed state.** Use `{"collapsed": False}` for the per-trigger editor step. A collapsed section folds again after a base error. The values are kept, but the user has to expand the section again to fix the action.
- **Action-list guidance.** The ActionSelector field's `data_description` is not rendered in either language. The mode field's description is rendered. Put the action-list guidance in the section `description` or the step description.
- **Error channel.** `errors["base"]` is the right channel. The `ha-alert` renders above the section and stays visible when the section is collapsed.
- **Validation.** ActionSelector output is raw frontend data. Manager validation (`cv.SCRIPT_SCHEMA` plus `async_validate_actions_config`) stays mandatory.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Browser tooling was provisioned in the user cache**
- **Found during:** Task 1
- **Issue:** The bench had no browser automation. T-11-SC in the plan says "no package install occurs".
- **Fix:** Playwright 1.64.0, Chromium (headless shell) and Pillow were used from the uv/Playwright cache under `~/.cache`. Nothing was installed globally and nothing was added to the repository dependencies. The orchestrator's bench hints explicitly allowed this.
- **Files modified:** none in the repository
- **Committed in:** n/a

**2. [Documentation] The screenshot is a composite**
- **Found during:** Task 1
- **Issue:** One screenshot cannot show both languages, the reopen state and the base alert at the same time.
- **Fix:** `11-frontend-smoke.png` is a 2x2 composite of four real browser captures. The evidence file states this.
- **Committed in:** `7691adb`

**3. [Process] The root-pin guard ran late once**
- **Found during:** Task 1
- **Issue:** The project-root pin guard first ran after the PNG was written, not before it.
- **Fix:** The guard passed on that run. It ran again and passed before the commit, and it ran before every later write and commit.
- **Committed in:** n/a

---

**Total deviations:** 3. One was a Rule 3 blocker; the other two were documentation and process notes.
**Impact on plan:** No production repository file changed. The supply-chain exposure is limited to the user cache and was pre-approved by the orchestrator.

## Issues Encountered

- `ha-dev` was skipped because it runs Core 2026.10.1 with frontend 20260930.3, which is not the pinned pair. Only `ha-a` matched.
- Cleanup was verified on the bench:
  - The smoke entry was deleted and `mqtt_actions_smoke` was removed from `~/ha-test/a/custom_components/`.
  - `ha-a` was restarted, and `mqtt_actions` is `loaded` again.
  - The smoke domain occurs 0 times in `core.config_entries`, `core.device_registry` and `core.entity_registry`.
  - The bench user's language was restored, and a diff of the stored value was empty.
  - The broker and the retained config were not touched.

## Not Covered

- The real `HubOptionsFlow` menu, the trigger picker and the replacement/mute confirmations are not covered. They belong to Plan 11-08.
- Only headless Chromium was tested. No other browser and no mobile viewport.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plan 11-08 is unblocked. It should take over the four findings listed under Decisions Made.
- MIR-01 and MIR-15 are also declared by later plans in this phase, including 11-08 and 11-13. They stay open until those plans finish (shared-ID gate).

---
*Phase: 11-local-actions-on-mirrors*
*Completed: 2026-10-21*

## Self-Check: PASSED

- Evidence files, SUMMARY and commits 7691adb, 1c920ff present; `Verdict: PASS` line present.
