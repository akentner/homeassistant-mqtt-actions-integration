---
phase: 05-evaluate-native-switch-select-entities-instead-of-mqtt-disco
plan: 09
subsystem: docs
tags: [documentation, release, native-entities, discovery-export, uat]

requires:
  - phase: 05-08
    provides: the export options, the legacy-only machinery and the native cleanup that the pages describe
provides:
  - README with native entities text, Upgrading from 0.1.x and MQTT Discovery export sections and updated Limitations
  - Operations, troubleshooting and ACL pages that name the legacy path and the export prefix
  - Five documentation tests that pin the upgrade and export claims and the removal of the old claims
  - PROJECT.md and REQUIREMENTS.md amendments and manifest version 0.2.0
affects: [release]

plan_head_before: 04e7aa5fee2711093b0e4b5a4ae9195a434411c4
plan_head_after: 3cc244db54da5e33437e05fd4250b8680d5fc00a
actuals:
  tokens: 14000
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Documentation claims about a one-way migration are pinned by phrase tests in tests/test_docs.py, like the Phase 4 pages"

key-files:
  created: []
  modified:
    - README.md
    - docs/operations.md
    - docs/troubleshooting.md
    - docs/broker-acl.md
    - tests/test_docs.py
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md
    - custom_components/mqtt_actions/manifest.json

key-decisions:
  - "The documented acl block is unchanged (a superset for the legacy path and the export, enforced by the broker test); only the explanation and the topic table changed, with a new <export prefix>/ row"
  - "ENT-03 is marked complete because the export and its documented duplicate warning are delivered; the real-instance UAT stays a separate human step"
  - "The tag and the GitHub release are not created here; the version is only bumped to 0.2.0"

patterns-established:
  - "The legacy path is described in every page as the path of a device while an older instance is online, so a fully upgraded fleet needs neither the test topic nor the discovery prefix"

requirements-completed: [ENT-01, ENT-02, ENT-03, MIG-01, MIG-02, MIG-03, DEC-01]

duration: about 35min
completed: 2026-10-03
status: complete
---

# Phase 5 Plan 09: Documentation, Project Record and Release Version Summary

**The README and the docs pages now describe native entities, the automatic one-way upgrade from 0.1.x and the optional Discovery export with its duplicate warning, pinned by five new tests; the project record names ADR 0001 and the manifest reads 0.2.0.**

## Performance

- **Duration:** about 35 min
- **Tasks:** 2 (task 1 TDD with a separate RED commit; task 2 automated part)
- **Files:** 8 modified

## Accomplishments

- `README.md`: the introduction, Requirements, Setup, multiple-instances bullets, Operations, deletion, topic contract, Behavior, Limitations and Security text follow the code. New sections `## Upgrading from 0.1.x` (automatic and one-way, what is kept, when an instance switches, `native_cutover_waiting`, stragglers lose the entities without a hint, no rollback and `_2` duplicates, removal removes the entities, no concurrent adoption between old and new, first release 0.2.0) and `## MQTT Discovery export` (optional, off by default, the two hub options, default prefix `mqtt_actions_export`, `enabled_by_default` false, no healing, no test buttons, the duplicate warning for the core prefix).
- `docs/operations.md`: `device_id` is the registry id of the device of MQTT Actions; "Modes and companion devices" became "Modes and devices"; resync and the upgrade notes follow the native model.
- `docs/troubleshooting.md`: new sections "Duplicate _2 entities after a downgrade" and "Entities are missing on an older instance"; `mqtt_discovery_disabled`, `discovery_removed`, the device-exists-twice and resync sections limited to the legacy path and the export.
- `docs/broker-acl.md`: the test-topic row is legacy-only, new `<export prefix>/` row, the discovery-prefix write access is now a legacy-path and export concern; the `acl` block is untouched and the broker tests still pass.
- `tests/test_docs.py`: five new tests (native entities and upgrade, export, old claims gone, ACL export row with a single `acl` block, upgrade problems in troubleshooting).
- `.planning/PROJECT.md`: What This Is, Active list and Platform constraint amended, Key Decisions row "Native entities instead of MQTT Discovery" (Accepted, ADR 0001). `.planning/REQUIREMENTS.md`: ENT-03 complete (the other six were already complete), DSC-01 to DSC-04 annotated. Manifest version 0.2.0.

## Task Commits

1. **Task 1 RED:** `71fa7df` (test) - failing documentation checks
2. **Task 1 GREEN:** `adb57e8` (docs) - README, operations, troubleshooting and ACL pages
3. **Task 2:** `3cc244d` (docs) - project record amendments and version 0.2.0

## Verification

- `uv run pytest tests -q`: 1403 passed (full run); tiers separately: `-m "not broker and not multi_instance"` 1221 passed, `-m multi_instance` 165 passed, `-m broker` 17 passed, `tests/test_repo_structure.py` 40 passed.
- `uv run ruff check .` and `uv run ruff format --check .` pass.
- Acceptance greps: "Upgrading from 0.1" 4 in README, `<export prefix>` 1 in the ACL page, `native_cutover_waiting` 1 in README, "ADR 0001" 5 in PROJECT.md, 7 checked ENT, MIG and DEC rows.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale-claim test was too broad**
- **Found during:** Task 1 GREEN
- **Issue:** `test_old_discovery_claims_are_gone` rejected the phrase "belong to the core mqtt integration and its own device", which the operations page legitimately keeps for a device on the legacy path.
- **Fix:** The operations sentence was reworded and the test now rejects "stay on the core mqtt device" and requires the page to mention the legacy path.
- **Files modified:** `docs/operations.md`, `tests/test_docs.py`
- **Commit:** `adb57e8`

Otherwise the plan was executed as written. Each statement was checked against the code (export covers owned native devices, resync republishes the export, option change applies without a reload, discovery-disabled issue only while discovery is needed).

## Pending Human Verification (not performed)

The real-instance UAT of task 2 (`<human-check>`) was NOT run by the executor: it needs the two Home Assistant instances and the Mosquitto container of `~/ha-test`. Results belong in the phase verification file. Items to settle:

1. Upgrade path (A4): entity ids, registry ids and device ids unchanged, history continuous, entities on the MQTT Actions page, no retained discovery for the devices.
2. Integration page counting (A1): all devices and entities of the other instance appear with the owner named.
3. Mixed fleet and live follower cutover (A5): Repairs issue while the second instance is on v0.1.0; both switch without a manual step, customizations kept.
4. Straggler: a v0.1.0 instance after the cutover keeps running actions, shows no entities, raises no error.
5. Replay race (A4): a re-published legacy discovery payload before two restarts creates no `_2` duplicate.
6. Commands: toggling runs the actions once on every approved instance; a payload that matches no StateValue is ignored.
7. Export: on, retained payloads with `enabled_by_default` false and no buttons; prefix `homeassistant` yields only disabled duplicates; off clears the topics.
8. Delete and removal: deleting an owned device and removing the integration remove the entities.

Release follow-up (human, after merge and a green Validate run): tag `v0.2.0` and the GitHub release. Nothing was pushed or tagged.

## Known Stubs

None.

## Threat Flags

None. The plan changes documentation, planning files and the manifest version only (T-5-18 mitigated by the new tests).

## Self-Check: PASSED

- README.md, docs/operations.md, docs/troubleshooting.md, docs/broker-acl.md, tests/test_docs.py, .planning/PROJECT.md, .planning/REQUIREMENTS.md and the manifest exist and contain the changes.
- Commits 71fa7df, adb57e8 and 3cc244d exist; `git rev-list --count 04e7aa5..HEAD` was 3 before this summary.
