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

## Local three-run proof (plan 07-03)

- **Date:** 2026-10-04 (loop ran 2026-10-04T13:07:32Z to 2026-10-04T13:13:11Z)
- **Head:** `0f9ad70a9fe54d28c73d31ca3d7f8acc577789aa` (contains the 07-01 and 07-02 commits; working tree clean before and during the runs)
- **Local broker:** `mosquitto version 2.1.2` (CI installs 2.0.18 from the Ubuntu 24.04 archive, so this does not prove the CI broker tier)
- **Command (each run):** `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run --locked pytest -q -p no:cacheprovider`, one invocation over the
  unit, broker and multi-instance tiers, no xdist, no marker filter, always-slow probe on
- **Retries:** none; three sequential runs, each accepted only on `N passed` with no skipped, failed, error or deselected

| Run | Summary line | Duration |
|-----|--------------|----------|
| 1 | `1490 passed in 111.42s (0:01:51)` | 111.42 s |
| 2 | `1490 passed in 111.42s (0:01:51)` | 111.42 s |
| 3 | `1490 passed in 110.26s (0:01:50)` | 110.26 s |

Runs 1 and 2 report the same duration to the hundredth of a second. They are separate runs (separate log files written
about 113 seconds apart); the equal figure is a coincidence of the rounded pytest timer.

- **Ruff:** `uv run ruff check .` printed `All checks passed!`; `uv run ruff format --check .` printed `91 files already formatted`
