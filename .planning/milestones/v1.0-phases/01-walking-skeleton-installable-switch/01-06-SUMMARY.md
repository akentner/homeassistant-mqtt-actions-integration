---
phase: 01-walking-skeleton-installable-switch
plan: 06
subsystem: distribution-ci
tags: [hacs, hassfest, github-actions, dependabot, readme, license, supply-chain]

requires:
  - phase: 01-05
    provides: Complete discovery lifecycle whose limitations (stale online availability, destructive hub removal, no cross-instance device_id) the README documents
  - phase: 01-02
    provides: manifest.json (domain mqtt_actions), D-13 verdict go-subentry, host version findings
provides:
  - HACS-installable repository layout (hacs.json with the 2026.9.0 floor, MIT LICENSE, local brand icon)
  - README with install, setup, topic and payload contract, behavior, limitations and the trust model
  - SHA-pinned Validate (hassfest, HACS) and CI (locked uv sync, Ruff, pytest with mosquitto) workflows with empty workflow-level permissions
  - Dependabot for github-actions and uv
  - tests/test_repo_structure.py (18 executable checks for FND-01 and FND-02)
  - Public GitHub repository akentner/homeassistant-mqtt-actions-integration with issues, topics and description, both branches pushed, Validate and CI green for head 0f6ae60
affects: [phase-01-verification, 01-ship, phase-02, phase-03]

actuals:
  tokens: 4100
  tasks: 3
  commits: 3
plan_head_before: 34d6515f22283770f2466294017c64dfc2342ac5
plan_head_after: 0f6ae608a9fa2fda43f1bee4edfcdf8e5c48b490

tech-stack:
  added: [GitHub Actions workflows, Dependabot]
  patterns:
    - "Every third-party action pinned by a 40-character commit SHA with the version as a trailing comment; a test fails the build on any regression"
    - "Workflow-level permissions are an empty mapping; token scopes, if ever needed, are granted at job level only"
    - "Structure test parses the workflow YAML (PyYAML reads the key on as boolean True, so the trigger block is read with doc.get('on', doc.get(True)))"

key-files:
  created:
    - hacs.json
    - LICENSE
    - README.md
    - custom_components/mqtt_actions/brand/icon.png
    - .github/workflows/validate.yml
    - .github/workflows/ci.yml
    - .github/dependabot.yml
    - tests/test_repo_structure.py
  modified: []

key-decisions:
  - "hacs.json floor is 2026.9.0, fixed by Home Assistant's own Python 3.14 requirement; the D-13 host findings do not change it"
  - "A LICENSE-only commit on main (c02d5fe) was needed for the HACS license check, because HACS reads GitHub's repository license, which GitHub detects from the default branch only"
  - "Validate re-run with --failed instead of a new phase-branch commit, so 0f6ae60 stays the proven-green head"

requirements-completed:
  - FND-01
  - FND-02

coverage:
  - id: D1
    description: "The repository carries valid HACS metadata: manifest keys, domain equal to the folder name, hacs.json with only allowed keys and the 2026.9.0 floor, a valid PNG icon of at least 256 by 256, MIT LICENSE with the holder"
    requirement: FND-01
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_manifest_has_hacs_required_keys"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_domain_matches_folder_name"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_hacs_json_keys_allowed_and_floor"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_brand_icon_is_valid_png"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_license_is_mit_with_holder"
        status: pass
      - kind: other
        ref: "GitHub Actions Validate run 36545688756 (HACS job, 9 of 9 checks) for head 0f6ae60"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every push runs hassfest, HACS validation, Ruff and pytest; workflows are SHA-pinned with empty permissions, no persisted checkout credentials, no HACS ignore input, locked uv sync; Dependabot covers github-actions and uv"
    requirement: FND-02
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_workflows_have_empty_permissions"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_all_action_refs_are_pinned_by_sha"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_checkout_does_not_persist_credentials"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_hacs_action_has_category_and_no_ignore"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_push_trigger_has_no_branch_filter"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_ci_runs_locked_sync_lint_format_and_pytest"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_validate_workflow_has_hassfest_and_hacs_jobs"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_dependabot_covers_actions_and_uv"
        status: pass
      - kind: other
        ref: "gh run list --commit 0f6ae608a9fa2fda43f1bee4edfcdf8e5c48b490 shows CI and Validate with conclusion success"
        status: pass
    human_judgment: false
  - id: D3
    description: "The README documents install, setup, the topic and payload contract, retained-baseline behavior, limitations and the trust model (write access to a state topic can trigger that device's actions; use broker ACLs; no device_id targets)"
    requirement: FND-01
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_readme_documents_install_limits_and_trust"
        status: pass
    human_judgment: true
    rationale: "The test asserts keywords and section headings only; whether the wording is accurate and understandable to a stranger deciding on broker exposure is a reading judgment"
  - id: D4
    description: "Frontend and host behavior no automated test sees: action editor rendering, error and warning banners, German and English strings, restart and reload behavior, Repairs issue, delete without ghosts"
    verification: []
    human_judgment: true
    rationale: "Requires the real frontend and a real retaining broker on haos-op3050-1; the 8-step manual UAT below is consolidated by the verifier at end of phase"

duration: multi-session (Task 1 in a worktree executor, Task 3 in a sequential executor; wall-clock not summed)
completed: 2026-09-29
status: complete
---

# Phase 1 Plan 06: HACS Metadata, SHA-pinned CI and Publication Summary

**The repository is HACS-shaped (hacs.json floor 2026.9.0, MIT LICENSE, local icon, README with the trust model) and published as public akentner/homeassistant-mqtt-actions-integration, with hassfest, HACS validation, Ruff and pytest green on GitHub for head 0f6ae60 through SHA-pinned workflows guarded by an 18-test structure check.**

## Performance

- **Tasks:** 3 (Task 1 auto with TDD, Task 2 human-action checkpoint, Task 3 auto)
- **Files created:** 8 (371 insertions between `plan_head_before` and `0f6ae60`), modified: 0
- **Commits:** 3 (measured from `plan_head_before`: two task commits and one worktree merge)
- **Suite at close:** 185 passed, Ruff check and format check clean

## Accomplishments

- **Task 1, distribution and CI:** `hacs.json` (name MQTT Actions, homeassistant 2026.9.0), MIT `LICENSE` (Alexander Kentner, 2026), `README.md`, `custom_components/mqtt_actions/brand/icon.png`, `.github/workflows/validate.yml` (hassfest and HACS jobs; triggers push without branch filter, pull_request, workflow_dispatch, daily schedule), `.github/workflows/ci.yml` (setup-uv with Python 3.14, mosquitto for the broker test, `uv sync --locked`, Ruff check and format check, pytest), `.github/dependabot.yml`, and `tests/test_repo_structure.py` (18 collected tests). RED commit precedes GREEN.
- **Task 2, publication:** the developer authorised the orchestrator to create the public repository; `origin` is `git@github.com:akentner/homeassistant-mqtt-actions-integration.git`.
- **Task 3, publish and prove green:** secret and address scans clean, repository configured, `main` and the phase branch pushed, CI and Validate green for head `0f6ae60` (details below).

## Task Commits

1. **Task 1 RED:** `596bacb` test(01-06): add failing repository structure tests
2. **Task 1 GREEN:** `893b6ba` feat(01-06): add HACS metadata, README, icon and SHA-pinned CI
3. **Task 1 merge (worktree executor):** `0f6ae60` chore: merge executor worktree (worktree-agent-a96ffc2ea5d5c1d01)
4. **Task 2:** no commit (checkpoint:human-action). `user_response`: "ausführen (developer authorised the orchestrator to run gh repo create)".
5. **Task 3:** no phase-branch commit (push, repository settings and workflow proof only).

**Plan metadata:** the SUMMARY commit and the STATE and ROADMAP commit follow this file on the phase branch and are local.

## Task 3 Results

**Pre-push scans (run by this executor immediately before pushing):**
- Secret patterns (`ghp_`, `github_pat_`, private key headers, `AKIA`) over all tracked files except `uv.lock`: no match.
- Full history (`git log --all -p`) for the same patterns: no match.
- Internal addresses (192.168.x.x, Tailscale 100.64/10 range, "campoint"): no match. No tracked file names resemble .env, secret, credential, .pem or .key.
- The only commit author in history is Alexander Kentner.

**Repository settings (`gh repo view`):** visibility PUBLIC, issues enabled, topics home-assistant, hacs, mqtt, custom-component, integration, description "Home Assistant integration that runs local actions when MQTT state changes: Switch and Select devices, HACS installable".

**Pushes:** `main` and `gsd/phase-01-walking-skeleton-installable-switch`, both with upstream tracking. No pull request, no force-push, no branch deleted, no other repository touched.

**Workflow proof, head SHA `0f6ae608a9fa2fda43f1bee4edfcdf8e5c48b490`:**
- CI: https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/36545688728 (success)
- Validate: https://github.com/akentner/homeassistant-mqtt-actions-integration/actions/runs/36545688756 (success after `--failed` re-run; hassfest job green on the first attempt, HACS job green on the re-run)
- `gh run list --commit 0f6ae60...` lists exactly the successful workflow names CI and Validate (confirmed by this executor and by the orchestrator).

**Head-SHA statement:** the proven-green head is `0f6ae60`. The SUMMARY commit and the tracking commit made after it are local and unpushed; the orchestrator decides about pushing. They change only `.planning/` files, and CI was not run on them.

**Post-run local check (this executor):** 185 tests passed, `ruff check .` and `ruff format --check .` clean, `tests/test_repo_structure.py` 18 passed.

## Deviations from Plan

**1. [Rule 3 - Blocking] HACS license check needed a LICENSE-only commit on `main`**
- **Found during:** Task 3 (workflow proof)
- **Issue:** The first Validate run failed in the HACS job with `<Validation license> failed: The repository has no license` (1 of 9 checks; the other eight, including brands, topics, description and issues, passed). The HACS validator reads GitHub's repository-level license attribute, which GitHub detects from the default branch only. `main` held only `.claude` and `.planning`, so `licenseInfo` was null and the API returned 404 even with `ref=<phase branch>`. No change on the phase branch could fix it.
- **Fix:** This executor stopped and reported, because the executor commit protocol forbids commits on the default branch and the push authorisation did not cover new content on `main`. The developer explicitly approved a LICENSE-only commit on `main`; the orchestrator (not this executor) committed the identical MIT LICENSE as `c02d5fe` (fast-forward push `f990255..c02d5fe`). GitHub then reported license MIT and Validate run 36545688756 was re-run with `--failed`; it is green.
- **Files modified:** `LICENSE` on `main` (identical to the phase-branch file)
- **Commit:** `c02d5fe` on `main`, not part of this plan's phase-branch commit count. The later pull request merges cleanly because both sides add identical content.

**Total deviations:** 1 (Rule 3 blocking, resolved with developer approval). **Impact:** none on scope; `main` now holds one extra file ahead of the phase branch.

## Issues Encountered

None beyond the deviation above. The Task 1 local hassfest run is recorded by the Task 1 executor as green; on GitHub the hassfest job passed on the first Validate attempt.

## Manual UAT (human-check, consolidated by the verifier at end of phase)

Manual UAT on haos-op3050-1 with the final build. If the tracer build from the D-13 gate is still installed, delete its device and the integration first.

1. Deploy: `ssh haos-op3050-1 "mkdir -p /config/custom_components/mqtt_actions"`, then `scp -r custom_components/mqtt_actions/* haos-op3050-1:/config/custom_components/mqtt_actions/`, then `ssh haos-op3050-1 "ha core restart"`.
2. Add the integration; accept the defaults. Switch the profile language between English and German and confirm all dialog texts are translated (FND-04).
3. Add switch device: the action editor renders (DEV-02). Enter an invalid action in YAML mode (a mapping with an unknown key): a form-level error appears and nothing is saved. Enter a service action targeting a device_id: a warning banner appears, submitting again saves (DEV-05).
4. Toggle the switch entity in the UI: the ON actions run once. Publish `on`, `off` and `ON` to `mqtt_actions/v1/devices/{device_uuid}/state` with mosquitto_pub or ha-ws: one run per real change, none for a repeated identical value (STA-01, STA-02).
5. Restart Home Assistant and reload the integration: no actions run; then publish a changed value: the actions run once (STA-04, STA-05).
6. Make an action fail (call a service that does not exist): Repairs shows exactly one issue with device, trigger, time and error; fix the action and trigger again: the issue disappears (DEV-08).
7. Delete the device: the entity is gone and no ghost device remains under the MQTT integration; remove the hub: nothing MQTT Actions related remains (DSC-02, D-15, D-16).
8. If not recorded at the D-13 gate: open Settings, About on lxc-haos-104 and hassio-n2plus and note the Core versions.

No deployment to or probe of any Home Assistant host was made by this executor.

## Findings for the Verifier and Later Phases

From this plan:
- The HACS license check depends on the default branch: any future repository bootstrap must put the LICENSE on the default branch before the first HACS validation.
- `/gsd-ship` opens the pull request; the phase branch and `main` differ by the identical LICENSE (`c02d5fe`).

Carried over from earlier summaries in context (not re-verified here):
- D-13 verdict is go-subentry (01-02): the subentry dialog worked on the real frontend on `haos-op3050-1` (Core 2026.9.4).
- The Core versions of `lxc-haos-104` and `hassio-n2plus` remain **not verified** (probes were denied in 01-02 and not retried); UAT step 8 covers them.
- From 01-05: an offline publish on unload can wait up to core's acknowledgement timeout on a dead broker; a reconfigure stops an in-flight run of the old Script; hub removal is destructive on a shared broker (Phase 3 must replace it); `mqtt_discovery_disabled` persists after an unload until recomputed; Issue text and German wording in the real frontend and the broker-side half of delete and reconnect are asserted by no test (01-05 coverage D7).

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-16 (CI supply chain) is mitigated and guarded by the structure test; T-01-17 (publication) was mitigated by the developer-approved gate and the pre-push scans; T-01-18 (state-topic write access) is mitigated by the README Security section; T-01-SC (mosquitto apt install in CI) is accepted as planned.

## Next Phase Readiness

Phase 1 plans are complete; ready for end-of-phase verification (manual UAT above) and `/gsd-ship` for the pull request. The LICENSE is already on `main`. Pushing the local SUMMARY and tracking commits is left to the orchestrator.

## Self-Check: PASSED

- Files exist: `hacs.json`, `LICENSE`, `README.md`, `custom_components/mqtt_actions/brand/icon.png`, `.github/workflows/validate.yml`, `.github/workflows/ci.yml`, `.github/dependabot.yml`, `tests/test_repo_structure.py`
- Commits `596bacb`, `893b6ba`, `0f6ae60` exist; `c02d5fe` exists on `origin/main` (fetched)
- `gh run list --commit 0f6ae60...` returns CI and Validate with conclusion success; repository is PUBLIC with issues, five topics and a description
- Acceptance criteria re-run: structure test 18 passed, full suite 185 passed, Ruff check and format clean
