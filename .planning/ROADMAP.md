# Roadmap: MQTT Actions Integration

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-10-03)
- ✅ **v1.0.1 Hardening** — Phases 6-8 (closed 2026-10-11 with accepted gap, not released)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-10-03</summary>

- [x] Phase 1: Walking Skeleton - Installable Switch (6/6 plans) — completed 2026-09-29
- [x] Phase 2: Select Devices and Reliable Execution (5/5 plans) — completed 2026-09-30
- [x] Phase 3: Trust, Central Config and Ownership (8/8 plans) — completed 2026-10-02
- [x] Phase 4: Operations, Recovery and Release (14/14 plans) — completed 2026-10-03
- [x] Phase 5: Evaluate native switch/select entities instead of MQTT Discovery (9/9 plans) — completed 2026-10-03

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.0.1 Hardening (Phases 6-8) — CLOSED 2026-10-11 (accepted gap ACCEPTED-GAP-V101, no release)</summary>

- [x] Phase 6: Native Entity Residual Fixes (2/2 plans) — completed 2026-10-04
- [ ] Phase 7: Verification, Stable Tests and Pinned CI (5/5 plans) — executed, verification human_needed, accepted as tech debt
- [x] Phase 8: Real-Instance Verification (18/18 plans) — completed 2026-10-11

Full details: [milestones/v1.0.1-ROADMAP.md](milestones/v1.0.1-ROADMAP.md)

</details>

## Backlog

### Phase 999.1: Per-instance local actions on mirrored devices (followers add own actions, relates to MAP-01) (BACKLOG)

**Goal:** [Captured for future planning] A follower instance can add its own local actions to a mirrored device, on top of the owner's document (for example different entities per instance). Found during Phase 3 UAT: mirrors are read-only today.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
