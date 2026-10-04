# Phase 7: Verification, Stable Tests and Pinned CI - Pattern Map

**Mapped:** 2026-10-04
**Files analyzed:** 10 (edited or created)
**Analogs found:** 9 / 10 (all tracked in git; no gitignored mirror paths)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/conftest.py` (+ always-slow-loop autouse fixture) | test config | transform | `tests/conftest.py:42-47` (existing `@pytest.fixture(autouse=True)`) | exact |
| `tests/test_manager_breaker.py` (`_warnings`, line 94-95) | test | request-response | `tests/log_helpers.py:own_warnings` | exact |
| `tests/test_modes.py` (line 134) | test | request-response | `tests/test_trust.py:236` (own-logger filter) | exact |
| `tests/test_hub_removal.py` (line 277, optional hardening) | test | request-response | `tests/log_helpers.py:own_warnings` | exact |
| `tests/test_repo_structure.py` (+ `workflow_runners`, pinned-runner test, negative tests) | test | file-I/O | same file (`_load_workflow`, `_all_jobs`) and `tests/test_log_helpers.py` (helper plus negative test) | exact |
| `.github/workflows/ci.yml` (4 `runs-on`) | config | batch | itself (lines 17, 34, 50, 73) | exact |
| `.github/workflows/validate.yml` (2 `runs-on`) | config | batch | itself (lines 19, 30) | exact |
| `.github/workflows/release.yml` (2 `runs-on`) | config | batch | itself (lines 13, 52) | exact |
| `custom_components/mqtt_actions/manifest.json` (temporary `1.0.1-rc1`, then byte-exact reset) | config | n/a | n/a (version edit) | n/a |
| `.planning/milestones/v1.0-phases/0{1..4}-*/0N-VERIFICATION.md` (overwritten) | docs | n/a | existing reports in the same directories (04-VERIFICATION.md refresh note) | exact |
| `07-VERIFICATION.md` (run URLs, per-job results) | docs | n/a | `04-VERIFICATION.md` | role-match |

No production code (`custom_components/`) changes: the flake is a test-scope defect (RESEARCH Finding C).

## Pattern Assignments

### `tests/conftest.py` (test config, always-slow loop; RED commit)

**Analog:** `tests/conftest.py:42-47`, autouse fixtures. Add `import asyncio` to the import block at the top (the file starts with `import uuid` at line 3).

**Core pattern** (from RESEARCH Pattern 1; PHACC `plugins.py:407-410` defines `enable_event_loop_debug`):
```python
@pytest.fixture(autouse=True)
async def always_slow_event_loop(enable_event_loop_debug: None) -> None:
    """Count every callback as slow so asyncio logs its slow-callback WARNING all the time (QLT-02)."""
    asyncio.get_running_loop().slow_callback_duration = 0.0
```
Expected RED: exactly 2 failures (`test_manager_breaker.py::test_change_after_max_runs_trips_pauses_and_informs`, `test_modes.py::test_observe_logs_and_runs_nothing_but_tracks_the_baseline`). Ruff `select=["ALL"]`: tests ignore `D`, `ANN` per `.ruff.toml`.

---

### `tests/test_manager_breaker.py` (line 94-95)

**Analog:** `tests/log_helpers.py:11-26`

Current:
```python
def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno == logging.WARNING]
```
Replace the body with `return own_warnings(caplog, exact=True)` and add `from tests.log_helpers import own_warnings`.
Helper being reused:
```python
OWN_LOGGER = "custom_components.mqtt_actions"
def own_warnings(caplog, *, exact: bool = False) -> list[logging.LogRecord]:
    return [record for record in caplog.records
            if record.name.startswith(OWN_LOGGER)
            and (record.levelno == logging.WARNING if exact else record.levelno >= logging.WARNING)]
```
Line 147 asserts `len(warnings) == 1`; line 451 adds a name filter. If `logging` becomes unused in the file, remove the import (Ruff).

---

### `tests/test_modes.py` (line 134)

**Analog:** `tests/test_trust.py:236`
```python
records = [r for r in caplog.records if r.name.startswith("custom_components.mqtt_actions")]
```
Current (line 134):
```python
lines = [record.getMessage() for record in caplog.records if "observe" in record.getMessage().lower()]
```
Target: add `record.name.startswith(OWN_LOGGER)` (import `OWN_LOGGER` from `tests.log_helpers`) to the comprehension condition.

### `tests/test_hub_removal.py` (line 277, optional)
Same own-logger filter added to the level plus `"MQTT"` substring filter.

---

### `tests/test_repo_structure.py` (test, file-I/O: workflow runner guard)

**Analog:** same file. Constants and helpers at lines 18-19 and 38-42, `_all_jobs` at 354-357.

**Existing imports and constants to reuse** (lines 3-19): `re`, `Path`, `Any`, `pytest`, `yaml`, `WORKFLOWS = ROOT / ".github" / "workflows"`.

**Existing loader style** (lines 38-42):
```python
def _load_workflow(filename: str) -> dict[Any, Any]:
    document = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document
```

**New helper and test** (RESEARCH Pattern 3; use a glob, not the fixed `WORKFLOW_FILES` tuple, so a new workflow cannot escape):
```python
RUNNER = re.compile(r"^ubuntu-\d{2}\.\d{2}$")

def workflow_runners(directory: Path) -> dict[tuple[str, str], Any]:
    runners: dict[tuple[str, str], Any] = {}
    for path in sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")]):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (document.get("jobs") or {}).items():
            if "runs-on" in job:          # reusable-workflow caller jobs (release.yml ci/validate) have `uses:` only
                runners[(path.name, name)] = job["runs-on"]
    return runners

def test_every_job_runs_on_one_pinned_runner() -> None:
    runners = workflow_runners(WORKFLOWS)
    assert runners, "no workflow job declares a runner"
    for (filename, job), runner in runners.items():
        assert isinstance(runner, str) and RUNNER.match(runner), f"{filename}:{job} runs on {runner!r}"
    assert len(set(runners.values())) == 1, f"more than one runner version: {sorted(set(runners.values()))}"
```
Name must match `-k pinned_runner` (the validation command), so name the test `..._one_pinned_runner`.

**Negative tests** on `tmp_path` YAML: follow `tests/test_log_helpers.py` (helper plus a test proving the helper rejects). Cases: `ubuntu-latest`, two distinct versions, non-string `runs-on` (list or matrix expression), a caller job with `uses:` being skipped. Refactor the assertion into a `_assert_pinned(runners)` function so the negative tests can call it with `pytest.raises(AssertionError)`.

TDD order: guard test RED at HEAD (8 `ubuntu-latest`), then `test:` commit, then `ci:` pin commit GREEN.

---

### `.github/workflows/{ci,validate,release}.yml` (config)

**Analog:** the files themselves. Replace every `runs-on: ubuntu-latest` with `runs-on: ubuntu-24.04` (8 entries):
- `ci.yml` lines 17, 34, 50, 73
- `validate.yml` lines 19, 30
- `release.yml` lines 13 (`check-version`), 52 (`release`)

Keep: `permissions: {}` at workflow level, SHA-pinned actions with a version comment (e.g. `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`), Mosquitto via `apt` in the broker job only. Existing guards that must stay green: `test_workflows_have_empty_permissions`, `test_all_action_refs_are_pinned_by_sha`, `test_only_the_release_job_can_write`.

### `custom_components/mqtt_actions/manifest.json`
Bump `version` to `1.0.1-rc1` for the tag proof (requires owner approval before pushing the tag, D-13). Reset must be byte-identical (`git checkout <pre-bump commit> -- file`) so Phase 1's covered-file digest does not change. `check-version` regex `^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$` at `release.yml:24` accepts `v1.0.1-rc1`.

---

### `.planning/milestones/v1.0-phases/0{1..4}-*/0N-VERIFICATION.md`

**Analog:** the existing reports in the same directories, especially `04-VERIFICATION.md` (2026-10-03 refresh note precedent).
Pattern: spawn `gsd-verifier` with `PHASE_DIR` set to the archived directory, output path overridden to it, `covered_files` listing archived paths (all `*-PLAN.md` and `*-SUMMARY.md` must be included), `covered_digest` only from `gsd_run query verification.fingerprint`. Gate: `node ~/.claude/gsd-core/bin/gsd-tools.cjs verification status <archived dir>` returns `passed` for all four. Run this plan last. Mark gaps from Phase 5 behavior as "superseded by Phase 5" (D-03).

## Shared Patterns

### Own-logger scoping of log assertions
**Source:** `tests/log_helpers.py:11-26` (`own_warnings`, `OWN_LOGGER`); tested by `tests/test_log_helpers.py`.
**Apply to:** every test that counts or matches caplog records (breaker, modes, hub_removal).

### Workflow YAML guards
**Source:** `tests/test_repo_structure.py` (`WORKFLOWS`, `_load_workflow`, `_all_jobs`).
**Apply to:** the new runner guard. Note PyYAML parses the bare `on` key as `True` (see `_triggers`).

### Proof commands
**Source:** RESEARCH "Code Examples". Use bash scripts, not Fish. Run with `MQTT_ACTIONS_REQUIRE_BROKER=1`; 50 repetitions via a shell loop (no `pytest-repeat`).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `07-VERIFICATION.md` (CI run URLs and per-job table) | docs | n/a | Only role-match with `04-VERIFICATION.md`; the table format is at the planner's discretion |

## Metadata

**Analog search scope:** `tests/`, `.github/workflows/`, `.planning/milestones/v1.0-phases/`
**Files scanned:** about 10 read, tracked file list checked via `git ls-files`
**Pattern extraction date:** 2026-10-04
