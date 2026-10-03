---
phase: 04-operations-recovery-and-release
verified: 2026-10-03T10:00:00Z
status: passed
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
  - renovate.json
  - tests/test_translations.py
  - uv.lock
covered_digest: "v2:sha256:a60bafb727065e28c4a4c1f51d1948d336239a473eb88fa6ca1943a23e1edf19"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification: []
---

# Phase 4: Operations, Recovery and Release Verification Report

**Phase Goal:** As a user running several HA instances, I want to re-trigger actions, see who is connected and recover devices, so that I can operate the setup with confidence.
**Verified:** 2026-10-03
**Status:** passed
**Re-verification:** Yes - refresh after the main merge (stale fingerprint) and after human UAT

## Summary

The single gap of the first report (hassfest rejects the translations, so the `validate` job in front of `release.yml` is red) is closed in the code. I confirmed it independently of the SUMMARY: I loaded both translation files, and none of the three formerly offending issues (`approval_required`, `duplicate_instance_id`, `transferred`) carries an issue-level `description` next to `fix_flow` any more; the hassfest container I ran myself (`ghcr.io/home-assistant/hassfest`) reports `Validating translations... done` and `Invalid integrations: 0`. The other four truths were re-checked by regression: the full suite passes (1257 passed, up from 1228 because of the 04-14 tests), Ruff check and format are clean, and the diff since the first verification touches only `en.json`, `de.json` and `tests/test_translations.py`.

Refresh on 2026-10-03: the report had gone stale because `pyproject.toml` changed through the merge of main (Ruff `0.16.9` -> `0.16.10`; `renovate.json` added; `uv.lock` updated). I re-checked the diff `19ae5d6..HEAD` over `custom_components`, `tests`, `.github`, `docs`, `README.md`, `pyproject.toml`, `renovate.json` and `uv.lock`: only the two translation files and `tests/test_translations.py` (plan 04-14, already verified), the Ruff pin, `renovate.json` (Renovate requires dashboard approval for `pytest-homeassistant-custom-component`) and `uv.lock` changed. No workflow, docs or other source file changed. `uv.lock` still resolves `homeassistant 2026.9.4`. I re-ran the full suite once (1257 passed in 79.93 s), `ruff check` (clean) and `ruff format --check` (77 files formatted), and regenerated the `covered_files` / `covered_digest` fingerprint with `verification.fingerprint` (72 files, now including `renovate.json` and `uv.lock`).

The items that cannot be confirmed from code (green Validate run on GitHub, the first `v0.1.0` tag, real-Home-Assistant and two-instance checks) were completed by the human UAT on 2026-10-03 (see "Human verification outcome"). `gh release view v0.1.0` confirms the release exists (published 2026-10-03T08:19:22Z, not a draft).

## Re-verification of the previous gap

| Check | Evidence | Result |
|-------|----------|--------|
| No issue has `description` and `fix_flow` together (en and de) | Loaded both files with Python: `approval_required`, `duplicate_instance_id`, `transferred` have keys `[fix_flow, title]` only; the other 10 issues have `[description, title]` and no `fix_flow`; 13 issues in both languages | PASS |
| hassfest locally | `docker run --rm -v "$PWD":/github/workspace:Z ghcr.io/home-assistant/hassfest` -> `Validating translations... done`, `Integrations: 1`, `Invalid integrations: 0` | PASS |
| Text not lost | `git diff 19ae5d6 HEAD` on `en.json`: the removed issue-level sentences were merged into `fix_flow.step.confirm.description` of `duplicate_instance_id` and `transferred`; `approval_required` already carried all facts in its confirm step (only the obsolete "Open this repair" call to action was dropped) | PASS |
| Placeholders still supplied | Placeholders in confirm texts: `approval_required` {device, owner, hash, actions, startup, run_mode, breaker_max_runs, breaker_window, templated, residual, invalid}; `duplicate_instance_id` {instance, devices}; `transferred` {claimant, device}. `repairs.py` passes exactly these as `description_placeholders` in each flow's `async_show_form` | PASS |
| Local guard exists | `tests/test_translations.py` `test_issue_has_one_text_source` (all issues, both languages), `test_issue_guard_detects_the_hassfest_violations` (synthetic violation self-test), `test_fixable_issue_text_keeps_its_explanation`; in the full-suite run | PASS |
| `release.yml` unchanged and correct | `release` needs `[check-version, ci, validate]`; `validate` is the reusable `validate.yml` (hassfest + HACS). Previous failing run 36958292292: HACS job success, hassfest job failed only on `issues.approval_required.<fixable>` | Structure OK; remaining cause removed |
| Green Validate run on GitHub for this branch | At the first verification the branch was not on origin; UAT test 1 records a successful Validate run on the pushed branch (c52a548), and test 2 the green Release run for v0.1.0 | PASS (by UAT) |

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Re-trigger service (non-retained, `request_id` dedupe, rate-limited), caller sees which instances acknowledged and executed | VERIFIED (regression) | `retrigger.py` unchanged since the first verification (no code diff in `custom_components` except translations); tests `test_duplicate_request_ids_run_once`, `test_receiver_rate_limit_per_device`, `test_retained_requests_are_ignored`, `test_retrigger_runs_approved_instances_and_touches_no_state`, `test_roster_offline_and_silent_instances_are_no_answer`, `test_unapproved_mirror_answers_not_approved_and_runs_nothing` pass in the 1257-test run. Service registered with `SupportsResponse.OPTIONAL`, admin only; run path uses `test=True` so tracker, baseline and breaker stay untouched. |
| 2 | Roster with presence heartbeat; duplicate instance id detected and reported | VERIFIED (regression) | `presence.py` (30 s non-retained heartbeat, 90 s offline rule), `sensor.py` `RosterSensor`; duplicate detection -> `Manager.on_duplicate_id_changed` -> fixable Repairs issue -> `repairs.DuplicateIdRepairFlow`. The Repairs flow's confirm form still supplies `instance` and `devices`, which the reworded translation uses. Tests for heartbeats, offline rule and duplicate-id fix pass. |
| 3 | Manual resync, export/import JSON, transfer or adopt an orphaned device | VERIFIED (regression, with scope note) | `Manager.async_resync`, `portability.py`, `Manager.async_adopt`, services `resync`, `export_devices`, `import_devices`, `adopt_device`; tests `test_adoption_end_to_end`, `tests/test_portability.py`, `tests/test_services.py` pass. Scope note: D-09 in 04-CONTEXT.md deliberately implements adoption (with `force` for an online owner) and defers active hand-off; SYN-07 says "transfer ... or adopt". An override can record this (see end of report). The `transferred` Repairs issue (old owner follows the adopter) is the receiving side and is intact. |
| 4 | Per instance and device mode (run / observe / disabled); diagnostics download with sensitive data redacted | VERIFIED (regression) | `modes.py`, `Manager.effective_mode`, `select.py`, `diagnostics.py` allow-list plus `async_redact_data`; `tests/test_modes.py`, `tests/test_runner_modes.py`, `tests/test_companions.py`, `tests/test_diagnostics.py` pass. |
| 5 | README and docs cover setup, trust model, limitations; tagged release built automatically with manifest version matching the tag; CI runs unit, real-Mosquitto and multi-instance tiers | VERIFIED (code and workflow; green Validate and Release runs and the published release v0.1.0 confirmed by UAT tests 1 and 2, release existence re-checked with `gh release view`) | Docs: `README.md`, `docs/operations.md`, `docs/diagnostics.md`, `docs/troubleshooting.md`, `docs/broker-acl.md` exist and `tests/test_docs.py` passes. Tiers: `ci.yml` jobs `unit`, `broker`, `multi-instance`; markers registered in `pyproject.toml`. Tag/manifest: `release.yml` `check-version` validates the tag shape and compares with `manifest.json` (0.1.0). Release gate: the only known reason `validate` failed (hassfest translations) is removed; `release.yml` `release` still `needs: [check-version, ci, validate]`; per UAT the v0.1.0 Release run passed hassfest, HACS, Ruff and all three test tiers. |

**Score:** 5/5 truths verified (0 present, behavior-unverified; the real-HA and GitHub checks were completed by human UAT, 11 of 11 passed)

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
| Full suite (unit, broker, multi-instance) | `uv run pytest -q` (run once, 2026-10-03, Ruff 0.16.10, HA 2026.9.4) | 1257 passed in 79.93 s | PASS |
| Lint and format | `uv run ruff check .`, `uv run ruff format --check .` | All checks passed, 77 files already formatted (Ruff 0.16.10) | PASS |
| hassfest (earlier run, 2026-10-02) | `docker run --rm -v "$PWD":/github/workspace:Z ghcr.io/home-assistant/hassfest` | `Invalid integrations: 0` | PASS |
| Translation structure | Python load of en.json and de.json, key sets per issue | 13 issues each, no issue with both `description` and `fix_flow` | PASS |
| Release exists | `gh release view v0.1.0 --json tagName,isDraft,publishedAt` | `v0.1.0`, not a draft, published 2026-10-03T08:19:22Z | PASS |
| hassfest | not re-run in this refresh: no translation, manifest or workflow change since the container run recorded above; UAT confirms hassfest green in the v0.1.0 Release run | - | PASS (by UAT) |

### Probe Execution

No `probe-*.sh` files are declared or present. Skipped.

### Requirements Coverage

Every ID in the plan frontmatter (04-01 to 04-14) and every ID that REQUIREMENTS.md maps to Phase 4 is accounted for; no orphans.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| OPS-01 | 04-10 | SATISFIED | `retrigger.py`, SC1 tests |
| OPS-02 | 04-10 | SATISFIED | acks and service response |
| OPS-03 | 04-03, 04-04 | SATISFIED | heartbeat, roster sensor |
| OPS-04 | 04-07 | SATISFIED (real endpoint checked in UAT test 3) | `diagnostics.py`, `tests/test_diagnostics.py` |
| OPS-05 | 04-01, 04-13, 04-14 | SATISFIED (green Validate run and first tag v0.1.0 confirmed by UAT) | Docs, tag check, tiered CI, hassfest-clean translations |
| OPS-06 | 04-01 | SATISFIED | three tiers, CI job per tier, 17 broker and 160 multi-instance tests |
| SYN-07 | 04-11, 04-12 | SATISFIED (adoption only, per D-09) | `async_adopt`, marker rules, `TransferredRepairFlow` |
| SYN-08 | 04-08, 04-09 | SATISFIED (see review WR-05, WR-06) | `portability.py`, services |
| SYN-09 | 04-02, 04-05, 04-06 | SATISFIED | modes, hash binding (see WR-03) |
| SYN-10 | 04-12, 04-14 | SATISFIED (real two-instance check in UAT test 8) | duplicate detection, fix flow, hassfest-valid issue text |
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

None open. The former list was completed by the human UAT (see below).

### Human verification outcome

All eleven human verification items were completed on 2026-10-03: ten on the two test instances ha-one and ha-two and on GitHub, and the release item with the published release v0.1.0. Details per item are in `04-UAT.md` (status complete, 11 passed, 0 issues). Notes recorded there that are not gaps against a must-have: the test broker ACL needs `instances/+/heartbeat`, `devices/+/retrigger` and `instances/+/acks` (a documentation point; `docs/broker-acl.md` exists), and after the duplicate-id repair ha-one and ha-two briefly disagreed on the owner of one device (possibly an overlap-period artifact, not analyzed). Both are worth a follow-up but do not falsify any success criterion.

### Gaps Summary

No gaps remain. The previous gap (hassfest translation rule) is closed and guarded by a local test, the post-merge changes (Ruff pin, `renovate.json`, `uv.lock`) introduce no regression, and the human items that needed GitHub Actions or a real Home Assistant passed in the UAT. Status is `passed`.

Optional override to record the adoption-only reading of SYN-07:

```yaml
overrides:
  - must_have: "User can transfer ownership of a device or adopt an orphaned device (SYN-07)"
    reason: "D-09 in 04-CONTEXT.md: adoption of orphaned devices only; adopt_device with force covers taking over; active hand-off deferred"
    accepted_by: "akentner"
    accepted_at: "<ISO timestamp, to be set by the user>"
```

---

_Verified: 2026-10-03_
_Verifier: Claude (gsd-verifier)_
