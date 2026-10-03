---
phase: 04-operations-recovery-and-release
plan: 01
subsystem: infra
tags: [github-actions, pytest-markers, mosquitto, hacs, release]

requires:
  - phase: 03-multi-instance-sync
    provides: fake-broker multi-instance test tier and the real-Mosquitto broker tests
provides:
  - pytest tiers (unit, broker, multi_instance) selectable by marker with strict markers
  - ci.yml with one job per tier plus lint, reusable through workflow_call
  - broker tier that fails instead of skipping in CI (MQTT_ACTIONS_REQUIRE_BROKER)
  - validate.yml reusable through workflow_call
  - tag-triggered release.yml gated on version check, every tier and hassfest/HACS validation
affects: [04-operations-recovery-and-release, release, ci]

actuals:
  tokens: 4571
  tasks: 3
  commits: 6
plan_head_before: 3eb311c67d7020a375a6e312060fd1cf76c45f69
plan_head_after: 2f786d84010fc8931f82e6e66fcebbdfff68ecd8

tech-stack:
  added: []
  patterns:
    - "Tier membership by module-level pytestmark, enforced by an AST-based repository test"
    - "Local reusable workflows (workflow_call) reused by the release workflow"
    - "Environment switch that turns a skip into a failure in CI only"

key-files:
  created:
    - .github/workflows/release.yml
  modified:
    - pyproject.toml
    - .github/workflows/ci.yml
    - .github/workflows/validate.yml
    - tests/broker/conftest.py
    - tests/test_multi_instance.py
    - tests/test_fake_broker.py
    - tests/test_repo_structure.py

key-decisions:
  - "--strict-markers in pytest addopts so a mistyped marker fails collection"
  - "Release also requires hassfest/HACS validation by making validate.yml reusable"
  - "ci and validate jobs in release.yml need check-version, so a mismatching tag stops before any tier runs"
  - "Hyphenated tags (v0.2.0-rc1) are created with --prerelease"

patterns-established:
  - "Tier partition test: broker dir => broker marker, make_instance users => multi_instance, rest unmarked"
  - "Job-level reuse of local workflows is exempt from the SHA-pin rule only when the file exists"

requirements-completed: [OPS-05, OPS-06]

coverage:
  - id: D1
    description: "Test suite partitioned into unit, broker and multi_instance tiers by marker; disjoint selections cover the whole suite (788 + 40 + 11 = 839) and an unregistered marker fails the run"
    requirement: OPS-06
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_tiers_partition_the_suite"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_markers_are_registered_and_strict"
        status: pass
    human_judgment: false
  - id: D2
    description: "ci.yml has lint, unit, broker and multi-instance jobs; Mosquitto only in the broker job, which fails instead of skipping when Mosquitto is missing"
    requirement: OPS-06
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_ci_has_one_job_per_tier"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_mosquitto_is_installed_only_in_the_broker_job"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_require_broker_switch_turns_skip_into_failure"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_broker_job_sets_the_require_switch"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tag-triggered release workflow: version check against manifest.json, requires ci and validate, only the release job writes, gh release create with generated notes and no third-party action"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_release_needs_the_version_check_and_every_tier"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_only_the_release_job_can_write"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_release_checks_the_manifest_version_against_the_tag"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_release_creates_the_release_with_generated_notes"
        status: pass
    human_judgment: false
  - id: D4
    description: "The first real tag (for example v0.1.0) runs check-version, ci and validate and then creates the GitHub release with generated notes on GitHub Actions"
    requirement: OPS-05
    verification: []
    human_judgment: true
    rationale: "Cannot be exercised locally; needs a pushed tag on GitHub (end-of-phase human check from the plan)"

duration: 7min
completed: 2026-10-02
status: complete
---

# Phase 4 Plan 01: Test tiers, per-tier CI and the gated release workflow Summary

**Three pytest tiers selected by marker (unit, Mosquitto, multi-instance), a four-job CI that cannot pass vacuously, and a tag-triggered release workflow that checks the manifest version and requires every tier plus hassfest/HACS before `gh release create`**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-02T07:21:47Z
- **Completed:** 2026-10-02T07:28:32Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- `multi_instance` marker registered next to `broker`, `--strict-markers` on; the two `make_instance` modules carry `pytestmark = pytest.mark.multi_instance`. Selections: 788 unit + 40 multi-instance + 11 broker = 839 tests, none empty.
- `ci.yml` split into `lint`, `unit`, `broker`, `multi-instance`; Mosquitto installed only in `broker`, which sets `MQTT_ACTIONS_REQUIRE_BROKER: "1"` so a missing binary fails instead of skipping (a local run without Mosquitto still skips).
- `ci.yml` and `validate.yml` are reusable (`workflow_call`) and ignore `v*.*.*` tag pushes; new `release.yml` runs `check-version`, then `ci` and `validate`, then `release` (only job with `contents: write`).
- `tests/test_repo_structure.py` pins all of it: markers, tier partition (AST scan), per-tier jobs, require switch, reusable workflows, release gating, permissions, no actions in the release job.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Tracer, the tier split end to end** - `c1d6259` (test), `452b4a2` (feat)
2. **Task 2: The broker tier cannot pass vacuously** - `ce2ca88` (test), `56db2f9` (feat)
3. **Task 3: Reusable CI and validation, and the release workflow** - `a08d57e` (test), `2f786d8` (feat)

**Plan metadata:** committed with this summary (docs: complete plan)

## TDD Gate Compliance

RED precedes GREEN for all three tasks (`test(04-01)` commits `c1d6259`, `ce2ca88`, `a08d57e` before `feat(04-01)` commits `452b4a2`, `56db2f9`, `2f786d8`). Each RED failed on the planned assertion (unregistered marker, untagged modules, single `test` job; missing switch and env; missing release.yml and `workflow_call`/`tags-ignore`). One test, `test_mosquitto_is_installed_only_in_the_broker_job`, already passed at RED because Task 1 had moved the install step into the `broker` job; it is a regression guard for the prohibition, not a driver of new behavior. No refactor commits were needed. Tracer gate: the Task 1 verify chain was re-run end to end after the GREEN commit (all passed) before expansion.

## Files Created/Modified
- `.github/workflows/release.yml` - tag-triggered release: version check, reuse of ci and validate, `gh release create --verify-tag --generate-notes` (+ `--prerelease` for hyphenated tags)
- `.github/workflows/ci.yml` - four tier jobs, `workflow_call`, `tags-ignore` for version tags, require-broker env on the broker job
- `.github/workflows/validate.yml` - `workflow_call` and `tags-ignore` added; jobs and schedule untouched
- `pyproject.toml` - `multi_instance` marker, `addopts = "--strict-markers"`
- `tests/broker/conftest.py` - `_broker_unavailable` helper (fail or skip by `MQTT_ACTIONS_REQUIRE_BROKER`, read at call time) used by both missing-binary sites
- `tests/test_multi_instance.py`, `tests/test_fake_broker.py` - module-level `multi_instance` marker
- `tests/test_repo_structure.py` - `release.yml` in `WORKFLOW_FILES`, steps-less jobs tolerated, local reusable refs allowed only when the file exists, 13 new checks

## Decisions Made
- `--strict-markers` in `addopts` (plan assumption, now decided).
- `ci` and `validate` jobs in `release.yml` also `needs: check-version`, so a tag that differs from `manifest.json` stops at `check-version` without spending runner time on the tiers (matches the plan's done criterion "a mismatching tag stops at check-version").
- The tag name is only read as a shell variable (`GITHUB_REF_NAME`), validated against a semantic-version pattern before any output, and never interpolated with an expression; a test asserts no `${{` appears in `check-version` scripts.
- `test_fake_broker.py` is tagged as a whole module, so its `mqtt_mock`-based seam tests run in the multi-instance tier (tier membership is by module, per the plan's assumption; no test was touched).

## Deviations from Plan

None - plan executed exactly as written. (Two small test-quality adjustments inside Task 2's RED, not plan deviations: the require-broker test catches skip or fail and asserts the type, so an unmet expectation reports as a failure instead of a skip, and the unneeded `noqa: SLF001` directives were dropped because that rule is not enabled.)

## Issues Encountered
None. `actionlint` is not installed locally, so the workflow files are validated by the repository tests and a manual run of the version-check logic (`v0.1.0` matches `0.1.0`, `v0.2.0` mismatches), not by a workflow linter.

## User Setup Required
None - no external service configuration required. End-of-phase human check (plan Task 3, `<human-check>`): after the phase is merged, push the first tag (for example `v0.1.0`, equal to the manifest version) and confirm in GitHub Actions that Release runs `check-version`, `ci` and `validate` before it creates the GitHub release with generated notes.

## Threat Flags

None. The surfaces added (tag-triggered workflow, `contents: write` on the release job, tag name reaching a script) are the ones in the plan's threat model (T-04-01 to T-04-05), each mitigated and pinned by a repository test.

## Known Stubs

None.

## Next Phase Readiness
- Test tiers and CI are in place; later plans in this phase add tests that must carry the right tier marker (the partition test fails otherwise).
- `release.yml` is untested on GitHub until the first real tag is pushed.

## Self-Check: PASSED

- Created/modified files exist: `.github/workflows/release.yml`, `.github/workflows/ci.yml`, `.github/workflows/validate.yml`, `pyproject.toml`, `tests/broker/conftest.py`, `tests/test_repo_structure.py` found on disk.
- Commits found in `git log`: `c1d6259`, `452b4a2`, `ce2ca88`, `56db2f9`, `a08d57e`, `2f786d8`.
- Plan verification re-run: `uv run pytest tests -q` 839 passed; tier selections 788 / 40 / 11 passed; `ruff check` and `ruff format --check` clean.

---
*Phase: 04-operations-recovery-and-release*
*Completed: 2026-10-02*
