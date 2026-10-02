---
phase: 03-trust-central-config-and-ownership
plan: 08
subsystem: config-flow
tags: [markdown-escaping, config-flow, translations, gap-closure, uat, tdd]

requires:
  - phase: 03-trust-central-config-and-ownership
    provides: "escape_markdown in document.py (plan 03-06), the delete confirmation (plan 03-05), the Select option flows (phase 2)"
provides:
  - "config_flow.py: the delete confirmation name, the Select menu name and every option line, the option removal friendly name and state value, and the option edit state value pass through escape_markdown"
  - "tests/test_config_flow_escaping.py: seven tests (constants pin, delete confirmation for both device types, Select menu, removal, edit, plain-text chooser labels)"
  - "tests/test_translations.py: guard that no escaped flow placeholder is wrapped in Markdown control characters, in en and de"
affects: [verification, uat-retest-of-test-2]

requirements-completed: [SYN-06]

plan_head_before: 02c7359e2713924b5a77010cb6dfc3c0712eb9bf
plan_head_after: f5c3cb13da71ce9b788698ede04b5a9c0a97ce9f

actuals:
  tokens: 3100
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Escape at the placeholder, never in the stored data: the escaped strings are display text only; the draft, the subentry data, chooser labels and suggested values stay raw"
    - "Hand-written expected constants are pinned to the real escape function by a dedicated test, so a wrong constant fails with a clear message"
    - "Translation guard parametrized over both languages checks that escaped placeholders are bare words"

key-files:
  created:
    - tests/test_config_flow_escaping.py
  modified:
    - custom_components/mqtt_actions/config_flow.py
    - tests/test_translations.py

key-decisions:
  - "Only Markdown-rendered description placeholders are escaped; the option chooser labels and form suggested values render plain text and keep the raw text (an escape there would show backslashes)"
  - "The option edit form state_value placeholder was escaped too: same defect class and same file, although the UAT list did not name it"
  - "Translations are untouched: every affected description already uses the placeholders as bare words, and the new guard keeps that true"

patterns-established:
  - "Every config-flow description placeholder that carries user text goes through escape_markdown (T-03-05, Pitfall 12, T-03-38)"

coverage:
  - id: D1
    description: "The delete confirmation of a Switch and a Select device shows the UAT name as literal text"
    requirement: "SYN-06"
    verification:
      - kind: unit
        ref: "tests/test_config_flow_escaping.py::test_delete_confirmation_shows_the_device_name_as_plain_text"
        status: pass
  - id: D2
    description: "The Select menu, option removal confirmation and option edit form show user text literally while the option list keeps its structure"
    requirement: "SYN-06"
    verification:
      - kind: unit
        ref: "tests/test_config_flow_escaping.py::test_select_menu_escapes_the_name_and_every_option_line"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_escaping.py::test_remove_confirmation_escapes_friendly_name_and_state_value"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow_escaping.py::test_edit_option_details_escapes_the_state_value"
        status: pass
  - id: D3
    description: "Plain-text widgets are not over-escaped and no translation wraps an escaped placeholder in markup"
    verification:
      - kind: unit
        ref: "tests/test_config_flow_escaping.py::test_option_chooser_labels_stay_plain_text"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py::test_escaped_flow_placeholders_are_not_wrapped_in_markup"
        status: pass

duration: 20min
completed: 2026-10-02
status: complete
---

# Phase 3 Plan 08: Escape user text in config-flow descriptions Summary

**`escape_markdown` now covers every Markdown-rendered config-flow description placeholder that carries user text (delete confirmation, Select menu, option removal, option edit), closing UAT gap G-03-2.**

## Performance

- **Duration:** about 20 min
- **Tasks:** 2 of 2
- **Commits:** 4 (2 RED, 2 GREEN)

## Accomplishments

- Task 1 (tracer): the delete confirmation of both device types escapes the subentry title. The UAT name ``UAT `bt` a_b_c | <b>fett</b>`` now reaches the description as ``UAT \`bt\` a\_b\_c \| \<b\>fett\</b\>``.
- Task 2: the Select menu escapes the draft name and, separately, the friendly name and state value of every option line; the "- " marker, the parentheses and the newline join are untouched. The removal confirmation escapes both values, and the option edit form escapes its `state_value`.
- `test_option_chooser_labels_stay_plain_text` pins that the chooser labels keep the raw text, and `test_escaped_flow_placeholders_are_not_wrapped_in_markup` pins the five descriptions in en and de against double escaping.

## Task Commits

| Task | Commit | Type | Description |
| ---- | ------ | ---- | ----------- |
| 1 RED | 27d2448 | test | failing test for the escaped delete confirmation name |
| 1 GREEN | 169e238 | feat | escape the device name in the delete confirmation |
| 2 RED | 588f782 | test | failing tests for escaped select dialog text |
| 2 GREEN | f5c3cb1 | feat | escape user text in the select menu, option removal and option edit dialogs |

## Verification

- `uv run pytest tests -q`: 823 passed (baseline before this plan: 814)
- `uv run pytest tests/test_config_flow_escaping.py tests/test_translations.py tests/test_config_flow_select.py tests/test_config_flow_delete.py -q`: 77 passed
- `uv run ruff check .`: All checks passed
- `uv run ruff format --check .`: 54 files already formatted
- `grep -v '^[[:space:]]*#' custom_components/mqtt_actions/config_flow.py | grep -c "escape_markdown("`: 6
- Task 1 RED failed on the `description_placeholders` assertion (raw name returned) for both device types; Task 2 RED failed on the same kind of assertion for the three escaping tests while the chooser-label test and the translation guard passed already, as the plan expected.
- Tracer gate: the Task 1 `<verify>` command was re-run end-to-end after GREEN and passed before Task 2 started.
- The optional human check (repeat UAT test 2 in a real frontend) is outside this plan and was not done.

## Deviations from Plan

### Environment

**1. [Rule 3 - Blocking] Worktree was based on the wrong commit**
- **Found during:** startup
- **Issue:** the worktree branch `worktree-agent-a07fcd26d7b468cd3` was created from `main` (08be6de), which has neither the Phase 3 work nor plan 03-08. The plan, the UAT and the code under change live on `gsd/phase-03-trust-central-config-and-ownership` (02c7359).
- **Fix:** the worktree had no commits of its own, so it was reset to 02c7359 (the startup branch check, the one sanctioned `reset --hard`) before any work. The plan ledger records 02c7359 as the base.
- **Files modified:** none

No other deviations: the plan was executed as written. The acceptance check "`git show --stat HEAD~1 HEAD` lists only config_flow.py, test_config_flow_escaping.py and test_translations.py" holds for the Task 2 commit pair (RED touches the two test files, GREEN touches config_flow.py).

## Known Stubs

None.

## Threat Flags

None. T-03-38 and T-03-39 are mitigated as planned; no new network, auth or schema surface.

## Self-Check: PASSED

- FOUND: tests/test_config_flow_escaping.py
- FOUND: custom_components/mqtt_actions/config_flow.py (6 `escape_markdown(` calls, import line present once)
- FOUND commits: 27d2448, 169e238, 588f782, f5c3cb1
