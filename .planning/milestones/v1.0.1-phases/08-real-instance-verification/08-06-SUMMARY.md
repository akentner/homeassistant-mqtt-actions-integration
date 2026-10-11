---
phase: 08-real-instance-verification
plan: 06
subsystem: verification-bench
tags: [uat, human-verify, p1-3, p1-4, p3-2, frontend, repairs, delete-dialog, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: pinned bench, uat_probe user, owner tokens, 08-UAT.md ledger and recorder gate, UAT Marker fixture (plans 08-01 to 08-05)
provides:
  - P1-3, P1-4 and P3-2 recorded as pass in 08-UAT.md (blocks 7, 8, 14) with the owner's statement verbatim and the build SHA
  - check-frontend.sh (outside the repo) with modes baseline, fixtures, trigger-p14, prep, readback, remove, cleanup
  - broker read-back that both hostile-named devices leave no retained config topic after their deletes
affects: [08-07, 08-08, 08-09, 08-10]
tech-stack:
  added: []
  patterns:
    - "owner-judged frontend items with a bench fixture builder and a baseline-diff cleanup gate"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/p1-3/ (browser.txt, screens.txt, result.txt)
    - .planning/phases/08-real-instance-verification/08-evidence/p1-4/ (screens.txt, result.txt)
    - .planning/phases/08-real-instance-verification/08-evidence/p3-2/ (screens.txt, deletes.txt, readback-before-delete.txt, topics-after-delete.txt, result.txt)
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "Browser MCP unavailable: the plan's fallback (planner decision 2) was used, so the owner performed the click paths and there are no screenshots"
metrics:
  duration: about 25 min active, plus the owner checkpoint
  completed: 2026-10-06
status: complete
commits: 2
plan_head_before: 93aa09ad0dfe07f5e675c3d2018ef04ef26888b3
plan_head_after: d7bb9c3
actuals:
  tokens: 30000
  tasks: 3
  commits: 3
---

# Phase 8 Plan 06: P1-3, P1-4 and P3-2 frontend checks Summary

The owner approved P1-3 (action editor and banners), P1-4 (Repairs dialog of a failing action) and P3-2 (delete dialogs with a hostile name) with the statement "approved P1-3 P1-4 P3-2"; all three are recorded as `pass` on build b7f52b34, the throwaway devices are gone and both hostile-named devices read back with no retained config topic. `commits:` is 2 measured at write time (`git rev-list --count 93aa09a..HEAD`); this SUMMARY is the third.

## What was done

- **Task 1 (3613c27):** wrote `~/ha-test/bin/check-frontend.sh`, took the baseline of ha-a (3 owned devices, 7 retained config topics), and found no browser MCP in the executing session. `browser.txt` records `unavailable` and the allowed origins; each `screens.txt` holds the owner click path. Claude built the fixtures that need no browser: `UAT P1-4` (import, action `uat_missing.nothing`, toggled on, Repairs issue `action_failed_{uuid}` listed) and the two P3-2 devices named with backticks and a bold tag (inert `system_log.write`). It also pre-checked the P1-3 data path through the subentry flow REST API on ha-a (invalid action gives `invalid_actions` with field onChangeToOn, a literal `device_id` gives `device_id_warning` on the first submit; flow aborted, nothing saved).
- **Task 2:** checkpoint, answered by the owner in chat: "approved P1-3 P1-4 P3-2".
- **Task 3 (d7bb9c3):** `readback p3-2` first found both hostile devices still present with their retained config topics (`readback-before-delete.txt`); the owner had judged the dialogs but not confirmed the deletes. Claude deleted them over the guard through the same paths: the integration's reconfigure flow (menu step `delete_device`: name placeholder `UAT P3-2a \`code\` \<b\>bold\</b\>` markdown-escaped plain text, count 1, then `delete_confirmed`, abort reason `device_deleted`) and the WebSocket `config_entries/subentries/delete` for the generic path. After 20 s `topics-after-delete.txt` shows both retained topics empty and both subentries gone. `remove` deleted `UAT P1-4`; `cleanup`, `check-marker.sh approved`, `check-recorded.sh` for the three items, `check-evidence-clean.sh` and `check-preflight.sh --quick` print PASS. Blocks 7, 8, 14, the table and the Summary counts (passed 7, issues 1, pending 6) are updated.

## Deviations from Plan

**1. [Rule 3 - Blocking] Browser MCP unavailable.** The chrome-devtools tools are not exposed to the subagent and tool search is disabled. Per the plan's fallback no screenshots exist; the owner performed the click paths (their statement is the evidence). Nothing was navigated to, `/profile/security` was never touched.

**2. [Plan adaptation] P1-4 fixture by import.** `UAT P1-4` was created with `mqtt_actions.import_devices` instead of the add dialog (the dialog is covered by P1-3). The Repairs issue was listed before the owner looked live. The orchestrator restarted ha-a and ha-b afterwards (user request); the issue was gone at cleanup, which does not affect the approved result.

**3. [Plan adaptation] P3-2 deletes done by Claude.** The plan has Claude delete and screenshot; with no browser the devices were left for the owner, who judged the dialogs but did not confirm the deletes. Claude performed them headless through the same two code paths (see Task 3). The owner's judgement of the rendering is unchanged; the deletion and the retained-topic read-back are API evidence, and `result.txt` and the ledger note say so.

**4. Observation, not a deviation.** At recording time no `UAT P1-3a` or `UAT P1-3b` device existed on ha-a, so there is no device trace of the owner's save steps; the pass rests on the owner's statement.

**5. Extra modes in `check-frontend.sh`.** `baseline`, `fixtures`, `trigger-p14`, `readback` and `remove` were added beyond `prep` and `cleanup`; `cleanup` also checks ha-b for leftover mirrors and approval issues of the throwaway devices.

**6. Sandbox and ledger.** The sandbox refuses commands that pass runtime-computed values (for example `$EID`) to `ha-test-guard`, so literal ids and scripts were used. No plan commit ledger file (it refuses writes to the shared git directory); `commits:` is measured with `git rev-list --count 93aa09a..HEAD`.

## Findings

- The integration's own delete step shows the name escaped (placeholder `\`code\` \<b\>bold\</b\>`) and `count` 1 with one online peer.
- P1-3 pre-check data path matches the unit-test twins on the real build.
- No product code, tests or workflows changed (`git status --porcelain -- custom_components tests .github` empty).

## Bench edits (outside the repository)

- New: `~/ha-test/bin/check-frontend.sh`, `~/ha-test/.frontend-baseline.txt`, `~/ha-test/.fixtures-frontend.env` (mode 600, device uuids only).
- Broker and instances: throwaway devices `UAT P1-4`, `UAT P3-2a`, `UAT P3-2b` were created on ha-a (mirrors on ha-b, unapproved) and all removed; retained config topics are back to the 7 of the baseline. The marker and the three original devices were untouched (`check-marker.sh approved` PASS). No token was printed, ha-ws and production hosts were not used.

## Known Stubs

None. No product code changed.

## Threat Flags

None beyond the plan's register. T-08-16 (inert names and actions, every throwaway device removed and read back empty), T-08-17 (no screenshots, no security page, evidence scan PASS) and T-08-18 (no browser navigation at all) were applied.

## Self-Check: PASSED

- Evidence files of p1-3, p1-4 and p3-2 and this SUMMARY exist; commits 3613c27 and d7bb9c3 exist on the branch.
- `check-recorded.sh P1-3`, `P1-4`, `P3-2`, `check-frontend.sh cleanup`, `check-evidence-clean.sh` and `check-preflight.sh --quick` print PASS.
