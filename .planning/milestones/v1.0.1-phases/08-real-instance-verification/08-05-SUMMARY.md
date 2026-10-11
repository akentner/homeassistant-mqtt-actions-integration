---
phase: 08-real-instance-verification
plan: 05
subsystem: verification-bench
tags: [uat, uat-01, straggler, v0.1.0, mosquitto-acl, home-assistant, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: pinned bench, uat_probe user, owner tokens, 08-UAT.md ledger and recorder gate, UAT Marker fixture (plans 08-01 to 08-04)
provides:
  - UAT-01 recorded as pass under the owner wording UAT01-WORDING (observation) with evidence from a real mixed fleet (v0.1.0 next to two native instances)
  - ha-c bench instance (v0.1.0, byte-identical to the tag) with its own MQTT user, ACL block and token, now stopped
  - ha-c-setup.sh (resumable), check-hac.sh (identity, ready, stopped), check-uat01.sh (run)
affects: [08-06, 08-07, 08-08, 08-09, 08-10]
tech-stack:
  added: []
  patterns:
    - "scripted onboarding of a fresh HA instance (onboarding API, auth/token, long-lived token over the guard)"
    - "wording policy coded as a variable before the observation (UAT01_MODE_SELECT)"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/uat-01/ (11 files)
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "UAT01-WORDING = observation (owner, chat, 2026-10-06): the v0.1.0 companion mode selects are recorded under Observations and do not fail UAT-01"
  - "The two core bench issues of a fresh instance (country_not_configured, yaml_still_present_after_migration) are allowed explicitly in the Repairs criterion and listed in the evidence"
metrics:
  duration: about 25 min wall clock
  completed: 2026-10-06
status: complete
commits: 3
plan_head_before: 15711836abec7865692498f9ef0c75020606fb1c
plan_head_after: c0a1ffa48b2e76ac95a6dd431040314aca54f718
actuals:
  tokens: 40000
  tasks: 3
  commits: 3
---

# Phase 8 Plan 05: UAT-01 straggler v0.1.0 instance Summary

UAT-01 is recorded as `pass`: with the byte-identical v0.1.0 component on a third instance (ha-c) next to the native ha-a and ha-b, a marker state change runs its actions exactly once on all three, ha-c holds no `mqtt`-platform row and no switch or button for the seven migrated devices, and no error was raised; the seven v0.1.0 mode selects are recorded as an observation per the owner's wording.

## What was done

- **Task 1 (2339345):** recorded `UAT01-WORDING` (option `observation`, 2026-10-06, taken from the owner's chat answer relayed by the orchestrator) under Owner decisions and rewrote the `expected:` line of block 1. No checkpoint was returned.
- **Task 2 (6081d98):** set up ha-c. `check-hac.sh identity` compares all 26 `.py` files with `git show v0.1.0:...` and the manifest (0.1.0): all equal. Container from image tag `2026.9` with the flags of ha-b (host network, TZ, restart no, not privileged), port 8125, the v0.1.0 folder mounted read-only; `deps` copied from ha-b (it was empty). Onboarding ran headless on the first try (`/api/onboarding/users`, `/auth/token`, the remaining onboarding steps, long-lived token over `ha-test-guard`); owner password and token are in `~/ha-test/.ha-c-owner` and `~/ha-test/.token-c`, both mode 0600 and never printed. Broker: user `ha_three` plus a block copied from the documented example (the existing `ha_two` pattern, without the export row and without the availability line first); the MQTT entry was created through the flow API (protocol 5); the hub through the flow API (`Test HA Three v0.1.0`); the instance id `f292c620-c6e8-4563-ae3c-38f64d4b344e` was read with `jq` (that field only) and added as the availability write line; after SIGHUP and a restart of ha-c the second client read availability `online` and heard a heartbeat. The marker mirror was approved through the Repairs fix flow API; all other mirrors stay unapproved.
- **Task 3 (c0a1ffa):** `check-uat01.sh run` with expectations and the policy coded first.
  - Outcome 1: two marker changes on ha-a (60 s after each): delta +1 on ha-a, ha-b and ha-c for each, 0 for the other text on ha-c, marker back at its start state.
  - Outcome 2: from the retained config topics seven device ids; ha-c registry has 0 `mqtt` rows, no row with unique id = device id or `{id}_test_*`, no switch or button of `mqtt_actions` for those devices, no switch state; 7 of 7 mode selects (`select.{name}_mode`) listed as observation.
  - Outcome 3: 0 ERROR or CRITICAL naming `custom_components.mqtt_actions` or `homeassistant.components.mqtt` in the whole container output of ha-c and 0 on ha-a and ha-b since ha-c's hub entry was created; Repairs on ha-c: the approval request for Lampe Test plus the two core bench artifacts; no retained topic under `homeassistant/`; new retained topics against the preflight snapshot: only ha-c's availability and the marker's config and state (the marker postdates the snapshot).
  - Stop: `podman stop -t 60 ha-c`; the retained availability still read `online`, cleared with an empty retained publish; `check-hac.sh stopped` PASS.
  - Block 1 recorded; `check-recorded.sh UAT-01`, `check-hac.sh stopped`, `check-preflight.sh --quick` and `check-evidence-clean.sh` over `08-evidence` print PASS.

## Deviations from Plan

**1. [Rule 3 - Blocking] HA 2026.9 reverted ha-c's HTTP port.** The YAML `http:` block of a fresh instance is stored as a pending config; unconfirmed after 5 minutes it was dropped, HA restarted with the stable default port 8123 (held by ha-a) and ended in recovery mode (20:08). The first `check-uat01.sh run` stopped on its `check-hac.sh ready` gate with ABORT (bench problem, no observation, its verdict file was overwritten by the real run). Fix: stopped ha-c, promoted pending to stable in `~/ha-test/c/.storage/http` (backup `http.bak-phase8-05`), started it, `check-hac.sh ready` PASS; scripted as `ha-c-setup.sh --step 9`. The v0.1.0 setup and the marker approval survived; the UAT run happened entirely in the fixed process lifetime.

**2. [Rule 1 - Bug in plan text] Marker change order.** The plan names `switch.turn_off` then `switch.turn_on`; the marker was `off`, so a first turn_off would change nothing. The script reads the start state and goes to the opposite state first (turn_on, then turn_off). Deltas are +1 per change as specified.

**3. [Rule 1 - Bug in plan text] Flow API and form shape.** The plan names `/api/config_entries/flow`; the working path on 2026.9.4 is `/api/config/config_entries/flow` (the same prefix as in 08-03 and 08-04). The mqtt broker form needs `protocol` at the top level and a required `other_settings` section (`set_client_cert`, `set_ca_cert`, `transport`); the first call without it returned a validation error, the second created the entry. The first call left one open flow, aborted by hand.

**4. Repairs criterion made explicit.** "No Repairs issue other than approval requests" holds for the integration (one approval issue, the marker's is gone), but a fresh instance also raises `homeassistant/country_not_configured` and `http/yaml_still_present_after_migration` (ha-b has the latter as well). Both are unrelated to the integration; the check allows exactly those two ids and lists all issues in `issues-c.txt`.

**5. ACL block follows the documented example.** The `ha_two` block pattern includes `homeassistant/#`; ha_three has it as well (without the export row it does not need), so a straggler that published Discovery would really arrive and the "no new homeassistant topic" check is meaningful. The plan text's shorter list in the fixture facts omitted it.

**6. Plan-commit ledger.** The sandbox refuses writes to the shared git directory from the worktree, so no ledger file; `commits:` is measured as `git rev-list --count 1571183..HEAD` = 3 at write time (the base verified by `git merge-base` at start). The SUMMARY commit follows as a fourth.

**7. Broker password on one command line.** The MQTT flow body, which carries the throwaway bench broker password of `ha_three`, is passed to `ha-test-guard rest` as an argument (the guard has no stdin mode); it is visible in the process list for a moment on this single-user machine. The guard was not changed.

## Findings

- UAT-01 passes under the wording the owner chose. Strict reading would have failed it by design (7 mode selects).
- A v0.1.0 instance stopped cleanly keeps its retained availability `online` (observation, no gap raised); cleared by hand for Pitfall 10.
- Not an integration finding: HA 2026.9 pending HTTP config on a fresh instance (see deviation 1).
- No product code, tests or workflows changed (`git status --porcelain -- custom_components tests .github` empty).

## Bench edits (outside the repository)

- New: `~/ha-test/c/` (configuration.yaml with port 8125 and the INFO logger block, `deps`, HA state), `~/ha-test/bin/ha-c-setup.sh`, `check-hac.sh`, `check-uat01.sh`, `~/ha-test/.token-c` and `~/ha-test/.ha-c-owner` (0600), container `ha-c` (stopped, not removed).
- Edited: `~/ha-test/mosquitto/passwd` (user `ha_three`), `~/ha-test/mosquitto/acl` (`ha_three` block with ha-c's own availability line; copy before the edit `acl.bak-phase8-05`), `~/ha-test/.mqtt-uat.env` (variable `UAT_HA_THREE_PW`, mode 0600 kept), `~/ha-test/c/.storage/http` (pending promoted, backup `http.bak-phase8-05`).
- Broker: SIGHUP only (`mosq` StartedAt unchanged, preflight PASS); the empty retained publish cleared one topic (ha-c's availability). ha-a and ha-b were not restarted; their state was changed only by the two marker changes (state back to `off`). No token value was printed, ha-ws and production hosts were not touched.
- Tokens: `.token-c` joins `.token-a` and `.token-b` in the list the owner revokes after the phase (08-UAT.md Bench state).

## Known Stubs

None. No product code changed.

## Threat Flags

None beyond the plan's register. T-08-13 (own ACL line read back before the check), T-08-14 (secrets only in `~/ha-test`, evidence scan PASS, only `instance_id` and `created_at` read from `core.config_entries`), T-08-15 (no new Discovery topic, topic diff in `broker-topics.txt`) and T-08-SC (image tag 2026.9, component verified by hash; ha-b's `deps` folder was empty, so nothing was copied, and I did not audit what the first start of ha-c fetched) were applied.

## Self-Check: PASSED

- `uat-01` evidence (11 files) and this SUMMARY exist; commits 2339345, 6081d98 and c0a1ffa exist on the branch.
- `check-recorded.sh UAT-01`, `check-hac.sh stopped`, `check-preflight.sh --quick` and `check-evidence-clean.sh` over `08-evidence` all print PASS.
