# Phase 7: Verification, Stable Tests and Pinned CI - Context

**Gathered:** 2026-10-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the v1.0.1 build verifiably sound without adding features. Phases 1 to 4 get a current verification against the
final code (QLT-01), the full test suite passes three consecutive runs and the known flake
`test_delete_device_own_subscription_never_sees_state_clear` is fixed at its cause (QLT-02), and CI, Validate and Release
run on one pinned runner version instead of `ubuntu-latest` (QLT-03). Phase 8 (manual real-instance UAT) is out of scope.

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` — Phase 7 goal and success criteria 1 to 4
- `.planning/REQUIREMENTS.md` — QLT-01, QLT-02, QLT-03

### Re-verification inputs
- `.planning/milestones/v1.0-phases/01-walking-skeleton-installable-switch/01-VERIFICATION.md` — current report, overwritten (D-02)
- `.planning/milestones/v1.0-phases/02-select-devices-and-reliable-execution/02-VERIFICATION.md`
- `.planning/milestones/v1.0-phases/03-trust-central-config-and-ownership/03-VERIFICATION.md`
- `.planning/milestones/v1.0-phases/04-operations-recovery-and-release/04-VERIFICATION.md`
- `.planning/phases/06-native-entity-residual-fixes/06-CONTEXT.md` — Phase 6 decisions the final code includes
- `~/.claude/gsd-core/bin/lib/verification.cjs` — staleness rule (summary or covered source newer than the report)

### Flake
- `tests/test_manager.py:932` — the flaky test
- `custom_components/mqtt_actions/manager.py:2126` — `_async_remove_device` (order: pop device, clear discovery, unsubscribe, clear config, clear state)
- `.planning/quick/261003-rmy-native-entities-test-buttons-disabled-by/261003-rmy-SUMMARY.md` and `.planning/quick/261003-sfb-native-entity-ids-shorter-and-english/261003-sfb-SUMMARY.md` — recorded occurrences (fails in full run, passes alone)

### CI and release
- `.github/workflows/ci.yml`, `.github/workflows/validate.yml`, `.github/workflows/release.yml` — all `runs-on` entries
- `tests/test_docs.py` — pattern for a test that pins a repo artifact to code
- `custom_components/mqtt_actions/manifest.json` — version (1.0.0 now); `check-version` requires tag == manifest version

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_docs.py`: model for the workflow-pinning guard test.
- `gsd-verifier` agent and the `gsd_run query init.manager` staleness report: the QLT-01 mechanism and its check.
- Pytest markers `broker` and `multi_instance` (`pyproject.toml`): the three tiers CI already runs as separate jobs.

### Established Patterns
- Workflow actions are pinned to commit SHAs with a version comment; `permissions: {}` at workflow level.
- `release.yml` calls `ci.yml` and `validate.yml` via `workflow_call`; a hyphenated tag becomes a prerelease.
- TDD mode: a failing `test:` commit precedes each `fix:` commit.

### Integration Points
- Phase 6 branch code is the baseline: re-verification, the three-run proof and the prerelease run must happen after the
  flake fix and the runner pin.
- `init.manager` currently lists only the active milestone's phases (6 to 8); check in research whether it reports the
  archived Phases 1 to 4 at all and what makes them "stale" (success criterion 1 depends on it).

</code_context>

<specifics>
## Specific Ideas

- Observed during discussion: `tests/test_manager.py` alone passes in 6 s (51 tests) and the flaky test passed 25 of 25
  isolated runs, so the flake needs load or suite ordering to appear.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 7-Verification, Stable Tests and Pinned CI*
*Context gathered: 2026-10-04*
