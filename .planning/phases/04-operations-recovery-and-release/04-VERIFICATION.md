---
phase: 04-operations-recovery-and-release
verified: 2026-10-02T15:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .github/dependabot.yml
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - .github/workflows/validate.yml
  - .planning/phases/04-operations-recovery-and-release/04-01-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-01-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-02-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-02-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-03-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-03-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-04-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-04-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-05-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-05-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-06-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-06-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-07-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-07-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-08-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-08-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-09-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-09-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-10-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-10-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-11-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-11-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-12-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-12-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-13-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-13-SUMMARY.md
  - .planning/phases/04-operations-recovery-and-release/04-14-PLAN.md
  - .planning/phases/04-operations-recovery-and-release/04-14-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/actions.py
  - custom_components/mqtt_actions/brand/icon.png
  - custom_components/mqtt_actions/breaker.py
  - custom_components/mqtt_actions/button.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/diagnostics.py
  - custom_components/mqtt_actions/discovery.py
  - custom_components/mqtt_actions/document.py
  - custom_components/mqtt_actions/entities.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/manifest.json
  - custom_components/mqtt_actions/model.py
  - custom_components/mqtt_actions/modes.py
  - custom_components/mqtt_actions/mqtt_gateway.py
  - custom_components/mqtt_actions/portability.py
  - custom_components/mqtt_actions/presence.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/retrigger.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/select.py
  - custom_components/mqtt_actions/sensor.py
  - custom_components/mqtt_actions/services.py
  - custom_components/mqtt_actions/services.yaml
  - custom_components/mqtt_actions/state.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/topics.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/trust.py
  - docs/broker-acl.md
  - docs/diagnostics.md
  - docs/operations.md
  - docs/troubleshooting.md
  - pyproject.toml
  - tests/test_translations.py
covered_digest: "v2:sha256:d572d71fa977e52f060ab6857bd39ed03737d5d28afbd2f3a404e4c92fb92a49"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Release gate: hassfest rejected description next to fix_flow on approval_required, duplicate_instance_id and transferred (closed by plan 04-14)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Validate (hassfest + HACS) is green on the pushed phase branch / PR (plan 04-14, D4)"
    expected: "After pushing gsd/phase-04-operations-recovery-and-release (the branch is not on origin yet), `gh run list --workflow Validate --branch gsd/phase-04-operations-recovery-and-release --limit 1` shows conclusion success with both the hassfest and the HACS job green"
    why_human: "Only GitHub Actions can confirm it. Locally the hassfest container exits 0 with Invalid integrations: 0, and the HACS job was already green on origin/main"
  - test: "First release v0.1.0 (plan 04-01, D4)"
    expected: "After the phase is merged and Validate is green, push tag v0.1.0 (equal to manifest version 0.1.0); Release runs check-version, ci and validate, then creates the GitHub release with generated notes"
    why_human: "Needs a pushed tag on GitHub Actions"
  - test: "D5/D8 diagnostics download in a real Home Assistant (plan 04-07)"
    expected: "Settings > Devices & services > MQTT Actions > Download diagnostics yields a JSON with hub, roster and device rows; no action YAML, entity ids, service data, broker host or credentials; instance ids shortened to 8 characters"
    why_human: "Real frontend download and a real config entry are not reproduced by any automated test"
  - test: "D6 companion devices and mode selects for mirrored devices, two real instances (plan 04-06, assumption A14)"
    expected: "A mirror and an owned device with the same name appear as separate, distinguishable devices on the integration page; the mode select changes behavior (observe logs, disabled stops processing) against a real Mosquitto"
    why_human: "Real frontend rendering and registry behavior of core MQTT next to the companion device"
  - test: "D8 mode selects on the integration page (plan 04-05)"
    expected: "Hub instance-mode select and per-device mode selects appear in the configuration category with translated option labels (en and de); effective mode is the most restrictive of hub and device"
    why_human: "Appearance and translated labels in the real UI"
  - test: "D8 re-trigger from Developer Tools with two real instances (plan 04-10)"
    expected: "Calling mqtt_actions.retrigger with response shows per-instance statuses (executed, not_approved, paused, observing, disabled, no_answer) within the 5 s window; actions run on the approving instance and the state and baseline do not change"
    why_human: "Real services UI, real core MQTT and two running instances"
  - test: "Import and export in a real Home Assistant (plan 04-09) and export-file reachability"
    expected: "export_devices with file_name writes /config/mqtt_actions/<name>.json (mode 0600) and the file is NOT reachable through /local or any unauthenticated URL; import_devices of that file creates owned devices with new UUIDs, and mirrors on other instances ask for approval"
    why_human: "Real file system, real web server and a real second instance"
  - test: "D9 duplicate instance id, including the reworded confirm text (plans 04-12, 04-14)"
    expected: "With the same backup restored on two instances the Repairs issue appears; its dialog now carries the cause explanation (formerly the issue-level description) in the confirm step and reads correctly in en and de; after confirmation that instance runs under a new id with the original's devices as mirrors while the original's entities stay available"
    why_human: "Real core MQTT discovery, real Repairs dialog (the Repairs list now shows only the issue title for fixable issues) and two real instances"
  - test: "D10 adoption and returning old owner, including the reworded confirm text (plans 04-12, 04-14)"
    expected: "Adopt a device on instance two while instance one is stopped; start instance one; it shows the transferred Repairs issue whose confirm dialog opens with the adoption explanation and, after confirmation, the device as a mirror of instance two with working entities"
    why_human: "Real discovery overwrite and registry behavior during the start overlap; Repairs dialog rendering"
  - test: "README and docs read-through (plan 04-13, D5)"
    expected: "A new user can go from README to installation, the first operations and the troubleshooting entry of a Repairs issue by following links"
    why_human: "Readability and navigation are judgment"
  - test: "Wording of the approval dialog paragraph in German and English (plan 04-02, D5)"
    expected: "The paragraph naming run mode and breaker limits reads naturally"
    why_human: "Prose quality"
---

# Phase 4: Operations, Recovery and Release Verification Report

**Phase Goal:** As a user running several HA instances, I want to re-trigger actions, see who is connected and recover devices, so that I can operate the setup with confidence.
**Verified:** 2026-10-02
**Status:** human_needed
**Re-verification:** Yes - after gap closure plan 04-14

## Summary

The single gap of the first report (hassfest rejects the translations, so the `validate` job in front of `release.yml` is red) is closed in the code. I confirmed it independently of the SUMMARY: I loaded both translation files, and none of the three formerly offending issues (`approval_required`, `duplicate_instance_id`, `transferred`) carries an issue-level `description` next to `fix_flow` any more; the hassfest container I ran myself (`ghcr.io/home-assistant/hassfest`) reports `Validating translations... done` and `Invalid integrations: 0`. The other four truths were re-checked by regression: the full suite passes (1257 passed, up from 1228 because of the 04-14 tests), Ruff check and format are clean, and the diff since the first verification touches only `en.json`, `de.json` and `tests/test_translations.py`.

What remains cannot be confirmed from this machine: a green Validate run on GitHub for the pushed branch (the phase branch is not on origin), the first `v0.1.0` tag, and the real-Home-Assistant / two-instance checks that the executors deferred. They are listed as human verification, not as gaps.

## Re-verification of the previous gap

| Check | Evidence | Result |
|-------|----------|--------|
| No issue has `description` and `fix_flow` together (en and de) | Loaded both files with Python: `approval_required`, `duplicate_instance_id`, `transferred` have keys `[fix_flow, title]` only; the other 10 issues have `[description, title]` and no `fix_flow`; 13 issues in both languages | PASS |
| hassfest locally | `docker run --rm -v "$PWD":/github/workspace:Z ghcr.io/home-assistant/hassfest` -> `Validating translations... done`, `Integrations: 1`, `Invalid integrations: 0` | PASS |
| Text not lost | `git diff 19ae5d6 HEAD` on `en.json`: the removed issue-level sentences were merged into `fix_flow.step.confirm.description` of `duplicate_instance_id` and `transferred`; `approval_required` already carried all facts in its confirm step (only the obsolete "Open this repair" call to action was dropped) | PASS |
| Placeholders still supplied | Placeholders in confirm texts: `approval_required` {device, owner, hash, actions, startup, run_mode, breaker_max_runs, breaker_window, templated, residual, invalid}; `duplicate_instance_id` {instance, devices}; `transferred` {claimant, device}. `repairs.py` passes exactly these as `description_placeholders` in each flow's `async_show_form` | PASS |
| Local guard exists | `tests/test_translations.py` `test_issue_has_one_text_source` (all issues, both languages), `test_issue_guard_detects_the_hassfest_violations` (synthetic violation self-test), `test_fixable_issue_text_keeps_its_explanation`; in the full-suite run | PASS |
| `release.yml` unchanged and correct | `release` needs `[check-version, ci, validate]`; `validate` is the reusable `validate.yml` (hassfest + HACS). Previous failing run 36958292292: HACS job success, hassfest job failed only on `issues.approval_required.<fixable>` | Structure OK; remaining cause removed |
| Green Validate run on GitHub for this branch | Branch `gsd/phase-04-...` is not on origin (`git ls-remote`) | Human check |

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Re-trigger service (non-retained, `request_id` dedupe, rate-limited), caller sees which instances acknowledged and executed | VERIFIED (regression) | `retrigger.py` unchanged since the first verification (no code diff in `custom_components` except translations); tests `test_duplicate_request_ids_run_once`, `test_receiver_rate_limit_per_device`, `test_retained_requests_are_ignored`, `test_retrigger_runs_approved_instances_and_touches_no_state`, `test_roster_offline_and_silent_instances_are_no_answer`, `test_unapproved_mirror_answers_not_approved_and_runs_nothing` pass in the 1257-test run. Service registered with `SupportsResponse.OPTIONAL`, admin only; run path uses `test=True` so tracker, baseline and breaker stay untouched. |
| 2 | Roster with presence heartbeat; duplicate instance id detected and reported | VERIFIED (regression) | `presence.py` (30 s non-retained heartbeat, 90 s offline rule), `sensor.py` `RosterSensor`; duplicate detection -> `Manager.on_duplicate_id_changed` -> fixable Repairs issue -> `repairs.DuplicateIdRepairFlow`. The Repairs flow's confirm form still supplies `instance` and `devices`, which the reworded translation uses. Tests for heartbeats, offline rule and duplicate-id fix pass. |
| 3 | Manual resync, export/import JSON, transfer or adopt an orphaned device | VERIFIED (regression, with scope note) | `Manager.async_resync`, `portability.py`, `Manager.async_adopt`, services `resync`, `export_devices`, `import_devices`, `adopt_device`; tests `test_adoption_end_to_end`, `tests/test_portability.py`, `tests/test_services.py` pass. Scope note: D-09 in 04-CONTEXT.md deliberately implements adoption (with `force` for an online owner) and defers active hand-off; SYN-07 says "transfer ... or adopt". An override can record this (see end of report). The `transferred` Repairs issue (old owner follows the adopter) is the receiving side and is intact. |
| 4 | Per instance and device mode (run / observe / disabled); diagnostics download with sensitive data redacted | VERIFIED (regression) | `modes.py`, `Manager.effective_mode`, `select.py`, `diagnostics.py` allow-list plus `async_redact_data`; `tests/test_modes.py`, `tests/test_runner_modes.py`, `tests/test_companions.py`, `tests/test_diagnostics.py` pass. |
| 5 | README and docs cover setup, trust model, limitations; tagged release built automatically with manifest version matching the tag; CI runs unit, real-Mosquitto and multi-instance tiers | VERIFIED (code and workflow; the first green GitHub run is a human check) | Docs: `README.md`, `docs/operations.md`, `docs/diagnostics.md`, `docs/troubleshooting.md`, `docs/broker-acl.md` exist and `tests/test_docs.py` passes. Tiers: `ci.yml` jobs `unit`, `broker`, `multi-instance`; markers registered in `pyproject.toml`. Tag/manifest: `release.yml` `check-version` validates the tag shape and compares with `manifest.json` (0.1.0). Release gate: the only known reason `validate` failed (hassfest translations) is removed; hassfest passes locally with the same container image family used by the action. |

**Score:** 5/5 truths verified (0 present, behavior-unverified; deferred real-HA checks are human items)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/translations/en.json`, `de.json` | hassfest-valid translations, en/de parity | VERIFIED | One text source per issue, 13 issues in both languages, same keys and placeholders |
| `tests/test_translations.py` | Local model of the hassfest `fixable` rule | VERIFIED | Substantive (structural check over all issues plus a self-test so the guard cannot pass vacuously) and run in the suite |
| `.github/workflows/ci.yml`, `release.yml`, `validate.yml` | Tiered CI, gated release | VERIFIED | Wiring as described above; green GitHub run pending |
| `retrigger.py`, `presence.py`, `portability.py`, `services.py`/`services.yaml`, `sensor.py`, `button.py`, `select.py`, `entities.py`, `diagnostics.py`, `modes.py`, `repairs.py`, `document.py` | Operations features | VERIFIED | Unchanged since the first verification, wired as before |
| `docs/*.md`, `README.md` | Documentation | VERIFIED | |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `__init__.py` `async_setup` | `services.async_setup_services` | direct call | WIRED |
| `services._async_handle_retrigger` | `RetriggerCoordinator.async_retrigger` | `manager.retrigger` | WIRED |
| `Manager._on_message` / `_run_trigger` / test path | `effective_mode` | direct call | WIRED |
| `PresenceManager` -> `Manager.on_duplicate_id_changed` -> issue -> `DuplicateIdRepairFlow` | `async_create_fix_flow` | `ISSUE_DUPLICATE_INSTANCE_ID` | WIRED |
| `sync` transfer detection -> `TransferredRepairFlow` | `async_release_device_locally` | `ISSUE_TRANSFERRED_PREFIX` | WIRED |
| Repairs flows -> translations | `description_placeholders` vs `{...}` in `fix_flow.step.confirm.description` | placeholder sets compared above | WIRED (all placeholders supplied) |
| `release.yml` `release` job | `validate.yml` | `needs: validate` | WIRED; hassfest cause removed |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `RosterSensor` | online count, rows | `presence.rows()` from validated heartbeats | Yes | FLOWING |
| Diagnostics | roster, devices | `manager.presence`, `manager.devices`, `manager.mirrors` | Yes | FLOWING |
| Re-trigger response | `instances` | acks collected in `_Pending` | Yes | FLOWING |
| Repairs confirm text | instance, devices, device, claimant | live `Manager` state in each flow's form | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (unit, broker, multi-instance) | `uv run pytest -q` (run once) | 1257 passed in 79 s | PASS |
| Lint and format | `uv run ruff check .`, `uv run ruff format --check .` | All checks passed, 77 files formatted | PASS |
| hassfest | `docker run --rm -v "$PWD":/github/workspace:Z ghcr.io/home-assistant/hassfest` | `Invalid integrations: 0` | PASS |
| Translation structure | Python load of en.json and de.json, key sets per issue | no issue with both `description` and `fix_flow` | PASS |

### Probe Execution

No `probe-*.sh` files are declared or present. Skipped.

### Requirements Coverage

Every ID in the plan frontmatter (04-01 to 04-14) and every ID that REQUIREMENTS.md maps to Phase 4 is accounted for; no orphans.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| OPS-01 | 04-10 | SATISFIED | `retrigger.py`, SC1 tests |
| OPS-02 | 04-10 | SATISFIED | acks and service response |
| OPS-03 | 04-03, 04-04 | SATISFIED | heartbeat, roster sensor |
| OPS-04 | 04-07 | SATISFIED (real download is a human check) | `diagnostics.py`, `tests/test_diagnostics.py` |
| OPS-05 | 04-01, 04-13, 04-14 | SATISFIED in code (green Validate run and first tag are human checks) | Docs, tag check, tiered CI, hassfest-clean translations |
| OPS-06 | 04-01 | SATISFIED | three tiers, CI job per tier, 17 broker and 160 multi-instance tests |
| SYN-07 | 04-11, 04-12 | SATISFIED (adoption only, per D-09) | `async_adopt`, marker rules, `TransferredRepairFlow` |
| SYN-08 | 04-08, 04-09 | SATISFIED (see review WR-05, WR-06) | `portability.py`, services |
| SYN-09 | 04-02, 04-05, 04-06 | SATISFIED | modes, hash binding (see WR-03) |
| SYN-10 | 04-12, 04-14 | SATISFIED (real-instance check is human) | duplicate detection, fix flow, hassfest-valid issue text |
| DSC-04 | 04-04, 04-08 | SATISFIED | hub button and `resync` service share `async_resync` |

REQUIREMENTS.md bookkeeping is inconsistent right now: `OPS-05` is `[x]`/Complete, while OPS-01..04, OPS-06, SYN-07..10 and DSC-04 are `[ ]` with "Gaps Found" in the traceability table (they were reverted after the first verification). With the gap closed, those rows can go back to `[x]`/Complete; the verifier did not edit REQUIREMENTS.md or ROADMAP.md (the Phase 4 checkbox in ROADMAP.md is still unticked).

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| (all phase files) | TBD / FIXME / XXX markers | none | none found |
| (04-14 files) | `return null` / stub patterns | none | the change is JSON text plus a structural test |

### Code review (advisory, 04-REVIEW.md, all open)

Unchanged since the first report; none blocks a must-have. Worth deciding before the first public release: WR-02 (forged `transferred_from` marker or forged heartbeats can raise a Repairs flow whose confirm deletes local device configuration; the 04-14 rewording makes the confirm text explicit that the device is forgotten locally, which helps), WR-04 (adoption builds the Script unrestricted), WR-05 and WR-06 (import applies the broker denylist and skips Select UI option rules), WR-03 (`actions_hash` lower-cases StateValues), WR-12 (`release.yml` does not check that the tag is on `main`).

### Human Verification Required

See the `human_verification` list in the frontmatter. The two GitHub-only items come first: a green Validate run on the pushed branch and the `v0.1.0` tag. After them, the deferred real-HA checks (diagnostics download, companion devices and mode selects, re-trigger from Developer Tools, export file reachability, duplicate id and adoption flows with the reworded confirm dialogs, README read-through, dialog wording).

### Gaps Summary

No gaps remain. The previous gap (hassfest translation rule) is closed and guarded by a local test. Status is `human_needed` solely because of items that need GitHub Actions or a real Home Assistant.

Optional override to record the adoption-only reading of SYN-07:

```yaml
overrides:
  - must_have: "User can transfer ownership of a device or adopt an orphaned device (SYN-07)"
    reason: "D-09 in 04-CONTEXT.md: adoption of orphaned devices only; adopt_device with force covers taking over; active hand-off deferred"
    accepted_by: "akentner"
    accepted_at: "<ISO timestamp, to be set by the user>"
```

---

_Verified: 2026-10-02_
_Verifier: Claude (gsd-verifier)_
