---
phase: 08-real-instance-verification
plan: 07
subsystem: verification-bench
tags: [uat, human-verify, p2-1, p2-2, select-flow, circuit-breaker, repairs, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: pinned bench, owner tokens, 08-UAT.md ledger and recorder gate, check-frontend.sh (plans 08-01 to 08-06)
provides:
  - P2-1 and P2-2 recorded as pass in 08-UAT.md (blocks 11 and 12) with the owner's per-item statement and the build SHA
  - check-p22.sh (outside the repo) with modes p21, setup, run, teardown, clear-loop, peek
  - scripted proof that the breaker bounds the loop, survives a restart while paused, and is released by a hub reload
affects: [08-08, 08-09, 08-10]
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/p2-1/ (screens.txt, flow-precheck.txt, result.txt)
    - .planning/phases/08-real-instance-verification/08-evidence/p2-2/ (screens.txt, loop-config.txt, topic-capture.txt, issues.txt, log-a.txt, result.txt, verdict.txt)
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "Browser MCP unavailable to the subagent: the owner judged rendering and wording in their own browser; no screenshots"
  - "Task 3 was executed by the orchestrator, not the executor: the executor declined to treat a relayed owner answer as the owner's approval, and the owner had answered the orchestrator directly via its question prompt"
metrics:
  completed: 2026-10-06
status: complete
commits: 1
plan_head_before: d66b3202e61b4cb46231ac39b36291f1b76d993e
plan_head_after: f61a12e
---

# Phase 8 Plan 07: P2-1 and P2-2 Summary

P2-1 (select subentry flow) and P2-2 (breaker loop) are recorded as `pass` on build b7f52b34. The scripted parts stand on their own evidence; the owner judged rendering and wording in English and German. Both throwaway devices (`UAT P2-1`, `UAT Loop`) are removed and `check-frontend.sh cleanup` prints PASS.

## What was done

- **Task 1 (f61a12e, executor):** drove the select flow over the REST endpoints the frontend uses (`flow-precheck.txt`): menu entries by option count, edit, remove with the confirm menu, add, Remove hidden again at 2 options, retained config document holds `one` ("One edited"), `three`, `four`. Ran the breaker loop with `check-p22.sh run` (`verdict.txt` = PASS): one external ON gives exactly 6 live messages on the state topic (1 external plus 5 action publishes), one "Circuit breaker tripped" warning, the `circuit_breaker_{uuid}` issue listed, an external change while paused adds exactly +1 message, the pause survives `podman restart ha-a`, a hub entry reload releases it and the loop runs again and re-trips.
- **Task 2:** owner checkpoint. The owner answered the orchestrator directly: first "Noch nicht geprüft", then "Nur teilweise gesehen", then, per item, P2-1 = "Vollständig, ok" and P2-2 = "Vollständig, ok".
- **Task 3 (orchestrator):** `check-p22.sh teardown` removed `UAT P2-1` and `UAT Loop`; `check-frontend.sh cleanup`, `check-recorded.sh P2-1`, `check-recorded.sh P2-2`, `check-evidence-clean.sh` and `check-preflight.sh --quick` print PASS. Blocks 11 and 12, the table and the Summary counts (passed 9, issues 1, pending 4) are updated.

## Deviations from Plan

**1. [Rule 3 - Blocking] Browser MCP unavailable to the subagent.** No screenshots. P2-1 was driven over the flow REST API; the loop actions were set through the `edit_device` flow step instead of the action editor (`loop-config.txt` proves both `mqtt.publish` actions on the device's own state topic).

**2. Task 3 run by the orchestrator.** The executor stopped at the blocking-human gate because the owner's answers reached it only as an agent message. The owner had given them directly to the orchestrator, so the orchestrator recorded blocks 11 and 12. The ledger notes that the owner first answered "not checked yet" and "partially seen" before confirming both items completely when asked per item. Whether the owner performed every click path is not independently evidenced (as in 08-06).

**3. Profile language not verified.** The plan asks to confirm that the profile language is English again. That setting lives in the owner's browser profile and cannot be read by the bench scripts; it is not verified here.

**4. ha-b mirror is a `blocked_` issue, not an approval request.** `mqtt.publish` is a denied service for actions received from the broker, so the loop cannot run on ha-b at all, approved or not. This satisfies T-08-21 more strongly than planned; the plan text and the cleanup check expected `approval_{uuid}`.

**5. First breaker run discarded.** Its absolute message counts were off by one (a script counting bug, deltas were right); the run was repeated on a fresh device and the repeat is the recorded evidence.

**6. Orchestrator restarts.** ha-a and ha-b were restarted by the orchestrator at the owner's request between Task 1 and Task 3. It does not affect either result (`podman restart ha-a` was already part of the scripted check).

**7. Ledger.** No plan commit ledger file (sandbox refuses writes to the shared git directory); `commits:` is 1 (Task 1), the recording and this SUMMARY are further orchestrator commits.

## Bench edits (outside the repository)

- New: `~/ha-test/bin/check-p22.sh` (modes `p21`, `setup`, `run`, `teardown`, `clear-loop`, `peek`).
- `~/ha-test/bin/check-frontend.sh` extended: `prep` knows p2-1 and p2-2; `remove` also removes `UAT Loop`; `cleanup` checks the fixtures P21_ID and LOOP_ID, a leftover `circuit_breaker_` issue, `blocked_{id}` issues on ha-b and mirrors named `UAT Loop`.
- `~/ha-test/.fixtures-frontend.env` gained P21_ID and LOOP_ID (device uuids only).
- Throwaway devices `UAT P2-1` and `UAT Loop` were created and removed; `mosq` was not restarted; no token value was printed; ha-ws and production hosts were not used.

## Self-Check: PASSED

- Evidence files of p2-1 and p2-2 exist; commit f61a12e is merged into the phase branch.
- `check-recorded.sh P2-1`, `P2-2`, `check-frontend.sh cleanup`, `check-evidence-clean.sh` and `check-preflight.sh --quick` print PASS.
- `git status --porcelain -- custom_components tests .github` is empty.
