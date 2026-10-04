# Phase 7: Verification, Stable Tests and Pinned CI - Research

**Researched:** 2026-10-04
**Domain:** Test determinism (pytest + pytest-homeassistant-custom-component), GitHub Actions runner pinning, GSD verification-staleness mechanics
**Confidence:** HIGH (every central finding was reproduced or read in this session; the few `[ASSUMED]` items are listed in the Assumptions Log)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### QLT-01: re-verification of Phases 1 to 4
- **D-01:** Each of Phases 1 to 4 is re-verified by running the `gsd-verifier` agent against the current code. The report
  and its digest are regenerated, so `init.manager` can no longer read them as stale. No hand-edited frontmatter.
- **D-02:** The new reports overwrite the existing `*-VERIFICATION.md` in `.planning/milestones/v1.0-phases/<phase>/`
  (history stays in Git). No phase directories are revived under `.planning/phases/`, no side-by-side files.
- **D-03:** A gap caused by intended later behavior (for example Phase 5 native entities replacing MQTT Discovery) is
  recorded in the report as "superseded by Phase 5". A real regression becomes a fix plan inside this phase.
- **D-04:** The human-verification items of the old reports are covered by the automated tiers (real Mosquitto,
  multi-instance); the verifier may cite those tests. Real-instance checks stay in Phase 8, not repeated here.

### QLT-02: the flake and the three-run proof
- **D-05:** Diagnose before fixing. The flake does not occur when the test runs alone (25 of 25 passed during this
  discussion), so reproduce it first with repeated full-suite runs or load, capture the traceback or log, then determine
  the cause (test isolation, teardown race, subscription removal ordering in `_async_remove_device`, `manager.py:2126`).
- **D-06:** The fix goes where the cause is: a race in production code is fixed in production code, a test
  synchronization problem makes the test deterministic (events, no sleeps). No retry decorator, no skip, no xfail.
- **D-07:** TDD: if the race can be forced, a deterministic reproducer test is committed first (red on current code,
  green after the fix). If it cannot be forced, the stress proof stands alone and the reason is documented.
- **D-08:** Stress proof: 50 consecutive error-free repetitions of the test under load, on top of the three-run proof.
- **D-09:** Three consecutive full-suite runs (unit, broker, multi_instance) are shown both locally (3 runs with
  Mosquitto) and in CI (3 consecutive green runs on the pinned runner via push or `workflow_dispatch`).

### QLT-03: pinned runner
- **D-10:** Pin `ubuntu-24.04` for every job in `ci.yml`, `validate.yml` and `release.yml` (8 `runs-on` entries at the time
  of discussion, `ci.yml` has 4, `validate.yml` 2, `release.yml` 2). Mosquitto stays installed via `apt` as today.
  Verify in research which image `ubuntu-latest` currently resolves to (it was assumed, not checked, to be 24.04) and
  whether `ubuntu-24.04` is still a supported image.
- **D-11:** A test in the suite reads `.github/workflows/*.yml` and fails on any `*-latest` runner or on more than one
  distinct runner version across the workflows. Same pattern as `tests/test_docs.py` (pin docs to code).

### QLT-03: prerelease proof
- **D-12:** The release proof is a prerelease tag run: set the manifest version to `1.0.1-rc1` on the phase branch, tag
  `v1.0.1-rc1`; `check-version`, CI, validate and release must all pass on the pinned runner (`release.yml` already marks
  a hyphenated tag as prerelease).
- **D-13:** Pushing the tag creates a public GitHub release in the HACS repo, so the executor MUST stop and ask for
  explicit approval before the tag push. After a green run, the prerelease and the tag are deleted and the manifest
  version is reset (the real 1.0.1 release belongs to the end of the milestone). The run URL and per-job result are
  recorded in the phase VERIFICATION.

### Claude's Discretion
- How the load for the flake reproduction is generated (loop, `xdist`, CPU stress) and the exact stress harness.
- Plan split and order (re-verification must run after the flake fix and pinned runner so it covers the final code).
- Format of the workflow guard test and how the CI run results are recorded.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QLT-01 | Phases 1 to 4 have a current verification; `init.manager` no longer reports them as stale | Finding A: `init.manager` does not list archived phases at all; the real stale signal is `verification status <archived dir>`, currently `stale` for all of Phases 1 to 5 because the stored `covered_files` point to `.planning/phases/...` paths that no longer exist. Finding B: a regenerated fingerprint with archived paths reads `passed` (reproduced). Ordering rule: re-verify last. |
| QLT-02 | Full suite passes three consecutive runs; the known flake no longer occurs | Finding C: the flake cause is a test-scope defect (an assertion that counts the foreign `asyncio` slow-callback WARNING), reproduced deterministically; `own_warnings` already fixes the named test, but two more tests have the identical defect and are exposed by a deterministic probe. No production race exists. |
| QLT-03 | CI and release workflows run on a pinned runner version and pass | Finding D: `ubuntu-latest` resolves to `ubuntu-24.04` today and moves to 26.04 between 2026-10-19 and 2026-11-19. Pin `ubuntu-24.04` in 8 jobs, guard it with a test in `tests/test_repo_structure.py`, prove it with 3 `workflow_dispatch` CI runs and one `v1.0.1-rc1` tag run. |
</phase_requirements>

## Summary

This phase adds no feature and no new dependency. It is three independent pieces of hygiene on top of the Phase 6 code: (1) regenerate four `*-VERIFICATION.md` reports so GSD's fingerprint check reads them as current, (2) remove the load-dependent test flake and prove determinism, (3) pin the runner image and prove CI, Validate and Release on it.

Three findings change the shape of the plans compared with the CONTEXT assumptions. First, `init.manager` only lists the active milestone's phases (6, 7, 8, 999.1), so success criterion 1 is vacuously true today; the real, checkable signal is `verification status <phase dir>` on the archived directories, which reports `stale` for every one of Phases 1 to 5 right now (root cause: the reports' `covered_files` name `.planning/phases/...` paths that moved to `.planning/milestones/v1.0-phases/...`, and the fingerprint fails closed). Second, the flake is not a race: it is a test-scope defect. PHACC turns on asyncio debug mode for every test, so a callback that runs longer than 0.1 s under load makes the `asyncio` logger emit a WARNING that `caplog` captures; the named test counted it. Commit `b6e9589` already scoped that one assertion with `own_warnings`, and it has not been seen since, but two other tests have the identical defect and a deterministic probe (force every callback to count as slow) fails exactly those two. Third, `ubuntu-latest` moves to Ubuntu 26.04 starting 2026-10-19, 15 days from now, so the pin is time-sensitive.

**Primary recommendation:** Order the work as (a) QLT-02 test fix under a permanent "always slow loop" probe, (b) QLT-03 pin plus guard test, (c) CI proof (3 dispatch runs) then the approval-gated rc tag run, (d) QLT-01 re-verification last, because every workflow, test and source file edited in (a) to (c) is inside the covered-file digests of Phases 1 to 4.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deterministic log assertions | Test harness (`tests/conftest.py`, `tests/log_helpers.py`) | — | The defect is in what tests count, not in `custom_components/`. No production change. |
| Runner pin | CI platform (`.github/workflows/*.yml`) | Test harness (guard test) | The label is the pin; the guard test keeps it pinned. |
| Release proof (prerelease tag) | CI platform (`release.yml` on GitHub) | Git remote (tag, public Release) | Only a real tag push exercises `check-version`, CI, Validate and the release job. |
| Verification freshness | Planning tooling (`gsd-verifier`, `verification.cjs`) | Git (content digest of covered files) | Staleness is a content digest over the covered files, not a timestamp. |
| Three-run proof | Local dev machine (uv + Mosquitto) | CI platform (3 dispatch runs) | D-09 asks for both. |

## Standard Stack

No package is added or changed. The proof uses what is already pinned.

### Core
| Tool | Version | Purpose | Why |
|------|---------|---------|-----|
| pytest | 9.0.3 | Test runner | [VERIFIED: `uv pip list` in the project venv] |
| pytest-homeassistant-custom-component (PHACC) | 0.13.367 | `hass`, `mqtt_mock`, `caplog`-compatible harness, enables loop debug | [VERIFIED: `uv pip list`; `pyproject.toml` `dev` group pins `pytest-homeassistant-custom-component==0.13.367`] |
| homeassistant | 2026.9.4 | Host under test | [VERIFIED: `uv pip list`] |
| ruff | 0.16.10 | Lint and format, `select = ["ALL"]` | [VERIFIED: `pyproject.toml` `ruff==0.16.10`] |
| uv | 0.12.7 local | Env and runner | [VERIFIED: `uv --version`] |
| gh | 2.102.0 | Dispatch CI, watch runs, create and delete the rc release | [VERIFIED: `gh --version`; authenticated as `akentner`] |
| PyYAML | already imported by `tests/test_repo_structure.py` | Parse workflows in the guard test | [VERIFIED: `tests/test_repo_structure.py:1-12` imports `yaml`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Shell loop for the 50 repetitions | `pytest-repeat` (`--count=50`) | The legitimacy seam rated it `SUS` (unknown downloads, no repository), and the project rule is to add nothing beyond PHACC. A bash loop costs about 2 minutes. Do not add it. |
| Repeating the node id on the command line | `--keep-duplicates` | Does not work: 50 identical node ids still collect one test (verified: `1 passed`). |
| Hand-editing `covered_digest` | `verification.fingerprint` | Forbidden by D-01 and by the verifier's own rule ("never hand-write `covered_digest`"). |

**Installation:** none.

## Package Legitimacy Audit

No external package is installed by this phase.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pytest-repeat (evaluated, not used) | PyPI | latest release 2025-04-07 | unknown | none in registry metadata | [SUS] | Not adopted; a shell loop replaces it |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** pytest-repeat (evaluated only; not part of any plan)

## Architecture Patterns

### System Architecture Diagram

```
 phase branch (Phase 6 code + Phase 7 edits)
        |
        v
 [A] QLT-02: conftest autouse "always slow loop"  --RED-->  2 tests fail (breaker trip, observe)
        |   scope those assertions to own loggers  --GREEN->  suite passes with noise always on
        v
 [B] QLT-03: runs-on: ubuntu-24.04 (8 jobs)  <--guard-->  tests/test_repo_structure.py (glob *.yml)
        |
        v
 local proof: 50x known test (under CPU load) + 3x full suite (MQTT_ACTIONS_REQUIRE_BROKER=1)
        |
        v   git push branch
 [C] GitHub: gh workflow run ci.yml x3 (dispatch)  +  validate.yml x1  --> green on ubuntu-24.04
        |
        v   *** human approval gate (D-13) ***
 tag v1.0.1-rc1 (manifest 1.0.1-rc1) --> release.yml:
      check-version -> [ci, validate] (workflow_call) -> release (prerelease)
        |
        v   gh release delete --cleanup-tag ; manifest back to 1.0.0
 [D] QLT-01: gsd-verifier x4 (archived dirs) -> verification.fingerprint -> `verification status` = passed
```

### Recommended Project Structure
```
tests/conftest.py                 # + autouse always-slow-loop fixture (QLT-02)
tests/log_helpers.py              # existing own_warnings, reused
tests/test_repo_structure.py      # + workflow runner guard (QLT-03), next to the existing workflow tests
.github/workflows/{ci,validate,release}.yml   # runs-on: ubuntu-24.04
.planning/milestones/v1.0-phases/0{1..4}-*/0N-VERIFICATION.md   # overwritten (D-02)
.planning/phases/07-.../07-VERIFICATION.md    # run URLs and per-job results (D-13)
```

### Pattern 1: Make the nondeterministic input constant (always-slow loop)
**What:** PHACC enables loop debug mode for every test. `[VERIFIED: .venv/lib/python3.14/site-packages/pytest_homeassistant_custom_component/plugins.py:407-410]`:
```python
@pytest.fixture(autouse=True)
async def enable_event_loop_debug() -> None:
    """Enable event loop debug mode."""
    asyncio.get_running_loop().set_debug(True)
```
In debug mode asyncio logs `Executing <handle> took N seconds` at WARNING for any callback slower than `loop.slow_callback_duration` (0.1 s default). Setting that threshold to 0.0 makes every callback "slow", so the noise a loaded machine produces occasionally is present always, and any assertion that depends on its absence fails every time instead of once in a hundred runs.
**When to use:** permanently, as an autouse fixture in `tests/conftest.py` (recommended), or env-gated if the owner dislikes noisy failure output (captured logs only print for failing tests).
**Evidence:** In a scratch copy of the repo at HEAD, adding the fixture below and running `pytest tests -m "not broker" -n 6` gave `2 failed, 1461 passed in 30.05s`; the two failures are `tests/test_manager_breaker.py::test_change_after_max_runs_trips_pauses_and_informs` (`assert 7 == 1`, seven asyncio records counted as warnings) and `tests/test_modes.py::test_observe_logs_and_runs_nothing_but_tracks_the_baseline` (`assert 6 == 1`, the asyncio record names the test coroutine `test_observe_logs...` and matches the `"observe"` substring filter). `[VERIFIED: local experiment 2026-10-04]`
```python
# tests/conftest.py (works with PHACC's autouse fixture order because it depends on it)
import asyncio

@pytest.fixture(autouse=True)
async def always_slow_event_loop(enable_event_loop_debug: None) -> None:
    """Count every callback as slow so asyncio logs its slow-callback WARNING all the time (QLT-02)."""
    asyncio.get_running_loop().slow_callback_duration = 0.0
```

### Pattern 2: Scope log assertions to the integration's own loggers
**What:** Use the existing helper. `[VERIFIED: tests/log_helpers.py:11-26]`:
```python
OWN_LOGGER = "custom_components.mqtt_actions"

def own_warnings(caplog: pytest.LogCaptureFixture, *, exact: bool = False) -> list[logging.LogRecord]:
    ...
    return [
        record
        for record in caplog.records
        if record.name.startswith(OWN_LOGGER)
        and (record.levelno == logging.WARNING if exact else record.levelno >= logging.WARNING)
    ]
```
**Apply to (found by the probe plus a grep sweep):**
- `tests/test_manager_breaker.py:94-95` `_warnings` is `[record for record in caplog.records if record.levelno == logging.WARNING]`: replace the body with `own_warnings(caplog, exact=True)` (line 147 asserts `len(warnings) == 1`; line 451 already adds a name filter).
- `tests/test_modes.py:134` `lines = [record.getMessage() for record in caplog.records if "observe" in record.getMessage().lower()]`: add `record.name.startswith(OWN_LOGGER)` (other tests in the suite already do, for example `tests/test_trust.py:236`).
- Hardening, optional because the probe passes today: `tests/test_hub_removal.py:277` filters only on level and the substring `"MQTT"` (an asyncio record whose task repr contains `MQTT` would match); add the own-logger filter.

### Pattern 3: Workflow runner guard (D-11)
**What:** One helper that returns the runner of every job that has `runs-on`, plus tests on the real files and negative tests on `tmp_path` YAML (the `tests/test_log_helpers.py` pattern: helper plus a test that proves the helper rejects what it should). Put it in `tests/test_repo_structure.py`, which already has `WORKFLOWS`, `_load_workflow`, `_all_jobs` and the other workflow guards `[VERIFIED: tests/test_repo_structure.py:18-19, 38-42, 354-357]`; use a glob (`*.yml` and `*.yaml`) instead of the fixed `WORKFLOW_FILES` tuple so a new workflow file cannot escape the guard.
```python
RUNNER = re.compile(r"^ubuntu-\d{2}\.\d{2}$")

def workflow_runners(directory: Path) -> dict[tuple[str, str], Any]:
    """Return the runs-on value of every job that declares one; a reusable-workflow caller job has none."""
    runners: dict[tuple[str, str], Any] = {}
    for path in sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")]):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (document.get("jobs") or {}).items():
            if "runs-on" in job:
                runners[(path.name, name)] = job["runs-on"]
    return runners

def test_every_job_runs_on_one_pinned_runner() -> None:
    runners = workflow_runners(WORKFLOWS)
    assert runners, "no workflow job declares a runner"
    for (filename, job), runner in runners.items():
        assert isinstance(runner, str) and RUNNER.match(runner), f"{filename}:{job} runs on {runner!r}"
    assert len(set(runners.values())) == 1, f"more than one runner version: {sorted(set(runners.values()))}"
```
Jobs that only call a reusable workflow (`ci`, `validate` in `release.yml`) carry `uses:` and no `runs-on` `[VERIFIED: .github/workflows/release.yml:35-47]`, so they must be skipped, not failed. The guard goes red at HEAD (eight `ubuntu-latest` entries) and green after the pin, which is the TDD order for this part.

### Pattern 4: Rebase `covered_files` to the archived directory, then fingerprint
**What:** The verifier writes `covered_files` as project-root-relative paths and `covered_digest` from `verification.fingerprint`. For an archived phase, spawn the verifier with `PHASE_DIR=.planning/milestones/v1.0-phases/<phase dir>` and list the phase's PLAN and SUMMARY files under that archived path. The verifier's report template writes to `.planning/phases/{phase_dir}/...`; the spawn prompt must override the output path to the archived directory (D-02).
**Reproduced:** In a scratch copy, Phase 1's `covered_files` rewritten from `.planning/phases/...` to `.planning/milestones/v1.0-phases/...` (45 files, all present) with a digest from `verification fingerprint` read `status: passed`; appending one line to a covered source file flipped it to `stale`; restoring the file read `passed` again. `[VERIFIED: local experiment 2026-10-04]`

### Anti-Patterns to Avoid
- **Retry, skip or xfail** on the flaky test: forbidden by D-06 and the success criterion.
- **`sleep` to "settle" logs:** the problem is what is counted, not when.
- **Suppressing the `asyncio` logger globally** (`logging.getLogger("asyncio").setLevel(ERROR)`): hides a real signal in every test; scoping assertions fixes the cause.
- **Re-verifying before the last code edit:** the digests cover the workflows, tests and sources this phase edits.
- **Hand-editing frontmatter or `covered_digest`** (D-01).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Repeating a test 50 times | A custom plugin or parametrization hack | A bash `for` loop around `uv run pytest <node id>` | No new dependency; `--keep-duplicates` does not repeat node ids. |
| CPU load | A stress binary | `taskset` plus busy loops (`taskset -c 0,1 sh -c 'while :; do :; done'`) | `stress-ng` is not installed; this worked here (unit tier passed pinned to 2 cores next to 4 spinners, 194.5 s). |
| Fingerprint of covered files | Manual hashing | `gsd_run query verification.fingerprint <phaseDir> <files...>` | Deterministic, fail-closed, versioned. |
| Release proof | A mocked release job | A real prerelease tag run | Only a tag exercises `check-version`, `workflow_call` and `gh release create`. |
| Delete the proof release | Manual UI clicks | `gh release delete v1.0.1-rc1 --cleanup-tag --yes` | `--cleanup-tag` removes the remote tag too `[VERIFIED: gh release delete --help]`. |

**Key insight:** every part of this phase is "prove it with a real run", so the work is mostly choosing the right observable (digest status, red-to-green test, green job list) and ordering the runs so a later edit cannot invalidate an earlier proof.

## Common Pitfalls

### Pitfall 1: The re-verification reads stale again right after it passed
**What goes wrong:** Phases 1 and 4 cover `.github/workflows/ci.yml` and `validate.yml` (Phase 4 also `release.yml`), and cover test and source files; any later edit changes a digest.
**Why:** The digest hashes file bytes of every covered path `[VERIFIED: ~/.claude/gsd-core/bin/lib/verification.cjs `computeCoveredDigest`]`.
**How to avoid:** Run QLT-01 as the last plan, after the pin, the guard test, the test fixes, the CI proof and the rc cleanup. Check `verification status` for all four at the very end. The manifest bump to `1.0.1-rc1` and its reset restore identical bytes, so they do not leave a digest change as long as the reset is exact.
**Warning signs:** `verification status` returns `stale` for a phase right after its report was written.

### Pitfall 2: Archived reports can never read `passed` with their old frontmatter
**What goes wrong:** Re-running the verifier but keeping the old `covered_files`, or letting the verifier default to `.planning/phases/<dir>`, recreates the same `stale`.
**Why:** The stored paths `.planning/phases/0N-.../0N-NN-PLAN.md` no longer exist (12, 10, 16 and 28 of 45, 45, 72 and 72 paths are missing for Phases 1 to 4), so the fingerprint is unresolvable and fails closed. `allCurrentArtifactsCovered` also requires every `*-PLAN.md` and `*-SUMMARY.md` in the archived directory to appear in `covered_files`.
**How to avoid:** Name the archived directory in the verifier spawn, list planning artifacts under the archived path, copy the digest only from `verification.fingerprint`, and gate on `verification status <archived dir>` returning `passed`.

### Pitfall 3: The version bump at milestone close will stale Phase 1 again
**What goes wrong:** `manifest.json` is in Phase 1's covered files. The real 1.0.1 bump changes its bytes.
**How to avoid:** Not a Phase 7 problem. Note it so nobody reads it as a regression; the precedent is the 2026-10-03 refresh note in `04-VERIFICATION.md` (re-run `verification.fingerprint`, record why). Renovate or Dependabot bumps of `uv.lock` or action SHAs have the same effect on Phase 4.

### Pitfall 4: `init.manager` is the wrong check for QLT-01
**What goes wrong:** `init.manager` returns phases 6, 7, 8, 999.1 only, so it "passes" before any work. `[VERIFIED: `node gsd-tools.cjs query init.manager`]`
**How to avoid:** Use `node ~/.claude/gsd-core/bin/gsd-tools.cjs verification status <archived dir>` as the acceptance command and record all four outputs. Phase 5 also reads `stale` (outside QLT-01; see Open Questions).

### Pitfall 5: A local "three runs" proof that silently skips the broker tier
**What goes wrong:** Without Mosquitto the broker tests skip and the run is still green.
**How to avoid:** Run with `MQTT_ACTIONS_REQUIRE_BROKER=1` (the CI broker job sets the same variable, `ci.yml:53-54`); check the summary line shows 1480 passed and no skipped. Local Mosquitto is 2.1.2, CI installs 2.0.18 from the Ubuntu 24.04 archive (see below), so a green local broker tier does not prove the CI one.

### Pitfall 6: `ubuntu-24.04` pins the OS, not the image build
**What goes wrong:** Expecting byte-identical runs. The hosted image still rolls weekly (the v1.0.0 release ran on image `ubuntu-24.04` version `20260927.320.1`).
**How to avoid:** State in the guard test docstring and the VERIFICATION that "pinned" means one OS label. Record the image version string from each proof run's "Runner Image" log group.

### Pitfall 7: The rc tag publishes a public prerelease
**What goes wrong:** `release.yml` creates a GitHub Release in the HACS repo. HACS shows "the 5 latest releases" to users `[CITED: https://www.hacs.xyz/docs/publish/integration/]`; whether a prerelease is listed is not stated there.
**How to avoid:** Approval checkpoint before the push (D-13), keep the window short, delete with `gh release delete v1.0.1-rc1 --cleanup-tag --yes`, then confirm `gh release list` shows only `v1.0.0` (Latest) and `v0.1.0`. A prerelease cannot become "Latest" `[ASSUMED]`.

### Pitfall 8: Dispatching CI needs the branch on origin
**What goes wrong:** `gh workflow run ci.yml --ref <branch>` fails if the branch is not pushed. The current branch `gsd/phase-06-native-entity-residual-fixes` is 27 commits ahead of `origin/main` and has no remote branch (`git branch -r` lists none for it; `git rev-list --count origin/main..HEAD` = 27).
**How to avoid:** Decide the merge order at plan time (see Open Questions). `workflow_dispatch` only works because `ci.yml` and `validate.yml` already exist on the default branch `[CITED: docs.github.com events-that-trigger-workflows]`.

### Pitfall 9: Deleting the tag may or may not start a workflow
**What goes wrong:** Unknown whether a tag deletion fires `release.yml`. `[ASSUMED]` it does not (no commit to check out).
**How to avoid:** After the delete, run `gh run list --workflow release.yml --limit 3` and record that no new run appeared.

## Code Examples

### Local proof commands (bash scripts; the interactive shell here is zsh or Fish, so put these in a `.sh` file)
```bash
# 1. Deterministic probe: baseline before the fix shows 2 failures, after the fix 0
uv run --locked pytest -q -p no:cacheprovider -n 6 -m "not broker"   # xdist ships with PHACC

# 2. 50 repetitions of the known test under CPU load (2 cores shared with 4 spinners)
for i in 1 2 3 4; do taskset -c 0,1 timeout 900 sh -c 'while :; do :; done' & done
for i in $(seq 1 50); do
  taskset -c 0,1 .venv/bin/python -m pytest -q -p no:cacheprovider \
    tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear || break
done
pkill -f 'while :; do :; done'

# 3. Three consecutive full runs, broker tier mandatory (baseline: 1480 passed in 100.98 s)
export MQTT_ACTIONS_REQUIRE_BROKER=1
for i in 1 2 3; do uv run --locked pytest -q -p no:cacheprovider || break; done
```
Baseline observed this session at HEAD: `1480 passed in 100.98s`; per tier `1298` unit, `17` broker, `165` multi_instance (from `--collect-only -m`). Under 2-core starvation the unit tier passed (`1298 passed, 182 deselected in 194.52s`). `[VERIFIED: local runs 2026-10-04]`

### CI proof (3 consecutive green runs, D-09)
```bash
BRANCH=$(git branch --show-current)
for i in 1 2 3; do
  gh workflow run ci.yml --ref "$BRANCH"
  sleep 8
  RUN=$(gh run list --workflow ci.yml --event workflow_dispatch --branch "$BRANCH" --limit 1 --json databaseId --jq '.[0].databaseId')
  gh run watch "$RUN" --exit-status
  gh run view "$RUN" --json jobs --jq '.jobs[] | "\(.name) \(.conclusion)"'
done
gh workflow run validate.yml --ref "$BRANCH"    # once; its schedule trigger only runs on main
```
Guard against picking the previous run's id (compare to the last id). A 4-job CI run takes about 4 minutes. Job names seen in the green v1.0.0 release run, which the rc record should match: `Tag matches manifest version`, `Validate / hassfest`, `Validate / HACS`, `CI / Broker tests (Mosquitto)`, `CI / Multi-instance tests`, `CI / Unit tests`, `CI / Ruff`, `Create GitHub release` `[VERIFIED: gh run view 37151165767]`.

### Prerelease proof (D-12, D-13)
```bash
# STOP: ask the owner for explicit approval before the push (D-13)
jq '.version = "1.0.1-rc1"' custom_components/mqtt_actions/manifest.json   # edit via the Edit tool, keep formatting
git commit -am "chore(07): manifest 1.0.1-rc1 for the release proof" && git tag v1.0.1-rc1
git push origin "$BRANCH" v1.0.1-rc1
gh run list --workflow release.yml --limit 1 ; gh run watch <id> --exit-status
gh run view <id> --json jobs,url
gh release delete v1.0.1-rc1 --cleanup-tag --yes ; git tag -d v1.0.1-rc1
# restore manifest.json to the byte-identical 1.0.0 content (git checkout <pre-bump commit> -- file), commit, push
```
`1.0.1-rc1` is valid for the manifest: hassfest's `verify_version` accepts CALVER, SEMVER, SIMPLEVER, BUILDVER or PEP440 `[CITED: home-assistant/core script/hassfest/manifest.py `verify_version`]`, and `AwesomeVersion("1.0.1-rc1", ensure_strategy=[...])` returns strategy SEMVER in the project venv `[VERIFIED: local run]`. The `check-version` regex `^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$` accepts `v1.0.1-rc1` `[VERIFIED: release.yml:24]`, and the glob `v*.*.*` in both `release.yml` (`on.push.tags`) and the `tags-ignore` of `ci.yml`/`validate.yml` matches it `[VERIFIED: release.yml:5-6, ci.yml:6-7]` (so CI and Validate run once, through the release workflow, not twice).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ubuntu-latest` = Ubuntu 24.04 | `ubuntu-latest` migrates to Ubuntu 26.04, gradually 2026-10-19 to 2026-11-19; pin `ubuntu-24.04` to stay | GitHub changelog 2026-09-17 `[CITED: https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/]` | Phase is time-sensitive: roughly two weeks until `main` may start drifting. |
| Runner images supported | "only support the latest 2 versions of an OS" `[CITED: https://github.com/actions/runner-images README]`; the README lists `ubuntu-26.04`, `ubuntu-24.04` (currently `ubuntu-latest`), `ubuntu-22.04` | current | `ubuntu-24.04` is a supported label today; its end of support is not stated by either source (`[ASSUMED]` stays available while it is one of the two newest). |

**Verified resolution of `ubuntu-latest`:** the v1.0.0 release run's job log shows `Image: ubuntu-24.04`, `Version: 20260927.320.1`, and installs `mosquitto 2.0.18-1build3` `[VERIFIED: gh api .../actions/jobs/111285211958/logs]`. D-10's assumption holds.

**Deprecated/outdated:** none relevant. Dependabot's `github-actions` ecosystem (`.github/dependabot.yml`) updates action refs, not `runs-on` labels `[ASSUMED]`; `renovate.json` extends `config:recommended` and may propose a runner label bump `[ASSUMED]`, which the guard test would catch if it changes only some jobs.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A GitHub prerelease cannot take over the "Latest" marker from v1.0.0 | Pitfall 7 | Users of HACS "latest" could briefly see the rc; mitigated by the short window and by the owner approval gate |
| A2 | Deleting a tag does not trigger `release.yml` | Pitfall 9 | A failing run on a deleted tag, harmless but noisy; check with `gh run list` |
| A3 | `ubuntu-24.04` stays a supported label while it is one of the two newest Ubuntu images | State of the Art | A later forced move; the guard test makes the next change a one-line edit |
| A4 | Dependabot does not bump `runs-on`; Renovate might | State of the Art | An unexpected bump PR; the guard test catches mixed versions |
| A5 | The executor/orchestrator can spawn `gsd-verifier` four times with an overridden `PHASE_DIR` and output path | Pattern 4, Open Question 2 | If an executor subagent cannot spawn agents, the verifier step must be run by the orchestrator |

## Open Questions

1. **Which command is the literal acceptance of success criterion 1?**
   - What we know: `init.manager` lists only 6, 7, 8, 999.1 and never reports Phases 1 to 4; `verification status <archived dir>` is `stale` for all of 1 to 5.
   - What's unclear: whether the owner wants the criterion read as the latter.
   - Recommendation: accept `verification status` on the four archived directories returning `passed` as the check, and also record that `init.manager` shows no stale phase.

2. **Who runs `gsd-verifier`?**
   - What we know: it is an agent with the template path `.planning/phases/{phase_dir}/{phase_num}-VERIFICATION.md`; D-02 forbids reviving phase directories.
   - Recommendation: mark the QLT-01 plan as orchestrator-run (or give the executor the verifier procedure inline) with an explicit instruction block: `PHASE_DIR` is the archived directory, output overwrites `0N-VERIFICATION.md` there, `covered_files` use archived paths, digest comes from `verification.fingerprint`, gate is `verification status`.

3. **Merge order and push of the Phase 6 branch.**
   - What we know: the Phase 6 branch is unpushed and 27 commits ahead of `origin/main`; dispatch and the tag run need commits on origin; `branching_strategy` is `phase`.
   - Recommendation: planner decides at plan time: merge Phase 6 via PR first, or stack Phase 7 on it. Either way the three CI dispatch runs and the rc run must use the final Phase 7 head.

4. **Phase 5's report is also stale.** QLT-01 names Phases 1 to 4 only. Re-verifying Phase 5 in the same pass costs one more verifier run and removes the last stale archived report. Needs an owner call (scope is locked to 1 to 4).

5. **Permanent versus env-gated slow-loop probe.** Recommendation is permanent (strongest guarantee, only failing tests print the noise). If the owner prefers opt-in, gate on an env var and add the probe run to the local proof and to one CI job.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all test runs | yes | 0.12.7 | — |
| Python 3.14 | tests | yes (via uv, `.venv`) | `requires-python >=3.14.2` | — |
| Mosquitto | broker tier, local 3-run proof | yes | 2.1.2 (CI: 2.0.18 from the 24.04 archive) | tier would skip without `MQTT_ACTIONS_REQUIRE_BROKER=1`; set it |
| gh CLI | dispatch, watch, rc release, cleanup | yes, authenticated | 2.102.0 | GitHub UI |
| git remote | push branch and tag | yes (`git@github.com:akentner/homeassistant-mqtt-actions-integration.git`) | — | — |
| taskset | CPU-load emulation | yes | util-linux | any busy-loop |
| stress-ng | optional | no | — | `taskset` plus spinners |
| 8 cores / 15 GB RAM | local proof | yes | — | — |

**Missing dependencies with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + PHACC 0.13.367, `asyncio_mode = "auto"`, `--strict-markers` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, markers `broker`, `multi_instance`) |
| Quick run command | `uv run --locked pytest -q -p no:cacheprovider tests/test_repo_structure.py tests/test_log_helpers.py tests/test_manager_breaker.py tests/test_modes.py` |
| Full suite command | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider && uv run ruff check . && uv run ruff format --check .` (about 101 s) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QLT-02 | No test depends on the absence of foreign `asyncio` WARNINGs (always-slow loop, whole suite green) | probe + unit | `uv run --locked pytest -q -p no:cacheprovider -n 6 -m "not broker"` | Wave 0: fixture in `tests/conftest.py` |
| QLT-02 | Known test stable: 50 repetitions under load | stress loop | loop in "Code Examples" | existing test |
| QLT-02 | Three consecutive full runs, broker tier mandatory | full suite x3 | loop in "Code Examples" | existing |
| QLT-03 | Every job pinned to one `ubuntu-NN.NN`, no `*-latest` | unit | `uv run pytest tests/test_repo_structure.py -k pinned_runner -q` | Wave 0: new test |
| QLT-03 | Guard rejects `ubuntu-latest`, two versions, non-string `runs-on` | unit (tmp_path YAML) | same file | Wave 0: new tests |
| QLT-03 | CI x3 and Validate green on the pin; Release passes on `v1.0.1-rc1` | CI | `gh run view <id> --json jobs` | n/a (recorded in `07-VERIFICATION.md`) |
| QLT-01 | Four archived reports read `passed` | tooling | `node ~/.claude/gsd-core/bin/gsd-tools.cjs verification status .planning/milestones/v1.0-phases/<dir>` for each of 01 to 04 | overwritten by the verifier |

### Sampling Rate
- **Per task commit:** the quick run command (a few seconds).
- **Per wave merge:** the full suite command.
- **Phase gate:** three local runs, three CI runs, the rc run, then the four `verification status` checks, all after the last code edit.

### Wave 0 Gaps
- [ ] `tests/conftest.py`: the always-slow-loop fixture (the RED commit; expect exactly the two failures named above)
- [ ] `tests/test_repo_structure.py`: `workflow_runners` helper, the pinned-runner test and negative tests (RED at HEAD: eight `ubuntu-latest`)
- [ ] none for the framework itself: infrastructure exists

## Security Domain

`security_enforcement` is enabled (absent in `.planning/config.json` counts as enabled; `security_asvs_level` is 1). This phase touches CI supply chain and a public release, not runtime auth.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture / V14 Configuration (build and deploy) | yes | Pinned runner label, SHA-pinned actions, `permissions: {}` at workflow level (already enforced by `test_workflows_have_empty_permissions` and `test_all_action_refs_are_pinned_by_sha`) |
| V2 Authentication / V3 Session / V4 Access Control | no | no runtime change |
| V5 Input Validation | yes (small) | The tag name is validated by regex in `check-version` before use (`release.yml:23-27`); do not weaken it |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Floating runner image changes the build environment silently | Tampering | Pin `ubuntu-24.04`; guard test |
| Release job runs with write permission | Elevation of privilege | Only the `release` job has `contents: write`; keep it (`test_only_the_release_job_can_write` exists) |
| Tag push publishes a public artifact | Tampering / Repudiation | Human approval gate before the push, delete the prerelease and tag afterwards, record run URL |
| Attacker-influenced tag name reaching the shell | Tampering | Existing regex validation and `$GITHUB_REF_NAME` read as a variable |

## Project Constraints (from CLAUDE.md)

From `./.claude/CLAUDE.md` and the parent `CLAUDE.md` files:
- Python 3.14, HA 2026.9.x, Ruff with `select = ["ALL"]`, line length 120; tests have the per-file ignores listed in `.ruff.toml` (no `D`, `ANN`, `S101`, `PLR2004`, `PLC0415`, `SLF001`).
- Do not add `pytest`, `pytest-asyncio` or `voluptuous` beyond PHACC; no `setup.py`/Poetry; use `uv`.
- Pin GitHub actions by commit SHA; do not use `hacs/action@main` or unpinned `hassfest@master`.
- Code, commits and comments in English; chat in German; GSD workflow required for edits; TDD mode on (a failing `test:` commit precedes each `fix:` commit); atomic, minimal implementations.
- The shell used by the agent tooling is zsh/Fish: put multi-line bash in script files or `bash -c`.

## Sources

### Primary (HIGH confidence)
- Local files read this session: `.github/workflows/{ci,validate,release}.yml`, `tests/test_manager.py:930-953`, `tests/log_helpers.py`, `tests/test_repo_structure.py`, `custom_components/mqtt_actions/manager.py:2126-2161`, PHACC `plugins.py:407-410`, `~/.claude/gsd-core/bin/lib/verification.cjs`, the four archived `*-VERIFICATION.md`.
- Local experiments: full suite (1480 passed, 100.98 s), 50 passes under 16 busy loops, unit tier under 2-core starvation, probe with `slow_callback_duration = 0.0`, regenerated-fingerprint status check, `AwesomeVersion("1.0.1-rc1")`.
- `gh` API: v1.0.0 release run 37151165767 job log (`Image: ubuntu-24.04`, `20260927.320.1`, `mosquitto 2.0.18-1build3`), run history, release list.
- `node gsd-tools.cjs query init.manager`, `verification status`, `verification fingerprint`, `package-legitimacy check`.

### Secondary (MEDIUM confidence)
- https://github.com/actions/runner-images (README table: `ubuntu-26.04`, `ubuntu-24.04` currently `ubuntu-latest`, latest-2 support policy)
- https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/ and https://github.com/actions/runner-images/issues/14748 (migration window 2026-10-19 to 2026-11-19, pin `ubuntu-24.04`)
- https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows (`workflow_dispatch` needs the workflow on the default branch)
- https://www.hacs.xyz/docs/publish/integration/ (5 latest releases; prerelease handling not stated)
- home-assistant/core `script/hassfest/manifest.py` `verify_version`

### Tertiary (LOW confidence)
- None beyond the `[ASSUMED]` items in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, nothing new, versions read from the venv and `pyproject.toml`.
- Architecture and flake cause: HIGH, reproduced red and green in a scratch copy; documented occurrences (04-05, 05-03, 05-VERIFICATION) all describe the asyncio slow-callback record.
- Verification mechanics: HIGH, reproduced stale, passed, stale, passed.
- Release proof details: MEDIUM, hassfest version rule and gh flags verified, HACS prerelease visibility and tag-deletion trigger unverified.
- Pitfalls: HIGH for 1 to 6, MEDIUM for 7 to 9.

**Research date:** 2026-10-04
**Valid until:** 2026-10-19 for the runner facts (the `ubuntu-latest` migration starts that day); 30 days for the rest.
