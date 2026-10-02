---
phase: 03-trust-central-config-and-ownership
plan: 06
subsystem: trust
tags: [approval, repairs, fix-flow, denylist, guarded-template, security, markdown-injection, tdd]

requires:
  - phase: 03-trust-central-config-and-ownership
    provides: "Follower mirrors with MirrorInfo (actions_hash, denied, templated, residual), Manager.mirrors, mirror persistence and removal (plans 03-04, 03-05); analyze_actions, is_denied, approval_sections, escape_markdown, actions_hash (plan 03-01); ISSUE_DEVICE_PREFIXES and the owner/follower SyncManager (plans 03-02, 03-04)"
provides:
  - "Approval gate: a mirror gets a Script only while the stored approval equals its actions hash; unapproved, changed, blocked and action-less mirrors run nothing for state, test button and run-on-startup"
  - "trust.py: DeniedServiceCallError (plain Exception), GuardedTemplate, guard_actions, ApprovalView, build_approval_view"
  - "ActionRunner restricted build: statically denied triggers are refused, service-name templates are guarded, a denial aborts the run even with continue_on_error and is surfaced in the log and Repairs (denied_call_<id>)"
  - "Manager approvals in the Store (approvals key), async_approve for the exact current hash, async_approval_view, approval and blocked issue lifecycle (delete then create)"
  - "repairs.py: ApprovalRepairFlow and async_create_fix_flow; the dialog binds the displayed hash, aborts on change, too_large and not_loaded"
  - "English and German texts for approval_required (with the fix flow), mirror_blocked and denied_service_call"
affects: [03-07, 04-operations]

requirements-completed: [TRU-01, TRU-02, TRU-03]

plan_head_before: 9631f51b0c206f0f1bf9bc2805b7103d526827b9
plan_head_after: 08c778ddd3e7a031e7ad812ea83a529ded5333f4

actuals:
  tokens: 21200
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Gate by construction: a mirror without a Script is inert, and the only code path that builds one for a mirror checks approvals[id] == actions_hash and builds restricted"
    - "Execution-time denylist through a Template subclass whose async_render raises a plain Exception, because core re-raises everything that is neither HomeAssistantError nor TemplateError past continue_on_error"
    - "A changed request is delete-then-create so an issue dismissal never hides it; issues are recreated from the Store state at every start and on every applied document"
    - "The fix flow binds the hash it displayed and re-checks it twice (issue data, remembered hash) before async_approve re-checks the current hash under the manager lock"
    - "Broker-supplied text in Repairs: escape_markdown on names and error text, control and format characters removed, fence runs broken up, hard cap with refusal instead of a truncated review"

key-files:
  created:
    - custom_components/mqtt_actions/trust.py
    - custom_components/mqtt_actions/repairs.py
    - tests/test_trust.py
    - tests/test_repairs_flow.py
  modified:
    - custom_components/mqtt_actions/const.py
    - custom_components/mqtt_actions/runner.py
    - custom_components/mqtt_actions/manager.py
    - custom_components/mqtt_actions/translations/en.json
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_multi_instance.py
    - tests/test_translations.py
    - tests/test_manager_breaker.py
    - tests/test_sync_owner.py

key-decisions:
  - "The Script of a mirror is built before the mirror subscribes (create, update and restore), so an approved mirror never misses its startup window and an unapproved one never has a moment with a Script"
  - "async_approve also refuses a mirror without actions (nothing to approve), besides unknown ids, blocked mirrors and a hash that is not the current one"
  - "GuardedTemplate wraps Template values under action, service_template and also the legacy service key anywhere in the tree; a payload key of that name is wrapped too and only acts when its rendered value is a denied service name (conservative, mirrors the static walker)"
  - "An empty list in the dialog is an em dash, not a hyphen: a lone hyphen on its own line would turn the preceding line into a markdown heading"
  - "Approval issues are deleted and recreated on every applied mirror document and at every start, even for a rename; a dismissed request therefore returns, which is the safe side (Pitfall 8)"
  - "report_failure escapes device name, trigger label and error text for restricted devices, because a mirror's action failure issue would otherwise render broker text as markdown"
  - "The approval is dropped with the mirror on a tombstone or prune (A10); a kept approval whose hash no longer matches stays in the Store and applies again if the owner reverts to exactly those actions"

patterns-established:
  - "Runner API: async_build_device(spec, restricted=False), report_failure(..., escape=False), report_denied(...)"
  - "New per-device issue families (denied_call_, approval_, blocked_) are appended to ISSUE_DEVICE_PREFIXES so tombstone, device delete and hub removal clean them"

coverage:
  - id: D1
    description: "An unapproved, changed, blocked or action-less mirror never runs anything: no Script exists for live state, the test button or run-on-startup; a forged approval entry in the Store or in memory cannot give a statically denied mirror a Script"
    requirement: TRU-01
    verification:
      - kind: integration
        ref: "tests/test_trust.py#test_unapproved_mirror_runs_nothing"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_blocked_mirror_is_not_approvable_and_never_built"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_changed_actions_lapse_the_approval"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_mirror_without_actions_needs_no_approval"
        status: pass
    human_judgment: false
  - id: D2
    description: "Approval binds the exact current hash: other hashes, unknown ids and blocked mirrors are refused with nothing stored; approval persists across restart, survives renames and settings changes, runs nothing retroactively and owned devices need none"
    requirement: TRU-02
    verification:
      - kind: integration
        ref: "tests/test_trust.py#test_approval_requires_the_current_hash"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_approval_is_not_retroactive"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_approval_persists_across_restart"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_rename_and_settings_change_keep_the_approval"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_owned_devices_are_unrestricted_and_need_no_approval"
        status: pass
      - kind: unit
        ref: "tests/test_trust.py#test_malformed_approvals_store_is_dropped"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Repairs fix flow shows device, owner, YAML, hash and templated names, approves only the displayed hash, aborts when the owner changed the document while it was open, refuses an over-long review, leaves the mirror paused when closed, and a dismissed request never hides a changed one"
    requirement: TRU-02
    verification:
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_flow_shows_device_owner_yaml_hash_and_templates"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_race_owner_edits_while_the_dialog_is_open_aborts"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_dismissed_issue_does_not_hide_a_changed_request"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_submit_approves_and_the_issue_disappears"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_too_long_actions_refuse_approval"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_issues_are_recreated_at_start"
        status: pass
    human_judgment: false
  - id: D4
    description: "The denylist is enforced again at execution time on resolved service names of mirror Scripts: a plain Exception from the guard aborts the run even with continue_on_error, is surfaced in the log and Repairs, and owned actions stay unrestricted; statically denied mirrors are blocked and explained"
    requirement: TRU-03
    verification:
      - kind: integration
        ref: "tests/test_trust.py#test_denied_call_aborts_the_run_even_with_continue_on_error"
        status: pass
      - kind: unit
        ref: "tests/test_trust.py#test_guarded_template_raises_a_plain_exception_for_a_denied_name"
        status: pass
      - kind: unit
        ref: "tests/test_trust.py#test_nested_templated_service_name_three_levels_deep_is_guarded"
        status: pass
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_blocked_mirror_raises_a_non_fixable_blocked_issue"
        status: pass
    human_judgment: false
  - id: D5
    description: "Broker-supplied text is neutralized in the approval view: names and owner names are markdown-escaped, fence runs and control or format characters removed from the YAML, long lists capped and an over-long document refused"
    requirement: TRU-03
    verification:
      - kind: integration
        ref: "tests/test_repairs_flow.py#test_hostile_names_and_yaml_are_neutralized"
        status: pass
      - kind: unit
        ref: "tests/test_trust.py#test_view_removes_control_characters_and_fence_runs"
        status: pass
      - kind: unit
        ref: "tests/test_trust.py#test_view_caps_the_templated_names"
        status: pass
    human_judgment: false
  - id: D6
    description: "After approval a real state change from the UI of any instance or an external client runs the actions locally on every instance that approved; the test button on an approved mirror runs with test true; a mirror trips its breaker like an owned device"
    requirement: STA-03
    verification:
      - kind: integration
        ref: "tests/test_multi_instance.py#test_approved_mirror_runs_actions_on_both_instances"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_approved_mirror_test_button_runs_with_test_true"
        status: pass
      - kind: integration
        ref: "tests/test_trust.py#test_mirror_breaker_trips_like_an_owned_device"
        status: pass
    human_judgment: false
  - id: D7
    description: "English and German texts for the approval request, the fix flow, the blocked and the denied-call issues with exactly the placeholders the code supplies, and the fenced yaml block in the confirm description"
    verification:
      - kind: unit
        ref: "tests/test_translations.py#test_required_keys_present"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_issue_strings_use_expected_variables"
        status: pass
      - kind: unit
        ref: "tests/test_translations.py#test_confirm_description_contains_a_fenced_yaml_block"
        status: pass
    human_judgment: false
  - id: D8
    description: "Whether the Home Assistant frontend renders the fix flow description as markdown so the fenced YAML shows as a code block (A3), whether hassfest accepts repairs.py without a repairs dependency in the manifest, the exact wording of the German texts, the denylist policy (A1) and the reconciliation of 'local opt-in flag' with per-device approval (Open Question 6) are judgments and environment checks tests cannot assert"
    verification: []
    human_judgment: true
    rationale: "Frontend rendering needs two real instances in the manual UAT at the end of the phase; hassfest runs only in CI; policy and phrasing are for the user to confirm"

duration: 55 min
completed: 2026-10-01
status: complete
---

# Phase 3 Plan 06: Approval Gate Summary

**A mirrored device runs its actions only after the user approved exactly the hash shown in a Repairs dialog on this instance, through a Script whose service-name templates are guarded by a plain-Exception hook that continue_on_error cannot swallow; every other state runs nothing**

## Performance

- **Duration:** about 55 min
- **Completed:** 2026-10-01
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto, all TDD)
- **Files modified:** 13 (4 created, 9 modified)

## Accomplishments

- **Gate by construction.** `Manager._async_refresh_mirror_script` builds a Script for a mirror only when it is not blocked, has actions and `_approvals[id] == actions_hash`; otherwise it unloads, which stops running and queued runs. It runs on create, on every applied update and for every restored mirror, and always before the mirror subscribes, so approved mirrors never miss the startup window. State edges, the test topic and run-on-startup all go through `runner.can_run`, so an unapproved mirror is inert on every path.
- **Hash-bound approvals.** `Manager.async_approve(device_id, actions_hash)` runs under the manager lock and accepts only the exact current hash of an existing, unblocked mirror with actions; it stores the approval (Store key `approvals`, parsed defensively and pruned to mirror ids at start), builds the restricted Script and deletes the approval and denied-call issues. A changed document keeps the stored entry as a non-matching one and unloads the Script; reverting to exactly the approved actions makes the mirror run again. Rename, run mode and breaker changes keep the approval (A5). A tombstone or prune pops the entry (A10).
- **Execution-time guard.** `GuardedTemplate` (a `Template` subclass with `__slots__ = ()`) raises `DeniedServiceCallError` when a resolved service name is on the denylist; the error is a plain `Exception`, so core's `continue_on_error` re-raises it instead of swallowing it. `guard_actions` returns a copy of the validated tree with every Template under `action`, `service_template` and `service` wrapped. The restricted build also refuses statically denied triggers itself, so even a forged approval cannot give a denied mirror a Script (T-03-33). `_async_run` logs one warning with device, trigger and service name and raises `denied_call_<id>`; owned devices keep the unrestricted build.
- **Approval through Repairs.** `approval_<id>` is a fixable warning whose data carries only the device id and hash; `blocked_<id>` is a non-fixable error naming the denied services; both are rebuilt by delete-then-create so a dismissed request never hides a changed one. `ApprovalRepairFlow` shows device, owner, YAML, short hash, templated names, residual step kinds and the triggers that do not validate here, remembers the hash it displayed, and approves only that hash. It aborts with `changed` (owner edited during the dialog, or approval refused), `too_large` and `not_loaded`; closing the dialog stores nothing.
- **Safe view.** `build_approval_view` escapes names, dumps the actions with the core YAML dumper, removes control, format, surrogate and separator characters, breaks up backtick runs of three or more, caps the YAML at `APPROVAL_YAML_MAX_CHARS` (the flow refuses instead of showing a truncated review) and caps each list; empty lists are an em dash.
- **Texts.** English and German texts for the request, the fix flow (confirm step with the actions in a fenced yaml block, three abort reasons), the blocked issue and the denied-call issue.

## Task Commits

1. **Task 1: Tracer, approved mirror runs through a guarded Script** - `afbda74` (test, RED), `cbea6a2` (feat, GREEN)
2. **Task 2: Approval through Repairs** - `42fa889` (test, RED), `8005376` (feat, GREEN)
3. **Task 3: Texts in English and German** - `17b0315` (test, RED), `08c778d` (feat, GREEN)

**Plan metadata:** added by the docs commit that follows this file.

## TDD Gate Compliance

Every task has a `test(03-06)` commit before its `feat(03-06)` commit; no refactor commits. Tracer gate: Task 1's verify is automated only, so after the GREEN commit both test modules, the full suite, Ruff check and format and the gateway-import test were re-run end to end (734 passed) before Task 2 expanded; the run is logged here as "tracer verified end-to-end, expanding". RED evidence (`check tdd-red-evidence` was not run):

- Task 1: 25 tests failed on the missing surface (`ModuleNotFoundError`-style import of `trust` inside the test body, `restricted` keyword, `_approvals`, `async_approve`); the existing behavior pins (for example `test_unapproved_mirror_runs_nothing`) passed at RED because mirrors had no Script already. The two constant names `STORE_APPROVALS` and `ISSUE_DENIED_CALL_PREFIX` were added in the RED commit so the tests fail on behavior and not at collection; the prefix was appended to `ISSUE_DEVICE_PREFIXES` only in GREEN.
- Task 2: 21 tests failed (no view builder, no `repairs` platform, no issue lifecycle; the flow manager raised `UnknownStep` because no fixable issue existed). Constant names (`ISSUE_APPROVAL_PREFIX`, `ISSUE_BLOCKED_PREFIX`, `APPROVAL_*`) were added in the RED commit, the prefixes were appended to `ISSUE_DEVICE_PREFIXES` only in GREEN.
- Task 3: eight translation tests failed on the missing keys and variables.
- Mutations run by hand after GREEN, each making the intended tests fail: no `guard_actions` call (`test_denied_call_aborts_the_run_even_with_continue_on_error`); approval matched by id instead of hash (`test_changed_actions_lapse_the_approval`, `test_malformed_approvals_store_is_dropped[non-matching-hash]`); no delete before create of the approval issue (`test_dismissed_issue_does_not_hide_a_changed_request`); flow without hash binding approving the current hash (`test_race_owner_edits_while_the_dialog_is_open_aborts`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Constant names moved into the RED commits**
- **Found during:** Task 1 and Task 2 RED
- **Issue:** the new tests import `STORE_APPROVALS`, `ISSUE_DENIED_CALL_PREFIX`, `ISSUE_APPROVAL_PREFIX`, `ISSUE_BLOCKED_PREFIX` and the `APPROVAL_*` limits; a missing name is an import error at collection, which is INVALID_RED, not a failing assertion for the behavior (same precedent as plans 03-04 and 03-05).
- **Fix:** the names (no behavior) are added in the RED commits; appending the prefixes to `ISSUE_DEVICE_PREFIXES` is GREEN work. The first Task 2 RED commit also had one over-long comment line that Ruff flagged; it was corrected with an amend of the unpushed RED commit (`42fa889`).
- **Files modified:** `custom_components/mqtt_actions/const.py`
- **Commits:** `afbda74`, `42fa889`

**2. [Rule 1 - Bug] Two existing tests pinned behavior that this plan changes by design**
- **Found during:** Task 1 and Task 2 full-suite runs
- **Issue:** `tests/test_manager_breaker.py::test_trip_is_persisted_as_config_hash` asserts the exact set of Store keys, which gains `approvals` (additive key, no version bump). `tests/test_sync_owner.py::test_documents_for_unowned_ids_are_ignored_here` asserted that a foreign document creates no issue at all; since the follower branch (plan 03-04) mirrors it and this plan raises its approval request, exactly one `approval_` issue exists.
- **Fix:** the first expects `STORE_APPROVALS` in the key set; the second asserts `["approval_someone-elses-device"]` and keeps its intent (nothing published, no owner-branch issue).
- **Files modified:** `tests/test_manager_breaker.py`, `tests/test_sync_owner.py`
- **Commits:** `cbea6a2`, `8005376`

**3. [Rule 2 - Missing critical] Action failure issues of mirrors escape broker text**
- **Found during:** Task 1 design (T-03-28 and T-03-05 class of risk)
- **Issue:** `report_failure` put device name, trigger label (a Select friendly name) and the error text (which can quote action data) into a markdown issue text unescaped; once mirrors have a Script, those values come from the broker.
- **Fix:** `report_failure(..., escape=False)`; the runner tracks which devices were built restricted and passes `escape=True` for their setup and run failures. The denied-call issue always escapes.
- **Files modified:** `custom_components/mqtt_actions/runner.py`
- **Commit:** `cbea6a2`

**4. [Rule 1 - Bug] The fix flow's first step must ignore the init data**
- **Found during:** Task 2 GREEN
- **Issue:** core passes the init data (`{"issue_id": ...}`) as `user_input` to `async_step_init`; delegating that into the confirm step made the first call look like a submit and aborted with `changed`.
- **Fix:** `async_step_init` calls `async_step_confirm()` without arguments, as core's own `ConfirmRepairFlow` does.
- **Files modified:** `custom_components/mqtt_actions/repairs.py`
- **Commit:** `8005376`

**5. [Rule 1 - Bug] Plan test expectations did not account for markdown escaping and an em dash**
- **Found during:** Task 1 and Task 2 GREEN
- **Issue:** assertions compared service names and placeholders with the raw text, but `escape_markdown` turns `_` into `\_`; and an empty list is the language-neutral dash, for which this plan chose the em dash (a lone hyphen would make the previous markdown line a heading).
- **Fix:** tests compare against `escape_markdown(...)` and the `EMPTY_LIST_TEXT` constant.
- **Files modified:** `tests/test_trust.py`, `tests/test_repairs_flow.py`
- **Commits:** `cbea6a2`, `8005376`

**6. [Rule 1 - Bug] Plan acceptance wording not literally satisfiable**
- **Issue:** Task 3 requires `grep -c "approval_required"` on `en.json` and `de.json` to be equal and at least 2; the key occurs once per file (title, description and flow strings are nested below it and do not repeat the name). Counts are equal (1 and 1) and all texts are covered by `test_required_keys_present` and `test_issue_strings_use_expected_variables`; no artificial text was added (same situation as plans 03-02 deviation 4 and 03-04 deviation 5).
- **Files modified:** none

---

**Total deviations:** 6 (2 Rule 3/Rule 1 constant and test pins, 1 Rule 2, 3 Rule 1). **Impact on plan:** no scope change; no assertion of an existing test was weakened, two were updated for behavior this plan introduces.

## Issues Encountered

- The core service-name hook was verified against the installed 2026.9.4 source before writing: `async_prepare_call_from_config` calls `async_render` on the validated Template and only converts `TemplateError` and `vol.Invalid`; `ScriptRun._handle_exception` re-raises every exception that is not a `HomeAssistantError` even with `continue_on_error`. The control in `test_denied_call_aborts_the_run_even_with_continue_on_error` (unrestricted build runs both steps) pins this coupling.
- `cv.service` lower-cases but does not strip a rendered service name, so a template that renders a name with surrounding spaces fails core's own check; the guard still normalizes with strip and lower, which is the stricter side.
- Core's `Script` logs its own ERROR lines ("Unexpected error for call_service") for the denial; they contain only the guard's message (service name), no action data.
- Core MQTT drops a second retained message per topic in the mocked tier, so update tests deliver changed documents with `retain=False` (as in plan 03-04).
- hassfest cannot run in the local suite; `repairs.py` imports `homeassistant.components.repairs` like core's own mqtt repairs and the manifest has no `repairs` dependency. If the validate workflow objects after the push, add `repairs` to `after_dependencies` in `manifest.json` in a separate fix commit (plan assumption).

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. The new surfaces (Repairs fix flow, approval Store key, guard on rendered names) are those of T-03-24 to T-03-33, all mitigated and covered above; T-03-31 and T-03-32 are accepted as planned (residual step kinds and notify-style disclosure; the approval view lists the step kinds and the full YAML). T-03-SC: no package was installed.

## Next Phase Readiness

- Plan 03-07 documents: the README trust section (per-device approval is the opt-in of D-01; reconciles `.claude/CLAUDE.md` "local opt-in flag"), the residual risk of local scripts, automations, scenes, device actions and events (A14, T-03-31), `notify` deliberately allowed (T-03-32), `mqtt.publish` denied for mirrors, the test button on an approved mirror running on every approving instance (Open Question 4: the ACL document names the test topic as a second trigger source), and that a forged tombstone or prune drops an approval (A10).
- Needs user confirmation at review: the denylist policy of plan 03-01 (A1, Open Question 2), no hub-level opt-in switch (Open Question 6), `APPROVAL_YAML_MAX_CHARS = 20000`, `APPROVAL_TEMPLATED_MAX_LINES = 20`, `APPROVAL_HASH_PREFIX_LENGTH = 12`, `BLOCKED_SERVICES_MAX_SHOWN = 10`, the em dash for empty lists, the always-reset dismissal of a pending request on every applied document and restart, and the English and German wording.
- Manual UAT at the end of the phase (assumption A3): with two real instances on one broker, open the approval issue on the follower and check that the YAML renders as a code block with device, owner, hash and templated names, that approving removes the issue and a state change then runs the action, and that changing the actions on the owner makes the follower show a new request and stop running until approved again.
- Requirement bookkeeping: TRU-01, TRU-02 and TRU-03 are declared by this plan only and are finished here; STA-03 is shared with plan 03-07 and is left for the phase verification.

## Self-Check: PASSED

- Created files exist: `custom_components/mqtt_actions/trust.py`, `custom_components/mqtt_actions/repairs.py`, `tests/test_trust.py`, `tests/test_repairs_flow.py` (FOUND)
- Commits exist: `afbda74`, `cbea6a2`, `42fa889`, `8005376`, `17b0315`, `08c778d` (FOUND); each `test(03-06)` commit precedes its `feat(03-06)` commit (three of each)
- Acceptance: `grep -c "class DeniedServiceCallError(Exception)"` on `trust.py` prints 1; `grep -c "async def async_create_fix_flow"` on `repairs.py` prints 1; `restricted=True` and `guard_actions` are present in `manager.py` and `runner.py`; `test_denied_call_aborts_the_run_even_with_continue_on_error` asserts zero calls for the denied service and the following step and one call each in the unrestricted control; `test_race_owner_edits_while_the_dialog_is_open_aborts` asserts the approvals map is empty after the abort; `test_dismissed_issue_does_not_hide_a_changed_request` asserts `dismissed_version is None` after a prior dismissal; `test_only_gateway_imports_mqtt_component` passes
- `uv run pytest -q` 757 passed; `uv run ruff check .` and `uv run ruff format --check .` clean
