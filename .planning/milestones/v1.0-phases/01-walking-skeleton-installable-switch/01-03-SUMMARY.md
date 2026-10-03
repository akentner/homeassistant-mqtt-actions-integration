---
phase: 01-walking-skeleton-installable-switch
plan: 03
subsystem: config-flow
tags: [home-assistant, config-flow, config-subentries, validation, translations, hassfest]

requires:
  - phase: 01-02
    provides: tracer hub flow and switch subentry flow, make_hub_entry and make_switch_subentry fixtures, D-13 verdict go-subentry
provides:
  - validate_base_topic and InvalidBaseTopic (pure, no Home Assistant import)
  - find_device_ids (static, template-aware detector for instance-local device ids)
  - Hardened hub flow (trim, base topic and instance name validation, suggested values on error, no reconfigure step)
  - SwitchSubentryFlow with create and reconfigure sharing one handler, action validation as a base error, device_id warn-then-confirm
  - Complete en.json and de.json with a parity test
affects: [01-04, 01-05, 01-06]

actuals:
  tokens: 11200
  tasks: 3
  commits: 6
plan_head_before: 54f94c1d2621ac53c5b425fe152ed245369798b9
plan_head_after: 2c80ecaf3b59b16472eec9f96e8e716fe7c1bfe2

tech-stack:
  added: []
  patterns:
    - "One form handler shared by async_step_user and async_step_reconfigure; reconfigure ends with async_update_and_abort and re-injects the immutable device_id"
    - "Action problems reported as a form-level base error with field and error placeholders (error text capped at 200 characters)"
    - "Warn-then-confirm via a per-flow JSON fingerprint of the submitted input"
    - "Translation parity enforced by tests because hassfest validates only en.json"

key-files:
  created:
    - custom_components/mqtt_actions/translations/de.json
    - tests/test_topics.py
    - tests/test_device_ids.py
    - tests/test_config_flow.py
    - tests/test_translations.py
  modified:
    - custom_components/mqtt_actions/topics.py
    - custom_components/mqtt_actions/actions.py
    - custom_components/mqtt_actions/config_flow.py
    - custom_components/mqtt_actions/translations/en.json

key-decisions:
  - "The invalid_actions placeholder field carries the labels onChangeToOn and onChangeToOff, as the plan states, not the translated field labels"
  - "The device_id warning fingerprints the raw submitted input, so any change to the form (not only to the actions) warns again"
  - "Reconfigure tests run against a set-up hub entry so the entry update listener really runs and would expose a dropped device_id (KeyError trap from research Pattern 6)"
  - "run_on_startup uses selector.BooleanSelector with default False"

requirements-completed:
  - FND-03
  - FND-04
  - DEV-01
  - DEV-02
  - DEV-05

coverage:
  - id: D1
    description: "Base topics that would widen a subscription or are not valid prefixes are rejected; valid ones pass unchanged"
    requirement: FND-03
    verification:
      - kind: unit
        ref: "tests/test_topics.py#test_invalid_base_topic_is_rejected"
        status: pass
    human_judgment: false
  - id: D2
    description: "Hub flow: defaults, trimming, mqtt_required abort, invalid topic and blank name errors, single instance, no reconfigure step"
    requirement: FND-03
    verification:
      - kind: unit
        ref: "tests/test_config_flow.py#test_hub_flow_rejects_invalid_base_topic"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow.py#test_hub_flow_has_no_reconfigure_step"
        status: pass
    human_judgment: false
  - id: D3
    description: "Switch device creation stores a uuid4 device_id equal to unique_id, RAW action lists and run_on_startup (default off)"
    requirement: DEV-01
    verification:
      - kind: unit
        ref: "tests/test_config_flow.py#test_switch_flow_creates_subentry"
        status: pass
    human_judgment: false
  - id: D4
    description: "Invalid actions are rejected with a base error; instance-local device_ids warn once and save on an identical resubmit"
    requirement: DEV-02
    verification:
      - kind: unit
        ref: "tests/test_config_flow.py#test_switch_flow_rejects_invalid_actions"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow.py#test_switch_flow_device_id_warns_then_saves_on_resubmit"
        status: pass
      - kind: unit
        ref: "tests/test_device_ids.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "Reconfigure replaces both action lists, keeps device_id and unique_id, applies the same validation and warning"
    requirement: DEV-05
    verification:
      - kind: unit
        ref: "tests/test_config_flow.py#test_switch_reconfigure_replaces_actions_and_keeps_device_id"
        status: pass
      - kind: unit
        ref: "tests/test_config_flow.py#test_switch_reconfigure_applies_validation_and_warning"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every UI string exists in English and German with identical keys and template variables; hassfest accepts en.json"
    requirement: FND-04
    verification:
      - kind: unit
        ref: "tests/test_translations.py"
        status: pass
      - kind: other
        ref: "hassfest container (podman): Integrations 1, Invalid integrations 0"
        status: pass
    human_judgment: false
  - id: D7
    description: "German wording and the visual rendering of the base error banner in the subentry dialog"
    requirement: FND-04
    verification: []
    human_judgment: true
    rationale: "Tone, grammar and how the frontend renders a base error next to the action editor are not asserted by any test (research assumption A2)"

duration: about 20min
completed: 2026-09-29
status: complete
---

# Phase 1 Plan 03: Authoring Experience Summary

**Strict hub and Switch dialogs: base topics that would widen a subscription are rejected, invalid actions produce a form-level error, instance-local device_ids warn once and save on an identical resubmit, reconfigure replaces actions while keeping the device identity, and every string ships in English and German with parity tests.**

## Performance

- **Duration:** about 20 min
- **Tasks:** 3 (all TDD, RED then GREEN each)
- **Files created:** 5, modified: 4
- **Commits:** 6 (measured from `plan_head_before`)

## Accomplishments

- **Task 1, validators:** `validate_base_topic` rejects empty, `#`, `+`, NUL, leading or trailing slash, empty level and a `$` first level (threat T-01-06). `find_device_ids` walks raw structures (dicts and lists, so `choose`, `sequence`, `parallel`, `repeat`, `if/then/else`, `target`, `data` and device actions are covered), returns unique ids in first-seen order and ignores non-strings and templates.
- **Task 2, flows:** hub flow trims input, maps `InvalidBaseTopic` to `invalid_base_topic`, rejects a blank instance name and redisplays the user's input as suggested values; it has no reconfigure step. `SwitchSubentryFlow` shares one handler between `user` and `reconfigure`. Check order is blank name, then per-field action validation (base error `invalid_actions`, placeholders `field` and `error`, capped at 200 characters), then the device_id warning. Create stores the RAW lists with a uuid4 `device_id` used as `unique_id`. Reconfigure ends in `async_update_and_abort` with the device_id re-injected.
- **Task 3, translations:** `en.json` and `de.json` (informal du) cover hub, both subentry steps, errors, aborts and both Repairs issues. `tests/test_translations.py` checks key parity, variable parity, no placeholder inside single quotes, required keys, the issue variables and the absence of `strings.json`.

## Task Commits

1. **Task 1 RED:** `ba549c4` test(01-03): add failing validator tests
2. **Task 1 GREEN:** `fefdde9` feat(01-03): add base topic validator and device id detector
3. **Task 2 RED:** `9998e86` test(01-03): add failing flow tests
4. **Task 2 GREEN:** `2346d88` feat(01-03): harden hub flow and add the switch subentry flow
5. **Task 3 RED:** `e504421` test(01-03): add failing translation parity tests
6. **Task 3 GREEN:** `2c80eca` feat(01-03): add English and German translations

## Verification Results

- `uv run pytest tests/test_topics.py tests/test_device_ids.py tests/test_config_flow.py tests/test_translations.py -q`: pass (full suite: 63 passed)
- `uv run pytest tests/test_config_flow.py -k switch -q`: 10 passed, 14 deselected
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 18 files already formatted
- hassfest container: `Integrations: 1`, `Invalid integrations: 0`
- Acceptance criteria: `test(01-03)` commit precedes each `feat(01-03)` commit; `topics.py` contains no `homeassistant` reference; `config_flow.py` contains no `voluptuous`; stored subentry data is JSON-serialisable (asserted with `json.dumps`); no `strings.json` exists.

## TDD Gate Compliance

All three tasks have a `test(01-03)` commit before their `feat(01-03)` commit. No refactor commits were needed.

## Deviations from Plan

### Notes

**1. [Note] RED failure shape.** To make RED fail on the missing function rather than on an import error, the validator tests reference `topics.validate_base_topic` and `actions.find_device_ids` through the module. Every RED failure there is an `AttributeError` for the missing symbol. In the flow tests, 19 of 24 tests failed at RED (assertions, plus `UnknownStep` for the two reconfigure tests because `async_step_reconfigure` did not exist). Five behavior tests already passed at RED because the plan 01-02 tracer implemented them (hub defaults, `mqtt_required`, single instance, no reconfigure step, entity targets without a warning); they stay as regression guards.

**2. [Note] hassfest invocation.** The plan's `docker run -v "$PWD":...` form is refused by the sandbox guard, as recorded in 01-02. The same image ran through podman with the literal worktree path mounted at `/ws` and `--workdir /ws`.

**3. [Note] Extra tests beyond the plan list.** Input trimming, error-text truncation, and reconfigure validation plus warning were added, along with `test_error_placeholders_are_the_ones_the_flow_supplies` and `test_no_strings_json_exists`.

**4. [Note] Broader single-quote check.** The parity test flags any single-quoted span that contains a variable, which is stricter than the exact hassfest rule. No shipped string uses an apostrophe, so nothing is affected.

**Total deviations:** 0 auto-fixed, 4 notes. **Impact:** none on scope.

## Findings for Later Plans (observations, not fixes here)

- **Error text echo:** `invalid_actions` shows the first Home Assistant validation message, capped at 200 characters. Some messages quote the offending value the admin just typed. It is shown only to that admin in their own form and never logged or stored, which matches T-01-09, but it is worth knowing when the same validator runs on broker payloads in Phase 3 (do not reuse that text in shared places).
- **Field label placeholder:** the `{field}` value is the literal `onChangeToOn` or `onChangeToOff`, so the German text shows an English identifier. Switching to translated labels would need a placeholder per language.
- **For plan 01-04 and 01-05:** `issues.action_failed` (`device`, `trigger`, `time`, `error`) and `issues.mqtt_discovery_disabled` strings already exist; the code that raises these issues does not yet.
- **hacs.json and docs:** not touched here; the README should mention that device_id targets do not sync across instances.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-06 (base topic validation, no reconfigure), T-01-07 (schema plus deep validation before create or update, RAW list stored) and T-01-09 (error text capped, action data never echoed into placeholders or logs) are mitigated as planned.

## Next Phase Readiness

Plans 01-04 and 01-05 can rely on validated, RAW-stored subentry data and on the translation keys for Repairs issues. No blockers.

## Self-Check: PASSED

- Files exist: `topics.py`, `actions.py`, `config_flow.py`, `translations/en.json`, `translations/de.json`, `tests/test_topics.py`, `tests/test_device_ids.py`, `tests/test_config_flow.py`, `tests/test_translations.py` (verified before the SUMMARY commit)
- Commits `ba549c4`, `fefdde9`, `9998e86`, `2346d88`, `e504421`, `2c80eca` exist on branch `worktree-agent-a1077764c63104ddc`
- Acceptance criteria re-run: pytest, ruff, hassfest all pass
