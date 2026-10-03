---
phase: 01-walking-skeleton-installable-switch
plan: 01
subsystem: infra
tags: [uv, ruff, pytest, pytest-homeassistant-custom-component, toolchain]

requires: []
provides:
  - uv project with zero runtime dependencies and a hash-locked dev group
  - Ruff configuration (py314, 120 chars, blueprint base, tests per-file ignores)
  - PHACC test harness wiring (enable_custom_integrations, expected_lingering_timers override)
  - Smoke tests proving Python >= 3.14.2, HA >= 2026.9.0, probatio import and a booting hass fixture
affects: [01-02, 01-03, 01-04, 01-05, 01-06]

actuals:
  tokens: 9000
  tasks: 2
  commits: 1
plan_head_before: 35380174ddc9238f00dfa8df850a8380f85bdd49
plan_head_after: eb9fc42ce29520911854aae9b7dffd7460c440ef

tech-stack:
  added: [pytest-homeassistant-custom-component==0.13.367, ruff==0.16.9]
  patterns:
    - "uv sync --locked as the lockfile drift gate"
    - "Tests import HomeAssistant under TYPE_CHECKING (ruff TC002)"

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .ruff.toml
    - .gitignore
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_toolchain.py
  modified: []

key-decisions:
  - "Task 1 package-legitimacy checkpoint resolved by the developer with user_response=approved before any install ran"
  - "Ruff excludes .planning and .claude so ruff 0.16 never reformats Markdown planning docs or agent worktrees"
  - "tests/__init__.py added to satisfy INP001 instead of ignoring the rule"

requirements-completed: [FND-02]

coverage:
  - id: D1
    description: "Dev toolchain resolves from a committed lockfile with exact pins and zero runtime dependencies"
    requirement: FND-02
    verification:
      - kind: other
        ref: "uv sync --locked && python tomllib assertion on pyproject.toml"
        status: pass
    human_judgment: false
  - id: D2
    description: "PHACC harness runs a real hass fixture test without lingering-timer errors"
    requirement: FND-02
    verification:
      - kind: unit
        ref: "tests/test_toolchain.py#test_hass_fixture_boots"
        status: pass
      - kind: unit
        ref: "tests/test_toolchain.py#test_python_floor"
        status: pass
      - kind: unit
        ref: "tests/test_toolchain.py#test_home_assistant_floor"
        status: pass
      - kind: unit
        ref: "tests/test_toolchain.py#test_probatio_importable"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ruff check and format check are clean at 120 characters"
    requirement: FND-02
    verification:
      - kind: other
        ref: "uv run ruff check . && uv run ruff format --check ."
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-09-29
status: complete
---

# Phase 1 Plan 01: Dev Toolchain Scaffold Summary

**uv project with zero runtime deps, exact-pinned and hash-locked PHACC 0.13.367 + Ruff 0.16.9, blueprint-based Ruff config at 120 chars, and a PHACC harness whose four smoke tests pass on HA 2026.9.4.**

## Performance

- **Duration:** about 12 min
- **Tasks:** 2 (1 human checkpoint resolved by the orchestrator, 1 auto)
- **Files created:** 7

## Accomplishments

- Task 1 (blocking-human package-legitimacy checkpoint) was presented by the orchestrator; developer reply: `approved` (user_response="approved"). No install ran before that reply (threat T-01-SC mitigated).
- `pyproject.toml`: `dependencies = []`, `requires-python = ">=3.14.2"`, `[tool.uv] package = false`, dev group with exact pins, pytest `asyncio_mode = "auto"`.
- `uv.lock` committed; `uv sync --locked` exits 0 (T-01-01).
- `.ruff.toml` with `select = ["ALL"]`, `CPY001` ignored, `tests/**` per-file ignores per research Pitfall 14.
- `tests/conftest.py` with autouse `auto_enable_custom_integrations` and `expected_lingering_timers` returning True (Pitfall 6).
- `.gitignore` covers venv, caches and `.planning/research/.cache/` (T-01-02).

## Task Commits

1. **Task 1: package legitimacy checkpoint** - no commit (developer approval only)
2. **Task 2: scaffold** - `eb9fc42` (chore)

## Verification Results

- `uv sync --locked`: exit 0 (153 packages resolved)
- `uv run pytest -q`: 4 passed
- `uv run ruff check .`: All checks passed
- `uv run ruff format --check .`: 3 files already formatted
- tomllib assertion: pass (both exact pins, empty runtime deps, `>=3.14.2`)
- Resolved versions: homeassistant 2026.9.4, probatio 0.11.4, ruff 0.16.9

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff reformatted Markdown planning docs**
- **Found during:** Task 2, first `ruff format .`
- **Issue:** Ruff 0.16 formatted Markdown code blocks in `.planning/phases/01-.../01-RESEARCH.md`, `.planning/research/ARCHITECTURE.md` and `.planning/research/STACK.md`, and `ruff check` would also scan `.claude/worktrees`.
- **Fix:** Reverted the three docs with `git checkout -- <file>` (per-file), added `extend-exclude = [".planning", ".claude"]` to `.ruff.toml`.
- **Files modified:** `.ruff.toml`

**2. [Rule 3 - Blocking] Ruff INP001 and TC002 findings in the new tests**
- **Found during:** Task 2, first `ruff check .`
- **Issue:** `tests/` was an implicit namespace package (INP001) and `HomeAssistant` was a runtime import used only for annotations (TC002).
- **Fix:** Added an empty `tests/__init__.py`; moved the `HomeAssistant` import under `TYPE_CHECKING` (Python 3.14 lazy annotations make this safe).
- **Files modified:** `tests/__init__.py`, `tests/test_toolchain.py`

**3. [Note] uv init name**
- `uv init --bare` generated a project name from the worktree directory; `pyproject.toml` was rewritten by hand with the planned name, so no residue remains.

**4. [Note] Plan commit ledger not persisted**
- The sandbox refused writing `gsd-plan-head-before-01-01` into the shared git dir. `plan_head_before` is the verified worktree base (HEAD was 3538017 with no commits before the task commit), so `commits: 1` is still measured with `git rev-list --count`.

**Total deviations:** 2 auto-fixed (both Rule 3). **Impact:** none on scope; the plan artifacts are as specified plus `tests/__init__.py`.

## Issues Encountered

None blocking. Observation: `uv==0.12.5` appears in the project venv as a transitive dependency of pytest-homeassistant-custom-component; it is not a direct dependency and does not affect the system uv (0.12.7).

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

Plans 01-02 to 01-06 can run `uv sync --locked`, `uv run pytest` and `uv run ruff check .` without setup work.

## Self-Check: PASSED

- Files exist: pyproject.toml, uv.lock, .ruff.toml, .gitignore, tests/__init__.py, tests/conftest.py, tests/test_toolchain.py
- Commit eb9fc42 exists on branch worktree-agent-a267882c9582859f6
- Acceptance criteria re-run: all pass
