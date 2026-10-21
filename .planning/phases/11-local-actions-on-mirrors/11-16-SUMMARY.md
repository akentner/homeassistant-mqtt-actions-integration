---
phase: 11-local-actions-on-mirrors
plan: 16
subsystem: config-flow
tags: [config-flow, local-actions, local-store, hub-lifecycle, gap-closure, tdd]

requires:
  - phase: 11-local-actions-on-mirrors
    provides: "11-05 LocalActionsStore with async_remove_records (allowed after a refused load); 11-09 hub removal deletes the local Store (D-08); 11-11 ledger finding F-03 / gap G-03; 11-15 en/de translation layout"
provides:
  - "MqttActionsConfigFlow.async_step_user removes a leftover mqtt_actions.local_actions Store right before async_create_entry"
  - "Existing-hub guard: abort single_instance_allowed when a non-ignored hub exists at submit, before any removal"
  - "Fail closed: LocalActionsStoreError shows base error local_actions_not_removed and creates no entry"
  - "config.error.local_actions_not_removed in en.json and de.json; README downgrade sentence; ledger row F-03 FIXED"
affects: [11-13 final gate precondition, 11-17]

actuals:
  tokens: 4509
  tasks: 3
  commits: 6
plan_head_before: e248db31f4a48035e203d1b0e94ad016c3b42221
plan_head_after: f766d47305e3ff051524d05f7b9def4a502d761f

tech-stack:
  added: []
  patterns:
    - "A destructive cleanup in a config flow runs only after an explicit _async_current_entries(include_ignore=False) guard and fails closed into a base form error"

key-files:
  created:
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-16-task1-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-16-task1-red.xml
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-16-task2-red.json
    - .planning/phases/11-local-actions-on-mirrors/tdd/11-16-task2-red.xml
  modified:
    - custom_components/mqtt_actions/config_flow.py
    - tests/test_hub_removal.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - README.md
    - .planning/phases/11-local-actions-on-mirrors/11-CROSS-FILE-REVIEW.md

key-decisions:
  - "G-03: the hub user flow removes a leftover local actions Store (production key) right before async_create_entry; the Store key and format are unchanged, no hub id is bound to records"
  - "G-03 guard: abort single_instance_allowed when a non-ignored hub entry exists at submit, before the removal, so the cleanup never reaches a live hub (T-11-45)"
  - "G-03 failure path: a LocalActionsStoreError creates no entry and shows the base error local_actions_not_removed in en and de, so the user can retry (fail closed, T-11-44)"

patterns-established:
  - "Config flow tests that need caplog must not run with -p no:logging; RED records use -p no:logging only on the target node ids"

requirements-completed: [MIR-02, MIR-15]

coverage:
  - id: D1
    description: "A new hub over a leftover local Store starts with 0 local devices and the key is gone from hass_storage"
    requirement: MIR-02
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_new_hub_never_loads_local_actions_left_by_an_earlier_hub"
        status: pass
    human_judgment: false
  - id: D2
    description: "A hub flow submitted while a hub exists aborts with single_instance_allowed and leaves that hub's local Store bytes identical"
    requirement: MIR-02
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_new_hub_flow_never_removes_the_local_actions_of_an_existing_hub"
        status: pass
    human_judgment: false
  - id: D3
    description: "A failed removal returns the user form with errors base local_actions_not_removed, creates no entry and keeps the bytes"
    requirement: MIR-02
    verification:
      - kind: integration
        ref: "tests/test_hub_removal.py#test_new_hub_flow_shows_an_error_when_leftover_local_actions_cannot_be_removed"
        status: pass
    human_judgment: false
  - id: D4
    description: "en and de carry config.error.local_actions_not_removed with identical key sets and no variable"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_en_and_de_have_identical_keys"
        status: pass
    human_judgment: false
  - id: D5
    description: "Natural, accurate German wording of the new error text"
    requirement: MIR-15
    human_judgment: true
    rationale: "Tests pin only presence and the absence of variables; whether the German reads naturally needs a human"
  - id: D6
    description: "README downgrade warning names a removal on 1.0.1 and adding the hub again; all pinned phrases stay"
    requirement: MIR-15
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_warns_prominently_about_a_downgrade_to_1_0_1"
        status: pass
    human_judgment: false
  - id: D7
    description: "Ledger row F-03 FIXED with c9c9c63 and the regression test id; F-01, F-02 FIXED, F-04 ROUTED"
    verification:
      - kind: other
        ref: "plan 11-16 Task 3 ledger verify command (row grep, sha ancestry, feat(11-16) subject)"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-21
status: complete
---

# Phase 11 Plan 16: No leftover local Store on a new hub (G-03) Summary

**The hub config flow now deletes a leftover `mqtt_actions.local_actions` file right before it creates the entry, so a new hub never runs trusted local actions written for an earlier, removed hub. The cleanup refuses to run while a hub exists (abort `single_instance_allowed`), and a failed removal creates no hub and shows `local_actions_not_removed` in English and German.**

## Performance

- **Duration:** about 7 min (2026-10-21T04:40:39Z to 2026-10-21T04:47:30Z)
- **Tasks:** 3 of 3
- **Files modified:** 6 source/test/doc/ledger files plus 4 RED evidence files

## Accomplishments

- `config_flow.py` imports `LocalActionsStore` and `LocalActionsStoreError`. After validation passes, `async_step_user` does three things in order:
  1. It aborts with `single_instance_allowed` if `self._async_current_entries(include_ignore=False)` is not empty.
  2. It awaits `LocalActionsStore(self.hass).async_remove_records()` with the production key.
  3. On `LocalActionsStoreError` it sets `errors["base"] = "local_actions_not_removed"` and falls through to the existing form. Otherwise it creates the entry.
- A missing file is a no-op, so every existing hub-flow test passed without changes.
- `config.error.local_actions_not_removed` is in en.json and de.json.
- The README downgrade warning has one new sentence.
- Ledger row F-03 is FIXED and gap G-03 is resolved.

## Task Commits

| Task | Gate | Commit | Message |
|------|------|--------|---------|
| 1 | RED | f8cdfa8 | test(11-16): add failing test for a new hub loading leftover local actions |
| 1 | GREEN | c9c9c63 | feat(11-16): remove a leftover local actions Store before a new hub entry exists |
| 2 | RED | c5c8d5a | test(11-16): add failing tests for the existing-hub guard and a failed leftover removal |
| 2 | GREEN | ba5ee23 | feat(11-16): guard an existing hub and fail closed when leftover local actions stay |
| 3 | docs | f509ac8 | docs(11-16): explain that a new hub deletes local actions left by a removal on 1.0.1 |
| 3 | ledger | f766d47 | docs(11-16): set ledger row F-03 to FIXED and resolve gap G-03 |

No REFACTOR commit was needed.

## RED semantic assessments

- **Task 1** (`tdd/11-16-task1-red.json`, RED_EVIDENCE_OK). The target ran: 1 test, 0 errors, 0 skipped. Seeding, flow init (FORM), submit (CREATE_ENTRY) and setup (LOADED) all succeeded. The test then failed on its first planned assertion: the new hub's Manager counted 3 devices (`assert 3 == 0`, records=5, orphan_only_devices=3). That is exactly G-03, not a fixture fault.
- **Task 2** (`tdd/11-16-task2-red.json`, RED_EVIDENCE_OK). The target ran, and its abort type and reason `single_instance_allowed` matched, because HA refuses the second entry in `async_finish_flow`. It failed on the guard: the Task 1 removal had already deleted the live hub's Store. The failing check was the key-presence assertion right before the byte comparison.
  - Disclosure: the failure-path test also failed at RED. The patched `LocalActionsStoreError("disk")` propagated out of `async_configure`. JUnit counts this as a failure in the test body, not as a setup error.

## README sentence

Appended inside the `> [!WARNING]` block of "Downgrading to 1.0.1", after the MIR-F4 sentence:

> Removing the integration on 1.0.1 does not delete that local actions file; when you add the hub again on 1.1, the file is deleted before the new hub starts, so the new hub never runs local actions of the removed one.

## Error texts

- **en:** "Local actions left by an earlier MQTT Actions hub could not be deleted, so the hub was not created. Try again. If this error comes back, check the Home Assistant log."
- **de:** "Lokale Aktionen eines früheren MQTT-Actions-Hubs konnten nicht gelöscht werden, deshalb wurde der Hub nicht angelegt. Versuche es erneut. Wenn der Fehler wieder auftritt, sieh im Home-Assistant-Protokoll nach."

## Ledger row change

- F-03 changed from `ROUTED` to `FIXED`. Its Gap column changed from `G-03` to `G-03 fixed in c9c9c63`. The regression test id is unchanged.
- The G-03 YAML now reads `status: resolved` with `fixed_in: "c9c9c63 (plan 11-16)"`.
- Ledger summary: 1 routed (F-04) and 3 fixed (F-01, F-02, F-03). The routed-gap line now says 3 of 4 are fixed. No other row changed.

## Decisions Made

- In the guard test, the hub entry is only added (`add_to_hass`) and not set up. That way no Manager load or save can touch the seeded bytes, and the test checks only the flow.
- The byte comparison uses `json.dumps(..., sort_keys=True)` of the stored envelope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Planned deviation] Two translation files beyond the ledger's file list**
- The plan already states the reason: a failed removal must not create the hub (fail closed, T-11-44), and the form then needs an en and de error text, because no existing config error fits. Commit ba5ee23.

**2. [Minor] RED evidence files committed with each RED commit**
- Plans 11-07, 11-12, 11-14 and 11-15 did the same: `tdd/*-red.{json,xml}` went into the RED commit. No `test(11-16)` commit touches `custom_components/`, which is what the verify command checks.

**3. [Minor] Task 2 target fails on the key-presence check, not the byte comparison**
- The plan says the target fails "on its byte-equality assertion". The test checks first that the key still exists, then that the bytes are identical. At RED the key was gone, so the presence check failed first. Both checks pin the same guard behavior.

**Total deviations:** 1 planned, 2 minor. **Impact:** none on behavior or scope.

## TDD Gate Compliance

- Every task has its RED commit before its GREEN commit: f8cdfa8 then c9c9c63, and c5c8d5a then ba5ee23.
- Tracer gate (Task 1): auto-approval was not needed. `human_verify_mode` is end-of-phase and the verify step is automated only. The tracer `<verify>` was run again: 1 passed, 72 passed in the three-module set, and the RED/commit-scope script passed. Expansion then went ahead.

## Verification

- **Task 1:** target 1 passed. hub_removal, config_flow and local_actions_flow: 72 passed. The RED evidence, commit scope and no-skip script passed.
- **Task 2:** the two targets plus translations and config_flow: 113 passed. The RED evidence, the en/de text check and the `include_ignore=False` grep passed.
- **Task 3:**
  - The README phrase check, `tests/test_docs.py` (34 passed), `ruff check .` and `ruff format --check .` passed.
  - `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run pytest -q`: **2071 passed, 2 xfailed**, with nothing deselected or skipped (baseline 2056).
  - The ledger verify command passed.

## Issues Encountered

- A first combined run used `-p no:logging`. That flag disables `caplog`, so the two caplog tests in `tests/test_hub_removal.py` (`test_delete_mode_survives_unavailable_mqtt`, `test_keep_mode_needs_no_mqtt`) errored with "recursive dependency involving fixture 'caplog'". The plan's command has no such flag, and without it all 72 passed. The cause was the run setup, not the code.
- `README.md` already has six lines over 120 characters (164, 249, 441, 483, 547, 582). They were there before this plan and are out of scope. The new lines (394-396) stay within the limit.

## Next Phase Readiness

- Only G-04 (F-04, plan 11-17) is still routed. Plan 11-13 runs the final gate once F-04 is FIXED.

## Self-Check: PASSED
