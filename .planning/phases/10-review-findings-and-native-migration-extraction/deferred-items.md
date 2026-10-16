# Phase 10 Deferred Items

Out-of-scope findings recorded during execution. They are not fixed in the plan that found them.

## From plan 10-04 (post-move mutation run)

Two glue methods of `NativeMigration` survived the post-move mutation run (`mutation/post-move.tsv`). Both gaps exist
before the move as well. At the base `dbfbf81`, the same statements inline in `Manager` were deleted one at a time,
and the full suite stayed green both times (1735 passed, 2 xfailed). The move lost no guard. D-10 forbids a new test
in the move plan, so the pins are left to a later plan.

| Glue method | Pre-move statement | Unpinned behavior |
|---|---|---|
| `NativeMigration.defer_for_run` | `Manager._follow_native_status`: `self._legacy_this_run.add(device.device_id)` | A running legacy mirror whose owner turns native has to stay legacy until the scheduled reload (D-12, T-5-09). Without the add, it reads native in that window. |
| `NativeMigration.forget` | `Manager._forget_native`: the `_legacy_this_run` and `_clear_unconfirmed` discards | Suppose a device's takeover was deferred in this run, and the device is then deleted or released here. If its id comes back in the same run, as a re-added device or as a mirror, it has to start clean. Without the discards it stays legacy for the rest of the run. |

Suggested pins (later plan, test-only): for the first, a mirror flips to native while it runs, and `is_native` stays
False until the reload. For the second, a deferred device is released locally, and the mirror that follows it is
native in the same run once its owner is native.
