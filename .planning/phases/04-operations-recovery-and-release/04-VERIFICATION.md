---
phase: 04-operations-recovery-and-release
verified: 2026-10-02T12:00:00Z
status: gaps_found
score: 4/5 must-haves verified
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
covered_digest: "v2:sha256:db115c92230a6149d4b9766a910f840ff5978621f7172142ae676b4f802a8af2"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "A tagged release is built automatically with the manifest version matching the tag; CI runs the unit, real-Mosquitto and multi-instance test tiers (ROADMAP SC5, OPS-05)"
    status: failed
    reason: "release.yml gates `release` on the `validate` job (hassfest + HACS). hassfest fails on the translations: three fixable issues (approval_required from Phase 3, duplicate_instance_id and transferred from this phase) carry both `description` and `fix_flow` at issue level, which hassfest forbids (exclusion group 'fixable'). The same failure is already red on origin/main (Validate, scheduled run 36958292292 and push runs 36944099412, 36944162521) and would be red on this branch. The first v*.*.* tag would therefore stop at `validate` and never create the GitHub release. No local test models this hassfest rule (tests/test_translations.py checks only en/de parity)."
    artifacts:
      - path: "custom_components/mqtt_actions/translations/en.json"
        issue: "issues.approval_required, issues.duplicate_instance_id, issues.transferred have both `description` and `fix_flow` keys"
      - path: "custom_components/mqtt_actions/translations/de.json"
        issue: "same structure (keep parity)"
    missing:
      - "Remove the issue-level `description` from the three fixable issues (move the text into fix_flow.step.<step>.description, which already exists for each), in en.json and de.json"
      - "Add a test in tests/test_translations.py that fails when an issue has both `description` and `fix_flow`, so the hassfest rule is covered locally"
      - "Confirm Validate (hassfest + HACS) is green on the pushed phase branch before the first tag"
human_verification:
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
  - test: "D9 duplicate instance id (plan 04-12)"
    expected: "With the same backup restored on two instances the Repairs issue appears, its text reads correctly, and after confirmation that instance runs under a new id with the original's devices as mirrors while the original's entities stay available"
    why_human: "Real core MQTT discovery, real Repairs dialog and two real instances"
  - test: "D10 adoption and returning old owner (plan 04-12)"
    expected: "Adopt a device on instance two while instance one is stopped; start instance one; it shows the transferred Repairs issue and, after confirmation, the device as a mirror of instance two with working entities"
    why_human: "Real discovery overwrite and registry behavior during the start overlap"
  - test: "README and docs read-through (plan 04-13, D5)"
    expected: "A new user can go from README to installation, the first operations and the troubleshooting entry of a Repairs issue by following links"
    why_human: "Readability and navigation are judgment"
  - test: "First release (plan 04-01, D4)"
    expected: "After the gap above is closed and the phase is merged, push v0.1.0 (equal to manifest version 0.1.0); Release runs check-version, ci and validate, then creates the GitHub release with generated notes"
    why_human: "Needs a pushed tag on GitHub Actions"
  - test: "Wording of the approval dialog paragraph in German and English (plan 04-02, D5)"
    expected: "The paragraph naming run mode and breaker limits reads naturally"
    why_human: "Prose quality"
---

# Phase 4: Operations, Recovery and Release Verification Report

**Phase Goal:** As a user running several HA instances, I want to re-trigger actions, see who is connected and recover devices, so that I can operate the setup with confidence.
**Verified:** 2026-10-02
**Status:** gaps_found
**Re-verification:** No - initial verification

## Summary

The implementation is real, wired and tested. I ran the full suite once (1228 passed, including the 17 real-Mosquitto tests and 160 multi-instance tests; mosquitto is installed locally, so none were skipped), `ruff check` and `ruff format --check` (clean). Code review 04-REVIEW.md has 0 critical findings and 12 open warnings (04-REVIEW-DISPOSITION.md); none of them makes a must-have false on its own.

One goal-relevant gap was found that no local test sees: the hassfest step of the `Validate` workflow fails, and `release.yml` requires `validate` before it creates the release. Roadmap success criterion 5 ("a tagged release is built automatically") is therefore not achieved yet. The fix is small and mechanical. Once it is closed, the remaining items are the real-Home-Assistant, two-instance and first-release checks that the executors deferred; those are listed under human verification.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Re-trigger service (non-retained, `request_id` dedupe, rate-limited), caller sees which instances acknowledged and executed | VERIFIED | `retrigger.py` (487 lines): non-retained publish (`retain=False`), receiver drops retained, stale, duplicate ids (`_seen`), per-device 5 s limit on receiver and caller side, acks on `acks_topic`, response `instances[]` with executed/not_approved/paused/observing/disabled/error/no_answer collected within `RETRIGGER_ACK_WINDOW_SECONDS`. Registered in `services.py` with `SupportsResponse.OPTIONAL`, admin only. Run path uses `test=True` enqueue, so tracker, baseline and breaker are untouched (D-01). Behavioral tests pass: `test_duplicate_request_ids_run_once`, `test_receiver_rate_limit_per_device`, `test_retained_requests_are_ignored`, `test_retrigger_runs_approved_instances_and_touches_no_state`, `test_roster_offline_and_silent_instances_are_no_answer`, `test_unapproved_mirror_answers_not_approved_and_runs_nothing`. |
| 2 | Roster with presence heartbeat; duplicate instance id detected and reported | VERIFIED | `presence.py`: 30 s non-retained heartbeat with session id, 90 s offline rule, strict parsing and caps, `Roster.rows()`; `sensor.py` `RosterSensor` on the hub device (diagnostic, `instances` attribute). Duplicate detection via foreign session id needs `DUPLICATE_ID_CONFIRMATIONS` observations, then `Manager.on_duplicate_id_changed` creates the fixable Repairs issue; `repairs.DuplicateIdRepairFlow` calls `async_resolve_duplicate_id`. Tests: `test_instances_see_each_other_through_heartbeats`, `test_roster_marks_a_peer_offline_after_90_seconds`, `test_duplicate_detection_changes_nothing_by_itself`, `test_duplicate_id_fix_leaves_the_originals_topics_byte_identical`. |
| 3 | Manual resync, export/import JSON, transfer or adopt an orphaned device | VERIFIED (with scope note) | `Manager.async_resync` (cooldown, documents then discovery then `online` then heartbeat), hub `ResyncButton`, `resync` service. `portability.py` + `export_devices`/`import_devices` services: private dir 0700/file 0600, bare-name regex, `O_NOFOLLOW`, all-or-nothing, new UUIDs, strict `parse_document` per item. `Manager.async_adopt` with owner-offline check or `force`, approval required, additive `transferred_from` marker honored only when the pinned owner is offline; `adopt_device` service. Tests: `test_adoption_end_to_end`, `test_adoption_needs_the_owner_offline_or_force`, `test_adoption_clears_nothing_on_the_broker`, `test_marker_survives_a_restart_of_the_adopter`, `test_forged_marker_cannot_repin_when_the_owner_is_online`, `tests/test_portability.py`, `tests/test_services.py`. Scope note: SYN-07 and this criterion say "transfer ... or adopt"; D-09 (user decision in 04-CONTEXT.md) deliberately implements adoption only, with `force` as the way to take over an online owner. Active hand-off is deferred by the user. Suggested override below if the user wants it recorded. |
| 4 | Per instance and device mode (run / observe / disabled); diagnostics download with sensitive data redacted | VERIFIED | `modes.py`, `Manager.effective_mode` (most restrictive of hub and device), enforced in `_on_message` (disabled: no processing, no baseline), `_run_trigger` (observe: logged, no breaker count), test-button path and re-trigger path; instance mode and device modes persisted in the Store; `select.py` `InstanceModeSelect` and `DeviceModeSelect` on hub and companion devices. `diagnostics.py` builds from an allow-list (no actions, entity ids, service data, broker host or credentials, ids shortened to 8 chars) and runs `async_redact_data` as a net. Tests: `tests/test_modes.py`, `tests/test_runner_modes.py`, `tests/test_companions.py`, `test_leaving_disabled_rebaselines_without_running`, `tests/test_diagnostics.py`. |
| 5 | README and docs cover setup, trust model and limitations; tagged release built automatically with manifest version matching the tag; CI runs unit, real-Mosquitto and multi-instance tiers | FAILED | Docs: VERIFIED (README 338 lines, `docs/operations.md`, `diagnostics.md`, `troubleshooting.md` with an entry per Repairs issue, `broker-acl.md` with heartbeat and acks lines; `tests/test_docs.py` passes). Tiers: VERIFIED (`ci.yml` has `unit`, `broker` with mosquitto install and `MQTT_ACTIONS_REQUIRE_BROKER=1`, `multi-instance`; markers registered in `pyproject.toml`). Tag/manifest check: VERIFIED (`release.yml` `check-version` compares `GITHUB_REF_NAME` with `manifest.json` 0.1.0 after validating the tag shape). **Release gate: FAILED.** `release` needs `[check-version, ci, validate]`, and `validate` (hassfest) fails: `[TRANSLATIONS] Invalid translations/en.json: two or more values in the same group of exclusion 'fixable' at 'issues.approval_required.<fixable>'` (GitHub run 36958292292, also push runs on main 36944099412 and 36944162521 and the phase-3 branch). `en.json` has `description` and `fix_flow` side by side in `approval_required`, `duplicate_instance_id` and `transferred` (confirmed by loading the file). The first tag would never produce a release. |

**Score:** 4/5 truths verified (0 present, behavior-unverified; the deferred real-HA checks are human items, not presence-only truths)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/retrigger.py` | Re-trigger protocol | VERIFIED | Substantive, wired via `manager.retrigger`, `services.py` |
| `custom_components/mqtt_actions/presence.py` | Heartbeat, roster, duplicate id | VERIFIED | Wired via `manager.presence`, `sensor.py`, `diagnostics.py`, `repairs.py` |
| `custom_components/mqtt_actions/portability.py` | Export/import | VERIFIED | Wired in `services.py` |
| `custom_components/mqtt_actions/services.py` + `services.yaml` | Five admin services in `async_setup` | VERIFIED | resync, export_devices, import_devices, retrigger, adopt_device |
| `custom_components/mqtt_actions/sensor.py`, `button.py`, `select.py`, `entities.py` | Hub entities, companions | VERIFIED | `PLATFORMS` forwarded in `__init__.py` after manager start |
| `custom_components/mqtt_actions/diagnostics.py` | Redacted diagnostics | VERIFIED | Allow-list builder |
| `custom_components/mqtt_actions/modes.py` | Mode helpers | VERIFIED | Used by manager |
| `custom_components/mqtt_actions/repairs.py` | Duplicate-id and transferred fix flows | VERIFIED | Wired in `async_create_fix_flow` |
| `custom_components/mqtt_actions/document.py` (`actions_hash`, transfer marker) | D-16, D-09 | VERIFIED | Hash covers run mode and both breaker limits; `transferred_from` additive, no schema bump |
| `.github/workflows/ci.yml`, `release.yml`, `validate.yml` | Tiered CI, gated release | PARTIAL | Structure is correct; `validate` job is red because of translations (gap) |
| `custom_components/mqtt_actions/translations/en.json`, `de.json` | hassfest-valid translations | FAILED | Three fixable issues violate the hassfest `fixable` exclusion |
| `docs/*.md`, `README.md` | Documentation | VERIFIED | |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `__init__.py` `async_setup` | `services.async_setup_services` | direct call | WIRED |
| `services._async_handle_retrigger` | `RetriggerCoordinator.async_retrigger` | `manager.retrigger` | WIRED |
| `Manager._on_message` / `_run_trigger` / test path / `_decide` | `effective_mode` | direct call | WIRED |
| `PresenceManager._on_message` | `Manager.on_duplicate_id_changed` | `_observe_duplicate` | WIRED |
| `Manager.on_duplicate_id_changed` issue | `repairs.DuplicateIdRepairFlow` | `ISSUE_DUPLICATE_INSTANCE_ID` in `async_create_fix_flow` | WIRED |
| `sync` transfer detection | `TransferredRepairFlow` -> `async_release_device_locally` | `ISSUE_TRANSFERRED_PREFIX` | WIRED |
| `release.yml` `release` job | `validate.yml` | `needs: validate` | WIRED, but the called workflow fails |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `RosterSensor` | online count, rows | `presence.rows()` from validated heartbeats | Yes | FLOWING |
| Diagnostics | roster, devices | `manager.presence`, `manager.devices`, `manager.mirrors` | Yes | FLOWING |
| Re-trigger response | `instances` | acks collected in `_Pending` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite (unit, broker, multi-instance) | `uv run pytest -q -x` (run once) | 1228 passed in 80 s | PASS |
| Lint and format | `uv run ruff check .` and `ruff format --check .` | All checks passed, 77 files formatted | PASS |
| Tier markers exist | `pytest --collect-only -m broker` / `-m multi_instance` | 17 and 160 tests | PASS |
| hassfest on GitHub | `gh run view 36958292292 --log-failed` | translations error on `issues.approval_required` | FAIL |

### Probe Execution

No `probe-*.sh` files are declared or present. Skipped.

### Requirements Coverage

Every ID in the plan frontmatter and every ID that REQUIREMENTS.md maps to Phase 4 is accounted for; there are no orphaned requirements.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| OPS-01 | 04-10 | SATISFIED | `retrigger.py`, SC1 tests |
| OPS-02 | 04-10 | SATISFIED | acks and service response |
| OPS-03 | 04-03, 04-04 | SATISFIED | heartbeat, roster sensor |
| OPS-04 | 04-07 | SATISFIED (real download is a human check) | `diagnostics.py`, `tests/test_diagnostics.py` |
| OPS-05 | 04-01, 04-13 | BLOCKED | Docs and tag check exist; release gate red because of hassfest (gap) |
| OPS-06 | 04-01 | SATISFIED | three tiers, CI job per tier, 17 broker and 160 multi-instance tests |
| SYN-07 | 04-11, 04-12 | SATISFIED (adoption only, per D-09) | `async_adopt`, marker rules, `TransferredRepairFlow` |
| SYN-08 | 04-08, 04-09 | SATISFIED (see WR-05, WR-06) | `portability.py`, services |
| SYN-09 | 04-02, 04-05, 04-06 | SATISFIED | modes, hash binding (see WR-03) |
| SYN-10 | 04-12 | SATISFIED (real-instance check is human) | duplicate detection and fix flow |
| DSC-04 | 04-04, 04-08 | SATISFIED | hub button and `resync` service share `async_resync` |

REQUIREMENTS.md state: all 44 v1 IDs are `[x]` and "Complete" in the traceability table, including the Phase 4 IDs that are shared across plans (OPS-03, DSC-04, SYN-07, SYN-08, SYN-09, OPS-05). That is ahead of the evidence for OPS-05 (release gate red, no release ever created) and for the parts of OPS-04, SYN-07 and SYN-10 that rest on the pending real-instance checks. ROADMAP still has Phase 4 unchecked, which is consistent. Recommend leaving OPS-05 un-ticked until the gap is closed and the first release has run; the verifier did not edit REQUIREMENTS.md.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `translations/en.json`, `de.json` | `description` plus `fix_flow` on three fixable issues | BLOCKER | hassfest fails, release gate red |
| (all phase files) | TBD / FIXME / XXX markers | none | grep found none; the TODO/PLACEHOLDER matches are the identifier `ADOPT_PLACEHOLDERS` |

### Code review (advisory, 04-REVIEW.md, all open)

None blocks a must-have on its own; they are hardening items. Worth deciding before the first public release:
- WR-02: a forged `transferred_from` marker or two forged heartbeats can raise a Repairs flow whose confirm step deletes local device configuration; the confirm text does not say the actions are deleted.
- WR-04: adoption builds the Script unrestricted, dropping the templated-service guard that held for the mirror.
- WR-05 and WR-06: import applies the broker denylist (so an own export with denied services will not restore) and skips the UI option rules for Select devices; this narrows what SYN-08 "export as backup" means.
- WR-03: `actions_hash` lower-cases StateValues, so the README claim that the hash binds everything that can run is slightly too strong.
- WR-12: `release.yml` does not verify that the tag is on `main`.
- WR-01, WR-07 to WR-11 and IN-01 to IN-04 are robustness items.

### Human Verification Required

See the `human_verification` list in the frontmatter. These are the deferred real-HA, two-instance and first-release checks (D5 diagnostics download and dialog wording, D6 companion devices on two real instances, D8 mode selects and re-trigger from Developer Tools, D9 duplicate id, D10 adoption with a returning owner, export file not reachable via /local, README read-through, first v*.*.* release). They only become the sole open items once the gap below is fixed.

### Gaps Summary

One gap, single root cause: the translation files put `description` next to `fix_flow` for three fixable Repairs issues. hassfest rejects that, so the `validate` job is red on every branch that contains Phase 3 or 4, and `release.yml` will not create a release behind it. Phase 3 introduced the pattern for `approval_required`; Phase 4 repeated it for `duplicate_instance_id` and `transferred`, and its release workflow made the failure goal-relevant. The fix is to drop the issue-level `description` of those three entries (the confirm step already has its own text), mirror it in `de.json`, add a local test for the rule, and confirm Validate is green on the pushed branch.

No override is suggested for this gap. For the adoption-only reading of SYN-07 an override could be recorded if the user wants the deviation from "transfer or adopt" on file:

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
