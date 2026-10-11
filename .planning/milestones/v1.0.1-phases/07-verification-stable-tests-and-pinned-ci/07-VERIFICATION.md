---
phase: 07-verification-stable-tests-and-pinned-ci
verified: 2026-10-04T17:30:00Z
status: human_needed
score: 4/4 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - .github/workflows/validate.yml
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-01-PLAN.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-01-SUMMARY.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-02-PLAN.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-02-SUMMARY.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-03-PLAN.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-03-SUMMARY.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-04-PLAN.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-04-SUMMARY.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-05-PLAN.md
  - .planning/phases/07-verification-stable-tests-and-pinned-ci/07-05-SUMMARY.md
  - custom_components/mqtt_actions/manifest.json
  - tests/conftest.py
  - tests/test_hub_removal.py
  - tests/test_manager_breaker.py
  - tests/test_modes.py
  - tests/test_repo_structure.py
covered_digest: "v2:sha256:e927c7c98cd7112be74282c95d751b28d40fd14979426c8193b0f25b40c10039"
behavior_unverified: 0
overrides_applied: 0
re_verification: false
gaps: []
human_verification:
  - test: "Run the ten deferred Phase 1 to 3 human checks (Phase 1: HACS install, EN/DE strings, action editor banners, Repairs dialog of a failing action, retained-versus-live chain on real HA + broker, core version of hassio-n2plus; Phase 2: select subentry flow in the real frontend, breaker loop on real Mosquitto + real HA; Phase 3: approval-request Markdown rendering, device-delete dialogs with hostile names), then re-run the verifier or /gsd-verify-work for Phases 1 to 3."
    expected: "Each check passes and is recorded with evidence; archived Phases 1 to 3 then read `passed` under `verification status`, or the owner accepts individual items as overrides under the owner's name."
    why_human: "These checks need a real HA frontend, a real HACS client, or a real HA core with a real retaining broker. No automated tier performs them. Owner decision 2026-10-04 deferred them to Phase 8, but Phase 8's ROADMAP success criteria (UAT-01 to UAT-04) do not name them yet."
audit_acknowledged:
  milestone: v1.0.1
  at: 2026-10-11
  status: human_needed
---

# Phase 7: Verification, Stable Tests and Pinned CI Verification Report

**Phase Goal:** The v1.0.1 build is verifiably sound: Phases 1 to 4 have a current verification of the final code, the test suite is deterministic, and CI and release no longer drift with the floating `ubuntu-latest` image.
**Verified:** 2026-10-04
**Status:** human_needed
**Re-verification:** No, initial verification

Verifier stance: SUMMARY claims were not trusted. Workflows, tests and archived reports were read directly. The `verification status` readings, the five GitHub runs, the RED commit, the guard test and the previously flaky test were re-checked independently in this run.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Phases 1 to 4 each have a current verification, and `init.manager` no longer reports any of them as stale | VERIFIED as written, with a human-needed carry-over (see below) | `verification status` re-run now on the four archived dirs: Phase 1 `human_needed`, Phase 2 `human_needed`, Phase 3 `human_needed`, Phase 4 `passed`. None reads `stale` (Phase 5, out of scope, still reads `stale`). Each report has `verified: 2026-10-04`, a `v2:sha256` `covered_digest`, `gaps: []`, scores 8/8, 10/10, 5/5, 5/5. `init manager` lists only phases 6 to 8 and reports no stale phase, but it never listed Phases 1 to 4, so that half of the criterion is vacuously true and the archived `verification status` is the real gate (the ledger says this). |
| 2 | Full suite (unit, real-Mosquitto, multi-instance) passes three consecutive runs; `test_delete_device_own_subscription_never_sees_state_clear` no longer flakes because its cause is fixed, not retried or skipped | VERIFIED | Ledger: three local runs of `1490 passed` (111.42, 111.42, 110.26 s), `MQTT_ACTIONS_REQUIRE_BROKER=1`, no skip. Three consecutive CI dispatch runs (37205596675, 37205721595, 37205851615) re-checked via `gh run view`: all success, all four jobs, headSha `d92b87f`; job log of run 3 shows 17 broker + 1308 unit + 165 multi-instance = 1490. `tests/conftest.py:49` has a permanent autouse `always_slow_event_loop` fixture (`slow_callback_duration = 0.0`), so the foreign asyncio slow-callback WARNING is present in every test. The assertions that counted it are scoped to `custom_components.mqtt_actions` via `tests/log_helpers.py::own_warnings`. A grep for `xfail`, `flaky`, `reruns`, `mark.skip` and `pytest.skip` in the touched test files and `pyproject.toml` returns nothing. Spot-check in this run: the named test plus `test_manager_breaker`, `test_modes`, `test_hub_removal` and `test_repo_structure`: 115 passed with the probe on. 50 of 50 stress repetitions under load are in the ledger (not re-run, 354 s). See the caveat below on how the named test's own fix came about. |
| 3 | No job in `ci.yml`, `validate.yml` or `release.yml` runs on `ubuntu-latest`; every job names one pinned runner; CI and Validate green on it | VERIFIED | `grep -rn runs-on .github/workflows`: eight jobs (ci 4, validate 2, release 2), all `ubuntu-24.04`; `ubuntu-latest` appears nowhere under `.github`. Guard `test_every_job_runs_on_one_pinned_runner` globs the whole workflow dir. I ran it at its RED commit `758e16b` in a throwaway worktree and it failed (`1 failed`), so the RED was real. GREEN order is `758e16b` then `a5d54d9` then `5cedd7b`. `gh run view` confirms three CI runs and one Validate run (37205956233: hassfest and HACS success) on `d92b87f`. The job logs show `Image: ubuntu-24.04`. The `Version: 20260901.588` lines are the runner provisioner, not the image. No non-planning file differs between `d92b87f` and HEAD (`git diff --stat d92b87f HEAD -- . ':!.planning'` is empty). The proven code is therefore the final code. |
| 4 | The release workflow runs on the same pinned runner and passes end to end (check-version, CI, validate, release), shown by a prerelease tag run | VERIFIED | `gh run view 37206309249`: workflow Release, event push, headSha `4d24fb4` (the rc tag commit), conclusion success, 8 jobs all success (Tag matches manifest version, four CI jobs, hassfest, HACS, Create GitHub release). `Image: ubuntu-24.04` appears 8 times and is the only image value. Cleanup re-checked: `gh release list` shows only `v1.0.0 Latest` and `v0.1.0`; `git ls-remote --tags origin` shows only `v0.1.0` and `v1.0.0`; the manifest is `1.0.0` again with a net-zero diff. |

**Score:** 4/4 criteria met as literally written. Criterion 1 carries an open human-verification list (below), so the overall status is `human_needed`, not `passed`.

### Judgment on success criterion 1 (the contested one)

- The criterion text requires "a current verification" and "not reported stale". Both hold. A `human_needed` report is a current, honest verification: all truths are verified, `gaps: []`, and the open items are checks only a real frontend or real HA plus broker can make.
- The plan-level gate (07-05: "`passed` for all four") is NOT met for Phases 1 to 3. 07-05 and the ledger say so openly, `requirements-completed` is `[]`, and no frontmatter was hand-edited. That is the correct handling and I confirm it.
- I do not classify this as `gaps_found`. Nothing failed or regressed, and the owner explicitly deferred the ten items (2026-10-04) instead of overriding them.
- It also cannot be `passed`, since ten human items exist (Phase 1: 6, Phase 2: 2, Phase 3: 2, counted from each report's frontmatter). That makes the status `human_needed`.
- QLT-01 should stay unchecked until those items are resolved or accepted, even though the ROADMAP criterion is met literally.

### Judgment on the tdd-red-evidence shim (question c)

- It does not change the outcome. The shim touched only scratchpad copies of the JUnit record. The checker's `name="..."` regex matches inside pytest's leading `classname="..."` attribute, which is a tool bug. Both the raw run and the shimmed run were disclosed.
- The RED itself is independently real. For 07-01 I re-ran the RED commit's test in a clean worktree and it failed on the eight floating jobs. For 07-02 the SUMMARY documents `assert 7 == 1` and `assert 5 == 1` against asyncio records, and the RED commit precedes the GREEN commit.
- Remaining weakness (informational): the gate verdict `RED_EVIDENCE_OK` is tooling-dependent for those two plans. It is recorded as a disclosed deviation, not hidden. If the upstream GSD checker is fixed, this can be dropped.

### Caveat on QLT-02 (honest reading)

- The named test `test_delete_device_own_subscription_never_sees_state_clear` is byte-identical between `v1.0.0` (`b6e9589`) and HEAD, and Phase 7 never saw it fail. It already carried the `own_warnings` scoping at v1.0.0. The Phase 5 report recorded the one failure at `test_manager.py:950`, before that scoping presumably landed in the same squashed PR. I cannot prove that ordering from the squash.
- What Phase 7 actually did: it diagnosed the defect class (an unscoped assertion that counts asyncio's slow-callback WARNING), removed it from the two siblings that still had it (`test_manager_breaker`, `test_modes`, plus a negative check in `test_hub_removal`), and made the class deterministic via the permanent probe. The probe turns a 1-in-N load flake into an every-run failure for any remaining unscoped assertion. The full suite is green with it on, 1490 times over three runs.
- That is a cause fix, not a retry. The residual risk is small but real: a different, unobserved flake source in that test cannot be excluded, but 50 of 50 under CPU load plus 6 green full runs make it unlikely.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/workflows/{ci,validate,release}.yml` | 8 jobs on `ubuntu-24.04` | VERIFIED | grep confirmed |
| `tests/test_repo_structure.py` | Directory-glob runner guard plus nine negative cases | VERIFIED | Guard passes at HEAD; fails at the RED commit |
| `tests/conftest.py::always_slow_event_loop` | Permanent autouse probe | VERIFIED | Present at line 49, wired via autouse, effective (full suite green with it) |
| `tests/log_helpers.py::own_warnings` | Own-logger scoping | VERIFIED | Used in the three touched tests |
| `07-PROOF.md` | Ledger with run URLs | VERIFIED | Spot-checked against GitHub; every claim I checked matched |
| Archived `0N-VERIFICATION.md`, N=1..4 | Regenerated with v2 digest | VERIFIED | Present, digest present, statuses read through the tool |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| Workflows | Guard test | glob of `.github/workflows/*.y*ml` | WIRED |
| `always_slow_event_loop` | every test | autouse, requests `enable_event_loop_debug` | WIRED |
| Archived reports | `verification status` | `covered_digest` over archived paths | WIRED (no stale reading) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Flake target plus three siblings plus guard under probe | `uv run --locked pytest -q -p no:cacheprovider` on those 5 files | 115 passed | PASS |
| Guard fails at its RED commit | worktree at `758e16b`, `-k pinned_runner` | 1 failed | PASS (RED real) |
| Archived verification gate | `gsd-tools verification status <dir> --pick status` for Phases 1 to 5 | human_needed, human_needed, human_needed, passed, stale (Phase 5) | PASS (matches ledger) |
| CI and release runs | `gh run view` on 37205596675, 37205721595, 37205851615, 37205956233, 37206309249 | all success, headSha as claimed | PASS |
| Release cleanup | `gh release list`, `git ls-remote --tags origin` | no `v1.0.1-rc1` | PASS |

I did not re-run the full three-run suite or the 50x stress loop. Both are ledger-only evidence, corroborated by the identical test counts in the CI logs.

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| QLT-01 | PARTIAL, human items open | The criterion as written is met. The plan gate is met for Phase 4 only. Ten checks are deferred to Phase 8 by owner decision. Keep unchecked. |
| QLT-02 | SATISFIED | Three local plus three CI full runs, cause fix plus probe, 50 of 50 stress, no retry or skip (see caveat) |
| QLT-03 | SATISFIED | All 8 jobs pinned, guard test, CI and Validate green, rc release run green end to end |

No orphaned requirements. REQUIREMENTS.md still shows all three as Pending and ROADMAP still shows Phase 7 as In Progress. That is bookkeeping for the orchestrator, and QLT-01 should not be ticked while the human items are open.

### Anti-Patterns Found

None. The debt-marker grep (TBD, FIXME, XXX) over the touched test and workflow files is empty. No retry, skip or xfail was added. `git diff d92b87f HEAD` shows no production-code change.

### Warnings (non-blocking)

1. **Phase 8 scope gap.** The ten deferred Phase 1 to 3 checks are not named in Phase 8's ROADMAP success criteria (UAT-01 to UAT-04). Unless Phase 8's scope is amended or the owner records overrides, they have no home and Phases 1 to 3 will stay `human_needed`.
2. **Pinned means a label, not an image.** `ubuntu-24.04` still rolls weekly (observed image `20260927.320.1`). The pin removes the 24.04 to 26.04 `ubuntu-latest` migration risk, nothing more. Mosquitto in CI is 2.0.18 from the archive while the local runs used 2.1.2; the CI runs cover the CI broker tier.
3. **Re-staling.** An edit to any covered file (`tests/conftest.py`, the touched tests, the workflows, or the manifest bump at milestone close) turns Phase 1 to 4 stale again. The 1.0.1 manifest bump will stale Phase 1; refresh with `verification.fingerprint`.
4. **Phase 5** still reads `stale` (same cause). It is out of QLT-01 scope but should be refreshed before milestone audit.
5. **`init.manager` is a vacuous gate** for Phases 1 to 4 because it only lists the active milestone's phases.

## Human Verification Required

### 1. Ten deferred Phase 1 to 3 checks

**Test:** Run the ten items listed in `07-PROOF.md` ("Open human-verification items") and in each archived report's `human_verification` frontmatter. Phase 1: HACS client install, EN/DE strings in the real frontend, action editor and validation banners, Repairs dialog of a failing action, the retained-versus-live chain on real HA plus broker, the core version of hassio-n2plus. Phase 2: select subentry flow in the real frontend, breaker loop on real Mosquitto and real HA. Phase 3: approval-request Markdown rendering, device-delete dialogs with hostile names.
**Expected:** Each passes with evidence; re-run the verifier for Phases 1 to 3 afterwards, or the owner records overrides.
**Why human:** Real frontend, real HACS client, or real HA core with a real retaining broker; no automated tier covers them.

## Gaps Summary

No gaps and no failed truth. All four ROADMAP success criteria are met as written, and the claims in the ledger that I spot-checked (runs, runner image, tag and release cleanup, status readings, RED commit) are accurate. The phase cannot be called `passed` because the plan-level gate for QLT-01 (all four archived reports `passed`) is open for Phases 1 to 3: ten real-environment checks are deferred to Phase 8 by owner decision, with no Phase 8 success criterion yet covering them. Recommended next step: amend Phase 8's scope (or record owner overrides) to cover the ten items, and leave QLT-01 unchecked until then.

---

_Verified: 2026-10-04_
_Verifier: Claude (gsd-verifier)_
