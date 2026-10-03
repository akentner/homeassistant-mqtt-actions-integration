---
phase: 04-operations-recovery-and-release
plan: 13
subsystem: docs
tags: [documentation, markdown, operations, troubleshooting, diagnostics, release, doc-tests]

requires:
  - phase: 04-operations-recovery-and-release
    provides: services, heartbeat and roster, modes, re-trigger, adoption, duplicate id, export and import, diagnostics, release workflow and test tiers (plans 04-01 to 04-12)
provides:
  - docs/operations.md covering every service, protocol, mode, adoption, duplicate id, export and import, limits and upgrade notes
  - docs/diagnostics.md with the exact keys of the diagnostics file and what it never contains
  - docs/troubleshooting.md with one entry per Repairs issue key and the common operating problems
  - README as the entry point with an Operations overview, Releases, test tiers and current Limitations
  - tests/test_docs.py tying the pages to services.yaml, const.py, the translations, the diagnostics key sets and each other
affects: [phase verification, 04-VERIFICATION, release v0.x, HACS users]

actuals:
  tokens: 17700
  tasks: 3
  commits: 6
plan_head_before: 805e7269b21f9a1984742555a7e1099b164e4de3
plan_head_after: a7ebed6cbde71a6e54ae104355eab7657f63e238

tech-stack:
  added: []
  patterns:
    - "Documentation is pinned to the code by tests: services.yaml, const.py, the English translations and the diagnostics key sets are read by tests/test_docs.py"
    - "A fenced example may carry device_id only as the data field of an mqtt_actions service call (YAML parsed, key path checked), next to the instance-specific warning"

key-files:
  created:
    - docs/operations.md
    - docs/diagnostics.md
    - docs/troubleshooting.md
  modified:
    - README.md
    - docs/broker-acl.md
    - tests/test_docs.py

key-decisions:
  - "The numbers of the operations page live in one Limits table that names each constant in backticks next to its value and unit; the test finds the rows by the constant name, so a changed constant fails the build"
  - "The diagnostics page test imports the key sets that tests/test_diagnostics.py pins to the real output, so the page cannot drift from the allow-list"
  - "Responses are shown as YAML without any device_id key (the response key is uuid) and wire payloads as tables, so the device_id rule needs no exception for them"
  - "docs/broker-acl.md needed one added limits bullet (adoption and import are the administrator's responsibility); the tested acl block and tests/broker/test_acl.py are unchanged"
  - "The page text states the 04-09, 04-11 and 04-12 caveats as they are: imports and adoption are owned content without approval, recognition of a returning owner is in memory only, a released baseline does not survive a restart"

patterns-established:
  - "Pattern: a page-existence helper asserts the file first, so a missing page is an assertion failure for the behavior and never a file error"

requirements-completed: [OPS-05]

coverage:
  - id: D1
    description: "docs/operations.md documents every service of services.yaml with fields, caller and response, and the operating features with numbers equal to const.py"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_operations_page_names_every_service_and_field"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_operations_page_documents_the_wire_contract"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_operations_page_numbers_match_the_constants"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/diagnostics.md lists the diagnostics keys and states what is never included; docs/troubleshooting.md has an entry for every Repairs issue key and the operating problems"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_diagnostics_page_lists_the_included_keys_and_the_exclusions"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_troubleshooting_covers_every_issue_key"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_troubleshooting_covers_the_operating_problems"
        status: pass
    human_judgment: false
  - id: D3
    description: "README is the entry point: links the three pages, overview of operations, release process, test tiers, current limitations; existing README tests keep passing"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_phase4_behavior"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_the_release_process"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_readme_documents_the_test_tiers"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_readme_limitations_are_current"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py (README phrase tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "ACL page names every topic family and states the advisory acknowledgements and the administrator's responsibility; no page promises more security than the code gives; no device_id outside a service data field"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_acl_document_names_every_topic_family"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_security_limits_are_stated"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_device_id_appears_only_as_a_service_data_field"
        status: pass
      - kind: integration
        ref: "uv run pytest -m broker tests/broker/test_acl.py -q (13 passed)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A new user can go from the README to installation, the first operations and the troubleshooting entry of a Repairs issue by following links"
    verification: []
    human_judgment: true
    rationale: "Whether the pages read well and lead a new user without searching is a judgment no test asserts; the plan names this human check"

duration: 11 min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 13: Operations, diagnostics and troubleshooting documentation Summary

**Three new Markdown pages (operations, diagnostics, troubleshooting) and a README that leads to them, with 15 executable checks that tie every service, field, topic, status word, limit, diagnostics key and Repairs issue key to services.yaml, const.py, the translations and the tested diagnostics output**

## Performance

- **Duration:** 11 min (the machine clock is not reliable across this phase)
- **Started:** 2026-10-02T17:34:10Z
- **Completed:** 2026-10-02T17:45:43Z
- **Tasks:** 3
- **Files modified:** 6 (3 created)

## Accomplishments

- `docs/operations.md`: security limits first (advisory acknowledgements, cooperative ownership, adoption and import under the administrator's responsibility); a services table (all admin only, all with an optional response, field `device_id` explained as the instance-specific registry id and the response key `uuid`); re-trigger with its gates, statuses, reasons, refusals and topic tables; roster and heartbeat; resync; modes and companion devices (including the two similarly named devices); adoption with the exact precondition order and the returning-owner caveats; duplicate instance id; export and import with the all-or-nothing rule and the residual risk; a Limits table; upgrade notes (one-time approval lapse, ACL extension, new entities, mixed versions).
- `docs/diagnostics.md`: how to download, every key of the allow-list in tables, eight-character instance ids, one sentence each for what is never included (actions, device names, credentials and host names), and the honest note that instance names and the base topic are included.
- `docs/troubleshooting.md`: seven operating problems (entities unavailable, lapsed approvals, a denied publish that is not reported, adoption and ownership conflicts, a new instance id and the ACL, the device that exists twice, resync that did not restore entities) and one entry per Repairs issue key (all 13 keys of the English translations).
- `README.md`: new Operations section linking the three pages, extended Multiple instances (roster, companion devices, the adoption exception), current Limitations (heartbeat presence next to retained availability, adoption preconditions, the marker ignored by older versions, re-trigger reach, at-least-once delivery), a Releases section that matches `release.yml`, and a Development section with the three test tiers, their commands, the CI jobs and `MQTT_ACTIONS_REQUIRE_BROKER`. The approval-hash bullet is untouched.
- `docs/broker-acl.md`: one added limits bullet; the topic table already listed every topic family, and the tested `acl` block and `tests/broker/test_acl.py` were not changed.
- `tests/test_docs.py`: 15 new tests; the document checks read `services.yaml`, `const.py`, `translations/en.json` and the key sets of `tests/test_diagnostics.py`.

## Task Commits

Each task followed RED, then GREEN:

1. **Task 1: operations page (tracer)** - `dbe69b2` (test), `1e85233` (docs)
2. **Task 2: diagnostics and troubleshooting pages** - `776d706` (test), `8bf079b` (docs)
3. **Task 3: README, release process, test tiers, ACL consistency** - `a482d7e` (test), `a7ebed6` (docs)

**Plan metadata:** the commit that carries this summary (docs: complete plan)

## Files Created/Modified

- `docs/operations.md` - services, protocols, modes, adoption, duplicate id, export and import, limits, upgrade notes
- `docs/diagnostics.md` - contents and exclusions of the diagnostics file
- `docs/troubleshooting.md` - operating problems and one entry per Repairs issue key
- `README.md` - entry point, operations overview, releases, test tiers, current limitations
- `docs/broker-acl.md` - limits bullet on the administrator's responsibility
- `tests/test_docs.py` - executable checks for the pages

## Decisions Made

- Numbers are written in a single Limits table with the constant names in backticks, and the test reads the value and unit from `const.py`, so no number in the pages can silently go stale.
- The diagnostics test imports the key sets that `tests/test_diagnostics.py` already pins to the real output.
- Responses are shown as YAML without any `device_id` key, and wire payloads as tables, so only the service call examples carry `device_id`, always as a `data` key next to the "differs between instances and must not be used in shared actions" sentence.
- The known limitations from plans 04-09, 04-11 and 04-12 are stated as limitations, not smoothed over (recognition of a returning owner is in memory only, a delete-everywhere hub removal on a former owner could still clear an adopted-away device, a released baseline is not kept across a restart, the new instance id is not in a per-instance ACL).

## Deviations from Plan

None - plan executed exactly as written.

Notes, not deviations:

- `test_acl_document_names_every_topic_family` passed already at the RED commit of Task 3, because plans 04-03 and 04-10 left the topic table complete. It stays as a guard; no ACL change was needed there, and `tests/broker/test_acl.py` is unchanged.
- `test_security_limits_are_stated` needed one ACL sentence (the administrator's responsibility), which is the only edit to `docs/broker-acl.md`.
- The tests assert the existence of a page first, so RED failed on the planned behavior (an assertion that the page or phrase is missing) and never on a file error. `gsd_run check tdd-red-evidence` was not run: the plan is `type: execute` with `tdd="true"` tasks, and the RED failures were read from the pytest output.

## Issues Encountered

- `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear` failed once under load in the first full run of Task 1 (the known flake from plans 04-05 and 04-12) and passed alone and in every later full run (1219, 1223 and 1228 tests).
- A first draft of the operations page lacked the backticked path segment `v1`, which the wire-contract test asks for; a sentence on the protocol version was added.

## Known Stubs

None.

## Threat Flags

None. The plan's threats T-04-61 (overstated security), T-04-62 (device_id in shared examples) and T-04-63 (leaked ids or hosts; all examples use placeholders) are mitigated and tested.

## User Setup Required

None - no external service configuration required.

## TDD Gate Compliance

Each task has a `test(04-13)` commit before its `docs(04-13)` commit (the plan prescribes `docs` for the GREEN commits of these documentation tasks).

## Next Phase Readiness

- All thirteen plans of the phase have a summary; the phase is ready for verification.
- Human check still open (Task 3): read `README.md` from the top as a new user and follow the links to installation, the first operations and the troubleshooting entry of a Repairs issue.
- The first real release (a `v*.*.*` tag) and the checks with two real instances (re-trigger, adoption, duplicate id, export and import, diagnostics download) remain the end-of-phase manual checks noted in plans 04-01 to 04-12.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*

## Self-Check: PASSED

- Files exist: `docs/operations.md`, `docs/diagnostics.md`, `docs/troubleshooting.md`, `README.md`, `docs/broker-acl.md`, `tests/test_docs.py`
- Commits `dbe69b2`, `1e85233`, `776d706`, `8bf079b`, `a482d7e`, `a7ebed6` exist on `gsd/phase-04-operations-recovery-and-release`; `git rev-list --count` from the ledger base measures 6; each `test(04-13)` precedes its `docs(04-13)`
- Acceptance: `grep -c retrigger docs/operations.md` prints 4, `grep -c duplicate_instance_id docs/troubleshooting.md` prints 3, `grep -c docs/operations.md README.md` prints 2, `grep -c docs/troubleshooting.md README.md` prints 1
- Plan verification: `uv run pytest tests -q` 1228 passed, `uv run pytest -m broker tests/broker/test_acl.py -q` 13 passed, `uv run ruff check .` and `uv run ruff format --check .` exit 0
