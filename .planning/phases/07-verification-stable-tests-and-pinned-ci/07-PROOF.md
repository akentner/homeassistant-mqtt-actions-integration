# Phase 7 Proof Ledger

Evidence ledger of Phase 7 (Verification, Stable Tests and Pinned CI). It is the source for the proof section of the
phase VERIFICATION (D-13). Plans 07-03, 07-04 and 07-05 append their sections below.

## QLT-02 stress proof (plan 07-02)

- **Date:** 2026-10-04 (run started 2026-10-04T12:57:58Z)
- **Head:** `f8e271e927061fc413d79f8afc793f566bc7e7b5` (all three 07-02 code commits included)
- **Test:** `tests/test_manager.py::test_delete_device_own_subscription_never_sees_state_clear`
- **Result line:** `repetitions passed: 50 of 50`
- **Wall-clock time:** 354 seconds
- **Load:** four busy loops (`while :; do :; done`, each bounded by `timeout 900`) and every repetition pinned with
  `taskset -c 0,1`, so spinners and test share two cores
- **Probe:** the permanent autouse fixture `always_slow_event_loop` (`tests/conftest.py`) was on during every
  repetition, so asyncio's slow-callback WARNING was present in every run
- **Cleanup:** no busy loop left running afterwards (`ps -eo args | grep -c '[w]hile :; do :; done'` printed 0)
- **Retries:** none; the loop stops at the first failure and none occurred
