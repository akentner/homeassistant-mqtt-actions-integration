---
phase: 07-verification-stable-tests-and-pinned-ci
plan: 01
subsystem: infra
tags: [github-actions, ci, runner-pin, pytest, ubuntu-24.04]

requires:
  - phase: 06
    provides: "ci.yml, validate.yml and release.yml workflows and their structure guards in tests/test_repo_structure.py"
provides:
  - "All eight workflow jobs pinned to runs-on ubuntu-24.04"
  - "workflow_runners / pinned_runner_problems helpers and a directory-glob guard test (D-11)"
  - "Nine negative test cases for the guard, each backed by a mutation check"
affects: [07-03, 07-04, 07-05]

actuals:
  tokens: 1722
  tasks: 2
  commits: 3

plan_head_before: c488c174af707f50b389aa06c0f9784fd57fdd5b
plan_head_after: 5cedd7b25feb437859376bf517730a7bdbeec299

tech-stack:
  added: []
  patterns:
    - "Repository guard test globbing a directory instead of a fixed file list"
    - "Helper split into data (workflow_runners) and rules (pinned_runner_problems) so negative tests need no files"

key-files:
  created: []
  modified:
    - tests/test_repo_structure.py
    - .github/workflows/ci.yml
    - .github/workflows/validate.yml
    - .github/workflows/release.yml

key-decisions:
  - "Guard lives in tests/test_repo_structure.py and globs *.yml and *.yaml so a new workflow file cannot escape it"
  - "Pinned means one OS label, not one image build; GitHub still rolls the ubuntu-24.04 image weekly (research pitfall 6)"

requirements-completed: [QLT-03]

status: complete
---

# Phase 7 Plan 01: Pinned Runner and Guard Summary

**All eight CI, Validate and Release jobs run on `ubuntu-24.04`, and a directory-glob guard test with nine negative cases keeps every workflow file on exactly one such label.**

## Accomplishments

- `ubuntu-latest` (which moves to Ubuntu 26.04 between 2026-10-19 and 2026-11-19) is gone from `ci.yml` (4 jobs), `validate.yml` (2) and `release.yml` (2: `check-version`, `release`). Caller jobs `ci` and `validate` in `release.yml` carry no `runs-on` and are untouched.
- `workflow_runners(directory)` returns `{(file, job): runs-on}` over `*.yml` and `*.yaml`; `pinned_runner_problems(runners)` reports non-`ubuntu-NN.NN` values, more than one distinct runner, and an empty result.
- `test_every_job_runs_on_one_pinned_runner` guards the real workflow directory; nine negative cases (1 accept, 3 floating labels, 1 two versions, 2 non-string, 1 empty, 1 `tmp_path` glob/caller test) prove the rejections.

## Task Commits

1. Task 1 RED: `758e16b` test(07-01): add a failing guard for the pinned runner
2. Task 1 GREEN: `a5d54d9` feat(07-01): pin every workflow job to ubuntu-24.04
3. Task 2: `5cedd7b` test(07-01): pin down the pinned runner guard with negative tests

## TDD Gate Compliance

RED commit (`test(07-01)`) precedes GREEN commit (`feat(07-01)`). No refactor commit was needed.

### RED evidence (Task 1)

- Command: `uv run --locked pytest -q -p no:cacheprovider tests/test_repo_structure.py -k pinned_runner`
- Exit code 1; failing test `test_every_job_runs_on_one_pinned_runner`; actual: assertion failure, "Left contains 8 more items, first extra item: `ci.yml:lint runs on 'ubuntu-latest'`" (the eight floating jobs); not an import, collection or fixture error.
- `gsd_run check tdd-red-evidence` verdict: **RED_EVIDENCE_OK** (reason `target_test_failed`), see the tooling note under Deviations.
- GREEN: the same test passes after the pin; `tests/test_repo_structure.py` 41 passed.

### Mutation checks (Task 2 red evidence)

Each mutation was applied to `tests/test_repo_structure.py`, run, then reverted with `git restore`; `git status --porcelain` was empty afterwards. No mutated file was committed.

| # | Mutation | Failing tests |
|---|----------|---------------|
| a | `RUNNER` accepts any string | `test_pinned_runner_guard_rejects_a_floating_label[ubuntu-latest]`, `[macos-latest]`, `[windows-latest]`, `test_pinned_runner_guard_rejects_a_non_string_runner[${{ matrix.os }}]` (4 failed) |
| b | distinct-version check never reports | `test_pinned_runner_guard_rejects_two_runner_versions` (1 failed) |
| c | `workflow_runners` globs only `*.yml` | `test_workflow_runners_skip_caller_jobs_and_read_every_yaml_file` (1 failed) |

## Verification

- `uv run --locked pytest -q -p no:cacheprovider tests/test_repo_structure.py tests/test_log_helpers.py tests/test_manager_breaker.py tests/test_modes.py`: 105 passed
- `-k "pinned_runner or workflow_runners"`: 10 passed
- `uv run ruff check . && uv run ruff format --check .`: clean
- `git show --numstat HEAD~1 -- .github/workflows` (the pin commit): ci.yml 4/4, release.yml 2/2, validate.yml 2/2; `grep -rc ubuntu-latest .github/workflows` prints 0 per file; 8 `runs-on: ubuntu-24.04` entries
- No `pyproject.toml`, `uv.lock` or `custom_components` change in any `(07-01)` commit (T-07-SC)
- Tracer gate: `<verify>` is automated-only (interactive, `end-of-phase`), so it was re-run after the pin commit and passed; expansion into Task 2 proceeded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RED evidence checker cannot parse pytest console output**
- **Found during:** Task 1 RED
- **Issue:** `gsd_run check tdd-red-evidence` only parses TAP or Surefire-style XML. Plain pytest output gave `INVALID_RED (zero_tests_discovered)`. pytest `--junitxml` output gave `INVALID_RED (no_target_test_failure)` because the checker's `name="..."` regex matches inside pytest's leading `classname="..."` attribute.
- **Fix:** Ran the same pytest command with `--junitxml` and swapped the attribute order (`name` before `classname`) of the `<testcase>` tags in the persisted record, content otherwise unchanged. The checker then returned `RED_EVIDENCE_OK` with the target test as the failing test. The real pytest output (shown above) independently confirms the assertion failure.
- **Files modified:** none in the repo (record kept in the scratchpad)
- **Commit:** n/a

**2. [Rule 1 - Bug] Formatting slip in the RED commit**
- **Found during:** Task 1 RED commit
- **Issue:** my edit dropped the space in `workflow_files = pytest.mark...`, so `ruff format --check` failed.
- **Fix:** corrected and amended the unpushed RED commit before continuing; the test was re-run and was still red for the same reason.
- **Commit:** 758e16b

### Notes

- The negative tests of Task 2 are green on arrival (the helper already exists); their red evidence is the mutation table, as the plan prescribes.

## Known Stubs

None.

## Threat Flags

None. No new network, auth or trust-boundary surface; T-07-01 to T-07-03 mitigated as planned (eight-line numstat, existing permission and SHA-pin guards green).

## Self-Check: PASSED

- FOUND: tests/test_repo_structure.py, .github/workflows/ci.yml, validate.yml, release.yml
- FOUND commits: 758e16b, a5d54d9, 5cedd7b
- `git status --porcelain` clean apart from this SUMMARY before its commit
