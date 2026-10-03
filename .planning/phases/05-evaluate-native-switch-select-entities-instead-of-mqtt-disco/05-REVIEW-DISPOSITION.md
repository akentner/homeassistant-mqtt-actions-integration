---
phase: 05
review: 05-REVIEW.md
---

# Review disposition (phase 05)

| Finding | Severity | Disposition |
|---------|----------|-------------|
| CR-01 adopting a native mirror deletes its native entities | Critical | fixed (225557a): the companion device is kept for a native mirror, no early device-changed signal, registry entries rebound to the new subentry; test pins registry id, entity id, area, name and no removal events |
| WR-01 Store saved before registries flush | Warning | fixed (8bef861): both registries are flushed before the retained clear and the marker handling (private registry store, best effort) |
| WR-02 failure after the move demotes the device to legacy | Warning | fixed (23a1692): a moved device stays native for the run, only the clear is retried (republish) and the id stays pending; after an exception the registry decides |
| WR-03 cutover gate relies on unauthenticated heartbeats | Warning | fixed in part (16a972c): a capability claim cannot replace a blocking legacy row and a saturated roster blocks. Open by design: a forged retained `offline` availability still lifts a block, and a peer cleanly offline at the 5 s check is not waited for; needs an owner decision (ACL, settle time) |
| WR-04 duplicate branch deletes the user-customized entry | Warning | fixed (70092ff): the customized entry wins, otherwise the older one; the old pinning test was replaced deliberately |
| IN-01 unreachable code in `_follow_native_status` | Info | fixed (this commit): dead tail and stale docstring removed |
| IN-02 `with_native_marker` drops the flag near the size limit | Info | skipped: needs a design decision (separate persisted native set or a size headroom), not trivially safe |
| IN-03 takeover can race a boot-time retained replay | Info | skipped: needs a design decision (publish order for retried devices, settling of the discovery queue); moderate confidence in the finding |
| IN-04 tests do not pin identity across adoption and cutover reload | Info | fixed (adoption part in 225557a, end-to-end reload test in 950a6c0) |
