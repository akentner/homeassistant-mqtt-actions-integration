# Phase 9.1 - Deferred Items

Out-of-scope discoveries logged during execution. Not fixed here (scope boundary).

## From plan 09.1-01

### Pitfall 8 observed in the harness: a follower's mirror takeover defers while replayed buttons are loaded

- **Found during:** Task 2, `test_a_follower_removes_its_disabled_twin_and_publishes_nothing`
- **What:** On a follower, every start re-attempts the takeover of a native mirror whose legacy MQTT device exists
  (`manager._async_native_takeover`, the `mirrors` list). After a live replay, the guard disables only the switch, so
  the replayed test buttons stay enabled and loaded. `takeover.async_take_over` then waits `TAKEOVER_UNLOAD_TIMEOUT`
  (10 s) and returns DEFERRED. The mirror is legacy for that run, `_native_device_ids()` excludes it, and the
  quiet-period catch never sees it, so the rows and the legacy device stay.
- **Log signature:** `Takeover of device %r postponed: its legacy entities are still loaded` (`takeover.py`), followed by
  `The native takeover of a device is postponed to the next start`.
- **Status:** Pre-existing (research Pitfall 8). Not caused by the 09.1-01 fix. The harness test models the round-2
  state (all three rows integration-disabled and rediscovered), where the takeover returns DONE ("keeps its MQTT
  device") and the catch removes the rows.
- **Relevance for plan 09.1-05:** On the bench, grep the round logs of the follower instance for the postponed line.
  If it shows up, UAT-02 E1 to E3 on that instance fail for this reason and not for the CR-01 skip. Record it as an
  observation; changing the mirror takeover is out of scope for 9.1 (D-07 boundary, `async_take_over` unchanged).
